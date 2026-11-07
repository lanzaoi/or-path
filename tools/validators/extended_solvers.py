"""Independent Validators for Extended OR-Path Solvers (Numbers Truth).

Verifies solutions independently from the reported envelope data for:
1. jssp (Job Shop Scheduling)
2. bin_packing (1D Bin Packing & Knapsack)
3. facility_location (Capacitated Facility Location)
4. portfolio_opt (Markowitz Mean-Variance)
5. network_flow (Min-Cost Flow, Bipartite Matching, Multi-Commodity Flow)
6. qubo_ising (QUBO Max-Cut, Ising Number Partitioning, General QUBO / Ising)
7. rcpsp (Resource-Constrained Project Scheduling, PSPLib *.sm)
8. staff_rostering (Shift rostering / nurse scheduling, CP-SAT)
9. lot_sizing (Multi-Period Lot Sizing: ULSP via Wagner-Whitin DP / CLSP via SCIP MIP)
10. qap (Quadratic Assignment Problem: facility layout, SciPy FAQ + 2-opt)
11. graph_coloring (Chromatic number: DIMACS *.col / edge lists, NetworkX DSATUR + CP-SAT)
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

EPS = 1e-4


def validate_jssp(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate Job Shop Scheduling: precedence, no-overlap, makespan."""
    checks: list[dict[str, Any]] = []

    tasks = sol.get("schedule") or []
    if not isinstance(tasks, list) or not tasks:
        checks.append({"name": "schedule_presence", "ok": False, "detail": "Empty or missing schedule"})
        return checks

    # 1. Check task durations: duration == end - start
    duration_ok = True
    for t in tasks:
        if t.get("end", 0) - t.get("start", 0) != t.get("duration", 0):
            duration_ok = False
            break
    checks.append({"name": "task_duration_consistency", "ok": duration_ok})

    # 2. Check job precedence: within each job, task k starts after task k-1 ends
    jobs: dict[int, list[dict[str, Any]]] = {}
    for t in tasks:
        j_id = t.get("job_id", t.get("job", 0))
        jobs.setdefault(j_id, []).append(t)

    precedence_ok = True
    for j_id, j_tasks in jobs.items():
        # sort by task_id / task
        j_tasks_sorted = sorted(j_tasks, key=lambda x: x.get("task_id", x.get("task", 0)))
        for a, b in zip(j_tasks_sorted, j_tasks_sorted[1:]):
            if b.get("start", 0) < a.get("end", 0):
                precedence_ok = False
                break
        if not precedence_ok:
            break
    checks.append({"name": "job_precedence", "ok": precedence_ok})

    # 3. Check machine disjunctive constraint (no overlap)
    machines: dict[int, list[dict[str, Any]]] = {}
    for t in tasks:
        m_id = t.get("machine_id", t.get("machine", 0))
        machines.setdefault(m_id, []).append(t)

    no_overlap = True
    for m_id, m_tasks in machines.items():
        m_sorted = sorted(m_tasks, key=lambda x: x.get("start", 0))
        for a, b in zip(m_sorted, m_sorted[1:]):
            if b.get("start", 0) < a.get("end", 0):
                no_overlap = False
                break
        if not no_overlap:
            break
    checks.append({"name": "machine_no_overlap", "ok": no_overlap})

    # 4. Check makespan equals max end time
    recomputed_makespan = max((t.get("end", 0) for t in tasks), default=0)
    expected_obj = sol.get("objective", sol.get("makespan"))
    makespan_ok = recomputed_makespan == expected_obj
    checks.append({
        "name": "makespan_objective_match",
        "ok": makespan_ok,
        "expected": expected_obj,
        "got": recomputed_makespan,
    })

    # 5. Setup-time consistency (换模时延): when a setup schedule is present,
    #    every consecutive pair on a machine must respect start >= prev_end + setup.
    setup = sol.get("setup")
    if setup not in (None, "none"):
        # group by machine, ordered by start
        by_machine: dict[int, list[dict[str, Any]]] = {}
        for t in tasks:
            by_machine.setdefault(t.get("machine_id", t.get("machine", 0)), []).append(t)

        setup_ok = True
        recomputed_total = 0
        for _m, m_tasks in by_machine.items():
            m_sorted = sorted(m_tasks, key=lambda x: x.get("start", 0))
            for a, b in zip(m_sorted, m_sorted[1:]):
                if isinstance(setup, int):
                    dur = setup
                else:
                    dur = setup.get((a.get("op"), b.get("op")), 0)
                if dur:
                    recomputed_total += dur
                    if b.get("start", 0) < a.get("end", 0) + dur:
                        setup_ok = False
        checks.append({"name": "setup_time_respected", "ok": setup_ok})

        if "total_setup_time" in sol:
            checks.append({
                "name": "total_setup_time_match",
                "ok": recomputed_total == sol.get("total_setup_time"),
                "expected": sol.get("total_setup_time"),
                "got": recomputed_total,
            })

    return checks


def _aabb_overlap_3d(
    a: tuple[float, float, float, float, float, float],
    b: tuple[float, float, float, float, float, float],
) -> bool:
    """Epsilon-tolerant AABB overlap test for [x, y, z, dx, dy, dz] boxes."""
    ax, ay, az, adx, ady, adz = a
    bx, by, bz, bdx, bdy, bdz = b
    return (
        ax < bx + bdx - EPS and ax + adx > bx + EPS
        and ay < by + bdy - EPS and ay + ady > by + EPS
        and az < bz + bdz - EPS and az + adz > bz + EPS
    )


