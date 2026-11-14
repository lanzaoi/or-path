"""Unit tests for the unified Deep Mode isolated pipeline (``orpath/agents/adaptive_graph.py`` & ``callbacks.py``)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import get_type_hints

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402
from langgraph.graph.state import CompiledStateGraph, StateGraph  # noqa: E402

from orpath.agents.adaptive_graph import (  # noqa: E402
    ISOLATED_PIPELINE_NODES,
    MultiAgentPipelineState,
    _after_reviewer,
    _after_table_render,
    _after_validator,
    build_compiled_isolated_pipeline,
    build_isolated_pipeline_graph,
    run_deterministic_doc_gate,
)
from orpath.agents.callbacks import (  # noqa: E402
    get_default_supervisor_checkpointer,
    persist_agent_stage_log,
)
from orpath.agents.deterministic_nodes import run_deterministic_validator  # noqa: E402


def test_supervisor_module_retired() -> None:
    assert not (ROOT / "orpath" / "agents" / "supervisor.py").exists()


def test_isolated_pipeline_graph_nodes_and_topology() -> None:
    graph = build_isolated_pipeline_graph()
    assert isinstance(graph, StateGraph)
    compiled = build_compiled_isolated_pipeline()
    assert isinstance(compiled, CompiledStateGraph)
    for node in ISOLATED_PIPELINE_NODES:
        assert node in compiled.nodes


def test_isolated_pipeline_state_fields() -> None:
    hints = get_type_hints(MultiAgentPipelineState)
    for expected in (
        "slug",
        "workdir",
        "problem_id",
        "problem_class",
        "research_path",
        "solution_path",
        "validate_path",
        "paper_path",
        "review_path",
        "lifecycle_status",
        "validation_ok",
        "review_verdict",
        "fatal_defects",
        "revision_count",
        "max_revisions",
        "model_repair_count",
        "max_model_repairs",
        "tournament_path",
        "winning_track",
        "cosplay_quarantined",
    ):
        assert expected in hints, f"MultiAgentPipelineState missing field: {expected}"


def test_isolated_pipeline_checkpointer() -> None:
    saver = MemorySaver()
    compiled = build_compiled_isolated_pipeline(checkpointer=saver)
    assert getattr(compiled, "checkpointer", None) is saver
    assert isinstance(get_default_supervisor_checkpointer(), MemorySaver)


def test_persist_agent_stage_log_writes_full_jsonl(tmp_path: Path) -> None:
    huge = "X" * 5000
    log_p = persist_agent_stage_log(tmp_path, "demo_slug", "modeler_stage", [{"text": huge}])
    assert log_p.is_file()
    raw = log_p.read_text(encoding="utf-8")
    assert huge in raw


def test_isolated_verification_and_skip_paper_routing() -> None:
    assert _after_validator({"validation_ok": True}) == "table_render"
    assert _after_table_render({"tables_path": "outputs/x-tables.md"}) == "writer"
    assert _after_table_render({"tables_path": "outputs/x-tables.md", "skip_paper": True}) == "END_H"
    assert (
        _after_validator({"validation_ok": False, "model_retry_count": 0, "max_retries": 2})
        == "modeler"
    )
    assert (
        _after_validator({"validation_ok": False, "model_retry_count": 2, "max_retries": 2})
        == "fail_closed"
    )


def test_isolated_review_backtracking_to_writer() -> None:
    assert _after_reviewer({"fatal_defects": []}) == "END_H"

    state_writer = {
        "review_verdict": "REVISE",
        "fatal_defects": ["FATAL: Missing mandatory section ## 数学规划模型建立"],
        "paper_retry_count": 0,
        "max_retries": 2,
    }
    assert _after_reviewer(state_writer) == "writer"

    state_exhausted = {
        "review_verdict": "REVISE",
        "fatal_defects": ["FATAL: Optimality hype unproven"],
        "paper_retry_count": 2,
        "max_retries": 2,
    }
    assert _after_reviewer(state_exhausted) == "fail_closed"


def test_package_reexports_isolated_pipeline() -> None:
    import orpath.agents as agents

    assert hasattr(agents, "build_isolated_pipeline_graph")
    assert hasattr(agents, "build_compiled_isolated_pipeline")
    assert hasattr(agents, "MultiAgentPipelineState")
    assert hasattr(agents, "ISOLATED_PIPELINE_NODES")
    assert not hasattr(agents, "SUPERVISOR_MAX_MESSAGE_CHARS")


def test_isolated_verifier_failure_marks_failed(tmp_path: Path) -> None:
    res = run_deterministic_validator(
        {
            "workdir": str(tmp_path),
            "slug": "test_task",
            "solution_path": str(tmp_path / "nonexistent.json"),
        }
    )
    assert res["validation_ok"] is False
    assert "solution not found" in res["last_error"]


def test_isolated_doc_gate_catches_unproven_optimality(tmp_path: Path) -> None:
    paper_p = tmp_path / "papers" / "opt_test.md"
    paper_p.parent.mkdir(parents=True, exist_ok=True)
    paper_p.write_text(
        "# 摘要\n目标值 42.0，全局最优解。\n"
        "## 问题重述与建模假设\n## 数学规划模型建立\n## 求解策略与算子选型\n"
        "## 数值计算结果与敏感性分析\n## 模型评价、优缺点与工业落地建议\n",
        encoding="utf-8",
    )
    gate_res = run_deterministic_doc_gate(
        {
            "workdir": str(tmp_path),
            "slug": "opt_test",
            "paper_path": str(paper_p),
            "objective_value": 42.0,
            "proven_optimal": False,
        }
    )
    assert gate_res["doc_gate_ok"] is False
    assert any("全局最优" in d for d in gate_res["doc_gate_errors"])


def test_node_solve_reuses_multiagent_solution(tmp_path: Path) -> None:
    from orpath.pipeline.solve import node_solve

    out_dir = tmp_path / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    sol_p = out_dir / "custom_task-solution.json"
    sol_p.write_text(
        json.dumps(
            {
                "status": "FEASIBLE",
                "objective": 123.45,
                "solver": "custom_cp_sat",
            }
        ),
        encoding="utf-8",
    )

    state = {
        "workdir": str(tmp_path),
        "slug": "custom_task",
        "problem_id": "custom_p1",
        "problem_class": "custom_unregistered_class",
        "solve_mode": "auto",
        "gate_subagent_ok": True,
        "solution_path": str(sol_p),
    }

    res = node_solve(state)
    assert res["stage"] == "gate_validate"
    assert res["solution_path"] == str(sol_p)
    saved = json.loads(sol_p.read_text(encoding="utf-8"))
    assert saved["objective"] == 123.45
    assert saved["solver"] == "custom_cp_sat"


def test_node_revise_or_done_routes_to_draft_paper_on_fatal(tmp_path: Path) -> None:
    from orpath.pipeline.paper import node_revise_or_done

    out_dir = tmp_path / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    sol_p = out_dir / "rev_test-solution.json"
    sol_p.write_text(
        json.dumps({"status": "FEASIBLE", "objective": 10.0, "meta": {"proven_optimal": False}}),
        encoding="utf-8",
    )

    paper_p = tmp_path / "papers" / "rev_test.md"
    paper_p.parent.mkdir(parents=True, exist_ok=True)
    paper_p.write_text("# Paper\nSome draft", encoding="utf-8")

    state = {
        "workdir": str(tmp_path),
        "slug": "rev_test",
        "problem_id": "rev_test",
        "paper_path": str(paper_p),
        "solution_path": str(sol_p),
        "gate_r1_ok": False,
        "gate_r2_ok": False,
        "gate_claim_ok": False,
        "review_fatal": 1,
        "revise_count": 0,
        "max_revise": 2,
    }

    res = node_revise_or_done(state)
    assert res["stage"] == "draft_paper"
    assert res["revise_count"] == 1
