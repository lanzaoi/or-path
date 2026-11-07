# OR-Path 前端与前后端结合处精扫报告

> 扫描日期: 2026-XX-XX · 扫描范围: `orpath/web/src/**`、`orpath/web/build.py`、`orpath/web/watch.html`、`scripts/orpath_watch.py`、`START.sh` / `START.bat`、前后端契约(API ↔ JS)
> 方法: 全量人工通读 JS/HTML/CSS 源文件 + HTTP 层逐端点审计 + 前端 fetch 调用点与后端响应键名逐一对撞 + 与 AGENTS.md / specs 的架构声明比对

---

## TL;DR

前端单体(watch.html 232KB,由 build.py 拼接 src/ 生成,当前与源同步)整体质量可用,但存在 **4 个 P0 级问题**: ① Watch 服务默认面向全网暴露且可拉起子进程/写盘而无鉴权;② `/api/artifact` 存在路径遍历;③ 可视化驾驶舱三处图表用硬编码假数据并宣称"严密闭合/黄金基准";④ Studio 求解摘要无条件宣称"最优目标值"与"100% 合格",直接触碰 AGENTS.md 铁律 1(Numbers Truth)。另有 12 个 P1 缺陷、11 处冗余/死代码、20+ 处硬编码。

| 等级 | 数量 | 性质 |
|------|------|------|
| P0 高危 | 4 | 安全暴露面 / 数字真理违规 |
| P1 缺陷 | 8 | 挂死、状态漂移、逻辑死分支、无服务端校验 |
| P2 冗余 | 11 | 死标记、双源真相、退役架构残留、磁盘包袱 |
| P3 硬编码 | 20+ | 见 §5 明细表 |

---

## 1. 扫描对象清单

| 层 | 文件 | 行数 | 角色 |
|----|------|------|------|
| 构建 | `orpath/web/build.py` | 106 | src/ → watch.html 拼接器,mtime 增量重建 |
| HTML | `src/html/{header,studio,inspector,modals}.html` | 537 | Studio 三段式 + Inspector 监视台 + 弹窗 |
| JS | `src/js/common.js` | 234 | 全局状态/工具/Toast/模式切换 |
| JS | `src/js/studio.js` | 1357 | Studio 工作舱:拖拽导入、研判卡、求解确认、**可视化驾驶舱** |
| JS | `src/js/inspector.js` | 1473 | 监视台:轮询快照、阶段树、人导表单、题面工作台、一键导入 |
| CSS | `src/css/{base,studio,inspector}.css` | 2182 | 三主题样式,无跨文件重复选择器冲突 |
| HTTP | `scripts/orpath_watch.py` | 1849 | 13 个端点:snapshot/poll/steer/intake/studio/model/artifact/stream |
| 启动 | `START.sh` / `START.bat` | — | 统一入口,决定监听地址 |
| 后端支撑 | `orpath/studio_analyzer.py` `watch_snapshot.py` `human_steer.py` | — | LLM 研判、磁盘快照读取、人导文件 |

---

## 2. P0 — 高危问题(必须修)

### P0-1 Watch 服务安全暴露面: 全网监听 + CORS `*` + 零鉴权 + 可拉子进程

- `START.sh:47` 以 **`--host 0.0.0.0`** 启动;`START.bat` WSL 分支(`START.bat:103,105`)同样 `--host 0.0.0.0`(原生 Windows 分支是 127.0.0.1,**平台间行为不一致**)。
- `scripts/orpath_watch.py` 模块 docstring 声称 "**Bind 127.0.0.1 only.**" —— 与实际启动参数直接矛盾,说明 0.0.0.0 是后期改出来的。
- 所有 JSON 响应带 `Access-Control-Allow-Origin: *`(`_send_json`,`:486-489`;download 分支 `:1562-1564`),**无任何鉴权/Token**。
- 组合后果(局域网内任何人/恶意网页均可):
  - `POST /api/intake/run` → 以服务进程权限 **拉起 `run_orpath.py` 子进程** 执行任意任务(`:1180-1215`);
  - `POST /api/intake/import` (folder 模式) → 向 workdir/inbox 写任意文件(rel_path 有遍历防护,但**无总量/类型服务端限制**,前端 25MB 上限纯客户端);
  - `POST /api/steer` → 写 `notes/<slug>-human-steer.json`(slug 已由 `steer_path` 用 `[^\w.\-]+→_` 消毒,安全);
  - `GET /api/artifact` → 读 workdir 内文件(见 P0-2 的遍历缺口);
  - `GET /api/health` → 泄露 home/workdir 绝对路径。
