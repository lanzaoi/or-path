#!/usr/bin/env python3
"""Phase 3 / Task 3.3 — JSSP Scheduling team + hardening tests.

Covers the Phase 3.3 deliverables:

1. ``contracts/scheduling_collaboration_v1.json`` validates against the Domain
   Collaboration meta-schema.
2. ``orpath/agents/domains/scheduling.py`` wires the Phase 1 foundation modules
   (``guard_factory``, ``domain_state``, ``budget_engine``) while keeping the
   Lead + Pentad pattern verified in ``tube.py`` / ``routing.py``.
3. ``scripts/scheduling_redteam_gate.py`` never crashes on an unexpected
   solution schema; it fails safely with a structured report instead.
4. The 6-role scheduling team builds and enforces its pipeline order, and the
   5 DIMO tamper attacks are all rejected by the independent red-team gate on
   a real FT06 (and a changeover-delay) CP-SAT solution.
"""
from __future__ import annotations

import json
import re
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
from langchain_core.runnables import Runnable  # noqa: E402
from langgraph.graph.state import CompiledStateGraph, StateGraph  # noqa: E402

from orpath.agents.budget_engine import (  # noqa: E402
    BudgetLedgerManager,
    audit_file,
    evaluate_risk_override,
)
from orpath.agents.domain_state import (  # noqa: E402
    DomainSupervisorState,
    get_state_stage_progress,
)
from orpath.agents.domains.scheduling import (  # noqa: E402
    DEFAULT_JSSP_LEAD_PROMPT,
    JSSP_AUDITOR_NAME,
    JSSP_AUDITOR_PROMPT,
    JSSP_CANDIDATE_LIFECYCLE,
    JSSP_DISCRETIONARY_BUDGET,
    JSSP_EXACT_BOUND_NAME,
    JSSP_EXACT_BOUND_PROMPT,
    JSSP_GUARD_CALL_IDS,
    JSSP_HEURISTIC_NAME,
    JSSP_HEURISTIC_PROMPT,
    JSSP_LEAD_NAME,
    JSSP_OBJECTIVE_ORDER,
    JSSP_PIPELINE_STAGE_ORDER,
    JSSP_REALITY_NAME,
    JSSP_REALITY_PROMPT,
    JSSP_REDTEAM_NAME,
    JSSP_REDTEAM_PROMPT,
    JSSP_RISK_OVERRIDE_BUDGET,
    JSSP_TAMPER_TESTS,
    JSSP_WORKER_NAMES,
    SchedulingSupervisorState,
    check_scheduling_budget_ledger,
    create_jssp_auditor_agent,
    create_jssp_exact_bound_agent,
    create_jssp_heuristic_agent,
    create_jssp_lead_agent,
    create_jssp_realities_agent,
    create_jssp_redteam_agent,
    get_jssp_workers,
    scheduling_guard_post_hook,
    run_scheduling_collaboration_gate,
    run_scheduling_redteam_gate,
    validate_scheduling_contract,
)
from orpath.agents.guard_factory import create_domain_guard_hook  # noqa: E402
from orpath.control_plane import get_chat_model  # noqa: E402

import scheduling_redteam_gate as redteam_gate  # noqa: E402
from solve_jssp import solve_jssp  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore:create_react_agent has been moved")

META_SCHEMA_PATH = ROOT / "contracts" / "meta" / "domain_collaboration.schema.json"
SCHEDULING_CONTRACT_PATH = ROOT / "contracts" / "scheduling_collaboration_v1.json"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture()
def model() -> Any:
    return get_chat_model()


@pytest.fixture(scope="module", autouse=True)
def scheduling_golden_ledger() -> Path:
    """Provision the (gitignored) golden scheduling budget ledger for tool tests."""
    path = ROOT / "experiments" / "scheduling" / "budget-ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger = {
        "schema": "orpath.scheduling_budget_ledger.v1",
        "date": "2026-01-01",
        "scope": "discretionary_experiment_effort_excluding_baseline_and_gates",
        "budget_percent": dict(JSSP_DISCRETIONARY_BUDGET),
    }
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def ft06_solution() -> dict[str, Any]:
    """Real CP-SAT solution of Fisher-Thompson FT06 (6x6, published optimum 55)."""
    return solve_jssp("ft06", time_limit_s=30)


@pytest.fixture(scope="module")
def ft06_setup_solution() -> dict[str, Any]:
    """Real CP-SAT solution of FT06 with a uniform changeover delay (换模时延 = 2)."""
    return solve_jssp("ft06", setup=2, time_limit_s=30)


class MockChatModel(Runnable):
    """Deterministic offline stand-in LLM for supervisor pipeline execution.

    Every call returns a bare ``AIMessage`` with no ``tool_calls``.  The
    scheduling guard hook then re-routes the lead to the next missing pipeline
    stage, so a full 5-worker handoff sequence is driven without any network.
    """

    def __init__(self) -> None:
        self.calls = 0

    def bind_tools(self, tools: Any, **kwargs: Any) -> "MockChatModel":
        return self

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> AIMessage:
        self.calls += 1
        return AIMessage(content="mock final reply")


