# ADR-0005：统一 SubagentDispatch

**状态：** Accepted 且已实现（2026-07-30）  
**日期：** 2026-07-30  
**来源：** 架构评审候选 #5

## 背景

- M1–M3 后四模块：`subagent_runtime` / `harness` / `paper_live` / `graph_live`。  
- 改 anti-cosplay 或 stage→agent 映射要开多处；`nodes` 双 import。

## 决策

1. **`orpath/subagent_dispatch.py`** = 产品唯一导入面：  
   live 开关、cite/review/research/model leads、harness、detect/spawn、`STAGE_AGENTS`、`policy_snapshot()`。  
2. **分层实现保留**（深度实现，不是浅转发堆）：  
   - runtime = spawn/detect/env  
   - harness = no-write lead  
   - paper_live / graph_live = 阶段 brief  
3. **`nodes.py` / `subagent_gate`** 只 import `subagent_dispatch`。  
4. **不**物理删除四文件（避免巨大 diff / 破坏调试路径）。  
5. **不改** anti-cosplay 铁律、forced stages、数字真理。

## 后果

- **正：** 一个 policy 入口；AI 默认只开 dispatch。  
- **负：** 实现仍四文件（有意）。  
- **不变：** `ORPATH_LIVE_SUBAGENT=0` 门禁策略。
