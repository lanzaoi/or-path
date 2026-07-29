#!/usr/bin/env python3
"""B-题 问题三：12×11 芯片布局多目标 CP-SAT.

目标（层次）：
  1) min total cost
  2) max shared edges between different tiles
  3) min piece count

硬约束：
  - 完全覆盖 12×11
  - 四角必须覆盖（完全覆盖已蕴含）
  - 覆盖区域四连通（矩形满盖已蕴含；仍作文档约束）
  - 每个 2×2 (S) 至少两边被支撑（该边外侧与其它骨牌相邻）

成本（赛题）：M1, D1.5, I3/L3 2, 四格与 S 均为 2.5
内部用×2 整数：M2 D3 I3/L3 4 S/I4/T4/L4/Z4 5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from solve_polyomino import (  # noqa: E402
    NINE,
    _placements,
    _render_grid,
)

COST2 = {  # cost * 2
    "M": 2,
    "D": 3,
    "I3": 4,
    "L3": 4,
    "S": 5,
    "I4": 5,
    "T4": 5,
    "L4": 5,
    "Z4": 5,
}
COST_FLOAT = {k: v / 2.0 for k, v in COST2.items()}


def _unit_edges(rows: int, cols: int) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    edges = []
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                edges.append(((r, c), (r, c + 1)))
            if r + 1 < rows:
                edges.append(((r, c), (r + 1, c)))
    return edges


def _s_sides(cells: list[tuple[int, int]]) -> dict[str, list[tuple[int, int]]]:
    """External neighbor cells for each of 4 sides of a 2x2 block."""
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    r0, r1 = min(rs), max(rs)
    c0, c1 = min(cs), max(cs)
    return {
        "top": [(r0 - 1, c0), (r0 - 1, c1)],
        "bottom": [(r1 + 1, c0), (r1 + 1, c1)],
        "left": [(r0, c0 - 1), (r1, c0 - 1)],
        "right": [(r0, c1 + 1), (r1, c1 + 1)],
    }


def solve_q3(
    rows: int = 12,
    cols: int = 11,
    *,
    time_limit_s: float = 180.0,
    num_workers: int = 8,
) -> dict[str, Any]:
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        print("error: ortools missing", file=sys.stderr)
        raise SystemExit(2)

    board = {(r, c) for r in range(rows) for c in range(cols)}
    places = _placements(rows, cols, board, NINE, reflect=True)
    n_cells = rows * cols
    edges = _unit_edges(rows, cols)

    # index helpers
    cell_to_ps: dict[tuple[int, int], list[int]] = {c: [] for c in board}
    both_cover: dict[tuple[tuple[int, int], tuple[int, int]], list[int]] = {e: [] for e in edges}
    for i, p in enumerate(places):
        sc = set(map(tuple, p["cells"]))
        for cell in sc:
            cell_to_ps[cell].append(i)
        for e in edges:
            if e[0] in sc and e[1] in sc:
                both_cover[e].append(i)

    model = cp_model.CpModel()
    x = [model.NewBoolVar(f"p{i}") for i in range(len(places))]

    # exact cover
    for cell in board:
        model.Add(sum(x[i] for i in cell_to_ps[cell]) == 1)

    # corners explicit (redundant with full cover)
    for corner in [(0, 0), (0, cols - 1), (rows - 1, 0), (rows - 1, cols - 1)]:
        model.Add(sum(x[i] for i in cell_to_ps[corner]) == 1)

    # shared edges: 1 if no single placement covers both endpoints
    shared = []
    for ei, e in enumerate(edges):
        s = model.NewBoolVar(f"sh{ei}")
        shared.append(s)
        # if any placement covering both is chosen, shared=0; else 1
        both = both_cover[e]
        if not both:
            model.Add(s == 1)  # different pieces always
        else:
            # s == 1 - OR(x_p for p in both) ; at most one such p under exact cover
            model.Add(sum(x[i] for i in both) + s == 1)

    # S support: each chosen S has >=2 sides supported by external other tiles
    for i, p in enumerate(places):
        if p["piece"] != "S":
            continue
        cells = [tuple(c) for c in p["cells"]]
        sides = _s_sides(cells)
        side_vars = []
        for sname, neighs in sides.items():
            sv = model.NewBoolVar(f"S{i}_{sname}")
            side_vars.append(sv)
            # side supported if some external neighbor cell is covered by placement != i
            ext_terms = []
            for nb in neighs:
                if nb not in board:
                    continue
                for j in cell_to_ps[nb]:
                    if j == i:
                        continue
                    ext_terms.append(x[j])
            if not ext_terms:
                model.Add(sv == 0)
            else:
                # sv <= sum(ext); sum(ext) <= M*sv
                model.Add(sum(ext_terms) >= sv)
                model.Add(sum(ext_terms) <= len(ext_terms) * sv)
        # if x[i] then sum side_vars >= 2
        model.Add(sum(side_vars) >= 2 * x[i])

    cost_terms = []
    for i, p in enumerate(places):
        cost_terms.append(COST2[p["piece"]] * x[i])
    total_cost2 = sum(cost_terms)
    piece_count = sum(x)
    shared_sum = sum(shared)

    # hierarchical multi-objective via sequential solves
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_s) / 3.0
    solver.parameters.random_seed = 1
    solver.parameters.num_search_workers = int(num_workers)

    phases: list[dict[str, Any]] = []

    # Phase 1: min cost
    model.Minimize(total_cost2)
    st1 = solver.Solve(model)
    if st1 not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "problem_id": "polyomino_b_q3_12x11",
            "problem_class": "polyomino_multiobj",
            "status": "INFEASIBLE" if st1 == cp_model.INFEASIBLE else "ERROR",
            "objective": -1,
            "solver": "ortools-cpsat-polyomino-q3",
            "meta": {"phase": 1, "cp_status": int(st1)},
        }
    cost_star = int(solver.ObjectiveValue())
    phases.append(
        {
            "phase": 1,
            "goal": "min_cost2",
            "status": "OPTIMAL" if st1 == cp_model.OPTIMAL else "FEASIBLE",
            "cost2": cost_star,
            "cost": cost_star / 2.0,
            "shared": int(solver.Value(shared_sum)),
            "pieces": int(solver.Value(piece_count)),
            "proven": st1 == cp_model.OPTIMAL,
            "wall_time_s": float(solver.WallTime()),
        }
    )

    # Phase 2: max shared | cost2 = cost_star
    model.Add(total_cost2 == cost_star)
    model.Maximize(shared_sum)
    solver.parameters.max_time_in_seconds = float(time_limit_s) / 3.0
    st2 = solver.Solve(model)
    if st2 not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # fallback keep phase1 solution — re-solve phase1 values from last? shouldn't happen
        shared_star = phases[0]["shared"]
    else:
        shared_star = int(solver.ObjectiveValue())
    phases.append(
        {
            "phase": 2,
            "goal": "max_shared | cost2*",
            "status": "OPTIMAL" if st2 == cp_model.OPTIMAL else "FEASIBLE",
            "cost2": cost_star,
            "cost": cost_star / 2.0,
            "shared": shared_star if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE) else phases[0]["shared"],
            "pieces": int(solver.Value(piece_count)) if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE) else phases[0]["pieces"],
            "proven": st2 == cp_model.OPTIMAL,
            "wall_time_s": float(solver.WallTime()),
        }
    )

    # Phase 3: min pieces | cost2* and shared*
    if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        model.Add(shared_sum == shared_star)
    model.Minimize(piece_count)
    solver.parameters.max_time_in_seconds = float(time_limit_s) / 3.0
    st3 = solver.Solve(model)
    final_status = st3
    if st3 not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # use phase2 solution by resolving max shared again quickly
        return {
            "problem_id": "polyomino_b_q3_12x11",
            "problem_class": "polyomino_multiobj",
            "status": "ERROR",
            "objective": -1,
            "phases": phases,
            "meta": {"note": "phase3 failed"},
        }

    chosen = []
    for i, p in enumerate(places):
        if solver.Value(x[i]) == 1:
            chosen.append(
                {
                    "piece": p["piece"],
                    "cells": [list(c) for c in p["cells"]],
                    "size": p["size"],
                    "cost": COST_FLOAT[p["piece"]],
                }
            )
    counts: dict[str, int] = {}
    cost_sum = 0.0
    for p in chosen:
        counts[p["piece"]] = counts.get(p["piece"], 0) + 1
        cost_sum += p["cost"]
    pieces_n = len(chosen)
    shared_n = int(solver.Value(shared_sum))
    cost2_n = int(solver.Value(total_cost2))

    phases.append(
        {
            "phase": 3,
            "goal": "min_pieces | cost2* shared*",
            "status": "OPTIMAL" if st3 == cp_model.OPTIMAL else "FEASIBLE",
            "cost2": cost2_n,
            "cost": cost2_n / 2.0,
            "shared": shared_n,
            "pieces": pieces_n,
            "proven": st3 == cp_model.OPTIMAL,
            "wall_time_s": float(solver.WallTime()),
        }
    )

    # hierarchical proven only if all phases optimal
    hier_proven = all(ph.get("proven") for ph in phases)

    return {
        "problem_id": "polyomino_b_q3_12x11",
        "problem_class": "polyomino_multiobj",
        "status": "OPTIMAL" if hier_proven else "FEASIBLE",
        "objective": cost_sum,  # primary display: total cost
        "objectives": {
            "total_cost": cost_sum,
            "shared_edges": shared_n,
            "piece_count": pieces_n,
            "total_cost2": cost2_n,
        },
        "solver": "ortools-cpsat-polyomino-q3",
        "source": "tools/solve_polyomino_q3.py",
        "placements": chosen,
        "piece_count": pieces_n,
        "piece_counts": counts,
        "path": None,
        "tour": None,
        "routes": None,
        "phases": phases,
        "meta": {
            "exact": True,
            "proven_optimal": hier_proven,
            "method_class": "exact",
            "hierarchy": ["min_cost", "max_shared_edges", "min_piece_count"],
            "cost_table": COST_FLOAT,
            "n_cells": n_cells,
            "n_placements": len(places),
            "n_unit_edges": len(edges),
            "rows": rows,
            "cols": cols,
            "constraints": [
                "exact_cover",
                "four_corners_covered",
                "full_rectangle_implies_4connected",
                "S_square_at_least_2_sides_supported",
            ],
            "board_grid": _render_grid(rows, cols, chosen, set()),
            "time_limit_s_total": time_limit_s,
            "wall_time_s_last_phase": float(solver.WallTime()),
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="B-题 Q3 multi-objective polyomino")
    p.add_argument("--rows", type=int, default=12)
    p.add_argument("--cols", type=int, default=11)
    p.add_argument("--time-limit-s", type=float, default=180.0)
    args = p.parse_args(argv)
    try:
        data = solve_q3(args.rows, args.cols, time_limit_s=args.time_limit_s)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data.get("status") in {"OPTIMAL", "FEASIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
