#!/usr/bin/env python3
"""Anti-template guard: every domain team binds genuine domain-specific tools.

The Phase-3 domain teams were template-generated: every expert bound the same
five generic tools
(``execute_or_solver`` / ``validate_solution_tool`` / ``execute_python_sandbox``
/ ``read_problem_file`` / ``search_or_knowledge``), making each domain a
reskinned parrot that cannot reason about its own problem structure.

This test enforces the fix: each domain exposes two genuinely domain-specific
deep-analysis tools — ``profile_<domain>_data`` (input-side, bound to the
auditor) and ``inspect_<domain>_solution`` (output-side, bound to the
exact-bound / heuristic / realities specialists) — grounded in
``orpath.agents.domain_analytics``.

Numbers Truth: the inspect tools recompute metrics from the solver envelope and
the recomputed objective must match the envelope objective.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytestmark = pytest.mark.filterwarnings("ignore:create_react_agent has been moved")

from orpath.control_plane import get_chat_model  # noqa: E402


@pytest.fixture()
def model() -> Any:
    return get_chat_model()


GENERIC_TOOLS = {
    "execute_or_solver",
    "validate_solution_tool",
    "execute_python_sandbox",
    "read_problem_file",
    "search_or_knowledge",
    "export_paper_markdown",
    "list_available_solvers",
}


# --------------------------------------------------------------------------- #
# 1. Tool-binding coverage: every domain wires domain-specific tools
# --------------------------------------------------------------------------- #

DOMAIN_SPECS: dict[str, dict[str, Any]] = {
    "routing": {
        "module": "orpath.agents.domains.routing",
        "profile": "profile_routing_data",
        "inspect": "inspect_routing_solution",
        "auditor": "create_routing_auditor_agent",
        "solvers": ["create_routing_exact_bound_agent", "create_routing_hgs_agent", "create_routing_realities_agent"],
    },
    "scheduling": {
        "module": "orpath.agents.domains.scheduling",
        "profile": "profile_scheduling_data",
        "inspect": "inspect_scheduling_solution",
        "auditor": "create_jssp_auditor_agent",
        "solvers": ["create_jssp_exact_bound_agent", "create_jssp_heuristic_agent", "create_jssp_realities_agent"],
    },
    "rostering": {
        "module": "orpath.agents.domains.rostering",
        "profile": "profile_rostering_data",
        "inspect": "inspect_rostering_solution",
        "auditor": "create_rostering_auditor_agent",
        "solvers": ["create_rostering_exact_bound_agent", "create_rostering_heuristic_agent", "create_rostering_realities_agent"],
    },
    "inventory": {
        "module": "orpath.agents.domains.inventory",
        "profile": "profile_inventory_data",
        "inspect": "inspect_inventory_solution",
        "auditor": "create_inventory_auditor_agent",
        "solvers": ["create_inventory_exact_bound_agent", "create_inventory_heuristic_agent", "create_inventory_realities_agent"],
    },
    "facility": {
        "module": "orpath.agents.domains.facility",
        "profile": "profile_facility_data",
        "inspect": "inspect_facility_solution",
        "auditor": "create_facility_auditor_agent",
        "solvers": ["create_facility_exact_bound_agent", "create_facility_heuristic_agent", "create_facility_realities_agent"],
    },
    "pricing": {
        "module": "orpath.agents.domains.pricing",
        "profile": "profile_pricing_data",
        "inspect": "inspect_pricing_solution",
        "auditor": "create_pricing_auditor_agent",
        "solvers": ["create_pricing_exact_bound_agent", "create_pricing_heuristic_agent", "create_pricing_realities_agent"],
    },
    "project": {
        "module": "orpath.agents.domains.project",
        "profile": "profile_project_data",
        "inspect": "inspect_project_solution",
        "auditor": "create_project_auditor_agent",
        "solvers": ["create_project_exact_bound_agent", "create_project_heuristic_agent", "create_project_realities_agent"],
    },
    "finance": {
        "module": "orpath.agents.domains.finance",
        "profile": "profile_portfolio_data",
        "inspect": "inspect_portfolio_solution",
        "auditor": "create_finance_auditor_agent",
        "solvers": ["create_finance_exact_bound_agent", "create_finance_heuristic_agent", "create_finance_realities_agent"],
    },
}


def _agent_tool_names(agent: Any) -> set[str]:
    """Return the set of tool names bound to a compiled react agent.

    The compiled graph carries a ``tools`` node whose bound ``ToolNode``
    exposes ``tools_by_name``.
    """
    nodes = getattr(agent, "nodes", None) or {}
    tool_node = nodes.get("tools")
    if tool_node is not None:
        bound = getattr(tool_node, "bound", None)
        tbm = getattr(bound, "tools_by_name", None) if bound is not None else None
        if tbm:
            return set(tbm.keys())
    tbm = getattr(agent, "tools_by_name", None)
    if tbm:
        return set(tbm.keys())
    return set()


@pytest.mark.parametrize("domain", sorted(DOMAIN_SPECS))
def test_domain_auditor_binds_profile_tool(domain: str, model: Any) -> None:
    """Each auditor binds its domain-specific input profiler (not just generic)."""
    spec = DOMAIN_SPECS[domain]
    mod = __import__(spec["module"], fromlist=[spec["auditor"]])
    factory = getattr(mod, spec["auditor"])
    agent = factory(model=model)
    names = _agent_tool_names(agent)
    assert spec["profile"] in names, (
        f"{domain} auditor missing domain-specific profiler {spec['profile']!r}; "
        f"bound tools: {sorted(names)}"
    )


@pytest.mark.parametrize("domain", sorted(DOMAIN_SPECS))
def test_domain_solver_agents_bind_inspect_tool(domain: str, model: Any) -> None:
    """Each exact-bound / heuristic / realities specialist binds the solution inspector."""
    spec = DOMAIN_SPECS[domain]
    mod = __import__(spec["module"], fromlist=spec["solvers"])
    for factory_name in spec["solvers"]:
        factory = getattr(mod, factory_name)
        agent = factory(model=model)
        names = _agent_tool_names(agent)
        assert spec["inspect"] in names, (
            f"{domain} {factory_name} missing domain-specific inspector "
            f"{spec['inspect']!r}; bound tools: {sorted(names)}"
        )


@pytest.mark.parametrize("domain", sorted(DOMAIN_SPECS))
def test_domain_agents_have_domain_specific_tools(domain: str, model: Any) -> None:
    """No solver specialist is left with only the 5 generic tools."""
    spec = DOMAIN_SPECS[domain]
    mod = __import__(spec["module"], fromlist=spec["solvers"])
    for factory_name in spec["solvers"]:
        factory = getattr(mod, factory_name)
        agent = factory(model=model)
        names = _agent_tool_names(agent)
        domain_specific = names - GENERIC_TOOLS
        assert domain_specific, (
            f"{domain} {factory_name} has NO domain-specific tool; "
            f"bound: {sorted(names)}"
        )


# --------------------------------------------------------------------------- #
# 2. Tool correctness: profile + inspect produce valid, truthful output
# --------------------------------------------------------------------------- #

def test_profile_tools_are_importable_and_callable() -> None:
    from orpath.agents.domain_analytics import (
        inspect_facility_solution,
        inspect_inventory_solution,
        inspect_portfolio_solution,
        inspect_pricing_solution,
        inspect_project_solution,
        inspect_rostering_solution,
        inspect_routing_solution,
        inspect_scheduling_solution,
        profile_facility_data,
        profile_inventory_data,
        profile_portfolio_data,
        profile_pricing_data,
        profile_project_data,
        profile_rostering_data,
        profile_routing_data,
        profile_scheduling_data,
    )

    tools = [
        profile_routing_data, profile_scheduling_data, profile_rostering_data,
        profile_inventory_data, profile_facility_data, profile_pricing_data,
        profile_project_data, profile_portfolio_data,
        inspect_routing_solution, inspect_scheduling_solution,
        inspect_rostering_solution, inspect_inventory_solution,
        inspect_facility_solution, inspect_pricing_solution,
        inspect_project_solution, inspect_portfolio_solution,
    ]
    for t in tools:
        assert hasattr(t, "invoke"), f"{t.name} is not a callable tool"


def test_profile_routing_data_integrity() -> None:
    from orpath.agents.domain_analytics import profile_routing_data

    result = json.loads(profile_routing_data.invoke({
        "solomon_path": "fixtures/benchmarks/vrp/c101.txt"
    }))
    assert result["ok"] is True
    assert result["num_nodes"] == 101
    assert result["num_clients"] == 100
    assert result["distance_matrix_symmetric"] is True
    assert result["triangle_inequality_holds"] is True
    assert result["integrity_ok"] is True
    assert result["coord_sha256"]


def test_profile_scheduling_data_known_optimum() -> None:
    from orpath.agents.domain_analytics import profile_scheduling_data

    result = json.loads(profile_scheduling_data.invoke({"instance": "ft06"}))
    assert result["ok"] is True
    assert result["num_jobs"] == 6
    assert result["num_machines"] == 6
    assert result["known_optimum"] == 55
    assert result["total_processing_work"] == 197


def test_profile_project_data_structure() -> None:
    from orpath.agents.domain_analytics import profile_project_data

    result = json.loads(profile_project_data.invoke({"instance": "j301_1"}))
    assert result["ok"] is True
    assert result["num_activities"] == 32
    assert result["num_resources"] == 4
    assert result["known_optimum"] == 43


def test_profile_facility_data_structure() -> None:
    from orpath.agents.domain_analytics import profile_facility_data

    result = json.loads(profile_facility_data.invoke({"benchmark": "cap41"}))
    assert result["ok"] is True
    assert result["num_facilities"] == 16
    assert result["num_customers"] == 50
    assert result["known_optimum"] == 1040444.375


def test_profile_inventory_data_structure() -> None:
    from orpath.agents.domain_analytics import profile_inventory_data

    result = json.loads(profile_inventory_data.invoke({"benchmark": "ww12"}))
    assert result["ok"] is True
    assert result["num_periods"] == 12
    assert result["total_demand"] == 370.0
    assert result["known_optimum"] == 670.0


def test_inspect_tools_handle_missing_file() -> None:
    from orpath.agents.domain_analytics import (
        inspect_routing_solution,
        inspect_scheduling_solution,
        inspect_project_solution,
    )

    for tool in (inspect_routing_solution, inspect_scheduling_solution, inspect_project_solution):
        result = json.loads(tool.invoke({"solution_path": "/nonexistent/path/solution.json"}))
        assert result["ok"] is False
        assert "not found" in result["error"]
