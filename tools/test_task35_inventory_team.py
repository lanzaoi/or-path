#!/usr/bin/env python3
"""Phase 3 / Task 3.5 — Dynamic Inventory Control & Lot Sizing team + hardening tests.

Covers the Phase 3.5 deliverables:

1. ``contracts/inventory_collaboration_v1.json`` validates against the Domain
   Collaboration meta-schema.
2. ``orpath/agents/domains/inventory.py`` wires the Phase 1 foundation modules
   (``guard_factory``, ``domain_state``, ``budget_engine``) while keeping the
   Lead + Pentad pattern verified in ``tube.py`` / ``routing.py`` /
   ``scheduling.py`` / ``project.py``.
3. ``scripts/inventory_redteam_gate.py`` never crashes on an unexpected
   solution schema; it fails safely with a structured report instead.
4. The 6-role inventory-control team builds and enforces its pipeline order,
   and the 5 DIMO tamper attacks are all rejected by the independent red-team
   gate on a real CLSP (capacitated lot-sizing) SCIP-MIP solution.
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
from orpath.agents.domains.inventory import (  # noqa: E402
    DEFAULT_INVENTORY_LEAD_PROMPT,
    INVENTORY_ALL_AGENT_NAMES,
    INVENTORY_AUDITOR_NAME,
    INVENTORY_AUDITOR_PROMPT,
    INVENTORY_CANDIDATE_LIFECYCLE,
    INVENTORY_DISCRETIONARY_BUDGET,
    INVENTORY_EXACT_BOUND_NAME,
    INVENTORY_EXACT_BOUND_PROMPT,
    INVENTORY_GUARD_CALL_IDS,
    INVENTORY_HEURISTIC_NAME,
    INVENTORY_HEURISTIC_PROMPT,
    INVENTORY_LEAD_NAME,
    INVENTORY_OBJECTIVE_ORDER,
    INVENTORY_PIPELINE_STAGE_ORDER,
    INVENTORY_REALITY_NAME,
    INVENTORY_REALITY_PROMPT,
    INVENTORY_REDTEAM_NAME,
    INVENTORY_REDTEAM_PROMPT,
    INVENTORY_RISK_OVERRIDE_BUDGET,
    INVENTORY_TAMPER_TESTS,
    INVENTORY_WORKER_NAMES,
    InventorySupervisorState,
    check_inventory_budget_ledger,
    create_inventory_auditor_agent,
    create_inventory_exact_bound_agent,
    create_inventory_heuristic_agent,
    create_inventory_lead_agent,
    create_inventory_realities_agent,
    create_inventory_redteam_agent,
    get_inventory_workers,
    inventory_guard_post_hook,
    run_inventory_collaboration_gate,
    run_inventory_redteam_gate,
    validate_inventory_contract,
)
from orpath.agents.guard_factory import create_domain_guard_hook  # noqa: E402
from orpath.control_plane import get_chat_model  # noqa: E402

import inventory_redteam_gate as redteam_gate  # noqa: E402
from solve_lot_sizing import solve_lot_sizing  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore:create_react_agent has been moved")

META_SCHEMA_PATH = ROOT / "contracts" / "meta" / "domain_collaboration.schema.json"
INVENTORY_CONTRACT_PATH = ROOT / "contracts" / "inventory_collaboration_v1.json"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture()
def model() -> Any:
    return get_chat_model()


@pytest.fixture(scope="module", autouse=True)
def inventory_golden_ledger() -> Path:
    """Provision the (gitignored) golden inventory budget ledger for tool tests."""
    path = ROOT / "experiments" / "inventory" / "budget-ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger = {
        "schema": "orpath.inventory_budget_ledger.v1",
        "date": "2026-01-01",
        "scope": "discretionary_experiment_effort_excluding_baseline_and_gates",
        "budget_percent": dict(INVENTORY_DISCRETIONARY_BUDGET),
    }
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def ww12_solution() -> dict[str, Any]:
    """Real Wagner-Whitin DP solution of the 12-period benchmark (optimum 670)."""
    return solve_lot_sizing()


@pytest.fixture(scope="module")
def clsp60_solution() -> dict[str, Any]:
    """Real SCIP-MIP solution of the capacitated lot-sizing benchmark (capacity 60)."""
    return solve_lot_sizing(
        method="mip",
        capacity=60.0,
        problem_id="lot_sizing_clsp60",
    )


class MockChatModel(Runnable):
    """Deterministic offline stand-in LLM for supervisor pipeline execution.

    Every call returns a bare ``AIMessage`` with no ``tool_calls``.  The
    inventory guard hook then re-routes the lead to the next missing pipeline
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

def test_inventory_contract_file_wellformed() -> None:
    schema = _load_json(META_SCHEMA_PATH)
    assert schema["$schema"] == DRAFT07_URL
    assert schema["type"] == "object"
    assert schema["required"] == META_REQUIRED
    assert schema["definitions"]["role"]["required"] == ["owns", "forbidden"]


