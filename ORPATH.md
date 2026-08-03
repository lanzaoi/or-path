# OR-Path：宿主无关主控（OpenPi 已移除）

**Hermes 不是产品运行时。** **OpenPi 桌面壳已从本安装删除**（2026-07-31，方案 B）。  
控制面：**`orpath.bat menu`**；**实时过程脸：`orpath.bat watch` / `watch-run`**；轻量对话：**`pi.bat` / `orpath.bat pi`**。

## 默认策略

| 项 | 默认 | 关闭 |
|----|------|------|
| **Live 多 Agent** | **ON**（`ORPATH_LIVE_SUBAGENT=1`） | `set ORPATH_LIVE_SUBAGENT=0` 或 `--no-live-subagent` |
| **Intake / OCR** | 有文件：`pdf_text` / ppocr / rapidocr | 无题面 → skip |
| **控制面** | **`orpath.bat menu`** | — |
| **实时过程台** | **`orpath.bat watch`**；主路径 **`watch-run`（P3）** | 不是开文件夹 |
| **CI / 门禁** | live **OFF** | `orpath.bat gate*` |

裸 Pi 聊天 ≠ 多 Agent。须跑产品图后看 `outputs\.agents\` 是否含真实 `subagent` toolCall（见 watch L1 或 log）。

## 实时过程台（产品脸 · V0 / P1–P3）

> **合同答案：协作全过程与 sub 轨迹在 watch 看，不在「打开 runs/ 文件夹」。**  
> 法条：`specs/process-visibility.md` · 总流程：`specs/product-flow-sdd.md` §8–§9。

### 主路径（P3 一条命令）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
orpath.bat watch-run
:: 保留页面：
orpath.bat watch-run --slug p3-demo --keep-watch
:: LIVE（慢）：
orpath.bat watch-run --live --keep-watch
:: M1 任意文件夹做题（产物/runs 落 workdir，Watch 读同一目录）：
orpath.bat watch-run --workdir %TEMP%\orpath-case --slug demo --keep-watch
orpath.bat p3-gate
python scripts\m1_workdir_e2e_gate.py
```

### 只开脸

```bat
orpath.bat watch --slug test
orpath.bat watch --slug myrun --workdir D:\cases\myrun
:: 可选
orpath.bat watch --slug myrun --thread-id myrun --port 8765
orpath.bat watch --slug myrun --no-browser
```

**路径合同：** `ORPATH_HOME`=安装根（tools/fixtures/.pi）；`ORPATH_WORKDIR`/`--workdir`=案例数据（outputs/notes/papers/runs）。

- 浏览器：`http://127.0.0.1:<port>/?slug=...&thread=...`（默认端口 **8765**，占用则递增）  
- 页面：L0 阶段条 · L1 派工树 + children/transcript · L2/L3 事件（lead/sub 过滤）· L4 产物  
- menu → **6 Live Watch** / **7 Watch-run 边跑边看**  
- 工程：`orpath/watch_snapshot.py` · `scripts/orpath_watch_run.py`（**无 LLM**）  
- 冒烟：`docs/v0-smoke.md` · 门禁：`v0-watch-gate` · `p3-gate` · `p4-gate` · `p5-gate` · **`m1-gate`**  
- Tier-2 深看：`docs/p4-tier2-deep-look.md`（`ORPATH_PI_SESSION=1` + pi-kanban/Fleet）  
- P5 收口：`docs/p5-closeout.md` · 可选 Langfuse：`docs/p5-tier3-langfuse.md`  
- **M1 收口：** `docs/m1-closeout.md` · 冒烟：`docs/m1-smoke.md`

## M1 · workdir + Watch 加厚

```bat
orpath.bat m1-gate
orpath.bat watch-run --workdir %TEMP%\orpath-case --slug demo --keep-watch
orpath.bat watch --slug live-btube
:: 失败时：红条 Copy error / Jump stage / Next actions → Copy cmd（不自动 resume）
```

- 路径：`ORPATH_HOME`=安装；`ORPATH_WORKDIR`/`--workdir`=案例数据  
- 门禁：`scripts/m1_gate.py`（串 Part1–4）

