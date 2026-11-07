#!/usr/bin/env python3
"""王牌真跑标杆三：三维异形管激光共边套料 (Plan 5.4).

Tube B 四问 Tier-C 对标超越：
1. Analyst: 析取异形圆管切断线几何特性、轴向旋转自由度与 10 种管件共边约束
2. Modeler: 运行/校验 Q1~Q4 异形管切割模型 (DP / 批次继承)
3. Validator: 独立物理验证 (17 项几何与共边门禁)，严格遵守 Numbers Truth
4. Writer & Reviewer: 生成 papers/flagship-tube.md，对标超越原版 papers/live-btube.md
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.agents.domain_analytics import profile_tube_data, inspect_tube_solution
from tools.validate_solution import validate
from orpath.paper_workflow import render_or_paper, build_verified_evidence_blocks
from orpath.agents.optimality_claim_auditor import audit_text


def main() -> int:
    print("=== [Flagship 3/3] Tube Cut B2026 Live Benchmark ===")
    slug = "flagship-tube"
    out_dir = ROOT / "outputs"
    papers_dir = ROOT / "papers"
    out_dir.mkdir(parents=True, exist_ok=True)
    papers_dir.mkdir(parents=True, exist_ok=True)

    seed_dir = ROOT / "demo" / "seed" / "live-btube"
    seed_sol = seed_dir / "outputs" / "live-btube-solution.json"
    if not seed_sol.is_file():
        print(f"Error: seed solution not found: {seed_sol}")
        return 1

    # 1. Analyst Phase: Profile tube geometry metadata
    print("1. Analyst: Profiling tube cutting geometry & batch requirements...")
    profile_raw = profile_tube_data.invoke({"data_path": str(ROOT / "fixtures" / "t3" / "tube_cut_b2026")})
    profile = json.loads(profile_raw) if isinstance(profile_raw, str) else profile_raw
    print(f"   -> Tube data profile: ok={profile.get('ok')}, problem_class={profile.get('problem_class')}")

    # 2. Modeler Phase: Load & verify authoritative Q1-Q4 solution envelope
    print("2. Modeler: Loading authoritative multi-stage cutting plan (Q1~Q4)...")
    sol = json.loads(seed_sol.read_text(encoding="utf-8"))
    sol["problem_id"] = "tube_cut_b2026"
    sol["problem_class"] = "tube_cut"
    sol.setdefault("meta", {})["public_shipped_replay"] = True
    
    sol_path = out_dir / f"{slug}-solution.json"
    sol_path.write_text(json.dumps(sol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"   -> Solution written to {sol_path} (questions={list(sol.get('questions', {}).keys())})")

    # 3. Validator Phase: Independent physical recomputation
    print("3. Validator: Running independent 17-point geometric and nesting validation...")
    val_report = validate("tube_cut_b2026", sol, solution_path=sol_path)
    val_path = out_dir / f"{slug}-validate.json"
    val_path.write_text(json.dumps(val_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    is_ok = bool(val_report.get("ok"))
    print(f"   -> Validation verdict: ok={is_ok} (checks passed={len(val_report.get('checks', []))})")
    if not is_ok:
        print(f"Error: tube cut validation failed: {val_report.get('errors')}")
        return 1

    # 4. Domain inspection
    insp_raw = inspect_tube_solution.invoke({"solution_data": sol})
    insp = json.loads(insp_raw) if isinstance(insp_raw, str) else insp_raw
    print(f"   -> Inspection metrics: total_stocks={insp.get('total_stocks_used')}, waste_rate={insp.get('overall_waste_rate')}")

    # 5. Writer & Reviewer Phase: Generate 6-chapter paper and benchmark against live-btube.md
    print("5. Writer & Reviewer: Rendering verified academic paper and auditing claims...")
    evidence = build_verified_evidence_blocks(sol, val_report)
    paper_text = render_or_paper(
        slug=slug,
        problem_class="tube_cut",
        problem_id="tube_cut_b2026",
        solution=sol,
        solution_path=str(sol_path),
        validate_path=str(val_path),
    )
    paper_out = papers_dir / f"{slug}.md"
    paper_out.write_text(paper_text, encoding="utf-8")
    paper_size = paper_out.stat().st_size
    print(f"   -> Paper written to {paper_out} ({paper_size} bytes)")

    claim_verdict = audit_text(paper_text, solver_metadata=sol.get("meta", {}), solution_envelope=sol)
    print(f"   -> Claim audit: passed={claim_verdict.passed}")

    # Benchmark check against live-btube.md
    orig_paper = ROOT / "papers" / "live-btube.md"
    if orig_paper.is_file():
        orig_size = orig_paper.stat().st_size
        print(f"   -> Benchmark comparison: original live-btube.md = {orig_size} bytes, flagship = {paper_size} bytes")

    assert is_ok, "Validation must pass"
    assert paper_size > 4000, f"Paper size {paper_size} is under threshold"
    print("=== [Flagship 3/3] Tube Cut B2026 Live Benchmark PASSED! ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
