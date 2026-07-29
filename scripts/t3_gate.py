#!/usr/bin/env python3
"""T3 business matrix gate: SP/TSP/VRP/vrp_tw via product runner + t3_lg_gate."""
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
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env.pop("PYTHONPATH", None)
    return env


def run(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    r = subprocess.run(args, cwd=ROOT, env=child_env(), text=True, capture_output=True)
    if check and r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        fail(f"cmd failed ({r.returncode}): {' '.join(args)}")
    return r


def main() -> int:
    # skeleton first
    r = run([PY, str(ROOT / "scripts" / "t3_lg_gate.py")])
    print(r.stdout)

    cases = [
        ("shortest_path", "mock", "shortest_path", "off"),
        ("tsp_n8", "ortools", "tsp", "seed"),
        ("vrp_multi", "ortools", "vrp", "seed"),
        ("vrp_tw", "ortools", "vrp", "off"),
    ]
    for pid, mode, pc, km in cases:
        slug = f"t3-mat-{pid}"
        r = run(
            [
                PY,
                str(ROOT / "orpath" / "run_orpath.py"),
                "run",
                "--problem-id",
                pid,
                "--problem-class",
                pc,
                "--solve-mode",
                mode,
                "--knowledge-mode",
                km,
                "--slug",
                slug,
                "--thread-id",
                slug,
                "--fresh",
            ]
        )
        print(r.stdout)
        summary = json.loads(r.stdout)
        if summary.get("human_required"):
            fail(f"{pid} human_required")
        if not summary.get("gate_validate_ok"):
            fail(f"{pid} validate not ok")
        if pid == "vrp_tw":
            sol = json.loads(Path(summary["solution_path"]).read_text(encoding="utf-8"))
            if int(sol.get("objective", -1)) != 58:
                fail(f"vrp_tw objective {sol.get('objective')}")
            if not sol.get("meta", {}).get("has_time_windows"):
                fail("vrp_tw missing TW meta")

    # hybrid smoke (seed-like offline acceptable if hybrid falls back)
    r = run(
        [
            PY,
            str(ROOT / "orpath" / "run_orpath.py"),
            "run",
            "--problem-id",
            "shortest_path",
            "--solve-mode",
            "mock",
            "--knowledge-mode",
            "hybrid",
            "--slug",
            "t3-mat-hybrid-sp",
            "--thread-id",
            "t3-mat-hybrid-sp",
            "--fresh",
        ]
    )
    print(r.stdout)
    summary = json.loads(r.stdout)
    if not summary.get("gate_validate_ok"):
        fail("hybrid sp validate")

    # focused pytest vrp + owner
    r = run(
        [
            PY,
            "-m",
            "pytest",
            str(ROOT / "tools" / "test_gates.py"),
            "-q",
            "-k",
            "vrp or networkx or mock",
            "-p",
            "no:langsmith",
        ]
    )
    print(r.stdout)

    print("PASS: t3_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
