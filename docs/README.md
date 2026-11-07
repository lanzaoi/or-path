# docs/ — OR-Path 官方文档导航

**原则：** 顶层只放「当前生效且必须查阅的文档」。历史关单报告、早期施工计划、原始运行证据已统一沉淀至 **`archive/`** 目录。  
系统核心法条位于 **`../specs/`**；日常命令速查见仓库根目录 **`../ORPATH.md`**；一键启动见 **`../START.bat`** / **`../START.sh`**。

---

## 1. 快速上手与操作指南

| 文档路径 | 核心用途 | 目标受众 |
|----------|----------|----------|
| **[`user-guide.md`](user-guide.md)** | ★ **官方全功能使用教程**（Web Studio 拖拽做题、CLI 无头运行、门禁回归） | 全体用户 / 参赛队员 |
| **[`watch-studio.md`](watch-studio.md)** | ★ **Web Studio 与 Live Watch 前端实现架构**（双向工作舱、实时看板、数据流） | 前端 / 全栈开发者 |
| **[`../START.bat`](../START.bat)** | Windows / WSL 智能做题工作舱一键启动器 | 全体用户 |
| **[`../START.sh`](../START.sh)** | Linux / macOS 智能做题工作舱一键启动器 | 全体用户 |
| **[`../ORPATH.md`](../ORPATH.md)** | 命令行日常指令极速备忘清单（CLI CheatSheet） | 开发者 / 自动化运维 |

---

## 2. 核心架构与学术标准

| 文档路径 | 核心用途 | 规范对齐 |
|----------|----------|----------|
| **[`ARCHITECTURE.md`](ARCHITECTURE.md)** | ★ **现代原生纯 Python 5 大支柱架构总览**（精简 4 智能体 + 10 领域装备包 + 27 求解器） | `specs/architecture.md` |
| **[`solver-stack.md`](solver-stack.md)** | ★ **27 台重型工业求解器矩阵全谱系**（覆盖 7 大领域算法、输入输出与验证基准） | `specs/solvers-and-validate.md` |
| **[`or-paper-sop.md`](or-paper-sop.md)** | ★ **运筹优化 6 章标准学术论文写作与评审 SOP**（Numbers Truth 预渲染数据表与 R1/R2 审核） | `specs/paper-and-review.md` |
| **[`repo-surface.md`](repo-surface.md)** | 仓库代码边界、敏感信息保护与 Git 提交白名单 | `specs/engineering-hygiene.md` |

---

## 3. 典型赛题与专项目录

| 文档路径 | 核心用途 | 对应问题类 |
|----------|----------|------------|
| **[`tube-optimization-v2.md`](tube-optimization-v2.md)** | 国赛 B 题 3D 异构圆管套裁算法设计（列生成 + 几何 DP + ALNS + 跨批束搜索） | `tube_cut` |
| **[`m2-polyomino.md`](m2-polyomino.md)** | 多联骨牌平面精确平铺与非标覆盖域桥梁规范 | `polyomino_cover` |
| **[`vrp-public-baseline.md`](vrp-public-baseline.md)** | 公开 CVRPLIB / VRPTW 标准基线算法与测试复现说明 | `vrp`, `pyvrp` |

---

## 4. 架构决策记录（ADR）

| 路径 | 说明 |
|------|------|
| **[`adr/`](adr/)** | 历史与现行核心架构决策（ADR-0001 至 ADR-0006：阶段节点、求解与校验解耦、控制面唯一性、论文生成协议、智能体隔离、文档工程纪律） |

---

## 5. 历史归档（Historical Archive）

以下目录包含项目迭代历史记录、早期里程碑关单报告与旧版实验证据，默认无需加载至当前上下文：

- **`archive/closeouts/`**：T1–T3、1.x、M0、P5 等历史里程碑 Closeout 报告
- **`archive/plans/`**：早期阶段开发施工单与方案设计稿
- **`archive/tickets/`**：已闭环的重构与修复工单记录
- **`archive/design-notes/`**：早期的系统设计演进草稿与技术选型调研笔记
- **`archive/evidence/`**：历史运行日志与门禁测试证据文件
- 完整归档索引参见：[`archive/README.md`](archive/README.md)
