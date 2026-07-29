# ADR-0001：产品阶段节点合并到 `orpath/nodes.py`

**状态：** Accepted（决策冻结，**实现未做**）  
**日期：** 2026-07-29  
**来源：** 架构评审候选 #1 + grilling（用户选 D：本回合只落文档）

## 背景

阶段实现分叉：

| 文件 | 用途 |
|------|------|
| `orpath/nodes.py` | T1 旧图 `graph.py` |
| `orpath/nodes_t2.py` | 主实现（~1279 行） |
| `orpath/nodes_product.py` | t2 + bridge + NodeContext 薄包装 |

热点改动集中在 `nodes_t2`；T1/产品逻辑复制，局部性差。

## 决策

1. **权威阶段模块** = `orpath/nodes.py`（一个深模块，产品节点全集）。  
2. **T1 不再保留第二套节点实现**；改为走 **产品图**（`graph_product` / `run_orpath`）+ 固定参数。  
3. **`t1_gate` 必须改写验收**以匹配产品图产物/阶段（允许 deterministic live=0）。  
4. 过渡期：`nodes_t2` / `nodes_product` 可先 **re-export**，门禁全绿后再删。  
5. **本回合不改代码**（用户 Q3=D）；实现见工单 `docs/tickets/2026-07-29_stage-nodes-merge.md`。

## 后果

- **正：** 单一接口；T1/T2/T3/paper 同一套阶段语义；AI 导航成本下降。  
- **负：** `t1_gate` 与 `run_t1` 要动；一次合并 diff 大，需门禁矩阵。  
- **不变：** LG 控阶段；solve/validate 数字真理；CI `ORPATH_LIVE_SUBAGENT=0` / live 双路径。

## 不在此 ADR

- 求解器 `tools/` vs `scripts/b_tube_*` 统一（架构候选 #2）  
- Paper 包合并（#4）、Subagent 四文件合并（#5）

## 否决项

- 永久保留 T1 独立节点副本（会继续分叉）  
- 本回合强行按 `stages/` 拆多文件（可作后续工单）
