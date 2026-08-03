# OR-Path M1 Implementation Plan — workdir + Watch 加厚（五段）

> **For Hermes:** Implement **one part at a time** after user says 开干. Use TDD/gates per part. Do not start Part N+1 until Part N gate green + claim ladder honest.

**Goal:** M1 = **任意 `--workdir` 做题（产物/runs 落 workdir，Watch 仍可读）** + **Watch 失败/HUMAN 可操作 + 错误可抄可定位**；大 log/真 sub 跳转尽力；paper cite **仅当演示被卡**可顺手修。

**Architecture:** Reuse existing `orpath.paths.orpath_workdir` / `ensure_workdir_layout` / watch `workdir=` plumbing. Close gaps so **run → stages → snapshot → watch** all bind the same workdir. Watch UI adds **error panel + copy + stage highlight + next-action CTAs** driven by snapshot JSON (no LLM in aggregator).

**Tech stack:** Python 3.11/3.14 venv `.venv-314`, `orpath.bat` (clear PYTHONPATH), `watch_snapshot` + `watch.html` + `orpath_watch.py` + `orpath_watch_run.py`.

**Law (frozen from user 2026-08-03):**

| 项 | 冻结 |
|----|------|
| 主轴 | **D** = workdir + Watch 脸加厚；域桥/paper 非主叙事 |
| workdir 验收 | 能 `--workdir`；**outputs/notes/papers/runs 落该目录**；Watch 读同一 workdir |
| Watch 硬点（一票否决） | **(1) HUMAN/失败下一步 CTA** + **(3) 红条 + last_error 可复制 + stage 高亮** |
| Watch 尽力 | (2) 大 log 不卡 + 一键真 sub — 不做否决 |
| 管线 | 默认可小修 launcher/watch-run；**允许**演示被 paper cite 卡住时顺手修 |
| 不做 | 记忆/MCP、M2 域桥主轴、假绑 SP、手改 objective |

**Handoff context:** `%LOCALAPPDATA%\Temp\orpath-handoff-m1-20260803.md`  
**Baseline green (before M1):** `p5-gate` · `tube-live-gate` · `m0-gate` (with `PYTHONPATH=`)

---

## Part map（五段）

```text
P1 workdir 路径合同 + 单测/门禁骨架
    ↓
P2 CLI/bat/watch-run 端到端 workdir
    ↓
P3 Watch 错误面板（copy + stage 高亮）     } 可部分并行于 P2 后半
    ↓
P4 HUMAN/失败下一步 CTA（resume/from-stage）
    ↓
P5 门禁+文档+冒烟 closeout（+ 可选 paper cite 卡演示补丁）
```

| Part | 交付物（用户可感） | 门禁建议 |
|------|-------------------|----------|
| **1** | workdir 解析/布局契约明确；snapshot/root 不串目录 | `scripts/m1_workdir_paths_gate.py` |
| **2** | `watch-run --workdir D:\case` 产物进 D、Watch 打开即可见 | `scripts/m1_workdir_e2e_gate.py` |
| **3** | 失败 slug 上：红条、复制 last_error、点 stage 高亮 | `scripts/m1_watch_error_ux_gate.py`（静态 HTML/API 断言） |
| **4** | HUMAN/blocked 时右栏/条上给出可复制命令或按钮文案 | 同上扩展 or 独立 gate |
| **5** | `orpath.bat m1-gate` + `docs/m1-smoke.md` + closeout；claim ladder | `orpath.bat m1-gate` |

---

## Part 1 — workdir 路径合同

**Objective:** 单一真相：`ORPATH_HOME` = 安装根（代码/agents/pi）；`ORPATH_WORKDIR` = 案例数据根（outputs/notes/papers/runs）。

**Files (likely):**
- Modify: `orpath/paths.py`
- Modify: `orpath/run_orpath.py` (honor `--workdir` / env when writing artifacts)
- Modify: `orpath/watch_snapshot.py` (accept workdir; default `orpath_workdir()`)
- Create: `scripts/m1_workdir_paths_gate.py`
- Read: `AGENTS.md`, `docs/p5-closeout.md` (claim style)

