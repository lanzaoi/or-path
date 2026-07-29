#!/usr/bin/env python3
"""Run OR-Path T1 via product graph (ADR-0001). Deterministic, no live subagent."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.graph_product import build_graph_product  # noqa: E402


def main() -> int:
    # T1 smoke is always deterministic
    os.environ["ORPATH_LIVE_SUBAGENT"] = "0"

    p = argparse.ArgumentParser(description="OR-Path T1 runner (product graph)")
    p.add_argument("--problem", default="shortest_path")
    p.add_argument("--slug", default="t1-shortest-path")
    p.add_argument("--solve-mode", choices=("mock", "ortools", "networkx"), default="mock")
    p.add_argument("--knowledge-mode", choices=("off", "seed", "hybrid"), default="off")
    p.add_argument("--root", type=Path, default=ROOT)
    args = p.parse_args()
    root = args.root.resolve()
    thread_id = f"t1-{args.slug}-{uuid.uuid4().hex[:8]}"

    initial = {
        "slug": args.slug,
        "problem_id": args.problem,
        "problem_class": "shortest_path",
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
        "gate_claim_ok": True,
        "gate_subagent_ok": None,
        "review_fatal": 0,
        "live_pi": False,
        "live_subagent": False,
        "thread_id": thread_id,
        "bridge_attachment": "before_research",
        "bridge_path": "",
        "bridge_ok": False,
        "bridge_skipped": True,
        "orpath_checkpoint_id": "",
        "runs_dir": str(root / "runs" / thread_id),
        "artifact_manifest_path": "",
        "last_snapshot_path": "",
        "pipeline": "product",
    }
    app = build_graph_product(checkpointer=None)
    final = app.invoke(initial)
    summary = {
        "stage": final.get("stage"),
        "human_required": final.get("human_required"),
        "revise_count": final.get("revise_count"),
        "gate_r1_ok": final.get("gate_r1_ok"),
        "gate_r2_ok": final.get("gate_r2_ok"),
        "gate_validate_ok": final.get("gate_validate_ok"),
        "solution_path": final.get("solution_path"),
        "paper_path": final.get("paper_path"),
        "provenance_path": final.get("provenance_path"),
        "last_error": final.get("last_error"),
        "pipeline": "product",
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
