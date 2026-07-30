# ADR-0003：统一 ControlPlane（Graph + Runner）

**状态：** Accepted 且已实现（2026-07-30）  
**日期：** 2026-07-30  
**来源：** 架构评审候选 #3

## 背景

- `graph.py` / `graph_t2.py` / `graph_product.py` + `run_t1` / `run_t2` / `run_orpath` 多入口。  
- AI/人难辨「谁是产品法」；状态种子在 T1 与 run_orpath 重复。

## 决策

1. **`orpath/control_plane.py`** = 唯一控制面接口：  
   - `build_graph` · `default_initial` · `invoke_once` · `summarize_run`  
   - 再导出 `PRODUCT_NODES` / checkpointer / stage map  
2. **拓扑**仍在 `graph_product.py`（边与路由）；**不**在 runner 复制节点表。  
3. **CLI** 仍 `run_orpath.py`（checkpoint/resume/status/list），内部只调 ControlPlane。  
4. **薄 shim：** `graph.py` / `graph_t2.py` / `run_t1.py` / `run_t2.py`。  
5. **不改** CI/live 双路径、solve/validate 数字真理、阶段集合。

## 后果

- **正：** 一个 build/seed/one-shot 接口；T1 与产品同种子。  
- **负：** 历史文件名仍在（有意兼容门禁）。  
- **不变：** `orpath.bat run|status|resume|list`。
