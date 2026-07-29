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
    r = run([PY, str(TOOLS / "solve_networkx.py"), "shortest_path"])
    if r.returncode == 2:
        pytest.skip("networkx missing")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["objective"] == 42


def test_solve_ortools_tsp():
    r = run([PY, str(TOOLS / "solve_ortools.py"), "tsp_n8", "--class", "tsp"])
    if r.returncode == 2:
        pytest.skip("ortools missing")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["problem_class"] == "tsp"
    assert data.get("tour")
    assert data["status"] in {"OPTIMAL", "FEASIBLE"}
    assert data.get("meta", {}).get("exact") is False
    assert data.get("meta", {}).get("proven_optimal") is False


def test_solve_cpsat_tsp_exact():
    r = run([PY, str(TOOLS / "solve_cpsat.py"), "tsp_n8"])
    if r.returncode == 2:
        pytest.skip("ortools cpsat missing")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["status"] == "OPTIMAL"
    assert data["objective"] == 45
    assert data.get("meta", {}).get("exact") is True
    assert data.get("meta", {}).get("proven_optimal") is True


def test_solve_highs_tsp_exact():
    r = run([PY, str(TOOLS / "solve_highs.py"), "tsp_n8"])
    if r.returncode == 2:
        pytest.skip("highspy missing")
    assert r.returncode == 0, r.stderr + r.stdout
    data = json.loads(r.stdout)
    assert data["status"] in {"OPTIMAL", "FEASIBLE"}
    assert data["objective"] == 45
    assert data.get("meta", {}).get("exact") is True


def test_validate_tsp_gold():
    sol = ROOT / "fixtures" / "t2" / "tsp_n8" / "solution.json"
    r = run(
        [
            PY,
            str(TOOLS / "validate_solution.py"),
            "--problem-id",
            "tsp_n8",
            "--solution",
            str(sol),
        ]
    )
    assert r.returncode == 0, r.stderr + r.stdout


def test_validate_vrp_gold():
    sol = ROOT / "fixtures" / "t2" / "vrp_multi" / "solution.json"
    r = run(
        [
            PY,
            str(TOOLS / "validate_solution.py"),
            "--problem-id",
            "vrp_multi",
            "--solution",
            str(sol),
        ]
    )
    assert r.returncode == 0, r.stderr + r.stdout


def test_solve_ortools_vrp_tw():
    r = run(
        [
            PY,
            str(TOOLS / "solve_ortools.py"),
            "vrp_tw",
            "--class",
            "vrp",
            "--time-limit-ms",
            "8000",
        ]
    )
    if r.returncode == 2:
        pytest.skip("ortools missing")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["problem_class"] == "vrp"
    assert data.get("routes")
    assert data["status"] in {"OPTIMAL", "FEASIBLE"}
    assert data.get("meta", {}).get("has_time_windows") is True
    assert data["objective"] == 58
    assert data.get("meta", {}).get("exact") is False


def test_validate_vrp_tw_gold():
    sol = ROOT / "fixtures" / "t3" / "vrp_tw" / "solution.json"
    r = run(
        [
            PY,
            str(TOOLS / "validate_solution.py"),
            "--problem-id",
            "vrp_tw",
            "--solution",
            str(sol),
        ]
    )
    assert r.returncode == 0, r.stderr + r.stdout
    report = json.loads(r.stdout)
    tw = [c for c in report["checks"] if c["name"] == "time_windows"]
    assert tw and tw[0]["ok"]


def test_gate_schema_forbids_path_key():
    p = TD / "schema_with_path.json"
    p.write_text(
        json.dumps(
            {
                "problem_id": "shortest_path",
                "problem_class": "shortest_path",
                "nodes": ["S", "T"],
                "path": ["S", "T"],
            }
        ),
        encoding="utf-8",
    )
    r = run([PY, str(TOOLS / "gate_schema.py"), str(p)])
    assert r.returncode == 1


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
