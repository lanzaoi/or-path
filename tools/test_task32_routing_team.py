#!/usr/bin/env python3
"""Phase 3 / Task 3.2 — Vehicle Routing & Logistics team + hardening tests.

Covers the Phase 3.2 deliverables:

1. ``contracts/routing_collaboration_v1.json`` validates against the Domain
   Collaboration meta-schema.
2. ``orpath/agents/domains/routing.py`` wires the Phase 1 foundation modules
   (``guard_factory``, ``domain_state``, ``budget_engine``) while keeping the
   Lead + Pentad pattern verified in ``tube.py``.
3. ``scripts/routing_redteam_gate.py`` never crashes on an unexpected solution
   schema; it fails safely with a structured report instead.
4. The 6-role routing team builds and enforces its pipeline order, and the
   5 DIMO tamper attacks are all rejected by the independent red-team gate.
"""
from __future__ import annotations

import json
import math
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
from orpath.agents.domains.routing import (  # noqa: E402
    AUDITOR_PROMPT,
    DEFAULT_ROUTING_LEAD_PROMPT,
    EXACT_BOUND_PROMPT,
    HGS_PROMPT,
    REDTEAM_PROMPT,
    REALITY_PROMPT,
    ROUTING_ALL_AGENT_NAMES,
    ROUTING_AUDITOR_NAME,
    ROUTING_CANDIDATE_LIFECYCLE,
    ROUTING_DISCRETIONARY_BUDGET,
    ROUTING_EXACT_BOUND_NAME,
    ROUTING_GUARD_CALL_IDS,
    ROUTING_HGS_NAME,
    ROUTING_LEAD_NAME,
    ROUTING_OBJECTIVE_ORDER,
    ROUTING_PIPELINE_STAGE_ORDER,
    ROUTING_REALITY_NAME,
    ROUTING_REDTEAM_NAME,
    ROUTING_RISK_OVERRIDE_BUDGET,
    ROUTING_TAMPER_TESTS,
    ROUTING_WORKER_NAMES,
    RoutingSupervisorState,
    check_routing_budget_ledger,
    create_routing_auditor_agent,
    create_routing_exact_bound_agent,
    create_routing_hgs_agent,
    create_routing_lead_agent,
    create_routing_realities_agent,
    create_routing_redteam_agent,
    get_routing_workers,
    routing_guard_post_hook,
    run_routing_collaboration_gate,
    run_routing_redteam_gate,
    validate_routing_contract,
)
from orpath.agents.guard_factory import create_domain_guard_hook  # noqa: E402
from orpath.control_plane import get_chat_model  # noqa: E402

import routing_redteam_gate as redteam_gate  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore:create_react_agent has been moved")

META_SCHEMA_PATH = ROOT / "contracts" / "meta" / "domain_collaboration.schema.json"
ROUTING_CONTRACT_PATH = ROOT / "contracts" / "routing_collaboration_v1.json"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture()
def model() -> Any:
    return get_chat_model()


