#!/usr/bin/env python3
"""Task 4.3 — ControlPlane dynamic domain dispatch integration tests.

Covers the unified control-plane surface in ``orpath/control_plane.py``:

1. ``build_domain_supervisor_graph`` / ``build_compiled_domain_supervisor``
   for all 10 canonical domains (node count == 6, StateGraph /
   CompiledStateGraph types).
2. Invalid-domain ``ValueError`` interception (message lists legal domains).
3. The 10 per-domain convenience alias pairs delegating to the factory.
4. ``build_composite_supervisor`` (LRP / PRP / IRP / MICROGRID_FACILITY /
   CUSTOM validation) pipeline construction.
5. ``dispatch_supervisor_for_problem`` auto-routing from structured data,
   filename and free text — single-domain and composite verdicts.
6. Offline guarantee: no live API key is ever required (provider keys are
   stripped from the environment by an autouse fixture).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402
from langgraph.graph.state import CompiledStateGraph, StateGraph  # noqa: E402

import orpath.control_plane as cp  # noqa: E402
from orpath.agents.composite_lead import (  # noqa: E402
    COMPOSITE_DOMAIN_NODE_PREFIX,
    COMPOSITE_IRP,
    COMPOSITE_LRP,
    COMPOSITE_LEAD_NAME,
    COMPOSITE_MICROGRID_FACILITY,
    COMPOSITE_PRP,
    COMPOSITE_CUSTOM,
    CompositeLeadError,
)
from orpath.agents.meta_router import DomainRouteResult  # noqa: E402
from orpath.control_plane import (  # noqa: E402
    SUPPORTED_COMPOSITE_TYPES,
    SUPPORTED_DOMAIN_SUPERVISORS,
    build_compiled_domain_supervisor,
    build_composite_supervisor,
    build_domain_supervisor_graph,
    dispatch_supervisor_for_problem,
    get_chat_model,
    is_real_llm_configured,
)

pytestmark = pytest.mark.filterwarnings(
    "ignore:create_react_agent has been moved"
)

#: Canonical expected node count for every domain supervisor:
#: one lead supervisor + five specialist workers.
EXPECTED_DOMAIN_NODE_COUNT = 6

#: alias name pairs per domain: (graph alias, compiled alias)
DOMAIN_ALIASES: dict[str, tuple[str, str]] = {
    "tube": ("build_tube_supervisor_graph", "build_compiled_tube_supervisor"),
    "routing": ("build_routing_supervisor_graph", "build_compiled_routing_supervisor"),
    "scheduling": ("build_scheduling_supervisor_graph", "build_compiled_scheduling_supervisor"),
    "project": ("build_project_supervisor_graph", "build_compiled_project_supervisor"),
    "inventory": ("build_inventory_supervisor_graph", "build_compiled_inventory_supervisor"),
    "facility": ("build_facility_supervisor_graph", "build_compiled_facility_supervisor"),
    "rostering": ("build_rostering_supervisor_graph", "build_compiled_rostering_supervisor"),
    "microgrid": ("build_microgrid_supervisor_graph", "build_compiled_microgrid_supervisor"),
    "pricing": ("build_pricing_supervisor_graph", "build_compiled_pricing_supervisor"),
    "finance": ("build_finance_supervisor_graph", "build_compiled_finance_supervisor"),
}

# ---------------------------------------------------------------------------
# Offline guarantee — strip every provider API key so the shared model factory
# falls back to the placeholder key; no test may touch a live LLM endpoint.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def offline_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "DEEPSEEK_API_KEY",
        "XFYUN_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_BASE_URL",
        "XFYUN_BASE_URL",
        "OPENAI_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    assert is_real_llm_configured() is False


@pytest.fixture(scope="module")
def model() -> Any:
    """Shared offline model instance (placeholder key, never invoked)."""
    return get_chat_model()


# ---------------------------------------------------------------------------
# Structured payloads mirroring each domain solver's input contract
# (same shape as tools/test_task41_meta_router.py SCHEMA_PAYLOADS)
# ---------------------------------------------------------------------------
SCHEMA_PAYLOADS: dict[str, dict[str, Any]] = {
    "tube": {
        "tubes": [{"length": 3000.0, "diameter": 100.0}],
        "contours": [[[0.0, 0.0], [100.0, 0.0], [100.0, 50.0]]],
        "stock_lengths": [6000.0],
        "nesting": {"inset_mm": 4.0},
    },
    "routing": {
        "depot": 0,
        "customers": [{"id": 1, "demand": 5.0}],
        "demands": [0.0, 5.0, 3.0],
        "capacity": 10.0,
        "distance_matrix": [[0.0, 4.0, 6.0], [4.0, 0.0, 2.0], [6.0, 2.0, 0.0]],
        "time_windows": [[0.0, 999.0], [0.0, 999.0], [0.0, 999.0]],
    },
    "scheduling": {
        "jobs": [[(0, 4), (1, 3)], [(1, 2), (0, 5)]],
        "machines": [0, 1],
        "processing_times": [[4, 3], [2, 5]],
        "setup_times": {(0, 1): 2},
    },
    "project": {
        "activities": [{"duration": 4.0, "successors": [1]}, {"duration": 3.0, "successors": []}],
        "precedences": [[0, 1]],
        "resource_capacities": [10.0, 8.0],
        "renewable_resources": 2,
        "durations": [4.0, 3.0],
    },
    "inventory": {
        "demands": [20.0, 50.0, 10.0],
        "holding_cost": 1.0,
        "setup_cost": 85.0,
        "periods": 3,
        "production_cost": 5.0,
    },
    "facility": {
        "open_facilities": [0, 1],
        "fixed_costs": [100.0, 200.0],
        "capacities": [50.0, 60.0],
        "cost_matrix": [[0.0, 5.0], [5.0, 0.0]],
        "demands": [20.0, 30.0],
    },
    "rostering": {
        "roster": {"E1": ["D", "N"]},
        "shift_demands": [{"morning": 2, "night": 1}],
        "employees": ["E1", "E2"],
        "shifts": ["D", "N"],
        "assignments": {"E1": [0, 1]},
    },
    "microgrid": {
        "purchase_kwh": 10.0,
        "soc_kwh": 5.0,
        "loads_q1_kw": [[1.0, 2.0]],
        "prices_q1": [0.5],
        "pv_q1_kw": [[2.0, 1.5]],
        "battery_capacity_kwh": 20.0,
    },
    "pricing": {
        "first_stage_decision": {"capacity": 100.0},
        "second_stage_decision": {"production": 50.0},
        "scenarios": [{"probability": 0.5, "demand": 60.0}],
        "stochastic": True,
    },
    "finance": {
        "cov_matrix": [[0.04, 0.01], [0.01, 0.09]],
        "allocations": [0.6, 0.4],
        "expected_returns": [0.08, 0.12],
        "assets": ["A", "B"],
        "markowitz": True,
    },
}

#: filename → expected domain (bilingual keyword probe)
FILENAME_CASES: list[tuple[str, str]] = [
    ("tube_cutting_nesting_problem.json", "tube"),
    ("vehicle_routing_vrp_instance.json", "routing"),
    ("jssp_job_shop_scheduling.json", "scheduling"),
    ("rcpsp_project_scheduling.json", "project"),
    ("wagner_whitin_lot_sizing.json", "inventory"),
    ("cflp_facility_location.json", "facility"),
    ("staff_rostering_nurses.json", "rostering"),
    ("microgrid_dispatch_pv_battery.json", "microgrid"),
    ("dynamic_pricing_yield_management.json", "pricing"),
    ("markowitz_portfolio_optimization.json", "finance"),
]


# --------------------------------------------------------------------------- #
# 1. Dynamic domain supervisor factory — 10/10 domains
# --------------------------------------------------------------------------- #
def test_supported_domain_supervisors_registry() -> None:
    """The registry exposes exactly the 10 canonical domains."""
    assert set(SUPPORTED_DOMAIN_SUPERVISORS) == set(SCHEMA_PAYLOADS)
    assert len(SUPPORTED_DOMAIN_SUPERVISORS) == 10


@pytest.mark.parametrize("domain", sorted(SCHEMA_PAYLOADS))
def test_build_domain_supervisor_graph_all_domains(domain: str) -> None:
    """Un-compiled factory builds a 6-node StateGraph for every domain."""
    graph = build_domain_supervisor_graph(domain)
    assert isinstance(graph, StateGraph)
    assert not isinstance(graph, CompiledStateGraph)
    assert len(graph.nodes) == EXPECTED_DOMAIN_NODE_COUNT


@pytest.mark.parametrize("domain", sorted(SCHEMA_PAYLOADS))
def test_build_compiled_domain_supervisor_all_domains(domain: str) -> None:
    """Compiled factory returns a CompiledStateGraph with 6 agent nodes."""
    compiled = build_compiled_domain_supervisor(domain)
    assert isinstance(compiled, CompiledStateGraph)
    # ``__start__`` adds exactly one extra key to the compiled node map.
    assert len(compiled.nodes) - 1 == EXPECTED_DOMAIN_NODE_COUNT


@pytest.mark.parametrize("domain", sorted(SCHEMA_PAYLOADS))
def test_build_domain_supervisor_graph_accepts_model(domain: str, model: Any) -> None:
    """An injected model is forwarded to every domain worker."""
    graph = build_domain_supervisor_graph(domain, model=model)
    assert isinstance(graph, StateGraph)
    assert len(graph.nodes) == EXPECTED_DOMAIN_NODE_COUNT


@pytest.mark.parametrize("domain", sorted(SCHEMA_PAYLOADS))
def test_build_compiled_domain_supervisor_checkpointer(domain: str) -> None:
    """A LangGraph checkpointer is honoured by the compiled factory."""
    compiled = build_compiled_domain_supervisor(domain, checkpointer=MemorySaver())
    assert isinstance(compiled, CompiledStateGraph)
    assert len(compiled.nodes) - 1 == EXPECTED_DOMAIN_NODE_COUNT


def test_domain_name_normalization() -> None:
    """Domain keys are case/whitespace insensitive."""
    graph = build_domain_supervisor_graph("  TUBE ")
    assert isinstance(graph, StateGraph)
    assert len(graph.nodes) == EXPECTED_DOMAIN_NODE_COUNT


# --------------------------------------------------------------------------- #
# 2. Invalid-domain interception
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad_domain", ["unknown_domain", "", "   ", "tube_x"])
def test_build_domain_supervisor_graph_invalid_domain(bad_domain: str) -> None:
    with pytest.raises(ValueError) as excinfo:
        build_domain_supervisor_graph(bad_domain)
    message = str(excinfo.value)
    for legal in SUPPORTED_DOMAIN_SUPERVISORS:
        assert legal in message


@pytest.mark.parametrize("bad_domain", ["unknown_domain", "", "nope"])
def test_build_compiled_domain_supervisor_invalid_domain(bad_domain: str) -> None:
    with pytest.raises(ValueError) as excinfo:
        build_compiled_domain_supervisor(bad_domain)
    message = str(excinfo.value)
    for legal in SUPPORTED_DOMAIN_SUPERVISORS:
        assert legal in message


# --------------------------------------------------------------------------- #
# 3. Per-domain convenience aliases
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("domain", sorted(DOMAIN_ALIASES))
def test_domain_alias_graph_builders(domain: str) -> None:
    """Every ``build_<domain>_supervisor_graph`` alias delegates to the factory."""
    alias_name = DOMAIN_ALIASES[domain][0]
    builder = getattr(cp, alias_name)
    graph = builder()
    assert isinstance(graph, StateGraph)
    assert len(graph.nodes) == EXPECTED_DOMAIN_NODE_COUNT
    # delegation equivalence: same node set as the dynamic factory
    dynamic = build_domain_supervisor_graph(domain)
    assert set(graph.nodes) == set(dynamic.nodes)


@pytest.mark.parametrize("domain", sorted(DOMAIN_ALIASES))
def test_domain_alias_compiled_builders(domain: str) -> None:
    """Every ``build_compiled_<domain>_supervisor`` alias delegates to the factory."""
    alias_name = DOMAIN_ALIASES[domain][1]
    builder = getattr(cp, alias_name)
    compiled = builder()
    assert isinstance(compiled, CompiledStateGraph)
    assert len(compiled.nodes) - 1 == EXPECTED_DOMAIN_NODE_COUNT
    dynamic = build_compiled_domain_supervisor(domain)
    assert set(compiled.nodes) == set(dynamic.nodes)


@pytest.mark.parametrize("domain", sorted(DOMAIN_ALIASES))
def test_domain_alias_builders_accept_model(domain: str, model: Any) -> None:
    alias_name = DOMAIN_ALIASES[domain][0]
    graph = getattr(cp, alias_name)(model=model)
    assert isinstance(graph, StateGraph)
    assert len(graph.nodes) == EXPECTED_DOMAIN_NODE_COUNT


# --------------------------------------------------------------------------- #
# 4. Composite supervisor
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "composite_type, expected_chain",
    [
        (COMPOSITE_LRP, ["facility", "routing"]),
        (COMPOSITE_IRP, ["inventory", "routing"]),
        (COMPOSITE_PRP, ["scheduling", "inventory", "routing"]),
        (COMPOSITE_MICROGRID_FACILITY, ["facility", "microgrid"]),
    ],
)
def test_build_composite_supervisor_pipelines(composite_type: str, expected_chain: list[str]) -> None:
    """Canonical composite classes build compiled pipelines with stage nodes."""
    compiled = build_composite_supervisor(composite_type)
    assert isinstance(compiled, CompiledStateGraph)
    expected_nodes = {
        f"{COMPOSITE_DOMAIN_NODE_PREFIX}_{d}" for d in expected_chain
    } | {COMPOSITE_LEAD_NAME}
    assert expected_nodes <= set(compiled.nodes)


def test_build_composite_supervisor_checkpointer() -> None:
    compiled = build_composite_supervisor(COMPOSITE_LRP, checkpointer=MemorySaver())
    assert isinstance(compiled, CompiledStateGraph)
    assert f"{COMPOSITE_DOMAIN_NODE_PREFIX}_facility" in compiled.nodes


@pytest.mark.parametrize("bad_type", ["unknown", "", "lrp_x", "Location-Routing"])
def test_build_composite_supervisor_invalid_type(bad_type: str) -> None:
    with pytest.raises(ValueError) as excinfo:
        build_composite_supervisor(bad_type)
    message = str(excinfo.value)
    for legal in SUPPORTED_COMPOSITE_TYPES:
        assert legal in message


def test_build_composite_supervisor_custom_requires_chain() -> None:
    """CUSTOM without an explicit domain chain is rejected deterministically."""
    with pytest.raises(CompositeLeadError):
        build_composite_supervisor(COMPOSITE_CUSTOM)


def test_build_composite_supervisor_custom_with_chain() -> None:
    compiled = build_composite_supervisor(
        COMPOSITE_CUSTOM, domain_chain=["facility", "routing"]
    )
    assert isinstance(compiled, CompiledStateGraph)
    assert f"{COMPOSITE_DOMAIN_NODE_PREFIX}_facility" in compiled.nodes
    assert f"{COMPOSITE_DOMAIN_NODE_PREFIX}_routing" in compiled.nodes


def test_build_composite_supervisor_prp_pipeline_nodes() -> None:
    """PRP wires scheduling → inventory → routing plus the composite lead."""
    compiled = build_composite_supervisor(COMPOSITE_PRP)
    node_keys = list(compiled.nodes)
    assert node_keys.index(f"{COMPOSITE_DOMAIN_NODE_PREFIX}_scheduling") < \
        node_keys.index(f"{COMPOSITE_DOMAIN_NODE_PREFIX}_inventory") < \
        node_keys.index(f"{COMPOSITE_DOMAIN_NODE_PREFIX}_routing") < \
        node_keys.index(COMPOSITE_LEAD_NAME)


# --------------------------------------------------------------------------- #
# 5. dispatch_supervisor_for_problem — auto routing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("domain", sorted(SCHEMA_PAYLOADS))
def test_dispatch_from_structured_data(domain: str) -> None:
    """Structured payloads route to the matching compiled domain supervisor."""
    compiled, route_result = dispatch_supervisor_for_problem(data=SCHEMA_PAYLOADS[domain])
    assert isinstance(route_result, DomainRouteResult)
    assert route_result.domain == domain
    assert route_result.is_composite is False
    assert isinstance(compiled, CompiledStateGraph)
    assert len(compiled.nodes) - 1 == EXPECTED_DOMAIN_NODE_COUNT


@pytest.mark.parametrize("filename, expected_domain", FILENAME_CASES)
def test_dispatch_from_filename(filename: str, expected_domain: str) -> None:
    compiled, route_result = dispatch_supervisor_for_problem(filename=filename)
    assert route_result.domain == expected_domain
    assert isinstance(compiled, CompiledStateGraph)
    assert len(compiled.nodes) - 1 == EXPECTED_DOMAIN_NODE_COUNT


@pytest.mark.parametrize(
    "text, expected_domain",
    [
        ("激光套料与管材排样问题 cutting stock nesting", "tube"),
        ("车辆路径问题 VRP 配送路径优化", "routing"),
        ("车间调度 JSSP 作业车间生产排程", "scheduling"),
        ("工程项目调度 RCPSP 资源约束项目计划", "project"),
        ("动态批量 Wagner-Whitin 库存 lot sizing", "inventory"),
        ("设施选址 CFLP 供应链网络仓库规划", "facility"),
        ("护士排班 劳动力排班 班次安排", "rostering"),
        ("微电网光储充调度 分时电价优化", "microgrid"),
        ("收益管理 动态定价 两阶段随机规划", "pricing"),
        ("投资组合 资产配置 Markowitz 风险平价", "finance"),
    ],
)
def test_dispatch_from_text(text: str, expected_domain: str) -> None:
    compiled, route_result = dispatch_supervisor_for_problem(text=text)
    assert route_result.domain == expected_domain
    assert isinstance(compiled, CompiledStateGraph)


def test_dispatch_lrp_composite() -> None:
    """A composite LRP verdict pulls up the compiled composite supervisor."""
    compiled, route_result = dispatch_supervisor_for_problem(
        text="location-routing problem (LRP) 选址与配送联合优化"
    )
    assert route_result.is_composite is True
    assert route_result.composite_domains == ["facility", "routing"]
    assert isinstance(compiled, CompiledStateGraph)
    assert f"{COMPOSITE_DOMAIN_NODE_PREFIX}_facility" in compiled.nodes
    assert f"{COMPOSITE_DOMAIN_NODE_PREFIX}_routing" in compiled.nodes
    assert COMPOSITE_LEAD_NAME in compiled.nodes


def test_dispatch_prp_composite_from_data() -> None:
    """Structured data with scheduling + inventory + routing keys → PRP."""
    payload = {
        "jobs": [[(0, 4), (1, 3)], [(1, 2), (0, 5)]],
        "machines": [0, 1],
        "processing_times": [[4, 3], [2, 5]],
        "demands": [20.0, 50.0, 10.0],
        "holding_cost": 1.0,
        "setup_cost": 85.0,
        "periods": 3,
        "depot": 0,
        "customers": [{"id": 1, "demand": 5.0}],
        "capacity": 10.0,
        "distance_matrix": [[0.0, 4.0], [4.0, 0.0]],
    }
    compiled, route_result = dispatch_supervisor_for_problem(data=payload)
    assert route_result.is_composite is True
    assert route_result.composite_domains == ["scheduling", "inventory", "routing"]
    assert isinstance(compiled, CompiledStateGraph)
    for stage in ("scheduling", "inventory", "routing"):
        assert f"{COMPOSITE_DOMAIN_NODE_PREFIX}_{stage}" in compiled.nodes
    assert COMPOSITE_LEAD_NAME in compiled.nodes


def test_dispatch_microgrid_facility_composite() -> None:
    payload = {
        "open_facilities": [0],
        "fixed_costs": [100.0],
        "capacities": [200.0],
        "cost_matrix": [[0.0, 5.0], [5.0, 0.0]],
        "demands": [20.0, 30.0],
        "purchase_kwh": 10.0,
        "soc_kwh": 5.0,
        "loads_q1_kw": [[1.0, 2.0]],
        "prices_q1": [0.5],
        "pv_q1_kw": [[2.0, 1.5]],
    }
    compiled, route_result = dispatch_supervisor_for_problem(data=payload)
    assert route_result.is_composite is True
    assert set(route_result.composite_domains) == {"facility", "microgrid"}
    assert isinstance(compiled, CompiledStateGraph)
    assert f"{COMPOSITE_DOMAIN_NODE_PREFIX}_microgrid" in compiled.nodes


def test_dispatch_empty_input_defaults_to_scheduling() -> None:
    """No signal at all → the router's deterministic low-confidence default."""
    compiled, route_result = dispatch_supervisor_for_problem()
    assert route_result.domain == "scheduling"
    assert route_result.confidence == pytest.approx(0.2)
    assert isinstance(compiled, CompiledStateGraph)
    assert len(compiled.nodes) - 1 == EXPECTED_DOMAIN_NODE_COUNT


