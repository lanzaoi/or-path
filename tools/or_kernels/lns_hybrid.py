"""Weighted interval-union selection & LNS warm-start repair kernels via OR-Tools CP-SAT."""
from __future__ import annotations

import time
from typing import Any, Callable, Sequence

from ortools.sat.python import cp_model


def _build_axis_breakpoints(
    intervals_map: dict[str, list[tuple[float, float]]],
) -> list[float]:
    bps_set: set[float] = set()
    for ivs in intervals_map.values():
        for s, e in ivs:
            if float(e) > float(s):
                bps_set.add(float(s))
                bps_set.add(float(e))
    return sorted(bps_set)


def select_max_union_subset(
    intervals_by_item: dict[str, list[tuple[float, float]]] | None = None,
    *,
    target_intervals_by_item: dict[str, dict[Any, list[tuple[float, float]]]] | None = None,
    target_weights: dict[Any, float] | None = None,
    max_items: int | None = None,
    group_caps: dict[Any, tuple[list[str], int]] | None = None,
    regime_groups: dict[Any, dict[Any, tuple[list[str], int]]] | None = None,
    conflicts: Sequence[tuple[str, str]] = (),
    item_times: dict[str, tuple[Any, float]] | None = None,
    min_separation: float = 0.0,
    warm_start: Sequence[str] = (),
    scale: int = 1000,
    time_limit_s: float = 30.0,
) -> dict[str, Any]:
    """Select an optimal subset of items to maximize (weighted) interval-union length.

    Supports both single-axis ``intervals_by_item`` and multi-axis/multi-target
    ``target_intervals_by_item[item_id][target_id] -> [(start, end), ...]``.
    Also supports:
      - ``max_items``: global item cardinality cap
      - ``group_caps``: ``{group_id: (member_items, cap)}``
      - ``regime_groups``: One-of-Group-Regimes exclusivity per carrier/entity,
        ``{carrier_id: {regime_id: (member_items, cap)}}`` enforcing
        ``sum_r z_{c,r} <= 1``, ``x_m <= z_{c,r}``, ``sum_m x_m <= cap * z_{c,r}``
      - ``conflicts``: explicit mutually exclusive pairs ``(item_u, item_v)``
      - ``item_times`` + ``min_separation``: ``{item_id: (carrier_id, time_val)}``
        enforcing ``|t_u - t_v| >= min_separation`` within the same carrier
      - ``warm_start``: optional list of item IDs hinted to CP-SAT
    """
    t0 = time.monotonic()

    # Normalize into per-target-axis maps: axis -> {item -> [(s, e), ...]}
    axis_maps: dict[Any, dict[str, list[tuple[float, float]]]] = {}
    items_set: dict[str, None] = {}
    if target_intervals_by_item:
        for it, t_map in target_intervals_by_item.items():
            items_set[it] = None
            for ax, ivs in (t_map or {}).items():
                axis_maps.setdefault(ax, {})[it] = [(float(s), float(e)) for s, e in ivs]
    if intervals_by_item:
        for it, ivs in intervals_by_item.items():
            items_set[it] = None
            axis_maps.setdefault("__default__", {})[it] = [
                (float(s), float(e)) for s, e in ivs
            ]

    items = list(items_set.keys())
    if not items or not axis_maps:
        return {
            "ok": True,
            "selected": [],
            "selected_regimes": {},
            "union_length": 0.0,
            "union_by_target": {},
            "proven_optimal": True,
            "wall_time_s": round(time.monotonic() - t0, 4),
        }

    model = cp_model.CpModel()
    x = {it: model.NewBoolVar(f"x_{i}") for i, it in enumerate(items)}

    if warm_start:
        warm_set = set(warm_start)
        for it, var in x.items():
            model.AddHint(var, 1 if it in warm_set else 0)

    if max_items is not None:
        model.Add(sum(x.values()) <= int(max_items))

    if group_caps:
        for _g, (members, cap) in group_caps.items():
            vars_g = [x[m] for m in members if m in x]
            if vars_g:
                model.Add(sum(vars_g) <= int(cap))

    regime_vars: dict[Any, dict[Any, cp_model.IntVar]] = {}
    if regime_groups:
        for c_idx, (carrier_id, reg_map) in enumerate(regime_groups.items()):
            z_map: dict[Any, cp_model.IntVar] = {}
            for r_idx, (reg_id, (members, cap)) in enumerate((reg_map or {}).items()):
                z = model.NewBoolVar(f"reg_{c_idx}_{r_idx}")
                z_map[reg_id] = z
                m_vars = [x[m] for m in members if m in x]
                for mv in m_vars:
                    model.Add(mv <= z)
                if m_vars:
                    model.Add(sum(m_vars) <= int(cap) * z)
            if z_map:
                model.Add(sum(z_map.values()) <= 1)
                regime_vars[carrier_id] = z_map

    for u, v in conflicts:
        if u in x and v in x and u != v:
            model.Add(x[u] + x[v] <= 1)

    if item_times and float(min_separation) > 0.0:
        sep = float(min_separation) - 1e-9
        by_carrier: dict[Any, list[tuple[float, str]]] = {}
        for it, (cid, tval) in item_times.items():
            if it in x:
                by_carrier.setdefault(cid, []).append((float(tval), it))
        for cid_list in by_carrier.values():
            cid_list.sort(key=lambda pair: pair[0])
            n_c = len(cid_list)
            for i in range(n_c):
                ti, iti = cid_list[i]
                for j in range(i + 1, n_c):
                    tj, itj = cid_list[j]
                    if tj - ti >= sep:
                        break
                    model.Add(x[iti] + x[itj] <= 1)

    obj_terms = []
    axis_atom_vars: dict[Any, list[tuple[float, cp_model.LinearExpr]]] = {}
    for ax_idx, (ax, ax_items) in enumerate(axis_maps.items()):
        bps = _build_axis_breakpoints(ax_items)
        if len(bps) < 2:
            continue
        ax_w = float((target_weights or {}).get(ax, 1.0))
        if ax_w <= 0.0:
            continue
        ax_terms: list[tuple[float, cp_model.LinearExpr]] = []
        for j in range(len(bps) - 1):
            a, b = bps[j], bps[j + 1]
            span = b - a
            if span <= 1e-12:
                continue
            mid = 0.5 * (a + b)
            w_int = int(round(span * ax_w * scale))
            if w_int <= 0:
                continue
            covering = [
                x[it]
                for it, ivs in ax_items.items()
                if it in x and any(s <= mid <= e for s, e in ivs)
            ]
            if not covering:
                continue
            if len(covering) == 1:
                obj_terms.append(w_int * covering[0])
                ax_terms.append((span, covering[0]))
            else:
                yj = model.NewBoolVar(f"u_{ax_idx}_{j}")
                model.Add(yj <= sum(covering))
                obj_terms.append(w_int * yj)
                ax_terms.append((span, yj))
        if ax_terms:
            axis_atom_vars[ax] = ax_terms

    if not obj_terms:
        return {
            "ok": True,
            "selected": [],
            "selected_regimes": {},
            "union_length": 0.0,
            "union_by_target": {str(ax): 0.0 for ax in axis_maps},
            "proven_optimal": True,
            "wall_time_s": round(time.monotonic() - t0, 4),
        }

    model.Maximize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.5, float(time_limit_s))
    status = solver.Solve(model)
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    if not ok:
        return {
            "ok": False,
            "selected": [],
            "selected_regimes": {},
            "union_length": 0.0,
            "union_by_target": {},
            "proven_optimal": False,
            "wall_time_s": round(time.monotonic() - t0, 4),
        }

    selected = [it for it in items if solver.Value(x[it]) == 1]
    selected_regimes: dict[Any, Any] = {}
    for cid, z_map in regime_vars.items():
        for reg_id, z_var in z_map.items():
            if solver.Value(z_var) == 1:
                selected_regimes[cid] = reg_id
                break

    union_by_target: dict[Any, float] = {}
    raw_total = 0.0
    for ax in axis_maps:
        val_ax = sum(
            span * float(solver.Value(expr))
            for span, expr in axis_atom_vars.get(ax, [])
        )
        union_by_target[ax] = round(float(val_ax), 6)
        raw_total += float(val_ax) * float((target_weights or {}).get(ax, 1.0))

    return {
        "ok": True,
        "selected": selected,
        "selected_regimes": selected_regimes,
        "union_length": round(float(raw_total), 6),
        "union_by_target": union_by_target,
        "proven_optimal": status == cp_model.OPTIMAL,
        "wall_time_s": round(time.monotonic() - t0, 4),
    }


