# Skill export: or-solver-select

- kind: skill
- source_path: .pi/skills/or-solver-select/SKILL.md
- note: RAG **copy** for Pi retrieve only; runtime skill loading still uses `.pi/skills/` (not this file).

---

---
name: or-solver-select
description: Choose OR-Path solve_mode by problem class — SP networkx, TSP cpsat (+highs), VRP ortools honest non-proven, polyomino adapter, mock for CI.
---

# Solver selection (claim ladder)

| problem_class | default mode | claim |
|---------------|--------------|-------|
| shortest_path | `networkx` | exact proven (Dijkstra) |
| tsp | `cpsat` | exact; optional `highs` dual |
| vrp / vrp_tw | `ortools` | feasible search, **not** proven optimal |
| polyomino_cover | `polyomino` | CP-SAT cover; check meta |
| tube_cut | `tube` | heuristic FEASIBLE |
| CI / no solver | `mock` | fixture only |

## Rules

1. Prefer exact track when class + size allow (SP any non-neg; TSP small n).
2. Never advertise Routing/`ortools` as MIP proven optimal.
3. Always run validate after solve.
4. Set schema `preferred_solve_mode` to match table; do not invent engines.

## Dispatch

```bat
python tools\solve_dispatch.py <problem_id> --mode networkx|cpsat|highs|ortools|polyomino|tube|mock
```

See `docs/solver-stack.md` and `specs/solvers-and-validate.md`.
