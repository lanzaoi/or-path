"""Phase 2 / Task 2.4 — Facility Location: Beasley CFLP Benchmarks &
Haversine Distance Standardization (Numbers Truth).

Dedicated unit suite for tools/solve_facility.py against the published
J.E. Beasley OR-Library CFLP optima (capopt.txt):

* cap41 (16 facilities x 50 customers) → 1040444.375
* cap61 (16 facilities x 50 customers) → 932615.75
* cap71 (16 facilities x 50 customers) → 932615.75

Every case asserts the standard solution envelope
(status / objective / lower_bound / optimality_gap / open_facilities /
assignments / costs / metrics), independently recomputes the objective,
facility loads and customer coverage from the **raw fixture rows** rather
than from the solver's own cost matrix, verifies the Haversine geodesic
distance standardization against an independent spherical-law-of-cosines
implementation, and re-verifies the full result through the independent
validator ``tools/validators/extended_solvers.py::validate_facility_location``.
"""
from __future__ import annotations

import math
from pathlib import Path
import sys

import pytest

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from solve_facility import (  # noqa: E402
    BEASLEY_KNOWN_OPTIMA,
    haversine_km,
    load_orlibrary_cflp,
    solve_facility_location,
    solve_two_echelon_scnd,
)
from validators.extended_solvers import validate_facility_location  # noqa: E402

FIXTURE_DIR = TOOLS.parent / "fixtures" / "benchmarks" / "orlib_cflp"

# Published optima, J.E. Beasley OR-Library capopt.txt. Mirrors
# solve_facility.BEASLEY_KNOWN_OPTIMA but is stated here independently so a
# regression in the solver's constant table cannot silently rewrite the gold.
BEASLEY_GOLD: dict[str, float] = {
    "cap41": 1040444.375,
    "cap61": 932615.75,
    "cap71": 932615.75,
}

BASE_CHECKS = {
    "facility_capacity_respected",
    "facility_cost_positive",
    "demand_fully_satisfied",
}
SSCFLP_CHECKS = BASE_CHECKS | {"single_source_binary"}

# Independent recomputation from raw total-cost rows carries the rounding of
# the fixture's 5-decimal shipping costs; cap41 shows a ~0.004 spread.
RAW_RECOMPUTE_TOL = 1e-2


# ---------------------------------------------------------------------------
# Independent fixture parser (deliberately does NOT use load_orlibrary_cflp's
# derived unit-cost matrix, so the objective is recomputed on a second path).
# ---------------------------------------------------------------------------
def raw_parse_cflp(name: str) -> dict:
    """Parse a Beasley cap* instance straight off disk.

    Returns raw ``total_cost`` rows exactly as published: ``total[j][i]`` is
    the *total* shipping cost to satisfy customer j's whole demand from
    facility i — not a per-unit cost.
    """
    toks = (FIXTURE_DIR / f"{name}.txt").read_text(encoding="utf-8").split()
    m, n = int(toks[0]), int(toks[1])
    idx = 2

    capacities = [float(toks[idx + 2 * i]) for i in range(m)]
    fixed_costs = [float(toks[idx + 2 * i + 1]) for i in range(m)]
    idx += 2 * m

    demands: list[float] = []
    total: list[list[float]] = []
    for j in range(n):
        demands.append(float(toks[idx]))
        idx += 1
        total.append([float(toks[idx + i]) for i in range(m)])
        idx += m

    return {
        "m": m,
        "n": n,
        "capacities": capacities,
        "fixed_costs": fixed_costs,
        "demands": demands,
        "total_cost": total,
    }


def _solve_benchmark(name: str) -> dict:
    raw = raw_parse_cflp(name)
    unit = [
        [raw["total_cost"][j][i] / raw["demands"][j] for j in range(raw["n"])]
        for i in range(raw["m"])
    ]
    return solve_facility_location(
        fixed_costs=raw["fixed_costs"],
        capacities=raw["capacities"],
        demands=raw["demands"],
        cost_matrix=unit,
        problem_id=f"orlib_{name}",
        known_optimum=BEASLEY_GOLD[name],
        time_limit_s=60,
    )


