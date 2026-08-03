# P4 · Tier-2 深看（Pi session / kanban / Fleet）

**脸仍是 Watch**（P1–P3）。本页只讲 **第二屏：Pi 官方级 session 细看**。  
法：`specs/process-visibility.md` §9 S1 · §11 P4。

## 一句话

| 层 | 入口 | 看什么 |
|----|------|--------|
| **Tier-1 脸** | `orpath.bat watch` / `watch-run` | LG 阶段 + lead/sub 轨迹（读盘） |
| **Tier-2 深看** | pi-kanban / Pi FleetView | Pi **session JSONL** 树、todos、sub 细流 |

## 开关：`ORPATH_PI_SESSION`

| 值 | 行为 |
|----|------|
| **未设 / 0**（默认） | lead 命令带 **`--no-session`**；CI/gate 不变；kanban **吃不到** 产品 lead session |
| **`1` / true / on** | lead **不写** `--no-session`；Pi 会把 session 落到 `~/.pi/agent/sessions/` |

```bat
:: 产品 LIVE + 写 session（可给 kanban）
set ORPATH_PI_SESSION=1
set ORPATH_LIVE_SUBAGENT=1
orpath.bat watch-run --live --keep-watch --slug p4-session

:: CI / 默认
set ORPATH_PI_SESSION=0
```

lead log 头会写：

```text
pi_session=on|off
no_session_flag=True|False
sessions_root=C:\Users\…\.pi\agent\sessions
```

## Watch 上怎么看见

打开 `orpath.bat watch --slug …` 后看右栏 **L4 · Tier-2**：

- `ORPATH_PI_SESSION=0|1` 徽章  
- `sessions_root` 路径  
- **recent sessions**（扫盘，可含交互 `orpath.bat pi` 的 session）  
- honesty：`tier2_session_off` 表示产品 lead 仍 ephemeral  

snapshot 字段：`tier2`（`pi_session_env` / `sessions_root` / `recent[]` / hints）。

## 装 pi-kanban（可选）

```bat
:: 需本机已装 Pi / npm 通道
pi install npm:pi-kanban
:: 进 Pi 会话后：
:: /kanban start
```

kanban **只读** `~/.pi/agent/sessions/...`。  
若产品一直 `ORPATH_PI_SESSION=0`，它只能看到你 **交互 Pi** 产生的 session，**不是** `watch-run` mock 全链。

文档/上游：

- https://github.com/NikiforovAll/pi-kanban  
- 文章：pi-kanban workspace（读 session、subagents）

## FleetView（可选）

交互 Pi TUI：

```bat
orpath.bat pi
:: 包若提供： /subagents-fleet  或扩展命令（以本机 pi 插件为准）
```

## 验收（P4）

| # | 检查 |
|---|------|
| 1 | 默认 / SESSION=0：`build_pi_command` **含** `--no-session` |
| 2 | SESSION=1：命令 **不含** `--no-session`；dry lead 头 `pi_session=on` |
| 3 | Watch `tier2` 有 `sessions_root` + docs 指针 |
| 4 | 本文 + `orpath.bat p4-gate` 绿 |

**不强制：** 装 kanban、烧一次 LIVE、iframe 内嵌 kanban。

## 门禁

```bat
orpath.bat p4-gate
python scripts/p4_session_gate.py
```

## 与 P1–P3 边界

- 未开 session **不**等于可视化失败（P3 主路径不依赖 kanban）。  
- 假绿禁止：仅装 kanban、未开 Watch 联跑 → 不得称「实时主路径完成」。  
