# OR-Path Project Guide (Pi)

Durable project law for Pi sessions. Product runtime is **this repo + Pi** (`orpath.bat`), not Hermes MEMORY. **OpenPi removed** (2026-07-31).

## Specs first (SDD)

**硬法目录：`specs/`。** 实现与评审前先读：

1. **`specs/product-flow-sdd.md`** — 总流程主合同 · Demo **M0**  
2. **`specs/process-visibility.md`** — 时间线 · **sub 思考过程**怎么看见  
3. `specs/README.md` — 全册索引  

冲突优先级：`门禁真实输出` > **`product-flow-sdd.md`** ≥ **`process-visibility.md`** ≥ `specs/**` 其它分册 > 本文件 > `.hermes/plans/*` > `docs/**` > chat。

**当前产品最高优先级：**

1. **V0 实时过程台**（`process-visibility.md`）— **硬底线**  
2. **选型已冻结 S1**（`process-visibility.md` §9）：Watch 主脸；kanban/Fleet；Langfuse 可选  
3. **实时可视完工节奏：** 同文件 **§11 五阶段 P1→P5**（**P1–P5 工程已收口**，见 `docs/p5-closeout.md`）  
4. **M0** 可信数字 + 真 sub（`product-flow-sdd.md` §9）  

无 V0 工程入口不得宣称有脸。未过 **§11 P3** 不得宣称「实时可视化已满意」。S1 选型 ≠ 已实现增强。未 V0+M0 主路径前不新开记忆/MCP/大域桥史诗。  
T2 grill 冻结表：`specs/gates-and-dod.md`（历史 DoD）。  
**1.1 题面 intake：** `specs/problem-intake.md`。  
架构决策：`docs/adr/`（ADR-0001…0006）。

**不建** `.agents/`（T2）；Gemini 通道未启用。

## Project Overview

- **Product:** OR-Path Multi-Agent / Graph-OR Agent
- **Loop:** (opt intake OCR/审读) → NL/brief → retrieve/research → model (schema) → **solve** → **validate** → explain → paper → review/revise
- **Classes:** shortest_path, TSP (n=8), VRP (multi-vehicle, no time windows in T2)
- **Primary UI:** `orpath.bat menu` (host-agnostic); secondary Pi TUI (`pi.bat`). OpenPi deleted.

## Ground Rules

1. **Numbers truth:** `objective` / path / tour / routes come **only** from solve tools (`solve_dispatch` / `solve_*`) plus **validate** recompute. Never invent optima in prose or memory.
2. **Multi-agent:** Real `pi-subagents` via **`orpath.subagent_dispatch`** + **`orpath.pi_launch_law`**. Roles `or-orchestrator`, `or-researcher`, `or-modeler`, `or-writer`, `or-verifier`, `or-reviewer`. **裸 `pi -p` ≠ 多 Agent**（须 harness：`--tools …subagent`、无 write、`--mode json`）。No persona cosplay.
3. **Control plane:** **LangGraph** via **`orpath.control_plane`**. **Pi** is the **in-node** foreman (包工头), not the global boss. Subagents return **file paths**.
4. **File handoffs:** `notes/`, `outputs/`, `papers/`. Prefer paths over huge blobs in parent context.
5. **Memory:** L0 disk + L1 LG checkpointer **必须**. 运筹长期战法 → **Skill / agent md**（主加强轴）；pi-memory = 短 prefs；Cognee = 图 **smoke 旁路**（非主记忆）— **never** authoritative objectives. 详见 `specs/memory.md`。
6. **Hard gates:** schema (no optima) → solve → validate → R1/R2. Paper online R1 lives on **cloud** track.
7. **Docs surface:** living docs under `docs/` top-level; history in `docs/archive/`; out-of-band trees in `docs/OUT_OF_BAND.md`.
8. **Intake (1.1):** OCR + problem-brief + `intake.json` may precede orchestrate; **no** objectives in intake; full subproblem coverage; see `specs/problem-intake.md`. Default product: **live multi-agent ON**; intake when `--intake-in` or `inbox/` via `--auto-intake` (`ORPATH.md`). Gates force live OFF.

## Artifact layout

| Path | Use |
|------|-----|
| `specs/` | Living law (SDD) |
| `docs/README.md` | Docs navigation |
| `docs/adr/` | Architecture decisions |
| `docs/archive/` | Historical closeouts/evidence (do not bulk-load) |
| `fixtures/t1/` | T1 golden/smoke |
| `fixtures/t2/` | T2 TSP/VRP |
| `fixtures/intake/` | 1.1 intake stubs (when present) |
| `outputs/.plans/<slug>.md` | Task ledger |
| `outputs/<slug>-intake.json` | 1.1 structured intake |
| `papers/<slug>.md` | Paper draft |
| `notes/` | Research / explain / retrieval / OCR brief |
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
| Intake (1.1) | `scripts/intake_gate.py` — brief/intake 契约 + 禁键 |
| T1 | `scripts/t1_gate.py` must stay green |
| T2 | `t2_gate` + `t2_gate_cloud` + bridge proof (OpenPi screenshot retired) |

## Smoke

- T1: `docs/t1-smoke.md` — `fixtures/t1/shortest_path/`
- T2: `docs/t2-smoke.md`
- 1.1: `docs/1.1-smoke.md` — `scripts/intake_gate.py`（S1–S4）

## Status

- Topology locked 2026-07-29 (Supervisor–Worker pipeline + gates; Teams/bus out)
- T1 CLOSED/PASS — `docs/archive/closeouts/t1-closeout.md`
- T2 CLOSED/PASS — `docs/archive/closeouts/t2-closeout.md`
- 1.0 PASS — `docs/1.0-closeout.md`
- Architecture ADR-0001…0006 closed — `docs/architecture-refactor-status.md`
- **1.1 CLOSED/PASS** — `docs/1.1-closeout.md`（OCR/parse/gate + LG skip 前门；圆管 B 题 intake smoke）
- Specs first: `specs/README.md`
- Live board (archived): `docs/archive/evidence/t2-live-evidence-board.png`
