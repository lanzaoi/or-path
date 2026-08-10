#!/usr/bin/env python3
"""Full TSPLIB Benchmark Runner for OR-Path.

Runs solve_dispatch -> validate_solution on all 8 TSPLIB instances,
computes gap vs published optimal, and generates:
  - eval_or_bench/results/summary.json
  - eval_or_bench/results/summary.md
"""

import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
_RESULTS_DIR = _THIS_DIR / "results"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from eval_or_bench.tsplib_converter import KNOWN_OPTIMAL_REFS
from tools.solve_dispatch import solve
from tools.validate_solution import validate

INSTANCES = [
    "burma14", "ulysses16", "gr17", "bayg29",
    "swiss42", "att48", "eil51", "kroA100",
]


def run_benchmark():
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    total_pass = 0
    total_fail = 0
    total_optimal = 0

    print("=" * 70)
    print("OR-Path TSPLIB Benchmark — Full Evaluation Run")
    print(f"Timestamp: {datetime.now(timezone(timedelta(hours=8))).isoformat()}")
    print("=" * 70)

    for inst in INSTANCES:
        ref = KNOWN_OPTIMAL_REFS[inst]
        mode = "cpsat" if ref["dimension"] <= 20 else "ortools"

        print(f"\n[{inst}] N={ref['dimension']} metric={ref['edge_weight_type']} mode={mode} ...")

        t0 = time.perf_counter()
        try:
            ok, sol, raw = solve(_REPO_ROOT, inst, mode=mode, problem_class="tsp")
        except Exception as e:
            ok = False
            sol = {}
            raw = str(e)
        elapsed = time.perf_counter() - t0

        if not ok:
            print(f"  [SOLVE FAILED] {raw}")
            results.append({
                "instance": inst,
                "dimension": ref["dimension"],
                "edge_weight_type": ref["edge_weight_type"],
                "solver_mode": mode,
                "status": "SOLVE_ERROR",
                "objective": None,
                "optimal_value": ref["optimal_value"],
                "reference_type": ref["reference_type"],
                "gap_pct": None,
                "validate_ok": False,
                "elapsed_s": round(elapsed, 3),
                "error": raw[:500],
            })
            total_fail += 1
            continue

        sol_obj = float(sol.get("objective", 0))
        sol_status = sol.get("status", "UNKNOWN")

        # Validate
        try:
            val_report = validate(inst, sol)
            val_ok = val_report.get("ok", False)
        except Exception as e:
            val_ok = False
            val_report = {"error": str(e)}

        opt_val = ref["optimal_value"]
        gap_pct = round((sol_obj - opt_val) / opt_val * 100.0, 2) if opt_val > 0 else None
        is_optimal = abs(sol_obj - opt_val) < 1e-5

        if is_optimal:
            total_optimal += 1

        entry = {
            "instance": inst,
            "dimension": ref["dimension"],
            "edge_weight_type": ref["edge_weight_type"],
            "solver_mode": mode,
            "status": sol_status,
            "objective": sol_obj,
            "optimal_value": opt_val,
            "reference_type": ref["reference_type"],
            "gap_pct": gap_pct,
            "validate_ok": val_ok,
            "elapsed_s": round(elapsed, 3),
            "citation": ref.get("citation", ""),
        }
        results.append(entry)

        if val_ok:
            total_pass += 1
            marker = "✅ OPTIMAL" if is_optimal else f"gap={gap_pct}%"
            print(f"  [PASS] obj={sol_obj} optimal={opt_val} {marker} ({elapsed:.2f}s)")
        else:
            total_fail += 1
            print(f"  [FAIL] validate_ok=False report={val_report}")

    # Summary stats
    summary = {
        "benchmark_suite": "TSPLIB",
        "run_timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "total_instances": len(INSTANCES),
        "total_pass": total_pass,
        "total_fail": total_fail,
        "total_exact_optimal": total_optimal,
        "gap_definition": "(solver_objective - published_optimal) / published_optimal * 100%",
        "claim_ladder": {
            "optimal": "Solver reported OPTIMAL and objective matches published value exactly",
            "feasible_near_optimal": "Solver reported FEASIBLE, gap < 5%",
            "feasible": "Solver reported FEASIBLE, validate_ok=true",
            "failed": "Solve or validate error",
        },
        "not_tested": [
            "LIVE Multi-Agent pipeline (run_orpath.py)",
            "Watch process visibility UI",
            "Paper generation chain",
            "Polyomino / Cutting Stock problem classes",
        ],
        "results": results,
    }

    # Write JSON
    json_path = _RESULTS_DIR / "summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n→ summary.json written to: {json_path}")

    # Write Markdown
    md_path = _RESULTS_DIR / "summary.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# OR-Path TSPLIB Benchmark Results\n\n")
        f.write(f"**Suite:** TSPLIB  \n")
        f.write(f"**Run:** {summary['run_timestamp']}  \n")
        f.write(f"**Pass:** {total_pass}/{len(INSTANCES)}  |  ")
        f.write(f"**Exact Optimal:** {total_optimal}/{len(INSTANCES)}  |  ")
        f.write(f"**Fail:** {total_fail}/{len(INSTANCES)}\n\n")
        f.write("## Gap Definition\n\n")
        f.write("`gap = (solver_obj - optimal) / optimal × 100%`\n\n")
        f.write("## Results Table\n\n")
        f.write("| Instance | N | Metric | Mode | Status | Objective | Optimal | Gap (%) | Validate | Time (s) |\n")
        f.write("| :--- | ---: | :--- | :--- | :--- | ---: | ---: | ---: | :--- | ---: |\n")
        for r in results:
            obj_str = str(int(r["objective"])) if r["objective"] else "—"
            gap_str = f"{r['gap_pct']:.2f}" if r["gap_pct"] is not None else "—"
            val_str = "✅" if r["validate_ok"] else "❌"
            status_str = r["status"]
            if r["gap_pct"] is not None and r["gap_pct"] == 0.0:
                status_str += " 🏆"
            f.write(f"| {r['instance']} | {r['dimension']} | {r['edge_weight_type']} | "
                    f"{r['solver_mode']} | {status_str} | {obj_str} | {r['optimal_value']} | "
                    f"{gap_str} | {val_str} | {r['elapsed_s']} |\n")

        f.write("\n## Claim Ladder\n\n")
        for k, v in summary["claim_ladder"].items():
            f.write(f"- **{k}**: {v}\n")

        f.write("\n## Not Tested (Out of Scope)\n\n")
        for item in summary["not_tested"]:
            f.write(f"- {item}\n")

        f.write("\n## References\n\n")
        for r in results:
            cite = r.get("citation", "")
            if cite:
                f.write(f"- **{r['instance']}**: {cite}\n")

        f.write("\n---\n")
        f.write("*Generated by `eval_or_bench/run_full_benchmark.py` — numbers from `solve_dispatch` + `validate_solution` recomputation.*\n")

    print(f"→ summary.md written to: {md_path}")

    print("\n" + "=" * 70)
    print(f"FINAL: {total_pass}/{len(INSTANCES)} PASS | {total_optimal} exact optimal | {total_fail} fail")
    print("=" * 70)

    return total_fail == 0


if __name__ == "__main__":
    success = run_benchmark()
    sys.exit(0 if success else 1)