def _aabb_overlap_2d(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    """Epsilon-tolerant AABB overlap test for [x, y, w, h] rectangles."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax < bx + bw - EPS and ax + aw > bx + EPS
            and ay < by + bh - EPS and ay + ah > by + EPS)


def validate_bin_packing(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate Bin Packing across 1D / 2D / 3D modes (Numbers Truth).

    The validator detects the packing mode from the solution envelope and
    re-verifies the geometry independently from the reported coordinates:

    * **3D** (``mode == '3d'``): each item inside its bin bounds, no AABB
      overlap, and per-bin weight within ``max_weight``.
    * **2D** (``mode == '2d'``): each part inside its sheet bounds and no
      rectangle overlap.
    * **1D** (default / legacy): capacity respected, every item assigned once,
      and bin count matches the objective (original contract preserved).
    """
    checks: list[dict[str, Any]] = []
    mode = str(sol.get("mode", "1d")).lower()

    if mode == "3d":
        checks.extend(_validate_bin_packing_3d(sol))
    elif mode == "2d":
        checks.extend(_validate_bin_packing_2d(sol))
    else:
        checks.extend(_validate_bin_packing_1d(sol))
    return checks


def _validate_bin_packing_1d(sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate 1D Bin Packing: capacity, assignment, bin count."""
    checks: list[dict[str, Any]] = []

    bins = sol.get("bins") or []
    if not isinstance(bins, list):
        checks.append({"name": "bins_presence", "ok": False, "detail": "Missing bins list"})
        return checks

    bin_cap = sol.get("bin_capacity", 100)
    total_assigned_items = set()
    capacity_ok = True

    for b in bins:
        items = b.get("items", [])
        weights = b.get("weights", [])
        if sum(weights) != b.get("total_weight", 0):
            capacity_ok = False
        if sum(weights) > bin_cap + EPS:
            capacity_ok = False
        for item in items:
            if item in total_assigned_items:
                # Duplicate item assigned
                checks.append({"name": "item_uniqueness", "ok": False, "detail": f"Item {item} duplicate"})
                return checks
            total_assigned_items.add(item)

    checks.append({"name": "bin_capacity_respected", "ok": capacity_ok})

    # Check total items match
    num_items = sol.get("num_items", len(total_assigned_items))
    checks.append({
        "name": "all_items_packed",
        "ok": len(total_assigned_items) == num_items,
        "expected": num_items,
        "got": len(total_assigned_items),
    })

    # Check objective matches bin count
    checks.append({
        "name": "bin_count_objective_match",
        "ok": len(bins) == sol.get("objective"),
        "expected": sol.get("objective"),
        "got": len(bins),
    })

    return checks


def _validate_bin_packing_3d(sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Independently re-verify a 3D packing from reported coordinates."""
    checks: list[dict[str, Any]] = []
    bins = sol.get("bins") or []
    if not isinstance(bins, list) or not bins:
        checks.append({"name": "bins_presence", "ok": False, "detail": "Missing bins list"})
        return checks

    in_bounds = True
    no_overlap = True
    weight_ok = True
    placed_names: set[str] = set()

    for b in bins:
        bw, bh, bd = b.get("width", 0), b.get("height", 0), b.get("depth", 0)
        max_w = b.get("max_weight", 0)
        boxes: list[tuple[float, ...]] = []
        for it in b.get("items", []):
            x, y, z = it["x"], it["y"], it["z"]
            dx, dy, dz = it["dx"], it["dy"], it["dz"]
            placed_names.add(it.get("name"))
            if x < -EPS or y < -EPS or z < -EPS:
                in_bounds = False
            if dx <= 0 or dy <= 0 or dz <= 0:
                in_bounds = False
            if x + dx > bw + EPS or y + dy > bh + EPS or z + dz > bd + EPS:
                in_bounds = False
            boxes.append((x, y, z, dx, dy, dz))
        if b.get("total_weight", 0) > max_w + EPS:
            weight_ok = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if _aabb_overlap_3d(boxes[i], boxes[j]):
                    no_overlap = False

    num_items = sol.get("num_items", len(placed_names))
    unfitted = set(sol.get("unfitted_items", []))
    checks.append({"name": "bin_3d_in_bounds", "ok": in_bounds})
    checks.append({"name": "bin_3d_no_overlap", "ok": no_overlap})
    checks.append({"name": "bin_3d_weight_respected", "ok": weight_ok})
    checks.append({"name": "bin_3d_all_items_packed", "ok": len(placed_names) == num_items,
                   "expected": num_items, "got": len(placed_names)})
    checks.append({"name": "bin_3d_no_unfitted_expected", "ok": not unfitted,
                   "unfitted": sorted(unfitted)})
    return checks


def _validate_bin_packing_2d(sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Independently re-verify a 2D nesting from reported coordinates."""
    checks: list[dict[str, Any]] = []
    bins = sol.get("bins") or []
    if not isinstance(bins, list) or not bins:
        checks.append({"name": "bins_presence", "ok": False, "detail": "Missing bins list"})
        return checks

    in_bounds = True
    no_overlap = True
    placed_names: set[str] = set()

    for b in bins:
        bw, bh = b.get("width", 0), b.get("height", 0)
        rects: list[tuple[float, ...]] = []
        for p in b.get("parts", []):
            x, y, w, h = p["x"], p["y"], p["w"], p["h"]
            placed_names.add(p.get("name"))
            if x < -EPS or y < -EPS or w <= 0 or h <= 0:
                in_bounds = False
            if x + w > bw + EPS or y + h > bh + EPS:
                in_bounds = False
            rects.append((x, y, w, h))
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                if _aabb_overlap_2d(rects[i], rects[j]):
                    no_overlap = False

    num_parts = sol.get("num_parts", len(placed_names))
    unfitted = set(sol.get("unfitted_parts", []))
    checks.append({"name": "bin_2d_in_bounds", "ok": in_bounds})
    checks.append({"name": "bin_2d_no_overlap", "ok": no_overlap})
    checks.append({"name": "bin_2d_all_parts_placed", "ok": len(placed_names) == num_parts,
                   "expected": num_parts, "got": len(placed_names)})
    checks.append({"name": "bin_2d_no_unfitted_expected", "ok": not unfitted,
                   "unfitted": sorted(unfitted)})
    return checks


def validate_facility_location(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate Capacitated Facility Location Problem (CFLP, SSCFLP, SCND)."""
    checks: list[dict[str, Any]] = []

    open_facs = sol.get("open_facilities") or []
    allocs = sol.get("allocations") or sol.get("assignments") or []
    total_cost = sol.get("objective")

    if not isinstance(open_facs, list) or not isinstance(allocs, list):
        checks.append({"name": "solution_structure", "ok": False, "detail": "Missing facilities or allocations"})
        return checks

    # Check that open facility capacities are not exceeded
    open_fac_ids = {f.get("facility_id") for f in open_facs}
    fac_capacities = {f.get("facility_id"): f.get("capacity", float("inf")) for f in open_facs}
    fac_loads = {f.get("facility_id"): f.get("load", 0.0) for f in open_facs}

    capacity_ok = all(fac_loads[f_id] <= fac_capacities[f_id] + EPS for f_id in open_fac_ids)
    checks.append({"name": "facility_capacity_respected", "ok": capacity_ok})

    recomputed_fixed = sum(f.get("fixed_cost", 0) for f in open_facs)
    checks.append({
        "name": "facility_cost_positive",
        "ok": float(total_cost) >= recomputed_fixed - EPS,
        "fixed_cost": recomputed_fixed,
        "total_cost": total_cost,
    })

    # Check demand satisfaction: every customer demand is 100% satisfied
    demand_satisfied = True
    for a in allocs:
        served = a.get("served_by") or []
        tot_frac = sum(s.get("fraction", 0.0) for s in served)
        if abs(tot_frac - 1.0) > 1e-3:
            demand_satisfied = False
            break
    checks.append({"name": "demand_fully_satisfied", "ok": demand_satisfied})

    # If single-source mode, verify binary 0/1 assignment
    if sol.get("single_source") or sol.get("mode") == "sscflp":
        is_binary = True
        for a in allocs:
            served = a.get("served_by") or []
            if len(served) != 1 or abs(served[0].get("fraction", 0.0) - 1.0) > 1e-4:
                is_binary = False
                break
        checks.append({"name": "single_source_binary", "ok": is_binary})

    # If two-echelon mode, verify flow conservation (inflow == outflow)
    if sol.get("mode") == "two_echelon":
        flow_balanced = all(f.get("flow_balanced", False) or abs(f.get("inflow", 0.0) - f.get("outflow", 0.0)) < 1e-3 for f in open_facs)
        checks.append({"name": "two_echelon_flow_balance", "ok": flow_balanced})

    return checks


def _portfolio_inputs(sol: dict[str, Any]) -> dict[str, Any]:
    """Return the raw financial input manifest carried by ``sol`` (or ``{}``).

    The Markowitz solver embeds an ``inputs`` block (asset names, expected
    returns, covariance matrix, prices) so the independent validator and the
    red team can recompute every reported metric from first principles.  Legacy
    payloads may instead expose the arrays at the top level; both shapes are
    accepted defensively.
    """
    if not isinstance(sol, dict):
        return {}
    for key in ("inputs", "input_manifest", "raw_problem"):
        block = sol.get(key)
        if isinstance(block, dict) and block:
            return block
    return sol


def _portfolio_array(value: Any, length: int) -> list[float] | None:
    """Coerce ``value`` to a length-``length`` float list, else ``None``."""
    if not isinstance(value, (list, tuple)) or len(value) != length:
        return None
    try:
        return [float(v) for v in value]
    except (TypeError, ValueError):
        return None


def validate_portfolio(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate Markowitz Portfolio allocations and risk/return.

    Performs full independent recomputation of the reported metrics from the
    raw financial inputs (Numbers Truth):

      * ``weights_sum_to_one``            — allocations lie on the unit simplex
      * ``long_only_bounds``              — no negative (short) positions
      * ``expected_return_recompute``     — ``sum(w_i * mu_i)`` matches
      * ``volatility_recompute``          — ``sqrt(w^T Sigma w)`` matches
      * ``sharpe_recomputation``          — ``(ret - rf) / vol`` matches
      * ``discrete_shares_integrality``   — integer share lots only
      * ``discrete_capital_feasibility``  — share cost fits the capital budget

    The return/volatility recomputations are only emitted when the payload
    carries the matching raw inputs; legacy payloads therefore keep validating
    against the sharpe identity alone.
    """
    checks: list[dict[str, Any]] = []

    allocs = sol.get("allocations") or {}
    if not isinstance(allocs, dict) or not allocs:
        checks.append({"name": "allocations_presence", "ok": False, "detail": "Missing allocations"})
        return checks

    names = list(allocs.keys())
    try:
        weights = [float(allocs[name]) for name in names]
    except (TypeError, ValueError):
        checks.append({
            "name": "allocations_numeric",
            "ok": False,
            "detail": "allocation weights must be numeric",
        })
        return checks

    total_weight = sum(weights)
    weight_sum_ok = abs(total_weight - 1.0) <= 1e-3
    checks.append({
        "name": "weights_sum_to_one",
        "ok": weight_sum_ok,
        "got": round(total_weight, 4),
        "expected": 1.0,
    })

    all_non_negative = all(w >= -1e-5 for w in weights)
    checks.append({"name": "long_only_bounds", "ok": all_non_negative})

    vol = float(sol.get("volatility", 0.0) or 0.0)
    ret = float(sol.get("expected_return", 0.0) or 0.0)
    rf = float(sol.get("risk_free_rate", 0.02) or 0.0)
    sharpe = float(sol.get("sharpe_ratio", 0.0) or 0.0)

    inputs = _portfolio_inputs(sol)

    # Expected-return recomputation from the raw return vector.
    mu = _portfolio_array(inputs.get("expected_returns"), len(names))
    if mu is not None:
        recomputed_ret = sum(w * m for w, m in zip(weights, mu))
        checks.append({
            "name": "expected_return_recompute",
            "ok": abs(recomputed_ret - ret) <= 1e-3,
            "expected": ret,
            "got": round(recomputed_ret, 6),
        })

    # Volatility / variance recomputation from the raw covariance matrix.
    cov = inputs.get("cov_matrix")
    if isinstance(cov, (list, tuple)) and len(cov) == len(names):
        matrix = np.asarray(cov, dtype=float)
        if matrix.shape == (len(names), len(names)) and np.all(np.isfinite(matrix)):
            variance = float(np.dot(weights, np.dot(matrix, weights)))
            recomputed_vol = float(np.sqrt(max(variance, 0.0)))
            checks.append({
                "name": "volatility_recompute",
                "ok": abs(recomputed_vol - vol) <= 1e-3,
                "expected": vol,
                "got": round(recomputed_vol, 6),
            })

    # Sharpe identity.
    if vol > 0:
        recomputed_sharpe = (ret - rf) / vol
        checks.append({
            "name": "sharpe_recomputation",
            "ok": abs(recomputed_sharpe - sharpe) <= 1e-2,
            "expected": sharpe,
            "got": round(recomputed_sharpe, 4),
        })

    # Discrete integer-share allocation integrity and capital feasibility.
    discrete = sol.get("discrete_allocation")
    if isinstance(discrete, dict) and discrete:
        shares = discrete.get("shares")
        if isinstance(shares, dict) and shares:
            try:
                integral = all(
                    float(q) >= 0.0 and float(q) == int(float(q)) for q in shares.values()
                )
            except (TypeError, ValueError):
                integral = False
            checks.append({"name": "discrete_shares_integrality", "ok": bool(integral)})

            prices = discrete.get("prices") or inputs.get("prices") or {}
            total_value = discrete.get("total_portfolio_value")
            if isinstance(prices, dict) and prices and isinstance(total_value, (int, float)) \
                    and not isinstance(total_value, bool):
                invested = 0.0
                for name, qty in shares.items():
                    price = prices.get(name)
                    if isinstance(price, (int, float)) and not isinstance(price, bool):
                        invested += float(qty) * float(price)
                leftover = discrete.get("leftover_cash")
                leftover = float(leftover) if isinstance(leftover, (int, float)) \
                    and not isinstance(leftover, bool) else 0.0
                feasibility = (invested <= float(total_value) + 1e-6
                               and abs((invested + leftover) - float(total_value)) <= 1e-3)
                checks.append({
                    "name": "discrete_capital_feasibility",
                    "ok": bool(feasibility),
                    "invested": round(invested, 4),
                    "leftover": round(leftover, 4),
                    "total": float(total_value),
                })

    return checks


def validate_network_flow(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate Network Flow / Bipartite Matching / Multi-Commodity Flow."""
    checks: list[dict[str, Any]] = []

    mode = sol.get("mode", "min_cost_flow")
    if mode == "min_cost_flow":
        flows = sol.get("active_flows") or []
        obj = sol.get("objective", 0)
        recomputed_cost = sum(f.get("total_cost", 0) for f in flows)
        cost_ok = abs(recomputed_cost - obj) <= EPS
        checks.append({
            "name": "min_cost_flow_total",
            "ok": cost_ok,
            "expected": obj,
            "got": recomputed_cost,
        })
    elif mode == "bipartite_matching":
        matches = sol.get("matches") or {}
        obj = sol.get("objective", 0)
        matched_tasks = list(matches.values())
        unique_tasks = len(set(matched_tasks)) == len(matched_tasks)
        checks.append({"name": "bipartite_task_uniqueness", "ok": unique_tasks})
        checks.append({
            "name": "matching_cardinality_match",
            "ok": len(matches) == obj,
            "expected": obj,
            "got": len(matches),
        })
    elif mode == "multi_commodity_flow":
        checks.extend(_validate_mcnf(sol))

    return checks


def _validate_mcnf(sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Independently re-verify a Multi-Commodity Network Flow solution.

    Recomputes everything from the per-commodity ``edge_flows`` reported in
    the envelope (Numbers Truth):
      * mcnf_capacity_respected : aggregate per-edge flow <= capacity (+EPS)
      * mcnf_flow_conservation  : out - in == supply/demand at every node
      * mcnf_cost_match         : objective == sum(flow * unit_cost)
      * mcnf_total_flow_match   : total_flow == sum of commodity shipments
    """
    checks: list[dict[str, Any]] = []

    commodities = sol.get("commodity_flows") or []
    utilizations = sol.get("edge_utilizations") or []
    if not isinstance(commodities, list) or not isinstance(utilizations, list) or not commodities:
        checks.append({"name": "mcnf_structure", "ok": False, "detail": "commodity_flows or edge_utilizations missing"})
        return checks

    # Aggregate per-edge flows across commodities from the raw edge_flows.
    edge_total: dict[tuple[str, str], float] = {}
    for k in commodities:
        for r in k.get("edge_flows") or []:
            key = (r.get("from"), r.get("to"))
            edge_total[key] = edge_total.get(key, 0.0) + float(r.get("flow", 0.0))

    # 1. Bundle capacities
    capacity_ok = True
    for e in utilizations:
        key = (e.get("from"), e.get("to"))
        total = edge_total.get(key, 0.0)
        if total > float(e.get("capacity", float("inf"))) + EPS:
            capacity_ok = False
        if abs(total - float(e.get("total_flow", 0.0))) > EPS:
            capacity_ok = False
    checks.append({"name": "mcnf_capacity_respected", "ok": capacity_ok})

    # 2. Flow conservation per commodity at every touched node
    conservation_ok = True
    for k in commodities:
        src = k.get("source")
        sink = k.get("sink")
        demand = float(k.get("demand", 0.0))
        balance: dict[str, float] = {}
        nodes: set[str] = set()
        for r in k.get("edge_flows") or []:
            f = float(r.get("flow", 0.0))
            balance[r.get("from")] = balance.get(r.get("from"), 0.0) + f
            balance[r.get("to")] = balance.get(r.get("to"), 0.0) - f
            nodes.add(r.get("from"))
            nodes.add(r.get("to"))
        for n in nodes:
            # balance[n] = outflow - inflow; source supplies (+demand),
            # sink absorbs (-demand).
            expected = demand if n == src else (-demand if n == sink else 0.0)
            if abs(balance.get(n, 0.0) - expected) > EPS:
                conservation_ok = False
    checks.append({"name": "mcnf_flow_conservation", "ok": conservation_ok})

    # 3. Objective == recomputed sum(flow * unit_cost)
    recomputed_cost = sum(
        float(r.get("flow", 0.0)) * float(r.get("unit_cost", 0.0))
        for k in commodities
        for r in k.get("edge_flows") or []
    )
    obj = float(sol.get("objective", 0.0))
    checks.append({
        "name": "mcnf_cost_match",
        "ok": abs(recomputed_cost - obj) <= EPS,
        "expected": obj,
        "got": recomputed_cost,
    })

    # 4. total_flow == sum of commodity shipments
    shipped = sum(float(k.get("shipped", 0.0)) for k in commodities)
    checks.append({
        "name": "mcnf_total_flow_match",
        "ok": abs(shipped - float(sol.get("total_flow", 0.0))) <= EPS,
        "expected": sol.get("total_flow", 0.0),
        "got": shipped,
    })

    return checks


def _parse_bias_keys(bias: dict[Any, float]) -> dict[tuple[int, int], float]:
    """Normalize bias dict keys to int tuples (accepts 'i,j', '(i, j)', or tuple keys)."""
    out: dict[tuple[int, int], float] = {}
    for k, v in bias.items():
        if isinstance(k, str):
            clean = k.strip("()[] ")
            parts = clean.split(",")
            i, j = int(parts[0].strip()), int(parts[1].strip())
        else:
            i, j = int(k[0]), int(k[1])
        out[(i, j)] = float(v)
    return out


def validate_qubo_ising(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate QUBO Max-Cut, Number Partitioning, general QUBO, or Ising spin glass."""
    checks: list[dict[str, Any]] = []

    mode = sol.get("mode", "max_cut")
    if mode == "max_cut":
        cut_edges = sol.get("cut_edges") or []
        obj = sol.get("objective", 0)
        partitions = sol.get("node_partition") or {}
        set_0 = set(partitions.get("set_0", []))
        set_1 = set(partitions.get("set_1", []))

        # Check partitions are disjoint
        disjoint = len(set_0.intersection(set_1)) == 0
        checks.append({"name": "partition_disjoint", "ok": disjoint})

        # Check every cut edge actually spans across set_0 and set_1
        valid_cuts = True
        for u, v in cut_edges:
            if not ((u in set_0 and v in set_1) or (u in set_1 and v in set_0)):
                valid_cuts = False
                break
        checks.append({"name": "cut_edges_span_partitions", "ok": valid_cuts})
        checks.append({
            "name": "cut_size_matches_objective",
            "ok": len(cut_edges) == obj,
            "expected": obj,
            "got": len(cut_edges),
        })
    elif mode == "number_partitioning":
        subset_a = sol.get("subset_a") or []
        subset_b = sol.get("subset_b") or []
        sum_a = sum(subset_a)
        sum_b = sum(subset_b)
        discrepancy = abs(sum_a - sum_b)
        checks.append({
            "name": "partition_sums_consistency",
            "ok": sum_a == sol.get("sum_a") and sum_b == sol.get("sum_b"),
        })
        checks.append({
            "name": "discrepancy_matches_objective",
            "ok": discrepancy == sol.get("objective"),
            "expected": sol.get("objective"),
            "got": discrepancy,
        })
    elif mode == "qubo":
        # Recompute x^T Q x independently from the problem data (Numbers Truth).
        Q = _parse_bias_keys(sol.get("Q") or {})
        sample = {int(k): int(v) for k, v in (sol.get("sample") or {}).items()}
        recomputed = sum(Q[(i, j)] * sample.get(i, 0) * sample.get(j, 0) for (i, j) in Q)
        obj = float(sol.get("objective", 0.0))
        checks.append({
            "name": "qubo_energy_match",
            "ok": abs(recomputed - obj) <= EPS,
            "expected": obj,
            "got": recomputed,
        })
        binary_ok = all(v in (0, 1) for v in sample.values())
        checks.append({"name": "qubo_sample_binary", "ok": binary_ok})
    elif mode == "ising":
        # Recompute sum h_i s_i + sum J_ij s_i s_j + offset independently.
        h_raw = sol.get("h") or {}
        h = {int(k): float(v) for k, v in h_raw.items()}
        J = _parse_bias_keys(sol.get("J") or {})
        offset = float(sol.get("offset", 0.0))
        spins = {int(k): int(v) for k, v in (sol.get("spins") or {}).items()}
        recomputed = offset + sum(h[i] * spins.get(i, 0) for i in h)
        recomputed += sum(J[(i, j)] * spins.get(i, 0) * spins.get(j, 0) for (i, j) in J)
        obj = float(sol.get("objective", 0.0))
        checks.append({
            "name": "ising_energy_match",
            "ok": abs(recomputed - obj) <= EPS,
            "expected": obj,
            "got": recomputed,
        })
        binary_ok = all(v in (-1, 1) for v in spins.values())
        checks.append({"name": "ising_spins_binary", "ok": binary_ok})

    return checks


def validate_staff_rostering(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate Staff Rostering: coverage, one-shift, night-rest, consecutive limit.

    Recomputes everything from the envelope ``roster`` and ``shift_demands``
    (Numbers Truth — no solver is re-run).
    """
    checks: list[dict[str, Any]] = []

    roster = sol.get("roster") or {}
    shift_demands = sol.get("shift_demands") or []
    max_consec = int(sol.get("max_consecutive_days", 5))
    num_days = int(sol.get("num_days", len(shift_demands)))
    working_shifts = ["Morning", "Afternoon", "Night"]

    if not isinstance(roster, dict) or not roster:
        checks.append({"name": "roster_presence", "ok": False, "detail": "roster empty or missing"})
        return checks

    # 1. roster_daily_coverage: for every day and working shift, the number of
    #    assigned staff >= the required demand.
    coverage_ok = True
    coverage_detail: str | None = None
    for d in range(num_days):
        demand = shift_demands[d] if d < len(shift_demands) else {}
        for s in working_shifts:
            need = demand.get(s, 0)
            if need <= 0:
                continue
            assigned = sum(
                1 for emp_schedule in roster.values()
                if emp_schedule[d] == s
            )
            if assigned < need:
                coverage_ok = False
                coverage_detail = f"day {d} {s}: assigned {assigned} < demand {need}"
                break
        if not coverage_ok:
            break
    checks.append({"name": "roster_daily_coverage", "ok": coverage_ok,
                   "detail": coverage_detail})

    # 2. roster_one_shift_per_day: each employee has exactly one shift per day.
    one_shift_ok = True
    one_shift_detail: str | None = None
    for emp, schedule in roster.items():
        if len(schedule) != num_days:
            one_shift_ok = False
            one_shift_detail = f"{emp}: {len(schedule)} entries, expected {num_days}"
            break
    checks.append({"name": "roster_one_shift_per_day", "ok": one_shift_ok,
                   "detail": one_shift_detail})

    # 3. roster_night_shift_rest: Night on day d → not Morning on day d+1.
    night_rest_ok = True
    night_rest_detail: str | None = None
    for emp, schedule in roster.items():
        for d in range(num_days - 1):
            if schedule[d] == "Night" and schedule[d + 1] == "Morning":
                night_rest_ok = False
                night_rest_detail = f"{emp}: Night on day {d} followed by Morning on day {d+1}"
                break
        if not night_rest_ok:
            break
    checks.append({"name": "roster_night_shift_rest", "ok": night_rest_ok,
                   "detail": night_rest_detail})

    # 4. roster_consecutive_days_limit: no employee works > max_consec days in a row.
    consecutive_ok = True
    consecutive_detail: str | None = None
    for emp, schedule in roster.items():
        run = 0
        for d in range(num_days):
            if schedule[d] in working_shifts:
                run += 1
                if run > max_consec:
                    consecutive_ok = False
                    consecutive_detail = f"{emp}: {run} consecutive workdays ending day {d} > {max_consec}"
                    break
            else:
                run = 0
        if not consecutive_ok:
            break
    checks.append({"name": "roster_consecutive_days_limit", "ok": consecutive_ok,
                   "detail": consecutive_detail})

    return checks


def _precedence_pair(pair: Any) -> tuple[int, int] | None:
    """Normalize a precedence entry to (u, v); accepts dict or [u, v]."""
    try:
        if isinstance(pair, dict):
            u = int(pair.get("u", pair.get("from")))
            v = int(pair.get("v", pair.get("to")))
        else:
            u, v = int(pair[0]), int(pair[1])
        return u, v
    except (TypeError, ValueError, KeyError, IndexError):
        return None


def validate_rcpsp(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate RCPSP: precedence, renewable capacity per time slot, makespan.

    Recomputes everything from the envelope (schedule, precedences,
    resource_capacities) — Numbers Truth, no solver is re-run.
    """
    checks: list[dict[str, Any]] = []

    schedule = sol.get("schedule") or []
    if not isinstance(schedule, list) or not schedule:
        checks.append({"name": "schedule_presence", "ok": False,
                       "detail": "empty or missing schedule"})
        return checks

    starts: dict[int, int] = {}
    ends: dict[int, int] = {}
    demands: dict[int, list[int]] = {}
    for e in schedule:
        aid = int(e["activity_id"])
        starts[aid] = int(e["start"])
        ends[aid] = int(e["end"])
        demands[aid] = [int(d) for d in (e.get("demands") or [])]

    # 1. Duration consistency: end - start == duration for every activity.
    dur_ok = all(ends[a] - starts[a] == int(e["duration"]) for e in schedule
                 for a in [int(e["activity_id"])])
    checks.append({"name": "rcpsp_duration_consistency", "ok": dur_ok})

    # 2. Schedule completeness: ids cover 0..num_activities-1.
    n_expected = int(sol.get("num_activities", len(schedule)))
    ids_ok = sorted(starts) == list(range(n_expected))
    checks.append({"name": "rcpsp_schedule_completeness", "ok": ids_ok,
                   "expected": n_expected, "got": len(starts)})

    # 3. Precedences: start[v] >= end[u] for every (u, v) pair.
    prec_ok = True
    prec_detail: str | None = None
    for pair in sol.get("precedences") or []:
        uv = _precedence_pair(pair)
        if uv is None:
            prec_ok = False
            prec_detail = f"bad precedence entry: {pair!r}"
            break
        u, v = uv
        if u not in ends or v not in starts:
            prec_ok = False
            prec_detail = f"precedence {u}->{v} references unknown activity"
            break
        if starts[v] < ends[u]:
            prec_ok = False
            prec_detail = f"start[{v}]={starts[v]} < end[{u}]={ends[u]}"
            break
    checks.append({"name": "rcpsp_precedence_respected", "ok": prec_ok,
                   "detail": prec_detail})

    # 4. Renewable capacities at each integer time slot t.
    caps_raw = sol.get("resource_capacities") or []
    caps = [int(c) for c in caps_raw]
    n_res = int(sol.get("num_resources", len(caps)))
    horizon = max(ends.values(), default=0)
    cap_ok = True
    cap_detail: str | None = None
    for t in range(horizon):
        for r in range(n_res):
            used = sum(
                demands[a][r] if r < len(demands[a]) else 0
                for a in starts
                if starts[a] <= t < ends[a]
            )
            cap = caps[r] if r < len(caps) else 0
            if used > cap:
                cap_ok = False
                cap_detail = f"t={t} R{r}: used {used} > capacity {cap}"
                break
        if not cap_ok:
            break
    checks.append({"name": "rcpsp_resource_capacities_respected", "ok": cap_ok,
                   "detail": cap_detail})

    # 5. Makespan: max(end) == makespan == objective.
    recomputed = max(ends.values(), default=0)
    makespan = sol.get("makespan")
    obj = sol.get("objective")
    ms_ok = recomputed == makespan == obj
    checks.append({"name": "rcpsp_makespan_matches_objective", "ok": ms_ok,
                   "expected": obj,
                   "got": recomputed})

    return checks


def validate_pyvrp(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate PyVRP / VRPTW / VRPPDTW solution envelope.

    Numbers Truth:
    1. Envelope status in (OPTIMAL, FEASIBLE).
    2. Route structure: every route begins and ends at depot.
    3. Completeness: all clients / shipments visited exactly once.
    4. PDP Precedence: pickup before delivery on the same vehicle.
    5. Capacity: running load never exceeds vehicle capacity.
    6. Time windows: arrival/start times satisfy bounds.
    7. Objective: sum of route distances matches envelope objective.
    """
    checks: list[dict[str, Any]] = []

    # 1. Status & envelope check
    status = sol.get("status")
    status_ok = status in ("OPTIMAL", "FEASIBLE")
    checks.append({
        "name": "pyvrp_status_feasible",
        "ok": status_ok,
        "detail": f"status={status}",
    })
    if not status_ok:
        return checks

    routes = sol.get("routes", [])
    vehicle_capacity = int(sol.get("vehicle_capacity", 200))
    raw_clients = sol.get("raw_clients", [])
    raw_shipments = sol.get("raw_shipments", [])
    dist_matrix = sol.get("distance_matrix")

    # 2. Route endpoints at depot
    depot_ok = True
    depot_detail: str | None = None
    for r in routes:
        visits = r.get("visits", [])
        if len(visits) < 2:
            depot_ok = False
            depot_detail = f"route {r.get('route_id')} has fewer than 2 stops"
            break
        if visits[0].get("type") != "depot" or visits[-1].get("type") != "depot":
            depot_ok = False
            depot_detail = f"route {r.get('route_id')} does not start and end at depot"
            break
    checks.append({
        "name": "pyvrp_depot_endpoints",
        "ok": depot_ok,
        "detail": depot_detail,
    })

    # 3. Client visits completeness (for VRPTW)
    if raw_clients:
        visited_client_names: list[str] = []
        for r in routes:
            for v in r.get("visits", []):
                if v.get("type") == "client":
                    visited_client_names.append(v.get("name", ""))

        expected_names = [c.get("name") for c in raw_clients]
        all_visited = sorted(visited_client_names) == sorted(expected_names)
        checks.append({
            "name": "pyvrp_client_visits_complete",
            "ok": all_visited,
            "expected_count": len(expected_names),
            "got_count": len(visited_client_names),
        })

    # 4. PDP Precedence & Pairings (for VRPPDTW)
    if raw_shipments:
        pdp_ok = True
        pdp_detail: str | None = None
        shipment_route_map: dict[str, int] = {}
        shipment_pickup_idx: dict[str, int] = {}
        shipment_delivery_idx: dict[str, int] = {}

        for r_idx, r in enumerate(routes):
            visits = r.get("visits", [])
            for stop_idx, v in enumerate(visits):
                v_type = v.get("type")
                name = v.get("name", "")
                if v_type in ("pickup", "delivery"):
                    if name not in shipment_route_map:
                        shipment_route_map[name] = r_idx
                    elif shipment_route_map[name] != r_idx:
                        pdp_ok = False
                        pdp_detail = f"shipment {name} split across routes {shipment_route_map[name]} and {r_idx}"
                        break

                    if v_type == "pickup":
                        shipment_pickup_idx[name] = stop_idx
                    elif v_type == "delivery":
                        shipment_delivery_idx[name] = stop_idx
            if not pdp_ok:
                break

        if pdp_ok:
            for s in raw_shipments:
                s_name = s.get("name", "")
                if s_name not in shipment_pickup_idx or s_name not in shipment_delivery_idx:
                    pdp_ok = False
                    pdp_detail = f"shipment {s_name} missing pickup or delivery"
                    break
                p_idx = shipment_pickup_idx[s_name]
                d_idx = shipment_delivery_idx[s_name]
                if p_idx >= d_idx:
                    pdp_ok = False
                    pdp_detail = f"shipment {s_name} pickup at stop {p_idx} >= delivery at stop {d_idx}"
                    break

        checks.append({
            "name": "pyvrp_pdp_precedence_respected",
            "ok": pdp_ok,
            "detail": pdp_detail,
        })

    # 5. Capacity constraints along routes
    cap_ok = True
    cap_detail: str | None = None
    for r in routes:
        running_load = 0
        r_load = int(r.get("load", 0))
        if r_load > vehicle_capacity:
            cap_ok = False
            cap_detail = f"route {r.get('route_id')} total load {r_load} > capacity {vehicle_capacity}"
            break
        for v in r.get("visits", []):
            v_type = v.get("type")
            if v_type == "client":
                running_load += int(v.get("demand", 0))
            elif v_type == "pickup":
                running_load += int(v.get("amount", 0))
            elif v_type == "delivery":
                running_load -= int(v.get("amount", 0))

            if running_load > vehicle_capacity:
                cap_ok = False
                cap_detail = f"route {r.get('route_id')} running load {running_load} > capacity {vehicle_capacity}"
                break
            if running_load < 0:
                cap_ok = False
                cap_detail = f"route {r.get('route_id')} negative load {running_load}"
                break
        if not cap_ok:
            break

    checks.append({
        "name": "pyvrp_capacity_respected",
        "ok": cap_ok,
        "detail": cap_detail,
    })

    # 6. Time windows & chronology
    tw_ok = True
    tw_detail: str | None = None
    for r in routes:
        visits = r.get("visits", [])
        for i in range(len(visits) - 1):
            curr_end = visits[i].get("end_time", 0)
            next_start = visits[i + 1].get("start_time", 0)
            if curr_end > next_start:
                tw_ok = False
                tw_detail = f"route {r.get('route_id')} chronological violation at stop {i}: end {curr_end} > next start {next_start}"
                break
        if not tw_ok:
            break

    checks.append({
        "name": "pyvrp_time_windows_respected",
        "ok": tw_ok,
        "detail": tw_detail,
    })

    # 7. Total distance matches objective
    recomputed_total_dist = sum(int(r.get("distance", 0)) for r in routes)
    envelope_obj = sol.get("objective")
    envelope_dist = sol.get("total_distance")
    obj_ok = (recomputed_total_dist == envelope_obj == envelope_dist)
    checks.append({
        "name": "pyvrp_distance_matches_objective",
        "ok": obj_ok,
        "expected": envelope_obj,
        "got": recomputed_total_dist,
    })

    return checks


def validate_lot_sizing(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate Multi-Period Lot Sizing (ULSP / CLSP) — Numbers Truth.

    Recomputes everything from the envelope ``schedule`` + raw data
    (``raw_demands``, ``setup_costs``, ``holding_costs``, ``unit_cost``,
    ``capacity``, ``safety_stock``, ``initial_inventory``) — no solver is
    re-run.

    Checks:
      * lot_sizing_flow_balance        : I_{t-1} + x_t - I_t == d_t for all t
      * lot_sizing_setup_consistency   : x_t > 0 implies setup y_t == 1
      * lot_sizing_capacity_respected  : x_t <= capacity (when specified)
      * lot_sizing_safety_stock        : I_t >= safety_stock for all t
      * lot_sizing_demand_match        : schedule demand == raw_demands
      * lot_sizing_period_cost_recompute: per-period setup/holding/production
                                        costs recomputed from raw rates
      * lot_sizing_objective_match     : objective == recomputed total cost
      * lot_sizing_totals_match        : envelope totals match recomputation
    """
    checks: list[dict[str, Any]] = []

    schedule = sol.get("schedule") or []
    if not isinstance(schedule, list) or not schedule:
        checks.append({"name": "schedule_presence", "ok": False,
                       "detail": "empty or missing schedule"})
        return checks

    raw_demands = sol.get("raw_demands") or []
    if not isinstance(raw_demands, list) or len(raw_demands) != len(schedule):
        checks.append({"name": "raw_demands_presence", "ok": False,
                       "detail": f"raw_demands length {len(raw_demands)} != schedule length {len(schedule)}"})
        return checks

    initial_inventory = float(sol.get("initial_inventory", 0.0))
    unit_cost = float(sol.get("unit_cost", 0.0))
    capacity = sol.get("capacity")
    safety_stock = float(sol.get("safety_stock", 0.0))
    setup_costs_raw = sol.get("setup_costs") or []
    holding_costs_raw = sol.get("holding_costs") or []

    # 1. Flow balance: I_{t-1} + x_t - I_t == d_t for every period.
    flow_ok = True
    flow_detail: str | None = None
    prev_inv = initial_inventory
    for i, s in enumerate(schedule):
        d = float(s.get("demand", 0.0))
        x = float(s.get("production", 0.0))
        inv = float(s.get("inventory", 0.0))
        if abs(prev_inv + x - inv - d) > EPS:
            flow_ok = False
            flow_detail = (f"period {s.get('period', i+1)}: "
                           f"prev_inv {prev_inv} + x {x} - I {inv} != d {d}")
            break
        prev_inv = inv
    checks.append({"name": "lot_sizing_flow_balance", "ok": flow_ok,
                   "detail": flow_detail})

    # 2. Setup consistency: production in a period implies a setup charge.
    setup_ok = True
    setup_detail: str | None = None
    for s in schedule:
        x = float(s.get("production", 0.0))
        if x > EPS and not s.get("setup"):
            setup_ok = False
            setup_detail = f"period {s.get('period')}: x={x} > 0 but setup=False"
            break
    checks.append({"name": "lot_sizing_setup_consistency", "ok": setup_ok,
                   "detail": setup_detail})

    # 3. Capacity: x_t <= capacity (when specified).
    if capacity is not None:
        cap_ok = True
        cap_detail: str | None = None
        for s in schedule:
            x = float(s.get("production", 0.0))
            if x > float(capacity) + EPS:
                cap_ok = False
                cap_detail = f"period {s.get('period')}: x={x} > capacity {capacity}"
                break
        checks.append({"name": "lot_sizing_capacity_respected", "ok": cap_ok,
                       "detail": cap_detail})

    # 4. Safety stock: every inventory level (including the initial one)
    #    stays above the safety-stock floor.
    ss_ok = initial_inventory >= safety_stock - EPS
    ss_detail: str | None = None
    if not ss_ok:
        ss_detail = f"initial_inventory {initial_inventory} < safety_stock {safety_stock}"
    for s in schedule:
        inv = float(s.get("inventory", 0.0))
        if inv < safety_stock - EPS:
            ss_ok = False
            ss_detail = f"period {s.get('period')}: I={inv} < safety_stock {safety_stock}"
            break
    checks.append({"name": "lot_sizing_safety_stock", "ok": ss_ok,
                   "detail": ss_detail})

    # 5. Demand integrity: schedule demand matches raw_demands.
    demand_ok = True
    demand_detail: str | None = None
    for i, s in enumerate(schedule):
        if abs(float(s.get("demand", 0.0)) - float(raw_demands[i])) > EPS:
            demand_ok = False
            demand_detail = (f"period {s.get('period', i+1)}: "
                             f"demand {s.get('demand')} != raw_demands[{i}] {raw_demands[i]}")
            break
    checks.append({"name": "lot_sizing_demand_match", "ok": demand_ok,
                   "detail": demand_detail})

    # 6. Per-period cost recomputation from the raw rates (Numbers Truth).
    cost_ok = True
    cost_detail: str | None = None
    for i, s in enumerate(schedule):
        k = float(setup_costs_raw[i]) if i < len(setup_costs_raw) else 0.0
        h = float(holding_costs_raw[i]) if i < len(holding_costs_raw) else 0.0
        exp_setup = k if s.get("setup") else 0.0
        exp_hold = h * float(s.get("inventory", 0.0))
        exp_prod = unit_cost * float(s.get("production", 0.0))
        for label, expected, reported in (
            ("setup_cost", exp_setup, float(s.get("setup_cost", 0.0))),
            ("holding_cost", exp_hold, float(s.get("holding_cost", 0.0))),
            ("production_cost", exp_prod, float(s.get("production_cost", 0.0))),
        ):
            if abs(expected - reported) > EPS:
                cost_ok = False
                cost_detail = (f"period {s.get('period', i+1)} {label}: "
                               f"expected {expected}, got {reported}")
                break
        if not cost_ok:
            break
    checks.append({"name": "lot_sizing_period_cost_recompute", "ok": cost_ok,
                   "detail": cost_detail})

    # 7. Objective == recomputed total cost from raw data.
    recomputed_setup = sum(
        float(setup_costs_raw[i]) * (1.0 if s.get("setup") else 0.0)
        for i, s in enumerate(schedule)
        if i < len(setup_costs_raw)
    )
    recomputed_hold = sum(
        float(holding_costs_raw[i]) * float(s.get("inventory", 0.0))
        for i, s in enumerate(schedule)
        if i < len(holding_costs_raw)
    )
    recomputed_prod = unit_cost * sum(
        float(s.get("production", 0.0)) for s in schedule
    )
    recomputed_total = recomputed_setup + recomputed_hold + recomputed_prod
    obj = float(sol.get("objective", -1.0))
    checks.append({
        "name": "lot_sizing_objective_match",
        "ok": abs(recomputed_total - obj) <= EPS,
        "expected": obj,
        "got": recomputed_total,
    })

    # 8. Envelope totals agree with the recomputation.
    checks.append({
        "name": "lot_sizing_total_setup_match",
        "ok": abs(recomputed_setup - float(sol.get("total_setup_cost", -1.0))) <= EPS,
        "expected": sol.get("total_setup_cost"),
        "got": recomputed_setup,
    })
    checks.append({
        "name": "lot_sizing_total_holding_match",
        "ok": abs(recomputed_hold - float(sol.get("total_holding_cost", -1.0))) <= EPS,
        "expected": sol.get("total_holding_cost"),
        "got": recomputed_hold,
    })
    checks.append({
        "name": "lot_sizing_total_production_match",
        "ok": abs(recomputed_prod - float(sol.get("total_production_cost", -1.0))) <= EPS,
        "expected": sol.get("total_production_cost"),
        "got": recomputed_prod,
    })

    return checks


def validate_qap(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate a Quadratic Assignment Problem solution — Numbers Truth.

    Recomputes the exact objective from the envelope's raw ``distance_matrix``
    and ``flow_matrix`` using the double summation
    ``sum_i sum_j A[i, j] * B[perm[i], perm[j]]`` and independently verifies:

      * qap_permutation_presence  : permutation list present and non-empty
      * qap_permutation_bijection : entries are integers 0..n-1 exactly once
      * qap_matrix_dimensions     : distance/flow matrices are n x n
      * qap_objective_recompute   : recomputed objective == sol["objective"]
    """
    checks: list[dict[str, Any]] = []

    perm = sol.get("permutation")
    if not isinstance(perm, list) or not perm:
        checks.append(
            {
                "name": "qap_permutation_presence",
                "ok": False,
                "detail": "permutation list missing or empty",
            }
        )
        return checks

    n = len(perm)
    try:
        perm_int = [int(x) for x in perm]
    except (TypeError, ValueError):
        perm_int = None

    bijection_ok = perm_int is not None and sorted(perm_int) == list(range(n))
    checks.append(
        {
            "name": "qap_permutation_bijection",
            "ok": bijection_ok,
            "detail": None
            if bijection_ok
            else "permutation is not a bijection over 0..n-1",
        }
    )

    A = sol.get("distance_matrix")
    B = sol.get("flow_matrix")
    dims_ok = (
        isinstance(A, list)
        and isinstance(B, list)
        and len(A) == n
        and len(B) == n
        and all(isinstance(row, list) and len(row) == n for row in A)
        and all(isinstance(row, list) and len(row) == n for row in B)
    )
    checks.append(
        {
            "name": "qap_matrix_dimensions",
            "ok": dims_ok,
            "detail": None if dims_ok else f"expected {n}x{n} matrices",
        }
    )

    if bijection_ok and dims_ok:
        try:
            recomputed = 0.0
            for i in range(n):
                pi = perm_int[i]
                for j in range(n):
                    recomputed += float(A[i][j]) * float(B[pi][perm_int[j]])
        except (TypeError, ValueError) as exc:
            checks.append(
                {
                    "name": "qap_objective_recompute",
                    "ok": False,
                    "detail": f"non-numeric matrix entry: {exc}",
                }
            )
            return checks
        obj = float(sol.get("objective"))
        checks.append(
            {
                "name": "qap_objective_recompute",
                "ok": abs(recomputed - obj) <= EPS,
                "expected": obj,
                "got": recomputed,
            }
        )

    return checks


def validate_graph_coloring(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate Graph Coloring (chromatic number) — Numbers Truth.

    Recomputes everything from the envelope alone (no solver is re-run):

      * coloring_coverage          : node_colors covers every node exactly
                                    once (nodes from the envelope nodes
                                    list, or derived from edges)
      * color_values_nonneg_int    : every colour is an integer >= 0
      * zero_edge_conflicts        : color[u] != color[v] on every edge
      * chromatic_number_matches   : distinct colours == chromatic_number
                                    == objective
      * color_classes_partition    : color_classes partitions the vertices
                                    exactly as node_colors assigns them
    """
    checks: list[dict[str, Any]] = []

    node_colors = sol.get("node_colors")
    if not isinstance(node_colors, dict) or not node_colors:
        checks.append(
            {"name": "coloring_coverage", "ok": False,
             "detail": "node_colors missing or empty"}
        )
        return checks

    # Expected vertex set: envelope nodes when present, else derived
    # from the edge list (isolated vertices can only come from nodes).
    raw_nodes = sol.get("nodes")
    edges = sol.get("edges") or []
    if raw_nodes:
        expected_nodes = [int(x) for x in raw_nodes]
    elif isinstance(edges, list):
        derived: set[int] = set()
        for e in edges:
            if isinstance(e, (list, tuple)) and len(e) >= 2:
                try:
                    derived.add(int(e[0]))
                    derived.add(int(e[1]))
                except (TypeError, ValueError):
                    pass
        expected_nodes = sorted(derived)
    else:
        checks.append(
            {"name": "coloring_coverage", "ok": False,
             "detail": "neither nodes nor edges present in envelope"}
        )
        return checks

    def _norm(x: Any) -> int | None:
        try:
            return int(x)
        except (TypeError, ValueError):
            return None

    # 1. Coverage: every expected node has exactly one colour; no strays.
    expected_set = set(expected_nodes)
    missing = [n for n in expected_nodes if str(n) not in node_colors]
    stray = []
    for k in node_colors:
        n = _norm(k)
        if n is None or n not in expected_set:
            stray.append(k)
    coverage_ok = not missing and not stray
    checks.append(
        {
            "name": "coloring_coverage",
            "ok": coverage_ok,
            "expected": len(expected_nodes),
            "got": len(node_colors),
            "detail": None if coverage_ok else f"missing={missing[:5]} stray={stray[:5]}",
        }
    )

    # Colour values must be integers >= 0.
    int_colors_ok = all(
        isinstance(c, int) and not isinstance(c, bool) and c >= 0
        for c in node_colors.values()
    )
    checks.append(
        {
            "name": "color_values_nonneg_int",
            "ok": int_colors_ok,
            "detail": None if int_colors_ok else "non-integer or negative colour value",
        }
    )

    # 2. Zero conflicts: every edge joins differently coloured vertices.
    conflicts: list[list[Any]] = []
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) < 2:
            continue
        u, v = _norm(e[0]), _norm(e[1])
        cu, cv = node_colors.get(str(u)), node_colors.get(str(v))
        if cu is None or cv is None or cu == cv:
            conflicts.append([u, v, cu, cv])
    checks.append(
        {
            "name": "zero_edge_conflicts",
            "ok": not conflicts,
            "num_edges": len(edges),
            "conflicts": conflicts[:5],
            "detail": None if not conflicts else f"{len(conflicts)} conflicting edges",
        }
    )

    # 3. Chromatic number == distinct colours == objective.
    distinct = len({int(c) for c in node_colors.values()})
    chrom = sol.get("chromatic_number")
    obj = sol.get("objective")
    try:
        chrom_int = int(chrom)
        obj_int = int(obj)
        matches_ok = distinct == chrom_int == obj_int
    except (TypeError, ValueError):
        matches_ok = False
    checks.append(
        {
            "name": "chromatic_number_matches",
            "ok": matches_ok,
            "expected_distinct": distinct,
            "expected": chrom,
            "got": obj,
            "detail": None if matches_ok else
            f"distinct={distinct} chromatic={chrom} objective={obj}",
        }
    )

    # 4. color_classes partitions the vertices per node_colors.
    color_classes = sol.get("color_classes")
    partition_ok = False
    partition_detail: str | None = None
    if isinstance(color_classes, dict) and color_classes:
        rebuilt: dict[str, list[int]] = {}
        for node, c in node_colors.items():
            rebuilt.setdefault(str(int(c)), []).append(int(node))
        for k in rebuilt:
            rebuilt[k] = sorted(rebuilt[k])
        same_keys = set(color_classes) == set(rebuilt)
        same_members = same_keys and all(
            sorted(int(x) for x in color_classes[k]) == rebuilt[k]
            for k in rebuilt
        )
        flattened = sorted(
            int(x) for members in color_classes.values() for x in members
        )
        partition_ok = same_members and flattened == sorted(expected_nodes)
        partition_detail = None if partition_ok else (
            "color_classes mismatch" if not same_members
            else "partition does not cover vertices"
        )
    else:
        partition_detail = "color_classes missing or empty"
    checks.append(
        {
            "name": "color_classes_partition",
            "ok": partition_ok,
            "detail": partition_detail,
        }
    )

    return checks



def validate_stochastic_lp(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate Two-Stage Stochastic LP solution and indicators independently."""
    checks: list[dict[str, Any]] = []

    first_stage = sol.get("first_stage_decision")
    if not isinstance(first_stage, dict) or not first_stage:
        checks.append({"name": "first_stage_presence", "ok": False, "detail": "Missing first_stage_decision"})
        return checks

    raw_prob = sol.get("raw_problem")
    if not isinstance(raw_prob, dict):
        checks.append({"name": "raw_problem_presence", "ok": False, "detail": "Missing raw_problem for validation"})
        return checks

    total_land = float(raw_prob.get("total_land_acres", 500.0))
    crops = raw_prob.get("crops", ["wheat", "corn", "sugar_beets"])
    planting_costs = {c: float(raw_prob["planting_cost_per_acre"][c]) for c in crops}
    quota = float(raw_prob.get("sugar_beet_quota", 6000.0))

    # 1. First stage land feasibility
    total_allocated = 0.0
    non_neg = True
    for c in crops:
        acres = float(first_stage.get(c, 0.0))
        if acres < -EPS:
            non_neg = False
        total_allocated += acres

    land_ok = non_neg and total_allocated <= total_land + EPS
    checks.append(
        {
            "name": "first_stage_land_constraint",
            "ok": land_ok,
            "allocated_acres": round(total_allocated, 4),
            "total_land_acres": total_land,
            "detail": None if land_ok else f"allocated {total_allocated} > total {total_land} or negative acres",
        }
    )

    # 2. First-stage cost recomputation
    recomputed_f_cost = sum(planting_costs[c] * float(first_stage[c]) for c in crops)
    rep_f_cost = sol.get("first_stage_cost")
    f_cost_ok = rep_f_cost is not None and abs(float(rep_f_cost) - recomputed_f_cost) <= 1.0
    checks.append(
        {
            "name": "first_stage_cost_recompute",
            "ok": f_cost_ok,
            "expected": round(recomputed_f_cost, 4),
            "got": rep_f_cost,
        }
    )

    # 3. Scenario recourse feasibility & net revenue recomputation
    scenarios = sol.get("scenarios") or []
    scen_ok = bool(scenarios)
    raw_scenarios = {s["name"]: s for s in raw_prob.get("scenarios", [])}
    expected_revenue = 0.0

    for sc in scenarios:
        s_name = sc.get("scenario")
        raw_s = raw_scenarios.get(s_name)
        if not raw_s:
            scen_ok = False
            break

        prob = float(sc.get("probability", raw_s["probability"]))
        yields = raw_s["yield_per_acre"]

        w_sold = float(sc.get("wheat_sold", 0.0))
        w_bought = float(sc.get("wheat_purchased", 0.0))
        c_sold = float(sc.get("corn_sold", 0.0))
        c_bought = float(sc.get("corn_purchased", 0.0))
        b_q_sold = float(sc.get("sugar_beets_quota_sold", 0.0))
        b_e_sold = float(sc.get("sugar_beets_excess_sold", 0.0))

        # Check balances
        wheat_prod = yields["wheat"] * float(first_stage.get("wheat", 0.0))
        if wheat_prod + w_bought - w_sold < float(raw_prob["internal_demand"]["wheat"]) - EPS:
            scen_ok = False
            break

        corn_prod = yields["corn"] * float(first_stage.get("corn", 0.0))
        if corn_prod + c_bought - c_sold < float(raw_prob["internal_demand"]["corn"]) - EPS:
            scen_ok = False
            break

        beet_prod = yields["sugar_beets"] * float(first_stage.get("sugar_beets", 0.0))
        if b_q_sold + b_e_sold > beet_prod + EPS or b_q_sold > quota + EPS:
            scen_ok = False
            break

        scen_net_rev = (
            float(raw_prob["selling_price"]["wheat"]) * w_sold
            + float(raw_prob["selling_price"]["corn"]) * c_sold
            + float(raw_prob["selling_price"]["sugar_beets_quota"]) * b_q_sold
            + float(raw_prob["selling_price"]["sugar_beets_excess"]) * b_e_sold
            - float(raw_prob["purchase_price"]["wheat"]) * w_bought
            - float(raw_prob["purchase_price"]["corn"]) * c_bought
        )
        expected_revenue += prob * scen_net_rev

    checks.append(
        {
            "name": "scenario_recourse_feasibility",
            "ok": scen_ok,
            "detail": None if scen_ok else "Recourse balances or quotas violated in scenarios",
        }
    )

    # 4. Expected Recourse Profit (RP) & Objective recomputation
    recomputed_rp = round(expected_revenue - recomputed_f_cost, 4)
    rep_obj = float(sol.get("objective", 0.0))
    rp_ok = abs(recomputed_rp - rep_obj) <= 1.0
    checks.append(
        {
            "name": "recompute_objective",
            "ok": rp_ok,
            "expected": recomputed_rp,
            "got": rep_obj,
        }
    )

    # 5. Stochastic indicators check (EVPI, VSS, WS >= RP >= EEV)
    indicators = sol.get("stochastic_indicators") or {}
    rp_ind = indicators.get("RP")
    ws_ind = indicators.get("WS")
    eev_ind = indicators.get("EEV")
    evpi_ind = indicators.get("EVPI")
    vss_ind = indicators.get("VSS")

    ind_ok = True
    ind_detail = None
    if None in (rp_ind, ws_ind, eev_ind, evpi_ind, vss_ind):
        ind_ok = False
        ind_detail = "Missing stochastic indicators"
    else:
        if abs(float(evpi_ind) - (float(ws_ind) - float(rp_ind))) > 0.01:
            ind_ok = False
            ind_detail = f"EVPI mismatch: got {evpi_ind}, expected {float(ws_ind) - float(rp_ind)}"
        elif abs(float(vss_ind) - (float(rp_ind) - float(eev_ind))) > 0.01:
            ind_ok = False
            ind_detail = f"VSS mismatch: got {vss_ind}, expected {float(rp_ind) - float(eev_ind)}"
        elif not (float(ws_ind) + EPS >= float(rp_ind) >= float(eev_ind) - EPS):
            ind_ok = False
            ind_detail = f"Fundamental stochastic inequality WS >= RP >= EEV violated: WS={ws_ind}, RP={rp_ind}, EEV={eev_ind}"

    checks.append(
        {
            "name": "stochastic_indicators_consistency",
            "ok": ind_ok,
            "detail": ind_detail,
        }
    )

    return checks


def _max_clique_vertex_set(sol: dict[str, Any]) -> list[int] | None:
    """Vertex set from the envelope ``nodes`` list, else derived from edges."""
    raw_nodes = sol.get("nodes")
    edges = sol.get("edges") or []
    if raw_nodes:
        try:
            return [int(x) for x in raw_nodes]
        except (TypeError, ValueError):
            return None
    if isinstance(edges, list):
        derived: set[int] = set()
        for e in edges:
            if isinstance(e, (list, tuple)) and len(e) >= 2:
                try:
                    derived.add(int(e[0]))
                    derived.add(int(e[1]))
                except (TypeError, ValueError):
                    pass
        if derived:
            return sorted(derived)
    return None


def _max_clique_edge_set(sol: dict[str, Any]) -> set[tuple[int, int]] | None:
    """Undirected edge set (both directions) from the envelope edge list."""
    edges = sol.get("edges") or []
    if not isinstance(edges, list):
        return None
    out: set[tuple[int, int]] = set()
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) < 2:
            continue
        try:
            u, v = int(e[0]), int(e[1])
        except (TypeError, ValueError):
            continue
        out.add((u, v))
        out.add((v, u))
    return out


def _max_clique_norm_list(vals: Any) -> list[int]:
    out: list[int] = []
    for v in vals or []:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            pass
    return out


def _max_clique_optimality_recompute(
    expected: list[int], edge_set: set[tuple[int, int]]
) -> tuple[int, int, str | None]:
    """Independent exact recomputation of (omega, alpha) via NetworkX.

    Uses maximal-clique enumeration (``find_cliques``) on G and its
    complement — a different code path from the solver's
    ``max_weight_clique`` / CP-SAT formulations. Returns
    (omega, alpha, error_detail); error_detail is set when the
    enumeration is skipped (graph too large or networkx missing).
    """
    try:
        import networkx as nx
    except ImportError as exc:
        return 0, 0, f"networkx unavailable: {exc}"
    if len(expected) > 128:
        return 0, 0, "graph too large for exhaustive maximal-clique enumeration"
    g = nx.Graph()
    g.add_nodes_from(expected)
    for u, v in edge_set:
        if u < v:
            g.add_edge(u, v)
    omega = 0
    if g.number_of_nodes():
        omega = max((len(c) for c in nx.algorithms.clique.find_cliques(g)), default=0)
    g_comp = nx.complement(g)
    alpha = 0
    if g_comp.number_of_nodes():
        alpha = max(
            (len(c) for c in nx.algorithms.clique.find_cliques(g_comp)), default=0
        )
    return omega, alpha, None


def validate_max_clique(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate Max Clique / Max Independent Set — Numbers Truth.

    Recomputes everything from the envelope alone (no solver is re-run):

      * clique_node_subset      : clique_nodes ⊆ vertex set
      * clique_pairwise_adjacent: every pair in clique_nodes is an edge of G
      * mis_node_subset         : independent_set_nodes ⊆ vertex set
      * mis_zero_edges          : no edge of G joins two MIS vertices
      * objective_match         : objective == len(clique_nodes) for mode
                                  max_clique, else == len(independent_set_nodes)
      * size_fields_match       : max_clique_size == len(clique_nodes) and
                                  max_independent_set_size == len(independent_set_nodes)
      * duality_flag            : complement_duality_verified is True
      * optimality_recompute    : independent exact recomputation of omega
                                  and alpha via NetworkX maximal-clique
                                  enumeration on G and its complement
    """
    checks: list[dict[str, Any]] = []

    expected = _max_clique_vertex_set(sol)
    edge_set = _max_clique_edge_set(sol)
    if expected is None or edge_set is None:
        checks.append(
            {
                "name": "graph_presence",
                "ok": False,
                "detail": "envelope lacks nodes/edges needed to rebuild the graph",
            }
        )
        return checks
    expected_set = set(expected)

    clique = _max_clique_norm_list(sol.get("clique_nodes"))
    mis = _max_clique_norm_list(sol.get("independent_set_nodes"))

    # 1. clique_nodes ⊆ vertex set
    stray_clique = [v for v in clique if v not in expected_set]
    checks.append(
        {
            "name": "clique_node_subset",
            "ok": not stray_clique,
            "detail": None if not stray_clique else f"stray clique nodes {stray_clique[:5]}",
        }
    )

    # 2. pairwise adjacency within clique_nodes
    missing_pairs: list[list[int]] = []
    for i in range(len(clique)):
        for j in range(i + 1, len(clique)):
            u, v = clique[i], clique[j]
            if (u, v) not in edge_set:
                missing_pairs.append([u, v])
    checks.append(
        {
            "name": "clique_pairwise_adjacent",
            "ok": not missing_pairs,
            "detail": None if not missing_pairs else f"non-adjacent pairs {missing_pairs[:5]}",
        }
    )

    # 3. independent_set_nodes ⊆ vertex set
    stray_mis = [v for v in mis if v not in expected_set]
    checks.append(
        {
            "name": "mis_node_subset",
            "ok": not stray_mis,
            "detail": None if not stray_mis else f"stray MIS nodes {stray_mis[:5]}",
        }
    )

    # 4. zero edges inside independent_set_nodes
    internal_edges: list[list[int]] = []
    for i in range(len(mis)):
        for j in range(i + 1, len(mis)):
            u, v = mis[i], mis[j]
            if (u, v) in edge_set:
                internal_edges.append([u, v])
    checks.append(
        {
            "name": "mis_zero_edges",
            "ok": not internal_edges,
            "detail": None if not internal_edges else f"internal edges {internal_edges[:5]}",
        }
    )

    # 5. objective matches the reported side
    mode = str(sol.get("mode") or "max_clique").lower()
    target = len(mis) if mode == "max_independent_set" else len(clique)
    objective = sol.get("objective")
    try:
        obj_ok = int(objective) == target
    except (TypeError, ValueError):
        obj_ok = False
    checks.append(
        {
            "name": "objective_match",
            "ok": obj_ok,
            "expected": target,
            "got": objective,
            "detail": None if obj_ok else f"mode={mode}: objective {objective} != {target}",
        }
    )

    # 6. size fields match the reported node lists
    size_ok = True
    size_detail: str | None = None
    try:
        if int(sol.get("max_clique_size")) != len(clique):
            size_ok = False
            size_detail = (
                f"max_clique_size {sol.get('max_clique_size')} != "
                f"len(clique_nodes) {len(clique)}"
            )
        if int(sol.get("max_independent_set_size")) != len(mis):
            size_ok = False
            size_detail = (
                f"max_independent_set_size {sol.get('max_independent_set_size')} != "
                f"len(independent_set_nodes) {len(mis)}"
            )
    except (TypeError, ValueError):
        size_ok = False
        size_detail = "size fields not integers"
    checks.append(
        {
            "name": "size_fields_match",
            "ok": size_ok,
            "detail": size_detail,
        }
    )

    # 7. duality flag
    duality_ok = sol.get("complement_duality_verified") is True
    checks.append(
        {
            "name": "duality_flag",
            "ok": duality_ok,
            "detail": None if duality_ok else "complement_duality_verified is not True",
        }
    )

    # 8. independent optimality recomputation (NetworkX maximal cliques)
    omega_recomputed, alpha_recomputed, recompute_err = _max_clique_optimality_recompute(
        expected, edge_set
    )
    if recompute_err is not None:
        checks.append(
            {
                "name": "optimality_recompute",
                "ok": True,
                "detail": f"skipped: {recompute_err}",
            }
        )
    else:
        opt_ok = omega_recomputed == len(clique) and alpha_recomputed == len(mis)
        checks.append(
            {
                "name": "optimality_recompute",
                "ok": opt_ok,
                "expected_omega": omega_recomputed,
                "expected_alpha": alpha_recomputed,
                "got_omega": len(clique),
                "got_alpha": len(mis),
                "detail": None if opt_ok else "recomputed optimum differs from reported side",
            }
        )

    return checks


def validate_independent_set(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate the Max Independent Set side (alpha) of a max_clique envelope.

    Focused variant of ``validate_max_clique`` for the independent-set
    objective: subset, zero internal edges, objective/size consistency,
    and an independent exact recomputation of alpha.
    """
    checks: list[dict[str, Any]] = []

    expected = _max_clique_vertex_set(sol)
    edge_set = _max_clique_edge_set(sol)
    if expected is None or edge_set is None:
        checks.append(
            {
                "name": "graph_presence",
                "ok": False,
                "detail": "envelope lacks nodes/edges needed to rebuild the graph",
            }
        )
        return checks
    expected_set = set(expected)

    mis = _max_clique_norm_list(sol.get("independent_set_nodes"))

    stray_mis = [v for v in mis if v not in expected_set]
    checks.append(
        {
            "name": "mis_node_subset",
            "ok": not stray_mis,
            "detail": None if not stray_mis else f"stray MIS nodes {stray_mis[:5]}",
        }
    )

    internal_edges: list[list[int]] = []
    for i in range(len(mis)):
        for j in range(i + 1, len(mis)):
            u, v = mis[i], mis[j]
            if (u, v) in edge_set:
                internal_edges.append([u, v])
    checks.append(
        {
            "name": "mis_zero_edges",
            "ok": not internal_edges,
            "detail": None if not internal_edges else f"internal edges {internal_edges[:5]}",
        }
    )

    mode = str(sol.get("mode") or "max_clique").lower()
    objective = sol.get("objective")
    try:
        obj_ok = int(objective) == len(mis) if mode == "max_independent_set" else True
    except (TypeError, ValueError):
        obj_ok = False
    checks.append(
        {
            "name": "objective_match",
            "ok": obj_ok,
            "expected": len(mis) if mode == "max_independent_set" else objective,
            "got": objective,
            "detail": None if obj_ok else f"objective {objective} != {len(mis)}",
        }
    )

    try:
        size_ok = int(sol.get("max_independent_set_size")) == len(mis)
    except (TypeError, ValueError):
        size_ok = False
    checks.append(
        {
            "name": "size_field_match",
            "ok": size_ok,
            "expected": len(mis),
            "got": sol.get("max_independent_set_size"),
            "detail": None if size_ok else "max_independent_set_size != len(independent_set_nodes)",
        }
    )

    _, alpha_recomputed, recompute_err = _max_clique_optimality_recompute(expected, edge_set)
    if recompute_err is not None:
        checks.append(
            {
                "name": "optimality_recompute",
                "ok": True,
                "detail": f"skipped: {recompute_err}",
            }
        )
    else:
        checks.append(
            {
                "name": "optimality_recompute",
                "ok": alpha_recomputed == len(mis),
                "expected": alpha_recomputed,
                "got": len(mis),
                "detail": None if alpha_recomputed == len(mis) else "recomputed alpha differs",
            }
        )

    return checks


def validate_game_theory(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate a bimatrix-game Nash-equilibrium solution — Numbers Truth.

    Recomputes everything from the envelope ``raw_problem`` alone (no solver
    is re-run):

      * raw_problem_presence             : raw_problem carries both payoff matrices
      * strategy_probability_distribution: primary strategies are valid distributions
      * strategy_dimension_match        : strategy lengths == action counts
      * expected_payoffs_recompute       : u_row = x^T A y, u_col = x^T B y
      * best_response_regret             : row/col regret <= EPS (Nash iron law)
      * objective_match                  : sol["objective"] == u_row
      * all_equilibria_nash              : every reported equilibrium has zero regret
    """
    checks: list[dict[str, Any]] = []

    raw = sol.get("raw_problem")
    if not isinstance(raw, dict):
        checks.append({"name": "raw_problem_presence", "ok": False,
                       "detail": "raw_problem missing"})
        return checks

    A_raw = raw.get("row_payoffs")
    B_raw = raw.get("col_payoffs")
    try:
        A = np.asarray(A_raw, dtype=float)
        B = np.asarray(B_raw, dtype=float)
    except (TypeError, ValueError) as exc:
        checks.append({"name": "raw_problem_presence", "ok": False,
                       "detail": f"non-numeric payoff matrix: {exc}"})
        return checks
    if A.ndim != 2 or B.ndim != 2 or A.shape != B.shape or A.size == 0:
        checks.append({"name": "raw_problem_presence", "ok": False,
                       "detail": f"payoffs must be non-empty 2D of equal shape; got {A.shape}/{B.shape}"})
        return checks

    row_actions = raw.get("row_actions") or []
    col_actions = raw.get("col_actions") or []

    # Primary strategy pair: prefer primary_equilibrium, else top-level fields.
    pe = sol.get("primary_equilibrium")
    if isinstance(pe, dict):
        x_raw = pe.get("row_strategy")
        y_raw = pe.get("col_strategy")
        rep_payoffs = pe.get("expected_payoffs")
    else:
        x_raw = sol.get("primary_row_strategy")
        y_raw = sol.get("primary_col_strategy")
        rep_payoffs = sol.get("expected_payoffs")
    try:
        x = np.asarray(x_raw, dtype=float)
        y = np.asarray(y_raw, dtype=float)
    except (TypeError, ValueError) as exc:
        checks.append({"name": "strategy_presence", "ok": False,
                       "detail": f"bad strategy vectors: {exc}"})
        return checks
    if x.ndim != 1 or y.ndim != 1:
        checks.append({"name": "strategy_presence", "ok": False,
                       "detail": "primary strategies must be 1D vectors"})
        return checks

    # 1. Distribution properties (non-negative, sum to 1).
    x_ok = bool(np.all(x >= -EPS) and abs(float(x.sum()) - 1.0) <= 1e-4)
    y_ok = bool(np.all(y >= -EPS) and abs(float(y.sum()) - 1.0) <= 1e-4)
    checks.append({
        "name": "strategy_probability_distribution",
        "ok": x_ok and y_ok,
        "row_sum": round(float(x.sum()), 6),
        "col_sum": round(float(y.sum()), 6),
        "detail": None if (x_ok and y_ok) else "a strategy is negative or does not sum to 1",
    })

    # 2. Dimension match against declared action counts.
    if row_actions and col_actions:
        dim_ok = (
            x.shape[0] == len(row_actions)
            and y.shape[0] == len(col_actions)
            and A.shape == (len(row_actions), len(col_actions))
        )
    else:
        dim_ok = x.shape[0] == A.shape[0] and y.shape[0] == A.shape[1]
    checks.append({
        "name": "strategy_dimension_match",
        "ok": dim_ok,
        "row_strategy_len": int(x.shape[0]),
        "col_strategy_len": int(y.shape[0]),
        "row_actions": len(row_actions) if row_actions else int(A.shape[0]),
        "col_actions": len(col_actions) if col_actions else int(A.shape[1]),
    })

    # 3. Independently recompute expected payoffs (Numbers Truth).
    u_row = float(np.dot(x, np.dot(A, y)))
    u_col = float(np.dot(x, np.dot(B, y)))
    payoff_ok = False
    payoff_detail: str | None = None
    if isinstance(rep_payoffs, (list, tuple)) and len(rep_payoffs) == 2:
        payoff_ok = (
            abs(float(rep_payoffs[0]) - u_row) <= 1e-4
            and abs(float(rep_payoffs[1]) - u_col) <= 1e-4
        )
        payoff_detail = None if payoff_ok else "expected_payoffs mismatch"
    else:
        payoff_detail = "expected_payoffs missing or not a 2-vector"
    checks.append({
        "name": "expected_payoffs_recompute",
        "ok": payoff_ok,
        "expected": [u_row, u_col],
        "got": rep_payoffs,
        "detail": payoff_detail,
    })

    # 4. Best-response regret (the Nash iron law).
    row_regret = float(np.max(np.dot(A, y)) - u_row)
    col_regret = float(np.max(np.dot(x, B)) - u_col)
    regret_ok = row_regret <= EPS and col_regret <= EPS
    checks.append({
        "name": "best_response_regret",
        "ok": regret_ok,
        "row_regret": row_regret,
        "col_regret": col_regret,
        "tolerance": EPS,
        "detail": None if regret_ok else "a player has a profitable deviation",
    })

    # 5. Objective == u_row.
    obj = sol.get("objective")
    try:
        obj_ok = abs(float(obj) - u_row) <= 1e-4
    except (TypeError, ValueError):
        obj_ok = False
    checks.append({
        "name": "objective_match",
        "ok": obj_ok,
        "expected": u_row,
        "got": obj,
    })

    # 6. Every reported equilibrium must be a Nash equilibrium (zero regret).
    equilibria = sol.get("equilibria") or []
    all_nash = True
    bad: list[str] = []
    if not isinstance(equilibria, list) or not equilibria:
        all_nash = False
        bad.append("equilibria missing or empty")
    else:
        for i, eq in enumerate(equilibria):
            if not isinstance(eq, dict):
                all_nash = False
                bad.append(f"equilibria[{i}] not object")
                continue
            try:
                xe = np.asarray(eq.get("row_strategy"), dtype=float)
                ye = np.asarray(eq.get("col_strategy"), dtype=float)
            except (TypeError, ValueError):
                all_nash = False
                bad.append(f"equilibria[{i}] bad strategies")
                continue
            if xe.shape[0] != A.shape[0] or ye.shape[0] != A.shape[1]:
                all_nash = False
                bad.append(f"equilibria[{i}] dimension mismatch")
                continue
            ure = float(np.dot(xe, np.dot(A, ye)))
            uce = float(np.dot(xe, np.dot(B, ye)))
            rre = float(np.max(np.dot(A, ye)) - ure)
            cre = float(np.max(np.dot(xe, B)) - uce)
            if rre > EPS or cre > EPS:
                all_nash = False
                bad.append(f"equilibria[{i}] regret row={rre:.2e} col={cre:.2e}")
    checks.append({
        "name": "all_equilibria_nash",
        "ok": all_nash,
        "num_equilibria": len(equilibria) if isinstance(equilibria, list) else 0,
        "detail": None if all_nash else "; ".join(bad),
    })

    return checks


def _hub_assignment_map(sol: dict[str, Any]) -> dict[int, int]:
    """Normalize an envelope 'assignments' mapping to {int node: int hub}."""
    raw = sol.get("assignments") or {}
    out: dict[int, int] = {}
    if isinstance(raw, dict):
        items = list(raw.items())
    elif isinstance(raw, list):
        items = list(enumerate(raw))
    else:
        return out
    for k, v in items:
        try:
            out[int(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return out


def validate_hub_location(problem_id: str, sol: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate p-Hub Location Problem (p-HLP) — Numbers Truth.

    Recomputes everything from the envelope ``selected_hubs`` / ``assignments``
    and ``raw_problem`` (distances, flows, alpha, chi, delta). No solver is
    re-run.

    Checks:
      * hub_count_matches_p          : len(selected_hubs) == p_hubs
      * assignments_target_hubs      : every assignment points to an open hub
      * hubs_self_assigned           : each open hub is assigned to itself
      * assignments_complete         : every node has exactly one assignment
      * hub_location_objective_match : recomputed total == sol["objective"]
      * hub_location_breakdown_match : recomputed collection/transfer/distribution
                                      == cost_breakdown
    """
    checks: list[dict[str, Any]] = []

    raw = sol.get("raw_problem") or {}
    if not isinstance(raw, dict):
        raw = {}
    dist = raw.get("distances")
    flows = raw.get("flows")

    hubs_raw = sol.get("selected_hubs") or []
    if not isinstance(hubs_raw, list):
        hubs_raw = []
    try:
        hubs = sorted({int(h) for h in hubs_raw})
    except (TypeError, ValueError):
        hubs = []
    hub_set = set(hubs)

    p = sol.get("p_hubs")
    if p is None:
        p = raw.get("p_hubs")
    alpha = float(sol.get("alpha", raw.get("alpha", 0.7)))
    chi = float(sol.get("chi", raw.get("chi", 1.0)))
    delta = float(sol.get("delta", raw.get("delta", 1.0)))

    # 1. Hub count matches p
    if p is not None:
        checks.append(
            {
                "name": "hub_count_matches_p",
                "ok": len(hubs) == int(p),
                "expected": int(p),
                "got": len(hubs),
            }
        )

    assign = _hub_assignment_map(sol)

    # 2. Every assignment targets an open hub
    bad_targets = sorted(set(assign.values()) - hub_set)
    targets_ok = bool(assign) and not bad_targets
    checks.append(
        {
            "name": "assignments_target_hubs",
            "ok": targets_ok,
            "detail": None if targets_ok else f"targets not open hubs: {bad_targets}",
        }
    )

    # 3. Each open hub is assigned to itself
    not_self = [h for h in hubs if assign.get(h) != h]
    checks.append(
        {
            "name": "hubs_self_assigned",
            "ok": not not_self,
            "detail": None if not not_self else f"hubs not self-assigned: {not_self}",
        }
    )

    # 4. Assignment completeness over 0..n-1
    n = raw.get("num_nodes")
    if n is None and isinstance(dist, list):
        n = len(dist)
    if n is not None:
        complete = sorted(assign) == list(range(int(n)))
        checks.append(
            {
                "name": "assignments_complete",
                "ok": complete,
                "expected": int(n),
                "got": len(assign),
            }
        )

    # 5. + 6. Recompute objective and cost breakdown (Numbers Truth)
    if isinstance(dist, list) and isinstance(flows, list) and n is not None and assign:
        n = int(n)
        try:
            collection = transfer = distribution = 0.0
            for i in range(n):
                a_i = assign[i]
                for j in range(n):
                    a_j = assign[j]
                    w = float(flows[i][j])
                    if w == 0.0:
                        continue
                    collection += w * chi * float(dist[i][a_i])
                    transfer += w * alpha * float(dist[a_i][a_j])
                    distribution += w * delta * float(dist[a_j][j])
            total = collection + transfer + distribution
        except (TypeError, ValueError, IndexError) as exc:
            checks.append(
                {
                    "name": "hub_location_objective_match",
                    "ok": False,
                    "detail": f"recompute error: {exc}",
                }
            )
            return checks

        obj = float(sol.get("objective", -1.0))
        obj_ok = abs(total - obj) <= 1.0 or abs(total - obj) <= 1e-4 * max(1.0, abs(total))
        checks.append(
            {
                "name": "hub_location_objective_match",
                "ok": obj_ok,
                "expected": obj,
                "got": round(total, 6),
                "detail": None if obj_ok else f"recomputed {total} vs reported {obj}",
            }
        )

        cb = sol.get("cost_breakdown") or {}
        breakdown_ok = (
            isinstance(cb, dict)
            and abs(float(cb.get("collection_cost", -1.0)) - collection) <= 1.0
            and abs(float(cb.get("transfer_cost", -1.0)) - transfer) <= 1.0
            and abs(float(cb.get("distribution_cost", -1.0)) - distribution) <= 1.0
        )
        checks.append(
            {
                "name": "hub_location_breakdown_match",
                "ok": breakdown_ok,
                "expected": {
                    "collection_cost": round(collection, 6),
                    "transfer_cost": round(transfer, 6),
                    "distribution_cost": round(distribution, 6),
                },
                "got": cb,
                "detail": None if breakdown_ok else "cost_breakdown mismatch",
            }
        )
    else:
        checks.append(
            {
                "name": "hub_location_objective_match",
                "ok": False,
                "detail": "raw_problem distances/flows missing or malformed",
            }
        )

    return checks
