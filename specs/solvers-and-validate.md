# Solvers and Validate — 求解与校验

## 命名诚实

| 工具 | 含义 |
|------|------|
| `tools/solve_mock.py` | 读冻结 `fixtures/**/solution.json` |
| `tools/solve_networkx.py` | **NetworkX** 最短路等（自 T1 误名 `solve_ortools` 迁出） |
| `tools/solve_ortools.py` | **真 Google OR-Tools** |
| `tools/validate_solution.py` | 重算与可行性；写 ValidateReport |

禁止再把 NetworkX 脚本标成 `ortools`。

## solve_mode

| mode | 用途 |
|------|------|
| `mock` | CI 快速、负例、paper 绑定 |
| `networkx` | SP 主路径之一；objective 与经典 fixture **42** 对齐 |
| `ortools` | TSP / VRP **门禁必跑**；SP 可选交叉验证 |

## 问题类矩阵（T2）

| class | mock | networkx | ortools | fixture 规模 |
|-------|------|----------|---------|--------------|
| shortest_path | 必 | 必（Dijkstra） | 可选 | 保持 T1 图或 t2 副本 |
| tsp | 必 | 非金标 | **必** Routing | **n=8** |
| vrp | 必 | 否 | **必** | **≥2 车** + 容量；**无 TW**；单车不可行 |

金标 `solution.json`：**仅**允许由 `scripts/freeze_fixture_from_solver.py`（或等价）从绿解冻结后人工确认入库。禁止手编散文数字当 objective。

## OR-Tools 要求

- 依赖：`ortools` 已装入 `.venv-314` 则 `t2_gate` **不得**因「可选跳过」而跳过 TSP/VRP ortools 用例  
- 输出必须符合 `contracts.md` Solution  
- `solver` 字段标明具体后端，如 `ortools-routing`  
- 确定性：固定 seed / 参数写入 `meta` 以便复现  

## Validate 硬检查

### 通用

1. **envelope：** 必填字段、status 枚举、problem_class 一致  
2. **gold_gap（若有金标）：** `|objective - gold| ≤ eps`（状态均为 OPTIMAL/FEASIBLE 时）

### shortest_path

3. `path` 连续边存在于 graph  
4. 边权之和 == `objective`（容差内）

### tsp

3. `tour` 含全部节点恰好一次（起终点重复除外）  
4. 回到起点  
5. 矩阵费用之和 == `objective`

### vrp

3. 每个客户恰好服务一次  
4. 每车路线容量 ≤ capacity  
5. **vehicle_count ≥ 2** 的实例上：若强制 1 车应不可行（可用独立负例测）  
6. 路线费用之和 == `objective`  
7. **不做**时间窗检查（T2 无 TW）

### 负例（必须）

- 篡改 objective → validate 红  
- 断路 path/tour → 红  
- VRP 超容量 → 红  
- schema 含 objective → schema gate 红  

## 调参白名单（validate 红后，Q12-C）

允许自动搜索的参数（实现可子集，但必须文档化于 tune log）：

- `time_limit_ms` / 等价  
- `first_solution_strategy`（枚举有限集合）  
- `local_search_metaheuristic`（枚举有限集合）  
- `random_seed`  

**禁止**自动：

- 改 demands/capacities/边权（那是 model 的事）  
- 改 objective 字段  
- 任意 exec LLM 生成的代码  

默认 `max_solver_tune = 3`。Mock 模式跳过调参。

## CLI 约定

```text
python tools/solve_ortools.py <problem_id> [--class tsp|vrp|shortest_path]
python tools/validate_solution.py --problem <fixture_dir|id> --solution path.json
```

- 成功：solution/validate JSON 到 stdout 或 `--out`  
- 失败：exit ≠ 0；stderr 可读  

## 与 LG 集成

见 `control-plane.md`：solve → gate_validate → tune → model → HUMAN_REQUIRED。
