# 带外目录（Out-of-band）

下列路径**不属于 OR-Path 产品源码导航**，默认勿当业务代码读写。

| 路径 | 性质 | Git |
|------|------|-----|
| `vendor/` | 上游镜像 / 依赖快照 | **忽略** |
| `openpi/` | **已移除**（gitignore 保留） | **忽略** |
| `pi-main/` | Pi 上游/本地克隆 | **忽略** |
| `runtime/node_modules/` | Node 依赖 | **忽略** |
| `outputs/` `notes/` `papers/` `runs/` | 运行制品 | **忽略** |
| `.pi/npm/` `.pi/memory/` `.pi/orpath_model.json` `.pi-subagents/` | 本地 agent 运行时 | **忽略**（`.pi/agents` 仍跟踪） |
| **`.hermes/`** | **Hermes IDE 工作区**（含赛题 attachments） | **整棵忽略** |
| `inbox/*`（除 README） | 用户本地题面投放 | **忽略** |
| `demo/` | 可选视觉实验 | **忽略** |

## 产品应打开的树

```text
specs/                 法
orpath/                控制面 / 节点 / Watch 脸
tools/                 求解与校验
scripts/               门禁 CLI / 打包
fixtures/              金标（无 contest raw）
docs/                  活文档 + archive/
docs/archive/plans/    历史施工单（原 .hermes/plans）
.pi/agents/            or-* 角色定义
START-*.bat orpath.bat 启动器
```

## 启动器

| 文件 | 用途 |
|------|------|
| **`START-CASE.bat`** | 路径 A（本地文件夹） |
| **`START-WATCH.bat`** | 实时过程脸 |
| **`START-ORPATH.bat`** | 菜单 / Watch 选择 |
| **`orpath.bat` / `orpath.sh`** | 全命令 |
| **`pi.bat` / `pi.sh`** | Pi TUI |
| ~~`openpi.bat`~~ | **已删除** |

可上传边界细则：[`repo-surface.md`](repo-surface.md)。
