# Lesson: les_seed_vrp_routing

- kind: lesson
- source_path: knowledge/lessons/les_seed_vrp_routing.json
- problem_class: vrp
- schema: orpath.lesson.v1

## Summary

VRP/CVRPTW product path: OR-Tools Routing for feasible multi-vehicle solutions; claim ladder stays non-proven; validate capacity/TW.

## Key decisions

- default mode=ortools
- schema must include capacity / vehicle / demand fields when needed
- paper wording: feasible + recompute, not global optimum

## Pitfalls

- Missing distance_matrix or capacity often fails validate
- Do not upgrade Routing OPTIMAL label to MIP proven in prose

## Tags

vrp, ortools, routing, seed

## Authority

Process memory only. **Not** numeric authority. Optima only from solve+validate.
RAG holds a **searchable copy**; this is not a substitute for L0 solution JSON.
