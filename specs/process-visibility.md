# Process Visibility — 过程可见性与 Sub 思考过程（**产品硬底线**）

**状态：** LAW（与 `product-flow-sdd.md` **同级**；冲突时本文件管「看见什么/在哪看」）  
**用户底线（2026-08 锁定）：**  
> **实时可视化协作全过程 + sub 思考过程 = 必须交付的底线，不是可选美化、不是 M1 以后再说、不是「先门禁绿再考虑脸」。**

**原则：**

1. 可视化 = **读磁盘/事件流真相**，禁止 LLM 编「大家想了啥」当主界面  
2. **没有合格实时可视 = 产品未达底线**，不得宣称「多 Agent 产品体验完成」  
3. 门禁绿、有 lead log、会 `menu 6` 开文件夹 → **全部不够**当可视底线  

---

## 0. 底线定义（先读这节）

### 0.1 什么叫「达标」

用户在 **跑的过程中**（不必等 END）必须能打开 **一个固定入口**，看到：

| 必须同时有 | 说明 |
|------------|------|
| **R1 实时/准实时台** | 自动刷新（≤3s 或文件变更即刷），不是只生成静态 md 了事 |
| **阶段条 L0** | 当前站、已完成站、绿/红/跑着 |
| **派工树 L1** | 哪站 spawn 了哪个 or-*（真 toolCall，不是旁白） |
| **Sub 过程 L2** | 选中 sub 后可见：工具调用序、读写路径、assistant 片段 |
| **思考 L3** | 有 thinking/reasoning 则展示（默认可折叠）；**无则明确标 `thinking_unavailable`**，禁止装有 |
| **入口固定** | `orpath.bat watch` / menu 明确项 / 本地 URL 三者至少一，**写进 README** |

### 0.2 什么叫「未达标」（假交付）

| 假交付 | 为何不算 |
|--------|----------|
| 只有 `runs/` + `.agents/` 文件夹 | 运维盯盘，不是产品脸 |
| 只有跑完后的 `timeline.md` | 事后报告，**不满足实时底线**（可作附属） |
| menu「打开证据目录」 | 捷径 ≠ 可视化 |
| Hermes/聊天里粘 log | 非产品运行时 |
| gate/subagent_gate 绿 | 工程证，不是用户看见过程 |
| 「以后做 HTML」写在计划里 | 计划 ≠ 底线已满足 |

### 0.3 与 M0/里程碑关系（改口）

| 旧写法（作废） | 新法 |
|----------------|------|
| 实时 UI = M1/M2 以后 | **实时台 = 底线切片 V0 / 与数字 Demo 同级硬依赖** |
| M0 只需静态 timeline.md | M0 **必须**含 **watch 实时台**；静态 md 仅导出附件 |
| 先做求解再补脸 | **脸与跑通可并行，但宣称体验完成前脸必须在** |

**切片名建议：**

```text
V0 — Live Watch 底线（本文件 §0 + §3）
M0 — V0 + 可信数字 + 真 sub 证据（总流程）
```

无 V0 → 不得宣称 M0 用户体验 PASS。

---

## 1. 看见什么（L0–L4）

| 层 | 名称 | 是什么 | 权威源 | 底线 |
|----|------|--------|--------|------|
| **L0** | 流水线 | 第几站、绿/红/running | `runs/<thread>/stages/*.json` | **实时台必须** |
| **L1** | 派工 | 哪站→哪个 or-* | lead log `toolCall`/`toolName`=subagent | **实时台必须** |
| **L2** | Sub 轨迹 | 工具序、读写、消息 | `.pi-subagents/**` transcript；lead 内 child 事件 | **实时台必须**（有 run 则有） |
| **L3** | 思考文本 | thinking/reasoning | json 事件；无则 `thinking_unavailable` | **必须处理**（有或诚实无） |
| **L4** | 数字/门禁 | objective、R1/R2 | solution/validate/claim | **台面可点到路径** |

**「看见 sub 思考」合法含义：**

1. **主：** L2 工作轨迹（工具+消息）——工程上的「思考过程」  
2. **加：** L3 模型思维链（若供应商/Pi 暴露）  
3. **禁：** 父 lead 散文冒充 sub 内心戏  

---

## 2. 数据源（实现必须认）

### 2.1 L0

- `runs/<thread_id>/stages/NNNN_*.json`  
- 字段至少用：`node` `stage` `utc` `last_error` `human_required` `gate_*` `paths`  
- 无 stages → 实时台显示 **无产品 run**（裸 pi 不得装成全链）

### 2.2 L1

- `outputs/.agents/<slug>/*-lead-*.log`（`--mode json` 流）  
- `*-harness.json` / `*-subagent.json`  
- 只认真实 tool 事件（同 `detect_subagent_calls` 纪律）

### 2.3 L2 / L3

