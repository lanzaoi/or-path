# OR-Path 后端精扫报告与优化方案（2026-11-07）

> 范围：`orpath/`、`tools/`、`scripts/`（后端）、`knowledge_svc/` 全部 Python 代码。
> 方法：AST 枚举 207 个后端文件 / 1888 个函数，逐文件通读（核心链路 100% 精读，旧 swarm 遗产层抽样 + grep 模式扫描），
> 重点核对：异常吞噬路径、资源句柄生命周期、subprocess 超时、路径拼接、Numbers Truth 标签、状态机边界。
> 级别：P0 必须修 / P1 高 / P2 中 / P3 低。✅=已实证，【疑似】=推断待复核。
> 关联：`docs/_deprecated/tasks/bug_hunt_full_scan_2026-11-07.md`（全仓粗扫）、`docs/_deprecated/tasks/bugs_found.md`（既有精读清单）。

---

## 0. 覆盖统计

| 层 | 文件 | 函数 | 精读度 |
|---|---|---|---|
| HTTP 服务面 `scripts/orpath_watch.py`、`orpath/studio_analyzer.py`、`orpath/watch_snapshot.py` | 3 | 110 | 100% 精读 |
| 产品控制面 `graph_product/control_plane/nodes/pipeline/*` | 9 | 84 | 100% 精读 |
| Deterministic 门 `deterministic_nodes/callbacks/guard_factory/optimality_claim_auditor/dimo_mutator/domain_registry/domain_analytics` | 7 | 124 | 精读+抽样 |
| Agent 层 `supervisor/meta_router/composite_lead/budget_engine/lineage_relay/domain_state/cartridges/adaptive_graph/workers/contract_validator/tools_or/custom_mip/domains/*` | 16 | ~250 | 接口精读+模式扫描（遗产 swarm 层） |
| 求解调度 `solve_dispatch/validate_solution/solve_envelope/fixture_paths/gate_*/r1*/r2*/schema_models/intake_*` | 14 | ~90 | 100% 精读 |
| 知识服务 `knowledge_svc/*` | 13 | ~120 | 100% 精读 |
| 辅助 `state/paths/human_steer/node_context/intake_nodes/intake_discover/artifact_versions/claim_ledger/paper_workflow/process_memory/run_orpath/mcp_server/gates/tool_catalog/research_run/revise_proof/lab_continuity/web/build` | 17 | ~200 | 100% 精读 |
| 启动/安装 `START.* orpath.* install.ps1 bootstrap doctor install_demo_seed export_demo_seed orpath_watch_run` | 9 | ~50 | 100% 精读 |

---

## 1. 崩溃路径（精扫新发现）

### N1【P0】`orpath/run_orpath.py::cmd_run`（约 L288-330）：invoke 异常被吞 → NameError(final) + sqlite 连接泄漏
```python
try:
    ...
    final = app.invoke(initial, cfg)   # 抛异常 → 被下面的 except 吞掉
    ...
except Exception:  # noqa: BLE001
    pass

summary = {..., "stage": final.get("stage"), ...}   # ← NameError: final 未定义
...
conn.close()    # ← 永远到不了，连接泄漏
```
- **现象**：任何节点抛未捕获异常（如 node_gate_validate 读坏 JSON、求解器崩溃）时，程序先 NameError 崩溃（误导排障），且 `conn` 不关闭。
- **修复**：`except Exception as e: final = {..., "last_error": ...}; sys.stderr.write(traceback)`；`conn` 用 `try/finally` 包裹。

### N2【P1】`orpath/pipeline/paper.py::node_revise_or_done`（约 L470）：solution.json 直读无保护
```python
sol = json.loads(Path(state["solution_path"]).read_text(encoding="utf-8"))
```
- 修复轮中 solution.json 被截断/损坏 → JSONDecodeError/OSError 直接炸穿图（上游 `_solution_is_blocked` 有 try，这里没有）。
- **修复**：try/except → 降级 human_stop + last_error。

### N3【P1】`orpath/pipeline/paper.py::node_gate_validate` 边界：`solution_path` 为空时 `Path("")` 变成 `"."`
- `sol_path = Path(state.get("solution_path") or "")` → `Path("")` 即 `"."`（目录），`.is_file()` False → 跳过 BLOCKED 分支 → `gate_validate(root, pid, Path("."), vpath)` → `validate_solution._load(".")` 抛 `IsADirectoryError`（未捕获）→ 验证器子进程崩溃 → 报错信息混乱。
- **修复**：`if not sol_path or not str(sol_path).strip() or sol_path == Path("."): human_stop`。