def test_inventory_contract_validates_against_meta_schema() -> None:
    schema = _load_json(META_SCHEMA_PATH)
    doc = _load_json(INVENTORY_CONTRACT_PATH)
    errors = _validate_meta(doc, schema, schema)
    assert errors == [], errors

    # Domain-specific extras are permitted by additionalProperties: true.
    extras = set(doc) - set(schema["properties"])
    assert {"handoff_order", "experiment_rules", "registry", "tamper_tests"} <= extras


def test_inventory_contract_schema_id_matches_pattern() -> None:
    schema = _load_json(META_SCHEMA_PATH)
    pattern = schema["properties"]["schema"]["pattern"]
    doc = _load_json(INVENTORY_CONTRACT_PATH)
    assert re.search(pattern, doc["schema"]), doc["schema"]


def test_inventory_contract_budget_sums_to_100() -> None:
    doc = _load_json(INVENTORY_CONTRACT_PATH)
    assert sum(doc["budget_percent"].values()) == 100
    assert doc["budget_percent"] == {"auditor": 20, "exact_bound": 15, "heuristic": 35, "realities": 30}


def test_inventory_contract_tamper_tests_match_redteam_gate() -> None:
    doc = _load_json(INVENTORY_CONTRACT_PATH)
    assert doc["tamper_tests"] == list(INVENTORY_TAMPER_TESTS)
    assert doc["tamper_tests"] == list(redteam_gate.ATTACK_NAMES)


def test_inventory_contract_role_boundaries_and_handoff_order() -> None:
    doc = _load_json(INVENTORY_CONTRACT_PATH)
    roles = doc["roles"]
    assert set(roles) == {
        "or-inventory-lead",
        "or-inventory-auditor",
        "or-inventory-exact-bound",
        "or-inventory-heuristic",
        "or-inventory-realities",
        "or-inventory-redteam",
    }
    for role in roles.values():
        assert isinstance(role["owns"], list) and role["owns"]
        assert isinstance(role["forbidden"], list) and role["forbidden"]
    assert doc["handoff_order"] == [
        "assumptions",
        "audit",
        "exact_bound",
        "heuristic_search",
        "realities",
        "redteam_validate",
        "write",
    ]
    assert doc["candidate_lifecycle"] == list(INVENTORY_CANDIDATE_LIFECYCLE)
    assert doc["objective_order"] == list(INVENTORY_OBJECTIVE_ORDER)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema="inventory_collaboration.v1"),
        lambda d: d.update(schema="orpath.inventory_collaboration.vX"),
        lambda d: d.update(problem_id=None),
        lambda d: d.update(numeric_authority=7),
        lambda d: d.update(budget_scope=7),
        lambda d: d.update(objective_order="hard_constraints"),
        lambda d: d["budget_percent"].update(auditor="twenty"),
        lambda d: d["budget_percent"].update(auditor=20.5),
        lambda d: d.update(roles=[]),
        lambda d: d["roles"]["or-inventory-lead"].pop("owns"),
        lambda d: d["roles"]["or-inventory-heuristic"].pop("forbidden"),
        lambda d: d["roles"]["or-inventory-redteam"].clear(),
        lambda d: d["roles"]["or-inventory-auditor"].update(owns="not-a-list"),
        lambda d: d["roles"]["or-inventory-exact-bound"].update(forbidden=[3]),
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
def test_tampered_inventory_contract_rejected(mutate: Any) -> None:
    schema = _load_json(META_SCHEMA_PATH)
    doc = _load_json(INVENTORY_CONTRACT_PATH)
    mutate(doc)
    errors = _validate_meta(doc, schema, schema)
    assert errors, f"tampered inventory contract unexpectedly validated: {mutate}"


# --------------------------------------------------------------------------- #
# 2. Budget ledger: check_inventory_budget_ledger + deduction audit + 20/15/35/30 quota
# --------------------------------------------------------------------------- #

def test_budget_ledger_manager_audits_inventory_ledger(
    inventory_golden_ledger: Path,
) -> None:
    report = audit_file(
        inventory_golden_ledger,
        expected_budget=INVENTORY_DISCRETIONARY_BUDGET,
        root=ROOT,
    )
    assert report["ok"] is True
    assert report["validation"]["ok"] is True
    assert report["compliance"]["budget_percent"] == INVENTORY_DISCRETIONARY_BUDGET
    assert report["compliance"]["budget_sum"] == 100
    assert report["risk_override"]["active"] is False


def test_budget_ledger_manager_rejects_quota_drift() -> None:
    ledger = {"budget_percent": dict(INVENTORY_DISCRETIONARY_BUDGET)}
    ledger["budget_percent"]["heuristic"] = 36  # breaks the 20/15/35/30 quota
    ok, errors = BudgetLedgerManager(ledger=ledger).validate()
    assert ok is False
    assert any("budget_percent" in error for error in errors)


