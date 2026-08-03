# Product Flow SDD — 总项目流程主合同

> **地位：** specs 内流程/DoD/非目标 **最高分册**（仅次于门禁真实输出）。  
> **配套：** `process-visibility.md`（**实时过程台 = 产品硬底线**，与数字同级）。  
> **全册重写对齐日：** 2026-08-01；**底线升格：** 2026-08-03（实时可视不可再延期话术）。

---

## 0. 文档使命

本文件回答：

1. 系统 **应该怎么跑**（心智模型）  
2. **谁翻页、谁招工、谁算数、打回在哪**  
3. **底线交付顺序：V0 实时可视 + M0 可信数字**（无 V0 不得宣称体验完成）  
4. 旧里程碑（T1–1.2）与「愿景完成」如何切割  

分册写字段与命令细节；**本文件写总图与优先级**。

**用户锁定底线：** 实时可视化协作全过程与 sub 思考过程是 **必须**，不是表面功夫、不是「门禁先绿脸以后再说」。

---

## 1. 产品定义

### 1.1 名称

**OR-Path Multi-Agent / Graph-OR Agent**

### 1.2 一句话

自然语言/题面运筹问题 →（可选 OCR 审读）→ 研究与建模 → **确定性求解 + validate** → 论文有界打回；真 subagent；人在 **本机实时过程台（watch）** 看见站序、派工与 sub 过程。

### 1.3 三大用户价值（愿景锚 · 同级，不可砍 V1）

| ID | 价值 | 合同落点 | 硬度 |
|----|------|----------|------|
| **V1** | **实时看见**协作与 sub 思考/轨迹 | **`process-visibility.md` 全文**；入口 `orpath.bat watch` | **硬底线** |
| V2 | **能做题**出可信数字 | §3 + solve/validate | 硬底线 |
| V3 | 像系统而非纯脚本脸 | §2；**脸=watch 台**，脚本是手 | 硬（依赖 V1） |

### 1.4 工作区

- 默认根：`C:\Users\Lanzao\Desktop\agent` 或 `ORPATH_HOME`  
- 禁止在 inquisitive 等其它仓写本产品业务代码  

---

## 2. 控制面隐喻（成熟版 · 必须背）

```text
LG  = 总进度表（唯一：第几站、过不过、打回哪、停不停）
Pi  = 本站包工头（只在被请到的站内；规定 sub）
sub = 班组（真隔离；交文件路径）
脚本 = 计算器 + 质检章（OCR / schema / solve / validate / R1 / R2）
```

**背诵句：**  
**LG 翻页；Pi 只在某一页招人；打回是 LG 往回翻（有上限）；算分页永远手算。**

### 2.1 禁止脑图

| 禁止 | 后果 |
|------|------|
| Pi 与 LG 平级「交棒」 | 双老板、无法 resume 语义 |
| Pi 无限自由开窗当全局编排 | 无法质检、假 MA |
| LLM 写 objective | 作品集破产 |
| 多入口都叫正式产品 | 假竣工 |
| 用 lead 旁白冒充 sub 思考 | 见 process-visibility |

### 2.2 「LG 适合多智能体」在本法中的含义

- **是：** 适合编排多阶段协作 **流程**（图、状态、重试、resume）  
- **否：** 必须用 LG 节点扮演所有 Agent；否取消 Pi  
- **本产品形态：** **模式 B** = LG 进度 + Pi 站内真 sub  

**分工不交换**（除非未来单独立项改产品形态）。

### 2.3 站内时序

```text
LG → 站 S
  脚本站：工具 → 写盘 → gate 字段
  认知站：短 lead（无 write）→ 规定 sub → 路径回写 → lead 结束
  → LG：下一站 | 回边 | HUMAN
```

---

## 3. 主流程总图

```text
START
  [opt] intake_ocr → intake_parse → (human_confirm?)
  → orchestrate
  → retrieve
  → bridge_pi          # 可选 skip
  → research           # Pi → or-researcher
  → model              # Pi → or-modeler → schema（禁 optima）
  → gate_schema        # 脚本；红→model≤2→HUMAN
  → solve              # 脚本 only
  → gate_validate      # 脚本；红→tune≤3→model≤2→HUMAN
  → explain
  → draft_paper        # lead/writer
  → cite_pack          # live: or-verifier + R1/claim
  → review_pack        # live: or-reviewer + R2
  → revise_or_done     # 红→draft≤2；绿→provenance→END
```

### 3.1 站类型

