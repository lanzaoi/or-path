# ADR-0001：产品阶段节点合并到 `orpath/nodes.py`

**状态：** Accepted **且已实现**（2026-07-29 closeout）  
**日期：** 2026-07-29  
**来源：** 架构评审候选 #1 + grilling

## 背景

阶段实现曾分叉：`nodes.py`（T1）、`nodes_t2.py`（主）、`nodes_product.py`（包装）。

## 决策

1. **权威阶段模块** = `orpath/nodes.py`（核心阶段体 + product facade：bridge_pi、NodeContext wrap）。  
2. **T1 / T2 均走产品图**（`graph_product` / `run_orpath` / `run_t1`）。  
3. **`t1_gate` 断言** `pipeline=product`、`gate_validate_ok`、paper 含 fixture objective、provenance 含 product/T3 标记。  
4. **过渡清理（已做）：**  
   - 删除 `nodes_t2.py`  
   - `nodes_product.py` = 兼容 shim  
   - `graph.py` / `graph_t2.py` = 委托 `graph_product`  
5. 工单：`docs/archive/tickets/2026-07-29_stage-nodes-merge.md`

## 后果

- **正：** 单一接口；T1/T2/T3/paper 同一套阶段语义。  
- **负：** `nodes.py` 仍大文件（拆 `stages/` 不在本 ADR）。  
- **不变：** LG 控阶段；solve/validate 数字真理；CI `ORPATH_LIVE_SUBAGENT=0` / live 双路径。

## 不在此 ADR

- 求解器 `tools/` vs `scripts/b_tube_*`（候选 #2）  
- Paper 包合并（#4）、Subagent 四文件合并（#5）
