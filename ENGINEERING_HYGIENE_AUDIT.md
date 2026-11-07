# OR-Path 工程卫生全局审计清单

> **审计类型**：只读静态扫描（未修改任何文件）
> **扫描时间**：2026-11-07
> **范围**：`dazzling-bell` 全仓（排除 `.git/`、`.venv/`、`node_modules/`）
> **方法**：`git ls-files` 区分「被 Git 跟踪的源码」与「本地忽略的运行产物」；AST 扫描未用导入 / 重复函数体 / 孤儿符号；MD5 比对重复数据集；正则排查调试残留 / 注释垃圾 / 命名混乱。
> **标记约定**：✅ = 高置信（已用 MD5/证据验证）；⚠️**【疑似】** = 需人工复核，扫描器可能误报（如 `__init__.py` 再导出、gate marker 重导出、动态字符串导入）。

---

## 0. 总体数字

| 指标 | 数值 |
|---|---|
| 全仓文件数（排除 .git/.venv） | **11,159** |
| 磁盘占用（排除 .git/.venv） | **442 MB**（含 .venv 约 2.4 GB） |
| Git 跟踪文件 | **1,547** |
| Git 跟踪 `.py` 文件 | **306** |
| 真实未用导入（去 `__future__`/再导出误报后） | **142 处，涉及 65 个文件** |
| 归一化后完全重复的函数体 | **17 组**（最严重的为 10 份拷贝） |
| 字节级重复数据集（eval vs fixtures） | **21 个 JSON 文件完全一致** |
| 遗留兼容 shim / 疑似孤儿模块 | **6 个** |
| 本地忽略的运行产物（runs/memory/outputs 等） | **>9,200 文件** |

---

## 1. 高置信问题 ✅

### 1.1 `eval_or_bench/instances/` 与 `fixtures/benchmarks/` 数据集完全重复
- **证据**：`eval_or_bench/instances/{att48,bayg29,burma14,eil51,gr17,kroA100,swiss42,ulysses16}/` 下 **21 个 `*.json`（coords / distance_matrix / whitelist_refs）与 `fixtures/benchmarks/` 同名文件 MD5 完全一致**（逐对校验，21/21 命中）。
- **示例**：`eval_or_bench/instances/att48/coords.json` 与 `fixtures/benchmarks/att48/coords.json` → `1f21605d…` 相同。
- **叠加重复**：`eval_or_bench/raw_tsp/*.tsp`（8 个原始 TSPLIB 实例，已被 git 跟踪）→ 由 `eval_or_bench/tsplib_converter.py`、`build_raw_tsp.py` 生成 → 再产出上述 `instances/`，而同一批结论又落在 `fixtures/benchmarks/`。**同一数据至少三处落盘。**
- **建议**：保留单一权威源（建议 `fixtures/benchmarks/`），`eval_or_bench/instances/` 改为构建期生成或干脆删除；`raw_tsp/` 明确是否仍需入库。

### 1.2 十个域级 `*_redteam_gate.py` 为近乎逐行拷贝的克隆（违反 AGENTS.md「No 900-Line Domain Clones」）
- **涉及文件**：`scripts/{facility,finance,inventory,microgrid,pricing,project,rostering,routing,scheduling,tube}_redteam_gate.py`（10 个，合计 **≈5,400 行**）。
- **证据**：归一化函数体哈希在 10 个文件间**完全相同**：
  - `_dig`（18 行）× 10 处
  - `build_attacks`（28 行）× 10 处
  - `run_redteam`（48 行）× 10 处
  - `main`（29 行）× 8 处
- **附带**：`scripts/universal_redteam_gate.py`（577 行）已是通用化版本，与 10 份克隆职责重叠，存在「通用版 + 域克隆版」双轨维护。
- **建议**：抽公共骨架到单一模块（域差异仅注入数据/断言），或统一收敛到 `universal_redteam_gate.py`。

---

## 2. 重复代码 ⚠️【疑似】（需人工确认是否为有意的独立实现）

除 1.2 的大规模克隆外，AST 归一化发现以下**跨文件完全相同的函数体**（多为测试夹具或工具函数被复制多份）：

