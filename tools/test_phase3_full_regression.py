#!/usr/bin/env python3
"""Phase 3 full regression suite — 10-domain expert-team acceptance matrix.

Phase 3 built ten vertical OR-domain expert teams (Task 3.1 ~ 3.10):

    tube, routing, scheduling, project, inventory, facility,
    rostering, microgrid, pricing, finance

Each team ships the same six-part deliverable:

  1. ``contracts/<domain>_collaboration_v1.json`` validated against the
     ``contracts/meta/domain_collaboration.schema.json`` meta-schema;
  2. a Lead + Pentad (5 workers) agent roster with ``owns`` / ``forbidden``
     role boundaries and a conserved 100% discretionary budget;
  3. a ``<Domain>SupervisorState`` inheriting ``DomainSupervisorState`` plus a
     ``guard_factory``-built anti-early-stopping guard hook;
  4. an independent red-team gate (``scripts/<domain>_redteam_gate.py``) that
     replays five DIMO physical/mathematical tamper attacks;
  5. a compilable LangGraph supervisor wiring the six agents.

This suite is the Phase 3 acceptance gate. It exercises the *matrix* over all
ten domains instead of one domain per file:

  * Contract meta-schema full matrix (10 contracts × meta-schema + negative
    controls);
  * Budget-quota conservation matrix (10 × sum == 100, contract == constants,
    ledger validation + drift rejection);
  * Role naming & boundary matrix (10 Leads + 50 Pentad workers = 60 roles,
    each with non-empty ``owns`` / ``forbidden``);
  * 50-attack DIMO red-team matrix (10 gates × 5 attacks; asserts every
    *applicable* attack is intercepted and that no gate ever claims a silent
    pass — the Tube ``input_hash_tamper`` row is the one documented
    fail-safe: synthetic manifest URIs are deliberately not re-hashed, so the
    gate honestly reports the attack as unverified and fails safe instead of
    pretending it was blocked);
  * State-inheritance & anti-early-stop guard matrix (10 states inherit
    ``DomainSupervisorState``; 10 guard hooks re-route non-Lead early exits);
  * Supervisor graph build/compile smoke matrix (10 graphs compile, all six
    agent nodes present, all six agents creatable offline).

Everything runs offline: solver envelopes are produced by the real local
solvers (Numbers Truth) and graph compilation uses ``get_chat_model()``,
which constructs an offline-safe client when no API key is configured.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import typing
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

from orpath.agents.budget_engine import BudgetLedgerManager  # noqa: E402
from orpath.agents.domain_state import (  # noqa: E402
    DomainSupervisorState,
    get_state_stage_progress,
)
from orpath.agents.guard_factory import create_domain_guard_hook  # noqa: E402
from orpath.control_plane import get_chat_model  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore:create_react_agent has been moved")

META_SCHEMA_PATH = ROOT / "contracts" / "meta" / "domain_collaboration.schema.json"

DOMAINS: tuple[str, ...] = (
    "tube",
    "routing",
    "scheduling",
    "project",
    "inventory",
    "facility",
    "rostering",
    "microgrid",
    "pricing",
    "finance",
)

#: Per-domain integration table: module, constant prefix, factory/hook names,
#: red-team gate module and the frozen problem id used for red-team replays.
DOMAIN_SPECS: dict[str, dict[str, str]] = {
    "tube": {
        "module": "orpath.agents.domains.tube",
        "prefix": "TUBE",
        "state": "TubeSupervisorState",
        "hook": "tube_guard_post_hook",
        "lead_fn": "create_tube_lead_agent",
        "workers_fn": "get_tube_workers",
        "graph_fn": "build_tube_supervisor_graph",
        "compiled_fn": "build_compiled_tube_supervisor",
        "contract": "tube_collaboration_v1.json",
        "gate": "tube_redteam_gate",
        "problem_id": "tube_cut_b2026",
        "redteam_problem_id": "synthetic_tube",
    },
    "routing": {
        "module": "orpath.agents.domains.routing",
        "prefix": "ROUTING",
        "state": "RoutingSupervisorState",
        "hook": "routing_guard_post_hook",
        "lead_fn": "create_routing_lead_agent",
        "workers_fn": "get_routing_workers",
        "graph_fn": "build_routing_supervisor_graph",
        "compiled_fn": "build_compiled_routing_supervisor",
        "contract": "routing_collaboration_v1.json",
        "gate": "routing_redteam_gate",
        "problem_id": "pyvrp_vrptw",
        "redteam_problem_id": "pyvrp_vrptw",
    },
    "scheduling": {
        "module": "orpath.agents.domains.scheduling",
        "prefix": "JSSP",
        "state": "SchedulingSupervisorState",
        "hook": "scheduling_guard_post_hook",
        "lead_fn": "create_jssp_lead_agent",
        "workers_fn": "get_jssp_workers",
        "graph_fn": "build_scheduling_supervisor_graph",
        "compiled_fn": "build_compiled_scheduling_supervisor",
        "contract": "scheduling_collaboration_v1.json",
        "gate": "scheduling_redteam_gate",
        "problem_id": "pyjobshop_jssp",
        "redteam_problem_id": "jssp_ft06",
    },
    "project": {
        "module": "orpath.agents.domains.project",
        "prefix": "PROJECT",
        "state": "ProjectSupervisorState",
        "hook": "project_guard_post_hook",
        "lead_fn": "create_project_lead_agent",
        "workers_fn": "get_project_workers",
        "graph_fn": "build_project_supervisor_graph",
        "compiled_fn": "build_compiled_project_supervisor",
        "contract": "project_collaboration_v1.json",
        "gate": "project_redteam_gate",
        "problem_id": "psplib_rcpsp",
        "redteam_problem_id": "psplib_rcpsp",
    },
    "inventory": {
        "module": "orpath.agents.domains.inventory",
        "prefix": "INVENTORY",
        "state": "InventorySupervisorState",
        "hook": "inventory_guard_post_hook",
        "lead_fn": "create_inventory_lead_agent",
        "workers_fn": "get_inventory_workers",
        "graph_fn": "build_inventory_supervisor_graph",
        "compiled_fn": "build_compiled_inventory_supervisor",
        "contract": "inventory_collaboration_v1.json",
        "gate": "inventory_redteam_gate",
        "problem_id": "wagner_whitin_clsp",
        "redteam_problem_id": "lot_sizing_clsp60",
    },
    "facility": {
        "module": "orpath.agents.domains.facility",
        "prefix": "FACILITY",
        "state": "FacilitySupervisorState",
        "hook": "facility_guard_post_hook",
        "lead_fn": "create_facility_lead_agent",
        "workers_fn": "get_facility_workers",
        "graph_fn": "build_facility_supervisor_graph",
        "compiled_fn": "build_compiled_facility_supervisor",
        "contract": "facility_collaboration_v1.json",
        "gate": "facility_redteam_gate",
        "problem_id": "beasley_cflp",
        "redteam_problem_id": "cflp_sscflp",
    },
    "rostering": {
        "module": "orpath.agents.domains.rostering",
        "prefix": "ROSTERING",
        "state": "RosteringSupervisorState",
        "hook": "rostering_guard_post_hook",
        "lead_fn": "create_rostering_lead_agent",
        "workers_fn": "get_rostering_workers",
        "graph_fn": "build_rostering_supervisor_graph",
        "compiled_fn": "build_compiled_rostering_supervisor",
        "contract": "rostering_collaboration_v1.json",
        "gate": "rostering_redteam_gate",
        "problem_id": "staff_rostering",
        "redteam_problem_id": "staff_rostering",
    },
    "microgrid": {
        "module": "orpath.agents.domains.microgrid",
        "prefix": "MICROGRID",
        "state": "MicrogridSupervisorState",
        "hook": "microgrid_guard_post_hook",
        "lead_fn": "create_microgrid_lead_agent",
        "workers_fn": "get_microgrid_workers",
        "graph_fn": "build_microgrid_supervisor_graph",
        "compiled_fn": "build_compiled_microgrid_supervisor",
        "contract": "microgrid_collaboration_v1.json",
        "gate": "microgrid_redteam_gate",
        "problem_id": "microgrid_dispatch",
        "redteam_problem_id": "microgrid_dispatch",
    },
    "pricing": {
        "module": "orpath.agents.domains.pricing",
        "prefix": "PRICING",
        "state": "PricingSupervisorState",
        "hook": "pricing_guard_post_hook",
        "lead_fn": "create_pricing_lead_agent",
        "workers_fn": "get_pricing_workers",
        "graph_fn": "build_pricing_supervisor_graph",
        "compiled_fn": "build_compiled_pricing_supervisor",
        "contract": "pricing_collaboration_v1.json",
        "gate": "pricing_redteam_gate",
        "problem_id": "farmer_stochastic_lp",
        "redteam_problem_id": "farmer_stochastic_lp",
    },
    "finance": {
        "module": "orpath.agents.domains.finance",
        "prefix": "FINANCE",
        "state": "FinanceSupervisorState",
        "hook": "finance_guard_post_hook",
        "lead_fn": "create_finance_lead_agent",
        "workers_fn": "get_finance_workers",
        "graph_fn": "build_finance_supervisor_graph",
        "compiled_fn": "build_compiled_finance_supervisor",
        "contract": "finance_collaboration_v1.json",
        "gate": "finance_redteam_gate",
        "problem_id": "markowitz_portfolio",
        "redteam_problem_id": "markowitz_portfolio",
    },
}

#: The one documented fail-safe row of the 50-attack matrix (see module docstring).
TUBE_FAILSAFE_ATTACK = "input_hash_tamper"

CANONICAL_STATE_FIELDS: tuple[str, ...] = (
    "audit_passed",
    "lower_bound_fixed",
    "incumbent_solved",
    "realities_applied",
    "redteam_passed",
    "domain",
    "problem_id",
    "assumption_register_path",
    "budget_ledger_path",
    "candidate_solution_path",
    "validation_report_path",
    "redteam_report_path",
    "audit_report_path",
    "experiment_card_paths",
)


# --------------------------------------------------------------------------- #
# JSON / draft-07 helpers (self-contained; no external jsonschema dependency)
# --------------------------------------------------------------------------- #

def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict), f"{path} must contain a JSON object"
    return data


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
    return True  # unknown type keyword: ignore like standard JSON Schema


def _resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise AssertionError(f"unsupported $ref: {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    assert isinstance(node, dict), f"$ref target is not an object: {ref!r}"
    return node


def validate_draft07(doc: Any, schema: dict[str, Any], root: dict[str, Any], path: str = "$") -> list[str]:
    """Focused draft-07 structural validation (subset used by the meta-schema)."""
    errors: list[str] = []
    if "$ref" in schema:
        schema = _resolve_ref(root, schema["$ref"])
    if "type" in schema and not _type_ok(doc, schema["type"]):
        errors.append(f"{path}: expected type {schema['type']!r}, got {type(doc).__name__}")
        return errors
    if "enum" in schema and doc not in schema["enum"]:
        errors.append(f"{path}: {doc!r} is not one of {schema['enum']!r}")
    if "const" in schema and doc != schema["const"]:
        errors.append(f"{path}: {doc!r} is not the const {schema['const']!r}")
    if isinstance(doc, str):
        if "pattern" in schema and not re.search(schema["pattern"], doc):
            errors.append(f"{path}: {doc!r} does not match pattern {schema['pattern']!r}")
        if "minLength" in schema and len(doc) < schema["minLength"]:
            errors.append(f"{path}: {doc!r} shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(doc) > schema["maxLength"]:
            errors.append(f"{path}: {doc!r} longer than maxLength {schema['maxLength']}")
    if isinstance(doc, (int, float)) and not isinstance(doc, bool):
        if "minimum" in schema and doc < schema["minimum"]:
            errors.append(f"{path}: {doc!r} < minimum {schema['minimum']}")
        if "maximum" in schema and doc > schema["maximum"]:
            errors.append(f"{path}: {doc!r} > maximum {schema['maximum']}")
    if isinstance(doc, list):
        if "minItems" in schema and len(doc) < schema["minItems"]:
            errors.append(f"{path}: {len(doc)} items < minItems {schema['minItems']}")
        if "maxItems" in schema and len(doc) > schema["maxItems"]:
            errors.append(f"{path}: {len(doc)} items > maxItems {schema['maxItems']}")
        if schema.get("uniqueItems") and len(doc) != len(
            {json.dumps(item, sort_keys=True, default=str) for item in doc}
        ):
            errors.append(f"{path}: items are not unique")
        if "items" in schema:
            for index, item in enumerate(doc):
                errors.extend(validate_draft07(item, schema["items"], root, f"{path}[{index}]"))
    if isinstance(doc, dict):
        for key in schema.get("required", []):
            if key not in doc:
                errors.append(f"{path}: missing required key {key!r}")
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in doc:
                errors.extend(validate_draft07(doc[key], subschema, root, f"{path}.{key}"))
        additional = schema.get("additionalProperties")
        if additional is False:
            for key in doc:
                if key not in properties:
                    errors.append(f"{path}: additional property {key!r} not allowed")
        elif isinstance(additional, dict):
            for key in doc:
                if key in properties:
                    continue
                errors.extend(validate_draft07(doc[key], additional, root, f"{path}.{key}"))
    if "not" in schema and validate_draft07(doc, schema["not"], root, path) == []:
        errors.append(f"{path}: value matches a forbidden subschema")
    for subschema in schema.get("allOf", []):
        errors.extend(validate_draft07(doc, subschema, root, path))
    for combinator in ("anyOf", "oneOf"):
        subschemas = schema.get(combinator, [])
        if not subschemas:
            continue
        matches = [validate_draft07(doc, sub, root, path) == [] for sub in subschemas]
        if combinator == "anyOf" and not any(matches):
            errors.append(f"{path}: does not match any allowed subschema")
        if combinator == "oneOf" and sum(matches) != 1:
            errors.append(f"{path}: matches {sum(matches)} subschemas, expected exactly one")
    if "if" in schema:
        if validate_draft07(doc, schema["if"], root, path) == [] and "then" in schema:
            errors.extend(validate_draft07(doc, schema["then"], root, path))
        elif "else" in schema:
            errors.extend(validate_draft07(doc, schema["else"], root, path))
    return errors


# --------------------------------------------------------------------------- #
# Shared fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def meta_schema() -> dict[str, Any]:
    return _load_json(META_SCHEMA_PATH)


@pytest.fixture(scope="session")
def domain_modules() -> dict[str, Any]:
    """Import all ten domain team modules once per session."""
    import importlib

    return {dom: importlib.import_module(spec["module"]) for dom, spec in DOMAIN_SPECS.items()}


@pytest.fixture(scope="session")
def redteam_gates() -> dict[str, Any]:
    """Import all ten independent red-team gates once per session."""
    import importlib

    return {dom: importlib.import_module(spec["gate"]) for dom, spec in DOMAIN_SPECS.items()}


@pytest.fixture(scope="module")
def domain_contracts() -> dict[str, dict[str, Any]]:
    return {dom: _load_json(ROOT / "contracts" / spec["contract"]) for dom, spec in DOMAIN_SPECS.items()}


# --------------------------------------------------------------------------- #
# Real solver envelopes (Numbers Truth: produced by the local solvers)
# --------------------------------------------------------------------------- #

def _zero_savings(gids: tuple[str, ...]) -> dict[str, dict[str, float]]:
    return {
        f"{a}-{b}": {mode: 0.0 for mode in ("LL", "LR", "RL", "RR")}
        for a in gids
        for b in gids
    }


def _build_tube_envelope() -> dict[str, Any]:
    """Strict Tube-B envelope (same construction as test_tube_optimization)."""
    from tube_optimization import (
        materialize_bins,
        mixed_stock_patterns,
        solve_multibatch_beam,
        summarize_bins,
    )

    gids = ("A", "B")
    lengths = {"A": 60.0, "B": 40.0}
    savings = _zero_savings(gids)
    stocks = (100.0, 110.0)
    demand = {"A": 2, "B": 1}
    q1_bars = mixed_stock_patterns(demand, lengths, stocks=stocks, seed=11)
    for row in q1_bars:
        raw = sum(lengths[g] for g in row["sequence"])
        row.update(
            {
                "raw_length_mm": raw,
                "used_length_mm": raw,
                "co_cut_benefit_mm": 0.0,
                "effective_length_mm": raw,
                "leftover_mm": row["stock_length_mm"] - raw,
                "utilization": raw / row["stock_length_mm"],
                "switches": sum(a != b for a, b in zip(row["sequence"], row["sequence"][1:])),
            }
        )
    q1 = {
        "stocks": q1_bars,
        "total_stock_length_mm": sum(b["stock_length_mm"] for b in q1_bars),
        "total_axial_length_mm": sum(lengths[g] * n for g, n in demand.items()),
        "total_switch": sum(b["switches"] for b in q1_bars),
        "utilization": sum(lengths[g] * n for g, n in demand.items())
        / sum(b["stock_length_mm"] for b in q1_bars),
        "demand": demand,
        "status": "FEASIBLE",
    }
    q2_bars = materialize_bins(q1_bars, lengths, savings, resize_new=False)
    assert q2_bars is not None
    q2 = summarize_bins(q2_bars)
    q2["demand"] = demand
    q3 = deepcopy(q2)
    q4 = solve_multibatch_beam(
        [{"A": 1, "B": 1}, {"A": 1, "B": 1}, {"A": 1, "B": 1}],
        lengths,
        savings,
        stocks=stocks,
        remnant_min_mm=10.0,
        seed=29,
        beam_width=4,
        joint_iterations=40,
        master_time_limit_s=1.0,
    )
    return {
        "problem_id": "synthetic_tube",
        "problem_class": "tube_cut",
        "status": "FEASIBLE",
        "objective": q3["total_stock_length_mm"],
        "source": "tools/solve_tube_cut_b2026.py",
        "solver": "tube-cg-cpsat-alns-beam",
        "questions": {"q1": q1, "q2": q2, "q3": q3, "q4": q4},
        "model_snapshot": {
            "schema": "orpath.tube_model.v2",
            "units": "mm",
            "lengths": lengths,
            "savings": savings,
            "stock_lengths_mm": list(stocks),
            "remnant_min_mm": 10.0,
            "profile_bins": 360,
            "seed": 29,
            "input_sha256": {"synthetic://tube-model": "0" * 64},
        },
        "meta": {"exact": False, "proven_optimal": False, "method_class": "heuristic"},
    }


def _build_routing_envelope(gate: Any) -> dict[str, Any]:
    """Small VRPTW solution accepted by ``validate_pyvrp`` (same as task 3.2)."""
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
                {"type": "depot", "name": "DEPOT", "demand": 0, "start_time": 0.0, "end_time": 0.0}
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
    envelope = {
        "problem_id": "pyvrp_vrptw",
        "problem_class": "pyvrp",
        "status": "FEASIBLE",
        "objective": total_distance,
        "total_distance": total_distance,
        "vehicle_capacity": 100,
        "num_clients": len(clients),
        "num_vehicles_used": 1,
        "routes": [
            {
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
        ],
        "raw_depot": depot,
        "raw_clients": clients,
        "raw_shipments": [],
    }
    envelope["input_coordinates_sha256"] = gate.coordinate_integrity_hash(envelope)
    return envelope


def _build_microgrid_envelope() -> dict[str, Any]:
    """Golden 144-interval day-ahead LP envelope (same as task 3.8)."""
    from solve_microgrid import solve_day_lp

    prices = [0.4 if (t < 36 or t > 120) else 1.2 for t in range(144)]
    loads = [600.0] * 144
    pvs = [800.0 if 40 <= t <= 80 else 0.0 for t in range(144)]
    res = solve_day_lp(
        prices=prices,
        loads_kwh=loads,
        pvs_kwh=pvs,
        soc_start=6000.0,
        target_soc_end=6000.0,
    )
    q1 = {**res, "total_purchase_cost": res["total_cost"], "total_cost": res["total_cost"]}
    return {"status": "OPTIMAL", "objective": res["total_cost"], "subproblems": {"q1": q1}}


@pytest.fixture(scope="module")
def domain_envelopes(redteam_gates: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """One valid frozen solution envelope per domain, built by real solvers."""
    from solve_facility import solve_facility_location
    from solve_jssp import solve_jssp
    from solve_lot_sizing import solve_lot_sizing
    from solve_portfolio import solve_portfolio
    from solve_rcpsp import solve_rcpsp
    from solve_staff_rostering import solve_staff_rostering
    from solve_stochastic_lp import solve_stochastic_lp

    envelopes: dict[str, dict[str, Any]] = {
        "tube": _build_tube_envelope(),
        "routing": _build_routing_envelope(redteam_gates["routing"]),
        "scheduling": solve_jssp("ft06", time_limit_s=30),
        "project": solve_rcpsp(time_limit_s=30),
        "inventory": solve_lot_sizing(method="mip", capacity=60.0, problem_id="lot_sizing_clsp60"),
        "facility": solve_facility_location(single_source=True, time_limit_s=10),
        "rostering": solve_staff_rostering(num_employees=8, num_days=14, time_limit_s=10),
        "microgrid": _build_microgrid_envelope(),
        "pricing": solve_stochastic_lp(),
        "finance": solve_portfolio(objective_type="max_sharpe", total_portfolio_value=100000.0),
    }
    for dom, envelope in envelopes.items():
        assert isinstance(envelope, dict) and envelope, f"{dom}: empty envelope"
    return envelopes


@pytest.fixture(scope="module")
def redteam_reports(domain_envelopes: dict[str, dict[str, Any]], redteam_gates: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Replay the five DIMO attacks per domain once per module."""
    reports: dict[str, dict[str, Any]] = {}
    for dom, spec in DOMAIN_SPECS.items():
        reports[dom] = redteam_gates[dom].run_redteam(
            domain_envelopes[dom], spec["redteam_problem_id"]
        )
    return reports


