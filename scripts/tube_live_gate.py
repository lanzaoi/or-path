#!/usr/bin/env python3
"""Strict current Tube gate: source preflight -> solve -> v2 recompute validate.

Historical demo output is intentionally not accepted.  Missing unpublished
attachments is reported as BLOCKED with exit code 2, not as a solver PASS.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from solve_tube_cut_b2026 import blocked_envelope, input_readiness  # noqa: E402


def _py() -> str:
    candidate = ROOT / ".venv-314" / "Scripts" / "python.exe"
    return str(candidate) if candidate.is_file() else sys.executable


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    print("=== tube_live_gate v2 ===")
    ready = input_readiness()
    if not ready["ok"]:
        payload = blocked_envelope()
        payload["gate"] = "tube_live_gate"
        payload["gate_result"] = "BLOCKED"
        payload["strict_current_run"] = False
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    # A gate uses the short deterministic budget unless the caller explicitly
    # chooses another profile/budget.
    solve_args = argv or ["--fast"]
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "PYTHONHOME"}
    }
    env["PYTHONNOUSERSITE"] = "1"
    process = subprocess.run(
        [_py(), str(ROOT / "scripts" / "b_tube_solve.py"), *solve_args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0:
        return fail(((process.stdout or "") + (process.stderr or ""))[-2000:])

    solution_path = ROOT / "outputs" / "tube_cut_b2026-solution.json"
    validate_path = ROOT / "outputs" / "tube_cut_b2026-validate.json"
    if not solution_path.is_file() or not validate_path.is_file():
        return fail("current v2 solution/validate artifacts were not written")
    solution = json.loads(solution_path.read_text(encoding="utf-8"))
    report = json.loads(validate_path.read_text(encoding="utf-8"))
    if not report.get("ok"):
        return fail(f"strict validator rejected current run: {report.get('errors')}")
    snapshot = solution.get("model_snapshot") or {}
    if snapshot.get("schema") != "orpath.tube_model.v2":
        return fail("current solution lacks orpath.tube_model.v2 snapshot")
    if str(solution.get("status") or "").upper() != "FEASIBLE":
        return fail(f"unexpected solution status {solution.get('status')}")
    print(
        json.dumps(
            {
                "ok": True,
                "gate": "tube_live_gate",
                "gate_result": "PASS",
                "strict_current_run": True,
                "status": solution["status"],
                "objective": solution["objective"],
                "solution_path": str(solution_path),
                "validate_path": str(validate_path),
                "model_schema": snapshot["schema"],
                "seed": snapshot.get("seed"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("PASS tube_live_gate v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