| 组 | 函数 | 出现位置（示例） | 说明 |
|---|---|---|---|
| 5 | `_type_ok`/`meta_type_ok` | `tools/test_task32~35_*.py`、`orpath/agents/contract_validator.py` | 4–6 份拷贝 |
| 6 | `_validate_meta` | `tools/test_task32/33/34/35_*.py` | 4 份相同 |
| 7 | `_resolve_root` | `contract_validator` / `domain_analytics` / `supervisor` | 3 份 |
| 8 | `test_redteam_cli_rejects_malformed_solution` | `test_task36/37/39/38/310` | 多份相同测试 |
| 9 | `on_chain_error` / `on_tool_error` | `orpath/agents/callbacks.py`（同文件内） | 疑似可合并 |
| 10 | `_resolve_root` | `orpath/agents/tools_or.py` / `workers.py` | 2 份 |
| 12 | `_collect_solution_tokens` | `tools/r1_claim_map.py` / `r2_numeric_check.py` | 2 份 |
| 13 | `_load_matrix` | `tools/solve_cpsat.py` / `solve_highs.py` | 2 份 |
| 14/15 | `load_dimacs` / `_graph_from_data` | `solve_graph_coloring.py` / `solve_max_clique.py` | 2 份 |
| 16/17 | `test_domain_package_exports` / `test_redteam_cli_*` | `test_task310` / `test_task39` / `test_task38` | 2 份 |

- **建议**：将上述共享逻辑上移到 `tools/` 或 `orpath/` 的公共工具模块，测试文件统一引用；可显著降低维护面。

---

## 3. 未用 / 死导入（142 处，65 文件）⚠️【疑似】

> 已剔除 `from __future__ import annotations`（PEP 563 声明，必然"全仓未用"）与 `_`（翻译占位符）等**误报**；`__init__.py` 再导出与 shim 文件单独列于 §5。下表按目录汇总（完整清单见附录 A）。

**高信号（生产代码，非测试）**：
- `orpath/nodes.py`：从 `pipeline.common` 导入的 `_count_fatal / _ensure_dirs / _infer_class / _intake_front_door_active / _intake_whitelist_path / _paper_whitelist_path / _rel_under / TUNE_STRATEGIES / ORPathState / Any / json` 均未在文件内使用（⚠️**【疑似】**：部分可能是刻意再导出兼容旧 API，需核对调用方）。
- `orpath/agents/cartridges.py`：`Callable / CLASS_ALIASES / CANONICAL_CLASSES` 未用。
- `orpath/agents/composite_lead.py`：`NotRequired / TypedDict` 未用。
- `orpath/agents/supervisor.py`：`re / RemainingStepsManager / ACADEMIC_WORKER_NAMES` 未用。
- `orpath/pipeline/solve.py`：`Any / _ensure_dirs / _infer_class / _intake_whitelist_path / _paper_whitelist_path / _solution_is_blocked / timezone` 未用。
- `orpath/pipeline/paper.py`：`_count_fatal / _ensure_dirs / _infer_class / render_or_paper / timezone` 未用。
- `orpath/gates.py`：`json` 未用。
- `tools/solve_microgrid.py`：`copy / os / shutil / Border / PatternFill / Side` 等 openpyxl 相关未用。
- `tools/solve_ortools.py`：`ROOT / fixture_file` 未用。
- `tools/validate_solution.py`：`hashlib` 未用。

**测试文件（多为 `pytest` 或夹具符号未用，风险低但属垃圾）**：`tools/test_converter.py`、`tools/test_lean_cartridges_and_graph.py`、`tools/test_microgrid_optimization.py`、`tools/test_phase3_full_regression.py`、`tools/test_supervisor.py`、`eval_or_bench/*` 等（完整见附录 A／表）。

---

## 4. 调试残留 / 注释垃圾 / 死代码 ⚠️【疑似】

- **`breakpoint()` / `pdb` / `sys.settrace`**：✅ **未发现**（0 处）——干净的积极信号。
- **`TODO/FIXME/HACK/XXX/BUG` 注释**：仅 1 处（`orpath/run_orpath.py:201` `# BUG-1 fix: …`），无系统性垃圾。
- **注释掉的代码**：扫描到的 `# if/for/while/def/return/print(...)` 开头多为**自然语言注释**（如 `tub_optimization.py:1087 # return a bound.`），**疑似**真注释掉的代码仅零星出现，未形成规模。
- **大量 `print()`**：157 个非测试 `.py` 含 `print(`；其中 `scripts/bootstrap_orpath.py`(24)、`knowledge/skills/or-modeling/scripts/paper_search.py`(29)、`eval_or_bench/verify_m1_challenger2.py`(19)、`scripts/build_or_paper_list.py`(21) 打印较多。⚠️**【疑似】**：CLI/门控脚本的 `print` 多为正常输出，仅当出现 `>>>`、时间戳 dump、临时变量时才算调试残留——本次未见明显调试式打印。
- **孤儿函数 / 模块**（定义后全仓无引用，⚠️**【疑似】**：可能经 `getattr`/字符串名动态调用）：`orpath/graph_t2.py:9 build_graph_t2`、`tools/microgrid_reporting.py format_table*_markdown`、`tools/r1_online_check.py check_arxiv/check_doi`、`orpath/pipeline/research.py node_orchestrate` 等（动态 dispatch 导致误报，见 §7 复核）。

