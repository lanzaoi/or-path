# OpenPi 默认多 Agent + 自主审题（GUI 主控）Implementation Plan

> **For Hermes:** 用户先审核本计划；**未批准前不实现**。批准后按 task 执行。

**Goal:** 把「真多 Agent + 题面 intake」从 Hermes/特殊 CLI 旗标，改成 **OpenPi 打开本仓即可默认生效** 的产品体验；用户以 GUI 操控仓库，不依赖 Hermes 代跑。

**Architecture:**  
- **控制面仍是 LangGraph + `orpath run`**（不改拓扑赢家）。  
- **OpenPi = 主操作台**：开仓即注入项目法、默认 `ORPATH_LIVE_SUBAGENT=1`、默认可走 intake 前门。  
- **Pi 会话默认走 harness 法**（`--tools` 含 subagent、禁 cosplay），禁止「裸聊天 = 多 Agent」叙事。  
- **CI/门禁** 可显式 `--no-live-subagent` / `skip_intake` 保持快绿。

**Tech Stack:** OpenPi · Pi + `pi-subagents@0.37.2` · `orpath.bat` / `run_orpath.py` · intake OCR/parse · `.pi/` 项目配置 · specs/docs

---

## 用户目标（审核锚点）

| # | 你要的 | 当前缺口 |
|---|--------|----------|
| U1 | **默认多 Agent** | live 默认关；OpenPi 聊天 = 单会话 |
| U2 | **自主审题搞好** | 无 `--intake-in` 则 skip；真图 OCR 弱；parse 偏规则 |
| U3 | **GUI 开仓库即可操控** | 成功证据在 Hermes/CLI soak，未移植到 OpenPi 开箱路径 |
| U4 | **全局/产品级** | 不是一次性脚本，是默认策略 + 文档 + 门禁 |

**成功一句话（DoD 对外）：**  
打开 OpenPi → 选中 `Desktop/agent` → **不用记一堆 flag** → 丢题面或点「跑全链」→ 默认 **intake（有题面时）+ live 子 Agent 阶段** → 磁盘上能看见 `*-lead-*.log` 的 `name:subagent` 与 `*-intake.json`。

---

## 现状（事实，非叙事）

| 层 | 现状 |
|----|------|
| `run_orpath` | `skip_intake = not intake_in`；live 需 `--live-subagent` 或 env |
| `openpi.bat` | 仅 `npm run dev`，**不设** ORPATH_*，不提示 MA/intake |
| OpenPi | 桌面壳打开文件夹聊天；**不自动**跑 LG 全图 |
| 1.1 | 门禁绿；默认图 **skip intake**；OCR 真图占位 |
| 1.2 soak | harness+live **曾**跑通（`outputs/.agents/hdu-c2025-1.2`）；与 OpenPi 默认无关 |
| 门禁 | `subagent_gate` 大量 dry/skip；**不等于** GUI 默认 MA |

---

## 设计原则（建议你拍板）

1. **GUI 主控，CLI 同构**：OpenPi 能做的，`orpath.bat` 一条命令也能做；禁止「只有 Hermes 会话才绿」。  
2. **默认开 MA，显式关**：产品默认 `live_subagent=true`；CI/T1 快测用 `--no-live-subagent`。  
3. **Intake：有题面才进前门，无题面不装死**：  
   - 有 `intake` 源（用户指定 / 自动发现）→ 跑 intake；  
   - 纯 fixture `problem-id` 演示 → 仍可 skip（或提示「无题面，legacy 模式」）。  
4. **「自主审题」分两档（避免再吹）**：  
   - **P0 产品默认**：PDF 文字层 / md / txt → brief + intake.json + 禁键；可审计。  
   - **P1 增强**：扫描图 Paddle/AI Studio OCR（失败则 `needs_human`，不装成功）。  
5. **OpenPi 不等于自动全图**：须有 **显式产品入口**（斜杠命令 / 启动任务 / 一键 bat 菜单），避免「聊两句就算跑完 OR-Path」。  
6. **数字真相不变**：solve/validate 仍唯一写 objective；MA 不代算。

---

## 推荐方案（供选）

### 方案 A（推荐）：「默认策略 + OpenPi 产品命令面」

| 块 | 做什么 |
|----|--------|
| A1 默认 live MA | `ORPATH_LIVE_SUBAGENT` 默认 `1`（`.env.example`、`orpath.bat`、文档）；CLI `--no-live-subagent` 退出 |
| A2 Intake 自动发现 | 约定目录 `inbox/` 或打开时扫描用户拖入的 pdf/md；`orpath run --auto-intake` |
| A3 OpenPi 入口 | 项目根 `.pi/` + `AGENTS.md`/`ORPATH.md` 启动说明；`orpath.bat openpi` 打印「默认 MA=ON」；提供 **一键全链** `orpath.bat demo-full` |
| A4 会话法 | `.pi/agents` + orchestrator 系统提示：**全链必须 `orpath run`，禁止裸 cosplay**；research 等阶段由 LG 调 harness，不靠用户手写角色 |
| A5 可见证据 | 跑完自动打开/打印：`outputs/.agents/<slug>/`、`*-intake.json`、stage 列表 |

