"""Phase 2 / Task 2.5 — Lot Sizing: Wagner-Whitin DP & CLSP Multi-Period
Standardization (Numbers Truth).

Dedicated unit suite for tools/solve_lot_sizing.py against the classic
12-period Wagner-Whitin benchmark (known optimum = 670.0) and a capacitated
CLSP MIP variant (SCIP), asserting the standardized OR-Path envelope
(status / objective / lower_bound / optimality_gap / production / inventory
/ setup_actions / costs / metrics), the periodic material-balance
conservation equation ``I_t = I_{t-1} + x_t - d_t`` with ``I_t >= 0``,
setup binary consistency, per-period capacity limits, and full independent
re-verification through ``validate_lot_sizing`` from
tools/validators/extended_solvers.py.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from solve_lot_sizing import (  # noqa: E402
    BENCHMARK_DEMANDS,
    solve_lot_sizing,
)
from validators.extended_solvers import validate_lot_sizing  # noqa: E402

# Classic 12-period Wagner-Whitin benchmark, stated independently here so a
# regression in the solver's constant table cannot silently rewrite the gold.
WW_GOLD = 670.0  # setup 4 x 85 = 340 + holding 330

BASE_CHECKS = {
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
CLSP_CHECKS = BASE_CHECKS | {"lot_sizing_capacity_respected"}

ENVELOPE_KEYS = (
    "status",
    "objective",
    "lower_bound",
    "optimality_gap",
    "problem_id",
    "problem_class",
    "production",
    "inventory",
    "setup_actions",
    "costs",
    "metrics",
)


@pytest.fixture(scope="module")
def ww12():
    """Classic 12-period Wagner-Whitin benchmark solution."""
    return solve_lot_sizing(problem_id="lot_sizing_ww12")


@pytest.fixture(scope="module")
def clsp60():
    """Capacitated variant: same demands, per-period capacity 60."""
    return solve_lot_sizing(
        method="mip",
        capacity=60.0,
        problem_id="lot_sizing_clsp60",
        time_limit_s=30.0,
    )


def assert_validator_ok(problem_id: str, sol: dict, expected_checks: set[str]) -> list[dict]:
    """Run the domain validator directly; every check must be ok=True."""
    checks = validate_lot_sizing(problem_id, sol)
    bad = [c for c in checks if not c.get("ok")]
    assert not bad, f"{problem_id}: failing checks -> {bad}"
    names = {c["name"] for c in checks}
    missing = expected_checks - names
    assert not missing, f"{problem_id}: missing checks {sorted(missing)}"
    return checks


# ---------------------------------------------------------------------------
# 1. Wagner-Whitin 12-period benchmark (known optimum = 670.0)
# ---------------------------------------------------------------------------
def test_ww12_matches_known_optimum(ww12):
    sol = ww12
    assert sol["status"] == "OPTIMAL", f"status={sol['status']}"
    assert sol["objective"] == WW_GOLD, f"objective={sol['objective']} != {WW_GOLD}"
    assert sol["lower_bound"] == WW_GOLD, f"lower_bound={sol['lower_bound']} != {WW_GOLD}"
    assert sol["optimality_gap"] == 0.0, f"gap={sol['optimality_gap']!r}"
    # A negative zero would serialize as "-0.0" — the contract demands 0.0.
    assert str(sol["optimality_gap"]) == "0.0"
    assert sol["known_optimum"] == WW_GOLD


def test_ww12_cost_breakdown(ww12):
    """Optimal plan: 4 setups (340) + holding (330); batches cover the horizon."""
    sol = ww12
    assert sol["total_setup_cost"] == 340.0
    assert sol["total_holding_cost"] == 330.0
    assert sol["total_production_cost"] == 0.0
    assert sol["num_periods"] == 12
    assert sol["setup_periods"]
    batches = sol["production_batches"]
    assert batches[0][0] == 1
    assert batches[-1][1] == 12


def test_ww12_envelope_contract(ww12):
    sol = ww12
    for key in ENVELOPE_KEYS:
        assert key in sol, f"envelope missing key '{key}'"
    assert sol["problem_class"] == "lot_sizing"
    assert sol["problem_id"] == "lot_sizing_ww12"
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert isinstance(sol["objective"], float) and sol["objective"] > 0
    assert isinstance(sol["lower_bound"], float)
    assert isinstance(sol["optimality_gap"], float)
    # Bounds invariant: lb <= objective and gap == objective - lb.
    assert sol["lower_bound"] <= sol["objective"] + 1e-6
    assert abs(sol["optimality_gap"] - (sol["objective"] - sol["lower_bound"])) <= 1e-4


def test_ww12_flattened_views_agree_with_schedule(ww12):
    """production / inventory / setup_actions are the schedule flattened."""
    sol = ww12
    schedule = sol["schedule"]
    assert sol["production"] == [s["production"] for s in schedule]
    assert sol["inventory"] == [s["inventory"] for s in schedule]
    assert sol["setup_actions"] == [1 if s["setup"] else 0 for s in schedule]
    assert len(sol["production"]) == len(sol["inventory"]) == len(sol["setup_actions"]) == 12
    assert all(isinstance(v, int) for v in sol["setup_actions"])
    assert sol["costs"]["total"] == sol["objective"]
    assert sol["costs"]["setup"] == sol["total_setup_cost"]
    assert sol["costs"]["holding"] == sol["total_holding_cost"]
    assert sol["costs"]["total"] == round(
        sol["costs"]["setup"] + sol["costs"]["holding"] + sol["costs"]["production"], 6
    )
    assert sol["metrics"]["objective"] == sol["objective"]
    assert sol["metrics"]["lower_bound"] == sol["lower_bound"]
    assert sol["metrics"]["optimality_gap"] == sol["optimality_gap"]
    assert sol["metrics"]["proven_optimal"] is True


# ---------------------------------------------------------------------------
# 2. Periodic inventory balance conservation (all periods, both methods)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fixture", ["ww12", "clsp60"])
def test_material_balance_conservation(fixture, request):
    """I_t = I_{t-1} + x_t - d_t for every period; I_t >= 0 throughout."""
    sol = request.getfixturevalue(fixture)
    schedule = sol["schedule"]
    demands = sol["raw_demands"]
    inv_prev = float(sol["initial_inventory"])
    for i, row in enumerate(schedule):
        assert row["period"] == i + 1
        assert row["demand"] == pytest.approx(demands[i])
        # Flow balance: I_{t-1} + x_t - I_t == d_t
        assert inv_prev + row["production"] - row["inventory"] == pytest.approx(demands[i])
        # Non-negativity of ending inventory.
        assert row["inventory"] >= 0.0
        inv_prev = row["inventory"]
    # Final ending inventory is zero for the zero-initial-stock horizon.
    assert inv_prev == pytest.approx(0.0)


@pytest.mark.parametrize("fixture", ["ww12", "clsp60"])
def test_setup_binary_consistency(fixture, request):
    """production > 0 implies setup == 1 (and no setup without production)."""
    sol = request.getfixturevalue(fixture)
    for row in sol["schedule"]:
        if row["production"] > 1e-9:
            assert row["setup"] is True, f"period {row['period']}: x>0 but setup=False"
        else:
            assert row["setup"] is False, f"period {row['period']}: setup=True but x=0"
    assert all(a in (0, 1) for a in sol["setup_actions"])
    assert sol["setup_actions"] == [1 if s["setup"] else 0 for s in sol["schedule"]]


# ---------------------------------------------------------------------------
# 3. CLSP capacitated MIP benchmark
# ---------------------------------------------------------------------------
def test_clsp60_mip_benchmark(clsp60):
    sol = clsp60
    assert sol["status"] in ("OPTIMAL", "FEASIBLE"), f"status={sol['status']}"
    # Capacitated optimum cannot be cheaper than the uncapacitated WW optimum.
    assert sol["objective"] >= WW_GOLD
    if sol["status"] == "OPTIMAL":
        assert sol["optimality_gap"] == 0.0
        assert str(sol["optimality_gap"]) == "0.0"
    assert sol["lower_bound"] <= sol["objective"] + 1e-6
    assert abs(
        sol["optimality_gap"] - (sol["objective"] - sol["lower_bound"])
    ) <= 1e-4
    assert sol["capacity"] == 60.0


def test_clsp60_capacity_limits(clsp60):
    """production <= capacity * setup in every period."""
    sol = clsp60
    capacity = sol["capacity"]
    assert capacity is not None
    for row in sol["schedule"]:
        assert row["production"] <= capacity + 1e-9
        assert row["production"] <= capacity * (1 if row["setup"] else 0) + 1e-9


def test_clsp60_envelope_contract(clsp60):
    sol = clsp60
    for key in ENVELOPE_KEYS:
        assert key in sol, f"envelope missing key '{key}'"
    assert sol["problem_class"] == "lot_sizing"
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert sol["costs"]["total"] == sol["objective"]


# ---------------------------------------------------------------------------
# 4. Independent validation (tools/validators/extended_solvers.py)
# ---------------------------------------------------------------------------
def test_validate_lot_sizing_ww12_all_checks_ok(ww12):
    checks = assert_validator_ok("lot_sizing_ww12", ww12, BASE_CHECKS)
    names = {c["name"] for c in checks}
    assert "lot_sizing_capacity_respected" not in names  # no capacity in WW mode
    assert all(c["ok"] for c in checks)


def test_validate_lot_sizing_clsp60_all_checks_ok(clsp60):
    assert_validator_ok("lot_sizing_clsp60", clsp60, CLSP_CHECKS)


# ---------------------------------------------------------------------------
# 5. Robustness: method guards, mini instance, unit cost, -0.0 normalization
# ---------------------------------------------------------------------------
def test_ww_method_rejects_capacity_and_inventory_inputs():
    with pytest.raises(ValueError):
        solve_lot_sizing(method="ww", capacity=60.0)
    with pytest.raises(ValueError):
        solve_lot_sizing(method="ww", safety_stock=5.0)
    with pytest.raises(ValueError):
        solve_lot_sizing(method="ww", initial_inventory=10.0)
    with pytest.raises(ValueError):
        solve_lot_sizing(method="bogus")
    with pytest.raises(ValueError):
        solve_lot_sizing(demands=[-1.0, 2.0])


def test_mip_mini_instance_envelope_and_validation():
    sol = solve_lot_sizing(
        demands=[10.0, 20.0, 15.0],
        setup_cost=50.0,
        holding_cost=1.0,
        method="mip",
        problem_id="lot_mini_env",
        time_limit_s=20.0,
    )
    assert sol["status"] == "OPTIMAL"
    for key in ENVELOPE_KEYS:
        assert key in sol, f"envelope missing key '{key}'"
    assert sol["lower_bound"] <= sol["objective"] + 1e-6
    assert sol["optimality_gap"] == pytest.approx(
        sol["objective"] - sol["lower_bound"], abs=1e-4
    )
    assert_validator_ok("lot_mini_env", sol, BASE_CHECKS)


def test_mip_unit_cost_enters_objective_and_validation():
    sol = solve_lot_sizing(
        demands=[10.0, 20.0, 15.0],
        setup_cost=50.0,
        holding_cost=1.0,
        unit_cost=2.0,
        method="mip",
        problem_id="lot_unit_cost",
        time_limit_s=20.0,
    )
    assert sol["status"] == "OPTIMAL"
    assert sol["total_production_cost"] > 0.0
    assert sol["costs"]["production"] == sol["total_production_cost"]
    assert sol["costs"]["total"] == sol["objective"]
    assert_validator_ok("lot_unit_cost", sol, BASE_CHECKS)


def test_mip_optimal_gap_normalization_prevents_negative_zero():
    """Proven-optimal MIP: gap must be exactly +0.0, never "-0.0"."""
    sol = solve_lot_sizing(
        method="mip",
        capacity=60.0,
        problem_id="lot_gap_norm",
        time_limit_s=30.0,
    )
    assert sol["status"] == "OPTIMAL"
    assert sol["optimality_gap"] == 0.0
    assert str(sol["optimality_gap"]) == "0.0"
    assert repr(sol["optimality_gap"]) == "0.0"


def test_ww_matches_mip_on_uncapacitated_mini_instance():
    """WW DP and SCIP MIP agree on an uncapacitated 6-period instance."""
    demands = [10.0, 5.0, 20.0, 15.0, 5.0, 10.0]
    ww = solve_lot_sizing(demands=demands, setup_cost=85.0, holding_cost=1.0)
    mip = solve_lot_sizing(
        demands=demands,
        setup_cost=85.0,
        holding_cost=1.0,
        method="mip",
        problem_id="lot_ww_vs_mip",
        time_limit_s=30.0,
    )
    assert ww["status"] == "OPTIMAL"
    assert mip["status"] == "OPTIMAL"
    assert ww["objective"] == mip["objective"], (
        f"WW {ww['objective']} != MIP {mip['objective']}"
    )
