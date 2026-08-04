# Lesson: les_seed_sp_dijkstra

- kind: lesson
- source_path: knowledge/lessons/les_seed_sp_dijkstra.json
- problem_class: shortest_path
- schema: orpath.lesson.v1

## Summary

SP runs: use networkx Dijkstra as default exact track; mock only for CI fixtures.

## Key decisions

- preferred_solve_mode=networkx for non-negative weights
- schema must not contain path/objective
- always validate recompute after solve

## Pitfalls

- Do not use Routing/ortools as SP propaganda track
- Do not invent path length in research notes

## Tags

shortest_path, networkx, exact, seed

## Authority

Process memory only. **Not** numeric authority. Optima only from solve+validate.
RAG holds a **searchable copy**; this is not a substitute for L0 solution JSON.
