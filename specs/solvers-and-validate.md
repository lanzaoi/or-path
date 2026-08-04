# Solvers and Validate — 求解与校验（详细）

**对齐：** `product-flow-sdd.md` · ADR-0002  
**状态：** LAW 2026-08-01

---

## 1. 统一接缝

| 模块 | 职责 |
|------|------|
| `tools/solve_envelope.py` | status/objective/source/shape/meta 接口 |
| `tools/solve_dispatch.py` | **唯一调度** solve()/validate() + adapter 表 |
| `orpath` gates/nodes | 只调 dispatch，不写死脚本名 |
| `tools/solve_*.py` | 适配器实现 |

```text
python tools/solve_dispatch.py <problem_id> --mode mock|networkx|cpsat|highs|ortools|tube|...
python tools/validate_solution.py --problem-id <id> --solution path.json
```

---

## 2. 命名诚实

| 工具 | 含义 | exact? |
|------|------|--------|
| solve_mock | 冻结 fixture | fixture |
| solve_networkx | Dijkstra SP | ✅ |
| solve_cpsat | CP-SAT 小 TSP | ✅ |
| solve_highs | HiGHS MTZ TSP | ✅ |
| solve_ortools | Routing 实用搜索 | ❌ |
| solve_tube_cut_b2026 | 圆管 BFD | ❌ FEASIBLE |
| solve_polyomino* | 骨牌 **polyomino_cover**（M2：已注册 dispatch；validate 见阶段 2） | CP-SAT exact 视 meta |
| validate_solution | 重算与可行性 | — |

禁止：NetworkX 标 ortools；Routing/BFD 宣传 proven optimal。

---

## 3. 宣传原则

| 可 | 不可 |
|----|------|
| 精确轨规模内 proven + validate | 「启发式所以先进」 |
| Routing 作规模/性价比 | Routing= MIP 最优 |
| BLOCKED 诚实 | intake 假绑 SP 42 |

---

## 4. solve_mode 与默认策略

| mode | 用途 |
|------|------|
| mock | CI/金标 |
| networkx | SP 默认宣传 |
| cpsat | TSP 默认宣传 |
| highs | TSP 对照 |
| ortools | VRP/TW/扩展 |
| tube | 圆管 |
| polyomino | 多联骨牌覆盖（M2） |

| class | 默认 | 金标例 |
|-------|------|--------|
| shortest_path | networkx | 42 |
| tsp | cpsat | n=8 → 45 |
| vrp / tw | ortools 诚实 | 58 |
| polyomino_cover | polyomino | fixtures/t3/polyomino_b_q1 |

---

## 5. Solution meta 强制

```text
meta.exact: bool
meta.proven_optimal: bool
meta.method_class: exact | metaheuristic | fixture
```

envelope：`proven_optimal and not exact` → 非法。

status：`OPTIMAL` | `FEASIBLE` | `INFEASIBLE` | `ERROR` | `BLOCKED`（产品扩展，intake 无 adapter）

---

## 6. Validate 硬检查

- envelope 形状  
- 覆盖/回路/容量  
- TW 若有：服务开始窗  
- objective **重算一致**  
- 可选 gold_gap  

BLOCKED solution：validate **短路径** 不得假装调参修复出假优。

---

## 7. 调参白名单（仅 ortools 类）

- time_limit_ms、first_solution、metaheuristic、seed（seed 可仅 meta）  
- **禁止**改 objective/需求/边权  
- 精确轨/mock：不走调参阶梯  

计数器 → `control-plane.md`。

---

## 8. 域 adapter 注册法（产品扩展）

新问题类入产品必须：

1. `ADAPTER_SCRIPTS` 注册  
2. schema class 白名单 / alias（如 polyomino_cover→polyomino）  
3. validate 规则  
4. intake class hint（若走题面）  
5. **REGISTERED_INTAKE_CLASSES** 与 BLOCKED 逻辑一致  
6. fixture 或可重复命令  
7. 更新本文件 + contracts + 总流程缺口表  

未完成 1–5：**禁止**宣称该域产品已接通。

---

## 9. CLI 速查

```text
python tools/solve_dispatch.py <id> --mode ...
python tools/solve_networkx.py <id>
python tools/solve_cpsat.py <id>
python tools/solve_ortools.py <id> [--class tsp|vrp]
python tools/validate_solution.py --problem-id <id> --solution path.json
```

---

## 10. 参考

`docs/solver-stack.md` · `contracts.md` · ADR-0002

---

## 11. CVRPTW 叶（原 `t3-vrp-tw.md`）

| 项 | 值 |
|----|-----|
| Fixture | `fixtures/t3/vrp_tw/` |
| class | 仍为 `vrp`；TW 在 fixture 级 |
| Gold objective | **58**（仅 solver+validate） |
| Solve | `tools/solve_ortools.py` Time dimension；目标仍为距离 |
| Validate | 有 TW：仿真到达与服务开始 |
| 门禁 | 含于 `scripts/t3_gate.py` |
| 非目标 | 新枚举名 `vrp_tw` 当整 T3 故事 |

fixture_dir 解析顺序：**t3 → t2 → t1**。

```bat
.venv-314\Scripts\python.exe scripts	3_gate.py
.venv-314\Scripts\python.exe tools\solve_ortools.py vrp_tw --class vrp
```

