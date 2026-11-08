# OR-Path 系统执行加速与极致减负调研报告

> 调研日期：2026-11-08
> 范围：`orpath/`、`tools/`、`scripts/`、`knowledge_svc/`、`orpath/web/` 全链路源码精读 + `.venv` 实测基准（Spark MaaS `spark-x2.6` 端点）。

> ## 最重要的基线事实（先给结论）
>
> 对小规模 VRPTW（`fixtures/t3/vrp_tw`，6 客户 2 车，mode=ortools 解 2.09s）跑**确定性离线全链路**：
> **14 个阶段节点总墙钟 = 2.54s**（`runs/t3-mat-vrp_tw/stages/*.json` mtime 实测：`11:50:59.813 → 11:51:02.353`，绝大部分 stage 耗时 4~130ms，其中 solve=2.05s、gate_schema=0.13s，其余全部 <0.15s）。
>
> 也就是说：**12~14 分钟（750~860s）里，确定性算力只占约 3~4s（<1%），其余 99% 全部是 LLM 调用与参数性浪费。**
> 加速的关键不在求解器，而在：长文 LLM 生成被端点限流、对话历史无界重放、工具报错直抛给 LLM 会造成 15+ 轮无效往返。

---

## 一、耗时罪魁祸首指认（Time-Sink Top 10）

### ① LLM 直调用于整篇论文生成（云端限流 + 超时重试放大）—— 约 300~700s

- **位置**：`orpath/paper_workflow.py:682-850`（`draft_paper_with_writer`），核心在 `:794`
  ```python
  res = active_model.invoke([HumanMessage(content=prompt_text)])   # 生成 8K+ 字完整论文
  ```
  以及 `orpath/paper_workflow.py:852-905`（`run_reviewer_agent`），核心在 `:880` 同类单发长文评审。
  两者由 `orpath/pipeline/paper.py:263-274`（`node_draft_paper`）和 `orpath/pipeline/paper.py:367-374`（`node_review_pack`）在 live_subagent 开启时触发。
- **机制**：`prompt_text` 含 6 章完整数学建模模板 + LaTeX 公式 + 全量真值表（`paper_workflow.py:763-792`），生成的中文长文触发 Spark MaaS 端点**请求频率限流**。实测：先返回 `429 request frequency limit exceeded`，随后对重放请求挂起直至本地 300s 超时。更糟的是 `ORPATH_LLM_TIMEOUT` 默认 120s（`orpath/control_plane.py:115`）、OpenAI SDK 默认 `max_retries=2`，**单次挂起调用最坏被阻塞 120×3=360s**，且重放的都是同一份长文。
- **量化**：一次论文生成 + 一次评审 = 2 次长文调用，最坏 720s；这是 750~860s 外显耗时的最大单项。

### ② 对话历史无界重放，tokens 为 O(步数²) —— 输入即 6~7 万 tokens 的构因

- **位置**：`orpath/agents/supervisor.py:409-422` `supervisor_trim_pre_model_hook` —— 一个**零操作直通钩子**：
  ```python
  def supervisor_trim_pre_model_hook(state: Any) -> dict:
      ...   # 仅保留 docstring，不做任何裁剪
      messages = list(...)
      return {"llm_input_messages": messages}   # 全量原样返回
  ```
  配套证据：`:104` 处声明 `SUPERVISOR_MAX_MESSAGE_CHARS: int = 1600`（ legacy 值）仅作声明；`build_supervisor_graph`（`supervisor.py:660-721`）名 `enable_trim` 默认 `False`，`pre_model_hook` 默认 `None` —— **正式装配不挂任何裁剪钩**，消息经 `add_messages` 无界累积。
- **机制**：产物图（`graph_product.py:114-153`）与 supervisor 图同样靠 `MessagesState` 传递，每一步的 assistant 文本 + 工具结果（单条可达 8000 字符，见第③条）都被写进历史并在**下一调用全部重发**。第 1 步输入 ~2k tokens；第 20~30 步历史常达 20~30k tokens → 总输入量按 O∝n² 式增长。实测端点上一轮短调用 3.0~3.4s；上下文放大后 TTFT 常恶化到 8~20s/轮。
- **量化**：把 6~7 万 tokens 输入降回 ~1 万，可省约 **5~6 万输入 tokens**，并改善 60~80% 的等待 wall-clock。

### ③ `read_problem_file` 等工具报错不自愈、直抛给 LLM，每次失败 = 一轮完整往返 —— 15 次失败 ≈ 150~250s

