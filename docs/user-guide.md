# OR-Path 使用教程（详细）

面向：**第一次用的人** + **运筹队友** + **开发者**。  
更短的入口见根目录 [`README.md`](../README.md)；命令速查见 [`ORPATH.md`](../ORPATH.md)。  
法条见 [`specs/README.md`](../specs/README.md)。

---

## 0. 你在用什么

```text
题面 → 研究/检索 → 建模(schema 无最优值) → 求解器出数字 → validate 重算 → 论文门
LangGraph 管阶段 · Pi 子 Agent 隔离 · Watch 读盘做过程脸 · RAG 只给 Pi 提示
```

| 概念 | 含义 |
|------|------|
| **HOME** | 安装根 / 本仓库（代码、fixtures、skills） |
| **WORKDIR** | 案例目录（`outputs/` `runs/` `notes/` `papers/`） |
| **slug** | 一次任务的名字，贯穿产物文件名 |
| **LIVE** | `--live` 才真拉 Pi subagent；否则是快速确定性路径 |
| **数字真理** | 只信 `*-solution.json` + `*-validate.json` |

**不是产品运行时：** Hermes 桌面、裸 `pi -p` 聊天扮多 Agent。

---

## 1. 安装

### 1.1 路人（L2 · Release 半肥包）

当前线上 tag：**v0.2.0**。含 RAG v3 / promote-run / LIVE 管线的代码在 **main**；**v0.3.0** 半肥包见 `docs/archive/releases/v0.3.0-notes.md`（打 zip 后上传）。

```powershell
# v0.2.0（已发布）
irm https://github.com/lanzaoi/or-path/releases/download/v0.2.0/install.ps1 | iex

cd $env:LOCALAPPDATA\Programs\orpath
orpath.bat doctor
START-WATCH.bat
```

### 1.2 开发者（L1 · git）

```bat
git clone https://github.com/lanzaoi/or-path.git
cd or-path
orpath.bat setup
orpath.bat doctor
START-WATCH.bat
```

| 依赖 | 说明 |
|------|------|
| Python 3.11–3.13 推荐 | `.venv-314` |
| Node ≥ 22.19 | Pi runtime |
| `DEEPSEEK_API_KEY` | **仅 LIVE 真多 Agent 需要**；看 seed 脸 / mock **不要 key** |
| 可选硅基 key | `ORPATH_KNOWLEDGE_EMBED=live` 时 hybrid 向量 |

详情：[`install.md`](install.md)。

---

## 2. 三分钟上手（只看脸）

1. `orpath.bat doctor` 应大体 PASS  
2. 双击 **`START-WATCH.bat`**  
3. 浏览器打开 Watch（默认 seed **`live-btube`** 回放）  
4. 顶栏可见阶段；**这是回放，不是现场重算竞赛**  
5. 结束：黑窗 **Ctrl+C**；页面旧了 **Ctrl+F5**

---

## 3. 路径 A：用自己的题（主路径）

### 3.1 准备案例目录

```text
D:\orpath-cases\my1\
  inbox\          ← 题面 PDF/图（可选）
  attachments\    ← 解压后的附件（可选）
  （跑完后自动有）outputs\  runs\  notes\  papers\
```

### 3.2 双击 START-CASE

1. 选 **2 新跑**（或 **1 只看脸**）  
2. 粘贴案例目录路径（**不要加引号**）  
3. 输入 slug（如 `my1`）  
4. 可选题面文件  
5. LIVE：**先 N**（稳、快）；要真多 Agent 再 **y**（慢、耗 key）

### 3.3 命令行等价

```bat
:: 快速 no-live（确定性 model + 域 adapter）
orpath.bat watch-run --workdir D:\orpath-cases\my1 --slug my1 --keep-watch ^
  --auto-intake --intake-in D:\orpath-cases\my1\inbox\题.pdf

:: 真 LIVE 多 Agent
orpath.bat watch-run --workdir D:\orpath-cases\my1 --slug my1 --live --keep-watch ^
  --auto-intake --intake-in D:\orpath-cases\my1\inbox\题.pdf
```

可显式指定域（圆管示例）：

```bat
orpath.bat watch-run --workdir D:\cases\tube --slug t1 --live --keep-watch ^
  --auto-intake --intake-in D:\cases\tube\inbox\B.pdf ^
  --problem-id tube_cut_b2026 --problem-class tube_cut --solve-mode tube
```

骨牌示例：

```bat
orpath.bat watch-run --workdir D:\cases\b --slug b1 --live --keep-watch ^
  --auto-intake --intake-in D:\cases\b\B题.pdf ^
  --problem-id polyomino_b_q1 --problem-class polyomino_cover --solve-mode polyomino
```

### 3.4 跑完看什么

| 路径 | 内容 |
|------|------|
| `outputs/<slug>-solution.json` | **数字** |
| `outputs/<slug>-validate.json` | 重算是否 ok |
| `outputs/<slug>.provenance.md` | 门禁汇总 |
| `papers/<slug>.md` | 论文草稿 |
| `runs/<slug>/stages/` | 阶段快照 |
| `outputs/.agents/<slug>/` | **真 MA** lead/sub 日志（仅 LIVE） |
| `HUMAN_REQUIRED.md` | 若人停 |

**Watch 与 run 必须同一 `--workdir` + `--slug`。**

---

## 4. LIVE 与 no-live 怎么选

