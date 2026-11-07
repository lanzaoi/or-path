#!/usr/bin/env python3
"""Full-scale Industrial Bin Packing & Sheet-Nesting Solver.

Upgraded from the legacy OR-Tools 1D MIP into a tri-mode industrial adapter:

* ``--mode 3d`` (default) — 3D container / pallet loading via ``py3dbp``
  (``Packer`` / ``Bin`` / ``Item``).  The backend explores all **6 degrees of
  freedom** rotation of every item, ships standard industrial shipping
  containers (20GP / 40GP / 40HQ) and Euro-pallet bins together with a typical
  cargo manifest, and reports per-bin **volume utilization**, **weight
  utilization** and the exact placed coordinates ``[x, y, z, dx, dy, dz]``.

* ``--mode 2d`` — 2D rectangular cutting-stock / sheet nesting via ``rectpack``
  (MaxRects BSSF + BNF/BFF/BBF/Global bin-selection).  Supports multiple
  standard board/sheet sizes and multi-part cutting, reporting per-part
  ``[x, y, w, h]`` coordinates and per-sheet **area utilization**.

* ``--mode 1d`` — legacy OR-Tools 1D bin-packing / knapsack MIP.  Kept
  byte-for-byte backward compatible (``solve_bin_packing``) and proven optimal.

Every mode emits the standard OR-Path "Numbers Truth" contract envelope:
``problem_id, problem_class='bin_packing', status, objective, bins, meta``
plus ``solver`` / ``source``.  Objective values and coordinates are taken
strictly from the solver; heuristics report ``status='FEASIBLE'`` while the
proven MIP reports ``status='OPTIMAL'``.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# Sibling-import shim: works both as a script and when invoked in-process by
# solve_dispatch._try_in_proc.
_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from ortools.linear_solver import pywraplp  # noqa: E402

_SOURCE = "tools/solve_binpack.py"

# Rotation-type name map for the 6-DOF orientation of a packed item.
_ROTATION_NAMES = {
    0: "RT_WHD",  # W x H x D
    1: "RT_HWD",  # H x W x D
    2: "RT_HDW",  # H x D x W
    3: "RT_DHW",  # D x H x W
    4: "RT_DWH",  # D x W x H
    5: "RT_WDH",  # W x D x H
}


# ===========================================================================
# 1D — Legacy OR-Tools Bin Packing / Knapsack (backward compatible)
# ===========================================================================
def solve_bin_packing(
    weights: list[int] | None = None,
    bin_capacity: int = 100,
    time_limit_s: float = 30.0,
) -> dict[str, Any]:
    """Solve 1D Bin Packing minimizing bins used (OR-Tools MIP).

    Kept fully backward compatible with the original signature and envelope so
    that ``tools/test_extended_solvers.py`` and the dispatch pipeline keep
    passing.
    """
    if weights is None:
        # Standard benchmark items
        weights = [48, 30, 19, 19, 36, 36, 27, 42, 42, 36, 24, 30]

    num_items = len(weights)
    num_bins = num_items  # Upper bound on bins needed

    solver = pywraplp.Solver.CreateSolver("SCIP") or pywraplp.Solver.CreateSolver("GLOP")
    if not solver:
        # Fallback to CBC or basic solver
        solver = pywraplp.Solver("binpack", pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)

    # x[i, j] = 1 if item i is placed in bin j
    x = {}
    for i in range(num_items):
        for j in range(num_bins):
            x[i, j] = solver.BoolVar(f"x_{i}_{j}")

    # y[j] = 1 if bin j is used
    y = {}
    for j in range(num_bins):
        y[j] = solver.BoolVar(f"y_{j}")

    # Constraint 1: Each item must be in exactly one bin
    for i in range(num_items):
        solver.Add(solver.Sum([x[i, j] for j in range(num_bins)]) == 1)

    # Constraint 2: Sum of weights in bin j <= capacity * y[j]
    for j in range(num_bins):
        solver.Add(
            solver.Sum([weights[i] * x[i, j] for i in range(num_items)])
            <= bin_capacity * y[j]
        )

    # Objective: Minimize number of bins used
    solver.Minimize(solver.Sum([y[j] for j in range(num_bins)]))
    solver.SetTimeLimit(int(time_limit_s * 1000))

    status = solver.Solve()
    is_optimal = status == pywraplp.Solver.OPTIMAL
    is_feasible = status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE)

    if not is_feasible:
        return {
            "problem_id": f"binpack_{num_items}items_cap{bin_capacity}",
            "problem_class": "bin_packing",
            "status": "INFEASIBLE" if status == pywraplp.Solver.INFEASIBLE else "ERROR",
            "objective": -1,
            "solver": "ortools-scip-binpack",
            "source": _SOURCE,
            "bins": [],
        }

    used_bins = []
    for j in range(num_bins):
        if y[j].solution_value() > 0.5:
            bin_items = [i for i in range(num_items) if x[i, j].solution_value() > 0.5]
            bin_weight = sum(weights[i] for i in bin_items)
            used_bins.append({
                "bin_id": len(used_bins),
                "items": bin_items,
                "weights": [weights[i] for i in bin_items],
                "total_weight": bin_weight,
                "utilization": round(bin_weight / bin_capacity, 4),
            })

    total_weight = sum(weights)
    lower_bound = (total_weight + bin_capacity - 1) // bin_capacity

    return {
        "problem_id": f"binpack_{num_items}items_cap{bin_capacity}",
        "problem_class": "bin_packing",
        "status": "OPTIMAL" if is_optimal else "FEASIBLE",
        "objective": len(used_bins),
        "solver": "ortools-scip-binpack",
        "source": _SOURCE,
        "num_items": num_items,
        "bin_capacity": bin_capacity,
        "total_item_weight": total_weight,
        "theoretical_lower_bound": lower_bound,
        "bins": used_bins,
        "meta": {
            "exact": True,
            "proven_optimal": is_optimal,
            "wall_time_s": float(solver.WallTime() / 1000.0),
        },
    }


# ===========================================================================
# 3D — py3dbp industrial container / pallet loading
# ===========================================================================
# Standard industrial shipping containers & pallet bins (metres, kg).
DEFAULT_3D_BINS: list[dict[str, Any]] = [
    {"name": "40GP", "width": 12.032, "height": 2.352, "depth": 2.393,
     "max_weight": 28000.0, "copies": 3},
    {"name": "20GP", "width": 5.898, "height": 2.352, "depth": 2.393,
     "max_weight": 28000.0, "copies": 2},
    {"name": "EURO-PALLET", "width": 1.200, "height": 0.800, "depth": 1.500,
     "max_weight": 1000.0, "copies": 2},
]

# Typical cargo manifest (name, width_m, height_m, depth_m, weight_kg).
# ~72 m^3 total => requires ~2 x 40GP containers (67.7 m^3 each).
DEFAULT_3D_ITEMS: list[tuple[str, float, float, float, float]] = [
    ("cargo-001", 2.000, 1.200, 1.000, 900.0),
    ("cargo-002", 1.800, 1.200, 1.200, 1000.0),
    ("cargo-003", 1.500, 1.200, 1.000, 700.0),
    ("cargo-004", 2.000, 1.000, 0.800, 600.0),
    ("cargo-005", 1.500, 1.000, 0.800, 480.0),
    ("cargo-006", 1.200, 1.000, 1.000, 520.0),
    ("cargo-007", 1.500, 1.200, 1.200, 850.0),
    ("cargo-008", 1.200, 1.000, 0.800, 420.0),
    ("cargo-009", 1.000, 0.800, 0.800, 300.0),
    ("cargo-010", 1.800, 1.000, 1.000, 720.0),
    ("cargo-011", 1.500, 1.000, 1.000, 600.0),
    ("cargo-012", 1.200, 1.000, 1.000, 520.0),
    ("cargo-013", 2.000, 1.200, 1.500, 1400.0),
    ("cargo-014", 1.800, 1.000, 1.500, 1050.0),
    ("cargo-015", 1.500, 1.000, 1.200, 720.0),
    ("cargo-016", 1.200, 0.800, 1.200, 480.0),
    ("cargo-017", 1.500, 0.800, 1.000, 480.0),
    ("cargo-018", 1.000, 0.800, 1.000, 360.0),
    ("cargo-019", 1.800, 1.200, 1.200, 1000.0),
    ("cargo-020", 1.500, 1.200, 1.000, 700.0),
    ("cargo-021", 1.200, 1.000, 0.800, 420.0),
    ("cargo-022", 1.000, 0.800, 0.800, 300.0),
    ("cargo-023", 0.800, 0.600, 0.600, 150.0),
    ("cargo-024", 1.500, 0.800, 0.800, 450.0),
    ("cargo-025", 2.000, 1.200, 1.500, 1400.0),
    ("cargo-026", 1.800, 1.200, 1.200, 1000.0),
    ("cargo-027", 1.500, 1.200, 1.000, 700.0),
    ("cargo-028", 2.000, 1.000, 1.000, 800.0),
    ("cargo-029", 1.500, 1.000, 1.200, 720.0),
    ("cargo-030", 1.200, 1.000, 1.500, 640.0),
    ("cargo-031", 2.000, 1.200, 1.500, 1400.0),
    ("cargo-032", 1.800, 1.200, 1.500, 1150.0),
    ("cargo-033", 2.000, 1.000, 1.200, 880.0),
    ("cargo-034", 1.500, 1.200, 1.500, 980.0),
    ("cargo-035", 1.800, 1.000, 1.200, 800.0),
    ("cargo-036", 2.000, 1.200, 1.000, 820.0),
    ("cargo-037", 1.500, 1.000, 1.500, 860.0),
    ("cargo-038", 1.800, 1.000, 1.000, 720.0),
]


def _f(value: Any) -> float:
    """Coerce Decimal / int / float to a plain float for JSON serialization."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _boxes_overlap_3d(
    a: tuple[float, float, float, float, float, float],
    b: tuple[float, float, float, float, float, float],
    eps: float = 1e-6,
) -> bool:
    """AABB overlap test for two [x, y, z, dx, dy, dz] boxes.

    Uses an epsilon tolerance so that boxes that merely *touch* a shared face
    (a zero-volume intersection) are not flagged as overlapping — this avoids
    floating-point representation noise on exact-touch boundaries.
    """
    ax, ay, az, adx, ady, adz = a
    bx, by, bz, bdx, bdy, bdz = b
    return (
        ax < bx + bdx - eps and ax + adx > bx + eps
        and ay < by + bdy - eps and ay + ady > by + eps
        and az < bz + bdz - eps and az + adz > bz + eps
    )


