#!/usr/bin/env python3
"""P5 polish gate: Watch UX markers + tier3 surface + docs closeout.

Does not require Langfuse cloud or screen recording files.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def test_files() -> None:
    for rel in (
        "orpath/web/watch.html",
        "orpath/watch_snapshot.py",
        "docs/p5-closeout.md",
        "docs/p5-tier3-langfuse.md",
        "docs/v0-smoke.md",
        "orpath.bat",
    ):
        if not (ROOT / rel).is_file():
            _fail(f"missing {rel}")
    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    if "p5-gate" not in bat and "p5_polish" not in bat:
        _fail("orpath.bat missing p5-gate")
    _ok("files present")


def test_html_polish() -> None:
    html = (ROOT / "orpath/web/watch.html").read_text(encoding="utf-8", errors="replace")
    for n in (
        "swim",
        "Follow tail",
        "Pause",
        "errBanner",
        "EVENT_WINDOW",
        "tier3",
        "ORPATH_LANGFUSE",
        "pulse",
        "Demo checklist",
        "P5",
    ):
        if n not in html:
            _fail(f"watch.html missing {n}")
    # mobile
    if "max-width: 900px" not in html and "100dvh" not in html:
        _fail("mobile styles weak")
    _ok("HTML P5 polish markers")


def test_snapshot_tier3() -> None:
    os.environ["ORPATH_LANGFUSE"] = "0"
    from orpath.watch_snapshot import build_snapshot

    snap = build_snapshot(slug="test", thread_id="test", workdir=ROOT, root=ROOT)
    t3 = snap.get("tier3") or {}
    if "enabled" not in t3:
        _fail("tier3 missing")
    if t3.get("enabled") is not False:
        _fail("LANGFUSE=0 should disable tier3.enabled")
    if t3.get("replaces_watch") is True:
        _fail("tier3 must not replace watch")
    if not snap.get("ui"):
        _fail("ui phase block missing")
    _ok(f"tier3 off hint={t3.get('hint')}")

    os.environ["ORPATH_LANGFUSE"] = "1"
    snap1 = build_snapshot(slug="test", thread_id="test", workdir=ROOT, root=ROOT)
    if not (snap1.get("tier3") or {}).get("enabled"):
        _fail("ORPATH_LANGFUSE=1 should enable tier3")
    _ok("tier3 on when ORPATH_LANGFUSE=1")
    os.environ["ORPATH_LANGFUSE"] = "0"


def test_closeout_honesty() -> None:
    co = (ROOT / "docs/p5-closeout.md").read_text(encoding="utf-8", errors="replace")
    for n in (
        "Claim ladder",
        "P1",
        "P3",
        "P5",
        "未做",
        "Langfuse",
        "thinking_unavailable",
        "watch-run",
    ):
        if n not in co:
            _fail(f"closeout missing {n}")
    lf = (ROOT / "docs/p5-tier3-langfuse.md").read_text(encoding="utf-8", errors="replace")
    if "不替脸" not in lf and "Watch" not in lf:
        _fail("langfuse doc must stress Watch is face")
    if "ORPATH_LANGFUSE" not in lf:
        _fail("langfuse doc missing env")
    smoke = (ROOT / "docs/v0-smoke.md").read_text(encoding="utf-8", errors="replace")
    if "P5" not in smoke and "p5-gate" not in smoke:
        _fail("v0-smoke should mention P5")
    _ok("closeout + langfuse docs honest")


def main() -> int:
    print("=== p5_polish_gate ===")
    print("ROOT =", ROOT)
    test_files()
    test_html_polish()
    test_snapshot_tier3()
    test_closeout_honesty()
    print("PASS p5_polish_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
