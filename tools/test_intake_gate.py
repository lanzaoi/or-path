"""OR-Path 1.1 intake gate unit tests (S1)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
PY = sys.executable
FIX = ROOT / "fixtures" / "intake"

sys.path.insert(0, str(TOOLS))
from gate_intake import (  # noqa: E402
    check_brief_text,
    check_intake_dict,
    check_intake_files,
    walk_forbidden_intake_keys,
)
from schema_models import (  # noqa: E402
    FORBIDDEN_SCHEMA_KEYS,
    IntakeArtifact,
    walk_forbidden_keys,
)


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True)


def test_walk_forbidden_intake_nested():
    data = {"meta": {"Objective": 1}, "nested": [{"Best_Cost": 3}]}
    found = walk_forbidden_intake_keys(data)
    assert "objective" in found
    assert "best_cost" in found


def test_walk_allows_path_under_sources_and_assets():
    data = {
        "sources": [{"path": "a.txt"}],
        "data_assets": [{"path": "b.csv", "kind": "csv"}],
        "brief_path": "notes/x.md",
    }
    assert walk_forbidden_intake_keys(data) == set()


def test_walk_forbids_top_level_path_answer():
    data = {"path": ["S", "T"], "sources": []}
    assert "path" in walk_forbidden_intake_keys(data)


def test_walk_schema_keys_unchanged_default():
    data = {"path": ["a"], "objective": 1}
    found = walk_forbidden_keys(data)
    assert "path" in found and "objective" in found
    assert found <= FORBIDDEN_SCHEMA_KEYS or "objective" in found


def test_ok_fixture_dict_and_files():
    path = FIX / "ok" / "intake.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    errs = check_intake_dict(data, min_subproblems=2)
    assert errs == [], errs
    errs2 = check_intake_files(path, min_subproblems=2)
    assert errs2 == [], errs2


def test_ok_cli_pass():
    r = run(
        [
            PY,
            str(TOOLS / "gate_intake.py"),
            str(FIX / "ok" / "intake.json"),
            "--min-subproblems",
            "2",
        ]
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "PASS" in r.stdout


def test_bad_objective_forbidden_keys():
    path = FIX / "bad_objective" / "intake.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    errs = check_intake_dict(data)
    assert any("forbidden key" in e and "objective" in e for e in errs), errs
    assert any("optimal" in e for e in errs), errs
    r = run(
        [
            PY,
            str(TOOLS / "gate_intake.py"),
            str(path),
            "--no-brief",
        ]
    )
    assert r.returncode == 1
    assert "forbidden" in (r.stderr + r.stdout).lower()


def test_bad_brief_answer_assertion():
    brief = (FIX / "bad_brief" / "problem-brief.md").read_text(encoding="utf-8")
    errs = check_brief_text(brief)
    assert any("solution assertion" in e for e in errs), errs
    r = run(
        [
            PY,
            str(TOOLS / "gate_intake.py"),
            str(FIX / "bad_brief" / "intake.json"),
        ]
    )
    assert r.returncode == 1
    assert "solution assertion" in (r.stderr + r.stdout).lower() or "objective=" in (
        r.stderr + r.stdout
    ).lower()


def test_needs_human_ok():
    path = FIX / "needs_human" / "intake.json"
    errs = check_intake_files(path)
    assert errs == [], errs


def test_ok_status_with_ambiguities_fails():
    data = json.loads((FIX / "ok" / "intake.json").read_text(encoding="utf-8"))
    data["ambiguities"] = ["page missing"]
    data["status"] = "ok"
    errs = check_intake_dict(data)
    assert any("needs_human" in e for e in errs), errs


def test_min_subproblems():
    data = json.loads((FIX / "ok" / "intake.json").read_text(encoding="utf-8"))
    errs = check_intake_dict(data, min_subproblems=5)
    assert any("min_subproblems" in e for e in errs), errs


def test_missing_field():
    errs = check_intake_dict({"slug": "x"})
    assert any("missing field" in e for e in errs)


def test_intake_artifact_pydantic_roundtrip():
    data = json.loads((FIX / "ok" / "intake.json").read_text(encoding="utf-8"))
    art = IntakeArtifact.model_validate(data)
    assert art.schema_version == "1.1.0"
    assert len(art.subproblems) == 2


def test_export_includes_intake(tmp_path: Path):
    from schema_models import export_json_schemas

    export_json_schemas(tmp_path)
    assert (tmp_path / "intake.json").is_file()
    schema = json.loads((tmp_path / "intake.json").read_text(encoding="utf-8"))
    assert "slug" in schema.get("properties", {}) or "title" in schema
