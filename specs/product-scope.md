# Product Scope — 产品范围

## 产品名

**OR-Path Multi-Agent / Graph-OR Agent**

## 一句话

自然语言运筹问题 → 检索增强研究 → 结构化建模（无最优值）→ **确定性求解** → **validate 重算** → 解释与论文草稿（R1/R2）→ 有界回修；多智能体真隔离；知识云优先且可引用。

## 目标用户 / 场景

- 作品集主独立 AI 项目（Track B）  
- 演示与工程可审计的 OR 闭环（最短路 / TSP / VRP 等）  
- 开发者本机：`Desktop/agent` + OpenPi + Pi + LangGraph  

## In scope（产品目标能力）

1. **多问题类：** `shortest_path`、`tsp`、`vrp`（T2：TSP n=8；VRP ≥2 车 + 容量）  
2. **真多智能体：** `pi-subagents` 角色隔离 + 可检 transcript  
3. **控制面：** LangGraph 阶段机 + checkpointer  
4. **数字真相：** NetworkX / OR-Tools / mock 工具输出；LLM 禁止心算最优  
5. **校验：** `validate_solution` 重算可行性与 objective  
6. **知识竖切：** 种子图 + MinerU Cloud + LightRAG + BM25/FTS + RRF + Cognee Cloud smoke  
7. **论文环：** draft + R1（含在线轨）+ R2 + 有界 revise  
8. **UI：** OpenPi 主；Pi TUI 辅；T2 **OpenPi 截图硬 DoD**  
9. **LG↔Pi bridge：** T2 **硬 DoD**（可开关，CI 默认可关，但 closeout 必须证明通）

## Out of scope / 非目标（明确不做或不宣称）

| 非目标 | 说明 |
|--------|------|
| Agent Teams / 消息总线作脊柱 | 拓扑 OUT |
| Graphiti / MS GraphRAG 主路径 | 不用 |
| Feynman 作主开发壳 | vendor 参考 only |
| Hermes MEMORY 作产品记忆 | 仅导航 |
| 完整 codegen + sandbox 自修环 | OR-LLM-Agent 全套 → 非 T2（validate 调参 ≠ codegen） |
| 时间窗 VRP | T2 不做 TW |
| Compose/K8s 硬交付 | T2 不进仓内硬 DoD（Q15-A）；日后可再冻 |
| 多租户 SaaS / 计费 | 不做 |
| 自制「SOTA 黄金集」叙事 | 禁止；用 fixture gap + negatives + 诚实 smoke |
| 宣称 LightRAG 直接吃生 PDF 数学 | 公式在 MinerU 阶段固定 |
| 宣称顶会论文质量或抄论文准确率数字 | 无独立评测不写 |

## 作品集话术边界（claim ladder）

**可以说：**

- 带验证关卡的 Supervisor–Worker 流水线  
- 多 Agent 隔离轨迹可检  
- 最优值来自求解器并经 validate 重算  
- 云优先知识预处理 + 混合检索供 Researcher  

**不可以说：**

- 「保证全局最优 / 替代 OR 专家」  
- 「Pi/LG 保证最优」  
- 「已达 OR-LLM-Agent 85%」等无本仓评测支撑的数字  
- 「FTS/LightRAG 主搜索引擎已生产级」若仅 smoke  

## 里程碑关系

| 里程碑 | 状态 / 含义 |
|--------|-------------|
| **T1** | CLOSED/PASS — 薄全链 + 多 Agent 证明；不重开 DoD |
| **T2** | 数字真相加厚 + 知识竖切 + bridge + 云分轨 + OpenPi 截图 — 见 `gates-and-dod.md` |
| **T3+** | 更强 modeling/IR、评测、部署等 — 未冻 |

## 工作区法

- 根目录：`C:\Users\Lanzao\Desktop\agent\`  
- **禁止**在 `inquisitive-master` 等其它仓写本产品业务代码  
- 会话标题 ≠ cwd：写前确认 Project / pwd  
