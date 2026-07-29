#!/usr/bin/env python3
"""Exact TSP via OR-Tools CP-SAT (circuit) — proven optimal for small n."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_paths import fixture_dir  # noqa: E402


def _load_matrix(problem_id: str) -> tuple[list[list[int]], list[str]]:
    d = fixture_dir(problem_id)
    if (d / "distance_matrix.json").is_file():
        raw = json.loads((d / "distance_matrix.json").read_text(encoding="utf-8"))
        matrix = raw["matrix"] if isinstance(raw, dict) and "matrix" in raw else raw
        labels = (
            raw.get("labels")
            if isinstance(raw, dict) and raw.get("labels")
            else [str(i) for i in range(len(matrix))]
        )
        return [[int(x) for x in row] for row in matrix], [str(x) for x in labels]
    coords = json.loads((d / "coords.json").read_text(encoding="utf-8"))
    if isinstance(coords, dict):
        coords = coords["coords"]
    labels = [str(c.get("id", i)) for i, c in enumerate(coords)]
    n = len(coords)
    mat = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dx = float(coords[i]["x"]) - float(coords[j]["x"])
            dy = float(coords[i]["y"]) - float(coords[j]["y"])
            mat[i][j] = int(round(math.hypot(dx, dy)))
    return mat, labels


def solve_tsp_cpsat(problem_id: str, *, time_limit_s: float = 30.0) -> dict[str, Any]:
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        print("error: ortools cp_model import failed", file=sys.stderr)
        raise SystemExit(2)

    matrix, labels = _load_matrix(problem_id)
    n = len(matrix)
    if n < 2:
        raise ValueError("tsp needs n>=2")

    model = cp_model.CpModel()
    # circuit on arcs
    arcs: list[tuple[int, int, Any]] = []
    lit = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            lit[i, j] = model.NewBoolVar(f"x_{i}_{j}")
            arcs.append((i, j, lit[i, j]))
    model.AddCircuit(arcs)

    obj_terms = []
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            obj_terms.append(matrix[i][j] * lit[i, j])
    model.Minimize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_s)
    # deterministic-ish
    solver.parameters.random_seed = 1
    status = solver.Solve(model)

    ok_status = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    if not ok_status:
        return {
            "problem_id": problem_id,
            "problem_class": "tsp",
            "status": "INFEASIBLE" if status == cp_model.INFEASIBLE else "ERROR",
            "objective": -1,
            "solver": "ortools-cpsat-circuit",
            "source": "tools/solve_cpsat.py",
            "path": None,
            "tour": None,
            "routes": None,
            "meta": {
                "exact": True,
                "proven_optimal": False,
                "method_class": "exact",
                "cp_status": int(status),
            },
        }

    # rebuild tour from successor
    succ = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if solver.Value(lit[i, j]) == 1:
                succ[i] = j
                break
    tour_idx = [0]
    while len(tour_idx) < n:
        tour_idx.append(succ[tour_idx[-1]])
    tour_idx.append(0)
    tour = [labels[i] for i in tour_idx]
    obj = int(solver.ObjectiveValue())
    proven = status == cp_model.OPTIMAL
    return {
        "problem_id": problem_id,
        "problem_class": "tsp",
        "status": "OPTIMAL" if proven else "FEASIBLE",
        "objective": obj,
        "solver": "ortools-cpsat-circuit",
        "source": "tools/solve_cpsat.py",
        "path": None,
        "tour": tour,
        "routes": None,
        "meta": {
            "exact": True,
            "proven_optimal": proven,
            "method_class": "exact",
            "time_limit_s": time_limit_s,
            "cp_status": int(status),
            "n": n,
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="OR-Path exact CP-SAT TSP")
    p.add_argument("problem_id")
    p.add_argument("--time-limit-s", type=float, default=30.0)
    args = p.parse_args(argv)
    try:
        data = solve_tsp_cpsat(args.problem_id, time_limit_s=args.time_limit_s)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data.get("status") in {"OPTIMAL", "FEASIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
