#!/usr/bin/env python3
"""OR-Path declarer: ``DomainCartridge`` protocol + unified assembly registry.

Phase 2.1 — Replace the sixty-cloned-domain ``orpath/agents/domains/*.py``
(``~9,900`` lines of copy-pasted agents) with a *declarative* domain gear kit:

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

# Homomorphic tool type-hint (kept as Any so cartridges import without pulling
# langchain_core in this module's import graph, keeping offline gates fast).
ToolOrNone = Union[Any, None]

__all__ = [
    "DomainCartridge",
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
    """Immutable domain gear kit specification.

    Attributes
    ----------
    domain:
        Stable domain key, e.g. ``"scheduling"``, ``"routing"``, ``"microgrid".
    problem_classes:
        Canonical ``problem_class`` values this cartridge dispatches.
    default_tier:
        Default complexity rail (``"A"`` exact-polynomial / ``"B"``
        single-question combinatorial / ``"C"`` multi-question contests).
    tier_by_class:
        Optional per-class tier overrides used by :func:`cartridge_tier`
        (e.g. ``network_flow`` is Tier-A while a ``pyvrp`` route is Tier-B).
    solver_modes:
        Dispatch solver-mode names accepted by ``tools/solve_dispatch.py``.
    profile_tool:
        Input probe tool (``profile_<domain>_data``) mounted on the auditor.
    inspect_tool:
        Solution-sidebar decomposition tool (``inspect_<domain>_solution``).
    skill_topics:
        Knowledge / modeling-template topics auto-loaded from ``knowledge/skills/``.
    contract_path:
        Workdir-relative collaboration contract JSON.
    modeling_checklist:
        Domain-specific physics red-lines injected into the Modeler / Reviewer.
    general:
        True for the ``general_or`` fallback cartridge (unknown classes).
    """

    domain: str
    problem_classes: tuple[str, ...]
    default_tier: Literal["A", "B", "C"]
    solver_modes: tuple[str, ...]
    profile_tool: ToolOrNone = None
    inspect_tool: ToolOrNone = None
    skill_topics: tuple[str, ...] = ()
    contract_path: str = ""
    modeling_checklist: tuple[str, ...] = ()
    tier_by_class: dict[str, str] = field(default_factory=dict)
    general: bool = False


# --------------------------------------------------------------------------- #
# Registry assembly — 10 domain kits + general_or fallback
# --------------------------------------------------------------------------- #

def _t(name: str) -> Any:
    """Resolve a domain tool tool-name lazily (imports domain_analytics once)."""
    from orpath.agents.domain_analytics import _resolve_root as _  # noqa: F401

    return getattr(__import__("orpath.agents.domain_analytics", fromlist=[name]), name)


# Domain-analytics tool *names* (resolved lazily at handler-call time so imports stay light).
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
    da = __import__("orpath.agents.domain_analytics", fromlist=["profile_routing_data", "inspect_routing_solution"])
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


def _profile_tool(domain: str):
    return cartridge_tools(domain)["profile_tool"]


def _inspect_tool(domain: str):
    return cartridge_tools(domain)["inspect_tool"]


# --------------------------------------------------------------------------- #
# problem_class -> domain mapping (plan 2.1 acceptance: all 22 canonical classes)
# --------------------------------------------------------------------------- #

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
    "clsp": "B",   # multi-item capacity lot sizing -> combinatorial rail
    "ulsp": "B",
}

# Standard five-expert role tool templates (symbolic; resolved per domain).
ROLE_TOOLS: dict[str, tuple[str, ...]] = {
    "lead": ("contract", "ledger", "collab", "read_problem_file", "search_or_knowledge"),
    "auditor": (
        "contract", "profile", "read_problem_file", "execute_python_sandbox",
        "execute_or_solver", "search_or_knowledge",
    ),
    "exact_bound": (
        "execute_or_solver", "validate_solution_tool", "inspect", "execute_python_sandbox",
        "read_problem_file", "search_or_knowledge",
    ),
    "heuristic": (
        "execute_or_solver", "validate_solution_tool", "inspect", "execute_python_sandbox",
        "read_problem_file", "search_or_knowledge",
    ),
    "hgs": (
        "execute_or_solver", "validate_solution_tool", "inspect", "execute_python_sandbox",
        "read_problem_file", "search_or_knowledge",
    ),
    "realities": (
        "execute_or_solver", "validate_solution_tool", "inspect", "execute_python_sandbox",
        "read_problem_file", "search_or_knowledge",
    ),
    "redteam": (
        "redteam", "validate_solution_tool", "execute_python_sandbox",
        "read_problem_file", "search_or_knowledge",
    ),
    # tube-style roles
    "geometry": (
        "geometry_gate", "read_problem_file", "execute_python_sandbox",
        "execute_or_solver", "search_or_knowledge",
    ),
    "q1q2": (
        "card", "execute_or_solver", "validate_solution_tool", "execute_python_sandbox",
        "read_problem_file", "search_or_knowledge",
    ),
    "q3": (
        "card", "execute_or_solver", "validate_solution_tool", "execute_python_sandbox",
        "read_problem_file", "search_or_knowledge",
    ),
    "q4": (
        "card", "execute_or_solver", "validate_solution_tool", "execute_python_sandbox",
        "read_problem_file", "search_or_knowledge",
    ),
}

#: role id -> agent-name middle segment and protocol name suffix
ROLE_TITLES: dict[str, str] = {
    "auditor": "AUDITOR",
    "exact_bound": "EXACT_BOUND",
    "heuristic": "HEURISTIC",
    "hgs": "HGS",
    "realities": "REALITY",
    "redteam": "REDTEAM",
    "geometry": "GEOMETRY",
    "q1q2": "Q1Q2",
    "q3": "Q3",
    "q4": "Q4",
}

#: role id -> factory function suffix (create_<prefix>_<suffix>_agent)
ROLE_FACTORY_SUFFIX: dict[str, str] = {
    "auditor": "auditor",
    "exact_bound": "exact_bound",
    "heuristic": "heuristic",
    "hgs": "hgs",
    "realities": "realities",
    "redteam": "redteam",
    "geometry": "geometry",
    "q1q2": "q1q2",
    "q3": "q3",
    "q4": "q4",
}


@dataclass(frozen=True)
class TeamSpec:
    """Declarative identity of one domain collaboration team (plan 2.4)."""

    domain: str
    name_prefix: str                       # e.g. "JSSP" / "FACILITY"
    lead_prefix: str                       # agent-name prefix: jssp / vrp / tube ...
    roles: tuple[str, ...]                 # worker role ids in pipeline order
    state_prefix: str                      # e.g. "Scheduling" -> SchedulingSupervisorState
    state_fields: dict[str, tuple[Any, Any]]
    spec: Any                               # contract_validator.DomainSpec
    role_tools_overrides: dict[str, tuple[str, ...]] = field(default_factory=dict)
    prompt_vars: dict[str, str] = field(default_factory=dict)  # role -> prompt var name


# Standard stage flags shared by the auditor/exact/heuristic/realities domains.
_STANDARD_STAGE_FIELDS = {
    "has_auditor_verified": (bool, False),
    "has_exact_bound_computed": (bool, False),
    "has_heuristic_solved": (bool, False),
    "has_realities_applied": (bool, False),
    "has_redteam_verified": (bool, False),
    "exact_bound_report_path": (str, ""),
}


def _complete_team_specs() -> dict[str, "TeamSpec"]:
    """Assemble the declarative tables consumed by :func:`build_team_namespace`."""
    from orpath.agents.contract_validator import DomainSpec

    standard_budget = {"auditor": 20, "exact_bound": 15, "heuristic": 35, "realities": 30}
    standard_override = {"auditor": 35, "exact_bound": 10, "heuristic": 30, "realities": 25}
    override_30 = {"auditor": 30, "exact_bound": 10, "heuristic": 30, "realities": 30}
    lifecycle = (
        "PROPOSED", "SOLVER_FEASIBLE", "INDEPENDENTLY_VALIDATED", "REDTEAM_PASSED", "ACCEPTED",
    )
    roles_std = ("auditor", "exact_bound", "heuristic", "realities", "redteam")

    def mk_std(domain, prefix, problem_id, solution, out, budget, override, objective, tamper):
        return DomainSpec(
            domain=domain,
            contract_path=f"contracts/{domain}_collaboration_v1.json",
            ledger_path=f"experiments/{domain}/budget-ledger.json",
            solution_path=solution,
            redteam_out_path=out,
            budget=budget,
            risk_override_budget=override,
            objective_order=objective,
            candidate_lifecycle=lifecycle,
            tamper_tests=tamper,
        )

    specs: dict[str, dict[str, object]] = {}

    specs["scheduling"] = dict(
        domain="scheduling", name_prefix="JSSP", lead_prefix="jssp", problem_id="pyjobshop_jssp",
        state_prefix="Scheduling", roles=roles_std,
        state_fields={**_STANDARD_STAGE_FIELDS,
                      "schedule_plan_path": (str, ""),
                      "makespan": (int | None, None),
                      "total_setup_time": (int | None, None),
                      "total_tardiness": (int | None, None)},
        spec=mk_std("scheduling", "JSSP", "pyjobshop_jssp",
                    "outputs/pyjobshop_jssp-solution.json", "outputs/pyjobshop_jssp-redteam.json",
                    standard_budget, standard_override,
                    ("hard_constraints", "makespan", "total_setup_time", "total_tardiness"),
                    ("machine_overlap_injection", "operation_precedence_inversion", "setup_time_cheat",
                     "makespan_deflation", "job_omission_tamper")),
    )

    specs["routing"] = dict(
        domain="routing", name_prefix="ROUTING", lead_prefix="vrp", problem_id="pyvrp_vrptw",
        state_prefix="Routing", roles=("auditor", "exact_bound", "hgs", "realities", "redteam"),
        state_fields={**_STANDARD_STAGE_FIELDS,
                      **{"has_heuristic_solved": (bool, False)},
                      **{"has_hgs_solved": (bool, False)}},
        spec=DomainSpec(
            domain="routing",
            contract_path="contracts/routing_collaboration_v1.json",
            ledger_path="experiments/routing/budget-ledger.json",
            solution_path="outputs/pyvrp_vrptw-solution.json",
            redteam_out_path="outputs/pyvrp_vrptw-redteam.json",
            budget={"auditor": 20, "exact_bound": 15, "hgs": 35, "realities": 30},
            risk_override_budget={"auditor": 35, "exact_bound": 10, "hgs": 30, "realities": 25},
            objective_order=("hard_constraints", "total_distance", "num_vehicles_used", "max_route_duration"),
            candidate_lifecycle=lifecycle,
            tamper_tests=("capacity_overflow_injection", "client_omission_tamper", "time_window_inversion",
                          "distance_forgery", "coordinate_hash_tamper"),
        ),
        prompt_vars={
            "lead": "DEFAULT_ROUTING_LEAD_PROMPT",
            "auditor": "AUDITOR_PROMPT",
            "exact_bound": "EXACT_BOUND_PROMPT",
            "hgs": "HGS_PROMPT",
            "realities": "REALITY_PROMPT",
            "redteam": "REDTEAM_PROMPT",
        },
    )

    specs["project"] = dict(
        domain="project", name_prefix="PROJECT", lead_prefix="project", problem_id="psplib_rcpsp",
        state_prefix="Project", roles=roles_std,
        state_fields={**_STANDARD_STAGE_FIELDS,
                      "schedule_plan_path": (str, ""),
                      "schedule_plan": (list[dict[str, Any]], []),
                      "makespan": (int | None, None),
                      "num_activities": (int | None, None),
                      "num_resources": (int | None, None),
                      "precedence_count": (int | None, None),
                      "resource_capacities": (list[int], []),
                      "critical_path": (list[int], []),
                      "resource_peak_demand": (list[int], []),
                      "total_slack": (int | None, None)},
        spec=mk_std("project", "PROJECT", "psplib_rcpsp",
                    "outputs/psplib_rcpsp-solution.json", "outputs/psplib_rcpsp-redteam.json",
                    standard_budget, standard_override,
                    ("hard_constraints", "makespan", "resource_peak_demand", "total_slack"),
                    ("resource_capacity_overflow", "activity_precedence_inversion", "duration_inconsistency_cheat",
                     "makespan_deflation", "activity_omission_tamper")),
    )

    specs["rostering"] = dict(
        domain="rostering", name_prefix="ROSTERING", lead_prefix="rostering", problem_id="staff_rostering",
        state_prefix="Rostering", roles=roles_std,
        state_fields={**_STANDARD_STAGE_FIELDS,
                      "roster_plan_path": (str, ""),
                      "roster": (dict[str, list[str]], {}),
                      "schedule_by_day": (list[dict[str, Any]], []),
                      "shift_demands": (list[dict[str, int]], []),
                      "fairness_metrics": (dict[str, Any], {}),
                      "max_consecutive_days": (int, 5),
                      "num_employees": (int, 8),
                      "num_days": (int, 14),
                      "fairness_variance": (float | None, None),
                      "unpreferred_shift_count": (int, 0),
                      "total_overtime_hours": (float, 0.0),
                      "lower_bound": (int | None, None),
                      "optimality_gap": (float | None, None)},
        spec=mk_std("rostering", "ROSTERING", "staff_rostering",
                    "outputs/staff_rostering-solution.json", "outputs/staff_rostering-redteam.json",
                    standard_budget, override_30,
                    ("hard_constraints", "fairness_variance", "unpreferred_shift_count", "total_overtime_hours"),
                    ("understaffing_coverage_tamper", "shift_clash_tamper", "night_rest_violation_injection",
                     "consecutive_workday_overflow", "fairness_metric_tamper")),
    )

    specs["inventory"] = dict(
        domain="inventory", name_prefix="INVENTORY", lead_prefix="inventory", problem_id="wagner_whitin_clsp",
        state_prefix="Inventory", roles=roles_std,
        state_fields={**_STANDARD_STAGE_FIELDS,
                      "schedule_plan_path": (str, ""),
                      "schedule_plan": (list[dict[str, Any]], []),
                      "total_cost": (float | None, None),
                      "total_setup_cost": (float | None, None),
                      "total_holding_cost": (float | None, None),
                      "total_production_cost": (float | None, None),
                      "max_inventory_level": (float | None, None),
                      "num_setups": (int | None, None),
                      "num_periods": (int | None, None),
                      "safety_stock": (float | None, None),
                      "capacity": (float | None, None),
                      "initial_inventory": (float | None, None),
                      "unit_cost": (float | None, None)},
        spec=mk_std("inventory", "INVENTORY", "wagner_whitin_clsp",
                    "outputs/wagner_whitin_clsp-solution.json", "outputs/wagner_whitin_clsp-redteam.json",
                    standard_budget, standard_override,
                    ("hard_constraints", "total_cost", "total_setup_cost", "max_inventory_level"),
                    ("flow_balance_violation_injection", "setup_evasion_tamper", "capacity_overflow_injection",
                     "safety_stock_deficit_tamper", "cost_deflation_forgery")),
    )

    specs["finance"] = dict(
        domain="finance", name_prefix="FINANCE", lead_prefix="finance", problem_id="markowitz_portfolio",
        state_prefix="Finance", roles=roles_std,
        state_fields={**_STANDARD_STAGE_FIELDS,
                      "discrete_allocation_plan_path": (str, ""),
                      "allocations": (dict[str, Any], {}),
                      "discrete_shares": (dict[str, Any], {}),
                      "expected_return": (float, 0.0),
                      "volatility": (float, 0.0),
                      "sharpe_ratio": (float, 0.0),
                      "portfolio_variance": (float, 0.0),
                      "cvar_tail_risk": (float, 0.0),
                      "turnover": (float, 0.0),
                      "black_litterman_incumbent": (dict[str, Any], {}),
                      "risk_parity_incumbent": (dict[str, Any], {}),
                      "discrete_allocation_plan": (dict[str, Any], {}),
                      "transaction_slippage_policy": (dict[str, Any], {}),
                      "turnover_limit_policy": (dict[str, Any], {}),
                      "sector_exposure_ceiling_policy": (dict[str, Any], {}),
                      "reality_feasibility": (dict[str, Any], {}),
                      "convex_qp_markowitz_bound": (float | None, None),
                      "unconstrained_sharpe_bound": (float | None, None),
                      "bound_evidence": (dict[str, Any], {}),
                      "lower_bound": (float | None, None),
                      "optimality_gap": (float | None, None)},
        spec=mk_std("finance", "FINANCE", "markowitz_portfolio",
                    "outputs/markowitz_portfolio-solution.json", "outputs/markowitz_portfolio-redteam.json",
                    standard_budget, override_30,
                    ("hard_constraints", "sharpe_ratio", "portfolio_variance", "cvar_tail_risk"),
                    ("weight_simplex_violation_injection", "short_position_breach_injection",
                     "sharpe_ratio_inflation_forgery", "variance_risk_deflation_forgery",
                     "discrete_lot_allocation_tamper")),
    )

    specs["pricing"] = dict(
        domain="pricing", name_prefix="PRICING", lead_prefix="pricing", problem_id="farmer_stochastic_lp",
        state_prefix="Pricing", roles=roles_std,
        state_fields={**_STANDARD_STAGE_FIELDS,
                      "allocation_pricing_plan_path": (str, ""),
                      "first_stage_decision": (dict[str, Any], {}),
                      "first_stage_cost": (float, 0.0),
                      "expected_profit": (float, 0.0),
                      "expected_second_stage_revenue": (float, 0.0),
                      "stochastic_indicators": (dict[str, Any], {}),
                      "evpi": (float, 0.0),
                      "vss": (float, 0.0),
                      "cvar_penalty": (float, 0.0),
                      "sample_average_approximation_incumbent": (dict[str, Any], {}),
                      "bid_price_heuristic_incumbent": (dict[str, Any], {}),
                      "allocation_pricing_plan": (dict[str, Any], {}),
                      "cvar_risk_aversion_policy": (dict[str, Any], {}),
                      "overbooking_cancellation_policy": (dict[str, Any], {}),
                      "demand_elasticity_fencing_policy": (dict[str, Any], {}),
                      "reality_feasibility": (dict[str, Any], {}),
                      "deterministic_equivalent_lp_bound": (float | None, None),
                      "l_shaped_benders_cut": (float | None, None),
                      "bound_evidence": (dict[str, Any], {}),
                      "lower_bound": (float | None, None),
                      "optimality_gap": (float | None, None)},
        spec=mk_std("pricing", "PRICING", "farmer_stochastic_lp",
                    "outputs/farmer_stochastic_lp-solution.json", "outputs/farmer_stochastic_lp-redteam.json",
                    standard_budget, override_30,
                    ("hard_constraints", "expected_profit", "risk_cvar_penalty", "evpi_efficiency"),
                    ("first_stage_capacity_overflow", "scenario_recourse_balance_tamper",
                     "stochastic_inequality_forgery", "expected_profit_inflation_forgery",
                     "first_stage_cost_tamper")),
    )

    specs["microgrid"] = dict(
        domain="microgrid", name_prefix="MICROGRID", lead_prefix="microgrid", problem_id="microgrid_dispatch",
        state_prefix="Microgrid", roles=roles_std,
        state_fields={**_STANDARD_STAGE_FIELDS,
                      "battery_dispatch_plan_path": (str, ""),
                      "subproblems": (dict[str, Any], {}),
                      "q1": (dict[str, Any], {}),
                      "q2": (dict[str, Any], {}),
                      "q3": (dict[str, Any], {}),
                      "q4_2": (dict[str, Any], {}),
                      "q4_3": (dict[str, Any], {}),
                      "battery_dispatch_plan": (dict[str, Any], {}),
                      "total_purchase_cost": (float, 0.0),
                      "peak_demand_kw": (float, 0.0),
                      "battery_degradation_loss": (float, 0.0),
                      "tou_tariff_integrity": (dict[str, Any], {}),
                      "pv_load_profile_consistency": (dict[str, Any], {}),
                      "battery_nameplate_specs": (dict[str, Any], {}),
                      "lower_bound": (float | None, None),
                      "optimality_gap": (float | None, None)},
        spec=mk_std("microgrid", "MICROGRID", "microgrid_dispatch",
                    "outputs/microgrid_dispatch-solution.json", "outputs/microgrid_dispatch-redteam.json",
                    standard_budget, override_30,
                    ("hard_constraints", "total_purchase_cost", "peak_demand_kw", "battery_degradation_loss"),
                    ("power_balance_violation_injection", "soc_limit_breach_injection",
                     "battery_efficiency_dynamics_tamper", "daily_storage_imbalance_tamper",
                     "energy_cost_deflation_forgery")),
        role_tools_overrides={
            "exact_bound": ROLE_TOOLS["exact_bound"][:1] + ("inspect", "validate_solution_tool") + ROLE_TOOLS["exact_bound"][3:],
            "heuristic": ROLE_TOOLS["heuristic"][:1] + ("inspect", "validate_solution_tool") + ROLE_TOOLS["heuristic"][3:],
            "realities": ROLE_TOOLS["realities"][:1] + ("inspect", "validate_solution_tool", "export_paper_markdown") + ROLE_TOOLS["realities"][3:],
            "redteam": ("redteam", "profile", "validate_solution_tool", "execute_python_sandbox",
                        "read_problem_file", "search_or_knowledge"),
        },
    )

    specs["facility"] = dict(
        domain="facility", name_prefix="FACILITY", lead_prefix="facility", problem_id="beasley_cflp",
        state_prefix="Facility", roles=roles_std,
        state_fields={**_STANDARD_STAGE_FIELDS,
                      "facility_allocation_plan_path": (str, ""),
                      "open_facilities": (list[dict[str, Any]], []),
                      "allocations": (list[dict[str, Any]], []),
                      "total_cost": (float | None, None),
                      "num_open_facilities": (int | None, None),
                      "total_fixed_cost": (float | None, None),
                      "total_transport_cost": (float | None, None),
                      "total_co2_kg": (float | None, None),
                      "total_ton_km": (float | None, None),
                      "lower_bound": (float | None, None),
                      "optimality_gap": (float | None, None),
                      "known_optimum": (float | None, None),
                      "num_facilities": (int | None, None),
                      "num_customers": (int | None, None),
                      "single_source": (bool, False)},
        spec=mk_std("facility", "FACILITY", "beasley_cflp",
                    "outputs/beasley_cflp-solution.json", "outputs/beasley_cflp-redteam.json",
                    standard_budget, standard_override,
                    ("hard_constraints", "total_cost", "num_open_facilities", "total_co2_kg"),
                    ("facility_capacity_overflow_injection", "demand_undersatisfaction_tamper",
                     "closed_facility_allocation_cheat", "cost_deflation_forgery",
                     "single_source_fractional_cheat")),
    )

    specs["tube"] = dict(
        domain="tube", name_prefix="TUBE", lead_prefix="tube", problem_id="tube_cut_b2026",
        state_prefix="Tube", roles=("geometry", "q1q2", "q3", "q4", "redteam"),
        state_fields={
            "has_geometry_audited": (bool, False),
            "has_q1q2_solved": (bool, False),
            "has_q3_solved": (bool, False),
            "has_q4_solved": (bool, False),
            "has_redteam_verified": (bool, False),
            "geometry_stability_report_path": (str, ""),
        },
        spec=DomainSpec(
            domain="tube",
            ledger_path="experiments/tube/budget-ledger.json",
            solution_path="outputs/tube_cut_b2026-solution.json",
            redteam_out_path="outputs/tube_cut_b2026-redteam.json",
            budget={"geometry": 20, "q1_q2": 10, "q3": 25, "q4": 45},
            risk_override_budget={"geometry": 35, "q1_q2": 10, "q3": 25, "q4": 30},
            objective_order=("hard_constraints", "new_standard_stock_mm", "negative_co_cut_benefit_mm",
                             "type_switches", "diagnostic_waste_mm"),
            candidate_lifecycle=lifecycle,
            collaboration_gate_script="tube_collaboration_gate.py",
            sub_budget_key="q4_internal_budget_percent",
            sub_budget={"future_value_and_stratified_beam": 40, "remaining_demand_cocut_initializer": 25,
                        "beam_width_and_new_seeds": 20, "targeted_deletion_repair": 10,
                        "strict_validation_and_reproduction": 5},
        ),
        role_tools_overrides={
            "lead": ("card", "ledger", "collab", "read_problem_file", "search_or_knowledge"),
            "geometry": ("geometry_gate", "profile", "read_problem_file", "execute_python_sandbox", "execute_or_solver", "search_or_knowledge"),
            "q1q2": ("execute_or_solver", "validate_solution_tool", "inspect", "execute_python_sandbox", "read_problem_file", "search_or_knowledge"),
            "q3": ("execute_or_solver", "validate_solution_tool", "inspect", "execute_python_sandbox", "read_problem_file", "search_or_knowledge"),
            "q4": ("execute_or_solver", "validate_solution_tool", "inspect", "execute_python_sandbox", "read_problem_file", "search_or_knowledge"),
            "redteam": ("redteam", "profile", "validate_solution_tool", "execute_python_sandbox", "read_problem_file", "search_or_knowledge"),
        },
        prompt_vars={
            "lead": "DEFAULT_TUBE_LEAD_PROMPT",
            "geometry": "GEOMETRY_PROMPT",
            "q1q2": "Q1Q2_PROMPT",
            "q3": "Q3_PROMPT",
            "q4": "Q4_PROMPT",
            "redteam": "REDTEAM_PROMPT",
        },
    )

    teams: dict[str, TeamSpec] = {}
    for domain, cfg in specs.items():
        st = cfg.get("state_fields", {})
        state_fields = {**st, "domain": (str, cfg["domain"]), "problem_id": (str, cfg["problem_id"])}
        teams[domain] = TeamSpec(
            domain=domain,
            name_prefix=cfg["name_prefix"],
            lead_prefix=cfg["lead_prefix"],
            roles=tuple(cfg["roles"]),
            state_prefix=cfg["state_prefix"],
            state_fields=state_fields,
            spec=cfg["spec"],
            role_tools_overrides=dict(cfg.get("role_tools_overrides", {})),
            prompt_vars=dict(cfg.get("prompt_vars", {})),
        )
    return teams


TEAMS: dict[str, TeamSpec] = _complete_team_specs()


# --------------------------------------------------------------------------- #
# 10 DomainCartridges + general_or fallback (plans 2.1-2.3)
# --------------------------------------------------------------------------- #

CARTRIDGES: dict[str, DomainCartridge] = {
    "scheduling": DomainCartridge(
        domain="scheduling",
        problem_classes=("jssp",),
        default_tier="B",
        solver_modes=("jssp", "job_shop", "fjssp"),
        skill_topics=("pyjobshop-scheduling", "production-scheduling", "or-problems.md"),
        contract_path="contracts/scheduling_collaboration_v1.json",
        modeling_checklist=("析取图无环", "换模时延序列相关", "机器无重叠"),
    ),
    "routing": DomainCartridge(
        domain="routing",
        problem_classes=("shortest_path", "tsp", "vrp", "pyvrp", "network_flow"),
        default_tier="B",
        tier_by_class={"shortest_path": "A", "network_flow": "A"},
        solver_modes=("pyvrp", "vrp", "tsp", "shortest_path", "network_flow", "max_flow_matching"),
        contract_path="contracts/routing_collaboration_v1.json",
        modeling_checklist=("三角不等式", "时间窗一致", "需求+容量"),
    ),
    "project": DomainCartridge(
        domain="project",
        problem_classes=("rcpsp",),
        default_tier="B",
        solver_modes=("rcpsp", "psplib"),
        skill_topics=("or-problems.md", "or-process-memory"),
        contract_path="contracts/project_collaboration_v1.json",
        modeling_checklist=("CPM 关键路径下界", "资源累积约束", "活动偏序无环"),
    ),
    "rostering": DomainCartridge(
        domain="rostering",
        problem_classes=("staff_rostering",),
        default_tier="B",
        solver_modes=("staff_rostering",),
        skill_topics=("or-problems.md",),
        contract_path="contracts/rostering_collaboration_v1.json",
        modeling_checklist=("夜班强制休息", "每天一斑", "合同工时上限"),
    ),
    "inventory": DomainCartridge(
        domain="inventory",
        problem_classes=("lot_sizing",),
        default_tier="A",
        tier_by_class={"clsp": "B", "ulsp": "B"},
        solver_modes=("lot_sizing", "wagner_whitin", "clsp", "mrp"),
        skill_topics=("inventory-demand-planning", "or-problems.md"),
        contract_path="contracts/inventory_collaboration_v1.json",
        modeling_checklist=("Wagner-Whitin 最优性定律", "流量守恒 I(t-1)+x-I=d", "CLSP 产能"),
    ),
    "finance": DomainCartridge(
        domain="finance",
        problem_classes=("portfolio_opt",),
        default_tier="A",
        solver_modes=("portfolio_opt", "portfolio", "markowitz", "risk_parity"),
        skill_topics=("or-numbers-truth", "or-problems.md", "or-modeling"),
        contract_path="contracts/finance_collaboration_v1.json",
        modeling_checklist=("凸 QP 严格求解", "权重单纯形 sum(w)=1", "long-only"),
    ),
    "pricing": DomainCartridge(
        domain="pricing",
        problem_classes=("stochastic_lp",),
        default_tier="A",
        solver_modes=("stochastic_lp",),
        skill_topics=("or-numbers-truth", "or-problems.md"),
        contract_path="contracts/pricing_collaboration_v1.json",
        modeling_checklist=("情景概率单纯形=1", "两阶段 recourse 平衡", "EVPI/VSS 指标口径"),
    ),
    "microgrid": DomainCartridge(
        domain="microgrid",
        problem_classes=("microgrid_dispatch",),
        default_tier="B",
        solver_modes=("microgrid", "microgrid_dispatch", "energy_storage"),
        skill_topics=("or-modeling", "or-problems.md"),
        contract_path="contracts/microgrid_collaboration_v1.json",
        modeling_checklist=("SOC 上下限", "充放电互斥", "功率平衡 buy+pv+dis-ch>=load"),
    ),
    "tube": DomainCartridge(
        domain="tube",
        problem_classes=("tube_cut", "polyomino_cover", "bin_packing"),
        default_tier="B",
        solver_modes=("tube_cut", "tube", "polyomino", "polyomino_cover", "poly", "bin_packing", "binpack"),
        skill_topics=("or-problems.md", "research-ops-skills"),
        contract_path="contracts/tube_collaboration_v1.json",
        modeling_checklist=("PCA 几何一致性", "余料跨期继承账本", "共边负收益核算"),
    ),
    "facility": DomainCartridge(
        domain="facility",
        problem_classes=("facility_location", "hub_location", "qap"),
        default_tier="B",
        solver_modes=("facility_location", "cflp", "flp", "hub_location", "qap"),
        skill_topics=("or-numbers-truth", "or-problems.md"),
        contract_path="contracts/facility_collaboration_v1.json",
        modeling_checklist=("产能=需求分配", "单源二值", "运输成本 Haversine"),
    ),
    GENERAL_OR_DOMAIN: DomainCartridge(
        domain=GENERAL_OR_DOMAIN,
        problem_classes=(),
        default_tier="B",
        solver_modes=("sandbox", "custom_mip", "custom_cp"),
        skill_topics=("or-problems.md", "or-solver-select", "or-numbers-truth"),
        contract_path="",
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
    if raw in CARTRIDGES:  # direct domain key
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
    if raw in cartridge.tier_by_class:  # pre-normalisation key (e.g. clsp)
        return cartridge.tier_by_class[raw]  # type: ignore[return-value]
    return cartridge.default_tier


def cartridge_skills(problem_class_or_domain: str) -> tuple[str, ...]:
    return resolve_cartridge(problem_class_or_domain).skill_topics


cartridges = CLASS_TO_DOMAIN  # alias: class -> domain mapping


# --------------------------------------------------------------------------- #
# unified team assembly — thin-shim contract for orpath/agents/domains/*.py
# --------------------------------------------------------------------------- #

def _get_chat_model() -> Any:
    from orpath.control_plane import get_chat_model

    return get_chat_model()


def _resolve_symbol(sym: str, domain: str, tools_map: dict[str, Any]) -> Any:
    """Resolve one symbolic role-tool name to a real tool object."""
    from orpath.agents.tools_or import (
        execute_or_solver,
        execute_python_sandbox,
        list_available_solvers,
        validate_solution_tool,
    )
    from orpath.agents.workers import read_problem_file, search_or_knowledge

    static = {
        "read_problem_file": read_problem_file,
        "search_or_knowledge": search_or_knowledge,
        "execute_or_solver": execute_or_solver,
        "execute_python_sandbox": execute_python_sandbox,
        "validate_solution_tool": validate_solution_tool,
        "list_available_solvers": list_available_solvers,
    }
    if sym == "export_paper_markdown":
        from orpath.agents.workers import export_paper_markdown
        return export_paper_markdown
    if sym in static:
        return static[sym]
    return tools_map[sym]


def _build_role_tools(team: TeamSpec, tools_map: dict[str, Any]) -> dict[str, list[Any]]:
    resolved: dict[str, list[Any]] = {}
    for role in ("lead", *team.roles):
        template = team.role_tools_overrides.get(role)
        if template is None:
            template = ROLE_TOOLS.get(role) or ROLE_TOOLS["lead"]
        resolved[role] = [_resolve_symbol(s, team.domain, tools_map) for s in template]
    return resolved


def build_team_namespace(domain: str) -> Any:
    """Assemble every public symbol of ``orpath/agents/domains/<domain>.py``.

    Returns a namespace whose ``exports`` dict is injected verbatim into the
    thin shim module via ``globals().update(...)`` so the historical import
    surface (constants, prompts, tools, factories, state schema, graph
    builders) stays compatible while all machinery is shared.
    """
    from types import SimpleNamespace

    from langgraph.graph.state import CompiledStateGraph, StateGraph
    from langgraph.prebuilt import create_react_agent
    from langgraph_supervisor import create_supervisor

    from orpath.agents.contract_validator import (
        _json,
        _meta_resolve_ref,
        _meta_type_ok,
        _validate_against_meta_schema,
        DomainSpec,
        make_check_ledger_tool,
        make_collaboration_gate_tool,
        make_experiment_card_tool,
        make_redteam_gate_tool,
        make_script_gate_tool,
        make_validate_contract_tool,
        resolve_root,
    )
    from orpath.agents.domain_state import create_domain_state_schema
    from orpath.agents.guard_factory import create_domain_guard_hook
    from orpath.agents.supervisor import supervisor_trim_pre_model_hook

    team = TEAMS[domain]
    spec: DomainSpec = team.spec
    P = team.name_prefix
    lead_name = f"or_{team.lead_prefix}_lead"

    # --- bound protocol tools -------------------------------------------------
    tools_map: dict[str, Any] = {}
    tools_map["contract"] = make_validate_contract_tool(spec)
    tools_map["ledger"] = make_check_ledger_tool(spec)
    tools_map["collab"] = make_collaboration_gate_tool(spec)
    tools_map["redteam"] = make_redteam_gate_tool(spec)
    if team.domain == "tube":
        tools_map["card"] = make_experiment_card_tool(
            "tube", "contracts/tube_experiment_card.schema.json"
        )
        tools_map["geometry_gate"] = make_script_gate_tool(
            "tube",
            "run_tube_geometry_stability_gate",
            "scripts/tube_geometry_stability_gate.py",
            "Run the independent Tube geometry convergence gate comparing "
            "180/360/720 resolutions.",
            (
                ("snapshot_path", "outputs/b-tube-cut/model_snapshot.json", "--snapshot"),
                ("out_path", "outputs/tube-geometry-stability.json", "--out"),
            ),
        )
    ctools = cartridge_tools(domain)
    profile = ctools.get("profile_tool")
    inspect = ctools.get("inspect_tool")
    tools_map["profile"] = profile
    tools_map["inspect"] = inspect

    role_tools = _build_role_tools(team, tools_map)

    # --- names ----------------------------------------------------------------
    worker_names = tuple(
        f"or_{team.lead_prefix}_{ROLE_FACTORY_SUFFIX[r]}" for r in team.roles
    )
    worker_role = dict(zip(team.roles, worker_names))
    names = {"lead": lead_name, **worker_role}
    all_agent_names = (lead_name, *worker_names)
    stage_order = worker_names
    if team.domain == "tube":
        guard_ids = {n: f"guard_call_{n.replace('or_', '')}" for n in worker_names}
    else:
        guard_ids = {n: f"guard_call_{n}" for n in worker_names}

    # --- prompts --------------------------------------------------------------
    from orpath.agents.domain_prompts import DOMAIN_PROMPTS

    prompt_vars = {"lead": f"DEFAULT_{P}_LEAD_PROMPT"}
    for r in team.roles:
        prompt_vars[r] = f"{P}_{ROLE_TITLES[r]}_PROMPT"
    prompt_vars.update(team.prompt_vars)
    missing = [v for v in prompt_vars.values() if v not in DOMAIN_PROMPTS[domain]]
    if missing:
        raise KeyError(f"domain_prompts bank missing keys for {domain}: {missing}")
    prompt_texts = {r: DOMAIN_PROMPTS[domain][v] for r, v in prompt_vars.items()}

    # --- state schema ---------------------------------------------------------
    state_class = create_domain_state_schema(
        team.state_prefix, extra_fields=team.state_fields  # type: ignore[arg-type]
    )

    # --- agent factories -----------------------------------------------------
    def _factory(role: str):
        def create_role_agent(model: Any = None, extra_tools: list[Any] | None = None) -> Any:
            resolved_model = model if model is not None else _get_chat_model()
            return create_react_agent(
                model=resolved_model,
                tools=list(role_tools[role]) + list(extra_tools or []),
                prompt=prompt_texts[role],
                name=names[role],
            )

        return create_role_agent

    factories = {"lead": _factory("lead")}
    for r in team.roles:
        factories[r] = _factory(r)

    def get_workers(model: Any = None) -> list[Any]:
        resolved_model = model if model is not None else _get_chat_model()
        return [factories[r](model=resolved_model) for r in team.roles]

    guard_hook = create_domain_guard_hook(stage_order, guard_ids)

    def build_supervisor_graph(
        model: Any = None,
        workers: Any = None,
        prompt: str | None = None,
        state_schema: Any = None,
        enable_guard: bool = True,
        enable_trim: bool = False,
        pre_model_hook: Any = None,
        supervisor_name: str = lead_name,
    ) -> StateGraph:
        resolved_model = model if model is not None else _get_chat_model()
        resolved_workers = (
            workers if workers is not None else get_workers(model=resolved_model)
        )
        resolved_pre_hook = (
            pre_model_hook
            if pre_model_hook is not None
            else (supervisor_trim_pre_model_hook if enable_trim else None)
        )
        return create_supervisor(
            agents=resolved_workers,
            model=resolved_model,
            prompt=prompt or prompt_texts["lead"],
            state_schema=state_schema or state_class,
            pre_model_hook=resolved_pre_hook,
            post_model_hook=guard_hook if enable_guard else None,
            supervisor_name=supervisor_name,
        )

    def build_compiled_supervisor(
        checkpointer: Any = None,
        model: Any = None,
        workers: Any = None,
        prompt: str | None = None,
        state_schema: Any = None,
        enable_guard: bool = True,
        enable_trim: bool = False,
        pre_model_hook: Any = None,
        supervisor_name: str = lead_name,
    ) -> CompiledStateGraph:
        graph = build_supervisor_graph(
            model=model,
            workers=workers,
            prompt=prompt,
            state_schema=state_schema,
            enable_guard=enable_guard,
            enable_trim=enable_trim,
            pre_model_hook=pre_model_hook,
            supervisor_name=supervisor_name,
        )
        return graph.compile(checkpointer=checkpointer)

    # --- assemble export dict -------------------------------------------------
    exports: dict[str, Any] = {
        f"{P}_LEAD_NAME": lead_name,
        **{f"{P}_{ROLE_TITLES[r]}_NAME": names[r] for r in team.roles},
        f"{P}_WORKER_NAMES": worker_names,
        f"{P}_ALL_AGENT_NAMES": all_agent_names,
        f"{P}_PIPELINE_STAGE_ORDER": stage_order,
        f"{P}_GUARD_CALL_IDS": guard_ids,
        f"{P}_DISCRETIONARY_BUDGET": spec.budget,
        f"{P}_RISK_OVERRIDE_BUDGET": spec.risk_override_budget,
        f"{P}_OBJECTIVE_ORDER": spec.objective_order,
        f"{P}_CANDIDATE_LIFECYCLE": spec.candidate_lifecycle,
        **{v: prompt_texts[r] for r, v in prompt_vars.items()},
        f"check_{domain}_budget_ledger": tools_map["ledger"],
        f"run_{domain}_collaboration_gate": tools_map["collab"],
        f"run_{domain}_redteam_gate": tools_map["redteam"],
    }
    if "contract" in tools_map:
        exports[f"validate_{domain}_contract"] = tools_map["contract"]
    if team.domain == "tube":
        exports["validate_tube_experiment_card"] = tools_map["card"]
        exports["run_tube_geometry_stability_gate"] = tools_map["geometry_gate"]
        exports["TUBE_Q4_INTERNAL_BUDGET"] = dict(spec.sub_budget)
    if spec.tamper_tests:
        exports[f"{P}_TAMPER_TESTS"] = spec.tamper_tests
    exports[f"{team.state_prefix}SupervisorState"] = state_class
    exports[f"{domain}_guard_post_hook"] = guard_hook
    exports[f"get_{team.lead_prefix}_workers"] = get_workers
    exports[f"get_{domain}_workers"] = get_workers
    exports[f"build_{domain}_supervisor_graph"] = build_supervisor_graph
    exports[f"build_compiled_{domain}_supervisor"] = build_compiled_supervisor
    exports[f"create_{team.lead_prefix}_lead_agent"] = factories["lead"]
    exports[f"create_{domain}_lead_agent"] = factories["lead"]
    for r in team.roles:
        suffix = ROLE_FACTORY_SUFFIX[r]
        exports[f"create_{team.lead_prefix}_{suffix}_agent"] = factories[r]
        exports[f"create_{domain}_{suffix}_agent"] = factories[r]
    exports["_resolve_root"] = resolve_root
    exports["_json"] = _json
    exports["_meta_type_ok"] = _meta_type_ok
    exports["_meta_resolve_ref"] = _meta_resolve_ref
    exports["_validate_against_meta_schema"] = _validate_against_meta_schema
    if profile is not None:
        p_name = getattr(profile, "__name__", getattr(profile, "name", str(profile)))
        exports[p_name] = profile
    if inspect is not None:
        i_name = getattr(inspect, "__name__", getattr(inspect, "name", str(inspect)))
        exports[i_name] = inspect
    exports["StateGraph"] = StateGraph
    exports["CompiledStateGraph"] = CompiledStateGraph
    exports["__all__"] = sorted(k for k in exports if not k.startswith("__"))
    return SimpleNamespace(domain=domain, team=team, exports=exports)