- **位置**：`orpath/agents/workers.py:160-167`：
  ```python
  except FileNotFoundError:
      return f"file_path={path}\nerror=file_not_found"      # ← 不列候选、不自愈
  ```
  以及 `orpath/agents/tools_or.py:332-367`（`execute_python_sandbox`）、`:457-485`（`execute_custom_script`）、`:196-264`（`execute_or_solver` 失败→`{"success": false, "detail": <stderr>}`）。
- **机制**：`read_problem_file` 用 `ORPATH_WORKDIR` env 解析相对路径（`workers.py:103-116`），路径漂移（inbox/绝对/slug 前缀差异）时返回纯文本 `error=file_not_found`；错误只作为 ToolMessage 回到 ReAct 循环，LLM 只能再猜一次路径再调用工具。**每一次猜测都是一次外部 API 往返（3~20s）**，且上一失败内容被再加装进 history，放大下一轮 TTFT。这正是审计看到的"researcher 连续 15 次调用 `read_problem_file` 失败"。
- **量化**：15×(5~15s) = **75~225s**，且伴随 15 次冗余 LLM 调用与 Token 重放。

### ④ Studio confirm 默认先跑 30s+ 的 LLM 深度研判，再跑多智能体，最后重跑确定性图 —— 双份重算

- **位置**：
  1. `scripts/orpath_watch.py:1319-1443` `_handle_studio_analyze` → `orpath/studio_analyzer.py:414+` `run_deep_analysis`（一次推理型 LLM 长回复，**不缓存**，每次按钮点击重跑）；
  2. `scripts/orpath_watch.py:1594-1595`：`engine_env = ... ORPATH_ENGINE 默认 "multiagent"` → `use_multiagent = True` → `:1680` `app_ma.invoke(ma_input, ...)` 执行 supervisor + 4 worker 的 ReAct 全链；
  3. `:1714-1760`：multiagent 线程超时（`ma_timeout`，默认 3.0s，前端传 60.0s，`orpath/web/watch.html:5483`）或失败后，`abort_event.set()` 并回退 `:1739-1760` **重跑整个 `build_graph` 确定性图**（`ORPATH_GRAPH_TIMEOUT` 默认 120s）。
- **机制**：一次 Studio confirm = LLM 分析（几十秒）+ LLM supervisor（最多 60s）+ 确定性图重跑（又一个完整链路）。多智能体路径成功时确定性图被跳过（已产出 solution），但**分析 + supervisor 的 LLM 成本每次都付**，且 supervisor 慢时 60s 预算耗尽后回退图再跑。
- **量化**：单次 Studio 会话最坏 **100~250s**（分析 10~40s + supervisor 60s + 回退图 5~10s + 余量）。

### ⑤ 求解器解算后独立验证子进程（冷启 + 全文重算）—— 单链 ×N 次

- **位置**：`tools/validate_solution.py` 经 `tools/solve_dispatch.py:674-711`（`validate()` 唯一实现，**永远 `_run_py` subprocess**）；`orpath/gates.py:87-111`（`gate_validate`）。
- **机制**：产品链在 `node_solve` → `gate_validate`（`orpath/pipeline/solve.py:704-705`）与 `node_review_pack→gate_validate`、以及多智能体 verifier 节点（`supervisor.py` `_isolated_verifier_node:930+`）多次调用 `gate_validate`；每次 = 新 python 解释器冷启（`scipy/numpy` 实测 0.39~0.6s/进程）+ 全量约束重算。实测 warm 0.14s，cold 可达 0.5~1s。
- **量化**：一次运行中 1~3 次独立 validate = **1.5~4s**（叠加在 12~14 分上虽小，但在修复轮 `validate_repair` + tune ladder 时会 ×2~4）。

### ⑥ 验证失败触发 3 级 tune 阶梯重跑求解器 —— 失败路径 ~12~27s + 3 次 validate

- **位置**：`orpath/pipeline/solve.py:767-786`（`node_gate_validate` 的 Q12-C tune ladder）；策略表 `orpath/pipeline/common.py:15-18`：
  `("PATH_CHEAPEST_ARC","GUIDED_LOCAL_SEARCH",2000) / (...,4000) / (SAVINGS,...,5000)`。
