# OR-Path 求解器组合（深度选型结论）

**原则（用户校正）：**  
作品集/对外宣传主轴 = **可验证的精确解 + validate 重算**。  
启发式/元启发式 = **性价比与规模扩展轨**，**不当卖点、不单独当招牌**。

**产品约束：** 本地 Python、可 CI、开源默认可复现、多智能体只调 `solve_*`、数字经 `validate`。

---

## 1. 最终组合（推荐锁定）

| 层级 | 引擎 | 问题类 | 宣传口径 | `solve_mode` | 角色 |
|------|------|--------|----------|--------------|------|
| **L0 金标** | fixture mock | 全 class | 「门禁绑定冻结解」 | `mock` | CI / 负例 / 无求解器环境 |
| **L1 精确·图** | **NetworkX Dijkstra** | shortest_path | 「多项式精确最短路」 | `networkx` | **SP 默认宣传轨** |
| **L2 精确·组合** | **OR-Tools CP-SAT**（circuit 等） | TSP（小 n，如 ≤20） | 「约束规划可证最优」 | `cpsat` | **TSP 默认宣传轨** |
| **L3 精确·MIP** | **HiGHS**（MTZ/TSP 或小 VRP） | TSP；极小 CVRP | 「开源 MIP 可证最优」 | `highs` | **精确对照轨 / 双证** |
| **L4 实用·路由** | **OR-Tools Routing** | TSP / CVRP / CVRPTW | 「规模扩展用的路由搜索（**非**证明最优）」 | `ortools` | **扩展轨**，门禁可跑，**话术降级** |
| **L5（可选后置）** | VROOM | 真路网 VRP | 「工程路由引擎」 | `vroom` | 地图/OSRM 后再上 |
| **L6（可选旁注）** | Gurobi/Hexaly academic | 对照 | 仅 benchmark 脚注 | 不进默认 gate | 许可敏感 |

### 一句话产品叙事（正确）

> 对可精确类问题用 **Dijkstra / CP-SAT / HiGHS** 求 **可证最优**，一律 **validate 重算**；  
> 对更大 VRP 用 **OR-Tools Routing 作实用扩展**，明确 **非证明最优**，仍经 validate。

### 错误叙事（禁止）

- 「我们用启发式所以很先进」  
- 「OR-Tools 保证全局最优」  
- 把 Routing 的 `OPTIMAL` 标签当 MIP 意义的 proven optimal 对外吹  

---

## 2. 为什么是这套（按问题类）

### 2.1 最短路 → NetworkX（L1）独占宣传

| 候选 | 结论 |
|------|------|
| NetworkX Dijkstra | **胜出**：精确、标准、教学清晰、已集成 |
| OR-Tools flow | 能，但无必要替代图算法课叙事 |
| HiGHS/Gurobi | 杀鸡用牛刀 |

非负权最短路是 **P 问题**；宣传「精确算法」完全成立。

### 2.2 TSP → CP-SAT 主宣传 + HiGHS 双证 + Routing 扩展

| 候选 | 精确? | 小 n=8 | 宣传 |
|------|-------|--------|------|
| **CP-SAT circuit** | 可证 | 极快、合适 | **主推** |
| **HiGHS MTZ/MIP** | 可证 | 合适 | 双证/对照 |
| OR-Tools Routing | 元启发式 | 快但非证明 | 扩展 only |
| Gurobi | 可证 | 强但许可 | 不默认 |

小 TSP（作品集 n=8）**必须**能讲 proven optimal；Routing 可继续跑，但 **claim ladder 不以其为招牌**。

### 2.3 CVRP / CVRPTW → 分层

| 规模 | 推荐 | 宣传 |
|------|------|------|
| 极小（客户很少） | HiGHS/SCIP 式 MIP（若实现） | 可证最优（声明规模上限） |
| 作品集多车+TW（当前 fixture） | **Routing 出可行解 + validate** | 「可行+重算」；**不**称全局最优 |
| 大/真路网 | VROOM 后置 | 工程扩展 |

VRP 是 NP-hard：诚实产品 = **小实例精确 + 大实例实用搜索 + 始终 validate**，而不是假装 Routing = 最优证明。

---

## 3. 和「只 OR-Tools」比，组合赢在哪

| | 单 OR-Tools Routing | 本组合 |
|--|---------------------|--------|
| 宣传是否站得住 | 弱（启发式当招牌易被问穿） | **强**（精确轨可证 + validate） |
| SP | 绕 | Dijkstra 干净 |
| 小 TSP | 能跑，难称 proven | CP-SAT/HiGHS 可称 |
| 中大 VRP | 强项 | 保留为 L4 |
| CI/开源 | 好 | 仍然全开源默认 |
| 实现成本 | 低 | 中（多 `solve_*`，统一契约） |

---

## 4. 默认策略（产品逻辑）

```text
shortest_path  → networkx（精确）     [fallback mock]
tsp            → cpsat（精确）         [对照 highs；扩展 ortools]
vrp / vrp_tw   → ortools（实用）       [可选 highs 极小实例；永远 validate]
CI 无求解器    → mock
```

`meta` 强制字段（实现目标）：

```json
{
  "exact": true,
  "proven_optimal": true,
  "method_class": "exact"  
}
```

Routing 输出必须：

```json
{
  "exact": false,
  "proven_optimal": false,
  "method_class": "metaheuristic"
}
```

`status`：精确证明用 `OPTIMAL`；Routing 最佳用 `FEASIBLE` 或保留兼容但 **meta 必写清**。

---

## 5. 明确不进默认组合

| 引擎 | 原因 |
|------|------|
| jsprit / OptaPlanner | Java 异栈，主仓成本高 |
| Hexaly / Gurobi 默认 | 许可与复现；最多 academic 对照 |
| 纯 NetworkX 硬解 TSP/VRP | 理论错误用法 |
| 多引擎并列当「三个主品牌」 | 叙事乱；主品牌是 **精确+validate** |

---

## 6. 实现落点（与代码对齐）

| 文件 | 职责 |
|------|------|
| `tools/solve_networkx.py` | L1 SP exact |
| `tools/solve_cpsat.py` | L2 TSP exact（CP-SAT） |
| `tools/solve_highs.py` | L3 TSP(/tiny VRP) MIP exact |
| `tools/solve_ortools.py` | L4 routing；meta 标明非 proven |
| `tools/solve_mock.py` | L0 |
| `tools/validate_solution.py` | 全模式统一重算 |
| `orpath/gates.py` | 按 mode 分发 |
| `specs/solvers-and-validate.md` | 本法 |
| 本文件 | 选型备忘与 claim ladder |

---

## 7. 参考文献向（选型依据摘要）

- OR-Tools：开源套件，强在 routing / CP 等；Routing 为搜索框架，非通用「证明最优 MIP」。  
- CP-SAT：组合精确的有力开源选项；小 TSP 用 circuit 模型可证。  
- HiGHS：开源 MIP 主力之一，作精确对照合适。  
- VROOM：真路网 VRP 工程引擎，后置。  
- 商业 Gurobi/Hexaly：性能强，默认栈排除因许可/复现。

（细节与基准见会话内调研；厂商 VRP 基准有偏差，不作唯一依据。）

---

## 8. 冻结建议

**OR-Path 官方求解器组合 =**

> **NetworkX（SP 精确） + CP-SAT（TSP 精确） + HiGHS（精确对照）  
> \+ OR-Tools Routing（VRP/规模扩展，非宣传主轴）  
> \+ mock（CI）  
> \+ 全局 validate**

启发式只回答「大了怎么办」，不回答「我们凭什么说最优」。