- **修复建议**: 默认强制 127.0.0.1;确需 LAN 共享时加共享 Token(启动时输入/env 注入 + `Authorization` 头校验);CORS 改为 None 或白名单;`/api/intake/run` 增加来源校验。

### P0-2 `/api/artifact` 路径遍历(slug 未消毒)

- `_qs_slug_thread`(`:569-572`)对 slug/thread **不做任何消毒**,直接小写/strip 就用。
- `_handle_artifact_get`(`:770-790`)/`_handle_artifact_download`(`:792-…`)用 `f"{slug}-problem-brief.md"` 等拼接路径:`slug="../secret"` → `notes/../secret-problem-brief.md` 越出 workdir 读取。
- 后缀约束降低了危害(只能读到以固定后缀结尾的文件),但 `solution`/`validate`/`intake`/`paper` 等后缀在 workdir 外同样常见,仍属真实信息泄露面;且同一 slug 还会流入 `build_snapshot` 的路径拼接。
- 对照:`_sanitize_slug`(`:253-256`)已存在且被 intake/run 使用,**仅 artifact 两处漏用**。
- **修复建议**: `_qs_slug_thread` 内部直接调用 `_sanitize_slug`(与 POST 侧对齐)。

### P0-3 可视化驾驶舱三处硬编码假数据,且宣称最优/基准 (Numbers Truth 违规)

`studio.js` 的三张图函数全部内置 fallback 假数据,**如实数据分支与假数据分支的 UI 文案无法区分真伪**:

1. **收敛 Gap 曲线** `renderConvergenceGapCurve`(`studio.js:1242-1340`):
   - 形参 `gapHistory` **完全未使用**,永远画死 `iters` 数组(47.6% → 0.0% 九点),并硬编码文案:
     - `★ Gap: 0.00% 严密闭合`(:1312)、`初始Gap: 47.6% ➔ 最终Gap: 0.00% (已达理论最优下界)`(:1330)。
   - **无论后端返回 BLOCKED / 非最优 / 未求解,该图恒定宣称达到理论最优下界** —— 这是对 AGENTS.md 铁律 1 的正面违反,且对应 `or_reviewer` 红队必杀项(伪造最优性声明)。
2. **甘特图** `renderGanttChart`(`:968-1090`):无真实 schedule 时展示 16 条手写工序,徽标 `Taillard ft06 黄金基准`,角标 `冲突校验: 0 违背`(:1078)—— 该冲突数**没有任何计算来源**,是写死的断言。
3. **路线图** `renderRouteMap`(`:1104-1228`):无真实 routes 时展示 `Solomon C101 基准拓扑` 假坐标,角标 `车辆超载: 0% · 满足全量窗约束`(:1210)—— 同样无任何计算来源。
4. **实数据分支也造假布局**:即使 `solution.routes` 存在,`:1120-1140` 仍用 `samplePts` 径向假坐标绘制客户点,徽标却显示 `✓ 真实路径规划数据` —— 图对不上"真实"二字;`totalDist = (solution.total_distance || solution.objective || 159) + " km"`(:1114)对非距离目标(如时间、成本)强贴 "km" 单位。
- **修复建议**: 三图改为"真实数据 → 绘制;无数据 → 显示空白面板 + 中性徽标(如 `尚未求解 · 无数据可绘`)"。收敛曲线从 `solve_doc.metrics.gap_history` 或 `provenance` 读取;甘特/路线角标中的"0 违背/0%"必须来自 `validate.json` 的 `checks[].ok` 聚合值。

