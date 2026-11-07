# OR-Path 工业求解器全谱系选型与架构全景（Solver Stack）

**原则（Numbers Truth 铁律）：**  
1. **精确优化轨（Exact Rail）**：以 **可验证的精确最优解（Proven Optimal）** + **validate 独立物理重算** 作为学术与工程可信度的核心基石。
2. **规模扩展与启发式轨（Combinatorial / Metaheuristic Rail）**：必须提供**理论数学下界（Lower Bound）**与严谨的 **Optimality Gap** 报告，严禁伪造“全局最优”。
3. **接口标准统一**：所有求解器通过统一的 `tools/solve_dispatch.py` 调度，产出标准 JSON Envelope，并通过 `tools/validate_solution.py` 进行物理验算。

---

## 1. 27 台重型工业求解器矩阵全景表

```text
┌───────────────────────────────────────────────────────────────────────────────────┐
│                          OR-Path 27 工业求解器矩阵 (7 大领域)                     │
├───────────────────────┬─────────────────────────┬─────────────────────────────────┤
│ 领域分类              │ 求解脚本                │ 底层引擎与算法                  │
├───────────────────────┼─────────────────────────┼─────────────────────────────────┤
│ 1. 路径、流与图论     │ solve_networkx.py       │ NetworkX Dijkstra 最短路        │
│                       │ solve_cpsat.py          │ OR-Tools CP-SAT TSP             │
│                       │ solve_highs.py          │ HiGHS MIP MTZ 约束 TSP          │
│                       │ solve_ortools.py        │ OR-Tools Routing CVRP/VRPTW     │
│                       │ solve_pyvrp.py          │ PyVRP 混合遗传搜索 (HGS)        │
│                       │ solve_network_flow.py   │ NetworkX / OR-Tools 费用流      │
├───────────────────────┼─────────────────────────┼─────────────────────────────────┤
│ 2. 车间生产与工程调度 │ solve_jssp.py           │ PyJobShop CP-SAT JSSP/FJSSP     │
│                       │ solve_rcpsp.py          │ PSPLib CPM + Cumulative CP-SAT  │
│                       │ solve_staff_rostering.py│ OR-Tools CP-SAT 轮班排程        │
├───────────────────────┼─────────────────────────┼─────────────────────────────────┤
│ 3. 选址、枢纽与布局   │ solve_facility.py       │ HiGHS MIP 有容量选址 CFLP       │
│                       │ solve_hub_location.py   │ HiGHS MIP 轴辐式枢纽 p-Hub      │
│                       │ solve_qap.py            │ 线性化 MIP + 禁忌搜索 QAP       │
├───────────────────────┼─────────────────────────┼─────────────────────────────────┤
│ 4. 下料、装箱与几何   │ solve_binpack.py        │ 3D py3dbp / 2D rectpack / 1D MIP│
│                       │ solve_polyomino.py      │ DLX 精确覆盖 / CP-SAT 骨牌平铺  │
│                       │ solve_polyomino_q3.py   │ 异形边界非标多联骨牌填装        │
│                       │ solve_tube_cut_b2026.py │ 列生成 + 几何 DP + ALNS 套裁    │
├───────────────────────┼─────────────────────────┼─────────────────────────────────┤
│ 5. 新能源园区与微电网 │ solve_microgrid.py      │ 凸二次规划 + 滚动时域 MPC       │
├───────────────────────┼─────────────────────────┼─────────────────────────────────┤
│ 6. 批量库存、金融随机 │ solve_lot_sizing.py     │ Wagner-Whitin DP + CLSP MIP     │
│                       │ solve_portfolio.py      │ 马科维茨凸 QP + 风险平价优化    │
│                       │ solve_stochastic_lp.py  │ 两阶段随机规划 (农夫模型 MIP)   │
├───────────────────────┼─────────────────────────┼─────────────────────────────────┤
│ 7. 离散数学与博弈论   │ solve_game_theory.py    │ Nashpy Lemke-Howson 纳什均衡    │
│                       │ solve_max_clique.py     │ 补图对偶精确判定 + CP-SAT       │
│                       │ solve_graph_coloring.py │ DSATUR 启发式 + CP-SAT 图着色   │
│                       │ solve_qubo_ising.py     │ 模拟退火 / 二次无约束二值优化   │
│                       │ solve_mock.py           │ 离线快速回归冻结金标基线        │
└───────────────────────┴─────────────────────────┴─────────────────────────────────┘
```

