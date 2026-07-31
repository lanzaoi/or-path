#!/usr/bin/env python3
"""CLI: intake from inbox/ only (OCR+parse, no full graph)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.intake_discover import discover_inbox_sources  # noqa: E402
from orpath.intake_nodes import standalone_intake  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="OR-Path intake from inbox/")
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--slug", required=True)
    p.add_argument("--assets", default="", dest="intake_assets")
    args = p.parse_args()
    root = args.root.resolve()
    sources = discover_inbox_sources(root)
    if not sources:
        print(json.dumps({"ok": False, "error": "inbox_empty", "inbox": str(root / "inbox")}))
        return 2
    assets = Path(args.intake_assets) if args.intake_assets else None
    if assets and not assets.is_absolute():
        assets = root / assets
    result = standalone_intake(
        root=root,
        slug=args.slug,
        sources=[Path(s) for s in sources],
        assets_dir=assets if assets and str(assets) else None,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
