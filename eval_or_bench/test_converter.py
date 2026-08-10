#!/usr/bin/env python3
"""Comprehensive Verification Tests for M1 TSPLIB Benchmark Converter & Fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.schema_models import ProblemSchema, walk_forbidden_keys, FORBIDDEN_SCHEMA_KEYS
from tools.fixture_paths import fixture_dir
from tools.validate_solution import validate
from tools.solve_dispatch import solve

INSTANCES = [
    "burma14",
    "ulysses16",
    "gr17",
    "bayg29",
    "swiss42",
    "att48",
    "eil51",
    "kroA100",
]


def test_instances_exist_and_locatable():
    """Verify all 8 selected TSPLIB instances are locatable via fixture_dir."""
    for inst in INSTANCES:
        d = fixture_dir(inst)
        assert d.is_dir(), f"Fixture directory for {inst} not found"
        assert (d / "distance_matrix.json").is_file(), f"distance_matrix.json missing for {inst}"


def test_schema_compliance_and_forbidden_keys():
    """Verify ProblemSchema validation and zero forbidden key violations."""
    for inst in INSTANCES:
        d = fixture_dir(inst)
        dist_path = d / "distance_matrix.json"
        dist_data = json.loads(dist_path.read_text(encoding="utf-8"))

        # 1. Forbidden Key Scan
        forbidden = walk_forbidden_keys(dist_data)
        assert not forbidden, f"Forbidden keys {forbidden} found in {dist_path}"

        coords_data = None
        coords_path = d / "coords.json"
        if coords_path.is_file():
            coords_data = json.loads(coords_path.read_text(encoding="utf-8"))
            forbidden_coords = walk_forbidden_keys(coords_data)
            assert not forbidden_coords, f"Forbidden keys {forbidden_coords} found in {coords_path}"

        # 2. ProblemSchema Pydantic Validation
        matrix = dist_data.get("matrix")
        coords = coords_data.get("coords") if coords_data else None
        schema_obj = ProblemSchema(
            problem_id=inst,
            problem_class="tsp",
            distance_matrix=matrix,
            coords=coords,
        )
        assert schema_obj.problem_id == inst
        assert schema_obj.problem_class.value == "tsp"


def test_validate_solution_recomputation_burma14(tmp_path: Path):
    """Test validate_solution.py recomputes objectives correctly on burma14."""
    d = fixture_dir("burma14")
    raw = json.loads((d / "distance_matrix.json").read_text(encoding="utf-8"))
    matrix = raw["matrix"]
    labels = raw["labels"]

    # Simple tour 0 -> 1 -> ... -> 13 -> 0
    tour = labels + [labels[0]]
    total = sum(matrix[int(a)][int(b)] for a, b in zip(tour, tour[1:]))

    sol_dict = {
        "problem_id": "burma14",
        "problem_class": "tsp",
        "status": "FEASIBLE",
        "objective": total,
        "solver": "test_solver",
        "source": "test_source",
        "tour": tour,
        "meta": {"exact": False},
    }

    report = validate("burma14", sol_dict)
    assert report["ok"] is True, f"Validation report failed for burma14: {report}"
    recompute_check = next((c for c in report["checks"] if c["name"] == "recompute_objective"), None)
    assert recompute_check is not None
    assert recompute_check["ok"] is True


def test_solve_and_validate_burma14_cpsat():
    """Run CP-SAT solver on burma14 and verify it reaches mathematical optimum."""
    ok, sol, raw = solve(_REPO_ROOT, "burma14", mode="cpsat", problem_class="tsp")
    assert ok is True, f"solve_dispatch burma14 failed: {raw}"
    assert sol["status"] == "OPTIMAL"
    assert int(sol["objective"]) == 3323

    report = validate("burma14", sol)
    assert report["ok"] is True, f"Validation report failed for burma14 solution: {report}"


def test_solve_all_instances_literature_optima():
    """Verify solver runs on converted fixtures yield exact literature optimal costs for ALL 8 instances."""
    from eval_or_bench.tsplib_converter import KNOWN_OPTIMAL_REFS

    for inst in INSTANCES:
        expected_opt = KNOWN_OPTIMAL_REFS[inst]["optimal_value"]
        ok, sol, raw = solve(_REPO_ROOT, inst, mode="cpsat", problem_class="tsp")
        assert ok is True, f"solve_dispatch failed on {inst}: {raw}"
        assert sol["status"] == "OPTIMAL", f"Solver status on {inst} was {sol.get('status')}"
        achieved_obj = int(sol["objective"])
        assert achieved_obj == expected_opt, f"Objective mismatch on {inst}: got {achieved_obj}, expected {expected_opt}"

