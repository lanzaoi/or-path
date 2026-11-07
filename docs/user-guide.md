# OR-Path 官方使用指南（User Guide）

面向：**参赛队友** · **运筹工程师** · **算法研究员** · **系统开发者**。  
精简入口见根目录 [`README.md`](../README.md)；命令速查见 [`ORPATH.md`](../ORPATH.md)；核心系统法条见 [`specs/README.md`](../specs/README.md)。

---

## 0. 系统全景认知（What You Are Using）

OR-Path 是由纯 Python 原生驱动的**多智能体运筹优化（Operations Research）自动化求解与论文生成工作舱**：

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ 题面与数据 (PDF/TXT/CSV/XLSX) ──► 结构化深度探针 (studio_analyzer.py)       │
│                                                │                            │
│ ┌──────────────────────────────────────────────▼──────────────────────────┐ │
│ │ Web Studio (Problem Workbench) 交互确认: 模式切换 / 参数覆盖 / 约束复核  │ │
│ └──────────────────────────────────────────────┬──────────────────────────┘ │
│                                                │                            │
│   ┌────────────────────────────────────────────▼────────────────────────┐   │
│   │ LangGraph 控制面: 0-Token 确定性流转分支 + 4 大常驻智能体单兵调用   │   │
│   │                                                                     │   │
│   │  or_analyst  ──► or_modeler ──► 27 工业求解器 ──► validate_solution │   │
│   │                                                         │           │   │
│   │  END ◄── provenance ◄── or_reviewer ◄── or_writer ◄─────┘           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

| 核心实体 | 说明 |
|----------|------|
| **HOME** | 仓库安装根目录（算法、知识库、求解器、门禁脚本） |
| **WORKDIR** | 运行工作区（包含 `outputs/`, `runs/`, `notes/`, `papers/`） |
| **slug** | 案例标识符，贯穿全流程物理产物命名 |
| **Numbers Truth** | 数字真理铁律：所有最优值与决策序列必须 100% 经物理求解器真实运算与校验器独立复算 |
| **Web Studio** | 本地双向工作舱，支持拖拽做题、参数微调与全透明实时 Live Watch 监控 |

---

## 1. 环境准备与极速安装

系统已彻底退役并剥离历史 Node.js `pi` CLI 包装层，**无需安装任何 Node.js/npm 环境**，全流程 100% 运行于纯 Python 虚拟环境。

### 1.1 依赖准备
- **Python**: 3.11 – 3.14（推荐项目内置 `.venv`）
- **C/C++ 编译运行时**: Linux/WSL `build-essential`（用于编译安装 HiGHS / OR-Tools / PyVRP 等扩展库）
- **大模型 API Key（用于 Live 智能体闭环）**:
  - 科大讯飞星火 `spark-x2.6`（内置支持，极速响应与超长上下文）
  - DeepSeek `deepseek-chat` / `deepseek-reasoner`
  - 其他 OpenAI 兼容接口（如 Qwen、GLM）

### 1.2 快速启动与自检

```bash
# 1. 检查运行环境健康状态
.venv/bin/python scripts/orpath_doctor.py

# 2. 一键启动 Web Studio 智能工作舱
# Linux / macOS / WSL:
./START.sh

# Windows:
START.bat
```

启动后，系统会在本地启动 FastAPI/Uvicorn 服务并自动唤起浏览器打开：
`http://127.0.0.1:8000`

---

## 2. 核心工作流（三种使用模式）

### 模式 A：Web Studio 网页端拖拽做题（推荐主流）

1. **拖拽题面与附件**：
   - 将赛题文件夹（包含 PDF/TXT 题面及附带的 CSV/XLSX 数据表）直接拖入工作台正中央的虚线拖拽区。
2. **结构化深度画像（Data Profiling）**：
   - `orpath/studio_analyzer.py` 探针自动读取数据表，提取实体规模（客户数、机床数、零部件规格）、时间序列长度、矩阵稀疏度，并智能推荐匹配的求解算子与复杂度分轨（`Tier-A / Tier-B / Tier-C`）。
