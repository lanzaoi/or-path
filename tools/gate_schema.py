#!/usr/bin/env python3
"""Schema gate: modeler JSON must not contain optima; must describe the problem."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Keys that imply the modeler invented or leaked solver results
FORBIDDEN_KEYS = {
    "objective",
    "optimal",
    "objective_value",
    "optima",
    "optimal_value",
    "optimal_cost",
}


def _walk_keys(obj: Any, found: set[str] | None = None) -> set[str]:
    if found is None:
        found = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(str(k).lower())
            _walk_keys(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _walk_keys(item, found)
    return found


def check_schema(data: dict) -> list[str]:
    """Return list of error messages (empty = pass)."""
    errors: list[str] = []
    keys = _walk_keys(data)
    for bad in FORBIDDEN_KEYS:
        if bad in keys:
            errors.append(f"forbidden key present: {bad}")
    # Require problem_class or nodes (graph structure / class marker)
    top = {str(k).lower() for k in data.keys()}
    if "problem_class" not in top and "nodes" not in top:
        errors.append("require problem_class or nodes")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OR-Path modeler schema gate")
    parser.add_argument("schema_path", type=Path, help="Path to modeler schema JSON")
    args = parser.parse_args(argv)
    path: Path = args.schema_path
    if not path.is_file():
        print(f"FAIL: file not found: {path}", file=sys.stderr)
        return 1
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"FAIL: invalid JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print("FAIL: schema root must be object", file=sys.stderr)
        return 1
    errors = check_schema(data)
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print("PASS: schema gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
