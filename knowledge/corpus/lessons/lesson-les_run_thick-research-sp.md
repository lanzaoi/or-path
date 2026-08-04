# Lesson: les_run_thick-research-sp

- kind: lesson
- source_path: knowledge/lessons/les_run_thick-research-sp.json
- problem_class: shortest_path
- schema: orpath.lesson.v1

## Summary

Promoted method from run `thick-research-sp` class=shortest_path mode=networkx: validate OK. Skill `or-method-shortest-path-thick-research-sp` + 5 paper hit(s).

## Key decisions

- solve_mode_used=networkx
- problem_class=shortest_path
- preferred_solve_mode=networkx
- schema_field source present
- schema_field target present
- schema_field weight_key present
- schema must not carry path/tour/routes/objective as answers
- Research for `shortest_path` / `shortest_path`. Retrieval mode=hybrid.
- 2. Validate must recompute objective.
- 3. Seed/retrieval chunk_ids when present must be cited in this table.

## Pitfalls

- 1. Use deterministic solvers (networkx/cpsat/highs/ortools); never LLM optima.
- Do not invent objective/path in prose or skill text

## Tags

shortest_path, promoted, method_skill, validate_ok, networkx

## Authority

Process memory only. **Not** numeric authority. Optima only from solve+validate.
RAG holds a **searchable copy**; this is not a substitute for L0 solution JSON.
