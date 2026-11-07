#!/usr/bin/env python3
"""Graph Coloring solver — NetworkX DSATUR heuristic + OR-Tools CP-SAT exact.

Minimum-color (chromatic number) vertex coloring:

* ``dsatur``  — NetworkX ``greedy_color(strategy='DSATUR')`` heuristic upper
  bound. Status stays FEASIBLE (no optimality proof).
* ``cpsat``   — OR-Tools CP-SAT exact: colours in ``0..n-1``, pairwise
  ``color[u] != color[v]`` per edge, symmetry breaking ``color[0] == 0``,
  minimise ``max_c``.  Chromatic number = ``max_c + 1``.
* ``hybrid``  — DSATUR first to get a tight upper bound ``UB``; CP-SAT then
  minimises over colours ``0..UB-1`` and proves optimality.

Inputs:
* ``dimacs_path`` — DIMACS ``.col`` file (default:
  ``fixtures/benchmarks/dimacs/myciel3.col``, 11 vertices / 20 edges / chi=4)
* ``graph_data``  — edge list ``[[u, v], ...]`` (or ``{"edges": [...]}``)
* ``G``           — a pre-built ``networkx.Graph``

Output follows the OR-Path "Numbers Truth" envelope (ADR-0002):
``problem_id, problem_class="graph_coloring", mode="graph_coloring", status,
objective=chromatic_number, solver, source, num_nodes, num_edges,
chromatic_number, nodes, node_colors, color_classes, edges, meta``.
The independent validator (``validators/extended_solvers.py``) re-derives
coverage, zero edge conflicts, distinct-colour count, and the color-class
partition from the envelope alone — no solver is re-run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.algorithms.coloring import greedy_color
from ortools.sat.python import cp_model

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

DEFAULT_FIXTURE = _ROOT / "fixtures" / "benchmarks" / "dimacs" / "myciel3.col"
DEFAULT_SOLVER = "networkx-dsatur-cpsat"
METHODS = ("dsatur", "cpsat", "hybrid")


def _resolve_dimacs_path(path: str | Path | None) -> Path:
    """Resolve a DIMACS path against cwd, then the install root."""
    raw = str(path or DEFAULT_FIXTURE)
    if raw in ("test_prob", "default") or not raw:
        return DEFAULT_FIXTURE
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


def _dsatur_coloring(G: nx.Graph) -> dict[Any, int]:
    """NetworkX DSATUR greedy colouring (0-indexed colours)."""
    return greedy_color(G, strategy="DSATUR")


def _cpsat_coloring(
    G: nx.Graph,
    upper_bound: int,
    time_limit: float,
) -> tuple[str, dict[Any, int] | None, int | None]:
    """CP-SAT exact colouring.

    Returns (solver_status_name, node_colors, chromatic_number).
    ``chromatic_number`` is ``max_c + 1`` (proved when status is OPTIMAL).
    """
    nodes = list(G.nodes())
    n = len(nodes)
    node_idx = {node: i for i, node in enumerate(nodes)}

    model = cp_model.CpModel()
    color = [model.NewIntVar(0, upper_bound - 1, f"c_{i}") for i in range(n)]
    max_c = model.NewIntVar(0, upper_bound - 1, "max_c")
    for u, v in G.edges():
        model.Add(color[node_idx[u]] != color[node_idx[v]])
    for i in range(n):
        model.Add(color[i] <= max_c)
    if n > 0:
        model.Add(color[0] == 0)  # symmetry breaking
    model.Minimize(max_c)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.1, float(time_limit))
    status_code = solver.Solve(model)
    status = solver.StatusName(status_code)
    if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return status, None, None
    node_colors = {nodes[i]: int(solver.Value(color[i])) for i in range(n)}
    chromatic = int(solver.Value(max_c)) + 1
    return status, node_colors, chromatic


def solve_graph_coloring(
    dimacs_path: str | Path | None = None,
    graph_data: Any | None = None,
    G: nx.Graph | None = None,
    method: str = "hybrid",
    time_limit: float = 30.0,
    problem_id: str | None = None,
) -> dict[str, Any]:
    """Solve a graph coloring instance and emit the OR-Path envelope (ADR-0002).

    ``method`` ∈ {'dsatur', 'cpsat', 'hybrid'}; default ``hybrid``
    (DSATUR upper bound + CP-SAT exact proof).
    """
    method_l = (method or "hybrid").lower().strip()
    if method_l not in METHODS:
        raise ValueError(f"unknown method {method!r}; expected one of {METHODS}")

    G, source_label = _build_graph(dimacs_path=dimacs_path, graph_data=graph_data, G=G)
    nodes = sorted(G.nodes(), key=lambda x: (str(type(x)), x))
    _edge_pairs = [
        ([int(u), int(v)] if isinstance(u, int) and isinstance(v, int) else [u, v])
        for u, v in G.edges()
    ]
    if all(isinstance(u, int) and isinstance(v, int) for u, v in G.edges()):
        edges = sorted(_edge_pairs)
    else:
        _edge_key = lambda e: (str(type(e[0])), str(e[0]), str(type(e[1])), str(e[1]))
        edges = sorted(_edge_pairs, key=_edge_key)
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    # Default problem_id: derive from the DIMACS stem when we loaded a file.
    if problem_id is None:
        if dimacs_path is not None or (graph_data is None and G is None):
            problem_id = f"graph_coloring_{_resolve_dimacs_path(dimacs_path).stem}"
        else:
            problem_id = "graph_coloring_instance"

    dsatur_ub: int | None = None
    if n_nodes == 0:
        chromatic, node_colors, status = 0, {}, "OPTIMAL"
        exact, proven, solver_name = True, True, DEFAULT_SOLVER
    elif method_l == "dsatur":
        raw = _dsatur_coloring(G)
        node_colors = {int(k): int(v) for k, v in raw.items()}
        chromatic = len(set(node_colors.values()))
        dsatur_ub = chromatic
        status = "FEASIBLE"
        exact, proven = False, False
        solver_name = "networkx-dsatur"
    elif method_l == "cpsat":
        status_name, node_colors, chromatic = _cpsat_coloring(G, n_nodes, time_limit)
        if node_colors is None:
            raise RuntimeError(f"CP-SAT coloring failed with status {status_name}")
        exact, proven = True, status_name == "OPTIMAL"
        status = "OPTIMAL" if proven else "FEASIBLE"
        solver_name = "ortools-cpsat"
    else:  # hybrid
        dsatur_ub = len(set(_dsatur_coloring(G).values()))
        status_name, node_colors, chromatic = _cpsat_coloring(G, dsatur_ub, time_limit)
        if node_colors is None:
            raise RuntimeError(f"CP-SAT coloring failed with status {status_name}")
        exact, proven = True, status_name == "OPTIMAL"
        status = "OPTIMAL" if proven else "FEASIBLE"
        solver_name = DEFAULT_SOLVER

    # Normalise node ids to ints when possible (DIMACS / edge lists are ints).
    int_nodes = [int(x) if isinstance(x, (int, float)) else x for x in nodes]
    node_colors = {
        int(k) if isinstance(k, (int, float)) else k: int(v)
        for k, v in node_colors.items()
    }
    color_classes: dict[str, list[int]] = {}
    for node in sorted(node_colors, key=lambda x: (str(type(x)), x)):
        color_classes.setdefault(str(node_colors[node]), []).append(
            int(node) if isinstance(node, (int, float)) else node
        )

    envelope: dict[str, Any] = {
        "problem_id": problem_id,
        "problem_class": "graph_coloring",
        "mode": "graph_coloring",
        "status": status,
        "objective": int(chromatic),
        "solver": solver_name,
        "source": "tools/solve_graph_coloring.py",
        "num_nodes": n_nodes,
        "num_edges": n_edges,
        "chromatic_number": int(chromatic),
        "nodes": int_nodes,
        "node_colors": {str(k): v for k, v in node_colors.items()},
        "color_classes": color_classes,
        "edges": edges,
        "meta": {
            "exact": exact,
            "proven_optimal": proven,
            "method_class": "exact" if exact else "heuristic",
            "method": method_l,
            "input_source": source_label,
            "time_limit_s": float(time_limit),
        },
    }
    if dsatur_ub is not None:
        envelope["meta"]["dsatur_upper_bound"] = dsatur_ub
    return envelope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OR-Path Graph Coloring solver (NetworkX DSATUR + OR-Tools CP-SAT)"
    )
    parser.add_argument(
        "--fixture",
        default=str(DEFAULT_FIXTURE),
        help=f"DIMACS *.col instance (default: {DEFAULT_FIXTURE.name})",
    )
    parser.add_argument(
        "--method",
        choices=list(METHODS),
        default="hybrid",
        help="Solve method (default: hybrid = DSATUR UB + CP-SAT exact)",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=30.0,
        help="CP-SAT time limit in seconds (default: 30)",
    )
    parser.add_argument("--output", default=None, help="Write result JSON to path")
    args = parser.parse_args(argv)

    sol = solve_graph_coloring(
        dimacs_path=args.fixture,
        method=args.method,
        time_limit=args.time_limit,
    )
    out = json.dumps(sol, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if sol.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