### P0-4 Studio 求解摘要无条件宣称最优性

- `scripts/orpath_watch.py:1657-1663` `_handle_studio_confirm` 组装 `plain_language_summary`:
  - `"objective_str": f"最优目标值: {obj} 单位"` —— 即使 `sol_doc.meta.proven_optimal == False`(启发式解、未证最优)也照写"最优";
  - `"validation_status": f"数理校验通过 ({checks_count} 项物理约束 100% 合格)"` —— 当 `checks_count == 0` 且 `val_ok` 为真(或校验报告为空默认)时仍宣称 100% 合格。
  - `"headline": "优化路线求解完成"` 将 TSP 语境文案套给一切领域。
- `validate.json` 就在手边(`val_doc` 已解析)却**不检查 `proven_optimal`/`exact` 字段**,前端 `renderStudioResultCard`(`studio.js:930-940`)也照单全收展示。
- **修复建议**: 摘要按 provenance 分支:`proven_optimal=True → "严格最优"`;否则 `"可行解 (未证最优)"`;`checks_count==0` 时不得出现"100% 合格"。前端同步透出 `proven_optimal` 徽标。

---

## 3. P1 — 缺陷隐患(应修)

### P1-1 `/api/studio/confirm` 无挂死防线
`studio_analyzer` 侧:multiagent 尝试有 `ma_timeout`(默认 **3 秒**,客户端可传 60 秒),但 multiagent 失败后回退的 `build_graph(...).invoke(initial, cfg)`(`:1478-1486`)**没有任何超时**;前端 `btnConfirm` fetch(`studio.js:909-914`)**没有 AbortController/超时**。流水线卡死 → 页面无限转圈,用户无法中断重试。离线模式下 3s 预算秒杀 multiagent 后同样进入无界 graph 等待。**建议**:graph 回退包一层可中断工作者线程(与 multiagent 同构),前端加 120s 超时 + 重试按钮。

### P1-2 `/api/intake/run` 子进程治理薄弱
`_bg_worker` 用 `subprocess.run(..., timeout=300)`(`:1190-1197`):超时杀进程后**残留半成品 stage 文件**,UI 展示一半的阶段树;且 `_handle_intake_run` 启动前已手工清空 `runs/<thread>/stages`(`:1218-1224`)—— 与用户手动跑终端任务并发时会**误删进行中任务的 stage**(无锁、无 slug 占用检查)。另外 `--intake-in` 取 `sorted(inbox_slug.iterdir())` 第一个文件(`:1211-1215`),命名略序而非按题面关键字挑选,可能把数据 CSV 当题面传入。

### P1-3 客户端限制无服务端对应
`studio.js` 的 `MAX_STUDIO_FILES=200 / 25MB / 10MB / 深度12`(`:392-395`)仅前端生效;folder 导入直连 API 时 `_handle_intake_import` 无同名校验,任意大 body 可写盘。inspector 上传 25MB 限制同样只在前端。**建议** 服务端补同款限额。

### P1-4 429 重试机制脆弱
`studio.js:660-675`:重试条件把 `anaRes.status===429`、`errText.includes("429")`、`rText.includes("HTTP 429")`、`rText.includes("限流")` 混用;后端 `call_llm_reasoner` 的流式解析只对 `data: ` 前缀行容错,非流式错误体(纯 JSON)会落入 `stream_err_msg` 兜底,返回形状与前端期望(`analysis.thinking_meta.reasoning_text`)不一致时前端不显式报 429 而直接展示空思考链。后端重试 4 次 + 前端 3 次叠加,最坏 ~2×(2s+4s+6s)+后端 4×~2s ≈ 30s+ 的静默等待。