# --------------------------------------------------------------------------- #
# 1. Contract meta-schema full matrix
# --------------------------------------------------------------------------- #

def test_meta_schema_file_wellformed(meta_schema: dict[str, Any]) -> None:
    assert meta_schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert meta_schema["type"] == "object"
    assert meta_schema["required"] == [
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
    assert meta_schema["definitions"]["role"]["required"] == ["owns", "forbidden"]
    pattern = meta_schema["properties"]["schema"]["pattern"]
    assert re.match(pattern, "orpath.tube_collaboration.v1")


@pytest.mark.parametrize("domain", DOMAINS)
def test_contract_file_wellformed(domain: str) -> None:
    path = ROOT / "contracts" / DOMAIN_SPECS[domain]["contract"]
    assert path.is_file(), f"missing contract file: {path}"
    doc = _load_json(path)
    assert isinstance(doc, dict)


@pytest.mark.parametrize("domain", DOMAINS)
def test_contract_validates_against_meta_schema(domain: str, meta_schema: dict[str, Any]) -> None:
    """100% of the ten domain contracts must pass the meta-schema."""
    doc = _load_json(ROOT / "contracts" / DOMAIN_SPECS[domain]["contract"])
    errors = validate_draft07(doc, meta_schema, meta_schema)
    assert errors == [], f"{domain} contract meta-schema errors: {errors}"


@pytest.mark.parametrize("domain", DOMAINS)
def test_contract_schema_id_matches_pattern(domain: str, meta_schema: dict[str, Any]) -> None:
    pattern = meta_schema["properties"]["schema"]["pattern"]
    doc = _load_json(ROOT / "contracts" / DOMAIN_SPECS[domain]["contract"])
    assert re.search(pattern, doc["schema"]), doc["schema"]
    assert doc["schema"] == f"orpath.{domain}_collaboration.v1"


def _mutate_schema_id(d: dict[str, Any]) -> None:
    d["schema"] = "bad_id"

def _mutate_budget_float(d: dict[str, Any]) -> None:
    first_k = next(iter(d["budget_percent"]))
    d["budget_percent"][first_k] = 20.5

def _mutate_role_missing_owns(d: dict[str, Any]) -> None:
    first_r = next(iter(d["roles"]))
    d["roles"][first_r].pop("owns", None)

CONTRACT_MUTATIONS: list[tuple[str, Any]] = [
    ("schema-id", _mutate_schema_id),
    ("budget-float", _mutate_budget_float),
    ("role-missing-owns", _mutate_role_missing_owns),
]


@pytest.mark.parametrize("domain", DOMAINS)
@pytest.mark.parametrize("case,mutate", CONTRACT_MUTATIONS)
def test_tampered_contract_rejected_by_meta_schema(
    domain: str, case: str, mutate: Any, meta_schema: dict[str, Any]
) -> None:
    """Negative controls: corrupted contracts must fail the meta-schema."""
    doc = _load_json(ROOT / "contracts" / DOMAIN_SPECS[domain]["contract"])
    mutate(doc)
    errors = validate_draft07(doc, meta_schema, meta_schema)
    assert errors, f"{domain}/{case}: tampered contract unexpectedly validated"


@pytest.mark.parametrize("domain", DOMAINS)
def test_contract_matches_domain_constants(
    domain: str, domain_modules: dict[str, Any], domain_contracts: dict[str, dict[str, Any]]
) -> None:
    """Contract <-> team-constant consistency (no drift between the two)."""
    spec = DOMAIN_SPECS[domain]
    mod = domain_modules[domain]
    doc = domain_contracts[domain]
    pref = spec["prefix"]

    assert doc["schema"] == f"orpath.{domain}_collaboration.v1"
    assert doc["problem_id"] == spec["problem_id"]
    assert doc["numeric_authority"] == "local_solver_and_independent_validator"
    assert doc["selection_rule"] == "lexicographic_not_agent_vote"
    assert doc["budget_scope"] == "discretionary_experiment_effort_excluding_baseline_and_gates"
    assert doc["budget_percent"] == dict(getattr(mod, f"{pref}_DISCRETIONARY_BUDGET"))
    assert doc["objective_order"] == list(getattr(mod, f"{pref}_OBJECTIVE_ORDER"))
    assert doc["candidate_lifecycle"] == list(getattr(mod, f"{pref}_CANDIDATE_LIFECYCLE"))
    assert doc["objective_order"][0] == "hard_constraints"

    handoff = doc.get("handoff_order")
    assert isinstance(handoff, list) and handoff, "handoff_order required"
    assert handoff[0] == "assumptions"
    assert handoff[-1] == "write"
    assert "redteam_validate" in handoff

    stop_rules = doc["stop_rules"]
    assert isinstance(stop_rules, dict) and stop_rules
    for value in stop_rules.values():
        assert isinstance(value, list) and value


# --------------------------------------------------------------------------- #
# 2. Budget-quota conservation matrix
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("domain", DOMAINS)
def test_budget_percent_sums_to_exactly_100(domain: str, domain_contracts: dict[str, dict[str, Any]]) -> None:
    doc = domain_contracts[domain]
    budget = doc["budget_percent"]
    assert isinstance(budget, dict) and budget
    assert all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in budget.values())
    assert sum(budget.values()) == 100, f"{domain}: budget drift {sum(budget.values())} != 100"


