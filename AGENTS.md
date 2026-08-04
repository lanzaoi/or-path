# OR-Path Project Guide (Pi)

Durable project law for Pi sessions. Product runtime is **this repo + Pi** (`orpath.bat`), not Hermes MEMORY. **OpenPi removed** (2026-07-31).

## Specs first (SDD)

**硬法目录：`specs/`。** 实现与评审前先读：

1. **`specs/product-flow-sdd.md`** — 总流程主合同 · Demo **M0**  
2. **`specs/process-visibility.md`** — 时间线 · **sub 思考过程**怎么看见  
3. **`specs/README.md`** — 全册索引  
4. **`docs/ARCHITECTURE.md`** — 当前架构简图  

冲突优先级：`门禁真实输出` > **`product-flow-sdd.md`** ≥ **`process-visibility.md`** ≥ `specs/**` 其它分册 > 本文件 > `docs/archive/plans/*` > `docs/**` > chat。  
（`.hermes/` 为本机 IDE 区，**不入库**；历史计划在 `docs/archive/plans/`。）

**当前产品最高优先级：**

1. **V0 实时过程台**（`process-visibility.md`）— **硬底线**  
2. **选型已冻结 S1**：Watch 主脸（`process-visibility.md` §9）  
3. **P1–P5** 工程已收口（见 `docs/archive/closeouts/` / p5）  
4. **M0** 可信数字 + 真 sub（`product-flow-sdd.md` §9）  
5. **L1/L2 安装可复现**（`docs/install.md` · Release v0.2.0）  

无 V0 工程入口不得宣称有脸。S1 选型 ≠ 已实现增强。未 V0+M0 主路径前不新开记忆/MCP/大域桥史诗。  
**不建** `.agents/`（T2）；Gemini 通道未启用。

## Project Overview

- **Product:** OR-Path Multi-Agent / Graph-OR Agent  
- **Loop:** (opt intake) → research → model (schema) → **solve** → **validate** → explain → paper  
- **Classes:** shortest_path, TSP (n=8), VRP, **polyomino** (M2), tube (demo)  
- **UI:** `START-CASE` / `START-WATCH` / `orpath.bat`；次要 `pi.bat`  

## Ground Rules

1. **Numbers truth:** objective 等只来自 solve tools + validate。禁止散文编最优。  
2. **Multi-agent:** 真 `pi-subagents` via harness；裸 `pi -p` ≠ 多 Agent。  
3. **Control plane:** LangGraph；Pi = 节点内包工头。  
4. **File handoffs:** `notes/` `outputs/` `papers/`；路径优于大 blob。  
5. **HOME ≠ WORKDIR：** 安装根 vs 案例目录。  
6. **Docs：** 活文档 `docs/` 顶层极少；历史只进 `docs/archive/`。边界见 `docs/repo-surface.md`。  
7. **Intake (1.1):** 可选题面；禁 objective；见 `specs/problem-intake.md`。  

## Artifact layout

| Path | Use |
|------|-----|
| `specs/` | Living law |
| `docs/` | Living docs + `archive/` |
| `docs/ARCHITECTURE.md` | Architecture snapshot |
| `orpath/` `tools/` `scripts/` | Product code |
| `fixtures/` | Golden / smoke |
| `demo/seed/` | Default Watch replay |
| `outputs/` `runs/` `papers/` `notes/` | Workdir artifacts (root gitignore) |

## Verification (short)

| Gate | Command / rule |
|------|----------------|
| Doctor | `orpath.bat doctor` |
| T1 / T2 | `t1_gate` / `t2_gate` |
| M1 / M2 | `m1_gate` / `m2_gate` |
| L2 pack | `l2_release_gate --zip …` |
| Numbers | solve JSON + validate recompute |

## Smoke pointers

- V0 Watch: `docs/v0-smoke.md`  
- M0 / M1 / M2: `docs/m0-smoke.md` · `m1-smoke.md` · `m2-polyomino.md`  
- T1 / T2 / 1.1: `docs/t1-smoke.md` · `t2-smoke.md` · `1.1-smoke.md`  
- Install: `docs/install.md`  

## Status (compact)

- T1–T2 / 1.0 / 1.1 CLOSED — `docs/archive/closeouts/`  
- V0/M0/M1/M2 engineering closed — living smoke/closeout under `docs/`  
- L2 public pack v0.2.0 — GitHub Releases  
- Knowledge RAG v1–v3 CLOSED (~88–92%)
- promote-run + tube LIVE green (heuristic)
- M3/M4 not open  
