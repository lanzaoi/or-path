#!/usr/bin/env python3
"""Run OR-Path T2 LangGraph pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.graph_t2 import build_graph_t2  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="OR-Path T2 runner")
    p.add_argument("--problem-id", default="shortest_path")
    p.add_argument("--problem-class", default="")
    p.add_argument("--slug", default="")
    p.add_argument(
        "--solve-mode", choices=("mock", "networkx", "ortools"), default="mock"
    )
    p.add_argument(
        "--knowledge-mode", choices=("off", "seed", "hybrid"), default="seed"
    )
    p.add_argument("--live-pi", action="store_true")
    p.add_argument("--root", type=Path, default=ROOT)
    args = p.parse_args()
    root = args.root.resolve()
    slug = args.slug or f"t2-{args.problem_id}"

    initial = {
        "slug": slug,
        "problem_id": args.problem_id,
        "problem_class": args.problem_class,
        "solve_mode": args.solve_mode,
        "knowledge_mode": args.knowledge_mode,
        "root": str(root),
        "stage": "start",
        "revise_count": 0,
        "max_revise": 2,
        "schema_repair": 0,
        "max_schema_repair": 2,
        "validate_repair": 0,
        "max_validate_repair": 2,
        "solver_tune": 0,
        "max_solver_tune": 3,
        "human_required": False,
        "schema_path": "",
        "solution_path": "",
        "validate_path": "",
        "research_path": "",
        "retrieval_path": "",
        "explain_path": "",
        "paper_path": "",
        "review_path": "",
        "provenance_path": "",
        "plan_path": "",
        "cited_path": "",
        "last_error": "",
        "gate_schema_ok": False,
        "gate_validate_ok": False,
        "gate_r1_ok": False,
        "gate_r2_ok": False,
        "review_fatal": 0,
        "live_pi": bool(args.live_pi),
    }

    if args.live_pi:
        try:
            from orpath.pi_bridge import maybe_annotate_live

            maybe_annotate_live(root, slug)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"bridge_error": str(exc)}), file=sys.stderr)

    app = build_graph_t2()
    final = app.invoke(initial)
    summary = {
        "stage": final.get("stage"),
        "human_required": final.get("human_required"),
        "problem_class": final.get("problem_class"),
        "solve_mode": args.solve_mode,
        "gate_validate_ok": final.get("gate_validate_ok"),
        "gate_r1_ok": final.get("gate_r1_ok"),
        "gate_r2_ok": final.get("gate_r2_ok"),
        "solution_path": final.get("solution_path"),
        "validate_path": final.get("validate_path"),
        "paper_path": final.get("paper_path"),
        "provenance_path": final.get("provenance_path"),
        "last_error": final.get("last_error"),
        "solver_tune": final.get("solver_tune"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if final.get("human_required"):
        return 2
    if not final.get("provenance_path"):
        return 1
    if not final.get("gate_validate_ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
