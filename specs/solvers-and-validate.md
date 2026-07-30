# Solvers and Validate — 求解与校验

## 统一接缝（ADR-0002）

| 模块 | 职责 |
|------|------|
| `tools/solve_envelope.py` | solution **接口**：status / objective / source / shape / meta |
| `tools/solve_dispatch.py` | **唯一调度**：`solve()` / `validate()` + adapter 表 |
| `orpath/gates.py` | LG 节点只调 dispatch，不直写脚本名 |
| `tools/solve_*.py` | **适配器**（实现） |
| `scripts/b_tube_*.py` | **薄 CLI / 遗留**；圆管权威 = `solve_tube_cut_b2026.py` |

```text
python tools/solve_dispatch.py <problem_id> --mode mock|networkx|cpsat|highs|ortools|tube
python tools/validate_solution.py --problem-id <id> --solution path.json
```

## 命名诚实

| 工具 | 含义 |
|------|------|
| `tools/solve_mock.py` | 读冻结 `fixtures/**/solution.json` |
| `tools/solve_networkx.py` | **NetworkX Dijkstra** — **精确**最短路 |
| `tools/solve_cpsat.py` | **OR-Tools CP-SAT circuit** — **精确**小 TSP |
| `tools/solve_highs.py` | **HiGHS MTZ MIP** — **精确**小 TSP 对照 |
| `tools/solve_ortools.py` | **OR-Tools Routing** — 实用搜索轨（**非**证明最优） |
| `tools/solve_tube_cut_b2026.py` | 圆管 BFD/启发式 — **FEASIBLE only** |
| `tools/validate_solution.py` | 重算与可行性；写 ValidateReport |

禁止再把 NetworkX 标成 ortools；禁止把 Routing/BFD 宣传成 proven optimal。

权威组合与 claim ladder：`docs/solver-stack.md`。

## 宣传原则（硬）

| 可宣传 | 不可宣传 |
|--------|----------|
| Dijkstra / CP-SAT / HiGHS 在声明规模内 **proven optimal** | 「启发式所以先进」 |
| 一律 **validate 重算** | Routing `status` 暗示 MIP 意义最优 |
| Routing 作 **规模扩展 / 性价比** | 抄厂商 SOTA gap 当本仓成绩 |

## solve_mode

| mode | 用途 | exact? |
|------|------|--------|
| `mock` | CI / 负例 / 绑定金标 | fixture |
| `networkx` | **SP 默认宣传轨** | ✅ |
| `cpsat` | **TSP 默认宣传轨** | ✅ |
| `highs` | TSP 精确对照 | ✅ |
| `ortools` | VRP/TW 与规模扩展；TSP 扩展对照 | ❌ metaheuristic |
| `tube` / `tube_bfd` | 圆管下料 BFD | ❌ heuristic |

## 问题类默认策略

| class | 宣传默认 | 扩展 | fixture |
|-------|----------|------|---------|
| shortest_path | networkx | mock | SP **42** |
| tsp | **cpsat**（+ highs 双证） | ortools | n=8 **45** |
| vrp / vrp_tw | ortools + validate（诚实非证明） | 日后 tiny MIP | multi **58** / tw **58** |

## meta 强制语义

所有 solution JSON 应带：

- `meta.exact`: bool  
- `meta.proven_optimal`: bool  
- `meta.method_class`: `exact` \| `metaheuristic` \| `fixture`  

Routing 输出 `status` 宜为 `FEASIBLE`（兼容门禁可读 OPTIMAL/FEASIBLE）；精确证明用 `OPTIMAL` 且 `proven_optimal=true`。

## Validate 硬检查

（同前：envelope、coverage、容量、TW 若有、objective 重算、gold_gap。）

T3+ TW：有 `time_windows` 时必须检查服务开始时间窗。

## 调参白名单（仅 ortools / 非精确轨）

- `time_limit_ms`、first_solution、metaheuristic、seed  
- **禁止**改 objective / 需求 / 边权  
- Mock / cpsat / highs / networkx：**不走**启发式调参阶梯（失败直接 model 或 HUMAN）

## CLI

```text
python tools/solve_dispatch.py <id> --mode mock|networkx|cpsat|highs|ortools|tube
python tools/solve_networkx.py <id>          # adapter direct
python tools/solve_cpsat.py <id>
python tools/solve_highs.py <id>
python tools/solve_ortools.py <id> [--class tsp|vrp|shortest_path]
python tools/solve_tube_cut_b2026.py         # tube adapter (writes outputs/b-tube-cut)
python scripts/b_tube_solve.py               # thin → tube adapter + envelope
python tools/validate_solution.py --problem-id <id> --solution path.json
```