# --------------------------------------------------------------------------- #
# Focused draft-07 meta-schema validator (self-contained, no external deps)
# --------------------------------------------------------------------------- #

DRAFT07_URL = "http://json-schema.org/draft-07/schema#"
META_REQUIRED = [
    "schema",
    "problem_id",
    "numeric_authority",
    "roles",
    "budget_scope",
    "budget_percent",
    "objective_order",
    "candidate_lifecycle",
    "stop_rules",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    node: Any = root
    for token in ref[2:].split("/"):
        node = node[token]
    return node


def _validate_meta(doc: Any, schema: dict[str, Any], root: dict[str, Any], path: str = "$") -> list[str]:
    """Validate ``doc`` against the subset of draft-07 used by the meta-schema."""
    errors: list[str] = []
    if "$ref" in schema:
        schema = _resolve_ref(root, schema["$ref"])
    if "type" in schema and not _type_ok(doc, schema["type"]):
        errors.append(f"{path}: expected type {schema['type']!r}, got {type(doc).__name__}")
        return errors
    if isinstance(doc, str) and "pattern" in schema:
        if not re.search(schema["pattern"], doc):
            errors.append(f"{path}: {doc!r} does not match pattern {schema['pattern']!r}")
    if isinstance(doc, list) and "items" in schema:
        for index, item in enumerate(doc):
            errors.extend(_validate_meta(item, schema["items"], root, f"{path}[{index}]"))
    if isinstance(doc, dict):
        for key in schema.get("required", []):
            if key not in doc:
                errors.append(f"{path}: missing required key {key!r}")
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in doc:
                errors.extend(_validate_meta(doc[key], subschema, root, f"{path}.{key}"))
        additional = schema.get("additionalProperties")
        if additional is False:
            for key in doc:
                if key not in properties:
                    errors.append(f"{path}: additional property {key!r} not allowed")
        elif isinstance(additional, dict):
            for key in doc:
                if key in properties:
                    continue
                errors.extend(_validate_meta(doc[key], additional, root, f"{path}.{key}"))
    return errors


# --------------------------------------------------------------------------- #
# 1. Contract validates against the Domain Collaboration meta-schema
# --------------------------------------------------------------------------- #

def test_scheduling_contract_file_wellformed() -> None:
    schema = _load_json(META_SCHEMA_PATH)
    assert schema["$schema"] == DRAFT07_URL
    assert schema["type"] == "object"
    assert schema["required"] == META_REQUIRED
    assert schema["definitions"]["role"]["required"] == ["owns", "forbidden"]


def test_scheduling_contract_validates_against_meta_schema() -> None:
    schema = _load_json(META_SCHEMA_PATH)
    doc = _load_json(SCHEDULING_CONTRACT_PATH)
    errors = _validate_meta(doc, schema, schema)
    assert errors == [], errors

    # Domain-specific extras are permitted by additionalProperties: true.
    extras = set(doc) - set(schema["properties"])
    assert {"handoff_order", "experiment_rules", "registry", "tamper_tests"} <= extras


def test_scheduling_contract_schema_id_matches_pattern() -> None:
    schema = _load_json(META_SCHEMA_PATH)
    pattern = schema["properties"]["schema"]["pattern"]
    doc = _load_json(SCHEDULING_CONTRACT_PATH)
    assert re.search(pattern, doc["schema"]), doc["schema"]


def test_scheduling_contract_budget_sums_to_100() -> None:
    doc = _load_json(SCHEDULING_CONTRACT_PATH)
    assert sum(doc["budget_percent"].values()) == 100
    assert doc["budget_percent"] == {"auditor": 20, "exact_bound": 15, "heuristic": 35, "realities": 30}


def test_scheduling_contract_tamper_tests_match_redteam_gate() -> None:
    doc = _load_json(SCHEDULING_CONTRACT_PATH)
    assert doc["tamper_tests"] == list(JSSP_TAMPER_TESTS)
    assert doc["tamper_tests"] == list(redteam_gate.ATTACK_NAMES)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema="scheduling_collaboration.v1"),
        lambda d: d.update(schema="orpath.scheduling_collaboration.vX"),
        lambda d: d.update(problem_id=None),
        lambda d: d.update(numeric_authority=7),
        lambda d: d.update(budget_scope=7),
        lambda d: d.update(objective_order="hard_constraints"),
        lambda d: d["budget_percent"].update(auditor="twenty"),
        lambda d: d["budget_percent"].update(auditor=20.5),
        lambda d: d.update(roles=[]),
        lambda d: d["roles"]["or-jssp-lead"].pop("owns"),
        lambda d: d["roles"]["or-jssp-heuristic"].pop("forbidden"),
        lambda d: d["roles"]["or-jssp-redteam"].clear(),
        lambda d: d["roles"]["or-jssp-auditor"].update(owns="not-a-list"),
        lambda d: d["roles"]["or-jssp-exact-bound"].update(forbidden=[3]),
        lambda d: d.update(candidate_lifecycle="PROPOSED"),
        lambda d: d["stop_rules"].update(heuristic="stop_after_two_budget_levels"),
    ],
    ids=[
        "schema-missing-prefix",
        "schema-bad-version",
        "problem-id-wrong-type",
        "numeric-authority-wrong-type",
        "budget-scope-wrong-type",
        "objective-order-not-array",
        "budget-percent-string-value",
        "budget-percent-float-value",
        "roles-not-object",
        "role-missing-owns",
        "role-missing-forbidden",
        "role-missing-both",
        "role-owns-not-array",
        "role-forbidden-non-string-item",
        "candidate-lifecycle-not-array",
        "stop-rules-value-not-array",
    ],
)
def test_tampered_scheduling_contract_rejected(mutate: Any) -> None:
    schema = _load_json(META_SCHEMA_PATH)
    doc = _load_json(SCHEDULING_CONTRACT_PATH)
    mutate(doc)
    errors = _validate_meta(doc, schema, schema)
    assert errors, f"tampered scheduling contract unexpectedly validated: {mutate}"


