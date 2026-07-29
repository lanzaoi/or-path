#!/usr/bin/env python3
"""Real OR-Tools solvers: TSP, multi-vehicle capacitated VRP; optional SP via routing."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_paths import ROOT, fixture_dir, fixture_file  # noqa: E402


def _ortools():
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    except ImportError:
        print("error: ortools import failed", file=sys.stderr)
        raise SystemExit(2)
    return pywrapcp, routing_enums_pb2


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _dist_matrix_from_coords(coords: list[dict]) -> list[list[int]]:
    n = len(coords)
    mat: list[list[int]] = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dx = float(coords[i]["x"]) - float(coords[j]["x"])
            dy = float(coords[i]["y"]) - float(coords[j]["y"])
            mat[i][j] = int(round(math.hypot(dx, dy)))
    return mat


def solve_tsp(
    problem_id: str,
    *,
    time_limit_ms: int = 2000,
    first_solution: str = "PATH_CHEAPEST_ARC",
    metaheuristic: str = "GUIDED_LOCAL_SEARCH",
    random_seed: int = 1,
) -> dict:
    pywrapcp, enums = _ortools()
    d = fixture_dir(problem_id)
    if (d / "distance_matrix.json").is_file():
        raw = _load_json(d / "distance_matrix.json")
        matrix = raw["matrix"] if isinstance(raw, dict) and "matrix" in raw else raw
        labels = (
            raw.get("labels")
            if isinstance(raw, dict)
            else [str(i) for i in range(len(matrix))]
        )
    else:
        coords = _load_json(d / "coords.json")
        if isinstance(coords, dict):
            coords = coords["coords"]
        labels = [str(c.get("id", i)) for i, c in enumerate(coords)]
        matrix = _dist_matrix_from_coords(coords)

    n = len(matrix)
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_cb(from_index: int, to_index: int) -> int:
        a = manager.IndexToNode(from_index)
        b = manager.IndexToNode(to_index)
        return int(matrix[a][b])

    transit = routing.RegisterTransitCallback(distance_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.time_limit.FromMilliseconds(int(time_limit_ms))
    fs = getattr(enums.FirstSolutionStrategy, first_solution, None)
    if fs is not None:
        params.first_solution_strategy = fs
    mh = getattr(enums.LocalSearchMetaheuristic, metaheuristic, None)
    if mh is not None:
        params.local_search_metaheuristic = mh

    solution = routing.SolveWithParameters(params)
    if solution is None:
        return {
            "problem_id": problem_id,
            "problem_class": "tsp",
            "status": "INFEASIBLE",
            "objective": -1,
            "solver": "ortools-routing",
            "source": "tools/solve_ortools.py",
            "path": None,
            "tour": None,
            "routes": None,
            "meta": {"time_limit_ms": time_limit_ms, "random_seed": random_seed},
        }

    index = routing.Start(0)
    tour_idx: list[int] = []
    while not routing.IsEnd(index):
        tour_idx.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    tour_idx.append(manager.IndexToNode(index))  # depot end
    tour = [labels[i] for i in tour_idx]
    obj = int(solution.ObjectiveValue())
    return {
        "problem_id": problem_id,
        "problem_class": "tsp",
        "status": "FEASIBLE",
        "objective": obj,
        "solver": "ortools-routing",
        "source": "tools/solve_ortools.py",
        "path": None,
        "tour": tour,
        "routes": None,
        "meta": {
            "time_limit_ms": time_limit_ms,
            "first_solution": first_solution,
            "metaheuristic": metaheuristic,
            "random_seed": random_seed,
            "n": n,
            "exact": False,
            "proven_optimal": False,
            "method_class": "metaheuristic",
            "claim": "routing search — not MIP/CP proven optimal; use cpsat/highs for exact TSP",
        },
    }


def solve_vrp(
    problem_id: str,
    *,
    time_limit_ms: int = 3000,
    first_solution: str = "PATH_CHEAPEST_ARC",
    metaheuristic: str = "GUIDED_LOCAL_SEARCH",
    random_seed: int = 1,
) -> dict:
    pywrapcp, enums = _ortools()
    d = fixture_dir(problem_id)
    data = _load_json(d / "locations.json")
    locations = data["locations"]
    labels = [str(loc["id"]) for loc in locations]
    depot_id = str(data.get("depot", labels[0]))
    depot_index = labels.index(depot_id)
    vehicle_count = int(data["vehicle_count"])
    capacities = [int(c) for c in data["capacities"]]
    demands_raw = data["demands"]
    if isinstance(demands_raw, dict):
        demands = [int(demands_raw.get(lab, 0)) for lab in labels]
    else:
        demands = [int(x) for x in demands_raw]

    # distance matrix
    if "distance_matrix" in data:
        matrix = data["distance_matrix"]
    else:
        coords = [{"x": loc["x"], "y": loc["y"]} for loc in locations]
        matrix = _dist_matrix_from_coords(coords)

    tw_raw = data.get("time_windows") or {}
    st_raw = data.get("service_times") or {}
    has_tw = bool(tw_raw)
    time_windows: list[tuple[int, int]] = []
    service_times: list[int] = []
    for lab in labels:
        if isinstance(tw_raw, dict) and lab in tw_raw:
            lo, hi = tw_raw[lab]
            time_windows.append((int(lo), int(hi)))
        else:
            time_windows.append((0, 10**9))
        if isinstance(st_raw, dict):
            service_times.append(int(st_raw.get(lab, 0)))
        else:
            service_times.append(0)

    n = len(labels)
    manager = pywrapcp.RoutingIndexManager(n, vehicle_count, depot_index)
    routing = pywrapcp.RoutingModel(manager)

    def distance_cb(from_index: int, to_index: int) -> int:
        a = manager.IndexToNode(from_index)
        b = manager.IndexToNode(to_index)
        return int(matrix[a][b])

    transit = routing.RegisterTransitCallback(distance_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit)

    def demand_cb(from_index: int) -> int:
        return int(demands[manager.IndexToNode(from_index)])

    demand_dim = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(
        demand_dim,
        0,
        capacities,
        True,
        "Capacity",
    )

    if has_tw:
        # Transit = travel + service at from-node; waiting via slack on Time dimension.
        def time_cb(from_index: int, to_index: int) -> int:
            a = manager.IndexToNode(from_index)
            b = manager.IndexToNode(to_index)
            return int(matrix[a][b]) + int(service_times[a])

        time_idx = routing.RegisterTransitCallback(time_cb)
        horizon = max(hi for _, hi in time_windows)
        horizon = max(horizon, sum(max(row) for row in matrix) + sum(service_times))
        routing.AddDimension(
            time_idx,
            horizon,  # slack: allow waiting until ready
            horizon,
            False,  # don't force start cumul to zero for all vehicles via fix_start
            "Time",
        )
        time_dim = routing.GetDimensionOrDie("Time")
        for node, (lo, hi) in enumerate(time_windows):
            index = manager.NodeToIndex(node)
            if node == depot_index:
                continue
            # NodeToIndex can be negative for multiple vehicles? depot handled separately
            if index < 0:
                continue
            time_dim.CumulVar(index).SetRange(int(lo), int(hi))
        depot_lo, depot_hi = time_windows[depot_index]
        for v in range(vehicle_count):
            start = routing.Start(v)
            end = routing.End(v)
            time_dim.CumulVar(start).SetRange(int(depot_lo), int(depot_hi))
            time_dim.CumulVar(end).SetRange(int(depot_lo), int(depot_hi))
            routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(start))
            routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(end))

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.time_limit.FromMilliseconds(int(time_limit_ms))
    fs = getattr(enums.FirstSolutionStrategy, first_solution, None)
    if fs is not None:
        params.first_solution_strategy = fs
    mh = getattr(enums.LocalSearchMetaheuristic, metaheuristic, None)
    if mh is not None:
        params.local_search_metaheuristic = mh

    solution = routing.SolveWithParameters(params)
    solver_name = "ortools-routing-cvrptw" if has_tw else "ortools-routing"
    if solution is None:
        return {
            "problem_id": problem_id,
            "problem_class": "vrp",
            "status": "INFEASIBLE",
            "objective": -1,
            "solver": solver_name,
            "source": "tools/solve_ortools.py",
            "path": None,
            "tour": None,
            "routes": None,
            "meta": {
                "vehicle_count": vehicle_count,
                "random_seed": random_seed,
                "has_time_windows": has_tw,
            },
        }

    routes: list[list[str]] = []
    for v in range(vehicle_count):
        index = routing.Start(v)
        route: list[str] = []
        while not routing.IsEnd(index):
            route.append(labels[manager.IndexToNode(index)])
            index = solution.Value(routing.NextVar(index))
        route.append(labels[manager.IndexToNode(index)])
        routes.append(route)

    obj = int(solution.ObjectiveValue())
    return {
        "problem_id": problem_id,
        "problem_class": "vrp",
        "status": "FEASIBLE",
        "objective": obj,
        "solver": solver_name,
        "source": "tools/solve_ortools.py",
        "path": None,
        "tour": None,
        "routes": routes,
        "meta": {
            "time_limit_ms": time_limit_ms,
            "first_solution": first_solution,
            "metaheuristic": metaheuristic,
            "random_seed": random_seed,
            "vehicle_count": vehicle_count,
            "capacities": capacities,
            "has_time_windows": has_tw,
            "exact": False,
            "proven_optimal": False,
            "method_class": "metaheuristic",
            "claim": "routing search — not proven global optimal; validate recomputes feasibility",
        },
    }


def solve_sp_via_networkx(problem_id: str) -> dict:
    # Prefer dedicated networkx tool for SP
    from solve_networkx import shortest_path_solution

    data = shortest_path_solution(problem_id)
    data["solver"] = "networkx-dijkstra-via-ortools-cli"
    data["meta"] = {**(data.get("meta") or {}), "note": "SP delegated to networkx"}
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OR-Path real OR-Tools solver")
    parser.add_argument("problem_id")
    parser.add_argument(
        "--class",
        dest="problem_class",
        default=None,
        choices=["shortest_path", "tsp", "vrp"],
    )
    parser.add_argument("--time-limit-ms", type=int, default=2000)
    parser.add_argument("--first-solution", default="PATH_CHEAPEST_ARC")
    parser.add_argument("--metaheuristic", default="GUIDED_LOCAL_SEARCH")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args(argv)

    pc = args.problem_class
    if pc is None:
        # infer from fixture files
        d = fixture_dir(args.problem_id)
        if (d / "locations.json").is_file():
            pc = "vrp"
        elif (d / "distance_matrix.json").is_file() or (d / "coords.json").is_file():
            pc = "tsp"
        else:
            pc = "shortest_path"

    try:
        if pc == "tsp":
            data = solve_tsp(
                args.problem_id,
                time_limit_ms=args.time_limit_ms,
                first_solution=args.first_solution,
                metaheuristic=args.metaheuristic,
                random_seed=args.seed,
            )
        elif pc == "vrp":
            data = solve_vrp(
                args.problem_id,
                time_limit_ms=args.time_limit_ms,
                first_solution=args.first_solution,
                metaheuristic=args.metaheuristic,
                random_seed=args.seed,
            )
        else:
            data = solve_sp_via_networkx(args.problem_id)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data.get("status") in {"OPTIMAL", "FEASIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
