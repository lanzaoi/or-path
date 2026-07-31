# OR-Path × Feynman 源码对齐 — 大改清单

> **For Hermes:** 用户审核前 **不实现**。实现时按 Phase 顺序、每 Phase 可独立门禁绿。  
> **参考源码（只读模板，不 fork 整仓进产品）：** `vendor/feynman/`  
> 尤其：`src/pi/launch.ts` · `src/pi/runtime.ts` · `src/bootstrap/sync.ts` · `.feynman/SYSTEM.md` · `.feynman/settings.json` · `prompts/*.md` · `extensions/research-tools.ts` · `AGENTS.md`

**Goal:** 按 Feynman 的「唯一 launch + 真注入 + 磁盘 handoff + 诚实 blocked」重接 OR-Path，消灭「默认 ON / 写了法 / OCR 修了但做 B 题仍旁路」的假接。

**Architecture:**  
保留 **LangGraph 产品图** 作控制面（OR 域 solve/validate 硬门禁不能丢），但 **所有进 Pi 的路径** 收敛到对标 Feynman 的 `launch_orpath_pi()`；SYSTEM/agents/packages/extensions 只经 **Pi 官方 flag + agentDir sync** 生效；域求解器经 **dispatch 注册表** 进图，未知域诚实 BLOCKED。  
**不改 OpenPi Electron 源码（D5 继续搁置）**；小 GUI 以后只包 `orpath launch`。

**Tech Stack:** 现有 Python `orpath/*` + Pi (`runtime/` / `.pi/`) + `tools/solve_*` + 可选读 `vendor/feynman` 作对照测试向量。

**Constraints（用户已锁）：**
- Hermes ≠ 产品运行时  
- D5：不改 `openpi/` 嵌面板  
- 数字只来自 solve+validate  
- 门禁强制 LIVE=0  
- 大改先计划审核再开工  

---

## 0. Feynman → OR-Path 映射表（总纲）

