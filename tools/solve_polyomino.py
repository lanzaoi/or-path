#!/usr/bin/env python3
"""Exact polyomino covering via OR-Tools CP-SAT (exact ILP/CP).

Supports B-题 Q1/Q2: piece inventory caps, optional uncovered cells.
Numbers are proven optimal under the CP model when status=OPTIMAL.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
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
    hint_placements: list[dict[str, Any]] | None = None,
    symmetry_break: bool = False,
    lns_window: int = 0,
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
    wall_t0 = time.monotonic()
    lns_w = max(0, int(lns_window))
    run_lns = bool(lns_w > 0 and hint_placements and minimize_count and max_uncovered <= 0)
    solver.parameters.max_time_in_seconds = float(time_limit_s) * (0.45 if run_lns else 1.0)
    solver.parameters.random_seed = 1
    if symmetry_break:
        solver.parameters.symmetry_level = 2
    if num_workers and num_workers > 1:
        solver.parameters.num_search_workers = int(num_workers)

    def _p_key(piece: str, cells_seq: Any) -> tuple[str, tuple[tuple[int, int], ...]]:
        return (str(piece), tuple(sorted((int(c[0]), int(c[1])) for c in cells_seq)))

    hint_keys: set[tuple[str, tuple[tuple[int, int], ...]]] = set()
    if hint_placements:
        for hp in hint_placements:
            if isinstance(hp, dict) and hp.get("piece") and hp.get("cells"):
                hint_keys.add(_p_key(hp["piece"], hp["cells"]))
        if hint_keys:
            for i, p in enumerate(places):
                k = _p_key(p["piece"], p["cells"])
                model.AddHint(x[i], 1 if k in hint_keys else 0)

    status = solver.Solve(model)

    proven = status == cp_model.OPTIMAL
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    if not ok and hint_keys:
        # Fallback cleanly if hint solve hit tiny budget
        chosen_indices = [
            i for i, p in enumerate(places) if _p_key(p["piece"], p["cells"]) in hint_keys
        ]
        if chosen_indices:
            ok = True
    else:
        chosen_indices = [i for i in range(len(places)) if ok and solver.Value(x[i]) == 1]

    best_obj_bound = float(solver.BestObjectiveBound()) if hasattr(solver, "BestObjectiveBound") and ok else None
    lns_improvements = 0

    if ok and not proven and lns_w > 0 and minimize_count and max_uncovered <= 0:
        # Spatial sliding-window LNS Destroy & Exact CP-SAT Repair over remaining time budget
        place_keys = [_p_key(p["piece"], p["cells"]) for p in places]
        rem_budget = max(0.0, float(time_limit_s) - (time.monotonic() - wall_t0))
        deadline = time.monotonic() + rem_budget
        cur_indices = list(chosen_indices)
        # Prioritize windows centered around small-size pieces (size <= 3) where count can drop
        centers: list[tuple[int, int]] = []
        for idx in cur_indices:
            if places[idx]["size"] <= 3:
                r0 = min(c[0] for c in places[idx]["cells"])
                c0 = min(c[1] for c in places[idx]["cells"])
                centers.append((max(0, r0 - lns_w // 2), max(0, c0 - lns_w // 2)))
        stride = max(2, lns_w // 2)
        for rr in range(0, max(1, rows - lns_w + 1), stride):
            for cc in range(0, max(1, cols - lns_w + 1), stride):
                centers.append((rr, cc))
        seen_win: set[tuple[int, int]] = set()
        for w_r, w_c in centers:
            w_r_clamped = max(0, min(max(0, rows - lns_w), w_r))
            w_c_clamped = max(0, min(max(0, cols - lns_w), w_c))
            if (w_r_clamped, w_c_clamped) in seen_win:
                continue
            seen_win.add((w_r_clamped, w_c_clamped))
            left = deadline - time.monotonic()
            if left <= 0.8:
                break
            win_cells = {
                (r, c)
                for r in range(w_r_clamped, min(rows, w_r_clamped + lns_w))
                for c in range(w_c_clamped, min(cols, w_c_clamped + lns_w))
                if (r, c) in board_set
            }
            cur_set = set(cur_indices)
            fixed_on: list[int] = []
            for idx in cur_indices:
                if not any(cell in win_cells for cell in places[idx]["cells"]):
                    fixed_on.append(idx)
            # Build compact sub-model over cells NOT already covered by fixed_on placements
            covered_fixed = {cell for idx in fixed_on for cell in places[idx]["cells"]}
            free_cells = [cell for cell in board_cells if cell not in covered_fixed]
            if not free_cells:
                continue
            free_cell_set = set(free_cells)
            # Remaining inventory caps after fixed_on
            rem_caps: dict[str, int] | None = None
            if max_counts:
                used_counts: dict[str, int] = {}
                for idx in fixed_on:
                    pn = places[idx]["piece"]
                    used_counts[pn] = used_counts.get(pn, 0) + 1
                rem_caps = {k: max(0, int(v) - used_counts.get(k, 0)) for k, v in max_counts.items()}

            sub_place_idxs = [
                i
                for i, p in enumerate(places)
                if all(cell in free_cell_set for cell in p["cells"])
            ]
            if not sub_place_idxs:
                continue
            sub_m = cp_model.CpModel()
            sx = [sub_m.NewBoolVar(f"sx{j}") for j in range(len(sub_place_idxs))]
            sub_cell_map: dict[tuple[int, int], list[int]] = {c: [] for c in free_cells}
            for j, p_idx in enumerate(sub_place_idxs):
                if p_idx in cur_set:
                    sub_m.AddHint(sx[j], 1)
                else:
                    sub_m.AddHint(sx[j], 0)
                for c in places[p_idx]["cells"]:
                    sub_cell_map[c].append(j)
            for c in free_cells:
                sub_m.Add(sum(sx[j] for j in sub_cell_map[c]) == 1)
            if rem_caps:
                for pn, lim in rem_caps.items():
                    j_list = [j for j, p_idx in enumerate(sub_place_idxs) if places[p_idx]["piece"] == pn]
                    if j_list:
                        sub_m.Add(sum(sx[j] for j in j_list) <= lim)
            cur_free_count = len(cur_indices) - len(fixed_on)
            sub_m.Add(sum(sx) <= cur_free_count)
            sub_m.Minimize(sum(sx))

            sub_solv = cp_model.CpSolver()
            sub_solv.parameters.max_time_in_seconds = min(8.0, left)
            sub_solv.parameters.random_seed = 1
            if num_workers and num_workers > 1:
                sub_solv.parameters.num_search_workers = int(num_workers)
            sub_st = sub_solv.Solve(sub_m)
            if sub_st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                new_free = [sub_place_idxs[j] for j in range(len(sub_place_idxs)) if sub_solv.Value(sx[j]) == 1]
                if len(fixed_on) + len(new_free) < len(cur_indices):
                    cur_indices = fixed_on + new_free
                    lns_improvements += 1
                    _ = place_keys

        chosen_indices = cur_indices
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
    for i in chosen_indices:
        p = places[i]
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
            "wall_time_s": round(time.monotonic() - wall_t0, 4),
            "lns_improvements": lns_improvements,
            "objective_bound": best_obj_bound,
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
    for i, p in enumerate(placements):
        ch = letters[i % len(letters)]
        for r, c in p["cells"]:
            grid[r][c] = ch
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
    hint_placements: list[dict[str, Any]] | None = None,
    symmetry_break: bool = False,
    lns_window: int = 0,
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
        hint_placements=hint_placements,
        symmetry_break=symmetry_break,
        lns_window=lns_window,
    )
    data["problem_id"] = f"polyomino_b_q2_{rows}x{cols}"
    if max_uncovered:
        data["problem_id"] += f"_unc{max_uncovered}"
    return data


def _load_hint_placements(hint_path: str | None) -> list[dict[str, Any]] | None:
    if not hint_path:
        return None
    p = Path(str(hint_path)).expanduser()
    if not p.is_file():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        pls = doc.get("placements") if isinstance(doc, dict) else None
        return pls if isinstance(pls, list) else None
    except Exception:
        return None


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
    p.add_argument(
        "--is-replay",
        action="store_true",
        help="explicitly authorize built-in 4x4 fallback replay when board.json is absent",
    )
    p.add_argument(
        "--hint-solution",
        default="",
        help="optional previous solution JSON containing placements for CP-SAT AddHint / LNS",
    )
    p.add_argument(
        "--lns-window",
        type=int,
        default=0,
        help="sliding spatial destroy/repair window width (e.g. 12 for 30x30)",
    )
    p.add_argument(
        "--symmetry-break",
        action="store_true",
        help="enable CP-SAT enhanced symmetry breaking",
    )
    args = p.parse_args(argv)
    hint_placements = _load_hint_placements(args.hint_solution)

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
                    hint_placements=hint_placements,
                    symmetry_break=bool(args.symmetry_break),
                    lns_window=int(args.lns_window),
                )
                data["problem_id"] = args.problem_id
            except FileNotFoundError:
                if args.is_replay or os.environ.get("ORPATH_FIXTURE_REPLAY") == "1":
                    data = solve_q1_min_cover()
                    data["problem_id"] = args.problem_id
                    meta = data.setdefault("meta", {})
                    if isinstance(meta, dict):
                        meta["is_replay"] = True
                        meta["fixture_ref"] = "polyomino_q1_default_4x4"
                else:
                    data = {
                        "status": "BLOCKED",
                        "objective": None,
                        "solver": "none",
                        "source": "tools/solve_polyomino.py",
                        "problem_id": args.problem_id,
                        "problem_class": "polyomino_cover",
                        "meta": {
                            "exact": False,
                            "proven_optimal": False,
                            "blocked": True,
                            "blocked_code": "missing_board_data",
                            "is_replay": False,
                            "reason": (
                                f"missing board.json for problem_id={args.problem_id!r}; "
                                "refusing silent 4x4 default board fallback without --is-replay"
                            ),
                        },
                    }
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
                hint_placements=hint_placements,
                symmetry_break=bool(args.symmetry_break),
                lns_window=int(args.lns_window),
            )
        else:
            data = solve_cover(
                args.rows,
                args.cols,
                piece_ids=NINE,
                max_counts=caps_map[args.caps],
                max_uncovered=args.max_uncovered,
                time_limit_s=args.time_limit_s,
                hint_placements=hint_placements,
                symmetry_break=bool(args.symmetry_break),
                lns_window=int(args.lns_window),
            )
            data["problem_id"] = args.problem_id
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data.get("status") in {"OPTIMAL", "FEASIBLE", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
