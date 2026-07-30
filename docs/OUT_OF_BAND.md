# 带外目录（Out-of-band）

下列路径**不属于 OR-Path 产品源码导航**，默认勿当业务代码读写。

| 路径 | 性质 | Git |
|------|------|-----|
| `vendor/` | 上游镜像 / 依赖快照 | **忽略**（`.gitignore`） |
| `openpi/` | OpenPi 桌面壳源码树 | **忽略** |
| `pi-main/` | Pi 上游/本地克隆 | **忽略** |
| `runtime/node_modules/` | Node 依赖 | **忽略** |
| `outputs/` `notes/` `papers/` `runs/` | 运行制品 | **忽略** |
| `.pi/npm/` `.pi-subagents/` | 本地 agent 运行时 | **忽略** |

## 产品应打开的树

```text
specs/          法
orpath/         控制面 / 节点 / 协议
tools/          求解与门禁脚本
scripts/        门禁 CLI
fixtures/       金标（无 raw 大赛附件）
docs/           活文档 + archive/
.pi/agents/     or-* 角色定义
```

## 启动器

- `orpath.bat` / `openpi.bat` / `pi.bat` — 入口；不代表要把 openpi/pi-main 当产品模块 import。