| 站 | 类型 | sub | 硬门 |
|----|------|-----|------|
| intake_* | 脚本± | 可选 | 禁键、覆盖子问 |
| orchestrate/retrieve/bridge | 脚本± | 可选 | 路径 |
| research | 认知 | **规定** researcher | 知识相关 gate |
| model | 认知 | **规定** modeler | schema |
| gate_schema | 脚本 | 否 | schema |
| solve | 脚本 | **否** | envelope |
| gate_validate | 脚本 | 否 | validate |
| explain | 混合 | 可选 | — |
| draft_paper | 认知 | lead/writer | — |
| cite_pack | 认知+脚本 | **规定** verifier | R1/claim |
| review_pack | 认知+脚本 | **规定** reviewer | R2 |
| revise/provenance | LG/脚本 | 否 | 计数器 |

节点数以代码 `graph_product` / `t3-lg-skeleton` 为准（含 intake 时约 17）。

---

## 4. 打回（两类 LG 回边）

### 4.1 求解侧

| 序 | 动作 | max |
|----|------|-----|
| 1 | 同 schema 调参再解（允许的 mode） | `solver_tune`≤3 |
| 2 | 回 model | `validate_repair`≤2 / `schema_repair`≤2 |
| 3 | HUMAN + provenance | — |

Mock：调参可短路。  
无域 adapter + intake：**BLOCKED** 诚实，禁止假绑 SP 金标。

### 4.2 论文侧

| 序 | 动作 | max |
|----|------|-----|
| 1 | 回 draft（再 cite/review） | `revise_count`≤2 |
| 2 | HUMAN 或 provenance BLOCKED | — |

**禁止** writer 改 solution 数字充绿。

### 4.3 所有者

计数器与翻页 = **LG state**；触发 = **gate 结果**；Pi 只在被再调度时改稿/改模。

---

## 5. 数字真相（摘要）

- objective/path/tour/routes：**仅 solve_dispatch 适配器**  
- 必 validate 重算  
- schema 禁解答键  
- 精确轨 vs Routing 诚实 → `solvers-and-validate.md`  

---

## 6. 多智能体（摘要）

真 MA 四条：可检轨迹、隔离、toolCall 委派、数字仍工具。  
Import：`orpath.subagent_dispatch`。  
Harness：无 write、json mode、quarantine cosplay。  
产品 LIVE 默认 ON；gate 强制 OFF。  
裸 pi ≠ MA。  
细节 → `multi-agent.md`。

---

## 7. Intake（摘要）

可选前门；无源 skip。  
OCR 序：pdf_text → ppocr → api → rapidocr。  
禁 objective。  
全文 → `problem-intake.md`。

---

## 8. 过程可见（摘要 · 硬底线）

权威全文 → **`process-visibility.md`**（勿只读本节）。

| 层 | 内容 | 底线 |
|----|------|------|
| L0 | stages 进度 | 实时台必须 |
| L1 | lead toolCall sub 树 | 实时台必须 |
| L2 | sub 工具序/消息 | 实时台必须 |
| L3 | thinking；无则 `thinking_unavailable` | 必须处理 |
| L4 | solution/gates 路径 | 台面可点 |

**用户在哪看（合同）：**

```text
orpath.bat watch --slug <slug>
menu →「实时过程台 / Live Watch」
浏览器 http://127.0.0.1:<port>/  自动刷新 ≤3s
```

| 不算底线 | |
|----------|--|
| 只开 `runs/` `.agents/` 文件夹 | |
| 只有事后 `timeline.md` | |
| 只有 gate 绿 | |
| 「以后做 HTML」 | |

**V0** = 实时 watch 台达标；**无 V0 不得宣称 M0 体验 PASS**。

---

## 9. Demo：V0 + M0（当前最高产品优先级）

### 9.0 V0 — Live Watch 底线（先于/并入体验 PASS）

见 `process-visibility.md` §0、§6、**§9（选型 S1 冻结）**。摘要：

| ID | 要求 |
|----|------|
| V0-1 | `orpath.bat watch`（或 menu 等价）可启动本机页 |
| V0-2 | run **进行中**可打开；≤3s 刷新 |
| V0-3 | 可见 L0 阶段 + L1 派工 + L2 事件；L3 有或诚实无 |
| V0-4 | README/ORPATH 写明：**实时过程看 watch** |
| V0-S1 | **选型 S1**：Watch 主脸；可选 pi-kanban（需 session）；Langfuse 后置可选；**不得**仅 Tier-2/3 宣称 V0 |

**S1 未实现前：** 不得宣称可视化体验完成（选型 ≠ PASS）。  
**补充（现状）：** Watch **P1–P5 工程收口**（见 `docs/p5-closeout.md`）；主路径 `watch-run`；Langfuse **仅可选表面/文档**，不替脸。

### 9.1 M0 名称

**OR-Path M0 — 实时过程台 + 可信数字 + 真 sub 证据**

### 9.2 硬 DoD（含 V0）