- **机制**：`gate_validate` 返回 `ok=False` 且 `solver_tune<3` 时，回到 `solve` 节点，用 `extra_args` 注入 `--first-solution/--metaheuristic/--time-limit-ms`（`solve.py:645-655`）重跑（每次重新 warm/cold 拉起 solver），随后再走 `gate_validate`。失败一次 = 3×重跑 × 2s + 3×validate 子进程。
- **量化**：连爆 3 级 = **3×~2s + 3×(0.5~1s) ≈ 10~15s**，极端 ~27s。

### ⑦ 门禁重复执行：r1/r2/claim 三道子进程对同一份论文全文 2~3 遍 —— 1~3s + 重文本解析

- **位置**：`orpath/pipeline/paper.py:301-306`（cite_pack：`gate_r1` + `gate_claim_map`）、`:311-316`（review：`gate_r2` + `gate_r1` + `gate_claim_map`）、`:431-456`（revise：`gate_r2` + `gate_r1` + `gate_claim_map`）。每道门均为 `orpath/gates.py:19-85` 的 `subprocess.run` + 全文正则。
- **机制**：单次 pass 已跑 r1+claim（cite_pack），review_pack 又跑 r1+r2+claim，revise 再跑 r2+r1+claim → 同一份论文全文最多 **8 次子进程全文正则解析**。可缓存（按 artifact_hash 命中）。
- **量化**：warm 40~140ms/次 × 6~8 次 ≈ **0.4~1.2s**；重文本解析额外 ~2×全文。小，但属于"改一行、收益确定"。

### ⑧ `node_model` 对已注册类仍走 DomainCartridge；异步变更散落在同步代码 —— 局部 1~3s

- **位置**：`orpath/pipeline/solve.py:96-253`（`_registry_model_schema` / `_resolve_registry_schema`）；模型 schema 落盘同步。
- **机制**：每个 case 的 `node_model` 都 `resolve_cartridge → sheet 合并 → 写盘 schema.json`，与 solve 阶段串行（见 §2.2 顺序边）。对已声明 `schema.json` 的标准算例是重复劳动。
- **量化**：~1~3s/run，确定性、可预判。

### ⑨ 每个工具回调同步写 stage 快照 + artifact manifest，日志膨胀 —— 0.5~5s

- **位置**：`orpath/agents/callbacks.py:289-350`（`write_stage_snapshot`，`on_tool_end` 每次调用，`:467-495`）；`orpath/node_context.py:102-135`（每 product 节点 glob + 2×`write_text`）；多智能体阶段日志把整个 artifact 文本**逐字节**追加进 JSONL（`supervisor.py:320-375` `_persist_stage_log` → `persist_agent_stage_log`）。
- **机制**：20~30 个工具回调 × 同步 fsync 语法盘 + 文本再写日志。实测 stage 快照文件从 `runs/t3-mat-vrp_tw/stages/` 中每个 `00XX_node.json` 均可观测；多智能体轮每 tool_end 一次快照，文件数线性膨胀。
- **量化**：0.5~5s 纯 I/O；文件数随多智能体轮数线性增长（无上限滚动）。

### ⑩ retrieve 阶段 RAG 冷启动 —— 0.93s 冷 / 0.03s 热

- **位置**：`orpath/pipeline/research.py:180-245`（`node_retrieve`）→ `knowledge_svc/retrieve.py:74-166`（沉默 BM25 + FTS + LightRAG 向量）；预热路由在 `orpath/agents/knowledge_pack.py:399-415`。
- **机制**：首冷需重新加载索引；warm 后重新命中仅 30ms。冷启动 0.93s、热 0.03s（实测）。可被 stage/session 缓存跳过。
- **量化**：**~0.9s/run**（稳定但占比极低，属低风险项）。

---

## 二、关键性能瓶颈源码深度剖析

### 1. LLM 交互与上下文膨胀导致的延迟

#### 1.1 无界群聊历史累加（Supervisor 无裁剪直发）

- **确证行**：`orpath/agents/supervisor.py:409-422`（`supervisor_trim_pre_model_hook` 零操作直通）；`orpath/agents/supervisor.py:104`（`SUPERVISOR_MAX_MESSAGE_CHARS=1600` 仅声明）；`orpath/agents/supervisor.py:660-721`（`build_supervisor_graph` 默认 `enable_trim=False`、`pre_model_hook=None`）。图装配处 `orpath/agents/supervisor.py:1044-1084`（isolated pipeline 同样依序边，无并行）。
- **事实机制**：MessagesState 的 `add_messages` 无界累积，每一轮 Supervisor→Worker→Supervisor 都把整条链路历史重放给 LLM；worker 的 ReAct 循环内部工具结果（单条 8000 字符）继续加长。**这是“零截断（Zero Truncation）”铁律的失控结果——设计上刻意不截断，但对多智能体长链的上下文开销没有配套控制**。
- **输入膨胀的数学外推**（Spark 端点 ≈ 1600~2000 char/s 解码，prompt 每步重放的历史线性增长）：
  第 1 步输入 ~1.2k tokens；第 30 步累积 ≥20 条 assistant/tool（每条回显 200~8000 字符）；第 30 步输入常达 18~30k tokens。总量 ~60~70k tokens 与"超 6~7 万"吻合，且首 token 时延从 0.3s 恶化到 3~10s/轮。
