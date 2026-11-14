"""Unit tests for the LangChain Tools wrappers over ``tools/solve_dispatch.py``.

Covers the agent-facing surface in ``orpath/agents/tools_or.py``:

1. ``list_available_solvers``   — BaseTool + registered mode / family inventory
2. ``execute_or_solver``        — BaseTool + schema + real dispatch + failure path
3. ``validate_solution_tool``   — BaseTool + schema + real validation + tamper catch
4. ``execute_python_sandbox``   — BaseTool + schema + stdout / stderr / timeout capture
5. ``OR_TOOLS`` registry        — the bindable tool set

These tests exercise real solvers (NetworkX Dijkstra on a shipped fixture) and the
real validator, so they also guard the Numbers Truth contract: a tool never reports
an objective that ``validate_solution_tool`` cannot recompute.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langchain_core.tools import BaseTool  # noqa: E402

from orpath.agents.tools_or import (  # noqa: E402
    OR_TOOLS,
    SANDBOX_DEFAULT_TIMEOUT_SEC,
    SKILL_TOOLS,
    consult_or_skill,
    execute_or_solver,
    execute_python_sandbox,
    get_or_tools,
    get_problem_formulation_template,
    list_available_solvers,
    validate_solution_tool,
)
from tools.solve_dispatch import ADAPTER_SCRIPTS  # noqa: E402

# Modes the dispatcher must keep exposing (aliases collapse onto these families).
KNOWN_MODES = (
    "mock",
    "networkx",
    "cpsat",
    "highs",
    "ortools",
    "jssp",
    "bin_packing",
    "facility_location",
    "network_flow",
    "tube",
    "polyomino",
    "microgrid",
)

# Algorithm families the inventory must group by adapter.
KNOWN_FAMILIES = (
    "networkx",
    "cpsat",
    "highs",
    "ortools",
    "jssp",
    "binpack",
    "facility_location",
    "network_flow",
    "tube",
    "polyomino",
    "microgrid",
)

SHORTEST_PATH_SOLUTION = ROOT / "fixtures" / "t1" / "shortest_path" / "solution.json"


def _payload(tool: BaseTool, **kwargs: object) -> dict:
    """Invoke a tool and decode its JSON contract."""
    return json.loads(tool.invoke(kwargs))


def _assert_base_tool(
    tool: BaseTool,
    expected_fields: set[str],
    required_fields: set[str],
) -> None:
    assert isinstance(tool, BaseTool), f"{tool} is not a langchain BaseTool"
    assert isinstance(tool.name, str) and tool.name, "tool needs a name"
    assert isinstance(tool.description, str) and len(tool.description) > 30, (
        f"{tool.name} needs a description an agent can route on"
    )
    assert set(tool.args_schema.model_fields) == expected_fields, (
        f"{tool.name} args {sorted(tool.args_schema.model_fields)} != {sorted(expected_fields)}"
    )
    for field in required_fields:
        assert tool.args_schema.model_fields[field].is_required(), (
            f"{tool.name}.{field} should be required"
        )


# --------------------------------------------------------------------------- #
# 1. list_available_solvers
# --------------------------------------------------------------------------- #
def test_list_available_solvers_is_base_tool():
    _assert_base_tool(list_available_solvers, set(), set())


def test_list_available_solvers_reports_known_modes():
    payload = _payload(list_available_solvers)
    assert payload["success"] is True
    assert payload["total_modes"] == len(ADAPTER_SCRIPTS)
    for mode in KNOWN_MODES:
        assert mode in payload["modes"], f"missing registered mode {mode}"


def test_list_available_solvers_matches_dispatch_registry():
    """The advertised inventory must be exactly what the dispatcher routes."""
    payload = _payload(list_available_solvers)
    assert sorted(payload["modes"]) == sorted(ADAPTER_SCRIPTS)
    assert payload["total_modes"] == len(ADAPTER_SCRIPTS)


def test_list_available_solvers_groups_families_by_adapter():
    payload = _payload(list_available_solvers)
    families = {entry["family"]: entry for entry in payload["families"]}
    for family in KNOWN_FAMILIES:
        assert family in families, f"missing algorithm family {family}"
        entry = families[family]
        assert entry["modes"], f"{family} has no modes"
        assert entry["adapter"].startswith("solve_") and entry["adapter"].endswith(".py")
        assert entry["adapter_present"] is True, f"{entry['adapter']} not found under tools/"
    # every alias must land in exactly one family
    flattened = sorted(m for entry in payload["families"] for m in entry["modes"])
    assert flattened == sorted(payload["modes"])


# --------------------------------------------------------------------------- #
# 2. execute_or_solver
# --------------------------------------------------------------------------- #
def test_execute_or_solver_is_base_tool():
    _assert_base_tool(
        execute_or_solver,
        {"problem_id", "mode", "extra_args", "slug"},
        {"problem_id", "mode"},
    )


def test_execute_or_solver_runs_real_networkx_solve():
    payload = _payload(
        execute_or_solver, problem_id="shortest_path", mode="networkx"
    )
    assert payload["success"] is True, payload["detail"]
    solution = payload["solution"]
    assert solution["problem_class"] == "shortest_path"
    assert solution["status"] == "OPTIMAL"
    assert solution["objective"] == 42
    assert solution["path"] == ["S", "A", "T"]
    assert solution["meta"]["proven_optimal"] is True
    assert "networkx" in payload["detail"]


def test_execute_or_solver_forwards_extra_args():
    """extra_args is split on whitespace and handed to the adapter verbatim."""
    payload = _payload(
        execute_or_solver,
        problem_id="shortest_path",
        mode="networkx",
        extra_args="--source S --target T",
    )
    assert payload["success"] is True, payload["detail"]
    assert payload["solution"]["path"] == ["S", "A", "T"]


def test_execute_or_solver_normalizes_mode_case():
    payload = _payload(execute_or_solver, problem_id="shortest_path", mode="NetworkX")
    assert payload["success"] is True, payload["detail"]
    assert payload["mode"] == "networkx"


def test_execute_or_solver_reports_failure_without_inventing_objective():
    payload = _payload(
        execute_or_solver, problem_id="definitely_missing_fixture", mode="mock"
    )
    assert payload["success"] is False
    assert payload["solution"] == {}, "failed solve must not return a fabricated solution"
    assert payload["solution_path"] == "", "failed solve must not report a solution path"
    assert isinstance(payload["detail"], str) and payload["detail"].strip()


def test_execute_or_solver_persists_solution_with_explicit_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An explicit slug must land as outputs/<slug>-solution.json, content-equal."""
    monkeypatch.chdir(tmp_path)
    payload = _payload(
        execute_or_solver,
        problem_id="shortest_path",
        mode="networkx",
        slug="my-explicit-slug",
    )
    assert payload["success"] is True, payload["detail"]
    expected = Path("outputs") / "my-explicit-slug-solution.json"
    assert payload["solution_path"] == str(expected)
    assert expected.is_file(), f"expected {expected} to be written"
    persisted = json.loads(expected.read_text(encoding="utf-8"))
    assert persisted == payload["solution"], "persisted solution must equal returned solution"


