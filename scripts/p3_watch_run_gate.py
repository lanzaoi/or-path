#!/usr/bin/env python3
"""P3 watch-run gate: one command starts face + mock run and L0 grows.

Exit 0 only if:
- orpath_watch_run.py / bat / menu wiring present
- watch-run --no-browser mock completes with stages_grew
- evidence JSON written
- does NOT require LIVE Pi
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def _py() -> str:
    cand = ROOT / ".venv-314" / "Scripts" / "python.exe"
    return str(cand) if cand.is_file() else sys.executable


def test_files() -> None:
    for rel in (
        "scripts/orpath_watch_run.py",
        "scripts/orpath_watch.py",
        "orpath/web/watch.html",
        "docs/v0-smoke.md",
        "orpath.bat",
        "scripts/orpath_menu.py",
    ):
        if not (ROOT / rel).is_file():
            _fail(f"missing {rel}")
    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    if "watch-run" not in bat and "watch_run" not in bat:
        _fail("orpath.bat missing watch-run")
    menu = (ROOT / "scripts/orpath_menu.py").read_text(encoding="utf-8", errors="replace")
    if "watch-run" not in menu and "边跑边看" not in menu:
        _fail("menu missing watch-run / 边跑边看")
    smoke = (ROOT / "docs/v0-smoke.md").read_text(encoding="utf-8", errors="replace")
    if "watch-run" not in smoke and "P3" not in smoke:
        _fail("docs/v0-smoke missing P3/watch-run")
    _ok("P3 files + wiring")


def test_watch_run_mock() -> None:
    slug = f"p3-gate-{int(time.time())}"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["ORPATH_LIVE_SUBAGENT"] = "0"
    env.setdefault("ORPATH_HOME", str(ROOT))
    env.setdefault("ORPATH_WORKDIR", str(ROOT))
    cmd = [
        _py(),
        str(ROOT / "scripts" / "orpath_watch_run.py"),
        "--slug",
        slug,
        "--thread-id",
        slug,
        "--no-browser",
        "--solve-mode",
        "mock",
        "--problem-id",
        "shortest_path",
        "--run-timeout",
        "180",
        "--grow-timeout",
        "120",
        # no --keep-watch → exit after run
    ]
    print(">>", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
    )
    print(proc.stdout[-3000:] if proc.stdout else "")
    if proc.returncode != 0:
        print(proc.stderr[-2000:] if proc.stderr else "")
        _fail(f"watch-run exit={proc.returncode}")
    ev_path = ROOT / "outputs" / f"{slug}-watch-run.json"
    if not ev_path.is_file():
        _fail(f"missing evidence {ev_path}")
    ev = json.loads(ev_path.read_text(encoding="utf-8"))
    if not ev.get("ok"):
        _fail(f"evidence ok=false notes={ev.get('notes')}")
    if not ev.get("stages_grew"):
        _fail(f"stages did not grow: {ev.get('stages_before')}→{ev.get('stages_after')}")
    if int(ev.get("stages_after") or 0) <= int(ev.get("stages_before") or 0):
        _fail("stages_after not greater")
    # this slug is the evidence — not historical test alone
    if ev.get("slug") != slug:
        _fail("slug mismatch")
    stages_dir = ROOT / "runs" / slug / "stages"
    if not stages_dir.is_dir() or not any(stages_dir.glob("*.json")):
        _fail("runs/<slug>/stages empty")
    _ok(
        f"watch-run mock slug={slug} stages "
        f"{ev.get('stages_before')}→{ev.get('stages_after')} url={ev.get('url')}"
    )


def main() -> int:
    print("=== p3_watch_run_gate ===")
    print("ROOT =", ROOT)
    test_files()
    test_watch_run_mock()
    print("PASS p3_watch_run_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
