#!/usr/bin/env python3
"""Schema gate: modeler JSON must not contain optima; class-specific shape."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema_models import FORBIDDEN_SCHEMA_KEYS, walk_forbidden_keys  # noqa: E402


def check_schema(data: dict) -> list[str]:
    errors: list[str] = []
    bad = walk_forbidden_keys(data)
    for k in sorted(bad):
        if k in FORBIDDEN_SCHEMA_KEYS:
            errors.append(f"forbidden key present: {k}")

    top = {str(k).lower() for k in data.keys()}
    pc = str(data.get("problem_class") or "").lower()
    if not pc:
        if "nodes" in top or "edges" in top or "edges_ref" in top:
            pc = "shortest_path"
        else:
            errors.append("require problem_class")
            return errors

    if pc == "shortest_path":
        if "nodes" not in top and "edges_ref" not in top and "edges" not in top:
            errors.append("shortest_path requires nodes/edges/edges_ref")
    elif pc == "tsp":
        if "distance_matrix" not in top and "coords" not in top:
            errors.append("tsp requires distance_matrix or coords")
    elif pc == "vrp":
        vc = data.get("vehicle_count")
        if vc is None or int(vc) < 2:
            errors.append("vrp requires vehicle_count >= 2")
        if "capacities" not in top:
            errors.append("vrp requires capacities")
        if "demands" not in top:
            errors.append("vrp requires demands")
    else:
        errors.append(f"unknown problem_class: {pc}")

    if "problem_id" not in top:
        errors.append("require problem_id")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OR-Path modeler schema gate")
    parser.add_argument("schema_path", type=Path)
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
