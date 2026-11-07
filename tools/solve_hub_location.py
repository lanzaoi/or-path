#!/usr/bin/env python3
"""p-Hub Location Problem (p-HLP) — Civil Aeronautics Board (CAB) benchmarks.

Industrial-grade solver based on OR-Tools MIP (CBC / SCIP) implementing the
Ernst & Krishnamoorthy (1996) 3-index flow formulation:

  Decision variables
    z[i, k] in {0, 1}   : node i is assigned to hub k
    Y[k, m, i] >= 0     : transfer flow of commodity i from hub k to hub m

  Constraints
    sum_k z[k, k] == p                     (exactly p hubs)
    sum_k z[i, k] == 1  for all i         (each node assigned once)
    z[i, k] <= z[k, k]                    (assignment implies open hub)
    sum_m Y[k, m, i] - sum_m Y[m, k, i] == O[i]*z[i, k] - sum_j W[i, j]*z[j, k]

  Objective (collection + transfer + distribution)
    chi   * sum_i d[i, k] * O[i] * z[i, k]
    alpha * sum_k d[k, m] * sum_i Y[k, m, i]
    delta * sum_j d[m, j] * D[j] * z[j, m]

The reported objective / cost breakdown is recomputed directly from the
selected assignment via the Numbers Truth formula:

    total = sum_{i, j} W[i, j] * ( chi*d[i, a[i]]
                                   + alpha*d[a[i], a[j]]
                                   + delta*d[a[j], j] )

Benchmarks:
  - CAB10.json  : fast 10-city sub-instance, p=3, alpha=0.7, optimum 681216347.0158
  - CAB25.txt   : canonical 25-city instance, p=3, alpha=0.7, optimum 9361535773.97244
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from ortools.linear_solver import pywraplp

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent

DEFAULT_FIXTURE = "fixtures/benchmarks/hub_location/CAB10.json"
DEFAULT_P_HUBS = 3
DEFAULT_ALPHA = 0.7
DEFAULT_CHI = 1.0
DEFAULT_DELTA = 1.0
DEFAULT_TIME_LIMIT = 30.0


def _parse_txt(text: str) -> dict[str, Any]:
    """Parse the canonical CAB .txt format.

    Layout:
        line 1        : n (number of cities)
        "DISTANCE"    : n*n rows "i j distance"
        "DEMAND"      : n*n rows "i j demand"
    """
    lines = text.splitlines()
    if not lines:
        raise ValueError("empty CAB fixture")
    n = int(lines[0].strip())

    distances = [[0.0] * n for _ in range(n)]
    flows = [[0.0] * n for _ in range(n)]
    section: str | None = None

    for raw in lines[1:]:
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        head = parts[0].upper()
        if head in ("DISTANCE", "DEMAND"):
            section = head
            continue
        if section is None or len(parts) < 3:
            continue
        i = int(parts[0]) - 1
        j = int(parts[1]) - 1
        val = float(parts[2])
        if i < 0 or j < 0 or i >= n or j >= n:
            continue
        if section == "DISTANCE":
            distances[i][j] = val
        else:
            flows[i][j] = val

    if section != "DEMAND":
        raise ValueError("CAB .txt fixture missing DEMAND section")
    return {"num_nodes": n, "distances": distances, "flows": flows}


def load_hub_problem(
    fixture_path: str | Path | None = None,
    problem_dict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load a hub-location problem from a JSON dict or a CAB .txt/.json file."""
    if problem_dict is not None:
        data = dict(problem_dict)
    elif fixture_path is not None:
        path = Path(fixture_path)
        if not path.is_file():
            for base in (_ROOT, Path.cwd()):
                cand = base / fixture_path
                if cand.is_file():
                    path = cand
                    break
                cand_hub = base / "fixtures" / "benchmarks" / "hub_location" / fixture_path
                if cand_hub.is_file():
                    path = cand_hub
                    break
                cand_json = base / "fixtures" / "benchmarks" / "hub_location" / f"{fixture_path}.json"
                if cand_json.is_file():
                    path = cand_json
                    break
                cand_txt = base / "fixtures" / "benchmarks" / "hub_location" / f"{fixture_path}.txt"
                if cand_txt.is_file():
                    path = cand_txt
                    break
        if not path.is_file():
            raise FileNotFoundError(f"hub fixture not found: {fixture_path}")
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json" or text.lstrip().startswith("{"):
            data = json.loads(text)
        else:
            data = _parse_txt(text)
    else:
        # Default fixture path relative to the repo root.
        default = _ROOT / DEFAULT_FIXTURE
        if not default.is_file():
            default = Path.cwd() / DEFAULT_FIXTURE
        data = json.loads(default.read_text(encoding="utf-8"))

    distances = [[float(x) for x in row] for row in data["distances"]]
    flows = [[float(x) for x in row] for row in data["flows"]]
    n = int(data.get("num_nodes") or len(distances))

    if len(distances) != n or any(len(row) != n for row in distances):
        raise ValueError("distance matrix is not n x n")
    if len(flows) != n or any(len(row) != n for row in flows):
        raise ValueError("flow matrix is not n x n")

    return {
        "num_nodes": n,
        "distances": distances,
        "flows": flows,
        "p_hubs": int(data.get("p_hubs", DEFAULT_P_HUBS)),
        "alpha": float(data.get("alpha", DEFAULT_ALPHA)),
        "chi": float(data.get("chi", DEFAULT_CHI)),
        "delta": float(data.get("delta", DEFAULT_DELTA)),
    }


def _compute_costs(
    distances: list[list[float]],
    flows: list[list[float]],
    assignments: list[int],
    chi: float,
    alpha: float,
    delta: float,
) -> tuple[float, float, float, float]:
    """Recompute collection / transfer / distribution / total cost (Numbers Truth)."""
    n = len(distances)
    collection = 0.0
    transfer = 0.0
    distribution = 0.0
    for i in range(n):
        a_i = assignments[i]
        for j in range(n):
            a_j = assignments[j]
            w = flows[i][j]
            if w == 0.0:
                continue
            collection += w * chi * distances[i][a_i]
            transfer += w * alpha * distances[a_i][a_j]
            distribution += w * delta * distances[a_j][j]
    total = collection + transfer + distribution
    return collection, transfer, distribution, total


def solve_hub_location(
    fixture_path: str | Path | None = None,
    problem_dict: dict[str, Any] | None = None,
    p_hubs: int = DEFAULT_P_HUBS,
    alpha: float = DEFAULT_ALPHA,
    chi: float = DEFAULT_CHI,
    delta: float = DEFAULT_DELTA,
    time_limit_sec: float = DEFAULT_TIME_LIMIT,
    problem_id: str | None = None,
) -> dict[str, Any]:
    """Solve the p-Hub Location Problem via OR-Tools MIP (Ernst & Krishnamoorthy)."""
    t0 = time.perf_counter()
    if fixture_path is None and problem_id is not None and problem_id not in ("test_prob", "default"):
        fixture_path = problem_id

    data = load_hub_problem(fixture_path=fixture_path, problem_dict=problem_dict)
    n = data["num_nodes"]
    distances = data["distances"]
    flows = data["flows"]
    if problem_dict is not None:
        p_hubs = int(problem_dict.get("p_hubs", p_hubs))
        alpha = float(problem_dict.get("alpha", alpha))
        chi = float(problem_dict.get("chi", chi))
        delta = float(problem_dict.get("delta", delta))
    p_hubs = int(p_hubs)

    if p_hubs < 1 or p_hubs > n:
        raise ValueError(f"p_hubs={p_hubs} out of range for n={n}")

    # Outflow O[i] and inflow D[j]
    outflow = [sum(flows[i]) for i in range(n)]
    inflow = [sum(flows[i][j] for i in range(n)) for j in range(n)]

    solver = pywraplp.Solver.CreateSolver("CBC") or pywraplp.Solver.CreateSolver("SCIP")
    if not solver:
        solver = pywraplp.Solver("hub", pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)
    solver.SetTimeLimit(int(max(1e-3, float(time_limit_sec)) * 1000))

    # z[i, k] = 1 iff node i assigned to hub k
    z: dict[tuple[int, int], Any] = {}
    for i in range(n):
        for k in range(n):
            z[i, k] = solver.BoolVar(f"z_{i}_{k}")

    # Transfer flows Y[k, m, i]
    y: dict[tuple[int, int, int], Any] = {}
    for i in range(n):
        for k in range(n):
            for m in range(n):
                y[k, m, i] = solver.NumVar(0.0, solver.infinity(), f"Y_{k}_{m}_{i}")

    # Exactly p hubs
    solver.Add(solver.Sum([z[k, k] for k in range(n)]) == p_hubs)
    # Every node assigned to exactly one hub
    for i in range(n):
        solver.Add(solver.Sum([z[i, k] for k in range(n)]) == 1)
    # Assignment implies hub open
    for i in range(n):
        for k in range(n):
            solver.Add(z[i, k] <= z[k, k])

    # Flow conservation per origin i and node k
    for i in range(n):
        for k in range(n):
            outflow_y = solver.Sum([y[k, m, i] for m in range(n)])
            inflow_y = solver.Sum([y[m, k, i] for m in range(n)])
            supply = outflow[i] * z[i, k]
            sink = solver.Sum([flows[i][j] * z[j, k] for j in range(n)])
            solver.Add(outflow_y - inflow_y == supply - sink)

    # Objective: collection + transfer + distribution
    collection_expr = solver.Sum(
        chi * distances[i][k] * outflow[i] * z[i, k]
        for i in range(n)
        for k in range(n)
    )
    transfer_expr = solver.Sum(
        alpha * distances[k][m] * y[k, m, i]
        for i in range(n)
        for k in range(n)
        for m in range(n)
    )
    distribution_expr = solver.Sum(
        delta * distances[m][j] * inflow[j] * z[j, m]
        for j in range(n)
        for m in range(n)
    )
    solver.Minimize(collection_expr + transfer_expr + distribution_expr)

    status = solver.Solve()
    t1 = time.perf_counter()
    is_optimal = status == pywraplp.Solver.OPTIMAL
    is_feasible = status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE)

    problem_name = problem_id or _default_problem_id(fixture_path, data, n)

    if not is_feasible:
        return {
            "problem_id": problem_name,
            "problem_class": "hub_location",
            "mode": "hub_location",
            "status": "INFEASIBLE" if status == pywraplp.Solver.INFEASIBLE else "ERROR",
            "objective": -1.0,
            "solver": "ortools-mip-hub",
            "source": "tools/solve_hub_location.py",
            "num_nodes": n,
            "p_hubs": p_hubs,
            "alpha": alpha,
            "chi": chi,
            "delta": delta,
            "selected_hubs": [],
            "assignments": {},
            "cost_breakdown": {
                "collection_cost": 0.0,
                "transfer_cost": 0.0,
                "distribution_cost": 0.0,
            },
            "raw_problem": _raw_problem(data, p_hubs, alpha, chi, delta),
            "meta": {"exact": False, "proven_optimal": False, "wall_time_s": round(t1 - t0, 5)},
        }

    # Recompute every node's hub directly from z (Numbers Truth source).
    assignments = [_assigned_hub(z, i, n) for i in range(n)]
    selected_hubs = [h for h in range(n) if z[h, h].solution_value() > 0.5]
    if len(selected_hubs) != p_hubs:
        # Fall back to the assignments themselves if z[k,k] is numerically off.
        selected_hubs = sorted({assignments[h] for h in range(n) if assignments[h] == h})
    selected_hubs = sorted(selected_hubs)[:p_hubs]

    collection, transfer, distribution, total = _compute_costs(
        distances, flows, assignments, chi, alpha, delta
    )

    pid = problem_name
    return {
        "problem_id": pid,
        "problem_class": "hub_location",
        "mode": "hub_location",
        "status": "OPTIMAL" if is_optimal else "FEASIBLE",
        "objective": round(total, 6),
        "solver": "ortools-mip-hub",
        "source": "tools/solve_hub_location.py",
        "num_nodes": n,
        "p_hubs": p_hubs,
        "alpha": alpha,
        "chi": chi,
        "delta": delta,
        "selected_hubs": selected_hubs,
        "assignments": {str(i): int(assignments[i]) for i in range(n)},
        "cost_breakdown": {
            "collection_cost": round(collection, 6),
            "transfer_cost": round(transfer, 6),
            "distribution_cost": round(distribution, 6),
        },
        "raw_problem": _raw_problem(data, p_hubs, alpha, chi, delta),
        "meta": {
            "exact": True,
            "proven_optimal": is_optimal,
            "method_class": "exact",
            "wall_time_s": round(t1 - t0, 5),
            "mip_objective": round(float(solver.Objective().Value()), 6),
            "iterations": int(solver.iterations()),
        },
    }


