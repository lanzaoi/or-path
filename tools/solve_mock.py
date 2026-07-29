#!/usr/bin/env python3
"""Load fixture solution.json (t2 then t1) and print JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_paths import fixture_file  # noqa: E402


def load_solution(problem_id: str) -> dict:
    path = fixture_file(problem_id, "solution.json")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("solution.json must be a JSON object")
    # normalize class
    if "problem_class" not in data:
        if data.get("path"):
            data["problem_class"] = "shortest_path"
        elif data.get("tour"):
            data["problem_class"] = "tsp"
        elif data.get("routes"):
            data["problem_class"] = "vrp"
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OR-Path mock solver (fixture JSON)")
    parser.add_argument("problem_id", help="Fixture id under fixtures/t1|t2/<id>/")
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
