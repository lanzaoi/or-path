# Solvers and Validate — 求解算子与独立数学校验法（权威规范）

**对齐：** `AGENTS.md` · `specs/product-flow-sdd.md` · ADR-0002  
**状态：** LAW 2026-11（全量 27 台重型工业求解器 + DIMO 5 类变异验证全覆盖）

---

## 1. 统一接口与调用接缝（Unified Seams）

| 模块文件 | 核心职责 | 约束要求 |
|----------|----------|----------|
| `tools/solve_envelope.py` | 定义标准 JSON Envelope 规范（`status`, `objective`, `solver`, `proven_optimal`, `meta`） | 所有求解器必须返回符合 Envelope 约定的字典 |
| `tools/solve_dispatch.py` | 统一求解调度入口，维护求解器别名映射与参数分发 | 上层业务与 LangGraph 节点统一通过 `solve_dispatch` 路由 |
| `tools/validate_solution.py` | 独立物理校验主入口，不依赖求解器中间状态独立重算 | 必须读取原始输入数据从零复算物理指标与可行性 |
| `tools/validators/` | 细分领域独立物理重算与校验逻辑 | 严禁信任求解器自报的 `objective`，严禁大模型口头验证 |
| `orpath/agents/dimo_mutator.py` | DIMO 5 类不变量变异注入器 | 用于门禁对抗测试，验证校验器是否具有识破篡改能力 |

---

## 2. Numbers Truth 铁律与宣称阶梯（Claim Ladder）

1. **绝对客观原则**：
   - 最优值、路径序列、排产计划、装箱坐标等一切数值，必须 100% 来源于 `tools/solve_*.py` 真实物理运行与 `validate_solution.py` 严格独立重算。
   - 严禁在大模型 Prompt、代码逻辑或论文文本中通过伪造、投票或脑补捏造数值。
2. **宣称诚实律（Honesty Rules）**：
   - 仅当且仅当 `meta.exact == True` 且 `meta.proven_optimal == True` 时，方可在报告或论文中声称“已求得全局最优解（Globally Optimal）”。
   - 针对启发式算法（如 PyVRP、ALNS、遗传算法、退火等），一律报告为 `FEASIBLE`，并汇报真实数学下界与 `Optimality Gap`（若无法求界则诚实说明为“高质量可行解”）。
   - 严禁出现 `proven_optimal == True and exact == False` 的非法 Envelope。

---

## 3. 27 台工业求解器矩阵全谱系（27 Solvers Catalog）

系统内置 27 台工业求解器，覆盖运筹优化 7 大核心领域：

### 3.1 图论、路径与流网络（Graph, Routing & Flow）
1. **`solve_networkx.py`**：基于 NetworkX Dijkstra / Bellman-Ford 的最短路径精确求解器（Class: `shortest_path`）。
2. **`solve_cpsat.py`**：基于 Google OR-Tools CP-SAT 的小规模旅行商问题（TSP）精确求解器（Class: `tsp`）。
3. **`solve_highs.py`**：基于 HiGHS MIP (MTZ 约束) 的经典 TSP 精确求解器（Class: `tsp`）。
4. **`solve_ortools.py`**：基于 Google OR-Tools Routing 引擎的带容量/时间窗车辆路径规划器（Class: `vrp`, `vrptw`）。
5. **`solve_pyvrp.py`**：基于 PyVRP 混合遗传搜索算法（HGS）的工业级大规模 VRPTW 与取送货 PDP 求解器（Class: `pyvrp`, `vrptw`, `pdp`）。
6. **`solve_network_flow.py`**：基于 NetworkX / OR-Tools 的最小费用最大流（Min-Cost Max-Flow）与最大流割问题求解器（Class: `network_flow`）。

### 3.2 工业生产与工程调度（Industrial & Project Scheduling）
7. **`solve_jssp.py`**：基于 PyJobShop / CP-SAT 的作业车间调度（JSSP）与柔性作业车间调度（FJSSP）求解器，支持换模时延（Setup Times）与甘特图导出（Class: `jssp`, `fjssp`）。
8. **`solve_rcpsp.py`**：基于 PSPLib 标准规范的资源受限项目调度（RCPSP）求解器，集成关键路径法 CPM 与 Cumulative CP-SAT（Class: `rcpsp`）。
9. **`solve_staff_rostering.py`**：基于 CP-SAT 的护士排班/多班次员工排程求解器，满足硬性工时法规与软性偏好（Class: `staff_rostering`）。

### 3.3 设施选址、网络中枢与布局（Facility & Hub Location）
10. **`solve_facility.py`**：基于 HiGHS MIP 的有容量限制设施选址（CFLP）与 p-Median 优化求解器（Class: `facility_location`）。
11. **`solve_hub_location.py`**：基于 HiGHS MIP 的航空/物流轴辐式网络枢纽选址求解器（Class: `hub_location`, `p_hub`, `usahlp`）。
12. **`solve_qap.py`**：基于线性化 MIP 与局部禁忌搜索的二次分配问题求解器（Class: `qap`, `quadratic_assignment`）。

### 3.4 下料、装箱与空间几何规划（Cutting, Packing & Geometry）
13. **`solve_binpack.py`**：三合一全功能装箱求解器，支持 1D MIP 背包/装箱、2D 矩形板材排样（rectpack）、3D 立体集装箱装载（py3dbp）（Class: `bin_packing`）。
14. **`solve_polyomino.py`**：基于 DLX 精确覆盖与 CP-SAT 的多联骨牌平面精确平铺求解器（Class: `polyomino_cover`）。
15. **`solve_polyomino_q3.py`**：面向非标准异形边界的多联骨牌填装优化求解器（Class: `polyomino_q3`）。
16. **`solve_tube_cut_b2026.py`**：工业级 3D 异构圆管套裁混合引擎（列生成 + CP-SAT + 端头几何 DP + ALNS 联合共切优化）（Class: `tube_cut`）。