def run_lns_loop(
    initial_state: Any,
    evaluate_fn: Callable[[Any], float],
    repair_step_fn: Callable[[Any, int, float], tuple[Any, float]],
    *,
    maximize: bool = False,
    n_iterations: int = 10,
    time_limit_s: float = 120.0,
) -> dict[str, Any]:
    """Generic monotonic LNS loop keeping the best incumbent across destroy/repair iterations."""
    t0 = time.monotonic()
    deadline = t0 + max(1.0, float(time_limit_s))
    incumbent = initial_state
    best_obj = float(evaluate_fn(initial_state))
    improvements = 0
    for it in range(max(1, int(n_iterations))):
        rem = deadline - time.monotonic()
        if rem <= 0.5:
            break
        per_step = rem / max(1, int(n_iterations) - it)
        cand, cand_obj = repair_step_fn(incumbent, it, per_step)
        better = cand_obj > best_obj + 1e-9 if maximize else cand_obj < best_obj - 1e-9
        if better:
            incumbent = cand
            best_obj = float(cand_obj)
            improvements += 1
    return {
        "ok": True,
        "incumbent": incumbent,
        "objective": best_obj,
        "improvements": improvements,
        "wall_time_s": round(time.monotonic() - t0, 4),
        "proven_optimal": False,
    }
