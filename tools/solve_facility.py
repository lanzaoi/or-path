#!/usr/bin/env python3
"""Capacitated Facility Location Problem (CFLP) & Supply Chain Network Design (SCND).

Industrial-grade solver based on OR-Tools MIP (SCIP / CBC / GLOP):
1. Standard CFLP (continuous demand allocation x_{ij} in [0, 1])
2. Single-Source CFLP (SSCFLP, binary assignment x_{ij} in {0, 1})
3. Two-Echelon Supply Chain Network Design (Plants -> DCs -> Customers)
4. Geolocation-aware optimization with Haversine distance matrix & ESG carbon emissions
5. Standard J.E. Beasley OR-Library CFLP benchmarks (cap41, cap61, cap71)
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

from ortools.linear_solver import pywraplp

# Default carbon emission factor for road freight: ~0.062 kg CO2 per ton-km
DEFAULT_CO2_PER_TON_KM = 0.062
EARTH_RADIUS_KM = 6371.0

# Published optimal objectives for the OR-Library CFLP benchmarks
# (J.E. Beasley, capopt.txt) — reference only; Numbers Truth: the objective
# strictly comes from the MIP solver.
BEASLEY_KNOWN_OPTIMA: dict[str, float] = {
    "cap41": 1040444.375,
    "cap61": 932615.75,
    "cap71": 932615.75,
}


def _normalize_gap(gap: float | None) -> float | None:
    """Normalize a MIP duality gap.

    Two rounding artefacts need absorbing:
      * ``-0.0``  — ``-0.0 < 0.0`` is ``False`` in Python, so a plain
        ``lo <= gap < 0`` test silently keeps the negative zero; JSON then
        serializes ``optimality_gap`` as ``-0.0`` instead of ``0.0``.
      * tiny negative noise from ``BestBound()`` exceeding the rounded
        objective (e.g. cap71 ``932615.7500000001``).

    A proven optimum must report a clean ``0.0``.
    """
    if gap is None:
        return None
    if gap == 0.0 or -1e-6 <= gap < 0.0:
        return 0.0
    return gap


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two GPS coordinates in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def load_orlibrary_cflp(name: str = "cap41") -> dict[str, Any]:
    """Load standard J.E. Beasley OR-Library CFLP benchmark instance.

    Format:
    - Line 1: num_facilities (m), num_customers (n)
    - Next m lines: capacity, fixed_cost
    - For each customer j (1..n):
        demand
        m shipping costs (total cost to satisfy customer j demand from facility i)
    """
    clean_name = name.lower().replace(".txt", "")
    fixture_dir = Path(__file__).resolve().parent.parent / "fixtures" / "benchmarks" / "orlib_cflp"
    file_path = fixture_dir / f"{clean_name}.txt"

    if not file_path.is_file():
        # Fallback search under current directory or /tmp
        alt = Path(f"/tmp/{clean_name}.txt")
        if alt.is_file():
            file_path = alt
        else:
            raise FileNotFoundError(f"OR-Library CFLP benchmark instance '{clean_name}' not found at {file_path}")

    toks = file_path.read_text(encoding="utf-8").split()
    m, n = int(toks[0]), int(toks[1])
    idx = 2

    capacities: list[float] = []
    fixed_costs: list[float] = []
    for _ in range(m):
        capacities.append(float(toks[idx]))
        fixed_costs.append(float(toks[idx + 1]))
        idx += 2

    demands: list[float] = []
    total_costs_by_customer: list[list[float]] = []
    for _ in range(n):
        demands.append(float(toks[idx]))
        idx += 1
        row = [float(toks[idx + i]) for i in range(m)]
        idx += m
        total_costs_by_customer.append(row)

    # Convert customer-major total costs to facility-major cost matrix
    # cost_matrix[i][j] is unit cost or total cost
    # In OR-Library, cost is already total cost. To convert to cost_matrix per demand unit:
    cost_matrix = [[0.0] * n for _ in range(m)]
    for j in range(n):
        d = demands[j]
        for i in range(m):
            cost_matrix[i][j] = total_costs_by_customer[j][i] / d if d > 0 else 0.0

    return {
        "problem_id": f"orlib_{clean_name}",
        "name": clean_name,
        "num_facilities": m,
        "num_customers": n,
        "capacities": capacities,
        "fixed_costs": fixed_costs,
        "demands": demands,
        "cost_matrix": cost_matrix,
        "total_cost_matrix": total_costs_by_customer,
        "known_optimum": BEASLEY_KNOWN_OPTIMA.get(clean_name),
    }


def solve_facility_location(
    fixed_costs: list[float] | None = None,
    capacities: list[float] | None = None,
    demands: list[float] | None = None,
    cost_matrix: list[list[float]] | None = None,
    facility_coords: list[tuple[float, float]] | None = None,
    customer_coords: list[tuple[float, float]] | None = None,
    cost_per_km_ton: float = 1.0,
    single_source: bool = False,
    time_limit_s: float = 30.0,
    problem_id: str | None = None,
    co2_factor: float = DEFAULT_CO2_PER_TON_KM,
    known_optimum: float | None = None,
) -> dict[str, Any]:
    """Solve Capacitated Facility Location Problem (CFLP / SSCFLP).

    When facility_coords and customer_coords are given, cost_matrix is auto-computed
    via Haversine distance * cost_per_km_ton.
    """
    t0 = time.perf_counter()

    # Default benchmark baseline (3 candidate facilities, 4 customers)
    if fixed_costs is None:
        fixed_costs = [1000.0, 1200.0, 1100.0]
        capacities = [500.0, 600.0, 550.0]
        demands = [180.0, 220.0, 150.0, 250.0]
        cost_matrix = [
            [4.0, 6.0, 8.0, 5.0],
            [7.0, 3.0, 5.0, 6.0],
            [5.0, 5.0, 3.0, 4.0],
        ]

    num_facilities = len(fixed_costs)
    num_customers = len(demands)
    distances_km: list[list[float]] | None = None

    # Handle GPS Coordinates if provided
    if facility_coords and customer_coords:
        cost_matrix = [[0.0] * num_customers for _ in range(num_facilities)]
        distances_km = [[0.0] * num_customers for _ in range(num_facilities)]
        for i in range(num_facilities):
            f_lat, f_lon = facility_coords[i]
            for j in range(num_customers):
                c_lat, c_lon = customer_coords[j]
                d = haversine_km(f_lat, f_lon, c_lat, c_lon)
                distances_km[i][j] = d
                cost_matrix[i][j] = d * cost_per_km_ton

    if cost_matrix is None:
        raise ValueError("cost_matrix or (facility_coords, customer_coords) must be provided")

    solver = pywraplp.Solver.CreateSolver("SCIP") or pywraplp.Solver.CreateSolver("CBC")
    if not solver:
        solver = pywraplp.Solver("cflp", pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)

    # y[i] = 1 if facility i is opened
    y = [solver.BoolVar(f"y_{i}") for i in range(num_facilities)]

    # x[i, j] = fraction (or binary indicator) of customer j's demand served by facility i
    x = {}
    for i in range(num_facilities):
        for j in range(num_customers):
            if single_source:
                x[i, j] = solver.BoolVar(f"x_{i}_{j}")
            else:
                x[i, j] = solver.NumVar(0.0, 1.0, f"x_{i}_{j}")

    # Constraint 1: Every customer's demand must be 100% satisfied
    for j in range(num_customers):
        solver.Add(solver.Sum([x[i, j] for i in range(num_facilities)]) == 1.0)

    # Constraint 2: Facility capacity must not be exceeded
    for i in range(num_facilities):
        solver.Add(
            solver.Sum([demands[j] * x[i, j] for j in range(num_customers)])
            <= capacities[i] * y[i]
        )
        # Tightening cut: x[i, j] <= y[i]
        for j in range(num_customers):
            solver.Add(x[i, j] <= y[i])

    # Objective: Minimize total fixed costs + transportation costs
    fixed_cost_expr = solver.Sum([fixed_costs[i] * y[i] for i in range(num_facilities)])
    trans_cost_expr = solver.Sum(
        [cost_matrix[i][j] * demands[j] * x[i, j] for i in range(num_facilities) for j in range(num_customers)]
    )
    solver.Minimize(fixed_cost_expr + trans_cost_expr)
    solver.SetTimeLimit(int(time_limit_s * 1000))

    status = solver.Solve()
    t1 = time.perf_counter()
    is_optimal = status == pywraplp.Solver.OPTIMAL
    is_feasible = status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE)

    pid = problem_id or f"cflp_{num_facilities}f_{num_customers}c"
    mode_name = "sscflp" if single_source else "cflp"

    if not is_feasible:
        return {
            "problem_id": pid,
            "problem_class": "facility_location",
            "status": "INFEASIBLE" if status == pywraplp.Solver.INFEASIBLE else "ERROR",
            "objective": -1.0,
            "lower_bound": None,
            "optimality_gap": None,
            "solver": "ortools-scip-cflp",
            "source": "tools/solve_facility.py",
            "mode": mode_name,
            "single_source": single_source,
            "open_facilities": [],
            "allocations": [],
            "meta": {"wall_time_s": round(t1 - t0, 5)},
        }

    open_facs = []
    total_fixed = 0.0
    for i in range(num_facilities):
        if y[i].solution_value() > 0.5:
            f_load = sum(demands[j] * x[i, j].solution_value() for j in range(num_customers))
            total_fixed += fixed_costs[i]
            open_facs.append({
                "facility_id": i,
                "fixed_cost": round(fixed_costs[i], 4),
                "capacity": round(capacities[i], 4),
                "load": round(f_load, 4),
                "utilization": round(f_load / capacities[i], 4) if capacities[i] > 0 else 0.0,
            })

    allocations = []
    total_transport = 0.0
    total_ton_km = 0.0

    for j in range(num_customers):
        served_by = []
        for i in range(num_facilities):
            val = x[i, j].solution_value()
            if val > 1e-5:
                # Full double precision: a rounded fraction can drift enough that
                # an independent recomputation of facility load exceeds capacity
                # (cap41 facility 2 reaches 5000.0 exactly, and 6-dp rounding
                # pushes the recomputed load to 5000.006).
                frac = float(val)
                served_by.append({"facility_id": i, "fraction": frac})
                cost_ij = cost_matrix[i][j] * demands[j] * val
                total_transport += cost_ij
                if distances_km is not None:
                    total_ton_km += distances_km[i][j] * demands[j] * val
                else:
                    # Estimate ton-km from cost
                    total_ton_km += cost_ij / max(1e-6, cost_per_km_ton)

        allocations.append({
            "customer_id": j,
            "demand": demands[j],
            "served_by": served_by,
        })

    obj_val = round(float(solver.Objective().Value()), 4)
    co2_kg = round(total_ton_km * co2_factor, 4)

    # MIP incumbent bound → lower_bound / optimality_gap (Numbers Truth).
    solver_lower_bound = float(solver.Objective().BestBound())
    lower_bound = solver_lower_bound
    if known_optimum is not None and is_optimal and abs(obj_val - float(known_optimum)) <= 1e-3:
        # The solver proved optimality and reproduces the published Beasley
        # optimum (capopt.txt), so anchor the dual bound to that reference.
        lower_bound = float(known_optimum)
    optimality_gap = _normalize_gap(round(obj_val - lower_bound, 4))

    # --- Standardized envelope shape (ADR-0002 + Phase 2 bounds) ------------
    open_facility_ids = sorted(int(f["facility_id"]) for f in open_facs)

    assignments: list[dict[str, Any]] = []
    for a in allocations:
        served = a["served_by"]
        primary = max(served, key=lambda s: s["fraction"])["facility_id"] if served else None
        assignments.append({
            "customer_id": a["customer_id"],
            "demand": a["demand"],
            "facility_id": primary,
            "served_by": [
                {**s, "quantity": round(s["fraction"] * a["demand"], 6)}
                for s in served
            ],
        })

    costs = {
        "fixed": round(total_fixed, 4),
        "variable": round(total_transport, 4),
        "total": obj_val,
    }

    metrics = {
        "objective": obj_val,
        "lower_bound": lower_bound,
        "optimality_gap": optimality_gap,
        "solver_lower_bound": solver_lower_bound,
        "known_optimum": known_optimum,
        "num_facilities": num_facilities,
        "num_customers": num_customers,
        "num_open_facilities": len(open_facility_ids),
        "open_facility_ids": open_facility_ids,
        "total_demand": round(sum(demands), 4),
        "total_capacity": round(sum(capacities), 4),
        "mode": mode_name,
        "proven_optimal": is_optimal,
        "solver_status": "OPTIMAL" if is_optimal else "FEASIBLE",
        "solve_seconds": round(t1 - t0, 5),
        "esg": {
            "total_ton_km": round(total_ton_km, 4),
            "co2_emissions_kg": co2_kg,
            "emission_factor_kg_per_ton_km": co2_factor,
            "geodesic_distances_used": distances_km is not None,
        },
    }

    result: dict[str, Any] = {
        "problem_id": pid,
        "problem_class": "facility_location",
        "status": "OPTIMAL" if is_optimal else "FEASIBLE",
        "objective": obj_val,
        "lower_bound": lower_bound,
        "optimality_gap": optimality_gap,
        "solver": "ortools-scip-cflp",
        "source": "tools/solve_facility.py",
        "mode": mode_name,
        "single_source": single_source,
        "num_facilities": num_facilities,
        "num_customers": num_customers,
        "total_fixed_cost": round(total_fixed, 4),
        "total_transport_cost": round(total_transport, 4),
        "open_facilities": open_facs,
        "open_facility_ids": open_facility_ids,
        "allocations": allocations,
        "assignments": assignments,
        "costs": costs,
        "esg_metrics": {
            "total_ton_km": round(total_ton_km, 4),
            "co2_emissions_kg": co2_kg,
            "emission_factor_kg_per_ton_km": co2_factor,
        },
        "metrics": metrics,
        "meta": {
            "exact": True,
            "proven_optimal": is_optimal,
            "wall_time_s": round(t1 - t0, 5),
            "iterations": int(solver.iterations()),
        },
    }
    if known_optimum is not None:
        result["known_optimum"] = known_optimum
    return result


def solve_two_echelon_scnd(
    plant_capacities: list[float] | None = None,
    plant_fixed_costs: list[float] | None = None,
    dc_capacities: list[float] | None = None,
    dc_fixed_costs: list[float] | None = None,
    demands: list[float] | None = None,
    plant_to_dc_costs: list[list[float]] | None = None,
    dc_to_cust_costs: list[list[float]] | None = None,
    time_limit_s: float = 30.0,
    problem_id: str | None = None,
    co2_factor: float = DEFAULT_CO2_PER_TON_KM,
    cost_per_km_ton: float = 1.0,
) -> dict[str, Any]:
    """Solve Two-Echelon Supply Chain Network Design (Plants -> DCs -> Customers).

    Decision variables:
    - y_dc[i] in {0, 1}: open DC i
    - w[k, i] >= 0: product flow from Plant k to DC i
    - x[i, j] in [0, 1]: fraction of Customer j demand satisfied by DC i
    """
    t0 = time.perf_counter()

    # Default two-echelon instance (2 Plants, 3 Candidate DCs, 4 Customer zones)
    if plant_capacities is None:
        plant_capacities = [1200.0, 1000.0]
        plant_fixed_costs = [5000.0, 4500.0]
        dc_capacities = [600.0, 700.0, 500.0]
        dc_fixed_costs = [1500.0, 1800.0, 1200.0]
        demands = [200.0, 250.0, 180.0, 220.0]  # Total demand = 850
        plant_to_dc_costs = [
            [3.0, 5.0, 6.0],  # Plant 0 to DCs 0, 1, 2
            [6.0, 4.0, 3.0],  # Plant 1 to DCs 0, 1, 2
        ]
        dc_to_cust_costs = [
            [2.5, 4.0, 5.0, 3.5],  # DC 0 to Customers 0..3
            [4.5, 2.0, 3.0, 4.0],  # DC 1 to Customers 0..3
            [3.0, 3.5, 2.0, 2.5],  # DC 2 to Customers 0..3
        ]

    num_plants = len(plant_capacities)
    num_dcs = len(dc_capacities)
    num_custs = len(demands)

    solver = pywraplp.Solver.CreateSolver("SCIP") or pywraplp.Solver.CreateSolver("CBC")
    if not solver:
        solver = pywraplp.Solver("scnd", pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)

    # Decisions
    y_dc = [solver.BoolVar(f"y_dc_{i}") for i in range(num_dcs)]
    w = {(k, i): solver.NumVar(0.0, plant_capacities[k], f"w_{k}_{i}") for k in range(num_plants) for i in range(num_dcs)}
    x = {(i, j): solver.NumVar(0.0, 1.0, f"x_{i}_{j}") for i in range(num_dcs) for j in range(num_custs)}

    # Constraint 1: Demand satisfaction
    for j in range(num_custs):
        solver.Add(solver.Sum([x[i, j] for i in range(num_dcs)]) == 1.0)

    # Constraint 2: Plant capacities
    for k in range(num_plants):
        solver.Add(solver.Sum([w[k, i] for i in range(num_dcs)]) <= plant_capacities[k])

    # Constraint 3: DC Flow balance (Inflow from plants == Outflow to customers)
    for i in range(num_dcs):
        inflow = solver.Sum([w[k, i] for k in range(num_plants)])
        outflow = solver.Sum([demands[j] * x[i, j] for j in range(num_custs)])
        solver.Add(inflow == outflow)

    # Constraint 4: DC Throughput capacity & open indicator
    for i in range(num_dcs):
        outflow = solver.Sum([demands[j] * x[i, j] for j in range(num_custs)])
        solver.Add(outflow <= dc_capacities[i] * y_dc[i])
        for j in range(num_custs):
            solver.Add(x[i, j] <= y_dc[i])

    # Objective: Minimize DC fixed costs + Plant-to-DC shipping + DC-to-Customer shipping
    dc_fixed = solver.Sum([dc_fixed_costs[i] * y_dc[i] for i in range(num_dcs)])
    p2dc_trans = solver.Sum([plant_to_dc_costs[k][i] * w[k, i] for k in range(num_plants) for i in range(num_dcs)])
    dc2c_trans = solver.Sum([dc_to_cust_costs[i][j] * demands[j] * x[i, j] for i in range(num_dcs) for j in range(num_custs)])

    solver.Minimize(dc_fixed + p2dc_trans + dc2c_trans)
    solver.SetTimeLimit(int(time_limit_s * 1000))

    status = solver.Solve()
    t1 = time.perf_counter()
    is_optimal = status == pywraplp.Solver.OPTIMAL
    is_feasible = status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE)

    pid = problem_id or f"two_echelon_{num_plants}p_{num_dcs}dc_{num_custs}c"

    if not is_feasible:
        return {
            "problem_id": pid,
            "problem_class": "facility_location",
            "status": "INFEASIBLE" if status == pywraplp.Solver.INFEASIBLE else "ERROR",
            "objective": -1.0,
            "lower_bound": None,
            "optimality_gap": None,
            "solver": "ortools-scip-cflp",
            "source": "tools/solve_facility.py",
            "mode": "two_echelon",
            "open_facilities": [],
            "allocations": [],
            "meta": {"wall_time_s": round(t1 - t0, 5)},
        }

    open_dcs = []
    tot_fixed = 0.0
    for i in range(num_dcs):
        if y_dc[i].solution_value() > 0.5:
            inflow_val = sum(w[k, i].solution_value() for k in range(num_plants))
            outflow_val = sum(demands[j] * x[i, j].solution_value() for j in range(num_custs))
            tot_fixed += dc_fixed_costs[i]
            open_dcs.append({
                "facility_id": i,
                "fixed_cost": round(dc_fixed_costs[i], 4),
                "capacity": round(dc_capacities[i], 4),
                "load": round(outflow_val, 4),
                "inflow": round(inflow_val, 4),
                "outflow": round(outflow_val, 4),
                "flow_balanced": abs(inflow_val - outflow_val) < 1e-4,
            })

    plant_flows = []
    for k in range(num_plants):
        for i in range(num_dcs):
            flow = w[k, i].solution_value()
            if flow > 1e-4:
                plant_flows.append({
                    "plant_id": k,
                    "dc_id": i,
                    "flow": round(flow, 4),
                    "cost": round(flow * plant_to_dc_costs[k][i], 4),
                })

    allocations = []
    for j in range(num_custs):
        served_by = []
        for i in range(num_dcs):
            frac = x[i, j].solution_value()
            if frac > 1e-4:
                served_by.append({"facility_id": i, "fraction": float(frac)})
        allocations.append({
            "customer_id": j,
            "demand": demands[j],
            "served_by": served_by,
        })

    obj_val = round(float(solver.Objective().Value()), 4)
    tot_trans = round(obj_val - tot_fixed, 4)
    total_ton_km = round(tot_trans / max(1e-6, cost_per_km_ton), 4)

    # MIP incumbent bound → lower_bound / optimality_gap (Numbers Truth).
    solver_lower_bound = float(solver.Objective().BestBound())
    lower_bound = solver_lower_bound
    optimality_gap = _normalize_gap(round(obj_val - lower_bound, 4))

    # --- Standardized envelope shape (ADR-0002 + Phase 2 bounds) ------------
    open_facility_ids = sorted(int(f["facility_id"]) for f in open_dcs)

    assignments: list[dict[str, Any]] = []
    for a in allocations:
        served = a["served_by"]
        primary = max(served, key=lambda s: s["fraction"])["facility_id"] if served else None
        assignments.append({
            "customer_id": a["customer_id"],
            "demand": a["demand"],
            "facility_id": primary,
            "served_by": [
                {**s, "quantity": round(s["fraction"] * a["demand"], 6)}
                for s in served
            ],
        })

    costs = {
        "fixed": round(tot_fixed, 4),
        "variable": round(tot_trans, 4),
        "total": obj_val,
    }

    metrics = {
        "objective": obj_val,
        "lower_bound": lower_bound,
        "optimality_gap": optimality_gap,
        "solver_lower_bound": solver_lower_bound,
        "num_plants": num_plants,
        "num_facilities": num_dcs,
        "num_customers": num_custs,
        "num_open_facilities": len(open_facility_ids),
        "open_facility_ids": open_facility_ids,
        "total_demand": round(sum(demands), 4),
        "mode": "two_echelon",
        "proven_optimal": is_optimal,
        "solver_status": "OPTIMAL" if is_optimal else "FEASIBLE",
        "solve_seconds": round(t1 - t0, 5),
    }

    return {
        "problem_id": pid,
        "problem_class": "facility_location",
        "status": "OPTIMAL" if is_optimal else "FEASIBLE",
        "objective": obj_val,
        "lower_bound": lower_bound,
        "optimality_gap": optimality_gap,
        "solver": "ortools-scip-cflp",
        "source": "tools/solve_facility.py",
        "mode": "two_echelon",
        "num_plants": num_plants,
        "num_facilities": num_dcs,
        "num_customers": num_custs,
        "total_fixed_cost": round(tot_fixed, 4),
        "total_transport_cost": tot_trans,
        "open_facilities": open_dcs,
        "open_facility_ids": open_facility_ids,
        "plant_flows": plant_flows,
        "allocations": allocations,
        "assignments": assignments,
        "costs": costs,
        "esg_metrics": {
            "total_ton_km": total_ton_km,
            "co2_emissions_kg": round(total_ton_km * co2_factor, 4),
            "emission_factor_kg_per_ton_km": co2_factor,
        },
        "metrics": metrics,
        "meta": {
            "exact": True,
            "proven_optimal": is_optimal,
            "wall_time_s": round(t1 - t0, 5),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Facility Location & Supply Chain Solver (CFLP/SSCFLP/SCND)")
    parser.add_argument("--single-source", action="store_true", help="Enforce single-source binary allocations (SSCFLP)")
    parser.add_argument("--multi-echelon", action="store_true", help="Solve Two-Echelon SCND (Plants -> DCs -> Customers)")
    parser.add_argument("--benchmark", type=str, default=None, help="OR-Library benchmark instance (e.g. cap41, cap61)")
    parser.add_argument("--time-limit-s", type=float, default=30.0)
    args = parser.parse_args(argv)

    if args.multi_echelon:
        res = solve_two_echelon_scnd(time_limit_s=args.time_limit_s)
    elif args.benchmark:
        data = load_orlibrary_cflp(args.benchmark)
        res = solve_facility_location(
            fixed_costs=data["fixed_costs"],
            capacities=data["capacities"],
            demands=data["demands"],
            cost_matrix=data["cost_matrix"],
            problem_id=data["problem_id"],
            known_optimum=data.get("known_optimum"),
            single_source=args.single_source,
            time_limit_s=args.time_limit_s,
        )
    else:
        res = solve_facility_location(
            single_source=args.single_source,
            time_limit_s=args.time_limit_s,
        )

    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
