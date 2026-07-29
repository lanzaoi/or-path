# Seed graph

L4 domain seed: `or_domain_seed.json`

Node types: `ProblemClass`, `Constraint`, `Solver`, `Case`.

Query:

```bat
set PYTHONNOUSERSITE=1
.venv-314\Scripts\python.exe -m knowledge_svc.seed_graph_query --class tsp
```
