# OR-Path: 面向高端智能制造与复杂工程决策的运筹优化与智能工作台系统

> **核心定位：** 融合「大模型认知解析 + 本地知识库检索（RAG） + 27 台重型工业求解器矩阵（MILP / CP-SAT / DP / MPC / HGS / ALNS） + 独立物理与数学验证器（DIMO 5 类变异防御）」的原生级工业运筹优化平台，攻克空间异形管材激光下料、离散板材/芯片多目标排样、多车带时间窗路径调度、智慧能源园区光储充微电网优化调度等复杂工业工程决策场景。

[![Release](https://img.shields.io/badge/Release-v1.1.0-blue.svg)](https://github.com/lanzaoi/or-path/releases/tag/v1.1.0)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)]()
[![Solvers](https://img.shields.io/badge/Industrial%20Solvers-27%20Heavyweight-orange.svg)]()
[![Domain](https://img.shields.io/badge/Industry-AI%20%2B%20Operations%20Research-brightgreen.svg)]()
[![Validation](https://img.shields.io/badge/Numbers%20Truth-Independent%20Validator%20(DIMO)-success.svg)]()

---

## 🌟 30 秒开箱即用体验

```bat
:: 1. 全链路环境与运筹求解器健康诊断
orpath.bat doctor

:: 2. ⚡ 一键启动智能做题工作舱与实时过程看板（拖拽题面、深度研判、求解验算一站式完成）
START.bat
:: Linux / macOS / WSL 环境：./START.sh

:: 3. 运行核心运筹与验证器测试套件
pytest tools/ -v
```

| 统一入口 | 功能说明 |
|:---|:---|
| **`START.bat`** / **`START.sh`** | **智能做题工作舱与过程大屏（Web Studio & Live Watch）**：一键启动并打开浏览器（`http://127.0.0.1:8765`），支持题面文件夹拖拽导入、多视角智能研判、交互式反问确认、底层求解器调用与结果报告下载 |
| **`orpath.bat`** / **`orpath.sh`** | **命令行主控入口**：支持运行 `doctor` 健康检查、`tube-solve` 异形圆管下料求解、`demo-m0` 基准演示及各项自动化验证门禁 |

---

## 💎 四大核心工程资产

### 1. 统一启动入口与 Web Studio 智能工作台 (`START.bat`, `START.sh`, `orpath/web/`, `orpath/studio_analyzer.py`)
- **原生直连大模型与本地向量检索**：直接读取 `.env` 中的讯飞星火（`spark-x2.6`）或 DeepSeek API Key，结合本地 ONNX `bge-m3` 语义向量模型与 SQLite FTS5 混合检索（`knowledge_svc/`），无需任何外部 Node CLI 包装层。
- **全流程可视化交互**：集成了题面 OCR/文本解析、三路并行认知探针（结构拆解、方法选型、形式化建模）、工程师人在回路（Dialogue Steer）参数干预，以及毫秒级响应的实时过程台（`Live Watch`）。

### 2. 硬核运筹求解算法库 (`tools/` & `scripts/`)
所有优化计算均由纯正、可复现的运筹规划算法与精确/启发式求解器完成：
- **异形圆管三维空间展开与共切动态规划**（`scripts/b_tube_solve.py`, `scripts/b_tube_geometry.py`, `tools/solve_tube_cut_b2026.py`, `tools/tube_optimization.py`）：
  - 处理 3D 空间异形圆管端面相贯线展开、内外焊缝禁忌角度避让、轴向旋转角度离散化匹配；
  - 支持定长组合下料（Q1/Q2）、四模式激光共线共切动态规划（Q3）及跨批次余料结转排产（Q4），材料利用率达 **99.06%–99.74%**。
- **多联骨牌精确覆盖与芯片多目标布局优化**（`tools/solve_polyomino.py`, `tools/solve_polyomino_q3.py`）：
  - 基于 OR-Tools CP-SAT 求解二维网格精确覆盖与无重叠排样；
  - 支持多目标芯片/拼板布局优化（最小化采购成本、最大化共享切割边长以降低激光切割热损伤）。
- **园区光储充微电网多时段线性规划与滚动 MPC 控制**（`tools/solve_microgrid.py`, `tools/microgrid_reporting.py`）：
  - 基于 SciPy HiGHS 构建 96 时段（15 分钟粒度）日前光储充协同调度线性规划模型（分时电价套利、需量电费削峰、储能充放电损耗与寿命折旧、有序充电激励）；
  - 内置日内滚动时域模型预测控制（Rolling-Horizon MPC），平抑光伏出力与负荷预测误差，并自动生成全套调度数据报表与高分辨率分析图表。
- **经典图论与车辆路径规划引擎**（`tools/solve_ortools.py`, `tools/solve_highs.py`, `tools/solve_networkx.py`）：
  - 覆盖网络流最短路（Shortest Path）、旅行商问题（TSP）、带容量限制车辆路径问题（CVRP）及带硬时间窗准时制配送问题（VRPTW）。
- **作业车间调度 JSSP / 柔性作业车间调度 FJSSP 工业引擎**（`tools/solve_jssp.py`）：
  - 基于 PyJobShop（CP-SAT）工业级调度引擎，内置 **Taillard 基准算例库**（JSSP：ft/la/abz/orb/swv/yn/ta 共 67 例；FJSSP：kacem/mk/abz 变体/Dauzère-Pérès/Chambers-Barnes 等 407 例），均附带 JSPLib 已知最优值作为参考基准；
  - 支持 **工序换模时延**（sequence-dependent setup time）：均匀换模时间或按操作对的显式换模矩阵；
  - 支持 **甘特图生成**（每台机床一行，输出 PNG），并输出机床利用率、总流程时间、换模总时延等指标；
  - 严格遵循 Numbers Truth：目标值与排产方案均来自求解器，已知最优值仅作 gap 参照，绝不冒充求解结果。

### 3. 独立物理与数学验证器 (`tools/validate_solution.py` & `tools/validators/`)
- **坚守 Numbers Truth 铁律**：大模型绝不直接编造最优目标值或排产方案。
- **零信任独立重算**：验证器与求解器完全解耦，直接从原始算例输入数据出发，对每一份 `*-solution.json` 执行独立的物理可行性与目标函数重算（包括圆管 748 项空间几何与焊缝干涉硬约束检验、骨牌网格覆盖无重叠检验、微电网功率平衡与 SOC 边界检验、VRP 容量与时间窗检验）。

### 4. 核心业务案例验证与 Pytest 单元测试 (`tools/test_*.py` & `scripts/*_gate.py`)
- 配备完善的单元测试与端到端门禁：
  - `tools/test_tube_optimization.py`：三维圆管母材分配、模式匹配与共切优化单元测试
  - `tools/test_microgrid_optimization.py`：园区微电网日前规划、敏感性分析与 MPC 滚动控制测试
  - `tools/test_polyomino_q3.py` & `tools/test_solvers_t2.py`：骨牌排样、最短路、TSP、VRP 求解与独立验证器测试
  - `scripts/problem_workbench_gate.py` & `scripts/v0_watch_gate.py`：Web Studio 工作台与过程看板契约门禁

---

## 📂 项目结构

```text
OR-Path/
├── START.bat / START.sh            # 智能做题工作舱与 Live Watch 统一启动入口
├── orpath.bat / orpath.sh          # 命令行控制与门禁运行入口
├── orpath/                         # 核心控制面与 Web Studio 服务
│   ├── web/                        # Web Studio 与实时过程看板前端源码及构建产物 (watch.html)
│   ├── studio_analyzer.py          # 原生大模型多视角题面研判引擎 (Spark X2.6 / DeepSeek + 本地 RAG)
│   ├── graph_product.py            # 16 节点确定性 LangGraph 运筹工作流状态机
│   ├── pipeline/                   # 审题 (intake)、检索调研 (research)、建模求解 (solve)、报告生成 (paper)
│   └── watch_snapshot.py           # 零 LLM 依赖的高性能工作台状态聚合引擎
├── tools/                          # 硬核运筹求解器与独立物理/数学验证器
│   ├── solve_ortools.py            # OR-Tools 路由与组合优化求解器 (TSP / CVRP / VRPTW)
│   ├── solve_highs.py              # HiGHS 混合整数线性规划 (MILP) 求解器
│   ├── solve_networkx.py           # NetworkX 图论与最短路精确求解器
│   ├── solve_polyomino.py          # CP-SAT 多联骨牌二维精确覆盖求解器
│   ├── solve_polyomino_q3.py       # 芯片/板材多目标排样与共边最大化求解器
│   ├── solve_tube_cut_b2026.py     # 异形圆管激光下料多阶段运筹求解器
│   ├── tube_optimization.py        # 圆管下料动态规划与启发式核心算法库
│   ├── solve_microgrid.py          # 园区光储充微电网日前 LP 与日内滚动 MPC 求解器
│   ├── microgrid_reporting.py      # 微电网多维工程报表与图表生成工具
│   ├── solve_jssp.py               # JSSP/FJSSP 工业调度引擎 (Taillard 基准 + 换模时延 + 甘特图)
│   ├── validate_solution.py        # 独立物理与数学验证器主入口
│   └── validators/                 # 各领域独立重算验证器 (routing / polyomino / tube / microgrid)
├── scripts/                        # 核心业务求解脚本 (b_tube_solve.py 等) 与自动化门禁
├── knowledge/ & knowledge_svc/     # 本地运筹学知识库 (BM25 + ONNX bge-m3 混合检索)
├── fixtures/ & demo/seed/          # 标准测试算例与开箱即用演示种子 (live-btube / m0)
└── specs/ & docs/                  # 系统设计规范 (SDD) 与架构文档
```

---

## 🛠️ 质量验证与测试命令

```bash
# 1. 运行全量运筹求解器与验证器单元测试
pytest tools/ -v

# 2. 环境与核心资产健康检查
python scripts/orpath_doctor.py

# 3. Web Studio 工作台与看板门禁验证
python scripts/problem_workbench_gate.py
python scripts/v0_watch_gate.py

# 4. 异形圆管几何稳定性、协同账本与红队边界门禁
python scripts/tube_geometry_stability_gate.py
python scripts/tube_collaboration_gate.py
python scripts/tube_redteam_gate.py
```

---

## 📋 运行环境说明

- **操作系统**：Windows 10 / 11 (x64)、Linux、macOS 或 WSL2
- **核心依赖**：Python 3.10+（详见 `requirements.txt`：OR-Tools、SciPy/HiGHS、NetworkX、NumPy、Pandas、LangGraph 等）
- **大模型配置（可选）**：复制 `.env.example` 为 `.env`，填入 `XFYUN_API_KEY`（讯飞星火 `spark-x2.6`）或 `DEEPSEEK_API_KEY` 即可启用 Web Studio 智能审题与交互式建模分析；底层运筹求解器与独立验证器支持完全离线运行。