### P1-5 slug 智能建议越界
`studio.js:407`(`updateFileListUI`):当 slug 输入框仍是默认占位值(`case-my-problem`)时,载入任意文件即**静默改写** slug 为 `case-<文件名>`,用户照默认值提交的运行目录与预期不符;且只检查三个魔法字符串。**建议** 改为显式提示"建议 slug:xxx,已自动应用"或加确认。

### P1-6 `isOffline` 死分支
`studio.js:848`:`savedModel === "offline" || (!savedKey && !savedModel)` —— 第二项永远为 false(两处均有 `|| "spark-x2.6"` 兜底),纯死代码,且掩盖了"离线"的真实判定口径。

### P1-7 浏览器模式记忆与首屏竞态
`common.js:setAppMode` 写 `localStorage.orpath_mode`;`studio.js:42` 读回以恢复模式。若 localStorage 被设为 `inspector` 而当前 slug 无盘上产物,首屏停在监视台空态,Studio 入口只剩顶部按钮 —— 无降级提示。次要,但与 P0-3 的"空数据应诚实"原则同源。

### P1-8 `/api/stream` SSE 死端点
`_sse_loop`(`:1685-1720`)完整实现了 0.5s 轮询流,但**前端从未 fetch `/api/stream`**(全库 grep 无引用),是纯死代码;SimpleHTTPRequestHandler + ThreadingHTTPServer 下每个挂着的 SSE 连接都是长驻线程,白耗 fd。

---

## 4. P2 — 冗余文件 / 死代码 / 架构残留

### P2-1 `studio.html` 的 6 张硬编码 agent 卡是死标记
`src/html/studio.html` 内联了 Supervisor/Researcher/Modeler/Verifier/Realities/Redteam 六张卡片约 120 行 HTML,但 `initStudioWorkbench` 第一帧就调用 `renderDomainAgentStrip("default",…)` **整体替换 `strip.innerHTML`**。这份标记只在 JS 失败时短暂可见,是双重真相源(改文案要改两处)。同源问题:`legacyAliases=["Supervisor","Researcher","Modeler","Verifier","Realities","Redteam"]`(`studio.js:493`)保证重建后 id 与旧标记一致 —— 兼容的对象是"死标记",不是外部契约。

### P2-2 Footer 隐藏 token span 是测试钩子伪装成 UI
`src/html/inspector.html` 末尾 `<span style="display:none">` 内嵌 `auto-resume disabled · ORPATH_LANGFUSE · pi-kanban · /supervise · data-orpath-tier2 · 怎么了 · 为什么 · 复制命令 · 复制错误 · Jump stage …` 等一串关键词。这是给 `scripts/dialogue_steer_gate.py` / `problem_workbench_gate.py` / `m1_gate.py` / `v0_watch_gate.py` 做**纯字符串 grep**的保命符(gate 直接 `read watch.html` 断言子串)。它不是 UI 却长期随产品分发,任何文案调整都可能误伤 gate;反之 gate 的存在又冻结了文案。**建议** 把 marker 清单抽成 `contracts/watch_markers.json`,gate 与 build 共用。

### P2-3 `NODE_ZH` 残留已退役的旧 agent 名
`common.js:20-43`:`supervisor / or_researcher / or_verifier_writer / retrieve(混入)` 三个键在当前 `stage_map.json`(16 个 L0 节点)之外,永不命中;同时 `model/research/solve` 等键与 stage 名重名可能造成误译。`STATUS_ZH` 的 `no_product_run / available / thinking_unavailable` 在前端渲染路径中未见消费。无害但属化石。

### P2-4 Pi/LG 术语未随架构退役更新
AGENTS.md 已声明 "Legacy Node.js pi CLI wrapper … permanently stripped and retired",但前端仍处处可见:
- `inspector.html`: `影响随后启动的 Pi 会话`、`方法偏好 (Pi,逗号分隔)`、`求解模式 (LG)`、`续跑提示 (LG)`;
- `inspector.js`: `submitSteer` 的 `source:"watch_form"`、`lg/pi` 字段名;
- `orpath_watch.py` docstring `current Pi model + presets`、`_handle_intake_run` 的 `ORPATH_PI_SESSION` 环境变量继承。
字段名(API 契约)可保留,但**面向用户的文案与注释应更新**,否则用户被引导向不存在的执行模型。