def test_budget_ledger_manager_rejects_deducted_quota() -> None:
    """Deduction audit: dropping 1% from any workstream breaks the quota sum."""
    deducted = {"budget_percent": dict(INVENTORY_DISCRETIONARY_BUDGET)}
    deducted["budget_percent"]["heuristic"] -= 1  # 35 → 34 after deduction
    ok, errors = BudgetLedgerManager(ledger=deducted).validate()
    assert ok is False
    assert any("sum to exactly 100" in error for error in errors)


def test_check_inventory_budget_ledger_tool_rejects_deducted_ledger(tmp_path: Path) -> None:
    """A deducted ledger file is reported as non-compliant through the tool."""
    ledger = tmp_path / "deducted-ledger.json"
    deducted = {"budget_percent": dict(INVENTORY_DISCRETIONARY_BUDGET)}
    deducted["budget_percent"]["realities"] -= 2  # 30 → 28 after deduction
    ledger.write_text(json.dumps(deducted), encoding="utf-8")

    result = json.loads(check_inventory_budget_ledger.invoke({"ledger_path": str(ledger)}))
    assert result["ok"] is False
    assert result["total_budget_sum"] == 98
    assert result["budget_matches_protocol"] is False


def test_budget_ledger_manager_tracks_risk_override_lifecycle() -> None:
    manager = BudgetLedgerManager(
        domain="inventory",
        ledger={"budget_percent": dict(INVENTORY_DISCRETIONARY_BUDGET)},
        baseline_budget=INVENTORY_DISCRETIONARY_BUDGET,
        override_budget=INVENTORY_RISK_OVERRIDE_BUDGET,
    )
    assert manager.effective_budget() == INVENTORY_DISCRETIONARY_BUDGET

    effective = manager.apply_override(
        trigger="input_gate_red",
        temporary_percent=INVENTORY_RISK_OVERRIDE_BUDGET,
        release_condition="input_gate_green",
        evidence="outputs/wagner_whitin_clsp-validate.json",
    )
    assert effective == INVENTORY_RISK_OVERRIDE_BUDGET
    assert manager.active_overrides()

    assert manager.release_override() == INVENTORY_DISCRETIONARY_BUDGET
    assert manager.active_overrides() == []


def test_evaluate_risk_override_helper() -> None:
    assert evaluate_risk_override([], INVENTORY_DISCRETIONARY_BUDGET) == INVENTORY_DISCRETIONARY_BUDGET
    assert evaluate_risk_override(
        [{"trigger": "t", "released": True}], INVENTORY_DISCRETIONARY_BUDGET
    ) == INVENTORY_DISCRETIONARY_BUDGET
    assert evaluate_risk_override(
        [{"trigger": "t", "temporary_percent": INVENTORY_RISK_OVERRIDE_BUDGET}],
        INVENTORY_DISCRETIONARY_BUDGET,
    ) == INVENTORY_RISK_OVERRIDE_BUDGET


def test_check_inventory_budget_ledger_tool_is_backward_compatible(
    inventory_golden_ledger: Path,
) -> None:
    result = json.loads(check_inventory_budget_ledger.invoke({}))
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


