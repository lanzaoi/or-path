#!/usr/bin/env python3
"""M2 Phase 4 gate: Watch sees polyomino run + M1 error/CTA surface.

1. Phase3 still PASS (product workdir)
2. After polyomino product run in temp workdir:
   - build_snapshot has L0 stages, L4 solution/validate/schema
   - paper HUMAN → next_actions with workdir + solve-mode polyomino
3. HTTP watch API returns same snapshot shape
4. HTML still has M1 error/CTA markers
5. m1_watch_cta_gate still PASS
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer
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


def _env(wd: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["ORPATH_LIVE_SUBAGENT"] = "0"
    env["ORPATH_HOME"] = str(ROOT)
    if wd is not None:
        env["ORPATH_WORKDIR"] = str(wd)
    return env


def test_prior() -> None:
    r = subprocess.run(
        [_py(), str(ROOT / "scripts" / "m2_phase3_product_workdir_gate.py")],
        cwd=str(ROOT),
        env=_env(),
        capture_output=True,
        text=True,
        timeout=420,
    )
    if r.returncode != 0 or "PASS m2_phase3" not in (r.stdout or ""):
        print((r.stdout or "")[-1500:])
        print((r.stderr or "")[-500:])
        _fail("phase3 regression")
    _ok("phase3 still PASS")


def _run_poly(wd: Path, slug: str) -> None:
    cmd = [
        _py(),
        str(ROOT / "orpath" / "run_orpath.py"),
        "run",
        "--workdir",
        str(wd),
        "--slug",
        slug,
        "--thread-id",
        slug,
        "--problem-id",
        "polyomino_b_q1",
        "--problem-class",
        "polyomino_cover",
        "--solve-mode",
        "polyomino",
        "--no-live-subagent",
        "--fresh",
        "--force",
    ]
    subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=_env(wd),
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_snapshot_poly() -> tuple[Path, str, dict]:
    from orpath.paths import apply_workdir
    from orpath.watch_snapshot import (
        assert_no_llm_imports,
        build_snapshot,
        validate_snapshot_shape,
    )

    assert_no_llm_imports(ROOT / "orpath" / "watch_snapshot.py")
    wd = Path(tempfile.mkdtemp(prefix="orpath-m2p4-"))
    apply_workdir(wd)
    slug = f"m2p4-{int(time.time())}"
    _run_poly(wd, slug)

    snap = build_snapshot(slug=slug, thread_id=slug, workdir=wd, root=ROOT)
    errs = validate_snapshot_shape(snap)
    if errs:
        _fail(f"shape {errs}")

    stages = snap.get("stages") or []
    if len(stages) < 5:
        _fail(f"few stages {len(stages)}")
    _ok(f"L0 stages n={len(stages)} status={snap.get('status')}")

    art = snap.get("artifacts") or {}
    for k in ("solution", "validate", "schema"):
        if not art.get(k):
            _fail(f"artifacts missing {k}: {art}")
    _ok(f"L4 artifacts solution/validate/schema (+ paper={bool(art.get('paper'))})")

    # workdir contract on snapshot
    if str(Path(snap.get("workdir") or "")).lower() != str(wd.resolve()).lower():
        # Windows path normalize
        if Path(snap.get("workdir") or "").resolve() != wd.resolve():
            _fail(f"snap workdir {snap.get('workdir')} != {wd}")
    _ok("snapshot workdir matches")

    # After full product, often blocked on paper — CTA required
    status = str(snap.get("status") or "")
    err = snap.get("error") or {}
    na = snap.get("next_actions") or err.get("next_actions") or []
    if status in {"fail", "blocked"} or err.get("has_error") or (
        snap.get("current") or {}
    ).get("human_required"):
        if not na:
            _fail(f"expected next_actions on blocked/fail status={status}")
        cmds = " ".join(a.get("command") or "" for a in na)
        if "--workdir" not in cmds:
            _fail(f"CTA missing --workdir: {cmds[:200]}")
        if "polyomino" not in cmds.lower() and "solve-mode" not in cmds:
            # domain flags should appear from schema/solution
            _fail(f"CTA missing polyomino flags: {cmds[:240]}")
        if "orpath.bat watch" not in cmds:
            _fail("CTA missing Open Live Watch")
        if "--from-stage" not in cmds and "run --resume" not in cmds:
            _fail("CTA missing resume/from-stage")
        _ok(f"next_actions n={len(na)} with workdir+polyomino")
    else:
        # rare full green including paper
        _ok(f"status={status} (no HUMAN CTA required)")

    return wd, slug, snap


def test_http(wd: Path, slug: str) -> None:
    from scripts.orpath_watch import WatchHandler, DEFAULT_PORT
    from orpath.paths import orpath_home

    # pick free port
    home = orpath_home().resolve()
    handler = partial(WatchHandler, home=home, workdir=wd.resolve())
    httpd = None
    port = DEFAULT_PORT
    for p in range(DEFAULT_PORT, DEFAULT_PORT + 40):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), handler)
            port = p
            break
        except OSError:
            continue
    if httpd is None:
        _fail("no free port for watch")

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        url = f"http://127.0.0.1:{port}/api/snapshot?slug={slug}&thread={slug}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        data = json.loads(body)
        if not (data.get("stages") or []):
            _fail("HTTP snapshot empty stages")
        art = data.get("artifacts") or {}
        if not art.get("solution"):
            _fail(f"HTTP no solution art: {art}")
        # page root
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        for n in ("errCopy", "nextActions", "Copy cmd", "data-m1-next-actions"):
            if n not in html:
                _fail(f"HTML missing {n}")
        _ok(f"HTTP snapshot+HTML port={port} stages={len(data.get('stages') or [])}")
    except urllib.error.URLError as exc:
        _fail(f"HTTP failed: {exc}")
    finally:
        httpd.shutdown()


def test_html_and_m1_cta() -> None:
    html = (ROOT / "orpath" / "web" / "watch.html").read_text(encoding="utf-8", errors="replace")
    for n in ("errBanner", "errCopy", "nextActions", "renderNextActions", "Jump stage"):
        if n not in html:
            _fail(f"watch.html missing {n}")
    _ok("HTML M1 error/CTA markers")
    r = subprocess.run(
        [_py(), str(ROOT / "scripts" / "m1_watch_cta_gate.py")],
        cwd=str(ROOT),
        env=_env(),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        _fail("m1_watch_cta_gate regression")
    _ok("m1_watch_cta_gate still PASS")


def test_docs() -> None:
    t = (ROOT / "docs" / "m2-polyomino.md").read_text(encoding="utf-8")
    if "阶段 4" not in t and "Phase 4" not in t and "phase 4" not in t.lower():
        # table row **4**
        if "**4**" not in t and "Watch" not in t:
            _fail("docs missing phase 4")
    if "watch" not in t.lower():
        _fail("docs missing watch")
    _ok("docs phase 4")


def main() -> int:
    print("=== m2_phase4_watch_cta_gate ===")
    os.environ.pop("PYTHONPATH", None)
    os.environ["PYTHONNOUSERSITE"] = "1"
    # import scripts.orpath_watch as package path
    sys.path.insert(0, str(ROOT / "scripts"))
    test_prior()
    wd, slug, _snap = test_snapshot_poly()
    test_http(wd, slug)
    test_html_and_m1_cta()
    test_docs()
    print("PASS m2_phase4_watch_cta_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
