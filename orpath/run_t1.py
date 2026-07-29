#!/usr/bin/env python3
"""Run OR-Path T1 LangGraph pipeline (deterministic node bodies + real gates/tools)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.graph import build_graph  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="OR-Path T1 runner")
    p.add_argument("--problem", default="shortest_path")
    p.add_argument("--slug", default="t1-shortest-path")
    p.add_argument("--solve-mode", choices=("mock", "ortools"), default="mock")
    p.add_argument("--root", type=Path, default=ROOT)
    args = p.parse_args()
    root = args.root.resolve()

    initial = {
        "slug": args.slug,
        "problem_id": args.problem,
        "solve_mode": args.solve_mode,
        "root": str(root),
        "stage": "start",
        "revise_count": 0,
        "max_revise": 2,
        "human_required": False,
        "schema_path": "",
        "solution_path": "",
        "research_path": "",
        "explain_path": "",
        "paper_path": "",
        "review_path": "",
        "provenance_path": "",
        "plan_path": "",
        "cited_path": "",
        "last_error": "",
        "gate_schema_ok": False,
        "gate_r1_ok": False,
        "gate_r2_ok": False,
        "review_fatal": 0,
    }
    app = build_graph()
    final = app.invoke(initial)
    summary = {
        "stage": final.get("stage"),
        "human_required": final.get("human_required"),
        "revise_count": final.get("revise_count"),
        "gate_r1_ok": final.get("gate_r1_ok"),
        "gate_r2_ok": final.get("gate_r2_ok"),
        "solution_path": final.get("solution_path"),
        "paper_path": final.get("paper_path"),
        "provenance_path": final.get("provenance_path"),
        "last_error": final.get("last_error"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if final.get("human_required"):
        return 2
    if not final.get("provenance_path"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
