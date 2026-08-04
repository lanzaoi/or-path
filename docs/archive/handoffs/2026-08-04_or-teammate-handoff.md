# OR-Path 交接文档（给运筹学深耕队友）

**日期：** 2026-08-04  
**角色分工：**  
- **技术栈侧（已基本完成）：** 流水线、Watch 过程脸、门禁、知识 RAG、LIVE 多 Agent 壳、求解器接缝、论文门、安装/发布。  
- **运筹学侧（请你深耕）：** 各问题类的模型质量、精确/启发式算法、共切与几何、目标函数与下界、和「强手答卷」对齐的指标、新域 adapter 的数学与实现。

**产品法（硬）：** `specs/`（先读 `specs/README.md` → `product-flow-sdd.md` → `solvers-and-validate.md`）。  
**仓库：** https://github.com/lanzaoi/or-path  
**本机副本：** `%LOCALAPPDATA%\Temp\orpath-handoff-or-teammate-2026-08-04.md`  
**仓内：** `docs/archive/handoffs/2026-08-04_or-teammate-handoff.md`

---

## 0. 你需要先建立的心智模型（3 分钟）

OR-Path **不是**「让大模型直接报最优解」的聊天机器人，而是：

```text
题面 →（可选 OCR/intake）→ 检索研究 → 建模 schema（禁止写最优值）
     → 【求解器 / 算法代码出数字】→ validate 重算
     → 解释 / 论文（R1 引用 · R2 数字绑定 · claim_map 诚实）
```

| 角色 | 干什么 | 不干什么 |
|------|--------|----------|
| **LangGraph（orpath/）** | 翻页：阶段、回修、HUMAN | 不算最优 tour |
| **Pi 子 Agent** | research / model / cite 隔离干活 | 权威 optima |
| **tools/solve_*** | **数字唯一权威入口** | 散文最优 |
| **validate** | 重算/可行性，证伪瞎编 | — |
| **Watch** | 读盘做过程脸 | 不用 LLM 编时间线 |
| **RAG / Skills** | 给 research **提示与战法** | 不当答案库 |
| **MCP** | 可选 Host 暴露只读/校验类工具 | 主链默认不依赖 MCP |
| **Hermes** | 你同事的 IDE Agent（规划/门禁） | **不是**产品运行时 |

**HOME ≠ WORKDIR：**  
- 安装根 = 本仓库（代码、fixtures、skills）  
- 案例目录 = 用户题的 `outputs/ notes/ papers/ runs/`（产物只写这里）

---

## 1. 端到端工作流（串起来）

### 1.1 产品主链路（节点顺序）

```text
(intake_ocr → intake_parse)? 
  → orchestrate 
  → retrieve          ← knowledge hybrid / seed
  → bridge_pi 
  → research          ← LIVE 时可真 Pi sub（or-researcher）
  → model             ← LIVE 时可真 Pi sub（or-modeler）；no-live 确定性 schema
  → gate_schema       ← 禁 objective / 解形状键
  → solve             ← solve_dispatch → 具体 adapter
  → gate_validate     ← validate_solution 重算
  → explain 
  → draft_paper 
  → cite_pack         ← LIVE 时可 cite sub；R1
  → review_pack       ← R2 + claim_map
  → revise_or_done    ← 有限次确定性修订
  → provenance        → end
```

失败可 repair（schema / solver_tune / revise）；耗尽 → `HUMAN_REQUIRED.md`。

### 1.2 用户怎么启动

| 入口 | 场景 |
|------|------|
| `START-WATCH.bat` | 默认 **seed 回放**（演示脸，不是现算竞赛） |
| `START-CASE.bat` | **路径 A**：选本地案例文件夹，边跑边看 |
| `orpath.bat …` | 全命令（doctor / gates / knowledge / run） |
| `scripts/orpath_watch_run.py --live` | **真 LIVE 多 Agent**（必须带 `--live`） |

