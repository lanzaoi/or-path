# OR-Path 理想目标 — 套在 Learn Claude Code 骨架上

> **地位：** 活文档 / 心智与作品集讲法。**不是法。**  
> **法：** `specs/product-flow-sdd.md` ≥ `specs/process-visibility.md` ≥ 其它 `specs/**` ≥ 本文件。  
> **冲突时：** 以 specs + 门禁真实输出为准；本文件只负责「理顺」与对外叙事。  
> **参照骨架：** [Learn Claude Code](https://learn.shareai.run/zh/)（shareAI-lab）— *Agency 在模型；产品 = 模型 + Harness*。  
> **写法：** 保留 LCC 的层次与 s01–s20 课程序列；每一格改写成 **OR-Path 领域 harness 的理想目标**，不是重做一个 nano Claude Code。

---

## 0. 先背三句（和 LCC 对齐后的 OR 版）

| # | LCC 原意 | OR-Path 落点 |
|---|----------|--------------|
| 1 | Agency 来自模型训练，不是 if-else 编排冒充智能 | 认知判断在 **DeepSeek（Pi）**；**不算数、不翻全局页** |
| 2 | 你造的是 **Harness（载具）**，不是「编出智能」 | 载具 = **LG 进度 + Pi/sub 站内脑 + 脚本计算器/质检 + watch 观察面** |
| 3 | 一个 loop 稳定；机制挂在外面逐层加 | **全局进度 loop = LG**；**站内 agent loop = Pi**；扩展用 hook/事件/门禁，不把质检写进散文 |

**背诵句（产品法）：**  
**LG 翻页；Pi 只在某一页招人；打回是 LG 往回翻（有上限）；算分页永远手算；脸是 watch 读盘。**

```text
User / 题面
    │
    ▼
 LangGraph  ───────────  总进度表（now→next、回边、resume、HUMAN）
    │  每一站
    ├─ 脚本站 ──► tools（OCR / schema / solve / validate / R1 / R2）
    └─ 认知站 ──► Pi lead（无 write）──► pi-subagent ──► 文件路径回写
                                                      │
                         watch 实时台 ◄── 读盘 L0–L4 ─┘
```

---

## 1. 产品一句话（理想终态）

**自然语言 / 题面运筹问题**  
→（可选 intake OCR/审读）  
→ 检索与研究 → 建模（schema，**禁 optima**）  
→ **确定性求解 + validate**  
→ 解释与论文（有界 R1/R2 打回）  
→ 人在本机 **`orpath.bat watch`** 实时看见：站序、派工树、sub 工具轨迹（及诚实的 thinking 有/无）。

**三大用户价值（同级，V1 不可砍成「以后再说」）：**

| ID | 价值 | 理想验收脸 |
|----|------|------------|
| **V1** | 实时看见协作与 sub 过程 | Live Watch（L0–L4） |
| **V2** | 能做题出**可信数字** | `solution.json` + validate 绿 |
| **V3** | 像系统而非纯脚本脸 | menu/watch 主脸；脚本是手 |

---

## 2. Harness 公式（LCC → OR）

LCC：

```text
Harness = Tools + Knowledge + Observation + Action + Permissions
```

OR-Path 展开：

```text
OR Harness =
  Tools        : solve_* / validate / intake / R1 / R2 / retrieve …
  Knowledge    : specs、ADR、corpus、notes、skills（按需，不塞满窗）
  Observation  : stages JSON、lead toolCall、sub transcript、solution 路径
  Action       : Pi 工具 + 脚本入口（orpath.bat / control_plane）
  Permissions  : lead 无 write、anti-cosplay、LIVE vs gate、禁 LLM 写 objective
  + Control    : LangGraph 唯一全局翻页（LCC 通用 coding harness 常缺这一层 → 我们领域增强）
  + Face       : watch 实时台（Observation 的产品化，不是运维翻文件夹）
```

**模型是驾驶者；OR Harness 是运筹考场 + 质检车间 + 过程直播间。**

---

## 3. 架构层次（套 LCC L1–L5）

与官网「架构层」同构；名称沿用，**职责改成 OR。**

### L1 — Tools & Execution（工具与执行）

| 理想目标 | 说明 |
|----------|------|
| 工具原子、可组合、描述清晰 | 求解/校验/OCR 与「读笔记」分开 |
| **数字只从求解工具出** | `objective` / path / tour / routes ⊆ solve + validate 重算 |
| 权限在执行前 | 危险写盘、假 MA、禁键在 harness 拦，不靠模型自觉 |
| 横切不污染核心 | 日志、timeline 事件、审计 = hook/旁路，不把 loop 写成意大利面 |

**栈：** `tools/*`、`orpath.subagent_*`、`pi_launch_law`。

### L2 — Planning & Control（规划与控制）

| 理想目标 | 说明 |
|----------|------|
| 长任务有显式计划 | `outputs/.plans/<slug>.md`；可纠偏 |
| 站内大活拆 sub | 干净 `messages[]`；回传路径/摘要，不灌父窗 |
| 知识按需 | agent 角色 md + retrieval，不一次塞全书 |
| system/policy 运行时组装 | 角色、LIVE 开关、工具白名单是生成的，不是写死一篇巨 prompt |
| 失败可分类重试 | tune≤3 → model≤2 → HUMAN；论文 revise≤2 |

**栈：** LangGraph 边与计数器 + Pi lead 策略 + repair 状态机。

### L3 — Memory Management（记忆）

| 理想目标 | 说明 |
|----------|------|
| 上下文会满 → 可压缩 | 父窗保路径与结论；长轨迹在 sub/文件 |
| 跨会话战法 | **Skill / agent md** 为主加强轴（稳定套路） |
| 短 prefs | pi-memory 可选 |
| 图记忆 | Cognee **smoke 旁路**，非主轴 |
| **记忆永不权威 optima** | 与 LCC「有用记忆」同在；OR 多一条硬禁 |

**栈：** `runs/` + notes + **Skill/agent md** +（可选）pi-memory + Cognee smoke。  
**开闸：** V0+M0 PASS 前不新开记忆大脑 / Cognee 生产化。详见 `specs/memory.md`。

### L4 — Concurrency & Scheduling（并发与调度）

| 理想目标 | 说明 |
|----------|------|
| 慢活可后台 | OCR/检索/重解不堵死「看见过程」 |
| 调度在 harness | 重试与定时不是模型「记得明天再跑」 |

**OR 现实：** 主路径是 **同步阶段图**；真并行不是 M0 阻塞项。  
**LCC s14 Cron：** 非目标（默认 OUT）。

### L5 — Multi-Agent Platform（多 Agent 平台）

| 理想目标 | 说明 |
|----------|------|
| 任务可观察、有序 | **站 = 图上的任务**；状态在 `runs/<thread>/stages` |
| 真隔离协作 | research / modeler / verifier / reviewer 分会话 |
| **显式协议** | 文件契约 + schema/solution JSON + gate 字段；不是 vibe 聊天 |
| 派工可证明 | `toolName=subagent` + transcript；禁 cosplay |
| 观察面产品化 | watch = 多 agent 平台的「脸」 |

**明确不采用 LCC 默认形态：**

| LCC | OR |
|-----|-----|
| s15 持久队友 + 文件 mailbox 总线 | **OUT**（Teams/Bus 脊柱已否决） |
| s17 自主认领任务板 | **OUT**（抢单破坏 LG 唯一翻页） |
| s18 每人 git worktree | **OUT**（主叙事）；并行用路径契约即可 |
| s19 MCP 市场 | **后置**；V0+M0 前不新开 |

**OR 多 Agent 形态名：**  
**带验证关卡的 Supervisor–Worker 流水线**（hierarchical pipeline + tool verifiers）  
= LCC 的「sub + task 可观察 + 协议」精神，**控制面换成 LG，通信主轴换成文件手递。**

---

## 4. 课程序列 s01–s20 → OR 理想目标卡

> 读法：每张卡 =「这一层在理想 OR-Path 里必须成立什么」。  
> **状态：** `DONE` 历史资产已具备心智/代码骨架 · `NOW` 当前产品必达 · `LATER` 后置 · `OUT` 不进主产品。

### 4.1 L1 Tools & Execution

#### s01 · The Agent Loop — 循环稳定

| | |
|--|--|
| **理想目标** | 存在清晰、不可模糊的「谁在转圈」：全局是 LG 状态机；站内是 Pi `messages[]` loop。 |
| **OR 要求** | 禁止 Pi∥LG 双老板；禁止聊天跳阶段；脚本站无强制 LLM loop。 |
| **验收语** | 任意时刻能回答：现在是哪一站、谁拥有 next。 |
| **状态** | DONE（拓扑锁）· 讲法要常温习 |

#### s02 · Tool Use — 能力进表

| | |
|--|--|
| **理想目标** | 能力 = 注册进 dispatch 的工具；加能力主要加表项与适配器，不改「翻页哲学」。 |
| **OR 要求** | `solve_dispatch` / `solve_*` / validate / intake / R* 分表；认知工具与计算器工具不混谈。 |
| **验收语** | 新问题类优先加 adapter，而不是让 writer「编个最优值」。 |
| **状态** | DONE（T1/T2 类）· 域扩展 LATER |

#### s03 · Permission — 执行前裁决

| | |
|--|--|
| **理想目标** | 危险与作弊面在 harness 决策点拦截。 |
| **OR 要求** | Lead **无 write/edit**；`--mode json`；schema 禁解答键；gate 强制 `LIVE=0`；禁密钥/题面进 git。 |
| **验收语** | cosplay 产物 quarantine；数字门禁不靠「模型保证」。 |
| **状态** | DONE 骨架 · 持续守 |

#### s04 · Hooks — 挂在循环外 ★

| | |
|--|--|
| **理想目标** | 日志、阶段点、派工事件、timeline 聚合 = **Pre/Post 工具与站边界 hook**，不塞进 prompt 自述。 |
| **OR 要求** | 站进入/离开、sub spawn、tool 序写入 **可被 watch 消费的磁盘/事件**；禁止 LLM 编「大家想了啥」当主 UI。 |
| **验收语** | 关掉模型旁白仍能靠事件画出 L0–L2。 |
| **状态** | **NOW（V0 数据面）** |

### 4.2 L2 Planning & Control

#### s05 · TodoWrite — 显式计划

| | |
|--|--|
| **理想目标** | 长跑有清单：当前计划可见、可改、不靠模型「还记得」。 |
| **OR 要求** | `outputs/.plans/<slug>.md`；orchestrate 可写；watch/导出可链到 plan。 |
| **验收语** | 人能指着 plan 说「卡在哪一步」。 |
| **状态** | 部分 DONE · 与 watch 联动 NOW |

#### s06 · Subagent — 干净上下文 ★

| | |
|--|--|
| **理想目标** | 大任务拆小；子会话独立 `messages[]`；结束交 **路径/摘要**；父窗不被 60 轮检索污染。 |
| **OR 要求** | 真 `pi-subagents`；角色 `or-researcher/modeler/verifier/reviewer…`；文件手递 `notes/ outputs/ papers/`；真 MA 四条（可检、隔离、toolCall、数字仍工具）。 |
| **验收语** | 磁盘有 `name:subagent` / transcript；裸 `pi -p` 不得称 MA。 |
| **状态** | DONE 能力 · **M0 证据演示 NOW** |

#### s07 · Skill Loading — 按需知识

| | |
|--|--|
| **理想目标** | 领域知识与角色说明按需注入，不把 specs 全书塞进每一窗。 |
| **OR 要求** | `.pi/agents/or-*.md` + retrieval/notes；题面 intake 与知识库分流（MinerU≠题面 OCR）。 |
| **验收语** | 换角色 = 换薄设定 + 工具集，不是换人格演戏。 |
| **状态** | 部分 DONE · 精炼 LATER |

#### s10 · System Prompt — 运行时组装

| | |
|--|--|
| **理想目标** | system = policy × tools × skills × 本站上下文的**生成物**。 |
| **OR 要求** | `pi_launch_law` + harness 快照；SINGLE_LEAD vs MA 横幅诚实。 |
| **验收语** | 同一代码路径，LIVE 开/关、角色站，prompt 面可解释差异。 |
| **状态** | 部分 DONE |

#### s11 · Error Recovery — 失败分类

| | |
|--|--|
| **理想目标** | 失败分型：可调参 / 应回模 / 应回稿 / 必须 HUMAN；有上限，不装死循环绿。 |
| **OR 要求** | 求解侧与论文侧回边计数见 SDD；无 adapter **BLOCKED** 诚实。 |
| **验收语** | Demo 能讲清一次打回；计数器在 state/台面可见。 |
| **状态** | DONE 逻辑 · **M0 可讲 NOW** |

### 4.3 L3 Memory

#### s08 · Context Compact

| | |
|--|--|
| **理想目标** | 窗满时压的是过程渣，不是任务契约与路径真源。 |
| **OR 要求** | 父 lead 短；大块在文件；checkpointer 存状态不存「假 objective」。 |
| **状态** | 原则 DONE · 专用 compact 策略 LATER |

#### s09 · Memory

| | |
|--|--|
| **理想目标** | 战法可跨会话（Skill）；prefs 可薄记；图仅 smoke；**禁止**记忆覆盖 validate。 |
| **OR 要求** | 见 `specs/memory.md`：Skill > L0/L1 > 种子图/检索 > prefs ≫ Cognee。 |
| **状态** | Skill/角色 md 可渐进 · 大脑史诗 **LATER（V0+M0 后）** |

### 4.4 L4 Concurrency

#### s13 · Background Tasks

| | |
|--|--|
| **理想目标** | 慢 I/O 不堵观察；用户仍能看阶段在动。 |
| **状态** | 非 M0 阻塞 · LATER 按需 |

#### s14 · Cron Scheduler

| | |
|--|--|
| **理想目标** | （通用 harness 有）定时产活。 |
| **OR 要求** | **OUT** 主产品；不做「每晚自动交卷」。 |
| **状态** | **OUT** |

### 4.5 L5 Multi-Agent Platform

#### s12 · Task System — 可观察任务图 ★

| | |
|--|--|
| **理想目标** | 大目标 = 有序、可恢复、可观察的任务/站；依赖与状态在盘上。 |
| **OR 要求** | LG 阶段图 + `runs/.../stages/*.json` + plan；**脸 = watch L0**，不是只有 `.tasks` 给开发者看。 |
| **验收语** | 跑的过程中阶段条会变；resume 语义不被 Pi 抢。 |
| **状态** | 图 DONE · **脸 V0 NOW** |

#### s15 · Agent Teams

| | |
|--|--|
| **LCC 意** | 持久队友 + 收件箱并行。 |
| **OR 理想（改写）** | **固定角色流水线 + 站内临时 sub**，不是长期群聊团队。 |
| **状态** | 流水线 DONE · **mailbox Teams OUT** |

#### s16 · Team Protocols

| | |
|--|--|
| **理想目标** | Agent 之间靠**结构化契约**，不是 vibe。 |
| **OR 要求** | schema/solution/intake JSON；gate 字段 owner；手递路径约定；shutdown/审批类协议 **非必须**（LG HUMAN 已覆盖停机）。 |
| **状态** | 契约 DONE · 持续硬化 |

#### s17 · Autonomous Agents（抢单）

| | |
|--|--|
| **OR 要求** | **OUT**。工作发现与分配由 **LG 调度 + 站内 lead 派 sub**，不由队友浏览看板 claim。 |
| **状态** | **OUT** |

#### s18 · Worktree Isolation

| | |
|--|--|
| **OR 要求** | 上下文隔离优先；文件系统用目录契约。全量 worktree 并行 **OUT** 主叙事。 |
| **状态** | **OUT**（可笔记级提及） |

#### s19 · MCP Tools

| | |
|--|--|
| **理想目标** | 外设标准协议接入（OCR 云、检索等已有特例）。 |
| **OR 要求** | 不挡 V0；不把「MCP 市场」当里程碑。 |
| **状态** | **LATER** |

#### s20 · Comprehensive Agent — 仍是分层，不是一团

| | |
|--|--|
| **理想目标** | 全部机制就位后，**用户仍只感知一条做题路径 + 一块过程台**；内部仍是 LG+Pi+tools。 |
| **OR 要求** | menu / `demo-m0` 单一入口叙事；doctor；无密钥；claim ladder 诚实。 |
| **状态** | **目标态 = V0+M0 体验 PASS**（再往上才是域扩展与抛光） |

---

## 5. 领域特有层（LCC 骨架上的「OR 补丁章」）

LCC 教的是通用 coding harness。OR-Path **必须**多三章，否则套骨架会丢灵魂：

### oA · Numbers Truth（数字真相）— 硬补丁

```text
objective / path / tour / routes
  唯一来源 = solve 工具 JSON + validate 重算
禁止：记忆、论文、sub 旁白、lead 总结「算」出最优
```

### oB · Gate Ladder（质检与打回）— 硬补丁

```text
schema（禁 optima）→ solve → validate → R1/R2
回边有上限 → HUMAN_REQUIRED + provenance
```

### oC · Live Watch Face（过程脸）— 硬补丁 = V0

```text
L0 阶段 · L1 派工 · L2 sub 轨迹 · L3 thinking|unavailable · L4 数字路径
入口：orpath.bat watch / menu / 本地 URL
假交付：只开文件夹、只事后 md、只 gate 绿、只 Hermes 贴 log
```

这三章在作品集里应与 s04/s06/s12 **绑在一起讲**。

---

## 6. 理想目标总表（一页纸）

| 层 | 理想一句话 | 当前产品焦点 |
|----|------------|--------------|
| L1 工具 | 计算器与质检真；权限在前 | 守门禁 |
| L2 规划控制 | LG 翻页 + 站内 plan/sub/recovery | M0 可讲打回 |
| L3 记忆 | 有记性但不篡改数字 | 后置 |
| L4 并发 | 慢活不噎死脸 | 非阻塞 |
| L5 多 Agent | 真 sub + 契约 + **可看见** | **V0 脸 + M0 证据** |
| oA 数字 | 只手算 | 永久 |
| oB 门禁 | 有上限回修 | 永久 |
| oC 脸 | 实时 watch | **最高优先** |

### 里程碑套骨架

```text
V0  = s04 事件面 + s12 可观察站 + oC 实时台（L0–L3 底线）
M0  = V0 + oA 可信数字 + s06 真 sub 证据 + s11 打回可讲 + 单一入口
此后 = s07/s10 精炼、域 adapter、s09 记忆、s19 MCP…（按 specs 优先级）
永不 = s14 主路径 Cron、s15 mailbox Teams、s17 抢单、s18 worktree 主叙事
```

---

## 7. 与「严格跟网站一步一步重写」的边界

| 做 | 不做 |
|----|------|
| 用 LCC 层次讲清 OR harness | 用 s01 代码替换 `control_plane` |
| 一步只攻一个机制（先 V0） | 从零再实现 nano agent 当产品 |
| sub = 干净上下文 + 文件手递 | 持久 Teams 总线 |
| task 可观察 = LG stages + watch | 让模型自由 claim 看板 |
| hooks 喂观察面 | LLM 生成「协作内心戏」UI |
| specs 为法 | 本文升级为法 |

---

## 8. 推荐阅读顺序（理顺用）

```text
1. 本文 §0–§3     — 骨架与公式
2. 本文 §4–§6     — 理想卡与 V0/M0
3. specs/product-flow-sdd.md
4. specs/process-visibility.md
5. specs/architecture.md · multi-agent.md
6. LCC 原站：优先 s04 · s06 · s11 · s12（对照，不抄 Teams）
```

---

## 9. 修订

| 日 | 说明 |
|----|------|
| 2026-08-03 | 初版：LCC L1–L5 + s01–s20 映射 OR 理想目标；钉 V0/M0/OUT |

**维护原则：** specs 变则改映射表；不得在本文发明与 SDD 冲突的控制面。
