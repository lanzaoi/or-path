# Phase 3 执行进度跟踪（3.1 ~ 3.5）

> 状态机：每完成一项并在验收中通过，将 `[ ]` 改成 `[x]` 并记录验证命令输出摘要。

## 计划 3.1：重写 orpath/pipeline/research.py 接入前置探针与 or_analyst
- [ ] research.py node_research 接入确定性探针（outputs/<slug>-profile.json）
- [ ] 在线模式唤醒 or_analyst 深度研判 → notes/<slug>-research.md
- [ ] 离线 CI 保留确定性骨架回退（附件表头/行数/约束映射）
- [ ] 验收：多附件 Excel 数模题 research.md 列出真实表头字段、行数、约束映射

## 计划 3.2：铲除 orpath/pipeline/solve.py 静态分支，统一接入自适应 or_modeler
- [ ] node_model 删除 5 分支硬编码树，走 DomainCartridge + registry
- [ ] 22 类注册类全部能建 schema（fixture-driven / structural）
- [ ] Tier-B 松弛下界 + Incumbent 真实 Gap 记录（outputs/<slug>-gap.json）
- [ ] 验收：22 类问题走通 model → gate_schema → solve → gate_validate

## 计划 3.3：未知开放赛题“建模宝典检索 + 受控 Python 沙箱自编求解”闭环
- [ ] tools_or.py 增加 write_custom_solver_script / custom_mip 装备
- [ ] adaptive_graph.py node_modeler 装载 general_or：模板检索 → 沙箱自编 → 独立重算
- [ ] 验收：自定义资源分配/排产 MIP 新题自主写码求最优并通过独立重算校验

## 计划 3.4：收拢 orpath/control_plane.py 并实现快慢双模型梯队路由
- [ ] 新增 get_tiered_chat_model(role: Literal["fast","reasoning"])
- [ ] 领域构造别名动态收敛（PEP 562 __getattr__ + registry）
- [ ] .env.example 增加 ORPATH_FAST_MODEL / ORPATH_REASONING_MODEL / ORPATH_LLM_MODEL
- [ ] 验收：双模型配置/单模型自动回退均可

## 计划 3.5：全面对齐 CLI 与 Web Studio 交互入口
- [ ] /api/studio/confirm 与 run_orpath.py 统一 graph_product.py 主干图
- [ ] live_subagent=False 显式传入强制离线回路（CI 门禁不挂起）
- [ ] Web + 真实 API Key 默认 4 特种兵真跑
- [ ] 验收：problem_workbench_gate.py 与 CLI 一致、状态文件互通