def test_execute_or_solver_defaults_slug_to_problem_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A blank slug must fall back to problem_id for the output filename."""
    monkeypatch.chdir(tmp_path)
    payload = _payload(
        execute_or_solver,
        problem_id="shortest_path",
        mode="networkx",
        slug="",
    )
    assert payload["success"] is True, payload["detail"]
    expected = Path("outputs") / "shortest_path-solution.json"
    assert payload["solution_path"] == str(expected)
    assert expected.is_file(), f"expected {expected} to be written"
    assert json.loads(expected.read_text(encoding="utf-8")) == payload["solution"]


def test_execute_or_solver_default_slug_omitted_uses_problem_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Omitting slug entirely must behave like an empty slug."""
    monkeypatch.chdir(tmp_path)
    payload = _payload(execute_or_solver, problem_id="shortest_path", mode="networkx")
    assert payload["success"] is True, payload["detail"]
    expected = Path("outputs") / "shortest_path-solution.json"
    assert payload["solution_path"] == str(expected)
    assert expected.is_file()


# --------------------------------------------------------------------------- #
# 3. validate_solution_tool
# --------------------------------------------------------------------------- #
def test_validate_solution_tool_is_base_tool():
    _assert_base_tool(
        validate_solution_tool,
        {"problem_id", "solution_path", "output_path"},
        {"problem_id", "solution_path"},
    )