# --------------------------------------------------------------------------- #
# 2. Budget ledger: check_scheduling_budget_ledger + 20/15/35/30 quota consistency
# --------------------------------------------------------------------------- #

def test_budget_ledger_manager_audits_scheduling_ledger(
    scheduling_golden_ledger: Path,
) -> None:
    report = audit_file(
        scheduling_golden_ledger,
        expected_budget=JSSP_DISCRETIONARY_BUDGET,
        root=ROOT,
    )
    assert report["ok"] is True
    assert report["validation"]["ok"] is True
    assert report["compliance"]["budget_percent"] == JSSP_DISCRETIONARY_BUDGET
    assert report["compliance"]["budget_sum"] == 100
    assert report["risk_override"]["active"] is False


def test_budget_ledger_manager_rejects_quota_drift() -> None:
    ledger = {"budget_percent": dict(JSSP_DISCRETIONARY_BUDGET)}
    ledger["budget_percent"]["heuristic"] = 36  # breaks the 20/15/35/30 quota
    ok, errors = BudgetLedgerManager(ledger=ledger).validate()
    assert ok is False
    assert any("budget_percent" in error for error in errors)


def test_budget_ledger_manager_tracks_risk_override_lifecycle() -> None:
    manager = BudgetLedgerManager(
        domain="scheduling",
        ledger={"budget_percent": dict(JSSP_DISCRETIONARY_BUDGET)},
        baseline_budget=JSSP_DISCRETIONARY_BUDGET,
        override_budget=JSSP_RISK_OVERRIDE_BUDGET,
    )
    assert manager.effective_budget() == JSSP_DISCRETIONARY_BUDGET

    effective = manager.apply_override(
        trigger="input_gate_red",
        temporary_percent=JSSP_RISK_OVERRIDE_BUDGET,
        release_condition="input_gate_green",
        evidence="outputs/pyjobshop_jssp-validate.json",
    )
    assert effective == JSSP_RISK_OVERRIDE_BUDGET
    assert manager.active_overrides()

    assert manager.release_override() == JSSP_DISCRETIONARY_BUDGET
    assert manager.active_overrides() == []


def test_evaluate_risk_override_helper() -> None:
    assert evaluate_risk_override([], JSSP_DISCRETIONARY_BUDGET) == JSSP_DISCRETIONARY_BUDGET
    assert evaluate_risk_override(
        [{"trigger": "t", "released": True}], JSSP_DISCRETIONARY_BUDGET
    ) == JSSP_DISCRETIONARY_BUDGET
    assert evaluate_risk_override(
        [{"trigger": "t", "temporary_percent": JSSP_RISK_OVERRIDE_BUDGET}],
        JSSP_DISCRETIONARY_BUDGET,
    ) == JSSP_RISK_OVERRIDE_BUDGET


def test_check_scheduling_budget_ledger_tool_is_backward_compatible(
    scheduling_golden_ledger: Path,
) -> None:
    result = json.loads(check_scheduling_budget_ledger.invoke({}))
    assert result["ok"] is True
    assert result["budget_percent"] == {
        "auditor": 20,
        "exact_bound": 15,
        "heuristic": 35,
        "realities": 30,
    }
    assert result["budget_matches_protocol"] is True
    assert result["total_budget_sum"] == 100
    assert result["audit"]["ok"] is True


