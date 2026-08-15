#!/usr/bin/env python3
"""Deterministic optimization primitives for the Tube B cutting problem.

All lengths are millimetres.  The routines in this module are deliberately
independent of the unpublished contest attachments so they can be regression
tested with synthetic instances.
"""
from __future__ import annotations

import math
import random
import time
from collections import Counter
from copy import deepcopy
from typing import Iterable

from ortools.linear_solver import pywraplp
from ortools.sat.python import cp_model

DEFAULT_STOCKS = (9000.0, 10000.0, 11000.0, 12000.0)
EPS = 1e-6


def switches(sequence: list[str]) -> int:
    return sum(a != b for a, b in zip(sequence, sequence[1:]))


def orientation_dp(
    sequence: list[str], savings: dict[str, dict[str, float]]
) -> tuple[float, list[str], list[dict]]:
    """Maximise co-cut benefit for a fixed sequence in O(n).

    An orientation is the end appearing on the left of the installed piece.
    Its right end is therefore the opposite end.  There are only two states per
    position, so exhaustive 2**n enumeration is unnecessary.
    """
    if not sequence:
        return 0.0, [], []
    ends = ("L", "R")
    # state[left_end] = (benefit, orientation_path, joints)
    state: dict[str, tuple[float, list[str], list[dict]]] = {
        e: (0.0, [e], []) for e in ends
    }
    for pos in range(1, len(sequence)):
        a, b = sequence[pos - 1], sequence[pos]
        nxt: dict[str, tuple[float, list[str], list[dict]]] = {}
        pair = f"{a}-{b}"
        if pair not in savings:
            raise KeyError(f"missing co-cut pair {pair}")
        for left_b in ends:
            candidates = []
            for left_a, (value, path, joints) in state.items():
                right_a = "R" if left_a == "L" else "L"
                mode = right_a + left_b
                benefit = float(savings[pair][mode])
                candidates.append(
                    (
                        value + benefit,
                        path + [left_b],
                        joints
                        + [{"pair": pair, "mode": mode, "benefit": round(benefit, 6)}],
                    )
                )
            # Stable path tie-break makes seeded experiments reproducible.
            nxt[left_b] = max(candidates, key=lambda x: (x[0], tuple(x[1])))
        state = nxt
    value, path, joints = max(state.values(), key=lambda x: (x[0], tuple(x[1])))
    return round(value, 6), path, joints


def evaluate_sequence(
    sequence: list[str],
    lengths: dict[str, float],
    savings: dict[str, dict[str, float]],
) -> dict:
    raw = sum(float(lengths[g]) for g in sequence)
    benefit, orientations, joints = orientation_dp(sequence, savings)
    effective = raw - benefit
    return {
        "sequence": list(sequence),
        "orientations": orientations,
        "joints": joints,
        "raw_length_mm": round(raw, 6),
        "co_cut_benefit_mm": round(benefit, 6),
        "effective_length_mm": round(effective, 6),
        "switches": switches(sequence),
    }


def smallest_stock(
    required_mm: float, stocks: Iterable[float] = DEFAULT_STOCKS
) -> float | None:
    for stock in sorted(float(x) for x in stocks):
        if required_mm <= stock + EPS:
            return stock
    return None


