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
from fixture_paths import fixture_dir, fixture_file  # noqa: E402

EPS = 1e-6


def _tube_orientation_path_bound(
    demand: dict[str, int],
    lengths: dict[str, float],
    savings: dict[str, dict[str, float]],
    stocks: list[float],
) -> dict:
    """Independent aggregate orientation/path-cover co-cut upper bound.

    This validator implementation deliberately does not import
    ``tube_optimization``.  It permits disconnected cycles and ignores bar
    capacities before representable-stock rounding, so its maximum saving is
    optimistic and its stock result is a valid lower bound.
    """
    from ortools.sat.python import cp_model

    gids = tuple(demand)
    states = tuple((gid, orientation) for gid in gids for orientation in ("L", "R"))
    total_pieces = sum(int(value) for value in demand.values())
    raw = sum(float(lengths[gid]) * int(demand[gid]) for gid in gids)
    if not total_pieces:
        return {
            "status": "OPTIMAL",
            "co_cut_upper_bound_mm": 0.0,
            "effective_length_lower_bound_mm": 0.0,
            "stock_lower_bound_mm": 0.0,
            "relaxed_joint_count": 0,
        }
    scale = 10_000
    model = cp_model.CpModel()
    oriented = {
        state: model.new_int_var(0, int(demand[state[0]]), f"n_{state[0]}_{state[1]}")
        for state in states
    }
    arcs = {
        (left, right): model.new_int_var(
            0,
            total_pieces,
            f"x_{left[0]}_{left[1]}_{right[0]}_{right[1]}",
        )
        for left in states
        for right in states
    }
    for gid in gids:
        model.add(oriented[(gid, "L")] + oriented[(gid, "R")] == int(demand[gid]))
    for state in states:
        model.add(sum(arcs[(state, other)] for other in states) <= oriented[state])
        model.add(sum(arcs[(other, state)] for other in states) <= oriented[state])
    relaxed_joint_count = total_pieces - 1
    model.add(sum(arcs.values()) == relaxed_joint_count)

    def weight(left: tuple[str, str], right: tuple[str, str]) -> int:
        source_right = "R" if left[1] == "L" else "L"
        value = float(savings[f"{left[0]}-{right[0]}"][source_right + right[1]])
        return int(math.ceil(value * scale - EPS))

    model.maximize(
        sum(
            weight(left, right) * arcs[(left, right)]
            for left in states
            for right in states
        )
    )
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 1
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"independent orientation bound returned {solver.status_name(status)}")
    scaled_upper = max(float(solver.objective_value), float(solver.best_objective_bound))
    saving_upper = math.ceil(scaled_upper - EPS) / scale
    effective_lower = max(0.0, raw - saving_upper)
    stock_values = tuple(sorted(set(float(value) for value in stocks)))
    reachable = {0.0}
    all_totals: set[float] = set()
    for _bar in range(total_pieces):
        reachable = {
            round(total + stock, 6) for total in reachable for stock in stock_values
        }
        all_totals.update(reachable)
        if min(reachable) >= effective_lower - EPS:
            break
    stock_lower = min(total for total in all_totals if total + EPS >= effective_lower)
    return {
        "status": solver.status_name(status),
        "co_cut_upper_bound_mm": round(saving_upper, 6),
        "effective_length_lower_bound_mm": round(effective_lower, 6),
        "stock_lower_bound_mm": round(stock_lower, 6),
        "relaxed_joint_count": relaxed_joint_count,
        "scale_per_mm": scale,
    }


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
    coords = _load(d / "coords.json")
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