### N4【P1】`orpath/pipeline/solve.py::node_solve` mock 回退仍无"夹具答案绑定"标记（B14 未闭环）
- 工作树已加 BLOCKED 拦截，但 `solve(root, pid, "mock", pc)` 回退分支仍会把 fixtures 黄金答案静默写入 solution.json，无 `fixture_answer_bound` 标记，gate_validate 无法拒绝。
- **修复**：回退时强制 `meta.fixture_answer_bound=True` + `gate_validate` 拒绝通过。

### N5【P2】`tools/solve_dispatch.py::_try_in_proc`：进程内适配器崩溃被静默吞掉
```python
except Exception:
    return False, -1, "", ""
```
- 进程内调用抛异常时丢弃栈信息，回退 subprocess 重跑；若同样崩溃，最终只剩 stderr 尾部，原始异常丢失。
- **修复**：返回 `last_exc` 并在 subprocess 也失败时合并输出。

### N6【P2】`tools/solve_dispatch.py::_find_case_dir`：语义目录扫描用子串匹配，可能错配
- `pid.lower() in name_l or name_l in pid.lower()`：problem_id=`c`/`b` 或短 id 时命中任意含该子串的 case 目录（如 `cumcm2026_c` 与 `case-c` 混淆）。
- **修复**：短 id（<4 字符）禁用子串回退，仅精确匹配。

### N7【P2】`orpath/pipeline/solve.py::_resolve_registry_schema`：`except Exception: return None` 吞掉建模失败细节
- registry 建模任何异常（fixture 损坏、JSON 错误）都退化为 None → 走 isolated pipeline 或 human_stop，`last_error` 无根因。
- **修复**：返回 `(schema|None, err)` 或写 `outputs/<slug>-model-err.json`。

### N8【P3】`orpath/pipeline/paper.py::node_cite_pack`：`solution_path` 可能为空字符串
- `sol = Path(state["solution_path"])` → `Path("")`="." → claim_map 子进程读目录崩溃 → claim 门永久失败且原因不透明。

---

## 2. 资源泄露与性能

### N9【P1】`orpath/agents/callbacks.py`：每个 tool 结束写一份 stage 快照 → runs/stages 文件爆炸
- `on_tool_end`/`on_chain_end`/`on_chain_error` 每次都 `write_stage_snapshot`：多智能体一轮可能数百次工具调用 → `runs/<thread>/stages/*.json` 线性膨胀（每个 ~200B），并每次独立 open/close 文件。
- **修复**：节流（每 ≥2s 或每 N 事件写一次）+ 目录上限清理（>200 文件滚动）。

### N10【P1】`orpath/watch_snapshot.py::build_snapshot`：SSE 每 0.5s 全量快照重解析
- `parse_lead_events`/`parse_transcript_events` 每次 tick 重读整个 lead log（上限 1.5MB）与 transcript；`compute_source_fingerprint` 每次 glob 全目录。长跑时 CPU 与 payload 尺寸线性恶化。
- **修复**：fingerprint 增量 + 日志游标（已有 `log_cursors` 但未用于跳过已解析前缀）；snapshot 惰性懒加载 events。

### N11【P1】`scripts/orpath_watch.py`（R1/R3/R4 确认 + 细化）
- `_handle_studio_analyze`：`conn.close()` 只在成功路径（异常泄漏，见粗扫 R1）；
- `_handle_intake_run` bg worker `timeout=300` 强杀大算例；`capture_output` 全程持内存；
- SSE 半开连接无服务端超时；
- **修复**：try/finally 关闭 + 可配 `ORPATH_RUN_TIMEOUT`（默认 1800）+ SSE write 超时套 `select`。

### N12【P1】`tools/solve_dispatch.py::solve` tube 分支：以安装根为 cwd 运行 → 污染安装包且并发互相覆盖
- `_run_py(script, args, _ROOT)`：solver 写 `install/outputs/b-tube-cut/`；多 case 并发时后写覆盖前写；envelope 读取 `[root, install]` 双候选目录 → 读到别的 case 的输出。
- **修复**：tube solver 输出目录参数化（`--out`），cwd 用 case root。

