"""Phase 2 Golden Benchmarks & Solver Envelope Standardization tests.

Covers the 5 core industrial solvers (Tasks 2.1 ~ 2.5):

1. JSSP        (2.1) — ``tools/solve_jssp.py``         Taillard JSSP/FJSSP
2. PyVRP       (2.2) — ``tools/solve_pyvrp.py``        Solomon VRPTW / VRPPDTW
3. RCPSP       (2.3) — ``tools/solve_rcpsp.py``        PSPLib j301_1
4. Facility    (2.4) — ``tools/solve_facility.py``     Beasley OR-Library CFLP
5. Lot sizing  (2.5) — ``tools/solve_lot_sizing.py``    Wagner-Whitin DP / CLSP MIP

For every domain the suite verifies:

* **Benchmark execution** — the solver runs on the golden benchmark and
  reproduces the published optimum (reference only; Numbers Truth: the
  objective strictly comes from the solver).
* **Standard output envelope** — ``status`` / ``objective`` /
  ``lower_bound`` / ``optimality_gap`` present and mutually consistent
  (``lower_bound <= objective``, ``optimality_gap == objective - lower_bound``,
  proven-optimal solutions carry zero gap; heuristic engines report
  ``None`` bounds instead of invented ones).
* **Independent validation** — every solution passes the corresponding
  validator in ``tools/validators/extended_solvers.py`` with all checks ok.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from solve_facility import (
    load_orlibrary_cflp,
    solve_facility_location,
)
from solve_jssp import solve_jssp
from solve_lot_sizing import solve_lot_sizing
from solve_pyvrp import solve_pyvrp
from solve_rcpsp import solve_rcpsp
from validate_solution import validate

from validators.extended_solvers import (
    validate_facility_location,
    validate_jssp,
    validate_lot_sizing,
    validate_pyvrp,
    validate_rcpsp,
)

_ROOT = TOOLS.parent
_VRP_C101 = _ROOT / "fixtures" / "benchmarks" / "vrp" / "c101.txt"


# ---------------------------------------------------------------------------
# Shared envelope contract (Phase 2 standardization)
# ---------------------------------------------------------------------------
def assert_envelope(
    sol: dict,
    problem_class: str,
    statuses: tuple[str, ...] = ("OPTIMAL", "FEASIBLE"),
) -> dict:
    """Assert the standardized OR-Path output envelope (ADR-0002 + bounds)."""
    assert sol.get("problem_class") == problem_class, sol.get("problem_class")
    assert sol.get("status") in statuses, f"bad status: {sol.get('status')}"
    assert isinstance(sol.get("objective"), (int, float))
    assert sol["objective"] > 0, f"non-positive objective: {sol['objective']}"

    for key in ("lower_bound", "optimality_gap"):
        assert key in sol, f"envelope missing '{key}' (Phase 2 standard)"

    lb, gap = sol["lower_bound"], sol["optimality_gap"]
    if lb is None:
        # Heuristic engine (e.g. PyVRP HGS): bounds not applicable — the
        # honest representation is None, never an invented number.
        assert gap is None, "None lower_bound must imply None optimality_gap"
        return sol

    assert float(lb) <= float(sol["objective"]) + 1e-6, (
        f"lower_bound {lb} > objective {sol['objective']}"
    )
    assert gap is not None, "finite lower_bound must carry an optimality_gap"
    assert abs(float(gap) - (float(sol["objective"]) - float(lb))) <= 1e-4, (
        f"optimality_gap {gap} != objective - lower_bound "
        f"{float(sol['objective']) - float(lb)}"
    )
    if sol["status"] == "OPTIMAL":
        assert float(gap) <= 1e-6, (
            f"status OPTIMAL but nonzero gap {gap} "
            f"(objective {sol['objective']}, lower_bound {lb})"
        )
    return sol


def assert_validator_ok(
    validator, problem_id: str, sol: dict, expected_checks: set[str]
) -> list[dict]:
    """Run the domain validator directly; every check must be ok=True."""
    checks = validator(problem_id, sol)
    bad = [c for c in checks if not c.get("ok")]
    assert not bad, f"{problem_id}: failing checks -> {bad}"
    names = {c["name"] for c in checks}
    missing = expected_checks - names
    assert not missing, f"{problem_id}: missing checks {sorted(missing)}"
    return checks


JSSP_CHECKS = {
    "task_duration_consistency",
    "job_precedence",
    "machine_no_overlap",
    "makespan_objective_match",
}
PYVRP_CHECKS = {
    "pyvrp_status_feasible",
    "pyvrp_depot_endpoints",
    "pyvrp_client_visits_complete",
    "pyvrp_capacity_respected",
    "pyvrp_time_windows_respected",
    "pyvrp_distance_matches_objective",
}
# PDP instances carry shipments instead of plain clients: the client-
# completeness check is replaced by pickup/delivery precedence.
PYVRP_PDP_CHECKS = (
    PYVRP_CHECKS - {"pyvrp_client_visits_complete"}
) | {"pyvrp_pdp_precedence_respected"}
RCPSP_CHECKS = {
    "rcpsp_duration_consistency",
    "rcpsp_schedule_completeness",
    "rcpsp_precedence_respected",
    "rcpsp_resource_capacities_respected",
    "rcpsp_makespan_matches_objective",
}
FACILITY_CHECKS = {
    "facility_capacity_respected",
    "demand_fully_satisfied",
    "facility_cost_positive",
}
LOT_CHECKS = {
    "lot_sizing_flow_balance",
    "lot_sizing_setup_consistency",
    "lot_sizing_safety_stock",
    "lot_sizing_demand_match",
    "lot_sizing_period_cost_recompute",
    "lot_sizing_objective_match",
    "lot_sizing_total_setup_match",
    "lot_sizing_total_holding_match",
    "lot_sizing_total_production_match",
}


# ===========================================================================
# Task 2.1 — JSSP (Taillard benchmarks, makespan bound, machine Gantt)
# ===========================================================================
def test_jssp_ft06_benchmark():
    sol = solve_jssp("ft06", time_limit_s=20)
    assert_envelope(sol, "jssp")
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == 55
    assert sol["known_optimum"] == 55
    assert sol["lower_bound"] == 55
    assert sol["optimality_gap"] == 0
    assert len(sol["schedule"]) == 36  # 6 jobs x 6 machines

    assert_validator_ok(validate_jssp, "jssp_ft06_bench", sol, JSSP_CHECKS)


def test_jssp_taillard_la01_benchmark():
    sol = solve_jssp("la01", time_limit_s=20)
    assert_envelope(sol, "jssp")
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == 666  # published Taillard optimum
    assert sol["known_optimum"] == 666
    assert sol["optimality_gap"] == 0

    assert_validator_ok(validate_jssp, "jssp_la01_bench", sol, JSSP_CHECKS)


def test_jssp_fjssp_kacem1_benchmark():
    sol = solve_jssp("kacem1", family="fjssp", time_limit_s=20)
    assert_envelope(sol, "fjssp")
    assert sol["problem_class"] == "fjssp"
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == 11
    assert sol["known_optimum"] == 11
    assert sol["optimality_gap"] == 0

    assert_validator_ok(validate_jssp, "jssp_kacem1_bench", sol, JSSP_CHECKS)


@pytest.mark.parametrize("name,family,gold", [("ft06", "jssp", 55), ("la01", "jssp", 666)])
def test_jssp_envelope_bounds_standardized(name, family, gold):
    """Phase 2 envelope: lower_bound/optimality_gap on every Taillard run."""
    sol = solve_jssp(name, family=family, time_limit_s=20)
    assert_envelope(sol, "jssp")
    assert sol["lower_bound"] == gold
    assert sol["optimality_gap"] == 0
    assert sol["meta"]["proven_optimal"] is True


def test_jssp_machine_gantt_schedule_structure():
    """Machine Gantt schedule: every op assigned to exactly one machine."""
    sol = solve_jssp("ft06", time_limit_s=20)
    schedule = sol["schedule"]
    assert len(schedule) == 36
    for op in schedule:
        assert set(op) >= {"job", "task", "machine", "start", "end", "duration"}
        assert op["end"] - op["start"] == op["duration"]
        assert isinstance(op["machine"], int)

    # Exactly one (job, op) pair per schedule row; all 36 operations covered.
    assert len({(op["job"], op["task"]) for op in schedule}) == 36
    # Machine utilization profile (processing time / makespan).
    util = sol["machine_utilization"]
    assert len(util) == 6
    assert all(0.0 < u <= 1.0 for u in util.values())

    assert_validator_ok(validate_jssp, "jssp_ft06_gantt", sol, JSSP_CHECKS)


def test_jssp_gantt_png_render(tmp_path):
    """Per-machine Gantt chart PNG export (2.1 deliverable)."""
    out = tmp_path / "ft06_gantt.png"
    sol = solve_jssp("ft06", time_limit_s=20, gantt_path=out)
    assert out.exists() and out.stat().st_size > 0
    assert sol["gantt_path"] == str(out)


# ===========================================================================
# Task 2.2 — PyVRP (routes, arrival times, load profile, distance/cost)
# ===========================================================================
def test_pyvrp_solomon_c101_benchmark():
    sol = solve_pyvrp(
        solomon_path=_VRP_C101,
        max_customers=25,
        time_limit_s=3.0,
        problem_id="bench_c101_25",
    )
    assert_envelope(sol, "pyvrp")
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert sol["num_clients"] == 25
    assert sol["objective"] == sol["total_distance"] > 0

    assert_validator_ok(validate_pyvrp, "bench_c101_25", sol, PYVRP_CHECKS)


def test_pyvrp_route_structure_and_load_profile():
    sol = solve_pyvrp(
        solomon_path=_VRP_C101,
        max_customers=25,
        time_limit_s=3.0,
        problem_id="bench_c101_routes",
    )
    assert sol["routes"], "expected at least one route"
    capacity = sol["vehicle_capacity"]
    visited: list[str] = []
    for route in sol["routes"]:
        visits = route["visits"]
        # Depot -> clients -> depot with arrival-time chronology.
        assert visits[0]["type"] == "depot" and visits[-1]["type"] == "depot"
        for prev, curr in zip(visits, visits[1:]):
            assert curr["start_time"] >= prev["end_time"]
            assert curr["end_time"] >= curr["start_time"]
        # Vehicle load profile never exceeds capacity.
        assert route["load"] <= capacity
        running = 0
        for v in visits:
            if v["type"] == "client":
                running += int(v.get("demand", 0))
                assert running <= capacity
                visited.append(v["name"])
    # Every client served exactly once across the fleet.
    assert sorted(visited) == sorted(c["name"] for c in sol["raw_clients"])

    assert_validator_ok(validate_pyvrp, "bench_c101_routes", sol, PYVRP_CHECKS)


def test_pyvrp_pdp_demo_benchmark():
    """VRPPDTW: paired shipments, pickup-before-delivery, amount flow."""
    sol = solve_pyvrp(is_pdp=True, time_limit_s=2.0, problem_id="bench_pdp_demo")
    assert_envelope(sol, "pyvrp")
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert sol["num_shipments"] == 4
    assert sol["objective"] == sol["total_distance"] > 0

    checks = assert_validator_ok(
        validate_pyvrp, "bench_pdp_demo", sol, PYVRP_PDP_CHECKS
    )
    assert all(c["ok"] for c in checks)


def test_pyvrp_envelope_heuristic_bounds():
    """HGS is a heuristic: envelope carries None bounds (no invented numbers)."""
    sol = solve_pyvrp(is_pdp=True, time_limit_s=1.0, problem_id="bench_pdp_env")
    assert "lower_bound" in sol and "optimality_gap" in sol
    assert sol["lower_bound"] is None
    assert sol["optimality_gap"] is None
    assert_envelope(sol, "pyvrp")


# ===========================================================================
# Task 2.3 — RCPSP (activity schedule, resource profile, makespan bound)
# ===========================================================================
def test_rcpsp_j301_1_benchmark():
    sol = solve_rcpsp(time_limit_s=20)
    assert_envelope(sol, "rcpsp")
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == 43  # published PSPLib optimal makespan
    assert sol["known_optimum"] == 43
    assert sol["lower_bound"] == 43
    assert sol["optimality_gap"] == 0
    assert sol["num_activities"] == 32
    assert sol["num_resources"] == 4

    assert_validator_ok(validate_rcpsp, "rcpsp_j301_1_bench", sol, RCPSP_CHECKS)


def test_rcpsp_resource_usage_profile():
    """Renewable resource usage profile recomputed from the schedule."""
    sol = solve_rcpsp(time_limit_s=20)
    schedule = sol["schedule"]
    capacities = sol["resource_capacities"]
    horizon = max(e["end"] for e in schedule)
    for t in range(horizon):
        for r, cap in enumerate(capacities):
            used = sum(
                e["demands"][r]
                for e in schedule
                if e["start"] <= t < e["end"] and r < len(e["demands"])
            )
            assert used <= cap, f"t={t} R{r}: {used} > {cap}"
    # Critical path is a non-empty chain ending at the sink dummy.
    assert sol["critical_path"]
    assert sol["critical_path"][-1] == sol["num_activities"] - 1

    assert_validator_ok(validate_rcpsp, "rcpsp_j301_1_profile", sol, RCPSP_CHECKS)


def test_rcpsp_envelope_bounds_standardized():
    sol = solve_rcpsp(time_limit_s=20)
    assert_envelope(sol, "rcpsp")
    assert sol["lower_bound"] <= sol["objective"]
    assert sol["optimality_gap"] == sol["objective"] - sol["lower_bound"]


# ===========================================================================
# Task 2.4 — Facility (Beasley benchmarks, status, assignments, total cost)
# ===========================================================================
def test_facility_beasley_cap41_benchmark():
    data = load_orlibrary_cflp("cap41")
    assert data["known_optimum"] == 1040444.375  # Beasley capopt.txt reference
    sol = solve_facility_location(
        fixed_costs=data["fixed_costs"],
        capacities=data["capacities"],
        demands=data["demands"],
        cost_matrix=data["cost_matrix"],
        problem_id=data["problem_id"],
        known_optimum=data["known_optimum"],
        time_limit_s=30,
    )
    assert_envelope(sol, "facility_location")
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == pytest.approx(1040444.375, rel=1e-9, abs=1e-3)
    assert sol["known_optimum"] == 1040444.375
    assert sol["optimality_gap"] == 0

    assert_validator_ok(validate_facility_location, "cflp_cap41_bench", sol, FACILITY_CHECKS)


@pytest.mark.parametrize(
    "name,gold",
    [("cap61", 932615.75), ("cap71", 932615.75)],
)
def test_facility_beasley_benchmark_family(name, gold):
    data = load_orlibrary_cflp(name)
    sol = solve_facility_location(
        fixed_costs=data["fixed_costs"],
        capacities=data["capacities"],
        demands=data["demands"],
        cost_matrix=data["cost_matrix"],
        problem_id=data["problem_id"],
        known_optimum=data["known_optimum"],
        time_limit_s=30,
    )
    assert_envelope(sol, "facility_location")
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == pytest.approx(gold, rel=1e-9, abs=1e-3)
    assert sol["optimality_gap"] == 0

    assert_validator_ok(
        validate_facility_location, f"cflp_{name}_bench", sol, FACILITY_CHECKS
    )


def test_facility_status_assignments_and_total_cost():
    """Facility status, customer assignments and cost breakdown consistency."""
    sol = solve_facility_location(time_limit_s=30, problem_id="cflp_default_struct")
    assert_envelope(sol, "facility_location")
    assert sol["status"] == "OPTIMAL"
    assert sol["open_facilities"], "expected at least one open facility"
    for fac in sol["open_facilities"]:
        assert set(fac) >= {"facility_id", "capacity", "load", "utilization"}
        assert fac["load"] <= fac["capacity"] + 1e-6

    assert len(sol["allocations"]) == sol["num_customers"]
    for alloc in sol["allocations"]:
        frac = sum(s["fraction"] for s in alloc["served_by"])
        assert frac == pytest.approx(1.0, abs=1e-6)

    # Total cost = fixed + transport (Numbers Truth recomputation).
    assert sol["total_fixed_cost"] + sol["total_transport_cost"] == pytest.approx(
        sol["objective"], abs=1e-3
    )

    assert_validator_ok(
        validate_facility_location, "cflp_default_struct", sol, FACILITY_CHECKS
    )


def test_facility_sscflp_single_source():
    sol = solve_facility_location(
        single_source=True, time_limit_s=30, problem_id="cflp_ss_default"
    )
    assert_envelope(sol, "facility_location")
    assert sol["mode"] == "sscflp"
    assert sol["status"] == "OPTIMAL"
    assert_validator_ok(
        validate_facility_location,
        "cflp_ss_default",
        sol,
        FACILITY_CHECKS | {"single_source_binary"},
    )


# ===========================================================================
# Task 2.5 — Lot Sizing (periodic production, inventory balance, setups)
# ===========================================================================
def test_lot_sizing_ww12_benchmark():
    sol = solve_lot_sizing()
    assert_envelope(sol, "lot_sizing")
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == 670.0  # classic WW benchmark optimum
    assert sol["known_optimum"] == 670.0
    assert sol["lower_bound"] == 670.0
    assert sol["optimality_gap"] == 0
    assert sol["num_periods"] == 12

    assert_validator_ok(validate_lot_sizing, "lot_ww12_bench", sol, LOT_CHECKS)


def test_lot_sizing_periodic_production_and_balance():
    """Periodic production plan: flow balance + setup actions per period."""
    sol = solve_lot_sizing()
    schedule = sol["schedule"]
    demands = sol["raw_demands"]
    inv = 0.0
    for i, row in enumerate(schedule):
        assert row["period"] == i + 1
        assert row["demand"] == demands[i]
        # Flow balance: I_{t-1} + x_t - I_t == d_t
        assert inv + row["production"] - row["inventory"] == pytest.approx(demands[i])
        # Setup action iff production > 0
        assert bool(row["setup"]) == (row["production"] > 0)
        inv = row["inventory"]
    # Wagner-Whitin zero-order property: production only in setup periods.
    assert sol["setup_periods"]
    assert all(row["production"] == 0 for row in schedule if not row["setup"])
    # Production batches (first_period, last_period) cover the horizon.
    batches = sol["production_batches"]
    assert batches[0][0] == 1
    assert batches[-1][1] == 12

    assert_validator_ok(validate_lot_sizing, "lot_ww12_structure", sol, LOT_CHECKS)


def test_lot_sizing_clsp_mip_benchmark():
    """Capacitated variant (SCIP MIP): capacity + bounds + validation."""
    sol = solve_lot_sizing(
        method="mip",
        capacity=60.0,
        problem_id="lot_clsp60_bench",
        time_limit_s=20,
    )
    assert_envelope(sol, "lot_sizing")
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    # Capacitated optimum cannot be cheaper than the uncapacitated WW optimum.
    assert sol["objective"] >= 670.0
    if sol["status"] == "OPTIMAL":
        assert sol["optimality_gap"] == 0

    assert_validator_ok(
        validate_lot_sizing,
        "lot_clsp60_bench",
        sol,
        LOT_CHECKS | {"lot_sizing_capacity_respected"},
    )


def test_lot_sizing_mip_envelope_bounds():
    sol = solve_lot_sizing(
        demands=[10.0, 20.0, 15.0],
        setup_cost=50.0,
        holding_cost=1.0,
        method="mip",
        problem_id="lot_mini_env",
        time_limit_s=20,
    )
    assert_envelope(sol, "lot_sizing")
    assert sol["lower_bound"] <= sol["objective"] + 1e-6
    assert sol["optimality_gap"] == pytest.approx(
        sol["objective"] - sol["lower_bound"], abs=1e-4
    )

    assert_validator_ok(validate_lot_sizing, "lot_mini_env", sol, LOT_CHECKS)


# ===========================================================================
# Cross-domain — unified dispatch pipeline (envelope + validator integration)
# ===========================================================================
@pytest.mark.parametrize(
    "mode,problem_class",
    [
        ("jssp", "jssp"),
        ("pyvrp", "pyvrp"),
        ("rcpsp", "rcpsp"),
        ("facility_location", "facility_location"),
        ("lot_sizing", "lot_sizing"),
    ],
)
def test_dispatch_envelope_standardization(mode, problem_class):
    """All 5 domains flow through the unified pipeline with Phase 2 envelope."""
    from solve_dispatch import solve

    ok, sol, raw = solve(_ROOT, "test_prob", mode=mode)
    assert ok, f"Dispatch failed for {mode}: {raw}"
    assert sol["problem_class"] == problem_class
    assert_envelope(sol, problem_class)

    report = validate(f"dispatch_{mode}", sol)
    assert report["ok"], f"{mode}: validation failed -> {report['errors']}"
