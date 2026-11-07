#!/usr/bin/env python3
"""Unit tests for the deterministic pre/post nodes (Plan 1.4 acceptance).

Covers ``orpath/agents/deterministic_nodes.py``:

  * zero-LLM structural guarantee — the module must not reference any chat
    model / ReAct machinery (LLM tokens consumed: exactly 0);
  * front probe: SHA-256 fingerprinting of raw inputs, CSV/Excel/JSON row /
    column scale and field overview, ``outputs/<slug>-profile.json`` landing
    disk, deterministic domain guess + auto ``profile_<domain>_data`` run;
  * back gate: ``validate_artifact`` in-process seam and the
    ``tools.solve_dispatch.validate`` subprocess fallback, extraction of
    ``ok`` / ``recomputed_objective`` / ``proven_optimal`` / ``errors``;
  * tampered-objective detection (Numbers Truth);
  * timing acceptance: front probe & lightweight back gate ``< 0.5s`` per run.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import openpyxl  # noqa: E402

from orpath.agents import deterministic_nodes as dn  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _make_case(tmp_path: Path, slug: str = "case-x", with_data: bool = True) -> Path:
    inbox = tmp_path / "inbox" / slug
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "problem.md").write_text(
        "# 最短路 / Shortest Path\n给定有向加权图求 S 到 T 的最短路径。\n", encoding="utf-8"
    )
    if with_data:
        rows = ["src", "dst", "w"] + [f"n{i}" for i in range(4)]
        lines = [",".join(rows)]
        for r in range(1, 10):
            lines.append(",".join(str(r + i) for i in range(7)))
        (inbox / "edges.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (inbox / "meta.json").write_text(
            json.dumps({"vertices": ["S", "A", "T"], "weights": {"SA": 10}}), encoding="utf-8"
        )
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "plan"
        ws.append(["interval", "price"])
        for i in range(20):
            ws.append([i, 0.5 + i / 100])
        wb.save(inbox / "plan.xlsx")
    (tmp_path / "outputs").mkdir(exist_ok=True)
    (tmp_path / "notes").mkdir(exist_ok=True)
    return tmp_path


# --------------------------------------------------------------------------- #
# 1. zero-LLM structural guarantee
# --------------------------------------------------------------------------- #
def test_module_is_llm_free() -> None:
    import ast

    src = Path(dn.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert not (roots & {"langchain", "langgraph"}), f"LLM framework must not be imported: {roots}"
    assert "create_react_agent" not in src
    assert "get_chat_model" not in src
    assert not hasattr(dn, "get_chat_model")
    assert not hasattr(dn, "create_react_agent")


def test_domain_registry_shapes() -> None:
    profilers, inspectors = dn.domain_tool_registry()
    assert "scheduling" in profilers and "scheduling" in inspectors
    assert "routing" in profilers
    assert callable(profilers["portfolio"].invoke)


# --------------------------------------------------------------------------- #
# 2. front probe
# --------------------------------------------------------------------------- #
def test_preflight_profiles_inputs_with_sha256(tmp_path: Path) -> None:
    workdir = _make_case(tmp_path)
    csv_file = workdir / "inbox" / "case-x" / "edges.csv"
    expected_sha = hashlib.sha256(csv_file.read_bytes()).hexdigest()

    updates = dn.run_preflight_probe({"slug": "case-x", "workdir": str(workdir)})

    assert updates["preflight_ok"] is True
    assert updates["data_files"], "data_files pointers must be recorded"
    assert (workdir / "outputs" / "case-x-profile.json").is_file()

    profile = json.loads((workdir / "outputs" / "case-x-profile.json").read_text(encoding="utf-8"))
    files = {f["file"]: f for f in profile["input_files"]}
    manifest = files["inbox/case-x/edges.csv"]
    assert manifest["sha256"] == expected_sha
    assert manifest["rows"] == 10
    assert manifest["cols"] == 7
    assert manifest["fields"][0] == "src"
    xlsx = files["inbox/case-x/plan.xlsx"]
    assert "sheets" in xlsx and xlsx["sheets"]["plan"]["rows"] == 21  # header + 20
    js = files["inbox/case-x/meta.json"]
    assert js["top_level"] == "dict" and "vertices" in js["fields"]


def test_preflight_sets_pointer_state_and_summary(tmp_path: Path) -> None:
    workdir = _make_case(tmp_path)
    updates = dn.run_preflight_probe({"slug": "case-x", "workdir": str(workdir)})
    assert Path(updates["profile_path"]).is_file()
    assert "sha=" in updates["preflight_summary"]
    assert updates.get("last_error", "") == ""


def test_preflight_guesses_class_and_runs_domain_profiler(tmp_path: Path) -> None:
    workdir = _make_case(tmp_path, slug="scheduling_jssp_case")
    updates = dn.run_preflight_probe({"slug": "scheduling_jssp_case", "workdir": str(workdir)})
    assert updates["domain_cartridge"] == "scheduling"
    assert updates["problem_class"] == "jssp"
    profile = json.loads(Path(updates["profile_path"]).read_text(encoding="utf-8"))
    assert profile["domain_profile"], "scheduled domain profiler must auto-run"
    # ft06 fixtures ship in-tree, so the profiler resolves offline
    assert profile["summary"]["guessed_domain"] == "scheduling"


def test_preflight_skips_harness_dirs(tmp_path: Path) -> None:
    workdir = _make_case(tmp_path, slug="clean-case", with_data=False)
    (workdir / "outputs" / "noise.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (workdir / "notes" / "note.txt").write_text("x", encoding="utf-8")
    updates = dn.run_preflight_probe({"slug": "clean-case", "workdir": str(workdir)})
    profile = json.loads(Path(updates["profile_path"]).read_text(encoding="utf-8"))
    found = " ".join(f["file"] for f in profile["input_files"])
    assert "outputs/noise.csv" not in found
    assert "notes/note.txt" not in found
    assert "problem.md" in found


def test_preflight_timing_under_half_second(tmp_path: Path) -> None:
    workdir = _make_case(tmp_path)
    t0 = time.perf_counter()
    updates = dn.run_preflight_probe({"slug": "case-x", "workdir": str(workdir)})
    elapsed = time.perf_counter() - t0
    assert updates["preflight_ok"] is True
    assert elapsed < 0.5, f"front probe took {elapsed:.3f}s, budget is 0.5s"


def test_preflight_failure_reports_instead_of_raising(tmp_path: Path) -> None:
    updates = dn.run_preflight_probe({"slug": "ghost", "workdir": str(tmp_path / "nope")})
    assert updates["preflight_ok"] is False
    assert "preflight failed" in updates.get("last_error", "")

    empty = tmp_path / "empty-case"
    empty.mkdir()
    updates2 = dn.run_preflight_probe({"slug": "ghost", "workdir": str(empty)})
    assert updates2["preflight_ok"] is False
    assert "no input files" in updates2.get("last_error", "")


def test_collect_input_files_explicit_and_missing(tmp_path: Path) -> None:
    workdir = _make_case(tmp_path)
    files, notes = dn.collect_input_files(workdir, "case-x", ["missing.csv"])
    names = " ".join(str(f) for f in files)
    assert "edges.csv" in names
    assert "missing.csv" not in names


# --------------------------------------------------------------------------- #
# 3. back gate validator
# --------------------------------------------------------------------------- #
def _solution_copy(tmp_path: Path, problem_id: str = "shortest_path") -> Path:
    src = ROOT / "fixtures" / "t1" / "shortest_path" / "solution.json"
    dst = tmp_path / f"{problem_id}-solution.json"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def test_validator_extracts_verdict_and_writes_out(tmp_path: Path) -> None:
    sol = _solution_copy(tmp_path)
    t0 = time.perf_counter()
    updates = dn.run_deterministic_validator(
        {"slug": "sp-a", "workdir": str(tmp_path), "problem_id": "shortest_path", "solution_path": str(sol)}
    )
    elapsed = time.perf_counter() - t0
    assert updates["validation_ok"] is True
    assert updates["proven_optimal"] is True
    assert updates["objective_value"] == 42
    assert updates["recomputed_objective"] == 42
    assert updates["validator_errors"] == []
    out = Path(updates["validate_path"])
    assert out.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["ok"] is True
    assert elapsed < 0.5, f"lightweight back gate took {elapsed:.3f}s, budget is 0.5s"


def test_validator_detects_tampered_objective(tmp_path: Path) -> None:
    sol = _solution_copy(tmp_path)
    payload = json.loads(sol.read_text(encoding="utf-8"))
    payload["objective"] = 999
    sol.write_text(json.dumps(payload), encoding="utf-8")

    updates = dn.run_deterministic_validator(
        {"slug": "sp-bad", "workdir": str(tmp_path), "problem_id": "shortest_path", "solution_path": str(sol)}
    )
    assert updates["validation_ok"] is False
    assert any("recompute_objective" in e for e in updates["validator_errors"])
    assert updates["objective_value"] == 999
    assert updates["recomputed_objective"] == 42.0  # truth comes from recomputation, not the claim
    assert updates["last_error"]


def test_validator_subprocess_seam_fallback_equivalence(tmp_path: Path) -> None:
    sol = _solution_copy(tmp_path)
    ok1, data1, _ = dn.validate_artifact(tmp_path, "shortest_path", sol, tmp_path / "v1.json", in_process=True)
    t0 = time.perf_counter()
    ok2, data2, _ = dn.validate_artifact(tmp_path, "shortest_path", sol, tmp_path / "v2.json", in_process=False)
    elapsed = time.perf_counter() - t0
    assert ok1 is ok2 is True
    assert data1["ok"] == data2["ok"]
    assert elapsed < 2.0, f"subprocess dispatch seam took {elapsed:.3f}s"


def test_validator_missing_solution_reports(tmp_path: Path) -> None:
    updates = dn.run_deterministic_validator(
        {"slug": "sp-none", "workdir": str(tmp_path), "problem_id": "shortest_path", "solution_path": str(tmp_path / "nope.json")}
    )
    assert updates["validation_ok"] is False
    assert "not found" in updates["last_error"]


def test_validator_absent_solution_path_reports(tmp_path: Path) -> None:
    updates = dn.run_deterministic_validator({"slug": "sp", "workdir": str(tmp_path)})
    assert updates["validation_ok"] is False
    assert "missing solution_path" in updates["validator_errors"]


def test_validator_microgrid_heavy_case_end_to_end(tmp_path: Path) -> None:
    """Heavy simulation-backed case (excluded from the 0.5s budget by design)."""
    sol = ROOT / "outputs" / "cumcm2026_c-solution.json"
    slug = "cumcm2026_c_heavy"
    updates = dn.run_deterministic_validator(
        {"slug": slug, "workdir": str(tmp_path), "problem_id": "microgrid_cumcm2026_c", "solution_path": str(sol)}
    )
    assert updates["validation_ok"] is True
    assert updates["objective_value"] is not None
    assert abs(updates["objective_value"] - 35126.9486) < 0.01


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