def _validate_tube(_problem_id: str, sol: dict) -> list[dict]:
    """Validate tube_cut / cutting_stock envelope from solve_tube_cut_b2026.

    Does not re-solve the cutting problem. Checks:
    - envelope already applied by caller
    - questions.q1.. present with stocks/batches
    - top objective matches primary question total (q3 preferred, else q1)
    - source/solver claim tube tool (not SP mock gold)
    """
    checks: list[dict] = []
    pc = str(sol.get("problem_class") or "").lower()
    checks.append(
        {
            "name": "problem_class",
            "ok": pc in {"tube_cut", "tube", "tube_bfd", "cutting_stock", "cut_stock"},
            "detail": None if pc else "missing problem_class",
        }
    )
    src = str(sol.get("source") or "")
    solver = str(sol.get("solver") or "")
    tube_src = "tube" in src.lower() or "tube" in solver.lower() or "solve_tube" in src
    checks.append(
        {
            "name": "tube_source",
            "ok": tube_src,
            "detail": None if tube_src else f"source/solver not tube: {src!r}/{solver!r}",
        }
    )
    qs = sol.get("questions")
    if not isinstance(qs, dict) or not qs:
        checks.append(
            {"name": "shape_questions", "ok": False, "detail": "questions object required"}
        )
        return checks
    checks.append({"name": "shape_questions", "ok": True})

    for name in ("q1", "q2", "q3"):
        q = qs.get(name)
        if not isinstance(q, dict):
            checks.append(
                {"name": f"shape_{name}", "ok": False, "detail": f"{name} missing"}
            )
            continue
        stocks = q.get("stocks")
        ok_stocks = isinstance(stocks, list) and len(stocks) >= 1
        checks.append(
            {
                "name": f"shape_{name}_stocks",
                "ok": ok_stocks,
                "detail": None if ok_stocks else f"{name}.stocks empty/missing",
            }
        )
        st = str(q.get("status") or "").upper()
        checks.append(
            {
                "name": f"status_{name}",
                "ok": st in {"FEASIBLE", "OPTIMAL", "OK", ""},
                "detail": None if st in {"FEASIBLE", "OPTIMAL", "OK", ""} else f"{name}.status={st}",
            }
        )
        # light recompute: sum stock_length ≈ total_stock_length_mm
        if ok_stocks and "total_stock_length_mm" in q:
            try:
                total = sum(float(s.get("stock_length_mm") or 0) for s in stocks if isinstance(s, dict))
                declared = float(q["total_stock_length_mm"])
                checks.append(
                    {
                        "name": f"recompute_{name}_stock_sum",
                        "ok": _num_eq(total, declared),
                        "expected": declared,
                        "got": total,
                    }
                )
            except (TypeError, ValueError) as exc:
                checks.append(
                    {
                        "name": f"recompute_{name}_stock_sum",
                        "ok": False,
                        "detail": str(exc),
                    }
                )

    q4 = qs.get("q4")
    if isinstance(q4, dict):
        batches = q4.get("batches")
        ok_b = isinstance(batches, list) and len(batches) >= 1
        checks.append(
            {
                "name": "shape_q4_batches",
                "ok": ok_b,
                "detail": None if ok_b else "q4.batches empty/missing",
            }
        )
    else:
        checks.append({"name": "shape_q4", "ok": False, "detail": "q4 missing"})

    # primary objective = q3 total if present else q1 (matches solve_dispatch envelope)
    primary = None
    if isinstance(qs.get("q3"), dict) and "total_stock_length_mm" in qs["q3"]:
        primary = float(qs["q3"]["total_stock_length_mm"])
        primary_name = "q3.total_stock_length_mm"
    elif isinstance(qs.get("q1"), dict) and "total_stock_length_mm" in qs["q1"]:
        primary = float(qs["q1"]["total_stock_length_mm"])
        primary_name = "q1.total_stock_length_mm"
    else:
        primary_name = "missing"
    if primary is None:
        checks.append(
            {
                "name": "recompute_objective",
                "ok": False,
                "detail": "no q1/q3 total_stock_length_mm",
            }
        )
    else:
        try:
            obj = float(sol["objective"])
            checks.append(
                {
                    "name": "recompute_objective",
                    "ok": _num_eq(obj, primary),
                    "expected": primary,
                    "got": sol.get("objective"),
                    "detail": f"primary={primary_name}",
                }
            )
        except (TypeError, ValueError, KeyError) as exc:
            checks.append(
                {"name": "recompute_objective", "ok": False, "detail": str(exc)}
            )

    # heuristic honesty: not proven optimal unless meta says so
    meta = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
    if meta.get("proven_optimal") is True and str(sol.get("status")).upper() == "OPTIMAL":
        checks.append(
            {
                "name": "optimality_claim",
                "ok": False,
                "detail": "Tube heuristic pipeline must not claim proven_optimal OPTIMAL",
            }
        )
    else:
        checks.append({"name": "optimality_claim", "ok": True})

    checks.extend(_validate_tube_v2(_problem_id, sol, qs))

    return checks


