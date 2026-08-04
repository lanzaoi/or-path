#!/usr/bin/env python3
"""Schema gate: modeler JSON must not contain optima; class-specific shape."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema_models import FORBIDDEN_SCHEMA_KEYS, walk_forbidden_keys  # noqa: E402

# Prefer package registry when available (product install)
try:
    from orpath.domain_registry import (  # type: ignore
        POLYOMINO_SCHEMA_KEYS,
        is_polyomino_class,
        normalize_problem_class,
        schema_class_ok,
    )
except Exception:  # noqa: BLE001 — tools/ may run without package on path
    POLYOMINO_SCHEMA_KEYS = frozenset(
        {
            "board",
            "board_ref",
            "rows",
            "cols",
            "grid",
            "cells",
            "removed",
            "pieces",
            "piece_types",
            "piece_ids",
            "max_counts",
            "inventory",
            "allow_reflect",
            "max_uncovered",
            "task",
            "subproblems",
            "questions",
        }
    )

    def normalize_problem_class(raw: str | None) -> str:
        pc = (raw or "").strip().lower()
        aliases = {
            "polyomino": "polyomino_cover",
            "poly": "polyomino_cover",
            "polyomino_tiling": "polyomino_cover",
            "tiling_cover": "polyomino_cover",
            "tube": "tube_cut",
            "tube_bfd": "tube_cut",
            "cutting_stock": "tube_cut",
            "cut_stock": "tube_cut",
        }
        return aliases.get(pc, pc)

    def is_polyomino_class(raw: str | None) -> bool:
        return normalize_problem_class(raw) == "polyomino_cover"

    def schema_class_ok(raw: str | None) -> bool:
        pc = normalize_problem_class(raw)
        return pc in {
            "shortest_path",
            "tsp",
            "vrp",
            "tube_cut",
            "polyomino_cover",
        }


def check_schema(data: dict) -> list[str]:
    errors: list[str] = []
    bad = walk_forbidden_keys(data)
    for k in sorted(bad):
        if k in FORBIDDEN_SCHEMA_KEYS:
            errors.append(f"forbidden key present: {k}")

    top = {str(k).lower() for k in data.keys()}
    pc_raw = str(data.get("problem_class") or "")
    pc = normalize_problem_class(pc_raw)
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
    elif pc == "tube_cut":
        if not any(
            k in top
            for k in (
                "workpiece_specs",
                "workpieces",
                "stock",
                "stock_lengths",
                "batches",
                "geometry_preprocessing",
                "questions",
                "subproblems",
            )
        ):
            errors.append(
                "tube_cut/cutting_stock requires structural keys "
                "(workpiece_specs|stock|batches|geometry_preprocessing|…)"
            )
    elif is_polyomino_class(pc):
        # M2 phase 1: structural board/pieces only — no placements/objective (forbidden walk)
        if not any(k in top for k in POLYOMINO_SCHEMA_KEYS):
            errors.append(
                "polyomino_cover requires structural keys "
                "(board|board_ref|rows|cols|pieces|piece_types|…)"
            )
    elif not schema_class_ok(pc):
        errors.append(f"unknown problem_class: {pc_raw or pc}")

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