---

## 2. 分领域详细数学建模与算法原理

### 2.1 图论、路径与流网络（Graph, Routing & Flow）
- **`solve_networkx.py`**：求解非负边权有向图最短路。时间复杂度 $\mathcal{O}(|E| + |V| \log |V|)$，属于精确多项式时间（P 类）算法。
- **`solve_cpsat.py`** 与 **`solve_highs.py`**：针对经典 TSP，分别基于 CP-SAT 的 Circuit 弧环消除约束与 HiGHS MTZ（Miller-Tucker-Zemlin）整数规划消除子回路，小规模规模下（$n \le 50$）确保求得可证全局最优。
- **`solve_ortools.py`**：基于 Google OR-Tools Routing 模块，求解标准 CVRP 与带时间窗 VRPTW，采用 Guided Local Search 搜索高质量可行解。
- **`solve_pyvrp.py`**：基于现代顶级 PyVRP 引擎（Hybrid Genetic Search），处理工业级超大规模多车型车辆路径（VRPTW）与取送货问题（PDP），提供紧致松弛下界对比。
- **`solve_network_flow.py`**：基于容量缩减连续最短路算法与残差网络，求解最小费用最大流，满足物理物料守恒与边容量限制。

### 2.2 车间生产与工程调度（Industrial & Project Scheduling）
- **`solve_jssp.py`**：支持经典作业车间调度（JSSP）与柔性作业车间调度（FJSSP）。采用 `IntervalVar` 与 `AddNoOverlap` 建模机床加工互斥，支持**工件换模时延（Sequence-Dependent Setup Times）**，以最小化最大完工时间（Makespan）为目标，并能导出高精度甘特图。
- **`solve_rcpsp.py`**：符合标准 PSPLib 协议的资源受限项目调度。集成关键路径法（CPM）时差分析与累积资源约束 `AddCumulative`，有效处理活动时序依赖与资源峰值争用。
- **`solve_staff_rostering.py`**：基于 CP-SAT 建模多班次员工/护士排班，严格满足最大连续工作日、夜班后法定休息、每日各班次硬性人力需求，并优化员工排班偏好与方差公平性。

### 2.3 设施选址、枢纽网络与布局（Facility & Hub Location）
- **`solve_facility.py`**：求解经典容量限制设施选址问题（CFLP）与 p-Median 选址。基于 HiGHS 构建混合整数规划（MIP），平衡设施开辟固定成本与客户点到设施的分配运输费用。
- **`solve_hub_location.py`**：求解轴辐式枢纽网络设计（p-Hub Median & USAHLP）。构建 4-index 线性化 MIP，充分利用枢纽间干线运输规模折减系数 $\alpha \in (0, 1)$。
- **`solve_qap.py`**：求解二次分配问题（QAP）。针对经典 QAPLIB 算例，基于 Lawler/Gilmore-Lawler 线性化 MIP 求解小规模实例，对中大规模结合局部搜索提供紧下界。

### 2.4 下料、装箱与空间几何规划（Cutting, Packing & Geometry）
- **`solve_binpack.py`**：三合一全功能装箱求解器：
  - **1D**：基于 OR-Tools MIP 求解最少箱子数装箱与经典 0-1 背包；
  - **2D**：基于 `rectpack` 求解矩形板材几何排样与余料管理；
  - **3D**：基于 `py3dbp` 求解立体集装箱装载，严格校验长宽高旋转三维空间互不重叠。
