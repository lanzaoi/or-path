"""Exact LP / MILP reduction kernels backed by HiGHS (``scipy.optimize.milp``).

Provides zero-boilerplate building blocks so custom solvers can offload
combinatorial selection, weighted set covering / packing, regime exclusivity,
capacitated assignment, and arbitrary mixed-integer linear programs to an exact
branch-and-cut solver with honest ``proven_optimal`` and ``mip_gap`` reporting.
"""
from __future__ import annotations

import math
import time
from typing import Any, Sequence

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


def solve_general_milp(
    c: Sequence[float] | np.ndarray,
    *,
    A_ub: Any = None,
    b_ub: Sequence[float] | np.ndarray | None = None,
    A_eq: Any = None,
    b_eq: Sequence[float] | np.ndarray | None = None,
    bounds: Sequence[tuple[float | None, float | None]] | Bounds | None = None,
    integrality: Sequence[int] | np.ndarray | int | None = None,
    maximize: bool = False,
    time_limit_s: float = 30.0,
    mip_rel_gap: float = 1e-6,
) -> dict[str, Any]:
    """Solve a general LP/MILP ``min/max c^T x`` via HiGHS (``scipy.optimize.milp``).

    Returns a structured dict with ``ok``, ``status``, ``x``, ``objective``,
    ``mip_gap``, ``proven_optimal``, and ``wall_time_s``.
    """
    t0 = time.monotonic()
    c_arr = np.asarray(c, dtype=np.float64).ravel()
    n = c_arr.size
    if n == 0:
        return {
            "ok": True,
            "status": "OPTIMAL",
            "x": [],
            "objective": 0.0,
            "mip_gap": 0.0,
            "proven_optimal": True,
            "wall_time_s": round(time.monotonic() - t0, 4),
        }

    obj_c = -c_arr if maximize else c_arr

    if bounds is None:
        bnd_obj = Bounds(lb=np.zeros(n, dtype=np.float64), ub=np.full(n, np.inf))
    elif isinstance(bounds, Bounds):
        bnd_obj = bounds
    else:
        lb = np.array([-np.inf if lo is None else float(lo) for lo, _ in bounds], dtype=np.float64)
        ub = np.array([np.inf if hi is None else float(hi) for _, hi in bounds], dtype=np.float64)
        bnd_obj = Bounds(lb=lb, ub=ub)

    constraints: list[LinearConstraint] = []
    if A_ub is not None and b_ub is not None:
        a_u = np.asarray(A_ub, dtype=np.float64)
        b_u = np.asarray(b_ub, dtype=np.float64).ravel()
        if a_u.size > 0 and b_u.size > 0:
            constraints.append(LinearConstraint(a_u, -np.inf, b_u))
    if A_eq is not None and b_eq is not None:
        a_e = np.asarray(A_eq, dtype=np.float64)
        b_e = np.asarray(b_eq, dtype=np.float64).ravel()
        if a_e.size > 0 and b_e.size > 0:
            constraints.append(LinearConstraint(a_e, b_e, b_e))

    integ: Any
    if integrality is None:
        integ = np.zeros(n, dtype=int)
    elif isinstance(integrality, (int, np.integer)):
        integ = np.full(n, int(integrality), dtype=int)
    else:
        integ = np.asarray(integrality, dtype=int).ravel()

    options = {
        "time_limit": max(0.5, float(time_limit_s)),
        "mip_rel_gap": max(0.0, float(mip_rel_gap)),
    }
    res = milp(
        c=obj_c,
        integrality=integ,
        bounds=bnd_obj,
        constraints=constraints if constraints else None,
        options=options,
    )

    has_x = res.x is not None and len(res.x) == n
    proven = bool(res.status == 0 and res.success)
    feasible = bool(has_x and res.status in (0, 1))
    obj_val: float | None = None
    if feasible and res.fun is not None and math.isfinite(float(res.fun)):
        obj_val = float(-res.fun if maximize else res.fun)

    gap = 0.0 if proven else float("nan")
    raw_gap = getattr(res, "mip_gap", None)
    if raw_gap is not None and math.isfinite(float(raw_gap)):
        gap = float(raw_gap)

    return {
        "ok": feasible,
        "status": "OPTIMAL" if proven else ("FEASIBLE" if feasible else "INFEASIBLE"),
        "x": [float(v) for v in res.x] if has_x else [],
        "objective": obj_val,
        "mip_gap": None if math.isnan(gap) else round(gap, 8),
        "proven_optimal": proven,
        "message": str(getattr(res, "message", "")),
        "wall_time_s": round(time.monotonic() - t0, 4),
    }