| # | Feynman 机制 | 源码锚点 | OR-Path 应对 | 现状 |
|---|--------------|----------|--------------|------|
| F1 | 唯一 `launchPiChat` | `src/pi/launch.ts` | `orpath/pi_launch_product.py` + `orpath.bat launch` | 分散：`pi.bat` / `openpi.bat` / harness 各写各的 |
| F2 | `buildPiArgs` 真参 | `runtime.ts` `--system-prompt` `--extension` `--prompt-template` | 同一 builder；禁「只 cd 开壳」 | `.pi` 自定义键 `orpath.appendSystem` **Pi 不读** |
| F3 | `PI_CODING_AGENT_DIR` 隔离 | `buildPiEnv` | 固定 product agentDir + env | 部分有 `pi_launch_law`，未成唯一入口 |
| F4 | bootstrap sync agents/skills | `bootstrap/sync.ts` | `scripts/orpath_bootstrap_sync.py`：`.pi/agents`→agentDir | 文件在仓，无 hash sync |
| F5 | CORE packages 含 pi-subagents | `.feynman/settings.json` + presets | `.pi/settings.json` 钉死 packages；doctor 验 tool 可见性 | 有 packages，缺 launch 绑定证明 |
| F6 | SYSTEM.md 经 CLI 注入 | `.feynman/SYSTEM.md` | `.pi/SYSTEM.md`（合并 APPEND+OR 法）+ `--system-prompt` | APPEND_SYSTEM 未进 launch |
| F7 | prompt-template 工作流 | `prompts/deepresearch.md` | `.pi/prompts/`：`run-full.md` `intake.md` `solve-b.md` | 无；靠 bat 字符串 |
| F8 | extension 真注册工具 | `extensions/research-tools.ts` | 可选 `extensions/orpath-tools.ts` 或 Python tools 仅经 dispatch；先不抄 TS 研究工具 | OCR/solve 在 Python，未进 Pi 可见集 |
| F9 | 磁盘 slug handoff | AGENTS.md outputs/ | 已有 notes/outputs/papers；统一 slug 法 + plan ledger | 部分有，B 旁路不遵守 |
| F10 | 诚实 blocked | SYSTEM + deepresearch | intake 未知域 BLOCKED；**已注册域必须真算** | intake **一律** BLOCKED，polyomino 孤儿 |
| F11 | 范围纪律 | AGENTS Feature scope | specs：产品环 vs 竞赛 adapter 清单 | 双世界（水赛旁路） |
| F12 | workbench=Pi control plane | workbench/* | `orpath.bat menu` = 唯一推荐壳；OpenPi 可选且必须经 launch 包装 | menu 有；OpenPi 仍可裸开 |

---

## 1. 目标架构（改完后）

```text
用户
  ├─ orpath.bat menu | launch | run-full | intake
  │         │
  │         ▼
  │   orpath/pi_launch_product.py   ←── 对标 Feynman launchPiChat
  │         │  build_pi_args/env
  │         │  bootstrap_sync
  │         ▼
  │   Pi 子进程（SYSTEM + subagents + prompts）
  │
  └─ orpath.bat run / run-full
            │
            ▼
      LangGraph product graph
            │
            ├─ intake_ocr / parse（真引擎）
            ├─ live nodes → 只通过 pi_launch_product / harness 起 Pi
            ├─ node_solve → solve_dispatch（注册表）
            │       ├─ mock|networkx|cpsat|ortools|tube|polyomino|…
            │       └─ 未注册 + intake → BLOCKED（诚实）
            └─ validate / paper / review
```

**禁止：**
- 水赛目录默认做题当产品路径  
- 裸 `openpi.bat` 不经 bootstrap 却宣称 MA  
- `settings.json` 里 Pi 不认识的键冒充「已注入」  
- intake 开了却绑 SP fixture 假绿  

---

## 2. Phase 总览与验收

| Phase | 名 | 人日（估） | 验收（必须命令级） |
|-------|----|------------|-------------------|
| **P0** | 规格 + 对照矩阵冻结 | 0.5 | `specs/feynman-launch-parity.md` 合入 |
| **P1** | 唯一 Pi launch + SYSTEM 真注入 | 1–2 | `orpath.bat launch --print-args` 含 system-prompt 文本/hash；doctor 查 agentDir |
| **P2** | bootstrap sync agents/packages | 1 | sync 后 agentDir 有 or-*；改源再 sync 更新 |
| **P3** | prompt-template 工作流 | 1 | `launch --workflow run-full` 会话首条含协议要点 |
| **P4** | dispatch 域桥（polyomino 首个） | 2–3 | intake B fixture → solution 非 BLOCKED 且数字=求解器 |
| **P5** | LG 节点只走 launch_law | 1–2 | live 日志仍有 `name:subagent`；无第二套 spawn |
| **P6** | 菜单/文档/反旁路 | 0.5 | ORPATH.md；openpi 包装打印 launch 要求 |
| **P7** | 门禁 + 人测封条 | 1 | t1/t2/intake/subagent gate 绿；人测 A1–A5 |

**合计约 8–12 人日。** 可先批 P0–P3（接线），再批 P4（B 题真通）。

---

## 3. 详细任务清单

### Phase P0 — 规格冻结

#### Task P0.1: 写 parity 规格

**Files:**
- Create: `specs/feynman-launch-parity.md`
- Modify: `specs/README.md`（索引一条）
- Modify: `docs/adr/` 新增 `ADR-0007-feynman-launch-parity.md`（决策：LG 保留 + Pi launch 唯一）

**内容必须含：**
- 上表 F1–F12  
- 非目标：不 vendoring 整份 Feynman UI；不抄 alpha/生物工具  
- 成功定义：用户只跑 `orpath.bat …` 即可；证据在磁盘  

**Verify:** 规格可被 gate 文档链接；无代码。

---

### Phase P1 — 唯一 Launch（对标 `launch.ts` + `runtime.ts`）

#### Task P1.1: 抽出 `build_pi_args` / `build_pi_env`

**Files:**
- Create: `orpath/pi_launch_product.py`
- Modify: `orpath/pi_launch_law.py`（复用或薄包装，避免三套）
- Modify: `orpath/subagent_harness.py` / `subagent_runtime.py`（改为调用 product launch builder）

**对标 Feynman API 形状：**

```python
@dataclass
class PiLaunchOptions:
    app_root: Path          # repo root
    working_dir: Path
    session_dir: Path
    agent_dir: Path         # .pi 或 runtime agent home
    mode: str | None = None           # text|json
    system_prompt_path: Path | None = None  # .pi/SYSTEM.md
    extension_paths: list[Path] = field(default_factory=list)
    prompt_template_dir: Path | None = None  # .pi/prompts
    one_shot_prompt: str | None = None
    model: str | None = None
    extra_args: list[str] = field(default_factory=list)

def build_pi_args(opt: PiLaunchOptions) -> list[str]: ...
def build_pi_env(opt: PiLaunchOptions) -> dict[str, str]: ...
def launch_pi(opt: PiLaunchOptions) -> int: ...  # subprocess
def print_launch_plan(opt: PiLaunchOptions) -> dict: ...  # doctor/--print-args
```

**硬规则（抄 Feynman）：**
- 若 `SYSTEM.md` 存在 → args 必须含 `--system-prompt` **文件全文或 Pi 支持的路径形式**（以本机 Pi CLI 为准；先 `pi --help` 查）
- env 必须设 `PI_CODING_AGENT_DIR`（及若有 `FEYNMAN_CODING_AGENT_DIR` 类自定义则 `ORPATH_CODING_AGENT_DIR` 仅文档，**主键仍是 PI_***）
- `cwd=working_dir`（产品仓）

**Test:**
- Create: `tools/test_pi_launch_product.py`
  - mock 无真实 Pi：断言 args 列表含 session-dir、system-prompt 内容非空、agent env 键存在
  - `print_launch_plan` JSON 稳定字段

**Verify:**
```bat
.venv-314\Scripts\python.exe -m pytest tools/test_pi_launch_product.py -q
orpath.bat launch --print-args
```

#### Task P1.2: `.pi/SYSTEM.md` 真法（合并）

**Files:**
- Create: `.pi/SYSTEM.md`（从 `APPEND_SYSTEM.md` + OR 硬法 + Feynman 式 tool discipline 精简）
- Modify: `.pi/APPEND_SYSTEM.md` → 改为「已合并到 SYSTEM.md」指针或删除重复
- Delete 幻觉：`.pi/settings.json` 的 `"orpath.appendSystem"` 键（或改成注释文档字段移到 specs）

**SYSTEM.md 必含（对标 Feynman SYSTEM）：**
- 身份：OR-Path product agent  
- 数字真相 / 禁 cosplay  
- 只用可见 `subagent` tool  
- 控制面：`orpath.bat`；裸聊 ≠ 全图  
- 缺 adapter → blocked 落盘  
- 产物路径 notes/outputs/papers  

#### Task P1.3: `orpath.bat launch` 子命令

**Files:**
- Modify: `orpath.bat`
- Modify: `scripts/orpath_menu.py`（菜单项「Launch Pi (wired)」）
- Modify: `ORPATH.md`

```bat
orpath.bat launch              REM 交互 Pi，已注入 SYSTEM
orpath.bat launch --print-args
orpath.bat launch --workflow run-full --slug X
```

**openpi.bat / `orpath openpi`：**  
启动前跑 bootstrap + 打印：「MA 证据仍看 orpath run-full；本壳不自动全图」。  
可选：设置与 launch 相同的 `PI_CODING_AGENT_DIR`（若 OpenPi 读该 env）。

---

### Phase P2 — Bootstrap sync（对标 `bootstrap/sync.ts`）

#### Task P2.1: sync 脚本

**Files:**
- Create: `scripts/orpath_bootstrap_sync.py`
- Create: `runs/.orpath-bootstrap-state.json`（gitignore）或 `%LOCALAPPDATA%/orpath/bootstrap-state.json`
- Modify: `scripts/orpath_doctor.py`（调用 sync + 报告）

**同步映射：**
| 源 | 目标 |
|----|------|
| `.pi/agents/*.md` | `{agentDir}/agents/` |
| `.pi/prompts/*` | `{agentDir}/prompts/` 或 launch `--prompt-template` 直指仓内 |
| `.pi/settings.json` packages | 由 Pi 包管理消费；doctor 检查 |

**行为抄 Feynman：**
- source hash / target hash  
- 用户改过 target 且 ≠ lastApplied → skip（不覆盖）  
- 源更新且 target 仍是上次写入 → update  

**Test:** `tools/test_bootstrap_sync.py` 用 tmp 目录。

#### Task P2.2: settings 钉死 CORE packages

**Files:**
- Modify: `.pi/settings.json`

最低 packages（对齐 Feynman core 思想，名称用现有）：
```json
"packages": [
  "npm:pi-subagents@0.37.2",
  "npm:@samfp/pi-memory"
]
```
可选后续：docparser/web-access（非本大改必须）。

**doctor 检查：** agentDir 下 node_modules 或 Pi 报告含 subagents；否则 FAIL。

---

### Phase P3 — Prompt-template 工作流（对标 `prompts/deepresearch.md`）

#### Task P3.1: 目录与三份协议

**Files:**
- Create: `.pi/prompts/README.md`
- Create: `.pi/prompts/run-full.md`
- Create: `.pi/prompts/intake-only.md`
- Create: `.pi/prompts/contest-polyomino.md`（B 题专用协议）

**`run-full.md` 结构（抄 deepresearch 纪律）：**
1. Tool discipline（字面工具名；禁 Task 冒充 subagent）  
2. 立即写 `outputs/.plans/<slug>.md`  
3. Scale：何时 spawn research/model/writer  
4. 文件 handoff 列表  
5. Verification：solution.json / validate / provenance  
6. 失败 → blocked 落盘，禁 chat-only  

**`contest-polyomino.md`：**
- 必须调用产品 `orpath run` / solve_polyomino，禁水赛旁路  
- 子问清单 Q1–Q3  
- 数字只认 outputs  

#### Task P3.2: launch 挂 `--prompt-template`

**Files:**
- Modify: `orpath/pi_launch_product.py`  
- 查本机 Pi 是否支持 `--prompt-template`（Feynman 用）；若 OpenPi 版 Pi 旗标不同，**adapter 层兼容**并在 doctor 写明。

**Verify:** `--print-args` 含 prompt-template 路径。

---

### Phase P4 — 域桥：dispatch + 有条件解除 BLOCKED（对标「能力可见才算有」）

> 这是 **B 题接进产品** 的唯一结构性修复。P1–P3 只接线；P4 才出数。

#### Task P4.1: 注册 polyomino adapter

**Files:**
- Modify: `tools/solve_dispatch.py`  
  - `ADAPTER_SCRIPTS["polyomino"] = "solve_polyomino.py"`  
  - 必要时 `polyomino_q3` → `solve_polyomino_q3.py`  
- Modify: `tools/solve_polyomino.py` CLI 与 envelope 对齐 `normalize_solution`  
- Test: `tools/test_solve_dispatch_polyomino.py`（小 fixture 或 mock 超时短）

#### Task P4.2: intake class 识别

**Files:**
- Modify: `tools/intake_parse.py` → `guess_problem_class_hint` 增加：
  - `多联骨牌|polyomino|骨牌覆盖|tetromino`
- Modify: `orpath/intake_nodes.py` / state：把 hint 写入 `problem_class`  
- Modify: `orpath/run_orpath.py`：允许 `--problem-class polyomino`

#### Task P4.3: `node_solve` 白名单放行（改 F10）

**Files:**
- Modify: `orpath/nodes.py` `node_solve`

**新逻辑：**
```text
if intake_front_door_active:
    if problem_class in REGISTERED_INTAKE_CLASSES:  # {"polyomino", "tube", ...}
        → 走 solve_dispatch(mode=adapter)
    else:
        → BLOCKED no_domain_adapter  (保持诚实)
else:
    → 现有 fixture/SP/TSP/VRP 路径
```

**REGISTERED_INTAKE_CLASSES** 与 `ADAPTER_SCRIPTS` 单一来源（dry）。

#### Task P4.4: B 端到端 fixture

**Files:**
- Create: `fixtures/intake/polyomino/` 最小题面 txt（或现有 B 摘要）  
- Create: `docs/b-polyomino-product-smoke.md`  
- Test / script: `scripts/polyomino_product_smoke.py`

**验收数字（已有仓内真值，仅作回归锚，来自求解器）：**  
Q 相关 objective 必须与 `tools/solve_polyomino` 输出一致；**禁止**散文编造。

**Verify:**
```bat
set ORPATH_LIVE_SUBAGENT=0
orpath.bat run --fresh --slug b-smoke --thread-id b-smoke --problem-class polyomino --intake-in fixtures\intake\polyomino\source.txt --solve-mode polyomino
:: solution.json status != BLOCKED
```

---

### Phase P5 — LG live 节点收敛到同一 launch

#### Task P5.1: 审计所有 spawn 点

**Files to grep & unify:**
- `orpath/subagent_harness.py`
- `orpath/subagent_runtime.py`
- `orpath/subagent_dispatch.py`
- `orpath/graph_live_subagent.py`
- `orpath/paper_live_subagent.py`
- `orpath/pi_bridge.py`

**规则：** 禁止直接 `subprocess pi` 拼参；一律 `launch_pi` / harness 调 builder。

#### Task P5.2: 证据不变式

- live ON：`outputs/.agents/<slug>/*-lead-*.log` 含 `"name":"subagent"`  
- LIVE=0：gate 仍绿  

---

### Phase P6 — 控制面与反旁路

#### Task P6.1: menu 升级

**Files:** `scripts/orpath_menu.py`  
增加：
- Launch Pi (wired)  
- Run polyomino smoke  
- Print launch args（调试）

#### Task P6.2: 文档

**Files:**
- `ORPATH.md` 重写「唯一入口」  
- `AGENTS.md` 增加 Feynman-parity 三条（launch 未验证=未完成）  
- `docs/OPENPI-DEFAULT-MA-INTAKE.md` 标明被 P1 取代的部分  
- `inbox/README.md`：B 题 PDF 丢 inbox → run-full 的预期（P4 后）

#### Task P6.3: 反旁路（软）

- `contest-polyomino.md` + SYSTEM：禁止默认改水赛目录交卷  
- doctor：若 cwd 不在 ORPATH_HOME 警告  

**不**强删用户水赛目录。

---

### Phase P7 — 门禁与人测

#### Task P7.1: 自动化

```bat
set ORPATH_LIVE_SUBAGENT=0
orpath.bat gate-intake
orpath.bat subagent-gate
orpath.bat gate
:: + pytest tools/test_pi_launch_product.py tools/test_bootstrap_sync.py tools/test_intake_ocr.py
:: + polyomino product smoke
```

#### Task P7.2: 人测封条（你签）

| ID | 操作 | 过线 |
|----|------|------|
| H1 | `orpath.bat launch --print-args` | 见 system-prompt / agentDir |
| H2 | `orpath.bat menu` → Launch | 会话知 OR 法（抽问禁编造 objective） |
| H3 | intake 扫图 fixture | meta backend ≠ placeholder |
| H4 | polyomino product smoke | solution 非 BLOCKED，数字=工具 |
| H5 | 裸 OpenPi（若仍用） | 文档写明 ≠ 全图；不宣称已 MA |

---

## 4. 建议提交切片（frequent commits）

1. `docs(spec): feynman launch parity ADR-0007`  
2. `feat(pi): pi_launch_product build_args/env + bat launch`  
3. `feat(pi): SYSTEM.md + remove dead appendSystem key`  
4. `feat(pi): bootstrap sync agents`  
5. `feat(pi): prompts run-full/intake/polyomino`  
6. `feat(solve): polyomino adapter + intake class`  
7. `feat(graph): intake allowlist solve for registered classes`  
8. `refactor(live): all spawns use launch builder`  
9. `docs: ORPATH unique entry + smoke`  

---

## 5. 明确不抄 Feynman 的部分（防范围爆炸）

| 不抄 | 原因 |
|------|------|
| workbench-web / serve UI | D5；体积 |
| alpha-hub / 生物/化学工具 | 非 OR 产品 |
| PostHog 遥测 | 非必需 |
| 整包 replace LangGraph | OR 硬门禁依赖 LG |
| deepresearch 默认「先问 yes」交互 | 产品可 `run-full` 无人值守；协议可选用 |

---

## 6. 风险

| 风险 | 缓解 |
|------|------|
| 本机 Pi CLI 旗标 ≠ Feynman 的 `--system-prompt` | P1 先 `pi --help` 探测；兼容层 |
| polyomino 全问太慢 | smoke 用小实例；30×30 限时 FEASIBLE 诚实标 |
| sync 覆盖用户改 agent | hash skip 策略 |
| 大改破坏 t1/t2 | 每 Phase 后门禁；LIVE=0 |
| 用户仍走水赛旁路 | 文档+prompt 硬约束；产品路径出数后自然迁移 |

---

## 7. 决策表（请批）

| ID | 决策 | 建议 |
|----|------|------|
| D1 | 保留 LG 控制面 + Feynman 式 Pi launch | **是** |
| D2 | D5 仍不改 openpi 源码 | **是** |
| D3 | P4 polyomino 作为第一注册 intake 域 | **是** |
| D4 | 未知 intake 域继续 BLOCKED | **是** |
| D5 | 一次性做完 P0–P7 vs 先 P0–P3 | 建议 **先 P0–P3 接线，再 P4 出 B 数** |
| D6 | OpenPi 是否强制经 `orpath launch` 包装 env | **是（软强制：openpi.bat 注入 agentDir）** |

---

## 8. 批准话术

- `批准 Feynman 大改，D 全默认，先 P0–P3`  
- `批准全量 P0–P7`  
- `只批 P4 域桥`（不推荐单独做，launch 仍假）  

**未批准前：仅本计划文件，不写实现。**

---

## 9. 与旧计划关系

| 旧计划 | 关系 |
|--------|------|
| `2026-07-31_openpi-boot-ma-ocr.md` | OCR/menu **并入** P1/P6；D5 一致搁置 |
| 默认 LIVE + inbox (`b752c44`) | 保留；**服从** 唯一 launch |
| 1.2 BLOCKED | **收窄**：仅未注册域；注册域真算 |

---

## 10. 一页检查清单（实现时打勾）

- [ ] 存在唯一 `launch_pi` / `orpath.bat launch`  
- [ ] `--print-args` 证明 SYSTEM 注入  
- [ ] 无 Pi 不读的「假 settings 键」冒充完成  
- [ ] bootstrap sync agents  
- [ ] packages 含 pi-subagents 且 doctor 验  
- [ ] `.pi/prompts/*` 工作流  
- [ ] `ADAPTER_SCRIPTS` 含 polyomino  
- [ ] intake + polyomino → 非 BLOCKED  
- [ ] 未知 intake → BLOCKED  
- [ ] live spawn 无分叉实现  
- [ ] 门禁绿  
- [ ] 人测 H1–H5  
