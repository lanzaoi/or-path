#!/usr/bin/env python3
"""Composite Lead — cross-domain composite scheduling orchestrator (Task 4.2).

An industrial-grade *composite* supervisor that coordinates several
single-domain supervisor teams (facility, routing, inventory, scheduling,
microgrid) into a single pipeline, executing canonical composite OR problem
patterns:

  * **LRP**  (Location-Routing Problem)
      ``facility`` (选址定仓) → ``routing`` (从开放仓库到客户的路径优化)
  * **IRP**  (Inventory-Routing Problem)
      ``inventory`` (各周期补货量) → ``routing`` (周期车辆配送路径)
  * **PRP**  (Production-Inventory-Routing Problem)
      ``scheduling`` (车间排产) → ``inventory`` (成品入库与批量控制)
      → ``routing`` (多周期出库物流)
  * **Microgrid-Facility**
      ``facility`` (微电网储能电站选址) → ``microgrid`` (分时充放电调度与套利)

The module provides three layers:

1. **Handoff Transformers** — deterministic, conservation-checked context
   adapters that convert one domain's solution envelope into the next
   domain's input contract (e.g. open facilities → VRP depot, per-period
   net shipments → per-vehicle loading demands, job completion times →
   per-period production counts).  Every transformer recomputes a mass /
   demand conservation proof from raw data and raises
   ``HandoffConservationError`` on any drift.

2. **CompositeLeadOrchestrator** — the deterministic pipeline engine.  It
   walks ``domain_chain`` in order, calls each domain's executor (a real
   solver function, a compiled supervisor, or a test double), applies the
   matching handoff transformer, records a SHA-256 lineage entry for every
   stage, and aggregates the composite objective + comprehensive validation
   report.

3. **build_composite_supervisor_graph** — a LangGraph ``StateGraph`` that
   materialises the pipeline as one node per domain plus a final composite
   lead node, wired in dependency-topological order.

Numbers Truth: the composite objective is the *sum of the independently
recomputed per-domain objectives* returned by the solvers — never invented.
A tampered upstream envelope fails the conservation check and aborts the
pipeline with a structured error.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable, Mapping
from typing import Any, NotRequired, TypedDict

from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

__all__ = [
    # composite problem classes
    "COMPOSITE_LRP",
    "COMPOSITE_IRP",
    "COMPOSITE_PRP",
    "COMPOSITE_MICROGRID_FACILITY",
    "COMPOSITE_CUSTOM",
    "COMPOSITE_TYPES",
    "COMPOSITE_DOMAIN_CHAINS",
    # lineage / hashing
    "stable_hash",
    "record_lineage",
    "verify_lineage_chain",
    "verify_input_integrity",
    # errors
    "CompositeLeadError",
    "HandoffConservationError",
    "CompositeTamperError",
    # transformers
    "transform_facility_to_routing",
    "transform_inventory_to_routing",
    "transform_scheduling_to_inventory",
    "transform_facility_to_microgrid",
    "HANDOFF_TRANSFORMERS",
    # conservation
    "verify_conservation",
    # state
    "CompositeSupervisorState",
    "COMPOSITE_LEAD_NAME",
    "COMPOSITE_DOMAIN_NODE_PREFIX",
    # orchestrator
    "CompositeLeadOrchestrator",
    "compute_composite_objective",
    "build_composite_supervisor_graph",
    "build_compiled_composite_supervisor",
    # default executors
    "DEFAULT_DOMAIN_EXECUTORS",
    "default_facility_executor",
    "default_routing_executor",
    "default_inventory_executor",
    "default_scheduling_executor",
    "default_microgrid_executor",
]

# ---------------------------------------------------------------------------
# Canonical composite problem classes & domain chains
# ---------------------------------------------------------------------------
COMPOSITE_LRP = "LRP"
COMPOSITE_IRP = "IRP"
COMPOSITE_PRP = "PRP"
COMPOSITE_MICROGRID_FACILITY = "MICROGRID_FACILITY"
COMPOSITE_CUSTOM = "CUSTOM"

COMPOSITE_TYPES: tuple[str, ...] = (
    COMPOSITE_LRP,
    COMPOSITE_IRP,
    COMPOSITE_PRP,
    COMPOSITE_MICROGRID_FACILITY,
    COMPOSITE_CUSTOM,
)

#: Canonical pipeline topology per composite class.
COMPOSITE_DOMAIN_CHAINS: dict[str, list[str]] = {
    COMPOSITE_LRP: ["facility", "routing"],
    COMPOSITE_IRP: ["inventory", "routing"],
    COMPOSITE_PRP: ["scheduling", "inventory", "routing"],
    COMPOSITE_MICROGRID_FACILITY: ["facility", "microgrid"],
    COMPOSITE_CUSTOM: [],
}

COMPOSITE_LEAD_NAME = "or_composite_lead"
COMPOSITE_DOMAIN_NODE_PREFIX = "composite_stage"

#: Tolerance for mass / demand conservation recomputes.
CONSERVATION_TOL = 1e-6


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class CompositeLeadError(Exception):
    """Base error for the composite lead pipeline."""


class HandoffConservationError(CompositeLeadError):
    """Raised when a handoff transformer detects mass / demand drift."""


class CompositeTamperError(CompositeLeadError):
    """Raised when upstream data is tampered between lineage recording."""


# ---------------------------------------------------------------------------
# Lineage & hashing
# ---------------------------------------------------------------------------
def _hash_default(obj: Any) -> Any:
    """Normalize non-JSON objects for stable lineage hashing.

    numpy scalars/arrays are normalized through ``.tolist()`` / ``.item()`` so
    that ``stable_hash({"a": 5}) == stable_hash({"a": np.int64(5)})``.
    Without this, the JSON encoder's ``str()`` fallback would stringify a
    numpy scalar (``"5"``) while keeping a Python int numeric (``5``),
    producing different digests for the *same* logical payload and causing
    false ``CompositeTamperError`` lineage mismatches whenever a solver
    returns numpy-typed envelope fields.
    """
    tolist = getattr(obj, "tolist", None)
    if callable(tolist):
        try:
            return tolist()
        except Exception:  # noqa: BLE001 - fall through to generic handling
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
    """Return a deterministic SHA-256 hex digest of a JSON-serialisable payload.

    Keys are sorted and ``ensure_ascii=False`` keeps the digest stable across
    runs; ``default=_hash_default`` tolerates solver objects (notably numpy
    scalars/arrays) that are not natively JSON-serialisable while keeping the
    digest independent of the numeric type representation.  This is the *data*
    hash used for cross-domain lineage — it is intentionally independent of
    dict insertion order.
    """
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=_hash_default).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def record_lineage(
    upstream_domain: str,
    downstream_domain: str,
    upstream_sol: Any,
    downstream_input: Any,
    conservation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one cross-domain lineage record with SHA-256 hashes.

    The record captures the data fingerprints on both sides of the handoff
    plus the conservation proof, so a downstream stage can prove (or refute)
    that it received exactly what the upstream stage produced.
    """
    return {
        "upstream_domain": upstream_domain,
        "downstream_domain": downstream_domain,
        "upstream_sha256": stable_hash(upstream_sol),
        "downstream_sha256": stable_hash(downstream_input),
        "conservation": dict(conservation or {}),
    }