def test_validate_solution_tool_accepts_known_solution(tmp_path: Path):
    out = tmp_path / "validation.json"
    payload = _payload(
        validate_solution_tool,
        problem_id="shortest_path",
        solution_path=str(SHORTEST_PATH_SOLUTION),
        output_path=str(out),
    )
    assert payload["success"] is True and payload["ok"] is True, payload["detail"]
    report = payload["validation"]
    assert report["problem_class"] == "shortest_path"
    check_names = {c["name"] for c in report["checks"]}
    assert {"envelope", "feasibility", "recompute_objective"} <= check_names
    assert all(c["ok"] for c in report["checks"]), report["checks"]
    assert report["errors"] == []
    assert out.is_file(), "validation report should be written"
    assert json.loads(out.read_text(encoding="utf-8"))["ok"] is True


def test_validate_solution_tool_default_output_path(tmp_path: Path):
    """Default report lands next to the solution as <problem_id>-validation.json."""
    solution = tmp_path / "solution.json"
    shutil.copy(SHORTEST_PATH_SOLUTION, solution)
    payload = _payload(
        validate_solution_tool,
        problem_id="shortest_path",
        solution_path=str(solution),
    )
    assert payload["success"] is True, payload["detail"]
    expected = tmp_path / "shortest_path-validation.json"
    assert payload["output_path"] == str(expected)
    assert expected.is_file()


def test_validate_solution_tool_flags_tampered_objective(tmp_path: Path):
    solution = tmp_path / "solution.json"
    blob = json.loads(SHORTEST_PATH_SOLUTION.read_text(encoding="utf-8"))
    blob["objective"] = 9999
    solution.write_text(json.dumps(blob), encoding="utf-8")

    payload = _payload(
        validate_solution_tool,
        problem_id="shortest_path",
        solution_path=str(solution),
        output_path=str(tmp_path / "validation.json"),
    )
    assert payload["success"] is False and payload["ok"] is False
    failing = {c["name"] for c in payload["validation"]["checks"] if not c["ok"]}
    assert "recompute_objective" in failing, "tampered objective must be caught"
    assert payload["validation"]["errors"]


def test_validate_solution_tool_reports_missing_solution(tmp_path: Path):
    """A missing file must come back as a JSON failure, not a raised exception."""
    payload = _payload(
        validate_solution_tool,
        problem_id="shortest_path",
        solution_path=str(tmp_path / "nope.json"),
        output_path=str(tmp_path / "validation.json"),
    )
    assert payload["success"] is False and payload["ok"] is False
    assert payload["detail"].strip() or payload["validation"]


# --------------------------------------------------------------------------- #
# 4. execute_python_sandbox
# --------------------------------------------------------------------------- #
def test_execute_python_sandbox_is_base_tool():
    _assert_base_tool(
        execute_python_sandbox,
        {"code", "timeout_sec"},
        {"code"},
    )


def test_execute_python_sandbox_captures_stdout():
    payload = _payload(execute_python_sandbox, code="print('sandbox_ok')")
    assert payload["success"] is True
    assert payload["returncode"] == 0
    assert payload["stdout"].strip() == "sandbox_ok"
    assert payload["stderr"] == ""
    assert payload["timed_out"] is False


def test_execute_python_sandbox_captures_stderr_and_returncode():
    payload = _payload(
        execute_python_sandbox,
        code="import sys; print('oops', file=sys.stderr); sys.exit(3)",
    )
    assert payload["success"] is False
    assert payload["returncode"] == 3
    assert "oops" in payload["stderr"]


