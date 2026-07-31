# OR-Path Multi-Agent / Graph-OR Agent（个人独立项目）

## STAR（对外叙事底稿）

**技术栈（现行锁定）：** Pi Agent（`@earendil-works/pi-coding-agent`）· `pi-subagents` · LangGraph · MinerU Cloud · LightRAG + BM25 · Cognee Cloud · OR-Tools · NetworkX ·  Docker Compose（可选薄 K8s solver worker）· DeepSeek only

【Situation】经典运筹学（OR）计算工具门槛高且交互复杂，而通用大语言模型直接进行路径计算与数学建模时存在严重的数值计算幻觉，难以解决非结构化业务需求到确定性最优解的闭环。

【Task】基于开源组件整合的理念，独立构建一套面向最优路径（最短路、TSP、VRP 等）的专用多智能体运筹推理系统。

【Action】
- 多智能体：Pi harness + 真子 Agent 隔离（Researcher / Modeler）；LangGraph 管阶段流水线与可恢复状态
- 图检索：MinerU 预处理 → LightRAG + 关键词腿融合；Cognee 作长期记忆；领域种子图（问题类–约束–求解器–案例）
- 确定性求解：OR-Tools / NetworkX 为数字唯一真相；LLM 禁止心算最优解
- 工程交付：Compose 一键；可选薄 K8s solver worker；桌面壳已移除；主控 orpath.bat menu

【Result】打通「自然语言 → 语义研究 → 数学建模 → 确定性求解 → 验证与解释」闭环；作品集卖点是可验证的多 Agent OR，而非 Agent 平台发行。

---

## 协作拓扑决策（锁定 2026-07-29）

> 用户对照五种熟知模式（生成–验证 / 编排者+子 Agent / Agent Teams / 消息总线 / 共享状态）选型。  
> **拒绝「三种模式并列都是主模式」的理想化堆叠**——必须有控制面赢家与明确非目标。

### 一句话

**带验证关卡的 Supervisor–Worker 流水线**  
（hierarchical pipeline with tool verifiers）

### 控制面规则（最重要）

| 层 | 老板 | 职责 |
|----|------|------|
| **全局流程** | **LangGraph 阶段机 + checkpointer** | now→next、重试、可恢复 run |
| **局部 LLM 隔离** | **Pi + `pi-subagents` Supervisor** | 仅 research / model 等需要隔离的节点 |
| **阶段关卡** | **生成–验证（验证器优先非 LLM）** | schema / solver / 约束检查 |
| **状态** | **窄共享 structured run state** | schema、solution、metrics、errors；字段有 owner |
| **非目标** | Agent Teams、消息总线作脊柱 | 对等互聊 / Agent 社交 pub-sub |

**禁止双方向盘：** Pi 负责节点内子会话并返回结果；**阶段跳转只听 LangGraph**。

### 目标阶段图

```text
LangGraph（老板：阶段 + 重试 + checkpoint）
│
├─ [optional] research_node
│     └─ Pi Supervisor → Researcher 子会话（可检轨迹）
│
├─ model_node
│     └─ Pi Supervisor → Modeler 子会话（结构化 schema，禁止最优值）
│     └─ GATE: schema validate
│
├─ solve_node
│     └─ OR-Tools / NetworkX 工具（不是 Agent）
│     └─ GATE: feasible + constraint check
│
└─ explain_node
      └─ 只读 solution JSON 生成解释（禁止编造数字）
```

### 五种模式投票

| 模式 | 投票 | 在本项目中的用法 |
|------|------|------------------|
| **生成–验证** | **P0** | 阶段边界 gate；验证器 = 代码/求解器优先；LLM-vs-LLM 仅可选辅助 |
| **编排者 + 子 Agent** | **P0 局部** | Researcher/Modeler 真隔离（`pi-subagents@0.37.2` 已装） |
| **共享状态** | **P0 窄** | LG run state + artifacts；**不是**多 Agent 自由聊天黑板 |
| **Agent Teams** | **P3 / 主路径 OUT** | 角色不对等 + 成本高；不对等 OR 角色不宜对等互聊 |
| **消息总线** | **P3 / 主路径 OUT** | 以后 solver worker 可用任务队列；N≈3 时不做 Agent 总线 |

### 必须防的失败模式

