#!/usr/bin/env python3
"""Independent recompute plus deliberate tamper attacks for a Tube solution."""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from validate_solution import validate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Red-team a frozen Tube solution")
    parser.add_argument(
        "--solution",
        type=Path,
        default=ROOT / "outputs" / "tube_cut_b2026-solution.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "tube_cut_b2026-redteam.json",
    )
    args = parser.parse_args(argv)
    if not args.solution.is_file():
        print(f"FAIL: missing frozen solution {args.solution}", file=sys.stderr)
        return 1
    solution = json.loads(args.solution.read_text(encoding="utf-8"))
    problem_id = str(solution.get("problem_id") or "tube_cut_b2026")
    original = validate(problem_id, solution)
    attacks: list[tuple[str, dict]] = []

    changed = deepcopy(solution)
    changed["questions"]["q2"]["stocks"][0]["co_cut_benefit_mm"] += 1.0
    attacks.append(("numeric_cocut_inflation", changed))

    changed = deepcopy(solution)
    changed["questions"]["q3"]["stocks"][0]["sequence"].pop()
    attacks.append(("q3_demand_deletion", changed))

    changed = deepcopy(solution)
    q4_batches = changed["questions"]["q4"]["batches"]
    target = 1 if len(q4_batches) > 1 else 0
    q4_batches[target]["result"]["inventory_before"].append(
        {"id": "REDTEAM-FAKE", "length_mm": 999.0}
    )
    attacks.append(("q4_inventory_injection", changed))

    changed = deepcopy(solution)
    changed["questions"]["q4"]["optimality"]["lower_bound_mm"] = (
        float(changed["questions"]["q4"]["total_new_standard_stock_mm"]) + 1000.0
    )
    attacks.append(("invalid_lower_bound_claim", changed))

    changed = deepcopy(solution)
    hashes = changed.get("model_snapshot", {}).get("input_sha256", {})
    if hashes:
        first = next(iter(hashes))
        hashes[first] = "0" * 64
    attacks.append(("input_hash_tamper", changed))

    results = []
    for name, attacked in attacks:
        report = validate(problem_id, attacked)
        failed_names = [
            str(check.get("name"))
            for check in report.get("checks") or []
            if not check.get("ok")
        ]
        results.append(
            {
                "attack": name,
                "rejected": not bool(report.get("ok")),
                "failed_checks": failed_names,
            }
        )
    passed = bool(original.get("ok")) and all(row["rejected"] for row in results)
    payload = {
        "schema": "orpath.tube_redteam.v1",
        "problem_id": problem_id,
        "solution_path": str(args.solution.resolve()),
        "original_recompute_ok": bool(original.get("ok")),
        "original_check_count": len(original.get("checks") or []),
        "attacks": results,
        "ok": passed,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("PASS tube_redteam_gate" if passed else "FAIL tube_redteam_gate")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