- **`solve_polyomino.py`** 与 **`solve_polyomino_q3.py`**：基于 DLX（Dancing Links）与 CP-SAT 二进制网格覆盖，处理多联骨牌空间平铺与异形边界覆盖。
- **`solve_tube_cut_b2026.py`**：面向国赛 B 题的重型工业级 3D 异构圆管套裁系统：
  - **Q1**：混合规格原材料选择（9/10/11/12m），基于列生成生成切割模式库，整数主问题由 CP-SAT 快速求解；
  - **Q2**：固定多重集零件分配，基于端向几何状态动态规划（DP）实现毫米级共切刀路计算；
  - **Q3**：自适应大邻域搜索（ALNS）实现多目标联合字典序优化；
  - **Q4**：跨批次动态余料账本管理与多状态束搜索（Beam Search）。

### 2.5 新能源园区与微电网调度（PV-BESS-EV Microgrid）
- **`solve_microgrid.py`**：园区光储充一体化综合能源管理。联合考虑分时电价（TOU）套利、月度需量申报峰值削减（Peak Shaving）、锂电池充放电 C 率损耗与非线性寿命衰减折损模型，结合滚动时域控制（MPC）抵御新能源发电与负荷预测不确定性。

### 2.6 批量库存、投资组合与随机规划（Inventory, Finance & Stochastic）
- **`solve_lot_sizing.py`**：
  - 动态规划：针对无能力限制多阶段批量问题，运行 $O(T^2)$ 经典 Wagner-Whitin 精确 DP 算法；
  - MIP 规划：针对多产品多资源有能力批量问题（CLSP），基于 HiGHS 联合求解生产批量与机器能力冲突。
- **`solve_portfolio.py`**：基于二次规划（QP）求解经典马科维茨均值-方差有效前沿，并集成风险平价（Risk Parity）凸优化模型，实现各类资产风险贡献均衡。
- **`solve_stochastic_lp.py`**：两阶段随机线性规划（经典农夫种植模型），基于 Extensive Form 确定性等价型与 L-shaped（Benders）分解求解。

### 2.7 离散图论、量子启发与博弈论（Discrete Math & Game Theory）
- **`solve_max_clique.py`**：利用图论补图对偶性定理 $\omega(G) = \alpha(\overline{G})$，基于 CP-SAT 与 NetworkX 精确求解最大团与最大独立集。
- **`solve_graph_coloring.py`**：基于 DSATUR 动态饱和度启发式与 CP-SAT 严格隐式枚举，对 DIMACS 标准图着色基准库求解最小着色数 $\chi(G)$。
- **`solve_qubo_ising.py`**：二次无约束二值优化（QUBO）与伊辛模型，采用自适应模拟退火寻找哈密顿量基态能量。
- **`solve_game_theory.py`**：基于 Nashpy，采用 Lemke-Howson 旋转主元法与支撑集枚举法，精确计算双矩阵非合作博弈的全部纯策略与混合策略纳什均衡。
- **`solve_mock.py`**：完全确定性的冻结金标测试桩，为离线 CI 门禁提供秒级回归保障。

---

## 3. 标准输入输出契约与 Numbers Truth 校验

每个求解器必须输出如下标准 JSON Envelope：

```json
{
  "problem_id": "jssp_ft06",
  "problem_class": "jssp",
  "status": "OPTIMAL",
  "objective": 55,
  "solver": "ortools-pyjobshop-cpsat",
  "source": "tools/solve_jssp.py",
  "makespan": 55,
  "proven_optimal": true,
  "optimality_gap": 0.0,
  "lower_bound": 55,
  "meta": {
    "exact": true,
    "proven_optimal": true,
    "method_class": "exact"
  }
}
```

校验器 `tools/validate_solution.py` 会读取问题原始输入，执行：
1. **完全脱离求解器的客观重算**：独立复算工件加工时间、路径距离、电荷平衡等。
2. **DIMO 变异拦截**：拦截 5 类恶意篡改（伪造更优目标、违背物理约束、篡改时间序列维度、翻转完成状态、浮点噪声扰动）。