def _self_check_3d(bins: list[dict[str, Any]]) -> dict[str, Any]:
    """Independent geometric re-verification of a 3D packing (Numbers Truth)."""
    in_bounds = True
    no_overlap = True
    weight_ok = True
    placed_count = 0
    for b in bins:
        bw, bh, bd = b["width"], b["height"], b["depth"]
        box_list: list[tuple[float, ...]] = []
        for it in b["items"]:
            x, y, z = it["x"], it["y"], it["z"]
            dx, dy, dz = it["dx"], it["dy"], it["dz"]
            placed_count += 1
            if x < 0 or y < 0 or z < 0 or dx <= 0 or dy <= 0 or dz <= 0:
                in_bounds = False
            if x + dx > bw + 1e-6 or y + dy > bh + 1e-6 or z + dz > bd + 1e-6:
                in_bounds = False
            box_list.append((x, y, z, dx, dy, dz))
            if b["total_weight"] > b["max_weight"] + 1e-6:
                weight_ok = False
        for i in range(len(box_list)):
            for j in range(i + 1, len(box_list)):
                if _boxes_overlap_3d(box_list[i], box_list[j]):
                    no_overlap = False
    return {
        "items_placed": placed_count,
        "in_bounds": in_bounds,
        "no_overlap": no_overlap,
        "weight_respected": weight_ok,
        "ok": in_bounds and no_overlap and weight_ok,
    }


