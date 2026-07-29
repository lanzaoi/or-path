#!/usr/bin/env python3
"""Semi-automatic T1 DoD gate (Q1=D)."""
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
    # Prefer this interpreter's site-packages only
    env.pop("PYTHONPATH", None)
    return env


def main() -> int:
    agents = ROOT / ".pi" / "agents"
    needed = [
        "or-orchestrator.md",
        "or-researcher.md",
        "or-modeler.md",
        "or-writer.md",
        "or-verifier.md",
        "or-reviewer.md",
    ]
    for n in needed:
        if not (agents / n).is_file():
            fail(f"missing agent {n}")

    settings = json.loads((ROOT / ".pi" / "settings.json").read_text(encoding="utf-8"))
    pkgs = settings.get("packages") or []
    if not any("pi-subagents" in str(p) for p in pkgs):
        fail("pi-subagents not in .pi/settings.json packages")

    sol = ROOT / "fixtures" / "t1" / "shortest_path" / "solution.json"
    data = json.loads(sol.read_text(encoding="utf-8"))
    if data.get("objective") != 42:
        fail("fixture objective != 42")

    env = child_env()
    r = subprocess.run(
        [PY, "-m", "pytest", str(ROOT / "tools"), "-q", "-p", "no:langsmith"],
        cwd=ROOT,
        env=env,
    )
    if r.returncode != 0:
        fail("pytest tools failed")

    r = subprocess.run(
        [PY, str(ROOT / "scripts" / "t1_negatives.py")],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        fail("t1_negatives failed")

    r = subprocess.run(
        [PY, str(ROOT / "orpath" / "run_t1.py"), "--solve-mode", "mock"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        fail(f"run_t1 exit {r.returncode}")
    summary = json.loads(r.stdout)
    if not summary.get("provenance_path"):
        fail("no provenance")
    if summary.get("human_required"):
        fail("human_required set")
    # ADR-0001: T1 must run product graph
    if summary.get("pipeline") != "product":
        fail(f"expected pipeline=product, got {summary.get('pipeline')!r}")
    if summary.get("gate_validate_ok") is not True:
        fail(f"gate_validate_ok not true: {summary.get('gate_validate_ok')!r}")
    paper = Path(summary["paper_path"])
    text = paper.read_text(encoding="utf-8")
    if "objective = 42" not in text and "objective: 42" not in text:
        if "42" not in text:
            fail("paper missing objective 42")
    prov = Path(summary["provenance_path"]).read_text(encoding="utf-8")
    if "pipeline: product" not in prov and "pipeline: product" not in text:
        # provenance thick section should mark product
        if "T3 skeleton" not in prov and "pipeline: product" not in prov:
            fail("provenance missing product/T3 skeleton markers")
    print("PASS: t1_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