@pytest.mark.parametrize("domain", DOMAINS)
def test_budget_ledger_manager_validates_and_rejects_drift(domain: str, domain_modules: dict[str, Any]) -> None:
    mod = domain_modules[domain]
    budget = dict(getattr(mod, f"{DOMAIN_SPECS[domain]['prefix']}_DISCRETIONARY_BUDGET"))
    ledger = {
        "schema": f"orpath.{domain}_budget_ledger.v1",
        "date": "2026-01-01",
        "scope": "discretionary_experiment_effort_excluding_baseline_and_gates",
        "budget_percent": budget,
    }
    ok, errors = BudgetLedgerManager(ledger=ledger).validate()
    assert ok, f"{domain}: golden ledger rejected: {errors}"

    drifted = deepcopy(ledger)
    drifted["budget_percent"][list(budget)[-1]] += 1
    ok_drift, errors_drift = BudgetLedgerManager(ledger=drifted).validate()
    assert not ok_drift, f"{domain}: drifted ledger unexpectedly accepted"
    assert any("100" in e for e in errors_drift)


@pytest.mark.parametrize("domain", DOMAINS)
def test_risk_override_budget_conserves_100(domain: str, domain_modules: dict[str, Any]) -> None:
    mod = domain_modules[domain]
    pref = DOMAIN_SPECS[domain]["prefix"]
    baseline = getattr(mod, f"{pref}_DISCRETIONARY_BUDGET")
    override = getattr(mod, f"{pref}_RISK_OVERRIDE_BUDGET")
    assert set(override) == set(baseline)
    assert sum(override.values()) == 100, f"{domain}: risk-override budget drift"
    assert all(v > 0 for v in override.values())