def verify_lineage_chain(lineage: list[dict[str, Any]]) -> list[str]:
    """Return structural problems in a cross-domain lineage record list.

    Each handoff record must carry both SHA-256 fingerprints and a
    conservation proof.  Because domain executors *transform* their input
    into a solution envelope, consecutive records do not share a common hash
    — the meaningful tamper interception is the per-stage input-integrity
    check (:func:`verify_input_integrity`) plus the transformers' conservation
    recomputations.  This function audits the records' structural integrity.
    """
    problems: list[str] = []
    for i, entry in enumerate(lineage):
        for key in ("upstream_domain", "downstream_domain", "upstream_sha256", "downstream_sha256", "conservation"):
            if key not in entry:
                problems.append(f"lineage entry {i} missing key {key!r}")
        if not entry.get("conservation", {}).get("checks"):
            problems.append(f"lineage entry {i} missing conservation checks")
    return problems


def verify_input_integrity(
    expected_sha256: str,
    actual_input: Any,
    *,
    upstream_domain: str = "",
    downstream_domain: str = "",
) -> None:
    """Raise ``CompositeTamperError`` when ``actual_input`` was mutated in flight.

    Called by the orchestrator immediately before each downstream stage runs:
    the input prepared by the previous handoff transformer must still hash to
    the value recorded in the lineage entry.  A mismatch means an illegal
    tamper occurred between the handoff and the executor call.
    """
    actual = stable_hash(actual_input)
    if actual != expected_sha256:
        raise CompositeTamperError(
            f"input tamper detected between {upstream_domain!r} and "
            f"{downstream_domain!r}: expected {expected_sha256[:12]}… "
            f"got {actual[:12]}…"
        )


# ---------------------------------------------------------------------------
# Conservation verification
# ---------------------------------------------------------------------------
def _close(a: float, b: float, tol: float = CONSERVATION_TOL) -> bool:
    return abs(float(a) - float(b)) <= tol


def verify_conservation(
    served_total: float,
    demand_total: float,
    *,
    served_total_name: str = "served_total",
    demand_total_name: str = "demand_total",
    tol: float = CONSERVATION_TOL,
) -> None:
    """Raise ``HandoffConservationError`` when served mass ≠ demand mass."""
    if not _close(served_total, demand_total, tol):
        raise HandoffConservationError(
            f"conservation violation: {served_total_name}={served_total!r} "
            f"≠ {demand_total_name}={demand_total!r} (tol={tol})"
        )


# ---------------------------------------------------------------------------
# Handoff transformers
# ---------------------------------------------------------------------------
def _extract_facility_demands(facility_sol: Mapping[str, Any]) -> list[float]:
    """Return per-customer demand from a facility solution, preserving order."""
    allocations = facility_sol.get("allocations") or facility_sol.get("assignments") or []
    demands: list[float] = []
    for alloc in allocations:
        demands.append(float(alloc.get("demand", 0.0)))
    return demands


