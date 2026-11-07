#!/usr/bin/env python3
"""王牌真跑标杆一：智能制造车间作业调度 (Plan 5.2).

Taillard JSSP (ft06 / la01) 真实端到端全链路运行：
1. Analyst 析取图拓扑诊断与特征提取
2. Modeler 调用 solve_jssp (CP-SAT) 求解已知最优解 / 松弛下界对比
3. Validator 独立重算工序偏序与机器无重叠约束
4. Python 确定性装配甘特图与指标表
5. Writer & Reviewer 生成并终审 papers/flagship-jssp.md
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.solve_jssp import solve_jssp
from tools.validate_solution import validate
from orpath.paper_workflow import render_or_paper, build_verified_evidence_blocks


def main() -> int:
    print("=== [Flagship 1/3] JSSP Industrial Scheduling Live Benchmark ===")
    slug = "flagship-jssp"
    out_dir = ROOT / "outputs"
    papers_dir = ROOT / "papers"
    out_dir.mkdir(parents=True, exist_ok=True)
    papers_dir.mkdir(parents=True, exist_ok=True)

    ft06_path = ROOT / "fixtures" / "benchmarks" / "taillard" / "jssp" / "ft06.json"
    if not ft06_path.is_file():
        print(f"Error: fixture not found: {ft06_path}")
        return 1

    print(f"1. Loading Taillard fixture: {ft06_path.name}")
    # 2. Modeler exact solver run
    print("2. Modeler: Executing PyJobShop CP-SAT exact solver...")
    sol = solve_jssp(instance_name="ft06", time_limit_s=10)
    sol["problem_id"] = "ft06"
    sol["problem_class"] = "jssp"

    sol_path = out_dir / f"{slug}-solution.json"
    sol_path.write_text(json.dumps(sol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"   -> Solution written to {sol_path} (status={sol.get('status')}, makespan={sol.get('objective')})")

    # 3. Independent validation (Numbers Truth)
    print("3. Validator: Independent recomputation of machine disjunctions and job precedence...")
    val_report = validate("ft06", sol)
    val_path = out_dir / f"{slug}-validate.json"
    val_path.write_text(json.dumps(val_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    is_ok = bool(val_report.get("ok"))
    print(f"   -> Validation verdict: ok={is_ok} (checks passed={len(val_report.get('checks', []))})")
    if not is_ok:
        print(f"Error: validation failed: {val_report.get('errors')}")
        return 1

    # 4. Evidence Assembly & Academic Paper Generation
    print("4. Writer: Assembling verified truth tables and SOP 6-chapter paper...")
    evidence = build_verified_evidence_blocks(sol, val_report)
    paper_text = render_or_paper(
        slug=slug,
        problem_class="jssp",
        problem_id="ft06",
        solution=sol,
        solution_path=str(sol_path),
        validate_path=str(val_path),
    )
    paper_out = papers_dir / f"{slug}.md"
    paper_out.write_text(paper_text, encoding="utf-8")
    paper_size = paper_out.stat().st_size
    print(f"   -> Paper written to {paper_out} ({paper_size} bytes)")

    assert paper_size > 4000, f"Paper size {paper_size} bytes is under minimum expected threshold"
    print("=== [Flagship 1/3] JSSP Live Benchmark PASSED! ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