- transcript：`.pi-subagents/**`  
- lead 流内 assistant / tool_result / thinking 类事件  
- 大文件：流式/索引；UI 截断 + 「打开原 log」

### 2.4 刷新

| 模式 | 要求 |
|------|------|
| **准实时（底线最低）** | 轮询 ≤ **3 秒** 或 mtime 变更即重载 JSON API |
| 真推送 | 可选 SSE/websocket，非必须 |
| 手动 F5 only | **不达标** |

---

## 3. 用户「在哪里看到」（合同写死）

### 3.1 唯一产品答案（实现后必须成立）

```text
命令:  orpath.bat watch --slug <slug> [--thread-id <id>]
  或:  menu →「实时过程台 / Live Watch」

浏览器: http://127.0.0.1:<port>/   （本机，默认打开）

页面至少三栏或等价：
  [阶段条 L0]  [当前站/事件流 L1·L2·L3]  [产物与门禁 L4]
```

| 属性 | 要求 |
|------|------|
| 谁开 | 用户本机；**不依赖 Hermes** |
| 何时开 | **run 进行中**即可开；run 前开则 idle 态 |
| 是否实时 | **是**（§2.4） |
| 是否替代 folder | **是产品脸**；folder 仅 debug 附属 |

### 3.2 附属（可有，不可单独当底线）

- `outputs/<slug>-timeline.md` 事后导出  
- menu「打开 agents/runs」  
- 终端打印 stage 名  

### 3.3 明确「不在哪里」

| 不在 | |
|------|--|
| GitHub 网页 | |
| Hermes 聊天自动动画 | |
| 已删除的 OpenPi（除非未来薄 GUI 再包 watch） | |
| 只存在于 specs 的一句「以后做」 | |

---

## 4. UX 规格（底线台）

### 4.1 总览条

- slug / thread / live_subagent on-off / human_required  
- 当前 `node` + 状态：`running | ok | fail | blocked`  
- 最后错误一行  

### 4.2 阶段条 L0

- 按 stage 序号列表  
- 点击 → 中栏详情  
- running 高亮  

### 4.3 Sub 树 L1+L2

- 树：`research → or-researcher (runId)`  
- 点击 sub → 事件流时间序：  
  `tool` / `tool_result` / `assistant` / `thinking`  
- thinking 默认折叠  
- 无 transcript：标红 `transcript_missing`（若声称 MA）  

### 4.4 思考 L3

```text
if events.thinking: 展示全文或分页
else: 固定文案
  「thinking_unavailable — 模型/Pi 未返回思维链；以下为工具与回复轨迹（L2）」
```

### 4.5 安全

- 只读本机  
- 不执行 log 内代码  
- 密钥脱敏  

---

## 5. 架构（specs 层约束实现）

```text
LG/Pi 写盘
    → GET /api/snapshot?slug=&thread=   （聚合器，无 LLM）
    → Watch HTML（轮询 snapshot）
    → 可选导出 timeline.md
```

| 模块（目标名） | 职责 |
|----------------|------|
| `orpath/timeline.py` 或 `orpath/watch_api.py` | 聚合 L0–L4 |
| `scripts/orpath_watch.py` | HTTP + 静态页 |
| `orpath.bat watch` | 启动并打开浏览器 |
| menu 项 | 与 bat 同入口 |

**禁止：** 聚合器用 LLM 生成「协作故事」当 snapshot 主数据。

---

## 6. DoD 清单（V0 底线 / 体验 PASS 前置）

### 6.1 硬勾选

- [ ] `orpath.bat watch --slug …` 有文档且可跑  
- [ ] 浏览器本机页自动刷新 ≤3s  
- [ ] 进行中 run 能看到阶段变化（L0）  
- [ ] live MA run 能看到 sub 节点（L1）与事件（L2）  
- [ ] L3 有或诚实无  
- [ ] README/ORPATH **写明：实时过程台在 watch**  
- [ ] 无 V0 不得宣称「可视化多 Agent 产品完成」  

### 6.2 负例

- [ ] cosplay（无 toolCall）→ 台面 **不**显示假 sub  
- [ ] LIVE=0 → 标明无 live sub  
- [ ] 裸 pi → 标明非产品全链  

### 6.3 与工程门禁

- `subagent_gate` 绿 **不替代** V0  
- V0 可有独立 smoke：`watch` 对 fixture 历史 slug `test` 能渲染非空 L0  

---

## 7. 话术法

| 可说 | 不可说 |
|------|--------|
| 本机 watch 实时台看阶段与 sub 轨迹 | 已有实时可视（仅 folder/log 时） |
| 思维链视模型是否返回 | 保证完整 CoT |
| 静态 timeline 为导出 | 导出 = 已满足实时底线 |

---

## 8. 非目标（仍非底线范围）

