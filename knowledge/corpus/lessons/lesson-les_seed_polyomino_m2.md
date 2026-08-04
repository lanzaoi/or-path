# Lesson: les_seed_polyomino_m2

- kind: lesson
- source_path: knowledge/lessons/les_seed_polyomino_m2.json
- problem_class: polyomino_cover
- schema: orpath.lesson.v1

## Summary

Polyomino domain bridge: use polyomino solve mode via dispatch; schema uses board/pieces fields; validate recompute coverage.

## Key decisions

- problem_class=polyomino_cover
- solve_mode=polyomino
- register via domain_registry + solve_dispatch

## Pitfalls

- Do not fake SP fixture as polyomino success
- Large boards may need specialized q3 solver path

## Tags

polyomino, m2, seed

## Authority

Process memory only. **Not** numeric authority. Optima only from solve+validate.
RAG holds a **searchable copy**; this is not a substitute for L0 solution JSON.
