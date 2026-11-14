#!/usr/bin/env python3
"""DIMO Mutator — Universal Domain Invariant Mutation Operator Engine (Task 5.1).

Abstracts the 5 universal operations research physical & mathematical invariant
mutations:

  1. **CONSERVATION** (守恒破坏) — Breaks mass, energy, flow or money balance.
  2. **CAPACITY**     (容量超限) — Injects extreme demands or item sizes exceeding capacity.
  3. **PRECEDENCE**   (时序颠倒) — Inverts dependencies, swaps order, or injects DAG cycles.
  4. **BOUND**        (下界欺诈) — Injects invalid dual bounds or impossible convergence claims.
  5. **HASH**         (哈希篡改) — Modifies payload under an unchanged signature or forges hash.

The engine provides:
  * A unified enum :class:`MutationType` and result container :class:`MutationResult`.
  * Generic heuristic mutators capable of mutating arbitrary structured OR data
    with named domain invariant attack profiles.
  * Complete deepcopy isolation: the original input data is never modified in place.
"""
from __future__ import annotations

import enum
import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping

__all__ = [
    "MutationType",
    "MutationResult",
    "DIMOMutator",
    "apply_mutation",
    "generate_attack_suite",
    "stable_hash",
    "DOMAIN_ATTACK_MAPPINGS",
    "SUPPORTED_DOMAINS",
]