def test_check_scheduling_budget_ledger_tool_handles_missing_ledger(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    result = json.loads(check_scheduling_budget_ledger.invoke({"ledger_path": str(missing)}))
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_check_scheduling_budget_ledger_tool_handles_malformed_ledger(tmp_path: Path) -> None:
    broken = tmp_path / "ledger.json"
    broken.write_text("[1, 2, 3]", encoding="utf-8")
    result = json.loads(check_scheduling_budget_ledger.invoke({"ledger_path": str(broken)}))
    assert result["ok"] is False
    assert "JSON object" in result["error"]


# --------------------------------------------------------------------------- #
# 3. Six-role scheduling team
# --------------------------------------------------------------------------- #

def test_scheduling_team_six_role_roster() -> None:
    assert JSSP_WORKER_NAMES == (
        JSSP_AUDITOR_NAME,
        JSSP_EXACT_BOUND_NAME,
        JSSP_HEURISTIC_NAME,
        JSSP_REALITY_NAME,
        JSSP_REDTEAM_NAME,
    )
    all_names = (JSSP_LEAD_NAME, *JSSP_WORKER_NAMES)
    assert len(all_names) == 6
    assert JSSP_PIPELINE_STAGE_ORDER == JSSP_WORKER_NAMES
    assert set(JSSP_GUARD_CALL_IDS) == set(JSSP_WORKER_NAMES)


def test_scheduling_team_all_six_agents_creable(model: Any) -> None:
    lead = create_jssp_lead_agent(model=model)
    assert lead.name == JSSP_LEAD_NAME

    assert create_jssp_auditor_agent(model=model).name == JSSP_AUDITOR_NAME
    assert create_jssp_exact_bound_agent(model=model).name == JSSP_EXACT_BOUND_NAME
    assert create_jssp_heuristic_agent(model=model).name == JSSP_HEURISTIC_NAME
    assert create_jssp_realities_agent(model=model).name == JSSP_REALITY_NAME
    assert create_jssp_redteam_agent(model=model).name == JSSP_REDTEAM_NAME

    workers = get_jssp_workers(model=model)
    assert [w.name for w in workers] == list(JSSP_WORKER_NAMES)


def test_scheduling_team_prompts_unchanged() -> None:
    for prompt in (
        DEFAULT_JSSP_LEAD_PROMPT,
        JSSP_AUDITOR_PROMPT,
        JSSP_EXACT_BOUND_PROMPT,
        JSSP_HEURISTIC_PROMPT,
        JSSP_REALITY_PROMPT,
        JSSP_REDTEAM_PROMPT,
    ):
        assert isinstance(prompt, str) and len(prompt) > 50

    # The red-team prompt must enumerate all five DIMO tamper tests by name.
    for tamper in JSSP_TAMPER_TESTS:
        assert tamper in JSSP_REDTEAM_PROMPT


def test_scheduling_protocol_constants() -> None:
    assert JSSP_DISCRETIONARY_BUDGET == {
        "auditor": 20,
        "exact_bound": 15,
        "heuristic": 35,
        "realities": 30,
    }
    assert sum(JSSP_DISCRETIONARY_BUDGET.values()) == 100
    assert JSSP_RISK_OVERRIDE_BUDGET == {
        "auditor": 35,
        "exact_bound": 10,
        "heuristic": 30,
        "realities": 25,
    }
    assert sum(JSSP_RISK_OVERRIDE_BUDGET.values()) == 100
    assert JSSP_OBJECTIVE_ORDER[0] == "hard_constraints"
    assert JSSP_OBJECTIVE_ORDER == (
        "hard_constraints",
        "makespan",
        "total_setup_time",
        "total_tardiness",
    )
    assert JSSP_CANDIDATE_LIFECYCLE == (
        "PROPOSED",
        "SOLVER_FEASIBLE",
        "INDEPENDENTLY_VALIDATED",
        "REDTEAM_PASSED",
        "ACCEPTED",
    )
    assert JSSP_TAMPER_TESTS == (
        "machine_overlap_injection",
        "operation_precedence_inversion",
        "setup_time_cheat",
        "makespan_deflation",
        "job_omission_tamper",
    )


# --------------------------------------------------------------------------- #
# 4. SchedulingSupervisorState inherits the Phase 1 domain state
# --------------------------------------------------------------------------- #

def test_scheduling_supervisor_state_inherits_domain_supervisor_state() -> None:
    assert SchedulingSupervisorState.__orig_bases__ == (DomainSupervisorState,)


def test_scheduling_supervisor_state_keeps_scheduling_specific_fields() -> None:
    from typing import get_type_hints

    hints = get_type_hints(SchedulingSupervisorState)
    for flag in (
        "has_auditor_verified",
        "has_exact_bound_computed",
        "has_heuristic_solved",
        "has_realities_applied",
        "has_redteam_verified",
    ):
        assert flag in hints and hints[flag] is bool
    assert hints["exact_bound_report_path"] is str
    assert hints["schedule_plan_path"] is str
    assert hints["makespan"] == int | None
    assert hints["total_setup_time"] == int | None
    assert hints["total_tardiness"] == int | None
    assert hints["domain"] is str
    assert hints["problem_id"] is str


def test_scheduling_supervisor_state_inherits_canonical_fields() -> None:
    from typing import get_type_hints

    base_fields = set(get_type_hints(DomainSupervisorState))
    scheduling_hints = get_type_hints(SchedulingSupervisorState)
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
        assert field in scheduling_hints, f"SchedulingSupervisorState lost inherited {field}"
        assert field in base_fields

    assert SchedulingSupervisorState.__dict__["domain"] == "scheduling"
    assert SchedulingSupervisorState.__dict__["problem_id"] == "pyjobshop_jssp"


def test_scheduling_state_stage_progress_is_readable() -> None:
    state = SchedulingSupervisorState(
        messages=[HumanMessage("run")],
        domain="scheduling",
        or_jssp_auditor=True,
        or_jssp_exact_bound=True,
    )
    progress = get_state_stage_progress(state, JSSP_PIPELINE_STAGE_ORDER)
    assert progress["domain"] == "scheduling"
    assert progress["total_stages"] == 5
    assert progress["completed_count"] == 2
    assert progress["next_stage"] == JSSP_HEURISTIC_NAME
    assert 0.0 < progress["progress"] < 1.0

    transcript = SchedulingSupervisorState(
        messages=[HumanMessage("run"), AIMessage("g", name=JSSP_AUDITOR_NAME)]
    )
    fallback = get_state_stage_progress(transcript, JSSP_PIPELINE_STAGE_ORDER)
    assert fallback["completed_count"] == 1
    assert fallback["next_stage"] == JSSP_EXACT_BOUND_NAME


# --------------------------------------------------------------------------- #
# 5. Scheduling guard hook is the guard_factory product and enforces order
# --------------------------------------------------------------------------- #

def test_scheduling_guard_hook_is_built_by_guard_factory() -> None:
    assert scheduling_guard_post_hook.__name__ == "domain_guard_post_hook"

    fresh = create_domain_guard_hook(JSSP_PIPELINE_STAGE_ORDER, JSSP_GUARD_CALL_IDS)
    states = [
        {"messages": []},
        {"messages": [HumanMessage("start")]},
        {"messages": [HumanMessage("run"), AIMessage("done", id="m1")]},
        {
            "messages": [
                HumanMessage("run"),
                AIMessage("a", name=JSSP_AUDITOR_NAME),
                AIMessage("done", id="m2"),
            ]
        },
    ]
    for state in states:
        assert scheduling_guard_post_hook(state) == fresh(state)


def test_scheduling_guard_hook_blocks_non_lead_early_termination() -> None:
    """A bare reply before the red-team stage is done is never allowed to finish."""
    # Empty / non-AI / already-scheduling states pass through untouched.
    assert scheduling_guard_post_hook({"messages": []}) == {}
    assert scheduling_guard_post_hook({"messages": [HumanMessage("start")]}) == {}
    assert scheduling_guard_post_hook(
        {"messages": [AIMessage("scheduling", tool_calls=[{"name": "x", "args": {}, "id": "c"}])]}
    ) == {}

    def bare(messages: list[Any]) -> str:
        update = scheduling_guard_post_hook({"messages": messages})
        assert update, f"guard did not act on {messages!r}"
        injected = update["messages"][-1]
        assert injected.tool_calls[0]["id"] in JSSP_GUARD_CALL_IDS.values()
        return injected.tool_calls[0]["name"]

    # Stage 1: nothing done yet -> auditor.
    assert bare([HumanMessage("run"), AIMessage("done", id="m1")]) == (
        "transfer_to_or_jssp_auditor"
    )

    # Stage 2: auditor done -> exact_bound (a *later* stage being done must not
    # skip the first missing one).
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("a", name=JSSP_AUDITOR_NAME),
            AIMessage("rt", name=JSSP_REDTEAM_NAME),
            AIMessage("done", id="m2"),
        ]
    ) == "transfer_to_or_jssp_exact_bound"

    # Stage 3: auditor + exact_bound done -> heuristic.
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("a", name=JSSP_AUDITOR_NAME),
            AIMessage("b", name=JSSP_EXACT_BOUND_NAME),
            AIMessage("done", id="m3"),
        ]
    ) == "transfer_to_or_jssp_heuristic"

    # Stage 4: auditor + exact_bound + heuristic done -> realities.
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("a", name=JSSP_AUDITOR_NAME),
            AIMessage("b", name=JSSP_EXACT_BOUND_NAME),
            AIMessage("h", name=JSSP_HEURISTIC_NAME),
            AIMessage("done", id="m4"),
        ]
    ) == "transfer_to_or_jssp_realities"

    # Stage 5: four stages done -> redteam. A bare "all finished" reply from the
    # lead is force-rerouted to the last specialist instead of terminating.
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("a", name=JSSP_AUDITOR_NAME),
            AIMessage("b", name=JSSP_EXACT_BOUND_NAME),
            AIMessage("h", name=JSSP_HEURISTIC_NAME),
            AIMessage("r", name=JSSP_REALITY_NAME),
            AIMessage("completed", id="m5"),
        ]
    ) == "transfer_to_or_jssp_redteam"

    # Stage 6: every stage handed off -> bare reply is allowed.
    assert scheduling_guard_post_hook(
        {
            "messages": [
                HumanMessage("run"),
                AIMessage("a", name=JSSP_AUDITOR_NAME),
                AIMessage("b", name=JSSP_EXACT_BOUND_NAME),
                AIMessage("h", name=JSSP_HEURISTIC_NAME),
                AIMessage("r", name=JSSP_REALITY_NAME),
                AIMessage("rt", name=JSSP_REDTEAM_NAME),
                AIMessage("completed", id="m6"),
            ]
        }
    ) == {}


