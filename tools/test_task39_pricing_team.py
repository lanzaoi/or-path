#!/usr/bin/env python3
"""Phase 3 / Task 3.9 — Revenue Management & Dynamic Pricing team + hardening tests.

Covers contract vs. meta-schema, golden budget-ledger audit (20/15/35/30),
PricingSupervisorState inheritance, guard hook blocking early termination,
6-role roster/prompts/agents, red-team gate robustness, 5 DIMO tamper attacks
on real GLOP two-stage stochastic LP solutions (100% interception), supervisor
mock pipeline, and the 4 domain tools.
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

from orpath.agents import (  # noqa: E402
    PRICING_LEAD_NAME,
    PricingSupervisorState,
    build_compiled_pricing_supervisor,
    create_pricing_lead_agent,
)
from orpath.agents.budget_engine import BudgetLedgerManager, audit_file  # noqa: E402
from orpath.agents.domain_state import (  # noqa: E402
    DomainSupervisorState,
    get_state_stage_progress,
)
from orpath.agents.domains.pricing import (  # noqa: E402
    DEFAULT_PRICING_LEAD_PROMPT, PRICING_ALL_AGENT_NAMES, PRICING_AUDITOR_NAME,
    PRICING_AUDITOR_PROMPT, PRICING_CANDIDATE_LIFECYCLE, PRICING_DISCRETIONARY_BUDGET,
    PRICING_EXACT_BOUND_NAME, PRICING_EXACT_BOUND_PROMPT, PRICING_GUARD_CALL_IDS,
    PRICING_HEURISTIC_NAME, PRICING_HEURISTIC_PROMPT, PRICING_LEAD_NAME,
    PRICING_OBJECTIVE_ORDER, PRICING_PIPELINE_STAGE_ORDER, PRICING_REALITY_NAME,
    PRICING_REALITY_PROMPT, PRICING_REDTEAM_NAME, PRICING_REDTEAM_PROMPT,
    PRICING_RISK_OVERRIDE_BUDGET, PRICING_TAMPER_TESTS, PRICING_WORKER_NAMES,
    check_pricing_budget_ledger, create_pricing_auditor_agent,
    create_pricing_exact_bound_agent, create_pricing_heuristic_agent,
    create_pricing_realities_agent, create_pricing_redteam_agent,
    get_pricing_workers, pricing_guard_post_hook, run_pricing_collaboration_gate,
    run_pricing_redteam_gate, validate_pricing_contract,
)
from orpath.agents.guard_factory import create_domain_guard_hook  # noqa: E402
from orpath.control_plane import get_chat_model  # noqa: E402

import pricing_redteam_gate as redteam_gate  # noqa: E402
from solve_stochastic_lp import solve_stochastic_lp  # noqa: E402
from validators.extended_solvers import validate_stochastic_lp  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore:create_react_agent has been moved")

META_SCHEMA_PATH = ROOT / "contracts" / "meta" / "domain_collaboration.schema.json"
PRICING_CONTRACT_PATH = ROOT / "contracts" / "pricing_collaboration_v1.json"
LEDGER_PATH = ROOT / "experiments" / "pricing" / "budget-ledger.json"

#: Second stochastic LP instance (non-uniform scenario probabilities, shifted
#: internal demands) used to exercise the DIMO attack surface generically.
VARIANT_PROBLEM: dict[str, Any] = {
    "name": "farmer_problem_variant",
    "total_land_acres": 500.0,
    "crops": ["wheat", "corn", "sugar_beets"],
    "planting_cost_per_acre": {"wheat": 150.0, "corn": 230.0, "sugar_beets": 260.0},
    "scenarios": [
        {"name": "good", "probability": 0.4,
         "yield_per_acre": {"wheat": 3.0, "corn": 3.6, "sugar_beets": 24.0}},
        {"name": "average", "probability": 0.35,
         "yield_per_acre": {"wheat": 2.5, "corn": 3.0, "sugar_beets": 20.0}},
        {"name": "bad", "probability": 0.25,
         "yield_per_acre": {"wheat": 2.0, "corn": 2.4, "sugar_beets": 16.0}},
    ],
    "internal_demand": {"wheat": 300.0, "corn": 200.0},
    "selling_price": {"wheat": 170.0, "corn": 150.0,
                      "sugar_beets_quota": 36.0, "sugar_beets_excess": 10.0},
    "purchase_price": {"wheat": 238.0, "corn": 210.0},
    "sugar_beet_quota": 6000.0,
    "known_optimal": {},
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# --- fixtures --------------------------------------------------------------- #

@pytest.fixture()
def model() -> Any:
    return get_chat_model()


@pytest.fixture(scope="module", autouse=True)
def pricing_golden_ledger() -> Path:
    """Provision the golden pricing budget ledger for tool tests."""
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(
        {"schema": "orpath.pricing_budget_ledger.v1", "date": "2026-01-01",
         "scope": "discretionary_experiment_effort_excluding_baseline_and_gates",
         "budget_percent": dict(PRICING_DISCRETIONARY_BUDGET)},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return LEDGER_PATH


@pytest.fixture(scope="module")
def pricing_solutions() -> tuple[dict[str, Any], dict[str, Any]]:
    """Two real GLOP two-stage stochastic LP solutions (default + variant)."""
    default_sol = solve_stochastic_lp()
    variant_sol = solve_stochastic_lp(VARIANT_PROBLEM)
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

    result = json.loads(validate_pricing_contract.invoke({}))
    assert result["ok"] is True
    assert result["schema"] == "orpath.pricing_collaboration.v1"
    assert result["problem_id"] == "farmer_stochastic_lp"
    assert result["errors"] == []
    assert result["numeric_authority"] == "local_solver_and_independent_validator"
    assert "or-pricing-lead" in result["roles"]


def test_contract_budget_strict_100_and_tamper_tests() -> None:
    doc = _load_json(PRICING_CONTRACT_PATH)
    assert doc["budget_percent"] == {"auditor": 20, "exact_bound": 15,
                                     "heuristic": 35, "realities": 30}
    assert sum(doc["budget_percent"].values()) == 100
    assert doc["budget_percent"] == dict(PRICING_DISCRETIONARY_BUDGET)
    # tamper_tests complete: contract, domain constants and gate agree exactly.
    assert doc["tamper_tests"] == list(PRICING_TAMPER_TESTS) == list(redteam_gate.ATTACK_NAMES)
    assert doc["candidate_lifecycle"] == list(PRICING_CANDIDATE_LIFECYCLE)
    assert doc["objective_order"] == list(PRICING_OBJECTIVE_ORDER)
    assert doc["objective_order"][0] == "hard_constraints"
    assert doc["handoff_order"] == ["assumptions", "audit", "exact_bound",
                                     "heuristic_search", "realities",
                                     "redteam_validate", "write"]
    assert re.search(_load_json(META_SCHEMA_PATH)["properties"]["schema"]["pattern"], doc["schema"])


def test_contract_role_boundaries() -> None:
    doc = _load_json(PRICING_CONTRACT_PATH)
    assert set(doc["roles"]) == {
        "or-pricing-lead", "or-pricing-auditor", "or-pricing-exact-bound",
        "or-pricing-heuristic", "or-pricing-realities", "or-pricing-redteam"}
    for role in doc["roles"].values():
        assert isinstance(role["owns"], list) and role["owns"]
        assert isinstance(role["forbidden"], list) and role["forbidden"]


@pytest.mark.parametrize("mutate,case", [
    (lambda d: d.update(schema="pricing_collaboration.v1"), "schema-missing-prefix"),
    (lambda d: d["budget_percent"].update(auditor=20.5), "budget-percent-float"),
    (lambda d: d["budget_percent"].update(heuristic=36), "budget-sum-101"),
    (lambda d: d["roles"]["or-pricing-lead"].pop("owns"), "role-missing-owns"),
    (lambda d: d.update(roles=[]), "roles-not-object"),
    (lambda d: d.update(tamper_tests=["first_stage_capacity_overflow"]), "tamper-tests-incomplete"),
    (lambda d: d.update(candidate_lifecycle=["ACCEPTED"]), "lifecycle-bad-bounds"),
    (lambda d: d["stop_rules"].update(heuristic="stop"), "stop-rules-value-not-array"),
])
def test_tampered_contract_rejected(tmp_path: Path, mutate: Any, case: str) -> None:
    doc = _load_json(PRICING_CONTRACT_PATH)
    mutate(doc)
    tampered = tmp_path / f"{case}.json"
    tampered.write_text(json.dumps(doc), encoding="utf-8")
    result = json.loads(validate_pricing_contract.invoke({"contract_path": str(tampered)}))
    assert result["ok"] is False, case
    assert result["errors"], case


# --- 2. budget ledger 20/15/35/30 ------------------------------------------ #

def test_budget_ledger_manager_audits_golden_ledger(pricing_golden_ledger: Path) -> None:
    report = audit_file(pricing_golden_ledger,
                        expected_budget=PRICING_DISCRETIONARY_BUDGET, root=ROOT)
    assert report["ok"] is True
    assert report["validation"]["ok"] is True
    assert report["compliance"]["budget_percent"] == PRICING_DISCRETIONARY_BUDGET
    assert report["compliance"]["budget_sum"] == 100
    assert report["risk_override"]["active"] is False


def test_budget_ledger_manager_rejects_drift_and_deduction() -> None:
    drift = {"budget_percent": dict(PRICING_DISCRETIONARY_BUDGET)}
    drift["budget_percent"]["heuristic"] = 36  # breaks 20/15/35/30
    ok, errors = BudgetLedgerManager(ledger=drift).validate()
    assert ok is False and any("budget_percent" in e for e in errors)

    deducted = {"budget_percent": dict(PRICING_DISCRETIONARY_BUDGET)}
    deducted["budget_percent"]["realities"] -= 1  # 30 → 29 after deduction
    ok, errors = BudgetLedgerManager(ledger=deducted).validate()
    assert ok is False and any("sum to exactly 100" in e for e in errors)


def test_budget_ledger_manager_risk_override_lifecycle() -> None:
    manager = BudgetLedgerManager(
        domain="pricing", ledger={"budget_percent": dict(PRICING_DISCRETIONARY_BUDGET)},
        baseline_budget=PRICING_DISCRETIONARY_BUDGET,
        override_budget=PRICING_RISK_OVERRIDE_BUDGET)
    assert manager.effective_budget() == PRICING_DISCRETIONARY_BUDGET
    manager.apply_override(trigger="input_gate_red", temporary_percent=PRICING_RISK_OVERRIDE_BUDGET)
    assert manager.effective_budget() == PRICING_RISK_OVERRIDE_BUDGET
    assert manager.active_overrides()
    assert manager.release_override() == PRICING_DISCRETIONARY_BUDGET
    assert manager.active_overrides() == []


def test_check_pricing_budget_ledger_tool(pricing_golden_ledger: Path) -> None:
    result = json.loads(check_pricing_budget_ledger.invoke({}))
    assert result["ok"] is True
    assert result["budget_percent"] == {"auditor": 20, "exact_bound": 15,
                                        "heuristic": 35, "realities": 30}
    assert result["budget_matches_protocol"] is True
    assert result["total_budget_sum"] == 100
    assert result["audit"]["ok"] is True


def test_check_pricing_budget_ledger_tool_handles_bad_ledgers(tmp_path: Path) -> None:
    missing = json.loads(check_pricing_budget_ledger.invoke({"ledger_path": str(tmp_path / "nope.json")}))
    assert missing["ok"] is False and "not found" in missing["error"]

    deducted = tmp_path / "deducted.json"
    deducted.write_text(json.dumps(
        {"budget_percent": {"auditor": 20, "exact_bound": 15, "heuristic": 35, "realities": 28}}),
        encoding="utf-8")
    result = json.loads(check_pricing_budget_ledger.invoke({"ledger_path": str(deducted)}))
    assert result["ok"] is False
    assert result["total_budget_sum"] == 98
    assert result["budget_matches_protocol"] is False


# --- 3. PricingSupervisorState inheritance + stage transitions ---------- #

def test_state_inheritance_and_fields() -> None:
    from typing import get_type_hints

    assert PricingSupervisorState.__orig_bases__ == (DomainSupervisorState,)
    hints = get_type_hints(PricingSupervisorState)
    for flag in ("has_auditor_verified", "has_exact_bound_computed", "has_heuristic_solved",
                 "has_realities_applied", "has_redteam_verified"):
        assert hints[flag] is bool
    for field in ("first_stage_decision", "first_stage_cost", "expected_profit",
                  "expected_second_stage_revenue", "stochastic_indicators", "evpi", "vss",
                  "cvar_penalty", "sample_average_approximation_incumbent",
                  "bid_price_heuristic_incumbent", "allocation_pricing_plan",
                  "allocation_pricing_plan_path", "cvar_risk_aversion_policy",
                  "overbooking_cancellation_policy", "demand_elasticity_fencing_policy",
                  "reality_feasibility", "deterministic_equivalent_lp_bound",
                  "l_shaped_benders_cut", "bound_evidence", "lower_bound", "optimality_gap"):
        assert field in hints
    # Canonical base fields are preserved.
    base_fields = set(get_type_hints(DomainSupervisorState))
    for field in ("assumption_register_path", "budget_ledger_path", "redteam_passed", "messages"):
        assert field in hints and field in base_fields
    assert PricingSupervisorState.__dict__["domain"] == "pricing"
    assert PricingSupervisorState.__dict__["problem_id"] == "farmer_stochastic_lp"


def test_state_stage_progress_transitions() -> None:
    stages = PRICING_PIPELINE_STAGE_ORDER
    base = {"messages": [HumanMessage("run")], "domain": "pricing"}

    progress = get_state_stage_progress(
        PricingSupervisorState(**base, **{s: True for s in stages[:2]}), stages)
    assert progress["domain"] == "pricing" and progress["total_stages"] == 5
    assert progress["completed_count"] == 2
    assert progress["next_stage"] == PRICING_HEURISTIC_NAME
    assert 0.0 < progress["progress"] < 1.0

    # Later stage done must not skip the first missing one.
    partial = get_state_stage_progress(
        PricingSupervisorState(**base, **{PRICING_REDTEAM_NAME: True}), stages)
    assert partial["completed_count"] == 1
    assert partial["next_stage"] == PRICING_AUDITOR_NAME

    # Transcript fallback: an AIMessage named after a worker counts as done.
    transcript = PricingSupervisorState(
        messages=[HumanMessage("run"), AIMessage("g", name=PRICING_AUDITOR_NAME)])
    fallback = get_state_stage_progress(transcript, stages)
    assert fallback["completed_count"] == 1
    assert fallback["next_stage"] == PRICING_EXACT_BOUND_NAME

    # Every stage handed off → all_completed, full progress, no next stage.
    full = get_state_stage_progress(
        PricingSupervisorState(**base, **{s: True for s in stages}), stages)
    assert full["all_completed"] is True
    assert full["completed_count"] == 5 and full["next_stage"] is None
    assert full["progress"] == 1.0


# --- 4. guard hook blocks non-Lead early termination ------------------------ #

def test_guard_hook_built_by_guard_factory() -> None:
    assert pricing_guard_post_hook.__name__ == "domain_guard_post_hook"
    fresh = create_domain_guard_hook(PRICING_PIPELINE_STAGE_ORDER, PRICING_GUARD_CALL_IDS)
    states = [
        {"messages": []},
        {"messages": [HumanMessage("start")]},
        {"messages": [AIMessage("x", tool_calls=[{"name": "y", "args": {}, "id": "c"}])]},
        {"messages": [HumanMessage("run"), AIMessage("a", name=PRICING_AUDITOR_NAME),
                      AIMessage("done", id="m2")]},
    ]
    for state in states:
        assert pricing_guard_post_hook(state) == fresh(state)


def test_guard_hook_intercepts_early_termination() -> None:
    # Pass-through states are untouched.
    assert pricing_guard_post_hook({"messages": []}) == {}
    assert pricing_guard_post_hook({"messages": [HumanMessage("start")]}) == {}

    def next_transfer(messages: list[Any]) -> str | dict:
        update = pricing_guard_post_hook({"messages": messages})
        if not update:
            return {}
        injected = update["messages"][-1]
        assert injected.tool_calls[0]["id"] in PRICING_GUARD_CALL_IDS.values()
        return injected.tool_calls[0]["name"]

    # Nothing done → auditor, even if a later stage already answered.
    assert next_transfer([HumanMessage("run"), AIMessage("done", id="m1")]) == \
        "transfer_to_or_pricing_auditor"

    stages = [PRICING_AUDITOR_NAME, PRICING_EXACT_BOUND_NAME, PRICING_HEURISTIC_NAME,
              PRICING_REALITY_NAME]
    expected = ["transfer_to_or_pricing_exact_bound", "transfer_to_or_pricing_heuristic",
                "transfer_to_or_pricing_realities", "transfer_to_or_pricing_redteam"]
    for idx in range(4):
        messages = [HumanMessage("run")] + [AIMessage(n[:1], name=n) for n in stages[: idx + 1]]
        if idx == 0:  # red-team done must not skip the first missing stage
            messages.append(AIMessage("rt", name=PRICING_REDTEAM_NAME))
        messages.append(AIMessage("completed", id=f"m{idx + 2}"))
        assert next_transfer(messages) == expected[idx]

    # All five stages handed off → bare reply allowed to finish.
    all_done = [HumanMessage("run")] + [
        AIMessage(n[:1], name=n) for n in PRICING_PIPELINE_STAGE_ORDER]
    all_done.append(AIMessage("completed", id="m6"))
    assert pricing_guard_post_hook({"messages": all_done}) == {}


# --- 5. six-role roster, prompts, agent factories -------------------------- #

def test_team_roster_and_constants() -> None:
    assert PRICING_WORKER_NAMES == (PRICING_AUDITOR_NAME, PRICING_EXACT_BOUND_NAME,
                                     PRICING_HEURISTIC_NAME, PRICING_REALITY_NAME,
                                     PRICING_REDTEAM_NAME)
    assert len(PRICING_ALL_AGENT_NAMES) == 6
    assert PRICING_PIPELINE_STAGE_ORDER == PRICING_WORKER_NAMES
    assert set(PRICING_GUARD_CALL_IDS) == set(PRICING_WORKER_NAMES)
    assert PRICING_DISCRETIONARY_BUDGET == {"auditor": 20, "exact_bound": 15,
                                             "heuristic": 35, "realities": 30}
    assert sum(PRICING_DISCRETIONARY_BUDGET.values()) == 100
    assert sum(PRICING_RISK_OVERRIDE_BUDGET.values()) == 100
    assert PRICING_CANDIDATE_LIFECYCLE[0] == "PROPOSED" and PRICING_CANDIDATE_LIFECYCLE[-1] == "ACCEPTED"


def test_team_all_six_agents_creable(model: Any) -> None:
    assert create_pricing_lead_agent(model=model).name == PRICING_LEAD_NAME
    assert create_pricing_auditor_agent(model=model).name == PRICING_AUDITOR_NAME
    assert create_pricing_exact_bound_agent(model=model).name == PRICING_EXACT_BOUND_NAME
    assert create_pricing_heuristic_agent(model=model).name == PRICING_HEURISTIC_NAME
    assert create_pricing_realities_agent(model=model).name == PRICING_REALITY_NAME
    assert create_pricing_redteam_agent(model=model).name == PRICING_REDTEAM_NAME
    assert [w.name for w in get_pricing_workers(model=model)] == list(PRICING_WORKER_NAMES)


def test_team_prompts_and_protocol_constants() -> None:
    prompts = {"lead": DEFAULT_PRICING_LEAD_PROMPT, "auditor": PRICING_AUDITOR_PROMPT,
               "exact_bound": PRICING_EXACT_BOUND_PROMPT, "heuristic": PRICING_HEURISTIC_PROMPT,
               "realities": PRICING_REALITY_PROMPT, "redteam": PRICING_REDTEAM_PROMPT}
    for name, prompt in prompts.items():
        assert isinstance(prompt, str) and len(prompt) > 50, name
    # Lead prompt enumerates the 20/15/35/30 split; red-team prompt names all
    # five DIMO tamper tests.
    for percent in ("20%", "15%", "35%", "30%"):
        assert percent in DEFAULT_PRICING_LEAD_PROMPT
    for tamper in PRICING_TAMPER_TESTS:
        assert tamper in PRICING_REDTEAM_PROMPT


def test_domain_package_exports() -> None:
    """pricing constants/state/builders are re-exported from both packages."""
    import orpath.agents
    import orpath.agents.domains as domains_pkg

    for name in ("PRICING_LEAD_NAME", "PRICING_WORKER_NAMES", "PricingSupervisorState",
                 "build_compiled_pricing_supervisor", "build_pricing_supervisor_graph",
                 "pricing_guard_post_hook", "get_pricing_workers"):
        assert hasattr(domains_pkg, name), name
        assert name in domains_pkg.__all__, name

    for name in ("PRICING_LEAD_NAME", "PricingSupervisorState",
                 "build_compiled_pricing_supervisor", "create_pricing_lead_agent",
                 "get_pricing_workers", "pricing_guard_post_hook"):
        assert hasattr(orpath.agents, name), name
        assert name in orpath.agents.__all__, name


# --- 6. red-team gate robustness on malformed input ------------------------- #

MALFORMED_PRICING_SOLUTIONS: tuple[Any, ...] = (
    None, "not-a-dict", 42, [], {},
    {"first_stage_decision": "x"},
    {"first_stage_decision": []},
    {"first_stage_decision": None},
    {"first_stage_decision": {}},
    {"first_stage_decision": {"wheat": "x"}},
    {"raw_problem": "x"},
    {"raw_problem": []},
    {"raw_problem": {}},
    {"raw_problem": {"crops": "x"}},
    {"scenarios": "x"},
    {"scenarios": []},
    {"scenarios": [None]},
    {"scenarios": [{}]},
    {"scenarios": [{"scenario": "good"}]},
    {"stochastic_indicators": "x"},
    {"stochastic_indicators": {}},
    {"stochastic_indicators": {"WS": "x"}},
    {"objective": "x"},
    {"first_stage_cost": "x"},
    {"status": "OPTIMAL", "objective": -5.0, "first_stage_cost": 0.0},
)


@pytest.mark.parametrize("solution", MALFORMED_PRICING_SOLUTIONS)
def test_redteam_build_attacks_never_raises(solution: Any) -> None:
    attacks = redteam_gate.build_attacks(solution)
    assert [row["attack"] for row in attacks] == list(redteam_gate.ATTACK_NAMES)
    for row in attacks:
        assert isinstance(row["applied"], bool)
        if not row["applied"]:
            assert isinstance(row["reason"], str) and row["reason"]


@pytest.mark.parametrize("solution", MALFORMED_PRICING_SOLUTIONS)
def test_redteam_run_redteam_fails_safely(solution: Any) -> None:
    report = redteam_gate.run_redteam(solution)
    assert report["ok"] is False
    assert report["schema"] == "orpath.pricing_redteam.v1"
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

    monkeypatch.setitem(redteam_gate.ATTACK_BUILDERS, "first_stage_cost_tamper", boom)
    attacks = redteam_gate.build_attacks({"first_stage_cost": 1.0})
    by_name = {row["attack"]: row for row in attacks}
    assert by_name["first_stage_cost_tamper"]["applied"] is False
    assert "TypeError" in by_name["first_stage_cost_tamper"]["reason"]


def test_redteam_recompute_rejects_non_dict_payload() -> None:
    for payload in (None, "x", 42, [], 3.14, True):
        report = redteam_gate.recompute("farmer_stochastic_lp", payload)
        assert report["ok"] is False and report["checks"] == []


def test_redteam_cli_rejects_malformed_solution(tmp_path: Path) -> None:
    solution = tmp_path / "solution.json"
    solution.write_text(json.dumps({"scenarios": [None]}), encoding="utf-8")
    out = tmp_path / "redteam.json"
    assert redteam_gate.main(["--solution", str(solution), "--out", str(out)]) == 1
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema"] == "orpath.pricing_redteam.v1"
    assert report["ok"] is False
    assert report["solution_path"] == str(solution.resolve())

    # Missing / invalid solution files also fail without crashing.
    assert redteam_gate.main(["--solution", str(tmp_path / "absent.json"),
                              "--out", str(tmp_path / "r.json")]) == 1
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert redteam_gate.main(["--solution", str(broken), "--out", str(tmp_path / "r.json")]) == 1


# --- 7. DIMO tamper attacks vs. real GLOP solutions (100% interception) ---- #

EXPECTED_ATTACK_FAILURES: dict[str, str] = {
    "first_stage_capacity_overflow": "first_stage_land_constraint",
    "scenario_recourse_balance_tamper": "scenario_recourse_feasibility",
    "stochastic_inequality_forgery": "stochastic_indicators_consistency",
    "expected_profit_inflation_forgery": "recompute_objective",
    "first_stage_cost_tamper": "first_stage_cost_recompute",
}


def test_stochastic_lp_golden_solution_envelope(
    pricing_solutions: tuple[dict, dict],
) -> None:
    default_sol, variant_sol = pricing_solutions
    for sol in (default_sol, variant_sol):
        assert sol["status"] in ("OPTIMAL", "FEASIBLE")
        assert sol["objective"] > 0.0
        assert all(check["ok"] for check in validate_stochastic_lp("farmer_stochastic_lp", sol))
        # The red-team recompute must also accept the original.
        assert redteam_gate.run_redteam(sol, "farmer_stochastic_lp")["original_recompute_ok"] is True

    # Numbers Truth: the default envelope reproduces the published optima.
    assert default_sol["objective"] == 108390.0
    assert default_sol["first_stage_decision"] == {"wheat": 170.0, "corn": 80.0, "sugar_beets": 250.0}
    assert default_sol["first_stage_cost"] == 108900.0
    indicators = default_sol["stochastic_indicators"]
    assert indicators["RP"] == 108390.0
    assert abs(indicators["EVPI"] - 7015.5556) < 1e-3
    assert indicators["VSS"] == 1150.0


@pytest.mark.parametrize("idx,case", [(0, "default-farmer"), (1, "variant-probability-demand")])
def test_dimo_all_five_attacks_applied_and_rejected(
    pricing_solutions: tuple[dict, dict], idx: int, case: str
) -> None:
    sol = pricing_solutions[idx]
    report = redteam_gate.run_redteam(sol, "farmer_stochastic_lp")
    assert report["original_recompute_ok"] is True
    assert report["ok"] is True, case
    assert report["attacks_applied"] == 5

    by_name = {row["attack"]: row for row in report["attacks"]}
    for name, failed_check in EXPECTED_ATTACK_FAILURES.items():
        row = by_name[name]
        assert row["applied"] is True, f"{name}: {row.get('reason')}"
        assert row["rejected"] is True, f"{name} was not blocked: {row['failed_checks']}"
        assert row["failed_checks"] == [failed_check], row["failed_checks"]


def test_redteam_does_not_mutate_input(pricing_solutions: tuple[dict, dict]) -> None:
    for sol in pricing_solutions:
        before = deepcopy(sol)
        redteam_gate.build_attacks(sol)
        assert sol == before


# --- 8. supervisor graph: compile, 6 nodes, mock pipeline ------------------ #

def test_supervisor_graph_compiles_with_six_nodes(model: Any) -> None:
    from orpath.agents.domains.pricing import (
        build_compiled_pricing_supervisor, build_pricing_supervisor_graph)

    graph = build_pricing_supervisor_graph(model=model)
    assert isinstance(graph, StateGraph)

    compiled = build_compiled_pricing_supervisor(model=model)
    assert isinstance(compiled, CompiledStateGraph)
    for expected_node in PRICING_ALL_AGENT_NAMES:
        assert expected_node in compiled.nodes


def test_supervisor_runs_mock_pipeline() -> None:
    """Guard-hook-driven execution: every worker node runs exactly once, in order."""
    from orpath.agents.domains.pricing import build_compiled_pricing_supervisor

    mock = MockChatModel()
    compiled = build_compiled_pricing_supervisor(model=mock, enable_trim=False)
    final = compiled.invoke({"messages": [HumanMessage("run")]})

    # 1 supervisor decision per worker handoff + 5 worker model calls.
    assert mock.calls == 11

    transfers = [m.tool_calls[0]["name"] for m in final["messages"]
                 if getattr(m, "tool_calls", None)]
    for worker in PRICING_WORKER_NAMES:
        assert f"transfer_to_{worker}" in transfers
        assert f"transfer_back_to_{PRICING_LEAD_NAME}" in transfers

    worker_answers = [m for m in final["messages"]
                      if getattr(m, "name", None) in PRICING_WORKER_NAMES
                      and not getattr(m, "tool_calls", None)]
    assert [getattr(m, "name", None) for m in worker_answers] == list(PRICING_WORKER_NAMES)

    assert final["messages"][-1].name == PRICING_LEAD_NAME
    assert not final["messages"][-1].tool_calls
    assert final["messages"][-1].content == "mock final reply"


# --- 9. domain tools: contract / collaboration gate / red-team gate -------- #

def test_validate_pricing_contract_tool_handles_missing_file(tmp_path: Path) -> None:
    result = json.loads(validate_pricing_contract.invoke({"contract_path": str(tmp_path / "nope.json")}))
    assert result["ok"] is False
    assert "Missing contract" in result["error"]


def test_run_pricing_collaboration_gate_tool(pricing_golden_ledger: Path) -> None:
    result = json.loads(run_pricing_collaboration_gate.invoke({}))
    assert result["ok"] is True
    assert result["gate"] == "pricing_collaboration_gate"
    assert result["contract"]["ok"] is True
    assert result["budget_ledger"]["ok"] is True
    assert result["budget_ledger"]["budget_matches_protocol"] is True


def test_run_pricing_redteam_gate_tool_writes_report(
    tmp_path: Path, pricing_solutions: tuple[dict, dict]
) -> None:
    solution = tmp_path / "farmer_stochastic_lp-solution.json"
    solution.write_text(json.dumps(pricing_solutions[0]), encoding="utf-8")
    out = tmp_path / "farmer_stochastic_lp-redteam.json"

    result = json.loads(run_pricing_redteam_gate.invoke(
        {"solution_path": str(solution), "out_path": str(out)}))
    assert result["ok"] is True
    assert result["returncode"] == 0
    assert result["report"]["schema"] == "orpath.pricing_redteam.v1"
    assert result["report"]["ok"] is True
    assert out.is_file()


def test_run_pricing_redteam_gate_tool_handles_missing_solution(tmp_path: Path) -> None:
    result = json.loads(run_pricing_redteam_gate.invoke(
        {"solution_path": str(tmp_path / "absent.json"), "out_path": str(tmp_path / "r.json")}))
    assert result["ok"] is False
    assert "not found" in result["error"]
