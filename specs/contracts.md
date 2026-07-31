# Contracts — 数据契约

## 原则

1. **单一形状源：** pydantic 模型（如 `tools/schema_models.py`）可导出 JSON Schema 到 `contracts/`。  
2. **Modeler schema 禁止最优：** 任何 solution 形状字段不得出现在 problem schema。  
3. **数字权威：** 仅 `Solution` 经 solve 工具产生后，方可进入 explain/paper。  
4. 变更契约必须：改模型 + 测试 + 本 spec + 必要时 bump fixture。

## ProblemSchema（modeler 输出）

**用途：** 描述问题，供 solve 工具编译/读取。

**必填（逻辑）：**

- `problem_id`: string  
- `problem_class`: `"shortest_path" | "tsp" | "vrp"`  
- 随 class 的结构字段（见下）

**禁止键（大小写不敏感，递归扫 key）：**

```text
objective, optimal, objective_value, optima, optimal_value, optimal_cost,
tour, routes, path   # path/tour/routes 作为「解答」禁止；
```

说明：若 SP 建模需要边列表，用 `nodes` + `edges`（边为 `{u,v,w}`），**不要**输出答案 `path`。  
TSP 用 `distance_matrix` 或 `coords`，不要输出 `tour`。  
VRP 用 `depot`, `locations`, `demands`, `vehicle_count`, `capacities` 等，不要输出 `routes`。

### shortest_path

- `nodes`: string[]  
- `edges`: `{u, v, w}[]`  
- 可选 `source`, `target`（默认 fixture 约定）

### tsp

- `n` 或由 matrix 推导  
- `distance_matrix`: 方阵 number[][] **或** `coords`: `{id, x, y}[]`  
- T2 fixture 目标规模：**n=8**

### vrp

- `depot`: id  
- `locations` / matrix  
- `demands`: 与节点对齐  
- `vehicle_count`: **≥ 2**（T2）  
- `capacities`: 每车容量  
- **T2 不做** `time_windows`  
- 设计约束：存在 **单车不可行、多车可行** 的容量设定（fixture 必须体现）

## Solution（solve 工具 stdout / 文件）

```json
{
  "problem_id": "tsp_n8",
  "problem_class": "tsp",
  "status": "OPTIMAL",
  "objective": 0,
  "solver": "ortools-routing",
  "source": "tools/solve_ortools.py",
  "path": null,
  "tour": ["0", "1", "...", "0"],
  "routes": null,
  "meta": {}
}
```

| status | 含义 |
|--------|------|
| `OPTIMAL` | 求解器宣称最优 |
| `FEASIBLE` | 可行非证优 |
| `INFEASIBLE` | 不可行 |
| `ERROR` | 工具错误 |

**class 必填解字段：**

| class | 必填 |
|-------|------|
| shortest_path | `path`（节点序列） |
| tsp | `tour`（含回到起点） |
| vrp | `routes`（`[[node,...], ...]` 每车一条；可含 depot） |

`objective` 必须为 number；优先与重算一致的可 JSON 数值。

## ValidateReport

```json
{
  "ok": true,
  "problem_id": "...",
  "problem_class": "...",
  "checks": [
    {"name": "envelope", "ok": true},
    {"name": "recompute_objective", "ok": true, "expected": 42, "got": 42},
    {"name": "feasibility", "ok": true},
    {"name": "capacity", "ok": true},
    {"name": "gold_gap", "ok": true, "gap": 0.0}
  ],
  "errors": []
}
```

- `ok` 当且仅当全部硬 check 通过  
- 浮点比较：相对/绝对容差在实现中固定并单测（如 abs ≤ 1e-6 或相对 1e-9）

## Chunk

- `chunk_id`: 稳定唯一  
- `doc_id`  
- `text`  
- `source_path`  
- 可选：`page`, `mineru_job_id`, `title`

## RetrievalHit

- `chunk_id`  
- `score`  
- `backend`: `lightrag | bm25 | fts | seed | rrf`  
- `snippet`  
- 可选：`source_path`

## RetrievalArtifact（`notes/<slug>-retrieval.json`）

```json
{
  "query": "...",
  "knowledge_mode": "hybrid",
  "hits": [ /* RetrievalHit */ ],
  "seed_facts": [ /* optional */ ]
}
```

## IntakeArtifact（1.1 · `outputs/<slug>-intake.json`）

权威字段表与禁键：`specs/problem-intake.md` §6。

**原则：**

1. intake **不是** ProblemSchema，也 **不是** Solution。  
2. 递归禁止 solution 形状键（与 Modeler 禁键同精神）：  
   `objective`, `optimal`, `objective_value`, `optima`, `tour`, `routes`, …  
   顶层/任意嵌套的解答形 `path` 亦禁；**例外：** `sources[]` / `data_assets[]` 元素上的文件 `path` 字段允许（见 `gate_intake.walk_forbidden_intake_keys`）。  
3. 必填逻辑：`slug`, `schema_version` (`"1.1.0"`), `status`, `sources`, `subproblems`,  
   `data_assets`, `constraints_text`, `objectives_text`, `deliverables`, `ambiguities`,  
   `brief_path`, `ocr_raw_path`, `ocr_meta_path`, `ocr_backend`。  
4. `problem_class_hint` / `problem_id_hint` 仅为软提示。  
5. 伴随制品：`notes/<slug>-ocr.raw.md`、`notes/<slug>-ocr.meta.json`、`notes/<slug>-problem-brief.md`。

## 版本与兼容

- T1 fixture `shortest_path` solution 可缺 `problem_class` 时由加载器默认 `shortest_path`  
- T2 新 fixture 必须带齐字段  
- R2 与 validate 必须以本契约为准扩展  
- 1.1 intake 默认可选；`skip_intake` 时不要求 IntakeArtifact
