#!/usr/bin/env python3
"""Phase 3.3 acceptance — custom MIP sandbox closed loop.

Coverage:

  * a custom resource-allocation MIP instance (no registered adapter) is
    solved end-to-end by the deterministic sandbox: generated solver script
    ``outputs/<slug>-custom-solver.py`` (OR-Tools CP-SAT) produces the exact
    optimum; the generated validator script ``outputs/<slug>-custom-validate.py``
    recomputes objective & constraints **strictly from raw instance data**
    (no solver imports — asserted by source inspection);
  * the solution envelope passes ``validate_artifact`` (envelope closure +
    validation_report + recompute_objective agreement);
  * tamper rejection: corrupting a solution value fails independent recompute;
  * the adaptive-graph wiring (Phase 3.3 protocol in node_modeler brief +
    general_or toolset mounted on the modeler) is asserted offline.

Run:
    .venv/bin/python tools/test_phase3_custom_mip.py -q -p no:langsmith
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("ORPATH_LIVE_SUBAGENT", "0")
os.environ.setdefault("ORPATH_KNOWLEDGE_MODE", "off")

import pytest  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore")

from orpath.agents.custom_mip import (  # noqa: E402
    build_solver_script,
    build_validator_script,
    custom_mip_solve,
    parse_linear,
)
from orpath.agents.deterministic_nodes import validate_artifact  # noqa: E402

#: resource allocation: min 2x + 3y s.t. 2x+y <= 10, x+2y >= 8, 0 <= x,y <= 8.
INSTANCE = {
    "problem_id": "custom_res_alloc",
    "slug": "custom-res-alloc",
    "decision_vars": [
        {"id": "x", "kind": "int", "domain": [0, 8]},
        {"id": "y", "kind": "int", "domain": [0, 8]},
    ],
    "objective": {"sense": "min", "coeffs": {"x": 2.0, "y": 3.0}},
    "constraints": [
        {"id": "c1", "lhs": "2*x + y", "op": "<=", "rhs": 10.0},
        {"id": "c2", "lhs": "x + 2*y", "op": ">=", "rhs": 8.0},
    ],
}
#: true optimum: min 2x+3y with 2x+y<=10 & x+2y>=8 → x=0,y=4 → 12
EXPECTED_OBJECTIVE = 12.0
EXPECTED_VALUES = {"x": 0, "y": 4}


def _make_instance(tmp: Path) -> Path:
    case = tmp / "inbox" / "custom-res-alloc"
    case.mkdir(parents=True, exist_ok=True)
    path = case / "instance.json"
    path.write_text(json.dumps(INSTANCE, ensure_ascii=False), encoding="utf-8")
    return path


def test_parse_linear() -> None:
    assert parse_linear("2*x + y - 3") == {"x": 2.0, "y": 1.0, "__const__": -3.0}
    assert parse_linear("x") == {"x": 1.0}
    assert parse_linear("-4.5*q") == {"q": -4.5}


def test_custom_mip_sandbox_solves_exact_optimum() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="phase33-solve-"))
    inst_path = _make_instance(tmp)
    out = custom_mip_solve(instance_path=inst_path, out_dir=tmp / "outputs")
    assert out["ok"], out.get("error")
    assert out["status"] == "OPTIMAL"
    assert out["objective"] == pytest.approx(EXPECTED_OBJECTIVE)
    assert out["values"] == EXPECTED_VALUES
    # artifacts on disk
    assert Path(out["solver_script"]).is_file()
    assert Path(out["validator_script"]).is_file()
    assert Path(out["solution_path"]).is_file()
    assert (tmp / "outputs" / "custom-res-alloc-custom-validate.json").is_file()


def test_validator_script_independent_of_solver() -> None:
    """The generated validator must not import solver variables."""
    src = build_validator_script(INSTANCE)
    assert "cp_model" not in src and "ortools" not in src
    assert "CUSTOM_MIP_OUT_DIR" in src
    # the solver script must be self-contained CP-SAT
    sol_src = build_solver_script(INSTANCE)
    assert "cp_model" in sol_src and "from ortools.sat.python import cp_model" in sol_src


def test_solution_passes_independent_validation() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="phase33-val-"))
    inst_path = _make_instance(tmp)
    out = custom_mip_solve(instance_path=inst_path, out_dir=tmp / "outputs")
    assert out["ok"]
    ok, rep, raw = validate_artifact(
        tmp, "custom_res_alloc", Path(out["solution_path"]),
        tmp / "outputs" / "custom-validate.json",
    )
    assert ok, rep
    recov = [c.get("expected") for c in rep.get("checks", []) if c.get("name") == "recompute_objective"]
    assert recov and recov[0] is not None
    names = {c["name"] for c in rep.get("checks", [])}
    assert {"envelope", "validation_report", "recompute_objective"} <= names


def test_tampered_solution_rejected_by_recompute() -> None:
    """A doctored objective must fail the independent recomputation check."""
    tmp = Path(tempfile.mkdtemp(prefix="phase33-tamper-"))
    inst_path = _make_instance(tmp)
    out = custom_mip_solve(instance_path=inst_path, out_dir=tmp / "outputs")
    assert out["ok"]
    # tamper: claim objective 100 instead of 12
    sol_path = Path(out["solution_path"])
    sol = json.loads(sol_path.read_text(encoding="utf-8"))
    sol["objective"] = 100.0
    sol_path.write_text(json.dumps(sol, ensure_ascii=False), encoding="utf-8")
    ok, rep, raw = validate_artifact(
        tmp, "custom_res_alloc", sol_path, tmp / "outputs" / "custom-tamper.json"
    )
    assert not ok
    failed = [c["name"] for c in rep.get("checks", []) if not c.get("ok")]
    assert "recompute_objective" in failed


def test_adaptive_graph_wires_general_or_protocol() -> None:
    """Phase 3.3 wiring: node_modeler brief carries the custom-MIP protocol."""
    src = (ROOT / "orpath" / "agents" / "adaptive_graph.py").read_text(encoding="utf-8")
    assert "general_or" in src
    assert "custom_solver.py" in src
    assert "get_problem_formulation_template" in src
    assert "GENERAL_OR_TOOLS" in src
    # tools_or exposes the script authoring/execution tools
    from orpath.agents.tools_or import (
        GENERAL_OR_TOOLS,
        execute_custom_script,
        write_custom_solver_script,
    )
    names = {t.name for t in GENERAL_OR_TOOLS}
    assert {"get_problem_formulation_template", "consult_or_skill",
            "write_custom_solver_script", "execute_custom_script",
            "validate_solution_tool"} <= names
    assert write_custom_solver_script.name == "write_custom_solver_script"
    assert execute_custom_script.name == "execute_custom_script"


def test_validate_solution_custom_branch_signature() -> None:
    """validate() accepts the optional solution_path used by the custom branch."""
    import inspect

    from validate_solution import validate as vs_validate

    sig = inspect.signature(vs_validate)
    assert "solution_path" in sig.parameters
    assert sig.parameters["solution_path"].default is None


def test_unknown_custom_mip_without_validator_report_fails_honestly() -> None:
    """An envelope without a validation_report must NOT pass the gate."""
    tmp = Path(tempfile.mkdtemp(prefix="phase33-noreport-"))
    out_dir = tmp / "outputs"
    out_dir.mkdir(parents=True)
    sol = {
        "problem_id": "custom_res_alloc",
        "problem_class": "custom_mip",
        "slug": "custom-res-alloc",
        "status": "OPTIMAL",
        "objective": 12.0,
        "solver": "x",
        "source": "y",
        "values": {"x": 0, "y": 4},
    }
    sol_path = out_dir / "custom-res-alloc-solution.json"
    sol_path.write_text(json.dumps(sol), encoding="utf-8")
    ok, rep, raw = validate_artifact(tmp, "custom_res_alloc", sol_path, out_dir / "v.json")
    assert not ok
    failed = [c["name"] for c in rep.get("checks", []) if not c.get("ok")]
    assert "validation_report" in failed
