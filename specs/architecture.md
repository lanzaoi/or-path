# Architecture — 架构法（现行权威规范）

**对齐：** `AGENTS.md` · `specs/product-flow-sdd.md` · `docs/ARCHITECTURE.md`  
**状态：** LAW 2026-11（精简 4 智能体 + 10 领域装备包 + 27 工业求解器架构全量上线）

---

## 1. 架构核心宣言与口令

> **确定性 Python 管全局流程与硬验算，4 大常驻智能体负责分析/建模/撰写/评审，27 台求解器充当物理计算引擎，门禁章锁死数字真理，Web Studio 呈现全透明实时过程。**

- **系统定位**：工业级运筹优化（Operations Research）自动化求解与学术论文生成平台。
- **运行基石**：全纯 Python（LangGraph + FastAPI/Uvicorn），彻底剥离历史 Node.js `pi` CLI 外部包装层，直连 `.env` 原生 LLM API（科大讯飞星火 `spark-x2.6`、DeepSeek `deepseek-chat` / `deepseek-reasoner` 等）。

---

## 2. 系统五大支柱（5 Pillars）

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       1. Unified Launcher & Web Studio                      │
│        START.bat / START.sh · orpath/web/ · Problem Workbench · Live Watch   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                  4. Lean 4-Agent + 10 Domain Cartridge                      │
│                                                                             │
│   [ or_analyst ] ──(0-Token Gate)──► [ or_modeler ] ──(0-Token Gate)──┐     │
│          ▲                                   ▲                        │     │
│          └──────────(10 Domain Cartridges)───┴────────────────────────┤     │
│                       (tube, routing, scheduling, etc.)               │     │
│                                                                       ▼     │
│   [ or_reviewer ] ◄──(0-Token Gate)── [ or_writer ] ◄── 2. Solvers & 3. Val │
│                                                          (27 Solvers + DIMO)│
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                    5. Core Gates & High-Signal Verification                 │
│      tools/test_*.py · universal_redteam_gate.py · problem_workbench_gate   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pillar 1: 统一启动器与 Web Studio（`START.bat`, `START.sh`, `orpath/web/`）
- 一键唤起前端双向工作舱：支持文件夹/文件拖拽题目摄入、深层结构化数据剖析（`studio_analyzer.py`）、人机交互确认（参数覆盖与模式切换）、后台自适应求解与全要素 Live Watch 看板。
- 零外部 npm/node 依赖，本地内嵌静态资产与 WebSocket 实时推送。

### Pillar 2: 27 台重型工业求解器矩阵（`tools/solve_*.py`）
- 覆盖组合优化 7 大主流领域：图论路径、工业排产、三维下料/多维装箱、微电网储能调度、库存与批量、金融投资组合、博弈与非凸规划。
- 引擎支持：Google OR-Tools (CP-SAT/GLOP)、HiGHS (MIP/Simplex)、PyVRP (HGS)、NetworkX、ALNS、Nashpy、Py3DBP 等。

### Pillar 3: 独立物理与数学校验器（`tools/validate_solution.py`, `tools/validators/`）
- **Numbers Truth 铁律**：最优值与物理指标严禁由大模型口头生成或评判。
- 独立重算原始问题数据，执行 5 类 DIMO 变异对抗测试（目标篡改、约束破坏、维度伪造、状态翻转、极端扰动），零误报、零漏检。

### Pillar 4: 原生精悍 4 智能体 + 10 领域装备包（`orpath/agents/`）
- **4 大常驻专家**：
  1. `or_analyst`（问题解构与装备包挂载）
  2. `or_modeler`（数学建模与求解脚本生成）
  3. `or_writer`（基于真实数据预渲染的六章学术论文撰写）
  4. `or_reviewer`（红队盲审与 R1/R2 论文门禁审核）