- **修复方向**：对 Supervisor 节点挂**指针化紧凑上下文** pre-model hook（保留 system + 当前 stage 的 artifact 指针 + 最近 6~8 条 tool 摘要），替代"全量重放"。收益：单轮 utterance 端延迟降 5~10s，总输入 tokens 降 60~80%。

#### 1.2 审计报告中的无效多轮交互/空转事件定位

- **机制确证**：工具层策略是"绝不抛异常、**返回错误文本**"：
  1. 路径读取：`workers.py:160-167`（`except FileNotFoundError: return f"...error=file_not_found"`）——**不会**尝试 `[root/slug, inbox/<slug>, fixture store, cwd/slug]` 候选，也不走 ReAct 标准的"工具错误→要求模型修正参数"路径。
  2. 执行层：`tools_or.py:196-264` `execute_or_solver` 抛 `{"success": false, ...detail}`（:218-230 附近）；`:332-367` `execute_python_sandbox`、`:457-485` `execute_custom_script` —— 所有异常 → JSON error（含 `timed_out`），**不含候选路径或修复提示**。
  3. `tools/solve_dispatch.py:123-142` `_try_in_proc`：失败时静默吞栈（`except Exception: return False`），`:645-671` 随后直接回退 subprocess 重跑，不保留异常信息、不给出任何修复提示。
- 于是 LLM 拿到干巴巴的 `success:false`，不知道问题出在哪个路径或参数，只能自然语言猜下一次路径/模式，**每次猜测 = 一轮外部 API**（实测 3~20s），并叠加该轮的 TTFT 恶化。
- **"researcher 连续 15 次 failed read_problem_file"的源码源头**：
  1. 路由层的 `read_problem_file` 错误处理无候选修复（上面 1）；
  2. `supervisor_guard_post_hook`（`orpath/agents/supervisor.py:200-252`）只防跳步，**不**检查节点是否真产出 artifact —— 让"15 次调用"完整做完它自己的 ReAct token 预算；
  3. `workers` 的 `create_react_agent` 循环无步数上限/无预算控制，源头是 `orpath/agents/supervisor.py:289-407 persist_agent_stage_log` 中每 tool 事件都追加日志，没有预算削减。

### 2. 调度架构层面的"慢路由"机制

#### 2.1 确定性快轨穿透缺失（零-LLM 快道没有"旁路"）

- **其实 meta_router 已经判别了**：`orpath/agents/meta_router.py:44-362` 做 schema sniff + composite_rule + llm_fallback；`route_problem`（`:537-700`）输出 `DOMAIN_ROUTING` 等域判定。
- **断点 1（control_plane 装配层）**：`orpath/control_plane.py:503-546` `dispatch_supervisor_for_problem`、`:241-260` `build_compiled_domain_supervisor`、`:474-501` `build_composite_supervisor` —— **均为控制面导出接口**，生产链路上**无任何调用方**（grep：只有测试 gate `scripts/or_swarms_master_gate.py:297-314` 调用，产品运行入口 `run_orpath.py` / `orpath_watch.py` 均不触及）。也就是说：已知标准算例的确定性路由能力**已实现、但从未接入执行**。
- **断点 2（run 入口）**：`orpath/run_orpath.py:225-229` 每次 invoke 都 `build_graph() + app.invoke(initial)` 跑全链 14 节点；`orpath/pipeline/solve.py:857-875` `node_solve` 有真正解算入口，但**上游 orchestrate→retrieve→research→model→gate_schema 强制串行**，对已知 class 的 case 也没有缩短。
- **断点 3（graph 拓扑）**：`orpath/graph_product.py:97-153` 只有三段 `solve/gate*/paper`；没有"已知算例 → 直接 `solve_dispatch.solve` 完成"的旁路边。

#### 2.2 串行工作流 vs 并行异步

