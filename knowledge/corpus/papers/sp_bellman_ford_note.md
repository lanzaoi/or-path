# Shortest path — Bellman–Ford (awareness)


- kind: paper-note
- title: Shortest path — Bellman–Ford (awareness)
- source: curated

- kind: paper-note
- domain: shortest_path
- source: curated textbook summary

## Idea

Relax all edges |V|−1 times; detects negative cycles.

## When vs Dijkstra

| Graph | Prefer |
|-------|--------|
| Non-negative weights | Dijkstra (default product) |
| Negative edges, no neg cycle needed handling | Bellman–Ford |
| Dense all-pairs | Floyd–Warshall (not default OR-Path SP) |

## Product note

OR-Path default SP track remains NetworkX Dijkstra unless a future adapter registers BF. Research may mention BF; solve still uses dispatch.