### N13【P2】`orpath/mcp_server.py::orpath_validate_check`：subprocess 无超时 → MCP 请求可永久挂起
- `subprocess.run(...)`（无 timeout）。同理 `orpath/gates.py::run_py`、`scripts/bootstrap_orpath.py::_run`（pip 无超时）。
- **修复**：统一 `timeout=ORPATH_SUBPROC_TIMEOUT`（默认 300）。

### N14【P2】`orpath/process_memory.py::save_lesson` 默认 `local=True`：自动 lesson 全落 `memory/lessons/`（gitignored）
- 当前 484 个本地草稿无合并/清理策略；`knowledge/lessons` 只承载种子。
- **修复**：定期 `consolidate`（去重 + 摘要合并）+ `doctor` 报告数量。

### N15【P3】`orpath/web/build.py`：每次请求 `/` 都触发 `build()`（mtime 竞争 + 服务中写文件）
- `do_GET` 里 `try: build() except: pass`：并发首请求可能互相写坏 watch.html。
- **修复**：构建锁 + 构建产物 mtime 校验。

---

## 3. 安全（精扫补充）

### N16【P1】`orpath/agents/workers.py::read_problem_file / export_paper_markdown`：绝对路径直通 → 智能体文件系统逃逸面
- 两个 tool 均 `Path(file_path).expanduser()`，绝对路径直接使用：LLM 生成的路径可读 `~/.ssh/...`、写任意位置（与 `execute_python_sandbox` 同属一类逃逸面，且更隐蔽）。
- **修复**：限定 workdir 根 + 白名单后缀；绝对路径拒绝或仅允许 workdir 内。

### N17【P1】`scripts/orpath_watch.py`（S1/S2/S3/S5/S10 确认）
- GET `/api/artifact?slug=` 不经 `_sanitize_slug` 直接拼路径（粗扫 S2）；
- 静态文件 `startswith(src_root)` 无分隔符哨兵（S3）；
- 请求体 api_key 写 `os.environ` 永不清理（S5）；
- POST body 无大小上限（S10）。
- **修复**：GET slug 统一过 `_sanitize_slug`；`startswith(str(src_root) + os.sep)`；env 写入改局部传递；`Content-Length` 上限 32MB。

### N18【P2】`tools/intake_ocr.py`：`_DEFAULT_PADDLE_PY` 硬编码 `C:\Users\Lanzao\...Python311\python.exe`
- 换机即失效（静默 fallback rapidocr，OCR 质量下降无提示）。
- **修复**：移入 `.env.example` 可选配置，代码只认 env。

### N19【P2】`orpath/studio_analyzer.py::run_deep_analysis`：手工解析 .env 文本取密钥
- 不处理引号/注释/多行值；与 dotenv 行为不一致。
- **修复**：复用 `load_dotenv` 或规范化解析。

---

## 4. Numbers Truth 标签（精扫状态核实）

| 项 | 工作树状态 | 残留问题 |
|---|---|---|
| B5 `deterministic_nodes._extract_verdict` | ✅已改：优先读 `meta.proven_optimal`，增加 `method_class∈{heuristic,...}` 拦截 | ⚠️最终兜底仍是 `status==OPTIMAL`：对 qubo_ising 等**硬编码 OPTIMAL 的启发式 solver** 仍误判 proven → P0 残留 |
| B6 `adaptive_graph.py:288` | ❌未修 | `sol.get('proven_optimal', sol.get('status','').upper()=='OPTIMAL')` 同款兜底 → P0 |
| B8 `optimality_claim_auditor` | ✅已修（`_HEURISTIC_KEYWORDS` 含 mpc/rolling_horizon/rolling） | ⚠️仍为子串匹配：method=`MILP_wrapper_with_SA` 类命名不在黑名单 → 可能放行 → P1 残留 |
| B7 `validate_solution._validate_vrp` | ✅已加 depot_endpoints 检查 | ⚠️TW 只查 `start_service≤due`，不查 `start_service+service≤due`；depot 自身 TW 不查 → P2 |
| B14 mock 回退 | ❌未闭环 | 见 N4 → P1 |
| B9/B11/B13/B17/B23 | ✅工作树已改（pyvrp/portfolio/binpack） | 需回归验证（见 §6） |
| **N20【P1】`orpath/state.py::orpath_state_to_core`** | 新发现 | `proven_optimal: bool(state.get("gate_claim_ok", False))`：claim 门通过 ≠ 数学最优证明 → 下游 adaptive/legacy 层语义误读 |
| **N21【P2】`tools/r1_claim_map.py::build_claim_map`** | 新发现 | `allowed.add(str(i)) for i in range(21)`：论文中 0–20 任意整数恒放行 → claim 门弱化 |

