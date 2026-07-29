# T3 — LangGraph Product Skeleton（硬法）

**Grill freeze:** 2026-07-29（用户确认后开工）  
**主轴：** LG 产品骨架完整（非题型堆料）  
**T3-mini CVRPTW：** 仅为矩阵中的一叶，见 `t3-vrp-tw.md`

## Freeze 表

| ID | 锁 |
|----|-----|
| Q1 DoD | **E** — 骨架+叶子 + 图内 bridge + portfolio（截图/口播/multi-CLI/resume 双帧） |
| Q2 图 | **B 很厚** — `graph_product` + `run_orpath`；T1/T2 薄包装 |
| Q3 CP | **C** — Sqlite + 每节点 snapshot JSON + CLI `status\|resume\|list` + provenance 记 checkpoint id |
| Q4 Resume | **D** — 严格续跑 + `--from-stage` + 脏制品检测 |
| Q5 阶段 | **C** — control-plane 全表 + `bridge_pi` + snapshot 横切 |
| Q6 矩阵 | **D** — SP/TSP/VRP + `vrp_tw` + hybrid≥1 + live bridge≥1（可分轨） |
| Q7 门禁 | **D** — `t3_lg_gate` ∥ 业务 `t3_gate` ∥ live；**图导出 diff 代码节点** |
| Q8 Bridge | **D** — live 硬失败；证据文件；插入点可配，**默认 research 前** |
| Q9 脏检 | **D** — `artifact_hashes.json` manifest 全量校验 |
| Q10 作品集 | **D** — closeout + OpenPi 截图 + 口播 + 施工记录 + resume 双帧 |
| Q11 谁写 | **D** — Hermes 主写；CLI 叶任务；骨架文件禁止双写 |
| Q12 OUT | **D** — codegen 沙箱、Teams/bus、Graphiti、Compose/K8s 硬、新题类、OpenPi 大改、重开 T1/T2 |
| Q13 启动 | **C** — `orpath.bat run\|status\|resume\|list\|gate-t3` |
| Q14 Owner | **D** — specs + TypedDict + 运行时 assert + 单测 |
| Q15 节点 | **D′** — **`orpath/nodes.py` 权威**（含 NodeContext wrap + bridge）；`nodes_product` 仅 shim（ADR-0001） |
| Q16 旧 gate | **C′** — t1/t2 **均走产品图**；`t1_gate` 断言 `pipeline=product` |


## 产品入口

| 组件 | 路径 |
|------|------|
| 图 | `orpath/graph_product.py` |
| 节点 | **`orpath/nodes.py`**（阶段权威 + NodeContext 横切 + bridge）；`nodes_product` = 兼容 shim |
| Runner/CLI | `orpath/run_orpath.py` |
| Stage map 导出 | `orpath/stage_map.json` + `docs/t3-stage-map.mmd` |
| Checkpointer | `runs/orpath.sqlite`（gitignore） |
| Thread 快照 | `runs/<thread_id>/stages/*.json` + `artifact_hashes.json` |

## 阶段表（代码必须 1:1）

```text
START
 → orchestrate
 → [optional bridge_pi if attachment=before_retrieve]
 → retrieve
 → [default bridge_pi if attachment=before_research]
 → research
 → model
 → gate_schema → solve | model | human_stop
 → solve → gate_validate → explain | solve | model | human_stop
 → human_stop → provenance
 → explain → draft_paper → review_pack → revise_or_done
 → revise → draft_paper | provenance | human_stop
 → provenance → END
```

每个节点退出时：写 stage snapshot + 更新 artifact manifest hashes。

## 门禁

| 脚本 | 内容 |
|------|------|
| `scripts/t3_lg_gate.py` | 拓扑=导出图；checkpointer；resume；from-stage；脏检测；HUMAN 负例；owner 单测 |
| `scripts/t3_gate.py` | 业务矩阵（扩展含 vrp_tw）；可调用 run_orpath |
| `scripts/t3_gate_live.py` | live bridge 硬证据（可选分轨） |
| `t1_gate` | **仍打** `graph.py` 标本 |
| `t2_gate` | 经 `run_t2` **委托** 产品图 |

## 数字 / owner

- `objective` / routes / tour / path：**仅 solve 工具**  
- NodeContext 运行时拒绝非 solve 节点写入 solution 数字字段  
- 单测覆盖 modeler schema 禁 objective  

## 非目标

见 Q12-D。不重开 T1/T2 DoD。

## Verify（本地）

```bat
set PYTHONNOUSERSITE=1
orpath.bat gate-t3
.venv-314\Scripts\python.exe scripts\t3_lg_gate.py
.venv-314\Scripts\python.exe scripts\t1_gate.py
.venv-314\Scripts\python.exe scripts\t2_gate.py
```
