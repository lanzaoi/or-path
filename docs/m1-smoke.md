# M1 smoke（workdir + Watch 加厚）

**法：** `specs/product-flow-sdd.md` §14 M1 · 计划 `.hermes/plans/2026-08-03_220049-m1-workdir-watch-ux-five-parts.md`

## 快速门禁

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONPATH=

python scripts\m1_workdir_paths_gate.py
python scripts\m1_workdir_e2e_gate.py
python scripts\m1_watch_error_ux_gate.py
python scripts\m1_watch_cta_gate.py

:: 总装（推荐）
orpath.bat m1-gate
:: 等价：python scripts\m1_gate.py
```

## 人眼 2–3 分钟

```bat
:: workdir 边跑边看
orpath.bat watch-run --workdir %TEMP%\orpath-m1-demo --slug m1-demo --keep-watch

:: 失败/HUMAN slug（历史）
orpath.bat watch --slug live-btube
```

检查：

1. 产物在 **workdir** 下的 `runs/` `outputs/`  
2. 有错误时红条：**Copy error** / **Jump stage**  
3. **Next actions**：可复制 `orpath.bat run --resume … --from-stage …`（**不会**自动 resume）  
4. 开文件夹仍 ≠ 产品脸  

## Claim ladder

| 可说 | 不可说 |
|------|--------|
| M1 workdir + 失败可操作 CTA | 浏览器一点自动重跑全链 |
| Watch 是产品脸 | 域桥 M2 / 记忆 MCP 已交付 |