---

## 5. 一致性 / 卫生 / 冗余（精扫补充）

| # | 位置 | 现象 | 级别 |
|---|------|------|------|
| N22 | `control_plane.default_initial` vs `state.make_initial_orpath_state` | `max_revise` 两处真值不一致（2 vs 3） | P2 |
| N23 | `run_orpath.cmd_run` 尾部 | `if not final.get("gate_validate_ok"): return 1`：honest human_stop/BLOCKED 终态也非零退出，CI 误报失败 | P2 |
| N24 | `human_steer.build_steer_cta` | CTA 用 Windows `type` 命令 + `notes\...` 反斜杠路径，Linux/macOS 复制即错 | P2 |
| N25 | `watch_snapshot.discover_pi_sessions` | deep_links 硬编码 `orpath.bat`（Windows 命令），跨平台 CTA 失效 | P2 |
| N26 | `scripts/orpath_watch_run.py` | 与 `orpath_watch.py` 重复实现 WatchHandler 绑定/端口重试/健康等待（同一契约两实现） | P2 |
| N27 | `scripts/export_demo_seed.py` | `shutil.rmtree(dest)` 前无 `dest ≠ workdir` 双保险（当前 dest=out_root/slug 有界，防御性不足） | P2 |
| N28 | `orpath/agents/contract_validator.py::audit_budget_ledger` | 读 `experiments/<domain>/budget-ledger.json`（gitignored）→ 发布 zip 中缺失 → 审计结果为空 | P3 |
| N29 | `orpath/agents/domain_analytics.py::profile_routing_data` | 依赖 `vrplib`（requirements.txt 未列）→ import 失败仅返回 error（优雅但静默） | P3 |
| N30 | `orpath/watch_snapshot.py::_match_children_for_dispatch` | `if score < 5 and out: if len(out) >= 1: break` 冗余条件，弱匹配语义与注释不符 | P3 |
| N31 | `orpath/watch_snapshot.py::read_log_text` | `from_offset` 与 `size<=max_full` 同时命中时未 seek，增量契约不一致 | P3 |
| N32 | `callbacks.write_stage_snapshot` | 文件名 `{stage:04d}`，>9999 阶段后序号位数变化破坏 glob 排序稳定性 | P3 |
| N33 | 三处领域关键词表 | `studio_analyzer` if/elif 链 vs `_guess_domain_info` vs `deterministic_nodes.DOMAIN_KEYWORDS`：同一领域知识三份实现，顺序/词表漂移（粗扫 N5 实证） | P2 |
| N34 | `graph_product.open_sqlite_checkpointer` | `saver.setup()` 异常被吞（R5） | P2 |

---

## 6. 工作树已修改项的回归验证清单

`git status` 9 个 M 文件已改未提交，需回归：
1. `tools/solve_lot_sizing.py`（B1 WW DP off-by-one）：跑 300 组随机实例 vs 暴力枚举（复用 bugs_found 实证脚本）。
2. `tools/solve_binpack.py`（B13）：unfitted 非空时 status 语义 + validator 联调。
3. `tools/solve_portfolio.py`（B11/B23）：SLSQP 路径 status=FEASIBLE、proven_optimal=False；efficient_return 口径。
4. `tools/solve_pyvrp.py`（B9/B17）：random_seed 透传；TW 检查改 `start_service+service≤due`。
5. `tools/validate_solution.py`（B7）：depot/重复/TW 三项检查的负例测试（构造非法 route 必须被拒）。
6. `tools/test_gates.py`（唯一失败用例）：`test_tube_dispatch_returns_after_one_successful_adapter_run` 复跑。
7. `orpath/pipeline/solve.py`（B12/N4）：非 dict solution 不再 AttributeError；mock 回退标记化（N4 未闭环，需补）。
8. `orpath/paper_workflow.py`（+28/-6）：cite/review 链路回归 + `docs/or-paper-sop.md` SOP 一致性检查（`tools/test_sop_doc.py`）。
9. `tools/solve_polyomino.py`（B18 死代码删除）：确认无引用残留。

