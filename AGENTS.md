# OR-Path Project Guide (Pi)

Durable project law for Pi / OpenPi sessions. Product runtime is **this repo + Pi**, not Hermes MEMORY.

## Specs first (SDD)

**硬法目录：`specs/`。** 实现与评审前先读 `specs/README.md`。

冲突优先级：`门禁真实输出` > `specs/**` > 本文件 > `.hermes/plans/*` > `docs/**`（活文档优先 `docs/README.md`；历史在 `docs/archive/`） > chat。

T2 grill 冻结表：`specs/gates-and-dod.md`。  
架构决策：`docs/adr/`（ADR-0001…0006）。

**不建** `.agents/`（T2）；Gemini 通道未启用。

## Project Overview

- **Product:** OR-Path Multi-Agent / Graph-OR Agent
- **Loop:** NL → retrieve/research → model (schema) → **solve** → **validate** → explain → paper → review/revise
- **Classes:** shortest_path, TSP (n=8), VRP (multi-vehicle, no time windows in T2)
- **Primary UI:** OpenPi (`openpi.bat`); secondary Pi TUI (`pi.bat`)

## Ground Rules

1. **Numbers truth:** `objective` / path / tour / routes come **only** from solve tools (`solve_dispatch` / `solve_*`) plus **validate** recompute. Never invent optima in prose or memory.
2. **Multi-agent:** Real `pi-subagents` via **`orpath.subagent_dispatch`**. Roles `or-orchestrator`, `or-researcher`, `or-modeler`, `or-writer`, `or-verifier`, `or-reviewer`. No persona cosplay.
3. **Control plane:** **LangGraph** via **`orpath.control_plane`**. **Pi** is the **in-node** foreman (包工头), not the global boss. Subagents return **file paths**.
4. **File handoffs:** `notes/`, `outputs/`, `papers/`. Prefer paths over huge blobs in parent context.
5. **Memory:** L0 disk + L1 LG checkpointer. pi-memory + Cognee = prefs/lessons/graph smoke — **never** authoritative objectives.
6. **Hard gates:** schema (no optima) → solve → validate → R1/R2. Paper online R1 lives on **cloud track**.
7. **Docs surface:** living docs under `docs/` top-level; history in `docs/archive/`; out-of-band trees in `docs/OUT_OF_BAND.md`.

## Artifact layout

| Path | Use |
|------|-----|
| `specs/` | Living law (SDD) |
| `docs/README.md` | Docs navigation |
| `docs/adr/` | Architecture decisions |
| `docs/archive/` | Historical closeouts/evidence (do not bulk-load) |
| `fixtures/t1/` | T1 golden/smoke |
| `fixtures/t2/` | T2 TSP/VRP |
| `outputs/.plans/<slug>.md` | Task ledger |
| `papers/<slug>.md` | Paper draft |
| `notes/` | Research / explain / retrieval |
| `runs/` | LG checkpointer (gitignored) |
| `knowledge/` | Corpus, seed graph, indexes (caches gitignored) |

## Verification gates

| Gate | Rule |
|------|------|
| Schema | Modeler JSON has no objective/solution-shaped keys |
| Solve | Tool JSON: status, objective, path\|tour\|routes, source |
| Validate | Recompute feasibility + objective |
| R1 local | Citations ⊆ whitelist ∪ retrieval evidence |
| R1 online | arXiv/DOI check on **cloud** track |
| R2 | Draft numerics ⊆ solution.json |
| Repair | tune≤3 → model≤2 → HUMAN_REQUIRED (see specs) |
| T1 | `scripts/t1_gate.py` must stay green |
| T2 | `t2_gate` + `t2_gate_cloud` + OpenPi screenshot + bridge proof |

## Smoke

- T1: `docs/t1-smoke.md` — `fixtures/t1/shortest_path/`
- T2: `docs/t2-smoke.md`

## Status

- Topology locked 2026-07-29 (Supervisor–Worker pipeline + gates; Teams/bus out)
- T1 CLOSED/PASS — `docs/archive/closeouts/t1-closeout.md`
- T2 CLOSED/PASS — `docs/archive/closeouts/t2-closeout.md`
- 1.0 PASS — `docs/1.0-closeout.md`
- Architecture ADR-0001…0006 closed — `docs/architecture-refactor-status.md`
- Specs first: `specs/README.md`
- Live board (archived): `docs/archive/evidence/t2-live-evidence-board.png`
