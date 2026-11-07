"""Unit tests for the extended industrial OR solvers and independent validators.

Validates:
1. JSSP (Job Shop Scheduling, CP-SAT)
2. Bin Packing (1D Bin Packing & Knapsack, MIP)
3. Facility Location (Capacitated Facility Location, MIP)
4. Portfolio Optimization (Markowitz Mean-Variance, PyPortfolioOpt primary / SciPy fallback)
5. Network Flow & Bipartite Matching (NetworkX) + Multi-Commodity Flow (OR-Tools GLOP)
6. QUBO & Ising (Statistical Physics / Annealing, dimod)
7. RCPSP (Resource-Constrained Project Scheduling, PSPLib *.sm via OR-Tools CP-SAT)
8. Staff Rostering (Shift scheduling / nurse rostering, OR-Tools CP-SAT)
9. Multi-Period Lot Sizing (Wagner-Whitin DP / SCIP MIP)
10. Dispatch & Validation through unified OR-Path pipeline.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from solve_binpack import solve_bin_packing, solve_bin_packing_2d, solve_bin_packing_3d
from solve_dispatch import solve
from solve_facility import load_orlibrary_cflp, solve_facility_location, solve_two_echelon_scnd
from solve_jssp import solve_jssp
from solve_graph_coloring import solve_graph_coloring
from solve_game_theory import solve_game_theory
from solve_hub_location import solve_hub_location
from solve_max_clique import solve_max_clique
from solve_stochastic_lp import solve_stochastic_lp
from solve_lot_sizing import solve_lot_sizing
from solve_network_flow import solve_bipartite_matching, solve_min_cost_flow, solve_multi_commodity_flow
from solve_portfolio import solve_portfolio
from solve_qubo_ising import solve_ising, solve_max_cut, solve_number_partitioning, solve_qubo
from solve_rcpsp import solve_rcpsp
from solve_staff_rostering import solve_staff_rostering
from solve_pyvrp import solve_pyvrp
from solve_qap import solve_qap
from validate_solution import validate

_ROOT = Path(__file__).resolve().parent.parent


def test_jssp_solve_and_validate():
    sol = solve_jssp()
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == 55
    assert len(sol["schedule"]) == 36

    report = validate("jssp_ft06", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert "job_precedence" in check_names
    assert "machine_no_overlap" in check_names
    assert "makespan_objective_match" in check_names


def test_bin_packing_solve_and_validate():
    sol = solve_bin_packing()
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == 4
    assert len(sol["bins"]) == 4

    report = validate("binpack_12items", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert "bin_capacity_respected" in check_names
    assert "all_items_packed" in check_names
    assert "bin_count_objective_match" in check_names


def test_bin_packing_3d_solve_and_validate():
    sol = solve_bin_packing_3d()
    assert sol["problem_class"] == "bin_packing"
    assert sol["mode"] == "3d"
    assert sol["status"] == "FEASIBLE"
    assert sol["objective"] == len(sol["bins"])
    assert sol["rotation_dof"] == 6
    # All items placed, every reported coordinate is a valid 6-DOF placement.
    assert sol["unfitted_items"] == []
    placed_items = [it for b in sol["bins"] for it in b["items"]]
    assert len(placed_items) == sol["num_items"]
    for it in placed_items:
        assert set(it) >= {"x", "y", "z", "dx", "dy", "dz", "rotation_type"}
        assert it["dx"] > 0 and it["dy"] > 0 and it["dz"] > 0
        assert it["rotation_type"] in range(6)
    # Utilization metrics present and sane.
    for b in sol["bins"]:
        assert 0.0 <= b["volume_utilization"] <= 1.0
        assert 0.0 <= b["weight_utilization"] <= 1.0

    report = validate("binpack_3d", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {"bin_3d_in_bounds", "bin_3d_no_overlap", "bin_3d_weight_respected", "bin_3d_all_items_packed"} <= check_names


def test_bin_packing_2d_solve_and_validate():
    sol = solve_bin_packing_2d()
    assert sol["problem_class"] == "bin_packing"
    assert sol["mode"] == "2d"
    assert sol["status"] == "FEASIBLE"
    assert sol["objective"] == len(sol["bins"])
    # All parts placed, every reported coordinate is a valid 2D placement.
    assert sol["unfitted_parts"] == []
    placed_parts = [p for b in sol["bins"] for p in b["parts"]]
    assert len(placed_parts) == sol["num_parts"]
    for p in placed_parts:
        assert set(p) >= {"x", "y", "w", "h"}
        assert p["w"] > 0 and p["h"] > 0
    for b in sol["bins"]:
        assert 0.0 <= b["area_utilization"] <= 1.0

    report = validate("binpack_2d", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {"bin_2d_in_bounds", "bin_2d_no_overlap", "bin_2d_all_parts_placed"} <= check_names


def test_facility_location_solve_and_validate():
    sol = solve_facility_location()
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == 5370.0
    assert len(sol["open_facilities"]) == 2

    report = validate("facility_cflp", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert "facility_capacity_respected" in check_names
    assert "facility_cost_positive" in check_names
    assert "demand_fully_satisfied" in check_names


def test_facility_location_single_source():
    sol = solve_facility_location(single_source=True)
    assert sol["status"] == "OPTIMAL"
    assert sol["mode"] == "sscflp"
    assert sol["single_source"] is True
    assert sol["objective"] == 5580.0
    for a in sol["allocations"]:
        assert len(a["served_by"]) == 1
        assert a["served_by"][0]["fraction"] == 1.0

    report = validate("facility_sscflp", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert "single_source_binary" in check_names
    assert "demand_fully_satisfied" in check_names


def test_facility_location_two_echelon():
    sol = solve_two_echelon_scnd()
    assert sol["status"] == "OPTIMAL"
    assert sol["mode"] == "two_echelon"
    assert sol["objective"] == 7610.0
    assert len(sol["open_facilities"]) == 2
    for f in sol["open_facilities"]:
        assert f["flow_balanced"] is True
        assert abs(f["inflow"] - f["outflow"]) < 1e-4

    report = validate("facility_two_echelon", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert "two_echelon_flow_balance" in check_names


def test_facility_location_haversine():
    # Candidate DCs: Shanghai, Beijing, Guangzhou
    facility_coords = [(31.2304, 121.4737), (39.9042, 116.4074), (23.1291, 113.2644)]
    # Customers: Shanghai, Beijing, Guangzhou, Hangzhou
    customer_coords = [(31.2304, 121.4737), (39.9042, 116.4074), (23.1291, 113.2644), (30.2741, 120.1551)]
    fixed_costs = [1000.0, 1200.0, 1100.0]
    capacities = [500.0, 600.0, 550.0]
    demands = [180.0, 220.0, 150.0, 250.0]
    sol = solve_facility_location(
        fixed_costs=fixed_costs,
        capacities=capacities,
        demands=demands,
        facility_coords=facility_coords,
        customer_coords=customer_coords,
        cost_per_km_ton=0.5,
    )
    assert sol["status"] == "OPTIMAL"
    assert sol["esg_metrics"]["total_ton_km"] > 0
    assert sol["esg_metrics"]["co2_emissions_kg"] > 0

    report = validate("facility_haversine", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"


def test_facility_location_orlibrary_benchmarks():
    # cap41 official optimum = 1040444.375
    data_cap41 = load_orlibrary_cflp("cap41")
    sol_cap41 = solve_facility_location(
        fixed_costs=data_cap41["fixed_costs"],
        capacities=data_cap41["capacities"],
        demands=data_cap41["demands"],
        cost_matrix=data_cap41["cost_matrix"],
        problem_id=data_cap41["problem_id"],
    )
    assert sol_cap41["status"] == "OPTIMAL"
    assert sol_cap41["objective"] == pytest.approx(1040444.375, rel=1e-5)

    # cap61 official optimum = 932615.75
    data_cap61 = load_orlibrary_cflp("cap61")
    sol_cap61 = solve_facility_location(
        fixed_costs=data_cap61["fixed_costs"],
        capacities=data_cap61["capacities"],
        demands=data_cap61["demands"],
        cost_matrix=data_cap61["cost_matrix"],
        problem_id=data_cap61["problem_id"],
    )
    assert sol_cap61["status"] == "OPTIMAL"
    assert sol_cap61["objective"] == pytest.approx(932615.75, rel=1e-5)


def test_portfolio_opt_solve_and_validate():
    sol = solve_portfolio(objective_type="max_sharpe")
    assert sol["status"] == "OPTIMAL"
    assert sol["solver"] == "pypfopt-cvxpy"
    assert sol["problem_class"] == "portfolio_opt"
    assert sol["source"] == "tools/solve_portfolio.py"
    assert sol["sharpe_ratio"] > 0.5
    assert len(sol["allocations"]) == 5

    report = validate("portfolio_5assets", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert "weights_sum_to_one" in check_names
    assert "long_only_bounds" in check_names
    assert "sharpe_recomputation" in check_names


def test_portfolio_opt_min_volatility_solve_and_validate():
    sol = solve_portfolio(objective_type="min_volatility")
    assert sol["status"] == "OPTIMAL"
    assert sol["objective_type"] == "min_volatility"
    assert sol["volatility"] == sol["objective"]
    assert sol["volatility"] < 0.10

    report = validate("portfolio_minvol", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert "weights_sum_to_one" in check_names
    assert "long_only_bounds" in check_names


def test_portfolio_opt_efficient_frontier_generation():
    sol = solve_portfolio(objective_type="max_sharpe", frontier=True)
    frontier = sol.get("efficient_frontier")
    assert isinstance(frontier, list)
    assert 20 <= len(frontier) <= 50

    for point in frontier:
        assert set(point) == {"expected_return", "volatility", "sharpe_ratio"}
        assert point["volatility"] > 0
        rf = sol["risk_free_rate"]
        recomputed = (point["expected_return"] - rf) / point["volatility"]
        assert abs(recomputed - point["sharpe_ratio"]) <= 1e-2

    # Frontier should be non-decreasing in return and non-decreasing in vol.
    returns = [p["expected_return"] for p in frontier]
    vols = [p["volatility"] for p in frontier]
    assert returns == sorted(returns)
    assert vols == sorted(vols)


def test_portfolio_opt_discrete_allocation():
    sol = solve_portfolio(
        objective_type="max_sharpe", total_portfolio_value=100000.0
    )
    discrete = sol.get("discrete_allocation")
    assert isinstance(discrete, dict)
    shares = discrete["shares"]
    assert len(shares) == len(sol["allocations"])
    assert all(int(q) >= 0 for q in shares.values())
    assert discrete["leftover_cash"] >= 0.0

    assert discrete["total_invested"] == pytest.approx(
        100000.0 - discrete["leftover_cash"], abs=1e-6
    )


def test_portfolio_opt_efficient_return_objective():
    sol = solve_portfolio(objective_type="efficient_return", target_return=0.12)
    assert sol["status"] == "OPTIMAL"
    assert sol["expected_return"] == pytest.approx(0.12, abs=1e-4)

    report = validate("portfolio_effret", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"


def test_network_flow_solve_and_validate():
    # Min Cost Flow
    sol_flow = solve_min_cost_flow()
    assert sol_flow["status"] == "OPTIMAL"
    assert sol_flow["objective"] == 485

    rep_flow = validate("mcf_instance", sol_flow)
    assert rep_flow["ok"], f"Validation failed: {rep_flow['errors']}"
    assert any(c["name"] == "min_cost_flow_total" for c in rep_flow["checks"])

    # Bipartite Matching
    sol_match = solve_bipartite_matching()
    assert sol_match["status"] == "OPTIMAL"
    assert sol_match["objective"] == 5

    rep_match = validate("bipartite_instance", sol_match)
    assert rep_match["ok"], f"Validation failed: {rep_match['errors']}"
    assert any(c["name"] == "matching_cardinality_match" for c in rep_match["checks"])


def test_network_flow_multi_commodity_solve_and_validate():
    sol = solve_multi_commodity_flow()
    assert sol["status"] == "OPTIMAL"
    assert sol["problem_class"] == "network_flow"
    assert sol["mode"] == "multi_commodity_flow"
    assert sol["solver"] == "ortools-glop-mcnf"
    assert sol["source"] == "tools/solve_network_flow.py"
    assert sol["total_flow"] == pytest.approx(175.0)
    assert sol["objective"] == pytest.approx(565.0)
    assert len(sol["commodity_flows"]) == 3
    assert len(sol["edge_utilizations"]) == 9
    # Every commodity demand is fully shipped.
    for c in sol["commodity_flows"]:
        assert c["shipped"] == pytest.approx(c["demand"])

    rep = validate("mcnf_benchmark", sol)
    assert rep["ok"], f"Validation failed: {rep['errors']}"
    check_names = {c["name"] for c in rep["checks"]}
    assert {"mcnf_capacity_respected", "mcnf_flow_conservation", "mcnf_cost_match"} <= check_names


def test_network_flow_multi_commodity_bottleneck_detection():
    sol = solve_multi_commodity_flow()
    bottlenecks = sol["bottlenecks"]
    assert bottlenecks, "expected at least one saturated bottleneck edge"
    for b in bottlenecks:
        assert b["utilization"] >= 0.99
        assert b["shadow_price"] > 0

    # The saturated Central_Hub -> South_Market lane must be flagged.
    bn_keys = {(b["from"], b["to"]) for b in bottlenecks}
    assert ("Central_Hub", "South_Market") in bn_keys

    # Utilization entries must be internally consistent.
    for e in sol["edge_utilizations"]:
        assert e["utilization"] == pytest.approx(e["total_flow"] / e["capacity"])
    # Bottleneck entries agree with the utilization table.
    for b in bottlenecks:
        match = [e for e in sol["edge_utilizations"] if (e["from"], e["to"]) == (b["from"], b["to"])]
        assert match, f"bottleneck edge missing from edge_utilizations: {b}"
        assert match[0]["shadow_price"] == pytest.approx(b["shadow_price"])


def test_qubo_ising_solve_and_validate():
    # Max Cut on Petersen Graph
    sol_mc = solve_max_cut(method="exact")
    assert sol_mc["status"] == "OPTIMAL"
    assert sol_mc["objective"] == 12

    rep_mc = validate("petersen_maxcut", sol_mc)
    assert rep_mc["ok"], f"Validation failed: {rep_mc['errors']}"
    assert any(c["name"] == "cut_size_matches_objective" for c in rep_mc["checks"])

    # Number Partitioning
    sol_part = solve_number_partitioning(method="exact")
    assert sol_part["status"] == "OPTIMAL"
    assert sol_part["objective"] == 0

    rep_part = validate("num_partition", sol_part)
    assert rep_part["ok"], f"Validation failed: {rep_part['errors']}"
    assert any(c["name"] == "discrepancy_matches_objective" for c in rep_part["checks"])


def test_qubo_ising_general_solve_and_validate():
    # Default 6-variable QUBO benchmark (known ground state energy -5.0)
    sol = solve_qubo()
    assert sol["problem_class"] == "qubo_ising"
    assert sol["mode"] == "qubo"
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert isinstance(sol["sample"], dict)
    assert set(sol["sample"].values()) <= {0, 1}
    assert isinstance(sol["energy_spectrum"], list)
    assert len(sol["energy_spectrum"]) == 5
    assert sol["objective"] == pytest.approx(-5.0)

    rep = validate("qubo_default", sol)
    assert rep["ok"], f"Validation failed: {rep['errors']}"
    check_names = {c["name"] for c in rep["checks"]}
    assert "qubo_energy_match" in check_names


def test_qubo_ising_spin_glass_solve_and_validate():
    # Default 6-spin frustrated spin glass (known ground state energy -7.6)
    sol = solve_ising()
    assert sol["problem_class"] == "qubo_ising"
    assert sol["mode"] == "ising"
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert isinstance(sol["spins"], dict)
    assert set(sol["spins"].values()) <= {-1, 1}
    assert isinstance(sol["energy_spectrum"], list)
    assert len(sol["energy_spectrum"]) == 5
    assert sol["objective"] == pytest.approx(-7.6)

    rep = validate("ising_default", sol)
    assert rep["ok"], f"Validation failed: {rep['errors']}"
    check_names = {c["name"] for c in rep["checks"]}
    assert "ising_energy_match" in check_names


def test_qubo_ising_adaptive_annealing_spectrum():
    # Exact enumeration: spectrum is sorted ascending and objective equals
    # the lowest energy in the spectrum.
    sol_exact = solve_qubo(method="exact")
    assert sol_exact["status"] == "OPTIMAL"
    energies = [e["energy"] for e in sol_exact["energy_spectrum"]]
    assert energies == sorted(energies)
    assert sol_exact["objective"] == pytest.approx(energies[0])
    assert sol_exact["meta"]["proven_optimal"] is True

    # Simulated annealing with an explicit beta_range (adaptive schedule)
    sol_sa = solve_qubo(
        method="simulated_annealing", num_reads=50, beta_range=(0.5, 10.0)
    )
    assert sol_sa["status"] in ("OPTIMAL", "FEASIBLE")
    assert sol_sa["meta"]["num_reads"] == 50
    assert sol_sa["meta"]["beta_range"] == (0.5, 10.0)
    assert isinstance(sol_sa["energy_spectrum"], list)
    sa_energies = [e["energy"] for e in sol_sa["energy_spectrum"]]
    assert sa_energies == sorted(sa_energies)
    assert sol_sa["objective"] == pytest.approx(sa_energies[0])


def test_qubo_ising_json_roundtrip_validation():
    # Verify that serializing QUBO and Ising solutions to JSON (where integer keys
    # become strings) preserves validation correctness (Numbers Truth).
    sol_qubo = solve_qubo()
    roundtripped_qubo = json.loads(json.dumps(sol_qubo))
    rep_qubo = validate("qubo_default", roundtripped_qubo)
    assert rep_qubo["ok"], f"QUBO JSON round-trip validation failed: {rep_qubo['errors']}"

    # Test spaced and parenthesized bias keys format e.g. "(0, 1)" and "0, 1"
    spaced_qubo = json.loads(json.dumps(sol_qubo))
    spaced_qubo["Q"] = {f"({k.replace(',', ', ')})": v for k, v in spaced_qubo["Q"].items()}
    rep_spaced_qubo = validate("qubo_default", spaced_qubo)
    assert rep_spaced_qubo["ok"], f"QUBO spaced/bracketed key validation failed: {rep_spaced_qubo['errors']}"

    sol_ising = solve_ising()
    roundtripped_ising = json.loads(json.dumps(sol_ising))
    rep_ising = validate("ising_default", roundtripped_ising)
    assert rep_ising["ok"], f"Ising JSON round-trip validation failed: {rep_ising['errors']}"

    spaced_ising = json.loads(json.dumps(sol_ising))
    spaced_ising["J"] = {f"({k.replace(',', ', ')})": v for k, v in spaced_ising["J"].items()}
    rep_spaced_ising = validate("ising_default", spaced_ising)
    assert rep_spaced_ising["ok"], f"Ising spaced/bracketed key validation failed: {rep_spaced_ising['errors']}"


def test_rcpsp_solve_and_validate():
    # PSPLib j301_1.sm: known optimal makespan = 43 (Numbers Truth — the
    # objective comes strictly from the CP-SAT solver).
    sol = solve_rcpsp()
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == 43
    assert sol["makespan"] == 43
    assert sol["problem_class"] == "rcpsp"
    assert sol["mode"] == "rcpsp"
    assert sol["solver"] == "ortools-cpsat-rcpsp"
    assert sol["source"] == "tools/solve_rcpsp.py"
    assert sol["num_activities"] == 32
    assert sol["num_resources"] == 4
    assert sol["meta"]["proven_optimal"] is True
    assert sol["critical_path"], "critical path must be non-empty"
    # Critical path is zero-slack and topologically ordered by early start.
    sched = {e["activity_id"]: e for e in sol["schedule"]}
    es = {a: e["start"] for a, e in sched.items()}
    cp = sol["critical_path"]
    assert [es[a] for a in cp] == sorted(es[a] for a in cp)
    assert sol["meta"]["sink_dummy"] == sol["num_activities"] - 1
    assert cp[-1] == sol["meta"]["sink_dummy"]
    assert sched[sol["meta"]["sink_dummy"]]["end"] == 43

    report = validate("rcpsp_j301_1", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "rcpsp_precedence_respected",
        "rcpsp_resource_capacities_respected",
        "rcpsp_makespan_matches_objective",
    } <= check_names


def test_staff_rostering_solve_and_validate():
    sol = solve_staff_rostering()
    assert sol["status"] == "OPTIMAL"
    assert sol["problem_class"] == "staff_rostering"
    assert sol["mode"] == "staff_rostering"
    assert sol["solver"] == "ortools-cpsat-rostering"
    assert sol["source"] == "tools/solve_staff_rostering.py"
    assert sol["num_employees"] == 8
    assert sol["num_days"] == 14
    assert sol["shifts"] == ["Morning", "Afternoon", "Night", "Off"]
    # Exactly one shift per employee per day
    for emp, schedule in sol["roster"].items():
        assert len(schedule) == sol["num_days"]
    # Fairness metrics present
    fm = sol["fairness_metrics"]
    assert "total_shifts_per_employee" in fm
    assert "min_shifts" in fm
    assert "max_shifts" in fm
    assert "std_dev" in fm

    report = validate("staff_rostering", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "roster_daily_coverage",
        "roster_one_shift_per_day",
        "roster_night_shift_rest",
        "roster_consecutive_days_limit",
    } <= check_names


def test_lot_sizing_wagner_whitin_optimal():
    # Classic 12-period Wagner-Whitin benchmark: known optimal cost = 670.0
    # (setup 4×85 = 340 + holding 330).  Numbers Truth: the objective comes
    # strictly from the exact DP.
    sol = solve_lot_sizing()
    assert sol["status"] == "OPTIMAL"
    assert sol["problem_class"] == "lot_sizing"
    assert sol["mode"] == "lot_sizing"
    assert sol["solver"] == "ww-dp-exact"
    assert sol["source"] == "tools/solve_lot_sizing.py"
    assert sol["num_periods"] == 12
    assert sol["objective"] == 670.0
    assert sol["total_setup_cost"] == 340.0
    assert sol["total_holding_cost"] == 330.0
    assert sol["total_production_cost"] == 0.0
    assert sol["known_optimum"] == 670.0
    assert sol["optimality_gap"] == 0.0
    # Optimal WW plan: produce in periods 1, 4, 8, 10 (1-based).
    assert sol["setup_periods"] == [1, 4, 8, 10]
    assert sol["production_batches"] == [[1, 3], [4, 7], [8, 9], [10, 12]]
    # Schedule rows are complete and internally consistent.
    assert len(sol["schedule"]) == 12
    for s in sol["schedule"]:
        assert set(s) >= {"period", "demand", "production", "inventory",
                          "setup", "holding_cost", "setup_cost"}
    inv = 0.0
    for s in sol["schedule"]:
        inv = inv + s["production"] - s["demand"]
        assert inv == s["inventory"] >= 0
    assert inv == 0.0

    report = validate("lot_sizing_ww12", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "lot_sizing_flow_balance",
        "lot_sizing_setup_consistency",
        "lot_sizing_objective_match",
    } <= check_names


def test_lot_sizing_mip_matches_ww():
    ww = solve_lot_sizing(method="ww")
    mip = solve_lot_sizing(method="mip")
    assert mip["status"] == "OPTIMAL"
    assert mip["solver"] == "ortools-scip-mip"
    # Both exact methods recover the same optimal objective.
    assert mip["objective"] == ww["objective"] == 670.0
    assert mip["total_setup_cost"] + mip["total_holding_cost"] == mip["objective"]

    report = validate("lot_sizing_mip_ww12", mip)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert "lot_sizing_objective_match" in check_names


def test_lot_sizing_capacitated():
    # Capacitated lot sizing (CLSP): capacity 60/period.  The optimum (725.0)
    # was cross-checked against an independent exact DP over inventory
    # states (Numbers Truth: objective strictly from the SCIP MIP).
    sol = solve_lot_sizing(capacity=60.0, method="mip", problem_id="lot_sizing_clsp60")
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == 725.0
    assert sol["capacity"] == 60.0
    for s in sol["schedule"]:
        assert s["production"] <= 60.0
        assert s["inventory"] >= 0.0

    report = validate("lot_sizing_clsp60", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "lot_sizing_flow_balance",
        "lot_sizing_setup_consistency",
        "lot_sizing_capacity_respected",
        "lot_sizing_objective_match",
    } <= check_names


def test_lot_sizing_safety_stock_and_initial_inventory():
    sol = solve_lot_sizing(
        demands=[10.0, 20.0, 30.0],
        setup_cost=50.0,
        holding_cost=2.0,
        capacity=40.0,
        safety_stock=5.0,
        initial_inventory=5.0,
        method="mip",
        problem_id="lot_sizing_ss",
    )
    assert sol["status"] == "OPTIMAL"
    for s in sol["schedule"]:
        assert s["inventory"] >= 5.0 - 1e-6

    report = validate("lot_sizing_ss", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert "lot_sizing_safety_stock" in check_names


def test_pyvrp_solomon_c101_solve_and_validate():
    c101_path = _ROOT / "fixtures" / "benchmarks" / "vrp" / "c101.txt"
    sol = solve_pyvrp(solomon_path=c101_path, max_customers=25, time_limit_s=1.5)
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert sol["problem_class"] == "pyvrp"
    assert sol["mode"] == "pyvrp"
    assert sol["solver"] == "pyvrp-hgs"
    assert sol["num_clients"] == 25
    assert sol["num_vehicles_used"] >= 1
    assert sol["total_distance"] > 0
    assert len(sol["routes"]) == sol["num_vehicles_used"]

    report = validate("pyvrp_c101", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "pyvrp_status_feasible",
        "pyvrp_depot_endpoints",
        "pyvrp_client_visits_complete",
        "pyvrp_capacity_respected",
        "pyvrp_time_windows_respected",
        "pyvrp_distance_matches_objective",
    } <= check_names


def test_pyvrp_pdp_solve_and_validate():
    sol = solve_pyvrp(is_pdp=True, time_limit_s=1.0)
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert sol["num_shipments"] == 4
    assert sol["total_distance"] > 0
    assert len(sol["routes"]) >= 1

    report = validate("pyvrp_pdp_demo", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "pyvrp_status_feasible",
        "pyvrp_depot_endpoints",
        "pyvrp_pdp_precedence_respected",
        "pyvrp_capacity_respected",
        "pyvrp_time_windows_respected",
        "pyvrp_distance_matches_objective",
    } <= check_names


def test_pyvrp_alns_solve_and_validate():
    c101_path = _ROOT / "fixtures" / "benchmarks" / "vrp" / "c101.txt"
    sol = solve_pyvrp(solomon_path=c101_path, max_customers=15, time_limit_s=1.0, engine="alns")
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert sol["solver"] == "alns-vrp"
    assert sol["num_clients"] == 15
    assert sol["num_vehicles_used"] >= 1
    assert sol["total_distance"] > 0

    report = validate("pyvrp_alns", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "pyvrp_status_feasible",
        "pyvrp_depot_endpoints",
        "pyvrp_client_visits_complete",
        "pyvrp_capacity_respected",
        "pyvrp_time_windows_respected",
        "pyvrp_distance_matches_objective",
    } <= check_names


def test_qap_nug12_solve_and_validate():
    # QAPLIB nug12: known optimum = 578. Numbers Truth: the objective comes
    # strictly from the SciPy FAQ + 2-opt solver and is re-verified by the
    # independent validator.
    sol = solve_qap()
    assert sol["problem_class"] == "qap"
    assert sol["mode"] == "qap"
    assert sol["num_facilities"] == 12
    assert sol["objective"] == 578.0
    assert sol["status"] == "OPTIMAL"
    assert sol["solver"] == "scipy-qap-faq-2opt"
    assert sol["source"] == "tools/solve_qap.py"
    assert sol["meta"]["known_optimum"] == 578
    assert sol["meta"]["optimality_gap"] == 0.0
    # permutation is a valid bijection and assignments agree with it
    assert sorted(sol["permutation"]) == list(range(12))
    for i, a in enumerate(sol["assignments"]):
        assert a["facility_id"] == i
        assert a["location_id"] == sol["permutation"][i]

    report = validate("qap_nug12", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "qap_permutation_bijection",
        "qap_matrix_dimensions",
        "qap_objective_recompute",
    } <= check_names


def test_qap_small_exact_solve_and_validate():
    # 4-facility layout: brute-force the exact optimum and confirm the hybrid
    # heuristic recovers it.
    from itertools import permutations

    A = [
        [0, 1, 2, 3],
        [1, 0, 1, 2],
        [2, 1, 0, 1],
        [3, 2, 1, 0],
    ]
    B = [
        [0, 5, 0, 0],
        [5, 0, 3, 0],
        [0, 3, 0, 2],
        [0, 0, 2, 0],
    ]

    def _obj(perm):
        return sum(
            A[i][j] * B[perm[i]][perm[j]] for i in range(4) for j in range(4)
        )

    best = min(_obj(p) for p in permutations(range(4)))

    sol = solve_qap(
        distance_matrix=A, flow_matrix=B, method="hybrid", n_repeats=8, seed=1
    )
    assert sol["objective"] == best
    assert sorted(sol["permutation"]) == [0, 1, 2, 3]

    report = validate("qap_small4", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "qap_permutation_bijection",
        "qap_matrix_dimensions",
        "qap_objective_recompute",
    } <= check_names


def test_graph_coloring_myciel3_solve_and_validate():
    # DIMACS myciel3: 11 vertices, 20 edges, canonical chromatic number 4.
    # Numbers Truth: chi comes strictly from CP-SAT and is re-verified by the
    # independent validator.
    sol = solve_graph_coloring()
    assert sol["problem_class"] == "graph_coloring"
    assert sol["mode"] == "graph_coloring"
    assert sol["status"] == "OPTIMAL"
    assert sol["chromatic_number"] == 4
    assert sol["objective"] == 4
    assert sol["num_nodes"] == 11
    assert sol["num_edges"] == 20
    assert sol["solver"] == "networkx-dsatur-cpsat"
    assert sol["source"] == "tools/solve_graph_coloring.py"
    assert sol["meta"]["proven_optimal"] is True
    assert sol["meta"]["exact"] is True
    assert sol["meta"]["dsatur_upper_bound"] == 4
    assert len(sol["node_colors"]) == 11
    assert len(sol["color_classes"]) == 4
    assert sol["edges"] == [
        [1, 2], [1, 4], [1, 7], [1, 9], [2, 3], [2, 6], [2, 8],
        [3, 5], [3, 7], [3, 10], [4, 5], [4, 6], [4, 10], [5, 8],
        [5, 9], [6, 11], [7, 11], [8, 11], [9, 11], [10, 11],
    ]

    report = validate("graph_coloring_myciel3", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "shape_node_colors",
        "coloring_coverage",
        "zero_edge_conflicts",
        "chromatic_number_matches",
        "color_classes_partition",
    } <= check_names


def test_graph_coloring_odd_cycle():
    # C5 (odd cycle): chromatic number 3 — not 2-colorable.
    edges = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 0]]
    sol = solve_graph_coloring(graph_data=edges)
    assert sol["problem_class"] == "graph_coloring"
    assert sol["status"] == "OPTIMAL"
    assert sol["chromatic_number"] == 3
    assert sol["objective"] == 3
    assert sol["num_nodes"] == 5
    assert sol["num_edges"] == 5
    assert sol["meta"]["proven_optimal"] is True
    assert sorted(sol["color_classes"].keys()) == ["0", "1", "2"]

    report = validate("graph_coloring_c5", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "coloring_coverage",
        "zero_edge_conflicts",
        "chromatic_number_matches",
        "color_classes_partition",
    } <= check_names


def test_graph_coloring_dsatur_method_validate():
    # Pure heuristic track: DSATUR gives a valid colouring but no proof.
    sol = solve_graph_coloring(method="dsatur")
    assert sol["status"] == "FEASIBLE"
    assert sol["solver"] == "networkx-dsatur"
    assert sol["meta"]["exact"] is False
    assert sol["meta"]["proven_optimal"] is False
    assert sol["chromatic_number"] >= 4  # myciel3 needs at least 4 colours
    assert len(set(sol["node_colors"].values())) == sol["chromatic_number"]

    report = validate("graph_coloring_myciel3_dsatur", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "coloring_coverage",
        "zero_edge_conflicts",
        "chromatic_number_matches",
        "color_classes_partition",
    } <= check_names


def test_stochastic_lp_farmer_optimal():
    sol = solve_stochastic_lp()
    assert sol["problem_class"] == "stochastic_lp"
    assert sol["mode"] == "stochastic_lp"
    assert sol["status"] == "OPTIMAL"
    assert abs(sol["objective"] - 108390.0) < 1.0

    indicators = sol["stochastic_indicators"]
    assert abs(indicators["RP"] - 108390.0) < 1.0
    assert abs(indicators["WS"] - 115405.5556) < 1.0
    assert abs(indicators["EEV"] - 107240.0) < 1.0
    assert abs(indicators["EVPI"] - 7015.5556) < 1.0
    assert abs(indicators["VSS"] - 1150.0) < 1.0

    report = validate("farmer_problem", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"


def test_stochastic_lp_first_stage_acres():
    sol = solve_stochastic_lp()
    dec = sol["first_stage_decision"]
    assert abs(dec["wheat"] - 170.0) < 0.1
    assert abs(dec["corn"] - 80.0) < 0.1
    assert abs(dec["sugar_beets"] - 250.0) < 0.1
    assert abs(sum(dec.values()) - 500.0) < 0.1


def test_max_clique_myciel3():
    # DIMACS myciel3: triangle-free → omega(G) = 2; alpha(G) = 5.
    # Numbers Truth: the objectives come strictly from the solver and are
    # re-verified by the independent validator.
    sol = solve_max_clique()
    assert sol["problem_class"] == "max_clique"
    assert sol["mode"] == "max_clique"
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == 2
    assert sol["max_clique_size"] == 2
    assert sol["max_independent_set_size"] == 5
    assert sol["num_nodes"] == 11
    assert sol["num_edges"] == 20
    assert sol["solver"] == "networkx-cpsat-clique"
    assert sol["source"] == "tools/solve_max_clique.py"
    assert sol["complement_duality_verified"] is True
    assert len(sol["clique_nodes"]) == 2
    assert len(sol["independent_set_nodes"]) == 5
    assert sol["meta"]["proven_optimal"] is True
    assert sol["meta"]["exact"] is True
    # Spot-check clique adjacency and MIS independence from the envelope.
    edge_set = {frozenset(e) for e in sol["edges"]}
    for i in range(len(sol["clique_nodes"])):
        for j in range(i + 1, len(sol["clique_nodes"])):
            assert frozenset((sol["clique_nodes"][i], sol["clique_nodes"][j])) in edge_set
    for i in range(len(sol["independent_set_nodes"])):
        for j in range(i + 1, len(sol["independent_set_nodes"])):
            assert frozenset((sol["independent_set_nodes"][i], sol["independent_set_nodes"][j])) not in edge_set

    report = validate("max_clique_myciel3", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "clique_node_subset",
        "clique_pairwise_adjacent",
        "mis_node_subset",
        "mis_zero_edges",
        "objective_match",
        "size_fields_match",
        "duality_flag",
        "optimality_recompute",
    } <= check_names


def test_max_clique_odd_cycle_c5():
    # C5 (odd cycle): omega = 2, alpha = 2 (self-complementary).
    edges = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 0]]
    sol = solve_max_clique(graph_data=edges)
    assert sol["problem_class"] == "max_clique"
    assert sol["status"] == "OPTIMAL"
    assert sol["max_clique_size"] == 2
    assert sol["max_independent_set_size"] == 2
    assert sol["objective"] == 2
    assert sol["num_nodes"] == 5
    assert sol["num_edges"] == 5
    assert sol["complement_duality_verified"] is True

    report = validate("max_clique_c5", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "clique_node_subset",
        "clique_pairwise_adjacent",
        "mis_zero_edges",
        "objective_match",
        "duality_flag",
    } <= check_names


def test_max_clique_cpsat_method():
    sol = solve_max_clique(method="cpsat")
    assert sol["status"] == "OPTIMAL"
    assert sol["solver"] == "ortools-cpsat-clique"
    assert sol["meta"]["method"] == "cpsat"
    assert sol["max_clique_size"] == 2
    assert sol["max_independent_set_size"] == 5
    assert sol["objective"] == 2
    assert sol["complement_duality_verified"] is True

    report = validate("max_clique_myciel3_cpsat", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "clique_node_subset",
        "clique_pairwise_adjacent",
        "mis_zero_edges",
        "objective_match",
        "duality_flag",
        "optimality_recompute",
    } <= check_names


def test_max_clique_networkx_method():
    sol = solve_max_clique(method="networkx")
    assert sol["status"] == "OPTIMAL"
    assert sol["solver"] == "networkx-clique"
    assert sol["meta"]["method"] == "networkx"
    assert sol["max_clique_size"] == 2
    assert sol["max_independent_set_size"] == 5
    assert sol["complement_duality_verified"] is True

    report = validate("max_clique_myciel3_nx", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"


def test_max_clique_independent_set_mode():
    # mode='max_independent_set': objective = alpha(G) = 5.
    sol = solve_max_clique(mode="max_independent_set")
    assert sol["mode"] == "max_independent_set"
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == 5
    assert sol["max_independent_set_size"] == 5
    assert sol["max_clique_size"] == 2
    assert sol["complement_duality_verified"] is True

    report = validate("max_clique_myciel3_mis", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "objective_match",
        "size_fields_match",
        "duality_flag",
    } <= check_names


def test_game_theory_prisoners_dilemma():
    # Canonical PD: unique pure Nash (Defect, Defect) with payoffs [1, 1].
    sol = solve_game_theory(problem_id="prisoners_dilemma")
    assert sol["problem_class"] == "game_theory"
    assert sol["mode"] == "game_theory"
    assert sol["status"] == "OPTIMAL"
    assert sol["solver"] == "nashpy-engine"
    assert sol["source"] == "tools/solve_game_theory.py"
    assert sol["num_equilibria"] == 1

    pe = sol["primary_equilibrium"]
    assert pe["row_strategy"] == pytest.approx([0.0, 1.0])
    assert pe["col_strategy"] == pytest.approx([0.0, 1.0])
    assert pe["expected_payoffs"] == pytest.approx([1.0, 1.0])
    assert pe["is_pure"] is True
    assert sol["objective"] == pytest.approx(1.0)
    assert sol["game_value"] is None
    assert sol["row_regret"] <= 1e-4
    assert sol["col_regret"] <= 1e-4

    report = validate("game_theory_prisoners_dilemma", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "strategy_probability_distribution",
        "strategy_dimension_match",
        "expected_payoffs_recompute",
        "best_response_regret",
        "objective_match",
        "all_equilibria_nash",
    } <= check_names


def test_game_theory_matching_pennies():
    # Canonical zero-sum Matching Pennies: unique mixed Nash [0.5, 0.5].
    sol = solve_game_theory(problem_id="matching_pennies")
    assert sol["status"] == "OPTIMAL"
    assert sol["game_type"] == "zero_sum"
    assert sol["num_equilibria"] == 1

    pe = sol["primary_equilibrium"]
    assert pe["row_strategy"] == pytest.approx([0.5, 0.5])
    assert pe["col_strategy"] == pytest.approx([0.5, 0.5])
    assert pe["expected_payoffs"] == pytest.approx([0.0, 0.0])
    assert pe["is_pure"] is False
    assert sol["objective"] == pytest.approx(0.0)
    assert sol["game_value"] == pytest.approx(0.0)

    report = validate("game_theory_matching_pennies", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"


def test_game_theory_battle_of_the_sexes():
    # Coordination game with 3 Nash equilibria: 2 pure + 1 mixed.
    sol = solve_game_theory(problem_id="battle_of_the_sexes")
    assert sol["status"] == "OPTIMAL"
    assert sol["game_type"] == "coordination"
    assert sol["num_equilibria"] == 3

    pure = [eq for eq in sol["equilibria"] if eq["is_pure"]]
    mixed = [eq for eq in sol["equilibria"] if not eq["is_pure"]]
    assert len(pure) == 2
    assert len(mixed) == 1

    # Canonical mixed equilibrium (2/5, 3/5) for the row player.
    assert mixed[0]["row_strategy"] == pytest.approx([0.6, 0.4])
    assert mixed[0]["col_strategy"] == pytest.approx([0.4, 0.6])
    assert mixed[0]["expected_payoffs"] == pytest.approx([1.2, 1.2])

    # Primary = first discovered equilibrium (Opera, Opera).
    assert sol["expected_payoffs"] == pytest.approx([3.0, 2.0])
    assert sol["objective"] == pytest.approx(3.0)

    report = validate("game_theory_battle_of_the_sexes", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"


def test_game_theory_lemke_howson():
    # Lemke-Howson track: nashpy finds one equilibrium via the label path.
    sol = solve_game_theory(problem_id="prisoners_dilemma", method="lemke_howson")
    assert sol["status"] == "OPTIMAL"
    assert sol["meta"]["method"] == "lemke_howson"
    assert sol["num_equilibria"] == 1
    assert sol["expected_payoffs"] == pytest.approx([1.0, 1.0])
    assert sol["objective"] == pytest.approx(1.0)

    sol_bos = solve_game_theory(
        problem_id="battle_of_the_sexes", method="lemke_howson"
    )
    assert tuple(sol_bos["expected_payoffs"]) in ((3.0, 2.0), (2.0, 3.0))

    report = validate("game_theory_lemke_howson", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"


def test_game_theory_vertex_enumeration():
    # Vertex enumeration also recovers all three BoS equilibria.
    sol = solve_game_theory(
        problem_id="battle_of_the_sexes", method="vertex_enumeration"
    )
    assert sol["status"] == "OPTIMAL"
    assert sol["num_equilibria"] == 3
    assert sol["expected_payoffs"] == pytest.approx([3.0, 2.0])

    report = validate("game_theory_vertex_enumeration", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"


def test_hub_location_cab10_optimal():
    sol = solve_hub_location(time_limit_sec=60.0)
    assert sol["status"] == "OPTIMAL"
    assert sol["problem_class"] == "hub_location"
    assert sol["num_nodes"] == 10
    assert sol["p_hubs"] == 3
    assert sol["objective"] == pytest.approx(681216347.0158, rel=1e-5, abs=1.0)
    assert sol["selected_hubs"] == [3, 5, 6]
    assert sol["assignments"] == {
        "0": 5, "1": 5, "2": 5, "3": 3, "4": 5,
        "5": 5, "6": 6, "7": 6, "8": 5, "9": 6,
    }

    report = validate("hub_cab10", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert {
        "hub_count_matches_p",
        "assignments_target_hubs",
        "hubs_self_assigned",
        "assignments_complete",
        "hub_location_objective_match",
        "hub_location_breakdown_match",
    } <= check_names


def test_hub_location_cost_breakdown():
    sol = solve_hub_location(time_limit_sec=60.0)
    cb = sol["cost_breakdown"]
    assert set(cb) == {"collection_cost", "transfer_cost", "distribution_cost"}
    assert all(float(v) > 0.0 for v in cb.values())
    total = cb["collection_cost"] + cb["transfer_cost"] + cb["distribution_cost"]
    assert total == pytest.approx(sol["objective"], rel=1e-6, abs=1.0)

    report = validate("hub_cab10_breakdown", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"
    check_names = {c["name"] for c in report["checks"]}
    assert "hub_location_breakdown_match" in check_names


def test_hub_location_cab25_optimal():
    sol = solve_hub_location(
        fixture_path="fixtures/benchmarks/hub_location/CAB25.txt",
        time_limit_sec=120.0,
    )
    assert sol["status"] == "OPTIMAL"
    assert sol["num_nodes"] == 25
    assert sol["objective"] == pytest.approx(9361535773.97244, rel=1e-5, abs=1.0)
    assert sol["selected_hubs"] == [1, 3, 11]

    report = validate("hub_cab25", sol)
    assert report["ok"], f"Validation failed: {report['errors']}"


@pytest.mark.parametrize(
    "mode,expected_class",
    [
        ("jssp", "jssp"),
        ("bin_packing", "bin_packing"),
        ("facility_location", "facility_location"),
        ("portfolio_opt", "portfolio_opt"),
        ("network_flow", "network_flow"),
        ("qubo_ising", "qubo_ising"),
        ("rcpsp", "rcpsp"),
        ("staff_rostering", "staff_rostering"),
        ("pyvrp", "pyvrp"),
        ("lot_sizing", "lot_sizing"),
        ("qap", "qap"),
        ("graph_coloring", "graph_coloring"),
        ("stochastic_lp", "stochastic_lp"),
        ("max_clique", "max_clique"),
        ("game_theory", "game_theory"),
        ("hub_location", "hub_location"),
    ],
)
def test_dispatch_extended_solvers(mode: str, expected_class: str):
    ok, sol, raw = solve(_ROOT, "test_prob", mode=mode)
    assert ok, f"Dispatch failed for {mode}: {raw}"
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert sol["problem_class"] == expected_class
