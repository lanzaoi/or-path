"""Phase 2 / Task 2.2 — PyVRP Solomon / VRPLIB Benchmark Gate (Numbers Truth).

Dedicated unit suite for tools/solve_pyvrp.py (PyVRP HGS + ALNS fallback)
against the Solomon VRPTW benchmark and the built-in VRPPDTW demo:

* Solomon C101-25 (VRPTW): 25 customers, published optimum 192.
* VRPPDTW PDP demo: 4 paired shipments with pickup-before-delivery.
* ALNS engine fallback on a 15-customer C101 slice.

Every case asserts the standard solution envelope (status / objective /
lower_bound / optimality_gap / routes / metrics), independently recomputes
the route constraints (depot return, load capacity, time windows, pickup
precedence) from raw problem data, and re-verifies the full result through
the independent validator tools/validators/extended_solvers.py::validate_pyvrp.

Heuristic honesty (Numbers Truth): PyVRP HGS / ALNS produce no optimality
proof, so the envelope must carry status FEASIBLE (never a forged OPTIMAL)
and lower_bound / optimality_gap None — never invented numbers.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from solve_pyvrp import solve_pyvrp
from validators.extended_solvers import validate_pyvrp

_ROOT = TOOLS.parent
C101_PATH = _ROOT / "fixtures" / "benchmarks" / "vrp" / "c101.txt"

# Published Solomon C101 optimum for the first 25 customers (VRPTW).
C101_25_OPTIMUM = 192

PYVRP_CHECKS = {
    "pyvrp_status_feasible",
    "pyvrp_depot_endpoints",
    "pyvrp_client_visits_complete",
    "pyvrp_capacity_respected",
    "pyvrp_time_windows_respected",
    "pyvrp_distance_matches_objective",
}

PYVRP_PDP_CHECKS = {
    "pyvrp_status_feasible",
    "pyvrp_depot_endpoints",
    "pyvrp_pdp_precedence_respected",
    "pyvrp_capacity_respected",
    "pyvrp_time_windows_respected",
    "pyvrp_distance_matches_objective",
}


@pytest.fixture(scope="module")
def c101_sol() -> dict:
    """Solve Solomon C101-25 once per module run (Numbers Truth: solver-only)."""
    return solve_pyvrp(
        solomon_path=C101_PATH,
        max_customers=25,
        time_limit_s=3.0,
        problem_id="task22_c101_25",
    )


@pytest.fixture(scope="module")
def pdp_sol() -> dict:
    """Solve the VRPPDTW pickup-and-delivery demo once per module run."""
    return solve_pyvrp(is_pdp=True, time_limit_s=2.0, problem_id="task22_pdp_demo")


@pytest.fixture(scope="module")
def alns_sol() -> dict:
    """Solve a 15-customer C101 slice with the ALNS fallback engine."""
    return solve_pyvrp(
        solomon_path=C101_PATH,
        max_customers=15,
        time_limit_s=1.5,
        engine="alns",
        problem_id="task22_alns_15",
    )


# ---------------------------------------------------------------------------
# 1. Solomon C101-25 benchmark: envelope contract & published optimum
# ---------------------------------------------------------------------------
def test_c101_25_envelope_contract(c101_sol):
    sol = c101_sol
    for key in ("status", "objective", "lower_bound", "optimality_gap",
                "problem_id", "problem_class", "routes", "metrics"):
        assert key in sol, f"envelope missing key '{key}'"
    assert sol["problem_class"] == "pyvrp"
    assert sol["status"] in ("FEASIBLE", "OPTIMAL")
    assert isinstance(sol["objective"], (int, float))
    assert sol["objective"] > 0


def test_c101_25_matches_published_optimum(c101_sol):
    """Numbers Truth: objective comes from the solver and equals the
    published Solomon C101-25 optimum (192), reproducibly."""
    sol = c101_sol
    assert sol["status"] == "FEASIBLE", (
        "HGS is a heuristic: status must be FEASIBLE, never a forged OPTIMAL"
    )
    assert sol["objective"] == C101_25_OPTIMUM, (
        f"objective {sol['objective']} != published optimum {C101_25_OPTIMUM}"
    )
    assert sol["num_clients"] == 25
    assert sol["num_vehicles_used"] >= 1


def test_c101_25_heuristic_bounds_honest(c101_sol):
    """Heuristic engines carry no proof bounds — None, never invented."""
    sol = c101_sol
    assert sol["lower_bound"] is None
    assert sol["optimality_gap"] is None
    assert sol["metrics"]["lower_bound"] is None
    assert sol["metrics"]["optimality_gap"] is None


# ---------------------------------------------------------------------------
# 2. Route standardization: visit sequence, load usage, timing
# ---------------------------------------------------------------------------
def test_c101_25_route_contract(c101_sol):
    sol = c101_sol
    assert sol["routes"], "expected at least one route"
    for r in sol["routes"]:
        # Standardized route keys (ADR-0002 envelope).
        for key in ("vehicle", "route", "distance", "load", "timeline"):
            assert key in r, f"route missing key '{key}'"
        assert isinstance(r["vehicle"], int)
        assert isinstance(r["route"], list) and len(r["route"]) >= 2
        assert isinstance(r["load"], (int, float))
        assert isinstance(r["timeline"], list) and len(r["timeline"]) >= 2
        # route sequence mirrors the timeline location indices.
        assert r["route"] == [v["location_idx"] for v in r["timeline"]]
        # timeline carries timing for every stop.
        for v in r["timeline"]:
            assert "start_time" in v and "end_time" in v


def test_c101_25_every_client_visited_once(c101_sol):
    sol = c101_sol
    visited: list[str] = []
    for r in sol["routes"]:
        for v in r["visits"]:
            if v["type"] == "client":
                visited.append(v["name"])
    assert sorted(visited) == sorted(c["name"] for c in sol["raw_clients"])


# ---------------------------------------------------------------------------
# 3. Vehicle load capacity is never violated on any route (independent recompute)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fixture_name", ["c101_sol", "pdp_sol"])
def test_capacity_never_violated(fixture_name, request):
    sol = request.getfixturevalue(fixture_name)
    capacity = sol["vehicle_capacity"]
    for r in sol["routes"]:
        running = 0
        for v in r["visits"]:
            if v["type"] == "client":
                running += int(v.get("demand", 0))
            elif v["type"] == "pickup":
                running += int(v.get("amount", 0))
            elif v["type"] == "delivery":
                running -= int(v.get("amount", 0))
            assert 0 <= running <= capacity, (
                f"route {r['vehicle']}: running load {running} outside "
                f"[0, {capacity}] after stop {v.get('name')}"
            )
        # Route-level load equals the recomputed final load.
        assert r["load"] == running


# ---------------------------------------------------------------------------
# 4. Depot return & arrival timing constraints (independent recompute)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fixture_name", ["c101_sol", "pdp_sol"])
def test_depot_return_and_timing(fixture_name, request):
    sol = request.getfixturevalue(fixture_name)
    depot_tw = (sol["raw_depot"]["tw_early"], sol["raw_depot"]["tw_late"])

    for r in sol["routes"]:
        visits = r["visits"]
        # Depot return: route starts and ends at the depot.
        assert visits[0]["type"] == "depot", f"route {r['vehicle']} does not start at depot"
        assert visits[-1]["type"] == "depot", f"route {r['vehicle']} does not return to depot"

        # Chronology: each stop starts at/after the previous stop ends.
        for prev, curr in zip(visits, visits[1:]):
            assert curr["start_time"] >= prev["end_time"], (
                f"route {r['vehicle']} chronology violated: "
                f"{prev['name']} end {prev['end_time']} > {curr['name']} start {curr['start_time']}"
            )

        # Client time windows: PyVRP enforces the service START within
        # [tw_early, tw_late] (service duration may extend past tw_late).
        client_tw = {c["name"]: (c["tw_early"], c["tw_late"]) for c in sol["raw_clients"]}
        shipment_tw: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {}
        for s in sol["raw_shipments"]:
            shipment_tw[s["name"]] = (
                (s["pickup"]["tw_early"], s["pickup"]["tw_late"]),
                (s["delivery"]["tw_early"], s["delivery"]["tw_late"]),
            )
        for v in visits:
            v_type = v["type"]
            if v_type == "client":
                tw = client_tw[v["name"]]
            elif v_type == "pickup":
                tw = shipment_tw[v["name"]][0]
            elif v_type == "delivery":
                tw = shipment_tw[v["name"]][1]
            else:  # depot
                tw = depot_tw
            assert tw[0] <= v["start_time"] <= tw[1], (
                f"route {r['vehicle']} stop {v['name']}: start {v['start_time']} "
                f"outside [{tw[0]}, {tw[1]}]"
            )

        # Depot return arrival within the depot time window.
        assert visits[-1]["start_time"] <= depot_tw[1], (
            f"route {r['vehicle']}: depot return {visits[-1]['start_time']} > {depot_tw[1]}"
        )


# ---------------------------------------------------------------------------
# 5. PDP benchmark: pickup-before-delivery precedence
# ---------------------------------------------------------------------------
def test_pdp_demo_envelope_and_shipments(pdp_sol):
    sol = pdp_sol
    assert sol["status"] == "FEASIBLE"
    assert sol["num_shipments"] == 4
    assert sol["objective"] > 0
    assert sol["lower_bound"] is None and sol["optimality_gap"] is None
    assert sol["metrics"]["num_shipments"] == 4


def test_pdp_pickup_before_delivery(pdp_sol):
    sol = pdp_sol
    # Each shipment's pickup must precede its delivery on the same vehicle.
    for r in sol["routes"]:
        for s in sol["raw_shipments"]:
            names = [v["name"] for v in r["visits"] if v["type"] in ("pickup", "delivery")]
            if s["name"] not in names:
                continue
            p_idx = next(i for i, v in enumerate(r["visits"])
                         if v["type"] == "pickup" and v["name"] == s["name"])
            d_idx = next(i for i, v in enumerate(r["visits"])
                         if v["type"] == "delivery" and v["name"] == s["name"])
            assert p_idx < d_idx, (
                f"shipment {s['name']}: delivery at stop {d_idx} before pickup at {p_idx}"
            )
    # Every shipment is served exactly once across the fleet.
    served = {
        v["name"]
        for r in sol["routes"]
        for v in r["visits"]
        if v["type"] in ("pickup", "delivery")
    }
    assert served == {s["name"] for s in sol["raw_shipments"]}


# ---------------------------------------------------------------------------
# 6. ALNS fallback engine: same envelope standard
# ---------------------------------------------------------------------------
def test_alns_engine_envelope(alns_sol):
    sol = alns_sol
    assert sol["solver"] == "alns-vrp"
    assert sol["status"] in ("FEASIBLE", "OPTIMAL")
    assert sol["num_clients"] == 15
    assert sol["objective"] > 0
    assert sol["lower_bound"] is None and sol["optimality_gap"] is None
    assert "metrics" in sol
    for r in sol["routes"]:
        for key in ("vehicle", "route", "distance", "load", "timeline"):
            assert key in r


# ---------------------------------------------------------------------------
# 7. Independent validation via tools.validators.extended_solvers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fixture_name,expected_checks", [
    ("c101_sol", PYVRP_CHECKS),
    ("pdp_sol", PYVRP_PDP_CHECKS),
    ("alns_sol", PYVRP_CHECKS),
])
def test_validate_pyvrp_ok(fixture_name, expected_checks, request):
    sol = request.getfixturevalue(fixture_name)
    checks = validate_pyvrp(f"task22_{fixture_name}", sol)
    assert checks, "validate_pyvrp returned no checks"
    failed = [c for c in checks if not c.get("ok")]
    assert not failed, f"validate_pyvrp failed checks: {failed}"
    assert expected_checks <= {c["name"] for c in checks}


def test_validate_pyvrp_route_distance_matches_objective(c101_sol):
    """Numbers Truth: envelope objective == sum of route distances."""
    sol = c101_sol
    recomputed = sum(int(r["distance"]) for r in sol["routes"])
    assert recomputed == sol["objective"] == sol["total_distance"]