def test_check_inventory_budget_ledger_tool_handles_missing_ledger(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    result = json.loads(check_inventory_budget_ledger.invoke({"ledger_path": str(missing)}))
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_check_inventory_budget_ledger_tool_handles_malformed_ledger(tmp_path: Path) -> None:
    broken = tmp_path / "ledger.json"
    broken.write_text("[1, 2, 3]", encoding="utf-8")
    result = json.loads(check_inventory_budget_ledger.invoke({"ledger_path": str(broken)}))
    assert result["ok"] is False
    assert "JSON object" in result["error"]


# --------------------------------------------------------------------------- #
# 3. InventorySupervisorState inherits the Phase 1 domain state + stage transitions
# --------------------------------------------------------------------------- #

def test_inventory_supervisor_state_inherits_domain_supervisor_state() -> None:
    assert InventorySupervisorState.__orig_bases__ == (DomainSupervisorState,)


def test_inventory_supervisor_state_keeps_inventory_specific_fields() -> None:
    from typing import get_type_hints

    hints = get_type_hints(InventorySupervisorState)
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
    assert hints["schedule_plan"] == list[dict[str, Any]]
    for cost in (
        "total_cost",
        "total_setup_cost",
        "total_holding_cost",
        "total_production_cost",
        "max_inventory_level",
        "safety_stock",
        "capacity",
        "initial_inventory",
        "unit_cost",
    ):
        assert hints[cost] == float | None, cost
    for count in ("num_setups", "num_periods"):
        assert hints[count] == int | None, count
    assert hints["domain"] is str
    assert hints["problem_id"] is str


def test_inventory_supervisor_state_inherits_canonical_fields() -> None:
    from typing import get_type_hints

    base_fields = set(get_type_hints(DomainSupervisorState))
    inventory_hints = get_type_hints(InventorySupervisorState)
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
        assert field in inventory_hints, f"InventorySupervisorState lost inherited {field}"
        assert field in base_fields

    assert InventorySupervisorState.__dict__["domain"] == "inventory"
    assert InventorySupervisorState.__dict__["problem_id"] == "wagner_whitin_clsp"


def test_inventory_state_stage_progress_is_readable() -> None:
    state = InventorySupervisorState(
        messages=[HumanMessage("run")],
        domain="inventory",
        or_inventory_auditor=True,
        or_inventory_exact_bound=True,
    )
    progress = get_state_stage_progress(state, INVENTORY_PIPELINE_STAGE_ORDER)
    assert progress["domain"] == "inventory"
    assert progress["total_stages"] == 5
    assert progress["completed_count"] == 2
    assert progress["next_stage"] == INVENTORY_HEURISTIC_NAME
    assert 0.0 < progress["progress"] < 1.0

    # Later stages being done must not skip the first missing one.
    later = InventorySupervisorState(
        messages=[HumanMessage("run")],
        domain="inventory",
        or_inventory_redteam=True,
    )
    partial = get_state_stage_progress(later, INVENTORY_PIPELINE_STAGE_ORDER)
    assert partial["completed_count"] == 1
    assert partial["next_stage"] == INVENTORY_AUDITOR_NAME

    # Transcript-based fallback: an AIMessage named after the worker counts.
    transcript = InventorySupervisorState(
        messages=[HumanMessage("run"), AIMessage("g", name=INVENTORY_AUDITOR_NAME)]
    )
    fallback = get_state_stage_progress(transcript, INVENTORY_PIPELINE_STAGE_ORDER)
    assert fallback["completed_count"] == 1
    assert fallback["next_stage"] == INVENTORY_EXACT_BOUND_NAME

    # Every stage handed off -> all_completed, no next stage, full progress.
    done = InventorySupervisorState(messages=[HumanMessage("run")], domain="inventory")
    for stage in INVENTORY_PIPELINE_STAGE_ORDER:
        done[stage] = True
    full = get_state_stage_progress(done, INVENTORY_PIPELINE_STAGE_ORDER)
    assert full["all_completed"] is True
    assert full["completed_count"] == 5
    assert full["next_stage"] is None
    assert full["progress"] == 1.0


# --------------------------------------------------------------------------- #
# 4. Inventory guard hook is the guard_factory product and enforces order
# --------------------------------------------------------------------------- #

def test_inventory_guard_hook_is_built_by_guard_factory() -> None:
    assert inventory_guard_post_hook.__name__ == "domain_guard_post_hook"

    fresh = create_domain_guard_hook(INVENTORY_PIPELINE_STAGE_ORDER, INVENTORY_GUARD_CALL_IDS)
    states = [
        {"messages": []},
        {"messages": [HumanMessage("start")]},
        {"messages": [HumanMessage("run"), AIMessage("done", id="m1")]},
        {
            "messages": [
                HumanMessage("run"),
                AIMessage("a", name=INVENTORY_AUDITOR_NAME),
                AIMessage("done", id="m2"),
            ]
        },
    ]
    for state in states:
        assert inventory_guard_post_hook(state) == fresh(state)


def test_inventory_guard_hook_blocks_non_lead_early_termination() -> None:
    """A bare reply before the red-team stage is done is never allowed to finish."""
    # Empty / non-AI / already-transferring states pass through untouched.
    assert inventory_guard_post_hook({"messages": []}) == {}
    assert inventory_guard_post_hook({"messages": [HumanMessage("start")]}) == {}
    assert inventory_guard_post_hook(
        {"messages": [AIMessage("lot_sizing", tool_calls=[{"name": "x", "args": {}, "id": "c"}])]}
    ) == {}

    def bare(messages: list[Any]) -> str:
        update = inventory_guard_post_hook({"messages": messages})
        assert update, f"guard did not act on {messages!r}"
        injected = update["messages"][-1]
        assert injected.tool_calls[0]["id"] in INVENTORY_GUARD_CALL_IDS.values()
        return injected.tool_calls[0]["name"]

    # Stage 1: nothing done yet -> auditor.
    assert bare([HumanMessage("run"), AIMessage("done", id="m1")]) == (
        "transfer_to_or_inventory_auditor"
    )

    # Stage 2: auditor done -> exact_bound (a *later* stage being done must not
    # skip the first missing one).
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("a", name=INVENTORY_AUDITOR_NAME),
            AIMessage("rt", name=INVENTORY_REDTEAM_NAME),
            AIMessage("done", id="m2"),
        ]
    ) == "transfer_to_or_inventory_exact_bound"

    # Stage 3: auditor + exact_bound done -> heuristic.
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("a", name=INVENTORY_AUDITOR_NAME),
            AIMessage("b", name=INVENTORY_EXACT_BOUND_NAME),
            AIMessage("done", id="m3"),
        ]
    ) == "transfer_to_or_inventory_heuristic"

    # Stage 4: auditor + exact_bound + heuristic done -> realities.
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("a", name=INVENTORY_AUDITOR_NAME),
            AIMessage("b", name=INVENTORY_EXACT_BOUND_NAME),
            AIMessage("h", name=INVENTORY_HEURISTIC_NAME),
            AIMessage("done", id="m4"),
        ]
    ) == "transfer_to_or_inventory_realities"

    # Stage 5: four stages done -> redteam. A bare "all finished" reply from the
    # lead is force-rerouted to the last specialist instead of terminating.
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("a", name=INVENTORY_AUDITOR_NAME),
            AIMessage("b", name=INVENTORY_EXACT_BOUND_NAME),
            AIMessage("h", name=INVENTORY_HEURISTIC_NAME),
            AIMessage("r", name=INVENTORY_REALITY_NAME),
            AIMessage("completed", id="m5"),
        ]
    ) == "transfer_to_or_inventory_redteam"

    # Stage 6: every stage handed off -> bare reply is allowed.
    assert inventory_guard_post_hook(
        {
            "messages": [
                HumanMessage("run"),
                AIMessage("a", name=INVENTORY_AUDITOR_NAME),
                AIMessage("b", name=INVENTORY_EXACT_BOUND_NAME),
                AIMessage("h", name=INVENTORY_HEURISTIC_NAME),
                AIMessage("r", name=INVENTORY_REALITY_NAME),
                AIMessage("rt", name=INVENTORY_REDTEAM_NAME),
                AIMessage("completed", id="m6"),
            ]
        }
    ) == {}


