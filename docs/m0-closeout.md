# M0 Closeout（工程切片 · 诚实）

**日期：** 2026-08-03  
**状态：** **CORE PASS**（V0 脸 + mock 可信数字 + 证据清单 + 历史真 sub 证据）  
**范围：** Phase A–D（Watch + demo-m0），**不是**竞赛交卷 / 记忆 / MCP / 域桥。

## 命令证据

```bat
orpath.bat v0-watch-gate          → PASS
orpath.bat demo-m0 --slug m0      → exit 0
orpath.bat m0-gate                → PASS
orpath.bat watch --slug m0        → 本机脸（人工可开）
```

## DoD 勾选（product-flow-sdd §9.2）

| ID | 要求 | 结果 |
|----|------|------|
| D0 | V0 实时台 | **PASS** `v0_watch_gate` |
| D1 | 单一入口 | **PASS** `orpath.bat demo-m0` / menu 7 / `ORPATH.md` |
| D2 | solution + validate | **PASS** `outputs/m0-solution.json` objective=**42**（fixture-mock）+ validate ok |
| D3 | 真 subagent toolCall | **PASS（历史证据）** 默认认 `outputs/.agents/test` lead log；本 run LIVE OFF 未再烧 Pi |
| D4 | timeline 可选 | 不替代 D0 |
| D5 | 打回可讲 | **PASS** watch counters 可见（`solver_tune/schema_repair/...`） |
| D6 | 只承诺 V0+M0 | 本文 + ORPATH claim ladder |
| D7 | 无密钥进 git | 本切片未引入密钥；提交时仍须自检 |

## 产物路径

| 路径 | 说明 |
|------|------|
| `orpath/watch_snapshot.py` | L0–L4 聚合 |
| `orpath/web/watch.html` | 三栏脸 |
| `scripts/orpath_watch.py` | HTTP |
| `scripts/v0_watch_gate.py` | V0 门禁 |
| `scripts/orpath_demo_m0.py` | M0 演示入口 |
| `scripts/m0_demo_gate.py` | M0 门禁 |
| `outputs/m0-solution.json` | 数字 |
| `outputs/m0-validate.json` | 校验 |
| `outputs/m0-evidence.json` | D0–D7 机读 |
| `runs/m0/stages/` | L0 阶段 |

## 诚实边界（不可对外夸大）

1. **mock 最短路 42** = 工具链路可信，**不是**「已证明任意题全局最优」。  
2. **D3** 本机 demo 默认 **LIVE OFF**；真 sub 证据来自**既有** lead log（如 `test`）。要「本 slug 当场 LIVE sub」须：  
   `orpath.bat demo-m0 --slug m0-live --live`  
3. **S1 Tier-2/3**（pi-kanban / Langfuse）**未**做，不得当 V0。  
4. **未做：** 记忆大脑、MCP 市场、域桥 polyomino 产品化、Feynman 全量 launch。  
5. **开文件夹 ≠ 实时可视**（仍写在 ORPATH/README）。

## 回归建议（提交前）

```bat
set PYTHONPATH=
orpath.bat v0-watch-gate
orpath.bat m0-gate
:: 可选更重：
:: orpath.bat gate-t3
:: orpath.bat subagent-gate
```

## 结论

- **V0 工程底线：** 已落地可复现。  
- **M0 core 体验串：** 已落地可复现（watch + mock 数字 + 清单 + 历史 sub 证据）。  
- **作品集话术：** 用 LCC harness 层次讲「Model + Harness」；控制面 LG；脸是 watch；数字手算。  
