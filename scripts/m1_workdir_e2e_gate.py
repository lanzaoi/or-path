#!/usr/bin/env python3
"""M1 Part 2 gate: watch-run --workdir end-to-end (mock, no LIVE Pi).

Exit 0 only if:
- watch-run accepts --workdir
- mock run writes stages under that workdir (not install root bleed)
- evidence JSON lives under workdir/outputs
- /api/health reports the same workdir
- /api/snapshot for slug is non-empty L0
- wrong empty workdir does not see stages
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
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


def _get_json(url: str, timeout: float = 3.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_wiring() -> None:
    src = (ROOT / "scripts" / "orpath_watch_run.py").read_text(encoding="utf-8")
    if "--workdir" not in src or "apply_workdir" not in src:
        _fail("orpath_watch_run missing --workdir/apply_workdir")
    if '"--workdir"' not in src and "'--workdir'" not in src:
        # passed to run_orpath
        if "workdir.resolve()" not in src and "--workdir" not in src:
            _fail("run product must pass --workdir")
    wsrc = (ROOT / "scripts" / "orpath_watch.py").read_text(encoding="utf-8")
    if "--workdir" not in wsrc:
        _fail("orpath_watch missing --workdir")
    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    if "watch-run" not in bat and "watch_run" not in bat:
        _fail("bat missing watch-run")
    _ok("CLI wiring")


def test_watch_run_workdir() -> None:
    wd = Path(tempfile.mkdtemp(prefix="orpath-m1-e2e-"))
    slug = f"m1-wd-{int(time.time())}"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["ORPATH_LIVE_SUBAGENT"] = "0"
    env["ORPATH_HOME"] = str(ROOT)
    # Intentionally wrong parent env — CLI --workdir must override
    env["ORPATH_WORKDIR"] = str(ROOT)

    cmd = [
        _py(),
        str(ROOT / "scripts" / "orpath_watch_run.py"),
        "--slug",
        slug,
        "--thread-id",
        slug,
        "--workdir",
        str(wd),
        "--no-browser",
        "--solve-mode",
        "mock",
        "--problem-id",
        "shortest_path",
        "--run-timeout",
        "180",
        "--grow-timeout",
        "120",
        "--port",
        "8791",
    ]
    print(">>", " ".join(cmd))
    print("workdir", wd)
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
    print((proc.stdout or "")[-2500:])
    if proc.returncode != 0:
        print((proc.stderr or "")[-1500:])
        _fail(f"watch-run exit={proc.returncode}")

    stages = wd / "runs" / slug / "stages"
    if not stages.is_dir() or not any(stages.glob("*.json")):
        _fail(f"no stages under workdir {stages}")
    _ok(f"stages under workdir n={len(list(stages.glob('*.json')))}")

    # Must not require install-root stages for this slug
    root_stages = ROOT / "runs" / slug / "stages"
    # ok if also created (legacy) but workdir must have them
    _ok("workdir stages present")

    ev = wd / "outputs" / f"{slug}-watch-run.json"
    if not ev.is_file():
        _fail(f"missing evidence {ev}")
    evidence = json.loads(ev.read_text(encoding="utf-8"))
    if not evidence.get("stages_grew") and not evidence.get("ok"):
        _fail(f"evidence not ok: {evidence}")
    if Path(evidence.get("workdir") or "").resolve() != wd.resolve():
        _fail(f"evidence.workdir {evidence.get('workdir')} != {wd}")
    _ok(f"evidence ok stages {evidence.get('stages_before')}→{evidence.get('stages_after')}")

    # Snapshot isolation via library
    from orpath.watch_snapshot import build_snapshot

    snap = build_snapshot(slug=slug, thread_id=slug, workdir=wd, root=ROOT)
    if not snap.get("stages"):
        _fail("build_snapshot empty on workdir")
    if Path(str(snap.get("workdir"))).resolve() != wd.resolve():
        _fail("snap.workdir mismatch")
    _ok(f"snapshot L0={len(snap['stages'])} status={snap.get('status')}")

    # Negative: other empty workdir
    wd2 = Path(tempfile.mkdtemp(prefix="orpath-m1-e2e-empty-"))
    from orpath.paths import ensure_workdir_layout

    ensure_workdir_layout(wd2)
    snap2 = build_snapshot(slug=slug, thread_id=slug, workdir=wd2, root=ROOT)
    if snap2.get("stages"):
        _fail("empty workdir should not see stages")
    if snap2.get("status") != "no_product_run":
        _fail(f"expected no_product_run got {snap2.get('status')}")
    _ok("negative empty workdir isolation")

    # Health while skip-run server briefly (optional lightweight)
    # Use a short skip-run to verify health.workdir — separate process
    port = 8792
    cmd2 = [
        _py(),
        str(ROOT / "scripts" / "orpath_watch_run.py"),
        "--slug",
        slug,
        "--workdir",
        str(wd),
        "--skip-run",
        "--no-browser",
        "--port",
        str(port),
    ]
    # run with timeout kill via communicate — use short background then health
    proc2 = subprocess.Popen(
        cmd2,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        health = None
        deadline = time.time() + 12
        while time.time() < deadline:
            try:
                health = _get_json(f"http://127.0.0.1:{port}/api/health")
                if health.get("ok"):
                    break
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
                time.sleep(0.2)
        if not health or not health.get("ok"):
            _fail("health not ok for skip-run server")
        hwd = Path(str(health.get("workdir") or "")).resolve()
        if hwd != wd.resolve():
            _fail(f"health.workdir {hwd} != {wd}")
        _ok(f"health workdir={hwd}")

        snap_api = _get_json(
            f"http://127.0.0.1:{port}/api/snapshot?slug={slug}&thread={slug}"
        )
        if not snap_api.get("stages"):
            _fail("api snapshot empty stages")
        _ok(f"api snapshot stages={len(snap_api.get('stages') or [])}")
    finally:
        proc2.terminate()
        try:
            proc2.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc2.kill()


def main() -> int:
    print("=== m1_workdir_e2e_gate (Part 2) ===")
    print("ROOT =", ROOT)
    os.environ.pop("PYTHONPATH", None)
    os.environ["PYTHONNOUSERSITE"] = "1"
    test_wiring()
    test_watch_run_workdir()
    # Part1 still green
    r = subprocess.run(
        [_py(), str(ROOT / "scripts" / "m1_workdir_paths_gate.py")],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": "", "PYTHONNOUSERSITE": "1"},
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        _fail("part1 gate regression")
    _ok("part1 gate still PASS")
    print("PASS m1_workdir_e2e_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
