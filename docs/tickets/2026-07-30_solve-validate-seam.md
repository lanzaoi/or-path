# 工单：统一 Solve/Validate 接缝（候选 #2）

**状态：** DONE  
**ADR：** `docs/adr/0002-solve-validate-seam.md`

## 交付
- [x] `tools/solve_envelope.py`
- [x] `tools/solve_dispatch.py`（含 tube adapter）
- [x] `orpath/gates.py` 委托 dispatch
- [x] `scripts/b_tube_solve.py` 薄 CLI
- [x] `test_gates` envelope/dispatch 用例
- [x] specs + ADR

## 验收
- pytest tools（含新测）
- t1/t2/paper/subagent 门禁绿
- 不强制 CI 跑全量 tube 几何（过重）