def _tube_check(name: str, ok: bool, detail: str | None = None, **extra) -> dict:
    return {"name": name, "ok": bool(ok), "detail": None if ok else detail, **extra}


def _tube_validate_stocks(
    name: str,
    q: dict,
    model: dict,
    *,
    cocut: bool,
    allow_remnants: bool = False,
) -> tuple[list[dict], dict[str, int]]:
    from collections import Counter

    from tube_optimization import evaluate_sequence, switches

    checks: list[dict] = []
    lengths = model["lengths"]
    savings = model["savings"]
    allowed_stocks = [float(x) for x in model["stock_lengths_mm"]]
    counts: Counter = Counter()
    declared_stocks = q.get("stocks")
    if not isinstance(declared_stocks, list):
        return [_tube_check(f"strict_{name}_stocks", False, "stocks must be a list")], {}

    total_capacity = total_raw = total_benefit = total_effective = total_purchase = 0.0
    total_switch = 0
    seen_ids: set[str] = set()
    for index, stock in enumerate(declared_stocks):
        label = f"{name}.stocks[{index}]"
        if not isinstance(stock, dict):
            checks.append(_tube_check(f"strict_{label}", False, "stock must be an object"))
            continue
        stock_id = str(stock.get("id") or "")
        checks.append(
            _tube_check(
                f"strict_{label}_unique_id",
                bool(stock_id) and stock_id not in seen_ids,
                f"missing or duplicate id {stock_id!r}",
            )
        )
        seen_ids.add(stock_id)
        sequence = stock.get("sequence")
        valid_sequence = isinstance(sequence, list) and bool(sequence) and all(
            isinstance(g, str) and g in lengths for g in sequence
        )
        checks.append(
            _tube_check(
                f"strict_{label}_sequence",
                valid_sequence,
                "sequence must contain known tube ids",
            )
        )
        if not valid_sequence:
            continue
        counts.update(sequence)
        capacity = float(stock.get("stock_length_mm") or 0.0)
        from_remnant = bool(stock.get("from_remnant"))
        stock_kind_ok = capacity > 0 and (
            (allow_remnants and from_remnant)
            or any(_num_eq(capacity, allowed) for allowed in allowed_stocks)
        )
        checks.append(
            _tube_check(
                f"strict_{label}_stock_kind",
                stock_kind_ok,
                f"new stock must be one of {allowed_stocks}; remnant={from_remnant}",
            )
        )
        if cocut:
            expected = evaluate_sequence(sequence, lengths, savings)
        else:
            raw = sum(float(lengths[g]) for g in sequence)
            expected = {
                "raw_length_mm": raw,
                "co_cut_benefit_mm": 0.0,
                "effective_length_mm": raw,
                "switches": switches(sequence),
            }
        raw = float(expected["raw_length_mm"])
        benefit = float(expected["co_cut_benefit_mm"])
        effective = float(expected["effective_length_mm"])
        expected_switch = int(expected["switches"])
        left = capacity - effective
        checks.append(
            _tube_check(
                f"strict_{label}_fits",
                effective <= capacity + EPS,
                f"effective={effective} exceeds stock={capacity}",
            )
        )
        for field, expected_value in (
            ("raw_length_mm", raw),
            ("co_cut_benefit_mm", benefit),
            ("effective_length_mm", effective),
            ("leftover_mm", left),
            ("utilization", effective / capacity if capacity else 0.0),
        ):
            try:
                got = float(stock[field])
                ok = _num_eq(got, expected_value)
            except (KeyError, TypeError, ValueError):
                got, ok = stock.get(field), False
            checks.append(
                _tube_check(
                    f"strict_{label}_{field}",
                    ok,
                    f"expected={expected_value}, got={got}",
                )
            )
        try:
            got_switch = int(stock["switches"])
        except (KeyError, TypeError, ValueError):
            got_switch = -1
        checks.append(
            _tube_check(
                f"strict_{label}_switches",
                got_switch == expected_switch,
                f"expected={expected_switch}, got={got_switch}",
            )
        )
        purchase = float(stock.get("purchase_cost_mm", 0.0 if from_remnant else capacity))
        expected_purchase = 0.0 if from_remnant else capacity
        checks.append(
            _tube_check(
                f"strict_{label}_purchase",
                _num_eq(purchase, expected_purchase),
                f"expected={expected_purchase}, got={purchase}",
            )
        )
        total_capacity += capacity
        total_raw += raw
        total_benefit += benefit
        total_effective += effective
        total_purchase += purchase
        total_switch += expected_switch

    if cocut:
        totals = {
            "total_stock_length_mm": total_capacity,
            "total_raw_length_mm": total_raw,
            "total_co_cut_benefit_mm": total_benefit,
            "total_effective_length_mm": total_effective,
            "total_new_standard_stock_mm": total_purchase,
            "total_switch": total_switch,
        }
    else:
        totals = {
            "total_stock_length_mm": total_capacity,
            "total_axial_length_mm": total_raw,
            "total_switch": total_switch,
        }
    for field, expected_value in totals.items():
        if field not in q:
            checks.append(_tube_check(f"strict_{name}_{field}", False, f"missing {field}"))
            continue
        try:
            got = float(q[field])
            ok = _num_eq(got, expected_value)
        except (TypeError, ValueError):
            got, ok = q.get(field), False
        checks.append(
            _tube_check(
                f"strict_{name}_{field}", ok, f"expected={expected_value}, got={got}"
            )
        )
    expected_util = total_effective / total_capacity if total_capacity else 0.0
    try:
        got_util = float(q["utilization"])
        util_ok = _num_eq(got_util, expected_util)
    except (KeyError, TypeError, ValueError):
        got_util, util_ok = q.get("utilization"), False
    checks.append(
        _tube_check(
            f"strict_{name}_utilization",
            util_ok,
            f"expected={expected_util}, got={got_util}",
        )
    )
    return checks, dict(counts)