@pytest.fixture(scope="module", autouse=True)
def routing_golden_ledger() -> Path:
    """Provision the (gitignored) golden routing budget ledger for tool tests."""
    path = ROOT / "experiments" / "routing" / "budget-ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger = {
        "schema": "orpath.routing_budget_ledger.v1",
        "date": "2026-01-01",
        "scope": "discretionary_experiment_effort_excluding_baseline_and_gates",
        "budget_percent": dict(ROUTING_DISCRETIONARY_BUDGET),
    }
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _build_strict_envelope() -> dict[str, Any]:
    """Build a small VRPTW solution that ``validate_pyvrp`` accepts."""
    depot = {"name": "DEPOT", "coords": [0.0, 0.0], "tw_early": 0, "tw_late": 1000}
    clients = [
        {"name": "C1", "coords": [2.0, 3.0], "demand": 10, "tw_early": 0, "tw_late": 1000},
        {"name": "C2", "coords": [5.0, 1.0], "demand": 20, "tw_early": 0, "tw_late": 1000},
        {"name": "C3", "coords": [1.0, 6.0], "demand": 15, "tw_early": 0, "tw_late": 1000},
        {"name": "C4", "coords": [8.0, 4.0], "demand": 25, "tw_early": 0, "tw_late": 1000},
        {"name": "C5", "coords": [4.0, 7.0], "demand": 30, "tw_early": 0, "tw_late": 1000},
    ]

    def dist(a: list[float], b: list[float]) -> int:
        return int(round(math.hypot(a[0] - b[0], a[1] - b[1])))

    order = [depot, *clients, depot]
    coords = [node["coords"] for node in order]
    leg_distances = [dist(coords[i], coords[i + 1]) for i in range(len(coords) - 1)]
    total_distance = sum(leg_distances)

    arrival = [0]
    for leg in leg_distances:
        arrival.append(arrival[-1] + leg)

    visits: list[dict[str, Any]] = []
    for index, node in enumerate(order):
        if index == 0:
            visits.append(
                {"type": "depot", "name": "DEPOT", "demand": 0,
                 "start_time": 0.0, "end_time": 0.0}
            )
        elif index == len(order) - 1:
            visits.append(
                {"type": "depot", "name": "DEPOT", "demand": 0,
                 "start_time": arrival[index], "end_time": arrival[index]}
            )
        else:
            visits.append(
                {"type": "client", "name": node["name"], "demand": node["demand"],
                 "start_time": arrival[index], "end_time": arrival[index]}
            )

    location_idx = [0, *range(1, len(clients) + 1), 0]
    route = {
        "vehicle": 1,
        "route": location_idx,
        "distance": total_distance,
        "load": sum(c["demand"] for c in clients),
        "timeline": [
            {"location_idx": idx, "start_time": v["start_time"], "end_time": v["end_time"]}
            for idx, v in zip(location_idx, visits)
        ],
        "visits": visits,
    }

    envelope = {
        "problem_id": "pyvrp_vrptw",
        "problem_class": "pyvrp",
        "status": "FEASIBLE",
        "objective": total_distance,
        "total_distance": total_distance,
        "vehicle_capacity": 100,
        "num_clients": len(clients),
        "num_vehicles_used": 1,
        "routes": [route],
        "raw_depot": depot,
        "raw_clients": clients,
        "raw_shipments": [],
    }
    envelope["input_coordinates_sha256"] = redteam_gate.coordinate_integrity_hash(envelope)
    return envelope


@pytest.fixture(scope="module")
def strict_envelope() -> dict[str, Any]:
    return _build_strict_envelope()


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

def test_routing_contract_file_wellformed() -> None:
    schema = _load_json(META_SCHEMA_PATH)
    assert schema["$schema"] == DRAFT07_URL
    assert schema["type"] == "object"
    assert schema["required"] == META_REQUIRED
    assert schema["definitions"]["role"]["required"] == ["owns", "forbidden"]


def test_routing_contract_validates_against_meta_schema() -> None:
    schema = _load_json(META_SCHEMA_PATH)
    doc = _load_json(ROUTING_CONTRACT_PATH)
    errors = _validate_meta(doc, schema, schema)
    assert errors == [], errors

    # Domain-specific extras are permitted by additionalProperties: true.
    extras = set(doc) - set(schema["properties"])
    assert {"handoff_order", "experiment_rules", "registry", "tamper_tests"} <= extras


def test_routing_contract_schema_id_matches_pattern() -> None:
    schema = _load_json(META_SCHEMA_PATH)
    pattern = schema["properties"]["schema"]["pattern"]
    doc = _load_json(ROUTING_CONTRACT_PATH)
    assert re.search(pattern, doc["schema"]), doc["schema"]


