#!/usr/bin/env python3
"""Phase 3 / Task 3.7 — Staff Rostering team + hardening tests.

Covers contract vs. meta-schema, golden budget-ledger audit (20/15/35/30),
RosteringSupervisorState inheritance, guard hook blocking early termination,
6-role roster/prompts/agents, red-team gate robustness, 5 DIMO tamper attacks
on real CP-SAT rostering solutions (100% interception), supervisor mock
pipeline, and the 4 domain tools.
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

from orpath.agents.budget_engine import BudgetLedgerManager, audit_file  # noqa: E402
from orpath.agents.domain_state import (  # noqa: E402
    DomainSupervisorState,
    get_state_stage_progress,
)
from orpath.agents.domains.rostering import (  # noqa: E402
    DEFAULT_ROSTERING_LEAD_PROMPT, ROSTERING_ALL_AGENT_NAMES, ROSTERING_AUDITOR_NAME,
    ROSTERING_AUDITOR_PROMPT, ROSTERING_CANDIDATE_LIFECYCLE, ROSTERING_DISCRETIONARY_BUDGET,
    ROSTERING_EXACT_BOUND_NAME, ROSTERING_EXACT_BOUND_PROMPT, ROSTERING_GUARD_CALL_IDS,
    ROSTERING_HEURISTIC_NAME, ROSTERING_HEURISTIC_PROMPT, ROSTERING_LEAD_NAME,
    ROSTERING_OBJECTIVE_ORDER, ROSTERING_PIPELINE_STAGE_ORDER, ROSTERING_REALITY_NAME,
    ROSTERING_REALITY_PROMPT, ROSTERING_REDTEAM_NAME, ROSTERING_REDTEAM_PROMPT,
    ROSTERING_RISK_OVERRIDE_BUDGET, ROSTERING_TAMPER_TESTS, ROSTERING_WORKER_NAMES,
    RosteringSupervisorState, check_rostering_budget_ledger, create_rostering_auditor_agent,
    create_rostering_exact_bound_agent, create_rostering_heuristic_agent,
    create_rostering_lead_agent, create_rostering_realities_agent, create_rostering_redteam_agent,
    get_rostering_workers, rostering_guard_post_hook, run_rostering_collaboration_gate,
    run_rostering_redteam_gate, validate_rostering_contract,
)
from orpath.agents.guard_factory import create_domain_guard_hook  # noqa: E402
from orpath.control_plane import get_chat_model  # noqa: E402

import rostering_redteam_gate as redteam_gate  # noqa: E402
from solve_staff_rostering import solve_staff_rostering  # noqa: E402
from validators.extended_solvers import validate_staff_rostering  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore:create_react_agent has been moved")

META_SCHEMA_PATH = ROOT / "contracts" / "meta" / "domain_collaboration.schema.json"
ROSTERING_CONTRACT_PATH = ROOT / "contracts" / "rostering_collaboration_v1.json"
LEDGER_PATH = ROOT / "experiments" / "rostering" / "budget-ledger.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# --- fixtures --------------------------------------------------------------- #

@pytest.fixture()
def model() -> Any:
    return get_chat_model()


@pytest.fixture(scope="module", autouse=True)
def rostering_golden_ledger() -> Path:
    """Provision the (gitignored) golden rostering budget ledger for tool tests."""
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(
        {"schema": "orpath.rostering_budget_ledger.v1", "date": "2026-01-01",
         "scope": "discretionary_experiment_effort_excluding_baseline_and_gates",
         "budget_percent": dict(ROSTERING_DISCRETIONARY_BUDGET)},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return LEDGER_PATH


@pytest.fixture(scope="module")
def rostering_solutions() -> tuple[dict[str, Any], dict[str, Any]]:
    """Two real CP-SAT rostering solutions covering the DIMO attack surface."""
    default_sol = solve_staff_rostering(num_employees=8, num_days=14, time_limit_s=10)
    variant_sol = solve_staff_rostering(
        num_employees=10, num_days=7, max_consecutive_days=3, time_limit_s=10)
    return default_sol, variant_sol


class MockChatModel(Runnable):
    """Offline stand-in LLM: every call returns a bare reply, so the guard hook
    alone drives the full 5-worker handoff sequence without any network."""

    def __init__(self) -> None:
        self.calls = 0

    def bind_tools(self, tools: Any, **kwargs: Any) -> "MockChatModel":
        return self

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> AIMessage:
        self.calls += 1
        return AIMessage(content="mock final reply")


# --- 1. contract vs. meta-schema --------------------------------------------- #

def test_contract_meta_schema_validates() -> None:
    """Contract passes the production validator (meta-schema + domain invariants)."""
    schema = _load_json(META_SCHEMA_PATH)
    assert schema["type"] == "object"
    assert schema["required"] == ["schema", "problem_id", "numeric_authority", "roles",
                                   "budget_scope", "budget_percent", "objective_order",
                                   "candidate_lifecycle", "stop_rules"]
    assert schema["definitions"]["role"]["required"] == ["owns", "forbidden"]

    result = json.loads(validate_rostering_contract.invoke({}))
    assert result["ok"] is True
    assert result["schema"] == "orpath.rostering_collaboration.v1"
    assert result["problem_id"] == "staff_rostering"
    assert result["errors"] == []
    assert result["numeric_authority"] == "local_solver_and_independent_validator"
    assert "or-rostering-lead" in result["roles"]


def test_contract_budget_strict_100_and_tamper_tests() -> None:
    doc = _load_json(ROSTERING_CONTRACT_PATH)
    assert doc["budget_percent"] == {"auditor": 20, "exact_bound": 15, "heuristic": 35, "realities": 30}
    assert sum(doc["budget_percent"].values()) == 100
    assert doc["budget_percent"] == dict(ROSTERING_DISCRETIONARY_BUDGET)
    # tamper_tests complete: contract, domain constants and gate agree exactly.
    assert doc["tamper_tests"] == list(ROSTERING_TAMPER_TESTS) == list(redteam_gate.ATTACK_NAMES)
    assert doc["candidate_lifecycle"] == list(ROSTERING_CANDIDATE_LIFECYCLE)
    assert doc["objective_order"] == list(ROSTERING_OBJECTIVE_ORDER)
    assert doc["objective_order"][0] == "hard_constraints"
    assert doc["handoff_order"] == ["assumptions", "audit", "exact_bound",
                                     "heuristic_search", "realities",
                                     "redteam_validate", "write"]
    assert re.search(_load_json(META_SCHEMA_PATH)["properties"]["schema"]["pattern"], doc["schema"])


def test_contract_role_boundaries() -> None:
    doc = _load_json(ROSTERING_CONTRACT_PATH)
    assert set(doc["roles"]) == {
        "or-rostering-lead", "or-rostering-auditor", "or-rostering-exact-bound",
        "or-rostering-heuristic", "or-rostering-realities", "or-rostering-redteam"}
    for role in doc["roles"].values():
        assert isinstance(role["owns"], list) and role["owns"]
        assert isinstance(role["forbidden"], list) and role["forbidden"]


@pytest.mark.parametrize("mutate,case", [
    (lambda d: d.update(schema="rostering_collaboration.v1"), "schema-missing-prefix"),
    (lambda d: d["budget_percent"].update(auditor=20.5), "budget-percent-float"),
    (lambda d: d["budget_percent"].update(heuristic=36), "budget-sum-101"),
    (lambda d: d["roles"]["or-rostering-lead"].pop("owns"), "role-missing-owns"),
    (lambda d: d.update(roles=[]), "roles-not-object"),
    (lambda d: d.update(tamper_tests=["coverage_tamper"]), "tamper-tests-incomplete"),
    (lambda d: d.update(candidate_lifecycle=["ACCEPTED"]), "lifecycle-bad-bounds"),
    (lambda d: d["stop_rules"].update(heuristic="stop"), "stop-rules-value-not-array"),
])
def test_tampered_contract_rejected(tmp_path: Path, mutate: Any, case: str) -> None:
    doc = _load_json(ROSTERING_CONTRACT_PATH)
    mutate(doc)
    tampered = tmp_path / f"{case}.json"
    tampered.write_text(json.dumps(doc), encoding="utf-8")
    result = json.loads(validate_rostering_contract.invoke({"contract_path": str(tampered)}))
    assert result["ok"] is False, case
    assert result["errors"], case


# --- 2. budget ledger 20/15/35/30 ------------------------------------------ #

def test_budget_ledger_manager_audits_golden_ledger(rostering_golden_ledger: Path) -> None:
    report = audit_file(rostering_golden_ledger,
                        expected_budget=ROSTERING_DISCRETIONARY_BUDGET, root=ROOT)
    assert report["ok"] is True
    assert report["validation"]["ok"] is True
    assert report["compliance"]["budget_percent"] == ROSTERING_DISCRETIONARY_BUDGET
    assert report["compliance"]["budget_sum"] == 100
    assert report["risk_override"]["active"] is False


def test_budget_ledger_manager_rejects_drift_and_deduction() -> None:
    drift = {"budget_percent": dict(ROSTERING_DISCRETIONARY_BUDGET)}
    drift["budget_percent"]["heuristic"] = 36  # breaks 20/15/35/30
    ok, errors = BudgetLedgerManager(ledger=drift).validate()
    assert ok is False and any("budget_percent" in e for e in errors)

    deducted = {"budget_percent": dict(ROSTERING_DISCRETIONARY_BUDGET)}
    deducted["budget_percent"]["realities"] -= 1  # 30 → 29 after deduction
    ok, errors = BudgetLedgerManager(ledger=deducted).validate()
    assert ok is False and any("sum to exactly 100" in e for e in errors)


def test_budget_ledger_manager_risk_override_lifecycle() -> None:
    manager = BudgetLedgerManager(
        domain="rostering", ledger={"budget_percent": dict(ROSTERING_DISCRETIONARY_BUDGET)},
        baseline_budget=ROSTERING_DISCRETIONARY_BUDGET, override_budget=ROSTERING_RISK_OVERRIDE_BUDGET)
    assert manager.effective_budget() == ROSTERING_DISCRETIONARY_BUDGET
    manager.apply_override(trigger="input_gate_red", temporary_percent=ROSTERING_RISK_OVERRIDE_BUDGET)
    assert manager.effective_budget() == ROSTERING_RISK_OVERRIDE_BUDGET
    assert manager.active_overrides()
    assert manager.release_override() == ROSTERING_DISCRETIONARY_BUDGET
    assert manager.active_overrides() == []


def test_check_rostering_budget_ledger_tool(rostering_golden_ledger: Path) -> None:
    result = json.loads(check_rostering_budget_ledger.invoke({}))
    assert result["ok"] is True
    assert result["budget_percent"] == {"auditor": 20, "exact_bound": 15, "heuristic": 35, "realities": 30}
    assert result["budget_matches_protocol"] is True
    assert result["total_budget_sum"] == 100
    assert result["audit"]["ok"] is True


def test_check_rostering_budget_ledger_tool_handles_bad_ledgers(tmp_path: Path) -> None:
    missing = json.loads(check_rostering_budget_ledger.invoke({"ledger_path": str(tmp_path / "nope.json")}))
    assert missing["ok"] is False and "not found" in missing["error"]

    deducted = tmp_path / "deducted.json"
    deducted.write_text(json.dumps(
        {"budget_percent": {"auditor": 20, "exact_bound": 15, "heuristic": 35, "realities": 28}}),
        encoding="utf-8")
    result = json.loads(check_rostering_budget_ledger.invoke({"ledger_path": str(deducted)}))
    assert result["ok"] is False
    assert result["total_budget_sum"] == 98
    assert result["budget_matches_protocol"] is False


# --- 3. RosteringSupervisorState inheritance + stage transitions ----------- #

def test_state_inheritance_and_fields() -> None:
    from typing import get_type_hints

    assert RosteringSupervisorState.__orig_bases__ == (DomainSupervisorState,)
    hints = get_type_hints(RosteringSupervisorState)
    for flag in ("has_auditor_verified", "has_exact_bound_computed", "has_heuristic_solved",
                 "has_realities_applied", "has_redteam_verified"):
        assert hints[flag] is bool
    for field in ("roster", "shift_demands", "fairness_metrics", "max_consecutive_days",
                  "num_employees", "num_days", "roster_plan_path", "fairness_variance",
                  "unpreferred_shift_count", "total_overtime_hours", "lower_bound",
                  "optimality_gap", "schedule_by_day"):
        assert field in hints
    # Canonical base fields are preserved.
    base_fields = set(get_type_hints(DomainSupervisorState))
    for field in ("assumption_register_path", "budget_ledger_path", "redteam_passed", "messages"):
        assert field in hints and field in base_fields
    assert RosteringSupervisorState.__dict__["domain"] == "rostering"
    assert RosteringSupervisorState.__dict__["problem_id"] == "staff_rostering"


def test_state_stage_progress_transitions() -> None:
    stages = ROSTERING_PIPELINE_STAGE_ORDER
    base = {"messages": [HumanMessage("run")], "domain": "rostering"}

    progress = get_state_stage_progress(
        RosteringSupervisorState(**base, **{s: True for s in stages[:2]}), stages)
    assert progress["domain"] == "rostering" and progress["total_stages"] == 5
    assert progress["completed_count"] == 2
    assert progress["next_stage"] == ROSTERING_HEURISTIC_NAME
    assert 0.0 < progress["progress"] < 1.0

    # Later stage done must not skip the first missing one.
    partial = get_state_stage_progress(
        RosteringSupervisorState(**base, **{ROSTERING_REDTEAM_NAME: True}), stages)
    assert partial["completed_count"] == 1
    assert partial["next_stage"] == ROSTERING_AUDITOR_NAME

    # Transcript fallback: an AIMessage named after a worker counts as done.
    transcript = RosteringSupervisorState(
        messages=[HumanMessage("run"), AIMessage("g", name=ROSTERING_AUDITOR_NAME)])
    fallback = get_state_stage_progress(transcript, stages)
    assert fallback["completed_count"] == 1
    assert fallback["next_stage"] == ROSTERING_EXACT_BOUND_NAME

    # Every stage handed off → all_completed, full progress, no next stage.
    full = get_state_stage_progress(RosteringSupervisorState(**base, **{s: True for s in stages}), stages)
    assert full["all_completed"] is True
    assert full["completed_count"] == 5 and full["next_stage"] is None
    assert full["progress"] == 1.0


# --- 4. guard hook blocks non-Lead early termination ------------------------ #

def test_guard_hook_built_by_guard_factory() -> None:
    assert rostering_guard_post_hook.__name__ == "domain_guard_post_hook"
    fresh = create_domain_guard_hook(ROSTERING_PIPELINE_STAGE_ORDER, ROSTERING_GUARD_CALL_IDS)
    states = [
        {"messages": []},
        {"messages": [HumanMessage("start")]},
        {"messages": [AIMessage("x", tool_calls=[{"name": "y", "args": {}, "id": "c"}])]},
        {"messages": [HumanMessage("run"), AIMessage("a", name=ROSTERING_AUDITOR_NAME),
                      AIMessage("done", id="m2")]},
    ]
    for state in states:
        assert rostering_guard_post_hook(state) == fresh(state)


def test_guard_hook_intercepts_early_termination() -> None:
    # Pass-through states are untouched.
    assert rostering_guard_post_hook({"messages": []}) == {}
    assert rostering_guard_post_hook({"messages": [HumanMessage("start")]}) == {}

    def next_transfer(messages: list[Any]) -> str | dict:
        update = rostering_guard_post_hook({"messages": messages})
        if not update:
            return {}
        injected = update["messages"][-1]
        assert injected.tool_calls[0]["id"] in ROSTERING_GUARD_CALL_IDS.values()
        return injected.tool_calls[0]["name"]

    # Nothing done → auditor, even if a later stage already answered.
    assert next_transfer([HumanMessage("run"), AIMessage("done", id="m1")]) == \
        "transfer_to_or_rostering_auditor"

    stages = [ROSTERING_AUDITOR_NAME, ROSTERING_EXACT_BOUND_NAME, ROSTERING_HEURISTIC_NAME,
              ROSTERING_REALITY_NAME]
    expected = ["transfer_to_or_rostering_exact_bound", "transfer_to_or_rostering_heuristic",
                "transfer_to_or_rostering_realities", "transfer_to_or_rostering_redteam"]
    for idx in range(4):
        messages = [HumanMessage("run")] + [AIMessage(n[:1], name=n) for n in stages[: idx + 1]]
        if idx == 0:  # red-team done must not skip the first missing stage
            messages.append(AIMessage("rt", name=ROSTERING_REDTEAM_NAME))
        messages.append(AIMessage("completed", id=f"m{idx + 2}"))
        assert next_transfer(messages) == expected[idx]

    # All five stages handed off → bare reply allowed to finish.
    all_done = [HumanMessage("run")] + [AIMessage(n[:1], name=n) for n in ROSTERING_PIPELINE_STAGE_ORDER]
    all_done.append(AIMessage("completed", id="m6"))
    assert rostering_guard_post_hook({"messages": all_done}) == {}


# --- 5. six-role roster, prompts, agent factories -------------------------- #

def test_team_roster_and_constants() -> None:
    assert ROSTERING_WORKER_NAMES == (ROSTERING_AUDITOR_NAME, ROSTERING_EXACT_BOUND_NAME,
                                       ROSTERING_HEURISTIC_NAME, ROSTERING_REALITY_NAME,
                                       ROSTERING_REDTEAM_NAME)
    assert len(ROSTERING_ALL_AGENT_NAMES) == 6
    assert ROSTERING_PIPELINE_STAGE_ORDER == ROSTERING_WORKER_NAMES
    assert set(ROSTERING_GUARD_CALL_IDS) == set(ROSTERING_WORKER_NAMES)
    assert ROSTERING_DISCRETIONARY_BUDGET == {"auditor": 20, "exact_bound": 15, "heuristic": 35, "realities": 30}
    assert sum(ROSTERING_DISCRETIONARY_BUDGET.values()) == 100
    assert sum(ROSTERING_RISK_OVERRIDE_BUDGET.values()) == 100
    assert ROSTERING_CANDIDATE_LIFECYCLE[0] == "PROPOSED" and ROSTERING_CANDIDATE_LIFECYCLE[-1] == "ACCEPTED"


def test_team_all_six_agents_creable(model: Any) -> None:
    assert create_rostering_lead_agent(model=model).name == ROSTERING_LEAD_NAME
    assert create_rostering_auditor_agent(model=model).name == ROSTERING_AUDITOR_NAME
    assert create_rostering_exact_bound_agent(model=model).name == ROSTERING_EXACT_BOUND_NAME
    assert create_rostering_heuristic_agent(model=model).name == ROSTERING_HEURISTIC_NAME
    assert create_rostering_realities_agent(model=model).name == ROSTERING_REALITY_NAME
    assert create_rostering_redteam_agent(model=model).name == ROSTERING_REDTEAM_NAME
    assert [w.name for w in get_rostering_workers(model=model)] == list(ROSTERING_WORKER_NAMES)


def test_team_prompts_and_protocol_constants() -> None:
    prompts = {"lead": DEFAULT_ROSTERING_LEAD_PROMPT, "auditor": ROSTERING_AUDITOR_PROMPT,
               "exact_bound": ROSTERING_EXACT_BOUND_PROMPT, "heuristic": ROSTERING_HEURISTIC_PROMPT,
               "realities": ROSTERING_REALITY_PROMPT, "redteam": ROSTERING_REDTEAM_PROMPT}
    for name, prompt in prompts.items():
        assert isinstance(prompt, str) and len(prompt) > 50, name
    # Lead prompt enumerates the 20/15/35/30 split; red-team prompt names all
    # five DIMO tamper tests.
    for percent in ("20%", "15%", "35%", "30%"):
        assert percent in DEFAULT_ROSTERING_LEAD_PROMPT
    for tamper in ROSTERING_TAMPER_TESTS:
        assert tamper in ROSTERING_REDTEAM_PROMPT


# --- 6. red-team gate robustness on malformed input ------------------------- #

MALFORMED_ROSTERING_SOLUTIONS: tuple[Any, ...] = (
    None, "not-a-dict", 42, [], {},
    {"roster": "nope"},
    {"roster": [], "shift_demands": None},
    {"roster": [None], "shift_demands": []},
    {"roster": [{}], "shift_demands": [{}]},
    {"roster": {"E0": "Off"}, "shift_demands": []},
    {"roster": {"E0": [None, "Morning"]}, "shift_demands": []},
    {"fairness_metrics": "x"},
    {"roster": {"E0": [1, 2, 3]}, "shift_demands": [{}], "objective": "x"},
    {"roster": {"E0": ["Night", "Morning"]}, "shift_demands": [],
     "fairness_metrics": {"std_dev": -1.0}},
)


@pytest.mark.parametrize("solution", MALFORMED_ROSTERING_SOLUTIONS)
def test_redteam_build_attacks_never_raises(solution: Any) -> None:
    attacks = redteam_gate.build_attacks(solution)
    assert [row["attack"] for row in attacks] == list(redteam_gate.ATTACK_NAMES)
    for row in attacks:
        assert isinstance(row["applied"], bool)
        if not row["applied"]:
            assert isinstance(row["reason"], str) and row["reason"]


@pytest.mark.parametrize("solution", MALFORMED_ROSTERING_SOLUTIONS)
def test_redteam_run_redteam_fails_safely(solution: Any) -> None:
    report = redteam_gate.run_redteam(solution)
    assert report["ok"] is False
    assert report["schema"] == "orpath.rostering_redteam.v1"
    assert report["original_recompute_ok"] is False
    assert report["attack_count"] == len(redteam_gate.ATTACK_NAMES)
    for row in report["attacks"]:
        if row["applied"]:
            assert isinstance(row["failed_checks"], list)
        else:
            assert row["rejected"] is False
            assert isinstance(row["reason"], str) and row["reason"]


def test_redteam_captures_builder_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_solution: Any) -> Any:
        raise TypeError("boom")

    monkeypatch.setitem(redteam_gate.ATTACK_BUILDERS, "fairness_metric_tamper", boom)
    attacks = redteam_gate.build_attacks({"fairness_metrics": {"std_dev": 0.0}})
    by_name = {row["attack"]: row for row in attacks}
    assert by_name["fairness_metric_tamper"]["applied"] is False
    assert "TypeError" in by_name["fairness_metric_tamper"]["reason"]


def test_redteam_recompute_rejects_non_dict_payload() -> None:
    for payload in (None, "x", 42, [], 3.14, True):
        report = redteam_gate.recompute("staff_rostering", payload)
        assert report["ok"] is False and report["checks"] == []


def test_redteam_cli_rejects_malformed_solution(tmp_path: Path) -> None:
    solution = tmp_path / "solution.json"
    solution.write_text(json.dumps({"roster": [None]}), encoding="utf-8")
    out = tmp_path / "redteam.json"
    assert redteam_gate.main(["--solution", str(solution), "--out", str(out)]) == 1
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema"] == "orpath.rostering_redteam.v1"
    assert report["ok"] is False
    assert report["solution_path"] == str(solution.resolve())

    # Missing / invalid solution files also fail without crashing.
    assert redteam_gate.main(["--solution", str(tmp_path / "absent.json"),
                              "--out", str(tmp_path / "r.json")]) == 1
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert redteam_gate.main(["--solution", str(broken), "--out", str(tmp_path / "r.json")]) == 1


# --- 7. DIMO tamper attacks vs. real CP-SAT solutions (100% interception) -- #

EXPECTED_ATTACK_FAILURES: dict[str, str] = {
    "understaffing_coverage_tamper": "roster_daily_coverage",
    "shift_clash_tamper": "roster_one_shift_per_day",
    "night_rest_violation_injection": "roster_night_shift_rest",
    "consecutive_workday_overflow": "roster_consecutive_days_limit",
    "fairness_metric_tamper": "fairness_metrics_integrity",
}


def test_rostering_golden_solution_envelope(rostering_solutions: tuple[dict, dict]) -> None:
    for sol in rostering_solutions:
        assert sol["status"] in ("OPTIMAL", "FEASIBLE")
        assert sol["mode"] == "staff_rostering"
        assert sol["objective"] == (sol["fairness_metrics"]["max_shifts"]
                                     - sol["fairness_metrics"]["min_shifts"])
        assert sol["max_consecutive_days"] >= 1
        assert all(check["ok"] for check in validate_staff_rostering("staff_rostering", sol))
        # The red-team fairness integrity check must also pass on the original.
        assert redteam_gate.run_redteam(sol)["original_recompute_ok"] is True


@pytest.mark.parametrize("idx,case", [(0, "default-8x14"), (1, "variant-10x7-maxconsec3")])
def test_dimo_all_five_attacks_applied_and_rejected(
    rostering_solutions: tuple[dict, dict], idx: int, case: str) -> None:
    sol = rostering_solutions[idx]
    report = redteam_gate.run_redteam(sol, "staff_rostering")
    assert report["original_recompute_ok"] is True
    assert report["ok"] is True, case
    assert report["attacks_applied"] == 5

    by_name = {row["attack"]: row for row in report["attacks"]}
    for name, failed_check in EXPECTED_ATTACK_FAILURES.items():
        row = by_name[name]
        assert row["applied"] is True, f"{name}: {row.get('reason')}"
        assert row["rejected"] is True, f"{name} was not blocked: {row['failed_checks']}"
        assert failed_check in row["failed_checks"], row["failed_checks"]


def test_redteam_does_not_mutate_input(rostering_solutions: tuple[dict, dict]) -> None:
    for sol in rostering_solutions:
        before = deepcopy(sol)
        redteam_gate.build_attacks(sol)
        assert sol == before


# --- 8. supervisor graph: compile, 6 nodes, mock pipeline ------------------ #

def test_supervisor_graph_compiles_with_six_nodes(model: Any) -> None:
    from orpath.agents.domains.rostering import (
        build_compiled_rostering_supervisor, build_rostering_supervisor_graph)

    graph = build_rostering_supervisor_graph(model=model)
    assert isinstance(graph, StateGraph)

    compiled = build_compiled_rostering_supervisor(model=model)
    assert isinstance(compiled, CompiledStateGraph)
    for expected_node in ROSTERING_ALL_AGENT_NAMES:
        assert expected_node in compiled.nodes


def test_supervisor_runs_mock_pipeline() -> None:
    """Guard-hook-driven execution: every worker node runs exactly once, in order."""
    from orpath.agents.domains.rostering import build_compiled_rostering_supervisor

    mock = MockChatModel()
    compiled = build_compiled_rostering_supervisor(model=mock, enable_trim=False)
    final = compiled.invoke({"messages": [HumanMessage("run")]})

    # 1 supervisor decision per worker handoff + 5 worker model calls.
    assert mock.calls == 11

    transfers = [m.tool_calls[0]["name"] for m in final["messages"]
                 if getattr(m, "tool_calls", None)]
    for worker in ROSTERING_WORKER_NAMES:
        assert f"transfer_to_{worker}" in transfers
        assert f"transfer_back_to_{ROSTERING_LEAD_NAME}" in transfers

    worker_answers = [m for m in final["messages"]
                      if getattr(m, "name", None) in ROSTERING_WORKER_NAMES
                      and not getattr(m, "tool_calls", None)]
    assert [getattr(m, "name", None) for m in worker_answers] == list(ROSTERING_WORKER_NAMES)

    assert final["messages"][-1].name == ROSTERING_LEAD_NAME
    assert not final["messages"][-1].tool_calls
    assert final["messages"][-1].content == "mock final reply"


# --- 9. domain tools: contract / collaboration gate / red-team gate -------- #

def test_validate_rostering_contract_tool_handles_missing_file(tmp_path: Path) -> None:
    result = json.loads(validate_rostering_contract.invoke({"contract_path": str(tmp_path / "nope.json")}))
    assert result["ok"] is False
    assert "Missing contract" in result["error"]


def test_run_rostering_collaboration_gate_tool(rostering_golden_ledger: Path) -> None:
    result = json.loads(run_rostering_collaboration_gate.invoke({}))
    assert result["ok"] is True
    assert result["gate"] == "rostering_collaboration_gate"
    assert result["contract"]["ok"] is True
    assert result["budget_ledger"]["ok"] is True
    assert result["budget_ledger"]["budget_matches_protocol"] is True


def test_run_rostering_redteam_gate_tool_writes_report(
    tmp_path: Path, rostering_solutions: tuple[dict, dict]) -> None:
    solution = tmp_path / "staff_rostering-solution.json"
    solution.write_text(json.dumps(rostering_solutions[0]), encoding="utf-8")
    out = tmp_path / "staff_rostering-redteam.json"

    result = json.loads(run_rostering_redteam_gate.invoke(
        {"solution_path": str(solution), "out_path": str(out)}))
    assert result["ok"] is True
    assert result["returncode"] == 0
    assert result["report"]["schema"] == "orpath.rostering_redteam.v1"
    assert result["report"]["ok"] is True
    assert out.is_file()


def test_run_rostering_redteam_gate_tool_handles_missing_solution(tmp_path: Path) -> None:
    result = json.loads(run_rostering_redteam_gate.invoke(
        {"solution_path": str(tmp_path / "absent.json"), "out_path": str(tmp_path / "r.json")}))
    assert result["ok"] is False
    assert "not found" in result["error"]