### 方案 B：「OpenPi 内嵌按钮/扩展」（更重）

在 openpi 源码加 OR-Path panel（Run / Intake / Live toggle）。  
**成本高、绑 OpenPi 版本**；仅当 A 不够用再上。

### 方案 C：「只改文档」（否决）

不解决你 GUI 测不到的问题。

**本计划默认落地 A；B 列为可选 Phase 2。**

---

## 分阶段交付

### Phase 0 — 冻结（审核当轮）

- [ ] 确认默认 live = ON  
- [ ] 确认 intake：自动发现路径 vs 必须拖文件  
- [ ] 确认「OpenPi 一键」形态：仅 bat 菜单 / 还是要改 openpi UI  
- [ ] 确认 CI 仍允许 `--no-live-subagent`  

### Phase 1 — 默认多 Agent（CLI 全局）

**Objective:** 不传 flag 时产品 run 默认 live；快测可关。

| 项 | 内容 |
|----|------|
| 改 | `orpath/run_orpath.py`：`_resolve_live_subagent` 默认倾向 ON（无 `--no-live-subagent` 且未显式 0） |
| 改 | `orpath.bat`：启动时 `set ORPATH_LIVE_SUBAGENT=1`（可被用户环境覆盖为 0） |
| 改 | `.env.example`：`ORPATH_LIVE_SUBAGENT=1` + 注释成本 |
| 改 | `scripts/t1_gate.py` / `t3_lg_gate.py` / 文档：快测强制 `--no-live-subagent` 或 env=0，避免门禁变慢变贵 |
| 验 | 无 flag run 短 slug → `outputs/.agents/<slug>/` 出现 lead log 且含 `"name":"subagent"`（允许 mock solve） |
| 验 | `ORPATH_LIVE_SUBAGENT=0` 时仍 skip，门禁绿 |

**风险：** 默认 live 烧 DeepSeek 钱与时间 → 文档大红警告；doctor 检查 key。

### Phase 2 — Intake 默认可用（有题面时）

**Objective:** 用户丢题面即可审题；无题面不假装审过。

| 项 | 内容 |
|----|------|
| 约定 | 新建 `inbox/`（gitignore 大 PDF 可选）：用户把题 pdf/md/txt 丢进来 |
| 改 | `orpath run --auto-intake`：扫描 `inbox/*` 或 `--intake-in`；有文件则 `skip_intake=false` |
| 改 | `orpath.bat intake-auto` / `run-full`：封装 auto-intake + live |
| 增强 P0 | pdf_text + md/txt 稳；brief 强制题面优先（复用 1.2 residual R2） |
| 增强 P1（可第二刀） | 接 Paddle/AI Studio 图 OCR；失败 → needs_human |
| 验 | `fixtures/intake/ok` 与真实 pdf 文字层 → intake.json 禁键 + 子问 ≥2 |
| 验 | 无 inbox 时 run fixture → 明确 log「legacy skip_intake」 |

### Phase 3 — OpenPi 开箱主控（移植「成功」到 GUI 路径）

**Objective:** 打开 OpenPi = 进入 OR-Path 工作法，而不是空白聊天。

| 项 | 内容 |
|----|------|
| 改 | `openpi.bat` / `orpath.bat openpi`：cd 安装根、设 `ORPATH_HOME`、`ORPATH_LIVE_SUBAGENT=1`、打印 5 行「怎么跑」 |
| 新增 | `docs/OPENPI-DEFAULT-MA-INTAKE.md`：开箱清单（中文） |
| 新增 | 项目根 `ORPATH.md` 或强化 `AGENTS.md`：**OpenPi 必读**——默认 MA、intake、禁止 cosplay、证据路径 |
| 改 | `.pi/`：确保 agents 同步；可选 `settings` 片段说明 tools（若 OpenPi 读项目 settings） |
| 新增 | `orpath.bat gui-demo`：一条龙 mock+live+intake fixture，给 GUI 旁路验证 |
| **不做 Phase1：** 大改 openpi Electron UI（留给 Phase 4） |
| 验 | **人测脚本**（你执行）：只开 OpenPi + 按 ORPATH.md 三条命令 → 磁盘证据齐；**Hermes 不在场** |

### Phase 4（可选）— OpenPi UI 按钮

- Run Full / Intake / Live toggle / 打开 evidence 文件夹  
- 仅当 Phase 1–3 仍不够「随便点」时再开 grill  

---

## 任务级施工单（批准后执行顺序）

### Task 1: 规格补丁（法条先改）

**Files:**  
- Modify: `specs/gates-and-dod.md`（默认 live / intake 策略）  
- Modify: `specs/problem-intake.md`（auto-intake / inbox 约定）  
- Modify: `specs/product-scope.md`（GUI 主控 claim）  
- Create: `docs/OPENPI-DEFAULT-MA-INTAKE.md`  

