# Human Steer · 人机协同引导 · Web Studio 交互与断点控制（权威规范）

> **状态：** LAW 2026-11（全面接入 Web Studio 可视化人机确认弹窗与断点控制；旧版 D2–D4 文件级 Steer 契约向下兼容保留）  
> **配套：** `specs/process-visibility.md`（过程脸）· `specs/control-plane.md`（阶段机）· `specs/multi-agent.md`（4 常驻特种兵）· `specs/solvers-and-validate.md`（数字真理）  
> **核心原则：** **控制类指令归流程（Web Studio / LangGraph），认知类提示归智能体，数值与最优解归求解器。严禁用户或模型在对话框中手写/篡改 objective。**

---

## 0. 现行架构：Web Studio 人机协同双向交互（Tier-1 主流形态）

在现代原生纯 Python 体系下，人机协同主要通过 **Web Studio**（`START.bat` / `START.sh`，运行于 `orpath/web/`）与 **Live Watch** 对话层承载：

1. **题目摄入期人机交互确认（Problem Intake Confirmation）**：
   - 用户拖拽题目文件夹或 PDF/TXT 之后，前端实时调用 `studio_analyzer.py` 剖析出数据维度、时间序列长度、硬物理约束提示。
   - 弹出结构化表单允许用户：切换求解模式（如从 `mock` 切换为 `networkx` / `highs` / `cpsat`）、调整时间上限（Time Limit）、显式指定 `Tier-A/B/C`。
2. **实时断点控制与阶段放行（Pause / Steer / Resume）**：
   - 控制面支持 `pause_next` 机制：在进入高开销阶段（如求解 `solve` 或正式撰写 `draft_paper`）前挂起，等待用户点击放行。
   - 允许向特定阶段注入提示词（`steer_prompt`），由对应智能体（如 `or_analyst` 或 `or_modeler`）在隔离调用时作为附加上下文读取。
3. **安全红线**：
   - 任何人类介入均**严禁直接修改或伪造计算客观目标值（`objective`）**。
   - 所有经过调整的模型与参数仍必须无条件经过 `validate_solution.py` 独立物理重算与 DIMO 门禁检验。

---

## 0.1 历史与无头通道：文件级 Steer 契约（Tier-2 Headless）

在无前端或自动化回归脚本中，系统通过 `inputs/steer.json` 或工作区中的 `steer.json` 提供强类型人控通道：

| 字段 | 含义 | 行为 |
|------|------|------|
| `mode_override` | 覆盖 `solve_mode`（如 `highs`, `networkx`） | 阶段机在进入 `solve` 节点前替换调度参数 |
| `pause_next` | 是否在下一节点暂停 | 置位后在目标节点前停机，等待 CLI `resume` |
| `steer_prompt` | 人工指导文字 | 注入目标节点的任务 Brief 中 |
| `objective` | 尝试手写目标值 | **绝对拒绝（REJECT）**，触发安全报警 |

---

---

## 0. 一句话

| 层 | 引导形态 | 是什么 |
|----|----------|--------|
| **Watch 对话层（Tier-1 脸增强）** | 阶段精要气泡 + 结构化人导表单 | 产品主脸；读盘；可写 steer 文件 |
| **LG 控制面** | **无**聊天插件；认 state / CLI / steer **控制字段** | 换 `solve_mode`、从哪站续、暂停放行 |
| **Pi 引导插件（Tier-2）** | 社区扩展 + 内置 steer | 会话内深导、目标监督、向人提问、看板 |

**禁止：** 把 Pi 插件当第二控制面；Watch 用 LLM 编时间线；对话框改 objective。

---

## 1. 研究结论（Pi 社区 · 开源引导相关）

调研基准：Pi `@earendil-works/pi-coding-agent`（本仓 `runtime/`）+ 官方 packages 模型 + npm 社区包（2026-08）。

### 1.1 内置（零安装 · 最重要）

| 能力 | 来源 | 行为 |
|------|------|------|
| **Steering message** | Pi TUI 核心 | 运行中 **Enter** 排队；当前 tool 批结束后注入 |
| **Follow-up** | 同上 | **Alt+Enter**（Windows Terminal 常需改键）；整段工作结束后再投递 |
| **RPC `steer` / `followUp`** | `docs/rpc.md` | 宿主进程可编程注入（未来 Watch→Pi 深链可用） |
| **Session 树** | `/tree` · JSONL | 分支、回放、细看 |