def solve_budgeted_coverage_milp(
    item_coverages: dict[str, Sequence[Any]],
    *,
    universe_weights: dict[Any, float] | None = None,
    item_costs: dict[str, float] | None = None,
    max_items: int | None = None,
    budget: float | None = None,
    cover_all: bool = False,
    regime_groups: dict[Any, dict[Any, tuple[list[str], int]]] | None = None,
    conflicts: Sequence[tuple[str, str]] = (),
    time_limit_s: float = 30.0,
) -> dict[str, Any]:
    """Exact HiGHS MILP for discrete Weighted Max-Coverage or Min-Cost Set Cover.

    - ``cover_all=False`` (default): **Max Weighted Coverage** — select items
      subject to ``max_items`` / ``budget`` / ``regime_groups`` / ``conflicts``
      to maximize total weight of covered universe elements.
    - ``cover_all=True``: **Min-Cost Set Cover** — select minimum-cost items
      such that every universe element is covered by at least one selected item.
    """
    t0 = time.monotonic()
    items = list(item_coverages.keys())
    if not items:
        return {
            "ok": not cover_all,
            "selected": [],
            "selected_regimes": {},
            "covered_elements": [],
            "objective": 0.0,
            "proven_optimal": True,
            "wall_time_s": round(time.monotonic() - t0, 4),
        }

    elem_list: list[Any] = []
    elem_seen: dict[Any, int] = {}
    for cov in item_coverages.values():
        for e in cov:
            if e not in elem_seen:
                elem_seen[e] = len(elem_list)
                elem_list.append(e)
    for e in (universe_weights or {}):
        if e not in elem_seen:
            elem_seen[e] = len(elem_list)
            elem_list.append(e)

    n_items = len(items)
    n_elems = len(elem_list)
    item_idx = {it: i for i, it in enumerate(items)}

    # Flatten regime variables z_{c,r} after x_i (and optional y_e for max coverage)
    regime_entries: list[tuple[Any, Any, list[int], int]] = []
    carrier_to_reg_indices: dict[Any, list[int]] = {}
    if regime_groups:
        for cid, r_map in regime_groups.items():
            for rid, (members, cap) in (r_map or {}).items():
                m_indices = [item_idx[m] for m in members if m in item_idx]
                r_pos = len(regime_entries)
                regime_entries.append((cid, rid, m_indices, int(cap)))
                carrier_to_reg_indices.setdefault(cid, []).append(r_pos)

    n_reg = len(regime_entries)
    n_y = 0 if cover_all else n_elems
    n_vars = n_items + n_y + n_reg

    c_vec = np.zeros(n_vars, dtype=np.float64)
    if cover_all:
        for i, it in enumerate(items):
            c_vec[i] = float((item_costs or {}).get(it, 1.0))
        maximize = False
    else:
        for e_i, elem in enumerate(elem_list):
            c_vec[n_items + e_i] = float((universe_weights or {}).get(elem, 1.0))
        maximize = True

    rows: list[np.ndarray] = []
    rhs: list[float] = []

    # Coverage constraints
    elem_coverers: list[list[int]] = [[] for _ in range(n_elems)]
    for i, it in enumerate(items):
        for e in item_coverages[it]:
            elem_coverers[elem_seen[e]].append(i)

    if cover_all:
        # sum_{i covers e} x_i >= 1  =>  -sum x_i <= -1
        for e_i in range(n_elems):
            row = np.zeros(n_vars, dtype=np.float64)
            for i in elem_coverers[e_i]:
                row[i] = -1.0
            rows.append(row)
            rhs.append(-1.0)
    else:
        # y_e - sum_{i covers e} x_i <= 0
        for e_i in range(n_elems):
            row = np.zeros(n_vars, dtype=np.float64)
            row[n_items + e_i] = 1.0
            for i in elem_coverers[e_i]:
                row[i] = -1.0
            rows.append(row)
            rhs.append(0.0)

    if max_items is not None:
        row = np.zeros(n_vars, dtype=np.float64)
        row[:n_items] = 1.0
        rows.append(row)
        rhs.append(float(max_items))

    if budget is not None:
        row = np.zeros(n_vars, dtype=np.float64)
        for i, it in enumerate(items):
            row[i] = float((item_costs or {}).get(it, 1.0))
        rows.append(row)
        rhs.append(float(budget))

    reg_offset = n_items + n_y
    for r_pos, (_cid, _rid, m_indices, cap) in enumerate(regime_entries):
        z_col = reg_offset + r_pos
        for mi in m_indices:
            row = np.zeros(n_vars, dtype=np.float64)
            row[mi] = 1.0
            row[z_col] = -1.0
            rows.append(row)
            rhs.append(0.0)
        if m_indices:
            row = np.zeros(n_vars, dtype=np.float64)
            for mi in m_indices:
                row[mi] = 1.0
            row[z_col] = -float(cap)
            rows.append(row)
            rhs.append(0.0)

    for r_indices in carrier_to_reg_indices.values():
        row = np.zeros(n_vars, dtype=np.float64)
        for rp in r_indices:
            row[reg_offset + rp] = 1.0
        rows.append(row)
        rhs.append(1.0)

    for u, v in conflicts:
        if u in item_idx and v in item_idx and u != v:
            row = np.zeros(n_vars, dtype=np.float64)
            row[item_idx[u]] = 1.0
            row[item_idx[v]] = 1.0
            rows.append(row)
            rhs.append(1.0)

    A_ub = np.vstack(rows) if rows else None
    b_ub = np.asarray(rhs, dtype=np.float64) if rows else None
    bnds = Bounds(lb=np.zeros(n_vars, dtype=np.float64), ub=np.ones(n_vars, dtype=np.float64))
    integ = np.ones(n_vars, dtype=int)

    res = solve_general_milp(
        c_vec,
        A_ub=A_ub,
        b_ub=b_ub,
        bounds=bnds,
        integrality=integ,
        maximize=maximize,
        time_limit_s=time_limit_s,
    )
    if not res["ok"]:
        return {
            "ok": False,
            "selected": [],
            "selected_regimes": {},
            "covered_elements": [],
            "objective": None,
            "proven_optimal": False,
            "wall_time_s": round(time.monotonic() - t0, 4),
        }

    x_sol = res["x"]
    selected = [it for i, it in enumerate(items) if x_sol[i] > 0.5]
    selected_regimes: dict[Any, Any] = {}
    for r_pos, (cid, rid, _m, _cap) in enumerate(regime_entries):
        if x_sol[reg_offset + r_pos] > 0.5:
            selected_regimes[cid] = rid
    covered_set: set[Any] = set()
    for it in selected:
        covered_set.update(item_coverages[it])
    covered_elements = [e for e in elem_list if e in covered_set]

    return {
        "ok": True,
        "selected": selected,
        "selected_regimes": selected_regimes,
        "covered_elements": covered_elements,
        "objective": res["objective"],
        "proven_optimal": res["proven_optimal"],
        "mip_gap": res["mip_gap"],
        "wall_time_s": round(time.monotonic() - t0, 4),
    }