| ID | 要求 |
|----|------|
| D0 | **V0 全绿**（实时台） |
| D1 | 单一做题入口文档化（menu / demo-m0） |
| D2 | `solution.json` + validate 绿（mock 或 networkx SP） |
| D3 | 至少一站真 `subagent` toolCall 证据 |
| D4 | 附属导出 `outputs/<slug>-timeline.md` 可选；**不能替代 D0** |
| D5 | 打回可讲（实演或台面标计数器） |
| D6 | 对外只承诺 V0+M0；T1–1.2 标历史资产 |
| D7 | 无密钥/竞赛 PDF 进 git |

### 9.3 M0 不做

全域竞赛交卷、任意目录完美、记忆大脑、MCP 市场、Feynman 全量 launch。  
**不做 ≠ 不做实时台。实时台在 V0，必须做。**

### 9.4 验收命令（实现后钉死）

```bat
orpath.bat doctor
orpath.bat watch --slug test
:: 另开：demo 或 run；确认浏览器阶段/sub 在变
orpath.bat demo-m0 --slug m0 --fresh
:: 查 solution + agents grep name:subagent
```

---

## 10. 入口

| 入口 | 角色 |
|------|------|
| menu / START-ORPATH | **主** |
| **watch** | **实时过程台（底线脸）** |
| run / run-full | 全链 |
| intake | 仅读题 |
| timeline | 事后导出（附属） |
| pi | TUI ≠ 自动全链 MA |
| openpi | REMOVED exit 2 |
| gate* | LIVE=0 |

---

## 11. 记忆 / 知识 / MCP 分期

| | M0 | 后 |
|--|----|----|
| L0 磁盘 / L1 checkpointer | **必须** | 必须 |
| Skill / agent 手册（程序记忆） | 不挡；角色 md 可用 | **主加强轴**（战法沉淀） |
| pi-memory（prefs） | 不挡 | 轻量可选 |
| Cognee Cloud | 不挡；**smoke only** | **保持旁路**，不升主记忆 |
| 语料检索 / 种子图 | seed 或 off 即可 | hybrid 按需 |
| MCP | **不做** | 先 1 个再扩 |

**选型口令：** Skill（战法）> L0/L1 > 种子图/检索 > prefs ≫ Cognee。  
记忆/Skill/图 **永非** objective 权威。→ `memory.md` `knowledge-and-retrieval.md`

---

## 12. 模块权威 import

| | |
|--|--|
| control_plane | 建图/invoke |
| nodes | 阶段 |
| solve_dispatch | 求解 |
| subagent_dispatch | MA |
| paper_protocol | 论文 |
| timeline（待建） | 可视聚合 |
| pi_launch_law | 启动合法性 |

---

## 13. 落实 vs 缺口

| 项 | 约 | 注 |
|----|----|-----|
| LG 图+resume | 高 | |
| harness 真 sub | 高 | |
| 数字法 | 高 | |
| 回修机制 | 中高 | |
| **实时 watch 台 V0** | **无/极低** | **当前底线缺口 #1** |
| 单一入口叙事 | 中 | |
| 域桥 polyomino | 低 | 后 |
| Feynman launch 注入 | 低 | 后 |
| 记忆/MCP | 低 | 后置 |

---

## 14. 里程碑

| | 目标 |
|--|------|
| **V0** | **Live Watch 底线**（process-visibility §0）— **体验 PASS 前置** |
| **M0** | V0 + 可信数字 + 真 sub 证据（§9） |
| **M1** | watch UX 加厚 / workdir |
| **M2** | 第一域桥 |
| **M3** | SYSTEM 真注入 launch |
| **M4** | 记忆叙事 / 1 MCP |
| T1–1.2 | 回归 only |

---

## 15. Claim ladder

可：流水线、真 sub 可检、validate、**watch 实时台**（实现后）。  
不可：保证全局最优、裸 pi=MA、gate=demo、**仅 folder/log 却说已实时可视**、已交 B 题、未做记忆/MCP 当已做。

---

## 16. 开发秩序

```text
V0 实时台（底线）→ 与 M0 数字证据可并行
  → 白名单实现 → 真命令验收
  → 无 V0 不宣称体验 PASS
  → 再 Mn（域桥/记忆…）
```

---

## 17. 分册指针

见 `README.md` 文件地图。  
**可视底线细节：只认 `process-visibility.md`。**

---

## 18. 变更记录

| 日期 | |
|------|--|
| 2026-08-01 | 主合同；对齐 process-visibility；M0 冻结意图 |
| 2026-08-01b | 全册重写波次 |
| 2026-08-03 | **用户底线：** 实时可视升格 V0；废「脸以后再说」；watch 为合同入口 |
| 2026-08-03c | **选型 S1 冻结**；其后 Watch 工程曾落地 |
| 2026-08-0x | 实时可视 **五阶段完工** 见 process-visibility §11（P1–P5） |