@pytest.fixture(scope="module")
def cap41() -> dict:
    return _solve_benchmark("cap41")


@pytest.fixture(scope="module")
def cap61() -> dict:
    return _solve_benchmark("cap61")


@pytest.fixture(scope="module")
def cap71() -> dict:
    return _solve_benchmark("cap71")


def _assert_validator_ok(sol: dict, expected: set[str]) -> list[dict]:
    checks = validate_facility_location(sol["problem_id"], sol)
    failed = [c for c in checks if not c.get("ok")]
    assert not failed, f"{sol['problem_id']}: failing checks -> {failed}"
    assert checks, "validate_facility_location returned no checks"
    missing = expected - {c["name"] for c in checks}
    assert not missing, f"{sol['problem_id']}: missing checks {sorted(missing)}"
    return checks


# ---------------------------------------------------------------------------
# 1. Published optima: objective, lower_bound, optimality_gap
# ---------------------------------------------------------------------------
def test_beasley_constants_agree_with_published_reference():
    assert BEASLEY_KNOWN_OPTIMA == BEASLEY_GOLD
    assert set(BEASLEY_GOLD) == {"cap41", "cap61", "cap71"}


def test_cap41_matches_published_optimum(cap41):
    """cap41 → 1040444.375, lower_bound anchored to the published optimum."""
    sol = cap41
    assert sol["status"] == "OPTIMAL", f"status={sol['status']}"
    assert sol["objective"] == 1040444.375, f"objective={sol['objective']}"
    assert sol["lower_bound"] == 1040444.375, f"lower_bound={sol['lower_bound']}"
    assert sol["optimality_gap"] == 0.0, f"gap={sol['optimality_gap']!r}"
    # A negative zero would serialize as "-0.0" — the contract demands 0.0.
    assert str(sol["optimality_gap"]) == "0.0"
    assert sol["known_optimum"] == 1040444.375


@pytest.mark.parametrize(
    "name,gold",
    [("cap61", 932615.75), ("cap71", 932615.75)],
)
def test_beasley_benchmark_family(cap41, cap61, cap71, name, gold):
    sol = {"cap61": cap61, "cap71": cap71}[name]
    assert sol["status"] == "OPTIMAL", f"{name} status={sol['status']}"
    assert sol["objective"] == gold, f"{name} objective={sol['objective']} != {gold}"
    assert sol["lower_bound"] == gold, f"{name} lower_bound={sol['lower_bound']} != {gold}"
    assert sol["optimality_gap"] == 0.0, f"{name} gap={sol['optimality_gap']!r}"
    assert str(sol["optimality_gap"]) == "0.0"


def test_benchmarks_do_not_regress_each_other(cap41, cap61, cap71):
    """cap61 and cap71 share a published optimum; cap41 is strictly worse."""
    assert cap61["objective"] == cap71["objective"] == 932615.75
    assert cap41["objective"] > cap61["objective"]


# ---------------------------------------------------------------------------
# 2. Envelope contract (ADR-0002 + Phase 2 bounds standardization)
# ---------------------------------------------------------------------------
def test_envelope_contract(cap41):
    sol = cap41
    for key in ("status", "objective", "lower_bound", "optimality_gap",
                "problem_id", "problem_class", "open_facilities",
                "assignments", "costs", "metrics"):
        assert key in sol, f"envelope missing key '{key}'"

    assert sol["problem_class"] == "facility_location"
    assert sol["problem_id"] == "orlib_cap41"
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert isinstance(sol["objective"], float) and sol["objective"] > 0
    assert isinstance(sol["lower_bound"], float)
    assert isinstance(sol["optimality_gap"], float)

    # Bounds invariant: lb <= objective and gap == objective - lb.
    assert sol["lower_bound"] <= sol["objective"] + 1e-6
    assert abs(sol["optimality_gap"] - (sol["objective"] - sol["lower_bound"])) <= 1e-4