def test_routing_contract_budget_sums_to_100() -> None:
    doc = _load_json(ROUTING_CONTRACT_PATH)
    assert sum(doc["budget_percent"].values()) == 100
    assert doc["budget_percent"] == {"auditor": 20, "exact_bound": 15, "hgs": 35, "realities": 30}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema="routing_collaboration.v1"),
        lambda d: d.update(schema="orpath.routing_collaboration.vX"),
        lambda d: d.update(problem_id=None),
        lambda d: d.update(numeric_authority=7),
        lambda d: d.update(budget_scope=7),
        lambda d: d.update(objective_order="hard_constraints"),
        lambda d: d["budget_percent"].update(auditor="twenty"),
        lambda d: d["budget_percent"].update(auditor=20.5),
        lambda d: d.update(roles=[]),
        lambda d: d["roles"]["or-vrp-lead"].pop("owns"),
        lambda d: d["roles"]["or-vrp-hgs"].pop("forbidden"),
        lambda d: d["roles"]["or-vrp-redteam"].clear(),
        lambda d: d["roles"]["or-vrp-auditor"].update(owns="not-a-list"),
        lambda d: d["roles"]["or-vrp-exact-bound"].update(forbidden=[3]),
        lambda d: d.update(candidate_lifecycle="PROPOSED"),
        lambda d: d["stop_rules"].update(hgs="stop_after_two_budget_levels"),
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
def test_tampered_routing_contract_rejected(mutate: Any) -> None:
    schema = _load_json(META_SCHEMA_PATH)
    doc = _load_json(ROUTING_CONTRACT_PATH)
    mutate(doc)
    errors = _validate_meta(doc, schema, schema)
    assert errors, f"tampered routing contract unexpectedly validated: {mutate}"


# --------------------------------------------------------------------------- #
# 2. Six-role routing team
# --------------------------------------------------------------------------- #

def test_routing_team_six_role_roster() -> None:
    assert ROUTING_WORKER_NAMES == (
        ROUTING_AUDITOR_NAME,
        ROUTING_EXACT_BOUND_NAME,
        ROUTING_HGS_NAME,
        ROUTING_REALITY_NAME,
        ROUTING_REDTEAM_NAME,
    )
    assert ROUTING_ALL_AGENT_NAMES == (ROUTING_LEAD_NAME, *ROUTING_WORKER_NAMES)
    assert len(ROUTING_ALL_AGENT_NAMES) == 6
    assert ROUTING_PIPELINE_STAGE_ORDER == ROUTING_WORKER_NAMES
    assert set(ROUTING_GUARD_CALL_IDS) == set(ROUTING_WORKER_NAMES)


def test_routing_team_all_six_agents_creable(model: Any) -> None:
    lead = create_routing_lead_agent(model=model)
    assert lead.name == ROUTING_LEAD_NAME

    assert create_routing_auditor_agent(model=model).name == ROUTING_AUDITOR_NAME
    assert create_routing_exact_bound_agent(model=model).name == ROUTING_EXACT_BOUND_NAME
    assert create_routing_hgs_agent(model=model).name == ROUTING_HGS_NAME
    assert create_routing_realities_agent(model=model).name == ROUTING_REALITY_NAME
    assert create_routing_redteam_agent(model=model).name == ROUTING_REDTEAM_NAME

    workers = get_routing_workers(model=model)
    assert [w.name for w in workers] == list(ROUTING_WORKER_NAMES)


def test_routing_team_prompts_unchanged() -> None:
    for prompt in (
        DEFAULT_ROUTING_LEAD_PROMPT,
        AUDITOR_PROMPT,
        EXACT_BOUND_PROMPT,
        HGS_PROMPT,
        REALITY_PROMPT,
        REDTEAM_PROMPT,
    ):
        assert isinstance(prompt, str) and len(prompt) > 50