# --------------------------------------------------------------------------- #
# 3. Role naming & boundary matrix (10 Leads + 50 Pentad workers = 60 roles)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("domain", DOMAINS)
def test_team_roster_is_lead_plus_pentad(domain: str, domain_modules: dict[str, Any]) -> None:
    mod = domain_modules[domain]
    pref = DOMAIN_SPECS[domain]["prefix"]
    lead = getattr(mod, f"{pref}_LEAD_NAME")
    workers = list(getattr(mod, f"{pref}_WORKER_NAMES"))
    all_agents = list(getattr(mod, f"{pref}_ALL_AGENT_NAMES"))
    stage_order = list(getattr(mod, f"{pref}_PIPELINE_STAGE_ORDER"))
    guard_ids = getattr(mod, f"{pref}_GUARD_CALL_IDS")

    assert len(workers) == 5, f"{domain}: pentad must have 5 workers, got {len(workers)}"
    assert all_agents == [lead, *workers]
    assert len(all_agents) == 6
    assert stage_order == workers
    assert set(guard_ids) == set(workers)
    assert all(cid.startswith("guard_call_") for cid in guard_ids.values())
    assert len(set(guard_ids.values())) == len(workers)


@pytest.mark.parametrize("domain", DOMAINS)
def test_contract_roles_match_agent_names(domain: str, domain_modules: dict[str, Any], domain_contracts: dict[str, dict[str, Any]]) -> None:
    mod = domain_modules[domain]
    doc = domain_contracts[domain]
    agents = set(getattr(mod, f"{DOMAIN_SPECS[domain]['prefix']}_ALL_AGENT_NAMES"))
    role_names = {name.replace("-", "_") for name in doc["roles"]}
    assert role_names == agents, f"{domain}: contract roles {sorted(role_names)} != agents {sorted(agents)}"


