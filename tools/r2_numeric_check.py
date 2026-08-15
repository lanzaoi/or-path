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
ARXIV_ID_RE = re.compile(r"\b(\d{4}\.\d{4,5})(v\d+)?\b")
DOI_NUM_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.I)
OBJECTIVE_CLAIM_RE = re.compile(
    r"(?i)(?:objective|optimal(?:\s+cost)?|total\s+cost|shortest\s+(?:path\s+)?cost|"
    r"最短路(?:径)?(?:代价|费用|长度|成本)?|目标值|最优(?:值|代价|费用)?)"
    r"\s*[:=是为]?\s*"
    r"([+-]?(?:\d+\.\d+|\d+))"
)
BIG_NUM_RE = re.compile(r"(?<![A-Za-z0-9_/])([+-]?(?:\d+\.\d+|\d{2,}))(?![A-Za-z0-9_])")
# Process/meta counters in paper verification logs must not bind as result numerics.
# e.g. "claims_recorded: 309" is claim-map size, not a stock length.
META_COUNTER_RE = re.compile(
    r"(?im)^[^\n]*\b("
    r"claims_recorded|claim_count|claims?\s+recorded|"
    r"lead_events|sub_events|tool_count|event_count|event_kinds|"
    r"duration_ms|log_size|log_truncated|children_count|subagent_dispatches|"
    r"stage_seq|revise_count|schema_repair|validate_repair|solver_tune|"
    r"labelIndex|prev_events|n_stages"
    r")\b[^\n]*$"
)
# Paths are provenance, not result claims. This also prevents a numeric Windows
# username or temporary directory name from becoming a false result number.
PATH_TOKEN_RE = re.compile(
    r"(?i)(?:[A-Z]:[\\/][^\s`'\"<>|]+|(?:\.\.?[\\/]|[A-Za-z0-9_.-]+[\\/])[^\s`'\"<>|]+)"
)


def mask_non_result_numbers(text: str) -> str:
    """Blank arxiv/doi and process-meta lines before numeric binding scans."""
    masked = ARXIV_ID_RE.sub(" ARXIV ", text or "")
    masked = DOI_NUM_RE.sub(" DOI ", masked)
    masked = PATH_TOKEN_RE.sub(" PATH ", masked)
    masked = META_COUNTER_RE.sub(" META_COUNTER_LINE ", masked)
    # also inline "claims_recorded: 309" mid-line
    masked = re.sub(
        r"(?i)\b(claims_recorded|claim_count)\s*[:=]\s*\d+\b",
        r"\1=N",
        masked,
    )
    return masked


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
    for i in range(0, 21):
        allowed.add(str(i))
    errors: list[str] = []

    masked = mask_non_result_numbers(draft)

    for m in OBJECTIVE_CLAIM_RE.finditer(masked):
        claim = m.group(1).lstrip("+")
        try:
            f = float(claim)
        except ValueError:
            errors.append(f"objective-like claim not in solution: {claim}")
            continue
        if claim not in allowed and not _allowed_float(allowed, f):
            errors.append(f"objective-like claim not in solution: {claim}")

    years = set(YEAR_RE.findall(masked))
    for m in BIG_NUM_RE.finditer(masked):
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
