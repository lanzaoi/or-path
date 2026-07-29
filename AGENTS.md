# OR-Path Project Guide (Pi)

Durable project law for Pi / OpenPi sessions. Product runtime is **this repo + Pi**, not Hermes MEMORY.

## Specs first (SDD)

**硬法目录：`specs/`。** 实现与评审前先读 `specs/README.md`。

冲突优先级：`门禁真实输出` > `specs/**` > 本文件 > `.hermes/plans/*` > `docs/**` > chat。

T2 grill 冻结表：`specs/gates-and-dod.md`。  
T2 施工单：`.hermes/plans/2026-07-29_105620-t2-thick-full-stack.md`（与 specs 冲突时以 specs 为准）。

**不建** `.agents/`（T2）；Gemini 通道未启用。

## Project Overview

- **Product:** OR-Path Multi-Agent / Graph-OR Agent
- **Loop:** NL → retrieve/research → model (schema) → **solve** → **validate** → explain → paper → review/revise
- **Classes:** shortest_path, TSP (n=8), VRP (multi-vehicle, no time windows in T2)
- **Primary UI:** OpenPi (`openpi.bat`); secondary Pi TUI (`pi.bat`)

## Ground Rules

1. **Numbers truth:** `objective` / path / tour / routes come **only** from solve tools (`solve_mock` / `solve_networkx` / `solve_ortools`) plus **validate** recompute. Never invent optima in prose or memory.
2. **Multi-agent:** Real `pi-subagents` roles `or-orchestrator`, `or-researcher`, `or-modeler`, `or-writer`, `or-verifier`, `or-reviewer`. No persona cosplay.
3. **Control plane:** **LangGraph** owns stage `now→next` and gates. **Pi** is the **in-node** foreman (包工头), not the global boss. Subagents return **file paths**.
4. **File handoffs:** `notes/`, `outputs/`, `papers/`. Prefer paths over huge blobs in parent context.
5. **Memory:** L0 disk + L1 LG checkpointer. pi-memory + Cognee = prefs/lessons/graph smoke — **never** authoritative objectives.
6. **Hard gates:** schema (no optima) → solve → validate → R1/R2. Paper online R1 lives on **cloud track**.

## Artifact layout

| Path | Use |
|------|-----|
| `specs/` | Living law (SDD) |
| `fixtures/t1/` | T1 golden/smoke |
| `fixtures/t2/` | T2 TSP/VRP (when added) |
| `outputs/.plans/<slug>.md` | Task ledger |
| `outputs/<slug>-*.md` | Reviews, briefs |
| `outputs/<slug>.provenance.md` | Provenance |
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
- T2: `docs/t2-smoke.md` (when written)

## Status

- Topology locked 2026-07-29 (Supervisor–Worker pipeline + gates; Teams/bus out)
- T1 CLOSED/PASS — `docs/t1-closeout.md`
- T2 **CLOSED/PASS** — `docs/t2-closeout.md` (gates + live Pi multi-agent TSP); OpenPi GUI screenshot optional polish
- Specs first: `specs/README.md`
- Live board: `docs/t2-live-evidence-board.png`