def test_open_facilities_shapes(cap41):
    sol = cap41
    # list[int] view
    ids = sol["open_facility_ids"]
    assert isinstance(ids, list) and ids, "expected at least one open facility"
    assert all(isinstance(i, int) for i in ids), "open_facility_ids must be list[int]"
    assert ids == sorted(ids) and len(set(ids)) == len(ids)

    # rich detail view (validator + consumers rely on these fields)
    details = {f["facility_id"]: f for f in sol["open_facilities"]}
    assert set(details) == set(ids)
    for f in sol["open_facilities"]:
        assert set(f) >= {"facility_id", "capacity", "load", "fixed_cost", "utilization"}
        assert isinstance(f["facility_id"], int)
        assert f["utilization"] == pytest.approx(f["load"] / f["capacity"], abs=1e-4)


def test_assignments_shape(cap41):
    sol = cap41
    raw = raw_parse_cflp("cap41")
    assert isinstance(sol["assignments"], list)
    assert len(sol["assignments"]) == raw["n"]
    for a in sol["assignments"]:
        assert set(a) >= {"customer_id", "demand", "facility_id", "served_by"}
        assert isinstance(a["customer_id"], int)
        assert a["demand"] == pytest.approx(raw["demands"][a["customer_id"]])
        for s in a["served_by"]:
            assert set(s) >= {"facility_id", "fraction", "quantity"}
            assert s["quantity"] == pytest.approx(s["fraction"] * a["demand"], abs=1e-3)


def test_costs_breakdown(cap41):
    sol = cap41
    costs = sol["costs"]
    assert set(costs) == {"fixed", "variable", "total"}
    assert costs["fixed"] == pytest.approx(sol["total_fixed_cost"], abs=1e-4)
    assert costs["variable"] == pytest.approx(sol["total_transport_cost"], abs=1e-4)
    assert costs["total"] == pytest.approx(sol["objective"], abs=1e-4)
    assert costs["fixed"] + costs["variable"] == pytest.approx(costs["total"], abs=1e-3)


def test_metrics_contract(cap41):
    sol = cap41
    m = sol["metrics"]
    for key in ("objective", "lower_bound", "optimality_gap", "num_facilities",
                "num_customers", "num_open_facilities", "proven_optimal",
                "solver_status", "solve_seconds", "mode"):
        assert key in m, f"metrics missing key '{key}'"
    assert m["objective"] == sol["objective"] == 1040444.375
    assert m["lower_bound"] == sol["lower_bound"] == 1040444.375
    assert m["optimality_gap"] == sol["optimality_gap"] == 0.0
    assert m["num_facilities"] == 16
    assert m["num_customers"] == 50
    assert m["num_open_facilities"] == len(sol["open_facility_ids"])
    assert m["proven_optimal"] is True
    assert m["solver_status"] == "OPTIMAL"
    assert m["solve_seconds"] >= 0.0
    assert isinstance(m["esg"], dict)


# ---------------------------------------------------------------------------
# 3. Numbers Truth: objective recomputed from the raw fixture rows
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,gold", sorted(BEASLEY_GOLD.items()))
def test_objective_recomputed_from_raw_fixture(name, gold, request):
    sol = request.getfixturevalue(name)
    raw = raw_parse_cflp(name)

    fixed = sum(raw["fixed_costs"][i] for i in sol["open_facility_ids"])
    transport = 0.0
    for a in sol["allocations"]:
        j = a["customer_id"]
        for s in a["served_by"]:
            # RAW total-cost row: total cost for the whole demand of j from i.
            transport += raw["total_cost"][j][s["facility_id"]] * s["fraction"]

    recomputed = fixed + transport
    assert recomputed == pytest.approx(sol["objective"], abs=RAW_RECOMPUTE_TOL), (
        f"{name}: recomputed {recomputed} != solver objective {sol['objective']}"
    )
    assert recomputed == pytest.approx(gold, abs=RAW_RECOMPUTE_TOL)


