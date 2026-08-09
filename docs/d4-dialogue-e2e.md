# D4 · 人导对话 E2E 收口

> **状态：** CLOSED engineering（2026-08-09）  
> **法：** `specs/human-steer-and-pi-guidance.md`  
> **前置：** D0 气泡 · D1 表单 · D2 LG 合并 · D3 Tier-2 深链

---

## 一句话

D4 = **表单补全 pause/at_stage + 产品 mock 跑证明 steer 改 mode + `orpath.bat dialogue-gate`**。  
仍 **不** 浏览器自动续跑；仍 **禁** objective。

---

## DoD

| # | 检查 | 命令/证据 |
|---|------|-----------|
| 1 | 表单有 `dlgAtStage` · `dlgPause` | Watch 协作对话 |
| 2 | POST 平铺 `pause_next` 写入 `lg.pause_next` | normalize / API |
| 3 | `invoke_once`：steer `networkx` 盖过 CLI `mock`，validate 绿 | gate D4 |
| 4 | `orpath.bat dialogue-gate` → `scripts/dialogue_steer_gate.py` | bat |
| 5 | 本文件 + specs 进度 D4 ✅ | docs/specs |

---

## 门禁

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONPATH=
set PYTHONNOUSERSITE=1
orpath.bat dialogue-gate
:: 等价：
.venv-314\Scripts\python.exe scripts\dialogue_steer_gate.py
```

期望：`PASS dialogue-steer-gate`（含 D0–D4）。

---

## 手测（可选）

1. `orpath.bat watch --slug live-btube` → Ctrl+F5  
2. 协作对话：mode=`networkx`，勾选 pause（可选），写备注 → **写入人导**  
3. 终端：

```bat
set ORPATH_LIVE_SUBAGENT=0
orpath.bat run --fresh --workdir <case> --slug <slug> --problem-id shortest_path --solve-mode mock --knowledge-mode off
```

日志/summary 应出现 `solve_mode=networkx` · `human_steer_applied`。

---

## 与 D0–D3

| 切片 | 角色 |
|------|------|
| D0–D1 | 看见 + 写盘 |
| D2 | LG/Pi 真合并 |
| D3 | Tier-2 可选深链 |
| **D4** | **产品路径可证明 + 表单/门禁收口** |