# --------------------------------------------------------------------------- #
# 6. Red-team gate defensive robustness (bad input never crashes)
# --------------------------------------------------------------------------- #

MALFORMED_JSSP_SOLUTIONS: tuple[Any, ...] = (
    None,
    "not-a-dict",
    42,
    [],
    {},
    {"schedule": "not-a-list"},
    {"schedule": None},
    {"schedule": []},
    {"schedule": [None]},
    {"schedule": ["x"]},
    {"schedule": [{}]},
    {"schedule": [{"job": 0, "task": 0}]},
    {"schedule": [{"job": 0, "task": 0, "machine": 0, "start": 0}]},
    {"objective": "x", "schedule": []},
    {"machine_schedules": "nope"},
    {"machine_schedules": {"m0": "x"}},
    {"schedule": [{"job": 0}], "setup": {"a": 1}},
    {"schedule": [{"job": 0, "task": 0, "machine": 0, "start": 0, "end": "x", "duration": 1}]},
    # Mixed-type starts make the overlap builder's sort raise; the gate must
    # capture that defensively instead of crashing.
    {
        "schedule": [
            {"job": 0, "task": 0, "machine": 0, "start": 0, "end": 1, "duration": 1},
            {"job": 1, "task": 0, "machine": 0, "start": "x", "end": 1, "duration": 1},
        ]
    },
)


