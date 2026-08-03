# Control Plane — 阶段机、回修与字段权属（详细）

**对齐：** `product-flow-sdd.md`  
**状态：** LAW 2026-08-01

---

## 1. 入口与模块

| 模块 | 职责 |
|------|------|
| **`orpath/control_plane.py`** | 权威：build_graph / default_initial / invoke_once（ADR-0003） |
| `orpath/run_orpath.py` | CLI：run/status/resume/list/from-stage/fresh |
| `orpath/graph_product.py` | 拓扑（边与条件） |
| `orpath/nodes.py` | 阶段节点实现 |
| `orpath/run_t1.py` / `run_t2.py` | 兼容/薄委托 |
| `orpath/graph.py` `graph_t2.py` | shim → control_plane |

```bat
orpath.bat run --problem-id shortest_path --solve-mode mock --slug demo --thread-id demo --fresh
orpath.bat status --thread-id demo
orpath.bat resume --thread-id demo
```

---

## 2. 逻辑阶段图（权威叙述）

实现节点名以代码为准；逻辑等价如下。

```text
START
  → [optional] intake_ocr → intake_parse → [human_confirm_intake?]
  → orchestrate
  → retrieve_or_seed
  → bridge_pi                 # 可 skip
  → research
  → model
  → gate_schema
       ├─ fail & schema_repair < 2 → model
       └─ fail & ceiling → HUMAN_REQUIRED
  → solve
  → gate_validate
       ├─ fail & solver_tune < 3 → param_retune_solve（同 schema）
       ├─ fail & validate_repair < 2 → model
       └─ fail & ceiling → HUMAN_REQUIRED
  → explain
  → draft_paper
  → cite_pack
  → review_pack
  → revise_or_done
       ├─ paper FATAL & revise_count < 2 → draft_paper（再 cite/review）
       ├─ ceiling → HUMAN 或 provenance BLOCKED
       └─ ok → provenance → END
```

**默认 skip_intake：** 无题面源时兼容 T1–1.0 门禁。

**intake 开启且无域 adapter：** solve 可 **BLOCKED**（诚实），见 `1.2-architecture-soak.md`。

---

## 3. 回修上限（硬）

| 计数器 | max | 触发 |
|--------|-----|------|
| `schema_repair` | **2** | schema 红 → model |
| `solver_tune` | **3** | validate 红 → 同 schema 调参重解 |
| `validate_repair` | **2** | 调参尽 → model |
| `revise_count` | **2** | 论文侧 FATAL → draft |
| 用尽 | — | `human_required=true` + provenance；**不装 PASS** |

**禁止：** 调参与回 model 无限交错；validate 红自动 codegen 沙箱（非本阶段）。

---

## 4. 调参环语义（非精确轨）

1. 输入：schema + ValidateReport + 上次 solution  
2. 仅改 **白名单** solver 参数（见 solvers 分册）  
3. 再 solve；**禁止** LLM 改 objective  
4. 追加 `outputs/<slug>-tune-log.jsonl`  
5. 顶格 → validate_repair  

Mock / networkx / cpsat / highs：**不走**启发式调参阶梯（直 model 或 HUMAN）。

---

## 5. 字段 owner（窄状态）

| 字段/制品 | 唯一写者 |
|-----------|----------|
| plan ledger | orchestrate |
| ocr / brief / intake.json / gate_intake_ok | intake 工具/gate |
| retrieval_* | retrieve |
| research_path | research（合并 child 后可由运行时写） |
| schema_* | **model only** |
| solution / objective / tour/routes/path 答案 | **solve only** |
| validate_* / gate_validate_ok | validate |
| gate_schema_ok | schema gate |
| tune log | validate/tune 辅助 |
| paper / drafts / review | paper 站 |
| cite/review live 元 | dispatch/harness |
| human_required | gates / revise 天花板 |
| 修理计数器 | **LG 节点递增** |
| timeline 制品 | timeline 聚合器（只读写盘衍生，不改 solution） |

**禁止：** sub / memory 覆盖 objective。

---

## 6. 运行参数（逻辑名）

| 参数 | 含义 |
|------|------|
| `problem_id` | fixture 或逻辑 id |
| `problem_class` | shortest_path \| tsp \| vrp \|（扩展注册类） |
| `solve_mode` | mock \| networkx \| cpsat \| highs \| ortools \| tube \| … |
| `knowledge_mode` | off \| seed \| hybrid |
| `slug` / `thread_id` | 制品与 resume 键 |
| `ORPATH_LIVE_SUBAGENT` | 真 sub；产品默认 1；gate=0 |
| `ORPATH_LIVE_PI` | bridge；历史 |
| `skip_intake` | 默认 true 若无源 |
| intake 路径 | `--intake-in` / auto inbox |

---

## 7. Checkpointer 与磁盘

| | |
|--|--|
| DB | `runs/orpath.sqlite`（gitignore） |
| Stage 快照 | `runs/<thread>/stages/*.json` |
| Manifest | `artifact_hashes.json`；脏 resume → 失败除非 force/fresh |
| 权威数字 | **仍是 solution 文件**，不是 checkpoint blob |

---

## 8. HUMAN_REQUIRED

1. `human_required=true`  
2. provenance 写：失败 gate、计数器、路径  
3. runner 非 0（或约定码）  
4. 时间线必须仍可生成（失败 run 也可视）  

---

## 9. 与可视化

每站结束应有足够字段供 `process-visibility` L0 条带使用：`node`/`stage`/`last_error`/主要 `*_path`/`gate_*`。  
缺字段视为控制面回归缺陷。

---

## 10. 参考

`t3-lg-skeleton.md` · `product-flow-sdd.md` · ADR-0003  
