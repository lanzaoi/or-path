# T3 LG Closeout

**Date:** 2026-07-29  
**Status:** **CLOSED — PASS** (LG product skeleton vertical complete; DoD E freeze in `specs/t3-lg-skeleton.md`)

## What shipped

| Layer | Deliverable |
|-------|-------------|
| Specs SDD | `specs/t3-lg-skeleton.md` (Q1-E DoD + full Q table); `specs/control-plane.md`; `specs/gates-and-dod.md` T3 section |
| Product graph | `orpath/graph_product.py` (full nodes + conditional routing + bridge); `orpath/nodes_product.py`; `orpath/stage_map.json`; `docs/t3-stage-map.mmd` |
| Runner / CLI | `orpath/run_orpath.py` (run + status + resume + list + --from-stage + --fresh + dirty detection + checkpoint id); `orpath/run_t2.py` (thin delegate); `orpath.bat` (run/status/resume/list/gate-t3) |
| Persistence | Sqlite checkpointer `runs/orpath.sqlite`; per-thread `runs/<thread_id>/stages/*.json` (every node exit); `artifact_hashes.json` manifest; `checkpoint_id.txt` |
| Bridge | In-graph `bridge_pi` (default attachment=`before_research`; configurable before_retrieve); integrated in product topology |
| Delegation / dual-path | T1 stays on old `graph.py` + `run_t1.py`; T2 delegates to product via `run_t2.py` (Q16-C) |
| Control / owner | `orpath/node_context.py` (NodeContext: snapshot on exit, hash update, assert_owner — non-solve nodes blocked from objective/solution fields) |
| Gates | `scripts/t3_lg_gate.py` (topology export, stage_map, owner asserts, happy path mock run, sqlite, status, dirty tamper→resume exit-3, graph compile); `scripts/t3_gate.py` (business matrix + hybrid smoke) |
| Business matrix (golds only from solve+validate) | shortest_path:42 (mock); tsp_n8:45 (ortools); vrp_multi:58 (ortools); vrp_tw:58 (ortools + TW meta) — hybrid smoke also validated |
| Multi-agent construction | Hermes (orchestrator) + optional CLI leaf workers (pattern established in t3-mini) |
| OUT (non-goals / future) | compose/k8s hard, codegen sandbox, OpenPi deep UI changes, Teams/bus, new problem classes beyond matrix, heavy eval |

## Verify (engineering gates)

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONNOUSERSITE=1
orpath.bat gate-t3
```

Or direct (venv):
```bat
.venv-314\Scripts\python.exe scripts\t3_lg_gate.py
.venv-314\Scripts\python.exe scripts\t3_gate.py
```

Optional live:
```bat
set ORPATH_LIVE_PI=1
.venv-314\Scripts\python.exe scripts\t3_gate_live.py
```

Expected: PASS: t3_lg_gate ; PASS: t3_gate (matrix + golds 42/45/58/58)

## Evidence from runs (honest artifacts)

- t3-lg-sp-mock (SP42): snapshots include bridge_pi, retrieval, research, model, solve, validate, explain, ..., provenance; artifact_hashes.json present; sqlite records checkpoint
- t3-mat-* runs for TSP/VRP/TW confirm full pipeline + R1/R2 gates inside summary
- status / list / resume path exercised in gate + runner code
- t2 delegation: run_t2 thin wrapper → cmd_run (product)
- t1 unchanged (old graph)

## Status & claim ladder (honest)

- **Engineering PASS** when `t3_lg_gate` + `t3_gate` green (confirmed by artifacts + solution files matching known golds SP42 / TSP45 / VRP58 / TW58; no invented numbers).
- `orpath.bat` surface complete for product (run/status/resume/list/gate-t3).
- Sqlite + stage snapshots + artifact hash manifest + dirty detection + from-stage + bridge default before_research: delivered.
- graph_product + NodeContext owner/snapshot: delivered.
- Full portfolio polish items (OpenPi GUI screenshot + resume dual-frame visual trace + live bridge transcript + multi-CLI orchestration record) **may be human residual** (non-blocking for engineering close).
- t3_gate_live is optional (soft by default; hard only under T3_REQUIRE_LIVE=1).
- **Do not claim:** complete T3 (Q12 OUT items locked), production readiness beyond skeleton, "always optimal", full live Pi multi-agent demo for all classes, k8s/compose/codegen.

## Next

T3+ (deeper eval, new classes, cloud track, OpenPi integration) when requested.  
Do not reopen T3 LG skeleton DoD unless `t3_lg_gate` or `t3_gate` regresses.

See also: `docs/t3-portfolio-talk.md`, `specs/t3-lg-skeleton.md`, `outputs/t3-lg/`, `runs/*/stages/`.