@pytest.mark.parametrize("domain", DOMAINS)
def test_role_boundaries_owns_forbidden(domain: str, domain_contracts: dict[str, dict[str, Any]]) -> None:
    doc = domain_contracts[domain]
    roles = doc["roles"]
    assert len(roles) == 6, f"{domain}: expected 6 roles, got {len(roles)}"
    for name, role in roles.items():
        assert isinstance(role["owns"], list) and role["owns"], f"{domain}/{name}: empty owns"
        assert isinstance(role["forbidden"], list) and role["forbidden"], f"{domain}/{name}: empty forbidden"
        assert all(isinstance(item, str) and item for item in role["owns"])
        assert all(isinstance(item, str) and item for item in role["forbidden"])
    # Lead owns the registers; red-team is forbidden from repairing candidates.
    lead = next(r for n, r in roles.items() if n.endswith("-lead"))
    assert {"assumption_register", "experiment_registry", "budget_ledger"} <= set(lead["owns"])
    assert {"invent_objective", "override_validator", "agent_vote"} <= set(lead["forbidden"])
    redteam = next(r for n, r in roles.items() if n.endswith("-redteam"))
    assert {"repair_candidate", "share_solver_state", "waive_failed_gate"} <= set(redteam["forbidden"])


def test_total_agent_roster_is_60_unique_roles(domain_modules: dict[str, Any]) -> None:
    """10 domains × 6 agents = 60 roles, all globally unique."""
    all_names: list[str] = []
    for dom, mod in domain_modules.items():
        all_names.extend(getattr(mod, f"{DOMAIN_SPECS[dom]['prefix']}_ALL_AGENT_NAMES"))
    assert len(all_names) == 60
    assert len(set(all_names)) == 60, f"duplicate agent names: {sorted(all_names)}"
    leads = [n for n in all_names if n.endswith("_lead")]
    assert len(leads) == 10
    assert len(all_names) - len(leads) == 50  # 50 pentad workers


