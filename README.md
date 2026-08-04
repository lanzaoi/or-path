# OR-Path 多智能体运筹工作台

**一句话：** 题面 / 自然语言 → 研究建模 → **求解器出数字** → validate → 论文。  
**LangGraph 管阶段 · Pi 子 Agent 隔离 · gate 质检 · Watch 过程脸。**

| | |
|--|--|
| 仓库 | https://github.com/lanzaoi/or-path |
| 主入口 | **`START-CASE.bat`** · **`START-WATCH.bat`** · `orpath.bat` |
| 法条 | **`specs/`** |
| 架构 | **`docs/ARCHITECTURE.md`** |
| 安装 | **`docs/install.md`** · Release **v0.2.0** |

---

## 30 秒上手

```bat
:: 新机器（L2）
irm https://github.com/lanzaoi/or-path/releases/download/v0.2.0/install.ps1 | iex
cd %LOCALAPPDATA%\Programs\orpath
orpath.bat doctor
START-WATCH.bat

:: 或开发者（L1）
git clone https://github.com/lanzaoi/or-path.git && cd or-path
orpath.bat setup && orpath.bat doctor && START-WATCH.bat
```

| 双击 | 作用 |
|------|------|
| **START-CASE** | 路径 A：本地案例文件夹 + 边跑边看 |
| **START-WATCH** | 过程脸（默认 live-btube **seed 回放**） |
| **START-ORPATH** | 菜单 / Watch 快捷 |

路径粘贴 **不要引号**。旧页面 **Ctrl+F5**。结束 Watch：**Ctrl+C**。

---

## 仓库结构（简洁）

```
orpath/          产品核心（LG · Watch · 控制面）
tools/           求解 / 校验 / intake
scripts/         doctor · gates · pack · watch-run · install
specs/           硬法（SDD）
docs/            活文档；历史在 docs/archive/
fixtures/        金标与冒烟数据
demo/seed/       默认脸回放（L1/L2）
.pi/agents/      Pi 角色定义
contracts/       JSON 契约
knowledge_svc/   检索侧车
START-*.bat      一键入口
ORPATH.md        操作说明
```

**本机-only（不入库）：** `.venv-314/` · `.env` · `.hermes/` · `inbox/*` · `/outputs` `/runs` 等。  
详见 **`docs/repo-surface.md`**。

---

## 硬规矩

1. 数字只认 **solve + validate** JSON。  
2. 真多 Agent = 磁盘 subagent 轨迹，不是聊天扮角色。  
3. schema **禁止** objective。  
4. **HOME ≠ WORKDIR**（安装根 vs 案例目录）。  
5. 勿提交 contest PDF、密钥、整棵 `.hermes/`。

---

## 里程碑（一览）

| 阶段 | 状态 |
|------|------|
| T1–T2 / 1.0 / 1.1 | CLOSED — `docs/archive/closeouts/` |
| V0 / M0 / M1 | 过程脸 · mock · workdir |
| **M2 polyomino** | 域桥 · Q1.1 obj=**6** |
| L1 / L2 安装 | setup + Release v0.2.0 |
| M3 / M4 | 未开 |

金标：最短路 **42** · TSP **45** · VRP **58** · poly Q1.1 **6** · tube 演示 **99000**（FEASIBLE）。

---

## 文档地图

| 读这个 | 当… |
|--------|-----|
| [`docs/install.md`](docs/install.md) | 安装 / Release |
| [`ORPATH.md`](ORPATH.md) | 每天怎么点 |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 架构 |
| [`specs/README.md`](specs/README.md) | 法条索引 |
| [`docs/README.md`](docs/README.md) | docs 导航 |
| [`docs/archive/`](docs/archive/) | 历史（默认别整树加载） |

---

## 开发常用

```bat
orpath.bat doctor
orpath.bat m2-gate
orpath.bat pack-release
orpath.bat l2-gate --zip dist\orpath-0.2.0-win-x64.zip
```
