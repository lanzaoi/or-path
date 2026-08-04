# Lesson: les_seed_tsp_cpsat

- kind: lesson
- source_path: knowledge/lessons/les_seed_tsp_cpsat.json
- problem_class: tsp
- schema: orpath.lesson.v1

## Summary

Small TSP (e.g. n=8): CP-SAT circuit is default proven track; HiGHS dual optional; Routing is expansion only.

## Key decisions

- default mode=cpsat for portfolio TSP
- meta.exact=true and proven_optimal only on exact solvers
- validate must recompute tour cost

## Pitfalls

- Never claim ortools Routing as MIP proven optimal
- Do not put tour into schema JSON

## Tags

tsp, cpsat, exact, seed

## Authority

Process memory only. **Not** numeric authority. Optima only from solve+validate.
RAG holds a **searchable copy**; this is not a substitute for L0 solution JSON.
