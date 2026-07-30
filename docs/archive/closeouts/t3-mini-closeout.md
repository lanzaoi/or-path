# T3-mini Closeout (Multi-CLI Grok orchestration)

**Date:** 2026-07-29  
**Status:** **CLOSED — PASS (T3-mini only)**  
**Not** a full T3 freeze (Compose/K8s/eval/codegen still open).

## Experiment

Orchestrator = this Hermes desktop session (Grok).  
Workers = parallel `hermes chat -q` CLI processes (Grok / xAI OAuth).

| Worker | Role | Result |
|--------|------|--------|
| W1 | Specs law | DONE — `specs/t3-vrp-tw.md` + gates/product pointers |
| W2 | Fixture | DONE — `fixtures/t3/vrp_tw/{locations,problem,whitelist}` |
| W3-ORCH | Solve/validate/gate | DONE — ortools CVRPTW + validate TW + `t3_gate` |
| W4 | Docs | closeout (this file) |

Evidence: `outputs/t3-multi-cli/`

## What shipped

| Layer | Deliverable |
|-------|-------------|
| Spec | `specs/t3-vrp-tw.md` |
| Fixture | `fixtures/t3/vrp_tw/` gold **objective 58** |
| Solver | `solve_ortools` Time dimension when `time_windows` present (`ortools-routing-cvrptw`) |
| Validate | capacity + time_windows + recompute distance objective |
| Gate | `scripts/t3_gate.py` → **PASS** |
| Tests | `tools/test_gates.py` 13 passed (with `PYTHONNOUSERSITE=1`) |

### Gold (solver + validate only)

```text
objective: 58
routes:
  D → C → B → D
  D → E → F → A → D
solver: ortools-routing-cvrptw
```

## Verify

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONNOUSERSITE=1
set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
.venv-314\Scripts\python.exe scripts\t3_gate.py
.venv-314\Scripts\python.exe -m pytest tools\test_gates.py -q -p no:langsmith
```

## Multi-CLI lessons

1. `hermes chat -q` workers work on Windows; log tee may buffer until process exit.  
2. Path allowlists prevent stampede; still need orchestrator merge when two writers touch specs.  
3. Numbers frozen by orchestrator after live solve — workers must not invent gold.  
4. Prefer orchestrator for shared `tools/*` edits; workers good for isolated dirs (`fixtures/t3`, docs).  
5. Shell `&` backgrounding blocked in Hermes terminal tool — use `background=true` sessions.

## Non-claims

- Not full T3 grill freeze  
- Not Compose/K8s DoD  
- Not live Pi multi-agent TW demo (T2 isolation path unchanged)  
- Not “global optimal guaranteed” beyond OR-Tools search params used  