def test_costs_match_independent_recomputation(cap41):
    """The declared cost split must be the objective, not a decorative copy."""
    sol = cap41
    raw = raw_parse_cflp("cap41")

    fixed = sum(raw["fixed_costs"][i] for i in sol["open_facility_ids"])
    transport = 0.0
    for a in sol["allocations"]:
        for s in a["served_by"]:
            transport += raw["total_cost"][a["customer_id"]][s["facility_id"]] * s["fraction"]

    assert sol["costs"]["fixed"] == pytest.approx(fixed, abs=1e-3)
    assert sol["costs"]["variable"] == pytest.approx(transport, abs=RAW_RECOMPUTE_TOL)


# ---------------------------------------------------------------------------
# 4. Facility capacity constraints (independently recomputed loads)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(BEASLEY_GOLD))
def test_facility_capacity_not_exceeded(name, request):
    sol = request.getfixturevalue(name)
    raw = raw_parse_cflp(name)

    for f in sol["open_facilities"]:
        i = f["facility_id"]
        # Recompute the load straight from raw demands and allocation splits.
        load = 0.0
        for a in sol["allocations"]:
            for s in a["served_by"]:
                if s["facility_id"] == i:
                    load += raw["demands"][a["customer_id"]] * s["fraction"]
        assert load <= raw["capacities"][i] + 1e-6, (
            f"{name}: facility {i} load {load} > capacity {raw['capacities'][i]}"
        )
        assert f["load"] == pytest.approx(load, abs=1e-2), (
            f"{name}: reported load {f['load']} != recomputed {load}"
        )

    # A closed facility must carry zero flow, and x[i,j] <= y[i] tightening.
    closed = set(range(raw["m"])) - set(sol["open_facility_ids"])
    for a in sol["allocations"]:
        for s in a["served_by"]:
            assert s["facility_id"] not in closed, (
                f"{name}: customer {a['customer_id']} served by closed facility {s['facility_id']}"
            )


def test_total_capacity_is_sufficient(cap41):
    """Instance feasibility precondition: aggregate capacity covers demand."""
    raw = raw_parse_cflp("cap41")
    assert sum(raw["capacities"]) >= sum(raw["demands"])


# ---------------------------------------------------------------------------
# 5. Customer demand coverage & single-source assignment
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(BEASLEY_GOLD))
def test_demand_fully_covered(name, request):
    sol = request.getfixturevalue(name)
    raw = raw_parse_cflp(name)
    assert len(sol["allocations"]) == raw["n"]
    assert len(sol["assignments"]) == raw["n"]

    for alloc, asg in zip(sol["allocations"], sol["assignments"]):
        j = alloc["customer_id"]
        assert asg["customer_id"] == j
        frac = sum(s["fraction"] for s in alloc["served_by"])
        assert frac == pytest.approx(1.0, abs=1e-6), (
            f"{name}: customer {j} coverage {frac} != 1.0"
        )
        served_ids = {s["facility_id"] for s in alloc["served_by"]}
        assert served_ids <= set(sol["open_facility_ids"])

        # Quantity delivered must equal the published demand, from both views.
        qty_alloc = sum(s["fraction"] * alloc["demand"] for s in alloc["served_by"])
        qty_asg = sum(s["quantity"] for s in asg["served_by"])
        assert qty_alloc == pytest.approx(raw["demands"][j], abs=1e-3)
        assert qty_asg == pytest.approx(raw["demands"][j], abs=1e-3)
        assert qty_asg == pytest.approx(qty_alloc, abs=1e-3)
        assert alloc["demand"] == pytest.approx(raw["demands"][j])


def test_assignments_and_allocations_views_agree(cap41):
    """The two assignment views must describe the same flow, not diverge."""
    sol = cap41
    for alloc, asg in zip(sol["allocations"], sol["assignments"]):
        assert alloc["customer_id"] == asg["customer_id"]
        assert alloc["demand"] == asg["demand"]
        assert {s["facility_id"] for s in alloc["served_by"]} == {
            s["facility_id"] for s in asg["served_by"]
        }
        assert sum(s["quantity"] for s in asg["served_by"]) == pytest.approx(
            alloc["demand"], abs=1e-3
        )


