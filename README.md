# OR-Path 多智能体运筹工作台

**一句话：** 自然语言 / 题面 → 检索研究 → 建模（无最优值）→ **求解器出数字** → validate 重算 → 解释 / 论文。  
**LangGraph 管阶段 · Pi 子 Agent 管隔离 · gate 管质检 · Watch 管过程脸。**

| | |
|--|--|
| 产品名 | OR-Path Multi-Agent / Graph-OR Agent |
| 主入口 | **`START-CASE.bat`（路径 A）** · **`START-WATCH.bat`（过程脸）** · `orpath.bat menu` |
| 硬法 | **`specs/`**（门禁真输出 > specs > 本文件 > docs） |
| 默认 | Live 多 Agent 可开；题面用 intake；**数字只认 solve+validate** |
| 不是什么 | 不是 Hermes 产品运行时；裸聊天 ≠ 多 Agent；开文件夹 ≠ 实时可视 |
| 安装 | **`docs/install.md`** · `orpath.bat setup` · L2 Release 半肥包 |

---

## 全新机器（L1）

```bat
git clone https://github.com/lanzaoi/or-path.git
cd or-path
orpath.bat setup
orpath.bat doctor
START-WATCH.bat
:: 默认 live-btube 来自 demo/seed（回放，不是你机器上的旧 LIVE 私货）
orpath.bat demo-m0 --slug m0
orpath.bat watch --slug m0
```

前置：Python **3.11+**、Node **≥ 22.19**（详见 `docs/install.md`）。  
LIVE 多 Agent：复制 `.env.example` → `.env`，填写 `DEEPSEEK_API_KEY`。

### L2 Release（路人 / 一键）

```powershell
# 发布 tag 后：
# irm https://github.com/lanzaoi/or-path/releases/download/v0.2.0/install.ps1 | iex
# 作者打包：
orpath.bat pack-release
orpath.bat l2-gate --zip dist\orpath-0.2.0-win-x64.zip
```

---

## 已装好后的 30 秒（Windows）

```bat
cd /d <ORPATH_HOME>
set PYTHONPATH=
set PYTHONNOUSERSITE=1

:: 1) 路径 A：本地案例文件夹 + 边跑边看（推荐日常）
START-CASE.bat
::    选 2 → 贴案例目录（不要引号）→ slug → 可选题面 PDF → LIVE y/N

:: 2) 只看过程脸（默认圆管 live-btube seed）
START-WATCH.bat

:: 3) 命令行
orpath.bat doctor
orpath.bat watch-run --workdir D:\cases\demo1 --slug demo1 --keep-watch
orpath.bat watch --workdir D:\cases\demo1 --slug demo1
```

| 双击 | 做什么 |
|------|--------|
| **`START-CASE.bat`** | 路径 A：指定本地文件夹；watch-run / 只看脸；题面可选；LIVE 可选 |
| **`START-WATCH.bat`** | 一键 Watch 脸（默认 `live-btube` seed） |
| **`START-ORPATH.bat`** | 1 菜单 / 2 Watch |

路径粘贴 **不要带引号**。页面旧样式 → **Ctrl+F5**。Watch 结束 → 黑窗 **Ctrl+C**。

---

## 你先盯这 6 个

| # | 路径 | 干什么 |
|---|------|--------|
| 1 | **`START-CASE.bat` / `START-WATCH.bat`** | 日常入口 |
| 2 | **`ORPATH.md`** | 操作说明（路径 A · Watch · LIVE） |
| 3 | **`specs/README.md`** | 法条索引；过程脸 `process-visibility.md` |
| 4 | **`orpath/`** | LG 骨架 · `watch.html` 中文脸 · workdir 合同 |
| 5 | **`tools/`** | solve_dispatch / validate / polyomino / tube |
| 6 | **`docs/m2-polyomino.md` · `docs/m1-smoke.md`** | M2 域桥 · M1 workdir 冒烟 |

历史关单 → `docs/archive/`。带外大树 → `docs/OUT_OF_BAND.md`。

---

## 里程碑（别被文件名绕晕）

| 阶段 | 状态 | 记住一句 |
|------|------|----------|
| T1–T2 / 1.0 / 1.1 | CLOSED/PASS | 薄全链 · 求解加厚 · 论文协议 · 题面 intake |
| V0 / M0 / M1 | 工程收口 | 过程脸 · mock 证据 · **HOME≠WORKDIR** |
| **M2 polyomino** | 工程收口 | 第一域桥；金标 Q1.1 **obj=6**；`orpath.bat m2-gate` |
| 圆管 LIVE | 旁路演示 | slug `live-btube`，obj **99000**（FEASIBLE 轨） |
| M3 / M4 | 未开 | 真 launch 注入 / 记忆+MCP 后置 |

**竞赛 B 题全问（Q1–Q3）** 数值 bank：`outputs/b-polyomino/`（gitignore 运行时目录，本机可有）。  
打包到案例目录：