**LIVE 示例（B 题圆管）：**

```bat
.venv-314\Scripts\python.exe scripts\orpath_watch_run.py ^
  --workdir C:\path\to\case ^
  --slug my-tube-live ^
  --live --keep-watch ^
  --auto-intake --intake-in C:\path\to\case\inbox\problem.pdf ^
  --problem-id tube_cut_b2026 --problem-class tube_cut --solve-mode tube
```

- **有 `--live`：** research/model/cite 可拉真 Pi subagent（慢、有磁盘轨迹）。  
- **无 `--live`：** 确定性/no-live 捷径（快，可绿，但 **不是**真 MA 演示）。

### 1.3 数字与论文如何咬合

```text
solve_*.py 写出 solution.json
    │  objective / status / meta.proven_optimal / shape…
    ▼
validate_solution.py 重算 → validate.json（ok / checks[]）
    │
    ▼
论文草稿只允许引用 solution 里出现过的数
    │
    ├─ R1  cite：URL/白名单
    ├─ R2  numeric：大数字 ⊆ solution tokens
    └─ claim_map：客观声明映射；禁「global optimal」除非 meta.proven_optimal
```

**你做算法时：** 改的是 `tools/solve_*.py`（或新 adapter），并保证 `validate` 仍能重算；**不要**只改论文散文。

### 1.4 知识轨（RAG）在链路哪一环（**默认强制 hybrid**）

```text
knowledge/corpus/papers (+ skills/lessons 副本)
        │ knowledge-sync / ingest（BM25 + FTS + RRF ± live embed）
        ▼
retrieve 节点 **默认 hybrid** → notes/<slug>-retrieval.json（应有 hits）
        ▼
research **必须**引用 hit 中的方法名/chunk_id（列生成、模式生成、共切…）
        ▼
model / solve —— 数字仍只来自求解器
```

关强制：`ORPATH_KNOWLEDGE_MODE=seed|off`。书库清单见 **§12**。

跑完题可：

```bat
orpath.bat promote-run --slug <slug>
```

压缩 **过程战法** → `.pi/skills/or-method-…` + `knowledge/lessons/` → allowlist → 再 sync。  
**禁止**把 objective/tour 当 skill 正文权威。

---

## 2. 求解器与算法栈（运筹核心接口）

### 2.1 统一调度

| 入口 | 路径 | 说明 |
|------|------|------|
| **唯一调度** | `tools/solve_dispatch.py` | `solve()` / `validate()`；产品节点只认它 |
| 信封规范 | `tools/solve_envelope.py` | status / objective / source / meta |
| 校验 | `tools/validate_solution.py` | 重算与可行性 |

```bat
.venv-314\Scripts\python.exe tools\solve_dispatch.py <problem_id> --mode networkx|cpsat|highs|ortools|polyomino|tube|mock
.venv-314\Scripts\python.exe tools\validate_solution.py --problem-id <id> --solution path\to\solution.json
```

### 2.2 Adapter 一览（mode → 脚本 → 数学含义）

| mode | 脚本 | 问题类 | 精确性话术 | 金标/演示 objective |
|------|------|--------|------------|---------------------|
| `networkx` | `solve_networkx.py` | shortest_path | **exact**（Dijkstra） | **42** |
| `cpsat` | `solve_cpsat.py` | TSP 小 n | **exact**（CP-SAT） | **45** |
| `highs` | `solve_highs.py` | 小 MIP/TSP | exact（视求解状态） | — |
| `ortools` | `solve_ortools.py` | VRP / CVRPTW 等 | **搜索 FEASIBLE**，非 proven global | VRP **58** |
| `polyomino` | `solve_polyomino.py` (+ q3) | polyomino_cover | CP-SAT；meta 标 exact/proven | Q1.1 **6** |
| `tube` | `solve_tube_cut_b2026.py` | tube_cut / cutting_stock | **BFD 启发式 FEASIBLE** | Q3 **99000**（演示） |
| `mock` | `solve_mock.py` | CI/fixture | fixture 绑定 | 门禁用 |