3. **人机协同确认弹窗（Interactive Confirmation Modal）**：
   - 弹出结构化确认卡片，支持用户微调关键配置：
     - **求解模式切换**：如将默认模式切换为 `highs`、`cpsat` 或 `pyvrp`；
     - **时间与精度上限**：调整超时秒数限制（Time Limit）；
     - **断点挂起（Pause Next）**：勾选在求解或写作前暂停等待确认。
4. **一键执行与 Live Watch 看板**：
   - 点击「🚀 启动全流程分析研判」，页面自动切换至实时 Live Watch 仪表盘。
   - 实时呈现 L0（阶段流转）、L1（智能体单兵时序）、L2（工具调用明细）、L3（思维分析链）与 L4（物理产物与验算报告）。
5. **下载成果**：
   - 求解完成后，直接在页面查看预渲染图表、数学模型，并一键导出 6 章标准学术论文（Markdown / PDF）。

---

### 模式 B：命令行极速运行（CLI Headless）

适用于服务器无图形界面环境或自动化批处理：

```bash
# 1. 运行标准测试案例（以最经典最短路为例，快速验证控制面）
.venv/bin/python orpath/run_orpath.py --problem-id shortest_path --solve-mode networkx --slug demo_sp --fresh

# 2. 运行 TSP 问题（采用 HiGHS MTZ 整数规划求解）
.venv/bin/python orpath/run_orpath.py --problem-id tsp_n8 --problem-class tsp --solve-mode highs --slug demo_tsp --fresh

# 3. 运行工业作业车间调度（JSSP 换模调度）
.venv/bin/python tools/solve_dispatch.py jssp_ft06 --mode jssp

# 4. 断点恢复与从特定阶段重跑
.venv/bin/python orpath/run_orpath.py --resume --thread-id demo_sp
.venv/bin/python orpath/run_orpath.py --from-stage model --thread-id demo_sp
```

---

### 模式 C：离线回归门禁与对抗演练（Engineering CI）

```bash
# 运行核心单元测试与数学真理测试
.venv/bin/pytest tools/test_sop_doc.py tools/test_lean_cartridges_and_graph.py -q -p no:langsmith

# 运行 DIMO 5 类变异对抗拦截红队门禁
.venv/bin/python scripts/universal_redteam_gate.py

# 运行 Web Studio 工作舱全功能集成门禁
.venv/bin/python scripts/problem_workbench_gate.py

# 运行 10 领域装备包全生命周期门禁
.venv/bin/python scripts/or_swarms_master_gate.py
```

---

## 3. 27 台工业求解器快速索引表

