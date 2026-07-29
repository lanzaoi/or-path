#!/usr/bin/env python3
"""Gate research notes: evidence table + coverage + retrieval id consumption (P1-4)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# allow running as script
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orpath.paper_workflow import gate_research_text, load_retrieval  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="OR-Path research evidence gate")
    p.add_argument("--research", type=Path, required=True)
    p.add_argument("--retrieval", type=Path, default=None)
    p.add_argument("--knowledge-mode", default="seed")
    args = p.parse_args(argv)

    if not args.research.is_file():
        print(f"FAIL: research not found: {args.research}", file=sys.stderr)
        return 1
    text = args.research.read_text(encoding="utf-8")
    retrieval = load_retrieval(args.retrieval) if args.retrieval else {}
    if args.retrieval and args.retrieval.is_file() and not retrieval:
        try:
            retrieval = json.loads(args.retrieval.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("FAIL: retrieval JSON invalid", file=sys.stderr)
            return 1

    ok, errors = gate_research_text(
        text, knowledge_mode=args.knowledge_mode, retrieval=retrieval
    )
    if not ok:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print("PASS: research evidence gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
