#!/usr/bin/env python3
"""Multi-Period Lot Sizing (ULSP / CLSP) Solver.

Two exact methods for the single-item dynamic lot-sizing problem:

* **``method='ww'`` — Wagner-Whitin dynamic programming.**  Exact O(T^2) DP
  for the uncapacitated lot-sizing problem (ULSP).  Supports per-period
  setup costs and per-period holding costs.  Requires zero initial
  inventory, zero safety stock, and no capacity (use ``method='mip'``
  otherwise).
* **``method='mip'`` — OR-Tools SCIP MIP.**  Capacitated lot sizing (CLSP)
  with per-period capacity, safety stock, initial inventory, unit
  production cost, and per-period setup/holding costs.  The uncapacitated
  case is handled with a big-M production/setup linking constraint.

Holding-cost convention (shared by both methods): period ``t`` is charged
``h_t * I_t`` where ``I_t`` is the *ending* inventory after period ``t``.

Default benchmark: classic 12-period Wagner-Whitin instance
``demands=[20, 50, 10, 50, 50, 10, 20, 40, 30, 30, 20, 40]``, ``K=85``,
``h=1`` → known optimal cost ``670.0`` (setup 4×85 = 340 + holding 330).

Output follows the OR-Path "Numbers Truth" envelope (ADR-0002):
  problem_id, problem_class="lot_sizing", mode="lot_sizing", status,
  objective, lower_bound, optimality_gap, solver, source, num_periods,
  production (per-period list), inventory (per-period ending stock),
  setup_actions (per-period 0/1), costs (setup/holding/production/total),
  metrics (objective/bounds/counts), total_setup_cost,
  total_holding_cost, total_production_cost, schedule (per-period dict with
  period, demand, production, inventory, setup, holding_cost, setup_cost),
  raw_demands, meta.  Objective values are recomputed from the delivered
  schedule; known optima are reported as reference only.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

DEFAULT_SOLVER = "ww-dp-exact"
MIP_SOLVER = "ortools-scip-mip"

# Classic 12-period Wagner-Whitin benchmark (known optimum = 670.0).
BENCHMARK_DEMANDS = [20.0, 50.0, 10.0, 50.0, 50.0, 10.0, 20.0, 40.0, 30.0, 30.0, 20.0, 40.0]

BENCHMARKS: dict[str, dict[str, Any]] = {
    "ww12": {
        "demands": list(BENCHMARK_DEMANDS),
        "setup_cost": 85.0,
        "holding_cost": 1.0,
        "unit_cost": 0.0,
        "known_optimum": 670.0,
    },
    "clsp60": {
        # Capacitated variant: same demands, per-period capacity 60.
        "demands": list(BENCHMARK_DEMANDS),
        "setup_cost": 85.0,
        "holding_cost": 1.0,
        "unit_cost": 0.0,
        "capacity": 60.0,
        "known_optimum": None,  # computed by solver; reference only
    },
}

_ROUND = 6


# ---------------------------------------------------------------------------
# Input coercion
# ---------------------------------------------------------------------------
def _coerce_cost_series(
    value: float | list[float] | None, length: int, default: float, name: str
) -> list[float]:
    """Normalize a scalar-or-list cost parameter to a per-period list."""
    if value is None:
        return [float(default)] * length
    if isinstance(value, (int, float)):
        return [float(value)] * length
    vals = [float(v) for v in value]
    if len(vals) != length:
        raise ValueError(f"{name}: got {len(vals)} values, expected {length}")
    return vals


def _validate_demands(demands: Any) -> list[float]:
    if not isinstance(demands, (list, tuple)) or not demands:
        raise ValueError("demands must be a non-empty list of per-period demands")
    out = [float(d) for d in demands]
    if any(d < 0 for d in out):
        raise ValueError("demands must be non-negative")
    return out


# ---------------------------------------------------------------------------
# Wagner-Whitin exact DP (ULSP)
# ---------------------------------------------------------------------------
def _solve_ww(
    demands: list[float],
    setup_costs: list[float],
    holding_costs: list[float],
) -> tuple[list[float], list[tuple[int, int]]]:
    """Exact Wagner-Whitin DP.

    Returns ``(production, batches)`` where ``production[t]`` is the amount
    produced in period ``t`` (0-based) and ``batches`` is the list of
    1-based ``(first_period, last_period)`` production batches in chronological
    order.
    """
    T = len(demands)
    pref_d = [0.0] * (T + 1)  # prefix sums of demands (1-based)
    pref_h = [0.0] * (T + 1)  # prefix sums of holding costs (1-based)
    for t in range(1, T + 1):
        pref_d[t] = pref_d[t - 1] + demands[t - 1]
        pref_h[t] = pref_h[t - 1] + holding_costs[t - 1]

    def holding(i: int, t: int) -> float:
        # Batch produced in period i covering demands i..t: the units consumed
        # in period k sit in inventory at the end of periods i..k-1 and are
        # charged at rates h_i..h_{k-1} → d_k * (pref_h[k] - pref_h[i]).
        return sum(
            demands[k - 1] * (pref_h[k] - pref_h[i]) for k in range(i + 1, t + 1)
        )

    F = [0.0] * (T + 1)
    parent = [0] * (T + 1)
    for t in range(1, T + 1):
        best, best_i = float("inf"), -1
        for i in range(1, t + 1):
            cost = F[i - 1] + setup_costs[i - 1] + holding(i, t)
            if cost < best:
                best, best_i = cost, i
        F[t], parent[t] = best, best_i

    batches: list[tuple[int, int]] = []
    t = T
    while t > 0:
        i = parent[t]
        batches.append((i, t))
        t = i - 1
    batches.reverse()

    production = [0.0] * T
    for i, t in batches:
        production[i - 1] = pref_d[t] - pref_d[i - 1]
    return production, batches


# ---------------------------------------------------------------------------
# SCIP MIP (CLSP / ULSP)
# ---------------------------------------------------------------------------
def _solve_mip(
    demands: list[float],
    setup_costs: list[float],
    holding_costs: list[float],
    unit_cost: float,
    capacity: float | None,
    safety_stock: float,
    initial_inventory: float,
    time_limit_s: float,
) -> tuple[list[float], list[bool], float, str]:
    """Solve CLSP (or ULSP via big-M) with OR-Tools SCIP.

    Returns ``(production, setup_flags, solver_objective, status)``.
    """
    from ortools.linear_solver import pywraplp

    T = len(demands)
    total_demand = sum(demands)
    big_m = initial_inventory + total_demand  # inventory can never exceed this

    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        raise RuntimeError("OR-Tools SCIP solver unavailable")
    if time_limit_s and time_limit_s > 0:
        solver.SetTimeLimit(int(time_limit_s * 1e3))  # SCIP expects milliseconds

    x = [solver.NumVar(0.0, big_m, f"x_{t}") for t in range(T)]
    y = [solver.BoolVar(f"y_{t}") for t in range(T)]
    I = [solver.NumVar(safety_stock, big_m, f"I_{t}") for t in range(T + 1)]

    solver.Add(I[0] == initial_inventory)
    for t in range(T):
        solver.Add(I[t] + x[t] - I[t + 1] == demands[t])
        # production/setup linking (capacity replaces big-M when given)
        cap = float(capacity) if capacity is not None else big_m
        solver.Add(x[t] <= cap * y[t])
    if safety_stock <= 0.0:
        # No point carrying inventory past the horizon.
        solver.Add(I[T] == 0.0)

    solver.Minimize(
        solver.Sum(
            setup_costs[t] * y[t] + holding_costs[t] * I[t + 1] + unit_cost * x[t]
            for t in range(T)
        )
    )

    status = solver.Solve()
    if status == solver.OPTIMAL:
        status_name = "OPTIMAL"
    elif status == solver.FEASIBLE:
        status_name = "FEASIBLE"
    else:
        status_name = "INFEASIBLE"
    if status_name not in ("OPTIMAL", "FEASIBLE"):
        return [], [], -1.0, None, "INFEASIBLE"
    production = [round(x[t].solution_value(), _ROUND) for t in range(T)]
    setup_flags = [bool(round(y[t].solution_value())) for t in range(T)]
    raw_objective = float(solver.Objective().Value())
    lower_bound = float(solver.Objective().BestBound())
    return production, setup_flags, raw_objective, lower_bound, status_name


# ---------------------------------------------------------------------------
# Schedule assembly (Numbers Truth: objective recomputed from the schedule)
# ---------------------------------------------------------------------------
def _build_schedule(
    demands: list[float],
    production: list[float],
    setup_flags: list[bool],
    setup_costs: list[float],
    holding_costs: list[float],
    unit_cost: float,
    initial_inventory: float,
) -> tuple[list[dict[str, Any]], float, float, float]:
    """Assemble per-period schedule rows and recompute all cost components."""
    schedule: list[dict[str, Any]] = []
    inv = float(initial_inventory)
    total_setup = 0.0
    total_holding = 0.0
    total_production_cost = 0.0
    for t in range(len(demands)):
        x = production[t]
        if abs(x) < 1e-9:
            x = 0.0
        inv_prev = inv
        inv = inv_prev + x - demands[t]
        if -1e-9 <= inv < 0.0:
            inv = 0.0
        holding = round(holding_costs[t] * inv, _ROUND)
        setup_cost = round(setup_costs[t], _ROUND) if setup_flags[t] else 0.0
        prod_cost = round(unit_cost * x, _ROUND)
        schedule.append(
            {
                "period": t + 1,
                "demand": demands[t],
                "production": x,
                "inventory": inv,
                "setup": setup_flags[t],
                "holding_cost": holding,
                "setup_cost": setup_cost,
                "production_cost": prod_cost,
            }
        )
        total_setup += setup_cost
        total_holding += holding
        total_production_cost += prod_cost
    objective = round(total_setup + total_holding + total_production_cost, _ROUND)
    return schedule, objective, total_setup, total_holding, total_production_cost


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def solve_lot_sizing(
    demands: list[float] | None = None,
    setup_cost: float | list[float] = 85.0,
    holding_cost: float | list[float] = 1.0,
    unit_cost: float = 0.0,
    capacity: float | None = None,
    safety_stock: float = 0.0,
    initial_inventory: float = 0.0,
    method: str = "ww",
    time_limit_s: float = 30.0,
    problem_id: str | None = None,
) -> dict[str, Any]:
    """Solve a multi-period lot-sizing problem (ULSP / CLSP).

    Parameters
    ----------
    demands
        Non-negative per-period demands.  Defaults to the 12-period
        Wagner-Whitin benchmark (known optimum 670.0).
    setup_cost, holding_cost
        Scalar (uniform across periods) or per-period lists.
    unit_cost
        Per-unit production cost (constant across periods).
    capacity
        Per-period production capacity; ``None`` = uncapacitated.
    safety_stock, initial_inventory
        Inventory bounds / starting stock.
    method
        ``"ww"`` (Wagner-Whitin DP; uncapacitated, zero initial stock and
        safety stock) or ``"mip"`` (OR-Tools SCIP; capacitated allowed).
    time_limit_s
        MIP wall-clock limit (ignored by the DP).
    problem_id
        Envelope problem id; auto-derived when omitted.
    """
    method = (method or "ww").lower().strip()
    if method not in ("ww", "mip"):
        raise ValueError(f"unknown method: {method!r} (expected 'ww' or 'mip')")

    raw_demands = _validate_demands(
        list(BENCHMARK_DEMANDS) if demands is None else demands
    )
    T = len(raw_demands)
    setup_costs = _coerce_cost_series(setup_cost, T, 85.0, "setup_cost")
    holding_costs = _coerce_cost_series(holding_cost, T, 1.0, "holding_cost")
    if unit_cost < 0:
        raise ValueError("unit_cost must be non-negative")
    if capacity is not None and capacity < 0:
        raise ValueError("capacity must be non-negative")
    if safety_stock < 0:
        raise ValueError("safety_stock must be non-negative")
    if initial_inventory < 0:
        raise ValueError("initial_inventory must be non-negative")

    if method == "ww":
        if capacity is not None:
            raise ValueError(
                "Wagner-Whitin DP requires no capacity; use method='mip'"
            )
        if safety_stock != 0.0:
            raise ValueError(
                "Wagner-Whitin DP requires zero safety stock; use method='mip'"
            )
        if initial_inventory != 0.0:
            raise ValueError(
                "Wagner-Whitin DP requires zero initial inventory; use method='mip'"
            )
        t0 = time.perf_counter()
        production, batches = _solve_ww(raw_demands, setup_costs, holding_costs)
        setup_flags = [p > 0.0 for p in production]
        solver_name = DEFAULT_SOLVER
        wall = time.perf_counter() - t0
        solver_objective = None
        status = "OPTIMAL"  # exact DP is always optimal
    else:
        t0 = time.perf_counter()
        production, setup_flags, solver_objective, mip_lower_bound, status = _solve_mip(
            raw_demands,
            setup_costs,
            holding_costs,
            unit_cost,
            capacity,
            safety_stock,
            initial_inventory,
            time_limit_s,
        )
        solver_name = MIP_SOLVER
        wall = time.perf_counter() - t0
        batches = []
        if status == "INFEASIBLE":
            envelope = {
                "problem_id": problem_id or "lot_sizing_infeasible",
                "problem_class": "lot_sizing",
                "mode": "lot_sizing",
                "status": "INFEASIBLE",
                "objective": -1.0,
                "lower_bound": None,
                "optimality_gap": None,
                "solver": solver_name,
                "source": "tools/solve_lot_sizing.py",
                "method": method,
                "num_periods": T,
                "raw_demands": raw_demands,
                "meta": {
                    "exact": True,
                    "proven_optimal": False,
                    "method_class": "exact",
                    "wall_time_s": round(wall, 4),
                },
            }
            return envelope

    schedule, objective, total_setup, total_holding, total_prod = _build_schedule(
        raw_demands,
        production,
        setup_flags,
        setup_costs,
        holding_costs,
        unit_cost,
        initial_inventory,
    )

    # Lower bound / optimality gap (Numbers Truth): the Wagner-Whitin DP is
    # exact, so the delivered objective IS the optimum (zero gap); the SCIP
    # MIP contributes its incumbent bound.
    if method == "ww":
        lower_bound: float | None = float(objective)
        optimality_gap: float | None = 0.0
    elif mip_lower_bound is not None:
        lower_bound = float(mip_lower_bound)
        optimality_gap = round(objective - lower_bound, _ROUND)
        if optimality_gap == 0.0:
            # Normalize -0.0 → +0.0 so the gap never serializes as "-0.0".
            optimality_gap = 0.0
    else:
        lower_bound = None
        optimality_gap = None

    if problem_id is None:
        problem_id = (
            "lot_sizing_ww12"
            if raw_demands == list(BENCHMARK_DEMANDS) and method == "ww"
            else "lot_sizing_custom"
        )

    production_series = [s["production"] for s in schedule]
    inventory_series = [s["inventory"] for s in schedule]
    setup_actions = [1 if s["setup"] else 0 for s in schedule]
    metrics: dict[str, Any] = {
        "objective": objective,
        "lower_bound": lower_bound,
        "optimality_gap": optimality_gap,
        "num_periods": T,
        "num_setups": sum(setup_actions),
        "total_production": round(sum(production_series), _ROUND),
        "total_demand": round(sum(raw_demands), _ROUND),
        "total_inventory": round(sum(inventory_series), _ROUND),
        "proven_optimal": status == "OPTIMAL",
        "wall_time_s": round(wall, 4),
    }
    costs = {
        "setup": total_setup,
        "holding": total_holding,
        "production": total_prod,
        "total": objective,
    }

    meta: dict[str, Any] = {
        "exact": True,
        "proven_optimal": status == "OPTIMAL",
        "method_class": "exact",
        "method": method,
        "wall_time_s": round(wall, 4),
        "capacity": capacity,
        "safety_stock": safety_stock,
        "initial_inventory": initial_inventory,
    }
    if solver_objective is not None:
        meta["solver_objective"] = round(solver_objective, _ROUND)
        meta["objective_drift"] = round(abs(solver_objective - objective), _ROUND)

    result: dict[str, Any] = {
        "problem_id": problem_id,
        "problem_class": "lot_sizing",
        "mode": "lot_sizing",
        "status": status,
        "objective": objective,
        "lower_bound": lower_bound,
        "optimality_gap": optimality_gap,
        "solver": solver_name,
        "source": "tools/solve_lot_sizing.py",
        "method": method,
        "num_periods": T,
        "total_setup_cost": total_setup,
        "total_holding_cost": total_holding,
        "total_production_cost": total_prod,
        "production": production_series,
        "inventory": inventory_series,
        "setup_actions": setup_actions,
        "costs": costs,
        "metrics": metrics,
        "unit_cost": unit_cost,
        "capacity": capacity,
        "safety_stock": safety_stock,
        "initial_inventory": initial_inventory,
        "raw_demands": raw_demands,
        "setup_costs": setup_costs,
        "holding_costs": holding_costs,
        "setup_periods": [s["period"] for s in schedule if s["setup"]],
        "schedule": schedule,
        "meta": meta,
    }
    if batches:
        result["production_batches"] = [[i, t] for i, t in batches]
    benchmark = BENCHMARKS.get("ww12")
    if benchmark and raw_demands == list(BENCHMARK_DEMANDS) and method == "ww":
        result["known_optimum"] = benchmark["known_optimum"]
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_series(raw: str | None) -> float | list[float] | None:
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) == 1:
        return float(parts[0])
    return [float(p) for p in parts]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OR-Path Multi-Period Lot Sizing Solver (WW-DP / SCIP-MIP)"
    )
    parser.add_argument(
        "--demands",
        default=None,
        help="Comma-separated per-period demands (default: 12-period WW benchmark)",
    )
    parser.add_argument(
        "--setup-cost",
        default="85.0",
        help="Setup cost K: float or per-period comma-separated list",
    )
    parser.add_argument(
        "--holding-cost",
        default="1.0",
        help="Holding cost h: float or per-period comma-separated list",
    )
    parser.add_argument("--unit-cost", type=float, default=0.0)
    parser.add_argument(
        "--capacity",
        default=None,
        help="Per-period production capacity (float); omit for uncapacitated",
    )
    parser.add_argument("--safety-stock", type=float, default=0.0)
    parser.add_argument("--initial-inventory", type=float, default=0.0)
    parser.add_argument(
        "--method",
        choices=["ww", "mip"],
        default="ww",
        help="'ww' = Wagner-Whitin DP (uncapacitated), 'mip' = SCIP CLSP/ULSP",
    )
    parser.add_argument(
        "--benchmark",
        default="ww12",
        choices=sorted(BENCHMARKS.keys()),
        help="Built-in benchmark preset (default: ww12)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write result JSON to this path",
    )
    args = parser.parse_args(argv)

    bench = BENCHMARKS[args.benchmark]
    demands = (
        _parse_series(args.demands)
        if args.demands is not None
        else list(bench["demands"])
    )
    if isinstance(demands, float):
        demands = [demands]
    setup_cost = _parse_series(args.setup_cost)
    if setup_cost is None:
        setup_cost = bench["setup_cost"]
    holding_cost = _parse_series(args.holding_cost)
    if holding_cost is None:
        holding_cost = bench["holding_cost"]
    capacity = (
        float(args.capacity)
        if args.capacity is not None
        else bench.get("capacity")
    )
    unit_cost = args.unit_cost if args.unit_cost is not None else bench.get("unit_cost", 0.0)

    sol = solve_lot_sizing(
        demands=demands,
        setup_cost=setup_cost,
        holding_cost=holding_cost,
        unit_cost=unit_cost,
        capacity=capacity,
        safety_stock=args.safety_stock,
        initial_inventory=args.initial_inventory,
        method=args.method,
        problem_id=f"lot_sizing_{args.benchmark}" if args.demands is None else None,
    )
    out = json.dumps(sol, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if sol.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
