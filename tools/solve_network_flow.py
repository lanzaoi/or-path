#!/usr/bin/env python3
"""Network Flow & Bipartite Matching Solver using NetworkX + OR-Tools GLOP.

Adapts classic NetworkX network simplex / Hopcroft-Karp / Dinic:
- Min-Cost Flow: Supply chain / transportation with capacities & costs
- Max Flow: Network bottleneck / throughput optimization
- Bipartite Matching: Optimal resource / task pairing
- Multi-Commodity Network Flow (MCNF): LP relaxation via OR-Tools GLOP
  with bundle capacities, edge utilizations and dual shadow prices.
"""
from __future__ import annotations

import argparse
import json
import time
from typing import Any

import networkx as nx
from networkx.algorithms import bipartite


def solve_min_cost_flow(
    nodes: list[dict[str, Any]] | None = None,
    edges: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Solve Minimum-Cost Flow problem using NetworkX network_simplex."""
    t0 = time.perf_counter()

    if nodes is None or edges is None:
        # Default benchmark: 2 plants supplying 3 distribution centers
        # negative demand = supply, positive demand = customer demand
        nodes = [
            {"id": "Plant_A", "demand": -50},
            {"id": "Plant_B", "demand": -40},
            {"id": "Hub_1", "demand": 0},
            {"id": "Hub_2", "demand": 0},
            {"id": "Market_1", "demand": 30},
            {"id": "Market_2", "demand": 35},
            {"id": "Market_3", "demand": 25},
        ]
        edges = [
            {"u": "Plant_A", "v": "Hub_1", "capacity": 40, "weight": 2},
            {"u": "Plant_A", "v": "Hub_2", "capacity": 30, "weight": 4},
            {"u": "Plant_B", "v": "Hub_1", "capacity": 30, "weight": 3},
            {"u": "Plant_B", "v": "Hub_2", "capacity": 40, "weight": 2},
            {"u": "Hub_1", "v": "Market_1", "capacity": 30, "weight": 3},
            {"u": "Hub_1", "v": "Market_2", "capacity": 25, "weight": 5},
            {"u": "Hub_2", "v": "Market_2", "capacity": 30, "weight": 2},
            {"u": "Hub_2", "v": "Market_3", "capacity": 35, "weight": 4},
        ]

    G = nx.DiGraph()
    for n in nodes:
        G.add_node(n["id"], demand=n.get("demand", 0))

    for e in edges:
        G.add_edge(
            e["u"],
            e["v"],
            capacity=e.get("capacity", float("inf")),
            weight=e.get("weight", 0),
        )

    try:
        total_cost = nx.min_cost_flow_cost(G)
        flow_dict = nx.min_cost_flow(G)
        status = "OPTIMAL"
    except nx.NetworkXUnfeasible:
        return {
            "problem_id": "min_cost_flow_unfeasible",
            "problem_class": "network_flow",
            "status": "INFEASIBLE",
            "objective": -1,
            "solver": "networkx-network-simplex",
            "flow": {},
        }

    t1 = time.perf_counter()

    # Format active shipments
    active_flows = []
    for u, targets in flow_dict.items():
        for v, amount in targets.items():
            if amount > 0:
                unit_cost = G[u][v].get("weight", 0)
                active_flows.append({
                    "from": u,
                    "to": v,
                    "flow": amount,
                    "unit_cost": unit_cost,
                    "total_cost": amount * unit_cost,
                })

    return {
        "problem_id": f"min_cost_flow_{len(nodes)}nodes_{len(edges)}edges",
        "problem_class": "network_flow",
        "mode": "min_cost_flow",
        "status": status,
        "objective": total_cost,
        "solver": "networkx-network-simplex",
        "source": "tools/solve_network_flow.py",
        "total_cost": total_cost,
        "active_flows": active_flows,
        "full_flow_dict": flow_dict,
        "meta": {
            "exact": True,
            "proven_optimal": True,
            "nodes_count": len(nodes),
            "edges_count": len(edges),
            "wall_time_s": round(t1 - t0, 5),
        },
    }


def solve_bipartite_matching(
    workers: list[str] | None = None,
    tasks: list[str] | None = None,
    compatibilities: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Solve Maximum Bipartite Matching using Hopcroft-Karp."""
    t0 = time.perf_counter()

    if workers is None or tasks is None or compatibilities is None:
        workers = ["Worker_A", "Worker_B", "Worker_C", "Worker_D", "Worker_E"]
        tasks = ["Task_1", "Task_2", "Task_3", "Task_4", "Task_5", "Task_6"]
        compatibilities = [
            ("Worker_A", "Task_1"),
            ("Worker_A", "Task_2"),
            ("Worker_B", "Task_2"),
            ("Worker_B", "Task_3"),
            ("Worker_C", "Task_1"),
            ("Worker_C", "Task_4"),
            ("Worker_D", "Task_3"),
            ("Worker_D", "Task_5"),
            ("Worker_E", "Task_4"),
            ("Worker_E", "Task_5"),
            ("Worker_E", "Task_6"),
        ]

    B = nx.Graph()
    B.add_nodes_from(workers, bipartite=0)
    B.add_nodes_from(tasks, bipartite=1)
    B.add_edges_from(compatibilities)

    matching = bipartite.maximum_matching(B, top_nodes=workers)
    t1 = time.perf_counter()

    # Extract clean pairs (only worker -> task)
    assigned_pairs = {}
    for w in workers:
        if w in matching:
            assigned_pairs[w] = matching[w]

    match_count = len(assigned_pairs)

    return {
        "problem_id": f"bipartite_{len(workers)}workers_{len(tasks)}tasks",
        "problem_class": "network_flow",
        "mode": "bipartite_matching",
        "status": "OPTIMAL",
        "objective": match_count,
        "solver": "networkx-hopcroft-karp",
        "source": "tools/solve_network_flow.py",
        "matched_count": match_count,
        "total_workers": len(workers),
        "total_tasks": len(tasks),
        "matches": assigned_pairs,
        "unmatched_workers": [w for w in workers if w not in assigned_pairs],
        "meta": {
            "exact": True,
            "proven_optimal": True,
            "wall_time_s": round(t1 - t0, 5),
        },
    }


def _default_mcnf_benchmark() -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """Default multi-commodity logistics benchmark (6 nodes / 9 edges / 3 commodities).

    Port logistics network: grain and fuel flow on unique cheapest paths,
    while Tech_Goods competes for the saturated Central_Hub -> South_Market
    lane and must detour via East_DC.  Expected LP optimum: 565.0 with a
    single bottleneck edge (utilization 1.0, shadow price 1.0).
    """
    nodes = ["North_Port", "South_Port", "Central_Hub", "East_DC", "West_Market", "South_Market"]
    edges = [
        {"u": "North_Port", "v": "Central_Hub", "capacity": 120.0,
         "cost": {"Grain": 2.0, "Fuel": 2.2, "Tech_Goods": 1.0}},
        {"u": "South_Port", "v": "Central_Hub", "capacity": 100.0,
         "cost": {"Grain": 2.4, "Fuel": 2.0, "Tech_Goods": 2.4}},
        {"u": "Central_Hub", "v": "East_DC", "capacity": 60.0,
         "cost": {"Grain": 2.1, "Fuel": 2.0, "Tech_Goods": 2.6}},
        {"u": "Central_Hub", "v": "West_Market", "capacity": 70.0,
         "cost": {"Grain": 1.5, "Fuel": 2.5, "Tech_Goods": 2.7}},
        {"u": "Central_Hub", "v": "South_Market", "capacity": 45.0,
         "cost": {"Grain": 2.6, "Fuel": 2.3, "Tech_Goods": 1.0}},
        {"u": "North_Port", "v": "East_DC", "capacity": 50.0,
         "cost": {"Grain": 3.0, "Fuel": 3.2, "Tech_Goods": 1.5}},
        {"u": "South_Port", "v": "West_Market", "capacity": 40.0,
         "cost": {"Grain": 2.7, "Fuel": 2.8, "Tech_Goods": 3.1}},
        {"u": "East_DC", "v": "South_Market", "capacity": 70.0,
         "cost": {"Grain": 2.9, "Fuel": 2.7, "Tech_Goods": 1.5}},
        {"u": "West_Market", "v": "South_Market", "capacity": 55.0,
         "cost": {"Grain": 2.3, "Fuel": 2.4, "Tech_Goods": 2.0}},
    ]
    commodities = [
        {"name": "Grain", "source": "North_Port", "sink": "West_Market", "demand": 60.0},
        {"name": "Fuel", "source": "South_Port", "sink": "East_DC", "demand": 55.0},
        {"name": "Tech_Goods", "source": "North_Port", "sink": "South_Market", "demand": 60.0},
    ]
    return nodes, edges, commodities


def solve_multi_commodity_flow(
    nodes: list[str] | list[dict[str, Any]] | None = None,
    edges: list[dict[str, Any]] | None = None,
    commodities: list[dict[str, Any]] | None = None,
    time_limit_s: float = 30.0,
) -> dict[str, Any]:
    """Multi-Commodity Network Flow (MCNF) via OR-Tools GLOP (LP relaxation).

    Variables ``x[k, u, v] >= 0`` per commodity ``k`` and directed edge
    ``(u, v)``; bundle capacities ``sum_k x[k, u, v] <= cap``; per-commodity
    flow conservation; minimize total transportation cost.

    Inputs (defaults: realistic 6-node / 9-edge / 3-commodity port logistics
    benchmark):
      nodes:       node ids (str or {"id": ...})
      edges:       {"u", "v", "capacity", "cost": {commodity: unit_cost}}
      commodities: {"name", "source", "sink", "demand"}

    Outputs edge utilizations (flow / capacity) and dual shadow prices.  For
    GLOP minimization, raw ``dual_value()`` of a ``<=`` capacity constraint is
    non-positive, so the reported ``shadow_price`` is ``-dual_value()``
    (economic convention: value of one extra unit of capacity).
    Bottleneck edges: utilization >= 0.99 and shadow_price > 0.
    """
    from ortools.linear_solver import pywraplp  # lazy import keeps NetworkX path light

    t0 = time.perf_counter()

    if nodes is None or edges is None or commodities is None:
        nodes, edges, commodities = _default_mcnf_benchmark()

    node_ids = [n["id"] if isinstance(n, dict) else n for n in nodes]
    edge_list: list[tuple[str, str, float, dict[str, float]]] = []
    for e in edges:
        u, v = e["u"], e["v"]
        cap = float(e.get("capacity", float("inf")))
        cost_map = {str(k): float(val) for k, val in (e.get("cost") or {}).items()}
        edge_list.append((u, v, cap, cost_map))

    commodity_list = [
        {
            "name": str(c["name"]),
            "source": c["source"],
            "sink": c["sink"],
            "demand": float(c["demand"]),
        }
        for c in commodities
    ]

    node_set = set(node_ids)
    for u, v, _cap, _cm in edge_list:
        node_set.add(u)
        node_set.add(v)
    for c in commodity_list:
        node_set.add(c["source"])
        node_set.add(c["sink"])
    node_list = list(node_ids) + sorted(n for n in node_set if n not in node_ids)

    out_edges: dict[str, list[str]] = {n: [] for n in node_list}
    in_edges: dict[str, list[str]] = {n: [] for n in node_list}
    for u, v, _cap, _cm in edge_list:
        out_edges[u].append(v)
        in_edges[v].append(u)

    problem_id = f"mcnf_{len(node_list)}nodes_{len(edge_list)}edges_{len(commodity_list)}commodities"

    solver = pywraplp.Solver.CreateSolver("GLOP")
    if time_limit_s and time_limit_s > 0:
        solver.SetTimeLimit(int(float(time_limit_s) * 1000.0))

    # x[k, u, v] >= 0
    x: dict[tuple[str, str, str], Any] = {}
    for c in commodity_list:
        for u, v, _cap, _cm in edge_list:
            x[(c["name"], u, v)] = solver.NumVar(
                0.0, solver.infinity(), f"x_{c['name']}_{u}_to_{v}"
            )

    # Bundle capacity constraints (with dual tracking)
    cap_constraints: list[Any] = []
    for u, v, cap, _cm in edge_list:
        cons = solver.Add(
            solver.Sum([x[(c["name"], u, v)] for c in commodity_list]) <= cap
        )
        cap_constraints.append(cons)

    # Per-commodity flow conservation: out - in == supply at node
    # (source: +demand supply, sink: -demand absorption)
    infeasible_sink = False
    for c in commodity_list:
        kname, src, sink, demand = c["name"], c["source"], c["sink"], c["demand"]
        for n in node_list:
            b = -demand if n == sink else (demand if n == src else 0.0)
            terms: list[Any] = []
            for v in out_edges[n]:
                terms.append(x[(kname, n, v)])
            for u in in_edges[n]:
                terms.append(-x[(kname, u, n)])
            if not terms:
                if abs(b) > 1e-9:
                    infeasible_sink = True
                continue
            solver.Add(solver.Sum(terms) == b)

    if infeasible_sink:
        return _mcnf_infeasible(problem_id, edge_list, commodity_list, t0, time_limit_s)

    # Objective: minimize sum(flow * unit_cost)
    solver.Minimize(
        solver.Sum(
            [
                x[(c["name"], u, v)] * float(cm.get(c["name"], 1.0))
                for c in commodity_list
                for u, v, _cap, cm in edge_list
            ]
        )
    )

    status_code = solver.Solve()
    status_map = {int(solver.OPTIMAL): "OPTIMAL", int(solver.FEASIBLE): "FEASIBLE"}
    for code, name in (
        (getattr(solver, "INFEASIBLE", 2), "INFEASIBLE"),
        (getattr(solver, "UNBOUNDED", 3), "UNBOUNDED"),
        (getattr(solver, "ABORTED", getattr(solver, "ABNORMAL", 4)), "ABORTED"),
    ):
        status_map[int(code)] = name
    status = status_map.get(int(status_code), str(status_code))

    if status not in ("OPTIMAL", "FEASIBLE"):
        return _mcnf_infeasible(problem_id, edge_list, commodity_list, t0, time_limit_s, status)

    # Per-commodity route extraction
    commodity_flows: list[dict[str, Any]] = []
    for c in commodity_list:
        routes: list[dict[str, Any]] = []
        kcost = 0.0
        for idx, (u, v, _cap, cm) in enumerate(edge_list):
            f = x[(c["name"], u, v)].solution_value()
            if f > 1e-9:
                uc = float(cm.get(c["name"], 1.0))
                routes.append({"from": u, "to": v, "flow": f, "unit_cost": uc, "total_cost": f * uc})
                kcost += f * uc
        shipped = sum(r["flow"] for r in routes if r["from"] == c["source"]) - sum(
            r["flow"] for r in routes if r["to"] == c["source"]
        )
        commodity_flows.append(
            {
                "commodity": c["name"],
                "source": c["source"],
                "sink": c["sink"],
                "demand": c["demand"],
                "shipped": shipped,
                "cost": kcost,
                "edge_flows": routes,
            }
        )

    # Edge utilizations + dual shadow prices
    edge_utilizations: list[dict[str, Any]] = []
    bottlenecks: list[dict[str, Any]] = []
    for idx, (u, v, cap, _cm) in enumerate(edge_list):
        total = sum(x[(c["name"], u, v)].solution_value() for c in commodity_list)
        raw_dual = cap_constraints[idx].dual_value()
        shadow = -raw_dual if raw_dual is not None else 0.0
        util = total / cap if cap and cap > 0 else 0.0
        entry = {
            "from": u,
            "to": v,
            "capacity": cap,
            "total_flow": total,
            "utilization": util,
            "shadow_price": shadow,
        }
        edge_utilizations.append(entry)
        if util >= 0.99 and shadow > 0:
            bottlenecks.append(entry)

    total_flow = sum(c["shipped"] for c in commodity_flows)
    t1 = time.perf_counter()

    return {
        "problem_id": problem_id,
        "problem_class": "network_flow",
        "mode": "multi_commodity_flow",
        "status": status,
        "objective": float(solver.Objective().Value()),
        "solver": "ortools-glop-mcnf",
        "source": "tools/solve_network_flow.py",
        "total_flow": total_flow,
        "commodity_flows": commodity_flows,
        "edge_utilizations": edge_utilizations,
        "bottlenecks": bottlenecks,
        "meta": {
            "lp_relaxation": True,
            "nodes_count": len(node_list),
            "edges_count": len(edge_list),
            "commodities_count": len(commodity_list),
            "time_limit_s": time_limit_s,
            "solver_status_code": int(status_code),
            "wall_time_s": round(t1 - t0, 5),
        },
    }


def _mcnf_infeasible(
    problem_id: str,
    edge_list: list[tuple[str, str, float, dict[str, float]]],
    commodity_list: list[dict[str, Any]],
    t0: float,
    time_limit_s: float,
    status: str = "INFEASIBLE",
) -> dict[str, Any]:
    return {
        "problem_id": problem_id,
        "problem_class": "network_flow",
        "mode": "multi_commodity_flow",
        "status": status,
        "objective": -1,
        "solver": "ortools-glop-mcnf",
        "source": "tools/solve_network_flow.py",
        "total_flow": 0.0,
        "commodity_flows": [],
        "edge_utilizations":
            [
                {"from": u, "to": v, "capacity": cap, "total_flow": 0.0, "utilization": 0.0, "shadow_price": 0.0}
                for u, v, cap, _cm in edge_list
            ],
        "bottlenecks": [],
        "meta": {
            "lp_relaxation": True,
            "nodes_count": len({u for u, _v, _c, _m in edge_list} | {v for _u, v, _c, _m in edge_list}),
            "edges_count": len(edge_list),
            "commodities_count": len(commodity_list),
            "time_limit_s": time_limit_s,
            "wall_time_s": round(time.perf_counter() - t0, 5),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Network Flow & Matching Solver (NetworkX + OR-Tools GLOP)")
    parser.add_argument(
        "--mode",
        choices=["min_cost_flow", "bipartite_matching", "multi_commodity_flow"],
        default="min_cost_flow",
        help="Problem mode to solve",
    )
    args = parser.parse_args(argv)

    if args.mode == "min_cost_flow":
        res = solve_min_cost_flow()
    elif args.mode == "bipartite_matching":
        res = solve_bipartite_matching()
    else:
        res = solve_multi_commodity_flow()

    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
