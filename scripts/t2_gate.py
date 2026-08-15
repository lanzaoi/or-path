#!/usr/bin/env python3
"""T2 local gate: contracts, solvers, validate, knowledge unit, run_t2 multi-class."""
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


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault('ORPATH_LIVE_SUBAGENT', '0')
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("PYTHONPATH", None)
    return env


def run(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    r = subprocess.run(
        args, cwd=ROOT, env=child_env(), text=True, capture_output=True
    )
    if check and r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        fail(f"cmd failed ({r.returncode}): {' '.join(args)}")
    return r


def main() -> int:
    # t1 still green
    r = run([PY, str(ROOT / "scripts" / "t1_gate.py")])
    print(r.stdout)

    r = run(
        [
            PY,
            "-m",
            "pytest",
            str(ROOT / "tools"),
            str(ROOT / "knowledge_svc"),
            "-q",
            "-p",
            "no:langsmith",
        ]
    )
    print(r.stdout)

    r = run([PY, str(ROOT / "scripts" / "t2_negatives.py")])
    print(r.stdout)

    cases = [
        ("shortest_path", "mock", "shortest_path"),
        ("tsp_n8", "ortools", "tsp"),
        ("vrp_multi", "ortools", "vrp"),
    ]
    for pid, mode, pc in cases:
        slug = f"t2-gate-{pid}"
        r = run(
            [
                PY,
                str(ROOT / "orpath" / "run_t2.py"),
                "--problem-id",
                pid,
                "--problem-class",
                pc,
                "--slug",
                slug,
                "--solve-mode",
                mode,
                "--knowledge-mode",
                "seed",
            ]
        )
        print(r.stdout)
        summary = json.loads(r.stdout)
        if summary.get("human_required"):
            fail(f"{pid} human_required")
        if not summary.get("gate_validate_ok"):
            fail(f"{pid} validate not ok")
        paper = Path(summary["paper_path"])
        sol = Path(summary["solution_path"])
        # R2
        rr = run(
            [
                PY,
                str(ROOT / "tools" / "r2_numeric_check.py"),
                "--draft",
                str(paper),
                "--solution",
                str(sol),
            ]
        )
        print(rr.stdout)

    # bridge capability evidence
    r = run(
        [
            PY,
            "-c",
            "from orpath.pi_bridge import require_bridge_evidence; "
            f"from pathlib import Path; p=require_bridge_evidence(Path(r'{ROOT}')); print(p)",
        ]
    )
    print("bridge:", r.stdout.strip())

    # T2 is a historical regression gate and all gate runs force LIVE off.
    # Validate the committed closeout evidence here; use `orpath.bat isolation`
    # for a strict, current-machine LIVE transcript check.
    r = run([PY, str(ROOT / "scripts" / "t2_archived_isolation_gate.py")])
    print(r.stdout)

    print("PASS: t2_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