回归基线：`.venv/bin/pytest tools/ -q -p no:langsmith`（目标 2397/2397 全绿）。

---

## 7. 优化方案（按波次）

### Wave 1 — 崩溃与安全止血（预计 1-2 天）
| 任务 | 对应 |
|---|---|
| cmd_run 异常吞没 + conn finally（N1） | P0 |
| GET slug 清洗 + startswith 哨兵 + body 上限（N17） | P0 |
| 默认绑定回 127.0.0.1（S1/N17） | P0 |
| paper 节点两处直读加保护（N2/N3/N8） | P1 |
| workers 两个 tool 限定 workdir（N16） | P1 |
| mcp/gates/bootstrap subprocess 超时（N13） | P1 |

### Wave 2 — Numbers Truth 闭环（预计 2-3 天）
| 任务 | 对应 |
|---|---|
| `_extract_verdict` / adaptive_graph:288 删除 status 兜底，改为"无 meta 即 False + 告警"（B5 残留/B6/N20） | P0 |
| solver 侧清理硬编码 OPTIMAL（qubo_ising B3 / microgrid B4） | P0 |
| auditor 关键字匹配改 method_class 精确枚举 + 复合 method 拒绝（B8 残留） | P1 |
| mock 回退 `fixture_answer_bound` 标记 + gate 拒绝（N4） | P1 |
| `orpath_state_to_core` 的 proven_optimal 映射改正（N20） | P1 |
| claim_map 0-20 放行收紧为"白名单上下文"（N21） | P2 |

### Wave 3 — 资源与性能（预计 2 天）
| 任务 | 对应 |
|---|---|
| studio_analyze/intake_run sqlite + subprocess finally/超时（N11） | P1 |
| callbacks 快照节流 + 目录上限（N9） | P1 |
| SSE 增量解析（fingerprint 跳过已读前缀）（N10） | P1 |
| tube solver 输出目录参数化（N12） | P1 |
| SSE 半开连接超时（N11） | P2 |

### Wave 4 — 一致性与卫生（预计 2 天）
| 任务 | 对应 |
|---|---|
| max_revise 单一真值（N22）；cmd_run 退出码语义（N23） | P2 |
| CTA 跨平台命令（N24/N25）；领域关键词表合并为一份（N33） | P2 |
| watch_run 复用 orpath_watch handler（N26）；export_demo_seed 双保险（N27） | P2 |
| save_lesson consolidate 策略（N14）；doctor 增 memory 统计 | P2 |
| setup 异常不再吞（N34）；_match_children 弱匹配语义（N30） | P3 |

### Wave 5 — 边界语义加固（预计 2 天）
| 任务 | 对应 |
|---|---|
| VRP TW 服务结束检查 + depot TW（N7/B7 残留） | P2 |
| `_find_case_dir` 短 id 禁子串（N6）；`_try_in_proc` 保留异常（N5） | P2 |
| registry schema 失败落盘根因（N7） | P2 |
| schema_models/gate_schema 与 domain_registry 的 class 清单对齐自动化测试 | P3 |

### 验收门（建议新增）
1. `tools/test_backend_wave1.py`：cmd_run 注入 invoke 异常断言不 NameError 且 conn 关闭；GET artifact slug 遍历攻击被拒。
2. `tools/test_backend_wave2.py`：启发式信封（status=OPTIMAL 但 meta.proven_optimal=false）在任何 verdict 路径不得判 True。
3. `tools/test_backend_wave3.py`：1000 次 tool_end 后 stages 文件数有界；SSE 快照二次 tick 不重复解析同一段日志（mock 计数）。
4. CI：`pytest tools/ -q -p no:langsmith` 全绿 + `scripts/or_swarms_master_gate.py`、`scripts/problem_workbench_gate.py` 保持绿。

---

## 8. 一句话总结

后端主体（产品控制面、deterministic 门、验证链、知识服务）工程质量高：异常吞噬少、信封法严谨、文件句柄基本都用 `with`；
**主要风险集中在三处**：① `run_orpath.cmd_run` 的异常吞没 + 连接泄漏（唯一必然崩溃路径）；② `proven_optimal` 的 status 兜底在 3 处残留（Numbers Truth 铁律）；③ HTTP 面 slug 清洗/绑定/env 三件套（安全）。
按 Wave 1→2→3→4→5 顺序推进，预计 9-10 人日可闭环本清单全部 P0/P1。