| 领域分类 | 求解器脚本 | 算法 / 求解引擎 | 典型问题类 | 默认状态宣称 |
|----------|------------|-----------------|------------|--------------|
| **路径与图论** | `solve_networkx.py` | Dijkstra / Bellman-Ford | 最短路 Shortest Path | `OPTIMAL` (Exact) |
| | `solve_cpsat.py` | Google OR-Tools CP-SAT | 旅行商问题 TSP | `OPTIMAL` (Exact) |
| | `solve_highs.py` | HiGHS MIP (MTZ Formulation) | 旅行商问题 TSP | `OPTIMAL` (Exact) |
| | `solve_ortools.py` | OR-Tools Routing | 车辆路径 CVRP / VRPTW | `FEASIBLE` (Heuristic) |
| | `solve_pyvrp.py` | PyVRP (Hybrid Genetic Search) | 大规模 VRPTW / 取送货 PDP | `FEASIBLE` (Bound + Gap) |
| | `solve_network_flow.py`| NetworkX / OR-Tools | 最小费用最大流 | `OPTIMAL` (Exact) |
| **车间与工程调度** | `solve_jssp.py` | PyJobShop / CP-SAT | 作业车间 JSSP / FJSSP (换模) | `OPTIMAL` / `FEASIBLE` |
| | `solve_rcpsp.py` | CPM 关键路径 + Cumulative CP-SAT | 资源受限项目调度 RCPSP | `OPTIMAL` / `FEASIBLE` |
| | `solve_staff_rostering.py`| OR-Tools CP-SAT | 护士/员工轮班排程 | `OPTIMAL` / `FEASIBLE` |
| **选址与网络设计**| `solve_facility.py` | HiGHS MIP | 容量限制设施选址 CFLP | `OPTIMAL` (Exact) |
| | `solve_hub_location.py`| HiGHS MIP | 轴辐式枢纽选址 p-Hub | `OPTIMAL` (Exact) |
| | `solve_qap.py` | 线性化 MIP + 禁忌搜索 | 二次分配问题 QAP | `FEASIBLE` (Bound + Gap) |
| **空间下料与装箱**| `solve_binpack.py` | py3dbp (3D) / rectpack (2D) / MIP (1D)| 三维集装箱/二维板材装箱 | `FEASIBLE` / `OPTIMAL` |
| | `solve_polyomino.py` | DLX 精确覆盖 / CP-SAT | 骨牌精确平铺覆盖 | `OPTIMAL` (Exact) |
| | `solve_tube_cut_b2026.py`| 列生成 + CP-SAT + 几何 DP + ALNS | 国赛 B 题 3D 异构圆管套裁 | `FEASIBLE` (Heuristic) |
| **微电网与能源调度**| `solve_microgrid.py` | 凸二次规划 + 滚动时域 MPC | 园区光储充一体化削峰填谷 | `OPTIMAL` (Exact) |
| **库存、金融与随机**| `solve_lot_sizing.py`| Wagner-Whitin DP / CLSP MIP | 多阶段批量库存规划 | `OPTIMAL` (Exact) |
| | `solve_portfolio.py` | 凸二次规划 (QP) / 风险平价 | 马科维茨投资组合优化 | `OPTIMAL` (Exact) |
| | `solve_stochastic_lp.py`| Extensive Form MIP / L-shaped | 两阶段随机线性规划 | `OPTIMAL` (Exact) |
| **博弈与离散优化**| `solve_game_theory.py`| Nashpy (Lemke-Howson / 枚举) | 双矩阵纳什均衡 | `OPTIMAL` (Exact) |
| | `solve_max_clique.py` | 补图对偶判定 + CP-SAT | 最大团 / 最大独立集 | `OPTIMAL` (Exact) |
| | `solve_graph_coloring.py`| DSATUR 启发式 + CP-SAT | 节点着色问题 | `OPTIMAL` / `FEASIBLE` |
| | `solve_qubo_ising.py` | 模拟退火 / 二次无约束二值优化 | QUBO / Ising 优化 | `FEASIBLE` (Heuristic) |

---

## 4. 运行产物全貌（Where Artifacts Live）

每次任务执行完毕后，所有产物以紧凑文件指针沉淀于工作区，支持完全离线复验：

```text
outputs/
  ├── <slug>-solution.json       # 物理求解器产出的标准 JSON 解包
  ├── <slug>-validation.json     # 独立物理校验器的重算报告与不变量检验结论
  ├── <slug>-review.md           # or_reviewer 红队盲审报告 (FATAL/MAJOR/MINOR 评级)
  ├── <slug>.provenance.md       # 全链路数字指纹与审计证据
  └── <slug>-tables.md           # Python 预渲染的真实 Markdown 数据表格
papers/
  └── <slug>.md                  # or_writer 撰写的 6 章学术标准完整学术论文
notes/
  ├── <slug>-problem-brief.md    # or_analyst 输出的问题语义分析与约束清单
  └── <slug>-profile.json        # 题目数据特征与矩阵结构画像
runs/<slug>/
  └── stages/                    # 阶段快照 JSON，记录每站耗时与状态迁移
```

---

## 5. 常见问题排查（Troubleshooting）

1. **大模型调用报错或超时**：
   - 检查 `.env` 文件中 `OPENAI_API_KEY` 与 `OPENAI_BASE_URL` 配置是否正确；
   - 系统支持离线回归模式：在环境变量中设置 `ORPATH_LIVE_SUBAGENT=0`，即可无需任何 API Key 走通确定性物理门禁。
2. **求解器提示缺少第三方包**：
   - 执行 `.venv/bin/pip install -r requirements.txt`，确保 `scipy`, `ortools`, `highs`, `pyvrp`, `networkx` 安装齐全。
3. **网页端拖拽题目无反应**：
   - 检查前端服务是否正常运行；若浏览器有缓存，按 `Ctrl + F5` 强制刷新 Web Studio 界面。
