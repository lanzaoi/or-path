# 工单：合并阶段节点 → `orpath/nodes.py`

**状态：** DONE + **closeout 完成**（2026-07-29）  
**ADR：** `docs/adr/0001-stage-nodes-merge.md`

## Closeout（相对首轮落地的补完）

- [x] `nodes_product` 逻辑并入 `orpath/nodes.py`（facade 段）
- [x] 删除 `nodes_t2.py`
- [x] `nodes_product.py` → shim
- [x] `graph_product` → `from orpath import nodes`
- [x] `graph_t2` → 委托产品图
- [x] `t1_gate` 加强：`pipeline=product`、`gate_validate_ok`、provenance product 标记
- [x] ADR 状态改为已实现；specs/README 同步
- [x] 全门禁再跑

## 验收门禁

t1 / t2 / paper / paper_1_0 / subagent — 须 PASS
