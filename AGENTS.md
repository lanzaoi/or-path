# OR-Path Project Guide (Pi)

Durable project law for Pi / OpenPi sessions. Product runtime is **this repo + Pi**, not Hermes MEMORY.

## Project Overview

- **Product:** OR-Path Multi-Agent / Graph-OR Agent
- **Loop:** NL problem → research → model (schema) → **deterministic solve** → explain → paper draft → review/revise
- **Classes:** shortest path, TSP, VRP, routing/assignment
- **Primary UI:** OpenPi (`openpi.bat`); secondary Pi TUI (`pi.bat`)

## Ground Rules

1. **Numbers truth:** `objective`, optimal path, and costs come **only** from solve tools (`solve_mock` / `solve_ortools`) or their JSON artifacts. Never invent optima in prose.
2. **Multi-agent:** Use real `pi-subagents` roles `or-orchestrator`, `or-researcher`, `or-modeler`, `or-writer`, `or-verifier`, `or-reviewer`. Do not cosplay roles in one transcript.
3. **Control plane:** LangGraph owns stage `now→next` and gates when running `orpath/run_t1.py`. Pi subagents work **inside** nodes and return file paths.
4. **File handoffs:** Intermediate results go to `notes/`, `outputs/`, `papers/`. Prefer paths over dumping huge blobs into parent context.
5. **Memory:** Working memory = disk artifacts + LG state. Optional `pi-memory` is prefs/lessons only — never store objectives there.

## Artifact layout

| Path | Use |
|------|-----|
| `fixtures/t1/` | Golden/smoke cases |
| `outputs/.plans/<slug>.md` | Task ledger + verification log |
| `outputs/<slug>-*.md` | Reviews, briefs |
| `outputs/<slug>.provenance.md` | Provenance sidecar |
| `papers/<slug>.md` | Paper-style draft |
| `notes/` | Research / explain notes |
| `runs/` | LG checkpointer sqlite (gitignored) |

## Verification gates

- Schema gate: modeler JSON has no `objective`
- Solution gate: tool JSON has `status`, `objective`, `path`, `source`
- R1: citations ⊆ whitelist ∪ research evidence
- R2: draft numerics ⊆ `solution.json`
- Review: FATAL must be fixed or `HUMAN_REQUIRED` after max 2 revises

## T1 smoke

See `docs/t1-smoke.md`. Default case: `fixtures/t1/shortest_path/`.

## Status

- Topology locked 2026-07-29 (Supervisor–Worker pipeline + gates; Teams/bus out)
- Shell: this repo + OpenPi — not Feynman primary
