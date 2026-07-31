# OpenPi「一开就有多 Agent + OCR」Implementation Plan

> **For Hermes:** 用户先审核；**未批准前不实现**。  
> **验收标准（用户冻结）：** `OpenPi 一开就有多 Agent + OCR` — 不以 CLI 默认、不以关单话术代替 GUI 体感。

**Goal:** 用户只打开 OpenPi 并选中本仓，**无需 Hermes、无需先记一堆 bat 命令**，即可：  
(1) 会话默认具备 **真多 Agent（pi-subagents 工具可用且被系统法强制使用）**；  
(2) 丢题面（含扫描 PDF/图片）即可 **OCR → brief/intake**；  
(3) 一键/自动入口跑产品全链，磁盘证据可自证。

**Architecture:**  
- **控制面仍是** LangGraph + `orpath run`（数字真相不变）。  
- **OpenPi 变成真主控壳：** 开仓 hook → 注入 OR-Path 系统法 + 默认 tools（含 subagent）+ OCR/intake 技能 + UI 入口（按钮/斜杠/欢迎卡）。  
- **OCR：** 产品路径接通 Paddle/AI Studio（或本机 paddleocr），废掉「只有 placeholder」的默认。  
- **多 Agent：** 禁止「裸聊天 cosplay」；开仓会话 = harness 级 tools；全链仍走 `orpath` 子进程或 Pi 强制 `task`/`subagent`。

**Tech Stack:** OpenPi (Electron) · Pi SDK · `pi-subagents` · 可选 `pi-task` · `orpath` CLI · `tools/intake_ocr.py` · PaddleOCR / 已有 AI Studio MCP 桥 · `.pi/` 项目配置

---

## 0. 验收定义（必须可测、可证伪）

### 0.1 「一开」操作路径（人测唯一路径）

```text
1. 不启动 Hermes
2. 双击 orpath.bat openpi  或  openpi.bat（工作区 = Desktop/agent）
3. 等待 UI 就绪（≤60s）
4. 不先手动敲 run-full（理想）；若必须点一次按钮，按钮须在首屏可见
```

### 0.2 通过标准（全部满足才算修好）

| ID | 标准 | 证据 |
|----|------|------|
| **A1** | 首个 Pi 会话 **tools 含 `subagent`**（或等价 task 委派） | OpenPi 工具列表 / session 启动 log |
| **A2** | 系统提示含 OR-Path 硬法：禁 cosplay、数字只认 solve | `.pi/APPEND_SYSTEM` 或 openpi bridge 注入文本 |
| **A3** | 用户丢 **扫描 PDF 或 png** 到指定入口 → 产出 `notes/*-ocr.raw.md` + `*-intake.json`，backend ≠ placeholder 失败 | 磁盘文件 + `ocr.meta.json.backend` |
| **A4** | 点首屏 **「跑全链」**（或等价）→ research/model/cite/review 至少一段 log 含 `"name":"subagent"` | `outputs/.agents/<slug>/` |
| **A5** | 全程无 Hermes | 操作录像/自述 |

### 0.3 明确「不算过」

- 只改了 `ORPATH_LIVE_SUBAGENT=1` 但 OpenPi 里仍要终端敲命令才算 MA  
- OCR 仍是 `paddleocr placeholder` / 只认文字层 PDF  
- 聊天里模型说「我是多 Agent」但无 toolcall  
- 门禁绿但 GUI 测不到  

---

## 1. 现状差距（相对该标准）

| 层 | 现状 | 距「一开」 |
|----|------|-----------|
| OpenPi | 宿主 Pi 会话的 Electron 壳；有 subagent widget、task 扩展能力 | **开仓不会自动进 OR-Path 法 + 产品图** |
| 本仓 `.pi/settings.json` | 已装 `pi-subagents` | 会话 tools 是否默认带 subagent **取决于 Pi/OpenPi 启动配置**，GUI 未保证 |
| `orpath.bat openpi` | 打印提示 + doctor + 启 UI | **仍是「提示你去终端跑」**，不满足一开 |
| intake OCR | `manual_stub` / `pdf_text`；`paddleocr` = **placeholder** | **扫描图失败** |
| 产品图 | CLI `run-full` 可用 | **未挂到 OpenPi 首屏** |

**结论：** `b752c44` 只做到「CLI/默认策略」；**本计划专治 GUI 开箱标准。**

---

## 2. 目标体验（用户视角）