def test_routing_protocol_constants() -> None:
    assert ROUTING_DISCRETIONARY_BUDGET == {"auditor": 20, "exact_bound": 15, "hgs": 35, "realities": 30}
    assert sum(ROUTING_DISCRETIONARY_BUDGET.values()) == 100
    assert ROUTING_RISK_OVERRIDE_BUDGET == {"auditor": 35, "exact_bound": 10, "hgs": 30, "realities": 25}
    assert sum(ROUTING_RISK_OVERRIDE_BUDGET.values()) == 100
    assert ROUTING_OBJECTIVE_ORDER[0] == "hard_constraints"
    assert ROUTING_CANDIDATE_LIFECYCLE == (
        "PROPOSED",
        "SOLVER_FEASIBLE",
        "INDEPENDENTLY_VALIDATED",
        "REDTEAM_PASSED",
        "ACCEPTED",
    )
    assert ROUTING_TAMPER_TESTS == (
        "capacity_overflow_injection",
        "client_omission_tamper",
        "time_window_inversion",
        "distance_forgery",
        "coordinate_hash_tamper",
    )


# --------------------------------------------------------------------------- #
# 3. RoutingSupervisorState inherits the Phase 1 domain state
# --------------------------------------------------------------------------- #

def test_routing_supervisor_state_inherits_domain_supervisor_state() -> None:
    assert RoutingSupervisorState.__orig_bases__ == (DomainSupervisorState,)


def test_routing_supervisor_state_keeps_routing_specific_fields() -> None:
    from typing import get_type_hints

    hints = get_type_hints(RoutingSupervisorState)
    for flag in (
        "has_auditor_verified",
        "has_exact_bound_computed",
        "has_hgs_solved",
        "has_realities_applied",
        "has_redteam_verified",
    ):
        assert flag in hints and hints[flag] is bool
    assert hints["exact_bound_report_path"] is str
    assert hints["domain"] is str
    assert hints["problem_id"] is str


def test_routing_supervisor_state_inherits_canonical_fields() -> None:
    from typing import get_type_hints

    base_fields = set(get_type_hints(DomainSupervisorState))
    routing_hints = get_type_hints(RoutingSupervisorState)
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
        assert field in routing_hints, f"RoutingSupervisorState lost inherited {field}"
        assert field in base_fields

    assert RoutingSupervisorState.__dict__["domain"] == "routing"
    assert RoutingSupervisorState.__dict__["problem_id"] == "pyvrp_vrptw"


def test_routing_state_stage_progress_is_readable() -> None:
    state = RoutingSupervisorState(
        messages=[HumanMessage("run")],
        domain="routing",
        or_vrp_auditor=True,
        or_vrp_exact_bound=True,
    )
    progress = get_state_stage_progress(state, ROUTING_PIPELINE_STAGE_ORDER)
    assert progress["domain"] == "routing"
    assert progress["total_stages"] == 5
    assert progress["completed_count"] == 2
    assert progress["next_stage"] == ROUTING_HGS_NAME
    assert 0.0 < progress["progress"] < 1.0

    transcript = RoutingSupervisorState(
        messages=[HumanMessage("run"), AIMessage("g", name=ROUTING_AUDITOR_NAME)]
    )
    fallback = get_state_stage_progress(transcript, ROUTING_PIPELINE_STAGE_ORDER)
    assert fallback["completed_count"] == 1
    assert fallback["next_stage"] == ROUTING_EXACT_BOUND_NAME


# --------------------------------------------------------------------------- #
# 4. Routing guard hook is the guard_factory product and enforces order
# --------------------------------------------------------------------------- #

def test_routing_guard_hook_is_built_by_guard_factory() -> None:
    assert routing_guard_post_hook.__name__ == "domain_guard_post_hook"

    fresh = create_domain_guard_hook(ROUTING_PIPELINE_STAGE_ORDER, ROUTING_GUARD_CALL_IDS)
    states = [
        {"messages": []},
        {"messages": [HumanMessage("start")]},
        {"messages": [HumanMessage("run"), AIMessage("done", id="m1")]},
        {
            "messages": [
                HumanMessage("run"),
                AIMessage("a", name=ROUTING_AUDITOR_NAME),
                AIMessage("done", id="m2"),
            ]
        },
    ]
    for state in states:
        assert routing_guard_post_hook(state) == fresh(state)