def test_continuous_cflp_may_split_demand():
    """Standard CFLP allows fractional splits — coverage still holds."""
    sol = solve_facility_location(time_limit_s=30, problem_id="task24_cflp_split")
    assert sol["status"] == "OPTIMAL"
    assert sol["mode"] == "cflp" and sol["single_source"] is False
    for a in sol["allocations"]:
        assert sum(s["fraction"] for s in a["served_by"]) == pytest.approx(1.0, abs=1e-6)


def test_single_source_assignment_is_binary():
    """SSCFLP: every customer is served by exactly one facility, fully."""
    sol = solve_facility_location(
        single_source=True, time_limit_s=30, problem_id="task24_sscflp"
    )
    assert sol["status"] == "OPTIMAL"
    assert sol["mode"] == "sscflp" and sol["single_source"] is True

    assert len(sol["assignments"]) == len(sol["allocations"])
    for alloc, asg in zip(sol["allocations"], sol["assignments"]):
        served = alloc["served_by"]
        assert len(served) == 1, (
            f"customer {alloc['customer_id']} split across {len(served)} facilities"
        )
        assert served[0]["fraction"] == pytest.approx(1.0, abs=1e-6)
        # assignments view must agree with allocations view.
        assert asg["facility_id"] == served[0]["facility_id"]
        assert len(asg["served_by"]) == 1

    # Validator must flag the extra single-source check as ok.
    checks = _assert_validator_ok(sol, SSCFLP_CHECKS)
    assert {c["name"] for c in checks} >= SSCFLP_CHECKS


def test_sscflp_objective_dominates_continuous():
    """Restricting to single-source can only make the CFLP objective worse."""
    cont = solve_facility_location(time_limit_s=30, problem_id="task24_cflp_cmp")
    ss = solve_facility_location(
        single_source=True, time_limit_s=30, problem_id="task24_sscflp_cmp"
    )
    assert ss["objective"] >= cont["objective"] - 1e-6


# ---------------------------------------------------------------------------
# 6. Haversine geodesic distance standardization
# ---------------------------------------------------------------------------
def _spherical_cosine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Independent great-circle implementation (spherical law of cosines)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    c = math.sin(phi1) * math.sin(phi2) + math.cos(phi1) * math.cos(phi2) * math.cos(dlam)
    return 6371.0 * math.acos(max(-1.0, min(1.0, c)))


def test_haversine_matches_independent_great_circle():
    pairs = [
        ((31.2304, 121.4737), (39.9042, 116.4074)),  # Shanghai -> Beijing
        ((31.2304, 121.4737), (22.5431, 114.0579)),  # Shanghai -> Shenzhen
        ((39.9042, 116.4074), (22.5431, 114.0579)),  # Beijing -> Shenzhen
        ((-33.8688, 151.2093), (51.5074, -0.1278)),  # Sydney -> London
    ]
    for a, b in pairs:
        h = haversine_km(*a, *b)
        c = _spherical_cosine_km(*a, *b)
        assert h == pytest.approx(c, abs=1e-6), f"{a}->{b}: {h} vs {c}"


def test_haversine_reference_distances():
    """Sanity anchors against well-known city-pair distances (~km)."""
    assert haversine_km(31.2304, 121.4737, 39.9042, 116.4074) == pytest.approx(
        1067.31, abs=0.5
    )
    # Zero distance to self, symmetry, and non-negative everywhere.
    assert haversine_km(31.2, 121.4, 31.2, 121.4) == 0.0
    a, b = (31.2304, 121.4737), (39.9042, 116.4074)
    assert haversine_km(*a, *b) == pytest.approx(haversine_km(*b, *a), abs=1e-9)
    assert haversine_km(0.0, 0.0, 0.0, 0.5) > 0.0


