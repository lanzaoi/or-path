#!/usr/bin/env python3
"""Max Clique / Max Independent Set solver — NetworkX exact + OR-Tools CP-SAT.

Two classic NP-hard graph problems, always solved together (complement
duality):

* ``max_clique``              — maximum clique omega(G): a largest set of
  vertices pairwise adjacent in G.
* ``max_independent_set``     — maximum independent set alpha(G): a largest
  set of vertices pairwise non-adjacent in G.

Methods:
* ``networkx`` — ``nx.algorithms.clique.max_weight_clique`` (exact Tomita
  branch-and-bound); the MIS side is solved on the complement graph.
* ``cpsat``    — OR-Tools CP-SAT exact formulations: pairwise
  ``x[u] + x[v] <= 1`` for non-adjacent pairs (clique), and
  ``y[u] + y[v] <= 1`` per edge (independent set).
* ``hybrid``   — NetworkX exact first; CP-SAT fallback if NetworkX raises.
  The complement-duality cross-check always runs CP-SAT on the complement
  graph independently of the primary method.

Inputs:
* ``dimacs_path`` — DIMACS ``.col`` file (default:
  ``fixtures/benchmarks/dimacs/myciel3.col``, 11 vertices / 20 edges,
  omega = 2, alpha = 5)
* ``graph_data``  — edge list ``[[u, v], ...]`` (or ``{"edges": [...]}``)
* ``G``           — a pre-built ``networkx.Graph``

Output follows the OR-Path "Numbers Truth" envelope (ADR-0002):
``problem_id, problem_class="max_clique", mode, status, objective, solver,
source, num_nodes, num_edges, clique_nodes, max_clique_size,
independent_set_nodes, max_independent_set_size,
complement_duality_verified, nodes, edges, meta``. The independent
validator (``validators/extended_solvers.py``) re-derives clique/MIS
validity, objective consistency, duality, and optimality from the envelope
alone — no solver is re-run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import networkx as nx
from ortools.sat.python import cp_model

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

DEFAULT_FIXTURE = _ROOT / "fixtures" / "benchmarks" / "dimacs" / "myciel3.col"
DEFAULT_SOLVER = "networkx-cpsat-clique"
METHODS = ("networkx", "cpsat", "hybrid")
MODES = ("max_clique", "max_independent_set")


def _sort_key(x: Any) -> tuple[str, Any]:
    return (str(type(x)), x)


def _resolve_dimacs_path(path: str | Path | None) -> Path:
    """Resolve a DIMACS path against cwd, then the install root."""
    raw = str(path or DEFAULT_FIXTURE)
    p = Path(raw)
    if p.is_file():
        return p
    for base in (_ROOT, Path.cwd()):
        cand = base / raw
        if cand.is_file():
            return cand
        cand_dimacs = base / "fixtures" / "benchmarks" / "dimacs" / raw
        if cand_dimacs.is_file():
            return cand_dimacs
        if not raw.endswith(".col"):
            cand_col = base / "fixtures" / "benchmarks" / "dimacs" / f"{raw}.col"
            if cand_col.is_file():
                return cand_col
    raise FileNotFoundError(f"DIMACS instance not found: {raw}")


def load_dimacs(path: str | Path | None = None) -> nx.Graph:
    """Parse a DIMACS ``.col`` file into a NetworkX graph (1-based nodes)."""
    resolved = _resolve_dimacs_path(path)
    g = nx.Graph()
    with resolved.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("c"):
                continue
            if line.startswith("p"):
                parts = line.split()
                if len(parts) >= 3 and parts[1] == "edge":
                    n = int(parts[2])
                    g.add_nodes_from(range(1, n + 1))
            elif line.startswith("e"):
                parts = line.split()
                if len(parts) >= 3:
                    g.add_edge(int(parts[1]), int(parts[2]))
    if g.number_of_nodes() == 0:
        raise ValueError(f"DIMACS file declares no vertices: {resolved}")
    return g


def _graph_from_data(graph_data: Any) -> nx.Graph:
    """Build a graph from an edge list or a dict carrying ``edges``."""
    if isinstance(graph_data, nx.Graph):
        return graph_data
    if isinstance(graph_data, dict):
        edges = graph_data.get("edges") or []
        nodes = graph_data.get("nodes")
    else:
        edges = graph_data or []
        nodes = None
    g = nx.Graph()
    if nodes:
        g.add_nodes_from(nodes)
    for e in edges:
        u, v = (int(e[0]), int(e[1]))
        g.add_edge(u, v)
    if g.number_of_nodes() == 0 and not edges:
        raise ValueError("graph_data produced an empty graph")
    return g


def _build_graph(
    dimacs_path: str | Path | None = None,
    graph_data: Any | None = None,
    G: nx.Graph | None = None,
) -> tuple[nx.Graph, str]:
    """Resolve the input surface into (graph, source_label)."""
    if G is not None:
        return G, "networkx-graph"
    if graph_data is not None:
        return _graph_from_data(graph_data), "graph_data"
    resolved = _resolve_dimacs_path(dimacs_path)
    return load_dimacs(resolved), f"dimacs:{resolved.name}"


def _nx_max_clique(G: nx.Graph) -> tuple[list[Any], int]:
    """NetworkX exact maximum clique (Tomita branch-and-bound)."""
    nodes = sorted(G.nodes(), key=_sort_key)
    if not nodes:
        return [], 0
    clique, _weight = nx.algorithms.clique.max_weight_clique(G, weight=None)
    chosen = sorted((int(v) if isinstance(v, (int, float)) else v) for v in clique)
    return chosen, len(chosen)


def _nx_max_independent_set(G: nx.Graph) -> tuple[list[Any], int]:
    """NetworkX exact maximum independent set via the complement graph."""
    nodes = sorted(G.nodes(), key=_sort_key)
    if not nodes:
        return [], 0
    g_comp = nx.complement(G)
    clique, _weight = nx.algorithms.clique.max_weight_clique(g_comp, weight=None)
    chosen = sorted((int(v) if isinstance(v, (int, float)) else v) for v in clique)
    return chosen, len(chosen)


def _cpsat_max_clique(
    G: nx.Graph,
    time_limit: float,
) -> tuple[str, list[Any] | None, int | None]:
    """CP-SAT exact maximum clique.

    Pairwise ``x[u] + x[v] <= 1`` for every non-adjacent pair; maximise
    ``sum(x)``. Returns (solver_status_name, clique_nodes, size).
    """
    nodes = sorted(G.nodes(), key=_sort_key)
    n = len(nodes)
    if n == 0:
        return "OPTIMAL", [], 0

    model = cp_model.CpModel()
    x = {v: model.NewBoolVar(f"x_{v}") for v in nodes}
    for i in range(n):
        for j in range(i + 1, n):
            u, v = nodes[i], nodes[j]
            if not G.has_edge(u, v):
                model.Add(x[u] + x[v] <= 1)
    model.Maximize(sum(x.values()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.1, float(time_limit))
    status_code = solver.Solve(model)
    status = solver.StatusName(status_code)
    if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return status, None, None
    chosen = [
        int(v) if isinstance(v, (int, float)) else v
        for v in nodes
        if solver.Value(x[v]) == 1
    ]
    return status, chosen, len(chosen)


def _cpsat_max_independent_set(
    G: nx.Graph,
    time_limit: float,
) -> tuple[str, list[Any] | None, int | None]:
    """CP-SAT exact maximum independent set.

    Pairwise ``y[u] + y[v] <= 1`` per edge; maximise ``sum(y)``. Returns
    (solver_status_name, mis_nodes, size).
    """
    nodes = sorted(G.nodes(), key=_sort_key)
    n = len(nodes)
    if n == 0:
        return "OPTIMAL", [], 0

    model = cp_model.CpModel()
    y = {v: model.NewBoolVar(f"y_{v}") for v in nodes}
    for u, v in G.edges():
        model.Add(y[u] + y[v] <= 1)
    model.Maximize(sum(y.values()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.1, float(time_limit))
    status_code = solver.Solve(model)
    status = solver.StatusName(status_code)
    if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return status, None, None
    chosen = [
        int(v) if isinstance(v, (int, float)) else v
        for v in nodes
        if solver.Value(y[v]) == 1
    ]
    return status, chosen, len(chosen)


def _solve_side(
    G: nx.Graph,
    kind: str,
    method: str,
    time_limit: float,
) -> tuple[str, list[Any], int]:
    """Solve one side (``clique`` or ``mis``) with the requested method.

    Returns (status_name, nodes, size). ``hybrid`` tries NetworkX first
    and falls back to CP-SAT on any exception.
    """
    if method == "networkx":
        if kind == "clique":
            nodes, size = _nx_max_clique(G)
        else:
            nodes, size = _nx_max_independent_set(G)
        return "OPTIMAL", nodes, size
    if method == "cpsat":
        if kind == "clique":
            status, nodes, size = _cpsat_max_clique(G, time_limit)
        else:
            status, nodes, size = _cpsat_max_independent_set(G, time_limit)
        if nodes is None:
            raise RuntimeError(f"CP-SAT {kind} failed with status {status}")
        return status, nodes, size
    # hybrid: NetworkX exact first, CP-SAT fallback
    try:
        if kind == "clique":
            nodes, size = _nx_max_clique(G)
        else:
            nodes, size = _nx_max_independent_set(G)
        return "OPTIMAL", nodes, size
    except Exception:
        if kind == "clique":
            status, nodes, size = _cpsat_max_clique(G, time_limit)
        else:
            status, nodes, size = _cpsat_max_independent_set(G, time_limit)
        if nodes is None:
            raise RuntimeError(f"CP-SAT {kind} fallback failed with status {status}")
        return status, nodes, size


def solve_max_clique(
    dimacs_path: str | Path | None = None,
    graph_data: Any | None = None,
    G: nx.Graph | None = None,
    method: str = "hybrid",
    mode: str = "max_clique",
    time_limit: float = 30.0,
    problem_id: str | None = None,
) -> dict[str, Any]:
    """Solve a max-clique / max-independent-set instance (ADR-0002 envelope).

    ``method`` ∈ {'networkx', 'cpsat', 'hybrid'}; default ``hybrid``.
    ``mode`` ∈ {'max_clique', 'max_independent_set'} selects which side
    feeds ``objective`` (omega(G) or alpha(G)); both sides are always
    computed and the complement-duality cross-check always runs.
    """
    method_l = (method or "hybrid").lower().strip()
    if method_l not in METHODS:
        raise ValueError(f"unknown method {method!r}; expected one of {METHODS}")
    mode_l = (mode or "max_clique").lower().strip()
    if mode_l not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")

    G, source_label = _build_graph(dimacs_path=dimacs_path, graph_data=graph_data, G=G)
    nodes = sorted(G.nodes(), key=_sort_key)
    if all(isinstance(u, int) and isinstance(v, int) for u, v in G.edges()):
        edges = sorted(
            ([int(u), int(v)] for u, v in G.edges()),
            key=lambda e: (e[0], e[1]),
        )
    else:
        edges = sorted(
            (
                (
                    [int(u), int(v)]
                    if isinstance(u, (int, float)) and isinstance(v, (int, float))
                    else [u, v]
                )
                for u, v in G.edges()
            ),
            key=lambda e: (_sort_key(e[0]), _sort_key(e[1])),
        )
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    if problem_id is None:
        if dimacs_path is not None or (graph_data is None and G is None):
            problem_id = f"max_clique_{_resolve_dimacs_path(dimacs_path).stem}"
        else:
            problem_id = "max_clique_instance"

    if n_nodes == 0:
        clique_nodes, omega = [], 0
        mis_nodes, alpha = [], 0
        status, solver_name = "OPTIMAL", DEFAULT_SOLVER
        proven = True
    else:
        status_clique, clique_nodes, omega = _solve_side(G, "clique", method_l, time_limit)
        status_mis, mis_nodes, alpha = _solve_side(G, "mis", method_l, time_limit)
        if method_l == "networkx":
            solver_name = "networkx-clique"
        elif method_l == "cpsat":
            solver_name = "ortools-cpsat-clique"
        else:
            solver_name = DEFAULT_SOLVER
        proven = status_clique == "OPTIMAL" and status_mis == "OPTIMAL"
        status = "OPTIMAL" if proven else "FEASIBLE"

    # Complement-duality cross-check: independently recompute both sides on
    # the complement graph with CP-SAT and verify the identities
    #   omega(G) == alpha(G_comp)   and   alpha(G) == omega(G_comp).
    duality_ok = False
    duality_detail: str | None = None
    try:
        g_comp = nx.complement(G)
        _, dual_mis_comp, alpha_comp = _cpsat_max_independent_set(g_comp, time_limit)
        _, dual_clique_comp, omega_comp = _cpsat_max_clique(g_comp, time_limit)
        if alpha_comp is not None and omega_comp is not None:
            duality_ok = (omega == alpha_comp) and (alpha == omega_comp)
            duality_detail = (
                f"omega(G)={omega}==alpha(G_comp)={alpha_comp}, "
                f"alpha(G)={alpha}==omega(G_comp)={omega_comp}"
                if duality_ok
                else (
                    f"omega(G)={omega} vs alpha(G_comp)={alpha_comp}; "
                    f"alpha(G)={alpha} vs omega(G_comp)={omega_comp}"
                )
            )
    except Exception as exc:  # noqa: BLE001
        duality_detail = f"duality cross-check failed: {exc}"

    int_nodes = [int(x) if isinstance(x, (int, float)) else x for x in nodes]
    objective = int(omega) if mode_l == "max_clique" else int(alpha)

    envelope: dict[str, Any] = {
        "problem_id": problem_id,
        "problem_class": "max_clique",
        "mode": mode_l,
        "status": status,
        "objective": objective,
        "solver": solver_name,
        "source": "tools/solve_max_clique.py",
        "num_nodes": n_nodes,
        "num_edges": n_edges,
        "clique_nodes": clique_nodes,
        "max_clique_size": int(omega),
        "independent_set_nodes": mis_nodes,
        "max_independent_set_size": int(alpha),
        "complement_duality_verified": bool(duality_ok),
        "nodes": int_nodes,
        "edges": edges,
        "meta": {
            "exact": True,
            "proven_optimal": bool(proven),
            "method_class": "exact",
            "method": method_l,
            "input_source": source_label,
            "time_limit_s": float(time_limit),
            "duality_cross_check": "cpsat-complement",
        },
    }
    if duality_detail:
        envelope["meta"]["duality_detail"] = duality_detail
    return envelope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OR-Path Max Clique / Max Independent Set solver "
        "(NetworkX + OR-Tools CP-SAT)"
    )
    parser.add_argument(
        "problem_id",
        nargs="?",
        default=None,
        help="Problem identifier (default: derived from the DIMACS stem)",
    )
    parser.add_argument(
        "--dimacs",
        default=str(DEFAULT_FIXTURE),
        help=f"DIMACS *.col instance (default: {DEFAULT_FIXTURE.name})",
    )
    parser.add_argument(
        "--method",
        choices=list(METHODS),
        default="hybrid",
        help="Solve method (default: hybrid = NetworkX exact + CP-SAT duality cross-check)",
    )
    parser.add_argument(
        "--mode",
        choices=list(MODES),
        default="max_clique",
        help="Objective side: max_clique (omega) or max_independent_set (alpha)",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=30.0,
        help="CP-SAT time limit in seconds (default: 30)",
    )
    parser.add_argument("--output", default=None, help="Write result JSON to path")
    args = parser.parse_args(argv)

    sol = solve_max_clique(
        dimacs_path=args.dimacs,
        method=args.method,
        mode=args.mode,
        time_limit=args.time_limit,
        problem_id=args.problem_id,
    )
    out = json.dumps(sol, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if sol.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
