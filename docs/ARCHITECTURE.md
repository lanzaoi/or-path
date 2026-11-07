# OR-Path 架构总览（纯 Python 原生精悍版）

> 活文档。项目最高宪章以 **`AGENTS.md`** 为准；当前实施总单见 **`tasks/lean_4agent_5x5_master_plan.md`**。历史 Node.js `pi` 包装层已永久剥离退役。

## 一句话定义

题面与附件 → **[纯 Python 前置探针]** → **`or_analyst` 研判与分档** → **`or_modeler`（装载 `DomainCartridge` 调成熟求解器或写沙箱 MIP/CP-SAT）** → **[纯 Python 独立物理验算铁闸]** → **[真数据图表硬渲染]** → **`or_writer` 六章 SOP 成文** → **[R1/R2/Claim 硬门 + `or_reviewer` 红队审稿]**。

## 目录拓扑

```
用户与外部入口
  ├─ START.bat / START.sh / orpath.bat / orpath.sh   ← Web Studio & CLI 统一入口
  └─ 案例工作区 ORPATH_WORKDIR
         inbox/  outputs/  runs/<slug>/  papers/  notes/

安装根 ORPATH_HOME（本仓库）
  ├─ AGENTS.md / CLAUDE.md     项目最高法与智能体守则
  ├─ tasks/                    执行计划总单（lean_4agent_5x5_master_plan.md）
  ├─ orpath/                   LangGraph 主控平面 (graph_product.py) · 4 精锐智能体与装备包 · Web Studio
  ├─ tools/                    27 个硬核运筹求解器 (solve_*.py) · 独立验证器 (validate_solution.py / validators/)
  ├─ knowledge/                19 份运筹建模宝典 (knowledge/skills/) + 语料种子
  ├─ knowledge_svc/            本地混合检索（BM25 / FTS5 + ONNX bge-m3）
  ├─ contracts/                领域协作与工件 JSON Schema 契约
  ├─ scripts/                  CLI 控制器 · DIMO 红队门禁 · 三大王牌真跑脚本
  ├─ demo/seed/ · fixtures/    回放演示种子与黄金基准测试集（Taillard, VRPLIB, PSPLib, Tube B, CUMCM C）
  ├─ specs/ · docs/            规格契约与六章论文规范 (docs/or-paper-sop.md)
```

## 核心架构契约

| 概念 | 工程铁律 |
|------|------|
| **4 常驻精锐智能体** | `or_analyst`、`or_modeler`、`or_writer`、`or_reviewer`，全部在独立纯净上下文运行，严禁多人群聊串味与 1600 字暴力截断 |
| **0 Token 确定性铁闸** | 前置数据画像探针、`validate_solution.py` 物理重算、真数据 Markdown 图表装配、R1/R2/最优声称校验均由纯 Python 条件边刚性执行 |
| **10 套可插拔 `DomainCartridge`** | 通过挂载 `orpath/agents/domain_analytics.py`（`profile_<domain>_data` & `inspect_<domain>_solution`）与领域清单赋予专业深度，严禁按领域复制粘贴 900 行雷同 Agent 图 |
| **Tier-A / B / C 复杂度分轨** | Tier-A（LP/凸QP/最短路/WW-DP）直走精确求解；Tier-B（NP-Hard 组合优化）走松弛下界 + 搜索算 Gap；Tier-C（多问大型赛题）动态派生子问 `or_modeler` 并传递跨期状态工件 |
| **Numbers Truth（数字真理）** | 目标函数值与物理指标 100% 来自 `tools/solve_*` + `tools/validate_solution.py`，严禁 LLM 心算或投票篡改 |
| **HOME ≠ WORKDIR & Feynman 交接** | 状态机仅传递轻量磁盘路径指针（`< 8 KB`），完整轨迹独立落盘 `runs/<slug>/agent_logs/` |
