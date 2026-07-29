# 工单：合并阶段节点 → `orpath/nodes.py`

**状态：** DONE（2026-07-29）  
**ADR：** `docs/adr/0001-stage-nodes-merge.md`  
**优先级：** P0（架构候选 #1）

## 已冻结决策

| # | 决策 |
|---|------|
| Q1 | 权威实现 = **`orpath/nodes.py`** |
| Q2 | **T1 走产品图**；`t1_gate` 仍绿（无需改断言：paper 仍含 42） |
| Q3 | 已实现（本会话） |

## 施工结果

### T0 — 基线
- [x] t1/t2/paper/paper_1_0/subagent 全绿（改前）

### T1 — 迁入权威模块
- [x] `nodes_t2` 主体 → `orpath/nodes.py`
- [x] `nodes_product` 改为 `from orpath import nodes`
- [x] `nodes_t2.py` → re-export
- [x] `graph_t2` / `post_solve_paper` 指 `nodes`
- [x] `graph_product` 仍用 `nodes_product`（bridge + wrap）

### T2 — T1 切产品图
- [x] `run_t1.py` → `build_graph_product`，`pipeline=product`，`live_subagent=False`
- [x] `graph.py` → 委托 `graph_product`
- [x] `t1_gate` PASS（输出含 `pipeline: product`）

### T3 — 清理
- [x] 全门禁再跑 PASS
- [x] `specs/architecture.md` + `control-plane.md` 补权威节点
- [x] 提交见 git log

## 验收（改后）

| 门禁 | 结果 |
|------|------|
| t1_gate | PASS |
| t2_gate | PASS |
| paper_gate | PASS |
| paper_1_0_gate | PASS |
| subagent_gate | PASS |