---

## 5. 遗留 shim / 孤儿模块 ⚠️【疑似】（多为 ADR 有意保留，需决定去留）

以下为薄封装 shim，功能已上移到新模块（见各自 docstring 所述 ADR）。它们**未被真实 import**（仅 docstring 提及），属技术债：

| 文件 | 行数 | 指向 | 状态 |
|---|---|---|---|
| `orpath/graph.py` | 248 B | ADR-0003 `ControlPlane.build_graph` | ⚠️【疑似】无人 import |
| `orpath/graph_t2.py` | 251 B | 同上 | ⚠️【疑似】无人 import |
| `orpath/nodes_product.py` | 19 L | ADR-0001 → `orpath.nodes` | shim |
| `orpath/post_solve_paper.py` | 11 L | ADR-0004 → `paper_protocol` | shim |
| `orpath/run_t1.py` | 52 L | 仍被 `scripts/t1_gate.py`、`tools/intake_s4_checks.py` 子进程调用 | 在用但旧 |
| `orpath/run_t2.py` | — | 仍被 phase3/4 多个 gate 子进程调用 | 在用但旧 |

- **说明**：`graph.py` / `graph_t2.py` 全仓**无真实 `import`**（仅 `control_plane.py:16` docstring 中列为 "Legacy shims"），是最可能直接删除的死 shim。
- **建议**：统一「shim 退役日」，过期即删；或集中到 `orpath/legacy/` 并加 `DeprecationWarning`。

---

## 6. 命名杂乱 ⚠️

- **门控脚本命名两套并存**：`scripts/*_gate.py`（56 个）vs `tools/gate_*.py`（3 个）vs `tools/*_gate.py`（2 个）——**前缀 / 后缀风格不统一**，全仓 `*_gate.py` 类脚本达 **58 个**。
- **任务测试编号乱序**：`tools/test_task{21…25,31…39,41…44,51…54,61,310}.py`——`test_task310` 数值突兀（应为 `0_610`? 或 `610` 笔误？），且缺号、跳号（40/45/55 等），缺字典序一致性。⚠️**【疑似】`test_task310` 命名异常**。
- **顶层包内测试文件**：`orpath/test_process_memory.py` 位于产品包内（其余测试集中在 `tools/`），目录约定不一致。⚠️**【疑似】**
- **中文 / 空格文件名**：跟踪文件**未发现**中文或含空格文件名（`git ls-files` 校验通过）；非 ASCII 仅出现在 `inbox/` 本地投递内容（已被忽略）。
- **双入口脚本**：`orpath.sh` / `orpath.bat` / `start` 类并存，`ORPATH.md` 与 `README.md` 双文档（内容有重叠风险），`requirements.txt` 与 `requirements-ocr.txt` 分离。

---

## 7. 文件夹混乱（本地运行产物，多数已被 .gitignore 正确忽略）

> 这些目录**未入库**（`git ls-files` 计数为 0），严格说不算「仓库污染」，但造成**工作区体积膨胀与浏览混乱**，且部分隐藏子目录易被误提交。

| 目录 | 文件数 | 体积 | 说明 |
|---|---|---|---|
| `runs/` | **7,347** | 53 MB | 含 `orpath.sqlite`(21MB) + 53 个 `t1-shortest-path-<hash>` 等临时跑批目录 |
| `dist/` | 5 | **140 MB** | 3 个发布 zip（0.3.6/1.0.0 ×2）+ install.ps1 |
| `knowledge/` | 1,351 | 197 MB | 含 `mineru_out/`(865, 14MB 本地)、bm25/fts/chunks 索引 |
| `outputs/` | 583 | 19 MB | 含隐藏子目录 `.agents/.artifacts/.drafts/.lab/.plans`（342 文件） |
| `memory/lessons/` | 484 | 2 MB | 进程记忆草稿（已忽略） |
| `docs/archive/` | — | — | 11 个子目录本地归档（已忽略） |

