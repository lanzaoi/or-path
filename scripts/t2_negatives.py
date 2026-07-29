#!/usr/bin/env python3
"""T2 negatives: bad schema, tampered objective, validate fail path."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def env() -> dict[str, str]:
    e = dict(os.environ)
    e["PYTHONNOUSERSITE"] = "1"
    e.pop("PYTHONPATH", None)
    return e


def main() -> int:
    # bad schema with objective
    bad = ROOT / "outputs" / "t2-neg-bad-schema.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text(
        json.dumps(
            {
                "problem_id": "tsp_n8",
                "problem_class": "tsp",
                "coords": [{"id": "0", "x": 0, "y": 0}],
                "objective": 99,
            }
        ),
        encoding="utf-8",
    )
    r = subprocess.run(
        [PY, str(ROOT / "tools" / "gate_schema.py"), str(bad)],
        cwd=ROOT,
        env=env(),
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0, "schema with objective must fail"

    # tampered solution
    gold = json.loads(
        (ROOT / "fixtures" / "t2" / "tsp_n8" / "solution.json").read_text(encoding="utf-8")
    )
    tampered = dict(gold)
    tampered["objective"] = int(gold["objective"]) + 12345
    tp = ROOT / "outputs" / "t2-neg-tampered-sol.json"
    tp.write_text(json.dumps(tampered, indent=2), encoding="utf-8")
    r = subprocess.run(
        [
            PY,
            str(ROOT / "tools" / "validate_solution.py"),
            "--problem-id",
            "tsp_n8",
            "--solution",
            str(tp),
        ],
        cwd=ROOT,
        env=env(),
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0, "tampered objective must fail validate"

    proof = ROOT / "outputs" / "t2-negatives-proof.md"
    proof.write_text(
        "# T2 negatives proof\n\n"
        "- bad schema with objective: FAIL as expected\n"
        "- tampered tsp objective: FAIL as expected\n",
        encoding="utf-8",
    )
    print("PASS: t2_negatives")
    print(proof)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