def test_execute_python_sandbox_honours_timeout():
    payload = _payload(
        execute_python_sandbox, code="import time; time.sleep(5)", timeout_sec=1
    )
    assert payload["success"] is False
    assert payload["timed_out"] is True
    assert payload["returncode"] is None


def test_execute_python_sandbox_default_timeout():
    payload = _payload(execute_python_sandbox, code="print('ok')")
    assert payload["timeout_sec"] == SANDBOX_DEFAULT_TIMEOUT_SEC == 180


@pytest.mark.parametrize("bad_timeout", [0, -5])
def test_execute_python_sandbox_rejects_bad_timeout(bad_timeout: int):
    payload = _payload(execute_python_sandbox, code="print('ok')", timeout_sec=bad_timeout)
    assert payload["success"] is False
    assert "timeout_sec" in payload["detail"]
    assert payload["stdout"] == "" and payload["timed_out"] is False


def test_execute_python_sandbox_schema_rejects_non_int_timeout():
    with pytest.raises((ValueError, TypeError)):
        execute_python_sandbox.invoke({"code": "print('ok')", "timeout_sec": "soon"})


def test_execute_python_sandbox_runs_real_modelling_code():
    """The sandbox is usable for exploratory OR modelling before a real solve."""
    payload = _payload(
        execute_python_sandbox,
        code=(  # absolute tools/ path: the sandbox inherits the caller cwd
            "import json, sys; sys.path.insert(0, %r);"
            "from solve_dispatch import list_adapters;"
            "print(json.dumps({'modes': len(list_adapters())}))" % str(TOOLS)
        ),
    )
    assert payload["success"] is True, payload["stderr"]
    assert json.loads(payload["stdout"])["modes"] == len(ADAPTER_SCRIPTS)


# --------------------------------------------------------------------------- #
# 5. OR_TOOLS registry
# --------------------------------------------------------------------------- #
def test_or_tools_registry_contains_all_four_tools():
    assert len(OR_TOOLS) == 4
    names = [t.name for t in OR_TOOLS]
    assert len(set(names)) == len(names), "tool names must be unique for binding"
    assert set(names) == {
        "list_available_solvers",
        "execute_or_solver",
        "validate_solution_tool",
        "execute_python_sandbox",
    }
    for tool in OR_TOOLS:
        assert isinstance(tool, BaseTool)


def test_get_or_tools_returns_mutable_copy():
    tools = get_or_tools()
    assert tools == list(OR_TOOLS)
    tools.pop()
    assert len(tools) == 3 and len(OR_TOOLS) == 4


def test_tools_are_directly_invokable_by_name():
    """Agents bind by name; each registry entry must survive a name-only lookup."""
    by_name = {t.name: t for t in OR_TOOLS}
    assert json.loads(by_name["list_available_solvers"].invoke({}))["success"] is True
    sandbox = json.loads(by_name["execute_python_sandbox"].invoke({"code": "print(1)"}))
    assert sandbox["success"] is True and sandbox["stdout"].strip() == "1"


# --------------------------------------------------------------------------- #
# 6. Case-dir resolution & auto-routing
# --------------------------------------------------------------------------- #
def test_find_case_dir_finds_problem_id_and_slug(tmp_path: Path):
    from tools.solve_dispatch import _find_case_dir

    inbox = tmp_path / "inbox"
    case_c = inbox / "Problem_C"
    case_c.mkdir(parents=True, exist_ok=True)

    found = _find_case_dir(tmp_path, "microgrid_cumcm2026_c")
    assert found == case_c.resolve()


def test_build_args_auto_routes_case_dir(tmp_path: Path):
    from tools.solve_dispatch import _build_args

    inbox = tmp_path / "inbox" / "microgrid"
    inbox.mkdir(parents=True, exist_ok=True)

    args = _build_args("microgrid", "microgrid", None, ["--out", "out.json"], root=tmp_path)
    assert "--case-dir" in args
    idx = args.index("--case-dir")
    assert args[idx + 1] == str(inbox.resolve())