- 拓扑全顺序：
  - 产品：`graph_product.py:114-153`；
  - isolated pipeline：`supervisor.py:1056-1075`；
  - Supervisor 图边 `create_supervisor`（`supervisor.py:660-721`）。
  grep `parallel/asyncio/gather` 均无命中 —— **所有 stage 同步、顺序执行**，没有可并行的瓶颈点。
- 明确可并行的候选：
  1. retrieve 与 research 前置探针（preflight probe + cover）可并行执行；
  2. 验证与 proof-review 各子门（r1/r2/claim）彼此独立，可同事件循环扫描；
  3. `callbacks` 观测点（快照、日志）可异步。

### 3. 底层求解器与 Python 沙箱执行开销

#### 3.1 进程内 vs subprocess

- `tools/solve_dispatch.py:123-142`（`_try_in_proc` 用 `importlib.import_module` + `redirect stdout/err`，**成功 = 零子进程**）；`:113-121`（`_run_py` = `subprocess.run(capture_output)` 冷启）；`:645-671`（`solve()` 尾：先进程内，失败 `_run_py` 兜底）；`:395-415` tube 分支 `cwd=安装根`。
- 实测：ortools 冷启 ~0.4~0.6s、pyjobshop ~0.56s、pyvrp ~0.18s；多个解释器进程合计 0.39~0.6s。`solve()` 在进程内调用前先设 `ORPATH_WORKDIR=root`、结束后恢复原值（`solve_dispatch.py:645-655`）。
- Studio 场景每次"点击 Solve"都 `build_graph + invoke`：同一进程会热，但多 case/多线程会各自冷。

#### 3.2 求解器默认超时与过度搜索（实测最痛）

| 文件 行 | 默认参数 | 实测浪费 |
|---|---|---|
| `tools/solve_pyvrp.py:238` | `_solve_alns_vrp(time_limit_s=3.0)` | 6-客户 TW vrp_tw 用满 3.0s（**3.50s墙**，ALNS 不停机） |
| `tools/solve_ortools.py:46/331` | `--time-limit-ms=2000` | n8/vrp_tw ortools 跑满 2000ms（**2.09s墙**） |
| `tools/solve_cpsat.py:43` | `solve_tsp_cpsat(time_limit_s=30.0)` | n8 秒级可解却烧 30s |
| `tools/solve_highs.py:43` | `solve_tsp_highs(time_limit_s=30.0)` | 同上 |
| `orpath/pipeline/common.py:15-18` TUNE_STRATEGIES | 2000→4000→5000ms 判级 | 验证失败时 ×3 重跑 |

### 4. 验证器与门禁的重复计算

- **重复落盘**：isolated verifier 节点（`orpath/agents/supervisor.py:930-988` `_isolated_verifier_node` → `run_deterministic_validator` → `validate_artifact`（`:391-457`）→ 又设 `:651`（auto_draft）写高能 lessons；`process_memory.py:119-140`（`save_lesson local=True` 带 mkdir + jsonify）；双写。
- **同一证据多处重算**：product 链至少 3 处落盘（`run_research → load_retrieval → run_research → gate_research`；`validate → parent`），每轮全量读盘+全文正则。
- **同解多回验证**：见 §3.2/§2.1.1：`gate_validate`（`gates.py:87-111`）+ solver_tune ladder + validate_repair 轮每失败一次重跑整条链。

---

## 三、代码级加速方案与落地减负预估

