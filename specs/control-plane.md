# Control Plane — 阶段机与回修

## 入口

| Runner | 用途 |
|--------|------|
| `orpath/run_t1.py` | T1 标本；**走产品图** `graph_product`（ADR-0001）；`t1_gate` 必绿 |
| `orpath/run_t2.py` | T2 薄委托 → 产品图 `run_orpath` / `graph_product` |
| `orpath/run_orpath.py` | **T3 主入口**：checkpointer、resume、from-stage、status/list |
| `orpath/nodes.py` | **阶段节点权威**；T1/T2/product 同一套 `node_*` |

## T3 产品图（权威阶段）

完整法条见 `t3-lg-skeleton.md`。相对 T2 目标图增量：

- Sqlite checkpointer + `runs/<thread>/` snapshots + artifact manifest  
- 图内 `bridge_pi`（默认 retrieve→research 之间；可配置 before_retrieve）  
- NodeContext 横切（snapshot / hash / owner assert）  
- CLI：`run | status | resume | list`  

T2 目标阶段图仍有效；实现以 **product graph** 为准。

```text
START
  → orchestrate
  → retrieve_or_seed          # seed 与/或 hybrid retrieve → notes/<slug>-retrieval.json
  → research                  # 消费 retrieval；写 notes/<slug>-research.md
  → model                     # outputs/<slug>-schema.json
  → gate_schema               # 代码
       ├─ fail → model (schema_repair < max_schema_repair)
       └─ fail & ceiling → HUMAN_REQUIRED
  → solve                     # tools only → solution.json
  → gate_validate             # validate_solution
       ├─ fail → param_retune_solve  (solver_tune < max_solver_tune)   # Q12-C
       ├─ still fail → model (validate_repair < max_validate_repair)
       └─ still fail → HUMAN_REQUIRED
  → explain
  → draft_paper
  → review_pack               # R1 ∥ R2 ∥ optional soft critic
  → revise_or_done            # paper max_revise
  → provenance
END
```

## 回修上限（硬）

| 计数器 | 默认 max | 触发 |
|--------|----------|------|
| `schema_repair` | **2** | gate_schema 红 → 回 model |
| `solver_tune` | **3** | gate_validate 红 → **同 schema** 调 OR-Tools 参数并重解（Q12-C / Q13-B） |
| `validate_repair` | **2** | 调参用尽仍红 → 回 model |
| `revise_count`（paper） | **2** | review FATAL → 回 draft |
| 任一用尽 | — | `human_required=true`，写 provenance，停止自动空转 |

**禁止：** 调参与回 model 无上限交错；validate 红自动进入 codegen 沙箱（非 T2）。

## 调参环（Q12-C）语义

1. 输入：当前 `schema` + 失败的 `ValidateReport` + 上次 `solution`  
2. 动作：仅允许在 **文档化的参数空间** 内改 solver 选项（如时间限制、first solution strategy、metaheuristic、随机种子等）— 具体白名单见 `solvers-and-validate.md`  
3. 再调用同一 `solve_*`；**不得**让 LLM 直接改 `objective`  
4. 每次尝试追加到 provenance / `outputs/<slug>-tune-log.jsonl`  
5. `solver_tune` 达上限仍红 → 进入 `validate_repair`（回 model）

Mock 模式：调参环可短路为「不再调参，直接走 validate_repair」，避免假调参。

## 字段 owner（窄状态）

| 字段 / 制品 | 唯一写者 |
|-------------|----------|
| plan ledger | orchestrate |
| `retrieval_path` / retrieval JSON | retrieve 节点 |
| `research_path` | research |
| `schema_path` / schema 内容 | model **only** |
| `solution_path` / `objective` / tour/routes | **solve 工具 only** |
| `validate_path` / `gate_validate_ok` | validate 工具 only |
| `gate_schema_ok` | schema gate |
| tune log | gate_validate / tune 辅助 |
| paper / review | writer / review 节点 |
| `human_required` | 各 gate / revise 天花板 |
| repair 计数器 | LG 节点递增 |

**禁止：** 子 Agent 或 memory 覆盖 `objective`。

## 运行参数（逻辑名）

| 参数 | 含义 | 示例 |
|------|------|------|
| `problem_id` | fixture id | `tsp_n8`, `vrp_multi` |
| `problem_class` | `shortest_path` \| `tsp` \| `vrp` | |
| `solve_mode` | `mock` \| `networkx` \| `ortools` | |
| `knowledge_mode` | `off` \| `seed` \| `hybrid` | |
| `ORPATH_LIVE_PI` | `0/1` bridge | closeout 需成功=1 证据 |
| `T2_REQUIRE_CLOUD` | cloud 轨 | 本机交付默认 1 |

## Checkpointer

- 路径：`runs/`（gitignore）  
- 用途：阶段恢复；**不是**文献库  
- 不得作为 objective 权威源（权威仍是 solution 文件）

## HUMAN_REQUIRED

当自动回修用尽：

1. state.`human_required` = true  
2. provenance 写明最后失败 gate、计数器、制品路径  
3. runner 退出码非 0（或约定码）  
4. **不**假装 PASS