# --------------------------------------------------------------------------- #
# 5. Six-role inventory team: roster, worker instantiation, prompts, constants
# --------------------------------------------------------------------------- #

def test_inventory_team_six_role_roster() -> None:
    assert INVENTORY_WORKER_NAMES == (
        INVENTORY_AUDITOR_NAME,
        INVENTORY_EXACT_BOUND_NAME,
        INVENTORY_HEURISTIC_NAME,
        INVENTORY_REALITY_NAME,
        INVENTORY_REDTEAM_NAME,
    )
    all_names = (INVENTORY_LEAD_NAME, *INVENTORY_WORKER_NAMES)
    assert len(all_names) == 6
    assert INVENTORY_PIPELINE_STAGE_ORDER == INVENTORY_WORKER_NAMES
    assert set(INVENTORY_GUARD_CALL_IDS) == set(INVENTORY_WORKER_NAMES)
    assert INVENTORY_ALL_AGENT_NAMES == all_names


def test_inventory_team_all_six_agents_creable(model: Any) -> None:
    lead = create_inventory_lead_agent(model=model)
    assert lead.name == INVENTORY_LEAD_NAME

    assert create_inventory_auditor_agent(model=model).name == INVENTORY_AUDITOR_NAME
    assert create_inventory_exact_bound_agent(model=model).name == INVENTORY_EXACT_BOUND_NAME
    assert create_inventory_heuristic_agent(model=model).name == INVENTORY_HEURISTIC_NAME
    assert create_inventory_realities_agent(model=model).name == INVENTORY_REALITY_NAME
    assert create_inventory_redteam_agent(model=model).name == INVENTORY_REDTEAM_NAME

    workers = get_inventory_workers(model=model)
    assert [w.name for w in workers] == list(INVENTORY_WORKER_NAMES)


def test_inventory_team_prompts_unchanged() -> None:
    for prompt in (
        DEFAULT_INVENTORY_LEAD_PROMPT,
        INVENTORY_AUDITOR_PROMPT,
        INVENTORY_EXACT_BOUND_PROMPT,
        INVENTORY_HEURISTIC_PROMPT,
        INVENTORY_REALITY_PROMPT,
        INVENTORY_REDTEAM_PROMPT,
    ):
        assert isinstance(prompt, str) and len(prompt) > 50

    # The lead prompt must enumerate the 20/15/35/30 budget split and the
    # strict stage order; the red-team prompt must enumerate all five DIMO
    # tamper tests by name.
    for percent in ("20%", "15%", "35%", "30%"):
        assert percent in DEFAULT_INVENTORY_LEAD_PROMPT
    for tamper in INVENTORY_TAMPER_TESTS:
        assert tamper in INVENTORY_REDTEAM_PROMPT


def test_inventory_protocol_constants() -> None:
    assert INVENTORY_DISCRETIONARY_BUDGET == {
        "auditor": 20,
        "exact_bound": 15,
        "heuristic": 35,
        "realities": 30,
    }
    assert sum(INVENTORY_DISCRETIONARY_BUDGET.values()) == 100
    assert INVENTORY_RISK_OVERRIDE_BUDGET == {
        "auditor": 35,
        "exact_bound": 10,
        "heuristic": 30,
        "realities": 25,
    }
    assert sum(INVENTORY_RISK_OVERRIDE_BUDGET.values()) == 100
    assert INVENTORY_OBJECTIVE_ORDER[0] == "hard_constraints"
    assert INVENTORY_OBJECTIVE_ORDER == (
        "hard_constraints",
        "total_cost",
        "total_setup_cost",
        "max_inventory_level",
    )
    assert INVENTORY_CANDIDATE_LIFECYCLE == (
        "PROPOSED",
        "SOLVER_FEASIBLE",
        "INDEPENDENTLY_VALIDATED",
        "REDTEAM_PASSED",
        "ACCEPTED",
    )
    assert INVENTORY_TAMPER_TESTS == (
        "flow_balance_violation_injection",
        "setup_evasion_tamper",
        "capacity_overflow_injection",
        "safety_stock_deficit_tamper",
        "cost_deflation_forgery",
    )


