#!/usr/bin/env python3
"""Run OR-Path T1 via ControlPlane.invoke_once (ADR-0001 + ADR-0003)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.control_plane import invoke_once, summarize_run  # noqa: E402


def main() -> int:
    os.environ["ORPATH_LIVE_SUBAGENT"] = "0"

    p = argparse.ArgumentParser(description="OR-Path T1 runner (ControlPlane)")
    p.add_argument("--problem", default="shortest_path")
    p.add_argument("--slug", default="t1-shortest-path")
    p.add_argument("--solve-mode", choices=("mock", "ortools", "networkx"), default="mock")
    p.add_argument("--knowledge-mode", choices=("off", "seed", "hybrid"), default="off")
    p.add_argument("--root", type=Path, default=ROOT)
    args = p.parse_args()
    root = args.root.resolve()

    final = invoke_once(
        root=root,
        slug=args.slug,
        problem_id=args.problem,
        problem_class="shortest_path",
        solve_mode=args.solve_mode,
        knowledge_mode=args.knowledge_mode,
        live_pi=False,
        live_subagent=False,
    )
    summary = summarize_run(final)
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
