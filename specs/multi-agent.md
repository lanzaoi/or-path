# Multi-Agent — 原生精悍多智能体协作规范

**对齐：** `AGENTS.md` · `specs/architecture.md` · `specs/product-flow-sdd.md` · `docs/or-paper-sop.md`  
**状态：** LAW 2026-11（已退役旧版 `.pi/` Node CLI 子进程规范）

---

## 1. 架构核心：4 常驻精锐智能体 + 纯 Python 确定性铁闸 + 10 领域装备包

系统严禁使用大模型“包工头（Lead/Supervisor）”轮询点名或用大模型“口头验算（Verifier）”，路由流转与数值验算全部下沉为 **0 Token 纯 Python 确定性节点与条件边**。

### 1.1 四大常驻 LLM 特种兵（`orpath/agents/workers.py`）

| 角色标识 | 职责边界（Owns） | 绝对红线（Forbidden） | 核心绑定工具 |
|---------|------------------|-----------------------|--------------|
| `or_analyst` | 读取前置探针 `profile.json` 与 `knowledge/skills/`，识别变量/约束/数学分类，选定 `DomainCartridge` 与 `Tier-A/B/C` | 严禁编写求解代码、严禁猜测或编造最优目标值 | `read_problem_file`, `search_or_knowledge`, `consult_or_skill`, `profile_<domain>_data` |
| `or_modeler` | 构建 `schema.json`，调度注册求解算子或编写受控 Python 沙箱 MIP/CP-SAT 脚本，提取松弛下界与 Gap（Tier-C 按子问动态派生隔离实例） | 严禁手写 `solution.json` 数值、严禁静默放松硬物理约束 | `execute_or_solver`, `execute_python_sandbox`, `get_problem_formulation_template`, `inspect_<domain>_solution` |
| `or_writer` | 基于 Python 预渲染真数据表与甘特图/轨迹图，严格按 `docs/or-paper-sop.md` 六章结构撰写 6~10 KB 学术论文 | 严禁篡改表格数字、严禁在 `proven_optimal == False` 时吹嘘“全局最优” | `read_problem_file`, `consult_or_skill` |
| `or_reviewer` | 扮演严苛同行审稿红队，联合 R1/R2/Claim 硬门核查公式闭合性、符号一致性与结论边界，输出 `FATAL / MAJOR / MINOR` | 严禁无上限互怼死循环（受 `max_retries <= 2` 硬约束） | `read_problem_file` |

---

## 2. 上下文隔离与零截断铁律（Feynman File Handoffs）

1. **零截断**：严禁对题面、坐标表、代码或模型输出施加 `1600` 字符腰斩钩子。
2. **零群聊污染**：每个智能体均以全新局部消息列表 `invoke({"messages": [HumanMessage(task_brief)]})` 启动，历史会话独立归档至 `runs/<slug>/agent_logs/<stage>.jsonl`。
3. **指针传递**：跨阶段仅通过强类型状态（`CorePipelineState` / `ORPathState`）传递 `notes/`、`outputs/`、`papers/` 下的文件路径与紧凑状态标志。

---

## 3. Tier-A / Tier-B / Tier-C 数学复杂度自适应轨道

- **Tier-A（精确多项式 / 凸优化极速轨）**：LP、马科维茨凸 QP、两阶段随机 LP、最短路、Wagner-Whitin DP —— 直接精确求解，**严禁强塞伪启发式搜索角色**。
- **Tier-B（单问 NP-Hard 组合优化轨）**：JSSP/FJSSP、VRPTW、RCPSP、CFLP、排班、装箱 —— 先锁松弛下界（Lower Bound）再跑 CP-SAT / PyVRP / ALNS 寻优，显式汇报真实 Optimality Gap。
- **Tier-C（多问递进大型数模赛题轨）**：如 Tube B 四问、CUMCM C 多问 —— 按子问题依赖链动态拉起隔离 `or_modeler` 实例并传递跨问状态工件（余料账本、初始 SOC 等）。

---

## 4. Live 模式与离线 CI 门禁纪律

| 运行场景 | 开关优先级 | 行为要求 |
|----------|------------|----------|
| 自动化离线门禁（CI Gates） | 显式传入 `state["live_subagent"] = False`（高于 `.env`） | 走确定性离线回路，零外网 API 阻塞 |
| 产品 Web Studio / 王牌实跑验收 | `.env` 配有真实 API Key 且未显式关闭 `live_subagent` | 真实调用大模型完成 4 精锐智能体闭环，严禁用 `MockChatModel` 冒充实跑产物 |
