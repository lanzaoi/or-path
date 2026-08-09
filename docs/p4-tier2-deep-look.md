# P4 · Tier-2 深看（Pi session / kanban / Fleet）

**脸仍是 Watch**（P1–P3）。本页讲 **第二屏：Pi session 细看**。  
法：`specs/process-visibility.md` §9 S1 · §11 P4 · **`specs/human-steer-and-pi-guidance.md` D3**。

> 手测清单（D3）：**`docs/d3-tier2-deep-link.md`**

## 一句话

| 层 | 入口 | 看什么 |
|----|------|--------|
| **Tier-1 脸** | `orpath.bat watch` / `watch-run` | LG 阶段 + lead/sub 轨迹（读盘） |
| **Tier-2 深看** | pi-kanban / Pi TUI `/supervise` | session JSONL、todos、sub 细流、目标监督 |

## 开关：`ORPATH_PI_SESSION`

| 值 | 行为 |
|----|------|
| **未设 / 0**（默认） | lead **`--no-session`**；CI/gate 不变；kanban **吃不到** 产品 lead session |
| **`1` / true / on** | lead **不写** `--no-session`；session → `~/.pi/agent/sessions/` |

```bat
set ORPATH_PI_SESSION=1
set ORPATH_LIVE_SUBAGENT=1
orpath.bat watch-run --live --keep-watch --slug p4-session
```

## 插件（项目本地）

```bat
pi.bat list
:: 应含 npm:pi-kanban · npm:pi-supervisor · npm:@juicesharp/rpiv-ask-user-question
```

Watch L4 **Tier-2 深链**面板会显示 `package_status` + 可复制命令（snapshot.`tier2.deep_links`）。

## 装/用

```bat
pi install npm:pi-kanban -l --approve
pi install npm:pi-supervisor -l --approve
pi.bat
:: /kanban start
:: /supervise Prefer exact tracks; never invent objective
```

历史长文：`docs/archive/design-notes/p4-tier2-deep-look.md`（若存在）。