SUPPORTED_DOMAINS: tuple[str, ...] = (
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


class MutationType(str, enum.Enum):
    """The 5 canonical physical & mathematical invariant mutation classes."""

    CONSERVATION = "conservation"
    CAPACITY = "capacity"
    PRECEDENCE = "precedence"
    BOUND = "bound"
    HASH = "hash"

    @classmethod
    def from_str(cls, value: str | MutationType) -> MutationType:
        """Parse string or enum into a canonical MutationType."""
        if isinstance(value, cls):
            return value
        cleaned = str(value).strip().lower()
        for member in cls:
            if member.value == cleaned or member.name.lower() == cleaned:
                return member
        raise ValueError(
            f"Unknown mutation type {value!r}; allowed: {[m.value for m in cls]}"
        )


def _hash_default(obj: Any) -> Any:
    """Normalize non-JSON objects for stable hashing (numpy → Python scalars)."""
    tolist = getattr(obj, "tolist", None)
    if callable(tolist):
        try:
            return tolist()
        except Exception:  # noqa: BLE001
            pass
    item = getattr(obj, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:  # noqa: BLE001
            pass
    if isinstance(obj, (set, frozenset)):
        return sorted(obj, key=repr)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", "ignore")
    return str(obj)


def stable_hash(payload: Any) -> str:
    """Deterministic SHA-256 hash over arbitrary JSON-serializable structures.

    numpy scalars/arrays are normalized so the digest depends on the logical
    payload, not the numeric type representation (``np.int64(5)`` == ``5``).
    """
    try:
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=_hash_default)
    except Exception:
        blob = str(payload)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class MutationResult:
    """Outcome of applying an invariant mutation to a data structure."""

    mutated_data: Any
    mutation_type: MutationType
    domain: str | None
    applied: bool
    description: str
    original_hash: str
    mutated_hash: str
    operator_name: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_tampered(self) -> bool:
        """True if the data was actively modified and payload hash changed."""
        return self.applied and (self.original_hash != self.mutated_hash)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to a plain serializable dict."""
        res = asdict(self)
        res["mutation_type"] = self.mutation_type.value
        return res


def _dig(target: Any, *keys: Any) -> Any:
    """Safely traverse nested dictionary keys."""
    curr = target
    for k in keys:
        if isinstance(curr, dict) and k in curr:
            curr = curr[k]
        else:
            return None
    return curr


# ---------------------------------------------------------------------------
# Domain Attack Mappings
# ---------------------------------------------------------------------------

DOMAIN_ATTACK_MAPPINGS: dict[str, dict[MutationType, str]] = {
    "tube": {
        MutationType.CONSERVATION: "numeric_cocut_inflation",
        MutationType.CAPACITY: "q4_inventory_injection",
        MutationType.PRECEDENCE: "q3_demand_deletion",
        MutationType.BOUND: "invalid_lower_bound_claim",
        MutationType.HASH: "input_hash_tamper",
    },
    "routing": {
        MutationType.CONSERVATION: "client_omission_tamper",
        MutationType.CAPACITY: "capacity_overflow_injection",
        MutationType.PRECEDENCE: "time_window_inversion",
        MutationType.BOUND: "distance_forgery",
        MutationType.HASH: "coordinate_hash_tamper",
    },
    "scheduling": {
        MutationType.CONSERVATION: "job_omission_tamper",
        MutationType.CAPACITY: "machine_overlap_injection",
        MutationType.PRECEDENCE: "operation_precedence_inversion",
        MutationType.BOUND: "makespan_deflation",
        MutationType.HASH: "matrix_hash_tamper",
    },
    "project": {
        MutationType.CONSERVATION: "activity_omission_tamper",
        MutationType.CAPACITY: "resource_capacity_overflow",
        MutationType.PRECEDENCE: "activity_precedence_inversion",
        MutationType.BOUND: "makespan_deflation",
        MutationType.HASH: "network_hash_tamper",
    },
    "inventory": {
        MutationType.CONSERVATION: "flow_balance_violation_injection",
        MutationType.CAPACITY: "capacity_overflow_injection",
        MutationType.PRECEDENCE: "safety_stock_deficit_tamper",
        MutationType.BOUND: "cost_deflation_forgery",
        MutationType.HASH: "setup_evasion_tamper",
    },
    "facility": {
        MutationType.CONSERVATION: "demand_undersatisfaction_tamper",
        MutationType.CAPACITY: "facility_capacity_overflow_injection",
        MutationType.PRECEDENCE: "closed_facility_allocation_cheat",
        MutationType.BOUND: "cost_deflation_forgery",
        MutationType.HASH: "single_source_fractional_cheat",
    },
    "rostering": {
        MutationType.CONSERVATION: "understaffing_coverage_tamper",
        MutationType.CAPACITY: "consecutive_workday_overflow",
        MutationType.PRECEDENCE: "night_rest_violation_injection",
        MutationType.BOUND: "fairness_metric_tamper",
        MutationType.HASH: "shift_clash_tamper",
    },
    "microgrid": {
        MutationType.CONSERVATION: "power_balance_violation_injection",
        MutationType.CAPACITY: "soc_limit_breach_injection",
        MutationType.PRECEDENCE: "daily_storage_imbalance_tamper",
        MutationType.BOUND: "energy_cost_deflation_forgery",
        MutationType.HASH: "battery_efficiency_dynamics_tamper",
    },
    "pricing": {
        MutationType.CONSERVATION: "scenario_recourse_balance_tamper",
        MutationType.CAPACITY: "first_stage_capacity_overflow",
        MutationType.PRECEDENCE: "stochastic_inequality_forgery",
        MutationType.BOUND: "expected_profit_inflation_forgery",
        MutationType.HASH: "first_stage_cost_tamper",
    },
    "finance": {
        MutationType.CONSERVATION: "weight_simplex_violation_injection",
        MutationType.CAPACITY: "short_position_breach_injection",
        MutationType.PRECEDENCE: "discrete_lot_allocation_tamper",
        MutationType.BOUND: "sharpe_ratio_inflation_forgery",
        MutationType.HASH: "variance_risk_deflation_forgery",
    },
}


# ---------------------------------------------------------------------------
# Generic Invariant Mutator Implementations (Heuristic fallback)
# ---------------------------------------------------------------------------

def _mutate_generic_conservation(data: Any, delta: float = 100.0) -> tuple[Any, bool, str]:
    """Break flow, mass, demand or supply conservation by perturbing numeric values."""
    mutated = deepcopy(data)
    if isinstance(mutated, dict):
        for k in ("demands", "flows", "supplies", "balance", "total", "weights", "inventory", "quantities"):
            if k in mutated and isinstance(mutated[k], (int, float)):
                orig = mutated[k]
                mutated[k] = orig + delta
                return mutated, True, f"Perturbed numeric sum '{k}' from {orig} to {mutated[k]} (+{delta})"
            if k in mutated and isinstance(mutated[k], list) and mutated[k]:
                if isinstance(mutated[k][0], (int, float)):
                    orig = mutated[k][0]
                    mutated[k][0] = orig + delta
                    return mutated, True, f"Perturbed list value '{k}[0]' from {orig} to {mutated[k][0]} (+{delta})"
        # search any numeric field
        for k, v in list(mutated.items()):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                mutated[k] = v + delta
                return mutated, True, f"Generic conservation mutation on '{k}': {v} -> {mutated[k]}"
            if isinstance(v, dict):
                sub_res, sub_app, sub_desc = _mutate_generic_conservation(v, delta)
                if sub_app:
                    mutated[k] = sub_res
                    return mutated, True, f"Nested conservation: {sub_desc}"
        mutated["_dimo_conservation_violation"] = delta
        return mutated, True, f"Injected synthetic conservation imbalance (+{delta})"
    elif isinstance(mutated, list) and mutated:
        if isinstance(mutated[0], (int, float)) and not isinstance(mutated[0], bool):
            orig = mutated[0]
            mutated[0] = orig + delta
            return mutated, True, f"Generic list conservation mutation on [0]: {orig} -> {mutated[0]}"
        if isinstance(mutated[0], dict):
            sub_res, sub_app, sub_desc = _mutate_generic_conservation(mutated[0], delta)
            if sub_app:
                mutated[0] = sub_res
                return mutated, True, f"List element conservation: {sub_desc}"
    return mutated, False, "No mutable numeric quantity found for conservation attack"


def _mutate_generic_capacity(data: Any, multiplier: float = 3.0) -> tuple[Any, bool, str]:
    """Inflate demands, weights, loads or durations to breach capacity limits."""
    mutated = deepcopy(data)
    if isinstance(mutated, dict):
        for k in ("demand", "load", "weight", "size", "duration", "hours", "usage", "power", "volume"):
            for actual_k, v in mutated.items():
                key_str = str(actual_k).lower()
                if k in key_str and isinstance(v, (int, float)) and not isinstance(v, bool):
                    orig = v
                    mutated[actual_k] = v * multiplier
                    return mutated, True, f"Inflated capacity parameter '{actual_k}' from {orig} to {mutated[actual_k]} (x{multiplier})"
                if k in key_str and isinstance(v, list) and v and isinstance(v[0], (int, float)):
                    orig = v[0]
                    v[0] = v[0] * multiplier
                    return mutated, True, f"Inflated capacity list item '{actual_k}[0]' from {orig} to {v[0]} (x{multiplier})"
        for k, v in list(mutated.items()):
            if isinstance(v, dict):
                sub_res, sub_app, sub_desc = _mutate_generic_capacity(v, multiplier)
                if sub_app:
                    mutated[k] = sub_res
                    return mutated, True, f"Nested capacity: {sub_desc}"
        mutated["_dimo_capacity_overflow"] = multiplier * 1e6
        return mutated, True, f"Injected synthetic capacity overflow (x{multiplier})"
    elif isinstance(mutated, list) and mutated and isinstance(mutated[0], dict):
        sub_res, sub_app, sub_desc = _mutate_generic_capacity(mutated[0], multiplier)
        if sub_app:
            mutated[0] = sub_res
            return mutated, True, f"List element capacity: {sub_desc}"
    return mutated, False, "No capacity-related attribute found to overflow"


def _mutate_generic_precedence(data: Any) -> tuple[Any, bool, str]:
    """Invert sequence, swap task order, or reverse routes/timeline."""
    mutated = deepcopy(data)
    if isinstance(mutated, dict):
        for k in ("route", "routes", "sequence", "order", "tasks", "jobs", "schedule", "stages", "periods", "steps"):
            for actual_k, v in mutated.items():
                if k in str(actual_k).lower() and isinstance(v, list) and len(v) >= 2:
                    v.reverse()
                    return mutated, True, f"Reversed sequence list in '{actual_k}' (length {len(v)})"
        # check any list with len >= 2
        for actual_k, v in mutated.items():
            if isinstance(v, list) and len(v) >= 2:
                v[0], v[-1] = v[-1], v[0]
                return mutated, True, f"Swapped first and last element in list '{actual_k}'"
            if isinstance(v, dict):
                sub_res, sub_app, sub_desc = _mutate_generic_precedence(v)
                if sub_app:
                    mutated[actual_k] = sub_res
                    return mutated, True, f"Nested precedence: {sub_desc}"
        mutated["_dimo_precedence_inversion"] = ["step_end", "step_start"]
        return mutated, True, "Injected inverted precedence sequence marker"
    elif isinstance(mutated, list) and len(mutated) >= 2:
        mutated.reverse()
        return mutated, True, f"Reversed top-level list of length {len(mutated)}"
    return mutated, False, "No ordered sequence found for precedence inversion"


def _mutate_generic_bound(data: Any, gap: float = 1000.0) -> tuple[Any, bool, str]:
    """Inject an impossible dual bound claim or deflated primal objective."""
    mutated = deepcopy(data)
    if isinstance(mutated, dict):
        for k in ("lower_bound", "dual_bound", "bound", "best_bound", "objective", "cost", "makespan"):
            for actual_k, v in mutated.items():
                if k in str(actual_k).lower() and isinstance(v, (int, float)) and not isinstance(v, bool):
                    orig = v
                    mutated[actual_k] = orig - gap if orig > gap else orig / 2.0
                    return mutated, True, f"Deflated bound/objective in '{actual_k}' from {orig} to {mutated[actual_k]}"
        for k, v in list(mutated.items()):
            if isinstance(v, dict):
                sub_res, sub_app, sub_desc = _mutate_generic_bound(v, gap)
                if sub_app:
                    mutated[k] = sub_res
                    return mutated, True, f"Nested bound: {sub_desc}"
        # fallback: inject an invalid lower bound attribute directly
        mutated["invalid_dual_bound_claim"] = gap * 100.0
        return mutated, True, f"Injected artificial impossible dual bound {gap * 100.0}"
    return mutated, False, "No objective or bound field found to forge"


def _mutate_generic_hash(data: Any) -> tuple[Any, bool, str]:
    """Modify content while maintaining or forging a fake hash digest."""
    mutated = deepcopy(data)
    fake_digest = "0" * 64
    if isinstance(mutated, dict):
        for k in ("sha256", "hash", "digest", "signature", "merkle_root", "input_hash"):
            for actual_k, v in mutated.items():
                if k in str(actual_k).lower() and isinstance(v, str):
                    orig = v
                    mutated[actual_k] = fake_digest
                    return mutated, True, f"Replaced hash '{actual_k}' with forged digest '{fake_digest[:8]}...'"
        # inject or modify an innocuous field to corrupt payload hash
        mutated["_dimo_hash_tamper_marker"] = "TAMPERED_WITHOUT_RECOMPUTING_HASH"
        return mutated, True, "Injected stealth marker payload disrupting signature verification"
    elif isinstance(mutated, list):
        mutated.append("TAMPERED_PAYLOAD_ELEMENT")
        return mutated, True, "Appended element to list disrupting hash integrity"
    return mutated, False, "Cannot mutate primitive hash"


GENERIC_OPERATORS: dict[MutationType, Callable[..., tuple[Any, bool, str]]] = {
    MutationType.CONSERVATION: _mutate_generic_conservation,
    MutationType.CAPACITY: _mutate_generic_capacity,
    MutationType.PRECEDENCE: _mutate_generic_precedence,
    MutationType.BOUND: _mutate_generic_bound,
    MutationType.HASH: _mutate_generic_hash,
}


# ---------------------------------------------------------------------------
# DIMOMutator Core Class
# ---------------------------------------------------------------------------

class DIMOMutator:
    """Universal Domain Invariant Mutation Operator Engine.

    Coordinates generic heuristic operators and domain-specific attack builders
    across all supported domains.
    """

    def __init__(self, default_domain: str | None = None) -> None:
        self.default_domain = default_domain
        self._custom_operators: dict[tuple[str | None, MutationType], Callable[..., tuple[Any, bool, str]]] = {}

    def register_operator(
        self,
        mutation_type: MutationType | str,
        operator: Callable[..., tuple[Any, bool, str]],
        domain: str | None = None,
    ) -> None:
        """Register a custom mutation operator function for a domain/type."""
        m_type = MutationType.from_str(mutation_type)
        self._custom_operators[(domain, m_type)] = operator

    def get_supported_domains(self) -> list[str]:
        """Return the list of all standard supported domain names."""
        return list(SUPPORTED_DOMAINS)

    def get_domain_attack_names(self, domain: str) -> dict[str, str]:
        """Return the dictionary of {MutationType.value: attack_builder_name} for a domain."""
        dom = domain.strip().lower()
        mapping = DOMAIN_ATTACK_MAPPINGS.get(dom, {})
        return {k.value: v for k, v in mapping.items()}

    def mutate(
        self,
        data: Any,
        mutation_type: MutationType | str,
        domain: str | None = None,
        **kwargs: Any,
    ) -> MutationResult:
        """Apply an invariant mutation to ``data`` with guaranteed deepcopy isolation.

        Args:
            data: The source input/solution data to mutate.
            mutation_type: The target invariant to break.
            domain: Target domain (e.g. 'routing', 'tube', etc.). If None, falls back
                    to ``self.default_domain``, or uses generic operators.
            **kwargs: Extra parameters passed to the operator (delta, gap, multiplier, etc.).

        Returns:
            A :class:`MutationResult` containing the mutated data, status, and audit hashes.
        """
        m_type = MutationType.from_str(mutation_type)
        target_domain = (domain or self.default_domain or "").strip().lower() or None
        orig_hash = stable_hash(data)

        # 1. Check custom registered operators
        custom_op = self._custom_operators.get((target_domain, m_type)) or self._custom_operators.get((None, m_type))
        if custom_op is not None:
            mut_data, applied, desc = custom_op(data, **kwargs)
            return MutationResult(
                mutated_data=mut_data,
                mutation_type=m_type,
                domain=target_domain,
                applied=applied,
                description=desc,
                original_hash=orig_hash,
                mutated_hash=stable_hash(mut_data),
                operator_name="custom_operator",
            )

        # 2. Generic physical/mathematical invariant operator (with domain attack metadata if mapped)
        generic_op = GENERIC_OPERATORS[m_type]
        mut_data, applied, desc = generic_op(data, **kwargs)
        attack_name = (
            DOMAIN_ATTACK_MAPPINGS.get(target_domain, {}).get(m_type)
            if target_domain
            else None
        )
        op_name = attack_name or f"generic_{m_type.value}"
        meta = {"domain_attack": attack_name} if attack_name else {}
        return MutationResult(
            mutated_data=mut_data,
            mutation_type=m_type,
            domain=target_domain,
            applied=applied,
            description=desc,
            original_hash=orig_hash,
            mutated_hash=stable_hash(mut_data),
            operator_name=op_name,
            metadata=meta,
        )

    def mutate_all_invariants(
        self,
        data: Any,
        domain: str | None = None,
        **kwargs: Any,
    ) -> list[MutationResult]:
        """Apply all 5 canonical invariant mutations sequentially to independent copies of data."""
        return [
            self.mutate(data, m_type, domain=domain, **kwargs)
            for m_type in MutationType
        ]


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

_GLOBAL_MUTATOR = DIMOMutator()


def apply_mutation(
    data: Any,
    mutation_type: MutationType | str,
    domain: str | None = None,
    **kwargs: Any,
) -> MutationResult:
    """Convenience helper to apply a single invariant mutation using the global engine."""
    return _GLOBAL_MUTATOR.mutate(data, mutation_type, domain=domain, **kwargs)


def generate_attack_suite(
    data: Any,
    domain: str | None = None,
    **kwargs: Any,
) -> list[MutationResult]:
    """Convenience helper to generate all 5 invariant attacks for a dataset."""
    return _GLOBAL_MUTATOR.mutate_all_invariants(data, domain=domain, **kwargs)
