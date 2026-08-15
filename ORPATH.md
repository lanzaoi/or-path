# OR-Path：宿主无关主控（OpenPi 已移除）

**Hermes 不是产品运行时。** **OpenPi 桌面壳已从本安装删除**（2026-07-31，方案 B）。  
控制面：**`orpath.bat menu`**；**实时过程脸：双击 `START-WATCH.bat` / `orpath.bat face` / `watch`**；轻量对话：**`pi.bat` / `orpath.bat pi`**。

**详细使用教程 → [`docs/user-guide.md`](docs/user-guide.md)**（安装 · 路径 A · LIVE · 求解器 · RAG · FAQ）。  
**全新机器请先：** `orpath.bat setup` → `doctor`（说明见 **`docs/install.md`**）。  
**版本：** 根目录 `VERSION`（**0.3.5**）；线上 Release 见 install 版本表。

## 一键启动（推荐）

| 方式 | 做什么 |
|------|--------|
| **`orpath.bat setup`** | 建 venv + Pi npm + 释放 demo seed + doctor |
| **双击 `START-WATCH.bat`** | 清环境 → 起 Watch → 开浏览器；默认 **圆管 seed `live-btube`** |
| **双击 `START-CASE.bat`** | **路径 A**：指定**本地案例文件夹** + slug；可选 watch-run / 只看脸 / 题面路径 |
| 双击 `START-ORPATH.bat` | 选 **1 菜单** / **2 Watch**（回车默认 2） |
| `orpath.bat face` | 命令行同 START-WATCH 默认 |
| `START-WATCH.bat 其它slug` | 看 workdir 下指定任务 |
| `orpath.bat pack-release` | 打半肥 zip → `dist/` |

- 路径**不要加引号**（脚本会剥引号，但易踩坑）。  
- 结束 Watch：黑窗 **Ctrl+C** → 任意键。  
- 旧页面：**Ctrl+F5**。  
- 题面有「骨牌/polyomino/圆管/tube」文件名时，`START-CASE` 会猜域并带 `--auto-intake`。

### 路径 A · 本地文件夹

1. 建目录，例如 `D:\orpath-cases\demo1` 或 `Desktop\test`  
2. 双击 **`START-CASE.bat`** → **2** → 贴目录 → slug  
3. 可选题面 PDF/图；LIVE 先 **N** 更稳，真多 Agent 选 **y**  
4. 产物在该目录：`outputs\` · `runs\<slug>\` · `papers\`  
5. 只看：同一 bat 选 **1**，同一目录 + slug  

```bat
orpath.bat watch-run --workdir D:\orpath-cases\demo1 --slug demo1 --keep-watch
orpath.bat watch --workdir D:\orpath-cases\demo1 --slug demo1

:: 骨牌 + LIVE
orpath.bat watch-run --workdir D:\cases\b --slug b1 --live --keep-watch ^
  --auto-intake --intake-in D:\cases\b\B题.pdf ^
  --problem-id polyomino_b_q1 --problem-class polyomino_cover --solve-mode polyomino