**Steps:**
1. Inventory every writer of `outputs/`, `runs/`, `notes/`, `papers/` under `orpath/` + `scripts/orpath_watch_run.py` — list in gate as checklist.
2. Ensure `ensure_workdir_layout(wd)` called at run start when workdir set.
3. Snapshot `build_snapshot(..., workdir=)` reads `runs/<slug>` **under workdir**, not always install root.
4. Gate: temp workdir + fake stages file → snapshot sees them; install-root stages with different slug not mixed.
5. Docstring in `paths.py` + one paragraph in plan residual risks.

**Verify:**
```bat
set PYTHONPATH=
.venv-314\Scripts\python.exe scripts\m1_workdir_paths_gate.py
```
Expected: PASS

**Out of scope:** menu UI polish, HUMAN CTAs.

---

## Part 2 — CLI / bat / watch-run 端到端 workdir

**Objective:** 用户一条命令指定 workdir，跑 mock 短链，产物只出现在 workdir，Watch API 返回该 workdir 路径。

**Files:**
- Modify: `scripts/orpath_watch_run.py` — `--workdir`, pass env `ORPATH_WORKDIR`, do **not** hardcode `setdefault(ROOT)` when flag set
- Modify: `orpath.bat` — pass-through `%2…` already; document; **careful CRLF/labels** (rewrite section if needed, no `shift`+`%*`)
- Modify: `scripts/orpath_menu.py` — optional prompt for workdir on watch-run / run
- Modify: `ORPATH.md`, `README.md` (short)
- Create: `scripts/m1_workdir_e2e_gate.py`

**Steps:**
1. `watch-run --workdir %TEMP%\orpath-m1-wd --slug m1-wd --no-browser` (mock, short timeout / skip live).
2. Assert ` %TEMP%\orpath-m1-wd\runs\m1-wd\stages` grows OR at least layout + solution/stages exist.
3. Assert `GET /api/health` → `workdir` equals that path.
4. Assert `GET /api/snapshot?slug=m1-wd` non-empty L0 when stages present.
5. Negative: wrong workdir → empty/no_product_run, not silent install-root bleed.

**Verify:**
```bat
.venv-314\Scripts\python.exe scripts\m1_workdir_e2e_gate.py
orpath.bat doctor
```

**Risk:** Pi agents still under install `.pi/agents` (OK — home vs workdir split). Subagent logs path may stay under workdir `outputs/.agents` — align with existing `subagent` writers.

---

## Part 3 — Watch 错误 UX 硬点 (3)

**Objective:** 任意 blocked/error snapshot：用户看得见、**一键复制 last_error**、点击 L0 stage **高亮**关联节点。

**Files:**
- Modify: `orpath/watch_snapshot.py` — ensure `current.last_error`, `status`, stage flags stable for UI
- Modify: `orpath/web/watch.html` — error banner, Copy button, stage highlight CSS/JS
- Optional: `scripts/orpath_watch.py` — no LLM
- Create: `scripts/m1_watch_error_ux_gate.py` — string checks on HTML + synthetic snapshot fixture

**Steps:**
1. Fixture snapshot JSON with `status=blocked`, `last_error=…`, stages with failed node.
2. HTML contains copy control + does not require LIVE server for static structure gate.
3. Manual/API: serve watch, poll fixture slug under temp workdir.
4. Keep P5 polish (follow/pause/window) unbroken — run `p5-gate` regression.

**Verify:**
```bat
.venv-314\Scripts\python.exe scripts\m1_watch_error_ux_gate.py
orpath.bat p5-gate
```

---

## Part 4 — HUMAN / 失败下一步 CTA 硬点 (1)

**Objective:** 当 `human_required` 或 gate 失败时，Watch 右栏/错误条给出**可执行下一步**（文案 + 可复制命令），至少覆盖：

- `orpath.bat run --resume --slug … --from-stage …`（或文档化的等价）
- `orpath.bat watch --slug … --workdir …`
- 若 schema/validate：指向对应 gate 名与路径字段