def _validate_tube_v2(problem_id: str, sol: dict, qs: dict) -> list[dict]:
    from collections import Counter

    checks: list[dict] = []
    model = sol.get("model_snapshot")
    if not isinstance(model, dict) or model.get("schema") != "orpath.tube_model.v2":
        return [
            _tube_check(
                "strict_model_snapshot",
                False,
                "orpath.tube_model.v2 snapshot required; stale/light outputs are not strictly valid",
            )
        ]
    lengths = model.get("lengths")
    savings = model.get("savings")
    stocks = model.get("stock_lengths_mm")
    model_ok = (
        isinstance(lengths, dict)
        and bool(lengths)
        and all(isinstance(g, str) and float(v) > 0 for g, v in lengths.items())
        and isinstance(savings, dict)
        and isinstance(stocks, list)
        and bool(stocks)
    )
    checks.append(_tube_check("strict_model_snapshot", model_ok, "invalid lengths/savings/stocks"))
    if not model_ok:
        return checks
    synthetic_allowed = str(problem_id).lower().startswith("synthetic")
    policy_ok = (
        str(model.get("units")) == "mm"
        and int(model.get("profile_bins") or 0) >= 36
        and (
            synthetic_allowed
            or (
                sorted(float(x) for x in stocks)
                == [9000.0, 10000.0, 11000.0, 12000.0]
                and _num_eq(float(model.get("remnant_min_mm") or 0.0), 200.0)
            )
        )
    )
    checks.append(
        _tube_check(
            "strict_problem_policy",
            policy_ok,
            "real Tube requires units=mm, profile_bins>=36, stocks=9/10/11/12m and remnant_min=200mm",
        )
    )
    if not policy_ok:
        return checks
    input_hashes = model.get("input_sha256")
    hashes_ok = isinstance(input_hashes, dict) and bool(input_hashes) and all(
        isinstance(path, str)
        and isinstance(digest, str)
        and len(digest) == 64
        for path, digest in (input_hashes or {}).items()
    )
    checks.append(
        _tube_check(
            "strict_input_hash_manifest",
            hashes_ok,
            "non-empty SHA-256 input manifest required",
        )
    )
    if not hashes_ok:
        return checks
    real_paths = [path for path in input_hashes if "://" not in path]
    synthetic_paths = [path for path in input_hashes if "://" in path]
    source_kind_ok = (
        synthetic_allowed and bool(synthetic_paths) and not real_paths
    ) or (not synthetic_paths and bool(real_paths))
    checks.append(
        _tube_check(
            "strict_input_source_kind",
            source_kind_ok,
            "synthetic URI hashes are allowed only for synthetic problem ids; real Tube solutions require filesystem inputs",
        )
    )
    if not source_kind_ok:
        return checks
    root = Path(__file__).resolve().parents[1]
    local_inputs_ok = True
    local_detail = None
    for rel in real_paths:
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            local_inputs_ok, local_detail = False, f"input path escapes repository: {rel}"
            break
        if not path.is_file():
            local_inputs_ok, local_detail = False, f"input missing after solve: {rel}"
            break
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        if digest != input_hashes[rel]:
            local_inputs_ok, local_detail = False, f"input changed after solve: {rel}"
            break
    checks.append(
        _tube_check("strict_input_hashes", local_inputs_ok, local_detail)
    )
    if not local_inputs_ok:
        return checks
    modes = {"LL", "LR", "RL", "RR"}
    matrix_ok = True
    matrix_detail = None
    for a in lengths:
        for b in lengths:
            row = savings.get(f"{a}-{b}")
            if not isinstance(row, dict) or not modes <= set(row):
                matrix_ok, matrix_detail = False, f"missing modes for {a}-{b}"
                break
            for mode in modes:
                value = float(row[mode])
                if value < -EPS or value > min(float(lengths[a]), float(lengths[b])) + EPS:
                    matrix_ok, matrix_detail = False, f"out-of-range saving {a}-{b}/{mode}={value}"
                    break
            if not matrix_ok:
                break
        if not matrix_ok:
            break
    checks.append(_tube_check("strict_cocut_matrix", matrix_ok, matrix_detail))
    if not matrix_ok:
        return checks
    # For a real attachment-backed solution, independently rebuild geometry
    # from the hashed files.  Synthetic sources deliberately use a URI scheme.
    expected_real_batches = None
    if real_paths:
        try:
            from solve_tube_cut_b2026 import (
                build_geometry,
                load_batches,
                required_input_paths,
            )

            expected_paths = {
                path.relative_to(root).as_posix() for path in required_input_paths()
            }
            manifest_complete = set(real_paths) == expected_paths
            checks.append(
                _tube_check(
                    "strict_input_manifest_complete",
                    manifest_complete,
                    f"expected={sorted(expected_paths)}, got={sorted(real_paths)}",
                )
            )
            if not manifest_complete:
                return checks
            rebuilt = build_geometry(n_bins=int(model.get("profile_bins") or 360))
            lengths_ok = set(rebuilt["lengths"]) == set(lengths) and all(
                _num_eq(rebuilt["lengths"][g], lengths[g]) for g in lengths
            )
            savings_ok = set(rebuilt["savings"]) == set(savings)
            if savings_ok:
                savings_ok = all(
                    _num_eq(rebuilt["savings"][pair][mode], savings[pair][mode])
                    for pair in savings
                    for mode in modes
                )
            checks.append(
                _tube_check(
                    "strict_geometry_recompute",
                    lengths_ok and savings_ok,
                    f"lengths_ok={lengths_ok}, savings_ok={savings_ok}",
                )
            )
            if not (lengths_ok and savings_ok):
                return checks
            expected_real_batches = load_batches()
        except Exception as exc:  # noqa: BLE001
            checks.append(
                _tube_check("strict_geometry_recompute", False, str(exc))
            )
            return checks

    question_counts: dict[str, dict[str, int]] = {}
    for name, cocut in (("q1", False), ("q2", True), ("q3", True)):
        q = qs.get(name)
        if not isinstance(q, dict):
            continue
        q_checks, counts = _tube_validate_stocks(name, q, model, cocut=cocut)
        checks.extend(q_checks)
        question_counts[name] = counts
        demand = q.get("demand")
        if real_paths:
            expected = {g: 50 for g in lengths}
            declared = (
                {g: int(demand.get(g, 0)) for g in lengths}
                if isinstance(demand, dict)
                else {}
            )
            demand_source_ok = declared == expected
            checks.append(
                _tube_check(
                    f"strict_{name}_source_demand",
                    demand_source_ok,
                    f"expected 50 each, got={declared}",
                )
            )
        else:
            expected = {g: int(demand.get(g, 0)) for g in lengths} if isinstance(demand, dict) else {}
        checks.append(
            _tube_check(
                f"strict_{name}_demand",
                bool(expected) and Counter(counts) == Counter(expected),
                f"expected={expected}, got={counts}",
            )
        )

    q1, q2 = qs.get("q1"), qs.get("q2")
    if isinstance(q1, dict) and isinstance(q2, dict):
        q1_assign = {
            str(s.get("id")): Counter(s.get("sequence") or []) for s in q1.get("stocks") or []
        }
        q2_assign = {
            str(s.get("id")): Counter(s.get("sequence") or []) for s in q2.get("stocks") or []
        }
        checks.append(
            _tube_check(
                "strict_q2_fixed_assignment",
                q1_assign == q2_assign,
                "Q2 must preserve the Q1 multiset assigned to every stock",
            )
        )
        q1_opt = q1.get("optimality") if isinstance(q1.get("optimality"), dict) else {}
        if q1_opt:
            primary_lb = float(q1_opt.get("primary_lower_bound_mm") or 0.0)
            primary_total = float(q1.get("total_stock_length_mm") or 0.0)
            secondary = (
                q1_opt.get("secondary")
                if isinstance(q1_opt.get("secondary"), dict)
                else {}
            )
            switch_incumbent = int(secondary.get("switch_incumbent", -1))
            switch_lb = int(secondary.get("switch_lower_bound", -1))
            checks.append(
                _tube_check(
                    "strict_q1_primary_bound",
                    0.0 <= primary_lb <= primary_total + EPS,
                    f"lower_bound={primary_lb}, incumbent={primary_total}",
                )
            )
            checks.append(
                _tube_check(
                    "strict_q1_secondary_evidence",
                    switch_incumbent == int(q1.get("total_switch") or 0)
                    and 0 <= switch_lb <= switch_incumbent,
                    f"lower_bound={switch_lb}, incumbent={switch_incumbent}",
                )
            )

    for name in ("q3", "q4"):
        question = qs.get(name)
        if not isinstance(question, dict):
            continue
        optimality = (
            question.get("optimality")
            if isinstance(question.get("optimality"), dict)
            else {}
        )
        if not optimality:
            continue
        incumbent_field = (
            "total_new_standard_stock_mm" if name == "q4" else "total_stock_length_mm"
        )
        incumbent = float(question.get(incumbent_field) or 0.0)
        lower = float(optimality.get("lower_bound_mm") or 0.0)
        declared_incumbent = float(optimality.get("incumbent_mm") or -1.0)
        checks.append(
            _tube_check(
                f"strict_{name}_bound_evidence",
                0.0 <= lower <= incumbent + EPS
                and _num_eq(declared_incumbent, incumbent),
                f"lower_bound={lower}, declared_incumbent={declared_incumbent}, incumbent={incumbent}",
            )
        )
        demand_for_bound: dict[str, int] = {}
        if name == "q3":
            declared_demand = question.get("demand")
            if isinstance(declared_demand, dict):
                demand_for_bound = {
                    gid: int(declared_demand.get(gid, 0)) for gid in lengths
                }
        else:
            batches_for_bound = question.get("batches")
            if isinstance(batches_for_bound, list):
                demand_for_bound = {
                    gid: sum(
                        int((batch.get("demand") or {}).get(gid, 0))
                        for batch in batches_for_bound
                        if isinstance(batch, dict)
                    )
                    for gid in lengths
                }
        orientation = optimality.get("orientation_consistent")
        if demand_for_bound and isinstance(orientation, dict):
            try:
                recomputed_bound = _tube_orientation_path_bound(
                    demand_for_bound,
                    lengths,
                    savings,
                    [float(value) for value in model.get("stock_lengths_mm") or []],
                )
                proof_ok = all(
                    _num_eq(orientation.get(field), recomputed_bound[field])
                    for field in (
                        "co_cut_upper_bound_mm",
                        "effective_length_lower_bound_mm",
                        "stock_lower_bound_mm",
                        "relaxed_joint_count",
                        "scale_per_mm",
                    )
                )
                declared_proven = bool(optimality.get("proven_optimal"))
                expected_proven = _num_eq(recomputed_bound["stock_lower_bound_mm"], incumbent)
                gap_abs = float(optimality.get("absolute_gap_mm") or 0.0)
                gap_rel = float(optimality.get("relative_gap_to_lower_bound") or 0.0)
                expected_abs = incumbent - recomputed_bound["stock_lower_bound_mm"]
                expected_rel = (
                    expected_abs / recomputed_bound["stock_lower_bound_mm"]
                    if recomputed_bound["stock_lower_bound_mm"]
                    else 0.0
                )
                aggregate_ok = (
                    _num_eq(lower, recomputed_bound["stock_lower_bound_mm"])
                    and proof_ok
                    and declared_proven == expected_proven
                    and _num_eq(gap_abs, expected_abs)
                    and _num_eq(gap_rel, expected_rel)
                )
                detail = (
                    f"declared_lower={lower}, recomputed={recomputed_bound}, "
                    f"declared_proven={declared_proven}, expected_proven={expected_proven}"
                )
            except Exception as exc:  # noqa: BLE001
                aggregate_ok, detail = False, str(exc)
            checks.append(
                _tube_check(
                    f"strict_{name}_orientation_bound_recompute",
                    aggregate_ok,
                    detail,
                )
            )

    q4 = qs.get("q4")
    if isinstance(q4, dict) and isinstance(q4.get("batches"), list):
        total_purchase = total_benefit = total_waste = total_effective = 0.0
        total_switch = 0
        previous_inventory: list[dict] = []
        for index, batch in enumerate(q4["batches"], 1):
            result = batch.get("result") if isinstance(batch, dict) else None
            if not isinstance(result, dict):
                checks.append(_tube_check(f"strict_q4_b{index}", False, "result missing"))
                continue
            b_checks, counts = _tube_validate_stocks(
                f"q4_b{index}", result, model, cocut=True, allow_remnants=True
            )
            checks.extend(b_checks)
            demand = batch.get("demand") if isinstance(batch.get("demand"), dict) else {}
            declared = {g: int(demand.get(g, 0)) for g in lengths}
            expected = (
                {g: int(expected_real_batches[index - 1][g]) for g in lengths}
                if expected_real_batches is not None and index <= len(expected_real_batches)
                else declared
            )
            if expected_real_batches is not None:
                checks.append(
                    _tube_check(
                        f"strict_q4_b{index}_source_demand",
                        declared == expected,
                        f"workbook={expected}, declared={declared}",
                    )
                )
            checks.append(
                _tube_check(
                    f"strict_q4_b{index}_demand",
                    Counter(counts) == Counter(expected),
                    f"expected={expected}, got={counts}",
                )
            )
            before = result.get("inventory_before")
            after = result.get("inventory_after")
            inv_shape = isinstance(before, list) and isinstance(after, list)
            checks.append(
                _tube_check(
                    f"strict_q4_b{index}_inventory_shape",
                    inv_shape,
                    "inventory_before/after lists required",
                )
            )
            if inv_shape:
                before_sig = sorted((str(r.get("id")), float(r.get("length_mm"))) for r in before)
                previous_sig = sorted(
                    (str(r.get("id")), float(r.get("length_mm"))) for r in previous_inventory
                )
                checks.append(
                    _tube_check(
                        f"strict_q4_b{index}_inventory_chain",
                        before_sig == previous_sig,
                        f"before={before_sig}, previous={previous_sig}",
                    )
                )
                before_map = dict(before_sig)
                used_remnant_ids: set[str] = set()
                remnant_sources_ok = True
                remnant_sources_detail = None
                for stock in result.get("stocks") or []:
                    if not stock.get("from_remnant"):
                        continue
                    remnant_id = str(stock.get("remnant_id") or "")
                    capacity = float(stock.get("stock_length_mm") or 0.0)
                    if (
                        remnant_id not in before_map
                        or remnant_id in used_remnant_ids
                        or not _num_eq(capacity, before_map.get(remnant_id, -1.0))
                    ):
                        remnant_sources_ok = False
                        remnant_sources_detail = (
                            f"invalid/reused remnant {remnant_id!r} capacity={capacity}"
                        )
                        break
                    used_remnant_ids.add(remnant_id)
                checks.append(
                    _tube_check(
                        f"strict_q4_b{index}_remnant_sources",
                        remnant_sources_ok,
                        remnant_sources_detail,
                    )
                )
                threshold = float(model.get("remnant_min_mm") or 0.0)
                expected_after = [
                    length for rem_id, length in before_sig if rem_id not in used_remnant_ids
                ]
                expected_waste = 0.0
                for stock in result.get("stocks") or []:
                    left = float(stock.get("leftover_mm") or 0.0)
                    if left >= threshold - EPS:
                        expected_after.append(left)
                    else:
                        expected_waste += max(0.0, left)
                got_after = sorted(float(r.get("length_mm")) for r in after)
                expected_after.sort()
                inventory_contents_ok = len(got_after) == len(expected_after) and all(
                    _num_eq(a, b) for a, b in zip(got_after, expected_after)
                )
                checks.append(
                    _tube_check(
                        f"strict_q4_b{index}_inventory_contents",
                        inventory_contents_ok,
                        f"expected_lengths={expected_after}, got={got_after}",
                    )
                )
                try:
                    got_waste = float(result.get("waste_mm"))
                    waste_ok = _num_eq(got_waste, expected_waste)
                except (TypeError, ValueError):
                    got_waste, waste_ok = result.get("waste_mm"), False
                checks.append(
                    _tube_check(
                        f"strict_q4_b{index}_waste",
                        waste_ok,
                        f"expected={expected_waste}, got={got_waste}",
                    )
                )
                previous_inventory = after
                balance = (
                    sum(v for _i, v in before_sig)
                    + float(result.get("total_new_standard_stock_mm") or 0.0)
                    - float(result.get("total_effective_length_mm") or 0.0)
                    - float(result.get("waste_mm") or 0.0)
                    - sum(float(r.get("length_mm")) for r in after)
                )
                checks.append(
                    _tube_check(
                        f"strict_q4_b{index}_inventory_balance",
                        abs(balance) <= 1e-4,
                        f"balance_error={balance}",
                    )
                )
            total_purchase += float(result.get("total_new_standard_stock_mm") or 0.0)
            total_benefit += float(result.get("total_co_cut_benefit_mm") or 0.0)
            total_waste += float(result.get("waste_mm") or 0.0)
            total_effective += float(result.get("total_effective_length_mm") or 0.0)
            total_switch += int(result.get("total_switch") or 0)
        for field, expected in (
            ("total_new_standard_stock_mm", total_purchase),
            ("total_stock_length_mm", total_purchase),
            ("total_co_cut_benefit_mm", total_benefit),
            ("total_switch", total_switch),
        ):
            try:
                got = float(q4[field])
                ok = _num_eq(got, expected)
            except (KeyError, TypeError, ValueError):
                got, ok = q4.get(field), False
            checks.append(
                _tube_check(
                    f"strict_q4_{field}", ok, f"expected={expected}, got={got}"
                )
            )
        final_inventory = q4.get("final_inventory")
        final_ok = isinstance(final_inventory, list) and sorted(
            (str(r.get("id")), float(r.get("length_mm"))) for r in final_inventory
        ) == sorted(
            (str(r.get("id")), float(r.get("length_mm"))) for r in previous_inventory
        )
        checks.append(
            _tube_check(
                "strict_q4_final_inventory",
                final_ok,
                "final_inventory must equal the last batch inventory_after",
            )
        )
        if final_ok:
            final_inventory_mm = sum(
                float(row.get("length_mm")) for row in final_inventory
            )
            extra_totals = (
                ("total_effective_length_mm", total_effective),
                ("total_waste_mm", total_waste),
                ("final_inventory_mm", final_inventory_mm),
                (
                    "direct_utilization",
                    total_effective / total_purchase if total_purchase else 0.0,
                ),
                (
                    "nonwaste_utilization",
                    (total_effective + final_inventory_mm) / total_purchase
                    if total_purchase
                    else 0.0,
                ),
            )
            for field, expected in extra_totals:
                try:
                    got = float(q4[field])
                    ok = _num_eq(got, expected)
                except (KeyError, TypeError, ValueError):
                    got, ok = q4.get(field), False
                checks.append(
                    _tube_check(
                        f"strict_q4_{field}",
                        ok,
                        f"expected={expected}, got={got}",
                    )
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


def _checks_envelope_tube(sol: dict) -> list[dict]:
    required = ["problem_id", "status", "objective", "solver", "source"]
    missing = [k for k in required if k not in sol]
    return [
        {
            "name": "envelope",
            "ok": not missing
            and str(sol.get("status") or "").upper()
            in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "ERROR", "BLOCKED"},
            "detail": f"missing={missing}" if missing else None,
        }
    ]


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
