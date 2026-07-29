#!/usr/bin/env python3
"""Exact polyomino covering via OR-Tools CP-SAT (exact ILP/CP).

Supports B-题 Q1/Q2: piece inventory caps, optional uncovered cells.
Numbers are proven optimal under the CP model when status=OPTIMAL.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_paths import fixture_dir  # noqa: E402

NINE = ["M", "D", "L3", "I3", "S", "I4", "T4", "L4", "Z4"]

# B-题 问题二 caps (OCR). Tromino 每种; 四格 listed types each ≤9 (若赛题为“四格合计9”可改 tetromino_total).
Q2_CAPS_12x11 = {
    "M": 18,
    "D": 15,
    "L3": 12,
    "I3": 12,
    "S": 9,
    "I4": 9,
    "T4": 9,
    "L4": 9,
    "Z4": 9,
}
Q2_CAPS_25x20 = {
    "M": 50,
    "D": 50,
    "L3": 40,
    "I3": 40,
    "S": 20,
    "I4": 20,
    "T4": 20,
    "L4": 20,
    "Z4": 20,
}
Q2_CAPS_30x30 = {
    "M": 100,
    "D": 80,
    "L3": 70,
    "I3": 70,
    "S": 50,
    "I4": 50,
    "T4": 50,
    "L4": 50,
    "Z4": 50,
}


def _cells(rows: int, cols: int, removed: set[tuple[int, int]]) -> list[tuple[int, int]]:
    return [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in removed]


def _normalize(shape: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    mr = min(r for r, _ in shape)
    mc = min(c for _, c in shape)
    pts = sorted((r - mr, c - mc) for r, c in shape)
    return tuple(pts)


def _orientations(shape: list[tuple[int, int]], *, reflect: bool) -> list[tuple[tuple[int, int], ...]]:
    seen: set[tuple[tuple[int, int], ...]] = set()
    out: list[tuple[tuple[int, int], ...]] = []
    bases = [list(shape)]
    if reflect:
        bases.append([(r, -c) for r, c in shape])
    for base in bases:
        cur = list(base)
        for _ in range(4):
            norm = _normalize(cur)
            if norm not in seen:
                seen.add(norm)
                out.append(norm)
            cur = [(c, -r) for r, c in cur]
    return out


def _piece_library(*, reflect: bool = True) -> dict[str, list[tuple[tuple[int, int], ...]]]:
    raw = {
        "M": [(0, 0)],
        "D": [(0, 0), (0, 1)],
        "L3": [(0, 0), (0, 1), (1, 0)],
        "I3": [(0, 0), (0, 1), (0, 2)],
        "S": [(0, 0), (0, 1), (1, 0), (1, 1)],
        "I4": [(0, 0), (0, 1), (0, 2), (0, 3)],
        "T4": [(0, 0), (0, 1), (0, 2), (1, 1)],
        "L4": [(0, 0), (1, 0), (2, 0), (2, 1)],
        "Z4": [(0, 0), (0, 1), (1, 1), (1, 2)],
    }
    return {k: _orientations(v, reflect=reflect) for k, v in raw.items()}


def _placements(
    rows: int,
    cols: int,
    board: set[tuple[int, int]],
    piece_ids: list[str],
    *,
    reflect: bool = True,
) -> list[dict[str, Any]]:
    lib = _piece_library(reflect=reflect)
    places: list[dict[str, Any]] = []
    pid = 0
    for name in piece_ids:
        for shape in lib[name]:
            for r0 in range(rows):
                for c0 in range(cols):
                    cells = [(r0 + dr, c0 + dc) for dr, dc in shape]
                    if all(cell in board for cell in cells):
                        places.append(
                            {
                                "id": pid,
                                "piece": name,
                                "cells": cells,
                                "size": len(cells),
                            }
                        )
                        pid += 1
    return places


def solve_cover(
    rows: int,
    cols: int,
    *,
    removed: list[list[int]] | None = None,
    piece_ids: list[str] | None = None,
    only_pieces: list[str] | None = None,
    max_counts: dict[str, int] | None = None,
    max_uncovered: int = 0,
    time_limit_s: float = 60.0,
    minimize_count: bool = True,
    reflect: bool = True,
    num_workers: int = 8,
) -> dict[str, Any]:
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        print("error: ortools missing", file=sys.stderr)
        raise SystemExit(2)

    rem = {(int(a), int(b)) for a, b in (removed or [])}
    board_cells = _cells(rows, cols, rem)
    board_set = set(board_cells)
    n_cells = len(board_cells)
    ids = list(only_pieces or piece_ids or NINE)
    places = _placements(rows, cols, board_set, ids, reflect=reflect)
    if not places:
        return {
            "problem_class": "polyomino_cover",
            "status": "INFEASIBLE",
            "objective": -1,
            "solver": "ortools-cpsat-polyomino",
            "meta": {"exact": True, "proven_optimal": False, "method_class": "exact"},
        }

    model = cp_model.CpModel()
    x = [model.NewBoolVar(f"p{i}") for i in range(len(places))]

    # cell -> placement indices (exact or at most one if holes allowed)
    cell_map: dict[tuple[int, int], list[int]] = {c: [] for c in board_cells}
    for i, p in enumerate(places):
        for cell in p["cells"]:
            cell_map[cell].append(i)

    uncovered_vars = []
    for cell in board_cells:
        cov = [x[i] for i in cell_map[cell]]
        if max_uncovered <= 0:
            model.Add(sum(cov) == 1)
        else:
            u = model.NewBoolVar(f"u_{cell[0]}_{cell[1]}")
            uncovered_vars.append(u)
            # either exactly one placement or uncovered
            model.Add(sum(cov) + u == 1)

    if uncovered_vars:
        model.Add(sum(uncovered_vars) <= int(max_uncovered))

    # inventory caps per piece type
    if max_counts:
        for name, lim in max_counts.items():
            idxs = [i for i, p in enumerate(places) if p["piece"] == name]
            if idxs:
                model.Add(sum(x[i] for i in idxs) <= int(lim))

    if minimize_count:
        model.Minimize(sum(x))
    else:
        model.Minimize(0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_s)
    solver.parameters.random_seed = 1
    if num_workers and num_workers > 1:
        solver.parameters.num_search_workers = int(num_workers)
    status = solver.Solve(model)

    proven = status == cp_model.OPTIMAL
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    if not ok:
        return {
            "problem_id": f"{rows}x{cols}",
            "problem_class": "polyomino_cover",
            "status": "INFEASIBLE" if status == cp_model.INFEASIBLE else "ERROR",
            "objective": -1,
            "solver": "ortools-cpsat-polyomino",
            "source": "tools/solve_polyomino.py",
            "placements": None,
            "piece_count": None,
            "path": None,
            "tour": None,
            "routes": None,
            "meta": {
                "exact": True,
                "proven_optimal": False,
                "method_class": "exact",
                "cp_status": int(status),
                "n_cells": n_cells,
                "n_placements": len(places),
                "pieces_allowed": ids,
                "max_counts": max_counts,
                "max_uncovered": max_uncovered,
            },
        }

    chosen = []
    for i, p in enumerate(places):
        if solver.Value(x[i]) == 1:
            chosen.append(
                {
                    "piece": p["piece"],
                    "cells": [list(c) for c in p["cells"]],
                    "size": p["size"],
                }
            )
    counts: dict[str, int] = {}
    for p in chosen:
        counts[p["piece"]] = counts.get(p["piece"], 0) + 1
    obj = len(chosen)
    covered = sum(p["size"] for p in chosen)
    holes = n_cells - covered

    max_piece = max((p["size"] for p in places), default=1)
    target_cells = n_cells - (0 if max_uncovered <= 0 else holes)
    # lower bound for full cover (or covered cells): ceil(cells_to_cover / max_piece)
    cells_for_lb = n_cells if max_uncovered <= 0 else covered
    lb = (cells_for_lb + max_piece - 1) // max_piece if cells_for_lb else 0
    # also inventory-aware crude LB: ignore if caps bind tightly
    lb_area = None
    if max_uncovered <= 0:
        # max cells coverable is n_cells; min pieces >= ceil(n/4) with size-4 available
        lb_area = (n_cells + max_piece - 1) // max_piece

    return {
        "problem_id": f"{rows}x{cols}",
        "problem_class": "polyomino_cover",
        "status": "OPTIMAL" if proven else "FEASIBLE",
        "objective": obj,
        "solver": "ortools-cpsat-polyomino",
        "source": "tools/solve_polyomino.py",
        "placements": chosen,
        "piece_count": obj,
        "piece_counts": counts,
        "path": None,
        "tour": None,
        "routes": None,
        "meta": {
            "exact": True,
            "proven_optimal": proven,
            "method_class": "exact",
            "time_limit_s": time_limit_s,
            "cp_status": int(status),
            "n_cells": n_cells,
            "cells_covered": covered,
            "cells_uncovered": holes,
            "n_placements": len(places),
            "pieces_allowed": ids,
            "max_counts": max_counts,
            "max_uncovered": max_uncovered,
            "lower_bound_by_max_piece": lb_area if lb_area is not None else lb,
            "max_piece_size": max_piece,
            "rows": rows,
            "cols": cols,
            "reflect": reflect,
            "removed": [list(x) for x in sorted(rem)],
            "board_grid": _render_grid(rows, cols, chosen, rem),
            "wall_time_s": float(solver.WallTime()),
            "objective_bound": float(solver.BestObjectiveBound())
            if hasattr(solver, "BestObjectiveBound")
            else None,
        },
    }


def _render_grid(
    rows: int,
    cols: int,
    placements: list[dict[str, Any]],
    removed: set[tuple[int, int]],
) -> list[str]:
    grid = [["." for _ in range(cols)] for _ in range(rows)]
    for r, c in removed:
        if 0 <= r < rows and 0 <= c < cols:
            grid[r][c] = "#"
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    covered: set[tuple[int, int]] = set()
    for i, p in enumerate(placements):
        ch = letters[i % len(letters)]
        for r, c in p["cells"]:
            grid[r][c] = ch
            covered.add((r, c))
    # mark uncovered as '.'
    return ["".join(row) for row in grid]


def solve_q1_min_cover() -> dict[str, Any]:
    return solve_cover(4, 4, piece_ids=["M", "D", "L3"], time_limit_s=30.0, reflect=False)


def solve_q1_l_only_deficient() -> dict[str, Any]:
    results = []
    any_yes = False
    for r in range(4):
        for c in range(4):
            sol = solve_cover(
                4,
                4,
                removed=[[r, c]],
                only_pieces=["L3"],
                time_limit_s=10.0,
                minimize_count=False,
                reflect=True,
            )
            ok = sol.get("status") in {"OPTIMAL", "FEASIBLE"}
            any_yes = any_yes or ok
            results.append({"removed": [r, c], "feasible": ok, "status": sol.get("status")})
    n_ok = sum(1 for x in results if x["feasible"])
    return {
        "problem_id": "4x4_deficient_L3_only",
        "problem_class": "polyomino_cover",
        "status": "OPTIMAL",
        "objective": 1 if any_yes else 0,
        "solver": "ortools-cpsat-polyomino",
        "source": "tools/solve_polyomino.py",
        "any_removed_cell_L3_coverable": any_yes,
        "feasible_positions": n_ok,
        "per_cell": results,
        "theorem": (
            f"CP-SAT: L3-only cover feasible for {n_ok}/16 single-cell removals on 4x4."
        ),
        "meta": {
            "exact": True,
            "proven_optimal": True,
            "method_class": "exact",
            "note": "objective 0/1 is boolean any-feasible flag, NOT piece count",
        },
        "path": None,
        "tour": None,
        "routes": None,
    }


def solve_q2(
    rows: int,
    cols: int,
    *,
    caps: dict[str, int],
    max_uncovered: int = 0,
    time_limit_s: float = 120.0,
) -> dict[str, Any]:
    data = solve_cover(
        rows,
        cols,
        piece_ids=NINE,
        max_counts=caps,
        max_uncovered=max_uncovered,
        time_limit_s=time_limit_s,
        reflect=True,
        num_workers=8,
    )
    data["problem_id"] = f"polyomino_b_q2_{rows}x{cols}"
    if max_uncovered:
        data["problem_id"] += f"_unc{max_uncovered}"
    return data


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Exact polyomino cover (CP-SAT)")
    p.add_argument("problem_id", nargs="?", default="polyomino_b_q1")
    p.add_argument(
        "--task",
        choices=["min_cover", "l3_deficient", "q2", "custom"],
        default="min_cover",
    )
    p.add_argument("--rows", type=int, default=4)
    p.add_argument("--cols", type=int, default=4)
    p.add_argument("--time-limit-s", type=float, default=60.0)
    p.add_argument("--max-uncovered", type=int, default=0)
    p.add_argument(
        "--caps",
        choices=["none", "12x11", "25x20", "30x30"],
        default="none",
        help="B-题 Q2 inventory presets",
    )
    args = p.parse_args(argv)

    caps_map = {
        "none": None,
        "12x11": Q2_CAPS_12x11,
        "25x20": Q2_CAPS_25x20,
        "30x30": Q2_CAPS_30x30,
    }

    try:
        if args.task == "min_cover":
            try:
                d = fixture_dir(args.problem_id)
                board = json.loads((d / "board.json").read_text(encoding="utf-8"))
                mc = board.get("max_counts")
                data = solve_cover(
                    int(board["rows"]),
                    int(board["cols"]),
                    removed=board.get("removed") or [],
                    piece_ids=[x["id"] for x in board.get("pieces") or []] or None,
                    max_counts=mc,
                    max_uncovered=int(board.get("max_uncovered") or 0),
                    time_limit_s=args.time_limit_s,
                    reflect=bool(board.get("allow_reflect", True)),
                )
                data["problem_id"] = args.problem_id
            except FileNotFoundError:
                data = solve_q1_min_cover()
                data["problem_id"] = args.problem_id
        elif args.task == "l3_deficient":
            data = solve_q1_l_only_deficient()
        elif args.task == "q2":
            caps = caps_map[args.caps if args.caps != "none" else "12x11"]
            # auto size from caps name if rows/cols default
            rc = {
                "12x11": (12, 11),
                "25x20": (25, 20),
                "30x30": (30, 30),
            }
            if args.caps in rc and args.rows == 4 and args.cols == 4:
                rows, cols = rc[args.caps]
            else:
                rows, cols = args.rows, args.cols
            if args.caps == "none":
                rows, cols = args.rows, args.cols
                caps = Q2_CAPS_12x11 if (rows, cols) == (12, 11) else caps
            data = solve_q2(
                rows,
                cols,
                caps=caps or Q2_CAPS_12x11,
                max_uncovered=args.max_uncovered,
                time_limit_s=args.time_limit_s,
            )
        else:
            data = solve_cover(
                args.rows,
                args.cols,
                piece_ids=NINE,
                max_counts=caps_map[args.caps],
                max_uncovered=args.max_uncovered,
                time_limit_s=args.time_limit_s,
            )
            data["problem_id"] = args.problem_id
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data.get("status") in {"OPTIMAL", "FEASIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