→ **「引导」首先是 Pi 一等公民，不是必须装插件才有。**

### 1.2 社区包（与「人导 / 监督 / 看板」直接相关）

| 包 | npm | 角色 | OR-Path 用法 |
|----|-----|------|----------------|
| **pi-supervisor** | `pi-supervisor@0.5.0`（tintinweb） | 外侧监督 LLM：目标 `/supervise`；漂移则 **steer**；不改主 agent system | **交互 Pi 深导**；项目规则 `.pi/SUPERVISOR.md` |
| **pi-kanban** | `pi-kanban@1.0.0`（NikiforovAll） | Web 看板：sessions / todos / subagents | **Tier-2 深看**（P4 已预留）；需 session 落盘 |
| **pi-subagents** | 已装 `0.37.2` | 派 sub；子上可 **steer/interrupt/stop/resume** | 产品 LIVE 主路径已依赖 |
| **@juicesharp/rpiv-ask-user-question** | `2.x` | 结构化问卷（选项式问人，少瞎猜） | 交互 Pi：模型该问人时用；kanban 可铺 Q&A 卡 |
| **@juicesharp/rpiv-todo** | 可选 companion | todo 列给 kanban | **未默认装**（减面）；要满配 kanban 再装 |
| **@samfp/pi-memory** | 已装 | prefs/lessons 类记忆 | 已有；**禁**权威 optima（`memory.md`） |

**明确不选为默认：**

| 包/方向 | 原因 |
|---------|------|
| 再叠一套「聊天壳」重写 Watch | 违 S1：脸=Watch 读盘 |
| 默认强制 supervisor 进产品 headless LIVE | 多一次 LLM、慢、难 gate；且 headless lead 常 `--no-session` |
| 任意第三方「自动改 objective」类 | 违数字真理 |

### 1.3 本仓已执行的安装（工程事实）

**项目本地**（`pi install … -l --approve` → `.pi/settings.json` + `.pi/npm/`）：

```text
npm:pi-subagents@0.37.2          （原有）
npm:@samfp/pi-memory             （原有）
npm:pi-kanban                    （新）
npm:pi-supervisor                （新）
npm:@juicesharp/rpiv-ask-user-question  （新）
```

校验：

```bat
cd /d <ORPATH_HOME>
pi.bat list
:: Project packages 应含 pi-kanban / pi-supervisor / rpiv-ask-user-question
```

项目监督规则文件：

- `.pi/SUPERVISOR.md` — OR-Path 数字真理 + 禁改 optima + 弱解改 adapter

---

## 2. 信息分流（冻结）

人在「对话框 / 表单 / CLI」输入后：

```text
                    ┌─ for: lg  ──────────────────────────► LangGraph / runner state
人输入 ─► steer 文件┤
                    └─ for: pi  ──────────────────────────► 下一站 Pi spawn prompt
                               （可选）深链 ─► 交互 Pi + 插件
数字 / objective ─────────────────────────────────────────► REJECT
```

| 字段类 | Owner | 例 |
|--------|-------|-----|
| **控制** | LG / runner | `solve_mode`, `resume_from`, `fresh`, `pause_policy`, `force_re_solve` |
| **认知** | 将执行的 Pi 站 | `prefer_methods[]`, `notes`, `focus_chunk_ids[]`, `modeling_hints` |
| **禁止** | — | `objective`, `tour`, `routes`, `proven_optimal=true` 手填 |

---

## 3. 制品合同

### 3.1 `notes/<slug>-human-steer.json`（权威人导单）

```json
{
  "schema_version": 1,
  "slug": "demo-steer",
  "utc": "2026-08-09T00:00:00Z",
  "at_stage": "after_research",
  "lg": {
    "solve_mode": "highs",
    "resume_from": "solve",
    "fresh": false,
    "pause_next": false
  },
  "pi": {
    "prefer_methods": ["cpsat", "column_generation"],
    "notes": "Q2 共切优先四模式包络；不要只 BFD",
    "focus_chunk_ids": [],
    "modeling_hints": "schema preferred_solve_mode 与 lg.solve_mode 一致"
  },
  "source": "watch_form|cli|file",
  "forbid_numbers_edit": true
}
```

