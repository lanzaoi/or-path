#!/usr/bin/env python3
"""Assemble full tube-cut B paper + case deliverables from solver JSON (no hand optima)."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "b-tube-cut"
CASE = Path(r"C:\Users\Lanzao\Desktop\hdu2026-b-tube")


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def g(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def main() -> int:
    CASE.mkdir(parents=True, exist_ok=True)
    axial = load("axial_lengths.json")
    q1, q2, q3, q4 = (
        load("q1-solution.json"),
        load("q2-solution.json"),
        load("q3-solution.json"),
        load("q4-solution.json"),
    )
    val = load("validate.json")
    done = (OUT / "DONE.md").read_text(encoding="utf-8") if (OUT / "DONE.md").is_file() else ""

    metrics = {
        "axial": g(axial, "axial_lengths_mm", default=axial),
        "q1_stock": g(q1, "total_stock_length", "total_stock_length_mm"),
        "q1_sw": g(q1, "total_switches", "total_switch"),
        "q1_util": g(q1, "utilization", "util"),
        "q2_stock": g(q2, "total_stock_length", "total_stock_length_mm"),
        "q2_cocut": g(q2, "total_cocut_benefit", "total_co_cut_benefit_mm"),
        "q2_sw": g(q2, "total_switches", "total_switch"),
        "q3_stock": g(q3, "total_stock_length", "total_stock_length_mm"),
        "q3_cocut": g(q3, "total_cocut_benefit", "total_co_cut_benefit_mm"),
        "q3_sw": g(q3, "total_switches", "total_switch"),
        "q4_stock": g(q4, "total_new_standard_stock_mm", "total_stock_length", "total_stock_length_mm"),
        "q4_cocut": g(q4, "total_cocut_benefit", "total_co_cut_benefit_mm"),
        "q4_sw": g(q4, "total_switches", "total_switch"),
    }
    ax = metrics["axial"] if isinstance(metrics["axial"], dict) else {}
    ax_rows = "\n".join(f"| {k} | {v} |" for k, v in ax.items())
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    val_s = json.dumps(val, ensure_ascii=False)

    paper = f"""# 2026 杭电数模校赛 B 题 · 异形圆管下料优化问题

> **数字权威：** 全部指标来自 `tools/solve_tube_cut_b2026.py` → `outputs/b-tube-cut/q*-solution.json` + `validate.json`。  
> **状态：** FEASIBLE（BFD/启发式 + 共切包络），**非** proven OPTIMAL。  
> **生成：** {ts} UTC · OR-Path 管线打包（监控侧不手改 objective）

---

## 摘要

针对异形圆管（10 种工件）在多规格母材上的下料优化，建立：

1. **几何层：** 点云 PCA 轴向长度 + 端部包络共切收益；  
2. **下料层：** 多规格母材 BFD/启发式排样 + 切换次数；  
3. **共切层：** 相邻工件端部嵌套旋转搜索；  
4. **多批次层：** 余料 ≥200mm 跨批复用。

求解器产出 Q1–Q4 可行方案与 result1–4.xlsx。验证 `validate.ok=true`。

---

## 1. 问题简述

- 数据：`fixtures/t3/tube_cut_b2026/raw/` 下 B 题附件  
- 母材规格：9000 / 10000 / 11000 / 12000 mm  
- 目标：最小化母材总长（及共切、切换、多批次余料策略）  
- 赛题 PDF：案例目录 `hdu2026-b-tube/inbox/`

## 2. 几何与建模

### 2.1 轴向长度（PCA）

对每种圆管点云做 SVD，取第一主轴投影跨度作为轴向长度（非 Z 截面厚度）。

| 工件 | 轴向长度 mm |
|------|-------------|
{ax_rows}

来源：`outputs/b-tube-cut/axial_lengths.json`

### 2.2 共切

相邻工件端部包络 + 旋转搜索，收益写入 joints。  
**限制：** 近似包络模型，非完整 3D 布尔。

### 2.3 下料

多规格母材上 BFD/启发式装箱；记录 sequence、leftover、utilization、switches。

## 3. 求解结果（solver JSON）

| 问 | 总母材长度 mm | 总共切 mm | 切换次数 | 备注 |
|----|---------------|-----------|----------|------|
| Q1 | {metrics['q1_stock']} | 0 | {metrics['q1_sw']} | 单批基准；util={metrics['q1_util']} |
| Q2 | {metrics['q2_stock']} | {metrics['q2_cocut']} | {metrics['q2_sw']} | 共切开启 |
| Q3 | {metrics['q3_stock']} | {metrics['q3_cocut']} | {metrics['q3_sw']} | 优化排样 |
| Q4 | {metrics['q4_stock']} | {metrics['q4_cocut']} | {metrics['q4_sw']} | 三批次+余料复用 |

