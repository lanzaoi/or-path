# OR-Path 架构总览（纯 Python 原生精悍版）

> 活文档。项目最高宪章以 **`AGENTS.md`** 为准；历史 Node.js `pi` 包装层及旧轮询 `supervisor.py` 均已永久剥离退役。

## 一句话定义

题面与附件 → **[纯 Python 前置探针]** → **双运行模式**（`fast` 单智能体 `or_modeler` 默认闭环 / `deep` 四精锐双轨赛马 `adaptive_graph`）→ **[纯 Python 独立物理验算铁闸 & DIMO]** → **[真数据图表硬渲染]** → **`or_writer` 六章 SOP 成文（可按需跳过 `skip_paper`）** → **[R1/R2/Claim 硬门 + `or_reviewer` 同行审稿]**。

## 目录拓扑

```text
用户与外部入口
  ├─ START.bat / START.sh / orpath.bat / orpath.sh   ← Web Studio（watch.html + studio.html）& CLI 统一入口
  └─ 案例工作区 ORPATH_WORKDIR
         inbox/  outputs/  runs/<slug>/  papers/  notes/  memory/

安装根 ORPATH_HOME（本仓库）
  ├─ AGENTS.md / CLAUDE.md     项目最高法与智能体守则
  ├─ orpath/                   LangGraph 控制面 (graph_product.py, control_plane.py) · 4 精锐、adaptive_graph 与 Web Studio
  ├─ tools/                    27 台重型运筹求解器 (solve_*.py) · 独立验证器 (validate_solution.py / validators/)
  ├─ knowledge/                19 份运筹建模技能 (knowledge/skills/，含 or-reduction-playbook) + 语料种子
  ├─ knowledge_svc/            本地混合检索（BM25 / FTS5 + ONNX bge-m3）
  ├─ contracts/                领域协作与工件 JSON Schema 契约
  ├─ scripts/                  CLI 控制器 · custom_sandbox_gate · DIMO 红队门禁 · 诊断脚本
  ├─ demo/seed/ · fixtures/    回放演示种子、Web 预设与黄金基准测试集（Taillard, VRPLIB, PSPLib, Tube B, CUMCM C）
  ├─ specs/ · docs/            规格契约与六章论文规范 (docs/or-paper-sop.md)
```

## 核心架构契约

| 概念 | 工程铁律 |
|---|---|
| **双模式运行架构 (`fast` / `deep`)** | `fast`（默认）：由前置确定性探针 + 满血 `or_modeler` 单智能体直接完成数学规约（`or-reduction-playbook`）或受控脚本闭环并跳过冗余论文节点；`deep`：激活 `adaptive_graph.py` 唯一四精锐自适应状态机与无条件双轨算法赛马（Track A 精确/规约 vs Track B 松弛界+启发式） |
| **4 常驻精锐 + 满血编码工具集** | `or_analyst`、`or_modeler`、`or_writer`、`or_reviewer` 各自在纯净单条简报上下文中运行；配备受控文件/搜索/执行工具（`orpath/agents/coding_tools.py`）与分页 `read_problem_file`，支持多轮自修复与外科手术式论文修订 |
| **Anti-Cosplay 防火墙与过程记忆** | 禁止在 `schema.json` 偷写目标/路径字段或无工具手写解（违规即隔离 `.cosplay-quarantine` 并递增 `RETRY`）；`process_memory` 自动沉淀剥离数值权威键的跨轮经验，每阶段轨迹落盘 `runs/<slug>/agent_logs/<stage>.jsonl` |
| **Numbers Truth 2.0（数字真理）** | 目标值与物理指标 100% 来自内置 27 算子或经 `scripts/custom_sandbox_gate.py` + `tools/validate_solution.py` 物理隔离重算的自定义脚本（含 `reduction_manifest` 原题域二层校验与静态防 `import` 扫描）；`proven_optimal == False` 时严禁宣称全局最优 |
| **10 套可插拔 `DomainCartridge`** | 通过在 `preflight` 后动态挂载 `orpath/agents/domain_analytics.py`（`profile_<domain>_data` & `inspect_<domain>_solution`）与领域红线清单赋予专业深度，同时放开非标开放赛题经 `custom` / `custom_reduced` / `custom_mip` 通道求解 |
| **HOME ≠ WORKDIR & Feynman 交接** | 状态机仅传递轻量磁盘路径指针，完整上下文与验收证据独立落盘 `notes/`、`outputs/`、`papers/`、`runs/` |
