# 架构整理进度（2026-07-29）

## 已完成
- [x] 安装 Matt Skills（全局）
- [x] `improve-codebase-architecture` 扫描 + 中文 HTML 报告
- [x] 候选 #1 grilling 决策
- [x] ADR-0001 + 工单
- [x] **#1 代码落地**：`orpath/nodes.py` 权威；T1 产品图；门禁全绿

## 冻结（#1 阶段节点）
1. 权威模块 = `orpath/nodes.py`
2. T1 → 产品图；`t1_gate` 绿
3. `nodes_t2` = re-export；`nodes_product` = bridge/wrap

## 下次（候选 #2）
- [ ] Deepen Solve/Validate 接缝（`tools/solve_*` + `scripts/b_tube_*`）