| | no-live | LIVE (`--live`) |
|--|---------|-----------------|
| 速度 | 快（秒～分钟） | 慢（research/model/cite 各可数分钟） |
| 真 Pi sub | 否 | 是 |
| 适用 | 调求解器、回归、演示数字链 | 演示多 Agent、研究档写作 |
| 证据 | stages + solution | + `.agents/*` toolCall |
| Key | 通常不需要 | 需要模型 key |

脸长时间停在 research/cite **不等于死**：看 stages 是否仍增长、`.agents` 日志是否在写。

---

## 5. 求解器怎么用（运筹向）

统一入口：

```bat
.venv-314\Scripts\python.exe tools\solve_dispatch.py <problem_id> --mode <mode>
.venv-314\Scripts\python.exe tools\validate_solution.py --problem-id <id> --solution path\solution.json
```

| mode | 典型问题 | 话术 |
|------|----------|------|
| `networkx` | 最短路 | exact · 金标 42 |
| `cpsat` | 小 TSP | exact · 金标 45 |
| `ortools` | VRP/TW | 搜索 FEASIBLE · 金标 58 |
| `polyomino` | 骨牌覆盖 | CP-SAT · Q1.1=6 |
| `tube` | 异形圆管下料 | BFD 启发式 · Q3≈99000 FEASIBLE |
| `mock` | CI | fixture |

圆管全问重算（写 `outputs/b-tube-cut/`）：

```bat
.venv-314\Scripts\python.exe tools\solve_tube_cut_b2026.py
```

骨牌全问 pack：

```bat
.venv-314\Scripts\python.exe scripts\pack_b_polyomino_case.py --case D:\cases\b
```

清单：`orpath.bat tools-list` · 法：`specs/solvers-and-validate.md`。

**禁止：** 手改 solution 的 objective 当「算过了」；无 `proven_optimal` 时写 global-optimal。

---

## 6. 知识库 RAG（给 Pi，不是网站）

```bat
:: 研究档
set ORPATH_KNOWLEDGE_PROFILE=research
set ORPATH_KNOWLEDGE_EMBED=auto
orpath.bat knowledge-sync
orpath.bat phase5-v3-gate

:: PDF → 预处理
:: 文件放入 knowledge\inbox_pdf\
orpath.bat knowledge-preprocess

:: 跑完题沉淀战法（无 optima）
orpath.bat promote-run --slug my1
orpath.bat promote-run-gate
```

| 放什么 | 目录 |
|--------|------|
| 文献 md | `knowledge/corpus/papers/` |
| PDF | `knowledge/inbox_pdf/` |
| 短教训 | `knowledge/lessons/*.json`（`orpath.lesson.v1`） |
| skill 白名单 | `knowledge/export_allowlist.txt` |

关单：`docs/archive/closeouts/knowledge-rag-v3-prod-closeout.md`。

---

## 7. Skills · MCP · 记忆（怎么配合）

| 层 | 位置 | 作用 |
|----|------|------|
| **Skill** | `.pi/skills/` | Pi 打开的手册（选型、数字纪律、OR 算法） |
| **RAG 副本** | `knowledge/corpus/skills/` | 仅检索；allowlist 导出 |
| **Lesson** | `knowledge/lessons/` | 短过程教训 |
| **MCP** | `orpath.bat mcp` / `mcp-highs` / `mcp-ortools` | 可选外挂；**主链不依赖** |

数字权威永远在 solve+validate，不在 skill/MCP 散文。

队友长交接（工作流串起来）：  
[`archive/handoffs/2026-08-04_or-teammate-handoff.md`](archive/handoffs/2026-08-04_or-teammate-handoff.md)

---

## 8. 门禁与回归（开发）

```bat
orpath.bat doctor
orpath.bat t1-gate
orpath.bat t2-gate
orpath.bat m2-gate
orpath.bat phase5-v3-gate
orpath.bat promote-run-gate
orpath.bat p3-gate
```

冒烟文档：`docs/v0-smoke.md` · `m1-smoke.md` · `m2-polyomino.md` · `t1-smoke.md` …

---

## 9. 常见问题

| 现象 | 原因 / 处理 |
|------|-------------|
| 多个浏览器标签 | 每次 watch-run 会 `start`；用 `--no-browser` 或关掉旧标签 |
| LIVE 像卡住 | research/cite 慢；看 stages 与 `.agents` 日志是否在增长 |
| `claims_recorded: 309` 爆红 | 旧 bug；main 已 mask 过程计数；请 pull 最新 |
| Watch ok 但 last_error 有字 | 看最终 provenance；中间阶段可能曾红后 revise 绿 |
| LIVE 未加 `--live` | `live=false`，秒完但不是真 MA |
| 无 key | 仍可 doctor + seed 脸 + no-live 域 adapter |
| tube 比强手差 | 共切启发式弱；改 `solve_tube_cut_b2026.py`，不是再装 MCP |

---

## 10. 发布（作者）

见 [`install.md`](install.md) 与 [`archive/releases/v0.3.0-notes.md`](archive/releases/v0.3.0-notes.md)。

```bat
python scripts\pack_release.py
python scripts\l2_release_gate.py --zip dist\orpath-0.3.0-win-x64.zip
:: gh release create v0.3.0 ...
```

---

## 11. 文档地图

| 文档 | 给谁 |
|------|------|
| 本文 `user-guide.md` | 使用教程（你在读） |
| `ORPATH.md` | 命令速查 |
| `README.md` | 仓库门面 |
| `install.md` | 安装 / L1 L2 |
| `ARCHITECTURE.md` | 架构 |
| `archive/handoffs/*` | 给人/Agent 的交接 |
| `specs/*` | 硬法 |
