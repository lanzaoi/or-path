#!/usr/bin/env python3
"""Phase 3 / Task 3.1 — Cutting & Packing team refactor + hardening tests.

Covers the Phase 3.1 deliverables:

1. ``orpath/agents/domains/tube.py`` wires the Phase 1 foundation modules
   (``guard_factory``, ``domain_state``, ``budget_engine``) while keeping every
   public constant, prompt and agent factory backward compatible.
2. ``scripts/tube_redteam_gate.py`` never crashes on an unexpected solution
   schema; it fails safely with a structured report instead.
3. The 6-role Tube-B cutting team still builds and enforces its pipeline order.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

from orpath.agents.budget_engine import (  # noqa: E402
    BudgetLedgerManager,
    audit_file,
    evaluate_risk_override,
)
from orpath.agents.domain_state import (  # noqa: E402
    DomainSupervisorState,
    get_state_stage_progress,
)
from orpath.agents.domains.tube import (  # noqa: E402
    DEFAULT_TUBE_LEAD_PROMPT,
    GEOMETRY_PROMPT,
    Q1Q2_PROMPT,
    Q3_PROMPT,
    Q4_PROMPT,
    REDTEAM_PROMPT,
    TUBE_ALL_AGENT_NAMES,
    TUBE_DISCRETIONARY_BUDGET,
    TUBE_GEOMETRY_NAME,
    TUBE_GUARD_CALL_IDS,
    TUBE_LEAD_NAME,
    TUBE_PIPELINE_STAGE_ORDER,
    TUBE_Q1Q2_NAME,
    TUBE_Q3_NAME,
    TUBE_Q4_NAME,
    TUBE_Q4_INTERNAL_BUDGET,
    TUBE_REDTEAM_NAME,
    TUBE_RISK_OVERRIDE_BUDGET,
    TUBE_WORKER_NAMES,
    TubeSupervisorState,
    check_tube_budget_ledger,
    create_tube_geometry_agent,
    create_tube_lead_agent,
    create_tube_q1q2_agent,
    create_tube_q3_agent,
    create_tube_q4_agent,
    create_tube_redteam_agent,
    get_tube_workers,
    tube_guard_post_hook,
)
from orpath.agents.guard_factory import create_domain_guard_hook  # noqa: E402
from orpath.control_plane import get_chat_model  # noqa: E402

import tube_redteam_gate as redteam_gate  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore:create_react_agent has been moved")

TUBE_LEDGER = ROOT / "experiments" / "tube" / "budget-ledger.json"


@pytest.fixture()
def model() -> Any:
    return get_chat_model()


@pytest.fixture(scope="module")
def strict_envelope() -> dict[str, Any]:
    """A ``synthetic_tube`` solution the strict validator accepts."""
    from test_tube_optimization import strict_envelope as _build

    envelope, _validate = _build()
    return envelope


# --------------------------------------------------------------------------- #
# 1. Six-role cutting team
# --------------------------------------------------------------------------- #

def test_cutting_team_six_role_roster() -> None:
    assert TUBE_WORKER_NAMES == (
        TUBE_GEOMETRY_NAME,
        TUBE_Q1Q2_NAME,
        TUBE_Q3_NAME,
        TUBE_Q4_NAME,
        TUBE_REDTEAM_NAME,
    )
    assert TUBE_ALL_AGENT_NAMES == (TUBE_LEAD_NAME, *TUBE_WORKER_NAMES)
    assert len(TUBE_ALL_AGENT_NAMES) == 6
    assert TUBE_PIPELINE_STAGE_ORDER == TUBE_WORKER_NAMES
    assert set(TUBE_GUARD_CALL_IDS) == set(TUBE_WORKER_NAMES)


def test_cutting_team_all_six_agents_creable(model: Any) -> None:
    lead = create_tube_lead_agent(model=model)
    assert lead.name == TUBE_LEAD_NAME

    assert create_tube_geometry_agent(model=model).name == TUBE_GEOMETRY_NAME
    assert create_tube_q1q2_agent(model=model).name == TUBE_Q1Q2_NAME
    assert create_tube_q3_agent(model=model).name == TUBE_Q3_NAME
    assert create_tube_q4_agent(model=model).name == TUBE_Q4_NAME
    assert create_tube_redteam_agent(model=model).name == TUBE_REDTEAM_NAME

    workers = get_tube_workers(model=model)
    assert [w.name for w in workers] == list(TUBE_WORKER_NAMES)


def test_cutting_team_prompts_unchanged() -> None:
    for prompt in (
        DEFAULT_TUBE_LEAD_PROMPT,
        GEOMETRY_PROMPT,
        Q1Q2_PROMPT,
        Q3_PROMPT,
        Q4_PROMPT,
        REDTEAM_PROMPT,
    ):
        assert isinstance(prompt, str) and len(prompt) > 50


# --------------------------------------------------------------------------- #
# 2. TubeSupervisorState inherits the Phase 1 domain state
# --------------------------------------------------------------------------- #

def test_tube_supervisor_state_inherits_domain_supervisor_state() -> None:
    # TypedDict classes reject ``issubclass``/``isinstance``; the canonical way
    # to assert the inheritance is ``__orig_bases__``.
    assert TubeSupervisorState.__orig_bases__ == (DomainSupervisorState,)


def test_tube_supervisor_state_keeps_tube_specific_fields() -> None:
    from typing import get_type_hints

    hints = get_type_hints(TubeSupervisorState)
    for flag in (
        "has_geometry_audited",
        "has_q1q2_solved",
        "has_q3_solved",
        "has_q4_solved",
        "has_redteam_verified",
    ):
        assert flag in hints and hints[flag] is bool
    assert hints["geometry_stability_report_path"] is str
    assert hints["domain"] is str
    assert hints["problem_id"] is str


def test_tube_supervisor_state_inherits_canonical_fields() -> None:
    from typing import get_type_hints

    base_fields = set(get_type_hints(DomainSupervisorState))
    tube_hints = get_type_hints(TubeSupervisorState)

    for field in (
        "assumption_register_path",
        "budget_ledger_path",
        "candidate_solution_path",
        "validation_report_path",
        "redteam_report_path",
        "audit_report_path",
        "experiment_card_paths",
        "audit_passed",
        "lower_bound_fixed",
        "incumbent_solved",
        "realities_applied",
        "redteam_passed",
    ):
        assert field in tube_hints, f"TubeSupervisorState lost inherited {field}"
        assert field in base_fields

    # Tube defaults are visible without instantiating the TypedDict.
    assert TubeSupervisorState.__annotations__["domain"] is not None
    assert TubeSupervisorState.__dict__["domain"] == "tube"
    assert TubeSupervisorState.__dict__["problem_id"] == "tube_cut_b2026"


def test_tube_state_stage_progress_is_readable() -> None:
    # Explicit canonical flags recognised by STAGE_FLAG_KEY_TEMPLATES.
    state = TubeSupervisorState(
        messages=[HumanMessage("run")],
        domain="tube",
        or_tube_geometry=True,
        or_tube_q1q2=True,
    )
    progress = get_state_stage_progress(state, TUBE_PIPELINE_STAGE_ORDER)
    assert progress["domain"] == "tube"
    assert progress["total_stages"] == 5
    assert progress["completed_count"] == 2
    assert progress["next_stage"] == TUBE_Q3_NAME
    assert 0.0 < progress["progress"] < 1.0

    # Transcript fallback: a worker reply counts as that stage being handed off.
    transcript = TubeSupervisorState(
        messages=[HumanMessage("run"), AIMessage("g", name=TUBE_GEOMETRY_NAME)]
    )
    fallback = get_state_stage_progress(transcript, TUBE_PIPELINE_STAGE_ORDER)
    assert fallback["completed_count"] == 1
    assert fallback["next_stage"] == TUBE_Q1Q2_NAME


# --------------------------------------------------------------------------- #
# 3. Tube guard hook is the guard_factory product
# --------------------------------------------------------------------------- #

def test_tube_guard_hook_is_built_by_guard_factory() -> None:
    assert tube_guard_post_hook.__name__ == "domain_guard_post_hook"

    fresh = create_domain_guard_hook(TUBE_PIPELINE_STAGE_ORDER, TUBE_GUARD_CALL_IDS)
    states = [
        {"messages": []},
        {"messages": [HumanMessage("start")]},
        {"messages": [HumanMessage("run"), AIMessage("done", id="m1")]},
        {
            "messages": [
                HumanMessage("run"),
                AIMessage("g", name=TUBE_GEOMETRY_NAME),
                AIMessage("done", id="m2"),
            ]
        },
    ]
    for state in states:
        assert tube_guard_post_hook(state) == fresh(state)


def test_tube_guard_hook_enforces_sequential_stage_order() -> None:
    # Empty / non-AI / already-routing states pass through untouched.
    assert tube_guard_post_hook({"messages": []}) == {}
    assert tube_guard_post_hook({"messages": [HumanMessage("start")]}) == {}
    assert tube_guard_post_hook(
        {"messages": [AIMessage("routing", tool_calls=[{"name": "x", "args": {}, "id": "c"}])]}
    ) == {}

    def bare(messages: list[Any]) -> str:
        update = tube_guard_post_hook({"messages": messages})
        assert update, f"guard did not act on {messages!r}"
        injected = update["messages"][-1]
        assert injected.tool_calls[0]["id"] in TUBE_GUARD_CALL_IDS.values()
        return injected.tool_calls[0]["name"]

    # Stage 1: nothing done yet -> geometry.
    assert bare([HumanMessage("run"), AIMessage("done", id="m1")]) == (
        "transfer_to_or_tube_geometry"
    )

    # Stage 2: geometry done -> q1q2 (a *later* stage being done must not skip
    # the first missing one).
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("g", name=TUBE_GEOMETRY_NAME),
            AIMessage("r", name=TUBE_REDTEAM_NAME),
            AIMessage("done", id="m2"),
        ]
    ) == "transfer_to_or_tube_q1q2"

    # Stage 3: geometry + q1q2 done -> q3.
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("g", name=TUBE_GEOMETRY_NAME),
            AIMessage("12", name=TUBE_Q1Q2_NAME),
            AIMessage("done", id="m3"),
        ]
    ) == "transfer_to_or_tube_q3"

    # Stage 4: geometry + q1q2 + q3 done -> q4.
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("g", name=TUBE_GEOMETRY_NAME),
            AIMessage("12", name=TUBE_Q1Q2_NAME),
            AIMessage("3", name=TUBE_Q3_NAME),
            AIMessage("done", id="m4"),
        ]
    ) == "transfer_to_or_tube_q4"

    # Stage 5: four stages done -> redteam.
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("g", name=TUBE_GEOMETRY_NAME),
            AIMessage("12", name=TUBE_Q1Q2_NAME),
            AIMessage("3", name=TUBE_Q3_NAME),
            AIMessage("4", name=TUBE_Q4_NAME),
            AIMessage("done", id="m5"),
        ]
    ) == "transfer_to_or_tube_redteam"

    # Stage 6: every stage handed off -> bare reply is allowed.
    assert tube_guard_post_hook(
        {
            "messages": [
                HumanMessage("run"),
                AIMessage("g", name=TUBE_GEOMETRY_NAME),
                AIMessage("12", name=TUBE_Q1Q2_NAME),
                AIMessage("3", name=TUBE_Q3_NAME),
                AIMessage("4", name=TUBE_Q4_NAME),
                AIMessage("rt", name=TUBE_REDTEAM_NAME),
                AIMessage("completed", id="m6"),
            ]
        }
    ) == {}


# --------------------------------------------------------------------------- #
# 4. Budget checking through BudgetLedgerManager
# --------------------------------------------------------------------------- #

def test_budget_ledger_manager_audits_tube_ledger() -> None:
    assert TUBE_LEDGER.is_file(), "golden Tube budget ledger is missing"
    report = audit_file(
        TUBE_LEDGER,
        expected_budget=TUBE_DISCRETIONARY_BUDGET,
        expected_sub_budgets={"q4_internal_budget_percent": TUBE_Q4_INTERNAL_BUDGET},
        root=ROOT,
    )
    assert report["ok"] is True
    assert report["validation"]["ok"] is True
    assert report["compliance"]["budget_percent"] == TUBE_DISCRETIONARY_BUDGET
    assert report["compliance"]["budget_sum"] == 100
    assert report["risk_override"]["active"] is False


def test_budget_ledger_manager_rejects_drift() -> None:
    ledger = json.loads(TUBE_LEDGER.read_text(encoding="utf-8"))
    ledger["budget_percent"] = {"geometry": 21, "q1_q2": 10, "q3": 25, "q4": 45}
    ok, errors = BudgetLedgerManager(ledger=ledger).validate()
    assert ok is False
    assert any("budget_percent" in error for error in errors)


def test_budget_ledger_manager_tracks_risk_override_lifecycle() -> None:
    manager = BudgetLedgerManager(
        domain="tube",
        ledger={"budget_percent": dict(TUBE_DISCRETIONARY_BUDGET)},
        baseline_budget=TUBE_DISCRETIONARY_BUDGET,
        override_budget=TUBE_RISK_OVERRIDE_BUDGET,
    )
    # Baseline, no override.
    assert manager.effective_budget() == TUBE_DISCRETIONARY_BUDGET

    # Activate the geometry risk override.
    effective = manager.apply_override(
        trigger="geometry_gate_red",
        temporary_percent=TUBE_RISK_OVERRIDE_BUDGET,
        release_condition="geometry_gate_green",
        evidence="outputs/tube-geometry-stability.json",
    )
    assert effective == TUBE_RISK_OVERRIDE_BUDGET
    assert manager.active_overrides()

    # Release -> back to baseline.
    assert manager.release_override() == TUBE_DISCRETIONARY_BUDGET
    assert manager.active_overrides() == []


def test_evaluate_risk_override_helper() -> None:
    assert evaluate_risk_override([], TUBE_DISCRETIONARY_BUDGET) == TUBE_DISCRETIONARY_BUDGET
    assert evaluate_risk_override(
        [{"trigger": "t", "released": True}], TUBE_DISCRETIONARY_BUDGET
    ) == TUBE_DISCRETIONARY_BUDGET
    assert evaluate_risk_override(
        [{"trigger": "t", "temporary_percent": TUBE_RISK_OVERRIDE_BUDGET}],
        TUBE_DISCRETIONARY_BUDGET,
    ) == TUBE_RISK_OVERRIDE_BUDGET


def test_check_tube_budget_ledger_tool_is_backward_compatible() -> None:
    result = json.loads(check_tube_budget_ledger.invoke({}))
    assert result["ok"] is True
    assert result["budget_percent"] == {"geometry": 20, "q1_q2": 10, "q3": 25, "q4": 45}
    assert result["budget_matches_protocol"] is True
    assert result["q4_budget_matches_protocol"] is True
    assert result["total_budget_sum"] == 100
    # The Phase 1 engine audit is embedded for richer callers.
    assert result["audit"]["ok"] is True
    assert result["audit"]["compliance"]["budget_sum"] == 100


def test_check_tube_budget_ledger_tool_handles_missing_ledger(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    result = json.loads(check_tube_budget_ledger.invoke({"ledger_path": str(missing)}))
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_check_tube_budget_ledger_tool_handles_malformed_ledger(tmp_path: Path) -> None:
    broken = tmp_path / "ledger.json"
    broken.write_text("[1, 2, 3]", encoding="utf-8")
    result = json.loads(check_tube_budget_ledger.invoke({"ledger_path": str(broken)}))
    assert result["ok"] is False
    assert "JSON object" in result["error"]


# --------------------------------------------------------------------------- #
# 5. Red-team gate robustness
# --------------------------------------------------------------------------- #

MALFORMED_SOLUTIONS: tuple[Any, ...] = (
    None,
    "not-a-dict",
    42,
    [],
    {},
    {"questions": "not-an-object"},
    {"questions": None},
    {"questions": {"q2": {}}},
    {"questions": {"q2": {"stocks": []}}, "model_snapshot": {}},
    {"questions": {"q3": {"stocks": []}}},
    {"questions": {"q3": {"stocks": [None]}}},
    {"questions": {"q4": {}}},
    {"questions": {"q4": {"batches": []}}},
    {"questions": {"q4": {"batches": [{}]}}},
    {"questions": {"q4": {"batches": [None, "x"]}}},
    {"questions": {"q4": {"batches": [{"result": {}}]}}},
    {"questions": {"q4": {"batches": [{"result": {"inventory_before": "nope"}}]}}},
    {"questions": {"q4": {"batches": [{"result": {"inventory_before": []}}]}}},
    {"questions": {"q4": {"batches": [{"result": {"inventory_after": []}}]}}},
    {"questions": {"q4": {"total_new_standard_stock_mm": "nope"}}},
    {"model_snapshot": {}},
    {"model_snapshot": {"input_sha256": []}},
    {"model_snapshot": {"input_sha256": {}}},
    {"model_snapshot": {"input_sha256": {"a": 1}}},
    {"model_snapshot": "not-an-object"},
)


@pytest.mark.parametrize("solution", MALFORMED_SOLUTIONS)
def test_redteam_build_attacks_never_raises_on_malformed_solution(solution: Any) -> None:
    attacks = redteam_gate.build_attacks(solution)
    assert [row["attack"] for row in attacks] == list(redteam_gate.ATTACK_NAMES)
    for row in attacks:
        assert isinstance(row["applied"], bool)
        if not row["applied"]:
            # An unapplied attack must explain itself, never raise.
            assert isinstance(row["reason"], str) and row["reason"]


def test_redteam_build_attacks_does_not_mutate_input(strict_envelope: dict[str, Any]) -> None:
    before = deepcopy(strict_envelope)
    redteam_gate.build_attacks(strict_envelope)
    assert strict_envelope == before


EMPTY_SOLUTIONS: tuple[Any, ...] = (
    None,
    "not-a-dict",
    42,
    [],
    {},
    {"questions": "not-an-object"},
    {"questions": None},
    {"model_snapshot": {}},
)


@pytest.mark.parametrize("solution", EMPTY_SOLUTIONS)
def test_redteam_build_attacks_unapplied_on_empty_solution(solution: Any) -> None:
    attacks = redteam_gate.build_attacks(solution)
    assert all(row["applied"] is False for row in attacks)


@pytest.mark.parametrize("solution", MALFORMED_SOLUTIONS)
def test_redteam_run_redteam_never_raises_on_malformed_solution(solution: Any) -> None:
    report = redteam_gate.run_redteam(solution)
    assert report["ok"] is False
    assert report["schema"] == "orpath.tube_redteam.v1"
    assert report["original_recompute_ok"] is False
    assert report["attack_count"] == len(redteam_gate.ATTACK_NAMES)
    assert 0 <= report["attacks_applied"] <= 5
    for row in report["attacks"]:
        if row["applied"]:
            assert isinstance(row["failed_checks"], list)
        else:
            assert row["rejected"] is False
            assert isinstance(row["reason"], str) and row["reason"]


def test_redteam_build_attacks_all_applied_on_strict_envelope(
    strict_envelope: dict[str, Any],
) -> None:
    attacks = redteam_gate.build_attacks(strict_envelope)
    assert len(attacks) == 5
    assert all(row["applied"] for row in attacks), [
        (row["attack"], row["reason"]) for row in attacks
    ]
    assert all(row["reason"] is None for row in attacks)
    # Payloads are deep copies: the frozen solution is never mutated.
    assert strict_envelope["questions"]["q3"]["stocks"][0]["sequence"]


def test_redteam_run_redteam_blocks_numeric_and_inventory_tampering(
    strict_envelope: dict[str, Any],
) -> None:
    report = redteam_gate.run_redteam(strict_envelope, "synthetic_tube")
    assert report["original_recompute_ok"] is True
    assert report["attacks_applied"] == 5

    by_name = {row["attack"]: row for row in report["attacks"]}
    for name in (
        "numeric_cocut_inflation",
        "q3_demand_deletion",
        "q4_inventory_injection",
        "invalid_lower_bound_claim",
    ):
        row = by_name[name]
        assert row["applied"] is True
        assert row["rejected"] is True, f"{name} was not blocked: {row['failed_checks']}"
        assert row["failed_checks"]

    # ``input_hash_tamper`` is applied but, for a ``synthetic://`` manifest the
    # strict validator deliberately does not re-hash URIs, so the gate reports
    # it honestly as unverified instead of pretending it was blocked.
    hash_row = by_name["input_hash_tamper"]
    assert hash_row["applied"] is True
    assert hash_row["rejected"] is False
    assert report["ok"] is False


def test_redteam_recompute_rejects_non_dict_payload() -> None:
    for payload in (None, "x", 42, [], {}):
        report = redteam_gate.recompute("synthetic_tube", payload)
        assert report["ok"] is False
        assert report["checks"] == []


def test_redteam_cli_rejects_malformed_solution_without_crashing(tmp_path: Path) -> None:
    solution = tmp_path / "solution.json"
    solution.write_text(
        json.dumps({"questions": {"q4": {"batches": [{"result": {}}]}}}), encoding="utf-8"
    )
    out = tmp_path / "redteam.json"

    exit_code = redteam_gate.main(["--solution", str(solution), "--out", str(out)])

    assert exit_code == 1
    assert out.is_file()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema"] == "orpath.tube_redteam.v1"
    assert report["ok"] is False
    assert report["solution_path"] == str(solution.resolve())


def test_redteam_cli_missing_solution_returns_failure(tmp_path: Path) -> None:
    out = tmp_path / "redteam.json"
    exit_code = redteam_gate.main(
        ["--solution", str(tmp_path / "absent.json"), "--out", str(out)]
    )
    assert exit_code == 1
    assert not out.exists()


def test_redteam_cli_invalid_json_returns_failure(tmp_path: Path) -> None:
    solution = tmp_path / "broken.json"
    solution.write_text("{not json", encoding="utf-8")
    exit_code = redteam_gate.main(
        ["--solution", str(solution), "--out", str(tmp_path / "redteam.json")]
    )
    assert exit_code == 1


def test_redteam_cli_writes_structured_report_for_strict_envelope(
    tmp_path: Path, strict_envelope: dict[str, Any]
) -> None:
    solution = tmp_path / "synthetic_tube-solution.json"
    solution.write_text(json.dumps(strict_envelope), encoding="utf-8")
    out = tmp_path / "redteam.json"

    exit_code = redteam_gate.main(["--solution", str(solution), "--out", str(out)])

    assert out.is_file()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema"] == "orpath.tube_redteam.v1"
    assert report["problem_id"] == "synthetic_tube"
    assert report["original_recompute_ok"] is True
    assert report["attack_count"] == 5
    # Synthetic URI manifests are not re-hashed, so the gate fails honestly.
    assert report["ok"] is False
    assert exit_code == 1


def test_redteam_cli_passes_when_every_attack_is_blocked(
    tmp_path: Path,
    strict_envelope: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate verdict is the conjunction of the original check and the attacks.

    A ``synthetic://`` hash manifest is deliberately not re-hashed by the strict
    validator, so ``input_hash_tamper`` cannot be blocked there.  Patch
    ``recompute`` to reject every *attack payload* so the PASS branch of the
    gate is exercised end to end without faking the validator itself.
    """
    real_recompute = redteam_gate.recompute
    seen_original = {"done": False}

    def fake_recompute(problem_id: str, payload: Any) -> dict[str, Any]:
        report = real_recompute(problem_id, payload)
        if not report.get("ok"):
            return report
        # ``run_redteam`` recomputes the frozen solution first; everything after
        # that is an injected payload and must be reported as blocked.
        if seen_original["done"]:
            report = dict(report, ok=False, errors=["tamper injected"])
        else:
            seen_original["done"] = True
        return report

    monkeypatch.setattr(redteam_gate, "recompute", fake_recompute)

    solution = tmp_path / "solution.json"
    solution.write_text(json.dumps(strict_envelope), encoding="utf-8")
    out = tmp_path / "redteam.json"

    exit_code = redteam_gate.main(["--solution", str(solution), "--out", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))

    assert report["original_recompute_ok"] is True
    assert report["ok"] is True
    assert all(row["rejected"] for row in report["attacks"])
    assert exit_code == 0
