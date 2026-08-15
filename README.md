# OR-Path 多智能体运筹工作台

**一句话：** 题面 / 自然语言 → 研究建模 → **求解器出数字** → validate → 论文。  
**LangGraph 管阶段 · Pi 子 Agent 隔离 · gate 质检 · Watch 过程脸 · 知识轨给 Pi。**

| | |
|--|--|
| 仓库 | https://github.com/lanzaoi/or-path |
| 主入口 | **`START-CASE.bat`** · **`START-WATCH.bat`** · `orpath.bat` |
| 法条 | **`specs/`**（索引 `specs/README.md`） |
| 架构 | **`docs/ARCHITECTURE.md`** |
| 安装 | **`docs/install.md`** · Release **v0.3.5**（线上） |
| 教程 | **`docs/user-guide.md`**（详细）· **`ORPATH.md`**（速查） |

---

## 30 秒上手

```bat
:: 新机器（安装包）
irm https://github.com/lanzaoi/or-path/releases/download/v0.3.5/install.ps1 | iex
cd %LOCALAPPDATA%\Programs\orpath
orpath.bat doctor
START-WATCH.bat

:: 或开发者（源码）
git clone https://github.com/lanzaoi/or-path.git && cd or-path
orpath.bat setup && orpath.bat doctor && START-WATCH.bat
```

| 双击 | 作用 |
|------|------|
| **START-CASE** | 路径 A：本地案例文件夹 + 边跑边看 |
| **START-WATCH** | 过程脸（默认 seed 回放；加参可 LIVE） |
| **START-ORPATH** | 菜单 / Watch 快捷 |

路径粘贴 **不要引号**。旧页面 **Ctrl+F5**。结束 Watch：**Ctrl+C**。

### LIVE 多 Agent（边跑边看）

```bat
.venv-314\Scripts\python.exe scripts\orpath_watch_run.py ^
  --workdir C:\path\to\case --slug my-run --live --keep-watch ^
  --auto-intake --intake-in C:\path\to\case\inbox\problem.pdf ^
  --problem-id tube_cut_b2026 --problem-class tube_cut --solve-mode tube
```

未加 **`--live`** 时只是确定性/no-live 管线，**不是**真 Pi sub。

---

## 仓库结构（简洁）

```
orpath/          产品核心（LG · Watch · 控制面 · paper）
tools/           求解 / 校验 / intake / R1·R2·claim_map
scripts/         doctor · gates · pack · watch-run · knowledge · promote-run
specs/           硬法（SDD）
docs/            活文档；历史 docs/archive/
fixtures/        金标与冒烟
demo/seed/       默认脸回放
knowledge/       书库元数据 · lessons · allowlist（大正文可本地）
knowledge_svc/   检索侧车（hybrid · MinerU · ingest）
.pi/agents/      Pi 角色
.pi/skills/      战法 skill（可 export 进 RAG）
START-*.bat      一键入口
ORPATH.md        操作说明
```

**本机-only（不入库）：** `.venv-314/` · `.env` · `.hermes/` · `inbox/*` · `outputs/` `runs/` · 大体量 `knowledge/corpus/papers/`。  
详见 **`docs/repo-surface.md`**。

---

## 硬规矩

1. 数字只认 **solve + validate** JSON。  
2. 真多 Agent = 磁盘 subagent 轨迹，不是聊天扮角色。  
3. schema **禁止** objective。  
4. **HOME ≠ WORKDIR**（安装根 vs 案例目录）。  
5. 勿提交 contest PDF、密钥、整棵 `.hermes/`、PAT。  
6. 无 `solution.meta.proven_optimal` 时 **禁止**宣称 global-optimal（claim_map）。  
7. RAG = 给 **Pi research** 的书库，不是人用站点、不是训练语料。

---

## 里程碑（一览）

| 阶段 | 状态 |
|------|------|
| T1–T2 / 1.0 / 1.1 | CLOSED — `docs/archive/closeouts/` |
| V0 / M0 / M1 | 过程脸 · mock · workdir |
| **M2 polyomino** | 域桥 · Q1.1 obj=**6** |
| 安装分发 | setup + 线上 **v0.3.5** |
| **Knowledge RAG v1–v3** | CLOSED ~88–92% — hybrid + lit 主粮 + research 档 |
| **promote-run** | 跑完题 → 压缩 skill/lesson → allowlist → sync |
| **Tube B LIVE** | 产品路径可全绿（启发式 FEASIBLE；共切弱于强手优化稿） |
| M3 / M4 | 未开 |

金标：最短路 **42** · TSP **45** · VRP **58** · poly Q1.1 **6** · tube 演示 Q3 **99000**（FEASIBLE，非 proven OPTIMAL）。

---

## 知识轨（给 Pi）

```bat
:: 研究档
set ORPATH_KNOWLEDGE_PROFILE=research
orpath.bat knowledge-sync
orpath.bat phase5-v3-gate

:: 跑完题沉淀战法（无 optima）
orpath.bat promote-run --slug <slug>
orpath.bat promote-run-gate
```

- md 文献 → `knowledge/corpus/papers/`（或 lit 物化脚本）  
- PDF → `knowledge/inbox_pdf/` → preprocess  
- Skill 白名单 → `knowledge/export_allowlist.txt`  
- 禁 solution/objective 进 corpus  

关单：`docs/archive/closeouts/knowledge-rag-v3-prod-closeout.md`

---

## 文档地图

| 读这个 | 当… |
|--------|-----|
| [`docs/install.md`](docs/install.md) | 安装 / Release |
| [`docs/user-guide.md`](docs/user-guide.md) | **详细使用教程** |
| [`ORPATH.md`](ORPATH.md) | 命令速查 |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 架构快照 |
| [`specs/README.md`](specs/README.md) | 法条索引 |
| [`docs/README.md`](docs/README.md) | docs 导航 |
| [`docs/archive/`](docs/archive/) | 历史计划/关单 |

---

## 开发常用

```bat
orpath.bat doctor
orpath.bat m2-gate
orpath.bat phase5-v3-gate
orpath.bat promote-run-gate
orpath.bat pack-release
orpath.bat l2-gate --zip dist\orpath-0.3.5-win-x64.zip
```