### P2-5 磁盘上的冗余产物
- `dist/` 140MB 发布 zip(已 gitignore,但常驻磁盘,易被误打包进交付);
- `outputs/.drafts/` 1.2MB 历次门禁生成的 figure HTML 草稿(运行痕迹,非产品资产);
- `orpath/web/__pycache__`、`orpath/__pycache__` 等。

### P2-6 `watch.html` 单文件内嵌全部源码的双源真相
232KB 的生成物被 git 跟踪,`build.py` 又在 `do_GET /` 时**静默增量重建**(`:698-704`)。结果:源码改动未跑 build → watch.html 陈旧仍被 serve;git diff 混入生成块;release 包出现 src 与 watch.html 两份真相。**建议**:CI 强制 rebuild 校验(`needs_rebuild` 失败即红灯),生成物发布前才落盘。

### P2-7 死别名与死全局
- `orpath/studio_analyzer.py:186` `extract_case_data_profile = profile_inbox_assets`(全库无调用);
- `common.js:19` `let modelPresets = []` 仅被 `inspector.js fillModelSelect` 写回、无跨文件读;
- `watch.py:56` 附近 `HTML_NAME/PORT` 之外的常量 `SSE_INTERVAL_S` 只服务死端点(P1-8)。

### P2-8 `_pick_python` 的 `.venv-314` 考古
`scripts/orpath_watch.py:230-241` 优先探测 `.venv-314/…`;`START.sh:16-20` 却优先 `.venv`。两处探测顺序不一致,若机器上同时存在 `.venv-314`(Python 3.14 试验残留)与 `.venv`,Watch 服务与 bash 直跑会走不同解释器,产物分裂。

### P2-9 `/src/` 静态服务暴露未使用能力
`do_GET` 的 `/static/`、`/src/` 分支(`:706-728`)带正确 `resolve()+startswith()` 防穿越,但前端是内联模式,从未请求这些路径 —— 为"可能的服务端渲染/调试模式"预留,实则只增加暴露面。

### P2-10 CSP 过度放宽
`watch.html` 与 `_send_html_file` 的 CSP:`script-src 'self' 'unsafe-inline'` —— 单文件内联脚本确实需要,但 `img-src data:` + `unsafe-inline` 组合使任何注入的内联脚本不受外链限制;既然全部代码本就内联,可用 nonce/hash 收紧(可选优化)。

### P2-11 `server_version` 与文档版本线
`server_version = "ORPathWatch/1.0.0"` 正确对齐 VERSION;但 `tool_catalog.py`/docstring 中残留的 `Pi` 字样(P2-4)同样需要对齐。(此项轻,列入待办即可)

---

## 5. P3 — 硬编码清单(建议入配置/常量)

### 前端 (`orpath/web/src/js/`)

