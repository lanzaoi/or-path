# TSP with OR-Tools Routing (curated note)


- kind: paper-note
- title: TSP with OR-Tools Routing (curated note)
- source: curated

- kind: paper-note
- domain: tsp
- source: curated agent briefing (not a paper PDF dump)

## Problem

Traveling Salesman Problem (TSP): visit each city once and return to the depot; minimize tour length.

## Product wiring (OR-Path)

- `problem_class`: `tsp`
- Default exact-ish track for small n: OR-Tools Routing (`tools/solve_ortools.py`) or CP-SAT circuit on tiny n
- Fixture smoke: `fixtures/t2/tsp_n8` (n=8)
- Schema: distance matrix / nodes — **no** `tour` or `objective`

## Modeling checklist

- Complete graph or distance matrix
- Visit-once + return-to-start
- Metric assumptions (triangle inequality) often help search but are not required for validity of validate

## Numbers law

Tour length comes only from solve JSON + validate recompute. Do not cite prose optima.
