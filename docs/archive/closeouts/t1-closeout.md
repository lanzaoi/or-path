# T1 Closeout

**Date:** 2026-07-29  
**Status:** **CLOSED — PASS** (core + three-day thicken; optional OpenPi GUI screenshot non-blocking)

## What shipped

| Layer | Deliverable |
|-------|-------------|
| Pi agents | `.pi/agents/or-{orchestrator,researcher,modeler,writer,verifier,reviewer}.md` |
| Project law | `AGENTS.md`, `.pi/settings.json` (pi-subagents) |
| Fixture | `fixtures/t1/shortest_path/*` (objective **42**) |
| Tools | `tools/solve_mock.py`, `solve_ortools.py` (NetworkX), gates R1/R2/schema + pytest |
| Control plane | `orpath/` LangGraph runner `run_t1.py` |
| Gates | `scripts/t1_gate.py`, `scripts/t1_negatives.py` |
| Docs | `docs/t1-smoke.md`, `t1-evidence.md`, `t1-day2-day3.md`, `t1-portfolio-talk.md`, `README.md` |
| Live multi-agent | Pi CLI: researcher, modeler, writer, verifier (transcripts local under `.pi-subagents/`, gitignored) |

## Verification

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONNOUSERSITE=1
.venv-314\Scripts\python.exe scripts\t1_gate.py
```

Expected: **PASS: t1_gate** (pytest + negatives + LG mock pipeline).

## Dual path (intentional)

- **CI / gate:** deterministic LG nodes + tools  
- **Live multi-agent:** Pi/OpenPi + pi-subagents  

## Explicit non-goals left open (not failures)

- OpenPi GUI screenshot (optional portfolio polish)
- LG node spawning Pi in-process
- pi-memory / Cognee / LightRAG production wire
- Second problem-class fixture

## Next

**T2** — solver/validate contracts, knowledge stack slices per `IDEA.md`.  
Do not reopen T1 DoD unless a regression fails `t1_gate`.

## Git baseline

See `main` history on this repo (`Desktop/agent`). Heavy trees (`openpi/`, `pi-main/`, `node_modules/`, `vendor/`, generated `outputs/`/`notes/`/`papers/`) stay gitignored; OpenPi remains its own nested git checkout on disk.