def solve_bin_packing_3d(
    bins: list[dict[str, Any]] | None = None,
    items: list[tuple[str, float, float, float, float]] | None = None,
    bigger_first: bool = True,
    number_of_decimals: int = 3,
) -> dict[str, Any]:
    """Solve 3D bin packing with 6-DOF rotation via py3dbp.

    Parameters
    ----------
    bins: list of dicts ``{name, width, height, depth, max_weight, copies}``.
    items: list of ``(name, width, height, depth, weight)`` in metres / kg.
    """
    from py3dbp import Bin, Item, Packer  # lazy import keeps 1D path light

    bin_specs = bins if bins is not None else DEFAULT_3D_BINS
    manifest = items if items is not None else DEFAULT_3D_ITEMS

    packer = Packer()
    for spec in bin_specs:
        for _ in range(int(spec.get("copies", 1))):
            packer.add_bin(
                Bin(
                    spec["name"],
                    spec["width"],
                    spec["height"],
                    spec["depth"],
                    spec["max_weight"],
                )
            )
    for name, w, h, d, weight in manifest:
        packer.add_item(Item(name, w, h, d, weight))

    # distribute_items=True is essential: py3dbp otherwise re-places every item
    # into *each* subsequent bin (a known multi-bin duplication defect).
    packer.pack(
        bigger_first=bigger_first,
        distribute_items=True,
        number_of_decimals=number_of_decimals,
    )

    out_bins: list[dict[str, Any]] = []
    placed_names: set[str] = set()
    total_item_volume = 0.0
    total_item_weight = 0.0
    expected_names: set[str] = set()

    for name, w, h, d, weight in manifest:
        expected_names.add(name)
        total_item_volume += _f(w) * _f(h) * _f(d)
        total_item_weight += _f(weight)

    for bid, b in enumerate(packer.bins):
        if not b.items:
            continue
        bw, bh, bd = _f(b.width), _f(b.height), _f(b.depth)
        bin_volume = bw * bh * bd
        item_records: list[dict[str, Any]] = []
        bin_weight = 0.0
        bin_volume_used = 0.0
        for it in b.items:
            dim = it.get_dimension()  # [dx, dy, dz] under chosen rotation
            x, y, z = (_f(p) for p in it.position)
            dx, dy, dz = (_f(v) for v in dim)
            rot = int(it.rotation_type)
            placed_names.add(it.name)
            bin_weight += _f(it.weight)
            bin_volume_used += dx * dy * dz
            item_records.append({
                "name": it.name,
                "x": round(x, number_of_decimals),
                "y": round(y, number_of_decimals),
                "z": round(z, number_of_decimals),
                "dx": round(dx, number_of_decimals),
                "dy": round(dy, number_of_decimals),
                "dz": round(dz, number_of_decimals),
                "rotation_type": rot,
                "rotation_name": _ROTATION_NAMES.get(rot, f"RT_{rot}"),
                "weight": round(_f(it.weight), number_of_decimals),
                "volume": round(dx * dy * dz, number_of_decimals),
            })
        out_bins.append({
            "bin_id": bid,
            "bin_name": b.name,
            "width": round(bw, number_of_decimals),
            "height": round(bh, number_of_decimals),
            "depth": round(bd, number_of_decimals),
            "max_weight": round(_f(b.max_weight), number_of_decimals),
            "bin_volume": round(bin_volume, number_of_decimals),
            "items": item_records,
            "item_count": len(item_records),
            "total_weight": round(bin_weight, number_of_decimals),
            "total_volume": round(bin_volume_used, number_of_decimals),
            "volume_utilization": round(bin_volume_used / bin_volume, 4) if bin_volume else 0.0,
            "weight_utilization": round(bin_weight / _f(b.max_weight), 4) if b.max_weight else 0.0,
        })

    unfitted = sorted(expected_names - placed_names)
    used_bin_count = len(out_bins)
    total_bin_volume = sum(_f(b["width"]) * _f(b["height"]) * _f(b["depth"]) for b in bin_specs for _ in range(int(b.get("copies", 1))))
    overall_vol_util = (sum(b["total_volume"] for b in out_bins) / total_bin_volume) if total_bin_volume else 0.0
    overall_wt_util = (sum(b["total_weight"] for b in out_bins) /
                       sum(_f(s["max_weight"]) * int(s.get("copies", 1)) for s in bin_specs)) or 0.0

    self_check = _self_check_3d(out_bins)

    return {
        "problem_id": f"binpack_3d_{len(manifest)}items",
        "problem_class": "bin_packing",
        "status": "FEASIBLE",
        "objective": used_bin_count,
        "solver": "py3dbp",
        "source": _SOURCE,
        "mode": "3d",
        "bin_definitions": [
            {
                "name": s["name"],
                "width": round(_f(s["width"]), number_of_decimals),
                "height": round(_f(s["height"]), number_of_decimals),
                "depth": round(_f(s["depth"]), number_of_decimals),
                "max_weight": round(_f(s["max_weight"]), number_of_decimals),
                "copies": int(s.get("copies", 1)),
            }
            for s in bin_specs
        ],
        "num_items": len(manifest),
        "total_item_volume": round(total_item_volume, number_of_decimals),
        "total_item_weight": round(total_item_weight, number_of_decimals),
        "overall_volume_utilization": round(overall_vol_util, 4),
        "overall_weight_utilization": round(overall_wt_util, 4),
        "rotation_dof": 6,
        "bins": out_bins,
        "unfitted_items": unfitted,
        "meta": {
            "mode": "3d",
            "heuristic": True,
            "proven_optimal": False,
            "backend": "py3dbp",
            "distribute_items": True,
            "bigger_first": bigger_first,
            "self_check": self_check,
        },
    }