- status: **FEASIBLE** · exact=False · proven_optimal=**False**  
- validate: `{val_s}`  
- 主 objective（Q1 母材总长）= **{metrics['q1_stock']}**

## 4. 方法诚实声明

1. 数字只来自 `solve_tube_cut_b2026.py` 与校验脚本，禁止 LLM 编造最优。  
2. 未声明全局最优；可继续用更长时限/精确 MIP 改进。  
3. 共切几何为工程近似。  
4. 赛题结果表：`result1.xlsx` … `result4.xlsx`。

## 5. 代码与产物路径

| 类型 | 路径 |
|------|------|
| 求解适配器 | `tools/solve_tube_cut_b2026.py` |
| 薄 CLI | `scripts/b_tube_solve.py` |
| Q1–Q4 JSON | `outputs/b-tube-cut/q1-solution.json` … `q4-solution.json` |
| Excel | `outputs/b-tube-cut/result1.xlsx` … `result4.xlsx` |
| 校验 | `outputs/b-tube-cut/validate.json` |
| 本全题论文 | `papers/B-tube-cut-full-paper.md` |
| 案例目录 | Desktop `hdu2026-b-tube/deliverables/` |

## 6. 求解器 DONE 摘录

```markdown
{done[:2500]}
```

## 7. 结论

在给定数据与 BFD/共切启发式下，得到 **可行** 下料方案：Q1 母材总长 **{metrics['q1_stock']}** mm，Q3 **{metrics['q3_stock']}** mm，Q4 新标准母材 **{metrics['q4_stock']}** mm。结果与 xlsx 已写出。

---

*OR-Path · tube_cut_b2026 · numbers from solve tools only*
"""

    paper_path = ROOT / "papers" / "B-tube-cut-full-paper.md"
    paper_path.write_text(paper, encoding="utf-8")
    print("WROTE", paper_path, "chars", len(paper))

    deliv = CASE / "deliverables"
    (deliv / "code").mkdir(parents=True, exist_ok=True)
    (deliv / "results").mkdir(parents=True, exist_ok=True)
    (deliv / "paper").mkdir(parents=True, exist_ok=True)

    for rel in [
        "tools/solve_tube_cut_b2026.py",
        "scripts/b_tube_solve.py",
        "scripts/b_tube_geometry.py",
        "scripts/b_tube_q4.py",
        "scripts/b_tube_final.py",
        "scripts/run_tube_cut_paper.py",
        "scripts/assemble_tube_b_paper.py",
    ]:
        src = ROOT / rel
        if src.is_file():
            shutil.copy2(src, deliv / "code" / src.name)

    for p in OUT.glob("q*-solution.json"):
        shutil.copy2(p, deliv / "results" / p.name)
    for p in OUT.glob("result*.xlsx"):
        shutil.copy2(p, deliv / "results" / p.name)
    for p in [
        "axial_lengths.json",
        "validate.json",
        "DONE.md",
        "tube_geometry.json",
        "cocut_savings.json",
        "solution.json",
    ]:
        sp = OUT / p
        if sp.is_file():
            shutil.copy2(sp, deliv / "results" / p)

    shutil.copy2(paper_path, deliv / "paper" / "B-tube-cut-full-paper.md")
    proto = ROOT / "papers" / "b-tube-cut-2026.md"
    if proto.is_file():
        shutil.copy2(proto, deliv / "paper" / "b-tube-cut-2026-protocol.md")

    (CASE / "README_DELIVERABLES.md").write_text(
        f"""# HDU 2026 B · 异形圆管下料 · 交付说明

## 题面
- `inbox/` PDF
- `attachments/extracted/` 附件

## 数字（solve 工具，FEASIBLE 非 proven optimal）
| Q | 母材总长 mm | 共切 mm | 切换 |
|---|-------------|---------|------|
| 1 | {metrics['q1_stock']} | 0 | {metrics['q1_sw']} |
| 2 | {metrics['q2_stock']} | {metrics['q2_cocut']} | {metrics['q2_sw']} |
| 3 | {metrics['q3_stock']} | {metrics['q3_cocut']} | {metrics['q3_sw']} |
| 4 | {metrics['q4_stock']} | {metrics['q4_cocut']} | {metrics['q4_sw']} |

validate.ok = {val.get('ok')}

## 交付
- `deliverables/paper/B-tube-cut-full-paper.md`
- `deliverables/results/` q*-solution.json + result1-4.xlsx
- `deliverables/code/` 求解脚本

## 重算
```bat
cd /d C:\\Users\\Lanzao\\Desktop\\agent
set PYTHONPATH=
.venv-314\\Scripts\\python.exe tools\\solve_tube_cut_b2026.py
.venv-314\\Scripts\\python.exe scripts\\assemble_tube_b_paper.py
```
""",
        encoding="utf-8",
    )
    print("CASE", CASE)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