| 规则 | |
|------|--|
| 写者 | 人（Watch 表单 / 手写 / 未来 API） |
| LG 读者 | `run_orpath` / 边界节点：合并 `lg.*` 进 state |
| Pi 读者 | `bridge_pi` / spawn：把 `pi.*` 拼进该站任务书 |
| 多份 | 同 slug **最后写赢**；历史可 `human-steer.jsonl` 追加（可选后置） |
| 与 gate | gate **默认不**因缺 steer 失败；有非法数字键 → 拒绝合并并记 `last_error` |

### 3.2 阶段精要气泡（Watch 只读）

来源 **仅磁盘**（与 snapshot 同源），禁止 Watch 调 LLM 生成假对话：

| 气泡角色 | 优先源 |
|----------|--------|
| 系统/阶段 | `runs/<slug>/stages/*.json` · `node`/`stage`/`utc` |
| 研究 | `notes/<slug>-retrieval.json` · research md/path |
| 建模 | schema path · `preferred_solve_mode` |
| 求解 | `*-solution.json` status/objective/meta |
| 校验 | `*-validate.json` ok/errors |
| 人导 | `human-steer.json` 摘要 |
| HUMAN | `*.HUMAN_REQUIRED.md` · snapshot error/CTA |

可选后置：对超长 transcript 的 **标明** `summary_of_disk` 摘要——不得替代 solution/validate。

---

## 4. 产品分层与切片

### 4.1 与 S1 / P4 关系

```text
Tier-1  Watch：时间线 +（本规格）对话精要 + 结构化人导表单
Tier-2  Pi session + pi-kanban +（可选）supervisor / ask-user
Tier-3  Langfuse 等（仍可选，P5 表面）
```

脸 **永远**是 Watch。插件满配 **不是** V0 PASS 条件（与 P4「强制装 kanban 不做」一致）。

### 4.2 实现切片（未开工默认）

| ID | 交付 | 动谁 | DoD 草案 |
|----|------|------|----------|
| **D0** | Watch 只读阶段精要气泡 | `watch.html` + snapshot 字段 | 对 fixture slug 非空 L0 气泡；无 LLM |
| **D1** | 表单 → 写 `human-steer.json` + CTA 带 mode/resume | Watch API + CTA 规则 | 非法 objective 键被拒；CTA 可复制 |
| **D2** | LG 边界可选 pause；读 steer 合并 state 再派 Pi | `control_plane` / nodes | 单测：mode 覆盖；Pi prompt 含 notes |
| **D3** | Tier-2 深链：session on → kanban/supervise 文档化手测 | 文档 + 可选 gate 字符串 | `ORPATH_PI_SESSION=1` + list 含包 |

**工程进度（2026-08-09）：**

| 切片 | 状态 | 落点 |
|------|------|------|
| 插件安装 + SUPERVISOR | ✅ | `.pi/settings.json` · `.pi/SUPERVISOR.md` |
| **D0 气泡** | ✅ | `snapshot.dialogue.bubbles` · `orpath/web/watch.html` `#dialogueSection` |
| **D1 表单+API** | ✅ | `POST/GET /api/steer` · `notes/<slug>-human-steer.json` · 表单 CTA |
| **D2 LG 合并** | ✅ | `apply_steer_to_state` · orchestrate/research/model/solve · Pi briefs · `resume_from` · pause_next |
| **D3 Tier-2 深链** | ✅ | `tier2.deep_links` · `package_status` · Watch L4 面板 · `docs/_deprecated/d3-tier2-deep-link.md` |
| **D4 E2E 收口** | ✅ | 表单 `pause_next`/`at_stage` · product `invoke_once` 验 mode · `orpath.bat dialogue-gate` · `docs/_deprecated/d4-dialogue-e2e.md` |

门禁：`orpath.bat dialogue-gate` → `scripts/dialogue_steer_gate.py`（D0–D4）· `scripts/p4_session_gate.py`  

**D4 行为摘要：**

1. Watch 表单可写 **暂停边界**（`at_stage`）+ **pause_next**；API 平铺字段进 `lg.*`。  
2. 产品 mock 路径：`notes/<slug>-human-steer.json` 的 `solve_mode` **覆盖** CLI mock（例 networkx），`gate_validate_ok`。  
3. 一键门禁：`orpath.bat dialogue-gate`（`ORPATH_APPLY_STEER=1`，LIVE off）。  
4. 手测/说明：`docs/_deprecated/d4-dialogue-e2e.md`。  

**人导规格切片 D0–D4 收口**（主路径可见可导可合并 + 可选深链 + E2E）。

---

## 5. 操作手册（装好后怎么用）

### 5.1 交互 Pi（认知引导 · 插件主场）

