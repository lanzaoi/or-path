#!/usr/bin/env python3
"""Validate solution.json against fixture problem data via recompute."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
# expose the repo root so the full orpath.domain_registry resolves under
# subprocess runs with the workdir as cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fixture_paths import fixture_dir, fixture_file  # noqa: E402

EPS = 1e-6



from validators.tube_cut import (
    _checks_envelope_tube,
    _tube_check,
    _tube_orientation_path_bound,
    _tube_validate_stocks,
    _validate_tube,
    _validate_tube_v2,
)

def _num_eq(a: float, b: float) -> bool:
    # Demo override: ORPATH_VALIDATE_ATOL / ORPATH_VALIDATE_RTOL relax the
    # cross-version numeric drift between shipped answers and re-validation.
    atol = float(os.environ.get("ORPATH_VALIDATE_ATOL", EPS))
    rtol = float(os.environ.get("ORPATH_VALIDATE_RTOL", "1e-9"))
    return abs(float(a) - float(b)) <= atol or (
        abs(float(a) - float(b)) / max(1.0, abs(float(b))) <= rtol
    )


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be object")
    return data


def _checks_envelope(sol: dict, pc: str) -> list[dict]:
    checks = []
    required = ["problem_id", "status", "objective", "solver", "source"]
    missing = [k for k in required if k not in sol]
    checks.append(
        {
            "name": "envelope",
            "ok": not missing and sol.get("status")
            in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "ERROR"},
            "detail": f"missing={missing}" if missing else None,
        }
    )
    if pc == "shortest_path":
        checks.append(
            {
                "name": "shape_path",
                "ok": bool(sol.get("path")),
                "detail": None if sol.get("path") else "path required",
            }
        )
    elif pc == "tsp":
        checks.append(
            {
                "name": "shape_tour",
                "ok": bool(sol.get("tour")),
                "detail": None if sol.get("tour") else "tour required",
            }
        )
    elif pc == "vrp":
        checks.append(
            {
                "name": "shape_routes",
                "ok": bool(sol.get("routes")),
                "detail": None if sol.get("routes") else "routes required",
            }
        )
    elif pc in {"polyomino_cover", "polyomino", "poly"}:
        pls = sol.get("placements")
        ok_pl = isinstance(pls, list) and len(pls) >= 1
        checks.append(
            {
                "name": "shape_placements",
                "ok": ok_pl,
                "detail": None if ok_pl else "placements list required",
            }
        )
    elif pc in {"microgrid_dispatch", "microgrid", "energy_storage"}:
        has_sub = "subproblems" in sol or "q1" in sol or "total_purchase_cost" in sol or "q1_objective" in sol
        checks.append(
            {
                "name": "shape_microgrid",
                "ok": has_sub,
                "detail": None if has_sub else "subproblems or q1 required in solution",
            }
        )
    elif pc in {"jssp", "job_shop"}:
        has_sched = bool(sol.get("schedule"))
        checks.append(
            {
                "name": "shape_schedule",
                "ok": has_sched,
                "detail": None if has_sched else "schedule required",
            }
        )
    elif pc in {"rcpsp", "project_scheduling", "psplib"}:
        has_sched = bool(sol.get("schedule"))
        checks.append(
            {
                "name": "shape_schedule",
                "ok": has_sched,
                "detail": None if has_sched else "schedule required",
            }
        )
    elif pc in {"bin_packing", "binpack", "knapsack"}:
        has_bins = bool(sol.get("bins"))
        checks.append(
            {
                "name": "shape_bins",
                "ok": has_bins,
                "detail": None if has_bins else "bins required",
            }
        )
    elif pc in {"facility_location", "facility", "cflp"}:
        has_fac = bool(sol.get("open_facilities"))
        checks.append(
            {
                "name": "shape_facilities",
                "ok": has_fac,
                "detail": None if has_fac else "open_facilities required",
            }
        )
    elif pc in {"portfolio_opt", "portfolio", "markowitz"}:
        has_alloc = bool(sol.get("allocations"))
        checks.append(
            {
                "name": "shape_allocations",
                "ok": has_alloc,
                "detail": None if has_alloc else "allocations required",
            }
        )
    elif pc in {"network_flow", "max_flow_matching", "bipartite_matching", "min_cost_flow"}:
        has_flow = bool(sol.get("active_flows") or sol.get("matches") or sol.get("commodity_flows"))
        checks.append(
            {
                "name": "shape_network_flow",
                "ok": has_flow,
                "detail": None if has_flow else "active_flows or matches required",
            }
        )
    elif pc in {"qubo_ising", "qubo", "ising", "max_cut"}:
        has_res = bool(sol.get("cut_edges") or sol.get("subset_a")
                       or sol.get("sample") or sol.get("spins"))
        checks.append(
            {
                "name": "shape_qubo",
                "ok": has_res,
                "detail": None if has_res else "cut_edges, subset_a, sample, or spins required",
            }
        )
    elif pc in {"qap", "quadratic_assignment", "facility_layout", "qaplib"}:
        has_perm = bool(sol.get("permutation"))
        checks.append(
            {
                "name": "shape_permutation",
                "ok": has_perm,
                "detail": None if has_perm else "permutation required",
            }
        )
    elif pc in {"graph_coloring", "vertex_coloring", "vcp", "coloring", "dimacs_col"}:
        has_nc = bool(sol.get("node_colors"))
        checks.append(
            {
                "name": "shape_node_colors",
                "ok": has_nc,
                "detail": None if has_nc else "node_colors required",
            }
        )
    elif pc in {"staff_rostering", "nurse_scheduling", "rostering", "shift_scheduling"}:
        has_roster = bool(sol.get("roster"))
        checks.append(
            {
                "name": "shape_roster",
                "ok": has_roster,
                "detail": None if has_roster else "roster required",
            }
        )
    elif pc in {"lot_sizing", "inventory_planning", "wagner_whitin", "clsp", "mrp"}:
        has_sched = bool(sol.get("schedule"))
        checks.append(
            {
                "name": "shape_schedule",
                "ok": has_sched,
                "detail": None if has_sched else "schedule required",
            }
        )
    elif pc in {"stochastic_lp", "stochastic_programming", "two_stage_lp", "farmer"}:
        has_dec = bool(sol.get("first_stage_decision"))
        checks.append(
            {
                "name": "shape_stochastic_lp",
                "ok": has_dec,
                "detail": None if has_dec else "first_stage_decision required",
            }
        )
    elif pc in {"max_clique", "clique", "maximum_clique", "max_independent_set", "mis", "independent_set"}:
        has_clique = bool(sol.get("clique_nodes")) or bool(sol.get("independent_set_nodes"))
        checks.append(
            {
                "name": "shape_clique",
                "ok": has_clique,
                "detail": None if has_clique else "clique_nodes or independent_set_nodes required",
            }
        )
    elif pc in {"game_theory", "game", "nash", "nash_equilibrium", "bimatrix"}:
        has_eq = bool(sol.get("primary_equilibrium")) or bool(sol.get("equilibria"))
        checks.append(
            {
                "name": "shape_equilibria",
                "ok": has_eq,
                "detail": None if has_eq else "primary_equilibrium or equilibria required",
            }
        )
    elif pc in {"hub_location", "hub", "hlp", "p_hub", "phub", "usahlp"}:
        has_hubs = bool(sol.get("selected_hubs"))
        checks.append(
            {
                "name": "shape_hubs",
                "ok": has_hubs,
                "detail": None if has_hubs else "selected_hubs required",
            }
        )
    return checks


def _validate_sp(problem_id: str, sol: dict) -> list[dict]:
    checks: list[dict] = []
    g = _load(fixture_file(problem_id, "graph.json"))
    edges = {(e["u"], e["v"]): float(e["w"]) for e in g.get("edges") or []}
    path = list(sol.get("path") or [])
    if len(path) < 2:
        checks.append({"name": "feasibility", "ok": False, "detail": "path too short"})
        return checks
    total = 0.0
    ok = True
    for a, b in zip(path, path[1:]):
        if (a, b) not in edges:
            ok = False
            checks.append(
                {
                    "name": "feasibility",
                    "ok": False,
                    "detail": f"missing edge {a}->{b}",
                }
            )
            break
        total += edges[(a, b)]
    if ok:
        checks.append({"name": "feasibility", "ok": True})
        obj = float(sol["objective"])
        checks.append(
            {
                "name": "recompute_objective",
                "ok": _num_eq(total, obj),
                "expected": total if float(total).is_integer() else total,
                "got": sol["objective"],
            }
        )
    return checks


def _matrix_and_labels(problem_id: str) -> tuple[list[list[float]], list[str]]:
    d = fixture_dir(problem_id)
    if (d / "distance_matrix.json").is_file():
        raw = _load(d / "distance_matrix.json")
        matrix = raw["matrix"] if "matrix" in raw else raw
        labels = raw.get("labels") or [str(i) for i in range(len(matrix))]
        return matrix, [str(x) for x in labels]
    coords_path = d / "coords.json"
    if not coords_path.is_file() and (d / "data" / "coords.json").is_file():
        coords_path = d / "data" / "coords.json"
    coords = _load(coords_path)
    if isinstance(coords, dict):
        coords = coords["coords"]
    labels = [str(c.get("id", i)) for i, c in enumerate(coords)]
    n = len(coords)
    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dx = float(coords[i]["x"]) - float(coords[j]["x"])
            dy = float(coords[i]["y"]) - float(coords[j]["y"])
            mat[i][j] = float(int(round(math.hypot(dx, dy))))
    return mat, labels


def _validate_tsp(problem_id: str, sol: dict) -> list[dict]:
    checks: list[dict] = []
    matrix, labels = _matrix_and_labels(problem_id)
    idx = {lab: i for i, lab in enumerate(labels)}
    tour = [str(x) for x in (sol.get("tour") or [])]
    if len(tour) < 2 or tour[0] != tour[-1]:
        checks.append(
            {
                "name": "feasibility",
                "ok": False,
                "detail": "tour must start and end at same node",
            }
        )
        return checks
    core = tour[:-1]
    if sorted(core) != sorted(labels):
        checks.append(
            {
                "name": "feasibility",
                "ok": False,
                "detail": f"tour must visit each city once; got {core}",
            }
        )
        return checks
    total = 0.0
    for a, b in zip(tour, tour[1:]):
        total += float(matrix[idx[a]][idx[b]])
    checks.append({"name": "feasibility", "ok": True})
    checks.append(
        {
            "name": "recompute_objective",
            "ok": _num_eq(total, float(sol["objective"])),
            "expected": int(total) if float(total).is_integer() else total,
            "got": sol["objective"],
        }
    )
    return checks


def _validate_vrp(problem_id: str, sol: dict) -> list[dict]:
    checks: list[dict] = []
    data = _load(fixture_file(problem_id, "locations.json"))
    locations = data["locations"]
    labels = [str(loc["id"]) for loc in locations]
    depot = str(data.get("depot", labels[0]))
    capacities = [int(c) for c in data["capacities"]]
    vehicle_count = int(data["vehicle_count"])
    demands_raw = data["demands"]
    if isinstance(demands_raw, dict):
        demands = {str(k): int(v) for k, v in demands_raw.items()}
    else:
        demands = {labels[i]: int(demands_raw[i]) for i in range(len(labels))}

    if "distance_matrix" in data:
        matrix = data["distance_matrix"]
    else:
        coords = [{"x": loc["x"], "y": loc["y"]} for loc in locations]
        n = len(coords)
        matrix = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                dx = float(coords[i]["x"]) - float(coords[j]["x"])
                dy = float(coords[i]["y"]) - float(coords[j]["y"])
                matrix[i][j] = int(round(math.hypot(dx, dy)))
    idx = {lab: i for i, lab in enumerate(labels)}

    tw_raw = data.get("time_windows") or {}
    st_raw = data.get("service_times") or {}
    has_tw = bool(tw_raw)
    tw: dict[str, tuple[int, int]] = {}
    st: dict[str, int] = {}
    if has_tw:
        for lab in labels:
            if isinstance(tw_raw, dict) and lab in tw_raw:
                lo, hi = tw_raw[lab]
                tw[lab] = (int(lo), int(hi))
            else:
                tw[lab] = (0, 10**9)
            st[lab] = int(st_raw.get(lab, 0)) if isinstance(st_raw, dict) else 0

    routes = sol.get("routes") or []
    checks.append(
        {
            "name": "vehicle_count_meta",
            "ok": vehicle_count >= 2,
            "detail": f"fixture vehicle_count={vehicle_count}",
        }
    )

    customers = [lab for lab in labels if lab != depot]
    seen: list[str] = []
    total = 0.0
    cap_ok = True
    tw_ok = True
    for ri, route in enumerate(routes):
        r = [str(x) for x in route]
        load = 0
        for node in r:
            if node == depot:
                continue
            load += demands.get(node, 0)
            seen.append(node)
        cap = capacities[min(ri, len(capacities) - 1)]
        if load > cap:
            cap_ok = False
            checks.append(
                {
                    "name": "capacity",
                    "ok": False,
                    "detail": f"route {ri} load {load} > cap {cap}",
                }
            )
        for a, b in zip(r, r[1:]):
            total += float(matrix[idx[a]][idx[b]])

        if has_tw and len(r) >= 2:
            # Simulate: start at depot at time max(0, ready_depot); wait allowed.
            t = float(tw[depot][0])
            for a, b in zip(r, r[1:]):
                travel = float(matrix[idx[a]][idx[b]])
                # leave a after service (depot service 0)
                # time at arrival to b
                arrive = t + travel
                ready, due = tw[b]
                start_service = max(arrive, float(ready))
                if b != depot and start_service > float(due) + 1e-9:
                    tw_ok = False
                    checks.append(
                        {
                            "name": "time_windows",
                            "ok": False,
                            "detail": (
                                f"route {ri} node {b}: start_service={start_service} "
                                f"> due={due} (arrive={arrive})"
                            ),
                        }
                    )
                # after service at b
                t = start_service + float(st.get(b, 0))
                # also ensure a started within window when leaving (except pure start)
                if a != depot or r.index(a) != 0:
                    pass

    if cap_ok:
        checks.append({"name": "capacity", "ok": True})

    if has_tw and tw_ok:
        checks.append({"name": "time_windows", "ok": True})
    elif not has_tw:
        checks.append(
            {
                "name": "time_windows",
                "ok": True,
                "detail": "no time_windows in fixture (T2-style CVRP)",
            }
        )

    if sorted(seen) != sorted(customers) or len(seen) != len(customers):
        checks.append(
            {
                "name": "feasibility",
                "ok": False,
                "detail": f"customers coverage bad seen={seen} need={customers}",
            }
        )
    else:
        checks.append({"name": "feasibility", "ok": True})

    checks.append(
        {
            "name": "recompute_objective",
            "ok": _num_eq(total, float(sol["objective"])),
            "expected": int(total) if float(total).is_integer() else total,
            "got": sol["objective"],
        }
    )
    return checks



def _cell_tuple(cell: Any) -> tuple[int, int] | None:
    if isinstance(cell, (list, tuple)) and len(cell) >= 2:
        try:
            return int(cell[0]), int(cell[1])
        except (TypeError, ValueError):
            return None
    if isinstance(cell, dict) and "r" in cell and "c" in cell:
        try:
            return int(cell["r"]), int(cell["c"])
        except (TypeError, ValueError):
            return None
    return None


def _cells_connected(cells: list[tuple[int, int]]) -> bool:
    if not cells:
        return False
    s = set(cells)
    if len(s) != len(cells):
        return False  # internal dup
    start = cells[0]
    stack = [start]
    seen = {start}
    while stack:
        r, c = stack.pop()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            n = (r + dr, c + dc)
            if n in s and n not in seen:
                seen.add(n)
                stack.append(n)
    return len(seen) == len(s)


def _load_polyomino_board(problem_id: str, sol: dict) -> dict[str, Any]:
    """Board geometry from fixture board.json, sol.meta, or sol fields."""
    board: dict[str, Any] = {}
    try:
        d = fixture_dir(problem_id)
        bp = d / "board.json"
        if bp.is_file():
            board = _load(bp)
    except FileNotFoundError:
        board = {}
    meta = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
    rows = board.get("rows") or meta.get("rows") or sol.get("rows")
    cols = board.get("cols") or meta.get("cols") or sol.get("cols")
    removed = board.get("removed") or meta.get("removed") or sol.get("removed") or []
    must_cover = board.get("must_cover_all", True)
    pieces = board.get("pieces") or []
    size_by_id: dict[str, int] = {}
    for p in pieces:
        if isinstance(p, dict) and p.get("id") is not None:
            if "size" in p:
                size_by_id[str(p["id"])] = int(p["size"])
    # defaults for common pieces
    defaults = {"M": 1, "D": 2, "L3": 3, "I3": 3, "S": 4, "I4": 4, "T4": 4, "L4": 4, "Z4": 4}
    for k, v in defaults.items():
        size_by_id.setdefault(k, v)
    return {
        "rows": int(rows) if rows is not None else None,
        "cols": int(cols) if cols is not None else None,
        "removed": {(int(a), int(b)) for a, b in (removed or [])},
        "must_cover_all": bool(must_cover),
        "size_by_id": size_by_id,
        "cells_declared": board.get("cells"),
    }


def _validate_polyomino(problem_id: str, sol: dict) -> list[dict]:
    """Recompute polyomino cover feasibility + piece-count objective.

    Does not re-run CP-SAT. Checks placements cover board without overlap;
    objective == len(placements) (minimize piece count convention).
    """
    checks: list[dict] = []
    pc = str(sol.get("problem_class") or "").lower()
    try:
        root = Path(__file__).resolve().parents[1]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from orpath.domain_registry import is_polyomino_class

        pc_ok = is_polyomino_class(pc)
    except Exception:  # noqa: BLE001
        pc_ok = pc in {"polyomino", "polyomino_cover", "poly", "polyomino_tiling"}
    checks.append(
        {
            "name": "problem_class",
            "ok": pc_ok,
            "detail": None if pc_ok else f"not polyomino: {pc}",
        }
    )
    src = str(sol.get("source") or "")
    solver = str(sol.get("solver") or "")
    poly_src = (
        "polyomino" in src.lower()
        or "polyomino" in solver.lower()
        or "solve_polyomino" in src
    )
    checks.append(
        {
            "name": "polyomino_source",
            "ok": poly_src,
            "detail": None if poly_src else f"source/solver not polyomino: {src!r}/{solver!r}",
        }
    )

    placements = sol.get("placements")
    if not isinstance(placements, list) or not placements:
        checks.append(
            {"name": "feasibility", "ok": False, "detail": "placements empty/missing"}
        )
        return checks

    board = _load_polyomino_board(problem_id, sol)
    rows, cols = board["rows"], board["cols"]
    removed: set[tuple[int, int]] = board["removed"]
    size_by_id: dict[str, int] = board["size_by_id"]

    if rows is None or cols is None:
        all_c: list[tuple[int, int]] = []
        for pl in placements:
            if not isinstance(pl, dict):
                continue
            for c in pl.get("cells") or []:
                t = _cell_tuple(c)
                if t:
                    all_c.append(t)
        if not all_c:
            checks.append(
                {"name": "board_geometry", "ok": False, "detail": "no cells / no board"}
            )
            return checks
        rows = max(r for r, _ in all_c) + 1
        cols = max(c for _, c in all_c) + 1
        checks.append(
            {
                "name": "board_geometry",
                "ok": True,
                "detail": f"inferred rows={rows} cols={cols}",
            }
        )
    else:
        checks.append(
            {
                "name": "board_geometry",
                "ok": True,
                "detail": f"rows={rows} cols={cols} removed={len(removed)}",
            }
        )

    board_cells = {
        (r, c)
        for r in range(int(rows))
        for c in range(int(cols))
        if (r, c) not in removed
    }
    covered: dict[tuple[int, int], int] = {}
    feas_ok = True
    feas_detail: str | None = None
    connected_ok = True

    for i, pl in enumerate(placements):
        if not isinstance(pl, dict):
            feas_ok = False
            feas_detail = f"placement[{i}] not object"
            break
        piece = str(pl.get("piece") or pl.get("id") or "")
        cells: list[tuple[int, int]] = []
        for c in pl.get("cells") or []:
            t = _cell_tuple(c)
            if t is None:
                feas_ok = False
                feas_detail = f"placement[{i}] bad cell {c!r}"
                break
            cells.append(t)
        if not feas_ok:
            break
        if not cells:
            feas_ok = False
            feas_detail = f"placement[{i}] empty cells"
            break
        declared_size = pl.get("size")
        if declared_size is not None and int(declared_size) != len(cells):
            feas_ok = False
            feas_detail = f"placement[{i}] size={declared_size} != n_cells={len(cells)}"
            break
        if piece in size_by_id and size_by_id[piece] != len(cells):
            feas_ok = False
            feas_detail = (
                f"placement[{i}] piece {piece} expects size {size_by_id[piece]} "
                f"got {len(cells)}"
            )
            break
        if not _cells_connected(cells):
            connected_ok = False
            feas_ok = False
            feas_detail = f"placement[{i}] cells not 4-connected"
            break
        for cell in cells:
            if cell not in board_cells:
                feas_ok = False
                feas_detail = f"placement[{i}] cell {cell} outside board/removed"
                break
            if cell in covered:
                feas_ok = False
                feas_detail = f"overlap at {cell} (placements {covered[cell]} and {i})"
                break
            covered[cell] = i
        if not feas_ok:
            break

    if feas_ok and board.get("must_cover_all", True):
        missing = board_cells - set(covered)
        if missing:
            feas_ok = False
            sample = sorted(missing)[:5]
            feas_detail = f"uncovered cells n={len(missing)} sample={sample}"

    checks.append({"name": "feasibility", "ok": feas_ok, "detail": feas_detail})
    checks.append(
        {
            "name": "connectivity",
            "ok": connected_ok,
            "detail": None if connected_ok else "some placement not 4-connected",
        }
    )

    n_pieces = len(placements)
    try:
        obj = float(sol["objective"])
        checks.append(
            {
                "name": "recompute_objective",
                "ok": _num_eq(obj, n_pieces),
                "expected": n_pieces,
                "got": sol.get("objective"),
                "detail": "objective == len(placements)",
            }
        )
    except (TypeError, ValueError, KeyError) as exc:
        checks.append({"name": "recompute_objective", "ok": False, "detail": str(exc)})

    if sol.get("piece_count") is not None:
        try:
            pc_val = int(sol["piece_count"])
            checks.append(
                {
                    "name": "piece_count_match",
                    "ok": pc_val == n_pieces,
                    "expected": n_pieces,
                    "got": pc_val,
                }
            )
        except (TypeError, ValueError):
            checks.append(
                {"name": "piece_count_match", "ok": False, "detail": "piece_count not int"}
            )

    meta = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
    if str(sol.get("status") or "").upper() == "OPTIMAL" and meta.get("exact") is False:
        checks.append(
            {
                "name": "optimality_claim",
                "ok": False,
                "detail": "OPTIMAL with meta.exact=false",
            }
        )
    else:
        checks.append({"name": "optimality_claim", "ok": True})

    return checks



def validate(problem_id: str, solution: dict, gold: dict | None = None) -> dict:
    pc = str(
        solution.get("problem_class")
        or (gold or {}).get("problem_class")
        or "shortest_path"
    ).lower()
    # aliases
    if pc in {"tube", "tube_bfd", "cutting_stock", "cut_stock"}:
        pc_norm = "tube_cut"
    elif pc in {"polyomino", "poly", "polyomino_tiling", "tiling_cover"}:
        pc_norm = "polyomino_cover"
    else:
        try:
            from orpath.domain_registry import normalize_problem_class

            pc_norm = normalize_problem_class(pc) or pc
        except Exception:  # noqa: BLE001
            pc_norm = pc

    checks = (
        _checks_envelope_tube(solution)
        if pc_norm == "tube_cut"
        else _checks_envelope(solution, pc_norm)
    )

    if solution.get("status") in {"INFEASIBLE", "ERROR", "BLOCKED"}:
        report = {
            "ok": False,
            "problem_id": problem_id,
            "problem_class": pc_norm,
            "checks": checks,
            "errors": [f"status={solution.get('status')}"],
        }
        return report

    if pc_norm == "shortest_path":
        checks.extend(_validate_sp(problem_id, solution))
    elif pc_norm == "tsp":
        checks.extend(_validate_tsp(problem_id, solution))
    elif pc_norm == "vrp":
        checks.extend(_validate_vrp(problem_id, solution))
    elif pc_norm == "tube_cut":
        checks.extend(_validate_tube(problem_id, solution))
    elif pc_norm == "polyomino_cover":
        checks.extend(_validate_polyomino(problem_id, solution))
    elif pc_norm == "microgrid_dispatch":
        from validators.microgrid_dispatch import validate_microgrid
        checks.extend(validate_microgrid(problem_id, solution))
    elif pc_norm == "jssp":
        from validators.extended_solvers import validate_jssp
        checks.extend(validate_jssp(problem_id, solution))
    elif pc_norm == "rcpsp":
        from validators.extended_solvers import validate_rcpsp
        checks.extend(validate_rcpsp(problem_id, solution))
    elif pc_norm == "bin_packing":
        from validators.extended_solvers import validate_bin_packing
        checks.extend(validate_bin_packing(problem_id, solution))
    elif pc_norm == "facility_location":
        from validators.extended_solvers import validate_facility_location
        checks.extend(validate_facility_location(problem_id, solution))
    elif pc_norm == "portfolio_opt":
        from validators.extended_solvers import validate_portfolio
        checks.extend(validate_portfolio(problem_id, solution))
    elif pc_norm == "network_flow":
        from validators.extended_solvers import validate_network_flow
        checks.extend(validate_network_flow(problem_id, solution))
    elif pc_norm == "qubo_ising":
        from validators.extended_solvers import validate_qubo_ising
        checks.extend(validate_qubo_ising(problem_id, solution))
    elif pc_norm == "staff_rostering":
        from validators.extended_solvers import validate_staff_rostering
        checks.extend(validate_staff_rostering(problem_id, solution))
    elif pc_norm == "lot_sizing":
        from validators.extended_solvers import validate_lot_sizing
        checks.extend(validate_lot_sizing(problem_id, solution))
    elif pc_norm == "qap":
        from validators.extended_solvers import validate_qap
        checks.extend(validate_qap(problem_id, solution))
    elif pc_norm == "graph_coloring":
        from validators.extended_solvers import validate_graph_coloring
        checks.extend(validate_graph_coloring(problem_id, solution))
    elif pc_norm == "stochastic_lp":
        from validators.extended_solvers import validate_stochastic_lp
        checks.extend(validate_stochastic_lp(problem_id, solution))
    elif pc_norm == "max_clique":
        from validators.extended_solvers import validate_max_clique
        checks.extend(validate_max_clique(problem_id, solution))
    elif pc_norm == "game_theory":
        from validators.extended_solvers import validate_game_theory
        checks.extend(validate_game_theory(problem_id, solution))
    elif pc_norm == "hub_location":
        from validators.extended_solvers import validate_hub_location
        checks.extend(validate_hub_location(problem_id, solution))
    elif pc_norm == "pyvrp" or pc_norm == "vrp_pdp" or solution.get("solver") == "pyvrp-hgs":
        from validators.extended_solvers import validate_pyvrp
        checks.extend(validate_pyvrp(problem_id, solution))
    else:
        checks.append(
            {"name": "problem_class", "ok": False, "detail": f"unknown class {pc}"}
        )

    if gold and "objective" in gold and solution.get("status") in {
        "OPTIMAL",
        "FEASIBLE",
    }:
        # only gold-gap for fixture classes, not tube contest heuristics unless gold provided intentionally
        if pc_norm != "tube_cut" or gold.get("problem_class"):
            gap = abs(float(solution["objective"]) - float(gold["objective"]))
            checks.append(
                {
                    "name": "gold_gap",
                    "ok": _num_eq(solution["objective"], gold["objective"]),
                    "expected": gold["objective"],
                    "got": solution["objective"],
                    "detail": f"gap={gap}",
                }
            )

    errors = [
        c.get("detail") or c["name"]
        for c in checks
        if not c.get("ok")
    ]
    ok = all(c.get("ok") for c in checks)
    return {
        "ok": ok,
        "problem_id": problem_id,
        "problem_class": pc_norm,
        "checks": checks,
        "errors": errors,
    }



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate OR-Path solution JSON")
    parser.add_argument("--problem-id", required=True)
    parser.add_argument("--solution", type=Path, required=True)
    parser.add_argument("--gold", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    sol = _load(args.solution)
    gold = None
    if args.gold and args.gold.is_file():
        gold = _load(args.gold)
    else:
        try:
            gold = _load(fixture_file(args.problem_id, "solution.json"))
        except FileNotFoundError:
            gold = None
    report = validate(args.problem_id, sol, gold)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
