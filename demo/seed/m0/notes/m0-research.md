# Research: m0

## Summary
Research for `shortest_path` / `shortest_path`. Retrieval mode=seed.

## Problem class
shortest_path

## Evidence table
| # | Source | Path/URL | Key claim | Type | Confidence |
|---|--------|----------|-----------|------|------------|
| 1 | chunk | s_ortools_routing | Google OR-Tools Routing for TSP and capacitated VRP. | retrieval | med |
| 2 | chunk | s_ortools_routing | Google OR-Tools Routing for TSP and capacitated VRP. | retrieval | med |
| 3 | chunk | pc_shortest_path | Find a minimum-cost path between two nodes on a weighted graph. | retrieval | med |
| 4 | chunk | pc_assignment | Assign agents to tasks at minimum cost (related routing building block). | retrieval | med |
| 5 | chunk | s_ortools_cpsat | CP-SAT for discrete OR models; optional SP/assignment parity. | retrieval | med |
| 6 | seed | None |  | seed | high |
| 7 | seed | None |  | seed | high |
| 8 | seed | None |  | seed | high |

## Findings
1. Use deterministic solvers (networkx/cpsat/highs/ortools); never LLM optima.
2. Validate must recompute objective.
3. Seed/retrieval chunk_ids when present must be cited in this table.

## Modeling recommendations
- problem_class: shortest_path
- no objective/tour/routes/path answers in schema

## Retrieval artifact
`C:\Users\Lanzao\Desktop\agent\notes\m0-retrieval.json`

## Problem excerpt
# 最短路 / Shortest Path (T1 fixture)

## 中文

给定有向加权图，节点为 `S`、`A`、`T`。边权：

- `S → A`：10
- `A → T`：32
- `S → T`：100

求从起点 **S** 到终点 **T** 的最短路径及其总代价。

## English

Given a directed weighted graph with nodes `S`, `A`, `T` and edges:

- `S → A` weight 10
- `A → T` weight 32
- `S → T` weight 100

Find the **shortest path from S to T** and its total cost.

## Notes

- Numbers truth comes only from solve tools / `solution.json`.
- Do not invent the optimal objective in prose without the solver artifact.

## Coverage Status
- knowledge_mode: seed
- hits: 5
- seed_facts: 4
- chunk_ids_seen: s_ortools_routing, s_ortools_routing, pc_shortest_path, pc_assignment, s_ortools_cpsat
- seed_ids_seen: pc_assignment, pc_shortest_path, pc_tsp, pc_vrp
- checked_directly: retrieval artifact + fixture problem.md
- uncertain: full-text of non-local URLs not fetched in CI stand-in

