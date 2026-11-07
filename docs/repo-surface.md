# 仓库表面 / 可上传边界（public）

**目的：** 分清「产品源码」与「本机/IDE 垃圾」，避免把竞赛 PDF、密钥、Hermes 缓存推上 public。

## 可以进 Git（产品）

| 路径 | 说明 |
|------|------|
| `orpath/` `tools/` `scripts/` `specs/` `contracts/` `knowledge/` `fixtures/`（无 raw 大附件） | 产品代码、求解器、规范与金标 |
| `START.bat` `START.sh` `orpath.bat` `orpath.sh` | 官方启动器与命令行调度器 |
| `docs/`（产品架构、用户指南、SOP 与 `releases/`） | 导航见 `docs/README.md`；架构见 `docs/ARCHITECTURE.md` |
| `AGENTS.md` `README.md` `ORPATH.md` `requirements.txt` | 入口、开发公约与环境依赖声明 |
| `demo/seed/` | 官方 Web Studio / Watch 默认演示种子 |
| `inbox/README.md` | 本地放题目录指引 |

## 禁止进 Git（本机 / 机密 / 赛题）

| 路径 | 原因 |
|------|------|
| **`.hermes/` 整棵** | Hermes 桌面工作区；**attachments=赛题 PDF/zip**；plans 已迁出 |
| **`.hermes/desktop-attachments/**`** | 竞赛材料，永不上传 |
| **`inbox/**`**（除 README） | 用户丢题面目录 |
| **`.env` / `*.env.local`** | 密钥 |
| **`outputs/` `notes/` `papers/` `runs/` `tasks/` `eval_or_bench/results/`** | 运行产物与内部执行清单（本地保留，不入版本库） |
| **`docs/archive/`** | 历史开发中间记录与关单草稿（已归档本地，不入版本库） |
| **`.pi/orpath_model.json`** | 本机换模型偏好 |
| **`.pi-subagents/` `.pi/npm/` `.pi/memory/`** | 运行时缓存 |
| **`demo/*` except `demo/seed/**`** | 可选视觉实验室，非产品主路径 |
| **`vendor/` `pi-main/` `openpi/` `.venv-314/`** | 上游/环境 |

## `.hermes` 架构（改完后）

```text
.hermes/                          # 本机 only · gitignore 全忽略
  desktop-attachments/            # 赛题 PDF — 绝对不上传
  plans/                          # 若本地再生成，仅本地；历史已迁 →

docs/archive/plans/               # ★ 可公开的历史施工单（从 .hermes/plans 迁入）
```

| 旧路径 | 新路径 |
|--------|--------|
| `.hermes/plans/*.md` | `docs/archive/plans/*.md` |

冲突优先级里「plans」一层改为 **`docs/archive/plans/*`（历史）**；新切片计划仍可先写本地，定稿后移入 archive 再提交。

## 启动器（统一收拢）

| 文件 | 角色 |
|------|------|
| **`START.bat`** | 统一主入口（Windows / WSL 双环境自动兼容，直接启动 Web Studio 智能工作舱） |
| **`START.sh`** | 统一主入口（Linux / macOS / WSL 终端一键启动 Web Studio） |
| **`orpath.bat` / `orpath.sh`** | 工业级命令行与门禁回归总入口（CLI Headless） |

历史遗留的 Node.js `pi.bat` / `pi.sh` 与冗余启动器均已永久剥离退役。

已删除历史冗余入口：`START-CASE.bat`、`START-WATCH.bat`、`START-ORPATH.bat`、`START-WATCH.sh`（功能已全部融合进 Web 工作舱）。  
`orpath.bat gui-demo` 仍为 **mock 冒烟命令**（不是独立 bat）。

## 检查清单（push 前）

```bat
git status
:: 不应出现：.hermes/  .env  inbox/*.pdf  outputs/  runs/
git check-ignore -v .hermes/desktop-attachments .env inbox/x.pdf
```