def solve_assignment_milp(
    cost_matrix: Sequence[Sequence[float]] | np.ndarray,
    *,
    maximize: bool = False,
    row_caps: Sequence[int] | None = None,
    col_demands: Sequence[int] | None = None,
    exact_row_assign: bool = True,
    conflicts: Sequence[tuple[tuple[int, int], tuple[int, int]]] = (),
    time_limit_s: float = 30.0,
) -> dict[str, Any]:
    """Exact HiGHS MILP for capacitated assignment / bipartite matching with conflicts."""
    t0 = time.monotonic()
    mat = np.asarray(cost_matrix, dtype=np.float64)
    if mat.ndim != 2 or mat.size == 0:
        return {"ok": False, "assignments": [], "objective": None, "proven_optimal": False}
    n_rows, n_cols = mat.shape
    n_vars = n_rows * n_cols
    c_vec = mat.ravel()

    ub_rows: list[np.ndarray] = []
    ub_rhs: list[float] = []
    eq_rows: list[np.ndarray] = []
    eq_rhs: list[float] = []

    for i in range(n_rows):
        row = np.zeros(n_vars, dtype=np.float64)
        row[i * n_cols : (i + 1) * n_cols] = 1.0
        cap = int(row_caps[i]) if row_caps is not None else 1
        if exact_row_assign:
            eq_rows.append(row)
            eq_rhs.append(float(cap))
        else:
            ub_rows.append(row)
            ub_rhs.append(float(cap))

    if col_demands is not None:
        for j in range(n_cols):
            row = np.zeros(n_vars, dtype=np.float64)
            row[j::n_cols] = 1.0
            eq_rows.append(row)
            eq_rhs.append(float(col_demands[j]))
    else:
        for j in range(n_cols):
            row = np.zeros(n_vars, dtype=np.float64)
            row[j::n_cols] = 1.0
            ub_rows.append(row)
            ub_rhs.append(1.0)

    for (r1, c1), (r2, c2) in conflicts:
        if 0 <= r1 < n_rows and 0 <= c1 < n_cols and 0 <= r2 < n_rows and 0 <= c2 < n_cols:
            row = np.zeros(n_vars, dtype=np.float64)
            row[r1 * n_cols + c1] += 1.0
            row[r2 * n_cols + c2] += 1.0
            ub_rows.append(row)
            ub_rhs.append(1.0)

    res = solve_general_milp(
        c_vec,
        A_ub=np.vstack(ub_rows) if ub_rows else None,
        b_ub=np.asarray(ub_rhs, dtype=np.float64) if ub_rows else None,
        A_eq=np.vstack(eq_rows) if eq_rows else None,
        b_eq=np.asarray(eq_rhs, dtype=np.float64) if eq_rows else None,
        bounds=Bounds(lb=np.zeros(n_vars, dtype=np.float64), ub=np.ones(n_vars, dtype=np.float64)),
        integrality=np.ones(n_vars, dtype=int),
        maximize=maximize,
        time_limit_s=time_limit_s,
    )
    if not res["ok"]:
        return {
            "ok": False,
            "assignments": [],
            "objective": None,
            "proven_optimal": False,
            "wall_time_s": round(time.monotonic() - t0, 4),
        }

    x_sol = np.asarray(res["x"], dtype=np.float64).reshape(n_rows, n_cols)
    assignments = [
        (int(i), int(j))
        for i in range(n_rows)
        for j in range(n_cols)
        if x_sol[i, j] > 0.5
    ]
    return {
        "ok": True,
        "assignments": assignments,
        "objective": res["objective"],
        "proven_optimal": res["proven_optimal"],
        "mip_gap": res["mip_gap"],
        "wall_time_s": round(time.monotonic() - t0, 4),
    }
