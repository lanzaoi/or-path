# OR-Path 多智能体运筹工作台

**一句话：** 自然语言运筹问题 → 检索/研究 → 建模（无最优值）→ **求解器出数字** → validate 重算 → 解释/论文；  
**LangGraph 管阶段**，**Pi 子 Agent 管隔离**，**gate 管质检**。

| | |
|--|--|
| 产品名 | OR-Path Multi-Agent / Graph-OR Agent |
| 主 UI | **`orpath.bat menu`** + **实时脸 `orpath.bat watch`**（OpenPi 已删）— 读 **`ORPATH.md`** |
| 辅 UI | Pi 终端（`orpath.bat pi` / `pi.bat`） |
| 硬法 | **`specs/`**（SDD，冲突时以门禁输出 > specs > 本文件） |
| 默认 | **Live 多 Agent ON**；有题面/`inbox/` 才 intake；门禁用 `--no-live-subagent` |
| 不是什么 | 不是 Feynman 主壳；不是 Hermes 产品运行时；裸聊天 ≠ 多 Agent；数字不靠 LLM 心算；**开文件夹 ≠ 实时可视** |

---

## 你先看这 5 个就够

目录很杂，**日常只盯这些**：

| 优先级 | 路径 | 干什么 |
|--------|------|--------|
| 1 | **`orpath.bat`** | 一切入口（menu / **watch** / doctor / gate / run / pi） |
| 2 | **`specs/README.md`** | 规范索引；**过程脸** `specs/process-visibility.md`；总流程 `product-flow-sdd.md` |
| 3 | **`orpath/`** | LangGraph 产品骨架与 runner（核心代码）；**`watch_snapshot.py`** 过程聚合 |
| 4 | **`tools/`** | solve_dispatch / validate / R1 / R2 / intake（数字真相+题面） |
| 5 | **`ORPATH.md`** · **`docs/v0-smoke.md`** | **menu + Live Watch** 操作；V0 冒烟 |

历史关单/证据/口播 → **`docs/archive/`**。带外大树 → **`docs/OUT_OF_BAND.md`**（vendor/pi-main；openpi 已移除）。

---

## 里程碑状态（别被文件名绕晕）

| 阶段 | 状态 | 关单文档 | 你要记住的一句话 |
|------|------|----------|------------------|
| **T1** | CLOSED/PASS | `docs/archive/closeouts/t1-closeout.md` | 薄全链 + 真多 Agent 证明 |
| **T2** | CLOSED/PASS | `docs/archive/closeouts/t2-closeout.md` | 求解加厚 + 知识竖切 + 隔离门禁 + 可搬迁安装 |
| **T3** | **工程 PASS** | `docs/archive/closeouts/t3-lg-closeout.md` | **LG 产品骨架完整**（checkpointer/resume/图内 bridge） |
| T3-mini | 叶 | `docs/archive/closeouts/t3-mini-closeout.md` | 时间窗 VRP 竖切，**不是** T3 标题 |
| **1.0** | PASS | `docs/1.0-closeout.md` | 论文协议 + 多智能体 harness + 架构 ADR-0001…0006 |
| **1.1** | CLOSED/PASS | `docs/1.1-closeout.md` | 题面 OCR + 自主审读 brief/intake.json（禁 objective） |
| **1.2** | **工程 PASS** + residual R1–R4 | `docs/1.2-closeout.md` | 真题 intake→LG→live MA→solve 诚实 BLOCKED（非交卷求解） |
| 规范 | 活文档 | `specs/`（含 `problem-intake.md` · `1.2-architecture-soak.md`） | 实现前先读 |

**T3 人侧还欠（可选）：** resume 双帧拼图（工程门禁已绿；OpenPi 截图已退役）。  
**1.2 不宣称：** 服装 C 题 Q1–Q4 交卷数值；零售问题类产品化。

金标数字（**只认求解器+validate**）：最短路 **42** · TSP n=8 **45** · VRP 多车 **58** · VRP 时间窗 **58**。  
竞赛旁路样例（精确轨）：多联骨牌 B 全问见 `outputs/b-polyomino/` · 论文 `papers/b-polyomino-full.md`。