GEO_FACILITIES = [
    (31.2304, 121.4737),  # Shanghai
    (39.9042, 116.4074),  # Beijing
    (22.5431, 114.0579),  # Shenzhen
]
GEO_CUSTOMERS = [
    (31.2304, 121.4737),
    (39.9042, 116.4074),
    (23.1291, 113.2644),  # Guangzhou
    (34.3416, 108.9398),  # Xi'an
]


def test_haversine_cost_matrix_standardization():
    """Coordinate inputs must drive the cost matrix through Haversine km."""
    sol = solve_facility_location(
        fixed_costs=[1000.0, 1200.0, 1100.0],
        capacities=[500.0, 600.0, 550.0],
        demands=[180.0, 220.0, 150.0, 250.0],
        facility_coords=GEO_FACILITIES,
        customer_coords=GEO_CUSTOMERS,
        cost_per_km_ton=1.0,
        problem_id="task24_haversine",
        time_limit_s=30,
    )
    assert sol["status"] == "OPTIMAL"
    assert sol["metrics"]["esg"]["geodesic_distances_used"] is True
    assert sol["esg_metrics"]["total_ton_km"] > 0.0
    assert sol["esg_metrics"]["co2_emissions_kg"] == pytest.approx(
        sol["esg_metrics"]["total_ton_km"] * sol["esg_metrics"]["emission_factor_kg_per_ton_km"],
        abs=1e-3,
    )

    # Independently recompute: transport cost == sum(haversine_km * demand * frac).
    transport = 0.0
    ton_km = 0.0
    for a in sol["allocations"]:
        c_lat, c_lon = GEO_CUSTOMERS[a["customer_id"]]
        for s in a["served_by"]:
            f_lat, f_lon = GEO_FACILITIES[s["facility_id"]]
            d = haversine_km(f_lat, f_lon, c_lat, c_lon)
            transport += d * a["demand"] * s["fraction"]
            ton_km += d * a["demand"] * s["fraction"]
    assert sol["costs"]["variable"] == pytest.approx(transport, abs=1e-3)
    assert sol["esg_metrics"]["total_ton_km"] == pytest.approx(ton_km, abs=1e-3)


def test_haversine_scales_linearly_with_cost_per_km():
    """cost_per_km_ton is a pure scale factor on the geodesic cost matrix."""
    base = solve_facility_location(
        fixed_costs=[1000.0, 1200.0, 1100.0],
        capacities=[500.0, 600.0, 550.0],
        demands=[180.0, 220.0, 150.0, 250.0],
        facility_coords=GEO_FACILITIES,
        customer_coords=GEO_CUSTOMERS,
        cost_per_km_ton=1.0,
        problem_id="task24_geo_scale_1",
        time_limit_s=30,
    )
    scaled = solve_facility_location(
        fixed_costs=[1000.0, 1200.0, 1100.0],
        capacities=[500.0, 600.0, 550.0],
        demands=[180.0, 220.0, 150.0, 250.0],
        facility_coords=GEO_FACILITIES,
        customer_coords=GEO_CUSTOMERS,
        cost_per_km_ton=2.5,
        problem_id="task24_geo_scale_25",
        time_limit_s=30,
    )
    assert scaled["objective"] > base["objective"]
    assert scaled["costs"]["variable"] == pytest.approx(
        2.5 * base["costs"]["variable"], abs=1e-2
    )
    assert scaled["open_facility_ids"] == base["open_facility_ids"]


def test_haversine_dominates_euclidean_km_error():
    """Haversine must not overstate distance the way a flat Euclidean chord does."""
    # Beijing -> Shenzhen: great circle 1943 km; planar chord on the raw degree
    # grid would be ~sqrt(17.36^2 + 2.35^2) = 17.52 — a ~110x underestimate.
    h = haversine_km(39.9042, 116.4074, 22.5431, 114.0579)
    e = math.hypot(39.9042 - 22.5431, 116.4074 - 114.0579)
    assert h == pytest.approx(1943.14, abs=0.5)
    assert h > 10 * e, "Haversine must capture the geodesic, not the planar chord"