```text
打开 OpenPi（本仓）
    │
    ├─ 欢迎卡 / 侧栏「OR-Path」
    │     · 状态：LIVE MA = ON · OCR = ready/not
    │     · [选择题面] [从 inbox 导入] [跑全链] [仅审题]
    │
    ├─ 默认聊天会话
    │     · 已注入 OR-Path 系统法
    │     · tools: read, bash, subagent, …（+ 可选 orpath_* 自定义工具）
    │
    └─ 用户拖入 题.pdf / 截图.png
          → OCR → brief/intake 预览
          → 确认后「跑全链」
          → 进度：stages + agents 日志 tail
          → 完成：打开 evidence 文件夹
```

---

## 3. 方案选型

### 方案 S1（推荐，**已按 D5 修订**）：薄启动器 + 本仓 `.pi` 法 + OCR；**不改 openpi 源码**

| 块 | 内容 |
|----|------|
| **S1-a 开仓注入** | 本仓 `.pi/APPEND_SYSTEM.md` + settings：检测 OR-Path 仓 → 硬法 + subagent 包 |
| **S1-b 默认 tools** | 项目 `.pi/settings.json` 保证 pi-subagents；任意 Pi 宿主（OpenPi / 未来小 GUI / 终端 Pi）共用 |
| **S1-c OCR** | `intake_ocr` 接通真实 Paddle（见 §4）；与 GUI 解耦 |
| **S1-d 首屏入口（不绑 OpenPi）** | **`orpath.bat menu` 或极薄 `orpath-gui`（可选 tkinter/webview 单文件）** 四按钮；内部 spawn `orpath`。OpenPi 仅作可选宿主 |
| **S1-e 证据** | 按钮/菜单打开 `outputs/.agents`、`runs/*/stages` |

**优点：** 满足能力就绪；**换 GUI 不推倒**；OpenPi 体积问题不堵主线。  
**缺点：** 在 OpenPi 里仍可能要侧开菜单/终端一次（见 D1）；不是 OpenPi 内嵌面板。

### 方案 S1-old（搁置）：OpenPi extension 内嵌面板

改 `openpi/` 加侧栏。**用户 D5 搁置** — 本阶段不做。

### 方案 S2：只做「超级欢迎 prompt + 技能」

开仓只塞一段「请你调用 subagent 和 OCR」的系统提示。  
**否决：** 仍易 cosplay；扫描 OCR 仍挂；不满足 A3/A4 硬证据。

### 方案 S3：大改 OpenPi 核心 fork

成本过高，非必要；与 D5 一致 **不做**。

**本计划采用 S1（修订版，无 openpi 源码）。**

---

## 4. OCR 子计划（A3 核心）

### 4.1 后端优先级（产品）

| 优先级 | Backend | 输入 | 说明 |
|--------|---------|------|------|
| 1 | `pdf_text` | 文字层 PDF | 已有，保留 |
| 2 | `paddleocr_local` | png/jpg/扫描 PDF 渲染页 | **本刀必做** |
| 3 | `paddleocr_remote` | 同上 | AI Studio / 已有 MCP 的 HTTP 封装 |
| 4 | `manual_stub` | md/txt | 已有 |
| fail | placeholder | — | **禁止**再当「成功」 |

### 4.2 实现要点

- Modify: `tools/intake_ocr.py`  
  - 去掉 `extract_paddleocr_placeholder` 作为默认真路径  
  - 实现：`pdf2image`/`pymupdf` 渲页 → paddleocr predict → 拼 raw md  
  - `meta.backend` 写真实名；失败 `ok:false` + `needs_human`  
- 依赖：可选 `paddlepaddle`/`paddleocr` 或调用外部 `paddleocr` CLI；Windows 路径与 `PYTHONNOUSERSITE` 隔离  
- 配置：`.env.example` 增加 `ORPATH_OCR_BACKEND=auto|pdf_text|paddleocr_local|paddleocr_remote`  
- 验收 fixture：`fixtures/intake/ocr/` 增加 **真实扫描样例**（小图）或用现有 sample + 一张强制走 paddle 的 png  

### 4.3 OpenPi 侧 OCR 入口

- 拖放文件到 OR-Path 面板 / 聊天附件 → 调用  
  `orpath.bat intake --slug <auto> --in <path>`  
  或 Python `standalone_intake`  
- UI 显示：backend、页数、brief 路径、禁键门禁结果  