# --------------------------------------------------------------------------- #
# 6. Red-team gate defensive robustness (bad input never crashes)
# --------------------------------------------------------------------------- #

MALFORMED_LOT_SIZING_SOLUTIONS: tuple[Any, ...] = (
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
    {"schedule": [{"period": 1}]},
    {"schedule": [{"period": 1, "demand": 0.0}]},
    {"schedule": [{"period": 1, "demand": 0.0, "production": 0.0}]},
    {"schedule": [{"period": 1, "demand": 0.0, "production": 0.0, "inventory": 0.0}]},
    {"schedule": [{"period": 1, "demand": 0.0, "production": 0.0, "inventory": 0.0, "setup": True}]},
    {"schedule": [{"period": 1, "demand": 0.0, "production": "x", "inventory": 0.0, "setup": True}]},
    {
        "schedule": [{"period": 1, "demand": 0.0, "production": 1.0, "inventory": 0.0, "setup": True}],
        "raw_demands": "nope",
    },
    {
        "schedule": [{"period": 1, "demand": 0.0, "production": 1.0, "inventory": 0.0, "setup": True}],
        "raw_demands": [1.0, 2.0],
    },
    {
        "schedule": [{"period": 1, "demand": 0.0, "production": 1.0, "inventory": 0.0, "setup": True}],
        "raw_demands": [1.0],
        "objective": "x",
    },
    {
        "schedule": [{"period": 1, "demand": 0.0, "production": 1.0, "inventory": 0.0, "setup": True}],
        "raw_demands": [1.0],
        "capacity": "x",
    },
    {
        "schedule": [{"period": 1, "demand": 0.0, "production": 1.0, "inventory": 0.0, "setup": True}],
        "raw_demands": [1.0],
        "safety_stock": "x",
    },
    {
        "schedule": [{"period": 1, "demand": 0.0, "production": 1.0, "inventory": 0.0, "setup": True}],
        "raw_demands": [1.0],
        "setup_costs": [85.0],
        "holding_costs": "nope",
    },
    {
        "schedule": [{"period": 1, "demand": 0.0, "production": 1.0, "inventory": 0.0, "setup": True}],
        "raw_demands": [1.0],
        "setup_costs": [85.0],
        "holding_costs": [1.0],
        "costs": "nope",
    },
    {"objective": "x", "schedule": []},
    {"objective": 100.0, "schedule": []},
    {"objective": 100.0},
    {"objective": None, "schedule": [{"period": 1}]},
)


@pytest.mark.parametrize("solution", MALFORMED_LOT_SIZING_SOLUTIONS)
def test_redteam_build_attacks_never_raises_on_malformed_solution(solution: Any) -> None:
    attacks = redteam_gate.build_attacks(solution)
    assert [row["attack"] for row in attacks] == list(redteam_gate.ATTACK_NAMES)
    for row in attacks:
        assert isinstance(row["applied"], bool)
        if not row["applied"]:
            assert isinstance(row["reason"], str) and row["reason"]


@pytest.mark.parametrize("solution", MALFORMED_LOT_SIZING_SOLUTIONS)
def test_redteam_run_redteam_never_raises_on_malformed_solution(solution: Any) -> None:
    report = redteam_gate.run_redteam(solution)
    assert report["ok"] is False
    assert report["schema"] == "orpath.inventory_redteam.v1"
    assert report["original_recompute_ok"] is False
    assert report["attack_count"] == len(redteam_gate.ATTACK_NAMES)
    for row in report["attacks"]:
        if row["applied"]:
            assert isinstance(row["failed_checks"], list)
        else:
            assert row["rejected"] is False
            assert isinstance(row["reason"], str) and row["reason"]


STRICT_UNAPPLIED_LOT_SIZING_SOLUTIONS: tuple[Any, ...] = (
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
)


@pytest.mark.parametrize("solution", STRICT_UNAPPLIED_LOT_SIZING_SOLUTIONS)
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