def test_routing_guard_hook_enforces_sequential_stage_order() -> None:
    # Empty / non-AI / already-routing states pass through untouched.
    assert routing_guard_post_hook({"messages": []}) == {}
    assert routing_guard_post_hook({"messages": [HumanMessage("start")]}) == {}
    assert routing_guard_post_hook(
        {"messages": [AIMessage("routing", tool_calls=[{"name": "x", "args": {}, "id": "c"}])]}
    ) == {}

    def bare(messages: list[Any]) -> str:
        update = routing_guard_post_hook({"messages": messages})
        assert update, f"guard did not act on {messages!r}"
        injected = update["messages"][-1]
        assert injected.tool_calls[0]["id"] in ROUTING_GUARD_CALL_IDS.values()
        return injected.tool_calls[0]["name"]

    # Stage 1: nothing done yet -> auditor.
    assert bare([HumanMessage("run"), AIMessage("done", id="m1")]) == (
        "transfer_to_or_vrp_auditor"
    )

    # Stage 2: auditor done -> exact_bound (a *later* stage being done must not
    # skip the first missing one).
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("a", name=ROUTING_AUDITOR_NAME),
            AIMessage("rt", name=ROUTING_REDTEAM_NAME),
            AIMessage("done", id="m2"),
        ]
    ) == "transfer_to_or_vrp_exact_bound"

    # Stage 3: auditor + exact_bound done -> hgs.
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("a", name=ROUTING_AUDITOR_NAME),
            AIMessage("b", name=ROUTING_EXACT_BOUND_NAME),
            AIMessage("done", id="m3"),
        ]
    ) == "transfer_to_or_vrp_hgs"

    # Stage 4: auditor + exact_bound + hgs done -> realities.
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("a", name=ROUTING_AUDITOR_NAME),
            AIMessage("b", name=ROUTING_EXACT_BOUND_NAME),
            AIMessage("h", name=ROUTING_HGS_NAME),
            AIMessage("done", id="m4"),
        ]
    ) == "transfer_to_or_vrp_realities"

    # Stage 5: four stages done -> redteam.
    assert bare(
        [
            HumanMessage("run"),
            AIMessage("a", name=ROUTING_AUDITOR_NAME),
            AIMessage("b", name=ROUTING_EXACT_BOUND_NAME),
            AIMessage("h", name=ROUTING_HGS_NAME),
            AIMessage("r", name=ROUTING_REALITY_NAME),
            AIMessage("done", id="m5"),
        ]
    ) == "transfer_to_or_vrp_redteam"

    # Stage 6: every stage handed off -> bare reply is allowed.
    assert routing_guard_post_hook(
        {
            "messages": [
                HumanMessage("run"),
                AIMessage("a", name=ROUTING_AUDITOR_NAME),
                AIMessage("b", name=ROUTING_EXACT_BOUND_NAME),
                AIMessage("h", name=ROUTING_HGS_NAME),
                AIMessage("r", name=ROUTING_REALITY_NAME),
                AIMessage("rt", name=ROUTING_REDTEAM_NAME),
                AIMessage("completed", id="m6"),
            ]
        }
    ) == {}


# --------------------------------------------------------------------------- #
# 5. Supervisor graph compilation
# --------------------------------------------------------------------------- #

def test_routing_supervisor_graph_compiles(model: Any) -> None:
    from orpath.agents.domains.routing import build_routing_supervisor_graph

    graph = build_routing_supervisor_graph(model=model)
    assert isinstance(graph, StateGraph)


def test_routing_compiled_supervisor_contains_all_nodes(model: Any) -> None:
    from orpath.agents.domains.routing import build_compiled_routing_supervisor

    compiled = build_compiled_routing_supervisor(model=model)
    assert isinstance(compiled, CompiledStateGraph)
    for expected_node in ROUTING_ALL_AGENT_NAMES:
        assert expected_node in compiled.nodes