---

## 5. 多 Agent 子计划（A1/A2/A4 核心）

### 5.1 「一开就有」的两层含义（都要做）

| 层 | 含义 | 做法 |
|----|------|------|
| **L1 会话层** | 打开即具备 subagent 工具 + 禁 cosplay 法 | `.pi` settings + APPEND_SYSTEM + OpenPi 扩展 |
| **L2 产品图层** | 真跑 research/model/cite/review harness | 首屏按钮 → `orpath run --auto-intake`（LIVE 默认 1） |

**注意：** 仅 L1 不够（用户仍可能闲聊）；仅 L2 不够（聊天里仍像单 Agent）。**L1+L2 同时过 A 表。**

### 5.2 L1 实施

**Files（预期）：**

- Create/Modify: `C:\Users\Lanzao\Desktop\agent\.pi\APPEND_SYSTEM.md`（或 Pi 等价 append）  
  内容硬法：  
  - 本仓是 OR-Path；数字只认 solve+validate  
  - 需要隔离角色时必须 `subagent` tool，禁止散文 cosplay  
  - 审题/全链优先建议用户点面板或调用 `orpath` CLI，勿假装已跑 LG  
- Modify: `.pi/settings.json`  
  - 确保 `packages` 含 `pi-subagents`  
  - 若 Pi 支持 default tools 列表 → 写入含 `subagent`  
- Modify: `openpi/.pi/extensions/` 新增 `orpath-bootstrap.ts`（或本仓扩展被 OpenPi 加载的路径）  
  - `onSessionStart`：若 cwd 含 `orpath.bat`+`ORPATH.md` → 注入状态条文案  

### 5.3 L2 实施

**Files（预期）：**

- OpenPi extension IPC：`orpath.runFull` / `orpath.intake` / `orpath.status`  
  - `child_process.spawn(orpath.bat, [...], { cwd: ORPATH_HOME, env: { ORPATH_LIVE_SUBAGENT: '1', PYTHONUNBUFFERED: '1' }})`  
  - stdout/stages 推到 UI  
- UI：侧栏或 Command Palette  
  - 「审题 (OCR+intake)」  
  - 「跑全链 (live MA)」  
  - 「廉价演示 (no-live)」  
  - 「打开证据目录」  
- 进度：轮询 `runs/<thread>/stages` + `outputs/.agents/<slug>`

### 5.4 成本护栏（必须）

- 首屏显示：**LIVE MA 会消耗 DeepSeek**  
- 开关：UI toggle → `ORPATH_LIVE_SUBAGENT=0|1`  
- `gui-demo` 默认仍可 live；提供「演示（关 live）」  

---

## 6. 分 Phase 交付

### Phase P0 — 验收契约与法条（0.5d）

- 写 `specs/openpi-boot-ma-ocr.md`（本验收表）  
- 更新 `ORPATH.md`：旧「终端三条」降级为 fallback；主路径改为「OpenPi 首屏」  
- **人测脚本** checklist 定稿  

### Phase P1 — OCR 真接通（1–2d）

- `intake_ocr` paddle 真实现 + fixture  
- `intake_gate` 增加「扫描样例 PASS」或 skip-if-no-engine  
- CLI：`orpath intake --in scan.png` 绿  

### Phase P2 — OpenPi L1 会话默认 MA 法（1d）

- `.pi/APPEND_SYSTEM` + settings  
- 开仓后新会话 tools/system 可检  
- 单元/手工：新 session 日志含 subagent tool 注册  

### Phase P3 — 宿主无关控制面（1d，**不改 openpi 源码**）

- `orpath.bat menu`：审题 / 全链 / 关 live 演示 / 打开证据  
- 可选极薄 `scripts/orpath_tray.py`（tkinter，单文件，可扔）  
- OpenPi 仅：`openpi.bat` 启动时仍打印「请用 orpath.bat menu」— **不**加 Electron 面板  
- 进度：轮询 stages（终端打印即可）  

### Phase P3-openpi（**搁置 / backlog**）

- 仅当选定长期 GUI 后再做内嵌面板；候选：小 Webview / 自研 / 他壳，**非**当前必做  

### Phase P4 — 打磨与回归（0.5–1d）

- t1/t3/intake/subagent gates 仍绿（live off）  
- 文档/截图进 `docs/archive/evidence/openpi-boot-*.png`  
- commit  

