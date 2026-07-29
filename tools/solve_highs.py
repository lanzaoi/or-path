#!/usr/bin/env python3
"""Exact TSP via HiGHS MIP (MTZ formulation) — proven optimal for small n."""
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


def solve_tsp_highs(problem_id: str, *, time_limit_s: float = 30.0) -> dict[str, Any]:
    try:
        import highspy
    except ImportError:
        print("error: highspy import failed — pip install highspy", file=sys.stderr)
        raise SystemExit(2)

    matrix, labels = _load_matrix(problem_id)
    n = len(matrix)
    if n < 2:
        raise ValueError("tsp needs n>=2")

    h = highspy.Highs()
    h.silent()
    h.setOptionValue("time_limit", float(time_limit_s))
    h.setOptionValue("random_seed", 1)

    # variables: x[i,j] binary i!=j ; u[i] continuous MTZ for i=1..n-1
    # index map
    x_idx: dict[tuple[int, int], int] = {}
    col = 0
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            x_idx[i, j] = col
            h.addVar(0.0, 1.0)  # will set integer below
            col += 1
    u_idx: dict[int, int] = {}
    for i in range(1, n):
        u_idx[i] = col
        h.addVar(1.0, float(n - 1))
        col += 1

    n_x = n * (n - 1)
    # integrality for x
    integrality = [highspy.HighsVarType.kInteger] * n_x + [
        highspy.HighsVarType.kContinuous
    ] * (n - 1)
    h.changeColsIntegrality(len(integrality), list(range(len(integrality))), integrality)

    # objective
    costs = [0.0] * col
    for (i, j), c in x_idx.items():
        costs[c] = float(matrix[i][j])
    h.changeColsCost(col, list(range(col)), costs)

    # out-degree / in-degree = 1
    for i in range(n):
        inds = [x_idx[i, j] for j in range(n) if j != i]
        vals = [1.0] * len(inds)
        h.addRow(1.0, 1.0, len(inds), inds, vals)
    for j in range(n):
        inds = [x_idx[i, j] for i in range(n) if i != j]
        vals = [1.0] * len(inds)
        h.addRow(1.0, 1.0, len(inds), inds, vals)

    # MTZ: u_i - u_j + (n-1)*x_ij <= n-2 for i!=j, i,j >=1
    for i in range(1, n):
        for j in range(1, n):
            if i == j:
                continue
            inds = [u_idx[i], u_idx[j], x_idx[i, j]]
            vals = [1.0, -1.0, float(n - 1)]
            h.addRow(-highspy.kHighsInf, float(n - 2), 3, inds, vals)

    h.run()
    info = h.getInfo()
    model_status = h.getModelStatus()
    # Optimal
    optimal = model_status == highspy.HighsModelStatus.kOptimal
    feasible = model_status in (
        highspy.HighsModelStatus.kOptimal,
        highspy.HighsModelStatus.kObjectiveBound,
    )

    if not feasible and not optimal:
        # try read anyway
        pass

    sol = h.getSolution()
    col_val = list(sol.col_value) if sol is not None else []
    if len(col_val) < n_x:
        return {
            "problem_id": problem_id,
            "problem_class": "tsp",
            "status": "ERROR",
            "objective": -1,
            "solver": "highs-mtz-mip",
            "source": "tools/solve_highs.py",
            "path": None,
            "tour": None,
            "routes": None,
            "meta": {
                "exact": True,
                "proven_optimal": False,
                "method_class": "exact",
                "highs_status": str(model_status),
            },
        }

    succ: dict[int, int] = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if col_val[x_idx[i, j]] > 0.5:
                succ[i] = j
                break
    if len(succ) != n:
        return {
            "problem_id": problem_id,
            "problem_class": "tsp",
            "status": "ERROR",
            "objective": -1,
            "solver": "highs-mtz-mip",
            "source": "tools/solve_highs.py",
            "path": None,
            "tour": None,
            "routes": None,
            "meta": {
                "exact": True,
                "proven_optimal": False,
                "method_class": "exact",
                "highs_status": str(model_status),
                "detail": "tour reconstruct failed",
            },
        }

    tour_idx = [0]
    guard = 0
    while len(tour_idx) < n and guard < n + 2:
        tour_idx.append(succ[tour_idx[-1]])
        guard += 1
    tour_idx.append(0)
    tour = [labels[i] for i in tour_idx]
    # objective from tour edges (trust recompute)
    obj = 0
    for a, b in zip(tour_idx, tour_idx[1:]):
        obj += matrix[a][b]

    return {
        "problem_id": problem_id,
        "problem_class": "tsp",
        "status": "OPTIMAL" if optimal else "FEASIBLE",
        "objective": int(obj),
        "solver": "highs-mtz-mip",
        "source": "tools/solve_highs.py",
        "path": None,
        "tour": tour,
        "routes": None,
        "meta": {
            "exact": True,
            "proven_optimal": bool(optimal),
            "method_class": "exact",
            "time_limit_s": time_limit_s,
            "highs_status": str(model_status),
            "n": n,
            "mip_objective": float(getattr(info, "objective_function_value", obj)),
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="OR-Path exact HiGHS TSP")
    p.add_argument("problem_id")
    p.add_argument("--time-limit-s", type=float, default=30.0)
    args = p.parse_args(argv)
    try:
        data = solve_tsp_highs(args.problem_id, time_limit_s=args.time_limit_s)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data.get("status") in {"OPTIMAL", "FEASIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
