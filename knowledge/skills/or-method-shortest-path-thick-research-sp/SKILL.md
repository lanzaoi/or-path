---
name: or-method-shortest-path-thick-research-sp
description: Compressed OR method from run `thick-research-sp` (shortest_path). Process playbook only — not numeric authority. Use after similar shortest_path cases.
---

# Method skill: `or-method-shortest-path-thick-research-sp`

> **Long-term process memory** (compressed).  
> **Not** L0 solution authority. Optima only from solve tools + validate.

## Provenance

- source_run_slug: `thick-research-sp`
- problem_class: `shortest_path`
- solve_mode: `networkx`
- validate_ok: `True`
- promoted_at: `2026-08-04T12:20:30Z`
- knowledge_mode: `hybrid`
- embed_mode: `live`

## Compressed playbook

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
- problem_class: shortest_path
- no objective/tour/routes/path answers in schema
- knowledge_mode: hybrid
- seed_facts: 1

## Pitfalls

- 1. Use deterministic solvers (networkx/cpsat/highs/ortools); never LLM optima.
- Do not invent objective/path in prose or skill text

## Papers / corpus hits (with this run)

- `knowledge/corpus/papers/lit_abs/r329_10.1016_j.cor.2019.01.009.md` (chunk `r329_10_1016_j_cor_2019_01_009_0003_635d39657bbd209a`)
- `knowledge/corpus/papers/lit_abs/r305_10.1007_978-0-387-77778-8_5.md` (chunk `r305_10_1007_978-0-387-77778-8_5_0000_9b6271bb7bfb68a1`)
- `knowledge/corpus/papers/lit_abs/r169_10.1287_opre.41.2.338.md` (chunk `r169_10_1287_opre_41_2_338_0001_e8c29fc6f9d1715f`)
- `knowledge/corpus/papers/lit_abs/r233_10.1016_j.cor.2021.105588.md` (chunk `r233_10_1016_j_cor_2021_105588_0003_617d365e64e03172`)
- `knowledge/corpus/papers/lit_abs/r313_10.1016_0377-2217_95_00023-j.md` (chunk `r313_10_1016_0377-2217_95_00023-j_0000_b895800b0ecff4a8`)

## Artifact pointers (disk)

- `notes/thick-research-sp-research.md`
- `notes/thick-research-sp-retrieval.json`
- `outputs/thick-research-sp-schema.json`
- `outputs/thick-research-sp-validate.json`
- `outputs/thick-research-sp-solution.json`

## How to use next time

1. If problem_class≈`shortest_path`, load this skill for process checklist.
2. Still run solve + validate; never copy numbers from this file.
3. Hybrid RAG may also retrieve the exported copy under `knowledge/corpus/skills/`.

## Authority

- Skill = compressed method / checklist.
- Lesson JSON (same promote) = searchable process memory.
- Solution JSON path is a pointer only — open validate/solution for numbers.
