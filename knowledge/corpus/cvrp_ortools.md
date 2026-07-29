# Capacitated VRP and OR-Tools (curated OR note)

This curated note supports OR-Path hybrid retrieval for vehicle routing. Numeric optima are **never** stored here as authoritative memory.

## Problem class

**CVRP** (capacitated vehicle routing) routes a fleet from a depot to customers. Each customer has demand; each vehicle has capacity. T2 scope:

- **≥ 2 vehicles**
- **Capacity constraints**
- **No time windows** (TW-VRP is out of T2)

A good tiny fixture is **single-vehicle infeasible, multi-vehicle feasible** under capacity.

## OR-Tools Routing

Google OR-Tools `pywrapcp` RoutingModel is the primary solver for TSP and VRP in this project:

- Dimension callbacks for distance and demand/capacity
- Search parameters (metaheuristics, time limits) may be tuned ≤3 times on validate failure
- Tool path: `tools/solve_ortools.py`
- Solution shape: `routes` as list of per-vehicle node sequences; `objective` from solver only

## Modeling checklist

- `depot`, `demands`, `vehicle_count`, `capacities`
- Model schema must **not** include `routes` or `objective`
- Validate recomputes distance sum and capacity feasibility

## Research landscape

Domain multi-agent OR systems (e.g. modeling → codegen/solve → repair loops such as discussed around arXiv:2503.10009 OR-LLM-Agent) emphasize **solver-backed numbers** and bounded repair — not peer “team debate” as the source of optima. Residual modeling error remains even at high pass rates; gates still matter.

## Seed graph anchors

- `pc_vrp` — ProblemClass
- `c_capacity` — Constraint
- `s_ortools_routing` — Solver
- `case_t2_vrp_tiny` — Case

## TSP cousin

TSP is the single-tour special case (visit once, return to start). T2 fixture target: **n=8**, solved with the same OR-Tools routing stack.