# --------------------------------------------------------------------------- #
# 6. Budget checking through BudgetLedgerManager
# --------------------------------------------------------------------------- #

def test_budget_ledger_manager_audits_routing_ledger(routing_golden_ledger: Path) -> None:
    report = audit_file(
        routing_golden_ledger,
        expected_budget=ROUTING_DISCRETIONARY_BUDGET,
        root=ROOT,
    )
    assert report["ok"] is True
    assert report["validation"]["ok"] is True
    assert report["compliance"]["budget_percent"] == ROUTING_DISCRETIONARY_BUDGET
    assert report["compliance"]["budget_sum"] == 100
    assert report["risk_override"]["active"] is False


def test_budget_ledger_manager_rejects_drift() -> None:
    ledger = {"budget_percent": dict(ROUTING_DISCRETIONARY_BUDGET)}
    ledger["budget_percent"]["auditor"] = 21
    ok, errors = BudgetLedgerManager(ledger=ledger).validate()
    assert ok is False
    assert any("budget_percent" in error for error in errors)


def test_budget_ledger_manager_tracks_risk_override_lifecycle() -> None:
    manager = BudgetLedgerManager(
        domain="routing",
        ledger={"budget_percent": dict(ROUTING_DISCRETIONARY_BUDGET)},
        baseline_budget=ROUTING_DISCRETIONARY_BUDGET,
        override_budget=ROUTING_RISK_OVERRIDE_BUDGET,
    )
    assert manager.effective_budget() == ROUTING_DISCRETIONARY_BUDGET

    effective = manager.apply_override(
        trigger="input_gate_red",
        temporary_percent=ROUTING_RISK_OVERRIDE_BUDGET,
        release_condition="input_gate_green",
        evidence="outputs/routing-audit.json",
    )
    assert effective == ROUTING_RISK_OVERRIDE_BUDGET
    assert manager.active_overrides()

    assert manager.release_override() == ROUTING_DISCRETIONARY_BUDGET
    assert manager.active_overrides() == []


def test_evaluate_risk_override_helper() -> None:
    assert evaluate_risk_override([], ROUTING_DISCRETIONARY_BUDGET) == ROUTING_DISCRETIONARY_BUDGET
    assert evaluate_risk_override(
        [{"trigger": "t", "released": True}], ROUTING_DISCRETIONARY_BUDGET
    ) == ROUTING_DISCRETIONARY_BUDGET
    assert evaluate_risk_override(
        [{"trigger": "t", "temporary_percent": ROUTING_RISK_OVERRIDE_BUDGET}],
        ROUTING_DISCRETIONARY_BUDGET,
    ) == ROUTING_RISK_OVERRIDE_BUDGET


def test_check_routing_budget_ledger_tool_is_backward_compatible(
    routing_golden_ledger: Path,
) -> None:
    result = json.loads(check_routing_budget_ledger.invoke({}))
    assert result["ok"] is True
    assert result["budget_percent"] == {"auditor": 20, "exact_bound": 15, "hgs": 35, "realities": 30}
    assert result["budget_matches_protocol"] is True
    assert result["total_budget_sum"] == 100
    assert result["audit"]["ok"] is True


