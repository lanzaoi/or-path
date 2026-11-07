# Phase-1 Runbook：计划 1.3 / 1.4 / 1.5 实施清单

> 母计划：`tasks/lean_4agent_5x5_master_plan.md`（Phase 1）。本文件为本次实施进度追踪。

## 基线确认（已完成）

- `orpath/agents/workers.py` 已重铸四特种兵工厂（analyst/modeler/writer/reviewer，支持
  `cartridge_tools` / `domain_directive` 动态注入）；旧合体角色 `or_verifier_writer` 已不存在。
- `tools/test_workers.py`（1.3 验收测试）：40 passed / 1 failed
  → `test_factories_invoke_in_isolated_message_lists`：测试自身存在自家 brief 与自家内容的
  自比较缺陷（实现无串味，`len(messages)==2` 成立），需修测试跳过 `other == name`。
- 耗时基线：shortest_path 子进程 validate 0.205s；in-process validate import 0.033s + 运行 0.003s
  （微电网重型带 openpyxl 约 1s —— 对应"不含重型仿真"豁免边界）。
- fixture：`fixtures/t1/shortest_path/{graph.json,solution.json,problem.md}` 为轻量 Tier-A 靶子；
  QUBO max_cut / portfolio 校验器完全自包含（无外部 fixture 依赖），适合 Tier-C 逐问测试。

## 计划 1.3 — workers.py（收尾） — **完成：41/41**
- [ ] 修 `test_factories_invoke_in_isolated_message_lists` 自比较缺陷（skip self）
- [ ] 更新 `orpath/agents/__init__.py` 过时 docstring（旧角色名列表）
- [ ] `pytest tools/test_workers.py -q` 全绿

## 计划 1.4 — orpath/agents/deterministic_nodes.py（**完成：15/15**）
- [ ] `run_preflight_probe(state)`：扫描 inbox/<slug>/ 与 data_files → SHA-256 → CSV/Excel/JSON
      行列规模与字段概览 → 领域关键词初判 + `profile_<domain>_data` 自动执行 → 落盘
      `outputs/<slug>-profile.json` → 返回指针型状态更新（输入指纹压缩进 preflight_summary）
- [ ] `run_deterministic_validator(state)`：in-process `tools.validate_solution.validate`
      （fast path，golden 解析与 main() 一致）→ 失败回退 `tools.solve_dispatch.validate`
      子进程缝 → 领域 `inspect_<domain>_solution` 守恒/容量/偏序检查 → 提取
      ok / recomputed_objective / proven_optimal / errors 写入状态
- [ ] 全程 0 LLM 调用（模块不导入任何 chat model）
- [ ] `tools/test_deterministic_nodes.py`：画像结构/SHA 正确性/失败注入/时长 <0.5s/0-token 结构断言

## 计划 1.5 — orpath/agents/adaptive_graph.py（**完成：13/13**）
- [ ] `AdaptivePipelineState`（CorePipelineState 扩展：指针 + 紧凑摘要键）
- [ ] 确定性节点：preflight / table_renderer（输出 `outputs/<slug>-tables.md` 真值表）/
      doc_gate（六章关键词 + objective 绑定 + proven_optimal 声明红线）/ fail_closed
- [ ] LLM 隔离节点：analyst / modeler / writer / reviewer（`invoke({"messages":[HumanMessage(brief)]})`，
      brief 仅含文件指针 + compact ledger，agents 可注入以便离线测试）
- [ ] `decide_tier(state)` 纯 Python 分类：A={shortest_path, network_flow, lot_sizing,
      portfolio_opt, stochastic_lp, game_theory}；subproblems 非空→C；其余→B
- [ ] Tier-A 轨道：preflight→analyst→modeler(exact)→validator→tables→writer→doc_gate→END（可挂 reviewer）
- [ ] Tier-B 轨道：…validator⇄失败打回 modeler（model_retry_count<max_retries）→writer→reviewer⇄FATAL 打回
- [ ] Tier-C 轨道：analyst 后 `node_tier_c_focus`：逐问隔离 modeler 子实例 + 逐问 deterministic_validator，
      notes/<slug>-ledger.json 跨问传递余料账本/初始 SOC；全部通过→合并 envelope 工件→tables→writer→reviewer
- [ ] `tools/test_adaptive_graph.py`：Tier-A/B/C 节点序列断言（fake agents + 真确定性 validator）、
      retry 上限精确计数（modeler max_retries+1 次、reviewer FATAL→writer max_retries+1 次）、
      串味检查（modeler brief 不含 analyst 正文）

## 已知既有问题（非本次回归）

- `tools/test_supervisor.py`（3）+ `tools/test_agent_callbacks.py`（1）在 WIP 树中即失败：断言的是
  旧 researcher/verifier 阶段设计，而 supervisor.py/callbacks.py 已演进为 4 精英+领域群组；
  本次改动未触及这些模块（`supervisor.py` 按母计划将在后续阶段退役，其残留测试由 Phase 2 统一清理）。
- 全量套件（排除上述两文件）：**2252 passed, 1 skipped**；
  `scripts/universal_redteam_gate.py` PASS、`scripts/or_swarms_master_gate.py` PASS（6/6）。

## 收尾
- [ ] `orpath/agents/__init__.py` 增加两个新模块导出
- [ ] 全量单元测试 + 既有门禁回归（test_supervisor / test_agent_callbacks 不回归）
- [x] 母计划文件勾选 1.3 / 1.4 / 1.5 为 [x]