注册表：`ADAPTER_SCRIPTS` in `solve_dispatch.py`；类名：`orpath/domain_registry.py`。

### 2.3 当前各域 OR 质量（诚实）

| 域 | 技术是否接通 | 运筹深度 | 你可深耕的方向 |
|----|--------------|----------|----------------|
| 最短路 | ✅ 金标绿 | 经典 Dijkstra，够演示 | 多源/约束最短路扩展 |
| TSP | ✅ 小 n exact | 小规模够 | 更大 n 的近似/分支 |
| VRP/TW | ✅ ortools 路由 | 实用搜索，非证明最优 | 邻域搜索、ALNS、下界 |
| Polyomino | ✅ M2 域桥 | CP-SAT cover | 更大板、多问、层次分解 |
| **Tube 异形圆管** | ✅ 管线/LIVE 绿 | **启发式偏弱**（共切粗） | **几何共切 + 序列优化 + 多期余料**（对照强手答） |

**Tube 与强手 GPT 迭代稿对照（同题口径，均非 proven OPTIMAL）：**

| 问 | 本仓库现状（量级） | 强手参考稿（量级） | 差距含义 |
|----|--------------------|--------------------|----------|
| Q1 母材 | 100000 | 100000 | 齐平 |
| Q2 共切 | ~464 | ~2400 | **共切模型/搜索弱一个数量级** |
| Q3 母材 | 99000 | 97000 | 差 ~2k mm |
| Q4 新母材 | 260000 | 252000 | 差 ~8k mm |

→ **技术栈已能跑通交卷流水线；指标要逼近强手，必须改 tube 几何与算法，而不是再堆 MCP。**

### 2.4 求解器相关 Skill（给建模/选型读）

| Skill（`.pi/skills/`） | 用途 |
|------------------------|------|
| `or-numbers-truth` | 数字只信 solve+validate；禁 LLM optima |
| `or-solver-select` | 何时 networkx/cpsat/ortools/… |
| `or-modeling` | 建模 schema 口径、禁键 |
| `or-process-memory` | 过程记忆 / lesson 纪律 |
| `operations-research-algorithm-developer` | 算法开发总册（启发式、MIP、路由…） |
| `alns-metaheuristic` | ALNS |
| `pyvrp-engine` / `vrplib-instances` | VRP 生态 |
| `pyjobshop-scheduling` / `production-scheduling` | 调度 |
| `inventory-demand-planning` | 库存需求 |
| `cuopt-*` | NVIDIA cuOpt 相关（安装/API/建模，**可选**；未当主路径默认） |
| `or-method-shortest-path-thick-research-sp` | promote-run 示例战法 |

**白名单进 RAG 副本的**（`knowledge/export_allowlist.txt`）：  
`or-numbers-truth` · `or-solver-select` · `or-process-memory` · `or-modeling` · `operations-research-algorithm-developer` · 及 promote 生成的 `or-method-*`。

运行时 Pi 读 **`.pi/skills/`**；RAG 只是 **可检索副本**，不是第二权威。

---

## 3. Tools 全景（按流水线阶段）

> 权威清单代码：`orpath/tool_catalog.py`（`orpath.bat tools-list` 可打印）。

### 3.1 Intake（读题，不求解）

| 工具 | 路径 | 作用 |
|------|------|------|
| intake_ocr | `tools/intake_ocr.py` | PDF/图 → 文本（backend 写实） |
| intake_parse | `tools/intake_parse.py` | 结构化 brief / 禁解键 |
| gate_intake | `tools/gate_intake.py` | intake 门 |
| s4 checks | `tools/intake_s4_checks.py` | 额外检查 |

### 3.2 知识检索

