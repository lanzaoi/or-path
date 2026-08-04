# Solver selection matrix (product)


- kind: paper-note
- title: Solver selection matrix (product)
- source: curated

- kind: paper-note
- domain: general_or
- source: curated (skill or-solver-select companion)

| Class | Default track | Notes |
|-------|---------------|-------|
| shortest_path | networkx Dijkstra | mock only for demos |
| tsp | ortools routing / small CP-SAT | n=8 smoke |
| vrp | ortools routing capacity | multi-vehicle |
| polyomino_cover | solve_polyomino CP-SAT | pack_b for full contest |
| generic LP/MIP | HiGHS / PuLP optional | not poly default |

Wrong solve_mode → wrong or empty solution.
