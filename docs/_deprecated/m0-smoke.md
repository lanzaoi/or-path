# M0 Demo 冒烟

**目的：** 一条命令串起 **V0 脸 + 可信数字 + 证据清单**（Phase D）。  
**法：** `specs/product-flow-sdd.md` §9 · `specs/process-visibility.md`

## 默认命令（推荐 · 不烧 Pi）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
orpath.bat doctor
orpath.bat demo-m0 --slug m0
orpath.bat watch --slug m0
orpath.bat m0-gate
```

默认：`shortest_path` + **`solve-mode mock`** + **LIVE OFF**。  
`objective` **只**来自 `outputs/m0-solution.json`（solve 工具），并经 `m0-validate.json` 重算。

## 证据文件

| 路径 | 内容 |
|------|------|
| `outputs/m0-solution.json` | 数字 |
| `outputs/m0-validate.json` | validate |
| `outputs/m0-evidence.json` | D0–D7 清单机读（slug=m0） |
| `outputs/m0-evidence.md` | 人读摘要 |
| `runs/m0/stages/` | L0 |
| `orpath.bat watch --slug m0` | 实时脸 |

> 其它 slug：`outputs/<slug>-m0-evidence.json`。

## D3 真 sub

- **默认：** 允许从历史 `outputs/.agents/**`（如 `test`）认 toolCall 证据（演示机常已有）。  
- **本 run 也要 LIVE sub：**  

```bat
orpath.bat demo-m0 --slug m0-live --live
:: 慢，需 Pi + API
```

- **强制本 slug 有 sub 才 0：** `--require-sub`（无证据 exit 3）

## 门禁

```bat
orpath.bat v0-watch-gate
orpath.bat m0-gate
```

`m0-gate` = V0 + demo-m0 mock 数字 + 清单；**不**每次强制新 LIVE。

## 与 gui-demo 区别

| | gui-demo | demo-m0 |
|--|----------|---------|
| 目标 | 快速 intake+mock | **M0 证据串** |
| 清单 D0–D7 | 否 | 是 |
| V0 gate | 否 | 内嵌 |
| watch 话术 | 附属 | 合同入口 |

## 诚实边界

- mock 数字 **不是**「保证全局最优」叙事；是 **工具出数 + validate** 可信链路。  
- 无历史/无 LIVE 时 **full_m0_experience=false** 但 core（V0+数字）仍可绿。  
- 未做：记忆大脑、MCP、域桥、竞赛全卷。  
