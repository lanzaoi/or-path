# Dijkstra Shortest Path (curated OR note)

This curated note supports OR-Path hybrid retrieval smoke tests. It is **not** a substitute for solver output.

## Problem class

**shortest_path** asks for a minimum-cost walk from a source node to a target node on a directed or undirected weighted graph. Edge weights must be non-negative for the classic Dijkstra algorithm.

## Algorithm sketch

Dijkstra maintains a priority queue of tentative distances. It repeatedly extracts the unsettled node with the smallest distance and relaxes outgoing edges. When the target is dequeued (or all reachable nodes are settled), the distance label is optimal.

Key properties:

- Exact on graphs with non-negative weights
- Common implementation: binary heap \(O((V+E)\log V)\)
- NetworkX exposes `shortest_path` / `dijkstra_path` with a weight key

## OR-Path tooling

- Preferred SP solver tool: `tools/solve_networkx.py` (honest NetworkX Dijkstra)
- Objective and path come **only** from the solve tool + `validate_solution` recompute
- Domain seed graph links `pc_shortest_path` → `s_networkx_dijkstra`

## Modeling tips for researchers

- Represent the instance as `nodes` + `edges` `{u,v,w}` in the modeler schema
- Do **not** put answer `path` or `objective` in the modeler schema
- Negative weights need Bellman–Ford / other methods — out of default T2 SP smoke

## Related reading (whitelist-friendly ids)

- NetworkX shortest paths documentation
- Classic Dijkstra 1959 formulation
- Internal fixture: `fixtures/t1/shortest_path` (gold objective appears only in solution files, not memory)
