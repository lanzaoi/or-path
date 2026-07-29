from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
PY = sys.executable
FIX = ROOT / "fixtures" / "t1" / "shortest_path"
TD = TOOLS / "testdata"


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True)


def test_solve_mock():
    r = run([PY, str(TOOLS / "solve_mock.py"), "shortest_path"])
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["objective"] == 42
    assert data["path"] == ["S", "A", "T"]


def test_solve_networkx_optional():
    r = run([PY, str(TOOLS / "solve_ortools.py"), "shortest_path"])
    if r.returncode == 2:
        pytest.skip("networkx missing")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["objective"] == 42


def test_gate_schema_good():
    r = run([PY, str(TOOLS / "gate_schema.py"), str(TD / "good_schema.json")])
    assert r.returncode == 0, r.stderr


def test_gate_schema_bad():
    r = run([PY, str(TOOLS / "gate_schema.py"), str(TD / "bad_schema.json")])
    assert r.returncode == 1


def test_r2_good():
    r = run(
        [
            PY,
            str(TOOLS / "r2_numeric_check.py"),
            "--draft",
            str(TD / "good_draft.md"),
            "--solution",
            str(FIX / "solution.json"),
        ]
    )
    assert r.returncode == 0, r.stderr


def test_r2_bad():
    r = run(
        [
            PY,
            str(TOOLS / "r2_numeric_check.py"),
            "--draft",
            str(TD / "bad_draft.md"),
            "--solution",
            str(FIX / "solution.json"),
        ]
    )
    assert r.returncode == 1


def test_r1_good():
    r = run(
        [
            PY,
            str(TOOLS / "r1_cite_check.py"),
            "--draft",
            str(TD / "good_draft.md"),
            "--whitelist",
            str(FIX / "whitelist_refs.json"),
        ]
    )
    assert r.returncode == 0, r.stderr
