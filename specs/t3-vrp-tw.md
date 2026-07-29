# T3-mini — VRP with Time Windows (CVRPTW)

**Status:** mini vertical slice (multi-CLI experiment 2026-07-29)  
**Not** a full T3 grill freeze.

## Scope

| Item | Lock |
|------|------|
| Fixture | `fixtures/t3/vrp_tw/` |
| `problem_class` | `vrp` (TW is fixture-level, not a new class enum) |
| Solver | `tools/solve_ortools.py` → `ortools-routing-cvrptw` when `time_windows` present |
| Validate | capacity + coverage + **time_windows** + recompute objective (distance) |
| Gate | `scripts/t3_gate.py`; must keep `t1_gate` + `t2_gate` green |
| Numbers | gold `solution.json` only from solver stdout + validate green |

## Fixture contract (`locations.json`)

Inherits T2 VRP fields, plus:

- `time_windows`: `{ node_id: [ready, due] }` integers  
- `service_times`: `{ node_id: int }` (depot 0)  
- travel_time = rounded Euclidean distance (unit speed 1)  
- Waiting until `ready` is allowed; service start must be ≤ `due`

## Non-goals

- Full T3 grill / Compose+K8s hard DoD / codegen sandbox  
- Reopening T1/T2 DoD  
- Self-built SOTA eval narrative  

## Verify

```bat
set PYTHONNOUSERSITE=1
.venv-314\Scripts\python.exe scripts\t3_gate.py
```
