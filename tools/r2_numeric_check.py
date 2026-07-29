#!/usr/bin/env python3
"""R2: objective-like claims and large result numerics must ⊆ solution.json."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

YEAR_RE = re.compile(r"\b(20\d{2})\b")
OBJECTIVE_CLAIM_RE = re.compile(
    r"(?i)(?:objective|optimal(?:\s+cost)?|total\s+cost|shortest\s+(?:path\s+)?cost|"
    r"最短路(?:径)?(?:代价|费用|长度|成本)?|目标值|最优(?:值|代价|费用)?)"
    r"\s*[:=是为]?\s*"
    r"([+-]?(?:\d+\.\d+|\d+))"
)
# Result-sized numbers outside tiny counters / table indices
BIG_NUM_RE = re.compile(r"(?<![A-Za-z0-9_/])([+-]?(?:\d+\.\d+|\d{2,}))(?![A-Za-z0-9_])")


def _collect_solution_tokens(obj: Any, out: set[str]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _collect_solution_tokens(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_solution_tokens(v, out)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, int):
        out.add(str(obj))
    elif isinstance(obj, float):
        if obj.is_integer():
            out.add(str(int(obj)))
        out.add(str(obj))
    elif isinstance(obj, str):
        out.add(obj)
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", obj):
            out.add(obj.lstrip("+"))


def _allowed_float(allowed: set[str], f: float) -> bool:
    for a in allowed:
        if re.fullmatch(r"[+-]?(?:\d+\.\d+|\d+)", a):
            try:
                if abs(float(a) - f) < 1e-9:
                    return True
            except ValueError:
                continue
    return False


def check_draft(draft: str, solution: dict) -> list[str]:
    allowed: set[str] = set()
    _collect_solution_tokens(solution, allowed)
    # path letters already; tiny counters 0-20 always ok for markdown lists/tables
    for i in range(0, 21):
        allowed.add(str(i))
    errors: list[str] = []

    for m in OBJECTIVE_CLAIM_RE.finditer(draft):
        claim = m.group(1).lstrip("+")
        try:
            f = float(claim)
        except ValueError:
            errors.append(f"objective-like claim not in solution: {claim}")
            continue
        if claim not in allowed and not _allowed_float(allowed, f):
            errors.append(f"objective-like claim not in solution: {claim}")

    years = set(YEAR_RE.findall(draft))
    for m in BIG_NUM_RE.finditer(draft):
        token = m.group(1).lstrip("+")
        if token in years:
            continue
        if token in allowed:
            continue
        try:
            f = float(token)
        except ValueError:
            continue
        if f <= 20:
            continue
        if _allowed_float(allowed, f):
            continue
        # ignore pure path drive noise like nothing; flag result-scale extras
        errors.append(f"numeric claim not in solution: {token}")

    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OR-Path R2 numeric check")
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--solution", type=Path, required=True)
    args = parser.parse_args(argv)

    if not args.draft.is_file():
        print(f"FAIL: draft not found: {args.draft}", file=sys.stderr)
        return 1
    if not args.solution.is_file():
        print(f"FAIL: solution not found: {args.solution}", file=sys.stderr)
        return 1

    draft = args.draft.read_text(encoding="utf-8")
    solution = json.loads(args.solution.read_text(encoding="utf-8"))
    if not isinstance(solution, dict):
        print("FAIL: solution must be object", file=sys.stderr)
        return 1

    errors = check_draft(draft, solution)
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print("PASS: R2 numeric check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