| 位置 | 硬编码 | 说明 |
|------|--------|------|
| `studio.js:392-395` | 200 文件 / 25MB / 10MB / 深度 12 | 客户端限额,服务端无对应(P1-3) |
| `studio.js:418-489` | 10 域 × 6 角色 = 60 条假 agent 配置 | `role` 如 `or-vrp-hgs`、`tool` 如 `solve_alns`/`pyjobshop_alns`/`osm_distance_engine` 等 **tools/ 目录不存在对应文件** —— 片头动画的"智能体"全是演示皮。建议:profile 数据从 `orpath/agents/domain_analytics.py` 注册表注入,或徽标注明"演示编队" |
| `studio.js:637-645` | 8 工位 TSP 预设题面+coords | 演示数据可接受,建议抽 `fixtures/` 引用 |
| `studio.js:968-1090` | ft06 16 工序、makespan 55、颜色表 | 假数据 fallback(见 P0-3) |
| `studio.js:1104-1228` | Solomon 12 坐标、车队 1-4、载重/里程 | 假数据 fallback(见 P0-3) |
| `studio.js:1242-1340` | 9 点 gap 曲线 210→128、"0.00% 严密闭合" | 严重(P0-3) |
| `studio.js:695` | `"🚀 启动全流程分析研判"` | 与 HTML 按钮 `"🚀 深度分析与研判建模思路"` 不一致,首次运行后按钮文案漂移 |
| `studio.js:848` | offline 判定 | 死分支(P1-6) |
| `inspector.js:114` | `<option value="deepseek|deepseek-v4-flash">DeepSeek V4 Flash` | fillModelSelect 兜底项硬编码,且与 `_MODEL_PRESETS` 不同步维护 |
| `common.js:5-6` | `POLL_MS=1000`、`EVENT_WINDOW=80` | 合理默认,建议入文件头常量注释(已现状)或 query 可配 |
| `studio.html` | `value="case-my-problem"` slug 默认值 | 触发 P1-5 静默改写 |
| `modals.html` | `内置赛题与工业案例 (9)` 计数 | 预设实际 14 个(`PROBLEM_PRESETS`),文案与数据漂移 |

### 后端 (`scripts/orpath_watch.py` / `orpath/`)

| 位置 | 硬编码 | 说明 |
|------|--------|------|
| `:56` | `DEFAULT_PORT=8765` | 与 START.sh 重复定义,建议单一来源 |
| `:230-241` | `.venv-314` 优先探测 | P2-8 |
| `:253-256` | `_sanitize_slug` 白名单 `[a-zA-Z0-9_-]` + 48 截断 | 合理;但 artifact 漏用(P0-2) |
| `_handle_intake_run:1130+` | 拦截文案中"已注册工业算例域: tube_cut, polyomino_cover, vrp, tsp, shortest_path" | 与 `domain_registry` 实际注册列表可能漂移,建议动态拼接 |
| `:1196` | `timeout=300` 子进程上限 | 建议 env 可调 |
| `:1280, :1380` | `detected_class … or "tsp"` | 研判失败时默认 TSP,可能误跑 `--solve-mode ortools`;建议失败即 BLOCKED |
| `:1657-1663` | 摘要文案(P0-4) | — |
| `:809` | artifact 内容截断 120000 字符 | 常量,合理;建议命名常量 |
| `studio_analyzer.py:211,215` | xfyun/deepseek 默认 base_url | 合理默认,建议 env 集中 |
| `studio_analyzer.py:440-468` | 手写 `.env` 行解析(`XFYUN_API_KEY=` split) | 不处理 export/注释/引号嵌套,建议 `python-dotenv`(若已依赖)或明确语法约定 |
| `process_memory.py/watch_snapshot.py` | 阶段名 → 中文映射 `_NODE_ZH` 重复实现(与前端 NODE_ZH 那份同源) | 双语言真相:同一改名要改 Python+JS 两处。建议暴露 API 由前端取用 |

---

## 6. 前后端契约核对(通过项,防止修复时回归)

已逐一对撞、**无键名漂移**的接口:

