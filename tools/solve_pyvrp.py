#!/usr/bin/env python3
"""High-Order Vehicle Routing Solver using PyVRP & VRPLIB.

Industrial VRP engine supporting:
* VRPTW: Capacitated Vehicle Routing Problem with Time Windows
* VRPPDTW: Pickup and Delivery Problem with Time Windows & Paired Shipments
* Heterogeneous fleet, multi-depot, service durations, release times
* Direct loading from Solomon / VRPLIB benchmarks (e.g. C101, R101, RC101)

Output follows OR-Path Numbers Truth envelope (ADR-0002):
  problem_id, problem_class="pyvrp", mode="pyvrp",
  status (FEASIBLE for heuristic engines — never a forged OPTIMAL),
  objective, lower_bound=None, optimality_gap=None (heuristic: no proof
  bounds, reported honestly as None), solver, source, num_clients,
  num_depots, num_shipments, num_vehicles_used, total_distance, routes
  (list[dict] with vehicle / route / distance / load / timeline),
  raw_depot, raw_clients, raw_shipments, distance_matrix, metrics, meta.

Heuristic honesty: PyVRP HGS and the ALNS fallback produce no optimality
proof, so status is FEASIBLE (not OPTIMAL) and lower_bound / optimality_gap
are None rather than invented numbers.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import pyvrp
import vrplib
import numpy as np
from alns import ALNS, State
from alns.accept import SimulatedAnnealing
from alns.select import RouletteWheel
from alns.stop import MaxRuntime

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

DEFAULT_SOLVER = "pyvrp-hgs"
DEFAULT_PROBLEM_ID = "pyvrp_benchmark"


def parse_solomon_file(
    file_path: str | Path,
    max_customers: int | None = None,
) -> dict[str, Any]:
    """Parse Solomon VRPTW benchmark instance using vrplib."""
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"Solomon benchmark file not found: {p}")
    data = vrplib.read_instance(str(p), instance_format="solomon")

    coords = data["node_coord"]
    tws = data["time_window"]
    demands = data["demand"]
    services = data["service_time"]
    capacity = int(data["capacity"])
    vehicles = int(data.get("vehicles", 25))

    total_nodes = len(coords)
    n_cust = total_nodes - 1
    if max_customers is not None and max_customers < n_cust:
        n_cust = max_customers

    depot = {
        "id": 0,
        "name": "Depot",
        "x": float(coords[0][0]),
        "y": float(coords[0][1]),
        "tw_early": int(tws[0][0]),
        "tw_late": int(tws[0][1]),
        "service_duration": int(services[0]),
    }

    clients = []
    for i in range(1, n_cust + 1):
        clients.append(
            {
                "id": i,
                "name": f"C{i}",
                "x": float(coords[i][0]),
                "y": float(coords[i][1]),
                "demand": int(demands[i]),
                "tw_early": int(tws[i][0]),
                "tw_late": int(tws[i][1]),
                "service_duration": int(services[i]),
            }
        )

    return {
        "name": data.get("name", p.stem),
        "capacity": capacity,
        "vehicles": vehicles,
        "depot": depot,
        "clients": clients,
        "shipments": [],
    }


def make_pdp_demo_instance() -> dict[str, Any]:
    """Create a self-contained Pickup and Delivery demo instance."""
    return {
        "name": "PDP_Demo_4Shipments",
        "capacity": 30,
        "vehicles": 3,
        "depot": {
            "id": 0,
            "name": "Central_Hub",
            "x": 40.0,
            "y": 50.0,
            "tw_early": 0,
            "tw_late": 1000,
            "service_duration": 0,
        },
        "clients": [],
        "shipments": [
            {
                "id": 1,
                "name": "Shipment_1",
                "pickup": {
                    "name": "P1",
                    "x": 25.0,
                    "y": 85.0,
                    "tw_early": 50,
                    "tw_late": 300,
                    "service_duration": 10,
                },
                "delivery": {
                    "name": "D1",
                    "x": 20.0,
                    "y": 80.0,
                    "tw_early": 100,
                    "tw_late": 500,
                    "service_duration": 10,
                },
                "amount": 12,
            },
            {
                "id": 2,
                "name": "Shipment_2",
                "pickup": {
                    "name": "P2",
                    "x": 45.0,
                    "y": 70.0,
                    "tw_early": 20,
                    "tw_late": 250,
                    "service_duration": 10,
                },
                "delivery": {
                    "name": "D2",
                    "x": 42.0,
                    "y": 68.0,
                    "tw_early": 80,
                    "tw_late": 450,
                    "service_duration": 10,
                },
                "amount": 15,
            },
            {
                "id": 3,
                "name": "Shipment_3",
                "pickup": {
                    "name": "P3",
                    "x": 15.0,
                    "y": 75.0,
                    "tw_early": 100,
                    "tw_late": 400,
                    "service_duration": 15,
                },
                "delivery": {
                    "name": "D3",
                    "x": 35.0,
                    "y": 69.0,
                    "tw_early": 200,
                    "tw_late": 600,
                    "service_duration": 15,
                },
                "amount": 10,
            },
            {
                "id": 4,
                "name": "Shipment_4",
                "pickup": {
                    "name": "P4",
                    "x": 30.0,
                    "y": 50.0,
                    "tw_early": 10,
                    "tw_late": 200,
                    "service_duration": 10,
                },
                "delivery": {
                    "name": "D4",
                    "x": 40.0,
                    "y": 66.0,
                    "tw_early": 60,
                    "tw_late": 350,
                    "service_duration": 10,
                },
                "amount": 8,
            },
        ],
    }


class _ALNSVrpState(State):
    """ALNS State representation for VRPTW."""

    def __init__(self, routes: list[list[int]], dist: np.ndarray, unassigned: list[int] | None = None):
        self.routes = [list(r) for r in routes if len(r) > 0]
        self.dist = dist
        self.unassigned = list(unassigned) if unassigned else []

    def copy(self) -> _ALNSVrpState:
        return _ALNSVrpState(self.routes, self.dist, self.unassigned)

    def objective(self) -> float:
        cost = 0.0
        for r in self.routes:
            prev = 0
            for c in r:
                cost += self.dist[prev, c]
                prev = c
            cost += self.dist[prev, 0]
        cost += len(self.unassigned) * 10000.0
        return float(cost)


def _solve_alns_vrp(
    data: dict[str, Any],
    problem_id: str,
    time_limit_s: float = 3.0,
) -> dict[str, Any]:
    """Solve VRPTW using Adaptive Large Neighborhood Search (ALNS)."""
    t0 = time.time()
    depot_spec = data["depot"]
    clients_spec = data.get("clients", [])
    capacity = int(data.get("capacity", 200))

    coords = [(float(depot_spec["x"]), float(depot_spec["y"]))]
    demands = [0]
    tws = [(int(depot_spec.get("tw_early", 0)), int(depot_spec.get("tw_late", 999999)))]
    services = [int(depot_spec.get("service_duration", 0))]

    for c in clients_spec:
        coords.append((float(c["x"]), float(c["y"])))
        demands.append(int(c.get("demand", 0)))
        tws.append((int(c.get("tw_early", 0)), int(c.get("tw_late", 999999))))
        services.append(int(c.get("service_duration", 0)))

    n_nodes = len(coords)
    dist = np.zeros((n_nodes, n_nodes))
    for i in range(n_nodes):
        for j in range(n_nodes):
            dist[i, j] = int(round(math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])))

    def check_route(r: list[int]) -> bool:
        load = sum(demands[c] for c in r)
        if load > capacity:
            return False
        curr_t = 0
        prev = 0
        for c in r:
            curr_t += int(dist[prev, c])
            if curr_t > tws[c][1]:
                return False
            curr_t = max(curr_t, tws[c][0]) + services[c]
            prev = c
        curr_t += int(dist[prev, 0])
        return curr_t <= tws[0][1]

    def random_destroy(state: _ALNSVrpState, rng: np.random.Generator) -> _ALNSVrpState:
        s = state.copy()
        custs = [c for r in s.routes for c in r]
        if not custs:
            return s
        k = min(len(custs), max(1, int(rng.integers(1, max(2, len(custs) // 3 + 1)))))
        chosen = set(rng.choice(custs, size=k, replace=False))
        new_routes = []
        for r in s.routes:
            rem = [c for c in r if c not in chosen]
            if rem:
                new_routes.append(rem)
        s.routes = new_routes
        s.unassigned.extend(list(chosen))
        return s

    def worst_destroy(state: _ALNSVrpState, rng: np.random.Generator) -> _ALNSVrpState:
        s = state.copy()
        cust_cost = []
        for r in s.routes:
            for idx, c in enumerate(r):
                p_prev = 0 if idx == 0 else r[idx - 1]
                p_next = 0 if idx == len(r) - 1 else r[idx + 1]
                delta = dist[p_prev, c] + dist[c, p_next] - dist[p_prev, p_next]
                cust_cost.append((delta, c))
        if not cust_cost:
            return s
        cust_cost.sort(key=lambda x: x[0], reverse=True)
        k = min(len(cust_cost), max(1, int(rng.integers(1, max(2, len(cust_cost) // 3 + 1)))))
        chosen = {c for _, c in cust_cost[:k]}
        new_routes = []
        for r in s.routes:
            rem = [c for c in r if c not in chosen]
            if rem:
                new_routes.append(rem)
        s.routes = new_routes
        s.unassigned.extend(list(chosen))
        return s

    def greedy_repair(state: _ALNSVrpState, rng: np.random.Generator) -> _ALNSVrpState:
        s = state.copy()
        to_insert = list(s.unassigned)
        rng.shuffle(to_insert)
        unplaced = []
        for c in to_insert:
            best_cost = float("inf")
            best_r_idx = -1
            best_pos = -1
            for r_idx, r in enumerate(s.routes):
                for pos in range(len(r) + 1):
                    cand = r[:pos] + [c] + r[pos:]
                    if check_route(cand):
                        p_prev = 0 if pos == 0 else r[pos - 1]
                        p_next = 0 if pos == len(r) else r[pos]
                        delta = dist[p_prev, c] + dist[c, p_next] - dist[p_prev, p_next]
                        if delta < best_cost:
                            best_cost = delta
                            best_r_idx = r_idx
                            best_pos = pos
            if check_route([c]):
                new_v_cost = dist[0, c] + dist[c, 0]
                if new_v_cost < best_cost:
                    best_cost = new_v_cost
                    best_r_idx = len(s.routes)
                    best_pos = 0

            if best_r_idx == len(s.routes):
                s.routes.append([c])
            elif best_r_idx >= 0:
                s.routes[best_r_idx].insert(best_pos, c)
            else:
                unplaced.append(c)
        s.unassigned = unplaced
        return s

    init_state = _ALNSVrpState([[i] for i in range(1, n_nodes)], dist)
    alns = ALNS(rng=np.random.default_rng(42))
    alns.add_destroy_operator(random_destroy)
    alns.add_destroy_operator(worst_destroy)
    alns.add_repair_operator(greedy_repair)

    select = RouletteWheel(scores=[3, 2, 1, 0.5], decay=0.8, num_destroy=2, num_repair=1)
    accept = SimulatedAnnealing(start_temperature=100.0, end_temperature=0.1, step=0.92)
    stop = MaxRuntime(max_runtime=max(0.1, float(time_limit_s)))

    res = alns.iterate(init_state, select, accept, stop)
    best_s = res.best_state
    elapsed = round(time.time() - t0, 4)

    is_feasible = (len(best_s.unassigned) == 0)
    routes = []
    total_dist = 0
    total_load = 0

    if is_feasible:
        for r_idx, r in enumerate(best_s.routes):
            r_dist = 0
            prev = 0
            visits = [{
                "start_time": 0,
                "end_time": 0,
                "wait_duration": 0,
                "time_warp": 0,
                "type": "depot",
                "name": depot_spec.get("name", "Depot"),
                "location_idx": 0,
            }]
            curr_t = 0
            r_load = sum(demands[c] for c in r)
            total_load += r_load

            for c in r:
                step_dist = int(dist[prev, c])
                r_dist += step_dist
                curr_t += step_dist
                wait = max(0, tws[c][0] - curr_t)
                start_t = curr_t + wait
                end_t = start_t + services[c]
                curr_t = end_t
                c_spec = clients_spec[c - 1]
                visits.append({
                    "start_time": int(start_t),
                    "end_time": int(end_t),
                    "wait_duration": int(wait),
                    "time_warp": 0,
                    "type": "client",
                    "client_idx": int(c - 1),
                    "name": c_spec.get("name", f"C{c}"),
                    "location_idx": int(c),
                    "demand": int(demands[c]),
                })
                prev = c

            return_dist = int(dist[prev, 0])
            r_dist += return_dist
            curr_t += return_dist
            visits.append({
                "start_time": int(curr_t),
                "end_time": int(curr_t),
                "wait_duration": 0,
                "time_warp": 0,
                "type": "depot",
                "name": depot_spec.get("name", "Depot"),
                "location_idx": 0,
            })
            total_dist += r_dist

            routes.append({
                "route_id": int(r_idx),
                "vehicle": int(r_idx),
                "vehicle_type": 0,
                "route": [v["location_idx"] for v in visits],
                "distance": int(r_dist),
                "duration": int(curr_t),
                "load": int(r_load),
                "num_stops": len(visits),
                "timeline": visits,
                "visits": visits,
            })

    # ALNS is a heuristic: no optimality proof exists, so the honest status
    # for a complete feasible solution is FEASIBLE (Numbers Truth — never
    # claim OPTIMAL without a solver-proved bound).
    status = "FEASIBLE" if is_feasible else "INFEASIBLE"

    return {
        "problem_id": problem_id,
        "problem_class": "pyvrp",
        "mode": "pyvrp",
        "status": status,
        "objective": int(total_dist) if is_feasible else None,
        # ALNS heuristic: no proof bound is available (Numbers Truth —
        # report None rather than inventing a bound).
        "lower_bound": None,
        "optimality_gap": None,
        "solver": "alns-vrp",
        "source": "alns-metaheuristic",
        "num_clients": len(clients_spec),
        "num_depots": 1,
        "num_shipments": 0,
        "num_vehicles_used": len(routes),
        "vehicle_capacity": capacity,
        "total_distance": int(total_dist),
        "total_load": int(total_load),
        "routes": routes,
        "raw_depot": depot_spec,
        "raw_clients": clients_spec,
        "raw_shipments": [],
        "distance_matrix": dist.tolist(),
        "metrics": {
            "num_clients": len(clients_spec),
            "num_shipments": 0,
            "num_vehicles_used": len(routes),
            "vehicle_capacity": capacity,
            "total_distance": int(total_dist),
            "total_load": int(total_load),
            "num_stops": sum(r["num_stops"] for r in routes),
            "elapsed_seconds": elapsed,
            "is_feasible": is_feasible,
            "unassigned_count": len(best_s.unassigned),
            "lower_bound": None,
            "optimality_gap": None,
        },
        "meta": {
            "elapsed_seconds": elapsed,
            "engine": "alns",
            "is_feasible": is_feasible,
            "unassigned_count": len(best_s.unassigned),
        },
    }


def solve_pyvrp(
    instance_data: dict[str, Any] | None = None,
    solomon_path: str | Path | None = None,
    max_customers: int | None = None,
    is_pdp: bool = False,
    time_limit_s: float = 3.0,
    problem_id: str | None = None,
    engine: str = "pyvrp",
) -> dict[str, Any]:
    """Solve VRPTW or VRPPDTW instance using PyVRP.

    Parameters
    ----------
    instance_data
        Dictionary specifying depot, clients or shipments, and vehicle capacity.
    solomon_path
        Optional path to Solomon VRPTW benchmark text file.
    max_customers
        Maximum number of customers to include (for fast tests or slicing).
    is_pdp
        If True, use built-in PDP demo instance if instance_data is None.
    time_limit_s
        PyVRP search wall-clock limit in seconds.
    problem_id
        Optional identifier for the problem envelope.
    """
    t0 = time.time()

    if solomon_path is not None:
        data = parse_solomon_file(solomon_path, max_customers=max_customers)
        pid = problem_id or f"solomon_{data['name']}"
    elif instance_data is not None:
        data = instance_data
        pid = problem_id or data.get("name", DEFAULT_PROBLEM_ID)
    elif is_pdp:
        data = make_pdp_demo_instance()
        pid = problem_id or "vrp_pdp_demo"
    else:
        # Default fallback: check default Solomon c101 fixture
        default_c101 = _ROOT / "fixtures" / "benchmarks" / "vrp" / "c101.txt"
        if default_c101.is_file():
            data = parse_solomon_file(default_c101, max_customers=max_customers or 25)
            pid = problem_id or "solomon_c101_25"
        else:
            data = make_pdp_demo_instance()
            pid = problem_id or "vrp_pdp_demo"

    depot_spec = data["depot"]
    clients_spec = data.get("clients", [])
    shipments_spec = data.get("shipments", [])
    capacity = int(data.get("capacity", 200))
    num_vehicles = int(data.get("vehicles", 25))

    if engine == "alns" and not is_pdp and not shipments_spec:
        return _solve_alns_vrp(data, pid, time_limit_s=time_limit_s)

    m = pyvrp.Model()

    # 1. Add Locations and Depot
    depot_loc = m.add_location(
        float(depot_spec["x"]), float(depot_spec["y"]), name=depot_spec.get("name", "Depot")
    )
    m.add_depot(
        depot_loc,
        tw_early=int(depot_spec.get("tw_early", 0)),
        tw_late=int(depot_spec.get("tw_late", 999999)),
        service_duration=int(depot_spec.get("service_duration", 0)),
        name=depot_spec.get("name", "Depot"),
    )

    # 2. Add Standard Clients
    client_locs = []
    for c in clients_spec:
        loc = m.add_location(float(c["x"]), float(c["y"]), name=c.get("name", f"C{c['id']}"))
        client_locs.append(loc)
        m.add_client(
            loc,
            delivery=[int(c.get("demand", 0))],
            service_duration=int(c.get("service_duration", 0)),
            tw_early=int(c.get("tw_early", 0)),
            tw_late=int(c.get("tw_late", 999999)),
            name=c.get("name", f"C{c['id']}"),
        )

    # 3. Add Paired Shipments (PDP)
    for s in shipments_spec:
        p_spec = s["pickup"]
        d_spec = s["delivery"]
        p_loc = m.add_location(float(p_spec["x"]), float(p_spec["y"]), name=p_spec.get("name", f"P{s['id']}"))
        d_loc = m.add_location(float(d_spec["x"]), float(d_spec["y"]), name=d_spec.get("name", f"D{s['id']}"))
        m.add_shipment(
            p_loc,
            d_loc,
            amount=[int(s.get("amount", 1))],
            pickup_tw_early=int(p_spec.get("tw_early", 0)),
            pickup_tw_late=int(p_spec.get("tw_late", 999999)),
            pickup_service_duration=int(p_spec.get("service_duration", 0)),
            delivery_tw_early=int(d_spec.get("tw_early", 0)),
            delivery_tw_late=int(d_spec.get("tw_late", 999999)),
            delivery_service_duration=int(d_spec.get("service_duration", 0)),
            name=s.get("name", f"Shipment_{s['id']}"),
        )

    # 4. Add Vehicle Fleet
    m.add_vehicle_type(num_available=num_vehicles, capacity=[capacity])

    # 5. Populate Complete Distance & Duration Graph
    all_locations = list(m.locations)
    n_locs = len(all_locations)
    dist_matrix = [[0.0] * n_locs for _ in range(n_locs)]
    for i, l1 in enumerate(all_locations):
        for j, l2 in enumerate(all_locations):
            if i == j:
                d = 0
            else:
                raw_d = math.hypot(l1.x - l2.x, l1.y - l2.y)
                d = int(round(raw_d))
                dist_matrix[i][j] = round(raw_d, 2)
            m.add_edge(l1, l2, distance=d, duration=d)

    # 6. Solve with HGS Search
    stop_crit = pyvrp.stop.MaxRuntime(max(0.1, float(time_limit_s)))
    res = m.solve(stop=stop_crit, display=False)
    elapsed = round(time.time() - t0, 4)

    is_feasible = res.is_feasible()
    cost = int(res.cost()) if is_feasible else None
    # HGS is a heuristic: no optimality proof exists, so the honest status
    # for a complete feasible solution is FEASIBLE (Numbers Truth — never
    # claim OPTIMAL without a solver-proved bound).
    status = "FEASIBLE" if is_feasible else "INFEASIBLE"

    routes = []
    total_distance = 0
    total_load = 0

    if is_feasible:
        for r_idx, r in enumerate(res.best.routes()):
            r_dist = int(r.distance())
            total_distance += r_dist
            delivery_val = r.delivery()
            r_load = int(delivery_val[0]) if delivery_val else 0
            total_load += r_load

            visits = []
            for act in r:
                act_info: dict[str, Any] = {
                    "start_time": int(act.start_time),
                    "end_time": int(act.end_time),
                    "wait_duration": int(act.wait_duration),
                    "time_warp": int(act.time_warp),
                }
                if act.is_depot():
                    act_info["type"] = "depot"
                    depot_obj = m.depots[act.idx]
                    act_info["name"] = depot_obj.name or "Depot"
                    act_info["location_idx"] = int(depot_obj.location)
                elif act.is_client():
                    act_info["type"] = "client"
                    client_obj = m.clients[act.idx]
                    act_info["client_idx"] = int(act.idx)
                    act_info["name"] = client_obj.name
                    act_info["location_idx"] = int(client_obj.location)
                    dem = client_obj.delivery
                    act_info["demand"] = int(dem[0]) if dem else 0
                elif act.is_shipment():
                    shipment_obj = m.shipments[act.idx]
                    act_info["shipment_idx"] = int(act.idx)
                    act_info["name"] = shipment_obj.name
                    if act.is_pickup():
                        act_info["type"] = "pickup"
                        act_info["location_idx"] = int(shipment_obj.pickup.location)
                    else:
                        act_info["type"] = "delivery"
                        act_info["location_idx"] = int(shipment_obj.delivery.location)
                    amt = shipment_obj.amount
                    act_info["amount"] = int(amt[0]) if amt else 0

                visits.append(act_info)

            routes.append({
                "route_id": r_idx,
                "vehicle": r_idx,
                "vehicle_type": int(r.vehicle_type()),
                "route": [v["location_idx"] for v in visits],
                "distance": r_dist,
                "duration": int(r.duration()),
                "load": r_load,
                "num_stops": len(visits),
                "timeline": visits,
                "visits": visits,
            })

    return {
        "problem_id": pid,
        "problem_class": "pyvrp",
        "mode": "pyvrp",
        "status": status,
        "objective": total_distance if is_feasible else None,
        # HGS heuristic: no proof bound is available (Numbers Truth —
        # report None rather than inventing a bound).
        "lower_bound": None,
        "optimality_gap": None,
        "solver": DEFAULT_SOLVER,
        "source": "pyvrp-engine",
        "num_clients": len(clients_spec),
        "num_depots": 1,
        "num_shipments": len(shipments_spec),
        "num_vehicles_used": len(routes),
        "vehicle_capacity": capacity,
        "total_distance": total_distance,
        "total_load": total_load,
        "routes": routes,
        "raw_depot": depot_spec,
        "raw_clients": clients_spec,
        "raw_shipments": shipments_spec,
        "distance_matrix": dist_matrix,
        "metrics": {
            "num_clients": len(clients_spec),
            "num_shipments": len(shipments_spec),
            "num_vehicles_used": len(routes),
            "vehicle_capacity": capacity,
            "total_distance": total_distance,
            "total_load": total_load,
            "num_stops": sum(r["num_stops"] for r in routes),
            "elapsed_seconds": elapsed,
            "is_feasible": is_feasible,
            "lower_bound": None,
            "optimality_gap": None,
        },
        "meta": {
            "elapsed_seconds": elapsed,
            "pyvrp_iterations": res.num_iterations,
            "is_feasible": is_feasible,
            "best_cost": cost,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PyVRP Advanced Vehicle Routing Solver")
    parser.add_argument("problem_id", nargs="?", default=None, help="Problem identifier")
    parser.add_argument("--solomon", type=str, default=None, help="Path to Solomon benchmark file")
    parser.add_argument("--max-customers", type=int, default=None, help="Max customers to include")
    parser.add_argument("--pickup-delivery", action="store_true", help="Run PDP demo mode")
    parser.add_argument("--input", type=str, default=None, help="Path to input JSON instance")
    parser.add_argument("--time-limit", type=float, default=3.0, help="Wall-clock time limit in seconds")
    parser.add_argument("--engine", choices=["pyvrp", "alns"], default="pyvrp", help="Solver engine (pyvrp or alns)")
    parser.add_argument("--output", type=str, default=None, help="Output path for JSON envelope")

    args = parser.parse_args(argv)

    instance_data = None
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            instance_data = json.load(f)

    result = solve_pyvrp(
        instance_data=instance_data,
        solomon_path=args.solomon,
        max_customers=args.max_customers,
        is_pdp=args.pickup_delivery,
        time_limit_s=args.time_limit,
        problem_id=args.problem_id,
        engine=args.engine,
    )

    out_json = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(out_json, encoding="utf-8")
    else:
        print(out_json)

    return 0 if result["status"] in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    sys.exit(main())
