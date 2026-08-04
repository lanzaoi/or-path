# Contracts — 数据契约（详细）

**对齐：** `product-flow-sdd.md`  
**状态：** LAW 2026-08-01

---

## 1. 原则

1. **单一形状源：** pydantic（如 `tools/schema_models.py`）可导出到 `contracts/`  
2. **Modeler schema 禁止最优/解答键**  
3. **数字权威：** 仅 Solution 经 solve 后进入 explain/paper  
4. 变更：改模型 + 测试 + 本 spec + 必要时 fixture  

---

## 2. ProblemSchema（modeler）

### 2.1 必填逻辑

- `problem_id`: string  
- `problem_class`: 已注册枚举（基线 `shortest_path` | `tsp` | `vrp`；扩展须注册）  

### 2.2 禁止键（递归扫 key，大小写不敏感）

```text
objective, optimal, objective_value, optima, optimal_value, optimal_cost,
tour, routes, path   # 作为「解答」禁止
```

说明：

- SP 用 `nodes`+`edges`，**不要**答案 path  
- TSP 用 matrix/coords，不要 tour  
- VRP 用 depot/demands/…，不要 routes  

### 2.3 shortest_path

- `nodes`: string[]  
- `edges`: `{u,v,w}[]`  
- 可选 source/target  

### 2.4 tsp

- n 或由 matrix 推  
- `distance_matrix` 或 `coords`  
- T2 目标 n=8  

### 2.5 vrp

- depot、locations/matrix、demands  
- vehicle_count ≥2（T2）  
- capacities  
- T2 无 TW；TW 见 solvers-and-validate.md §11 / fixture 级 time_windows  

### 2.6 扩展 class

新 class 必须：contracts 更新 + dispatch + validate +（若 intake）hint + 总流程登记。

---

## 3. Solution

```json
{
  "problem_id": "tsp_n8",
  "problem_class": "tsp",
  "status": "OPTIMAL",
  "objective": 0,
  "solver": "…",
  "source": "tools/…",
  "path": null,
  "tour": ["0", "1", "…", "0"],
  "routes": null,
  "meta": {
    "exact": true,
    "proven_optimal": true,
    "method_class": "exact"
  }
}
```

| status | 含义 |
|--------|------|
| OPTIMAL | 宣称最优 |
| FEASIBLE | 可行非证优 |
| INFEASIBLE | 不可行 |
| ERROR | 工具错误 |
| BLOCKED | 产品拒绝求解（无 adapter 等） |

| class | 解答字段 |
|-------|----------|
| shortest_path | path |
| tsp | tour |
| vrp | routes |
| BLOCKED | objective 可为 null |

---

## 4. ValidateReport

逻辑字段：ok、checks[]、recomputed_objective、errors/detail。  
路径：`outputs/<slug>-validate.json`（或约定）。

---

## 5. Intake（1.1）

见 `problem-intake.md` 与 `contracts/intake.json`。  
要点：无 solution 禁键；sources[].path 允许；顶层 path 答案键禁止。

---

## 6. Timeline JSON（M0 目标契约）

```json
{
  "schema_version": 1,
  "slug": "m0",
  "thread_id": "m0",
  "live_subagent": true,
  "summary": {},
  "stages": [],
  "subagents": [],
  "repairs": [],
  "raw_paths": {}
}
```

详细事件枚举 → `process-visibility.md`。

---

## 7. Retrieval hit

应含 `chunk_id`（可引用）；空列表合法。  
形状见 `contracts/retrieval_hit.json` 若存在。

---

## 8. 变更流程

1. 改 pydantic / JSON schema  
2. 单测边界（空/None/非法键）  
3. 更新本文件  
4.  bump fixture 若金标形状变  
5. 相关 gate 绿  

---

## 9. 参考

`contracts/*.json` · `solvers-and-validate.md` · `problem-intake.md`  
