# ADR-0002：统一 Solve / Validate 接缝

**状态：** Accepted 且已实现（2026-07-30）  
**日期：** 2026-07-30  
**来源：** 架构评审候选 #2

## 背景

- 产品求解分散在 `tools/solve_*.py`，竞赛圆管又在 `scripts/b_tube_*` 分叉。  
- `orpath/gates.solve` 硬编码脚本名，接口不统一。  
- 数字真理要求：调用方只认 **envelope**，不认「哪个脚本」。

## 决策

1. **接口模块** `tools/solve_envelope.py`：`status` / `objective` / `source` + shape + `meta.*`。  
2. **调度模块** `tools/solve_dispatch.py`：唯一 `solve()` / `validate()`；adapters 注册表。  
3. **`orpath/gates.solve|gate_validate`** 只委托 dispatch。  
4. **圆管权威适配器** = `tools/solve_tube_cut_b2026.py`；`scripts/b_tube_solve.py` 薄 CLI。  
5. **启发式不得** `meta.proven_optimal=true`（envelope 硬拒）。  
6. 不在本 ADR：拆 polyomino、上 VROOM、改门禁数字。

## 后果

- **正：** 一个调用面；tube 与 mock/networkx/ortools 同契约；AI 导航清晰。  
- **负：** tube 全量求解仍重（CI 不强制跑 tube adapter）。  
- **不变：** validate 重算；claim ladder；mock 金标。