**Files:**
- Modify: `orpath/watch_snapshot.py` — add `next_actions: [{title, command, reason}]` pure rules from stage/last_error/counters（**no LLM**）
- Modify: `orpath/web/watch.html` — render actions + copy
- Extend: `scripts/m1_watch_error_ux_gate.py` or `m1_watch_cta_gate.py`
- Touch: `docs/m1-smoke.md` draft commands

**Rules sketch (implementer fills):**
```text
if human_required and "schema" in last_error → from-stage gate_schema / model
if validate fail → from-stage gate_validate / solve
if status blocked intake → show intake paths
else → resume + open watch
```

**Verify:** synthetic HUMAN snapshot → `next_actions` non-empty; HTML lists them; `watch_snapshot_gate` still no-LLM import ban.

**Out of scope:** actually auto-resume from browser without user confirm.

---

## Part 5 — 门禁总装 + 文档 closeout + 可选 cite

**Objective:** 一条 `m1-gate` 串 Part1–4；文档与 claim ladder；仅当 demo 路径被 paper cite 卡住时最小修复。

**Files:**
- Create: `scripts/m1_gate.py` (compose child gates)
- Modify: `orpath.bat` → `m1-gate`
- Create: `docs/m1-smoke.md`, `docs/m1-closeout.md`
- Patch: `docs/README.md`, `ORPATH.md`, `README.md`
- Optional: paper cite/claim only if blocks a chosen demo slug (document if done)

**Verify:**
```bat
set PYTHONPATH=
orpath.bat m1-gate
orpath.bat p5-gate
orpath.bat tube-live-gate
```
Human 2–3 min:
```bat
mkdir %TEMP%\orpath-m1-demo
orpath.bat watch-run --workdir %TEMP%\orpath-m1-demo --slug m1-demo --keep-watch
```
Check: stages under temp workdir; fail a run or use historical blocked slug → copy error + CTA visible.

**Claim ladder (must appear in closeout):**

| 可说 | 不可说 |
|------|--------|
| M1：workdir 做题 + Watch 失败可操作/可复制 | M2 域桥已交付 |
| 实时脸仍是 watch | 开文件夹 = 可视化完成 |
| paper cite 仅若修过且写进 closeout | 竞赛卷已交 / 全局最优 |

---

## 建议实施顺序与并行

1. **Part 1 → 2** 严格串行（路径错了 UX 白做）。  
2. **Part 3** 可在 Part 2 门禁绿后立即开（或 Part 2 后半并行，注意 watch.html 冲突）。  
3. **Part 4** 依赖 Part 3 错误条容器。  
4. **Part 5** 最后总装。

**每段结束：** 跑该段 gate + 不破坏 `p5-gate` / `tube-live-gate`；**不要** `git add` 竞赛 PDF / desktop-attachments。

---

## 风险

| 风险 | 缓解 |
|------|------|
| bat 再插坏 label | 改 bat 用小补丁或整段标签重写；改后 `cmd /c orpath.bat m1-gate` |
| 产物仍写 HOME | Part1 inventory + e2e 断言 workdir-only |
| next_actions 乱跳 stage | 白名单 from-stage 名；未知则只给 resume + 文档链接 |
| 大 log | 保持 P5 window；Part 4 不做否决 |
| paper cite 深坑 | 时间盒（例如 ≤1 会话）；超时记 closeout「未修」 |

---

## Open questions（实施前默认可用默认）

| # | 默认 |
|---|------|
| workdir 与 install 同盘权限 | 要求可写；doctor 检查 |
| `--workdir` 与 `--root` 关系 | **workdir=数据**；`--root` 若存在保持兼容或别名 workdir |
| agents 日志目录 | 优先 `workdir/outputs/.agents`；Pi 定义仍 home |

---

## 一句话

> **M1 五段：路径合同 → workdir 端到端 → 错误可抄可高亮 → HUMAN 下一步 CTA → 门禁文档收口（cite 仅挡演示时动）。**

**Plan only — 未实施。** 你回 **「按五段开干」** 或指定从 Part N 开始即可。