```

**合同：** 安装根 = 代码/`.pi/agents`；workdir = 案例数据。Watch 必须同一 workdir+slug。

### B 题全问（不只 Q1.1）

单次产品 run 默认只演示 Q1.1。全问 bank → 案例目录：

```bat
.venv-314\Scripts\python.exe scripts\pack_b_polyomino_case.py --case D:\cases\b
:: 论文 papers\B-polyomino-full-paper.md · Excel outputs\b-full\*.xlsx
```

数字总表：Q1.1=**6** · Q1.2 L3 16/16 · Q2.1=**33** · Q2.2=**134** · Q2.3=**225** · Q2.4=**32** · Q3 cost=**82.5**/shared=**142**/pieces=**33**。

## 默认策略

| 项 | 默认 | 备注 |
|----|------|------|
| Live 多 Agent | 可选；START-CASE 默认 N | `--live` / `ORPATH_LIVE_SUBAGENT=1`；子代理超时默认 360s（watch-run） |
| Intake | 有 `--intake-in` 才开 | **不再**偷偷塞 fixtures intake |
| 过程台 | Watch HTTP :8765 | 中文 Apple 风；顶栏换模型 |
| CI / 门禁 | live OFF | `orpath.bat gate*` / `m1-gate` / `m2-gate` |

真 MA 证据：`outputs/.agents/<slug>/` 含 research/model/cite/review 日志与 subagent toolCall。

## 实时过程台

```bat
START-WATCH.bat
orpath.bat face
orpath.bat watch --slug live-btube
orpath.bat watch-run --slug p3-demo --keep-watch
orpath.bat p3-gate
```

法条：`specs/process-visibility.md` · 架构：`docs/ARCHITECTURE.md` · 冒烟：`docs/v0-smoke.md` · M1：`docs/m1-smoke.md` · M2：`docs/m2-polyomino.md` · 安装：`docs/install.md`。

## 菜单与 doctor

```bat
orpath.bat menu
orpath.bat doctor
orpath.bat m1-gate
orpath.bat m2-gate
orpath.bat tube-live-gate
```

当前 Tube v2 求解（原始附件缺失时返回 `BLOCKED`）：

```bat
orpath.bat tube-solve --fast
orpath.bat tube-solve
orpath.bat tube-solve --quality
```

## Skills · 过程记忆 · Tools · MCP（已接入产品）

| 能力 | 位置 / 命令 | 自动？ |
|------|-------------|--------|
| **Skills** | `.pi/skills/` **19+**（上游拉取，见 `third_party/PULLED.md`） | Pi 按需 |
| **Process memory** | `knowledge/lessons/` 种子；retrieve → `notes/<slug>-lessons.*` | **是** |
| **RAG（给 Pi）** | `knowledge/corpus` → hybrid BM25/FTS/RRF；`notes/*-retrieval.json` | research 读路径 |
| **Solvers / tools** | 默认 `tools/solve_*`；可选 pyvrp/pyjobshop/ALNS/pulp/vrplib | 流水线默认轨已有 |
| **MCP** | `mcp` · `mcp-highs` · `mcp-ortools` | Host 连接 |

```bat
orpath.bat memory-search --query "VRP capacity" --class vrp
orpath.bat memory-list
:: Pi 参考书库（不是人用网站；不是训练权重）
orpath.bat knowledge-rebuild
orpath.bat knowledge-export
orpath.bat knowledge-ingest
orpath.bat knowledge-retrieve --query "polyomino CP-SAT" --mode hybrid --topk 5
orpath.bat knowledge-smoke --step all
:: Phase 3：产品 run 里 Pi 吃 retrieval（mock SP + hybrid，无 LIVE）
orpath.bat phase3-hybrid-gate
:: Phase 4：allowlist 导出 skill/lesson 副本 + 重建索引
orpath.bat knowledge-sync
orpath.bat knowledge-eval
:: v2 Phase1：PDF 预处理（inbox → corpus/papers/_from_mineru）
orpath.bat knowledge-preprocess
orpath.bat phase1-mineru-gate
orpath.bat phase1-mineru-cloud-gate
orpath.bat phase2-embed-gate
orpath.bat knowledge-lit-materialize
orpath.bat phase2-real-corpus-gate
orpath.bat phase3-live-default-gate
orpath.bat product-research-gate
orpath.bat phase5-v3-gate
orpath.bat promote-run --slug <slug>
orpath.bat promote-run-gate
:: set ORPATH_KNOWLEDGE_PROFILE=research
orpath.bat phase3-scale-gate
orpath.bat thick-hybrid-gate
orpath.bat phase5-thick-gate
:: set ORPATH_KNOWLEDGE_EMBED=auto|live|stub  (default auto)

orpath.bat phase5-knowledge-gate
orpath.bat tools-list
orpath.bat mcp
orpath.bat mcp-highs
orpath.bat mcp-ortools
```

记忆 = **以前怎么解/关键点**；Skill = **解题/领域手册**；RAG = **运行时给 Pi 的论文/战法副本**。  
数字权威仍只在 solve+validate（可选引擎不改 claim ladder）。  
计划 v1：`docs/archive/plans/2026-08-04_knowledge-rag-thicken.md` · 关单 v1：`docs/archive/closeouts/knowledge-rag-v1-closeout.md`。  
计划 v2 厚栈：`docs/archive/plans/2026-08-04_knowledge-rag-v2-thick.md` · **关单 v2：** `docs/archive/closeouts/knowledge-rag-v2-thick-closeout.md`。  
hybrid 默认可用 **stub embed**；有硅基 key 时 `ORPATH_KNOWLEDGE_EMBED=live`（或 auto）走 bge-m3。  
验证：`orpath.bat phase2-embed-gate`。  
PDF：放 `knowledge/inbox_pdf/` 后 `knowledge-preprocess`。

## 环境

```bat
set PYTHONPATH=
set PYTHONHOME=
set PYTHONNOUSERSITE=1
:: 使用 .venv-314\Scripts\python.exe
```

## 相关

- 总览：[`README.md`](README.md)  
- 法条：[`specs/README.md`](specs/README.md)  
- docs：[`docs/README.md`](docs/README.md)


## 研究档四步（v3 Phase 4）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONPATH=
set PYTHONNOUSERSITE=1
set ORPATH_KNOWLEDGE_PROFILE=research
set ORPATH_KNOWLEDGE_EMBED=auto

orpath.bat knowledge-sync
orpath.bat product-research-gate
```

证据：`notes/thick-research-evidence.md` · `notes/thick-research-sp-retrieval.json`  
可选回归：`orpath.bat thick-hybrid-gate`


**RAG v3 关单：** `docs/archive/closeouts/knowledge-rag-v3-prod-closeout.md`


## promote-run

`orpath.bat promote-run --slug <slug>` → skill + lesson + RAG.