### 3.5 新能源园区与微电网储能调度（Campus PV-BESS-EV Microgrid）
17. **`solve_microgrid.py`**：园区光储充一体化微电网调度求解器，涵盖分时电价套利、需量削峰、电池寿命衰减非线性折损、滚动时域 MPC（Class: `microgrid`）。

### 3.6 库存批量、投资组合与随机规划（Inventory, Finance & Stochastic）
18. **`solve_lot_sizing.py`**：涵盖经典 Wagner-Whitin 动态规划与有能力多产品批量规划 CLSP 的生产库存求解器（Class: `lot_sizing`, `wagner_whitin`, `clsp`）。
19. **`solve_portfolio.py`**：基于凸二次规划（QP）的马科维茨均值-方差组合优化与风险平价（Risk Parity）资产配置求解器（Class: `portfolio`）。
20. **`solve_stochastic_lp.py`**：两阶段随机线性规划求解器（经典农夫问题 Extensive MIP 与 L-shaped 分解）（Class: `stochastic_lp`, `two_stage_lp`）。

### 3.7 离散图论、量子启发式与博弈论（Discrete Math & Game Theory）
21. **`solve_max_clique.py`**：最大团与最大独立集双模式求解器，利用补图对偶性精确判定（Class: `max_clique`, `max_independent_set`）。
22. **`solve_graph_coloring.py`**：基于 DSATUR 启发式与 CP-SAT 精确求解的图着色优化求解器（Class: `graph_coloring`, `vertex_coloring`）。
23. **`solve_qubo_ising.py`**：伊辛模型与二次无约束二值优化（QUBO）模拟退火与基态寻优器（Class: `qubo_ising`）。
24. **`solve_game_theory.py`**：基于 Lemke-Howson 与支撑集枚举的双矩阵博弈纳什均衡求解器（Class: `game_theory`, `nash_equilibrium`）。
25. **`solve_mock.py`**：确定性冻结基线桩，提供离线测试与极速门禁回归（Class: `mock`）。

---

## 4. 独立数学校验器与 DIMO 5 类变异防御（DIMO Rejection）

所有求解器产出的解必须经受 `tools/validate_solution.py` 与 `tools/validators/` 的严苛物理重算：

### 4.1 核心验算准则
1. **结构合法性**：校验 Envelope 字段完整性、物理对象存在性。
2. **原始物理复算**：从原始问题输入从零仿真行车路线、工件加工时延、余料剪切长度、光储充功率平衡，将复算得到的目标值与求解器自报值比对，误差超过容限立即驳回。
3. **硬约束绝不妥协**：容量越限、时间窗冲突、工序次序倒置、物料不守恒均判定为 `VALIDATION_FAILED`。

### 4.2 DIMO 5 类对抗性变异检验
`orpath/agents/dimo_mutator.py` 会对解注入 5 类恶意篡改，校验器必须 100% 拦截：
- **Target（篡改目标值）**：自报数值比实际物理重算更优，校验器必须当场识破。
- **Constraint（破坏硬约束）**：违背载重、超出手工时限制或交货期违约，校验器必须报错。
- **Dimension（伪造物理维度）**：篡改板材厚度、坐标系维度或遗漏加工工序，校验器必须拦截。
- **State（翻转物理状态）**：将未被满足的需求标记为完成，或虚假翻转布尔决策变量，校验器必须识别。
- **Perturbation（微小数值扰动）**：施加微小浮点扰动使得守恒定律破缺，校验器必须拒绝。

---

## 5. 特殊领域求解约束（Tube v2 与 CVRPTW 铁律）

### 5.1 Tube v2 圆管套裁约束
1. Q1 必须允许 9000/10000/11000/12000 mm 在同一方案中混合选择；实现为列生成模式库 + CP-SAT 整数主问题。
2. 固定序列的 L/R 朝向用两状态动态规划精确求解，不得在长序列退化成逐件贪心。
3. Q2 固定 Q1 每根母材的工件多重集合；只允许修改顺序和端向。
4. Q3 使用字典序 `(总母材长度, -总共切收益, 切换次数)`；联合 ALNS 为可复现启发式，不宣称最优。
5. Q4 使用带编号余料库存和多状态束搜索；逐批满足物料守恒，目标只累计新购标准母材。
6. 求解输出必须携带 `orpath.tube_model.v2` 模型快照；validator 逐根重算需求、几何收益、占用、余料、利用率、Q2 分配和 Q4 库存。超长方案必须拒绝，禁止缩放数字“修复”。
7. 随机搜索必须写入 seed；默认 `20260813`。

### 5.2 CVRPTW 规约
- 金标基准与到达/离开时间窗推演必须完全遵循时序一致性，仿真到达与服务开始窗重叠，严禁负耗时与超载行驶。

---

## 6. 命令行调用与自测速查

```bash
# 统一求解调度
.venv/bin/python tools/solve_dispatch.py <problem_id> --mode <mode>

# 统一独立校验
.venv/bin/python tools/validate_solution.py --problem-id <problem_id> --solution <solution_path.json>

# 变异对抗红队门禁
.venv/bin/python scripts/universal_redteam_gate.py
```