- **遗留 `.bak`（6 个）**：`outputs/.agents/{s5-skip-intake,s5-graph-intake-txt}/quarantine/*.pre-harness.bak` —— 隔离区的 `.pre-harness` 备份，属临时中间态。
- **隐藏目录散落**：`outputs/.{agents,artifacts,drafts,lab,plans}`、`tools/.pytest_cache`、根级 `.pytest_cache`、各 `__pycache__`（10 处，238 个 `.pyc`）。
- **建议**：`runs/`、`memory/`、`outputs/`、`dist/`、`docs/archive/` 明确「本地-only」，制定定期清理或移出工作区策略；`.bak` 见即删。

---

## 8. 大文件 / 超长文件（维护性，非错误）⚠️【疑似】

跟踪文件中最长的几个 `.py`：
`orpath/watch_snapshot.py`(2500 L)、`tools/validators/extended_solvers.py`(2409 L)、`tools/tube_optimization.py`(1849 L)、`scripts/orpath_watch.py`(1849 L)、`tools/solve_tube_cut_b2026.py`(1379 L)、`tools/solve_microgrid.py`(1301 L)、`orpath/agents/composite_lead.py`(1282 L)、`orpath/agents/domain_analytics.py`(1272 L)、`orpath/studio_analyzer.py`(1237 L)。
- ⚠️**【疑似】**：这些巨文件内聚度低、复制/改动风险高，建议择机拆分（尤其 `watch_snapshot`、`extended_solvers`、`tube_optimization`）。

---

## 9. 复核方法与误报说明（重要）

1. **动态 dispatch 会让「孤儿符号」误报**：`orpath/control_plane.py` 用 `__import__(module_name)` + `getattr` 按字符串加载 10 个域 supervisor，`graph_product.py` 用节点名表注册——因此 §4 的孤儿清单**未经人工按节点名/字符串名二次核对**，一律标 ⚠️**【疑似】**。
2. **`__init__.py` / shim 的「未用导入」多为刻意再导出**：`orpath/agents/__init__.py`、`orpath/pipeline/__init__.py`、`orpath/agents/domains/__init__.py`、`nodes_product.py`、`post_solve_paper.py` 的导入用于对外 `from X import Y`，故 §3 已将它们剔除，不计入死导入。
3. **`nodes.py` 的未用导入**：其 docstring 明确写有 "Gate markers (re-exported & referenced)"，`fixture_search_roots`/`apply_steer_to_state` 已带 `# noqa: F401`；其余 `_count_fatal` 等**疑似**同为再导出用途，删除前必须 grep 全仓调用方。
4. 扫描为**只读**：所有脚本仅 `read` / `grep` / `ast`，未对任何项目文件做写操作；分析脚本置于 `/tmp`。

---

## 附录 A：真实未用导入完整清单（142 处 / 65 文件）

> 已剔除 `__future__.annotations` 与 `_` 占位符；`__init__.py` 与 shim 已剔除。格式：`文件 → 未用符号`。

