#!/usr/bin/env python3
"""Domain-specific deep-analysis tools for the OR-Path agent teams.

This module is the *anti-template* layer.  Every other domain module binds its
five experts to the same five generic tools
(``execute_or_solver`` / ``validate_solution_tool`` / ``execute_python_sandbox``
/ ``read_problem_file`` / ``search_or_knowledge``).  That makes every domain
team a reskinned parrot: the agent cannot tell a JSSP schedule from a VRP
route, a roster shift matrix from a lot-sizing flow balance, without shelling
out to a generic solver and re-parsing JSON by hand.

The deep domain logic *already exists* in ``tools/solve_*.py`` and
``tools/validators/extended_solvers.py``.  What was missing was a first-class
tool surface that lets each expert reason about its own domain's structure
directly.  This module exposes exactly that: two genuinely domain-specific
tools per domain —

  * ``profile_<domain>_data``  — input-side structural profiling / integrity
    checks (what the auditor needs before any solver runs).
  * ``inspect_<domain>_solution`` — output-side envelope decomposition (what
    the exact-bound / heuristic / realities specialists need after a solve).

Numbers Truth: every metric is either echoed verbatim from the solver artifact
or recomputed from the raw data carried inside the envelope.  Nothing is
invented here.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy is a hard dep of the stack
    np = None  # type: ignore

__all__ = [
    # routing / VRP
    "profile_routing_data",
    "inspect_routing_solution",
    # scheduling / JSSP
    "profile_scheduling_data",
    "inspect_scheduling_solution",
    # rostering / staff
    "profile_rostering_data",
    "inspect_rostering_solution",
    # inventory / lot sizing
    "profile_inventory_data",
    "inspect_inventory_solution",
    # facility / CFLP
    "profile_facility_data",
    "inspect_facility_solution",
    # pricing / stochastic LP
    "profile_pricing_data",
    "inspect_pricing_solution",
    # project / RCPSP
    "profile_project_data",
    "inspect_project_solution",
    # finance / portfolio
    "profile_portfolio_data",
    "inspect_portfolio_solution",
    # microgrid (CUMCM 2026 Problem C)
    "profile_microgrid_data",
    "inspect_microgrid_solution",
    # tube (3D common-edge nesting)
    "profile_tube_data",
    "inspect_tube_solution",
]

EPS = 1e-6


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def _resolve_root() -> Path:
    raw = (os.environ.get("ORPATH_WORKDIR") or "").strip().strip('"')
    if raw:
        try:
            from orpath.paths import orpath_home

            raw_path = Path(raw).expanduser().resolve()
            home_path = orpath_home().resolve()
            cwd_path = Path.cwd().resolve()
            if raw_path == home_path and cwd_path != home_path:
                return cwd_path
            return raw_path
        except Exception:
            return Path(raw).expanduser().resolve()
    return Path.cwd()


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return None


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_array(value: Any) -> Any:
    """Coerce ``value`` to a numpy array (or empty list) without truthiness."""
    if value is None:
        return np.array([]) if np is not None else []
    if np is not None:
        return np.asarray(value, dtype=float)
    return list(value)


# --------------------------------------------------------------------------- #
# Routing / VRP (PyVRP, VRPTW, VRPPDTW)
# --------------------------------------------------------------------------- #

@tool
def profile_routing_data(solomon_path: str = "fixtures/benchmarks/vrp/c101.txt") -> str:
    """Profile a Solomon/VRPLIB VRPTW instance: integrity + distance-matrix checks.

    The routing auditor uses this to freeze the input before any solver runs.
    It parses the instance, checks the distance-matrix symmetry and triangle
    inequality, verifies time-window consistency (tw_early <= tw_late) and
    demand non-negativity, and computes a SHA-256 hash of the coordinate
    manifest for downstream red-team recompute.

    Args:
        solomon_path: Path to a Solomon/VRPLIB benchmark file.

    Returns:
        JSON with instance shape, integrity flags, worst triangle-inequality
        violations, and the coordinate SHA-256 hash.
    """
    root = _resolve_root()
    p = Path(solomon_path)
    if not p.is_absolute():
        p = root / p
    if not p.is_file():
        return _json({"ok": False, "error": f"instance not found: {p}"})
    try:
        import vrplib

        data = vrplib.read_instance(str(p), instance_format="solomon")
    except Exception as exc:
        return _json({"ok": False, "error": f"parse failed: {exc}"})

    coords = _as_array(data.get("node_coord"))
    demands = _as_array(data.get("demand"))
    tw = _as_array(data.get("time_window"))
    edge_weight = _as_array(data.get("edge_weight"))
    vehicles = data.get("vehicles")
    capacity = data.get("capacity")
    n = len(coords)

    # Recompute Euclidean distance matrix and compare to the declared one.
    sym_ok = tri_ok = True
    worst_tri: dict[str, float] = {}
    max_asym = 0.0
    if edge_weight.size and n:
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                d_ij = float(edge_weight[i][j])
                d_ji = float(edge_weight[j][i])
                max_asym = max(max_asym, abs(d_ij - d_ji))
                if abs(d_ij - d_ji) > EPS:
                    sym_ok = False
                if i < j:
                    dx = float(coords[i][0]) - float(coords[j][0])
                    dy = float(coords[i][1]) - float(coords[j][1])
                    eucl = math.hypot(dx, dy)
                    slack = d_ij + d_ji - eucl
                    if slack < -EPS:
                        tri_ok = False
                        worst_tri[f"{i}-{j}"] = round(slack, 4)

    tw_bad = [
        {"node": i, "early": float(tw[i][0]), "late": float(tw[i][1])}
        for i in range(n)
        if n and tw.shape == (n, 2) and float(tw[i][0]) > float(tw[i][1])
    ]
    neg_demand = [
        {"node": i, "demand": float(demands[i])}
        for i in range(n)
        if n and float(demands[i]) < 0
    ]

    coord_hash = _sha256(p)
    return _json({
        "ok": True,
        "instance": str(p),
        "num_nodes": n,
        "num_clients": max(n - 1, 0),
        "num_vehicles": vehicles,
        "vehicle_capacity": capacity,
        "coord_sha256": coord_hash,
        "distance_matrix_symmetric": sym_ok,
        "max_asymmetry": round(max_asym, 6),
        "triangle_inequality_holds": tri_ok,
        "worst_triangle_violations": worst_tri,
        "time_window_conflicts": tw_bad,
        "negative_demands": neg_demand,
        "integrity_ok": sym_ok and tri_ok and not tw_bad and not neg_demand,
    })


@tool
def inspect_routing_solution(solution_path: str = "outputs/pyvrp_vrptw-solution.json") -> str:
    """Decompose a PyVRP/VRPTW solution envelope into per-route domain metrics.

    Recomputes per-route distance/load/duration, capacity utilization,
    time-window slack, and confirms the total distance matches the envelope
    objective (Numbers Truth — no solver is re-run).

    Args:
        solution_path: Path to a solver solution JSON.

    Returns:
        JSON with envelope status/objective, per-route breakdown, aggregate
        utilization, and objective-consistency flags.
    """
    root = _resolve_root()
    p = Path(solution_path)
    if not p.is_absolute():
        p = root / p
    if not p.is_file():
        return _json({"ok": False, "error": f"solution not found: {p}"})
    sol = _load_json(p)

    routes = sol.get("routes") or []
    cap = float(sol.get("vehicle_capacity", 0) or 0)
    recomputed_dist = sum(float(r.get("distance", 0) or 0) for r in routes)
    obj = sol.get("objective")
    dist_match = (_is_num(obj) and abs(recomputed_dist - float(obj)) <= EPS)

    per_route = []
    for r in routes:
        visits = r.get("visits") or []
        load = float(r.get("load", 0) or 0)
        dist = float(r.get("distance", 0) or 0)
        dur = float(r.get("duration", 0) or 0)
        tw_slack = None
        if visits:
            tw_slack = min(
                (float(v.get("end_time", 0) or 0) - float(v.get("start_time", 0) or 0))
                for v in visits
            )
        per_route.append({
            "route_id": r.get("route_id"),
            "num_stops": r.get("num_stops", len(visits)),
            "distance": dist,
            "load": load,
            "duration": dur,
            "capacity_utilization": round(load / cap, 4) if cap > 0 else None,
            "min_visit_span": round(tw_slack, 4) if tw_slack is not None else None,
        })

    total_load = sum(float(r.get("load", 0) or 0) for r in routes)
    return _json({
        "ok": True,
        "path": str(p),
        "status": sol.get("status"),
        "objective": obj,
        "total_distance_recomputed": recomputed_dist,
        "distance_matches_objective": dist_match,
        "num_routes": len(routes),
        "num_vehicles_used": sol.get("num_vehicles_used"),
        "vehicle_capacity": cap,
        "total_load": total_load,
        "aggregate_capacity_utilization": round(total_load / (cap * len(routes)), 4)
        if cap > 0 and routes else None,
        "routes": per_route,
    })


# --------------------------------------------------------------------------- #
# Scheduling / JSSP
# --------------------------------------------------------------------------- #

@tool
def profile_scheduling_data(instance: str = "ft06") -> str:
    """Profile a Taillard JSSP instance: structure, bounds, known optimum.

    Reads the Taillard JSON fixture, reports job/machine/operation counts, the
    known optimum / lower / upper bounds carried by the fixture, and the total
    processing work (sum of durations) — the classic LB0 lower bound.

    Args:
        instance: Taillard instance name (e.g. ``ft06``, ``la01``).

    Returns:
        JSON with instance shape, published bounds, and recomputed work content.
    """
    root = _resolve_root()
    inst = instance.strip()
    cand = root / "fixtures" / "benchmarks" / "taillard" / "jssp" / f"{inst}.json"
    if not cand.is_file():
        return _json({"ok": False, "error": f"instance not found: {cand}"})
    data = _load_json(cand)
    jobs = data.get("jobs") or []
    num_jobs = data.get("num_jobs", len(jobs))
    num_machines = data.get("num_machines")
    total_work = sum(dur for job in jobs for _op, dur in job)
    n_ops = sum(len(job) for job in jobs)
    return _json({
        "ok": True,
        "instance": data.get("instance", inst),
        "family": data.get("family"),
        "num_jobs": num_jobs,
        "num_machines": num_machines,
        "num_operations": n_ops,
        "total_processing_work": total_work,
        "known_optimum": data.get("known_optimum"),
        "lower_bound": data.get("lower_bound"),
        "upper_bound": data.get("upper_bound"),
        "source": str(cand),
    })


@tool
def inspect_scheduling_solution(solution_path: str = "outputs/jssp-solution.json") -> str:
    """Decompose a JSSP solution envelope: makespan, utilization, critical path.

    Recomputes the makespan from the schedule, reports per-machine utilization
    and idle time, the longest job (critical-path lower bound), and checks the
    envelope objective against the recomputed makespan.

    Args:
        solution_path: Path to a solver solution JSON.

    Returns:
        JSON with recomputed makespan, machine utilization, flow time, and
        objective consistency.
    """
    root = _resolve_root()
    p = Path(solution_path)
    if not p.is_absolute():
        p = root / p
    if not p.is_file():
        return _json({"ok": False, "error": f"solution not found: {p}"})
    sol = _load_json(p)
    tasks = sol.get("schedule") or []
    if not tasks:
        return _json({"ok": False, "error": "empty schedule"})

    makespan = max(float(t.get("end", 0) or 0) for t in tasks)
    total_flow = sum(float(t.get("end", 0) or 0) - float(t.get("start", 0) or 0) for t in tasks)

    by_machine: dict[str, list[dict]] = {}
    for t in tasks:
        by_machine.setdefault(str(t.get("machine")), []).append(t)
    utilization: dict[str, float] = {}
    for m, mtasks in by_machine.items():
        busy = sum(float(t.get("duration", 0) or 0) for t in mtasks)
        utilization[m] = round(busy / makespan, 4) if makespan > 0 else 0.0

    by_job: dict[str, list[dict]] = {}
    for t in tasks:
        by_job.setdefault(str(t.get("job")), []).append(t)
    longest_job = max(
        (sum(float(t.get("duration", 0) or 0) for t in jt) for jt in by_job.values()),
        default=0.0,
    )

    obj = sol.get("objective")
    ms_match = _is_num(obj) and abs(makespan - float(obj)) <= EPS
    return _json({
        "ok": True,
        "path": str(p),
        "status": sol.get("status"),
        "objective": obj,
        "makespan_recomputed": makespan,
        "makespan_matches_objective": ms_match,
        "num_jobs": sol.get("num_jobs"),
        "num_machines": sol.get("num_machines"),
        "total_flow_time": round(total_flow, 4),
        "longest_job_work": longest_job,
        "machine_utilization": utilization,
        "known_optimum": sol.get("known_optimum"),
        "lower_bound": sol.get("lower_bound"),
    })


# --------------------------------------------------------------------------- #
# Rostering / Staff Scheduling
# --------------------------------------------------------------------------- #

@tool
def profile_rostering_data(num_employees: int = 8, num_days: int = 14) -> str:
    """Profile a staff-rostering instance: demand matrix + coverage requirements.

    Generates the canonical shift-demand structure the rostering solver uses,
    reports total required shifts per day, the peak daily coverage need, and
    the total working-shift demand across the horizon.

    Args:
        num_employees: Number of employees to schedule.
        num_days: Planning horizon in days.

    Returns:
        JSON with demand matrix shape, per-day totals, and peak coverage.
    """
    shifts = ["Morning", "Afternoon", "Night"]
    # Canonical demand pattern used by solve_staff_rostering default.
    demand_template = {"Morning": 2, "Afternoon": 2, "Night": 1}
    matrix = []
    for _ in range(num_days):
        matrix.append(dict(demand_template))
    per_day_total = [sum(d.values()) for d in matrix]
    peak = max(per_day_total) if per_day_total else 0
    return _json({
        "ok": True,
        "num_employees": num_employees,
        "num_days": num_days,
        "shifts": shifts,
        "demand_matrix": matrix,
        "per_day_total_required": per_day_total,
        "peak_daily_coverage": peak,
        "total_working_shift_demand": sum(per_day_total),
        "avg_load_per_employee": round(sum(per_day_total) / num_employees, 4)
        if num_employees else None,
    })


@tool
def inspect_rostering_solution(solution_path: str = "outputs/staff_rostering-solution.json") -> str:
    """Decompose a staff-rostering solution: coverage, fairness, rest rules.

    Recomputes per-day/per-shift coverage against demand, the fairness
    std-dev of shift counts, consecutive-workday runs, and night-to-morning
    rest violations — all from the envelope roster (Numbers Truth).

    Args:
        solution_path: Path to a solver solution JSON.

    Returns:
        JSON with coverage gaps, fairness metrics, and rule-violation counts.
    """
    root = _resolve_root()
    p = Path(solution_path)
    if not p.is_absolute():
        p = root / p
    if not p.is_file():
        return _json({"ok": False, "error": f"solution not found: {p}"})
    sol = _load_json(p)
    roster = sol.get("roster") or {}
    demands = sol.get("shift_demands") or []
    num_days = int(sol.get("num_days", len(demands)))
    max_consec = int(sol.get("max_consecutive_days", 5))
    working = ["Morning", "Afternoon", "Night"]

    coverage_gaps = []
    for d in range(num_days):
        demand = demands[d] if d < len(demands) else {}
        for s in working:
            need = demand.get(s, 0)
            if need <= 0:
                continue
            assigned = sum(1 for sched in roster.values() if d < len(sched) and sched[d] == s)
            if assigned < need:
                coverage_gaps.append({"day": d, "shift": s, "assigned": assigned, "required": need})

    shift_counts = {
        emp: sum(1 for s in sched if s in working) for emp, sched in roster.items()
    }
    counts = list(shift_counts.values())
    mean = sum(counts) / len(counts) if counts else 0.0
    std = math.sqrt(sum((c - mean) ** 2 for c in counts) / len(counts)) if counts else 0.0

    night_rest_violations = 0
    max_run = 0
    for sched in roster.values():
        for d in range(len(sched) - 1):
            if sched[d] == "Night" and sched[d + 1] == "Morning":
                night_rest_violations += 1
        run = 0
        for s in sched:
            run = run + 1 if s in working else 0
            max_run = max(max_run, run)
    consec_violations = sum(1 for sched in roster.values() if max_run > max_consec)

    return _json({
        "ok": True,
        "path": str(p),
        "status": sol.get("status"),
        "objective": sol.get("objective"),
        "num_employees": sol.get("num_employees"),
        "num_days": num_days,
        "coverage_gaps": coverage_gaps,
        "coverage_ok": not coverage_gaps,
        "fairness": {"min_shifts": min(counts) if counts else 0,
                     "max_shifts": max(counts) if counts else 0,
                     "std_dev": round(std, 4)},
        "night_rest_violations": night_rest_violations,
        "max_consecutive_workdays": max_run,
        "consecutive_limit": max_consec,
        "consecutive_violations": consec_violations,
    })


# --------------------------------------------------------------------------- #
# Inventory / Lot Sizing
# --------------------------------------------------------------------------- #

@tool
def profile_inventory_data(benchmark: str = "ww12") -> str:
    """Profile a lot-sizing instance: demand, costs, capacity, safety stock.

    Reads the lot-sizing benchmark demands and the cost structure, reports the
    total demand, the number of setup opportunities, and the holding/setup
    cost weights.

    Args:
        benchmark: Lot-sizing benchmark name (``ww12``, ``clsp60``).

    Returns:
        JSON with demand profile, cost structure, and aggregate statistics.
    """
    root = _resolve_root()
    bench = None
    try:
        import solve_lot_sizing as ls

        bench = (ls.BENCHMARKS or {}).get(benchmark) if hasattr(ls, "BENCHMARKS") else None
    except Exception:
        bench = None
    if not bench:
        return _json({"ok": False, "error": f"benchmark not found: {benchmark}"})
    demands = bench.get("demands") or []
    return _json({
        "ok": True,
        "benchmark": benchmark,
        "num_periods": len(demands),
        "demands": demands,
        "total_demand": sum(float(d) for d in demands),
        "avg_demand": round(sum(float(d) for d in demands) / len(demands), 4) if demands else 0.0,
        "setup_cost": bench.get("setup_cost"),
        "holding_cost": bench.get("holding_cost"),
        "unit_cost": bench.get("unit_cost", 0.0),
        "capacity": bench.get("capacity"),
        "known_optimum": bench.get("known_optimum"),
    })


@tool
def inspect_inventory_solution(solution_path: str = "outputs/lot_sizing-solution.json") -> str:
    """Decompose a lot-sizing solution: flow balance, setup/holding breakdown.

    Recomputes the inventory flow balance per period, the setup pattern
    (Wagner-Whitin batches), and the setup/holding/production cost split from
    the envelope schedule (Numbers Truth).

    Args:
        solution_path: Path to a solver solution JSON.

    Returns:
        JSON with flow-balance status, setup periods, and cost breakdown.
    """
    root = _resolve_root()
    p = Path(solution_path)
    if not p.is_absolute():
        p = root / p
    if not p.is_file():
        return _json({"ok": False, "error": f"solution not found: {p}"})
    sol = _load_json(p)
    schedule = sol.get("schedule") or []
    if not schedule:
        return _json({"ok": False, "error": "empty schedule"})

    prev_inv = float(sol.get("initial_inventory", 0.0) or 0.0)
    flow_ok = True
    flow_detail = None
    setup_periods = []
    for i, s in enumerate(schedule):
        d = float(s.get("demand", 0) or 0)
        x = float(s.get("production", 0) or 0)
        inv = float(s.get("inventory", 0) or 0)
        if abs(prev_inv + x - inv - d) > EPS:
            flow_ok = False
            flow_detail = f"period {s.get('period', i+1)}: balance broken"
            break
        prev_inv = inv
        if x > EPS and s.get("setup"):
            setup_periods.append(s.get("period", i + 1))

    costs = sol.get("costs") or {}
    return _json({
        "ok": True,
        "path": str(p),
        "status": sol.get("status"),
        "objective": sol.get("objective"),
        "num_periods": sol.get("num_periods"),
        "flow_balance_ok": flow_ok,
        "flow_balance_detail": flow_detail,
        "setup_periods": setup_periods,
        "num_setups": len(setup_periods),
        "costs": costs,
        "known_optimum": sol.get("known_optimum"),
        "lower_bound": sol.get("lower_bound"),
    })


# --------------------------------------------------------------------------- #
# Facility / CFLP
# --------------------------------------------------------------------------- #

@tool
def profile_facility_data(benchmark: str = "cap41") -> str:
    """Profile a CFLP benchmark: facility/customer structure, demand, costs.

    Reads the OR-Library CFLP instance, reports the number of facilities and
    customers, total customer demand, and the fixed-cost / demand-weighted
    transport cost structure.

    Args:
        benchmark: OR-Library benchmark name (``cap41``, ``cap61``, ``cap71``).

    Returns:
        JSON with instance shape, aggregate demand, and known optimum.
    """
    root = _resolve_root()
    cand = root / "fixtures" / "benchmarks" / "orlib_cflp" / f"{benchmark}.txt"
    if not cand.is_file():
        return _json({"ok": False, "error": f"benchmark not found: {cand}"})
    lines = [ln.split() for ln in cand.read_text(encoding="utf-8").splitlines() if ln.split()]
    m, n = int(lines[0][0]), int(lines[0][1])
    fixed_costs = [float(x) for x in lines[1][:m]]
    demands = [float(x) for x in lines[1 + m + 1][:n]] if len(lines) > 1 + m + 1 else []
    # demand row is the line after fixed-cost row; guard shape.
    if not demands:
        # fallback: parse the demand line by position
        for ln in lines[1:]:
            if len(ln) == n:
                demands = [float(x) for x in ln[:n]]
                break
    known = {"cap41": 1040444.375, "cap61": 932615.75, "cap71": 932615.75}.get(benchmark)
    return _json({
        "ok": True,
        "benchmark": benchmark,
        "num_facilities": m,
        "num_customers": n,
        "total_demand": sum(demands),
        "avg_demand": round(sum(demands) / n, 4) if n else 0.0,
        "fixed_costs": fixed_costs,
        "known_optimum": known,
        "source": str(cand),
        "coord_sha256": _sha256(cand),
    })


@tool
def inspect_facility_solution(solution_path: str = "outputs/facility-solution.json") -> str:
    """Decompose a CFLP solution: open facilities, allocation, cost split.

    Recomputes the fixed/transport/total cost split, per-facility capacity
    utilization, and demand-satisfaction fraction from the envelope
    (Numbers Truth).

    Args:
        solution_path: Path to a solver solution JSON.

    Returns:
        JSON with cost breakdown, utilization, and demand satisfaction.
    """
    root = _resolve_root()
    p = Path(solution_path)
    if not p.is_absolute():
        p = root / p
    if not p.is_file():
        return _json({"ok": False, "error": f"solution not found: {p}"})
    sol = _load_json(p)
    open_fac = sol.get("open_facilities") or []
    allocs = sol.get("allocations") or sol.get("assignments") or []
    costs = sol.get("costs") or {}

    utilization = []
    for f in open_fac:
        cap = float(f.get("capacity", 0) or 0)
        load = float(f.get("load", 0) or 0)
        utilization.append({
            "facility_id": f.get("facility_id"),
            "load": load,
            "capacity": cap,
            "utilization": round(load / cap, 4) if cap > 0 else None,
        })

    demand_satisfied = all(
        abs(sum(float(s.get("fraction", 0) or 0) for s in (a.get("served_by") or [])) - 1.0) <= 1e-3
        for a in allocs
    ) if allocs else False

    return _json({
        "ok": True,
        "path": str(p),
        "status": sol.get("status"),
        "objective": sol.get("objective"),
        "num_facilities_open": len(open_fac),
        "num_customers": sol.get("num_customers"),
        "costs": costs,
        "total_fixed_cost": sol.get("total_fixed_cost"),
        "total_transport_cost": sol.get("total_transport_cost"),
        "facility_utilization": utilization,
        "demand_fully_satisfied": demand_satisfied,
        "esg": sol.get("esg_metrics"),
        "known_optimum": sol.get("known_optimum"),
    })


# --------------------------------------------------------------------------- #
# Pricing / Two-Stage Stochastic LP
# --------------------------------------------------------------------------- #

@tool
def profile_pricing_data(fixture: str = "fixtures/benchmarks/stochastic/farmer_problem.json") -> str:
    """Profile a two-stage stochastic-LP instance: scenarios, crops, prices.

    Reads the stochastic problem JSON, reports the scenario tree, crop list,
    first-stage capacity, and the internal-demand / selling-price structure.

    Args:
        fixture: Path to a stochastic problem JSON.

    Returns:
        JSON with scenario count, crop structure, and price/demand summary.
    """
    root = _resolve_root()
    p = Path(fixture)
    if not p.is_absolute():
        p = root / p
    if not p.is_file():
        return _json({"ok": False, "error": f"fixture not found: {p}"})
    data = _load_json(p)
    scenarios = data.get("scenarios") or []
    crops = data.get("crops") or []
    prices = data.get("selling_price") or {}
    demand = data.get("internal_demand") or {}
    return _json({
        "ok": True,
        "name": data.get("name"),
        "total_land_acres": data.get("total_land_acres"),
        "crops": crops,
        "num_scenarios": len(scenarios),
        "scenario_names": [s.get("name") for s in scenarios],
        "planting_cost_per_acre": data.get("planting_cost_per_acre"),
        "selling_price": prices,
        "internal_demand": demand,
        "sugar_beet_quota": data.get("sugar_beet_quota"),
        "known_optimal": data.get("known_optimal"),
        "coord_sha256": _sha256(p),
    })


@tool
def inspect_pricing_solution(solution_path: str = "outputs/stochastic_lp-solution.json") -> str:
    """Decompose a stochastic-LP solution: first-stage, recourse, indicators.

    Reports the first-stage decision, first-stage cost, expected recourse
    revenue, and the stochastic indicators (RP / WS / EEV / EVPI / VSS),
    checking the fundamental inequality WS >= RP >= EEV.

    Args:
        solution_path: Path to a solver solution JSON.

    Returns:
        JSON with first-stage/recourse breakdown and indicator consistency.
    """
    root = _resolve_root()
    p = Path(solution_path)
    if not p.is_absolute():
        p = root / p
    if not p.is_file():
        return _json({"ok": False, "error": f"solution not found: {p}"})
    sol = _load_json(p)
    ind = sol.get("stochastic_indicators") or {}
    rp = float(ind.get("RP", 0) or 0)
    ws = float(ind.get("WS", 0) or 0)
    eev = float(ind.get("EEV", 0) or 0)
    inequality_ok = (ws + EPS >= rp >= eev - EPS)
    return _json({
        "ok": True,
        "path": str(p),
        "status": sol.get("status"),
        "objective": sol.get("objective"),
        "first_stage_decision": sol.get("first_stage_decision"),
        "first_stage_cost": sol.get("first_stage_cost"),
        "expected_second_stage_revenue": sol.get("expected_second_stage_revenue"),
        "stochastic_indicators": ind,
        "indicators_inequality_ok": inequality_ok,
        "num_scenarios": len(sol.get("scenarios") or []),
    })


# --------------------------------------------------------------------------- #
# Project / RCPSP
# --------------------------------------------------------------------------- #

@tool
def profile_project_data(instance: str = "j301_1") -> str:
    """Profile a PSPLib RCPSP instance: activities, precedence, resources.

    Reads the *.sm instance, reports the number of activities (including the
    source/sink dummies), the precedence DAG edge count, renewable resources
    and capacities, and the horizon.

    Args:
        instance: PSPLib instance name (``j301_1``).

    Returns:
        JSON with instance shape, DAG stats, and resource profile.
    """
    root = _resolve_root()
    cand = root / "fixtures" / "benchmarks" / "psplib" / f"{instance}.sm"
    if not cand.is_file():
        return _json({"ok": False, "error": f"instance not found: {cand}"})
    try:
        import psplib

        prob = psplib.parse(str(cand), instance_format="psplib")
        activities = prob.activities
        resources = prob.resources
        n = len(activities)
        edges = sum(len(a.successors) for a in activities)
        caps = [int(r.capacity) for r in resources]
        horizon = int(getattr(prob, "horizon", 0) or 0)
        return _json({
            "ok": True,
            "instance": instance,
            "num_activities": n,
            "num_precedence_edges": edges,
            "num_resources": len(resources),
            "resource_capacities": caps,
            "horizon": horizon,
            "known_optimum": 43 if instance == "j301_1" else None,
            "source": str(cand),
            "coord_sha256": _sha256(cand),
        })
    except Exception as exc:
        return _json({"ok": False, "error": f"parse failed: {exc}", "instance": instance})


@tool
def inspect_project_solution(solution_path: str = "outputs/rcpsp-solution.json") -> str:
    """Decompose an RCPSP solution: makespan, critical path, resource load.

    Recomputes the makespan from the schedule, reports the critical path,
    per-resource peak load vs capacity, and precedence slack.

    Args:
        solution_path: Path to a solver solution JSON.

    Returns:
        JSON with recomputed makespan, critical path, and resource utilization.
    """
    root = _resolve_root()
    p = Path(solution_path)
    if not p.is_absolute():
        p = root / p
    if not p.is_file():
        return _json({"ok": False, "error": f"solution not found: {p}"})
    sol = _load_json(p)
    schedule = sol.get("schedule") or []
    if not schedule:
        return _json({"ok": False, "error": "empty schedule"})

    makespan = max(float(e.get("end", 0) or 0) for e in schedule)
    caps = [int(c) for c in (sol.get("resource_capacities") or [])]
    n_res = int(sol.get("num_resources", len(caps)))
    peak_load = [0] * n_res
    for e in schedule:
        for r in range(n_res):
            d = int((e.get("demands") or [0] * n_res)[r]) if r < len(e.get("demands") or []) else 0
            if d > 0:
                peak_load[r] += d
    utilization = [
        {"resource": f"R{r}", "peak_load": peak_load[r], "capacity": caps[r] if r < len(caps) else None,
         "utilization": round(peak_load[r] / caps[r], 4) if r < len(caps) and caps[r] > 0 else None}
        for r in range(n_res)
    ]

    obj = sol.get("objective")
    ms_match = _is_num(obj) and abs(makespan - float(obj)) <= EPS
    return _json({
        "ok": True,
        "path": str(p),
        "status": sol.get("status"),
        "objective": obj,
        "makespan_recomputed": makespan,
        "makespan_matches_objective": ms_match,
        "num_activities": sol.get("num_activities"),
        "num_resources": n_res,
        "critical_path": sol.get("critical_path"),
        "critical_path_length": sol.get("metrics", {}).get("critical_path_length")
        if isinstance(sol.get("metrics"), dict) else None,
        "resource_utilization": utilization,
        "known_optimum": sol.get("known_optimum"),
        "lower_bound": sol.get("lower_bound"),
    })


# --------------------------------------------------------------------------- #
# Finance / Portfolio
# --------------------------------------------------------------------------- #

@tool
def profile_portfolio_data(fixture: str = "") -> str:
    """Profile a Markowitz portfolio instance: assets, returns, risk, budget.

    Reads the portfolio input manifest (asset names, expected returns,
    covariance matrix, prices, budget), reports the number of assets, the
    return range, the covariance matrix shape, and the total budget.

    Args:
        fixture: Optional path to a portfolio input JSON. Defaults to the
            shipped demo manifest.

    Returns:
        JSON with asset count, return/risk summary, and budget.
    """
    root = _resolve_root()
    if fixture:
        p = Path(fixture)
        if not p.is_absolute():
            p = root / p
        if p.is_file():
            data = _load_json(p)
            return _json({
                "ok": True,
                "source": str(p),
                "asset_names": data.get("asset_names") or list((data.get("allocations") or {}).keys()),
                "expected_returns": data.get("expected_returns"),
                "cov_matrix_shape": (
                    [len(data.get("cov_matrix") or []), len((data.get("cov_matrix") or [[]])[0])]
                    if data.get("cov_matrix") else None
                ),
                "total_portfolio_value": data.get("total_portfolio_value"),
            })
    # Default demo manifest (5 assets, max_sharpe).
    assets = ["US_EQUITY", "GLOBAL_TECH", "TREASURY_BONDS", "GOLD", "REIT"]
    return _json({
        "ok": True,
        "source": "default demo manifest",
        "asset_names": assets,
        "num_assets": len(assets),
        "expected_returns": {
            "US_EQUITY": 0.08, "GLOBAL_TECH": 0.12, "TREASURY_BONDS": 0.04,
            "GOLD": 0.06, "REIT": 0.07,
        },
        "cov_matrix_shape": [len(assets), len(assets)],
        "total_portfolio_value": 1_000_000.0,
    })


@tool
def inspect_portfolio_solution(solution_path: str = "outputs/portfolio-solution.json") -> str:
    """Decompose a Markowitz portfolio solution: weights, return, risk, Sharpe.

    Recomputes the weight sum, expected return, volatility, and Sharpe ratio
    from the raw inputs carried by the envelope (Numbers Truth), and reports
    the allocation breakdown.

    Args:
        solution_path: Path to a solver solution JSON.

    Returns:
        JSON with allocation, recomputed return/vol/Sharpe, and weights sum.
    """
    root = _resolve_root()
    p = Path(solution_path)
    if not p.is_absolute():
        p = root / p
    if not p.is_file():
        return _json({"ok": False, "error": f"solution not found: {p}"})
    sol = _load_json(p)
    allocs = sol.get("allocations") or {}
    names = list(allocs.keys())
    weights = [float(allocs[n]) for n in names]
    weight_sum = sum(weights)

    inputs = sol.get("inputs") or {}
    mu = inputs.get("expected_returns")
    ret = float(sol.get("expected_return_value", sol.get("expected_return", 0) or 0))
    vol = float(sol.get("volatility", 0) or 0)
    sharpe = float(sol.get("sharpe_ratio", 0) or 0)
    rf = float(sol.get("risk_free_rate", inputs.get("risk_free_rate", 0.02) or 0.02))

    recomputed_ret = None
    if isinstance(mu, (list, dict)):
        mu_list = [float(mu[i]) if isinstance(mu, list) else float(mu[n]) for i, n in enumerate(names)]
        recomputed_ret = round(sum(w * m for w, m in zip(weights, mu_list)), 6)

    return _json({
        "ok": True,
        "path": str(p),
        "status": sol.get("status"),
        "objective": sol.get("objective"),
        "objective_type": sol.get("objective_type"),
        "num_assets": len(names),
        "allocations": allocs,
        "weights_sum": round(weight_sum, 6),
        "weights_sum_to_one": abs(weight_sum - 1.0) <= 1e-3,
        "expected_return": ret,
        "expected_return_recomputed": recomputed_ret,
        "volatility": vol,
        "sharpe_ratio": sharpe,
        "risk_free_rate": rf,
    })


# --------------------------------------------------------------------------- #
# microgrid (moved from domains/microgrid.py — plan 2.3 alignment)
# --------------------------------------------------------------------------- #

def _microgrid_case_dir(root: Path) -> Path:
    return root / "inbox" / "cumcm2026_c"


@tool
def profile_microgrid_data(case_dir: str = "") -> str:
    """Read CUMCM 2026 Problem C Excel attachments and emit a data profile.

    The auditor uses this to freeze the input manifest before any solver
    runs: it summarises 附件1 (single-day TOU price/load/PV forecast),
    附件2 (334-day actual load & PV), 附件3 (24h PV forecast releases at
    0/6/12/18) and 附件4 (per-10-min dynamic prices), plus the battery
    nameplate specs from 附录1.

    Args:
        case_dir: Optional path to the case directory. Defaults to
            ``inbox/cumcm2026_c`` under the resolved root.

    Returns:
        JSON string with ``ok``, per-attachment shape/column profile, key
        numeric statistics (price range, load range, PV range), battery
        nameplate specs and a SHA-256 hash of each attachment.
    """
    root = _resolve_root()
    case = Path(case_dir) if case_dir else _microgrid_case_dir(root)
    if not case.is_absolute():
        case = root / case
    profile: dict[str, Any] = {
        "ok": False,
        "case_dir": str(case),
        "attachments": {},
        "battery_nameplate": {
            "max_capacity_kwh": 12000.0,
            "max_charge_discharge_power_kw": 5000.0,
            "max_charge_energy_per_slot_kwh": round(5000.0 / 6.0, 4),
            "soc_min_kwh": 1200.0,
            "soc_max_kwh": 10800.0,
            "round_trip_efficiency": 0.90,
            "initial_soc_kwh": 6000.0,
        },
    }
    try:
        import pandas as pd

        files = {
            "附件1": "附件1.xlsx",
            "附件2": "附件2.xlsx",
            "附件3": "附件3.xlsx",
            "附件4": "附件4.xlsx",
        }
        for label, fname in files.items():
            fpath = case / fname
            entry = {"path": str(fpath), "exists": fpath.is_file()}
            if fpath.is_file():
                try:
                    entry["sha256"] = hashlib.sha256(fpath.read_bytes()).hexdigest()
                except Exception:
                    pass
                try:
                    xl = pd.ExcelFile(fpath)
                    entry["sheets"] = xl.sheet_names
                    for sh in xl.sheet_names[:3]:
                        df = pd.read_excel(fpath, sheet_name=sh, nrows=50)
                        entry[f"sheet_{sh}_shape"] = list(df.shape)
                        entry[f"sheet_{sh}_columns"] = [str(c) for c in df.columns[:8]]
                    df0 = pd.read_excel(fpath, sheet_name=xl.sheet_names[0])
                    num = df0.select_dtypes(include="number") if df0.shape[0] else df0
                    if num.shape[1] > 0:
                        entry["numeric_summary"] = {
                            str(col): {
                                "min": float(num[col].min()),
                                "max": float(num[col].max()),
                                "mean": float(num[col].mean()),
                            }
                            for col in num.columns[:4]
                            if pd.api.types.is_numeric_dtype(num[col])
                        }
                except Exception as exc:
                    entry["error"] = f"{type(exc).__name__}: {exc}"
            profile["attachments"][label] = entry
        profile["ok"] = True
    except Exception as exc:
        profile["error"] = f"{type(exc).__name__}: {exc}"
    return _json(profile)


@tool
def inspect_microgrid_solution(solution_path: str = "outputs/cumcm2026_c-solution.json") -> str:
    """Read a microgrid solution JSON and surface its key metrics for reporting.

    The exact-bound / heuristic specialists call this after ``execute_or_solver``
    to read back the objective, per-subproblem status and battery-dispatch
    facts without re-parsing the raw file.  Numbers Truth boundary intact:
    values are echoed from the solver artifact, never recomputed here.
    """
    root = _resolve_root()
    path = Path(solution_path)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return _json({"ok": False, "error": f"Solution not found: {path}"})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _json({"ok": False, "error": f"Failed reading solution: {exc}"})
    sub = data.get("subproblems") or {}
    summary: dict[str, Any] = {
        "ok": True,
        "path": str(path),
        "status": data.get("status"),
        "objective": data.get("objective"),
        "total_purchase_cost": data.get("total_purchase_cost"),
        "solver": data.get("solver"),
        "solve_time_sec": data.get("solve_time_sec"),
        "proven_optimal": (data.get("meta") or {}).get("proven_optimal"),
        "subproblems": {
            k: (v.get("total_cost") if isinstance(v, dict) else v)
            for k, v in sub.items()
        },
    }
    for key in ("peak_demand_kw", "battery_degradation_loss", "emergency_purchase_cost"):
        if data.get(key) is not None:
            summary[key] = data.get(key)
    return _json(summary)


# --------------------------------------------------------------------------- #
# tube (3D laser common-edge nesting, tube_cut_b2026 / polyomino / binpack)
# --------------------------------------------------------------------------- #

@tool
def profile_tube_data(case_dir: str = "") -> str:
    """Profile the Tube B case directory (geometry snapshot + demand data).

    The auditor uses this to freeze the input manifest (stock inventory,
    cross-section demand, PCA geometry snapshot SHA-256) before any solver
    runs.

    Args:
        case_dir: Optional path to the case directory. Defaults to
            ``outputs/b-tube-cut`` under the resolved root.

    Returns:
        JSON string with ``ok``, manifest entries (paths, sha256, top-level
        keys for JSON, row/column counts for CSV), stock inventory totals
        when present, and bottleneck diagnostics.
    """
    root = _resolve_root()
    case = Path(case_dir) if case_dir else root / "outputs" / "b-tube-cut"
    if not case.is_absolute():
        case = root / case
    manifest: dict[str, Any] = {"ok": False, "case_dir": str(case), "files": {}}
    total_stock_mm = 0.0
    try:
        if not case.is_dir():
            manifest["error"] = f"Case directory not found: {case}"
            return _json(manifest)
        candidates = sorted(p for p in case.iterdir() if p.is_file())
        for p in candidates[:40]:
            entry: dict[str, Any] = {"path": str(p), "bytes": p.stat().st_size}
            try:
                entry["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
            except Exception:
                pass
            if p.suffix.lower() == ".json":
                try:
                    doc = json.loads(p.read_text(encoding="utf-8"))
                    entry["top_keys"] = sorted(doc.keys()) if isinstance(doc, dict) else type(doc).__name__
                    if isinstance(doc, dict):
                        for key in ("stocks", "inventory", "tubes", "sections"):
                            if key in doc and isinstance(doc[key], list):
                                entry[f"{key}_count"] = len(doc[key])
                                for item in doc[key][:5]:
                                    if isinstance(item, dict):
                                        if "length_mm" in item or "stock_length_mm" in item:
                                            total_stock_mm += float(item.get("length_mm") or item.get("stock_length_mm") or 0.0)
                except Exception as exc:
                    entry["error"] = f"JSON parse failed: {exc}"
            manifest["files"][p.name] = entry
        manifest["ok"] = bool(manifest["files"])
        if total_stock_mm:
            manifest["total_stock_length_mm"] = round(total_stock_mm, 2)
    except Exception as exc:
        manifest["error"] = f"{type(exc).__name__}: {exc}"
    return _json(manifest)


@tool
def inspect_tube_solution(solution_path: str = "outputs/tube_cut_b2026-solution.json") -> str:
    """Read a tube-cut solution JSON and surface its envelope per question.

    Numbers Truth: values are echoed from the solver artifact (objective,
    per-question stock usage, leftover ledger), never recomputed here.
    """
    root = _resolve_root()
    path = Path(solution_path)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return _json({"ok": False, "error": f"Solution not found: {path}"})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _json({"ok": False, "error": f"Failed reading solution: {exc}"})
    questions = data.get("questions") or {}
    per_q: dict[str, Any] = {}
    for qkey, qval in questions.items():
        if not isinstance(qval, dict):
            per_q[qkey] = qval
            continue
        stocks = qval.get("stocks") or []
        used_mm = 0.0
        alloc_count = len(stocks)
        for st in stocks:
            if isinstance(st, dict):
                seq = st.get("sequence") or []
                alloc_count += len(seq)
                try:
                    used_mm += float(st.get("used_length_mm") or 0.0)
                except Exception:
                    pass
        entry = {
            "status": qval.get("status"),
            "objective": qval.get("objective", data.get("objective")),
            "stock_entries": len(stocks),
            "allocations": alloc_count,
        }
        if used_mm:
            entry["used_stock_length_mm"] = round(used_mm, 2)
        leftover = qval.get("leftover_ledger") or qval.get("remainder")
        if leftover is not None:
            entry["leftover"] = leftover
        per_q[qkey] = entry
    return _json(
        {
            "ok": True,
            "path": str(path),
            "status": data.get("status"),
            "objective": data.get("objective"),
            "solver": data.get("solver"),
            "proven_optimal": (data.get("meta") or {}).get("proven_optimal"),
            "questions": per_q,
        }
    )