- **0 Token 纯 Python 确定性门禁**：取代大模型 Supervisor 轮询。
- **10 Pluggable `DomainCartridge` 装备包**：动态向智能体注入领域专用数据探针（`profile_<domain>_data`）与方案质检工具（`inspect_<domain>_solution`），绝不复制代码膨胀。

### Pillar 5: 主力门禁与高信噪比验证集（`scripts/*_gate.py`, `tools/test_*.py`）
- 覆盖单测、端到端全流程门禁、对抗性红队门禁（universal_redteam_gate）以及真题端到端实跑（National Contest 题集）。

---

## 3. 控制面分层所有权（Control Plane Ownership）

| 分层 | 所有者 | 职责 | 严禁行为 |
|------|--------|------|----------|
| **全局流程编排** | `LangGraph` (`orpath/graph_product.py`) | 维护状态迁移、条件边分支、失败重试上限 | 严禁通过大模型自然语言聊天动态跳转阶段 |
| **局部专家认知** | 4 大常驻 Specialist | 变量建模、求解构造、论文论述、缺陷挖掘 | 严禁大模型编写或伪造 `solution.json` 目标数值 |
| **数值计算与硬质检** | `Python tools` (`solve_*.py`, `validate_solution.py`) | 运行算法、求解器执行、客观约束验算、图表预渲染 | 严禁大模型以自然语言“验算”代替物理执行 |
| **状态共享存储** | `ORPathState` + 磁盘文件 | 强类型契约、紧凑路径指针传递 | 严禁无边界全局黑板与会话历史堆积膨胀 |
| **可视化呈现** | Web Studio + Live Watch | 读取磁盘工件展示 L0–L4 级别进度与指标 | 严禁伪造不存在的思考过程或假装执行 |

---

## 4. 零截断与上下文隔离纪律（Feynman File Handoffs）

1. **绝对零截断**：严禁在 Prompt 或回调中使用 1600 字符腰斩切片。完整数据与矩阵通过磁盘文件保存。
2. **隔离单兵调用**：每个智能体以全新的短小 Message 触发，不继承前序专家的冗长聊天上下文，根绝注意力漂移与上下文腐烂。
3. **文件手递手传递**：
   - 题面剖析存入 `notes/<slug>-problem-brief.md` 与 `notes/<slug>-profile.json`
   - 数学模型存入 `contracts/<slug>-schema.json`
   - 计算解输出至 `outputs/<slug>-solution.json`
   - 验算报告输出至 `outputs/<slug>-validation.json`
   - 论文初稿与终稿沉淀于 `papers/<slug>.md`
   - 评审意见写入 `outputs/<slug>-review.md`

---

## 5. 复杂度自适应分轨（Tier A / B / C）

- **Tier-A（精确凸优化 / 多项式极速轨）**：LP、凸 QP、最短路、经典 DP。直接调用解析求解器，拒绝无意义启发式迭代。
- **Tier-B（单问 NP-Hard 组合优化轨）**：JSSP、VRPTW、RCPSP、装箱等。锁定数学松弛下界（Lower Bound），求解器求解并给出严谨 Optimality Gap。
- **Tier-C（多问大型赛题递进轨）**：大型数模综合赛题（如圆管切割 4 问、C 题多问）。动态为每个子问生成独立 `or_modeler` 实例，严密传递跨问状态与余料资产。

---

## 6. 严禁的反模式（Anti-Patterns）

1. **大模型宣称全局最优**：当 `proven_optimal == False` 时，严禁在论文中使用“全局最优解”、“已求得最佳策略”等绝对化词汇。
2. **LLM 编造计算结果**：严禁在未经过求解器和校验器的情况下自行在文本中编造表格数据或数值。
3. **大模型当流程调度员**：严禁使用 LLM 投票或闲聊来决定下一步去哪个节点。
4. **巨石多智能体复制**：严禁为每个细分领域复制 900 行的孤立多智能体代码体系，统一收敛至 10 个轻量级 DomainCartridge 装备包。
