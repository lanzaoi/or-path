#!/usr/bin/env python3
"""Thin CLI for tube-cut through the authoritative solve dispatch (ADR-0002)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "tools"))
    from solve_dispatch import solve, validate  # noqa: E402

    argv = list(argv if argv is not None else sys.argv[1:])
    ok, data, raw = solve(
        ROOT,
        "tube_cut_b2026",
        "tube",
        problem_class="tube_cut",
        extra_args=argv or None,
    )
    if not ok:
        print(raw or json.dumps(data, ensure_ascii=False), file=sys.stderr)
        return 1
    if data.get("status") == "BLOCKED":
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    out_dir = ROOT / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    solution_path = out_dir / "tube_cut_b2026-solution.json"
    validate_path = out_dir / "tube_cut_b2026-validate.json"
    solution_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    valid, report, validation_raw = validate(
        ROOT, "tube_cut_b2026", solution_path, validate_path
    )
    if not valid:
        print(validation_raw or json.dumps(report, ensure_ascii=False), file=sys.stderr)
        return 1
    data["validation"] = {
        "ok": True,
        "solution_path": str(solution_path),
        "validate_path": str(validate_path),
    }
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