def test_build_args_respects_explicit_case_dir(tmp_path: Path):
    from tools.solve_dispatch import _build_args

    inbox = tmp_path / "inbox" / "microgrid"
    inbox.mkdir(parents=True, exist_ok=True)
    custom_dir = tmp_path / "custom_data"

    args = _build_args(
        "microgrid",
        "microgrid",
        None,
        ["--case-dir", str(custom_dir)],
        root=tmp_path,
    )
    assert args.count("--case-dir") == 1
    idx = args.index("--case-dir")
    assert args[idx + 1] == str(custom_dir)


def test_find_case_dir_ignores_unrelated_short_names(tmp_path: Path):
    from tools.solve_dispatch import _find_case_dir

    inbox = tmp_path / "inbox"
    (inbox / "d").mkdir(parents=True)
    microgrid_dir = inbox / "microgrid_run"
    microgrid_dir.mkdir(parents=True)

    found = _find_case_dir(tmp_path, "microgrid")
    assert found == microgrid_dir.resolve(), f"expected microgrid_run but got {found}"


def test_find_case_dir_uses_mode_for_routing(tmp_path: Path):
    from tools.solve_dispatch import _find_case_dir

    inbox = tmp_path / "inbox"
    microgrid_dir = inbox / "microgrid"
    microgrid_dir.mkdir(parents=True)

    found = _find_case_dir(tmp_path, "c_dispatch", mode="microgrid")
    assert found == microgrid_dir.resolve()


# --------------------------------------------------------------------------- #
# 7. Skill Access & Problem Formulation Tools
# --------------------------------------------------------------------------- #
def test_consult_or_skill_is_base_tool():
    _assert_base_tool(
        consult_or_skill,
        {"topic", "subtopic"},
        {"topic"},
    )


def test_consult_or_skill_finds_routing_skill():
    payload = _payload(consult_or_skill, topic="routing")
    assert payload["success"] is True
    assert "skill_file" in payload
    assert "routing" in payload["skill_file"].lower() or "networks" in payload["skill_file"].lower() or "pyvrp" in payload["skill_file"].lower()
    assert len(payload["content"]) > 100


def test_consult_or_skill_with_subtopic():
    payload = _payload(consult_or_skill, topic="linear", subtopic="mip")
    assert payload["success"] is True
    assert "content" in payload and len(payload["content"]) > 0


def test_consult_or_skill_missing_topic_reports_available():
    payload = _payload(consult_or_skill, topic="quantum_teleportation_xyz")
    assert payload["success"] is False
    assert "available_skills" in payload
    assert len(payload["available_skills"]) > 0


def test_get_problem_formulation_template_is_base_tool():
    _assert_base_tool(
        get_problem_formulation_template,
        {"problem_class"},
        {"problem_class"},
    )


def test_get_problem_formulation_template_tsp():
    payload = _payload(get_problem_formulation_template, problem_class="tsp")
    assert payload["success"] is True
    assert "2.1" in payload["section_title"] or "TSP" in payload["section_title"]
    assert "latex_formulation" in payload
    assert r"\min" in payload["latex_formulation"] or r"\sum" in payload["latex_formulation"]
    assert len(payload["content"]) > 100


def test_get_problem_formulation_template_cvrp():
    payload = _payload(get_problem_formulation_template, problem_class="cvrp")
    assert payload["success"] is True
    assert "VRP" in payload["section_title"] or "2.2" in payload["section_title"]
    assert len(payload["latex_formulation"]) > 50


def test_get_problem_formulation_template_unknown_class():
    payload = _payload(get_problem_formulation_template, problem_class="unknown_fantasy_class")
    assert payload["success"] is False
    assert "supported_classes" in payload
    assert "tsp" in payload["supported_classes"]


def test_skill_tools_registry():
    assert len(SKILL_TOOLS) == 2
    assert {t.name for t in SKILL_TOOLS} == {
        "consult_or_skill",
        "get_problem_formulation_template",
    }



