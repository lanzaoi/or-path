# Product Scope — 产品范围（详细）

**对齐：** `product-flow-sdd.md`  
**状态：** LAW 2026-08-01

---

## 1. 产品名与一句话

**OR-Path Multi-Agent / Graph-OR Agent**

自然语言/题面运筹问题 → 研究与建模 → **确定性求解 + validate** → 论文有界打回；真多 Agent 隔离；过程可审计、可可视化。

---

## 2. 目标用户 / 场景

- 作品集主独立 AI（Track B）  
- 工程可审计 OR 闭环演示  
- 本机：`ORPATH_HOME` + Pi + LangGraph  
- **当前交付焦点：** Demo **M0**（见总流程），不是「全竞赛自动交卷」  

---

## 3. In scope

### 3.1 能力（产品目标，分期交付）

| # | 能力 | 最低里程碑 |
|---|------|------------|
| 1 | 问题类 SP / TSP / VRP（+ 已注册域 adapter） | 基线已有；新域 M2+ |
| 2 | 真多智能体 pi-subagents | 已有；M0 要证据+时间线 |
| 3 | LG 控制面 + checkpointer | 已有 |
| 4 | 数字真相 + claim ladder | 已有 |
| 5 | validate 重算 | 已有 |
| 6 | 知识竖切（seed/hybrid） | 已有 smoke |
| 7 | 论文环 R1/R2/revise | 已有 |
| 8 | menu 主入口 | 已有 |
| 9 | 题面 intake OCR | 已有 |
| 10 | **过程时间线 + sub 轨迹可视** | **M0/M1** |
| 11 | 域桥（如 polyomino） | M2 |
| 12 | launch SYSTEM 真注入 | M3 |
| 13 | 记忆叙事 / 1 MCP | M4 |

### 3.2 当前唯一对外承诺

在 M0 PASS 前，对外只承诺：

> 能按文档跑通 **M0 Demo**：出数 + 真 sub 证据 + 时间线文件。

T1–1.2 closeout = **历史工程资产**，不等于愿景完成。

---

## 4. Out of scope / 非目标

| 非目标 | 说明 |
|--------|------|
| Agent Teams / 消息总线脊柱 | 拓扑 OUT |
| Graphiti / MS GraphRAG 主路径 | OUT |
| Feynman 主开发壳 | vendor only |
| Hermes MEMORY 产品记忆 | 导航 only |
| Cognee 作运筹主长期记忆 / 生产图脑 | **OUT**；仅 smoke 旁路（`memory.md`） |
| 完整 codegen sandbox 自修 | 非本阶段 |
| 未注册域假装求解成功 | 必须 BLOCKED 或显式 adapter |
| OpenPi 产品壳 | 已删除 |
| 自制 SOTA 黄金集叙事 | 禁止 |
| LightRAG 直接吃生 PDF 数学 | 公式在 MinerU |
| 抄论文准确率无本仓评测 | 禁止 |
| OCR 100% / 替代专家读题 | 禁止 |
| intake 内求解 | 禁止 |
| M0 前上完整 MCP 市场 / Cognee 生产化记忆大脑 | 禁止抢跑；战法用 Skill 沉淀不抢 V0 |
| 时间线用 LLM 编造协作 | 禁止 |

---

## 5. Claim ladder（话术）

### 可以说（有证据时）

- 带验证关卡的 Supervisor–Worker 流水线  
- 多 Agent 隔离轨迹可检（toolCall + 路径）  
- 精确轨 + validate；Routing 诚实非证明最优  
- 过程时间线来自磁盘聚合  
- M0：一入口 + 数 + sub + 时间线  

### 不可以说

- 保证全局最优（超规模）  
- Routing = 数学证明最优  
- 启发式是核心卖点  
- Pi/LG 保证最优  
- 无评测抄 85%  
- 裸 pi 聊天 = 产品 MA  
- 门禁绿 = 用户 Demo 完成  
- 已自动交 B 题（无 adapter/solution 时）  

权威求解 claim：`solvers-and-validate.md` · `docs/solver-stack.md`。

---

## 6. 里程碑状态表

| 里程碑 | 状态 | 含义 |
|--------|------|------|
| T1 | CLOSED/PASS | 薄全链 + MA 证明；不重开 |
| T2 | CLOSED/PASS | 厚栈；OpenPi 截图 DoD 退役 |
| T3 | 工程 PASS | LG 骨架 |
| 1.0 | PASS | paper + harness + ADR |
| 1.1 | CLOSED/PASS | intake |
| 1.2 | 工程 PASS | soak + BLOCKED 诚实；非交卷 |
| **M0** | **当前目标** | 总流程 Demo 合同 |
| M1+ | 未开 | 可视加厚/域桥/launch/记忆 |

---

## 7. 工作区法

- 根：`Desktop/agent` 或 `ORPATH_HOME`  
- 会话标题 ≠ cwd  
- git：不提交 `.env`、竞赛 PDF 附件、大宗 outputs、node_modules、默认 pi-main/vendor  

---

## 8. 参考

`product-flow-sdd.md` · `process-visibility.md` · `gates-and-dod.md`  