def test_check_routing_budget_ledger_tool_handles_missing_ledger(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    result = json.loads(check_routing_budget_ledger.invoke({"ledger_path": str(missing)}))
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_check_routing_budget_ledger_tool_handles_malformed_ledger(tmp_path: Path) -> None:
    broken = tmp_path / "ledger.json"
    broken.write_text("[1, 2, 3]", encoding="utf-8")
    result = json.loads(check_routing_budget_ledger.invoke({"ledger_path": str(broken)}))
    assert result["ok"] is False
    assert "JSON object" in result["error"]


# --------------------------------------------------------------------------- #
# 7. Domain tools: contract + collaboration gate + red-team gate wrapper
# --------------------------------------------------------------------------- #

def test_validate_routing_contract_tool() -> None:
    result = json.loads(validate_routing_contract.invoke({}))
    assert result["ok"] is True
    assert result["schema"] == "orpath.routing_collaboration.v1"
    assert result["problem_id"] == "pyvrp_vrptw"
    assert result["errors"] == []
    assert "or-vrp-lead" in result["roles"]


def test_run_routing_collaboration_gate_tool(routing_golden_ledger: Path) -> None:
    result = json.loads(run_routing_collaboration_gate.invoke({}))
    assert result["ok"] is True
    assert result["gate"] == "routing_collaboration_gate"
    assert result["contract"]["ok"] is True
    assert result["budget_ledger"]["ok"] is True
    assert result["budget_ledger"]["budget_matches_protocol"] is True


def test_run_routing_redteam_gate_tool_writes_report(
    tmp_path: Path, strict_envelope: dict[str, Any]
) -> None:
    solution = tmp_path / "pyvrp_vrptw-solution.json"
    solution.write_text(json.dumps(strict_envelope), encoding="utf-8")
    out = tmp_path / "pyvrp_vrptw-redteam.json"

    result = json.loads(
        run_routing_redteam_gate.invoke(
            {"solution_path": str(solution), "out_path": str(out)}
        )
    )
    assert result["ok"] is True
    assert result["returncode"] == 0
    assert result["report"]["schema"] == "orpath.routing_redteam.v1"
    assert result["report"]["ok"] is True


# --------------------------------------------------------------------------- #
# 8. Red-team gate robustness
# --------------------------------------------------------------------------- #

MALFORMED_SOLUTIONS: tuple[Any, ...] = (
    None,
    "not-a-dict",
    42,
    [],
    {},
    {"routes": "not-a-list"},
    {"routes": None},
    {"routes": []},
    {"routes": [None]},
    {"routes": ["x"]},
    {"routes": [{}]},
    {"routes": [{"visits": []}]},
    {"routes": [{"visits": [None]}]},
    {"routes": [{"visits": ["x"]}]},
    {"routes": [{"visits": [{"type": "client"}]}]},
    {"routes": [{"visits": [{"type": "depot", "end_time": "x"}]}]},
    {"vehicle_capacity": "nope", "routes": []},
    {"vehicle_capacity": 100, "routes": [{"distance": "x"}]},
    {"raw_depot": "nope", "raw_clients": "nope"},
    {"raw_depot": {}, "raw_clients": []},
)


@pytest.mark.parametrize("solution", MALFORMED_SOLUTIONS)
def test_redteam_build_attacks_never_raises_on_malformed_solution(solution: Any) -> None:
    attacks = redteam_gate.build_attacks(solution)
    assert [row["attack"] for row in attacks] == list(redteam_gate.ATTACK_NAMES)
    for row in attacks:
        assert isinstance(row["applied"], bool)
        if not row["applied"]:
            assert isinstance(row["reason"], str) and row["reason"]


def test_redteam_build_attacks_does_not_mutate_input(strict_envelope: dict[str, Any]) -> None:
    before = deepcopy(strict_envelope)
    redteam_gate.build_attacks(strict_envelope)
    assert strict_envelope == before


@pytest.mark.parametrize("solution", MALFORMED_SOLUTIONS)
def test_redteam_run_redteam_never_raises_on_malformed_solution(solution: Any) -> None:
    report = redteam_gate.run_redteam(solution)
    assert report["ok"] is False
    assert report["schema"] == "orpath.routing_redteam.v1"
    assert report["original_recompute_ok"] is False
    assert report["attack_count"] == len(redteam_gate.ATTACK_NAMES)
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
    assert strict_envelope["routes"][0]["visits"]


def test_redteam_run_redteam_blocks_all_five_attacks(
    strict_envelope: dict[str, Any],
) -> None:
    report = redteam_gate.run_redteam(strict_envelope, "pyvrp_vrptw")
    assert report["original_recompute_ok"] is True
    assert report["attacks_applied"] == 5

    by_name = {row["attack"]: row for row in report["attacks"]}
    for name in redteam_gate.ATTACK_NAMES:
        row = by_name[name]
        assert row["applied"] is True
        assert row["rejected"] is True, f"{name} was not blocked: {row['failed_checks']}"
        assert row["failed_checks"]
    assert report["ok"] is True


def test_redteam_original_recompute_runs_pyvrp_checks(
    strict_envelope: dict[str, Any],
) -> None:
    report = redteam_gate.recompute("pyvrp_vrptw", strict_envelope)
    assert report["ok"] is True
    names = {c["name"] for c in report["checks"]}
    assert {
        "pyvrp_status_feasible",
        "pyvrp_depot_endpoints",
        "pyvrp_client_visits_complete",
        "pyvrp_capacity_respected",
        "pyvrp_time_windows_respected",
        "pyvrp_distance_matches_objective",
        "pyvrp_coordinate_integrity_hash",
    } <= names


def test_redteam_recompute_rejects_non_dict_payload() -> None:
    for payload in (None, "x", 42, [], 3.14, True):
        report = redteam_gate.recompute("pyvrp_vrptw", payload)
        assert report["ok"] is False
        assert report["checks"] == []


def test_redteam_recompute_rejects_empty_dict() -> None:
    report = redteam_gate.recompute("pyvrp_vrptw", {})
    assert report["ok"] is False
    assert report["checks"]


def test_redteam_coordinate_integrity_hash_is_stable() -> None:
    envelope = _build_strict_envelope()
    first = redteam_gate.coordinate_integrity_hash(envelope)
    second = redteam_gate.coordinate_integrity_hash(deepcopy(envelope))
    assert first == second
    assert len(first) == 64
    assert redteam_gate.coordinate_integrity_hash("not-a-dict") is None


def test_redteam_coordinate_hash_tamper_detected(
    strict_envelope: dict[str, Any],
) -> None:
    tampered = deepcopy(strict_envelope)
    tampered["input_coordinates_sha256"] = "0" * 64
    report = redteam_gate.recompute("pyvrp_vrptw", tampered)
    assert report["ok"] is False
    assert "pyvrp_coordinate_integrity_hash" in {c["name"] for c in report["checks"] if not c["ok"]}


# --------------------------------------------------------------------------- #
# 9. Red-team gate CLI
# --------------------------------------------------------------------------- #

def test_redteam_cli_rejects_malformed_solution_without_crashing(tmp_path: Path) -> None:
    solution = tmp_path / "solution.json"
    solution.write_text(json.dumps({"routes": [{"visits": []}]}), encoding="utf-8")
    out = tmp_path / "redteam.json"

    exit_code = redteam_gate.main(["--solution", str(solution), "--out", str(out)])

    assert exit_code == 1
    assert out.is_file()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema"] == "orpath.routing_redteam.v1"
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


def test_redteam_cli_passes_when_every_attack_is_blocked(
    tmp_path: Path, strict_envelope: dict[str, Any]
) -> None:
    solution = tmp_path / "pyvrp_vrptw-solution.json"
    solution.write_text(json.dumps(strict_envelope), encoding="utf-8")
    out = tmp_path / "redteam.json"

    exit_code = redteam_gate.main(["--solution", str(solution), "--out", str(out)])

    assert out.is_file()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema"] == "orpath.routing_redteam.v1"
    assert report["problem_id"] == "pyvrp_vrptw"
    assert report["original_recompute_ok"] is True
    assert report["attack_count"] == 5
    assert report["attacks_applied"] == 5
    assert report["ok"] is True
    assert all(row["rejected"] for row in report["attacks"])
    assert exit_code == 0
