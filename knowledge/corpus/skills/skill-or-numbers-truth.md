# Skill export: or-numbers-truth

- kind: skill
- source_path: .pi/skills/or-numbers-truth/SKILL.md
- note: RAG **copy** for Pi retrieve only; runtime skill loading still uses `.pi/skills/` (not this file).

---

---
name: or-numbers-truth
description: OR-Path numbers law — objective/path/tour/routes only from solve+validate; never invent optima in prose, memory, or skills.
---

# Numbers truth (always)

1. `objective`, path, tour, routes, optimal_* come **only** from `tools/solve_*` JSON + `tools/validate_solution.py`.
2. Never invent numeric optima in research, explain, paper, memory lessons, or chat.
3. If a number is discussed, point at disk solution path + validate result.
4. Schema/model stage: **no** solution-shaped keys.
5. Memory/lessons may mention process only; never treat remembered numbers as authority.

## Commands

```bat
.venv-314\Scripts\python.exe tools\solve_dispatch.py <problem_id> --mode <mode>
.venv-314\Scripts\python.exe tools\validate_solution.py --problem-id <id> --solution <path>
```