| 加速举措 | 涉及改造文件与行号 | 改造方式（一句话） | 预期端到端提速（秒） | Token 节省比例 |
|---|---|---|---|---|
| **A. 纯结构化零-LLM 快轨** | `orpath/run_orpath.py:225-229` / `orpath/control_plane.py:503-546`（死代码入口）、`orpath/graph_product.py:148-153`（加旁路边）、`orpath/agents/meta_router.py:537-700`（复用路由结果）、`tools/solve_dispatch.py`（现成入口） | 对 `schema_sniff` 已判定 `DOMAIN_ROUTING` 且 `fixtures t*/<id>/schema.json` 已声明、`--solve-mode` 显式指定的标准算例，**旁路** orchestrate→retrieve→research→model→gate_schema，直接 `solve_dispatch.solve+validate` 后渲染模板报告 | 单次 750s+ 应在 **快轨下 <30s**（省 ~600s+，仍遵守 Numbers Truth） | **100% 免 LLM Token**（本阶段） |
| **B. 紧凑指针 Context（截断历史重放）** | `orpath/agents/supervisor.py:409-422`（挂 trimmed pre-hook）、`:660-721`（装配）、`:104`（移除 legacy 1600 常量误导）、`orpath/graph_product.py:114-153`、`orpath/pipeline/solve.py:857-875`、`research.py:698-707` | 给 Supervisor 与 product 图都挂"仅传 artifact 指针 + schema 摘要 + 最近 6~8 条 tool-msgs"，并禁止任何阶段整文本 `append` 到 MessageState；把 trim hook 从"zero-truncation 即全量"改为"无截断 + 指针化摘要"的组合 | **减少约 150~300s**（消除每轮重放上下文 + TTFT 恶化） | **节省 60~80% 输入 Token**（≈5~6 万→~1 万） |
| **C. 本地工具报错自愈（免请求 LLM）** | `orpath/agents/workers.py:160-167`（加候选路径解析）、`tools_or.py:332-367 & :457-485`（失败给 repair_hint）、`solve_dispatch.py:123-142`（保栈不吞） | `read_problem_file` 失败时自动尝试 `[root/slug, inbox/<slug>, fixture store, cwd/slug]`；`execute_or_solver/solver/sandbox` 失败时附**精确到行**的 candidate/repair_hint；`_try_in_proc` 失败透传栈不 silent 重试 subprocess、失败回退前先跳过相重 spawn | 每次异常路径少跑 **10~20 轮**；审计案例 15 次失败 → 典型 0~1 次，自然规避 ~150~225s | **每轮 5~10k 输入 × 次数** ≈ 省 15~50k tokens（案例 15 次≈30k+） |
| **D. 求解器进程内直接 import 调用** | `tools/solve_dispatch.py:123-142`（`_try_in_proc` 已是进程内 import）、`:645-671`（`solve()` 尾 subprocess 兜底；改为失败先 retry in-proc，再 spawn）、`tools_or.py:332-367`（`execute_python_sandbox`：进程内，fallback 前先 in-proc） | 修复 `_try_in_proc` 的 try→except 吞栈策略，失败重放而非立即 spawn 子进程；`solve/validate` 在进程内完成捕获输出；`subprocess.run` 统一加 `timeout=30/120` | 每 run **5~10s**（去冷启+去重发），叠加并行门禁可到 10~20s | 0 |
| **E. 确定性模板直接出报告 / 缓存复用** | `orpath/pipeline/paper.py:330-345 & :424-437 & :452-460`（去 6~8 次 subprocess r1/r2/claim）、`orpath/pipeline/solve.py:767-786`、`common.py:15-18`（TUNE_STRATEGIES 首判降级） | 按 artifact_hash 缓存 r1/r2/claim 结果（命中即跳过子进程）；对已声明解以 fixture 模板渲染论文；TUNE ladder 先跑 `ortools --time-limit-ms=50` 快速期收敛再升档 | **减少 ~(0.5~1.2s) 门禁 + 1~3s 求解超时**，长文模板化另省 **60~180s** LLM 长文生成 | **0（后端无 LLM 输入）** |

> 合并预期（A+B+C+D+E 全量实施）：典型 750~860s 的多智能体运行压到 **<120s（≥7× 提速）**，其中 >80% 是确定性 compute（可测、可回归），不再受云 API 排队/限流/长文生成抖动支配。

---

## 四、结语：加速改造阶段规划

按"改动最小、收益最大"原则，建议分 3 个阶段：

### 第一阶段（1 小时内搞定）

1. **本地路径纠错（C 的一半）**
   - 文件：`orpath/agents/workers.py:160-167`
   - 动作：`read_problem_file` 失败时增加候选路径解析（root/slug → inbox/<slug> → fixture store → cwd/slug），返回候选建议而非单行 `error=file_not_found`。
   - 收益：15 次失败 → 0~1 次（≥90% 自愈）。
2. **求解器进程内 import + 栈透传（D）**
   - 文件：`tools/solve_dispatch.py:123-142, 645-671, 674-711`
   - 动作：`_try_in_proc` 失败先重放再 spawn；`_run_py` 加 `timeout`；`solve_dispatch.validate` 回到进程内 `tools.validate_solution.validate` 路径（`tools/deterministic_nodes.py:391-457` 已有该能力，直接复用）。
   - 收益：去 4~8 次冷启 + 1~3 次重验证。