@pytest.mark.parametrize("solution", MALFORMED_JSSP_SOLUTIONS)
def test_redteam_build_attacks_never_raises_on_malformed_solution(solution: Any) -> None:
    attacks = redteam_gate.build_attacks(solution)
    assert [row["attack"] for row in attacks] == list(redteam_gate.ATTACK_NAMES)
    for row in attacks:
        assert isinstance(row["applied"], bool)
        if not row["applied"]:
            assert isinstance(row["reason"], str) and row["reason"]


@pytest.mark.parametrize("solution", MALFORMED_JSSP_SOLUTIONS)
def test_redteam_run_redteam_never_raises_on_malformed_solution(solution: Any) -> None:
    report = redteam_gate.run_redteam(solution)
    assert report["ok"] is False
    assert report["schema"] == "orpath.scheduling_redteam.v1"
    assert report["original_recompute_ok"] is False
    assert report["attack_count"] == len(redteam_gate.ATTACK_NAMES)
    for row in report["attacks"]:
        if row["applied"]:
            assert isinstance(row["failed_checks"], list)
        else:
            assert row["rejected"] is False
            assert isinstance(row["reason"], str) and row["reason"]


STRICT_UNAPPLIED_SOLUTIONS: tuple[Any, ...] = (
    None,
    "not-a-dict",
    42,
    [],
    {},
    {"schedule": "not-a-list"},
    {"schedule": None},
    {"schedule": []},
    {"schedule": [None]},
    {"schedule": ["x"]},
    {"schedule": [{}]},
    {"schedule": [{"job": 0, "task": 0}]},
    {"schedule": [{"job": 0, "task": 0, "machine": 0, "start": 0}]},
    {"objective": "x", "schedule": []},
    {"machine_schedules": "nope"},
    {"machine_schedules": {"m0": "x"}},
)


@pytest.mark.parametrize("solution", STRICT_UNAPPLIED_SOLUTIONS)
def test_redteam_malformed_solution_reports_rejected_false_and_ok_false(
    solution: Any,
) -> None:
    """Degenerate envelopes: every attack is unapplied (rejected: false) and the
    overall verdict fails safely (ok: false) instead of raising."""
    report = redteam_gate.run_redteam(solution)
    assert report["ok"] is False
    for row in report["attacks"]:
        assert row["applied"] is False
        assert row["rejected"] is False
        assert row["failed_checks"] == []
        assert isinstance(row["reason"], str) and row["reason"]


def test_redteam_build_attacks_captures_builder_exceptions() -> None:
    """A builder that raises internally is converted into applied: false + reason."""
    broken = {
        "schedule": [
            {"job": 0, "task": 0, "machine": 0, "start": 0, "end": 1, "duration": 1},
            {"job": 1, "task": 0, "machine": 0, "start": "x", "end": 1, "duration": 1},
        ]
    }
    attacks = redteam_gate.build_attacks(broken)
    by_name = {row["attack"]: row for row in attacks}
    overlap = by_name["machine_overlap_injection"]
    assert overlap["applied"] is False
    assert "TypeError" in overlap["reason"]
    setup = by_name["setup_time_cheat"]
    assert setup["applied"] is False
    assert "TypeError" in setup["reason"]


