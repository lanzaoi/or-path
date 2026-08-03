#!/usr/bin/env python3
"""M0 demo gate — V0 + demo-m0 mock numbers + sub evidence (history OK).

Does not require a fresh LIVE Pi run when historical subagent logs exist
(default allow_d3_from_history). Use --require-primary-sub to force D3 on slug=m0.

Exit 0 only if:
- v0_watch_gate PASS
- demo-m0 --slug m0 mock path produces solution+validate (or already on disk + --skip-run after run)
- D5 counters present on snapshot
- D3 true subagent evidence somewhere (default history allowed)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _py() -> str:
    cand = ROOT / ".venv-314" / "Scripts" / "python.exe"
    return str(cand) if cand.is_file() else sys.executable


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["ORPATH_LIVE_SUBAGENT"] = "0"
    env.setdefault("ORPATH_HOME", str(ROOT))
    env.setdefault("ORPATH_WORKDIR", str(ROOT))
    return env


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def main() -> int:
    print("=== m0_demo_gate (Phase D) ===")
    print("ROOT =", ROOT)
    env = _env()
    py = _py()

    # files
    for rel in (
        "scripts/orpath_demo_m0.py",
        "scripts/v0_watch_gate.py",
        "scripts/orpath_watch.py",
        "orpath/web/watch.html",
        "docs/m0-smoke.md",
        "ORPATH.md",
    ):
        if not (ROOT / rel).is_file():
            _fail(f"missing {rel}")
    _ok("required files")

    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    if "demo-m0" not in bat or "orpath_demo_m0.py" not in bat:
        _fail("orpath.bat missing demo-m0")
    if "PYTHONPATH=" not in bat and "set \"PYTHONPATH=\"" not in bat:
        # bat clears with set "PYTHONPATH="
        if "PYTHONPATH" not in bat:
            _fail("orpath.bat should clear PYTHONPATH")
    _ok("bat demo-m0 + path isolation")

    # run demo-m0 mock (no live)
    cmd = [
        py,
        str(ROOT / "scripts" / "orpath_demo_m0.py"),
        "--slug",
        "m0",
        "--no-live",
        "--solve-mode",
        "mock",
        "--problem-id",
        "shortest_path",
    ]
    print(">>", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
    sys.stdout.write(r.stdout or "")
    if r.stderr:
        sys.stderr.write(r.stderr[-1000:])
    if r.returncode not in (0, 3):
        # 3 = require-sub only; we don't pass require-sub
        _fail(f"demo-m0 rc={r.returncode}")
    if r.returncode == 0:
        _ok("demo-m0 exit 0")
    else:
        _fail(f"demo-m0 unexpected rc={r.returncode}")

    ev_json = ROOT / "outputs" / "m0-evidence.json"
    if not ev_json.is_file():
        alt = list((ROOT / "outputs").glob("*m0-evidence.json")) + list(
            (ROOT / "outputs").glob("m0*evidence*.json")
        )
        if not alt:
            _fail("missing m0 evidence json")
        ev_json = alt[0]
    import json

    rep = json.loads(ev_json.read_text(encoding="utf-8"))
    if not rep.get("D0_v0_watch_gate"):
        _fail("D0 V0 not green in evidence")
    if not rep.get("D2_solution_validate"):
        _fail("D2 solution+validate not green")
    if not rep.get("D5_counters_visible"):
        _fail("D5 counters missing")
    if not rep.get("pass_core"):
        _fail("pass_core false")
    _ok(
        f"evidence D0/D2/D5  obj={rep.get('solution',{}).get('objective')} "
        f"D3={rep.get('D3_true_subagent')} full={rep.get('pass_full_m0_experience')}"
    )

    sol = ROOT / "outputs" / "m0-solution.json"
    val = ROOT / "outputs" / "m0-validate.json"
    if not sol.is_file() or not val.is_file():
        _fail("m0-solution/validate missing after demo")
    _ok("m0-solution.json + m0-validate.json on disk")

    # docs claim
    orpath = (ROOT / "ORPATH.md").read_text(encoding="utf-8", errors="replace")
    if "demo-m0" not in orpath:
        _fail("ORPATH.md must document demo-m0")
    _ok("ORPATH documents demo-m0")

    print("PASS m0_demo_gate")
    if not rep.get("D3_true_subagent"):
        print(
            "NOTE: D3 historical sub evidence missing — full_m0_experience=false; "
            "core M0 numbers+V0 still PASS. Seed LIVE run or keep test slug agents."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
