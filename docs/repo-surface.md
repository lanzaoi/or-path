# 仓库表面 / 可上传边界（public）

**目的：** 分清「产品源码」与「本机/IDE 垃圾」，避免把竞赛 PDF、密钥、Hermes 缓存推上 public。

## 可以进 Git（产品）

| 路径 | 说明 |
|------|------|
| `orpath/` `tools/` `scripts/` `specs/` `fixtures/`（无 raw 大附件） | 产品代码与金标壳 |
| `START-CASE.bat` `START-WATCH.bat` `START-ORPATH.bat` `orpath.bat` `pi.bat` `orpath.sh` `pi.sh` | 启动器 |
| `.pi/agents/` `.pi/settings.json` | Pi 角色定义与默认设置 |
| `docs/`（顶层活文档 + `archive/`） | 导航见 `docs/README.md`；架构 `docs/ARCHITECTURE.md` |
| `AGENTS.md` `README.md` `ORPATH.md` `requirements.txt` | 入口与依赖声明 |
| `demo/seed/` | L1/L2 默认 Watch 回放 |
| `inbox/README.md` | 仅说明如何本地放题 |

## 禁止进 Git（本机 / 机密 / 赛题）

| 路径 | 原因 |
|------|------|
| **`.hermes/` 整棵** | Hermes 桌面工作区；**attachments=赛题 PDF/zip**；plans 已迁出 |
| **`.hermes/desktop-attachments/**`** | 竞赛材料，永不上传 |
| **`inbox/**`**（除 README） | 用户丢题面目录 |
| **`.env` / `*.env.local`** | 密钥 |
| **`outputs/` `notes/` `papers/` `runs/`** | 运行产物 |
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

## 启动器（清理后保留）

| 文件 | 角色 |
|------|------|
| **`START-CASE.bat`** | 路径 A 日常主入口 |
| **`START-WATCH.bat`** | 过程脸一键 |
| **`START-ORPATH.bat`** | 菜单/Watch 选择薄壳 |
| **`orpath.bat` / `orpath.sh`** | 全命令入口 |
| **`pi.bat` / `pi.sh`** | Pi TUI |

已删除/不再提供：`openpi.bat`（OpenPi 壳）。  
`orpath.bat gui-demo` 仍为 **mock 冒烟命令**（不是独立 bat）。

## 检查清单（push 前）

```bat
git status
:: 不应出现：.hermes/  .env  inbox/*.pdf  outputs/  runs/
git check-ignore -v .hermes/desktop-attachments .env inbox/x.pdf
```
