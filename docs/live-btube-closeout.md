# Tube LIVE closeout — 圆管 B 题路径 A 收口

**日期：** 2026-08-03  
**切片：** `tube-live-close`  
**题：** 2026 数模校赛 B · 异形圆管下料（`live-btube`）

---

## 目标 vs 结果

| 目标 | 结果 |
|------|------|
| 路径 A `watch-run --live` 过程可跑 | **通**（L0 多站；research/model 真 sub） |
| schema 不因 `cutting_stock` / 字符串 `path` 假杀 | **通**（`gate_schema` PASS） |
| tube 工具出数（非 SP mock 42） | **通** · `objective=99000` · `source=tools/solve_tube_cut_b2026.py` · FEASIBLE |
| validate 认 `tube_cut` | **通** · `live-btube-validate.json` ok=true |
| 论文 R1/claim 全绿 | **未承诺** · cite claim 仍可 HUMAN（旁路） |

---

## 证据路径

```text
inbox/b-tube-live-once/problem.pdf
inbox/b-tube-live-once/assets/          # 解压附件
outputs/live-btube-intake.json
outputs/live-btube-schema.json
outputs/live-btube-solution.json        # tube-bfd FEASIBLE 99000
outputs/live-btube-validate.json        # ok true
outputs/.agents/live-btube/*-lead-*.log # 真 sub
runs/live-btube/stages/
papers/live-btube.md                    # 有稿；claim 门禁可红
```

---

## 代码修复（本切片）

1. **`tools/validate_solution.py`** — `_validate_tube`：q1–q4 形状、stock 和、objective=q3 优先  
2. **`tools/schema_models.py`** — `path` 仅当值为 **list**（图路径）时禁；字符串文件路径放行  
3. **`tools/gate_schema.py`** — 认 `tube_cut` / `cutting_stock` 结构键  
4. 既有：`nodes` adhoc problem_id、intake 下 tube 适配器可跑、`watch-run --intake-in`

---

## 复验命令

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONPATH=

python tools\gate_schema.py outputs\live-btube-schema.json
python tools\validate_solution.py --problem-id b-tube-cut --solution outputs\live-btube-solution.json --out outputs\live-btube-validate.json
python scripts\tube_live_gate.py live-btube
```

可选再 LIVE 全链（慢）：

```bat
orpath.bat watch-run --slug live-btube2 --live --keep-watch ^
  --intake-in inbox\b-tube-live-once\problem.pdf ^
  --intake-assets inbox\b-tube-live-once\assets ^
  --problem-id b-tube-cut --problem-class tube_cut
```

---

## Claim ladder

| 可说 | 不可说 |
|------|--------|
| 路径 A + 本题 LIVE：过程台可见，真 sub 有 log | 论文/claim 门禁已全绿 |
| 数字来自 `solve_tube_cut_b2026`，validate 重算 stock 和 | 保证全局最优 / 已交竞赛卷 |
| schema/validate 已支持 tube_cut 类 | mock SP 42 就是本题答案 |

---

## 一句话

> **圆管 B：LIVE 过程 + 真 sub + tube 可行解 + validate 绿已收口；论文 cite/claim 仍可 HUMAN，不并入本切片 PASS。**