| 模块 | 路径 | 作用 |
|------|------|------|
| knowledge_svc | `knowledge_svc/` | ingest · retrieve · FTS · BM25 · embed · MinerU client |
| 语料 | `knowledge/corpus/` · `lessons/` · `export_allowlist.txt` | 书库与 skill 副本 |
| 门禁 | `scripts/phase*_*.py` · `phase5-v3-gate` | RAG 分层验收 |
| 沉淀 | `scripts/promote_run_to_skill.py` | 跑完题 → skill/lesson |

```bat
set ORPATH_KNOWLEDGE_PROFILE=research
orpath.bat knowledge-sync
orpath.bat phase5-v3-gate
orpath.bat promote-run --slug <slug>
```

### 3.3 建模与求解门

| 工具 | 路径 | 作用 |
|------|------|------|
| gate_schema | `tools/gate_schema.py` | schema 形状 + **禁 optima 键** |
| solve_* | 见 §2 | 出数字 |
| validate_solution | `tools/validate_solution.py` | 重算（**MCP 可暴露**） |

### 3.4 论文与诚实

| 工具 | 路径 | 作用 |
|------|------|------|
| r1_cite_check | `tools/r1_cite_check.py` | 引用/URL |
| r1_claim_map | `tools/r1_claim_map.py` | 声明映射；global-opt 规则；过程计数已 mask |
| r2_numeric_check | `tools/r2_numeric_check.py` | 数字 ⊆ solution |
| paper 协议 | `orpath/paper_workflow.py` · `paper_protocol.py` | 草稿/修订 |

### 3.5 过程与记忆

| 模块 | 路径 | 作用 |
|------|------|------|
| process_memory | `orpath/process_memory.py` | L0 后自动 lesson 草稿等 |
| Watch | `orpath/watch_*.py` · `scripts/orpath_watch_run.py` | 过程脸 |
| 证据盘 | `outputs/.agents/<slug>/` · `runs/<slug>/stages/` | 真 MA / 阶段快照 |

---

## 4. Skills 怎么参与工作流

```text
                    ┌─────────────────────────┐
                    │  .pi/skills/*/SKILL.md  │  ← 运行时手册（Pi 打开）
                    └───────────┬─────────────┘
                                │ export_allowlist + knowledge-sync
                                ▼
                    ┌─────────────────────────┐
                    │ knowledge/corpus/skills │  ← 仅检索副本
                    └───────────┬─────────────┘
                                │ retrieve
                                ▼
                         research 节点提示
                                │
                                ▼
              model 写 schema（仍无 optima）→ solve 算法
```

**运筹队友写 skill 时：**  
写「如何选模型/如何验收/常见坑」，**不要**写「这题最优一定是 6」。  
数字结论只应来自你改完的 **solve+validate**。

---

## 5. MCP 怎么接（可选，非主链）

| 命令 / 入口 | 含义 |
|-------------|------|
| `orpath.bat mcp` | 产品 MCP server（`orpath/mcp_server.py`，白名单窄：偏 validate/meta/memory） |
| `orpath.bat mcp-highs` | HiGHS 相关 MCP（若环境已配） |
| `orpath.bat mcp-ortools` | OR-Tools 相关 MCP（若环境已配） |

**原则（当前产品法）：**  
- 主链 **默认不靠 MCP** 才能绿。  
- MCP = 给外部 Host（Cursor/Claude 等）挂工具的可选面。  
- **solve 出 optima 的脚本默认 `mcp_expose=False`**，避免外部随便当黑盒最优器误用。  
- M4「记忆/MCP 史诗」**未开**——不要把 MCP 做成第二控制面。

你若要在自己的 OR 实验里用 MCP 调 HiGHS/OR-Tools，可以，但 **合入产品金标** 仍应走 `solve_dispatch` + validate。

---

## 6. 技术栈侧已交付清单（你可当「底座已稳」）

