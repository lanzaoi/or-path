# OR-Tools Routing dimensions for CVRP


- kind: paper-note
- title: OR-Tools Routing dimensions for CVRP
- source: curated

- kind: paper-note
- domain: vrp
- source: curated

## Dimensions

- **Distance/time** dimension for arc costs
- **Capacity** dimension with demand callback and vehicle capacity upper bounds
- Optional start/end cumulatives at depot

## Search

- First solution strategies + local search metaheuristics
- Time limits: product may tune ≤3 times on validate red (bounded repair)

## Output

`routes`: list of node sequences per vehicle; `objective` only from solver.
