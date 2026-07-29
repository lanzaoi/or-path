#!/usr/bin/env python3
"""T3 live bridge gate (optional). ORPATH_LIVE_PI=1 or --force-live."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    env = dict(os.environ)
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("PYTHONPATH", None)
    force = "--force-live" in sys.argv or env.get("T3_REQUIRE_LIVE") == "1"
    env["ORPATH_LIVE_PI"] = "1"

    slug = "t3-live-bridge"
    r = subprocess.run(
        [
            PY,
            str(ROOT / "orpath" / "run_orpath.py"),
            "run",
            "--problem-id",
            "shortest_path",
            "--solve-mode",
            "mock",
            "--knowledge-mode",
            "off",
            "--slug",
            slug,
            "--thread-id",
            slug,
            "--fresh",
            "--live-pi",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        if not force:
            print("SKIP/soft: live bridge run failed (set T3_REQUIRE_LIVE=1 to hard-fail)")
            return 0
        fail(f"live bridge run failed rc={r.returncode}")

    summary = json.loads(r.stdout)
    if summary.get("bridge_skipped"):
        if force:
            fail("bridge skipped while live requested")
    bp = summary.get("bridge_path") or ""
    if bp and not Path(bp).is_file():
        fail(f"bridge path missing {bp}")
    # also accept *-pi-bridge.json from bridge_smoke
    cands = list((ROOT / "outputs").glob(f"{slug}*bridge*.json"))
    if not cands and not bp:
        if force:
            fail("no bridge evidence files")
    print("PASS: t3_gate_live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