1. **双编排打架** — Pi 还在聊，LG 要跳阶段 → LG 定阶段  
2. **Supervisor 反模式** — 子任务互相依赖还硬并行 → 改顺序 pipeline 共享切片  
3. **过委派空转** — 子 Agent 半成品反复重派 → 迭代上限，优先 synthesize  
4. **流水线中毒** — 前段幻觉后段精装错答案 → 每段 gate + max retries  
5. **LLM 最优解** — 无 solver tool result 禁止给目标值/路径长度  
6. **宽共享状态** — 仅 solve 工具可写 `objective_value`；子 Agent 只读必要切片  

### 与领域/产业对齐（选型依据摘要）

- OR×LLM 系统（如 OR-LLM-Agent, arXiv:2503.10009）主旋律是 **建模 → 求解/代码 → 沙箱修复/不可行回修**，不是 peer team 开会；报告准确率约 85% 仍有残差 → **必须有评测，模式不包治**  
- 产业 2026：Supervisor 是生产默认；Pipeline 最易被误用成无意义全串行；Debate ~2.5× 成本；Swarm/总线在几十上百并行才值，3–10 Agent 用 supervisor 更简单  

### 角色与工具边界（未改）

| 角色 | 做 | 不做 |
|------|----|------|
| Orchestrator / LG 阶段 | 拆合、调 solve/validate | 心算最优 |
| Researcher | 算法/约束/案例/检索 | 写最终数字 |
| Modeler | 问题类 + solver schema JSON | 填 optimal value |
| Solver 工具 | OR-Tools / NetworkX | — |
| Validate 工具 | 可行性/约束/与金标 gap | — |

### 实现时检查清单

- [x] T1 骨架：`.pi/agents/or-*` + fixtures + solve/gates + LG `orpath/run_t1.py` + `scripts/t1_gate.py`  
- [x] T1 **真多 Agent**：Pi CLI researcher/modeler/writer/verifier + `.pi-subagents` transcripts（本地；见 `docs/t1-evidence.md`）  
- [x] T1 三天加厚：负例 `t1_negatives`、docs、README、git 基线（`docs/t1-day2-day3.md`）  
- [x] **T1 CLOSED** — `docs/t1-closeout.md`  
- [x] T2：**CLOSED/PASS** — gates + hard multi-agent isolation + relocatable orpath.bat/ORPATH_HOME（docs/t2-closeout.md）
- [x] LG 为阶段老板（T1 deterministic nodes；live 子 Agent 在 Pi）  
- [x] run state 字段在 `orpath/state.py`  
- [x] README/架构：**不以** Teams/Bus/Feynman 为主壳  
- [x] 简历一句话用「带验证关卡的 Supervisor–Worker 流水线」

---

## 记忆分层（产品 = Pi，不是 Hermes）

| 层 | 归属 | 用途 |
|----|------|------|
| 工作记忆 | 磁盘制品 `outputs/` `notes/` `papers/` + plan 账本 | 过程真相（对齐 Feynman L0） |
| Run 状态 | LangGraph checkpointer | 阶段/重试/字段 owner |
| 偏好/教训 | 可选 `@samfp/pi-memory`（项目 `.pi/memory`） | 习惯与纠错；**禁止**存 objective |
| 知识库 | LightRAG+BM25 / 后置 Cognee | 文献算法；非 T1 |
| **非产品** | Hermes `MEMORY.md` | 仅导航 Agent 笔记，**不是** OR-Path 运行时记忆 |
| **非 T1** | Hindsight | 与 Cognee 重叠；默认不上 |

T1 计划：`.hermes/plans/2026-07-29_093802-t1-pi-multiagent.md`  
**壳决策（2026-07-29）：** 主开发 = 本仓 + Pi + LG（OpenPi 已删）。**不以 Feynman 为主开发**；`vendor/feynman` 仅参考/可后置论文侧车。

## 工作区

- 根目录：`C:\Users\Lanzao\Desktop\agent\`  
- 含：`runtime/`、`pi-main/`、`.venv-314/`、`pi.bat`、`vendor/`（Feynman 等只读镜像）  
- **禁止**在 `inquisitive-master` 写本项目业务代码  
- 权威技能：`or-path-multi-agent`（含 `references/collaboration-patterns.md`）