---

## 30 秒上手（Windows）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
:: 可装到任意目录：set ORPATH_HOME=你的安装根

orpath.bat doctor
orpath.bat v0-watch-gate
orpath.bat watch --slug test
:: 浏览器看 L0 阶段 / L1 派工 / L2·L3 事件（实时过程台 = 产品脸）

orpath.bat demo-m0 --slug m0
orpath.bat m0-gate
orpath.bat m1-gate
:: M1：workdir + Watch 错误/CTA；见 docs/m1-smoke.md

orpath.bat gate-t3

:: 跑一条产品流水线（可恢复 thread）
orpath.bat run --problem-id shortest_path --solve-mode mock --slug demo --thread-id demo --fresh
orpath.bat status --thread-id demo
orpath.bat list
```

常用：

```bat
orpath.bat watch --slug <slug>   :: ★ 实时过程台（V0 脸；不是开文件夹）
orpath.bat demo-m0 --slug m0     :: ★ M0 证据串（mock 数字 + 清单）
orpath.bat gate          :: T2 本地门禁（重）
orpath.bat gate-t3       :: T3 骨架+矩阵门禁
orpath.bat v0-watch-gate :: V0 watch 文档+HTTP 烟
orpath.bat m0-gate       :: M0 demo 门禁
orpath.bat m1-gate       :: M1 workdir + Watch 加厚
orpath.bat isolation     :: 真多 Agent 隔离硬检
orpath.bat menu          :: 宿主无关主控（含 Live Watch / Demo M0）
orpath.bat t2 --problem-id tsp_n8 --solve-mode ortools
```

环境注意：

```bat
set PYTHONNOUSERSITE=1
:: 用安装根下的 .venv-314，避免混到 Hermes 全局包
```

可搬迁说明：`docs/archive/ops/t2-relocatable.md`（`ORPATH_HOME` / `ORPATH_WORKDIR`）。

---

## 目录地图（中文导览）

### 你要改业务 / 看架构 → 这些

```text
specs/                 【硬法】读这里，不要只信聊天
  README.md            索引
  t3-lg-skeleton.md    T3 主法（LG 骨架 freeze）
  control-plane.md     阶段机 / 回修上限
  product-scope.md     做什么 / 不做什么
  gates-and-dod.md     门禁与完成定义
  ...

orpath/                【大脑-流程】LangGraph
  control_plane.py     ★ 控制面：build / seed / invoke_once（ADR-0003）
  paper_protocol.py    ★ 论文环：run_from_solution（ADR-0004）
  subagent_dispatch.py ★ 子智能体策略：live/leads/harness（ADR-0005）
  graph_product.py     ★ 产品图拓扑（边/路由）
  run_orpath.py        ★ CLI：run/status/resume/list → ControlPlane
  nodes.py             ★ 阶段节点权威（含 bridge + NodeContext wrap）
  nodes_product.py     兼容 shim → nodes
  post_solve_paper.py  兼容 shim → paper_protocol
  paper_workflow.py    论文渲染/review 实现
  paper_live_subagent.py  cite/review live 实现（经 dispatch）
  graph_live_subagent.py  research/model live 实现（经 dispatch）
  subagent_runtime.py  spawn/detect 实现
  subagent_harness.py  anti-cosplay 实现
  node_context.py      snapshot / hash / owner 断言
  stage_map.json       阶段图导出（门禁 diff）
  graph.py + run_t1.py 委托 ControlPlane（t1_gate）
  graph_t2.py + run_t2.py 委托 ControlPlane / run_orpath
  pi_bridge.py         LG↔Pi 桥
  state.py             窄共享状态字段

tools/                 【计算器】数字唯一真相
  solve_dispatch.py    ★ 统一调度（ADR-0002）
  solve_envelope.py    ★ solution 接口契约
  solve_mock.py
  solve_networkx.py
  solve_ortools.py     含 TSP / VRP / CVRPTW
  solve_tube_cut_b2026.py  圆管 BFD 适配器
  validate_solution.py
  r1_*.py  r2_*.py
  gate_schema.py