- 像素级商业 APM  
- 云端多人同屏  
- 在 watch 里改 objective 重跑  
- 恢复 OpenPi 当唯一壳（薄 GUI 可后包 watch）  

---

## 9. 选型冻结：**S1**（用户 2026-08-03）

### 9.1 S1 定义

```text
Tier-1 脸（V0 必须）：OR-Path Watch
  orpath.bat watch → 本机页
  数据：runs/stages + outputs/.agents lead log + solution 路径
  （可选）.pi-subagents transcript

Tier-2 深看 sub（增强）：
  pi-kanban / Pi FleetView
  前提：产品 LIVE 可写 Pi session（ORPATH_PI_SESSION=1 时不传 --no-session）
  CI/gate 仍默认 --no-session

Tier-3 研发/作品集（可选后置）：
  Langfuse Agent Graph（LG span + 自定义 stage span）
  不替代 Tier-1 脸
```

### 9.2 禁止

| 禁止 | |
|------|--|
| 仅 Tier-2/3 宣称 V0 PASS | |
| LangSmith 作唯一主脸（闭源+Pi 黑洞） | |
| LLM 编造协作故事当 snapshot | |

### 9.3 实现模块（S1 · 现状）

| 路径 | 职责 | 状态（2026-08） |
|------|------|----------------|
| `orpath/watch_snapshot.py` | 聚合 L0–L4 JSON | **已有**（V0 工程） |
| `scripts/orpath_watch.py` | HTTP + 轮询 | **已有** |
| `orpath/web/watch.html` | 三栏 UI | **已有** |
| `orpath.bat watch` / menu 6 | 入口 | **已有** |
| `scripts/v0_watch_gate.py` | V0 门禁 | **已有** |
| `ORPATH_PI_SESSION` | 写 session 供 kanban | **未/未普及** |
| pi-kanban / Langfuse | Tier-2/3 | **P4 session 桥 + P5 文档/开关**；kanban 安装与 LF span **可选未强制** |

**诚实：** `docs/m0-closeout.md` 记 V0 **工程** PASS；用户体感仍「不理想」→ 见 **§11 五阶段完工**（目标 = **真·实时可视体验**，不是再勾一次 gate）。

---

## 11. 五阶段完工计划（实时可视 · 用户要的效果）

> **前提：** 不是从零；是在现有 Watch 上补「真实时 + 真 sub 过程 + 真联跑」。  
> **原则：** 每阶段有 **可感知验收** + **门禁/手测**；未过阶段 N 不宣称阶段 N+1 完成。  
> **选型：** 仍 S1（§9）。

### 11.0 为什么现在觉得不理想（诊断 · 写法条）

| # | 现状 | 体感问题 |
|---|------|----------|
| 1 | 2s **全量**拉 snapshot；lead 只 **tail 256KB** | 长 run 像「偶尔刷一下列表」，不像思考在流 |
| 2 | `MAX_EVENTS=200` 截断 | 中后段过程丢了 |
| 3 | 无 **byte cursor / 增量** | 大 log 又慢又不全 |
| 4 | 无 SSE；纯轮询 | 「准实时」下限，不像 live |
| 5 | 演示常 **LIVE OFF**；D3 认 **历史** `test` log | 看不到「这一次」sub 在长 |
| 6 | 默认 **`--no-session`** | Tier-2 kanban/Fleet 接不上 |
| 7 | transcript / thinking 弱 | 「思考过程」名不副实 |
| 8 | UI 偏运维三栏 | 缺泳道/跟随最新/高亮 running |
| 9 | watch 与 run **两终端手拧** | 不像产品一键开演 |

工程 gate 绿 **不否定** 上述体感缺口。

---

### 阶段 P1 — 真增量实时脊梁（数据面）✅ **DONE 工程**

**目标：** run 进行中，事件与阶段 **连续变长**，不靠「整文件重读幻觉」。

| 做 | 状态 |
|----|------|
| `compute_source_fingerprint` + `poll.fingerprint` | ✅ |
| lead 更大全量/ tail；`log_cursors`；`events_truncated` | ✅ |
| `GET /api/poll` dirty；snapshot `prev_fp`/`events_added` | ✅ |
| 前端 1s 先 poll 再 snap；footer fp/stages/+N | ✅ |
| 可选 `GET /api/stream` SSE | ✅ |
| 门禁 growing log + HTTP poll | ✅ `watch_snapshot_gate` / `v0_watch_gate` |

**PASS 话术：** 「阶段条真跟着跑（dirty 脊梁）」——sub 细看仍归 P2。

---

### 阶段 P2 — Sub 过程可读（L1/L2/L3 内容面）✅ **DONE 工程**

**目标：** 点进 dispatch 能看到 **工具序 + 消息片 + thinking 有/诚实无**，像在看 sub 干活。