def transform_facility_to_routing(
    facility_sol: Mapping[str, Any],
    customer_data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Transform a facility-location solution into a VRP input instance.

    Parameters
    ----------
    facility_sol
        CFLP/SSCFLP solution envelope from ``solve_facility_location``.
    customer_data
        Optional context: ``demands``, ``customer_coords``,
        ``facility_coords``, ``vehicle_capacity``, ``num_vehicles``.

    Returns
    -------
    dict
        A PyVRP ``instance_data`` dict with ``depot``, ``clients``,
        ``capacity``, ``vehicles`` and a ``conservation`` proof block.

    Raises
    ------
    HandoffConservationError
        If any customer's served fraction ≠ 1, or the aggregate served mass
        ≠ aggregate demand, or an open facility is over-capacity.
    """
    if not isinstance(facility_sol, Mapping):
        raise CompositeLeadError("facility_sol must be a mapping")
    customer_data = dict(customer_data or {})

    open_ids = [int(f) for f in facility_sol.get("open_facility_ids", [])]
    open_facs = {
        int(f["facility_id"]): f
        for f in (facility_sol.get("open_facilities") or [])
    }
    allocations = facility_sol.get("allocations") or facility_sol.get("assignments") or []
    if not allocations:
        raise HandoffConservationError("facility solution has no allocations")

    # --- per-customer conservation ------------------------------------------
    per_customer: list[dict[str, Any]] = []
    served_total = 0.0
    demand_total = 0.0
    for alloc in allocations:
        cid = int(alloc.get("customer_id"))
        demand = float(alloc.get("demand", 0.0))
        served_by = alloc.get("served_by") or []
        # ``allocations`` carries fractions; ``assignments`` carries quantities.
        if served_by and "quantity" in served_by[0]:
            served = sum(float(s.get("quantity", 0.0)) for s in served_by)
        else:
            frac_sum = sum(float(s.get("fraction", 0.0)) for s in served_by)
            if not _close(frac_sum, 1.0):
                raise HandoffConservationError(
                    f"customer {cid} served fraction sum {frac_sum!r} ≠ 1.0"
                )
            served = frac_sum * demand
        if not _close(served, demand):
            raise HandoffConservationError(
                f"customer {cid} served mass {served!r} ≠ demand {demand!r}"
            )
        served_total += served
        demand_total += demand
        per_customer.append({"customer_id": cid, "demand": demand, "served": served})

    verify_conservation(served_total, demand_total,
                        served_total_name="total_served",
                        demand_total_name="total_demand")

    # --- facility capacity & load conservation -------------------------------
    for fid in open_ids:
        spec = open_facs.get(fid)
        if spec is None:
            raise CompositeLeadError(f"open facility {fid} missing from open_facilities")
        load = float(spec.get("load", 0.0))
        cap = float(spec.get("capacity", 0.0))
        if cap > 0 and load > cap + CONSERVATION_TOL:
            raise HandoffConservationError(
                f"facility {fid} load {load!r} exceeds capacity {cap!r}"
            )

    # --- build VRP clients ----------------------------------------------------
    explicit_demands = customer_data.get("demands")
    if explicit_demands is not None:
        if len(explicit_demands) != len(allocations):
            raise HandoffConservationError(
                "customer_data['demands'] length "
                f"{len(explicit_demands)} ≠ allocations length {len(allocations)}"
            )
        # cross-check explicit demands against the facility solution
        for i, d in enumerate(explicit_demands):
            if not _close(float(d), float(allocations[i].get("demand", 0.0))):
                raise HandoffConservationError(
                    f"customer {i} demand mismatch: customer_data={d!r} "
                    f"facility_sol={allocations[i].get('demand')!r}"
                )

    customer_coords = customer_data.get("customer_coords") or [None] * len(allocations)
    raw_facility_coords = customer_data.get("facility_coords") or []
    facility_coords = raw_facility_coords or [None] * max(
        (max(open_ids) + 1) if open_ids else 0, len(raw_facility_coords)
    )

    # choose primary depot = open facility serving the largest load
    if not open_ids:
        raise HandoffConservationError("no open facilities in facility solution")
    primary_depot_id = max(
        open_ids,
        key=lambda fid: float(open_facs.get(fid, {}).get("load", 0.0)),
    )

    depot_coord = (
        facility_coords[primary_depot_id]
        if primary_depot_id < len(facility_coords) and facility_coords[primary_depot_id]
        else (0.0, 0.0)
    )

    clients: list[dict[str, Any]] = []
    for i, alloc in enumerate(allocations):
        cid = int(alloc.get("customer_id"))
        coord = customer_coords[i] if i < len(customer_coords) and customer_coords[i] else (float(cid) * 10.0, 0.0)
        clients.append({
            "id": cid,
            "name": f"C{cid}",
            "x": float(coord[0]),
            "y": float(coord[1]),
            "demand": float(alloc.get("demand", 0.0)),
            "tw_early": int(customer_data.get("tw_early", 0)),
            "tw_late": int(customer_data.get("tw_late", 999999)),
            "service_duration": int(customer_data.get("service_duration", 0)),
        })

    # facility → customer assignment map (for multi-depot provenance)
    assignment_map: dict[int, list[int]] = {fid: [] for fid in open_ids}
    for i, alloc in enumerate(allocations):
        served_by = alloc.get("served_by") or []
        primary_fid = primary_depot_id
        if served_by:
            best = max(served_by, key=lambda s: float(s.get("fraction", 0.0)))
            if best.get("facility_id") is not None:
                primary_fid = int(best["facility_id"])
        assignment_map.setdefault(primary_fid, []).append(int(alloc.get("customer_id")))

    routing_input: dict[str, Any] = {
        "name": f"lrp_routing_{facility_sol.get('problem_id', 'facility')}",
        "depot": {
            "id": 0,
            "name": f"Depot_{primary_depot_id}",
            "x": float(depot_coord[0]),
            "y": float(depot_coord[1]),
            "tw_early": int(customer_data.get("depot_tw_early", 0)),
            "tw_late": int(customer_data.get("depot_tw_late", 999999)),
            "service_duration": int(customer_data.get("depot_service_duration", 0)),
        },
        "clients": clients,
        "capacity": float(customer_data.get("vehicle_capacity", customer_data.get("capacity", 200))),
        "vehicles": int(customer_data.get("num_vehicles", customer_data.get("vehicles", 25))),
        "depot_assignments": assignment_map,
        "conservation": {
            "total_demand": round(demand_total, 6),
            "total_served": round(served_total, 6),
            "num_clients": len(clients),
            "num_open_facilities": len(open_ids),
            "primary_depot_id": primary_depot_id,
            "checks": ["per_customer_fraction", "aggregate_mass", "facility_capacity"],
        },
    }
    return routing_input


def transform_inventory_to_routing(
    inventory_sol: Mapping[str, Any],
    client_data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Transform a lot-sizing solution into a multi-period VRP input.

    Each period's *net shipment* (production − inventory delta) becomes one
    client loading demand.  Mass conservation is verified against the
    recorded per-period demands and the aggregate production / ending
    inventory identity.
    """
    if not isinstance(inventory_sol, Mapping):
        raise CompositeLeadError("inventory_sol must be a mapping")
    client_data = dict(client_data or {})

    production = [float(p) for p in (inventory_sol.get("production") or [])]
    inventory = [float(iv) for iv in (inventory_sol.get("inventory") or [])]
    schedule = inventory_sol.get("schedule") or []
    T = len(production)
    if T == 0:
        raise HandoffConservationError("inventory solution has no production series")
    if len(inventory) != T:
        raise HandoffConservationError(
            f"production length {T} ≠ inventory length {len(inventory)}"
        )

    initial_inventory = float(inventory_sol.get("initial_inventory", 0.0))
    # schedule demands (preferred) else fall back to net-shipment mass balance
    if schedule and len(schedule) == T:
        demands = [float(s.get("demand", 0.0)) for s in schedule]
    else:
        demands = []
        for t in range(T):
            prev_inv = initial_inventory if t == 0 else inventory[t - 1]
            demands.append(production[t] - (inventory[t] - prev_inv))

    # net shipment per period == demand (mass balance in a feasible plan)
    net_shipments: list[float] = []
    for t in range(T):
        prev_inv = initial_inventory if t == 0 else inventory[t - 1]
        net = production[t] - (inventory[t] - prev_inv)
        if not _close(net, demands[t]):
            raise HandoffConservationError(
                f"period {t} net shipment {net!r} ≠ recorded demand {demands[t]!r}"
            )
        net_shipments.append(max(0.0, net))

    total_demand = sum(demands)
    total_shipped = sum(net_shipments)
    # aggregate identity: sum(production) − final_inventory + initial = sum(demand)
    total_production = sum(production)
    final_inventory = inventory[-1] if inventory else initial_inventory
    verify_conservation(
        total_shipped,
        total_production - final_inventory + initial_inventory,
        served_total_name="total_shipped",
        demand_total_name="total_production-final_inventory+initial",
    )
    verify_conservation(total_shipped, total_demand,
                        served_total_name="total_shipped",
                        demand_total_name="total_demand")

    depot_coord = client_data.get("depot_coord", (0.0, 0.0))
    clients: list[dict[str, Any]] = []
    for t, net in enumerate(net_shipments):
        if net <= CONSERVATION_TOL:
            continue
        coord = client_data.get("client_coords", {}).get(t, (float(t) * 20.0, 0.0))
        clients.append({
            "id": t + 1,
            "name": f"P{t}",
            "x": float(coord[0]),
            "y": float(coord[1]),
            "demand": round(net, 6),
            "tw_early": int(client_data.get("tw_early", 0)),
            "tw_late": int(client_data.get("tw_late", 999999)),
            "service_duration": int(client_data.get("service_duration", 0)),
        })

    routing_input: dict[str, Any] = {
        "name": f"irp_routing_{inventory_sol.get('problem_id', 'inventory')}",
        "depot": {
            "id": 0,
            "name": "Depot",
            "x": float(depot_coord[0]),
            "y": float(depot_coord[1]),
            "tw_early": int(client_data.get("depot_tw_early", 0)),
            "tw_late": int(client_data.get("depot_tw_late", 999999)),
            "service_duration": int(client_data.get("depot_service_duration", 0)),
        },
        "clients": clients,
        "capacity": float(client_data.get("vehicle_capacity", client_data.get("capacity", 200))),
        "vehicles": int(client_data.get("num_vehicles", client_data.get("vehicles", 25))),
        "conservation": {
            "total_demand": round(total_demand, 6),
            "total_shipped": round(total_shipped, 6),
            "total_production": round(total_production, 6),
            "final_inventory": round(final_inventory, 6),
            "initial_inventory": round(initial_inventory, 6),
            "num_periods": T,
            "num_shipment_clients": len(clients),
            "checks": ["period_mass_balance", "aggregate_production_identity"],
        },
    }
    return routing_input


def transform_scheduling_to_inventory(
    scheduling_sol: Mapping[str, Any],
    period_duration: float | None = None,
) -> dict[str, Any]:
    """Transform a JSSP solution into a per-period inventory production plan.

    Each job's completion time (max end over its operations) is bucketed into
    periods of length ``period_duration`` (default: makespan / number of
    periods derived from the schedule).  Per-period ``production`` counts the
    number of jobs completed in that bucket; conservation requires the counts
    to sum to the total number of jobs.
    """
    if not isinstance(scheduling_sol, Mapping):
        raise CompositeLeadError("scheduling_sol must be a mapping")

    schedule = scheduling_sol.get("schedule") or []
    if not schedule:
        raise HandoffConservationError("scheduling solution has no schedule")

    # completion time per job
    completion: dict[int, float] = {}
    for op in schedule:
        job = int(op.get("job"))
        end = float(op.get("end"))
        if job not in completion or end > completion[job]:
            completion[job] = end
    jobs = sorted(completion)
    if not jobs:
        raise HandoffConservationError("scheduling solution has no jobs")

    # cross-check the recomputed job count against the envelope's declared count
    declared_num_jobs = scheduling_sol.get("num_jobs")
    if declared_num_jobs is not None and len(jobs) != int(declared_num_jobs):
        raise HandoffConservationError(
            f"recomputed job count {len(jobs)} ≠ declared num_jobs {declared_num_jobs}"
        )

    makespan = float(scheduling_sol.get("makespan") or max(completion.values()))
    if period_duration is None:
        period_duration = max(1.0, makespan / max(1, len(jobs)))
    if period_duration <= 0:
        raise CompositeLeadError("period_duration must be positive")

    num_periods = max(1, int(makespan // period_duration) + (1 if makespan % period_duration > 1e-9 else 0))
    production = [0] * num_periods
    period_output: list[list[int]] = [[] for _ in range(num_periods)]
    for job in jobs:
        ct = completion[job]
        bucket = min(num_periods - 1, int(ct // period_duration))
        production[bucket] += 1
        period_output[bucket].append(job)

    total_output = sum(production)
    if total_output != len(jobs):
        raise HandoffConservationError(
            f"production counts sum {total_output} ≠ num_jobs {len(jobs)}"
        )

    inventory_input: dict[str, Any] = {
        "name": f"prp_inventory_{scheduling_sol.get('problem_id', 'scheduling')}",
        "num_periods": num_periods,
        "period_duration": round(float(period_duration), 6),
        "production": production,
        "period_output": period_output,
        "job_completion_times": {str(j): round(completion[j], 6) for j in jobs},
        "makespan": round(makespan, 6),
        "conservation": {
            "total_output": total_output,
            "num_jobs": len(jobs),
            "num_periods": num_periods,
            "checks": ["job_count"],
        },
    }
    return inventory_input


def transform_facility_to_microgrid(
    facility_sol: Mapping[str, Any],
    microgrid_data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Transform open facilities into microgrid candidate dispatch sites.

    Each open facility becomes a candidate storage station with its capacity
    as the energy-storage bound.  Conservation: the number of candidate sites
    equals the number of open facilities, and total candidate capacity equals
    the sum of open-facility capacities.
    """
    if not isinstance(facility_sol, Mapping):
        raise CompositeLeadError("facility_sol must be a mapping")
    microgrid_data = dict(microgrid_data or {})

    open_facs = facility_sol.get("open_facilities") or []
    if not open_facs:
        raise HandoffConservationError("no open facilities for microgrid dispatch")

    candidates: list[dict[str, Any]] = []
    total_cap = 0.0
    for f in open_facs:
        cap = float(f.get("capacity", 0.0))
        total_cap += cap
        candidates.append({
            "site_id": int(f["facility_id"]),
            "name": f"Site_{f['facility_id']}",
            "storage_capacity_kwh": cap,
            "fixed_cost": float(f.get("fixed_cost", 0.0)),
        })

    microgrid_input: dict[str, Any] = {
        "name": f"microgrid_facility_{facility_sol.get('problem_id', 'facility')}",
        "candidate_sites": candidates,
        "num_sites": len(candidates),
        "total_storage_capacity_kwh": round(total_cap, 6),
        "tariff_profile": microgrid_data.get("tariff_profile", []),
        "load_profile": microgrid_data.get("load_profile", []),
        "pv_profile": microgrid_data.get("pv_profile", []),
        "conservation": {
            "num_sites": len(candidates),
            "num_open_facilities": len(open_facs),
            "total_storage_capacity_kwh": round(total_cap, 6),
            "checks": ["site_count", "capacity_sum"],
        },
    }
    return microgrid_input


#: (upstream, downstream) → (transformer, config_key).  ``config_key`` names
#: the ``problem_config`` sub-dict passed as the transformer's second argument.
HANDOFF_TRANSFORMERS: dict[tuple[str, str], tuple[Callable[..., dict], str | None]] = {
    ("facility", "routing"): (transform_facility_to_routing, "customer_data"),
    ("inventory", "routing"): (transform_inventory_to_routing, "client_data"),
    ("scheduling", "inventory"): (transform_scheduling_to_inventory, None),
    ("facility", "microgrid"): (transform_facility_to_microgrid, "microgrid_data"),
}


# ---------------------------------------------------------------------------
# Executor invocation
# ---------------------------------------------------------------------------

def _executor_arity(executor: Callable[..., dict]) -> int:
    """Return how many positional args ``executor`` accepts (0, 1 or 2+).

    Used to call domain executors with the arity they actually declare.  Catching
    ``TypeError`` from inside the call instead would mask genuine bugs in the
    executor body (any internal ``TypeError`` would look like an arity mismatch).
    """
    try:
        sig = inspect.signature(executor)
    except (TypeError, ValueError):
        return 2  # builtins / C callables: assume (input, config)
    if any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values()):
        return 2
    positional = [p for p in sig.parameters.values()
                  if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                                inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    return len(positional)


def _call_domain_executor(
    executor: Callable[..., dict],
    domain_input: Any,
    config: Mapping[str, Any],
    domain: str = "",
) -> dict[str, Any]:
    """Invoke a domain executor with the correct arity and validate the envelope."""
    if _executor_arity(executor) >= 2:
        result = executor(domain_input, config)
    else:
        result = executor(domain_input)
    if not isinstance(result, Mapping):
        raise CompositeLeadError(
            f"executor for {domain or getattr(executor, '__name__', executor)!r} "
            f"returned non-mapping {type(result).__name__}"
        )
    return dict(result)


# ---------------------------------------------------------------------------
# Composite supervisor state
# ---------------------------------------------------------------------------
class CompositeSupervisorState(MessagesState):
    """State schema for the composite lead pipeline.

    Extends LangGraph's ``MessagesState`` with the composite-orchestration
    fields: the composite class, the dependency-topological domain chain, the
    current stage index, per-domain result envelopes, cross-domain SHA-256
    lineage, the aggregated composite objective and the final validation
    report.
    """

    composite_type: str = COMPOSITE_CUSTOM
    domain_chain: list[str] = []
    current_domain_idx: int = 0
    domain_results: dict[str, Any] = {}
    domain_inputs: dict[str, Any] = {}
    cross_domain_lineage: list[dict[str, Any]] = []
    composite_objective: float = 0.0
    composite_report: dict[str, Any] = {}
    problem_config: dict[str, Any] = {}
    error: str = ""


# ---------------------------------------------------------------------------
# Composite objective
# ---------------------------------------------------------------------------
def compute_composite_objective(domain_results: Mapping[str, Mapping[str, Any]]) -> float:
    """Sum the independently recomputed per-domain objectives.

    Only non-negative, non-``None`` objectives are added (Numbers Truth: the
    composite value is the sum of solver-reported values, never invented).
    Non-numeric objective values are excluded rather than crashing the
    aggregation — the raw value stays visible in the per-stage report.
    """
    total = 0.0
    for result in domain_results.values():
        obj = result.get("objective")
        if obj is None or isinstance(obj, bool):
            continue
        try:
            value = float(obj)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            total += value
    return round(total, 6)


# ---------------------------------------------------------------------------
# Default domain executors (solver-backed, lazy-imported)
# ---------------------------------------------------------------------------
def default_facility_executor(
    domain_input: Mapping[str, Any] | None, config: Mapping[str, Any]
) -> dict[str, Any]:
    """Default facility executor → ``solve_facility_location``."""
    params = dict(config.get("facility", {}))
    if domain_input:
        params.update(domain_input)
    from solve_facility import solve_facility_location

    return solve_facility_location(**params)


def default_routing_executor(
    domain_input: Mapping[str, Any] | None, config: Mapping[str, Any]
) -> dict[str, Any]:
    """Default routing executor → ``solve_pyvrp``.

    The ``domain_input`` is the routing instance built by a handoff
    transformer; ``config['routing']`` supplies solver kwargs (time limit,
    engine, problem id).
    """
    params = dict(config.get("routing", {}))
    instance_data = domain_input if domain_input is not None else params.pop("instance_data", None)
    from solve_pyvrp import solve_pyvrp

    return solve_pyvrp(instance_data=instance_data, **params)


def default_inventory_executor(
    domain_input: Mapping[str, Any] | None, config: Mapping[str, Any]
) -> dict[str, Any]:
    """Default inventory executor → ``solve_lot_sizing``."""
    params = dict(config.get("inventory", {}))
    if domain_input:
        params.update(domain_input)
    from solve_lot_sizing import solve_lot_sizing

    return solve_lot_sizing(**params)


def default_scheduling_executor(
    domain_input: Mapping[str, Any] | None, config: Mapping[str, Any]
) -> dict[str, Any]:
    """Default scheduling executor → ``solve_jssp``."""
    params = dict(config.get("scheduling", {}))
    if domain_input:
        params.update(domain_input)
    from solve_jssp import solve_jssp

    return solve_jssp(**params)


def default_microgrid_executor(
    domain_input: Mapping[str, Any] | None, config: Mapping[str, Any]
) -> dict[str, Any]:
    """Default microgrid executor.

    Delegates to ``solve_microgrid.run_full_pipeline`` when a ``case_dir`` is
    configured; otherwise returns an honest ``NOT_SOLVED`` envelope (Numbers
    Truth: never invent a microgrid objective).
    """
    params = dict(config.get("microgrid", {}))
    case_dir = params.get("case_dir")
    if case_dir:
        from solve_microgrid import run_full_pipeline
        from pathlib import Path

        return run_full_pipeline(Path(case_dir), out_dir=params.get("out_dir"))
    return {
        "problem_id": params.get("problem_id", "microgrid_not_solved"),
        "problem_class": "microgrid_dispatch",
        "status": "NOT_SOLVED",
        "objective": None,
        "lower_bound": None,
        "optimality_gap": None,
        "solver": "composite-lead-default",
        "source": "orpath.agents.composite_lead",
        "meta": {"note": "no microgrid case_dir configured; objective not invented"},
    }


#: Canonical domain → default executor.
DEFAULT_DOMAIN_EXECUTORS: dict[str, Callable[[Mapping | None, Mapping], dict]] = {
    "facility": default_facility_executor,
    "routing": default_routing_executor,
    "inventory": default_inventory_executor,
    "scheduling": default_scheduling_executor,
    "microgrid": default_microgrid_executor,
}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class CompositeLeadOrchestrator:
    """Deterministic pipeline engine for composite OR problems.

    Walks ``domain_chain`` in dependency-topological order, calling each
    domain's executor, applying the matching handoff transformer, verifying
    conservation, recording SHA-256 lineage, and aggregating the composite
    objective + validation report.

    Parameters
    ----------
    composite_type
        One of ``COMPOSITE_TYPES`` (or ``"CUSTOM"`` with an explicit chain).
    domain_chain
        Ordered list of domain identifiers.  Defaults to the canonical chain
        for ``composite_type``.
    domain_executors
        Mapping ``domain → callable(domain_input, config) -> solution``.
        Missing domains fall back to :data:`DEFAULT_DOMAIN_EXECUTORS`.
    """

    def __init__(
        self,
        composite_type: str = COMPOSITE_CUSTOM,
        domain_chain: list[str] | None = None,
        domain_executors: Mapping[str, Callable[..., dict]] | None = None,
    ) -> None:
        if composite_type not in COMPOSITE_TYPES:
            raise CompositeLeadError(
                f"unknown composite_type {composite_type!r}; expected one of {COMPOSITE_TYPES}"
            )
        self.composite_type = composite_type
        if domain_chain is None:
            domain_chain = list(COMPOSITE_DOMAIN_CHAINS.get(composite_type, []))
        if not domain_chain:
            raise CompositeLeadError(
                f"composite_type {composite_type!r} requires an explicit domain_chain"
            )
        unknown = [d for d in domain_chain if d not in DEFAULT_DOMAIN_EXECUTORS]
        if unknown:
            raise CompositeLeadError(
                f"unknown domain(s) in chain: {unknown}; "
                f"known domains: {sorted(DEFAULT_DOMAIN_EXECUTORS)}"
            )
        self.domain_chain = list(domain_chain)
        self.executors: dict[str, Callable[..., dict]] = dict(DEFAULT_DOMAIN_EXECUTORS)
        if domain_executors:
            self.executors.update(domain_executors)

    # -- internal helpers ----------------------------------------------------
    def _transformer_for(self, upstream: str, downstream: str) -> tuple[Callable[..., dict], str | None]:
        key = (upstream, downstream)
        if key not in HANDOFF_TRANSFORMERS:
            raise CompositeLeadError(
                f"no handoff transformer registered for {upstream} → {downstream}"
            )
        return HANDOFF_TRANSFORMERS[key]

    def _run_stage(
        self,
        domain: str,
        domain_input: Any,
        config: Mapping[str, Any],
    ) -> dict[str, Any]:
        executor = self.executors[domain]
        return _call_domain_executor(executor, domain_input, config, domain=domain)

    # -- public API ----------------------------------------------------------
    def run(
        self,
        problem_config: Mapping[str, Any] | None = None,
        pre_stage_hook: Callable[[dict, str], None] | None = None,
    ) -> dict[str, Any]:
        """Execute the full composite pipeline and return the final state.

        ``pre_stage_hook(state, domain)`` is invoked immediately before each
        stage's input-integrity check (and thus before the executor runs).
        It exists as a test seam for tamper-interception tests and as a
        production monitoring hook.
        """
        config = dict(problem_config or {})
        state: dict[str, Any] = {
            "composite_type": self.composite_type,
            "domain_chain": list(self.domain_chain),
            "current_domain_idx": 0,
            "domain_results": {},
            "domain_inputs": {},
            "cross_domain_lineage": [],
            "composite_objective": 0.0,
            "composite_report": {},
            "problem_config": config,
            "error": "",
        }

        for idx, domain in enumerate(self.domain_chain):
            state["current_domain_idx"] = idx
            domain_input = state["domain_inputs"].get(domain)

            # --- input integrity (tamper interception) ---------------------
            if pre_stage_hook is not None and idx > 0:
                pre_stage_hook(state, domain)
            if idx > 0:
                expected_hash = state["cross_domain_lineage"][-1]["downstream_sha256"]
                verify_input_integrity(
                    expected_hash,
                    domain_input,
                    upstream_domain=self.domain_chain[idx - 1],
                    downstream_domain=domain,
                )

            # --- execute the domain ----------------------------------------
            sol = self._run_stage(domain, domain_input, config)
            state["domain_results"][domain] = sol

            # --- handoff to the next domain --------------------------------
            if idx + 1 < len(self.domain_chain):
                downstream = self.domain_chain[idx + 1]
                transformer, config_key = self._transformer_for(domain, downstream)
                extra = config.get(config_key, {}) if config_key else {}
                # scheduling→inventory accepts period_duration from config
                if domain == "scheduling" and downstream == "inventory":
                    extra = dict(extra)
                    extra.setdefault("period_duration", config.get("period_duration"))
                if domain == "scheduling" and downstream == "inventory":
                    downstream_input = transformer(
                        sol, period_duration=(extra or {}).get("period_duration")
                    )
                else:
                    downstream_input = transformer(sol, extra)
                state["domain_inputs"][downstream] = downstream_input
                state["cross_domain_lineage"].append(
                    record_lineage(domain, downstream, sol, downstream_input,
                                   downstream_input.get("conservation"))
                )

        # --- aggregate composite objective + report -------------------------
        state["composite_objective"] = compute_composite_objective(state["domain_results"])
        state["composite_report"] = self._build_report(state)
        state["current_domain_idx"] = len(self.domain_chain)
        return state

    def _build_report(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Build the comprehensive composite validation report."""
        domains: dict[str, dict[str, Any]] = {}
        for domain in self.domain_chain:
            sol = state["domain_results"].get(domain, {})
            domains[domain] = {
                "status": sol.get("status"),
                "objective": sol.get("objective"),
                "problem_class": sol.get("problem_class"),
                "solver": sol.get("solver"),
            }

        lineage_problems = verify_lineage_chain(state.get("cross_domain_lineage", []))
        conservation_ok = all(
            entry.get("conservation", {}).get("checks")
            for entry in state.get("cross_domain_lineage", [])
        )
        all_feasible = all(
            sol.get("status") in ("OPTIMAL", "FEASIBLE")
            for sol in state["domain_results"].values()
        )

        return {
            "composite_type": state["composite_type"],
            "domain_chain": list(self.domain_chain),
            "stages": domains,
            "composite_objective": state.get("composite_objective", 0.0),
            "lineage_entries": len(state.get("cross_domain_lineage", [])),
            "lineage_consistent": not lineage_problems,
            "lineage_problems": lineage_problems,
            "conservation_verified": bool(conservation_ok) and bool(state.get("cross_domain_lineage")),
            "all_stages_feasible": bool(all_feasible),
            "overall_status": (
                "COMPOSITE_FEASIBLE"
                if all_feasible and not lineage_problems
                else "COMPOSITE_INFEASIBLE"
            ),
        }


# ---------------------------------------------------------------------------
# LangGraph pipeline builder
# ---------------------------------------------------------------------------
def _make_domain_node(
    domain: str,
    idx: int,
    total: int,
    executor: Callable[..., dict],
) -> Callable[[dict], dict]:
    """Build a LangGraph node that runs one composite domain stage."""

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        config = state.get("problem_config", {}) or {}
        domain_input = (state.get("domain_inputs") or {}).get(domain)

        # input integrity (tamper interception) for every stage after the first
        prev_lineage = state.get("cross_domain_lineage") or []
        chain = state.get("domain_chain") or []
        if idx > 0 and prev_lineage:
            verify_input_integrity(
                prev_lineage[-1]["downstream_sha256"],
                domain_input,
                upstream_domain=chain[idx - 1] if idx - 1 < len(chain) else domain,
                downstream_domain=domain,
            )

        sol = _call_domain_executor(executor, domain_input, config, domain=domain)

        domain_results = dict(state.get("domain_results") or {})
        domain_results[domain] = sol

        lineage = list(state.get("cross_domain_lineage") or [])
        domain_inputs = dict(state.get("domain_inputs") or {})

        if idx + 1 < total:
            downstream = None
            # downstream is the next domain in the chain stored on state
            chain = state.get("domain_chain") or []
            if idx + 1 < len(chain):
                downstream = chain[idx + 1]
            if downstream is None:
                raise CompositeLeadError(f"no downstream domain for {domain!r}")
            transformer, config_key = HANDOFF_TRANSFORMERS.get(
                (domain, downstream), (None, None)
            )
            if transformer is None:
                raise CompositeLeadError(
                    f"no handoff transformer registered for {domain} → {downstream}"
                )
            extra = config.get(config_key, {}) if config_key else {}
            if domain == "scheduling" and downstream == "inventory":
                extra = dict(extra)
                extra.setdefault("period_duration", config.get("period_duration"))
            if domain == "scheduling" and downstream == "inventory":
                downstream_input = transformer(
                    sol, period_duration=(extra or {}).get("period_duration")
                )
            else:
                downstream_input = transformer(sol, extra)
            domain_inputs[downstream] = downstream_input
            lineage.append(
                record_lineage(domain, downstream, sol, downstream_input,
                               downstream_input.get("conservation"))
            )

        return {
            "domain_results": domain_results,
            "domain_inputs": domain_inputs,
            "cross_domain_lineage": lineage,
            "current_domain_idx": idx + 1,
        }

    node.__name__ = f"{COMPOSITE_DOMAIN_NODE_PREFIX}_{domain}"
    return node


def _composite_lead_node(state: Mapping[str, Any]) -> dict[str, Any]:
    """Final node: aggregate composite objective + validation report."""
    domain_results = state.get("domain_results") or {}
    composite_objective = compute_composite_objective(domain_results)

    chain = state.get("domain_chain") or []
    stages: dict[str, dict[str, Any]] = {}
    for domain in chain:
        sol = domain_results.get(domain, {})
        stages[domain] = {
            "status": sol.get("status"),
            "objective": sol.get("objective"),
            "problem_class": sol.get("problem_class"),
            "solver": sol.get("solver"),
        }

    lineage = state.get("cross_domain_lineage") or []
    lineage_problems = verify_lineage_chain(lineage)
    conservation_ok = all(
        entry.get("conservation", {}).get("checks") for entry in lineage
    )
    all_feasible = all(
        sol.get("status") in ("OPTIMAL", "FEASIBLE") for sol in domain_results.values()
    )

    report = {
        "composite_type": state.get("composite_type", COMPOSITE_CUSTOM),
        "domain_chain": list(chain),
        "stages": stages,
        "composite_objective": composite_objective,
        "lineage_entries": len(lineage),
        "lineage_consistent": not lineage_problems,
        "lineage_problems": lineage_problems,
        "conservation_verified": bool(conservation_ok) and bool(lineage),
        "all_stages_feasible": bool(all_feasible),
        "overall_status": (
            "COMPOSITE_FEASIBLE"
            if all_feasible and not lineage_problems
            else "COMPOSITE_INFEASIBLE"
        ),
    }
    return {
        "composite_objective": composite_objective,
        "composite_report": report,
        "current_domain_idx": len(chain),
    }


def build_composite_supervisor_graph(
    composite_type: str = COMPOSITE_CUSTOM,
    domain_chain: list[str] | None = None,
    domain_executors: Mapping[str, Callable[..., dict]] | None = None,
) -> StateGraph:
    """Build the un-compiled composite supervisor ``StateGraph``.

    Each domain in ``domain_chain`` becomes a deterministic stage node wired
    in dependency-topological order; a final ``COMPOSITE_LEAD_NAME`` node
    aggregates the composite objective and validation report.

    Parameters
    ----------
    composite_type
        Composite class identifier (used for validation + reporting).
    domain_chain
        Ordered domain identifiers.  Defaults to the canonical chain for
        ``composite_type``.
    domain_executors
        Mapping ``domain → callable(domain_input, config) -> solution``.
        Missing domains fall back to :data:`DEFAULT_DOMAIN_EXECUTORS`.

    Returns
    -------
    StateGraph
    """
    # validate + normalise the chain (same rules as the orchestrator)
    if composite_type not in COMPOSITE_TYPES:
        raise CompositeLeadError(
            f"unknown composite_type {composite_type!r}; expected one of {COMPOSITE_TYPES}"
        )
    if domain_chain is None:
        domain_chain = list(COMPOSITE_DOMAIN_CHAINS.get(composite_type, []))
    if not domain_chain:
        raise CompositeLeadError(
            f"composite_type {composite_type!r} requires an explicit domain_chain"
        )
    unknown = [d for d in domain_chain if d not in DEFAULT_DOMAIN_EXECUTORS]
    if unknown:
        raise CompositeLeadError(f"unknown domain(s) in chain: {unknown}")

    executors = dict(DEFAULT_DOMAIN_EXECUTORS)
    if domain_executors:
        executors.update(domain_executors)

    total = len(domain_chain)
    graph = StateGraph(CompositeSupervisorState)

    # stage nodes
    for idx, domain in enumerate(domain_chain):
        graph.add_node(
            f"{COMPOSITE_DOMAIN_NODE_PREFIX}_{domain}",
            _make_domain_node(domain, idx, total, executors[domain]),
        )

    # final composite lead node
    graph.add_node(COMPOSITE_LEAD_NAME, _composite_lead_node)

    # wire START → stage0 → stage1 → ... → lead → END
    nodes = [f"{COMPOSITE_DOMAIN_NODE_PREFIX}_{d}" for d in domain_chain]
    prev = START
    for node_name in nodes:
        graph.add_edge(prev, node_name)
        prev = node_name
    graph.add_edge(prev, COMPOSITE_LEAD_NAME)
    graph.add_edge(COMPOSITE_LEAD_NAME, END)

    return graph


def build_compiled_composite_supervisor(
    composite_type: str = COMPOSITE_CUSTOM,
    domain_chain: list[str] | None = None,
    domain_executors: Mapping[str, Callable[..., dict]] | None = None,
    checkpointer: Any = None,
) -> CompiledStateGraph:
    """Build and compile the composite supervisor graph."""
    graph = build_composite_supervisor_graph(
        composite_type=composite_type,
        domain_chain=domain_chain,
        domain_executors=domain_executors,
    )
    return graph.compile(checkpointer=checkpointer)
