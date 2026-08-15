#!/usr/bin/env python3
"""M2 composite gate — polyomino domain bridge Parts 1–5.

Exit 0 only if all child gates PASS and optional paper smoke is green.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHILDREN = (
    ("Part1 contract", "scripts/m2_phase1_contract_gate.py"),
    ("Part2 solve+validate", "scripts/m2_phase2_solve_validate_gate.py"),
    ("Part3 product workdir", "scripts/m2_phase3_product_workdir_gate.py"),
    ("Part4 watch+CTA", "scripts/m2_phase4_watch_cta_gate.py"),
    ("Part5 paper smoke", "scripts/m2_phase5_paper_gate.py"),
)


def _py() -> str:
    cand = ROOT / ".venv-314" / "Scripts" / "python.exe"
    return str(cand) if cand.is_file() else sys.executable


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ORPATH_LIVE_SUBAGENT"] = "0"
    env["ORPATH_HOME"] = str(ROOT)
    return env


def main() -> int:
    print("=== m2_gate (polyomino domain bridge · Parts 1–5) ===")
    print("ROOT =", ROOT)
    for rel in (
        "docs/m2-polyomino.md",
        "docs/m2-closeout.md",
        "orpath.bat",
        "orpath/domain_registry.py",
        "tools/solve_polyomino.py",
        "fixtures/t3/polyomino_b_q1/whitelist_refs.json",
    ):
        if not (ROOT / rel).is_file():
            print("FAIL: missing", rel)
            return 1
    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    if "m2-gate" not in bat and "m2_gate" not in bat:
        print("FAIL: orpath.bat missing m2-gate wiring")
        return 1
    print("OK: files + bat m2-gate")

    for title, rel in CHILDREN:
        script = ROOT / rel
        if not script.is_file():
            print(f"FAIL: missing {rel}")
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
            timeout=900,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        print(out[-2800:] if len(out) > 2800 else out)
        if proc.returncode != 0:
            print(f"FAIL: {rel} exit={proc.returncode}")
            return 1
        if "PASS" not in out:
            print(f"FAIL: {rel} no PASS marker")
            return 1
        print(f"OK: {title}")

    close = (ROOT / "docs" / "m2-closeout.md").read_text(encoding="utf-8", errors="replace")
    for n in ("polyomino", "Claim ladder", "M2", "m2-gate"):
        if n not in close:
            print("FAIL: m2-closeout missing", n)
            return 1
    print("OK: m2-closeout claim markers")
    print("\nPASS m2_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