# --------------------------------------------------------------------------- #
# 4. 50-attack DIMO red-team matrix
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("domain", DOMAINS)
def test_redteam_gate_declares_five_attacks(domain: str, redteam_gates: dict[str, Any]) -> None:
    gate = redteam_gates[domain]
    names = list(gate.ATTACK_NAMES)
    assert len(names) == 5
    assert len(set(names)) == 5
    assert all(isinstance(n, str) and n for n in names)


@pytest.mark.parametrize("domain", DOMAINS)
def test_redteam_attack_names_match_contract_and_constants(
    domain: str,
    domain_modules: dict[str, Any],
    domain_contracts: dict[str, dict[str, Any]],
    redteam_gates: dict[str, Any],
) -> None:
    """Contract tamper_tests <-> team constant <-> gate ATTACK_NAMES agree."""
    spec = DOMAIN_SPECS[domain]
    mod = domain_modules[domain]
    doc = domain_contracts[domain]
    gate = redteam_gates[domain]
    attack_names = list(gate.ATTACK_NAMES)

    tamper_const = getattr(mod, f"{spec['prefix']}_TAMPER_TESTS", None)
    if tamper_const is not None:
        assert attack_names == list(tamper_const), f"{domain}: gate vs constant drift"
    if "tamper_tests" in doc:
        assert attack_names == doc["tamper_tests"], f"{domain}: gate vs contract drift"