| 层 | 状态 |
|----|------|
| LG 产品图 + Watch + HOME/WORKDIR | ✅ |
| 真 LIVE subagent 轨迹 | ✅（如 tube `hdu-b-tube-ma2`） |
| T1/T2 金标 SP/TSP/VRP | ✅ |
| M2 polyomino 域桥 | ✅ |
| L1/L2 安装与 Release v0.2.0 | ✅ |
| Knowledge RAG v1–v3（~88–92%） | ✅ 关单在 `docs/archive/closeouts/` |
| promote-run 战法沉淀 | ✅ |
| claim_map / R2 诚实规则（含过程计数 mask） | ✅ |
| Tube 全流程可跑 + LIVE 绿 | ✅ **算法质量待你抬** |
| Specs 索引与 hygiene 合并 | ✅ `specs/engineering-hygiene.md` |

---

## 7. 运筹学侧建议工作包（按优先级）

### P0 — Tube 异形圆管（竞赛体感最明显）

1. **几何：** 对齐端轮廓 360° 包络与四模式 LL/LR/RL/RR 共切矩阵（强手稿量级）。  
2. **Q2：** 固定 Q1 分配下，序列 + 朝向优化，把共切从 ~464 往上千推。  
3. **Q3：** 分配与序列联合；冲母材 **97000** 量级。  
4. **Q4：** 余料实体滚动前馈；冲新母材 **252000** 量级。  
5. 全程：只改 `tools/solve_tube_cut_b2026.py`（及必要几何模块）+ 加强 `validate`；跑：

```bat
.venv-314\Scripts\python.exe tools\solve_tube_cut_b2026.py
.venv-314\Scripts\python.exe tools\solve_dispatch.py tube_cut_b2026 --mode tube
```

### P1 — 路由 / 调度（Skill 已齐，算法可深）

- VRP：OR-Tools 之上的 ALNS / PyVRP；金标 58 不回归。  
- 调度：PyJobShop 等与 `production-scheduling` skill 对齐的可复现实验。  

### P2 — 新问题类接入产品

按 `solvers-and-validate.md` **注册法**：adapter → schema 白名单 → validate → intake hint → fixture → 门禁。  
未完成注册 **禁止**宣称该域产品已接通。

### P3 — 不要做

- 用手改 `solution.json` 的 objective 刷绿  
- 在 skill/RAG 里写权威最优 tour  
- 未开 M4 就上「企业级记忆中枢」  
- 把 LIVE 慢当成全题失败（数字以 solve 盘为准）

---

## 8. 关键目录速查

```text
orpath/                 控制面 · Watch · paper · process_memory · mcp_server · tool_catalog
tools/                  solve_* · validate · intake · R1/R2/claim · gate_*
scripts/                watch-run · *gate · knowledge-* · promote-run · pack
knowledge_svc/          RAG 实现
knowledge/              corpus 元数据 · lessons · allowlist（大正文可本地）
.pi/skills/             运行时 Skill
.pi/agents/             Pi 角色
fixtures/t3/            金标与 tube_cut_b2026
specs/                  硬法
docs/ARCHITECTURE.md    架构快照
docs/archive/closeouts/ 关单
docs/m2-polyomino.md    骨牌
ORPATH.md               日常命令
```

**案例产物（gitignore）：** `outputs/` `runs/` `notes/` `papers/`  
**真 MA 证据：** `outputs/.agents/<slug>/*-lead-*.log` · `*-harness.json`

---

## 9. 常用命令（运筹日常）

```bat
:: 环境
orpath.bat doctor

:: 金标域
orpath.bat t1-gate
orpath.bat t2-gate
orpath.bat m2-gate

:: Tube 重算
.venv-314\Scripts\python.exe tools\solve_tube_cut_b2026.py

:: 知识
set ORPATH_KNOWLEDGE_PROFILE=research
orpath.bat knowledge-sync
orpath.bat phase5-v3-gate

:: 战法沉淀
orpath.bat promote-run --slug <slug>

:: 工具清单
orpath.bat tools-list

:: LIVE（真 sub）
.venv-314\Scripts\python.exe scripts\orpath_watch_run.py --live --workdir ... --slug ...
```

