# Control Plane — 阶段状态机、流转路由与字段权属（权威规范）

**对齐：** `AGENTS.md` · `specs/product-flow-sdd.md` · ADR-0003  
**状态：** LAW 2026-11（原生 LangGraph 纯 Python 控制面全量上线）

---

## 1. 架构模块与职责边界

| 模块文件 | 核心职责 | 规范要求 |
|----------|----------|----------|
| **`orpath/control_plane.py`** | 统一图构建器（`build_product_graph`）、初始状态种子构建（`default_initial_state`）与单步/全流执行引擎（`invoke_once`） | 阶段机唯一总管（ADR-0003） |
| **`orpath/graph_product.py`** | 定义 LangGraph 拓扑、节点注册、确定性条件边（Conditional Edges） | 零 LLM 投票，纯 Python 布尔判断 |
| **`orpath/nodes.py`** | 阶段节点逻辑实现（衔接 4 大常驻智能体与底层 27 求解器/验算门禁） | 保证上下文隔离，只写归属字段 |
| **`orpath/run_orpath.py`** | 命令行驱动核心（支持 `--fresh`, `--resume`, `--from-stage`, `--problem-id`, `--solve-mode`） | 统一 CLI 控制中枢 |

---

## 2. 核心状态图拓扑（Topological Flow）

```text
START
  │
  ▼
[ intake_ocr / intake_parse ] ──► [ human_confirm_intake? ] (Web Studio 可交互确认)
  │
  ▼
[ orchestrate ]  (确定性预检、装备包挂载、复杂度评级 Tier-A / B / C)
  │
  ▼
[ retrieve_or_seed ]  (本地 ONNX bge-m3 + BM25 检索技能库与建模战法)
  │
  ▼
[ research ]  (智能体: or_analyst 分析变量/约束/模型类，生成 problem-brief.md)
  │
  ▼
[ model ]  (智能体: or_modeler 构建 contracts/schema.json 或受控 MIP/CP-SAT 脚本)
  │
  ▼
[ gate_schema ] ──(失败 & schema_repair < 2)──► [ model ]
  │            ──(失败 & 达上限)──────────────► [ HUMAN_REQUIRED ]
  ▼ (成功)
[ solve ]  (调度 27 工业求解器运行物理计算，生成 outputs/solution.json)
  │
  ▼
[ gate_validate ] ──(失败 & solver_tune < 3)────► [ param_retune_solve ] (同 schema 调参)
  │               ──(调参尽 & validate_repair < 2)─► [ model ]
  │               ──(失败 & 达上限)──────────────► [ HUMAN_REQUIRED ]
  ▼ (成功: 独立物理验算与 DIMO 检验 100% 通过)
[ draft_paper ]  (智能体: or_writer 结合预渲染表格/轨迹图撰写 6 章学术论文)
  │
  ▼
[ cite_pack & review_pack ]  (智能体: or_reviewer 对抗红队审稿与公式/符号闭合性核查)
  │
  ▼
[ revise_or_done ] ──(FATAL & revise_count < 2)─► [ draft_paper ]
  │                ──(评审通过)────────────────► [ provenance ] ──► END
  └────────────────(达上限)────────────────────► [ HUMAN_REQUIRED ]
```

---

## 3. 确定性回修上限（Deterministic Ceiling Counters）

为了彻底杜绝大模型在死循环中耗尽 Token 与上下文，系统强制施加纯 Python 计数器物理熔断：

| 计数器字段 | 硬性上限（Max） | 触发机制 | 熔断后续 |
|------------|-----------------|----------|----------|
| `schema_repair` | **2 次** | Schema JSON 结构或语法校验失败 | 顶格后标记 `human_required=True`，严禁死转 |
| `solver_tune` | **3 次** | 求解返回未达到要求但可通过超参调优 | 仅允许白名单参数微调，顶格转入 `validate_repair` |
| `validate_repair` | **2 次** | 独立物理复算失败或硬物理约束违背 | 顶格后标记 `human_required=True` 并阻断流程 |
| `revise_count` | **2 次** | 论文评审红队给出 `FATAL` 级别缺陷报告 | 顶格后进入人工介入或保留诚实瑕疵记录 |

**绝对禁令**：严禁通过大模型自我安慰绕过计数器；严禁在门禁失败时强行将状态伪造为 `PASS`。

---

## 4. 强类型状态字段权属（Strict Field Ownership）

为防止状态被脏写与黑板污染，每个核心字段由且仅由特定节点负责写入：

| 状态字段 / 物理工件 | 唯一合法的写入方（Owner） | 严禁篡改方 |
|---------------------|---------------------------|------------|
| `plan_ledger`, `tier_class` | `orchestrate` | 任何后续 LLM 节点 |
| `ocr_raw`, `problem_brief`, `profile.json` | `intake_*` / 探针工具 | 求解器与写作智能体 |
| `retrieval_docs`, `skill_context` | `retrieve` 节点 | 论文审稿节点 |
| `research_path`, `problem_analysis` | `research` (`or_analyst`) | 求解器 |
| `schema`, `schema_path` | `model` (`or_modeler`) | 求解器（求解器只读 schema） |
| `solution`, `objective`, `status` | `solve` (底层 27 求解器) | **所有 LLM 智能体**（绝对红线） |
| `validation_report`, `gate_validate_ok` | `gate_validate` (物理校验器) | 任何 LLM 智能体 |
| `paper_path`, `paper_draft` | `draft_paper` (`or_writer`) | 求解器 |
| `review_report`, `review_grade` | `review_pack` (`or_reviewer`) | 论文撰写者 |
| `human_required`, `provenance` | 控制面条件边 / `provenance` 节点 | 无法自愈的异常场景 |

---

## 5. Checkpointer、会话隔离与断点恢复（Resume）

1. **持久化介质**：基于 SQLite Checkpointer（`runs/orpath.sqlite`），支持全链路状态快照保存。
2. **断点恢复策略**：
   - 运行中可通过 `orpath.bat resume --thread-id <slug>` 继续中断的流。
   - 可通过 `--from-stage <stage>` 回退至特定节点重跑，同时自动执行制品哈希校验（`artifact_hashes.json`），防止依赖脏文件。
3. **真实单兵会话**：
   - 各阶段调用 LLM 时均拉起独立的无状态消息上下文（Stateless Invocation）。
   - 绝不沿用 LangGraph 自带的全局无限追加式 `MessagesState`，有效防止 Token 爆炸与注意力崩溃。