## M0 演示入口（数字 + 证据清单）

```bat
orpath.bat demo-m0 --slug m0
orpath.bat watch --slug m0
orpath.bat m0-gate
```

- 默认：**mock shortest_path** + LIVE OFF（稳、可重复）  
- 数字：`outputs/m0-solution.json` + `m0-validate.json`（仅 solve+validate）  
- 清单：`outputs/m0-evidence.json`（D0–D7）  
- LIVE sub 演示：`orpath.bat demo-m0 --slug m0-live --live`（慢）  
- 说明：`docs/m0-smoke.md`

| 不算产品脸（假交付） | |
|----------------------|--|
| 只开 `runs/` / `outputs/.agents/` | debug 附属 |
| 只有事后 `timeline.md` | 可导出，不替代 watch |
| 只有 gate / subagent_gate 绿 | 工程证 ≠ 用户看见过程 |
| Hermes 聊天贴 log | 非产品运行时 |

## 推荐操作（无 Hermes、无 OpenPi）

**双击打开（推荐）：** 资源管理器进入本目录，双击 **`START-ORPATH.bat`**  
（会开菜单并在结束时 `pause`，窗口不会一闪就关。）

或命令行：

```bat
cd /d C:\Users\Lanzao\Desktop\agent
orpath.bat
orpath.bat menu
orpath.bat doctor
orpath.bat watch --slug test
```

> 注意：直接双击 `orpath.bat` 现在默认也是 **menu**。  
> 若窗口闪退，用 `START-ORPATH.bat`，或在 **cmd** 里运行看报错。

菜单：Intake / inbox / run-full / gui-demo / 廉价演示 / **Live Watch** / **Demo M0** / 证据目录(debug) / doctor。

```bat
orpath.bat intake --slug ocr1 --in fixtures\intake\ocr\scan_sample.png
orpath.bat run-full --slug myrun --thread-id myrun
orpath.bat watch --slug myrun
orpath.bat pi
```

`orpath.bat openpi` → **退出码 2**，提示已移除。

## OCR / ppocr

- `ORPATH_PADDLEOCR_PYTHON`（系统 Python311 paddleocr）  
- 失败 → paddle api token → **rapidocr**  
- `backend` 写实名，禁止 placeholder 当成功  

## Pi 会话法

- `.pi/APPEND_SYSTEM.md` / 后续 `SYSTEM.md`（Feynman 对齐大改）  
- `.pi/settings.json` — pi-subagents  
- 产品 LIVE 默认 **`--no-session`**（CI/gate）；kanban 深看需 `ORPATH_PI_SESSION=1`（S1 Tier-2，非 V0 阻塞）

## 证据

| 要验 | 路径 / 入口 |
|------|-------------|
| **实时过程** | **`orpath.bat watch --slug <slug>`** |
| OCR | `notes\*-ocr.raw.md` |
| 审题 | `outputs\*-intake.json` |
| 真 MA | watch L1 或 `outputs\.agents\<slug>\*-lead-*.log` → 真实 subagent toolCall |
| 数字 | `outputs\*-solution.json` + `*-validate.json`（仅 solve+validate） |

## 话术（claim ladder 摘要）

| 可说 | 不可说 |
|------|--------|
| 本机 watch 实时台看阶段与 sub 轨迹 | 已有实时可视（仅 folder/log 时） |
| 思维链视模型是否返回；无则标 thinking_unavailable | 保证完整 CoT |
| gate 绿 = 工程证 | gate 绿 = 多 Agent 体验完成 |
| 静态 timeline 为导出 | 导出 = 已满足实时底线 |

## 法条

- **`specs/process-visibility.md`** — 实时过程台硬底线  
- **`specs/product-flow-sdd.md`** — 总流程 · V0/M0  
- `specs/openpi-boot-ma-ocr.md`（历史文件名；内容已改宿主无关）  
- OpenPi 删除说明：本文件 + `docs/OUT_OF_BAND.md`  