def test_redteam_build_attacks_does_not_mutate_input(ft06_solution: dict[str, Any]) -> None:
    before = deepcopy(ft06_solution)
    redteam_gate.build_attacks(ft06_solution)
    assert ft06_solution == before


def test_redteam_recompute_rejects_non_dict_payload() -> None:
    for payload in (None, "x", 42, [], 3.14, True):
        report = redteam_gate.recompute("jssp_ft06", payload)
        assert report["ok"] is False
        assert report["checks"] == []


def test_redteam_recompute_rejects_empty_dict() -> None:
    report = redteam_gate.recompute("jssp_ft06", {})
    assert report["ok"] is False
    assert report["checks"]


def test_redteam_cli_rejects_malformed_solution_without_crashing(tmp_path: Path) -> None:
    solution = tmp_path / "solution.json"
    solution.write_text(json.dumps({"schedule": [None]}), encoding="utf-8")
    out = tmp_path / "redteam.json"

    exit_code = redteam_gate.main(["--solution", str(solution), "--out", str(out)])

    assert exit_code == 1
    assert out.is_file()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema"] == "orpath.scheduling_redteam.v1"
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


# --------------------------------------------------------------------------- #
# 7. Five DIMO tamper attacks vs. a real FT06 solution (100% interception)
# --------------------------------------------------------------------------- #

def test_ft06_solver_envelope_matches_published_optimum(
    ft06_solution: dict[str, Any],
) -> None:
    """Numbers Truth: FT06 objective comes from the CP-SAT solver, not prose."""
    assert ft06_solution["status"] == "OPTIMAL"
    assert ft06_solution["objective"] == 55
    assert ft06_solution["lower_bound"] == 55
    assert ft06_solution["optimality_gap"] == 0
    assert ft06_solution["known_optimum"] == 55
    assert len(ft06_solution["schedule"]) == 36


def test_redteam_build_attacks_all_applied_on_ft06(
    ft06_solution: dict[str, Any],
) -> None:
    attacks = redteam_gate.build_attacks(ft06_solution)
    assert len(attacks) == 5
    assert all(row["applied"] for row in attacks), [
        (row["attack"], row["reason"]) for row in attacks
    ]
    assert all(row["reason"] is None for row in attacks)
    assert ft06_solution["schedule"]


def test_redteam_run_redteam_blocks_all_five_dimo_attacks(
    ft06_solution: dict[str, Any],
) -> None:
    report = redteam_gate.run_redteam(ft06_solution, "jssp_ft06")
    assert report["original_recompute_ok"] is True
    assert report["attacks_applied"] == 5

    by_name = {row["attack"]: row for row in report["attacks"]}
    expected_failures = {
        "machine_overlap_injection": "machine_no_overlap",
        "operation_precedence_inversion": "job_precedence",
        "setup_time_cheat": "setup_time_respected",
        "makespan_deflation": "makespan_objective_match",
        "job_omission_tamper": "jssp_operation_completeness",
    }
    for name, failed_check in expected_failures.items():
        row = by_name[name]
        assert row["applied"] is True
        assert row["rejected"] is True, f"{name} was not blocked: {row['failed_checks']}"
        assert failed_check in row["failed_checks"], row["failed_checks"]
    assert report["ok"] is True


def test_redteam_setup_time_cheat_blocked_with_declared_changeover(
    ft06_setup_solution: dict[str, Any],
) -> None:
    """FT06 + uniform 换模时延=2: the cheat attack must still be intercepted."""
    assert ft06_setup_solution["status"] in ("OPTIMAL", "FEASIBLE")
    assert ft06_setup_solution["objective"] >= 55
    assert ft06_setup_solution["total_setup_time"] > 0
    assert ft06_setup_solution["setup"] == 2

    report = redteam_gate.run_redteam(ft06_setup_solution, "jssp_ft06_setup")
    assert report["original_recompute_ok"] is True
    assert report["attacks_applied"] == 5
    assert all(row["rejected"] for row in report["attacks"]), report["attacks"]
    assert report["ok"] is True

    by_name = {row["attack"]: row for row in report["attacks"]}
    assert "setup_time_respected" in by_name["setup_time_cheat"]["failed_checks"]


def test_redteam_cli_passes_when_every_attack_is_blocked(
    tmp_path: Path, ft06_solution: dict[str, Any],
) -> None:
    solution = tmp_path / "pyjobshop_jssp-solution.json"
    solution.write_text(json.dumps(ft06_solution), encoding="utf-8")
    out = tmp_path / "pyjobshop_jssp-redteam.json"

    exit_code = redteam_gate.main(["--solution", str(solution), "--out", str(out)])

    assert out.is_file()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema"] == "orpath.scheduling_redteam.v1"
    assert report["problem_id"] == "jssp_ft06"
    assert report["original_recompute_ok"] is True
    assert report["attack_count"] == 5
    assert report["attacks_applied"] == 5
    assert report["ok"] is True
    assert all(row["rejected"] for row in report["attacks"])
    assert exit_code == 0


