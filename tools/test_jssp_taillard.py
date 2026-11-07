"""Full-scale JSSP/FJSSP tests: Taillard benchmarks, setup times, Gantt charts.

Validates the PyJobShop-based industrial solver at tools/solve_jssp.py:
1. Backward compatibility (FT06 default = 55, 36 ops).
2. Taillard JSSP benchmarks match known optima (Numbers Truth).
3. FJSSP benchmarks (kacem / Brandimarte mk) match known optima.
4. Setup times (换模时延) are respected and independently re-verified.
5. Gantt chart generation produces a real PNG.
6. Dispatch integration for the ``fjssp`` alias.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from solve_jssp import solve_jssp, list_taillard_instances, load_taillard_instance
from solve_dispatch import solve
from validate_solution import validate

_ROOT = TOOLS.parent


# ---------------------------------------------------------------------------
# 1. Backward compatibility
# ---------------------------------------------------------------------------
def test_ft06_backward_compat():
    sol = solve_jssp()
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == 55
    assert len(sol["schedule"]) == 36
    assert sol["problem_class"] == "jssp"


def test_ft06_validate():
    sol = solve_jssp()
    rep = validate("jssp_ft06", sol)
    assert rep["ok"], f"Validation failed: {rep['errors']}"
    names = {c["name"] for c in rep["checks"]}
    assert {"job_precedence", "machine_no_overlap", "makespan_objective_match"} <= names


# ---------------------------------------------------------------------------
# 2. Taillard JSSP benchmarks
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name,gold",
    [
        ("ft06", 55),
        ("ft10", 930),
        ("la01", 666),
        ("la02", 655),
        ("la03", 597),
    ],
)
def test_taillard_jssp_known_optimum(name, gold):
    sol = solve_jssp(name, time_limit_s=20)
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert sol["objective"] == gold, f"{name}: got {sol['objective']} expected {gold}"
    assert sol["known_optimum"] == gold
    assert sol["optimality_gap"] == 0


def test_taillard_fixtures_present():
    names = list_taillard_instances("jssp")
    assert "ft06" in names and "la01" in names
    # 67 JSSP instances shipped
    assert len(names) >= 60


def test_taillard_instance_load():
    d = load_taillard_instance("la01")
    assert d["num_jobs"] == 10 and d["num_machines"] == 5
    assert d["known_optimum"] == 666
    assert len(d["jobs"]) == 10


# ---------------------------------------------------------------------------
# 3. FJSSP benchmarks
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name,gold",
    [
        ("kacem1", 11),
        ("mk01", 40),
    ],
)
def test_fjssp_known_optimum(name, gold):
    sol = solve_jssp(name, family="fjssp", time_limit_s=20)
    assert sol["problem_class"] == "fjssp"
    assert sol["objective"] == gold, f"{name}: got {sol['objective']} expected {gold}"
    assert sol["known_optimum"] == gold


def test_fjssp_fixtures_present():
    names = list_taillard_instances("fjssp")
    assert "kacem1" in names and "mk01" in names
    assert len(names) >= 400


# ---------------------------------------------------------------------------
# 4. Setup times (换模时延)
# ---------------------------------------------------------------------------
def test_setup_time_uniform_respected():
    sol = solve_jssp("ft06", time_limit_s=20, setup=3)
    assert sol["total_setup_time"] > 0
    rep = validate("jssp_ft06_setup", sol)
    assert rep["ok"], f"Validation failed: {rep['errors']}"
    names = {c["name"] for c in rep["checks"]}
    assert "setup_time_respected" in names
    assert "total_setup_time_match" in names


def test_setup_time_increases_makespan():
    plain = solve_jssp("ft06", time_limit_s=20)
    with_setup = solve_jssp("ft06", time_limit_s=20, setup=4)
    assert with_setup["objective"] > plain["objective"]


def test_setup_matrix_dict():
    # explicit setup only between op pair (0,1)
    setup = {(0, 1): 5}
    sol = solve_jssp("ft06", time_limit_s=20, setup=setup)
    assert sol["setup"] == setup
    rep = validate("jssp_ft06_matrix", sol)
    assert rep["ok"], f"Validation failed: {rep['errors']}"


# ---------------------------------------------------------------------------
# 5. Gantt chart generation
# ---------------------------------------------------------------------------
def test_gantt_chart_png(tmp_path):
    out = tmp_path / "ft06_gantt.png"
    sol = solve_jssp("ft06", time_limit_s=20, gantt_path=out)
    assert out.exists() and out.stat().st_size > 0
    assert sol["gantt_path"] == str(out)


def test_gantt_chart_fjssp_png(tmp_path):
    out = tmp_path / "kacem1_gantt.png"
    sol = solve_jssp("kacem1", family="fjssp", time_limit_s=20, gantt_path=out)
    assert out.exists() and out.stat().st_size > 0


# ---------------------------------------------------------------------------
# 6. Dispatch integration (fjssp alias → solve_jssp.py)
# ---------------------------------------------------------------------------
def test_dispatch_fjssp_alias():
    ok, sol, raw = solve(_ROOT, "fjssp_kacem1", mode="fjssp")
    assert ok, f"Dispatch failed: {raw}"
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")


def test_dispatch_jssp_alias():
    ok, sol, raw = solve(_ROOT, "jssp_ft06", mode="jssp")
    assert ok, f"Dispatch failed: {raw}"
    assert sol["objective"] == 55
