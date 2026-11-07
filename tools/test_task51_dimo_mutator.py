#!/usr/bin/env python3
"""Comprehensive test suite for Universal DIMO Mutator Engine (Task 5.1).

Covers:
  - MutationType enum parsing & string compatibility
  - Hash stability & tamper detection (original_hash != mutated_hash)
  - Deepcopy isolation: original payload is never mutated in place
  - All 5 generic heuristic mutators (conservation, capacity, precedence, bound, hash)
  - Domain-specific attack dispatching across all 10 OR-Path domains
  - Custom operator registration & overrides
  - Module-level convenience functions: apply_mutation, generate_attack_suite
"""
from __future__ import annotations

import importlib
from copy import deepcopy
from typing import Any
import pytest

from orpath.agents.dimo_mutator import (
    DIMOMutator,
    MutationResult,
    MutationType,
    apply_mutation,
    generate_attack_suite,
    stable_hash,
    DOMAIN_ATTACK_MAPPINGS,
    SUPPORTED_DOMAINS,
)


# ---------------------------------------------------------------------------
# 1. MutationType & Data Structure Tests
# ---------------------------------------------------------------------------

def test_mutation_type_enum_members():
    assert len(MutationType) == 5
    assert MutationType.CONSERVATION.value == "conservation"
    assert MutationType.CAPACITY.value == "capacity"
    assert MutationType.PRECEDENCE.value == "precedence"
    assert MutationType.BOUND.value == "bound"
    assert MutationType.HASH.value == "hash"


def test_mutation_type_from_str():
    assert MutationType.from_str("CONSERVATION") == MutationType.CONSERVATION
    assert MutationType.from_str("capacity") == MutationType.CAPACITY
    assert MutationType.from_str("Precedence") == MutationType.PRECEDENCE
    assert MutationType.from_str(MutationType.BOUND) == MutationType.BOUND

    with pytest.raises(ValueError, match="Unknown mutation type"):
        MutationType.from_str("nonexistent_mutation")


def test_mutation_result_properties():
    res = MutationResult(
        mutated_data={"x": 2},
        mutation_type=MutationType.CONSERVATION,
        domain="routing",
        applied=True,
        description="test applied",
        original_hash="hash_a",
        mutated_hash="hash_b",
        operator_name="test_op",
    )
    assert res.is_tampered is True
    d = res.to_dict()
    assert d["mutation_type"] == "conservation"
    assert d["applied"] is True

    # When not applied or hashes equal
    unapplied = MutationResult(
        mutated_data={"x": 1},
        mutation_type=MutationType.CONSERVATION,
        domain="routing",
        applied=False,
        description="test not applied",
        original_hash="hash_a",
        mutated_hash="hash_a",
        operator_name="test_op",
    )
    assert unapplied.is_tampered is False


def test_stable_hash_determinism():
    data1 = {"b": 2, "a": [1, 2, 3]}
    data2 = {"a": [1, 2, 3], "b": 2}
    assert stable_hash(data1) == stable_hash(data2)

    tampered = {"b": 3, "a": [1, 2, 3]}
    assert stable_hash(data1) != stable_hash(tampered)


# ---------------------------------------------------------------------------
# 2. Generic Invariant Mutator Tests
# ---------------------------------------------------------------------------

def test_generic_conservation_mutation():
    mutator = DIMOMutator()
    data = {"demands": 150.0, "notes": "sample"}
    orig_copy = deepcopy(data)

    res = mutator.mutate(data, MutationType.CONSERVATION)
    assert res.applied is True
    assert res.is_tampered is True
    assert res.mutated_data["demands"] != orig_copy["demands"]
    assert data == orig_copy  # Deepcopy isolation check


def test_generic_capacity_mutation():
    mutator = DIMOMutator()
    data = {"vehicle_load": 40.0, "capacity_limit": 50.0}
    orig_copy = deepcopy(data)

    res = mutator.mutate(data, MutationType.CAPACITY, multiplier=3.0)
    assert res.applied is True
    assert res.is_tampered is True
    assert res.mutated_data["vehicle_load"] == 120.0
    assert data == orig_copy


def test_generic_precedence_mutation():
    mutator = DIMOMutator()
    data = {"task_sequence": ["step1", "step2", "step3"]}
    orig_copy = deepcopy(data)

    res = mutator.mutate(data, MutationType.PRECEDENCE)
    assert res.applied is True
    assert res.is_tampered is True
    assert res.mutated_data["task_sequence"] == ["step3", "step2", "step1"]
    assert data == orig_copy


