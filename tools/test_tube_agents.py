#!/usr/bin/env python3
"""Unit tests for the Tube B domain multi-agent team (``orpath/agents/domains/tube.py``)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, get_type_hints

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage  # noqa: E402
from langgraph.graph.state import CompiledStateGraph, StateGraph  # noqa: E402

from orpath.agents.domains.tube import (  # noqa: E402
    DEFAULT_TUBE_LEAD_PROMPT,
    TUBE_ALL_AGENT_NAMES,
    TUBE_GEOMETRY_NAME,
    TUBE_GUARD_CALL_IDS,
    TUBE_LEAD_NAME,
    TUBE_PIPELINE_STAGE_ORDER,
    TUBE_Q1Q2_NAME,
    TUBE_Q3_NAME,
    TUBE_Q4_NAME,
    TUBE_REDTEAM_NAME,
    TUBE_WORKER_NAMES,
    TubeSupervisorState,
    build_compiled_tube_supervisor,
    build_tube_supervisor_graph,
    create_tube_geometry_agent,
    create_tube_q1q2_agent,
    create_tube_q3_agent,
    create_tube_q4_agent,
    create_tube_redteam_agent,
    get_tube_workers,
    tube_guard_post_hook,
)
from orpath.control_plane import get_chat_model  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore:create_react_agent has been moved")


@pytest.fixture()
def model() -> Any:
    return get_chat_model()


def test_tube_constants() -> None:
    assert len(TUBE_WORKER_NAMES) == 5
    assert len(TUBE_ALL_AGENT_NAMES) == 6
    assert TUBE_LEAD_NAME == "or_tube_lead"
    assert TUBE_PIPELINE_STAGE_ORDER == (
        TUBE_GEOMETRY_NAME,
        TUBE_Q1Q2_NAME,
        TUBE_Q3_NAME,
        TUBE_Q4_NAME,
        TUBE_REDTEAM_NAME,
    )
    for worker in TUBE_PIPELINE_STAGE_ORDER:
        assert worker in TUBE_GUARD_CALL_IDS


def test_tube_worker_creation(model: Any) -> None:
    geo = create_tube_geometry_agent(model=model)
    assert geo.name == TUBE_GEOMETRY_NAME

    q12 = create_tube_q1q2_agent(model=model)
    assert q12.name == TUBE_Q1Q2_NAME

    q3 = create_tube_q3_agent(model=model)
    assert q3.name == TUBE_Q3_NAME

    q4 = create_tube_q4_agent(model=model)
    assert q4.name == TUBE_Q4_NAME

    red = create_tube_redteam_agent(model=model)
    assert red.name == TUBE_REDTEAM_NAME

    workers = get_tube_workers(model=model)
    assert len(workers) == 5
    assert [w.name for w in workers] == list(TUBE_WORKER_NAMES)


def test_tube_supervisor_state_schema() -> None:
    from orpath.agents.domain_state import DomainSupervisorState

    # Phase 3 refactor: TubeSupervisorState now inherits the canonical OR-Path
    # supervisor schema instead of hand-rolling MessagesState.  TypedDict
    # classes do not support ``issubclass``, so assert via ``__orig_bases__``.
    assert TubeSupervisorState.__orig_bases__ == (DomainSupervisorState,)
    hints = get_type_hints(TubeSupervisorState)
    for flag in (
        "has_geometry_audited",
        "has_q1q2_solved",
        "has_q3_solved",
        "has_q4_solved",
        "has_redteam_verified",
    ):
        assert flag in hints and hints[flag] is bool
    for path_field in (
        "assumption_register_path",
        "budget_ledger_path",
        "candidate_solution_path",
        "validation_report_path",
    ):
        assert path_field in hints and hints[path_field] is str


def test_tube_supervisor_graph_build(model: Any) -> None:
    graph = build_tube_supervisor_graph(model=model)
    assert isinstance(graph, StateGraph)
    compiled = build_compiled_tube_supervisor(model=model)
    assert isinstance(compiled, CompiledStateGraph)
    for expected_node in TUBE_ALL_AGENT_NAMES:
        assert expected_node in compiled.nodes


def test_tube_guard_enforces_sequential_stages() -> None:
    # Empty
    assert tube_guard_post_hook({"messages": []}) == {}
    # Non AI
    assert tube_guard_post_hook({"messages": [HumanMessage("start")]}) == {}

    # Stage 1: bare reply -> transfer_to_or_tube_geometry
    u1 = tube_guard_post_hook({"messages": [HumanMessage("run"), AIMessage("done", id="m1")]})
    assert u1["messages"][1].tool_calls[0]["name"] == "transfer_to_or_tube_geometry"

    # Stage 2: geometry done -> transfer_to_or_tube_q1q2
    msgs2 = [
        HumanMessage("run"),
        AIMessage("g", name=TUBE_GEOMETRY_NAME),
        AIMessage("done", id="m2"),
    ]
    u2 = tube_guard_post_hook({"messages": msgs2})
    assert u2["messages"][1].tool_calls[0]["name"] == "transfer_to_or_tube_q1q2"

    # Stage 3: q1q2 done -> transfer_to_or_tube_q3
    msgs3 = [
        HumanMessage("run"),
        AIMessage("g", name=TUBE_GEOMETRY_NAME),
        AIMessage("12", name=TUBE_Q1Q2_NAME),
        AIMessage("done", id="m3"),
    ]
    u3 = tube_guard_post_hook({"messages": msgs3})
    assert u3["messages"][1].tool_calls[0]["name"] == "transfer_to_or_tube_q3"

    # Stage 4: q3 done -> transfer_to_or_tube_q4
    msgs4 = [
        HumanMessage("run"),
        AIMessage("g", name=TUBE_GEOMETRY_NAME),
        AIMessage("12", name=TUBE_Q1Q2_NAME),
        AIMessage("3", name=TUBE_Q3_NAME),
        AIMessage("done", id="m4"),
    ]
    u4 = tube_guard_post_hook({"messages": msgs4})
    assert u4["messages"][1].tool_calls[0]["name"] == "transfer_to_or_tube_q4"

    # Stage 5: q4 done -> transfer_to_or_tube_redteam
    msgs5 = [
        HumanMessage("run"),
        AIMessage("g", name=TUBE_GEOMETRY_NAME),
        AIMessage("12", name=TUBE_Q1Q2_NAME),
        AIMessage("3", name=TUBE_Q3_NAME),
        AIMessage("4", name=TUBE_Q4_NAME),
        AIMessage("done", id="m5"),
    ]
    u5 = tube_guard_post_hook({"messages": msgs5})
    assert u5["messages"][1].tool_calls[0]["name"] == "transfer_to_or_tube_redteam"

    # Stage 6: redteam done -> allow bare finish
    msgs6 = [
        HumanMessage("run"),
        AIMessage("g", name=TUBE_GEOMETRY_NAME),
        AIMessage("12", name=TUBE_Q1Q2_NAME),
        AIMessage("3", name=TUBE_Q3_NAME),
        AIMessage("4", name=TUBE_Q4_NAME),
        AIMessage("rt", name=TUBE_REDTEAM_NAME),
        AIMessage("completed", id="m6"),
    ]
    u6 = tube_guard_post_hook({"messages": msgs6})
    assert u6 == {}


def test_domains_reexport() -> None:
    import orpath.agents.domains as domains

    for symbol in (
        "TUBE_LEAD_NAME",
        "TUBE_GEOMETRY_NAME",
        "TUBE_Q1Q2_NAME",
        "TUBE_Q3_NAME",
        "TUBE_Q4_NAME",
        "TUBE_REDTEAM_NAME",
        "TUBE_WORKER_NAMES",
        "TUBE_ALL_AGENT_NAMES",
        "TUBE_DISCRETIONARY_BUDGET",
        "TUBE_RISK_OVERRIDE_BUDGET",
        "TUBE_Q4_INTERNAL_BUDGET",
        "TUBE_OBJECTIVE_ORDER",
        "TUBE_CANDIDATE_LIFECYCLE",
        "TubeSupervisorState",
        "create_tube_lead_agent",
        "create_tube_geometry_agent",
        "create_tube_q1q2_agent",
        "create_tube_q3_agent",
        "create_tube_q4_agent",
        "create_tube_redteam_agent",
        "get_tube_workers",
        "build_tube_supervisor_graph",
        "build_compiled_tube_supervisor",
        "tube_guard_post_hook",
        "validate_tube_experiment_card",
        "check_tube_budget_ledger",
        "run_tube_collaboration_gate",
        "run_tube_geometry_stability_gate",
        "run_tube_redteam_gate",
    ):
        assert hasattr(domains, symbol), f"domains missing {symbol}"


def test_tube_lead_agent_creation(model: Any) -> None:
    from orpath.agents.domains.tube import create_tube_lead_agent

    lead = create_tube_lead_agent(model=model)
    assert lead.name == TUBE_LEAD_NAME


def test_tube_protocol_constants() -> None:
    from orpath.agents.domains.tube import (
        TUBE_CANDIDATE_LIFECYCLE,
        TUBE_DISCRETIONARY_BUDGET,
        TUBE_OBJECTIVE_ORDER,
        TUBE_Q4_INTERNAL_BUDGET,
        TUBE_RISK_OVERRIDE_BUDGET,
    )

    assert TUBE_DISCRETIONARY_BUDGET == {"geometry": 20, "q1_q2": 10, "q3": 25, "q4": 45}
    assert sum(TUBE_DISCRETIONARY_BUDGET.values()) == 100
    assert TUBE_RISK_OVERRIDE_BUDGET == {"geometry": 35, "q1_q2": 10, "q3": 25, "q4": 30}
    assert sum(TUBE_RISK_OVERRIDE_BUDGET.values()) == 100
    assert sum(TUBE_Q4_INTERNAL_BUDGET.values()) == 100
    assert TUBE_OBJECTIVE_ORDER[0] == "hard_constraints"
    assert TUBE_CANDIDATE_LIFECYCLE == (
        "PROPOSED",
        "SOLVER_FEASIBLE",
        "INDEPENDENTLY_VALIDATED",
        "REDTEAM_PASSED",
        "ACCEPTED",
    )


def test_tube_domain_tools_execution() -> None:
    import json
    from orpath.agents.domains.tube import (
        check_tube_budget_ledger,
        run_tube_collaboration_gate,
        validate_tube_experiment_card,
    )

    # 1. Budget ledger tool
    ledger_res = json.loads(check_tube_budget_ledger.invoke({}))
    assert ledger_res["ok"] is True
    assert ledger_res["budget_percent"] == {"geometry": 20, "q1_q2": 10, "q3": 25, "q4": 45}

    # 2. Collaboration gate tool
    gate_res = json.loads(run_tube_collaboration_gate.invoke({}))
    assert gate_res["ok"] is True
    assert gate_res["returncode"] == 0

    # 3. Experiment card validation tool on golden card
    card_path = "experiments/tube/cards/tube-20260814-geometry-001.json"
    card_res = json.loads(validate_tube_experiment_card.invoke({"card_path": card_path}))
    assert card_res["ok"] is True
    assert card_res["owner_agent"] == "or-tube-geometry"


def test_control_plane_and_agents_tube_reexport(model: Any) -> None:
    import orpath.agents as agents
    import orpath.control_plane as cp

    assert hasattr(cp, "build_tube_supervisor_graph")
    assert hasattr(cp, "build_compiled_tube_supervisor")
    assert hasattr(agents, "build_tube_supervisor_graph")
    assert hasattr(agents, "build_compiled_tube_supervisor")
    assert hasattr(agents, "create_tube_lead_agent")

    compiled = cp.build_compiled_tube_supervisor(model=model)
    assert isinstance(compiled, CompiledStateGraph)
    for expected_node in TUBE_ALL_AGENT_NAMES:
        assert expected_node in compiled.nodes