```
orpath/agents/cartridges.py           Callable, CLASS_ALIASES, CANONICAL_CLASSES
orpath/agents/composite_lead.py       NotRequired, TypedDict
orpath/agents/optimality_claim_auditor.py  field
orpath/agents/supervisor.py           re, RemainingStepsManager, ACADEMIC_WORKER_NAMES
orpath/gates.py                       json
orpath/nodes.py                       Any, _count_fatal, _ensure_dirs, _infer_class,
                                       _intake_front_door_active, _intake_whitelist_path,
                                       _paper_whitelist_path, _rel_under, TUNE_STRATEGIES,
                                       ORPathState, json
orpath/pipeline/common.py             Any, os, sys
orpath/pipeline/paper.py              _count_fatal, _ensure_dirs, _infer_class,
                                       render_or_paper, timezone
orpath/pipeline/research.py           re, _rel_under
orpath/pipeline/solve.py              Any, _ensure_dirs, _infer_class,
                                       _intake_whitelist_path, _paper_whitelist_path,
                                       _solution_is_blocked, timezone
orpath/test_process_memory.py         write_retrieve_artifacts

eval_or_bench/build_raw_tsp.py        sys
eval_or_bench/test_converter.py       pytest, FORBIDDEN_SCHEMA_KEYS
eval_or_bench/test_converter_stress.py parse_tsp_file
eval_or_bench/verify_all_matrices.py  json, math
eval_or_bench/verify_held_karp.py     math
eval_or_bench/verify_m1_challenger2.py json, convert_tsp_to_fixture, KNOWN_OPTIMAL_REFS,
                                       _validate_tsp, fixture_dir
eval_or_bench/verify_m1_solvers.py    json

knowledge_svc/bm25_index.py           Sequence
knowledge_svc/lightrag_adapter.py    lightrag
knowledge_svc/notes_helper.py         Any
knowledge_svc/rrf_fuse.py             Iterable

scripts/b_tube_final.py               Alignment, Border, Side, defaultdict
scripts/b_tube_xlsx.py                Border, Side, PatternFill, copy, defaultdict
scripts/download_or_fulltexts.py      random
scripts/export_b_polyomino.py         sys
scripts/export_demo_seed.py           sys
scripts/extract_zip_longpath.py       sys
scripts/install_demo_seed.py          sys
scripts/orpath_watch.py               _PROVIDER_DEFAULTS, _resolve_provider, shutil
scripts/orpath_watch_run.py           socket
scripts/pack_release.py               sys
scripts/paper_1_0_gate.py             record_versions
scripts/phase3_hybrid_pi_gate.py      tempfile
scripts/phase4_product_research_gate.py re
scripts/problem_workbench_gate.py     os
scripts/run_flagship_jssp_live.py     os

tools/solve_microgrid.py              copy, os, shutil, Border, PatternFill, Side
tools/solve_network_flow.py           sys
tools/solve_ortools.py                ROOT, fixture_file
tools/solve_qubo_ising.py             sys
tools/validate_solution.py            hashlib
tools/validators/extended_solvers.py  math
tools/validators/tube_cut.py          Any, os, fixture_dir, fixture_file

tools/test_adaptive_graph.py          AdaptivePipelineState
tools/test_cartridges_phase2.py       Any, pytest
tools/test_intake_gate.py             pytest
tools/test_lean_cartridges_and_graph.py Any, pytest, cartridge_tier, resolve_cartridge
tools/test_microgrid_optimization.py  CLASS_ALIASES, INITIAL_SOC_KWH, solve_q1, guess_main
tools/test_phase3_full_regression.py  AIMessage, HumanMessage, get_state_stage_progress,
                                       create_domain_guard_hook
tools/test_studio_rate_limit.py       Path
tools/test_supervisor.py              ACADEMIC_WORKER_NAMES
tools/test_task25_lot_sizing_benchmark.py BENCHMARK_DEMANDS
tools/test_task41_meta_router.py      MATCHED_BY_KEYWORD
tools/test_task44_lineage_relay.py    CONSERVATION_TOL
tools/test_task53_optimality_claim_auditor.py ClaimAuditResult, OptimalityClaim
tools/test_task54_master_gate.py      pytest
tools/test_task61_watch_snapshot.py   re
tools/test_tube_agents.py             DEFAULT_TUBE_LEAD_PROMPT, RemoveMessage
```

---

## 附录 B：重复数据集 / 克隆一览（MD5 & AST 已验证）

- **数据**：`eval_or_bench/instances/**` ≅ `fixtures/benchmarks/{att48,bayg29,burma14,eil51,gr17,kroA100,swiss42,ulysses16}/**`（21 JSON，字节级一致）。
- **克隆**：`scripts/*_redteam_gate.py` ×10 内 `_dig/build_attacks/run_redteam/main` 完全相同（§1.2）。
- **函数级拷贝**：见 §2 表格（`_type_ok`、`_validate_meta`、`_resolve_root`、`load_dimacs`、`_load_matrix`、`_collect_solution_tokens` 等）。

---

## 修复优先级建议（供决策，非本次执行）

| 优先级 | 动作 | 对应条目 | 预估收益 |
|---|---|---|---|
| P0 | 合并/删除 10 份 redteam 域克隆（收敛到 universal 或抽骨架） | §1.2 | 消除 ~4,000 行重复，直击 AGENTS.md 禁令 |
| P0 | 去重 `eval_or_bench/instances`（保留单一权威源） | §1.1 | 消除 21 份重复数据 + 三处落盘 |
| P1 | 删除无人 import 的 `graph.py` / `graph_t2.py`；给其余 shim 设退役日 | §5 | 清理死 shim |
| P1 | 清理 142 处未用导入（先核对再导出用途） | §3 / 附录 A | 降低 ruff/lint 噪音与认知负担 |
| P2 | 拆分 9 个超长 `.py`（watch_snapshot / extended_solvers / tube_optimization…） | §8 | 可维护性 |
| P2 | 统一 `*_gate.py` 命名；修正 `test_task310`；`orpath/test_*` 归位 | §6 | 目录/命名一致性 |
| P3 | 制定 `runs/ memory/ outputs/ dist/ docs/archive/` 本地产物清理策略；清理 `.bak` / 隐藏目录 / `__pycache__` | §7 | 工作区整洁 |

> **声明**：本清单为**只读审计产物**，未改动任何既有文件；所有 ⚠️**【疑似】** 项均需按 §9 方法人工复核后方可处置。