# ---------------------------------------------------------------------------
# 7. Independent validation via tools.validators.extended_solvers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(BEASLEY_GOLD))
def test_validate_facility_location_all_checks_ok(name, request):
    sol = request.getfixturevalue(name)
    checks = _assert_validator_ok(sol, BASE_CHECKS)
    by_name = {c["name"]: c for c in checks}
    assert by_name["facility_capacity_respected"]["ok"] is True
    assert by_name["demand_fully_satisfied"]["ok"] is True
    assert by_name["facility_cost_positive"]["ok"] is True


def test_validate_facility_location_default_instance():
    sol = solve_facility_location(time_limit_s=30, problem_id="task24_default")
    _assert_validator_ok(sol, BASE_CHECKS)


def test_validate_two_echelon_scnd():
    sol = solve_two_echelon_scnd(time_limit_s=30, problem_id="task24_two_echelon")
    assert sol["status"] == "OPTIMAL"
    assert sol["problem_class"] == "facility_location"
    assert sol["mode"] == "two_echelon"
    # Envelope additions flow through to the two-echelon path too.
    for key in ("assignments", "costs", "metrics", "open_facility_ids"):
        assert key in sol, f"two-echelon envelope missing '{key}'"
    assert sol["costs"]["fixed"] + sol["costs"]["variable"] == pytest.approx(
        sol["objective"], abs=1e-3
    )
    checks = _assert_validator_ok(sol, BASE_CHECKS | {"two_echelon_flow_balance"})
    assert {c["name"] for c in checks} >= BASE_CHECKS | {"two_echelon_flow_balance"}


def test_two_echelon_flow_conservation():
    sol = solve_two_echelon_scnd(time_limit_s=30, problem_id="task24_scnd_balance")
    for f in sol["open_facilities"]:
        assert f["inflow"] == pytest.approx(f["outflow"], abs=1e-3)
        assert f["load"] <= f["capacity"] + 1e-6


# ---------------------------------------------------------------------------
# 8. Edge cases: infeasible / missing input contracts
# ---------------------------------------------------------------------------
def test_infeasible_instance_reports_honest_status():
    """Total capacity below total demand must not produce a forged objective."""
    sol = solve_facility_location(
        fixed_costs=[100.0, 100.0],
        capacities=[10.0, 10.0],
        demands=[100.0, 200.0],
        cost_matrix=[[1.0, 1.0], [1.0, 1.0]],
        problem_id="task24_infeasible",
        time_limit_s=10,
    )
    assert sol["status"] in ("INFEASIBLE", "ERROR", "UNKNOWN")
    assert sol["objective"] <= 0
    assert sol["lower_bound"] is None
    assert sol["optimality_gap"] is None
    assert sol["open_facilities"] == []


def test_missing_cost_matrix_raises():
    with pytest.raises(ValueError):
        solve_facility_location(
            fixed_costs=[100.0], capacities=[10.0], demands=[5.0], problem_id="task24_bad"
        )


def test_known_optimum_not_used_to_forge_optimality():
    """A wrong published optimum must not be adopted as the dual bound.

    When the solver objective disagrees with the supplied ``known_optimum``,
    the anchoring must be refused and the real SCIP bound must survive.
    """
    raw = raw_parse_cflp("cap41")
    unit = [
        [raw["total_cost"][j][i] / raw["demands"][j] for j in range(raw["n"])]
        for i in range(raw["m"])
    ]
    sol = solve_facility_location(
        fixed_costs=raw["fixed_costs"],
        capacities=raw["capacities"],
        demands=raw["demands"],
        cost_matrix=unit,
        problem_id="orlib_cap41_tampered",
        known_optimum=999999.0,
        time_limit_s=60,
    )
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == pytest.approx(1040444.375, abs=1e-3)
    assert sol["lower_bound"] == pytest.approx(1040444.375, abs=1e-3)
    # The tampered reference must be refused, not adopted as the dual bound.
    assert sol["lower_bound"] != 999999.0
    assert sol["metrics"]["known_optimum"] == 999999.0
    assert sol["optimality_gap"] == pytest.approx(0.0, abs=1e-4)