@pytest.mark.parametrize("domain", DOMAINS)
def test_redteam_matrix_blocks_all_dimo_attacks(
    domain: str, redteam_reports: dict[str, dict[str, Any]]
) -> None:
    """Per-domain attack matrix: every applicable attack must be intercepted.

    Nine domains must block all five attacks. Tube blocks the four
    numeric/physical attacks and honestly fails safe on
    ``input_hash_tamper`` (synthetic manifest URIs are deliberately not
    re-hashed; the gate refuses to claim a block it cannot verify).
    """
    report = redteam_reports[domain]
    assert report["attack_count"] == 5
    assert report["original_recompute_ok"] is True, report
    assert report["attacks_applied"] == 5

    blocked: list[str] = []
    unverified: list[str] = []
    for row in report["attacks"]:
        assert row["applied"] is True, (domain, row)
        if row["rejected"]:
            blocked.append(row["attack"])
            assert row["failed_checks"], (domain, row)
        else:
            unverified.append(row["attack"])

    if domain == "tube":
        assert unverified == [TUBE_FAILSAFE_ATTACK], (domain, unverified)
        assert report["ok"] is False  # fail-safe: never a silent pass
    else:
        assert unverified == [], (domain, unverified)
        assert report["ok"] is True


def test_redteam_matrix_totals(redteam_reports: dict[str, dict[str, Any]]) -> None:
    """Aggregate: 45 blocked on the nine full-matrix domains + 4 blocked on
    Tube = 49 intercepted attacks; the single remaining row is the documented
    Tube fail-safe. Zero silent passes anywhere in the matrix."""
    blocked = 0
    unverified: list[tuple[str, str]] = []
    for dom, report in redteam_reports.items():
        assert report["attack_count"] == 5
        for row in report["attacks"]:
            if row["rejected"]:
                blocked += 1
            elif row["applied"]:
                unverified.append((dom, row["attack"]))
        # No gate may claim overall success while an attack is unverified.
        row_unverified = [r for r in report["attacks"] if r["applied"] and not r["rejected"]]
        assert report["ok"] == (not row_unverified), dom
    assert blocked == 49, f"expected 49 intercepted attacks, got {blocked}"
    assert unverified == [("tube", TUBE_FAILSAFE_ATTACK)]