---

## 10. 一句话交接

> **技术栈已经把「多 Agent 工作台 + 门禁 + 知识 + 求解接缝 + 论文诚实」串通了；  
> 你的战场是各 `solve_*` 背后的运筹模型与算法质量——尤其是 tube 共切与联合优化，以及 VRP/调度等可插拔增强。  
> 改算法，走 dispatch+validate；用 skill/RAG 传战法，不传假最优。**

---



---

## 12. RAG 书库里有什么（已入库 / 2026-08-04 push）

> 详细布局：`knowledge/CORPUS.md`

| 内容 | 约量 | 说明 |
|------|------|------|
| `knowledge/corpus/papers/**/*.md` | **~419** | hybrid 主粮全文/笔记 |
| 其中 `lit_abs/` | **~201** | 文献摘要+建模笔记（Top 清单物化） |
| 其中 `_from_mineru/` | **~101** | PDF 预处理 md |
| 根目录短笔记 | 其余 | CG、BFD、ALNS、VRP、TSP… 方法笔记 |
| `or_papers_top200/500.json` | 书目 | 元数据清单，不是全文 |
| `corpus/skills/` + `lessons/` | 少 | allowlist 战法/教训检索副本 |
| `export_allowlist.txt` | — | 哪些 skill 可进 RAG |

**本机可有但不强求进 git：** `inbox_pdf/` 大 PDF、chunks 运行索引、ingest 日志。

### 检索会命中什么（tube 示例，本机冒烟）

query 含 *cutting stock column generation residual co-cut…* 时，hybrid 可返回如：

- lit_abs / MinerU 下的 cutting / COR / discrete opt 文献笔记  
- 方法短文（column generation、bin packing…）

→ research **必须**把 hit 写进 Evidence table，并在「Method candidates」里点名列生成等，避免只会 BFD。

---

## 13. 强制 RAG 流程（产品已改默认）

| 项 | 行为 |
|----|------|
| 默认 `knowledge_mode` | **`hybrid`**（不再是空 seed） |
| `watch-run` | 自动带 `--knowledge-mode hybrid` |
| 查询词 | tube/cutting_stock **带入** column generation / residual / co-cut 等词 |
| 关强制 | `set ORPATH_KNOWLEDGE_MODE=seed` 或 `off`；或 `ORPATH_KNOWLEDGE_FORCE_HYBRID=0` 保留字面 seed |
| research 模板 | 增加 **Method candidates (from RAG)**；要求引用 retrieval chunk_id |

```text
retrieve (hybrid, install-home index)
  → notes/<slug>-retrieval.json  (hits≥1 时才算吃到书库)
  → research 必须引用 chunk_id / 方法名（列生成、模式生成…）
  → model schema 仍无 optima
  → solve_tube / ortools / …
```

**验收：** 再跑 B 题时 `notes/*-retrieval.json` 应为 `knowledge_mode=hybrid` 且 `hits>0`（本机索引需已 `knowledge-sync`）。

```bat
set ORPATH_KNOWLEDGE_PROFILE=research
orpath.bat knowledge-sync
orpath.bat watch-run --workdir ... --slug ... --live --knowledge 会由脚本强制 hybrid
```


## 11. Suggested skills（下一会话）

| Skill | 何时加载 |
|-------|----------|
| `orpath-windows-product-runtime` | 跑 Watch / CASE / LIVE |
| `or-path-knowledge-rag` | 动书库 / promote |
| `operations-research-algorithm-developer` | 写/改算法 |
| `or-solver-select` · `or-numbers-truth` | 选型与数字纪律 |
| `alns-metaheuristic` / `pyvrp-engine` | 路由深耕 |
| `handoff` | 再交接 |

---

*文档生成：技术栈收工日。冲突时以 specs + 门禁磁盘输出为准。*
