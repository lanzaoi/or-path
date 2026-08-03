#!/usr/bin/env python3
"""M1 composite gate — Parts 1–4 (workdir + Watch error UX + CTAs).

Runs child gates in order. No LIVE Pi required.
Exit 0 only if all children PASS.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHILDREN = (
    ("Part1 workdir paths", "scripts/m1_workdir_paths_gate.py"),
    ("Part2 workdir e2e", "scripts/m1_workdir_e2e_gate.py"),
    ("Part3 error UX", "scripts/m1_watch_error_ux_gate.py"),
    ("Part4 next_actions CTA", "scripts/m1_watch_cta_gate.py"),
)


def _py() -> str:
    cand = ROOT / ".venv-314" / "Scripts" / "python.exe"
    return str(cand) if cand.is_file() else sys.executable


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["ORPATH_LIVE_SUBAGENT"] = "0"
    env.setdefault("ORPATH_HOME", str(ROOT))
    return env


def main() -> int:
    print("=== m1_gate (M1 composite · Parts 1–4) ===")
    print("ROOT =", ROOT)
    # wiring docs
    for rel in (
        "docs/m1-smoke.md",
        "docs/m1-closeout.md",
        "orpath.bat",
        "orpath/paths.py",
        "orpath/web/watch.html",
        "orpath/watch_snapshot.py",
    ):
        if not (ROOT / rel).is_file():
            print("FAIL: missing", rel)
            return 1
    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    if "m1-gate" not in bat and "m1_gate" not in bat:
        print("FAIL: orpath.bat missing m1-gate wiring")
        return 1
    print("OK: files + bat m1-gate")

    failed = False
    for title, rel in CHILDREN:
        script = ROOT / rel
        if not script.is_file():
            print(f"FAIL: missing child {rel}")
            return 1
        print(f"\n--- {title}: {rel} ---")
        proc = subprocess.run(
            [_py(), str(script)],
            cwd=str(ROOT),
            env=_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        # tail for readability
        print(out[-2500:] if len(out) > 2500 else out)
        if proc.returncode != 0:
            print(f"FAIL: {rel} exit={proc.returncode}")
            failed = True
            break
        if "PASS" not in out:
            print(f"FAIL: {rel} no PASS marker")
            failed = True
            break
        print(f"OK: {title}")

    if failed:
        print("\nFAIL m1_gate")
        return 1

    # light claim ladder markers in closeout
    close = (ROOT / "docs" / "m1-closeout.md").read_text(encoding="utf-8", errors="replace")
    for n in ("workdir", "next_actions", "Claim ladder", "M1"):
        if n not in close:
            print(f"FAIL: m1-closeout missing {n}")
            return 1
    print("OK: m1-closeout claim markers")
    print("\nPASS m1_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
