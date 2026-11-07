# tasks/ — 任务规划、重构总单与迭代路线图（Task Roadmap）

**定位：** 本目录管理 OR-Path 项目的施工大单、阶段性重构方案、任务切片与历史工单记录。

---

## 1. 核心总单索引（Master Plans）

| 计划文件 | 状态 | 核心内容 | 阶段跨度 |
|----------|------|----------|----------|
| **[`lean_4agent_5x5_master_plan.md`](lean_4agent_5x5_master_plan.md)** | **100% DONE ✅** | **精简 4 智能体 + 10 领域装备包 + 27 工业求解器 5×5 重构总单**（25 项子任务已全量落地并通过门禁） | Phase 1 ~ Phase 5 |

---

## 2. 5×5 主计划执行复盘（The 5x5 Completed Milestone）

该计划彻底重构了早期 60+ 冗余克隆智能体与旧版 Node.js `pi` 子进程架构，建立起现代 5 大支柱体系：

### Phase 1: 4 常驻特种兵与纯 Python 确定性门禁（Consolidation）
- [x] **Plan 1.1**: 剥离全库 60+ 膨胀复制的智能体文件，收敛至 4 大精锐专家（`or_analyst`, `or_modeler`, `or_writer`, `or_reviewer`）。
- [x] **Plan 1.2**: 0-Token 纯 Python 确定性节点与条件边全面取代大模型 Supervisor 轮询。
- [x] **Plan 1.3**: 建立紧凑单兵调用上下文（Isolated File Handoffs），杜绝会话累积与 1600 字符腰斩。
- [x] **Plan 1.4**: 实现复杂度自适应分轨（`Tier-A` 极速轨、`Tier-B` 组合松弛轨、`Tier-C` 大型赛题多问轨）。
- [x] **Plan 1.5**: 离线 CI 门禁与真实 Live 模式解耦（显式 `live_subagent=False` 保护自动化测试不挂起）。

### Phase 2: 10 领域装备包与 27 重型工业求解器矩阵（Solvers Expansion）
- [x] **Plan 2.1**: 实现 10 个即插即用的 `DomainCartridge` 装备包（挂载专用数据探针与解质检工具）。
- [x] **Plan 2.2**: 工业排产与工程调度算子库上线（JSSP/FJSSP 换模调度、RCPSP、员工排班）。
- [x] **Plan 2.3**: 现代车辆路径 PyVRP (HGS/PDP) 与轴辐式枢纽选址 (p-Hub) 深度集成。
- [x] **Plan 2.4**: 生产批量规划 (Wagner-Whitin / CLSP) 与马科维茨风险平价金融投资组合求解器上线。
- [x] **Plan 2.5**: 离散数学拓展（纳什均衡、最大团对偶判定、图着色、两阶段随机规划、三合一装箱）。

### Phase 3: Numbers Truth 物理校验与 DIMO 5 类变异防御（Defense & Verification）
- [x] **Plan 3.1**: 独立物理校验主入口 `validate_solution.py` 与 7 大细分领域校验器全面打通。
- [x] **Plan 3.2**: 建立 DIMO 5 类变异注入器（`dimo_mutator.py`：目标篡改、约束违背、维度伪造、状态翻转、浮点扰动）。
- [x] **Plan 3.3**: 研发通用红队拦截门禁（`universal_redteam_gate.py`），确保变异篡改 100% 拦截。
- [x] **Plan 3.4**: 严格执行禁止伪造全局最优律，强制输出 Optimality Gap 与物理证明。
- [x] **Plan 3.5**: 论文预渲染真数据表格与 Markdown 图表管道建立。

### Phase 4: Web Studio 拖拽做题工作舱与全透明过程看板（Visibility & Interaction）
- [x] **Plan 4.1**: 升级 `START.bat` / `START.sh`，构建纯 Python Web Studio 前端服务。
- [x] **Plan 4.2**: 实现赛题文件夹/文件拖拽题目摄入与实时解析。
- [x] **Plan 4.3**: 研发 `studio_analyzer.py` 结构化数据深层探针，自动输出矩阵规模与特征。
- [x] **Plan 4.4**: 研发人机协同参数覆盖与算法确认弹窗（Interactive Confirmation Modal）。
- [x] **Plan 4.5**: 全要素 Live Watch 仪表盘升级（覆盖 L0~L4 全链路状态实时呈现）。

### Phase 5: 国赛真题实跑验收、通用沙箱与遗留清理（Flagship Benchmarking）
- [x] **Plan 5.1**: 国赛 2024 C 题微电网与 2026 B 题圆管套裁端到端真题旗舰实跑验证。
- [x] **Plan 5.2**: 受控 Python MIP/CP-SAT 沙箱建模支持（`execute_python_sandbox`）。
- [x] **Plan 5.3**: 全库遗留 Node.js `pi` 废弃代码、失效测试与冗余脚本全面清理。
- [x] **Plan 5.4**: 自动化全套门禁回归与持续集成保障。
- [x] **Plan 5.5**: 提交主分支与版本发布。

---

## 3. 历史任务归档（`tasks/archive/`）

以下文件为已完成的早期求解器扩充草稿与实现笔记：
- `tasks/archive/binpack_upgrade_plan.md`: 1D/2D/3D 装箱求解器升级记录
- `tasks/archive/game_theory_impl.md`: 双矩阵博弈论求解器实现笔记
- `tasks/archive/task_max_clique.md`: 最大团/最大独立集对偶求解器实现记录
- `tasks/archive/expand_solvers_prompt.txt`: 早期求解器扩充需求草稿
- `tasks/archive/p1.txt`: 早期求解器开发提示词

---

## 4. 后续演进规划（Future Milestones）

1. **分布式求解器并发 Worker 调度池**：针对大规模网格搜索与超参数并行调优，提供后台进程池调度支持。
2. **论文直接导出 PDF 引擎**：结合本地 Weasyprint / Typst 编译器，将 6 章标准学术 Markdown 一键导出为符合国赛标准排版的 PDF。
3. **Web Studio 智能交互式约束提问对话**：利用 `or_analyst` 在题目识别产生歧义时，在前端工作台中向用户主动发起选项式交互确认。