```bat
cd /d <ORPATH_HOME>
pi.bat
:: 内置：跑着时 Enter = steer；Alt+Enter = follow-up（注意 Windows Terminal）

:: 目标监督
/supervise Prefer exact solve tracks; never invent objective; use tools/solve_dispatch + validate
/supervise sensitivity medium
/supervise stop

:: 看板（需本机已装 pi-kanban）
/kanban start
/kanban open web
```

### 5.2 产品 LIVE + 给 kanban 喂 session

```bat
set ORPATH_PI_SESSION=1
set ORPATH_LIVE_SUBAGENT=1
orpath.bat watch-run --live --keep-watch --slug steer-session-demo
```

默认 `ORPATH_PI_SESSION=0` → lead `--no-session` → kanban **看不到** 产品 lead（只看得到你交互 `pi.bat` 的 session）。诚实徽章：`tier2_session_off`。

### 5.3 LG / 航向引导（今天就有 · 不靠插件）

```bat
:: 换引擎重跑
orpath.bat run --fresh --problem-id tsp_n8 --solve-mode highs --slug tsp-highs

:: 只验算法
.venv-314\Scripts\python.exe tools\solve_dispatch.py tsp_n8 --mode highs
```

D1/D2 后：Watch 表单写 `lg.solve_mode` → 生成等价 CTA，仍 **手动**执行（浏览器不自动 resume——M1 硬法）。

### 5.4 Headless 产品 sub 与 supervisor

| 模式 | supervisor |
|------|------------|
| 交互 `pi.bat` | ✅ 推荐 `/supervise` |
| 产品 harness lead/sub（json/ephemeral） | **默认不启用** supervisor（成本+无 TUI）；认知靠 spawn 任务书 + skill + 未来 `pi.*` steer 字段 |
| 未来可选 | RPC steer 注入 running child（`pi-subagents` 已有 steer API）— 单独立项 |

---

## 6. 安全与卫生

1. **第三方包 = 全权限代码**（Pi 官方警告）。已装包来源：npm 公开包；升级用 `pi.bat update` 审 changelog。  
2. `pi install` 时 npm audit 可能报高危依赖——**不**在本规格要求 `audit fix --force`（易破 pin）；发布前人工扫。  
3. **不把** `.pi/npm/node_modules` 整树当「源码真相」提交策略：与现网 L2 半肥策略对齐——项目 `.pi/settings.json` **可提交**；`npm` 树可由 `pi install` 恢复（L2 pack 是否打入另见 `docs/install.md` / pack 脚本，本规格不强制改 pack）。  
4. Supervisor 另耗 token；演示默认 **sensitivity medium**，gate **禁止**依赖 supervisor 才绿。

---

## 7. 非目标

- Watch 内嵌完整 Pi TUI  
- LG 上「聊天插件市场」  
- 自动把弱 FEASIBLE 刷成 OPTIMAL  
- M3 launch 注入 / M4 记忆史诗借本规格偷开  
- 默认 LIVE 全站挂 supervisor  

---

## 8. 验收话术（claim ladder）

| 可说 | 不可说 |
|------|--------|
| 「项目已 **本地安装** pi-kanban / pi-supervisor / ask-user-question；交互 Pi 可 `/supervise` `/kanban`」 | 「Watch 对话框人导已完工」 |
| 「人导分流：控制→LG，认知→Pi；steer 文件合同已立法」 | 「装插件 = 产品自动换高难算法」 |
| 「内置 Enter steer 是 Pi 一等引导」 | 「必须装 supervisor 才算多 Agent」 |
| 「Tier-2 仍可选；脸是 Watch」 | 「kanban 替代 V0」 |

---

## 9. 索引与后续

| 动作 | 路径 |
|------|------|
| 本规格 | `specs/human-steer-and-pi-guidance.md` |
| Supervisor 项目规则 | `.pi/SUPERVISOR.md` |
| 包列表 | `.pi/settings.json` → `packages` |
| 旧 P4 说明 | `docs/archive/design-notes/p4-tier2-deep-look.md` |
| 用户点「开 D0」 | 只做 Watch 精要气泡 |
| 用户点「开 D1」 | steer 文件 + CTA |
| 用户点「开 D2」 | LG 合并 steer |

---

## 10. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-08-09 | 初版：社区调研 + 项目 `-l` 安装三包 + SUPERVISOR.md + 双通道 steer 合同 + D0–D3 切片 |
