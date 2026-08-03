#!/usr/bin/env python3
"""V0 Live Watch gate — docs + face wiring + HTTP smoke (no full product run).

Exit 0 only if:
- watch modules / HTML / bat / menu present
- ORPATH.md + README mention watch as live process face
- watch_snapshot_gate passes
- HTTP health + snapshot + HTML respond on ephemeral port
- claim-ladder negative: docs do not equate folder-only with live face

Does NOT claim M0 (solution + live sub demo). See specs/process-visibility.md §6.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orpath.watch_snapshot import (  # noqa: E402
    assert_no_llm_imports,
    build_snapshot,
    validate_snapshot_shape,
)


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def _read(rel: str) -> str:
    p = ROOT / rel
    if not p.is_file():
        _fail(f"missing file {rel}")
    return p.read_text(encoding="utf-8", errors="replace")


def test_files() -> None:
    for rel in (
        "orpath/watch_snapshot.py",
        "orpath/web/watch.html",
        "scripts/orpath_watch.py",
        "scripts/watch_snapshot_gate.py",
        "docs/v0-smoke.md",
        "ORPATH.md",
        "README.md",
    ):
        if not (ROOT / rel).is_file():
            _fail(f"missing {rel}")
    _ok("required files present")


def test_bat_menu() -> None:
    bat = _read("orpath.bat")
    if "orpath_watch.py" not in bat or ":watch" not in bat:
        _fail("orpath.bat missing watch entry")
    if 'if /i "%CMD%"=="watch"' not in bat and "goto :watch" not in bat:
        _fail("orpath.bat missing watch dispatch")
    # gui-demo must not be split across lines
    if any(ln.strip().startswith("un_orpath.py") for ln in bat.splitlines()):
        _fail("orpath.bat gui_demo path broken across lines")
    menu = _read("scripts/orpath_menu.py")
    if "Live Watch" not in menu or '"watch"' not in menu:
        _fail("menu missing Live Watch → watch")
    _ok("bat + menu watch wiring")


def test_docs_face() -> None:
    orpath = _read("ORPATH.md")
    readme = _read("README.md")
    smoke = _read("docs/v0-smoke.md")

    for label, text in (("ORPATH.md", orpath), ("README.md", readme)):
        if "orpath.bat watch" not in text and "orpath.bat watch" not in text.replace("`", ""):
            # allow either plain or code-formatted
            if "watch --slug" not in text and "Live Watch" not in text:
                _fail(f"{label} must document watch / Live Watch face")
        if "watch" not in text.lower():
            _fail(f"{label} missing watch")

    # Contract phrases: live process on watch, not folder-only
    needles_orpath = [
        "watch",
        "实时",
    ]
    for n in needles_orpath:
        if n not in orpath:
            _fail(f"ORPATH.md missing '{n}'")
    if "文件夹" not in orpath and "folder" not in orpath.lower():
        # should contrast fake delivery
        if "假交付" not in orpath and "不算" not in orpath:
            _fail("ORPATH.md should contrast folder-only fake delivery")

    if "v0-smoke" not in smoke.lower() and "Live Watch" not in smoke:
        _fail("docs/v0-smoke.md incomplete")
    if "orpath.bat watch" not in smoke:
        _fail("docs/v0-smoke.md must show orpath.bat watch")

    # README should point users to watch for process
    if "watch" not in readme.lower():
        _fail("README.md must mention watch")
    _ok("docs face contract (ORPATH/README/v0-smoke)")


def test_snapshot_unit() -> None:
    assert_no_llm_imports(ROOT / "orpath" / "watch_snapshot.py")
    snap = build_snapshot(slug="test", thread_id="test", root=ROOT, workdir=ROOT)
    errs = validate_snapshot_shape(snap)
    if errs:
        _fail(f"snapshot shape: {errs}")
    if not snap.get("stages"):
        _fail("expected historical runs/test stages for V0 smoke fixture")
    if snap.get("status") == "no_product_run":
        _fail("test slug should be a product run")
    miss = build_snapshot(
        slug="__v0_gate_missing__",
        thread_id="__v0_gate_missing__",
        root=ROOT,
        workdir=ROOT,
    )
    if miss.get("status") != "no_product_run":
        _fail("missing slug honesty")
    th = (snap.get("thinking") or {}).get("status")
    if th not in {"available", "thinking_unavailable"}:
        _fail(f"thinking status {th}")
    _ok(
        f"snapshot unit stages={len(snap['stages'])} status={snap['status']} "
        f"thinking={th} dispatches={len(snap.get('dispatches') or [])}"
    )


def test_watch_snapshot_gate() -> None:
    py = sys.executable
    r = subprocess.run(
        [py, str(ROOT / "scripts" / "watch_snapshot_gate.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        _fail(f"watch_snapshot_gate rc={r.returncode}\n{r.stdout}\n{r.stderr}")
    _ok("watch_snapshot_gate nested PASS")


def test_http_smoke() -> None:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    py = sys.executable
    proc = subprocess.Popen(
        [
            py,
            str(ROOT / "scripts" / "orpath_watch.py"),
            "--slug",
            "test",
            "--port",
            str(port),
            "--no-browser",
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 15
        last = ""
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(base + "/api/health", timeout=1) as resp:
                    health = json.loads(resp.read().decode())
                break
            except Exception as exc:  # noqa: BLE001
                last = str(exc)
                if proc.poll() is not None:
                    out = proc.stdout.read() if proc.stdout else ""
                    _fail(f"watch server died: {out or last}")
                time.sleep(0.15)
        else:
            _fail(f"watch server not up: {last}")

        if not health.get("ok") or not health.get("html_exists"):
            _fail(f"health bad: {health}")
        if health.get("p1") is not True and "/api/poll" not in str(health.get("endpoints") or []):
            # soft: still require poll endpoint works below
            pass
        _ok(f"HTTP health port={port}")

        with urllib.request.urlopen(
            base + "/api/poll?slug=test&thread=test", timeout=5
        ) as resp:
            poll = json.loads(resp.read().decode())
        if not poll.get("fingerprint"):
            _fail(f"poll missing fingerprint: {poll}")
        if poll.get("stages_count", 0) < 1:
            _fail("poll stages_count expected >=1 for test")
        _ok(f"HTTP poll fp={poll['fingerprint']} stages={poll['stages_count']}")

        with urllib.request.urlopen(
            base + "/api/snapshot?slug=test&thread=test", timeout=15
        ) as resp:
            snap = json.loads(resp.read().decode())
        if not snap.get("stages"):
            _fail("HTTP snapshot empty stages")
        if not (snap.get("poll") or {}).get("fingerprint"):
            _fail("snapshot missing poll.fingerprint (P1)")
        _ok(f"HTTP snapshot stages={len(snap['stages'])} poll_ok")

        with urllib.request.urlopen(base + "/", timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        if "Live Watch" not in html or "POLL_MS" not in html:
            _fail("HTML missing Live Watch / POLL_MS")
        # P1 refresh ≤1s
        if "1000" not in html and "POLL_MS = 1000" not in html:
            _fail("P1 poll interval 1000ms expected in page")
        if "/api/poll" not in html and "api/poll" not in html:
            # page uses fetch to /api/poll
            if "poll" not in html.lower():
                _fail("HTML missing poll path")
        _ok(f"HTTP HTML bytes={len(html)} P1 interval")

        with urllib.request.urlopen(
            base + "/api/snapshot?slug=__v0_http_missing__", timeout=5
        ) as resp:
            miss = json.loads(resp.read().decode())
        if miss.get("status") != "no_product_run":
            _fail("HTTP missing slug")
        _ok("HTTP missing slug honesty")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def test_claim_ladder_docs() -> None:
    """Docs must not claim folder-only equals live visibility."""
    orpath = _read("ORPATH.md").lower()
    # positive: watch is the answer
    if "watch" not in orpath:
        _fail("ORPATH claim ladder: watch missing")
    # negative phrasing present in some form
    bad_equate = (
        "打开 runs 就是实时可视",
        "folder is the live face",
        "only folder browse = v0",
    )
    for b in bad_equate:
        if b in orpath:
            _fail(f"ORPATH contains forbidden claim: {b}")
    _ok("claim ladder docs smoke")


def main() -> int:
    print("=== v0_watch_gate (Phase C) ===")
    print("ROOT =", ROOT)
    test_files()
    test_bat_menu()
    test_docs_face()
    test_claim_ladder_docs()
    test_snapshot_unit()
    test_watch_snapshot_gate()
    test_http_smoke()
    print("PASS v0_watch_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