def _initial_patterns(
    demand: dict[str, int], lengths: dict[str, float], stocks: tuple[float, ...]
) -> list[tuple[float, tuple[int, ...]]]:
    gids = tuple(demand)
    patterns: set[tuple[float, tuple[int, ...]]] = set()
    for stock in stocks:
        for i, gid in enumerate(gids):
            if lengths[gid] <= stock + EPS:
                one = [0] * len(gids)
                one[i] = 1
                patterns.add((stock, tuple(one)))
            pure = [0] * len(gids)
            pure[i] = min(int(demand[gid]), int(stock // math.ceil(lengths[gid])))
            if pure[i] > 0:
                patterns.add((stock, tuple(pure)))
    return sorted(patterns)


def _pricing_pattern(
    duals: list[float],
    demand: dict[str, int],
    lengths: dict[str, float],
    stock: float,
    *,
    seed: int,
    time_limit_s: float = 0.25,
) -> tuple[int, ...]:
    """Bounded knapsack pricing using deterministic single-worker CP-SAT."""
    gids = tuple(demand)
    model = cp_model.CpModel()
    xs = [model.new_int_var(0, int(demand[g]), f"x_{i}") for i, g in enumerate(gids)]
    length_scale = 1000  # input/output convention keeps millimetres to 0.001 mm
    weights = [int(math.ceil(float(lengths[g]) * length_scale - EPS)) for g in gids]
    model.add(
        sum(w * x for w, x in zip(weights, xs))
        <= int(math.floor(stock * length_scale + EPS))
    )
    dual_scale = 1000
    model.maximize(
        sum(int(round(max(0.0, d) * dual_scale)) * x for d, x in zip(duals, xs))
    )
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.max_time_in_seconds = max(0.01, float(time_limit_s))
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return tuple(0 for _ in gids)
    return tuple(int(solver.value(x)) for x in xs)


def generate_pattern_library(
    demand: dict[str, int],
    lengths: dict[str, float],
    *,
    stocks: Iterable[float] = DEFAULT_STOCKS,
    seed: int = 1,
    max_columns: int = 120,
    time_limit_s: float = 10.0,
) -> list[tuple[float, tuple[int, ...]]]:
    """Generate a reusable mixed-stock pattern library by LP pricing."""
    if not demand or any(int(v) < 0 for v in demand.values()):
        raise ValueError("demand must contain non-negative counts")
    gids = tuple(demand)
    stock_tuple = tuple(sorted(set(float(s) for s in stocks)))
    if any(float(lengths[g]) <= 0 for g in gids):
        raise ValueError("item lengths must be positive")
    if any(float(lengths[g]) > max(stock_tuple) + EPS for g in gids if demand[g]):
        raise ValueError("an item is longer than every allowed stock")

    patterns = _initial_patterns(demand, lengths, stock_tuple)
    pattern_set = set(patterns)
    deadline = time.perf_counter() + max(0.1, float(time_limit_s))
    for iteration in range(max_columns):
        if time.perf_counter() >= deadline:
            break
        lp = pywraplp.Solver.CreateSolver("GLOP")
        if lp is None:
            raise RuntimeError("OR-Tools GLOP is unavailable")
        vars_ = [lp.NumVar(0.0, lp.infinity(), f"p_{j}") for j in range(len(patterns))]
        constraints = []
        for i, gid in enumerate(gids):
            ct = lp.Constraint(float(demand[gid]), float(demand[gid]), f"d_{i}")
            for j, (_stock, counts) in enumerate(patterns):
                ct.SetCoefficient(vars_[j], counts[i])
            constraints.append(ct)
        objective = lp.Objective()
        for var, (stock, _counts) in zip(vars_, patterns):
            objective.SetCoefficient(var, stock)
        objective.SetMinimization()
        if lp.Solve() != pywraplp.Solver.OPTIMAL:
            raise RuntimeError("mixed-stock LP master is infeasible")
        duals = [ct.dual_value() for ct in constraints]
        additions: list[tuple[float, tuple[int, ...]]] = []
        for offset, stock in enumerate(stock_tuple):
            remaining_time = deadline - time.perf_counter()
            if remaining_time <= 0:
                break
            counts = _pricing_pattern(
                duals,
                demand,
                lengths,
                stock,
                seed=seed + iteration * 17 + offset,
                time_limit_s=min(0.25, remaining_time),
            )
            if not any(counts):
                continue
            reduced = stock - sum(d * c for d, c in zip(duals, counts))
            candidate = (stock, counts)
            if reduced < -1e-5 and candidate not in pattern_set:
                additions.append(candidate)
        if not additions:
            break
        for candidate in additions:
            pattern_set.add(candidate)
            patterns.append(candidate)

    return sorted(patterns)


def select_patterns(
    demand: dict[str, int],
    lengths: dict[str, float],
    patterns: list[tuple[float, tuple[int, ...]]],
    *,
    seed: int = 1,
    time_limit_s: float = 10.0,
    id_prefix: str = "M",
) -> list[dict]:
    """Select an exact-demand integer combination from a reusable library."""
    gids = tuple(demand)
    usable = [
        (stock, counts)
        for stock, counts in patterns
        if len(counts) == len(gids)
        and all(int(count) <= int(demand[gid]) for gid, count in zip(gids, counts))
        and any(counts)
    ]
    # Guarantee feasibility for small residual demands even when the reusable
    # library was generated for a larger batch.
    stock_values = sorted({float(stock) for stock, _counts in patterns})
    for i, gid in enumerate(gids):
        if not demand[gid]:
            continue
        feasible_stocks = [s for s in stock_values if lengths[gid] <= s + EPS]
        if not feasible_stocks:
            raise ValueError(f"item {gid} is longer than every stock")
        counts = [0] * len(gids)
        counts[i] = 1
        candidate = (min(feasible_stocks), tuple(counts))
        if candidate not in usable:
            usable.append(candidate)
    usable.sort()

    master = cp_model.CpModel()
    upper = sum(int(v) for v in demand.values())
    use = [master.new_int_var(0, upper, f"use_{j}") for j in range(len(usable))]
    for i, gid in enumerate(gids):
        master.add(
            sum(counts[i] * use[j] for j, (_s, counts) in enumerate(usable))
            == int(demand[gid])
        )
    master.minimize(
        sum(int(round(stock * 1000)) * use[j] for j, (stock, _c) in enumerate(usable))
    )
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.max_time_in_seconds = time_limit_s
    status = solver.solve(master)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("mixed-stock integer master found no solution")

    bars: list[dict] = []
    for j, (stock, counts) in enumerate(usable):
        for _ in range(int(solver.value(use[j]))):
            seq: list[str] = []
            for gid, count in zip(gids, counts):
                seq.extend([gid] * count)
            used = sum(float(lengths[g]) for g in seq)
            if used > stock + EPS:
                raise AssertionError("pricing returned an infeasible pattern")
            bars.append(
                {
                    "stock_length_mm": stock,
                    "purchase_cost_mm": stock,
                    "sequence": seq,
                    "from_remnant": False,
                }
            )
    bars.sort(key=lambda b: (b["stock_length_mm"], tuple(b["sequence"])))
    for i, bar in enumerate(bars, 1):
        bar["id"] = f"{id_prefix}{i}"
    return bars


def compact_mixed_stock_patterns(
    demand: dict[str, int],
    lengths: dict[str, float],
    *,
    stocks: Iterable[float] = DEFAULT_STOCKS,
    seed: int = 1,
    time_limit_s: float = 10.0,
    id_prefix: str = "M",
) -> list[dict]:
    """Solve the raw-length cutting master without a restricted column pool.

    There are only ten workpiece types in the contest instance, so a compact
    count-per-bar CP-SAT model is both small and materially safer than relying
    on the integer master to combine an LP-generated subset of patterns.  A
    deterministic first-fit solution supplies an incumbent and a tight upper
    bound on the number of candidate bars.
    """
    if not demand or any(int(value) < 0 for value in demand.values()):
        raise ValueError("demand must contain non-negative counts")
    gids = tuple(demand)
    stock_tuple = tuple(sorted(set(float(stock) for stock in stocks)))
    if not stock_tuple:
        raise ValueError("at least one stock length is required")
    if any(float(lengths[gid]) <= 0 for gid in gids):
        raise ValueError("item lengths must be positive")
    if any(
        int(demand[gid]) and float(lengths[gid]) > stock_tuple[-1] + EPS
        for gid in gids
    ):
        raise ValueError("an item is longer than every allowed stock")
    total_items = sum(int(value) for value in demand.values())
    if total_items == 0:
        return []

    # First-fit decreasing into the largest stock gives a deterministic,
    # feasible incumbent.  Each bin is then purchased at its smallest fitting
    # standard length.
    incumbent: list[dict] = []
    for gid in sorted(gids, key=lambda value: (-float(lengths[value]), value)):
        for _ in range(int(demand[gid])):
            item_length = float(lengths[gid])
            for row in incumbent:
                if row["used_mm"] + item_length <= stock_tuple[-1] + EPS:
                    row["sequence"].append(gid)
                    row["used_mm"] += item_length
                    break
            else:
                incumbent.append(
                    {"used_mm": item_length, "sequence": [gid]}
                )
    for row in incumbent:
        chosen = smallest_stock(float(row["used_mm"]), stock_tuple)
        if chosen is None:
            raise AssertionError("first-fit constructed an infeasible bin")
        row["stock_length_mm"] = chosen
    incumbent.sort(
        key=lambda row: (-float(row["stock_length_mm"]), tuple(row["sequence"]))
    )
    incumbent_cost = sum(float(row["stock_length_mm"]) for row in incumbent)
    max_bars = max(1, int(math.floor(incumbent_cost / stock_tuple[0] + EPS)))

    model = cp_model.CpModel()
    active = [model.new_bool_var(f"active_{bar}") for bar in range(max_bars)]
    choose = [
        [model.new_bool_var(f"stock_{bar}_{kind}") for kind in range(len(stock_tuple))]
        for bar in range(max_bars)
    ]
    counts = [
        [
            model.new_int_var(0, int(demand[gid]), f"count_{bar}_{item}")
            for item, gid in enumerate(gids)
        ]
        for bar in range(max_bars)
    ]
    scale = 1000
    item_weights = [
        int(math.ceil(float(lengths[gid]) * scale - EPS)) for gid in gids
    ]
    stock_weights = [int(round(stock * scale)) for stock in stock_tuple]
    for bar in range(max_bars):
        model.add(sum(choose[bar]) == active[bar])
        model.add(sum(counts[bar]) >= active[bar])
        model.add(sum(counts[bar]) <= total_items * active[bar])
        model.add(
            sum(
                item_weights[item] * counts[bar][item]
                for item in range(len(gids))
            )
            <= sum(
                stock_weights[kind] * choose[bar][kind]
                for kind in range(len(stock_tuple))
            )
        )
        if bar:
            model.add(active[bar - 1] >= active[bar])
            model.add(
                sum(
                    stock_weights[kind] * choose[bar - 1][kind]
                    for kind in range(len(stock_tuple))
                )
                >= sum(
                    stock_weights[kind] * choose[bar][kind]
                    for kind in range(len(stock_tuple))
                )
            )
    for item, gid in enumerate(gids):
        model.add(
            sum(counts[bar][item] for bar in range(max_bars))
            == int(demand[gid])
        )
    model.minimize(
        sum(
            stock_weights[kind] * choose[bar][kind]
            for bar in range(max_bars)
            for kind in range(len(stock_tuple))
        )
    )

    # The incumbent hint makes even a deliberately tiny time budget return a
    # useful feasible solution instead of dropping back to singleton patterns.
    for bar in range(max_bars):
        if bar < len(incumbent):
            row = incumbent[bar]
            model.add_hint(active[bar], 1)
            selected = stock_tuple.index(float(row["stock_length_mm"]))
            tally = Counter(row["sequence"])
            for kind in range(len(stock_tuple)):
                model.add_hint(choose[bar][kind], int(kind == selected))
            for item, gid in enumerate(gids):
                model.add_hint(counts[bar][item], int(tally.get(gid, 0)))
        else:
            model.add_hint(active[bar], 0)
            for kind in range(len(stock_tuple)):
                model.add_hint(choose[bar][kind], 0)
            for item in range(len(gids)):
                model.add_hint(counts[bar][item], 0)

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.max_time_in_seconds = max(0.01, float(time_limit_s))
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected_rows = incumbent
    else:
        selected_rows = []
        for bar in range(max_bars):
            if not solver.value(active[bar]):
                continue
            stock = sum(
                stock_tuple[kind] * solver.value(choose[bar][kind])
                for kind in range(len(stock_tuple))
            )
            sequence: list[str] = []
            for item, gid in enumerate(gids):
                sequence.extend([gid] * int(solver.value(counts[bar][item])))
            selected_rows.append(
                {
                    "stock_length_mm": float(stock),
                    "sequence": sequence,
                }
            )

    bars = [
        {
            "stock_length_mm": float(row["stock_length_mm"]),
            "purchase_cost_mm": float(row["stock_length_mm"]),
            "sequence": list(row["sequence"]),
            "from_remnant": False,
        }
        for row in selected_rows
    ]
    bars.sort(key=lambda row: (row["stock_length_mm"], tuple(row["sequence"])))
    for index, row in enumerate(bars, 1):
        row["id"] = f"{id_prefix}{index}"
    if counts_from_bins(bars) != Counter(
        {gid: int(value) for gid, value in demand.items()}
    ):
        raise AssertionError("compact mixed-stock master changed demand")
    return bars


def minimize_type_splits_for_fixed_stock(
    demand: dict[str, int],
    lengths: dict[str, float],
    incumbent: list[dict],
    *,
    stocks: Iterable[float] = DEFAULT_STOCKS,
    seed: int = 1,
    time_limit_s: float = 10.0,
    id_prefix: str = "M",
) -> tuple[list[dict], dict]:
    """Minimise type switches without worsening an incumbent stock total.

    Q1 sequences can always place equal workpieces consecutively.  Therefore a
    bar containing ``k`` distinct types needs exactly ``k-1`` type switches.
    This compact second-stage model fixes the proven/selected primary stock
    total, minimises the number of type/bar incidences minus active bars, and
    reports the CP-SAT bound even when the secondary optimum is not proven.
    """
    if not incumbent:
        if any(int(value) for value in demand.values()):
            raise ValueError("a non-empty demand requires an incumbent")
        return [], {
            "status": "OPTIMAL",
            "fixed_stock_length_mm": 0.0,
            "switch_incumbent": 0,
            "switch_lower_bound": 0,
            "switch_gap": 0,
            "proven_optimal": True,
            "time_limit_s": float(time_limit_s),
        }
    gids = tuple(demand)
    stock_tuple = tuple(sorted(set(float(stock) for stock in stocks)))
    fixed_cost = round(
        sum(float(row["stock_length_mm"]) for row in incumbent), 6
    )
    min_stock = min(stock_tuple)
    max_bars = max(
        len(incumbent), int(math.floor(fixed_cost / min_stock + EPS))
    )
    total_items = sum(int(value) for value in demand.values())
    scale = 1000
    fixed_cost_scaled = int(round(fixed_cost * scale))
    item_weights = [
        int(math.ceil(float(lengths[gid]) * scale - EPS)) for gid in gids
    ]
    stock_weights = [int(round(stock * scale)) for stock in stock_tuple]

    model = cp_model.CpModel()
    active = [model.new_bool_var(f"active_{bar}") for bar in range(max_bars)]
    choose = [
        [model.new_bool_var(f"stock_{bar}_{kind}") for kind in range(len(stock_tuple))]
        for bar in range(max_bars)
    ]
    counts = [
        [
            model.new_int_var(0, int(demand[gid]), f"count_{bar}_{item}")
            for item, gid in enumerate(gids)
        ]
        for bar in range(max_bars)
    ]
    present = [
        [model.new_bool_var(f"present_{bar}_{item}") for item in range(len(gids))]
        for bar in range(max_bars)
    ]
    for bar in range(max_bars):
        model.add(sum(choose[bar]) == active[bar])
        model.add(sum(counts[bar]) >= active[bar])
        model.add(sum(counts[bar]) <= total_items * active[bar])
        model.add(
            sum(
                item_weights[item] * counts[bar][item]
                for item in range(len(gids))
            )
            <= sum(
                stock_weights[kind] * choose[bar][kind]
                for kind in range(len(stock_tuple))
            )
        )
        for item, gid in enumerate(gids):
            model.add(counts[bar][item] <= int(demand[gid]) * present[bar][item])
            model.add(counts[bar][item] >= present[bar][item])
            model.add(present[bar][item] <= active[bar])
        if bar:
            model.add(active[bar - 1] >= active[bar])
            model.add(
                sum(
                    stock_weights[kind] * choose[bar - 1][kind]
                    for kind in range(len(stock_tuple))
                )
                >= sum(
                    stock_weights[kind] * choose[bar][kind]
                    for kind in range(len(stock_tuple))
                )
            )
    for item, gid in enumerate(gids):
        model.add(
            sum(counts[bar][item] for bar in range(max_bars))
            == int(demand[gid])
        )
    model.add(
        sum(
            stock_weights[kind] * choose[bar][kind]
            for bar in range(max_bars)
            for kind in range(len(stock_tuple))
        )
        == fixed_cost_scaled
    )
    switch_expression = sum(
        present[bar][item]
        for bar in range(max_bars)
        for item in range(len(gids))
    ) - sum(active)
    model.minimize(switch_expression)

    # A grouped version of the primary incumbent is a valid warm start.
    hint_rows = sorted(
        incumbent,
        key=lambda row: (-float(row["stock_length_mm"]), tuple(row["sequence"])),
    )
    for bar in range(max_bars):
        if bar < len(hint_rows):
            row = hint_rows[bar]
            tally = Counter(row["sequence"])
            selected = stock_tuple.index(float(row["stock_length_mm"]))
            model.add_hint(active[bar], 1)
            for kind in range(len(stock_tuple)):
                model.add_hint(choose[bar][kind], int(kind == selected))
            for item, gid in enumerate(gids):
                value = int(tally.get(gid, 0))
                model.add_hint(counts[bar][item], value)
                model.add_hint(present[bar][item], int(value > 0))
        else:
            model.add_hint(active[bar], 0)
            for kind in range(len(stock_tuple)):
                model.add_hint(choose[bar][kind], 0)
            for item in range(len(gids)):
                model.add_hint(counts[bar][item], 0)
                model.add_hint(present[bar][item], 0)

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.max_time_in_seconds = max(0.01, float(time_limit_s))
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected_rows = [
            {
                "stock_length_mm": float(row["stock_length_mm"]),
                "sequence": sorted(list(row["sequence"])),
            }
            for row in incumbent
        ]
        status_name = solver.status_name(status)
        lower_bound = 0
    else:
        selected_rows = []
        for bar in range(max_bars):
            if not solver.value(active[bar]):
                continue
            stock = sum(
                stock_tuple[kind] * solver.value(choose[bar][kind])
                for kind in range(len(stock_tuple))
            )
            sequence: list[str] = []
            for item, gid in enumerate(gids):
                sequence.extend([gid] * int(solver.value(counts[bar][item])))
            selected_rows.append(
                {"stock_length_mm": float(stock), "sequence": sequence}
            )
        status_name = solver.status_name(status)
        lower_bound = max(0, int(math.ceil(solver.best_objective_bound - EPS)))

    bars = [
        {
            "stock_length_mm": float(row["stock_length_mm"]),
            "purchase_cost_mm": float(row["stock_length_mm"]),
            "sequence": list(row["sequence"]),
            "from_remnant": False,
        }
        for row in selected_rows
    ]
    bars.sort(key=lambda row: (row["stock_length_mm"], tuple(row["sequence"])))
    for index, row in enumerate(bars, 1):
        row["id"] = f"{id_prefix}{index}"
    if counts_from_bins(bars) != Counter(
        {gid: int(value) for gid, value in demand.items()}
    ):
        raise AssertionError("secondary mixed-stock master changed demand")
    got_cost = sum(float(row["stock_length_mm"]) for row in bars)
    if abs(got_cost - fixed_cost) > EPS:
        raise AssertionError("secondary mixed-stock master changed primary objective")
    switch_value = sum(switches(row["sequence"]) for row in bars)
    evidence = {
        "status": status_name,
        "fixed_stock_length_mm": fixed_cost,
        "switch_incumbent": int(switch_value),
        "switch_lower_bound": int(lower_bound),
        "switch_gap": int(max(0, switch_value - lower_bound)),
        "proven_optimal": status == cp_model.OPTIMAL,
        "time_limit_s": float(time_limit_s),
        "seed": int(seed),
    }
    return bars, evidence


def homogeneous_block_stock_patterns(
    demand: dict[str, int],
    lengths: dict[str, float],
    savings: dict[str, dict[str, float]],
    *,
    stocks: Iterable[float] = DEFAULT_STOCKS,
    seed: int = 1,
    time_limit_s: float = 10.0,
    id_prefix: str = "M",
) -> tuple[list[dict], dict]:
    """Pack exact homogeneous blocks using their exact internal co-cut length.

    For each type and count, ``evaluate_sequence([gid] * count)`` gives the
    exact optimal orientation DP value inside that block.  The master assigns
    one count per type/bar and deliberately ignores additional savings between
    different blocks, so every selected pattern remains feasible when later
    materialised with the full sequence evaluator.
    """
    if not demand or any(int(value) < 0 for value in demand.values()):
        raise ValueError("demand must contain non-negative counts")
    gids = tuple(demand)
    stock_tuple = tuple(sorted(set(float(stock) for stock in stocks)))
    total_items = sum(int(value) for value in demand.values())
    if not total_items:
        return [], {
            "status": "OPTIMAL",
            "stock_incumbent_mm": 0.0,
            "stock_lower_bound_mm": 0.0,
            "stock_proven_optimal": True,
            "time_limit_s": float(time_limit_s),
            "seed": int(seed),
        }
    raw_incumbent = compact_mixed_stock_patterns(
        demand,
        lengths,
        stocks=stock_tuple,
        seed=seed,
        time_limit_s=max(0.01, min(float(time_limit_s), 2.0)),
        id_prefix=id_prefix,
    )
    max_bars = max(
        1,
        int(
            math.floor(
                sum(float(row["stock_length_mm"]) for row in raw_incumbent)
                / min(stock_tuple)
                + EPS
            )
        ),
    )
    scale = 1000
    stock_weights = [int(round(stock * scale)) for stock in stock_tuple]
    block_weights: dict[str, list[int]] = {}
    for gid in gids:
        values = [0]
        for count in range(1, int(demand[gid]) + 1):
            effective = evaluate_sequence(
                [gid] * count, lengths, savings
            )["effective_length_mm"]
            values.append(int(math.ceil(float(effective) * scale - EPS)))
        block_weights[gid] = values

    model = cp_model.CpModel()
    active = [model.new_bool_var(f"active_{bar}") for bar in range(max_bars)]
    choose = [
        [model.new_bool_var(f"stock_{bar}_{kind}") for kind in range(len(stock_tuple))]
        for bar in range(max_bars)
    ]
    select = [
        [
            [
                model.new_bool_var(f"select_{bar}_{item}_{count}")
                for count in range(int(demand[gid]) + 1)
            ]
            for item, gid in enumerate(gids)
        ]
        for bar in range(max_bars)
    ]
    for bar in range(max_bars):
        model.add(sum(choose[bar]) == active[bar])
        for item, gid in enumerate(gids):
            model.add(sum(select[bar][item]) == 1)
        selected_blocks = sum(
            select[bar][item][count]
            for item, gid in enumerate(gids)
            for count in range(1, int(demand[gid]) + 1)
        )
        model.add(selected_blocks >= active[bar])
        model.add(selected_blocks <= len(gids) * active[bar])
        model.add(
            sum(
                block_weights[gid][count] * select[bar][item][count]
                for item, gid in enumerate(gids)
                for count in range(int(demand[gid]) + 1)
            )
            <= sum(
                stock_weights[kind] * choose[bar][kind]
                for kind in range(len(stock_tuple))
            )
        )
        if bar:
            model.add(active[bar - 1] >= active[bar])
            model.add(
                sum(
                    stock_weights[kind] * choose[bar - 1][kind]
                    for kind in range(len(stock_tuple))
                )
                >= sum(
                    stock_weights[kind] * choose[bar][kind]
                    for kind in range(len(stock_tuple))
                )
            )
    for item, gid in enumerate(gids):
        model.add(
            sum(
                count * select[bar][item][count]
                for bar in range(max_bars)
                for count in range(int(demand[gid]) + 1)
            )
            == int(demand[gid])
        )
    # One thousandth of a millimetre of stock dominates every possible block
    # incidence reduction.
    dominance = total_items + 1
    model.minimize(
        dominance
        * sum(
            stock_weights[kind] * choose[bar][kind]
            for bar in range(max_bars)
            for kind in range(len(stock_tuple))
        )
        + sum(
            select[bar][item][count]
            for bar in range(max_bars)
            for item, gid in enumerate(gids)
            for count in range(1, int(demand[gid]) + 1)
        )
    )

    # The raw-length incumbent is feasible for this conservative block model:
    # replacing raw lengths by exact within-type block lengths can only reduce
    # occupancy.  Supplying the complete hint prevents short, reproducible
    # experiment budgets from returning UNKNOWN before CP-SAT has found any
    # candidate at all.
    for bar in range(max_bars):
        if bar < len(raw_incumbent):
            row = raw_incumbent[bar]
            model.add_hint(active[bar], 1)
            selected_stock = stock_tuple.index(float(row["stock_length_mm"]))
            tally = Counter(row["sequence"])
            for kind in range(len(stock_tuple)):
                model.add_hint(choose[bar][kind], int(kind == selected_stock))
            for item, gid in enumerate(gids):
                selected_count = int(tally.get(gid, 0))
                for count in range(int(demand[gid]) + 1):
                    model.add_hint(
                        select[bar][item][count], int(count == selected_count)
                    )
        else:
            model.add_hint(active[bar], 0)
            for kind in range(len(stock_tuple)):
                model.add_hint(choose[bar][kind], 0)
            for item, gid in enumerate(gids):
                for count in range(int(demand[gid]) + 1):
                    model.add_hint(select[bar][item][count], int(count == 0))

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.max_time_in_seconds = max(0.01, float(time_limit_s))
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            f"homogeneous-block master returned {solver.status_name(status)}"
        )
    bars: list[dict] = []
    for bar in range(max_bars):
        if not solver.value(active[bar]):
            continue
        stock = sum(
            stock_tuple[kind] * solver.value(choose[bar][kind])
            for kind in range(len(stock_tuple))
        )
        sequence: list[str] = []
        for item, gid in enumerate(gids):
            count = next(
                count
                for count in range(int(demand[gid]) + 1)
                if solver.value(select[bar][item][count])
            )
            sequence.extend([gid] * count)
        bars.append(
            {
                "stock_length_mm": float(stock),
                "purchase_cost_mm": float(stock),
                "sequence": sequence,
                "from_remnant": False,
            }
        )
    materialised = materialize_bins(
        bars, lengths, savings, resize_new=True, stocks=stock_tuple
    )
    if materialised is None:
        raise AssertionError("homogeneous-block master produced an infeasible plan")
    materialised.sort(
        key=lambda row: (row["stock_length_mm"], tuple(row["sequence"]))
    )
    for index, row in enumerate(materialised, 1):
        row["id"] = f"{id_prefix}{index}"
    if counts_from_bins(materialised) != Counter(
        {gid: int(value) for gid, value in demand.items()}
    ):
        raise AssertionError("homogeneous-block master changed demand")
    stock_incumbent = sum(
        float(row["stock_length_mm"]) for row in materialised
    )
    # Strip the secondary incidence term from the composite lower bound.  A
    # downward rounding is required because the bound also contains the small
    # non-negative type-incidence tie-break term.
    composite_bound = max(0.0, float(solver.best_objective_bound))
    relaxed_stock_lower = math.floor(composite_bound / dominance + EPS) / scale
    representable_totals: set[float] = set()
    exact_totals = {0.0}
    for _bar in range(max_bars):
        exact_totals = {
            round(total + stock, 6)
            for total in exact_totals
            for stock in stock_tuple
        }
        representable_totals.update(exact_totals)
    stock_lower = min(
        total
        for total in representable_totals
        if total + EPS >= relaxed_stock_lower
    )
    evidence = {
        "status": solver.status_name(status),
        "stock_incumbent_mm": round(stock_incumbent, 6),
        "continuous_stock_lower_bound_mm": round(relaxed_stock_lower, 6),
        "stock_lower_bound_mm": float(stock_lower),
        "stock_proven_optimal": float(stock_lower) >= stock_incumbent - EPS,
        "type_incidence": sum(
            len(set(row["sequence"])) for row in materialised
        ),
        "time_limit_s": float(time_limit_s),
        "seed": int(seed),
        "conservative": True,
        "ignored_extra_savings": "inter-block co-cut benefit",
    }
    return materialised, evidence


def joint_relaxation_stock_lower_bound(
    demand: dict[str, int],
    lengths: dict[str, float],
    savings: dict[str, dict[str, float]],
    *,
    stocks: Iterable[float] = DEFAULT_STOCKS,
) -> dict:
    """Return a valid stock lower bound for joint cutting.

    Two relaxations are computed.  The legacy bound lets every non-terminal
    piece independently take its best outgoing saving.  The stronger bound
    assigns each type to one of two physical orientations and uses an aggregate
    maximum-weight path-cover relaxation: incoming and outgoing joints must be
    consistent with that orientation, while connectivity, bar capacities and
    batch timing are still ignored.  It uses ``N-1`` joints (one relaxed path),
    which is at least as permissive as any feasible multi-bar plan because all
    savings are non-negative.  Its maximum saving is therefore a valid global
    upper bound.  Rounding the resulting effective-length lower bound up to the
    next representable stock total produces a valid purchase lower bound.
    """
    gids = tuple(demand)
    stock_tuple = tuple(sorted(set(float(stock) for stock in stocks)))
    piece_caps: list[float] = []
    raw = 0.0
    for gid in gids:
        count = int(demand[gid])
        raw += float(lengths[gid]) * count
        cap = max(
            float(savings[f"{gid}-{other}"][mode])
            for other in gids
            for mode in ("LL", "LR", "RL", "RR")
        )
        piece_caps.extend([cap] * count)
    if not piece_caps:
        return {
            "lower_bound_mm": 0.0,
            "relaxed_bar_count": 0,
            "raw_length_mm": 0.0,
            "co_cut_upper_bound_mm": 0.0,
            "effective_length_lower_bound_mm": 0.0,
            "method": "independent-joint terminal relaxation",
        }
    piece_caps.sort()
    total_cap = sum(piece_caps)
    possible_totals = {0.0}
    best: tuple[float, int, float, float] | None = None
    terminal_cap_sum = 0.0
    for bar_count in range(1, len(piece_caps) + 1):
        terminal_cap_sum += piece_caps[bar_count - 1]
        possible_totals = {
            round(total + stock, 6)
            for total in possible_totals
            for stock in stock_tuple
        }
        saving_upper = max(0.0, total_cap - terminal_cap_sum)
        effective_lower = max(0.0, raw - saving_upper)
        feasible_totals = [
            total for total in possible_totals if total + EPS >= effective_lower
        ]
        if feasible_totals:
            candidate = (
                min(feasible_totals),
                bar_count,
                effective_lower,
                saving_upper,
            )
            if best is None or candidate[0] < best[0]:
                best = candidate
        # Once every possible total already exceeds the current best, adding
        # another positive stock cannot improve the purchase lower bound.
        if best is not None and min(possible_totals) >= best[0] - EPS:
            break
    if best is None:
        raise AssertionError("joint relaxation failed to find a stock total")
    legacy_lower, bar_count, legacy_effective_lower, legacy_saving_upper = best

    # Stronger orientation-consistent aggregate path-cover relaxation.
    states = tuple((gid, orientation) for gid in gids for orientation in ("L", "R"))
    scale = 10_000  # source savings are recorded to 0.0001 mm
    model = cp_model.CpModel()
    oriented_count = {
        state: model.new_int_var(0, int(demand[state[0]]), f"n_{state[0]}_{state[1]}")
        for state in states
    }
    arcs = {
        (left, right): model.new_int_var(
            0, len(piece_caps),
            f"x_{left[0]}_{left[1]}_{right[0]}_{right[1]}",
        )
        for left in states
        for right in states
    }
    for gid in gids:
        model.add(
            oriented_count[(gid, "L")] + oriented_count[(gid, "R")]
            == int(demand[gid])
        )
    for state in states:
        model.add(
            sum(arcs[(state, other)] for other in states) <= oriented_count[state]
        )
        model.add(
            sum(arcs[(other, state)] for other in states) <= oriented_count[state]
        )
    total_pieces = len(piece_caps)
    relaxed_joint_count = max(0, total_pieces - 1)
    model.add(sum(arcs.values()) == relaxed_joint_count)

    def arc_weight(left: tuple[str, str], right: tuple[str, str]) -> int:
        right_end = "R" if left[1] == "L" else "L"
        value = float(savings[f"{left[0]}-{right[0]}"][right_end + right[1]])
        # Upward rounding preserves the upper-bound direction.
        return int(math.ceil(value * scale - EPS))

    model.maximize(
        sum(
            arc_weight(left, right) * arcs[(left, right)]
            for left in states
            for right in states
        )
    )
    path_solver = cp_model.CpSolver()
    path_solver.parameters.num_search_workers = 1
    path_solver.parameters.random_seed = 1
    path_solver.parameters.max_time_in_seconds = 5.0
    path_status = path_solver.solve(model)
    if path_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        saving_bound_scaled = max(
            float(path_solver.objective_value),
            float(path_solver.best_objective_bound),
        )
        orientation_saving_upper = math.ceil(saving_bound_scaled - EPS) / scale
        orientation_effective_lower = max(0.0, raw - orientation_saving_upper)
        reachable_totals = {0.0}
        representable_totals: set[float] = set()
        # No feasible solution needs more than one stock per workpiece.
        for _bar in range(total_pieces):
            reachable_totals = {
                round(total + stock, 6)
                for total in reachable_totals
                for stock in stock_tuple
            }
            representable_totals.update(reachable_totals)
            if min(reachable_totals) >= orientation_effective_lower - EPS:
                break
        orientation_lower = min(
            total
            for total in representable_totals
            if total + EPS >= orientation_effective_lower
        )
    else:
        # Retain the legacy valid relaxation if the stronger proof model cannot
        # return a bound.  This fallback is explicit in the evidence.
        orientation_saving_upper = legacy_saving_upper
        orientation_effective_lower = legacy_effective_lower
        orientation_lower = legacy_lower

    use_orientation = orientation_lower >= legacy_lower - EPS
    lower = orientation_lower if use_orientation else legacy_lower
    effective_lower = (
        orientation_effective_lower if use_orientation else legacy_effective_lower
    )
    saving_upper = orientation_saving_upper if use_orientation else legacy_saving_upper
    return {
        "lower_bound_mm": round(lower, 6),
        "relaxed_bar_count": int(bar_count),
        "raw_length_mm": round(raw, 6),
        "co_cut_upper_bound_mm": round(saving_upper, 6),
        "effective_length_lower_bound_mm": round(effective_lower, 6),
        "method": (
            "orientation-consistent aggregate path-cover relaxation; "
            "connectivity/capacity/batch timing relaxed"
            if use_orientation
            else "independent best outgoing joint minus one terminal per bar"
        ),
        "orientation_consistent": {
            "status": path_solver.status_name(path_status),
            "relaxed_joint_count": relaxed_joint_count,
            "co_cut_upper_bound_mm": round(orientation_saving_upper, 6),
            "effective_length_lower_bound_mm": round(orientation_effective_lower, 6),
            "stock_lower_bound_mm": round(orientation_lower, 6),
            "scale_per_mm": scale,
            "relaxations": [
                "all pieces may form disconnected cycles",
                "bar capacities and stock composition ignored before final rounding",
                "batch timing and remnant availability ignored",
            ],
        },
        "legacy_independent_joint": {
            "stock_lower_bound_mm": round(legacy_lower, 6),
            "co_cut_upper_bound_mm": round(legacy_saving_upper, 6),
            "effective_length_lower_bound_mm": round(legacy_effective_lower, 6),
            "relaxed_bar_count": int(bar_count),
        },
    }


def mixed_stock_patterns(
    demand: dict[str, int],
    lengths: dict[str, float],
    *,
    stocks: Iterable[float] = DEFAULT_STOCKS,
    seed: int = 1,
    max_columns: int = 120,
    time_limit_s: float = 10.0,
) -> list[dict]:
    """Solve genuine mixed-stock cutting with a compact integer master."""
    return compact_mixed_stock_patterns(
        demand,
        lengths,
        stocks=stocks,
        seed=seed,
        time_limit_s=time_limit_s,
    )


def materialize_bins(
    bins: list[dict],
    lengths: dict[str, float],
    savings: dict[str, dict[str, float]],
    *,
    resize_new: bool,
    stocks: Iterable[float] = DEFAULT_STOCKS,
) -> list[dict] | None:
    """Evaluate every bar and reject, never massage, infeasible occupancy."""
    out: list[dict] = []
    for source in bins:
        if not source.get("sequence"):
            continue
        evaluated = evaluate_sequence(list(source["sequence"]), lengths, savings)
        row = dict(source)
        row.update(evaluated)
        if resize_new and not row.get("from_remnant"):
            chosen = smallest_stock(evaluated["effective_length_mm"], stocks)
            if chosen is None:
                return None
            row["stock_length_mm"] = chosen
            row["purchase_cost_mm"] = chosen
        stock = float(row["stock_length_mm"])
        if evaluated["effective_length_mm"] > stock + EPS:
            return None
        row["leftover_mm"] = round(stock - evaluated["effective_length_mm"], 6)
        row["utilization"] = round(evaluated["effective_length_mm"] / stock, 8)
        row.setdefault("purchase_cost_mm", 0.0 if row.get("from_remnant") else stock)
        out.append(row)
    for i, row in enumerate(out, 1):
        row.setdefault("id", f"M{i}")
    return out


def solution_key(bins: list[dict]) -> tuple[float, float, int, int]:
    return (
        round(sum(float(b.get("purchase_cost_mm", b["stock_length_mm"])) for b in bins), 6),
        -round(sum(float(b["co_cut_benefit_mm"]) for b in bins), 6),
        sum(int(b["switches"]) for b in bins),
        len(bins),
    )


def _scalar_key(key: tuple[float, float, int, int]) -> float:
    # One extra 1 m stock dominates any possible secondary improvement.
    return key[0] * 1_000_000.0 + key[1] * 100.0 + key[2] + key[3] * 0.01


def _mutate_sequence(seq: list[str], rng: random.Random) -> list[str]:
    if len(seq) < 2:
        return list(seq)
    out = list(seq)
    op = rng.randrange(3)
    i, j = sorted(rng.sample(range(len(out)), 2))
    if op == 0:
        out[i], out[j] = out[j], out[i]
    elif op == 1:
        item = out.pop(j)
        out.insert(i, item)
    else:
        out[i : j + 1] = reversed(out[i : j + 1])
    return out


def optimize_fixed_assignments(
    bins: list[dict],
    lengths: dict[str, float],
    savings: dict[str, dict[str, float]],
    *,
    seed: int = 1,
    iterations: int = 1500,
) -> list[dict]:
    """Seeded ALNS-style sequence search while preserving each bar's multiset."""
    rng = random.Random(seed)
    result: list[dict] = []
    for bidx, source in enumerate(bins):
        current_seq = list(source["sequence"])
        current = materialize_bins([source], lengths, savings, resize_new=False)
        if current is None:
            raise ValueError(f"input bar {source.get('id', bidx)} is infeasible")
        best = current
        best_key = (-best[0]["co_cut_benefit_mm"], best[0]["switches"])
        current_key = best_key
        temp = max(1.0, abs(best_key[0]) * 0.02)
        for _ in range(max(0, iterations)):
            candidate_source = dict(source)
            candidate_source["sequence"] = _mutate_sequence(current_seq, rng)
            candidate = materialize_bins([candidate_source], lengths, savings, resize_new=False)
            if candidate is None:
                continue
            key = (-candidate[0]["co_cut_benefit_mm"], candidate[0]["switches"])
            delta = (key[0] - current_key[0]) + 0.001 * (key[1] - current_key[1])
            if key < current_key or rng.random() < math.exp(-max(0.0, delta) / temp):
                current_seq = list(candidate[0]["sequence"])
                current_key = key
            if key < best_key:
                best, best_key = candidate, key
            temp *= 0.997
            temp = max(temp, 1e-4)
        result.append(best[0])
    return result


def _random_joint_move(bins: list[dict], rng: random.Random) -> list[dict]:
    candidate = deepcopy(bins)
    nonempty = [i for i, b in enumerate(candidate) if b.get("sequence")]
    if not nonempty:
        return candidate
    if rng.random() < 0.45 or len(nonempty) == 1:
        i = rng.choice(nonempty)
        candidate[i]["sequence"] = _mutate_sequence(candidate[i]["sequence"], rng)
        return candidate
    src = rng.choice(nonempty)
    dst_options = [i for i in range(len(candidate)) if i != src]
    dst = rng.choice(dst_options)
    if rng.random() < 0.7 or not candidate[dst]["sequence"]:
        pos = rng.randrange(len(candidate[src]["sequence"]))
        item = candidate[src]["sequence"].pop(pos)
        insert = rng.randrange(len(candidate[dst]["sequence"]) + 1)
        candidate[dst]["sequence"].insert(insert, item)
    else:
        a = rng.randrange(len(candidate[src]["sequence"]))
        b = rng.randrange(len(candidate[dst]["sequence"]))
        candidate[src]["sequence"][a], candidate[dst]["sequence"][b] = (
            candidate[dst]["sequence"][b],
            candidate[src]["sequence"][a],
        )
    return candidate


def optimize_joint_bins(
    bins: list[dict],
    lengths: dict[str, float],
    savings: dict[str, dict[str, float]],
    *,
    seed: int = 1,
    iterations: int = 5000,
    resize_new: bool = True,
    stocks: Iterable[float] = DEFAULT_STOCKS,
) -> list[dict]:
    """Joint assignment/sequence/orientation search with strict feasibility."""
    rng = random.Random(seed)
    initial = materialize_bins(
        bins, lengths, savings, resize_new=resize_new, stocks=stocks
    )
    if initial is None:
        raise ValueError("initial joint solution is infeasible")
    current = initial
    current_key = solution_key(current)
    best, best_key = deepcopy(current), current_key
    temp = 500.0
    for iteration in range(max(0, iterations)):
        raw = _random_joint_move(current, rng)
        candidate = materialize_bins(
            raw, lengths, savings, resize_new=resize_new, stocks=stocks
        )
        if candidate is None:
            continue
        key = solution_key(candidate)
        delta = _scalar_key(key) - _scalar_key(current_key)
        if key < current_key or rng.random() < math.exp(-max(0.0, delta) / temp):
            current, current_key = candidate, key
        if key < best_key:
            best, best_key = deepcopy(candidate), key
        temp *= 0.9985
        temp = max(temp, 1e-3)
        # Periodic restart preserves exploration without changing reproducibility.
        if iteration and iteration % 1000 == 0:
            current, current_key = deepcopy(best), best_key
    for i, row in enumerate(best, 1):
        if not row.get("from_remnant"):
            row["id"] = f"M{i}"
    return best


def summarize_bins(bins: list[dict], *, status: str = "FEASIBLE") -> dict:
    raw = sum(float(b["raw_length_mm"]) for b in bins)
    benefit = sum(float(b["co_cut_benefit_mm"]) for b in bins)
    capacity = sum(float(b["stock_length_mm"]) for b in bins)
    purchase = sum(float(b.get("purchase_cost_mm", b["stock_length_mm"])) for b in bins)
    return {
        "stocks": bins,
        "total_stock_length_mm": round(capacity, 6),
        "total_new_standard_stock_mm": round(purchase, 6),
        "total_raw_length_mm": round(raw, 6),
        "total_co_cut_benefit_mm": round(benefit, 6),
        "total_effective_length_mm": round(raw - benefit, 6),
        "utilization": round((raw - benefit) / capacity, 8) if capacity else 0.0,
        "total_switch": sum(int(b["switches"]) for b in bins),
        "status": status,
        "exact": False,
    }


def counts_from_bins(bins: list[dict]) -> Counter:
    result: Counter = Counter()
    for b in bins:
        result.update(b.get("sequence") or [])
    return result


def _allocate_to_remnants(
    inventory: list[dict],
    demand: dict[str, int],
    lengths: dict[str, float],
    savings: dict[str, dict[str, float]],
    *,
    mode: str,
    rng: random.Random,
) -> tuple[list[dict], dict[str, int], list[dict]]:
    """Conservatively assign items to existing remnants using raw lengths."""
    if mode == "none" or not inventory:
        return [], dict(demand), deepcopy(inventory)
    items = [g for g, count in demand.items() for _ in range(int(count))]
    if mode in {"longest", "cocut"}:
        items.sort(key=lambda g: (-lengths[g], g))
        ordered_inventory = sorted(inventory, key=lambda r: (-r["length_mm"], r["id"]))
    elif mode == "shortest":
        items.sort(key=lambda g: (lengths[g], g))
        ordered_inventory = sorted(inventory, key=lambda r: (r["length_mm"], r["id"]))
    elif mode == "type":
        items.sort(key=lambda g: (g, -lengths[g]))
        ordered_inventory = sorted(inventory, key=lambda r: (-r["length_mm"], r["id"]))
    else:
        rng.shuffle(items)
        ordered_inventory = list(inventory)
        rng.shuffle(ordered_inventory)

    work = [{**deepcopy(rem), "sequence": []} for rem in ordered_inventory]
    unassigned: list[str] = []
    for gid in items:
        size = float(lengths[gid])
        feasible = []
        for idx, row in enumerate(work):
            sequence = row["sequence"]
            if mode == "cocut":
                positions = {0, len(sequence)}
                positions.update(i + 1 for i, value in enumerate(sequence) if value == gid)
                for position in positions:
                    candidate = list(sequence)
                    candidate.insert(position, gid)
                    effective = evaluate_sequence(candidate, lengths, savings)[
                        "effective_length_mm"
                    ]
                    left = float(row["length_mm"]) - effective
                    if left >= -EPS:
                        feasible.append((left, idx, position))
            else:
                raw_used = sum(float(lengths[g]) for g in sequence)
                left = float(row["length_mm"]) - raw_used - size
                if left >= -EPS:
                    feasible.append((left, idx, len(sequence)))
        if not feasible:
            unassigned.append(gid)
            continue
        _left, idx, position = min(feasible)
        work[idx]["sequence"].insert(position, gid)

    used, unused = [], []
    for row in work:
        if row["sequence"]:
            used.append(
                {
                    "id": f"USE-{row['id']}",
                    "remnant_id": row["id"],
                    "stock_length_mm": float(row["length_mm"]),
                    "purchase_cost_mm": 0.0,
                    "sequence": row["sequence"],
                    "from_remnant": True,
                }
            )
        else:
            unused.append({"id": row["id"], "length_mm": float(row["length_mm"])})
    remaining = Counter(unassigned)
    return used, {g: int(remaining.get(g, 0)) for g in demand}, unused


def solve_multibatch_beam(
    demands: list[dict[str, int]],
    lengths: dict[str, float],
    savings: dict[str, dict[str, float]],
    *,
    stocks: Iterable[float] = DEFAULT_STOCKS,
    remnant_min_mm: float = 200.0,
    seed: int = 1,
    beam_width: int = 12,
    variants_per_state: int = 5,
    joint_iterations: int = 500,
    master_time_limit_s: float = 3.0,
    cocut_initial_bins: list[list[dict] | None] | None = None,
    cocut_remaining_master_time_limit_s: float = 0.0,
    cocut_remaining_max_keys_per_batch: int = 12,
) -> dict:
    """Future-aware multi-batch remnant search with explicit material balance.

    Beam search is heuristic: it retains several inventory futures instead of
    greedily consuming every available remnant.  Within a future, a mixed-stock
    compact CP-SAT master supplies new bars and joint ALNS refines
    allocation/sequence.
    """
    if not demands:
        raise ValueError("at least one batch is required")
    stock_tuple = tuple(float(s) for s in stocks)
    rng = random.Random(seed)
    states = [
        {
            "inventory": [],
            "batches": [],
            "purchase_mm": 0.0,
            "waste_mm": 0.0,
            "benefit_mm": 0.0,
            "switches": 0,
        }
    ]
    pattern_cache: dict[tuple[int, ...], list[dict]] = {}
    cocut_pattern_cache: dict[tuple[int, ...], list[dict] | None] = {}
    cocut_pattern_evidence: list[dict] = []
    beam_trace: list[dict] = []
    gids = tuple(lengths)
    future_raw = [
        sum(float(lengths[g]) * int(d.get(g, 0)) for g in gids) for d in demands
    ]
    for batch_index, demand in enumerate(demands, 1):
        if set(demand) != set(gids):
            raise ValueError(f"batch {batch_index} demand keys do not match tube types")
        candidates = []
        cocut_keys_built_this_batch = 0
        full_demand_key = tuple(int(demand.get(g, 0)) for g in gids)
        block_initial = None
        if cocut_initial_bins and batch_index <= len(cocut_initial_bins):
            block_initial = cocut_initial_bins[batch_index - 1]
            if block_initial is not None and counts_from_bins(block_initial) != Counter(
                {g: int(v) for g, v in demand.items()}
            ):
                raise ValueError(
                    f"co-cut initial plan for batch {batch_index} changed demand"
                )
        modes = ("none", "longest", "shortest", "type", "random", "cocut")
        for state_index, state in enumerate(states):
            for variant in range(max(1, variants_per_state)):
                mode = modes[variant % len(modes)]
                local_rng = random.Random(seed + batch_index * 100_003 + state_index * 1009 + variant)
                remnant_bins, remaining, unused = _allocate_to_remnants(
                    state["inventory"],
                    demand,
                    lengths,
                    savings,
                    mode=mode,
                    rng=local_rng,
                )
                key = tuple(int(remaining.get(g, 0)) for g in gids)
                if any(key):
                    if key not in pattern_cache:
                        ordered_remaining = {g: int(remaining.get(g, 0)) for g in gids}
                        pattern_cache[key] = compact_mixed_stock_patterns(
                            ordered_remaining,
                            lengths,
                            stocks=stock_tuple,
                            seed=seed + batch_index * 101 + variant,
                            time_limit_s=master_time_limit_s,
                            id_prefix=f"B{batch_index}-M",
                        )
                    raw_new_bins = deepcopy(pattern_cache[key])
                else:
                    raw_new_bins = []
                new_stock_options = [("raw_length_master", raw_new_bins)]
                # The `none` branch deliberately preserves all old remnants.
                # It is therefore safe to add a full-demand co-cut-aware plan
                # as a second candidate.  Other modes still use their own
                # remaining-demand raw master, avoiding a CP-SAT call per beam
                # state while keeping both modeling hypotheses alive.
                if mode == "none" and key == full_demand_key and block_initial:
                    new_stock_options.append(
                        ("homogeneous_cocut_block_master", deepcopy(block_initial))
                    )
                elif (
                    any(key)
                    and remnant_bins
                    and cocut_remaining_master_time_limit_s > 0
                ):
                    if key not in cocut_pattern_cache:
                        if (
                            cocut_remaining_max_keys_per_batch >= 0
                            and cocut_keys_built_this_batch
                            >= cocut_remaining_max_keys_per_batch
                        ):
                            continue_cocut_master = False
                        else:
                            continue_cocut_master = True
                            cocut_keys_built_this_batch += 1
                    else:
                        continue_cocut_master = True
                    if key not in cocut_pattern_cache and continue_cocut_master:
                        remaining_demand = {
                            gid: int(remaining.get(gid, 0)) for gid in gids
                        }
                        try:
                            cocut_rows, cocut_evidence = homogeneous_block_stock_patterns(
                                remaining_demand,
                                lengths,
                                savings,
                                stocks=stock_tuple,
                                seed=seed + batch_index * 2003 + variant,
                                time_limit_s=cocut_remaining_master_time_limit_s,
                                id_prefix=f"B{batch_index}-C",
                            )
                            cocut_pattern_cache[key] = cocut_rows
                            cocut_pattern_evidence.append(
                                {
                                    "batch": batch_index,
                                    "remaining_key": list(key),
                                    "available": True,
                                    **cocut_evidence,
                                }
                            )
                        except RuntimeError as exc:
                            cocut_pattern_cache[key] = None
                            cocut_pattern_evidence.append(
                                {
                                    "batch": batch_index,
                                    "remaining_key": list(key),
                                    "available": False,
                                    "reason": str(exc),
                                    "time_limit_s": cocut_remaining_master_time_limit_s,
                                }
                            )
                    if cocut_pattern_cache.get(key):
                        new_stock_options.append(
                            (
                                "remaining_demand_homogeneous_cocut_block_master",
                                deepcopy(cocut_pattern_cache[key]),
                            )
                        )

                for pattern_source, new_bins in new_stock_options:
                    base = remnant_bins + new_bins
                    if not base and any(int(v) for v in demand.values()):
                        continue
                    refined_remnants = (
                        optimize_fixed_assignments(
                            remnant_bins,
                            lengths,
                            savings,
                            seed=seed + batch_index * 1009 + variant,
                            iterations=joint_iterations,
                        )
                        if remnant_bins
                        else []
                    )
                    refined_new = (
                        optimize_joint_bins(
                            new_bins,
                            lengths,
                            savings,
                            seed=seed + batch_index * 1009 + variant + 37,
                            iterations=joint_iterations,
                            resize_new=True,
                            stocks=stock_tuple,
                        )
                        if new_bins
                        else []
                    )
                    refined = refined_remnants + refined_new
                    if counts_from_bins(refined) != Counter(
                        {g: int(v) for g, v in demand.items()}
                    ):
                        raise AssertionError("multi-batch search changed demand")

                    inventory_after = deepcopy(unused)
                    waste = 0.0
                    for row_index, row in enumerate(refined, 1):
                        left = float(row["leftover_mm"])
                        if left >= remnant_min_mm - EPS:
                            inventory_after.append(
                                {
                                    "id": f"B{batch_index}-R{row_index}",
                                    "length_mm": round(left, 6),
                                }
                            )
                        else:
                            waste += max(0.0, left)
                    inventory_after.sort(key=lambda r: (r["length_mm"], r["id"]))
                    summary = summarize_bins(refined)
                    before_total = sum(
                        float(r["length_mm"]) for r in state["inventory"]
                    )
                    after_total = sum(
                        float(r["length_mm"]) for r in inventory_after
                    )
                    purchased = float(summary["total_new_standard_stock_mm"])
                    effective = float(summary["total_effective_length_mm"])
                    balance_error = (
                        before_total + purchased - effective - waste - after_total
                    )
                    if abs(balance_error) > 1e-4:
                        raise AssertionError(f"inventory balance error {balance_error}")
                    summary.update(
                        {
                            "batch": f"B{batch_index}",
                            "demand": {g: int(demand[g]) for g in gids},
                            "inventory_before": deepcopy(state["inventory"]),
                            "inventory_after": inventory_after,
                            "waste_mm": round(waste, 6),
                            "inventory_balance_error_mm": round(balance_error, 9),
                            "remnant_strategy": mode,
                            "new_stock_pattern_source": pattern_source,
                        }
                    )
                    candidates.append(
                        {
                            "inventory": inventory_after,
                            "batches": state["batches"] + [summary],
                            "purchase_mm": state["purchase_mm"] + purchased,
                            "waste_mm": state["waste_mm"] + waste,
                            "benefit_mm": state["benefit_mm"]
                            + float(summary["total_co_cut_benefit_mm"]),
                            "switches": state["switches"]
                            + int(summary["total_switch"]),
                        }
                    )

        # Keep inventory-diverse candidates, then apply a future-aware bound.
        unique = {}
        for state in candidates:
            signature = tuple(round(float(r["length_mm"]), 6) for r in state["inventory"])
            key = (round(state["purchase_mm"], 6), signature)
            incumbent = unique.get(key)
            if incumbent is None or (
                -state["benefit_mm"], state["switches"], state["waste_mm"]
            ) < (
                -incumbent["benefit_mm"],
                incumbent["switches"],
                incumbent["waste_mm"],
            ):
                unique[key] = state
        remaining_raw = sum(future_raw[batch_index:])

        def useful_inventory_mm(state):
            """Conservative next-batch value of remnants for beam ranking.

            Inventory length is not automatically useful: a remnant shorter
            than every next-batch item is worth zero.  Reuse the feasible
            remnant allocator under several deterministic orderings and value
            only demand that it can actually place.  This is a search
            heuristic, not an optimality bound.
            """
            if batch_index >= len(demands) or not state["inventory"]:
                return 0.0
            next_demand = demands[batch_index]
            next_raw = sum(
                float(lengths[g]) * int(next_demand.get(g, 0)) for g in gids
            )
            best = 0.0
            for mode_index, mode in enumerate(
                ("longest", "shortest", "type", "random", "cocut")
            ):
                _used, remaining, _unused = _allocate_to_remnants(
                    state["inventory"],
                    next_demand,
                    lengths,
                    savings,
                    mode=mode,
                    rng=random.Random(
                        seed + batch_index * 1_000_003 + mode_index * 97
                    ),
                )
                remaining_raw_next = sum(
                    float(lengths[g]) * int(remaining.get(g, 0)) for g in gids
                )
                best = max(best, next_raw - remaining_raw_next)
            return min(remaining_raw, best)

        def beam_key(state):
            usable = useful_inventory_mm(state)
            return (
                round(state["purchase_mm"] - usable, 6),
                round(state["purchase_mm"], 6),
                -round(state["benefit_mm"], 6),
                state["switches"],
                round(state["waste_mm"], 6),
            )

        ranked = sorted(unique.values(), key=beam_key)
        keep = max(1, beam_width)
        selected: list[dict] = []
        selected_ids: set[int] = set()

        def retain(state):
            if len(selected) < keep and id(state) not in selected_ids:
                selected.append(state)
                selected_ids.add(id(state))

        # Stratified elites prevent the future-value heuristic from deleting
        # the cheapest cumulative purchase lane.  Reserve roughly half of the
        # beam for the lowest distinct purchase levels, then retain the best
        # candidate from each initializer source before filling by beam score.
        purchase_elite_slots = max(1, keep // 2)
        by_purchase: dict[float, list[dict]] = {}
        for state in ranked:
            by_purchase.setdefault(round(state["purchase_mm"], 6), []).append(state)
        for purchase in sorted(by_purchase)[:purchase_elite_slots]:
            retain(min(by_purchase[purchase], key=beam_key))

        by_source: dict[str, list[dict]] = {}
        for state in ranked:
            source = str(
                state["batches"][-1].get("new_stock_pattern_source", "unknown")
            )
            by_source.setdefault(source, []).append(state)
        for source in sorted(by_source):
            retain(min(by_source[source], key=beam_key))

        for state in ranked:
            retain(state)
        states = sorted(selected, key=beam_key)
        beam_trace.append(
            {
                "batch": batch_index,
                "candidate_count": len(candidates),
                "unique_state_count": len(unique),
                "selected_state_count": len(states),
                "selected": [
                    {
                        "cumulative_purchase_mm": round(
                            float(state["purchase_mm"]), 6
                        ),
                        "heuristic_useful_inventory_mm": round(
                            float(useful_inventory_mm(state)), 6
                        ),
                        "inventory_lengths_mm": [
                            round(float(row["length_mm"]), 6)
                            for row in state["inventory"]
                        ],
                        "new_stock_pattern_source": state["batches"][-1].get(
                            "new_stock_pattern_source"
                        ),
                        "remnant_strategy": state["batches"][-1].get(
                            "remnant_strategy"
                        ),
                    }
                    for state in states
                ],
            }
        )
        if not states:
            raise RuntimeError(f"no feasible beam state after batch {batch_index}")

    best = min(
        states,
        key=lambda s: (
            round(s["purchase_mm"], 6),
            -round(s["benefit_mm"], 6),
            s["switches"],
            round(s["waste_mm"], 6),
        ),
    )
    total_waste = float(best["waste_mm"])
    final_inventory_mm = sum(
        float(row["length_mm"]) for row in best["inventory"]
    )
    total_effective = sum(
        float(row["total_effective_length_mm"]) for row in best["batches"]
    )
    purchase = float(best["purchase_mm"])
    return {
        "batches": [
            {
                "batch": row["batch"],
                "demand": row["demand"],
                "result": {k: v for k, v in row.items() if k not in {"batch", "demand"}},
                "inventory_after": row["inventory_after"],
            }
            for row in best["batches"]
        ],
        "total_new_standard_stock_mm": round(best["purchase_mm"], 6),
        "total_stock_length_mm": round(best["purchase_mm"], 6),
        "total_co_cut_benefit_mm": round(best["benefit_mm"], 6),
        "total_switch": best["switches"],
        "total_effective_length_mm": round(total_effective, 6),
        "total_waste_mm": round(total_waste, 6),
        "final_inventory_mm": round(final_inventory_mm, 6),
        "direct_utilization": round(total_effective / purchase, 8)
        if purchase
        else 0.0,
        "nonwaste_utilization": round(
            (total_effective + final_inventory_mm) / purchase, 8
        )
        if purchase
        else 0.0,
        "final_inventory": best["inventory"],
        "status": "FEASIBLE",
        "exact": False,
        "method": "multi-batch beam search + mixed-stock master + joint ALNS; lexicographic purchase/co-cut/switches (waste diagnostic)",
        "seed": seed,
        "beam_width": beam_width,
        "beam_policy": "stratified purchase/source elites + next-batch feasible remnant value",
        "beam_trace": beam_trace,
        "cocut_remaining_master_evidence": cocut_pattern_evidence,
    }