scripts/               【门禁按钮】
  t1_gate.py
  t2_gate.py  t2_gate_cloud.py  t2_multiagent_isolation.py
  t3_lg_gate.py  t3_gate.py  t3_gate_live.py
  orpath_doctor.py

fixtures/              【考题与金标】
  t1/shortest_path/    SP=42
  t2/tsp_n8/           TSP=45
  t2/vrp_multi/        VRP=58
  t3/vrp_tw/           时间窗 VRP=58

.pi/agents/or-*.md     Pi 子 Agent 角色定义（真隔离，不是 cosplay）
contracts/             JSON 契约形状
knowledge_svc/         知识竖切代码（MinerU/混合检索/Cognee…）
knowledge/             语料、种子图（缓存一般 gitignore）
```

### 运行时产生、可以当「草稿纸」→ 这些

```text
outputs/               方案、schema、review、provenance、施工证据
  t3-lg/               T3 骨架施工/关单证据
  t3-multi-cli/        多 CLI 实验痕迹
notes/                 研究/解释/检索 JSON
papers/                论文草稿
runs/                  ★ LG checkpointer + 每 thread 的 stage 快照（gitignore）
```

**提示：** `runs/<thread_id>/stages/*.json` 就是「流水线黑匣子」；`runs/orpath.sqlite` 是可恢复状态库。

### 体积大、别当业务代码翻 → 这些

```text
runtime/               Pi npm 运行时（别 npx pi）
# openpi/              REMOVED 2026-07-31
pi-main/               Pi 上游 monorepo 源码研究用
vendor/                Feynman 等只读参考
.venv-314/             Python 虚拟环境
node_modules/          （若存在）依赖
.pi-subagents/         子 Agent 轨迹缓存
.hermes/plans/         施工单（可过期；与 specs 冲突以 specs 为准）
```

### 根目录一堆 bat/sh 是啥

| 文件 | 用途 |
|------|------|
| **`orpath.bat` / `orpath.sh`** | ★ 正式产品启动器（优先用这个） |
| ~~`openpi.bat`~~ | **已删除** |
| `pi.bat` / `pi.sh` | Pi TUI |
| `orpath.env.example` | 环境变量样例（真密钥在本地 `.env`，勿提交） |
| `AGENTS.md` | 给 Agent 的短项目法（指针） |
| `IDEA.md` | 叙事/拓扑长文 |
| `requirements.txt` | Python 依赖列表 |

---

## 架构怎么记（防乱）

```text
你 / `orpath.bat menu` / **`orpath.bat watch`（实时脸）** / Pi TUI
        │
        ▼
 LangGraph 产品图（老板：now→next、重试、checkpoint）
   orchestrate → retrieve → bridge_pi → research → model
        → gate_schema → solve → gate_validate
        → explain → paper → review → provenance
        │              ▲
        │              └── 调参≤3 / 回 model≤2 / 否则 HUMAN_REQUIRED
        ▼
 工具：solve_* 只写 objective；validate 重算
        │
 Pi 子 Agent（包工头+班组）：只在需要隔离的节点里干活，交文件路径
        │
 watch 读盘 L0–L4（无 LLM 编协作故事）
```

- **禁止：** LLM / memory / 子 Agent 口述最优解  
- **禁止：** 把 Teams、消息总线当主架构  
- **禁止：** 只开 `runs/` 文件夹却宣称「已有实时可视」  
- **双路径：**  
  - 门禁/CI = 确定性 LG 节点  
  - 演示 = menu/run-full + **watch** + 真 subagent transcript  

阶段图导出：`docs/t3-stage-map.mmd`（可用支持 Mermaid 的编辑器预览）。

---

## 门禁怎么选（别全跑瞎等）

| 你想确认 | 命令 | 轻重 |
|----------|------|------|
| **V0 实时过程台** | `orpath.bat v0-watch-gate` | 轻 |
| **M0 demo 证据串** | `orpath.bat m0-gate` | 中（含 mock run） |
| **M1 workdir+Watch** | `orpath.bat m1-gate` | 中（含 workdir e2e mock） |
| T3 骨架+矩阵 | `orpath.bat gate-t3` | 中 |
| 仅骨架 | `python scripts/t3_lg_gate.py` | 轻 |
| T2 全家桶 | `orpath.bat gate` | **重** |
| 多 Agent 隔离 | `orpath.bat isolation` | 中（需已有 transcript 证据） |
| T1 回归 | `python scripts/t1_gate.py` | 中 |
| 云能力 | `python scripts/t2_gate_cloud.py` | 需 key |

一律建议：

```bat
set PYTHONNOUSERSITE=1
```

---

## 文档怎么找（中文）

| 需求 | 文件 |
|------|------|
| **文档导航** | **`docs/README.md`** |
| 1.0 总关单 | `docs/1.0-closeout.md` |
| 架构 ADR | `docs/adr/` |
| T1–T3 历史关单 | `docs/archive/closeouts/` |
| 口播 / 证据 | `docs/archive/portfolio/` · `docs/archive/evidence/` |
| 冒烟操作 | `docs/v0-smoke.md` · `docs/t1-smoke.md` · `docs/t2-smoke.md` |
| 带外大树 | `docs/OUT_OF_BAND.md` |
| 规范总索引 | `specs/README.md` |
| 产品故事长文 | `IDEA.md` |

**关单/证据已归档：** 见 `docs/archive/README.md`。默认只读活文档面。

---

## 常见懵点

1. **为什么还有 graph.py / graph_t2 / run_t1？**  
   历史入口名；**都进 `control_plane` / 产品图**（ADR-0003）。真逻辑：ControlPlane + `nodes.py` + `graph_product` 拓扑。

2. **outputs 一堆 t3-mat- / t3-lg- 是什么？**  
   门禁和实验跑出来的制品，可清，也可留作证据；**权威金标在 `fixtures/`**。

3. **多智能体怎么开 / 过程怎么看？**  
   用 `orpath.bat menu` → run-full / gui-demo；cwd 必须是安装根。OpenPi 已删除。  
   **实时看阶段与 sub：`orpath.bat watch --slug <slug>`**（不要用开文件夹代替）。

4. **数字和 README 对不上？**  
   以 **本次 `solve_*` + `validate` 输出** 为准，不要抄旧笔记。

5. **Hermes MEMORY？**  
   只是写代码的助手笔记，**不是** OR-Path 运行时记忆。

6. **gate 绿了算体验完成吗？**  
   **不算。** 工程门禁 ≠ 用户看见过程；V0 必须 watch 台达标（`specs/process-visibility.md`）。

---

## 技术栈锁定（极简）

- Harness：Pi（`runtime/`）+ **pi-subagents**  
- 流程：LangGraph（Python）+ Sqlite checkpointer  
- 求解：OR-Tools / NetworkX / mock + validate  
- 模型：Pi 侧 **DeepSeek only**  
- 知识：MinerU Cloud · LightRAG+BM25/FTS · Cognee Cloud · 种子图  
- UI：`orpath.bat menu` 主 · **`orpath.bat watch` 实时脸** · Pi TUI 辅  
- OUT：Graphiti 主路径、Agent Teams/总线脊柱、Feynman 主开发壳  

---

## 给自己的维护建议（文件夹）

| 做 | 不做 |
|----|------|
| 入口永远 `orpath.bat` | 不要记十个 py 路径 |
| 改行为先改 `specs/` + `docs/adr/` | 不要只改聊天结论 |
| 活文档只加 `docs/` 顶层；历史进 `docs/archive/` | 不要在顶层堆 closeout |
| 证据丢 `outputs/`；长期证据归档 `docs/archive/evidence/` | 不要往 `runtime/` 塞业务 |
| 金标只动 `fixtures/` | 不要手改 solution 当真相 |

带外树说明：`docs/OUT_OF_BAND.md`（ADR-0006）。

---

## 许可证与作品集

个人独立项目（Track B）。对外话术边界见 `specs/product-scope.md` claim ladder：  
可说「带验证关卡的 Supervisor–Worker 流水线」；  
不可说「保证全局最优 / 已达某论文 85%」等无本仓评测支撑的话。