| 端点 | 前端消费键 | 后端生产键 | 结论 |
|------|-----------|-----------|------|
| `POST /api/studio/analyze` | `analysis.thinking_meta.{reasoning_text,live_thinking,model_used}` `knowledge_hits[].{title,snippet,score}` `domain_diagnosis.{problem_class,domain_name,recommended_algorithm,algorithm_comparison,rationale}` `data_alignment.matched_variables[].{name,source,details,status}` `clarification_questions[].{id,question,options[{id,label,recommended}]}` | `studio_analyzer.run_deep_analysis` 返回 `thinking_meta:{mode,live_thinking,model,reasoning_text,citations,knowledge_hits,…}` + `knowledge_hits` + `clarification_questions` + `domain_diagnosis` + `data_alignment` | ✅ 一致 |
| `POST /api/studio/confirm` | `plain_language_summary.{headline,objective_str,validation_status,solution_detail}` `solution{status,objective,solver,schedule[].{machine,job,start,end,duration,task}}` `validation.checks[{name,ok,got,detail}]` | 同左 | ✅ 键一致,**值可信度问题见 P0-4 / P0-3** |
| `GET /api/problems` | `presets[].{id,title,tags,desc,can_solve,intake_only}` `cases[].{slug,title,problem_class,objective,…}` | `PROBLEM_PRESETS` + `_discover_workdir_cases` | ✅;但 modals.html"9 个"计数已漂移(P3) |
| `GET/POST /api/model` | `presets[].{provider,model,label}` | `_MODEL_PRESETS` 4 项 | ✅ 值 `provider|model` 拼接一致 |
| `GET /api/snapshot` | `poll.{fingerprint,events_count,dirty,sources_fresh,events_truncated}` `stages[].{seq,node,stage,state,last_error,human_required}` `artifacts{}` `tier2{}` `dialogue{bubbles,steer_path,steer_exists}` `problem_view{…}` `pi_model` | `watch_snapshot.build_snapshot` | ✅ 已抽查 |
| `POST /api/steer` / `GET` | `errors`(数组)、`next_actions[{title,command,reason}]`、`path` | `normalize_steer_payload` / `build_steer_cta` | ✅;禁止键 `objective/tour/routes/path/proven_optimal/global_optimal/optima/best_cost` 前后端同心(前端 confirm 的 `selected_options` 只传 q_algorithm 等白名单) |
| 数据模式导入 4 路 | preset/upload/text/folder 四模态请求与响应字段(`slug/thread_id/domain_guess/data_profile/problem_view`) | `_handle_intake_import` | ✅;folder 模式 rel_path 已做穿越防护(`startswith("/")`, `../`, `/../` in `/rel/`),服务端未再上锁也无总量限制(P1-3) |

---

## 7. 修复优先级路线图

1. **本周(P0)**
   - ① `START.sh`/`START.bat` 回退 `--host 127.0.0.1`,或在 0.0.0.0 场景加共享 Token;`_send_json` 去掉无条件 CORS `*`。
   - ② `_qs_slug_thread` 接 `_sanitize_slug`。
   - ③ 三图表改为"无数据即空白 + 中性徽标";收敛曲线读真实 gap 历史;角标断言改由 validate.checks 聚合。
   - ④ confirm 摘要按 `proven_optimal` 分档,`checks_count=0` 禁言"100% 合格",frontend 透出 provenance 徽标。
2. **两周内(P1)**:confirm 全路径超时(multiagent+graph 统一工作者线程+前端 AbortController);intake/run 加运行中锁与 stage 清理确认;服务端导入限额;slug 自动改写改显式提示。
3. **整理季(P2/P3)**:删 studio.html 死卡片;marker span → contracts JSON;统一 NODE_ZH 双语为单一来源;清理 `.venv-314` 探测顺序与 Pi 文案;移除 SSE 死端点或接上真实前端订阅;把均匀硬编码的 `.env` 解析与默认 URL 收归 config 层。

## 8. 值得表扬的点(稳定性基线)

- `build.py` 的增量重建 + `assert "boot();" in output` 防呆,rebuild 检测已验证为 False(当前同步);
- folder 导入服务端 rel_path 穿越防护、`_pick_python` 多 venv 探测、steer 写盘前 slug 消毒、artifact 读取的白名单后缀映射 —— 安全基本功在;
- 前后端 4 大接口键名全部对撞通过,无隐式契约漂移;
- CSS 无重复定义冲突,`.dropzone` 两处实现(studio/inspector)职责清晰。

> 报告路径: `docs/frontend_integration_audit.md` · 生成方式: 全量源码通读 + 端点逐项审计 + 契约对撞,所有结论标注 文件:行号 可复核。