**DoD:** 写清默认 ON、如何关、CI 例外；无实现也可先 merge 法条。

### Task 2: 默认 live MA

**Files:**  
- Modify: `orpath/run_orpath.py`（default live）  
- Modify: `orpath.bat`  
- Modify: `.env.example`  
- Modify: gates 调用处加 `--no-live-subagent` 或 env  

**Verify:**  
```bat
set PYTHONNOUSERSITE=1
set ORPATH_LIVE_SUBAGENT=
orpath.bat run --problem-id shortest_path --solve-mode mock --slug def-ma --thread-id def-ma --fresh
:: expect agents log + subagent name
orpath.bat run ... --no-live-subagent --slug def-off ...
:: expect skip
```

### Task 3: auto-intake + inbox

**Files:**  
- Create: `inbox/README.md`  
- Modify: `orpath/run_orpath.py`（`--auto-intake`）  
- Modify: `orpath/intake_nodes.py` / discovery helper  
- Modify: `orpath.bat`（`run-full` / `intake-auto`）  

**Verify:**  
```bat
copy fixtures\intake\ok\source.txt inbox\
orpath.bat run-full --slug inbox-demo --thread-id inbox-demo --fresh
:: expect stages intake_* + intake.json
```

### Task 4: OpenPi 启动与项目法

**Files:**  
- Modify: `openpi.bat`, `orpath.bat` openpi 段  
- Modify: `AGENTS.md` / Create `ORPATH.md`  
- Modify: `README.md` 开箱一节  

**Verify:** 冷启动 openpi 控制台出现默认 MA=ON + 三条命令；不依赖 Hermes。

### Task 5: 门禁与回归

**Files:**  
- Modify: `scripts/subagent_gate.py`（可选：断言 default env 文档）  
- Modify: `scripts/intake_gate.py`（auto-intake smoke 可选）  
- Run: `t1_gate` / `t3_lg_gate` / `intake_gate` / `subagent_gate` 全绿（live off 路径）  

### Task 6: 人测封条（你签）

**Checklist（OpenPi，无 Hermes）：**  
1. 开 OpenPi 到本仓  
2. 按 `ORPATH.md` 跑 `run-full` 或等价  
3. 确认：`outputs/<slug>-intake.json`（若有题面）  
4. 确认：`outputs/.agents/<slug>/*-lead-*.log` 含 `"name":"subagent"`  
5. 截图可选进 `docs/archive/evidence/`  

**未过此条不得宣称「GUI 默认多 Agent + 审题」。**

### Task 7: Commit

单 commit 或拆 `feat(defaults): live MA on` + `feat(intake): auto-inbox` + `docs(openpi): gui primary`。

---

## 明确不做（本计划边界）

| 不做 | 原因 |
|------|------|
| Hermes 当产品运行时 | 你已否定 |
| 默认 live 且无 opt-out | CI/钱包爆炸 |
| 宣称扫描图 OCR 100% | P1；失败要诚实 |
| OpenPi 大改 UI（首刀） | 先 A 方案 |
| 改数字真相 / 让 LLM 写 objective | 硬法 |
| 把 B 题手写脚本会话当成 MA | 单 Agent ≠ MA |

---

## 风险与代价

| 风险 | 缓解 |
|------|------|
| 默认 live 费钱费时 | doctor 警告；README 大红；一键 off |
| OpenPi 仍只是聊天壳 | Phase 3 强制「产品命令」；Phase 4 再 UI |
| auto-intake 误吞目录杂文件 | 只扫 `inbox/` + 扩展名白名单 |
| 门禁变慢 | 门禁强制 no-live |
| 用户以为聊天 = 已跑全链 | orchestrator/ORPATH.md 禁止；跑完看 stages |

---

## 工作量粗估

| Phase | 量级 |
|-------|------|
| 1 默认 MA | 0.5–1 日 |
| 2 auto-intake | 1 日 |
| 3 OpenPi 开箱法 | 0.5 日 |
| 5 门禁回归 | 0.5 日 |
| 6 你人测 | 30–60 min |
| 4 UI（可选） | 另估 |

---

## 请你审核的决策表（回复选项即可）

| ID | 问题 | 建议默认 |
|----|------|----------|
| D1 | 默认 live MA = ON？ | **是** |
| D2 | CI/gate 强制 no-live？ | **是** |
| D3 | Intake 用 `inbox/` 自动发现？ | **是** |
| D4 | 无题面时 skip intake 并打日志？ | **是** |
| D5 | 首刀是否改 OpenPi 源码 UI？ | **否（Phase 4）** |
| D6 | 图 OCR P1 是否本刀必做？ | **否，P0 文字层先** |
| D7 | 人测封条必须你签才算 GUI 成功？ | **是** |

---

## 批准后怎么开工

你回复例如：

- `批准 A + D1–D7 默认` → 按 Task 1→7 实现  
- 或改决策：`D5=要 UI` / `D6=要上 OCR`  

**未批准前：零代码改动（本文件除外）。**
