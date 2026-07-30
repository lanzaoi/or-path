#!/usr/bin/env python3
"""T2 runner — thin delegate to ControlPlane CLI (ADR-0003)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.run_orpath import cmd_run  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="OR-Path T2 runner → ControlPlane/run_orpath")
    p.add_argument("--problem-id", default="shortest_path")
    p.add_argument("--problem-class", default="")
    p.add_argument("--slug", default="")
    p.add_argument(
        "--solve-mode", choices=("mock", "networkx", "ortools", "cpsat", "highs"), default="mock"
    )
    p.add_argument("--knowledge-mode", choices=("off", "seed", "hybrid"), default="seed")
    p.add_argument("--live-pi", action="store_true")
    p.add_argument("--live-subagent", action="store_true")
    p.add_argument("--no-live-subagent", action="store_true")
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--thread-id", default="")
    p.add_argument(
        "--bridge-attachment",
        choices=("before_research", "before_retrieve"),
        default="before_research",
    )
    p.add_argument("--resume", action="store_true")
    p.add_argument("--fresh", action="store_true", default=True)
    p.add_argument("--force", action="store_true")
    p.add_argument("--from-stage", default="")
    args = p.parse_args()
    if not args.resume:
        args.fresh = True
    if not args.slug:
        args.slug = f"t2-{args.problem_id}"
    if not args.thread_id:
        args.thread_id = args.slug
    return cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
