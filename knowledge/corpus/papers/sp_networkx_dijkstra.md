# Shortest path — NetworkX Dijkstra


- kind: paper-note
- title: Shortest path — NetworkX Dijkstra
- source: curated

- kind: paper-note
- domain: shortest_path
- source: curated (pairs with root dijkstra note)

## Problem

Single-source / s–t shortest path on non-negative weighted digraphs or undirected graphs.

## Product

- `problem_class`: `shortest_path`
- Tool: `tools/solve_networkx.py` (Dijkstra / shortest_path)
- Gold smoke objective **42** on T1 fixture — only after solve+validate
- Schema: nodes, edges, source, target — **no** path list / objective

## Pitfalls

- Negative weights → Dijkstra invalid; need Bellman–Ford (out of default claim unless registered)
- Mock mode is demo-only, not a real optimum authority