**合计粗估：4–6 人日**（含 OCR 引擎踩坑缓冲）。

---

## 7. 任务级施工单（批准后顺序）

### Task 1: 法条 `specs/openpi-boot-ma-ocr.md`

写死 A1–A5、非目标、OCR backend 优先级。

### Task 2: OCR paddle 实现

- Modify: `tools/intake_ocr.py`, `tools/test_intake_ocr.py`  
- Create: `fixtures/intake/ocr/scan_sample.png`（小）  
- Verify:  
```bat
set PYTHONNOUSERSITE=1
.venv-314\Scripts\python.exe tools\intake_ocr.py --slug ocr-scan --in fixtures\intake\ocr\scan_sample.png --root .
:: meta.backend 含 paddle，非 placeholder
```

### Task 3: intake 门禁挂钩

- Modify: `scripts/intake_gate.py` / S2 tests：有引擎则必测 scan；无引擎则明确 SKIP 并 **fail-close 产品声明**（不能宣称 OCR ready）

### Task 4: 本仓 `.pi` 开箱法

- Create: `.pi/APPEND_SYSTEM.md`（OR-Path 硬法）  
- Modify: `.pi/settings.json`  
- Verify: Pi/OpenPi 新会话 system 含关键字 `subagent` / `OR-Path`

### Task 5: （搁置）OpenPi bootstrap extension

**Status: DEFERRED (D5).** 不修改 `openpi/` 源码。

### Task 6: 宿主无关控制面 `orpath.bat menu`

- Modify: `orpath.bat` 增加 `menu`  
- Optional Create: `scripts/orpath_menu.py`（编号菜单，零 Electron）  
- Verify: 无 OpenPi 也能完成 A3/A4（menu → intake / run-full → 证据）  

### Task 7: 端到端人测（你签）

按 §0.1–0.2；截图 + evidence json。

### Task 8: 回归门禁 + commit

```bat
set ORPATH_LIVE_SUBAGENT=0
orpath.bat gate-intake
orpath.bat subagent-gate
orpath.bat gate-t3
```

---

## 8. 风险与依赖

| 风险 | 缓解 |
|------|------|
| Windows 装 Paddle 重/慢 | 优先 remote/MCP 桥；local 可选安装脚本 |
| OpenPi 扩展 API / 体积 | **D5 搁置**：不改 openpi 源码；控制面用 bat/menu |
| 换小 GUI | 产品能力在 `orpath` + `.pi`；新 GUI 只包一层 spawn |
| 一开就 auto-run 全链太贵 | **默认不自动跑全链**；一开 = 能力就绪 + 一键；若你坚持「零点击开跑」可加 D8 |
| 与上游 OpenPi 升级冲突 | 扩展放本仓可拷贝路径；少改 openpi 核心 |
| 假 MA | A4 强制磁盘 `"name":"subagent"` |

---

## 9. 请你拍板的决策表

| ID | 问题 | 建议默认 |
|----|------|----------|
| **D1** | 「一开」是否允许 **首屏点 1 次「跑全链」**（不必零点击自动烧钱）？ | **是，允许 1 次点击** |
| **D2** | 零点击自动跑全链？ | **否**（太贵） |
| **D3** | OCR 引擎优先 | **Paddle 本地，失败再 remote/MCP** |
| **D4** | 无 OCR 引擎时产品是否允许宣称「OCR ready」？ | **否（fail-close）** |
| **D5** | 是否改 `openpi/` 源码加面板？ | **搁置（用户 2026-07-31）** — OpenPi 体积大，可能换更轻 GUI；**禁止**本阶段绑死 openpi 源码 |
| **D6** | LIVE 默认仍 ON？ | **是**（面板可关） |
| **D7** | 人测必须你签才算过？ | **是** |

---

## 10. 与已交付工作的关系

| 已有 | 本计划 |
|------|--------|
| `b752c44` CLI 默认 LIVE + inbox + ORPATH.md | **保留为引擎层** |
| 门禁 live=0 | **不变** |
| 本计划 | **补齐 GUI 开箱标准；接真 OCR** |

---

## 12. 决策日志

| 日期 | 决策 |
|------|------|
| 2026-07-31 | 用户：**D5 搁置** — OpenPi 体积大，可能换更小 GUI；本阶段 **不改 openpi 源码加面板**。控制面改为 `orpath.bat menu` / 可选薄脚本；OCR + `.pi` 法 + CLI 全链仍做。 |
