#!/usr/bin/env python3
"""王牌真跑标杆二：智慧能源园区微电网调度 (Plan 5.3).

CUMCM 2026 Problem C 真实端到端全链路运行：
1. Analyst: 前置探针自动解析 inbox/cumcm2026_c/ 原始题面与 4 个 Excel 附件
2. Modeler: 调度 tools/solve_microgrid.py 完成日前计划与滚动时域 MPC 求解
3. Validator: 独立重算 SOC 上下界、充放电互斥与节点功率平衡 (26 项物理门禁)
4. Writer & Reviewer: 装配确定性证据块并生成竞赛论文 papers/cumcm2026_c.md
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

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from orpath.agents.domain_analytics import profile_microgrid_data, inspect_microgrid_solution
from tools.solve_microgrid import run_full_pipeline
from tools.validate_solution import validate
from orpath.paper_workflow import render_or_paper, build_verified_evidence_blocks
from orpath.agents.optimality_claim_auditor import audit_text


def main() -> int:
    print("=== [Flagship 2/3] CUMCM 2026 C Microgrid Live Benchmark ===")
    slug = "cumcm2026_c"
    out_dir = ROOT / "outputs"
    papers_dir = ROOT / "papers"
    out_dir.mkdir(parents=True, exist_ok=True)
    papers_dir.mkdir(parents=True, exist_ok=True)

    inbox_dir = ROOT / "inbox" / slug
    problem_file = inbox_dir / "problem.txt"
    if not problem_file.is_file():
        print(f"Error: problem file not found: {problem_file}")
        return 1

    # 1. Analyst Phase: Profile raw problem and attachments
    print(f"1. Analyst: Profiling raw problem and Excel attachments from {inbox_dir.name}...")
    profile_raw = profile_microgrid_data.invoke({"data_path": str(inbox_dir)})
    profile = json.loads(profile_raw) if isinstance(profile_raw, str) else profile_raw
    print(f"   -> Profiled attachments: {list(profile.get('attachments', {}).keys())}")
    print(f"   -> Summary keys: {list(profile.get('summary', {}).keys())}")

    # 2. Modeler Phase: Run microgrid solver (MILP + Receding Horizon MPC)
    print("2. Modeler: Executing tools/solve_microgrid.py (GLOP / Highs MPC)...")
    sol_path = out_dir / f"{slug}-solution.json"
    start_t = time.time()
    sol = run_full_pipeline(case_dir=inbox_dir, out_dir=out_dir)
    sol["problem_id"] = "microgrid_cumcm2026_c"
    sol["problem_class"] = "microgrid_dispatch"
    sol_path.write_text(json.dumps(sol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elapsed = time.time() - start_t
    print(f"   -> Solved in {elapsed:.2f}s, objective={sol.get('objective')} 元")
    print(f"   -> Solution written to {sol_path}")

    # 3. Validator Phase: Independent physical recomputation
    print("3. Validator: Independent recomputation of SOC, power balance & dispatch constraints...")
    val_report = validate("microgrid_cumcm2026_c", sol, solution_path=sol_path)
    val_path = out_dir / f"{slug}-validate.json"
    val_path.write_text(json.dumps(val_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    is_ok = bool(val_report.get("ok"))
    print(f"   -> Validation verdict: ok={is_ok} (checks passed={len(val_report.get('checks', []))})")
    if not is_ok:
        print(f"Error: microgrid validation failed: {val_report.get('errors')}")
        return 1

    # 4. Domain inspection
    insp_raw = inspect_microgrid_solution.invoke({"solution_data": sol})
    insp = json.loads(insp_raw) if isinstance(insp_raw, str) else insp_raw
    print(f"   -> Inspection metrics: subproblems={insp.get('subproblems_solved', [])}")

    # 5. Writer & Reviewer Phase: SOP 6-chapter paper generation
    print("5. Writer & Reviewer: Rendering verified academic paper and auditing claims...")
    evidence = build_verified_evidence_blocks(sol, val_report)
    paper_text = render_or_paper(
        slug=slug,
        problem_class="microgrid_dispatch",
        problem_id="microgrid_cumcm2026_c",
        solution=sol,
        solution_path=str(sol_path),
        validate_path=str(val_path),
    )
    paper_out = papers_dir / f"{slug}.md"
    paper_out.write_text(paper_text, encoding="utf-8")
    paper_size = paper_out.stat().st_size
    print(f"   -> Paper written to {paper_out} ({paper_size} bytes)")

    # Audit optimality claims
    claim_verdict = audit_text(paper_text, solver_metadata=sol.get("meta", {}), solution_envelope=sol)
    print(f"   -> Claim audit: passed={claim_verdict.passed}")

    assert is_ok, "Validation must pass"
    assert paper_size > 4000, f"Paper size {paper_size} is under threshold"
    print("=== [Flagship 2/3] CUMCM 2026 C Live Benchmark PASSED! ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