# --------------------------------------------------------------------------- #
# 8. Supervisor graph construction + mock node execution
# --------------------------------------------------------------------------- #

def test_scheduling_supervisor_graph_compiles(model: Any) -> None:
    from orpath.agents.domains.scheduling import build_scheduling_supervisor_graph

    graph = build_scheduling_supervisor_graph(model=model)
    assert isinstance(graph, StateGraph)


def test_scheduling_compiled_supervisor_contains_all_nodes(model: Any) -> None:
    from orpath.agents.domains.scheduling import build_compiled_scheduling_supervisor

    compiled = build_compiled_scheduling_supervisor(model=model)
    assert isinstance(compiled, CompiledStateGraph)
    for expected_node in (JSSP_LEAD_NAME, *JSSP_WORKER_NAMES):
        assert expected_node in compiled.nodes


def test_scheduling_compiled_supervisor_runs_mock_pipeline() -> None:
    """Execute the compiled supervisor end to end with a mock LLM.

    The mock always answers with a bare reply, so the guard hook alone drives
    the handoff sequence: every one of the 5 worker nodes must run exactly once,
    in pipeline order, before the lead may terminate.
    """
    from orpath.agents.domains.scheduling import build_compiled_scheduling_supervisor

    mock = MockChatModel()
    compiled = build_compiled_scheduling_supervisor(model=mock, enable_trim=False)
    final = compiled.invoke({"messages": [HumanMessage("run")]})

    # 1 supervisor decision per worker handoff + 5 worker model calls.
    assert mock.calls == 11

    transfers = [
        message.tool_calls[0]["name"]
        for message in final["messages"]
        if getattr(message, "tool_calls", None)
    ]
    for worker in JSSP_WORKER_NAMES:
        assert f"transfer_to_{worker}" in transfers
        assert f"transfer_back_to_{JSSP_LEAD_NAME}" in transfers

    # Each worker node answered exactly once, in pipeline order.
    worker_answers = [
        message
        for message in final["messages"]
        if getattr(message, "name", None) in JSSP_WORKER_NAMES
        and not getattr(message, "tool_calls", None)
    ]
    assert [getattr(m, "name", None) for m in worker_answers] == list(JSSP_WORKER_NAMES)

    # The run ends with the lead's bare reply (guard hook allowed termination).
    assert final["messages"][-1].name == JSSP_LEAD_NAME
    assert not final["messages"][-1].tool_calls
    assert final["messages"][-1].content == "mock final reply"


# --------------------------------------------------------------------------- #
# 9. Domain tools: contract + collaboration gate + red-team gate wrapper
# --------------------------------------------------------------------------- #

def test_validate_scheduling_contract_tool() -> None:
    result = json.loads(validate_scheduling_contract.invoke({}))
    assert result["ok"] is True
    assert result["schema"] == "orpath.scheduling_collaboration.v1"
    assert result["problem_id"] == "pyjobshop_jssp"
    assert result["errors"] == []
    assert "or-jssp-lead" in result["roles"]


def test_run_scheduling_collaboration_gate_tool(scheduling_golden_ledger: Path) -> None:
    result = json.loads(run_scheduling_collaboration_gate.invoke({}))
    assert result["ok"] is True
    assert result["gate"] == "scheduling_collaboration_gate"
    assert result["contract"]["ok"] is True
    assert result["budget_ledger"]["ok"] is True
    assert result["budget_ledger"]["budget_matches_protocol"] is True


def test_run_scheduling_redteam_gate_tool_writes_report(
    tmp_path: Path, ft06_solution: dict[str, Any],
) -> None:
    solution = tmp_path / "pyjobshop_jssp-solution.json"
    solution.write_text(json.dumps(ft06_solution), encoding="utf-8")
    out = tmp_path / "pyjobshop_jssp-redteam.json"

    result = json.loads(
        run_scheduling_redteam_gate.invoke(
            {"solution_path": str(solution), "out_path": str(out)}
        )
    )
    assert result["ok"] is True
    assert result["returncode"] == 0
    assert result["report"]["schema"] == "orpath.scheduling_redteam.v1"
    assert result["report"]["ok"] is True


def test_run_scheduling_redteam_gate_tool_handles_missing_solution(
    tmp_path: Path,
) -> None:
    result = json.loads(
        run_scheduling_redteam_gate.invoke(
            {
                "solution_path": str(tmp_path / "absent.json"),
                "out_path": str(tmp_path / "redteam.json"),
            }
        )
    )
    assert result["ok"] is False
    assert "not found" in result["error"]