def test_generic_bound_mutation():
    mutator = DIMOMutator()
    data = {"objective_cost": 500.0}
    orig_copy = deepcopy(data)

    res = mutator.mutate(data, MutationType.BOUND, gap=200.0)
    assert res.applied is True
    assert res.is_tampered is True
    assert res.mutated_data["objective_cost"] == 300.0
    assert data == orig_copy


def test_generic_hash_mutation():
    mutator = DIMOMutator()
    data = {"sha256": "abcdef1234567890", "payload": {"foo": "bar"}}
    orig_copy = deepcopy(data)

    res = mutator.mutate(data, MutationType.HASH)
    assert res.applied is True
    assert res.is_tampered is True
    assert res.mutated_data["sha256"] == "0" * 64
    assert data == orig_copy


# ---------------------------------------------------------------------------
# 3. Domain-Specific Attack Integration (All 10 Domains)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def domain_envelopes() -> dict[str, Any]:
    from solve_facility import solve_facility_location
    from solve_jssp import solve_jssp
    from solve_lot_sizing import solve_lot_sizing
    from solve_portfolio import solve_portfolio
    from solve_rcpsp import solve_rcpsp
    from solve_staff_rostering import solve_staff_rostering
    from solve_stochastic_lp import solve_stochastic_lp
    from tools.test_phase3_full_regression import (
        _build_tube_envelope,
        _build_routing_envelope,
        _build_microgrid_envelope,
    )

    routing_gate = importlib.import_module("scripts.routing_redteam_gate")
    return {
        "tube": _build_tube_envelope(),
        "routing": _build_routing_envelope(routing_gate),
        "scheduling": solve_jssp("ft06", time_limit_s=30),
        "project": solve_rcpsp(time_limit_s=30),
        "inventory": solve_lot_sizing(method="mip", capacity=60.0, problem_id="lot_sizing_clsp60"),
        "facility": solve_facility_location(single_source=True, time_limit_s=10),
        "rostering": solve_staff_rostering(num_employees=8, num_days=14, time_limit_s=10),
        "microgrid": _build_microgrid_envelope(),
        "pricing": solve_stochastic_lp(),
        "finance": solve_portfolio(objective_type="max_sharpe", total_portfolio_value=100000.0),
    }


@pytest.mark.parametrize("domain", SUPPORTED_DOMAINS)
def test_domain_attack_mappings_complete(domain: str):
    mapping = DOMAIN_ATTACK_MAPPINGS.get(domain)
    assert mapping is not None, f"Domain {domain} must have attack mapping"
    assert len(mapping) == 5, f"Domain {domain} must map all 5 MutationTypes"
    for m_type in MutationType:
        assert m_type in mapping, f"Missing {m_type} in domain {domain}"


@pytest.mark.parametrize("domain", SUPPORTED_DOMAINS)
def test_all_10_domains_mutation_suite(domain: str, domain_envelopes: dict[str, Any]):
    sol = domain_envelopes[domain]
    mutator = DIMOMutator(default_domain=domain)
    orig_copy = deepcopy(sol)

    suite = mutator.mutate_all_invariants(sol)
    assert len(suite) == 5
    for res in suite:
        assert res.domain == domain
        assert res.applied is True
        assert res.is_tampered is True
        assert res.mutation_type in MutationType

    assert sol == orig_copy  # Deepcopy isolation check


# ---------------------------------------------------------------------------
# 4. Custom Operator Registration & Convenience Functions
# ---------------------------------------------------------------------------

def test_custom_operator_registration():
    mutator = DIMOMutator()

    def my_custom_bound(data: Any, **kw: Any):
        data = deepcopy(data)
        data["custom_bound_violation"] = True
        return data, True, "Injected custom bound marker"

    mutator.register_operator(MutationType.BOUND, my_custom_bound)
    res = mutator.mutate({"val": 10}, MutationType.BOUND)
    assert res.applied is True
    assert res.mutated_data.get("custom_bound_violation") is True
    assert res.operator_name == "custom_operator"


def test_convenience_functions():
    data = {"flow": 50.0}
    res = apply_mutation(data, "conservation", delta=25.0)
    assert res.applied is True
    assert res.mutated_data["flow"] == 75.0

    suite = generate_attack_suite(data)
    assert len(suite) == 5
    assert all(isinstance(r, MutationResult) for r in suite)


def test_dimo_mutator_introspection():
    mutator = DIMOMutator()
    domains = mutator.get_supported_domains()
    assert len(domains) == 10
    names = mutator.get_domain_attack_names("routing")
    assert "capacity" in names
    assert names["capacity"] == "capacity_overflow_injection"