def test_dispatch_returns_tuple_of_graph_and_route_result() -> None:
    result = dispatch_supervisor_for_problem(text="TSP 旅行商问题")
    assert isinstance(result, tuple)
    assert len(result) == 2
    compiled, route_result = result
    assert isinstance(compiled, CompiledStateGraph)
    assert isinstance(route_result, DomainRouteResult)


def test_dispatch_checkpointer_forwarded() -> None:
    compiled, route_result = dispatch_supervisor_for_problem(
        filename="jssp_job_shop_scheduling.json",
        checkpointer=MemorySaver(),
    )
    assert route_result.domain == "scheduling"
    assert isinstance(compiled, CompiledStateGraph)


# --------------------------------------------------------------------------- #
# 6. Module surface — __all__ completeness
# --------------------------------------------------------------------------- #
def test_control_plane_exports_complete() -> None:
    expected_symbols = [
        "build_domain_supervisor_graph",
        "build_compiled_domain_supervisor",
        "SUPPORTED_DOMAIN_SUPERVISORS",
        "build_composite_supervisor",
        "dispatch_supervisor_for_problem",
        "SUPPORTED_COMPOSITE_TYPES",
        "COMPOSITE_LRP",
        "COMPOSITE_IRP",
        "COMPOSITE_PRP",
        "COMPOSITE_MICROGRID_FACILITY",
        "COMPOSITE_CUSTOM",
        *(alias for pair in DOMAIN_ALIASES.values() for alias in pair),
    ]
    for symbol in expected_symbols:
        assert symbol in cp.__all__, f"{symbol!r} missing from __all__"
        assert hasattr(cp, symbol), f"{symbol!r} not defined on module"


def test_control_plane_no_live_api_dependency(offline_env: None) -> None:
    """Graph construction works with zero provider credentials configured."""
    graph = build_domain_supervisor_graph("tube")
    assert isinstance(graph, StateGraph)
    assert is_real_llm_configured() is False