```bat
.venv-314\Scripts\python.exe scripts\pack_b_polyomino_case.py --case D:\cases\my-b
:: 论文 → <case>\papers\B-polyomino-full-paper.md
```

> 产品链单次 `watch-run` 默认 `polyomino_b_q1` 只演示 **Q1.1**；**全问以 b-full bank + 打包论文为准**。

金标（只认求解器+validate）：最短路 **42** · TSP n=8 **45** · VRP **58** · poly Q1.1 **6**。

---

## 路径 A 合同（必读）

| 概念 | 含义 |
|------|------|
| **安装根 `ORPATH_HOME`** | 代码 / `.pi/agents` / 工具（本仓库） |
| **案例目录 `ORPATH_WORKDIR`** | 产物：`outputs/` · `runs/<slug>/` · `papers/` · `notes/` |
| **Watch** | 必须 **同一 workdir + 同一 slug** |
| **LIVE** | 真 Pi subagent（慢、要 Key）；失败时建模可回退确定性 schema |

```bat
:: 骨牌 PDF 示例（LIVE=yes）
orpath.bat watch-run --workdir C:\Users\...\Desktop\test --slug run1 --keep-watch --live ^
  --auto-intake --intake-in C:\Users\...\Desktop\test\B题.pdf ^
  --problem-id polyomino_b_q1 --problem-class polyomino_cover --solve-mode polyomino
```

`START-CASE.bat` 会按文件名猜 polyomino / tube，并去掉错误的外层 `--fresh`（fresh 只在内部 `run`）。

---

## 实时过程台（Watch）

- 中文 · 浅色 Apple 风 UI：`orpath/web/watch.html`
- 顶栏可 **换模型**（写 `.pi/orpath_model.json`，影响后续 Pi 会话）
- 合同：`specs/process-visibility.md` · 冒烟：`docs/v0-smoke.md`

```bat
orpath.bat face
orpath.bat watch --slug live-btube
orpath.bat watch --workdir D:\cases\x --slug x
orpath.bat p3-gate
orpath.bat m1-gate
orpath.bat m2-gate
```

---

## 常用命令

```bat
orpath.bat menu
orpath.bat doctor
orpath.bat gate-t3
orpath.bat m0-gate
orpath.bat m1-gate
orpath.bat m2-gate
orpath.bat tube-live-gate
orpath.bat run --problem-id shortest_path --solve-mode mock --slug demo --fresh
orpath.bat status --thread-id demo
```

环境：

```bat
set PYTHONNOUSERSITE=1
:: 优先 .venv-314，勿混 Hermes 全局包
:: 清 PYTHONPATH / PYTHONHOME
```

---

## 目录地图（精简）

```text
START-CASE.bat / START-WATCH.bat / START-ORPATH.bat   一键入口
orpath.bat / ORPATH.md                                主控与操作
specs/                                                硬法 SDD
orpath/                                               LG + Watch 脸 + workdir
  web/watch.html                                      中文过程台
  domain_registry.py                                  M2 域别名
  pi_model_pref.py                                    换模型偏好
tools/                                                求解器真相
  solve_polyomino.py / solve_polyomino_q3.py          骨牌 B
  solve_tube_cut_b2026.py                             圆管
scripts/                                              门禁与打包
  pack_b_polyomino_case.py                            全问→案例目录
  guess_intake_domain.py                             题面文件名猜域
fixtures/t1|t2|t3/                                    金标与域壳
docs/                                                 活文档（m1/m2/v0 smoke）
.pi/agents/or-*.md                                    真 sub 角色
```

运行时（多半 gitignore）：`outputs/` · `notes/` · `papers/` · `runs/` · `.venv-314/` · `runtime/node_modules/`

---

## 硬规矩

1. **数字**只来自 solve 工具 + validate 重算；散文/记忆不得冒充最优。  
2. **真多 Agent** = 磁盘 `outputs/.agents/<slug>/` 有 subagent 轨迹；裸 `pi -p` 不算。  
3. **schema 禁 objective**；paper R2 数字 ⊆ solution.json。  
4. **路径 A**：HOME≠WORKDIR；agent 定义读安装根，产物写案例目录。  
5. **勿提交** contest PDF、`inbox/*`、整棵 **`.hermes/`**、密钥。细则：`docs/repo-surface.md`。

---

## 文档入口

| 文档 | 用途 |
|------|------|
| [`ORPATH.md`](ORPATH.md) | 日常怎么跑 |
| [`specs/README.md`](specs/README.md) | 法条索引 |
| [`docs/README.md`](docs/README.md) | docs 导航 |
| [`docs/m2-polyomino.md`](docs/m2-polyomino.md) | M2 骨牌 |
| [`docs/m1-smoke.md`](docs/m1-smoke.md) | M1 workdir |
| [`docs/v0-smoke.md`](docs/v0-smoke.md) | Watch 冒烟 |
| [`AGENTS.md`](AGENTS.md) | Pi/助手项目法 |

---

## 仓库

私有：`https://github.com/rika-sleep/or-path`  
许可证与贡献以仓库设置为准。
