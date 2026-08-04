# VRP vs TSP — classification for agents


- kind: paper-note
- title: VRP vs TSP — classification for agents
- source: curated

- kind: paper-note
- domain: vrp
- source: curated

| | TSP | CVRP |
|--|-----|------|
| Vehicles | 1 tour | Multiple |
| Capacity | Usually none | Yes |
| Solution shape | `tour` | `routes` |
| OR-Path class | `tsp` | `vrp` |

Misclassifying CVRP as TSP drops capacity and yields wrong problem.