def _assigned_hub(z: dict[tuple[int, int], Any], i: int, n: int) -> int:
    best_k, best_v = 0, 0.5
    for k in range(n):
        v = z[i, k].solution_value()
        if v > best_v:
            best_k, best_v = k, v
    return best_k


def _default_problem_id(fixture_path: str | Path | None, data: dict[str, Any], n: int) -> str:
    if fixture_path:
        return Path(fixture_path).stem
    name = data.get("name")
    return f"hub_{name}" if name else f"hub_{n}city"


def _raw_problem(data: dict[str, Any], p_hubs: int, alpha: float, chi: float, delta: float) -> dict[str, Any]:
    return {
        "distances": data["distances"],
        "flows": data["flows"],
        "num_nodes": int(data["num_nodes"]),
        "p_hubs": int(p_hubs),
        "alpha": float(alpha),
        "chi": float(chi),
        "delta": float(delta),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="p-Hub Location Problem solver (CAB benchmarks)")
    parser.add_argument("problem_id", nargs="?", default=None, help="problem / instance id")
    parser.add_argument("--fixture", default=None, help="path to CAB .txt or .json fixture")
    parser.add_argument("--p-hubs", type=int, default=DEFAULT_P_HUBS)
    parser.add_argument("--alpha", type=float, default=DEFAULT_ALPHA)
    parser.add_argument("--chi", type=float, default=DEFAULT_CHI)
    parser.add_argument("--delta", type=float, default=DEFAULT_DELTA)
    parser.add_argument("--time-limit-sec", type=float, default=DEFAULT_TIME_LIMIT)
    parser.add_argument("--output", default=None, help="write JSON envelope to this path")
    args, _unknown = parser.parse_known_args(argv)

    sol = solve_hub_location(
        fixture_path=args.fixture,
        p_hubs=args.p_hubs,
        alpha=args.alpha,
        chi=args.chi,
        delta=args.delta,
        time_limit_sec=args.time_limit_sec,
        problem_id=args.problem_id,
    )

    out_text = json.dumps(sol, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(out_text, encoding="utf-8")
    print(out_text)
    return 0 if sol.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
