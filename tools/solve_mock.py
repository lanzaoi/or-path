#!/usr/bin/env python3
"""Load fixture solution.json for a problem_id and print JSON to stdout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_solution(problem_id: str) -> dict:
    path = ROOT / "fixtures" / "t1" / problem_id / "solution.json"
    if not path.is_file():
        raise FileNotFoundError(f"solution not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("solution.json must be a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OR-Path mock solver (fixture JSON)")
    parser.add_argument("problem_id", help="Fixture id under fixtures/t1/<id>/")
    args = parser.parse_args(argv)
    try:
        data = load_solution(args.problem_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
