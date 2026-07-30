# ADR-0004：统一 PaperProtocol

**状态：** Accepted 且已实现（2026-07-30）  
**日期：** 2026-07-30  
**来源：** 架构评审候选 #4

## 背景

- 论文环散落：`paper_workflow` / `post_solve_paper` / `paper_live` / `orpath_paper` / `run_tube_cut_paper`。  
- 圆管 CLI 另粘一层；调用方不知唯一入口。

## 决策

1. **`orpath/paper_protocol.py`** = 权威接口：  
   - `run_from_solution(...)` — 解后全文协议（不重解）  
   - `draft_paths` / `render_or_paper` 等 CLI 友好 re-export  
   - `IN_GRAPH_STAGES` — 与产品图论文半程对齐  
2. **`post_solve_paper`** = 兼容 shim（`run_post_solve_paper` 别名）。  
3. **图内**仍走 `nodes` 同名阶段；live 适配器仍 `paper_live_subagent`。  
4. **scripts** 只薄调 `run_from_solution`。  
5. **不改** R1/R2 数字真理、inject_bad_claim 演示语义。

## 后果

- **正：** 一个 post-solve 入口；tube 与 orpath_paper 同契约。  
- **负：** 辅助模块仍多文件（workflow/ledger 为深度实现，合理）。  
- **不变：** solve 在 paper 之外（ADR-0002）。
