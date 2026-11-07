# M1 Closeout — workdir + Watch 加厚

**日期：** 2026-08-03  
**切片：** M1 Parts 1–5（计划 `docs/archive/plans/2026-08-03_220049-m1-workdir-watch-ux-five-parts.md`）  
**法：** `specs/product-flow-sdd.md` §14 · `specs/process-visibility.md`

---

## 目标 vs 结果

| 目标（用户冻结） | 结果 |
|------------------|------|
| `--workdir`：产物/runs 落案例目录，Watch 同读 | **通**（Part1 路径合同 + Part2 e2e） |
| 错误红条 + last_error 可复制 + stage 高亮 | **通**（Part3） |
| HUMAN/失败可执行下一步 CTA（resume/from-stage） | **通**（Part4 `next_actions`，**不**自动 resume） |
| 大 log / 真 sub 一键 | 尽力（P5 window 保留；非否决项） |
| 域桥 / paper 主叙事 | **未开**（cite 未作为 M1 必绿） |

---

## 五段交付

| Part | 门禁 | 要点 |
|------|------|------|
| 1 | `m1_workdir_paths_gate.py` | HOME vs WORKDIR；fixtures/tools 从 install |
| 2 | `m1_workdir_e2e_gate.py` | `watch-run --workdir` 端到端 |
| 3 | `m1_watch_error_ux_gate.py` | error 块 + Copy/Jump + stage 高亮 |
| 4 | `m1_watch_cta_gate.py` | `next_actions` 纯规则 CTA |
| 5 | **`m1_gate.py` / `orpath.bat m1-gate`** | 总装 + 本文 |

---

## 命令证据

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONPATH=
orpath.bat m1-gate
:: 等价：python scripts\m1_gate.py
```

人眼：

```bat
orpath.bat watch-run --workdir %TEMP%\orpath-m1-demo --slug m1-demo --keep-watch
orpath.bat watch --slug live-btube
:: 红条 Copy error / Jump stage / Next actions → Copy cmd
```

冒烟：`docs/m1-smoke.md`

---

## Claim ladder

| 可说 | 不可说 |
|------|--------|
| **M1**：任意 workdir 做题 + Watch 失败可操作/可复制 CTA | M2 域桥已交付 |
| 实时脸仍是 **watch**（不是开文件夹） | 浏览器自动 resume 全链 |
| mock/工具数字仍只认 solve+validate | 竞赛卷已交 / 全局最优 |
| paper cite 未并入 M1 PASS | 记忆 / MCP / Langfuse 全埋点已做 |

---

## 关键路径

```text
orpath/paths.py
orpath/run_orpath.py          # --workdir
scripts/orpath_watch_run.py   # --workdir
scripts/orpath_watch.py
orpath/watch_snapshot.py      # error + next_actions
orpath/web/watch.html
scripts/m1_*_gate.py
scripts/m1_gate.py
orpath.bat m1-gate
docs/m1-smoke.md
docs/m1-closeout.md           # 本文
```

---

## 一句话

> **M1 收口：workdir 做题 + Watch 错误可抄可定位 + HUMAN 下一步可复制命令；不宣称自动重跑、不宣称域桥/交卷。**
