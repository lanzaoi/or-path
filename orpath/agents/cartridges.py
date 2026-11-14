#!/usr/bin/env python3
"""OR-Path declarer: ``DomainCartridge`` protocol + unified assembly registry.

Replaces the legacy 60-agent domain clone layer with a declarative domain gear kit:
    or:analyst  ->  selects a mechanism shipped with a DomainCartridge
    or:modeler  ->  pulls the solver suite listed in ``solver_modes``
    or:writer/reviewer ->  mounted ``profile_tool`` / ``inspect_tool`` domain

:func:`resolve_cartridge` maps any canonical ``problem_class`` (or an alias, or
an open-problem key) to a frozen :class:`DomainCartridge`. Unmapped / open
questions automatically fall back to the ``general_or`` cartridge which mounts
the shared MIP / CP-SAT sandbox and the modeling book.

Numbers Truth / Zero-truncation laws (AGENTS.md ground rule 3): cartridges only
point at tools and constants; no agent dialogue, no message-history slicing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Union

from orpath.domain_registry import normalize_problem_class as _norm

ToolOrNone = Union[Any, None]

__all__ = [
    "DomainCartridge",
    "CARTRIDGES",
    "CLASS_TO_DOMAIN",
    "TIER_FORCE_BY_RAW",
    "resolve_cartridge",
    "cartridge_tools",
    "cartridge_tier",
    "cartridge_skills",
    "cartridges",
    "GENERAL_OR_DOMAIN",
]

#: Fallback domain for non-standard / open MIP questions.
GENERAL_OR_DOMAIN = "general_or"


@dataclass(frozen=True)
class DomainCartridge:
    """Immutable domain gear kit specification."""

    domain: str
    problem_classes: tuple[str, ...]
    default_tier: Literal["A", "B", "C"]
    solver_modes: tuple[str, ...]
    profile_tool: ToolOrNone = None
    inspect_tool: ToolOrNone = None
    skill_topics: tuple[str, ...] = ()
    modeling_checklist: tuple[str, ...] = ()
    tier_by_class: dict[str, str] = field(default_factory=dict)
    general: bool = False


# --------------------------------------------------------------------------- #
# Registry assembly — 10 domain kits + general_or fallback
# --------------------------------------------------------------------------- #

_PROFILE_TOOL = {
    "routing": "profile_routing_data",
    "scheduling": "profile_scheduling_data",
    "microgrid": "profile_microgrid_data",
    "facility": "profile_facility_data",
    "finance": "profile_portfolio_data",
    "pricing": "profile_pricing_data",
    "inventory": "profile_inventory_data",
    "rostering": "profile_rostering_data",
    "project": "profile_project_data",
    "tube": "profile_tube_data",
}
_INSPECT_TOOL = {
    "routing": "inspect_routing_solution",
    "scheduling": "inspect_scheduling_solution",
    "microgrid": "inspect_microgrid_solution",
    "facility": "inspect_facility_solution",
    "finance": "inspect_portfolio_solution",
    "pricing": "inspect_pricing_solution",
    "inventory": "inspect_inventory_solution",
    "rostering": "inspect_rostering_solution",
    "project": "inspect_project_solution",
    "tube": "inspect_tube_solution",
}


def cartridge_tools(domain: str) -> dict[str, Any]:
    """Return ``{profile_tool, inspect_tool}`` resolved lazily for a domain."""
    da = __import__(
        "orpath.agents.domain_analytics",
        fromlist=["profile_routing_data", "inspect_routing_solution"],
    )
    p_name = _PROFILE_TOOL.get(domain)
    i_name = _INSPECT_TOOL.get(domain)
    profile = getattr(da, p_name, None) if p_name else None
    inspect = getattr(da, i_name, None) if i_name else None
    return {
        "profile_tool": profile,
        "inspect_tool": inspect,
        "profile": profile,
        "inspect": inspect,
    }


#: Canonical ``problem_class`` -> owning ``DomainCartridge`` domain key.
CLASS_TO_DOMAIN: dict[str, str] = {
    "shortest_path": "routing",
    "tsp": "routing",
    "vrp": "routing",
    "pyvrp": "routing",
    "network_flow": "routing",
    "jssp": "scheduling",
    "rcpsp": "project",
    "staff_rostering": "rostering",
    "facility_location": "facility",
    "hub_location": "facility",
    "qap": "facility",
    "portfolio_opt": "finance",
    "stochastic_lp": "pricing",
    "lot_sizing": "inventory",
    "tube_cut": "tube",
    "polyomino_cover": "tube",
    "bin_packing": "tube",
    "microgrid_dispatch": "microgrid",
    # combinatorial generalists routed through the general_or sandbox cartridge:
    "qubo_ising": "general_or",
    "graph_coloring": "general_or",
    "max_clique": "general_or",
    "game_theory": "general_or",
}

#: Raw-alias forced tiers (checked before canonical normalisation).
TIER_FORCE_BY_RAW: dict[str, str] = {
    "clsp": "B",
    "ulsp": "B",
}


CARTRIDGES: dict[str, DomainCartridge] = {
    "scheduling": DomainCartridge(
        domain="scheduling",
        problem_classes=("jssp",),
        default_tier="B",
        solver_modes=("jssp", "job_shop", "fjssp"),
        skill_topics=("pyjobshop-scheduling", "production-scheduling", "or-problems.md"),
        modeling_checklist=("析取图无环", "换模时延序列相关", "机器无重叠"),
    ),
    "routing": DomainCartridge(
        domain="routing",
        problem_classes=("shortest_path", "tsp", "vrp", "pyvrp", "network_flow"),
        default_tier="B",
        tier_by_class={"shortest_path": "A", "network_flow": "A"},
        solver_modes=("pyvrp", "vrp", "tsp", "shortest_path", "network_flow", "max_flow_matching"),
        modeling_checklist=("三角不等式", "时间窗一致", "需求+容量"),
    ),
    "project": DomainCartridge(
        domain="project",
        problem_classes=("rcpsp",),
        default_tier="B",
        solver_modes=("rcpsp", "psplib"),
        skill_topics=("or-problems.md", "or-process-memory"),
        modeling_checklist=("CPM 关键路径下界", "资源累积约束", "活动偏序无环"),
    ),
    "rostering": DomainCartridge(
        domain="rostering",
        problem_classes=("staff_rostering",),
        default_tier="B",
        solver_modes=("staff_rostering",),
        skill_topics=("or-problems.md",),
        modeling_checklist=("夜班强制休息", "每天一斑", "合同工时上限"),
    ),
    "inventory": DomainCartridge(
        domain="inventory",
        problem_classes=("lot_sizing",),
        default_tier="A",
        tier_by_class={"clsp": "B", "ulsp": "B"},
        solver_modes=("lot_sizing", "wagner_whitin", "clsp", "mrp"),
        skill_topics=("inventory-demand-planning", "or-problems.md"),
        modeling_checklist=("Wagner-Whitin 最优性定律", "流量守恒 I(t-1)+x-I=d", "CLSP 产能"),
    ),
    "finance": DomainCartridge(
        domain="finance",
        problem_classes=("portfolio_opt",),
        default_tier="A",
        solver_modes=("portfolio_opt", "portfolio", "markowitz", "risk_parity"),
        skill_topics=("or-numbers-truth", "or-problems.md", "or-modeling"),
        modeling_checklist=("凸 QP 严格求解", "权重单纯形 sum(w)=1", "long-only"),
    ),
    "pricing": DomainCartridge(
        domain="pricing",
        problem_classes=("stochastic_lp",),
        default_tier="A",
        solver_modes=("stochastic_lp",),
        skill_topics=("or-numbers-truth", "or-problems.md"),
        modeling_checklist=("情景概率单纯形=1", "两阶段 recourse 平衡", "EVPI/VSS 指标口径"),
    ),
    "microgrid": DomainCartridge(
        domain="microgrid",
        problem_classes=("microgrid_dispatch",),
        default_tier="B",
        solver_modes=("microgrid", "microgrid_dispatch", "energy_storage"),
        skill_topics=("or-modeling", "or-problems.md"),
        modeling_checklist=("SOC 上下限", "充放电互斥", "功率平衡 buy+pv+dis-ch>=load"),
    ),
    "tube": DomainCartridge(
        domain="tube",
        problem_classes=("tube_cut", "polyomino_cover", "bin_packing"),
        default_tier="B",
        solver_modes=("tube_cut", "tube", "polyomino", "polyomino_cover", "poly", "bin_packing", "binpack"),
        skill_topics=("or-problems.md", "research-ops-skills"),
        modeling_checklist=("PCA 几何一致性", "余料跨期继承账本", "共边负收益核算"),
    ),
    "facility": DomainCartridge(
        domain="facility",
        problem_classes=("facility_location", "hub_location", "qap"),
        default_tier="B",
        solver_modes=("facility_location", "cflp", "flp", "hub_location", "qap"),
        skill_topics=("or-numbers-truth", "or-problems.md"),
        modeling_checklist=("产能=需求分配", "单源二值", "运输成本 Haversine"),
    ),
    GENERAL_OR_DOMAIN: DomainCartridge(
        domain=GENERAL_OR_DOMAIN,
        problem_classes=(),
        default_tier="B",
        solver_modes=("sandbox", "custom_mip", "custom_cp"),
        skill_topics=("or-problems.md", "or-solver-select", "or-numbers-truth"),
        modeling_checklist=("受控沙箱自编 MIP/CP-SAT", "独立重算校验", "未知题型回退"),
        general=True,
    ),
}


def resolve_cartridge(problem_class_or_domain: str) -> DomainCartridge:
    """Map any canonical class / alias / domain key to its cartridge.

    Unknown or open questions fall back to the ``general_or`` cartridge that
    mounts the shared MIP / CP-SAT sandbox and the modeling book.
    """
    raw = str(problem_class_or_domain or "").strip().lower()
    if not raw:
        return CARTRIDGES[GENERAL_OR_DOMAIN]
    if raw in CARTRIDGES:
        return CARTRIDGES[raw]
    canonical = _norm(raw)
    domain = CLASS_TO_DOMAIN.get(canonical)
    if domain is None or domain not in CARTRIDGES:
        return CARTRIDGES[GENERAL_OR_DOMAIN]
    return CARTRIDGES[domain]


def cartridge_tier(problem_class_or_domain: str) -> Literal["A", "B", "C"]:
    """Resolve the complexity rail for a class/alias/domain."""
    raw = str(problem_class_or_domain or "").strip().lower()
    if raw in TIER_FORCE_BY_RAW:
        return TIER_FORCE_BY_RAW[raw]  # type: ignore[return-value]
    cartridge = resolve_cartridge(raw)
    canonical = _norm(raw)
    if canonical and canonical in cartridge.tier_by_class:
        return cartridge.tier_by_class[canonical]  # type: ignore[return-value]
    if raw in cartridge.tier_by_class:
        return cartridge.tier_by_class[raw]  # type: ignore[return-value]
    return cartridge.default_tier


def cartridge_skills(problem_class_or_domain: str) -> tuple[str, ...]:
    return resolve_cartridge(problem_class_or_domain).skill_topics


cartridges = CLASS_TO_DOMAIN