def test_redteam_build_attacks_captures_builder_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A builder that raises internally is converted into applied: false + reason."""
    def boom(_solution: Any) -> Any:
        raise TypeError("boom")

    monkeypatch.setitem(redteam_gate.ATTACK_BUILDERS, "flow_balance_violation_injection", boom)
    attacks = redteam_gate.build_attacks({"schedule": [{"production": 1.0}]})
    by_name = {row["attack"]: row for row in attacks}
    assert by_name["flow_balance_violation_injection"]["applied"] is False
    assert "TypeError" in by_name["flow_balance_violation_injection"]["reason"]


def test_redteam_build_attacks_does_not_mutate_input(clsp60_solution: dict[str, Any]) -> None:
    before = deepcopy(clsp60_solution)
    redteam_gate.build_attacks(clsp60_solution)
    assert clsp60_solution == before


def test_redteam_recompute_rejects_non_dict_payload() -> None:
    for payload in (None, "x", 42, [], 3.14, True):
        report = redteam_gate.recompute("wagner_whitin_clsp", payload)
        assert report["ok"] is False
        assert report["checks"] == []


def test_redteam_recompute_rejects_empty_dict() -> None:
    report = redteam_gate.recompute("wagner_whitin_clsp", {})
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
    assert report["schema"] == "orpath.inventory_redteam.v1"
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
# 7. Five DIMO tamper attacks vs. a real CLSP solution (100% interception)
# --------------------------------------------------------------------------- #

def test_ww12_solver_envelope_matches_published_optimum(
    ww12_solution: dict[str, Any],
) -> None:
    """Numbers Truth: the ww12 objective comes from the Wagner-Whitin DP, not prose."""
    assert ww12_solution["status"] == "OPTIMAL"
    assert ww12_solution["objective"] == 670.0
    assert ww12_solution["lower_bound"] == 670.0
    assert ww12_solution["optimality_gap"] == 0.0
    assert ww12_solution["known_optimum"] == 670.0
    assert ww12_solution["num_periods"] == 12
    assert len(ww12_solution["schedule"]) == 12


def test_clsp60_solver_envelope_is_internally_consistent(
    clsp60_solution: dict[str, Any],
) -> None:
    """Numbers Truth: the CLSP objective is the recomputed schedule total."""
    assert clsp60_solution["status"] in ("OPTIMAL", "FEASIBLE")
    assert clsp60_solution["num_periods"] == 12
    assert len(clsp60_solution["schedule"]) == 12
    assert clsp60_solution["capacity"] == 60.0
    # The delivered objective is recomputed from the delivered schedule.
    assert clsp60_solution["objective"] == clsp60_solution["costs"]["total"]
    assert clsp60_solution["metrics"]["objective"] == clsp60_solution["objective"]
    if clsp60_solution["lower_bound"] is not None:
        assert clsp60_solution["lower_bound"] <= clsp60_solution["objective"] + 1e-9
        assert abs(clsp60_solution["optimality_gap"] - (clsp60_solution["objective"] - clsp60_solution["lower_bound"])) <= 1e-9
    # Envelope series agree with the per-period schedule rows.
    assert clsp60_solution["production"] == [s["production"] for s in clsp60_solution["schedule"]]
    assert clsp60_solution["inventory"] == [s["inventory"] for s in clsp60_solution["schedule"]]
    assert clsp60_solution["setup_actions"] == [1 if s["setup"] else 0 for s in clsp60_solution["schedule"]]


def test_redteam_build_attacks_all_applied_on_clsp60(
    clsp60_solution: dict[str, Any],
) -> None:
    attacks = redteam_gate.build_attacks(clsp60_solution)
    assert len(attacks) == 5
    assert all(row["applied"] for row in attacks), [
        (row["attack"], row["reason"]) for row in attacks
    ]
    assert all(row["reason"] is None for row in attacks)
    assert clsp60_solution["schedule"]


def test_redteam_run_redteam_blocks_all_five_dimo_attacks(
    clsp60_solution: dict[str, Any],
) -> None:
    report = redteam_gate.run_redteam(clsp60_solution, "lot_sizing_clsp60")
    assert report["original_recompute_ok"] is True
    assert report["attacks_applied"] == 5

    by_name = {row["attack"]: row for row in report["attacks"]}
    expected_failures = {
        "flow_balance_violation_injection": "lot_sizing_flow_balance",
        "setup_evasion_tamper": "lot_sizing_setup_consistency",
        "capacity_overflow_injection": "lot_sizing_capacity_respected",
        "safety_stock_deficit_tamper": "lot_sizing_safety_stock",
        "cost_deflation_forgery": "lot_sizing_objective_match",
    }
    for name, failed_check in expected_failures.items():
        row = by_name[name]
        assert row["applied"] is True
        assert row["rejected"] is True, f"{name} was not blocked: {row['failed_checks']}"
        assert failed_check in row["failed_checks"], row["failed_checks"]
    assert report["ok"] is True


def test_redteam_cli_passes_when_every_attack_is_blocked(
    tmp_path: Path, clsp60_solution: dict[str, Any],
) -> None:
    solution = tmp_path / "wagner_whitin_clsp-solution.json"
    solution.write_text(json.dumps(clsp60_solution), encoding="utf-8")
    out = tmp_path / "wagner_whitin_clsp-redteam.json"

    exit_code = redteam_gate.main(["--solution", str(solution), "--out", str(out)])

    assert out.is_file()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema"] == "orpath.inventory_redteam.v1"
    assert report["problem_id"] == "lot_sizing_clsp60"
    assert report["original_recompute_ok"] is True
    assert report["attack_count"] == 5
    assert report["attacks_applied"] == 5
    assert report["ok"] is True
    assert all(row["rejected"] for row in report["attacks"])
    assert exit_code == 0


# --------------------------------------------------------------------------- #
# 8. Supervisor graph construction + mock node execution
# --------------------------------------------------------------------------- #

def test_inventory_supervisor_graph_compiles(model: Any) -> None:
    from orpath.agents.domains.inventory import build_inventory_supervisor_graph

    graph = build_inventory_supervisor_graph(model=model)
    assert isinstance(graph, StateGraph)


def test_inventory_compiled_supervisor_contains_all_nodes(model: Any) -> None:
    from orpath.agents.domains.inventory import build_compiled_inventory_supervisor

    compiled = build_compiled_inventory_supervisor(model=model)
    assert isinstance(compiled, CompiledStateGraph)
    for expected_node in INVENTORY_ALL_AGENT_NAMES:
        assert expected_node in compiled.nodes


def test_inventory_compiled_supervisor_runs_mock_pipeline() -> None:
    """Execute the compiled supervisor end to end with a mock LLM.

    The mock always answers with a bare reply, so the guard hook alone drives
    the handoff sequence: every one of the 5 worker nodes must run exactly once,
    in pipeline order, before the lead may terminate.
    """
    from orpath.agents.domains.inventory import build_compiled_inventory_supervisor

    mock = MockChatModel()
    compiled = build_compiled_inventory_supervisor(model=mock, enable_trim=False)
    final = compiled.invoke({"messages": [HumanMessage("run")]})

    # 1 supervisor decision per worker handoff + 5 worker model calls.
    assert mock.calls == 11

    transfers = [
        message.tool_calls[0]["name"]
        for message in final["messages"]
        if getattr(message, "tool_calls", None)
    ]
    for worker in INVENTORY_WORKER_NAMES:
        assert f"transfer_to_{worker}" in transfers
        assert f"transfer_back_to_{INVENTORY_LEAD_NAME}" in transfers

    # Each worker node answered exactly once, in pipeline order.
    worker_answers = [
        message
        for message in final["messages"]
        if getattr(message, "name", None) in INVENTORY_WORKER_NAMES
        and not getattr(message, "tool_calls", None)
    ]
    assert [getattr(m, "name", None) for m in worker_answers] == list(INVENTORY_WORKER_NAMES)

    # The run ends with the lead's bare reply (guard hook allowed termination).
    assert final["messages"][-1].name == INVENTORY_LEAD_NAME
    assert not final["messages"][-1].tool_calls
    assert final["messages"][-1].content == "mock final reply"


# --------------------------------------------------------------------------- #
# 9. Domain tools: contract + collaboration gate + red-team gate wrapper
# --------------------------------------------------------------------------- #

def test_validate_inventory_contract_tool() -> None:
    result = json.loads(validate_inventory_contract.invoke({}))
    assert result["ok"] is True
    assert result["schema"] == "orpath.inventory_collaboration.v1"
    assert result["problem_id"] == "wagner_whitin_clsp"
    assert result["errors"] == []
    assert "or-inventory-lead" in result["roles"]


def test_run_inventory_collaboration_gate_tool(inventory_golden_ledger: Path) -> None:
    result = json.loads(run_inventory_collaboration_gate.invoke({}))
    assert result["ok"] is True
    assert result["gate"] == "inventory_collaboration_gate"
    assert result["contract"]["ok"] is True
    assert result["budget_ledger"]["ok"] is True
    assert result["budget_ledger"]["budget_matches_protocol"] is True


def test_run_inventory_redteam_gate_tool_writes_report(
    tmp_path: Path, clsp60_solution: dict[str, Any],
) -> None:
    solution = tmp_path / "wagner_whitin_clsp-solution.json"
    solution.write_text(json.dumps(clsp60_solution), encoding="utf-8")
    out = tmp_path / "wagner_whitin_clsp-redteam.json"

    result = json.loads(
        run_inventory_redteam_gate.invoke(
            {"solution_path": str(solution), "out_path": str(out)}
        )
    )
    assert result["ok"] is True
    assert result["returncode"] == 0
    assert result["report"]["schema"] == "orpath.inventory_redteam.v1"
    assert result["report"]["ok"] is True


def test_run_inventory_redteam_gate_tool_handles_missing_solution(
    tmp_path: Path,
) -> None:
    result = json.loads(
        run_inventory_redteam_gate.invoke(
            {
                "solution_path": str(tmp_path / "absent.json"),
                "out_path": str(tmp_path / "redteam.json"),
            }
        )
    )
    assert result["ok"] is False
    assert "not found" in result["error"]