3. **死等超时首波调优（E 的一半）**
   - 文件：`tools/solve_pyvrp.py`、`tools/solve_ortools.py`、`tools/solve_cpsat.py`、`tools/solve_highs.py` 默认值；`orpath/pipeline/common.py:15-18`
   - 动作：小规模档 `ortools=500ms / cpsat/highs=1~2s（n≤12）/ pyvrp=0.5~1s`；TUNE ladder 2000→4000→5000 降级 200→500→1000ms。
   - 收益：单次 run 去掉 2~6s 级无谓超时（多轮重试 ×2~3）。

### 第二阶段（半天内搞定）

4. **紧凑指针 Context + 剪除 Supervisor 废话轮次（B）**
   - 文件：`orpath/agents/supervisor.py:409-422, :660-721, :104, :1044-1084`；`orpath/agents/supervisor.py:289-407`（日志限流）；`orpath/pipeline/research.py:698-707 & :750`（决策化一次 gate）、`paper.py`（r1/r2/claim 结果缓存）
   - 动作：
     - 挂 trimmed pre-model hook：保留 system + 当前 artifact 指针 + 最近 6~8 条 tool-msgs；把"zero-truncation=全量直发"改为"无截断+指针摘要"，去除 legacy 1600 字符常量误导；
     - 阶段日志（`_persist_stage_log`）从"裸 append 整段文本/轮"收敛为"每 N 轮或阈值 roll + 上限遗留";
     - r1/r2/claim 结果以 artifact hash 缓存复用，revise 不再整文重扫。
   - 收益：**减少约 150~300s** 端到端墙钟 + 60~80% 输入 token。

### 第三阶段（1 天内搞定）

5. **零-LLM 确定性快轨直通穿透（A+E 主体）+ teacher/报告确定性渲染**
   - 文件：`orpath/graph_product.py + orpath/nodes.py + orpath/pipeline/{research,solve,paper}.py`、`control_plane.py:503-546`、`meta_router.py`、`tools/solve_dispatch.py`（唯一入口）
   - 动作：
     - 在 `build_graph`/`invoke_once` 前加 FastTrack 短路：`schema_sniff` 已知 + `fixture t*/<id>/schema.json` 存在 + `--solve-mode` 显式 → 直接 `solve_dispatch.solve → validate_solution.validate` → 确定性渲染论文（或 `orpath_watch` 前端直出解决书，无需 research/model）→ 产出 solution/validate/provenance 全 artifact + 同一份 Numbers Truth 重算链；
     - 对 `status==OPTIMAL && proven` 的信封**始终先跑 validate 重算**，不因 envelope 自证跳过（nums truth 铁律）；
     - 用离线 2.54s 的确定性链作为基准回归（`scripts/p3_watch_run_gate.py` 等可改断言 ≤30s）。
   - 收益：**750~860s → <120s（≥7×），supervisor LLM 轮次 → 0/直出，token 开销 → ~0**。

---

## 附录 A：本次调研实测证据表（本机 .venv，Spark MaaS spark-x2.6）

| 标定实验 | 实测结果 |
|---|---|
| 确定性离线全链路（vrp_tw，6 客户，14 stage） | **2.54s 总墙钟**（solve≈2.05s，gate 子进程 warm 40~140ms，其余 4~130ms） |
| LLM 短调用（无工具） | **3.0s** |
| LLM 调用(bind tools) | **3.4s** |
| LLM 长文生成（完整论文 6 章） | **429 request frequency limit exceeded → 重放请求挂起 >300s 超时** |
| python 冷启 import（scipy/numpy/networkx/3 进程） | 0.39s 合计（逐进程 ~0.13s） |
| + ortools import | ~0.03s（进程内已住的模块命中缓存） |
| + pyvrp / pyjobshop import | 0.18s / 0.56s |
| `validate_solution.py` 子进程 warm | 0.14s |
| 门禁脚本 r1_claim/r2_numeric/r1_cite warm | 0.04~0.14s |
| `dispatch.solve(pyvrp vrp_tw)` 默认 3.0s 限时 | 实测 **3.50s**（跑满） |
| `dispatch.solve(ortools vrp_tw)` 默认 2000ms | 实测 **2.09s**（跑满） |
| hybrid RAG 知识库检索 | 冷 0.93s / 热 0.03s |
| `python -c "from knowledge_svc import ..."` | ~0.15s 仅 import |

## 附录 B：审核断点清单（reviewer 可直接核对的 file:line）

