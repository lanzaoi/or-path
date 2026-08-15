#!/usr/bin/env python3
"""Offline, reproducible CVRPLIB A-n32-k5 solve/validate/reference baseline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from solve_dispatch import solve, validate  # noqa: E402

PROBLEM_ID = "cvrplib_a_n32_k5"
FIXTURE = ROOT / "fixtures" / "t3" / PROBLEM_ID
REFERENCE = FIXTURE / "reference_solution.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the public CVRPLIB CVRP baseline")
    parser.add_argument("--time-limit-ms", type=int, default=5000)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs")
    args = parser.parse_args(argv)

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    solution_path = out_dir / f"{PROBLEM_ID}-solution.json"
    validate_path = out_dir / f"{PROBLEM_ID}-validate.json"
    ref_validate_path = out_dir / f"{PROBLEM_ID}-reference-validate.json"
    report_path = out_dir / f"{PROBLEM_ID}-baseline.json"

    ok, solution, raw = solve(
        ROOT,
        PROBLEM_ID,
        "ortools",
        "vrp",
        ["--time-limit-ms", str(args.time_limit_ms)],
    )
    if not ok:
        print(raw, file=sys.stderr)
        return 1
    solution_path.write_text(
        json.dumps(solution, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    candidate_ok, candidate_validation, _ = validate(
        ROOT, PROBLEM_ID, solution_path, validate_path
    )
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    reference_ok, reference_validation, _ = validate(
        ROOT, PROBLEM_ID, REFERENCE, ref_validate_path
    )

    candidate_objective = float(solution["objective"])
    reference_objective = float(reference["objective"])
    gap_percent = 100.0 * (candidate_objective - reference_objective) / reference_objective
    checks = {
        "candidate_solved": ok,
        "candidate_validated": candidate_ok and bool(candidate_validation.get("ok")),
        "reference_validated": reference_ok and bool(reference_validation.get("ok")),
        "reference_objective_is_784": reference_objective == 784.0,
        "candidate_not_below_proven_reference": candidate_objective >= reference_objective,
        "candidate_status_honest": str(solution.get("status")).upper() == "FEASIBLE"
        and solution.get("meta", {}).get("proven_optimal") is False,
    }
    report = {
        "ok": all(checks.values()),
        "problem_id": PROBLEM_ID,
        "instance": "A-n32-k5",
        "candidate_objective": solution["objective"],
        "reference_objective": reference["objective"],
        "gap_percent": round(gap_percent, 6),
        "time_limit_ms": args.time_limit_ms,
        "checks": checks,
        "artifacts": {
            "solution": str(solution_path),
            "validate": str(validate_path),
            "reference_validate": str(ref_validate_path),
        },
        "sources": [
            "https://galgos.inf.puc-rio.br/cvrplib/en/download/instance/4",
            "https://galgos.inf.puc-rio.br/cvrplib/en/download/bks/4",
        ],
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