| 做 | 状态 |
|----|------|
| 更多 lead json type（toolCall / content tool blocks / thinking） | ✅ |
| 挂 `.pi-subagents` meta+transcript；`children[]`；缺失标 `transcript_missing` | ✅ |
| UI：children 树、lead/sub 过滤、thinking 折叠、auto-scroll | ✅ |
| cosplay 仍不假成功 | ✅ |
| 门禁 `test_p2_sub_process_readable` | ✅ |

**PASS 话术：** 「能展开看 sub 轨迹（lead+transcript）」——一键联跑仍归 P3。

---

### 阶段 P3 — 一键联跑（产品面 · 当场实时）✅ **DONE 工程**

**目标：** **一次命令/菜单** 打开 watch + 启动演示 run，浏览器里 **当场** 看阶段变。

| 做 | 状态 |
|----|------|
| `orpath.bat watch-run` / menu 7 | ✅ |
| mock 默认；`--live` 可选；`--keep-watch` | ✅ |
| 证据 `outputs/<slug>-watch-run.json`（本 slug stages_grew） | ✅ |
| `p3_watch_run_gate` / `orpath.bat p3-gate` | ✅ |
| `docs/v0-smoke.md` 主路径改 P3 | ✅ |

**PASS 话术：** 「这就是实时可视化主路径（watch-run）」——Tier-2 kanban 仍归 P4。

---

### 阶段 P4 — Tier-2 深看（Pi session / kanban·Fleet）✅ **DONE 工程**

**目标：** 需要「Pi 官方级 sub 细看」时有第二屏，并从 Watch **露出路径/开关**。

| 做 | 状态 |
|----|------|
| `ORPATH_PI_SESSION=1` → lead 不加 `--no-session`；默认/0 仍 ephemeral | ✅ |
| lead 头写 `pi_session` / `sessions_root` | ✅ |
| Watch `tier2` + UI 面板；honesty `tier2_session_off` | ✅ |
| `docs/p4-tier2-deep-look.md`；`p4-gate` | ✅ |
| 强制装 kanban / 必烧 LIVE | 不做 |

**PASS 话术：** 「细看 sub 用 Tier-2（session+kanban）；脸仍是 Watch」。

---

### 阶段 P5 — 体验抛光 + 可选 Tier-3（收口）✅ **DONE 工程**

**目标：** 观感达到「愿意给人演示」；可选 Langfuse 作作品集第二图（**文档/开关**）。

| 做 | 状态 |
|----|------|
| UI：timeline/swim、running 脉冲、错误红条、Follow tail、Pause、移动端可滚 | ✅ |
| 性能：事件窗口渲染 + 服务端 cap | ✅ |
| 可选 Langfuse：`tier3` + `docs/p5-tier3-langfuse.md`（**未**默认全站 span） | ✅ 表面 |
| claim ladder + `docs/p5-closeout.md` | ✅ |
| `p5-gate` | ✅ |

**PASS 话术：** 「实时可视 S1 主路径完工（P1–P3）；P4/P5 增强已交付；Langfuse 全自动埋点未做」。

---

### 11.1 五阶段总表

| 阶段 | 一句话 | 你应该感到 |
|------|--------|------------|
| **P1** | 增量实时脊梁 | 条在长、在跟跑 |
| **P2** | sub 轨迹可读 | 点得开、看得见工具/话 |
| **P3** | 一键边跑边看 | 不用两终端猜 |
| **P4** | Pi 深看桥 | 要细看有第二屏 |
| **P5** | 抛光 + 可选 Langfuse | 敢录屏给人 |

| 依赖 | |
|------|--|
| P2 可部分并行 P1 | 但 P3 依赖 P1（建议 P1 先） |
| P4 依赖 LIVE session 策略 | 不阻塞 P3 mock 联跑 |
| P5 最后 | |

### 11.2 与旧 V0/M0 关系

| 旧状态 | 新解释 |
|--------|--------|
| V0 工程 gate PASS | = **P0 基线已存在**（入口+三栏+聚合） |
| 用户「不理想」 | = **P1–P3 未完成** |
| M0 core closeout | 数字链独立；**不替代** P3 实时体验 |
| 未完成 P3 前 | **不得**对外说「实时可视化已满意交付」 |

### 11.3 建议开工顺序（仍可只改 specs 后等你下令写码）

```text
P1 → P2 → P3  （主路径，必须）
P4 → P5       （增强）
```

---

## 10. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-08-01 | 初版（偏 M0 静态 + M1 HTML） |
| 2026-08-03 | **用户底线升格：** 实时可视 = 硬法；明确在哪看（watch） |
| 2026-08-03b | **选型 S1 冻结**；模块表 |
| 2026-08-03c | 注明实现曾未开工（历史） |
| 2026-08-0x | 现状：Watch 工程已落地；**§11 五阶段完工**（针对「做过但不理想」） |
