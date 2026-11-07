#!/usr/bin/env python3
"""Task 4.2 — Composite Lead cross-domain orchestrator tests.

Covers:
1. Handoff transformers (facility→routing, inventory→routing,
   scheduling→inventory) with strict material / demand conservation checks.
2. Composite pipeline state-machine flow (LRP / IRP / PRP topology order and
   per-stage recording).
3. End-to-end LRP composite solve (real CFLP facility solution + real PyVRP
   routing solution chained through the orchestrator).
4. Cross-team data lineage & illegal-tamper interception (a tampered upstream
   envelope fails the relay conservation check and raises).
5. Composite supervisor graph construction + mock-node execution.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langgraph.graph import StateGraph  # noqa: E402
from langgraph.graph.state import CompiledStateGraph  # noqa: E402

from orpath.agents.composite_lead import (  # noqa: E402
    COMPOSITE_DOMAIN_CHAINS,
    COMPOSITE_DOMAIN_NODE_PREFIX,
    COMPOSITE_IRP,
    COMPOSITE_LRP,
    COMPOSITE_LEAD_NAME,
    COMPOSITE_MICROGRID_FACILITY,
    COMPOSITE_PRP,
    COMPOSITE_CUSTOM,
    COMPOSITE_TYPES,
    CompositeLeadError,
    CompositeLeadOrchestrator,
    CompositeSupervisorState,
    CompositeTamperError,
    HandoffConservationError,
    HANDOFF_TRANSFORMERS,
    build_compiled_composite_supervisor,
    build_composite_supervisor_graph,
    compute_composite_objective,
    record_lineage,
    stable_hash,
    transform_facility_to_microgrid,
    transform_facility_to_routing,
    transform_inventory_to_routing,
    transform_scheduling_to_inventory,
    verify_lineage_chain,
)

# ---------------------------------------------------------------------------
# Real-solver fixtures (lazy, module-scoped so they run once)
# ---------------------------------------------------------------------------
FACILITY_COORDS = [(0.0, 0.0), (10.0, 0.0), (5.0, 10.0)]
CUSTOMER_COORDS = [(1.0, 1.0), (2.0, 2.0), (8.0, 1.0), (9.0, 9.0), (5.0, 5.0)]
FACILITY_DEMANDS = [30.0, 40.0, 50.0, 40.0, 30.0]


@pytest.fixture(scope="module")
def cflp_solution() -> dict[str, Any]:
    """Real OR-Tools CFLP solution on a geolocated instance."""
    from solve_facility import solve_facility_location

    return solve_facility_location(
        fixed_costs=[100.0, 120.0, 110.0],
        capacities=[200.0, 200.0, 200.0],
        demands=FACILITY_DEMANDS,
        facility_coords=FACILITY_COORDS,
        customer_coords=CUSTOMER_COORDS,
        cost_per_km_ton=1.0,
        time_limit_s=10.0,
        problem_id="task42_cflp",
    )


@pytest.fixture(scope="module")
def ft06_solution() -> dict[str, Any]:
    """Real PyJobShop CP-SAT FT06 solution (optimal makespan 55)."""
    from solve_jssp import solve_jssp

    return solve_jssp(instance_name="ft06", time_limit_s=10.0)


@pytest.fixture(scope="module")
def lot_sizing_solution() -> dict[str, Any]:
    """Real Wagner-Whitin lot-sizing solution."""
    from solve_lot_sizing import solve_lot_sizing

    return solve_lot_sizing(
        demands=[20.0, 50.0, 10.0, 50.0],
        setup_cost=85.0,
        holding_cost=1.0,
    )


# ---------------------------------------------------------------------------
# Mock executor helpers
# ---------------------------------------------------------------------------
def _mock_solution(problem_id: str, objective: float, status: str = "OPTIMAL") -> dict[str, Any]:
    return {
        "problem_id": problem_id,
        "status": status,
        "objective": objective,
        "problem_class": "mock",
        "solver": "mock",
        "lower_bound": objective,
        "optimality_gap": 0.0,
    }


def _mock_facility_solution() -> dict[str, Any]:
    sol = _mock_solution("mock_facility", 500.0)
    sol.update({
        "problem_class": "facility_location",
        "open_facility_ids": [0],
        "open_facilities": [
            {"facility_id": 0, "fixed_cost": 100.0, "capacity": 200.0, "load": 100.0, "utilization": 0.5},
        ],
        "allocations": [
            {"customer_id": 0, "demand": 60.0, "served_by": [{"facility_id": 0, "fraction": 1.0}]},
            {"customer_id": 1, "demand": 40.0, "served_by": [{"facility_id": 0, "fraction": 1.0}]},
        ],
    })
    return sol


def _mock_inventory_solution() -> dict[str, Any]:
    sol = _mock_solution("mock_inventory", 200.0)
    sol.update({
        "problem_class": "lot_sizing",
        "production": [100.0, 50.0],
        "inventory": [0.0, 0.0],
        "initial_inventory": 0.0,
        "schedule": [
            {"period": 0, "demand": 100.0, "production": 100.0, "inventory": 0.0},
            {"period": 1, "demand": 50.0, "production": 50.0, "inventory": 0.0},
        ],
    })
    return sol


def _mock_scheduling_solution() -> dict[str, Any]:
    sol = _mock_solution("mock_scheduling", 30.0)
    sol.update({
        "problem_class": "jssp",
        "makespan": 30.0,
        "schedule": [
            {"job": 0, "machine": 0, "start": 0, "end": 10, "duration": 10},
            {"job": 1, "machine": 0, "start": 10, "end": 20, "duration": 10},
            {"job": 2, "machine": 0, "start": 20, "end": 30, "duration": 10},
        ],
    })
    return sol


def _mock_routing_solution() -> dict[str, Any]:
    sol = _mock_solution("mock_routing", 300.0, status="FEASIBLE")
    sol.update({"problem_class": "pyvrp", "routes": [], "total_distance": 300})
    return sol


def _mock_executor(solution: dict[str, Any]):
    """Return a mock executor that always returns ``solution``."""
    def executor(domain_input: Any, config: Any) -> dict[str, Any]:
        return copy.deepcopy(solution)
    return executor


# ---------------------------------------------------------------------------
# 1. Handoff transformers — strict conservation
# ---------------------------------------------------------------------------
def test_transform_facility_to_routing_conservation(cflp_solution: dict[str, Any]) -> None:
    """Open facilities → depot; customer demand stays conserved."""
    routing_input = transform_facility_to_routing(
        cflp_solution,
        {
            "demands": FACILITY_DEMANDS,
            "customer_coords": CUSTOMER_COORDS,
            "facility_coords": FACILITY_COORDS,
            "vehicle_capacity": 100.0,
            "num_vehicles": 5,
        },
    )
    cons = routing_input["conservation"]
    assert cons["total_demand"] == pytest.approx(sum(FACILITY_DEMANDS))
    assert cons["total_served"] == pytest.approx(sum(FACILITY_DEMANDS))
    assert cons["num_clients"] == len(FACILITY_DEMANDS)
    assert cons["num_open_facilities"] == len(cflp_solution["open_facility_ids"])
    # every client demand matches the original customer demand
    client_demands = [c["demand"] for c in routing_input["clients"]]
    assert client_demands == pytest.approx(FACILITY_DEMANDS)
    # depot is one of the open facilities
    assert cons["primary_depot_id"] in cflp_solution["open_facility_ids"]
    # depot_assignments cover every customer exactly once
    assigned = sorted(
        cid for cids in routing_input["depot_assignments"].values() for cid in cids
    )
    assert assigned == sorted(range(len(FACILITY_DEMANDS)))


def test_transform_inventory_to_routing_conservation(lot_sizing_solution: dict[str, Any]) -> None:
    """Per-period net shipments → vehicle loading demands; mass conserved."""
    routing_input = transform_inventory_to_routing(
        lot_sizing_solution,
        {"vehicle_capacity": 100.0, "num_vehicles": 5},
    )
    cons = routing_input["conservation"]
    total_demand = sum(lot_sizing_solution["schedule"][t]["demand"] for t in range(len(lot_sizing_solution["production"])))
    assert cons["total_demand"] == pytest.approx(total_demand)
    assert cons["total_shipped"] == pytest.approx(total_demand)
    # aggregate production identity
    assert cons["total_production"] == pytest.approx(
        cons["total_shipped"] + cons["final_inventory"] - cons["initial_inventory"]
    )
    # client demands sum to total shipped
    assert sum(c["demand"] for c in routing_input["clients"]) == pytest.approx(cons["total_shipped"])
    # one client per period with positive net shipment
    assert cons["num_shipment_clients"] <= cons["num_periods"]


def test_transform_scheduling_to_inventory_conservation(ft06_solution: dict[str, Any]) -> None:
    """Job completion times → per-period production counts; job count conserved."""
    inventory_input = transform_scheduling_to_inventory(ft06_solution, period_duration=10.0)
    cons = inventory_input["conservation"]
    assert cons["total_output"] == ft06_solution["num_jobs"]
    assert cons["num_jobs"] == ft06_solution["num_jobs"]
    assert sum(inventory_input["production"]) == ft06_solution["num_jobs"]
    # every job appears in exactly one period bucket
    all_jobs = sorted(j for bucket in inventory_input["period_output"] for j in bucket)
    assert all_jobs == sorted(range(ft06_solution["num_jobs"]))
    # completion times are within [0, makespan]
    for ct in inventory_input["job_completion_times"].values():
        assert 0.0 <= ct <= ft06_solution["makespan"] + 1e-6


def test_transform_facility_to_microgrid_conservation(cflp_solution: dict[str, Any]) -> None:
    """Open facilities → microgrid candidate sites; capacity conserved."""
    microgrid_input = transform_facility_to_microgrid(cflp_solution, {})
    cons = microgrid_input["conservation"]
    assert cons["num_sites"] == len(cflp_solution["open_facilities"])
    assert cons["total_storage_capacity_kwh"] == pytest.approx(
        sum(f["capacity"] for f in cflp_solution["open_facilities"])
    )
    assert microgrid_input["num_sites"] == len(cflp_solution["open_facility_ids"])


# ---------------------------------------------------------------------------
# 2. Composite pipeline state-machine flow
# ---------------------------------------------------------------------------
def test_composite_domain_chains_topology() -> None:
    """Canonical composite chains match the documented topologies."""
    assert COMPOSITE_DOMAIN_CHAINS[COMPOSITE_LRP] == ["facility", "routing"]
    assert COMPOSITE_DOMAIN_CHAINS[COMPOSITE_IRP] == ["inventory", "routing"]
    assert COMPOSITE_DOMAIN_CHAINS[COMPOSITE_PRP] == ["scheduling", "inventory", "routing"]
    assert COMPOSITE_DOMAIN_CHAINS[COMPOSITE_MICROGRID_FACILITY] == ["facility", "microgrid"]
    for ctype in COMPOSITE_TYPES:
        assert ctype in COMPOSITE_DOMAIN_CHAINS


def test_orchestrator_lrp_state_flow() -> None:
    """LRP orchestrator runs facility → routing and records both stages."""
    orch = CompositeLeadOrchestrator(
        COMPOSITE_LRP,
        domain_executors={
            "facility": _mock_executor(_mock_facility_solution()),
            "routing": _mock_executor(_mock_routing_solution()),
        },
    )
    state = orch.run({"customer_data": {}})
    assert state["composite_type"] == COMPOSITE_LRP
    assert state["domain_chain"] == ["facility", "routing"]
    assert state["current_domain_idx"] == 2
    assert set(state["domain_results"]) == {"facility", "routing"}
    assert len(state["cross_domain_lineage"]) == 1
    assert state["cross_domain_lineage"][0]["upstream_domain"] == "facility"
    assert state["cross_domain_lineage"][0]["downstream_domain"] == "routing"
    # composite objective = facility + routing
    assert state["composite_objective"] == pytest.approx(500.0 + 300.0)
    assert state["composite_report"]["overall_status"] == "COMPOSITE_FEASIBLE"
    assert state["composite_report"]["conservation_verified"] is True


def test_orchestrator_irp_state_flow() -> None:
    """IRP orchestrator runs inventory → routing."""
    orch = CompositeLeadOrchestrator(
        COMPOSITE_IRP,
        domain_executors={
            "inventory": _mock_executor(_mock_inventory_solution()),
            "routing": _mock_executor(_mock_routing_solution()),
        },
    )
    state = orch.run({"client_data": {}})
    assert state["domain_chain"] == ["inventory", "routing"]
    assert state["current_domain_idx"] == 2
    assert set(state["domain_results"]) == {"inventory", "routing"}
    assert len(state["cross_domain_lineage"]) == 1
    assert state["composite_objective"] == pytest.approx(200.0 + 300.0)


def test_orchestrator_prp_state_flow() -> None:
    """PRP orchestrator runs scheduling → inventory → routing."""
    orch = CompositeLeadOrchestrator(
        COMPOSITE_PRP,
        domain_executors={
            "scheduling": _mock_executor(_mock_scheduling_solution()),
            "inventory": _mock_executor(_mock_inventory_solution()),
            "routing": _mock_executor(_mock_routing_solution()),
        },
    )
    state = orch.run({})
    assert state["domain_chain"] == ["scheduling", "inventory", "routing"]
    assert state["current_domain_idx"] == 3
    assert set(state["domain_results"]) == {"scheduling", "inventory", "routing"}
    assert len(state["cross_domain_lineage"]) == 2
    # lineage chain: scheduling→inventory then inventory→routing
    assert [e["upstream_domain"] for e in state["cross_domain_lineage"]] == ["scheduling", "inventory"]
    assert [e["downstream_domain"] for e in state["cross_domain_lineage"]] == ["inventory", "routing"]
    assert state["composite_objective"] == pytest.approx(30.0 + 200.0 + 300.0)
    assert state["composite_report"]["overall_status"] == "COMPOSITE_FEASIBLE"


def test_orchestrator_rejects_unknown_domain() -> None:
    with pytest.raises(CompositeLeadError):
        CompositeLeadOrchestrator(COMPOSITE_CUSTOM, domain_chain=["facility", "nonexistent"])


def test_orchestrator_rejects_unknown_composite_type() -> None:
    with pytest.raises(CompositeLeadError):
        CompositeLeadOrchestrator("NOT_A_COMPOSITE")


# ---------------------------------------------------------------------------
# 3. End-to-end LRP composite solve (real CFLP + real PyVRP)
# ---------------------------------------------------------------------------
def test_end_to_end_lrp_real_solvers() -> None:
    """Chain a real facility CFLP solution into a real PyVRP routing solution."""
    config = {
        "facility": {
            "fixed_costs": [100.0, 120.0, 110.0],
            "capacities": [200.0, 200.0, 200.0],
            "demands": FACILITY_DEMANDS,
            "facility_coords": FACILITY_COORDS,
            "customer_coords": CUSTOMER_COORDS,
            "cost_per_km_ton": 1.0,
            "time_limit_s": 10.0,
            "problem_id": "task42_lrp_e2e",
        },
        "customer_data": {
            "demands": FACILITY_DEMANDS,
            "customer_coords": CUSTOMER_COORDS,
            "facility_coords": FACILITY_COORDS,
            "vehicle_capacity": 100.0,
            "num_vehicles": 5,
        },
        "routing": {"time_limit_s": 3.0, "problem_id": "task42_lrp_e2e_routing"},
    }
    orch = CompositeLeadOrchestrator(COMPOSITE_LRP)
    state = orch.run(config)

    facility_sol = state["domain_results"]["facility"]
    routing_sol = state["domain_results"]["routing"]

    # both stages produced real solver envelopes
    assert facility_sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert routing_sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert facility_sol["objective"] >= 0
    assert routing_sol["objective"] >= 0

    # composite objective is the honest sum of the two solver objectives
    assert state["composite_objective"] == pytest.approx(
        facility_sol["objective"] + routing_sol["objective"]
    )

    # conservation held across the handoff
    assert state["composite_report"]["conservation_verified"] is True
    assert state["composite_report"]["lineage_consistent"] is True
    assert state["composite_report"]["overall_status"] == "COMPOSITE_FEASIBLE"

    # the routing solution actually visited every customer
    visited = set()
    for route in routing_sol["routes"]:
        for visit in route.get("visits", []):
            if visit.get("type") == "client":
                visited.add(visit.get("client_idx"))
    # PyVRP client indices are 0-based (the depot is a separate location)
    assert visited == set(range(len(FACILITY_DEMANDS)))


# ---------------------------------------------------------------------------
# 4. Cross-team data lineage & illegal-tamper interception
# ---------------------------------------------------------------------------
def test_tampered_facility_solution_rejected(cflp_solution: dict[str, Any]) -> None:
    """A tampered facility envelope (fraction ≠ 1) fails the relay check."""
    tampered = copy.deepcopy(cflp_solution)
    # corrupt the first customer's served fraction
    tampered["allocations"][0]["served_by"][0]["fraction"] = 0.5
    with pytest.raises(HandoffConservationError):
        transform_facility_to_routing(
            tampered,
            {
                "demands": FACILITY_DEMANDS,
                "customer_coords": CUSTOMER_COORDS,
                "facility_coords": FACILITY_COORDS,
            },
        )


def test_tampered_facility_demand_mismatch_rejected(cflp_solution: dict[str, Any]) -> None:
    """A tampered demand that contradicts customer_data fails the check."""
    tampered = copy.deepcopy(cflp_solution)
    tampered["allocations"][0]["demand"] = 999.0
    with pytest.raises(HandoffConservationError):
        transform_facility_to_routing(
            tampered,
            {
                "demands": FACILITY_DEMANDS,
                "customer_coords": CUSTOMER_COORDS,
                "facility_coords": FACILITY_COORDS,
            },
        )


def test_tampered_inventory_solution_rejected(lot_sizing_solution: dict[str, Any]) -> None:
    """A tampered inventory envelope (net shipment ≠ demand) is rejected."""
    tampered = copy.deepcopy(lot_sizing_solution)
    tampered["production"][0] = 999.0  # breaks the period mass balance
    with pytest.raises(HandoffConservationError):
        transform_inventory_to_routing(tampered, {})


def test_tampered_scheduling_solution_rejected(ft06_solution: dict[str, Any]) -> None:
    """Dropping a job from the schedule breaks job-count conservation."""
    tampered = copy.deepcopy(ft06_solution)
    tampered["schedule"] = [s for s in tampered["schedule"] if s["job"] != 0]
    with pytest.raises(HandoffConservationError):
        transform_scheduling_to_inventory(tampered, period_duration=10.0)


def test_lineage_chain_detects_tamper() -> None:
    """A structurally tampered lineage record (missing hash) is flagged."""
    upstream = {"objective": 100.0, "status": "OPTIMAL"}
    downstream = {"clients": [{"demand": 10.0}]}
    entry_a = record_lineage("facility", "routing", upstream, downstream)
    entry_b = record_lineage("routing", "inventory", downstream, {"routes": []})
    # tamper: drop the downstream hash from the second record
    del entry_b["downstream_sha256"]
    problems = verify_lineage_chain([entry_a, entry_b])
    assert problems, "tampered lineage record must be detected"
    assert any("downstream_sha256" in p for p in problems)


def test_lineage_chain_consistent_when_untouched() -> None:
    """Well-formed lineage records have no structural problems."""
    upstream = {"objective": 100.0}
    downstream_a = {"clients": []}
    cons = {"checks": ["mass_balance"]}
    entry_a = record_lineage("facility", "routing", upstream, downstream_a, cons)
    entry_b = record_lineage("routing", "inventory", downstream_a, {"routes": []}, cons)
    assert verify_lineage_chain([entry_a, entry_b]) == []


def test_verify_input_integrity_detects_tamper() -> None:
    """`verify_input_integrity` raises when the input was mutated in flight."""
    from orpath.agents.composite_lead import verify_input_integrity

    payload = {"clients": [{"demand": 10.0}]}
    expected = stable_hash(payload)
    # untampered → no raise
    verify_input_integrity(expected, payload, upstream_domain="facility", downstream_domain="routing")
    # tampered → CompositeTamperError
    tampered = {"clients": [{"demand": 999.0}]}
    with pytest.raises(CompositeTamperError):
        verify_input_integrity(expected, tampered, upstream_domain="facility", downstream_domain="routing")


def test_orchestrator_input_tamper_detected() -> None:
    """The orchestrator intercepts an in-flight mutation of a prepared input."""
    def tamper_hook(state: dict[str, Any], domain: str) -> None:
        if domain == "routing":
            # illegally mutate the routing input between handoff and execution
            state["domain_inputs"]["routing"]["clients"][0]["demand"] = 9999.0

    orch = CompositeLeadOrchestrator(
        COMPOSITE_LRP,
        domain_executors={
            "facility": _mock_executor(_mock_facility_solution()),
            "routing": _mock_executor(_mock_routing_solution()),
        },
    )
    with pytest.raises(CompositeTamperError):
        orch.run({"customer_data": {}}, pre_stage_hook=tamper_hook)


def test_orchestrator_rejects_tampered_upstream() -> None:
    """The orchestrator propagates a tampered upstream as a structured failure.

    A mock facility executor returns a valid envelope; the handoff transformer
    then sees a *tampered* copy (simulating an in-flight mutation) and must
    raise before the routing stage runs.
    """
    good_facility = _mock_facility_solution()

    def tampering_facility_executor(domain_input: Any, config: Any) -> dict[str, Any]:
        sol = copy.deepcopy(good_facility)
        # simulate an illegal mutation between execution and handoff
        sol["allocations"][0]["served_by"][0]["fraction"] = 0.3
        return sol

    orch = CompositeLeadOrchestrator(
        COMPOSITE_LRP,
        domain_executors={
            "facility": tampering_facility_executor,
            "routing": _mock_executor(_mock_routing_solution()),
        },
    )
    with pytest.raises(HandoffConservationError):
        orch.run({"customer_data": {}})


# ---------------------------------------------------------------------------
# 5. Composite supervisor graph construction + mock-node execution
# ---------------------------------------------------------------------------
def test_build_composite_supervisor_graph_returns_state_graph() -> None:
    graph = build_composite_supervisor_graph(COMPOSITE_LRP)
    assert isinstance(graph, StateGraph)


def test_build_compiled_composite_supervisor_nodes() -> None:
    compiled = build_compiled_composite_supervisor(
        COMPOSITE_PRP,
        domain_executors={
            "scheduling": _mock_executor(_mock_scheduling_solution()),
            "inventory": _mock_executor(_mock_inventory_solution()),
            "routing": _mock_executor(_mock_routing_solution()),
        },
    )
    assert isinstance(compiled, CompiledStateGraph)
    expected_nodes = {
        f"{COMPOSITE_DOMAIN_NODE_PREFIX}_scheduling",
        f"{COMPOSITE_DOMAIN_NODE_PREFIX}_inventory",
        f"{COMPOSITE_DOMAIN_NODE_PREFIX}_routing",
        COMPOSITE_LEAD_NAME,
    }
    assert expected_nodes <= set(compiled.nodes)


def test_compiled_composite_graph_runs_mock_pipeline() -> None:
    """Execute the compiled composite graph end-to-end with mock executors."""
    compiled = build_compiled_composite_supervisor(
        COMPOSITE_LRP,
        domain_executors={
            "facility": _mock_executor(_mock_facility_solution()),
            "routing": _mock_executor(_mock_routing_solution()),
        },
    )
    initial = {
        "messages": [],
        "composite_type": COMPOSITE_LRP,
        "domain_chain": ["facility", "routing"],
        "problem_config": {"customer_data": {}},
    }
    final = compiled.invoke(initial)

    assert final["current_domain_idx"] == 2
    assert set(final["domain_results"]) == {"facility", "routing"}
    assert final["composite_objective"] == pytest.approx(500.0 + 300.0)
    assert final["composite_report"]["overall_status"] == "COMPOSITE_FEASIBLE"
    assert len(final["cross_domain_lineage"]) == 1
    assert final["cross_domain_lineage"][0]["upstream_domain"] == "facility"


def test_compiled_composite_graph_prp_mock_pipeline() -> None:
    """PRP graph runs all three stages in order via the compiled graph."""
    compiled = build_compiled_composite_supervisor(
        COMPOSITE_PRP,
        domain_executors={
            "scheduling": _mock_executor(_mock_scheduling_solution()),
            "inventory": _mock_executor(_mock_inventory_solution()),
            "routing": _mock_executor(_mock_routing_solution()),
        },
    )
    initial = {
        "messages": [],
        "composite_type": COMPOSITE_PRP,
        "domain_chain": ["scheduling", "inventory", "routing"],
        "problem_config": {},
    }
    final = compiled.invoke(initial)
    assert final["current_domain_idx"] == 3
    assert final["composite_objective"] == pytest.approx(30.0 + 200.0 + 300.0)
    assert len(final["cross_domain_lineage"]) == 2
    assert final["composite_report"]["lineage_consistent"] is True


def test_composite_supervisor_state_is_typeddict() -> None:
    """>CompositeSupervisorState is a real TypedDict carrying the composite fields."""
    # TypedDict classes built on typing_extensions._TypedDictMeta (like
    # MessagesState) are not recognised by typing.is_typeddict, so verify the
    # structural TypedDict markers + annotations instead.
    assert hasattr(CompositeSupervisorState, "__annotations__")
    assert hasattr(CompositeSupervisorState, "__required_keys__")
    assert "composite_type" in CompositeSupervisorState.__annotations__
    assert "domain_chain" in CompositeSupervisorState.__annotations__
    assert "cross_domain_lineage" in CompositeSupervisorState.__annotations__
    assert "composite_objective" in CompositeSupervisorState.__annotations__


def test_handoff_transformers_registry_complete() -> None:
    """All canonical composite handoffs have a registered transformer."""
    for (up, down) in [
        ("facility", "routing"),
        ("inventory", "routing"),
        ("scheduling", "inventory"),
        ("facility", "microgrid"),
    ]:
        assert (up, down) in HANDOFF_TRANSFORMERS


def test_compute_composite_objective_sums_only_valid() -> None:
    results = {
        "facility": {"objective": 100.0},
        "routing": {"objective": 50.0},
        "inventory": {"objective": None},  # not solved → excluded
        "scheduling": {"objective": -1.0},  # infeasible sentinel → excluded
    }
    assert compute_composite_objective(results) == pytest.approx(150.0)


def test_stable_hash_deterministic() -> None:
    a = stable_hash({"x": 1, "y": [2, 3]})
    b = stable_hash({"y": [2, 3], "x": 1})
    assert a == b
    assert len(a) == 64


# --------------------------------------------------------------------------- #
# Regression: numpy-typed payloads must hash identically to Python scalars,
# and objective aggregation must not crash on non-numeric values.
# --------------------------------------------------------------------------- #
def test_stable_hash_numpy_matches_python_scalars() -> None:
    """np.int64(5) and 5 are the same logical payload → same digest."""
    np = pytest.importorskip("numpy")
    assert stable_hash({"a": 5}) == stable_hash({"a": np.int64(5)})
    assert stable_hash({"a": 1.5}) == stable_hash({"a": np.float64(1.5)})
    assert stable_hash({"a": [1, 2, 3]}) == stable_hash({"a": np.array([1, 2, 3])})


def test_compute_composite_objective_skips_non_numeric() -> None:
    """A non-numeric objective is excluded instead of crashing aggregation."""
    results = {
        "good": {"objective": 10.0},
        "weird": {"objective": {"not": "a number"}},
        "bool": {"objective": True},
        "none": {"objective": None},
    }
    assert compute_composite_objective(results) == pytest.approx(10.0)


def test_executor_arity_detection_single_arg() -> None:
    """A single-argument executor is called with one arg, not crash."""
    from orpath.agents.composite_lead import (
        CompositeLeadOrchestrator,
        _executor_arity,
        _call_domain_executor,
    )

    def one_arg_executor(domain_input):
        return {"status": "FEASIBLE", "objective": 1.0, "input_seen": domain_input}

    assert _executor_arity(one_arg_executor) == 1
    out = _call_domain_executor(one_arg_executor, {"x": 1}, {}, domain="demo")
    assert out["input_seen"] == {"x": 1}

    def two_arg_executor(domain_input, config):
        return {"status": "FEASIBLE", "objective": 2.0, "cfg": dict(config)}

    assert _executor_arity(two_arg_executor) == 2
    out2 = _call_domain_executor(two_arg_executor, None, {"k": 1}, domain="demo")
    assert out2["cfg"] == {"k": 1}


def test_executor_internal_typeerror_not_masked_as_arity() -> None:
    """A TypeError raised inside an executor propagates (not retried as 1-arg)."""
    from orpath.agents.composite_lead import _call_domain_executor

    def buggy_executor(domain_input, config):
        # Genuine internal bug: TypeError unrelated to argument count.
        raise TypeError("unsupported operand type(s) for +: 'int' and 'str'")

    with pytest.raises(TypeError, match="unsupported operand"):
        _call_domain_executor(buggy_executor, None, {}, domain="demo")


def test_transform_facility_to_routing_tolerates_missing_facility_id() -> None:
    """served_by entries without 'facility_id' fall back to the primary depot."""
    from orpath.agents.composite_lead import transform_facility_to_routing

    sol = {
        "problem_id": "tolerant",
        "open_facility_ids": [0],
        "open_facilities": [{"facility_id": 0, "capacity": 100.0, "load": 50.0}],
        "allocations": [
            {
                "customer_id": 1,
                "demand": 10.0,
                "served_by": [{"fraction": 1.0}],  # no facility_id
            }
        ],
    }
    out = transform_facility_to_routing(sol)
    assert out["depot"]["id"] == 0
    assert out["depot_assignments"][0] == [1]
