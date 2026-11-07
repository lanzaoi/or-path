#!/usr/bin/env python3
"""Unit tests for the reusable budget ledger engine (``orpath/agents/budget_engine.py``).

Covers:
  * loading and verifying ``experiments/tube/budget-ledger.json``.
  * structural edge cases: sum != 100, negatives, missing budget key, non-integers.
  * sub-budget sum verification.
  * risk-override application and release state transitions.
  * LangChain tool invocation and JSON output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.agents.budget_engine import (  # noqa: E402
    BudgetLedgerManager,
    audit_file,
    check_compliance,
    create_budget_check_tool,
    discover_sub_budgets,
    evaluate_risk_override,
    validate_ledger_structure,
)

TUBE_LEDGER = ROOT / "experiments" / "tube" / "budget-ledger.json"

TUBE_EXPECTED_BUDGET = {"geometry": 20, "q1_q2": 10, "q3": 25, "q4": 45}
TUBE_EXPECTED_Q4 = {
    "future_value_and_stratified_beam": 40,
    "remaining_demand_cocut_initializer": 25,
    "beam_width_and_new_seeds": 20,
    "targeted_deletion_repair": 10,
    "strict_validation_and_reproduction": 5,
}
TUBE_OVERRIDE_BUDGET = {"geometry": 35, "q1_q2": 10, "q3": 25, "q4": 30}


def _valid_ledger() -> dict:
    """A structurally valid ledger mirroring the Tube-B convention."""
    return {
        "schema": "orpath.demo_budget_ledger.v1",
        "budget_percent": dict(TUBE_EXPECTED_BUDGET),
        "q4_internal_budget_percent": dict(TUBE_EXPECTED_Q4),
        "risk_override_history": [],
        "current_phase": "active",
    }


# --------------------------------------------------------------------------- #
# Loading & verifying the real Tube ledger
# --------------------------------------------------------------------------- #

def test_load_and_verify_tube_ledger() -> None:
    manager = BudgetLedgerManager.from_file(
        TUBE_LEDGER,
        domain="tube",
        baseline_budget=TUBE_EXPECTED_BUDGET,
    )
    assert manager.load_error is None
    assert manager.validate()[0] is True

    report = manager.audit_file(TUBE_LEDGER, TUBE_EXPECTED_BUDGET, {"q4_internal_budget_percent": TUBE_EXPECTED_Q4})
    assert report["ok"] is True
    assert report["schema"] == "orpath.tube_budget_ledger.v1"
    assert report["compliance"]["budget_percent"] == TUBE_EXPECTED_BUDGET
    assert report["compliance"]["budget_sum"] == 100
    assert report["compliance"]["budget_matches_expected"] is True


def test_tube_ledger_sub_budget_discovered_and_valid() -> None:
    manager = BudgetLedgerManager.from_file(TUBE_LEDGER)
    assert "q4_internal_budget_percent" in discover_sub_budgets(manager.ledger)
    # The primary budget_percent is never treated as a sub-budget.
    assert "budget_percent" not in discover_sub_budgets(manager.ledger)

    report = manager.audit_file(
        TUBE_LEDGER,
        TUBE_EXPECTED_BUDGET,
        {"q4_internal_budget_percent": TUBE_EXPECTED_Q4},
    )
    q4 = report["compliance"]["sub_budgets"]["q4_internal_budget_percent"]
    assert q4["sum"] == 100
    assert q4["sum_ok"] is True
    assert q4["matches_expected"] is True


def test_audit_file_module_function_matches_manager() -> None:
    report = audit_file(
        TUBE_LEDGER,
        TUBE_EXPECTED_BUDGET,
        {"q4_internal_budget_percent": TUBE_EXPECTED_Q4},
    )
    assert report["ok"] is True
    assert report["validation"]["ok"] is True


# --------------------------------------------------------------------------- #
# Structural validation edge cases
# --------------------------------------------------------------------------- #

def test_validate_valid_ledger_passes() -> None:
    ok, errors = validate_ledger_structure(_valid_ledger())
    assert ok is True
    assert errors == []


@pytest.mark.parametrize(
    "budget",
    [
        {"geometry": 20, "q1_q2": 10, "q3": 25, "q4": 44},   # sum 99
        {"geometry": 20, "q1_q2": 10, "q3": 25, "q4": 46},   # sum 101
        {"geometry": 20, "q1_q2": 10, "q3": 25},              # missing key, sum 60
    ],
)
def test_budget_sum_not_100(budget: dict) -> None:
    ledger = _valid_ledger()
    ledger["budget_percent"] = budget
    ok, errors = validate_ledger_structure(ledger)
    assert ok is False
    assert any("sum to exactly 100" in e for e in errors)


@pytest.mark.parametrize("value", [-5, -1])
def test_negative_budget_rejected(value: int) -> None:
    ledger = _valid_ledger()
    ledger["budget_percent"]["geometry"] = value
    ok, errors = validate_ledger_structure(ledger)
    assert ok is False
    assert any("non-negative" in e for e in errors)


@pytest.mark.parametrize(
    "value",
    ["20", 20.5, True, None, [20], {"a": 1}],
)
def test_non_integer_budget_rejected(value: object) -> None:
    ledger = _valid_ledger()
    ledger["budget_percent"]["geometry"] = value
    ok, errors = validate_ledger_structure(ledger)
    assert ok is False
    assert any("integer percent" in e for e in errors)


def test_missing_budget_key_rejected() -> None:
    ledger = _valid_ledger()
    del ledger["budget_percent"]
    ok, errors = validate_ledger_structure(ledger)
    assert ok is False
    assert any("missing required key 'budget_percent'" in e for e in errors)


def test_empty_budget_rejected() -> None:
    ledger = _valid_ledger()
    ledger["budget_percent"] = {}
    ok, errors = validate_ledger_structure(ledger)
    assert ok is False
    assert any("must not be empty" in e for e in errors)


def test_non_dict_ledger_rejected() -> None:
    ok, errors = validate_ledger_structure(["not", "a", "dict"])
    assert ok is False
    assert errors == ["ledger must be a JSON object"]


# --------------------------------------------------------------------------- #
# Sub-budget sum verification
# --------------------------------------------------------------------------- #

def test_sub_budget_sum_not_100_rejected() -> None:
    ledger = _valid_ledger()
    ledger["q4_internal_budget_percent"]["future_value_and_stratified_beam"] = 39
    ok, errors = validate_ledger_structure(ledger)
    assert ok is False
    assert any("q4_internal_budget_percent' must sum to exactly 100" in e for e in errors)


def test_sub_budget_non_integer_rejected() -> None:
    ledger = _valid_ledger()
    ledger["q4_internal_budget_percent"]["targeted_deletion_repair"] = "10"
    ok, errors = validate_ledger_structure(ledger)
    assert ok is False
    assert any("q4_internal_budget_percent.targeted_deletion_repair" in e for e in errors)


def test_check_compliance_flags_missing_expected_sub_budget() -> None:
    ledger = _valid_ledger()
    del ledger["q4_internal_budget_percent"]
    report = check_compliance(
        ledger,
        TUBE_EXPECTED_BUDGET,
        {"q4_internal_budget_percent": TUBE_EXPECTED_Q4},
    )
    assert report["ok"] is False
    q4 = report["sub_budgets"]["q4_internal_budget_percent"]
    assert q4["sum"] == 0
    assert q4["sum_ok"] is False
    assert q4["matches_expected"] is False


def test_check_compliance_flags_mismatched_budget() -> None:
    ledger = _valid_ledger()
    ledger["budget_percent"]["geometry"] = 21
    ledger["budget_percent"]["q4"] = 44
    report = check_compliance(ledger, TUBE_EXPECTED_BUDGET)
    assert report["ok"] is False
    assert report["budget_matches_expected"] is False


def test_check_compliance_ok_when_expected_omitted() -> None:
    report = check_compliance(_valid_ledger())
    assert report["ok"] is True
    assert report["budget_matches_expected"] is True


# --------------------------------------------------------------------------- #
# Risk-override application and release state transitions
# --------------------------------------------------------------------------- #

def test_evaluate_risk_override_no_active_returns_baseline() -> None:
    active = [
        {"trigger": "t", "temporary_percent": TUBE_OVERRIDE_BUDGET, "released": True},
    ]
    effective = evaluate_risk_override(active, TUBE_EXPECTED_BUDGET, TUBE_OVERRIDE_BUDGET)
    assert effective == TUBE_EXPECTED_BUDGET


def test_evaluate_risk_override_active_applies_temporary() -> None:
    active = [
        {"trigger": "t", "temporary_percent": TUBE_OVERRIDE_BUDGET, "released": False},
    ]
    effective = evaluate_risk_override(active, TUBE_EXPECTED_BUDGET, TUBE_OVERRIDE_BUDGET)
    assert effective == TUBE_OVERRIDE_BUDGET
    assert all(isinstance(v, int) for v in effective.values())


def test_evaluate_risk_override_active_without_own_temp_uses_override_budget() -> None:
    active = [{"trigger": "t", "released": False}]
    effective = evaluate_risk_override(active, TUBE_EXPECTED_BUDGET, TUBE_OVERRIDE_BUDGET)
    assert effective == TUBE_OVERRIDE_BUDGET


def test_evaluate_risk_override_partial_temp_merges_baseline() -> None:
    active = [{"trigger": "t", "temporary_percent": {"geometry": 35}, "released": False}]
    effective = evaluate_risk_override(active, TUBE_EXPECTED_BUDGET, TUBE_OVERRIDE_BUDGET)
    assert effective["geometry"] == 35
    assert effective["q1_q2"] == 10
    assert effective["q3"] == 25
    assert effective["q4"] == 45


def test_manager_override_apply_and_release_transition() -> None:
    manager = BudgetLedgerManager(
        baseline_budget=TUBE_EXPECTED_BUDGET,
        override_budget=TUBE_OVERRIDE_BUDGET,
    )

    assert manager.effective_budget() == TUBE_EXPECTED_BUDGET
    assert manager.active_overrides() == []

    applied = manager.apply_override(
        trigger="geometry_gate_red",
        temporary_percent=TUBE_OVERRIDE_BUDGET,
        release_condition="geometry_gates_pass",
        evidence="outputs/tube-geometry-stability.json",
    )
    assert applied == TUBE_OVERRIDE_BUDGET
    assert len(manager.active_overrides()) == 1

    released = manager.release_override()
    assert released == TUBE_EXPECTED_BUDGET
    assert manager.active_overrides() == []


def test_manager_release_by_trigger() -> None:
    manager = BudgetLedgerManager(
        baseline_budget=TUBE_EXPECTED_BUDGET,
        override_budget=TUBE_OVERRIDE_BUDGET,
    )
    manager.apply_override("alpha", TUBE_OVERRIDE_BUDGET)
    manager.apply_override("beta", TUBE_OVERRIDE_BUDGET)
    released = manager.release_override(trigger="alpha")
    assert released == TUBE_OVERRIDE_BUDGET  # beta still active
    assert len(manager.active_overrides()) == 1
    assert manager.active_overrides()[0]["trigger"] == "beta"

    released = manager.release_override(trigger="beta")
    assert released == TUBE_EXPECTED_BUDGET
    assert manager.active_overrides() == []


def test_evaluate_risk_override_released_history_from_tube_ledger() -> None:
    manager = BudgetLedgerManager.from_file(TUBE_LEDGER)
    # The shipped ledger's override history is already released → baseline.
    assert manager.active_overrides() == []
    assert manager.effective_budget() == TUBE_EXPECTED_BUDGET


# --------------------------------------------------------------------------- #
# LangChain tool invocation and JSON output
# --------------------------------------------------------------------------- #

def test_create_budget_check_tool_invoke_tube_ledger() -> None:
    tool = create_budget_check_tool(
        domain="tube",
        expected_budget=TUBE_EXPECTED_BUDGET,
        expected_sub_budgets={"q4_internal_budget_percent": TUBE_EXPECTED_Q4},
        default_ledger_path=str(TUBE_LEDGER),
    )
    assert tool.name == "check_budget_ledger"

    raw = tool.invoke({"ledger_path": str(TUBE_LEDGER)})
    assert isinstance(raw, str)
    report = json.loads(raw)
    assert report["ok"] is True
    assert report["domain"] == "tube"
    assert report["compliance"]["budget_percent"] == TUBE_EXPECTED_BUDGET
    assert report["risk_override"]["active"] is False


def test_create_budget_check_tool_default_path() -> None:
    tool = create_budget_check_tool(
        domain="tube",
        expected_budget=TUBE_EXPECTED_BUDGET,
        expected_sub_budgets={"q4_internal_budget_percent": TUBE_EXPECTED_Q4},
        default_ledger_path="experiments/tube/budget-ledger.json",
    )
    raw = tool.invoke({})
    report = json.loads(raw)
    assert report["ok"] is True


def test_create_budget_check_tool_missing_file() -> None:
    tool = create_budget_check_tool(
        default_ledger_path="experiments/tube/does-not-exist.json",
    )
    raw = tool.invoke({})
    report = json.loads(raw)
    assert report["ok"] is False
    assert report["exists"] is False
    assert "not found" in report["error"]


def test_create_budget_check_tool_invalid_ledger(tmp_path: Path) -> None:
    bad = tmp_path / "bad-budget.json"
    bad.write_text(
        json.dumps({"budget_percent": {"geometry": 20, "q1_q2": 10, "q3": 25, "q4": 40}}),
        encoding="utf-8",
    )
    tool = create_budget_check_tool(default_ledger_path=str(bad))
    report = json.loads(tool.invoke({"ledger_path": str(bad)}))
    assert report["ok"] is False
    assert report["compliance"]["budget_sum"] == 95
    assert report["compliance"]["budget_sum_ok"] is False


# --------------------------------------------------------------------------- #
# Robustness: percent coercion must not silently truncate or crash.
# --------------------------------------------------------------------------- #
def test_evaluate_risk_override_preserves_non_integer_floats() -> None:
    """A 33.9 share must survive unchanged, not be silently truncated to 33."""
    baseline = {"geometry": 33.9, "q4": 66.1}
    result = evaluate_risk_override(None, baseline)
    assert result["geometry"] == 33.9
    assert result["q4"] == 66.1


def test_evaluate_risk_override_coerces_exact_floats_and_strings() -> None:
    baseline = {"a": 33.0, "b": "25", "c": 42}
    result = evaluate_risk_override(None, baseline)
    assert result == {"a": 33, "b": 25, "c": 42}


def test_evaluate_risk_override_tolerates_none_and_garbage() -> None:
    """None / non-numeric values pass through instead of raising TypeError."""
    baseline = {"a": None, "b": [1, 2], "c": 100}
    result = evaluate_risk_override(None, baseline)
    assert result["a"] is None
    assert result["b"] == [1, 2]
    assert result["c"] == 100


def test_evaluate_risk_override_active_merge_preserves_partial_types() -> None:
    baseline = {"geometry": 40, "q4": 60}
    override = [{"trigger": "risk", "temporary_percent": {"geometry": 55.5}}]
    result = evaluate_risk_override(override, baseline)
    assert result["geometry"] == 55.5
    assert result["q4"] == 60