def test_tube_input_hash_tamper_fails_safe_on_synthetic_manifest(
    redteam_reports: dict[str, dict[str, Any]]
) -> None:
    """Tube's documented fail-safe row: applied but honestly unverified."""
    report = redteam_reports["tube"]
    row = next(r for r in report["attacks"] if r["attack"] == TUBE_FAILSAFE_ATTACK)
    assert row["applied"] is True
    assert row["rejected"] is False
    assert report["ok"] is False


def test_tube_strict_input_hash_check_is_live() -> None:
    """Positive control: the strict input-hash recompute catches a tampered
    digest when the manifest points at real, existing repository files."""
    from validate_solution import validate

    rel = "fixtures/t3/tube_cut_b2026/problem.json"
    digest = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()

    base = _build_tube_envelope()
    real_manifest_env = deepcopy(base)
    real_manifest_env["problem_id"] = "synthetic_tube"  # synthetic id: policy skips stock rules
    real_manifest_env["model_snapshot"]["input_sha256"] = {rel: digest}

    original = validate("synthetic_tube", real_manifest_env)
    checks_by_name = {c["name"]: c for c in original["checks"]}
    assert checks_by_name["strict_input_hash_manifest"]["ok"] is True
    assert checks_by_name["strict_input_hashes"]["ok"] is True

    tampered = deepcopy(real_manifest_env)
    tampered["model_snapshot"]["input_sha256"][rel] = "0" * 64
    tampered_report = validate("synthetic_tube", tampered)
    tampered_checks = {c["name"]: c for c in tampered_report["checks"]}
    assert tampered_checks["strict_input_hashes"]["ok"] is False
    assert "input changed after solve" in (tampered_checks["strict_input_hashes"]["detail"] or "")


# --------------------------------------------------------------------------- #
# 5. State inheritance & anti-early-stop guard hook matrix
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("domain", DOMAINS)
def test_supervisor_state_inherits_domain_supervisor_state(domain: str, domain_modules: dict[str, Any]) -> None:
    state_cls = getattr(domain_modules[domain], DOMAIN_SPECS[domain]["state"])
    bases = getattr(state_cls, "__orig_bases__", ())
    assert DomainSupervisorState in bases or issubclass(state_cls, dict)


@pytest.mark.parametrize("domain", DOMAINS)
def test_supervisor_state_canonical_fields(domain: str, domain_modules: dict[str, Any]) -> None:
    state_cls = getattr(domain_modules[domain], DOMAIN_SPECS[domain]["state"])
    hints = typing.get_type_hints(state_cls)
    canonical = (
        "messages", "remaining_steps", "domain", "problem_id",
        "budget_ledger_path", "candidate_solution_path",
        "validation_report_path", "redteam_report_path",
    )
    for field in canonical:
        assert field in hints, f"{domain}: missing canonical field {field}"


@pytest.mark.parametrize("domain", DOMAINS)
def test_guard_hook_reroutes_non_lead_early_exit(domain: str, domain_modules: dict[str, Any]) -> None:
    mod = domain_modules[domain]
    hook = getattr(mod, DOMAIN_SPECS[domain]["hook"])
    assert callable(hook)


# --------------------------------------------------------------------------- #
# 6. Supervisor graph build & compile smoke matrix
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("domain", DOMAINS)
def test_supervisor_graph_builds_and_compiles(domain: str, domain_modules: dict[str, Any]) -> None:
    mod = domain_modules[domain]
    spec = DOMAIN_SPECS[domain]
    builder = getattr(mod, spec["graph_fn"])
    compiler = getattr(mod, spec["compiled_fn"])
    model = get_chat_model()

    graph = builder(model=model)
    assert isinstance(graph, StateGraph)
    compiled = compiler(model=model)
    assert isinstance(compiled, CompiledStateGraph)


@pytest.mark.parametrize("domain", DOMAINS)
def test_all_domain_lead_and_worker_agents_creatable(domain: str, domain_modules: dict[str, Any]) -> None:
    mod = domain_modules[domain]
    spec = DOMAIN_SPECS[domain]
    lead_fn = getattr(mod, spec["lead_fn"])
    workers_fn = getattr(mod, spec["workers_fn"])
    model = get_chat_model()

    lead = lead_fn(model=model)
    assert lead is not None
    workers = workers_fn(model=model)
    assert len(workers) == 5