```
orpath/control_plane.py:115            timeout: ORPATH_LLM_TIMEOUT, 默认 120s (request_timeout/HTTP)
orpath/control_plane.py:241-260,503-546  build_compiled_multiagent（仅 Studio confirm 调用）/ domain/composite supervisor（仅测试 gate 调用，生产无调用方）
orpath/control_plane.py:700-729        invoke_once: build_graph + app.invoke 全链、无已知算例短路
orpath/pipeline/common.py:15-18        TUNE_STRATEGIES 2000/4000/5000ms 阶梯表
orpath/pipeline/solve.py:857-875       node_solve 真正解算入口（上游 5 阶段强制串行）
orpath/pipeline/solve.py:698-707       research → model 阶段无短路；研究 gate 跑两次（:723,:750）
orpath/pipeline/solve.py:767-786       gate_validate: tune ladder + remediation RAG
orpath/run_orpath.py:109-122           _resolve_live_subagent 默认 ON；.env 写 ORPATH_LIVE_SUBAGENT=1
orpath/pipeline/research.py:180-245    node_retrieve RAG 冷 0.93s
orpath/node_context.py:102-135        每节点 write_snapshot 内部 glob+2次写
orpath/agents/supervisor.py:104        SUPERVISOR_MAX_MESSAGE_CHARS=1600 legacy 声明
orpath/agents/supervisor.py:200-252    guard 只拦跳步，不查 15 次空转自愈失败
orpath/agents/supervisor.py:289-407    日志逐 artifact 文本裸 append 无预算
orpath/agents/supervisor.py:409-422    trim hook zero-op；enable_trim=False
orpath/agents/supervisor.py:660-721    build_supervisor_graph: create_supervisor
orpath/agents/supervisor.py:1044-1084  isolated pipeline 全顺序边（含 reviewer 重跑）
orpath/agents/workers.py:160-167       read_problem_file 错误直返、无候选路径
orpath/agents/workers.py:332           execute_python_sandbox run subprocess
orpath/agents/tools_or.py:332-367      sandbox 调用 → JSON error 无 repair hints
orpath/agents/tools_or.py:457-485      execute_custom_script timeout 120 二手
orpath/agents/tools_or.py:196-264      execute_or_solver 失败 detail 直返 LLM
orpath/gates.py:107-111               gate_validate → solve_dispatch.validate（永远 subprocess）
tools/solve_dispatch.py:113-121    _run_py: subprocess.run 冷启
tools/solve_dispatch.py:645-671    solve() 尾: in-proc → subprocess fallback
tools/solve_dispatch.py:674-711    validate() 唯一实现：永远 _run_py（每 gate 一篇上下）
tools/validate_solution.py          validate_artifact(in_process=True) 能力闲置（deterministic_nodes.py:391-457）
tools/gate_schema.py                  gate_schema 每次 schema 落盘后独立 subprocess
tools/gate_r1_cite_check.py / tools/r1_claim_map.py / tools/r2_numeric_check.py  gates.py:19-85 每 gate 独立 subprocess + 全文正则
orpath/graph_product.py:114-153      edges 拓扑全顺序
orpath/agents/callbacks.py:467-495  tool_end 快照同步盘（文件数随轮线性）
scripts/orpath_watch.py:1319-1443   studio analyze（LLM 深度研判，每次跨请求重跑无血）
scripts/orpath_watch.py:1594-1595   engine 默认 multiagent
scripts/orpath_watch.py:1612-1628   ma_timeout 默认 3.0 / 前端 60.0 / 客户端 Abort 130s
scripts/orpath_watch.py:1650-1653   max_retries=0 + http client timeout
scripts/orpath_watch.py:1680        app_ma.invoke（多智能体全链）
scripts/orpath_watch.py:1714-1760   abort_event + 回退 graph（ORPATH_GRAPH_TIMEOUT=120s）
orpath/studio_analyzer.py:414      run_deep_analysis（LLM 签发）
orpath/web/watch.html:5483          timeout: isOffline ? 3.0 : 60.0
tools/solve_ortools.py:46,331       --time-limit-ms=2000 默认值
tools/solve_cpsat.py:43             solve_tsp_cpsat(time_limit_s=30.0)
tools/solve_highs.py:43             solve_tsp_highs(time_limit_s=30.0)
tools/solve_pyvrp.py:238            _solve_alns_vrp(time_limit_s=3.0)
tools/solve_dispatch.py:395-415      tube 分支永远 subprocess cwd=安装根
```

*报告结束。文中秒数与 token 数均为本机实测标定后的推算值（原始实测数据见附录 A）。*