# ===========================================================================
# 2D — rectpack rectangular cutting-stock / sheet nesting
# ===========================================================================
# Standard boards / sheets (millimetres).
DEFAULT_2D_BINS: list[dict[str, Any]] = [
    {"name": "板材-2440x1220", "width": 2440.0, "height": 1220.0, "copies": 5},
    {"name": "板材-3000x1500", "width": 3000.0, "height": 1500.0, "copies": 3},
]

# Typical cutting parts (name, width_mm, height_mm, copies).
DEFAULT_2D_ITEMS: list[tuple[str, float, float, int]] = [
    ("part-001", 800.0, 600.0, 4),
    ("part-002", 600.0, 400.0, 5),
    ("part-003", 500.0, 500.0, 3),
    ("part-004", 900.0, 300.0, 6),
    ("part-005", 400.0, 300.0, 8),
    ("part-006", 700.0, 400.0, 4),
    ("part-007", 500.0, 200.0, 10),
    ("part-008", 1000.0, 500.0, 3),
    ("part-009", 300.0, 300.0, 12),
    ("part-010", 800.0, 500.0, 4),
    ("part-011", 600.0, 600.0, 2),
    ("part-012", 450.0, 350.0, 6),
]


def _rects_overlap_2d(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    eps: float = 1e-6,
) -> bool:
    """AABB overlap test for two [x, y, w, h] rectangles (epsilon-tolerant)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax < bx + bw - eps and ax + aw > bx + eps
            and ay < by + bh - eps and ay + ah > by + eps)


def _self_check_2d(bins: list[dict[str, Any]]) -> dict[str, Any]:
    """Independent geometric re-verification of a 2D nesting."""
    in_bounds = True
    no_overlap = True
    placed_count = 0
    for b in bins:
        bw, bh = b["width"], b["height"]
        rect_list: list[tuple[float, ...]] = []
        for p in b["parts"]:
            x, y, w, h = p["x"], p["y"], p["w"], p["h"]
            placed_count += 1
            if x < 0 or y < 0 or w <= 0 or h <= 0:
                in_bounds = False
            if x + w > bw + 1e-6 or y + h > bh + 1e-6:
                in_bounds = False
            rect_list.append((x, y, w, h))
        for i in range(len(rect_list)):
            for j in range(i + 1, len(rect_list)):
                if _rects_overlap_2d(rect_list[i], rect_list[j]):
                    no_overlap = False
    return {
        "parts_placed": placed_count,
        "in_bounds": in_bounds,
        "no_overlap": no_overlap,
        "ok": in_bounds and no_overlap,
    }


def solve_bin_packing_2d(
    bins: list[dict[str, Any]] | None = None,
    items: list[tuple[str, float, float, int]] | None = None,
    bin_algo: str = "BBF",
    pack_algo: str = "MaxRectsBssf",
    sort_algo: str = "SORT_AREA",
    rotation: bool = True,
    number_of_decimals: int = 2,
) -> dict[str, Any]:
    """Solve 2D rectangular cutting-stock / nesting via rectpack.

    Parameters
    ----------
    bins: list of dicts ``{name, width, height, copies}`` (mm).
    items: list of ``(name, width, height, copies)`` (mm).
    """
    from rectpack import (  # lazy import
        MaxRectsBssf,
        SORT_AREA,
        newPacker,
        PackingBin,
        PackingMode,
    )

    _PACK_ALGO = {
        "MaxRectsBssf": MaxRectsBssf,
    }
    _SORT_ALGO = {
        "SORT_AREA": SORT_AREA,
    }
    _BIN_ALGO = {
        "BNF": PackingBin.BNF,
        "BFF": PackingBin.BFF,
        "BBF": PackingBin.BBF,
        "Global": PackingBin.Global,
    }

    bin_specs = bins if bins is not None else DEFAULT_2D_BINS
    parts = items if items is not None else DEFAULT_2D_ITEMS

    packer = newPacker(
        mode=PackingMode.Offline,
        bin_algo=_BIN_ALGO.get(bin_algo, PackingBin.BBF),
        pack_algo=_PACK_ALGO.get(pack_algo, MaxRectsBssf),
        sort_algo=_SORT_ALGO.get(sort_algo, SORT_AREA),
        rotation=rotation,
    )

    expected_rids: list[str] = []
    total_part_area = 0.0
    for name, w, h, count in parts:
        for k in range(int(count)):
            rid = f"{name}#{k+1}" if int(count) > 1 else name
            expected_rids.append(rid)
            total_part_area += _f(w) * _f(h)
            packer.add_rect(_f(w), _f(h), rid=rid)
    for spec in bin_specs:
        packer.add_bin(_f(spec["width"]), _f(spec["height"]), count=int(spec.get("copies", 1)))

    packer.pack()

    # Validate the packing (raises on collision / out-of-surface).
    try:
        packer.validate_packing()
        validate_error = None
    except Exception as exc:  # pragma: no cover - defensive
        validate_error = str(exc)

    # Collect placed rects grouped by sheet.
    sheets_raw: dict[int, list[dict[str, Any]]] = {}
    for bin_idx, x, y, w, h, rid in packer.rect_list():
        sheets_raw.setdefault(bin_idx, []).append({
            "name": rid,
            "x": round(_f(x), number_of_decimals),
            "y": round(_f(y), number_of_decimals),
            "w": round(_f(w), number_of_decimals),
            "h": round(_f(h), number_of_decimals),
            "area": round(_f(w) * _f(h), number_of_decimals),
        })

    out_bins: list[dict[str, Any]] = []
    placed_rids: set[str] = set()
    bin_index_map: dict[int, dict[str, Any]] = {}
    ci = 0
    for spec in bin_specs:
        for _ in range(int(spec.get("copies", 1))):
            bin_index_map[ci] = spec
            ci += 1

    for bid in sorted(sheets_raw.keys()):
        spec = bin_index_map.get(bid, {"name": f"sheet-{bid}"})
        bw, bh = _f(spec["width"]), _f(spec["height"])
        sheet_area = bw * bh
        part_list = sheets_raw[bid]
        used_area = sum(p["area"] for p in part_list)
        for p in part_list:
            placed_rids.add(p["name"])
        out_bins.append({
            "bin_id": bid,
            "bin_name": spec["name"],
            "width": round(bw, number_of_decimals),
            "height": round(bh, number_of_decimals),
            "sheet_area": round(sheet_area, number_of_decimals),
            "parts": part_list,
            "part_count": len(part_list),
            "used_area": round(used_area, number_of_decimals),
            "area_utilization": round(used_area / sheet_area, 4) if sheet_area else 0.0,
        })

    unfitted = sorted(set(expected_rids) - placed_rids)
    used_sheet_count = len(out_bins)
    total_sheet_area = sum(
        _f(s["width"]) * _f(s["height"]) * int(s.get("copies", 1)) for s in bin_specs
    )
    overall_area_util = (sum(b["used_area"] for b in out_bins) / total_sheet_area) if total_sheet_area else 0.0

    self_check = _self_check_2d(out_bins)

    return {
        "problem_id": f"binpack_2d_{len(expected_rids)}parts",
        "problem_class": "bin_packing",
        "status": "FEASIBLE",
        "objective": used_sheet_count,
        "solver": "rectpack",
        "source": _SOURCE,
        "mode": "2d",
        "bin_definitions": [
            {
                "name": s["name"],
                "width": round(_f(s["width"]), number_of_decimals),
                "height": round(_f(s["height"]), number_of_decimals),
                "copies": int(s.get("copies", 1)),
            }
            for s in bin_specs
        ],
        "num_parts": len(expected_rids),
        "total_part_area": round(total_part_area, number_of_decimals),
        "overall_area_utilization": round(overall_area_util, 4),
        "bins": out_bins,
        "unfitted_parts": unfitted,
        "meta": {
            "mode": "2d",
            "heuristic": True,
            "proven_optimal": False,
            "backend": "rectpack",
            "bin_algo": bin_algo,
            "pack_algo": pack_algo,
            "rotation": rotation,
            "validate_packing_error": validate_error,
            "self_check": self_check,
        },
    }


# ===========================================================================
# Dispatcher
# ===========================================================================
def solve(mode: str = "3d", **kwargs: Any) -> dict[str, Any]:
    """Dispatch to the requested packing mode.

    ``mode`` in {"3d", "2d", "1d"}.  Extra kwargs are forwarded to the
    corresponding solver.
    """
    mode = (mode or "3d").lower()
    if mode == "3d":
        return solve_bin_packing_3d(
            bins=kwargs.get("bins"),
            items=kwargs.get("items"),
            bigger_first=kwargs.get("bigger_first", True),
            number_of_decimals=kwargs.get("number_of_decimals", 3),
        )
    if mode == "2d":
        return solve_bin_packing_2d(
            bins=kwargs.get("bins"),
            items=kwargs.get("items"),
            bin_algo=kwargs.get("bin_algo", "BBF"),
            pack_algo=kwargs.get("pack_algo", "MaxRectsBssf"),
            sort_algo=kwargs.get("sort_algo", "SORT_AREA"),
            rotation=kwargs.get("rotation", True),
            number_of_decimals=kwargs.get("number_of_decimals", 2),
        )
    if mode in ("1d", "1d-binpack"):
        return solve_bin_packing(
            weights=kwargs.get("weights"),
            bin_capacity=kwargs.get("bin_capacity", 100),
            time_limit_s=kwargs.get("time_limit_s", 30.0),
        )
    raise ValueError(f"unknown packing mode: {mode!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Full-scale Industrial Bin Packing & Nesting Solver "
                    "(3D py3dbp / 2D rectpack / 1D OR-Tools)"
    )
    parser.add_argument(
        "--mode",
        choices=["3d", "2d", "1d"],
        default="3d",
        help="Packing mode: 3d (default), 2d, or 1d (legacy MIP).",
    )
    parser.add_argument("--capacity", type=int, default=100,
                        help="1D bin capacity (default 100).")
    parser.add_argument("--time-limit-s", type=float, default=30.0,
                        help="1D MIP time limit in seconds (default 30).")
    parser.add_argument("--json-indent", type=int, default=2,
                        help="JSON indent level for stdout (default 2).")
    args = parser.parse_args(argv)

    wall0 = time.perf_counter()
    if args.mode == "1d":
        result = solve_bin_packing(
            bin_capacity=args.capacity,
            time_limit_s=args.time_limit_s,
        )
    else:
        result = solve(mode=args.mode)
    result.setdefault("meta", {})
    result["meta"]["wall_time_s"] = round(time.perf_counter() - wall0, 4)

    print(json.dumps(result, ensure_ascii=False, indent=args.json_indent))
    return 0 if result.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
