#!/usr/bin/env python3
"""End-to-end parity tests for v0.3.6-grade Multi-Agent DEEP Mode (Phase 3BCD).

Validates the five parity upgrades unified onto ``orpath/agents/adaptive_graph.py``:
  1. Empowered ``or_writer`` & ``or_reviewer`` tool mounting + dynamic post-preflight
     ``DomainCartridge`` resolution for ``or_modeler``;
  2. Unconditional Dual-Track Modeler Horse-Racing (Track A exact/reduction vs
     Track B bound/heuristic) with deterministic tournament adjudication and
     cheater disqualification;
  3. Anti-Cosplay firewall (``.cosplay-quarantine`` + escalating ``RETRY`` prompts)
     blocking schema solution leaks and tool-free hallucinated solutions;
  4. ``skip_paper=True`` early stop at ``table_render`` + ``process_memory``
     retrieve/auto-draft wiring + per-stage JSONL traces under ``runs/<slug>/agent_logs/``;
  5. ``orpath.pipeline.solve._run_isolated_pipeline`` routing through the unified
     adaptive Deep Mode engine with offline ``live_subagent=False`` safety.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore:create_react_agent has been moved")

from orpath.agents.adaptive_graph import (  # noqa: E402
    _build_dynamic_role_agent,
    build_adaptive_graph,
)
from orpath.agents.workers import (  # noqa: E402
    create_reviewer_agent,
    create_writer_agent,
)
from orpath.process_memory import FORBIDDEN_AUTHORITY  # noqa: E402

SP_FIXTURE = json.loads(
    (ROOT / "fixtures" / "t1" / "shortest_path" / "solution.json").read_text(encoding="utf-8")
)


class _ToolRecordingModel(FakeMessagesListChatModel):
    """Offline fake model that records tool names passed to ``bind_tools``."""

    recorded_tool_names: list[str] = []

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_ToolRecordingModel":  # noqa: ANN401
        names = [getattr(t, "name", str(t)) for t in (tools or [])]
        self.recorded_tool_names = list(names)
        return self


class _FakeWorker:
    """Offline stand-in for a compiled worker agent expecting isolated single-message briefs."""

    def __init__(self, fn):
        self.fn = fn
        self.briefs: list[str] = []

    def invoke(self, payload: dict[str, Any], config: Any = None) -> dict[str, Any]:
        msgs = list(payload["messages"])
        assert len(msgs) == 1 and isinstance(msgs[0], HumanMessage), "Feynman single-message brief required"
        brief = str(msgs[0].content)
        self.briefs.append(brief)
        result = self.fn(brief)
        if isinstance(result, AIMessage):
            ai_msg = result
        else:
            ai_msg = AIMessage(content=str(result))
        return {"messages": [msgs[0], ai_msg]}


def _worker_tools(agent: Any) -> set[str]:
    node = agent.nodes["tools"].bound
    return set(getattr(node, "tools_by_name", {}))


def _make_case(root: Path, slug: str) -> None:
    d = root / "inbox" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "problem.md").write_text(
        "# Shortest Path Benchmark\nFind shortest directed path from S to T.\n",
        encoding="utf-8",
    )
    (root / "outputs").mkdir(exist_ok=True)
    (root / "notes").mkdir(exist_ok=True)
    (root / "papers").mkdir(exist_ok=True)


def _dummy_analyst(brief: str) -> str:
    return "Problem class verified: shortest_path; Tier A."


def _dummy_writer(brief: str) -> str:
    return "Writer should not run when skip_paper=True."


def _dummy_reviewer(brief: str) -> str:
    return "Verdict: PASS"


# --------------------------------------------------------------------------- #
# 1. Empowered writer/reviewer tools & dynamic cartridge mounting
# --------------------------------------------------------------------------- #
def test_writer_and_reviewer_tool_mounting_and_dynamic_cartridge() -> None:
    model_w = _ToolRecordingModel(responses=[AIMessage(content="ok")])
    writer = create_writer_agent(model=model_w)
    writer_tools = _worker_tools(writer)
    expected_writer = {
        "read_problem_file",
        "read_file",
        "edit_file",
        "list_files",
        "grep_search",
        "export_paper_markdown",
        "search_or_knowledge",
        "consult_or_skill",
        "get_problem_formulation_template",
    }
    assert expected_writer.issubset(writer_tools), writer_tools
    assert expected_writer.issubset(set(model_w.recorded_tool_names))

    model_r = _ToolRecordingModel(responses=[AIMessage(content="ok")])
    reviewer = create_reviewer_agent(model=model_r)
    reviewer_tools = _worker_tools(reviewer)
    expected_reviewer = {
        "read_problem_file",
        "read_file",
        "grep_search",
        "list_files",
        "run_shell",
        "validate_solution_tool",
        "export_paper_markdown",
    }
    assert expected_reviewer.issubset(reviewer_tools), reviewer_tools
    assert expected_reviewer.issubset(set(model_r.recorded_tool_names))

    model_m = _ToolRecordingModel(responses=[AIMessage(content="ok")])
    dyn_modeler = _build_dynamic_role_agent(
        "modeler",
        model_m,
        {"problem_class": "jssp", "domain_cartridge": "scheduling"},
    )
    modeler_tools = _worker_tools(dyn_modeler)
    expected_modeler = {
        "profile_scheduling_data",
        "inspect_scheduling_solution",
        "execute_or_solver",
        "write_custom_solver_script",
        "edit_file",
        "run_shell",
    }
    assert expected_modeler.issubset(modeler_tools), modeler_tools
    assert expected_modeler.issubset(set(model_m.recorded_tool_names))


# --------------------------------------------------------------------------- #
# 2. Dual-track horse-racing tournament + cheater disqualification
# --------------------------------------------------------------------------- #
def test_dual_track_horse_racing_valid_winner_and_cheater_disqualification(
    tmp_path: Path,
) -> None:
    # Subcase A: Fair race — Track A (proven_optimal=True, obj=42) beats Track B (proven_optimal=False, obj=42)
    sub_a = tmp_path / "fair_race"
    _make_case(sub_a, "race_fair")

    def fair_modeler_a(brief: str) -> AIMessage:
        sol_path = Path(re.search(r"SOLUTION_PATH=(\S+)", brief).group(1))
        sol_path.parent.mkdir(parents=True, exist_ok=True)
        sol = dict(SP_FIXTURE)
        sol["proven_optimal"] = True
        sol["meta"] = {"proven_optimal": True, "method_class": "exact"}
        sol_path.write_text(json.dumps(sol), encoding="utf-8")
        return AIMessage(
            content="Track A exact finished.",
            tool_calls=[{"name": "execute_or_solver", "args": {"mode": "networkx"}, "id": "tc_a"}],
        )

    def fair_modeler_b(brief: str) -> AIMessage:
        sol_path = Path(re.search(r"SOLUTION_PATH=(\S+)", brief).group(1))
        sol_path.parent.mkdir(parents=True, exist_ok=True)
        sol = dict(SP_FIXTURE)
        sol["status"] = "FEASIBLE"
        sol["solver"] = "heuristic-beam"
        sol["proven_optimal"] = False
        sol["method"] = {"algorithm": "beam", "exact": False, "proven_optimal": False, "method_class": "heuristic"}
        sol["meta"] = {"proven_optimal": False, "method_class": "heuristic"}
        sol_path.write_text(json.dumps(sol), encoding="utf-8")
        return AIMessage(
            content="Track B heuristic finished.",
            tool_calls=[{"name": "execute_or_solver", "args": {"mode": "heuristic"}, "id": "tc_b"}],
        )

    graph_a = build_adaptive_graph(
        agents={
            "or_analyst": _FakeWorker(_dummy_analyst),
            "or_modeler": _FakeWorker(fair_modeler_a),
            "or_modeler_track_a": _FakeWorker(fair_modeler_a),
            "or_modeler_track_b": _FakeWorker(fair_modeler_b),
            "or_writer": _FakeWorker(_dummy_writer),
            "or_reviewer": _FakeWorker(_dummy_reviewer),
        },
        race_tracks=2,
    )
    res_a = graph_a.invoke(
        {
            "slug": "race_fair",
            "workdir": str(sub_a),
            "problem_id": "shortest_path",
            "problem_class": "shortest_path",
            "enable_horse_race": True,
            "skip_paper": True,
        }
    )
    assert res_a["validation_ok"] is True
    assert res_a["winning_track"] == "track_a"
    tourn_a_path = sub_a / "notes" / "race_fair-tournament.json"
    assert tourn_a_path.is_file()
    tourn_a = json.loads(tourn_a_path.read_text(encoding="utf-8"))
    assert tourn_a["winner"] == "track_a"
    assert tourn_a["tracks"]["track_a"]["tournament_result"] == "WINNER"
    assert tourn_a["tracks"]["track_b"]["tournament_result"] == "RUNNER_UP"
    assert tourn_a["tracks"]["track_a"]["validation_ok"] is True
    assert tourn_a["tracks"]["track_b"]["validation_ok"] is True
    tables_text = (sub_a / "outputs" / "race_fair-tables.md").read_text(encoding="utf-8")
    assert "## 5. 双轨算法赛马实证对比 (Dual-Track Tournament Comparison)" in tables_text

    # Subcase B: Cheater disqualification — Track A claims fake obj=10 (fails recompute), Track B valid obj=42 wins
    sub_b = tmp_path / "cheat_race"
    _make_case(sub_b, "race_cheat")

    def cheat_modeler_a(brief: str) -> AIMessage:
        sol_path = Path(re.search(r"SOLUTION_PATH=(\S+)", brief).group(1))
        sol_path.parent.mkdir(parents=True, exist_ok=True)
        sol = dict(SP_FIXTURE)
        sol["objective"] = 10
        sol["path_cost"] = 10
        sol_path.write_text(json.dumps(sol), encoding="utf-8")
        return AIMessage(
            content="Track A fake low cost 10.",
            tool_calls=[{"name": "execute_or_solver", "args": {"mode": "fake"}, "id": "tc_cheat"}],
        )

    def valid_modeler_b(brief: str) -> AIMessage:
        sol_path = Path(re.search(r"SOLUTION_PATH=(\S+)", brief).group(1))
        sol_path.parent.mkdir(parents=True, exist_ok=True)
        sol_path.write_text(json.dumps(SP_FIXTURE), encoding="utf-8")
        return AIMessage(
            content="Track B valid 42.",
            tool_calls=[{"name": "execute_or_solver", "args": {"mode": "networkx"}, "id": "tc_valid"}],
        )

    graph_b = build_adaptive_graph(
        agents={
            "or_analyst": _FakeWorker(_dummy_analyst),
            "or_modeler": _FakeWorker(cheat_modeler_a),
            "or_modeler_track_a": _FakeWorker(cheat_modeler_a),
            "or_modeler_track_b": _FakeWorker(valid_modeler_b),
            "or_writer": _FakeWorker(_dummy_writer),
            "or_reviewer": _FakeWorker(_dummy_reviewer),
        },
        race_tracks=2,
    )
    res_b = graph_b.invoke(
        {
            "slug": "race_cheat",
            "workdir": str(sub_b),
            "problem_id": "shortest_path",
            "problem_class": "shortest_path",
            "enable_horse_race": True,
            "skip_paper": True,
        }
    )
    assert res_b["validation_ok"] is True
    assert res_b["winning_track"] == "track_b"
    tourn_b = json.loads((sub_b / "notes" / "race_cheat-tournament.json").read_text(encoding="utf-8"))
    assert tourn_b["tracks"]["track_a"]["tournament_result"] == "DISQUALIFIED"
    assert tourn_b["tracks"]["track_a"]["validation_ok"] is False
    assert tourn_b["tracks"]["track_b"]["tournament_result"] == "WINNER"
    assert tourn_b["tracks"]["track_b"]["validation_ok"] is True
    canonical_sol = json.loads((sub_b / "outputs" / "race_cheat-solution.json").read_text(encoding="utf-8"))
    assert canonical_sol["objective"] == 42


# --------------------------------------------------------------------------- #
# 3. Anti-cosplay quarantine + escalating RETRY prompts
# --------------------------------------------------------------------------- #
def test_anti_cosplay_quarantine_and_escalating_retry(tmp_path: Path) -> None:
    _make_case(tmp_path, "cosplay_test")
    calls = {"count": 0}
    seen_retry_prompts: list[str] = []

    def modeler_fn(brief: str) -> AIMessage | str:
        calls["count"] += 1
        schema_path = tmp_path / "outputs" / "cosplay_test-schema.json"
        sol_path = Path(re.search(r"SOLUTION_PATH=(\S+)", brief).group(1))
        if calls["count"] == 1:
            schema_path.write_text(
                json.dumps({"problem_class": "shortest_path", "objective": 999, "path": ["S", "T"]}),
                encoding="utf-8",
            )
            sol_path.write_text(json.dumps(SP_FIXTURE), encoding="utf-8")
            # Plain text response with NO tool_calls -> must trigger tool-free cosplay quarantine too
            return AIMessage(content="I solved it in my head without calling solver tools.")

        seen_retry_prompts.append(brief)
        assert "RETRY 1/2" in brief, brief
        schema_path.write_text(
            json.dumps({"problem_class": "shortest_path", "constraints": ["flow_conservation"]}),
            encoding="utf-8",
        )
        sol_path.write_text(json.dumps(SP_FIXTURE), encoding="utf-8")
        return AIMessage(
            content="Solved cleanly after retry.",
            tool_calls=[{"name": "execute_or_solver", "args": {"mode": "networkx"}, "id": "tc_ok"}],
        )

    g = build_adaptive_graph(
        agents={
            "or_analyst": _FakeWorker(_dummy_analyst),
            "or_modeler": _FakeWorker(modeler_fn),
            "or_writer": _FakeWorker(_dummy_writer),
            "or_reviewer": _FakeWorker(_dummy_reviewer),
        },
        race_tracks=1,
    )
    res = g.invoke(
        {
            "slug": "cosplay_test",
            "workdir": str(tmp_path),
            "problem_id": "shortest_path",
            "problem_class": "shortest_path",
            "enable_horse_race": False,
            "enforce_anti_cosplay": True,
            "skip_paper": True,
        }
    )
    assert calls["count"] == 2
    assert len(seen_retry_prompts) == 1
    assert res["validation_ok"] is True
    assert res.get("cosplay_quarantined"), "expected quarantined artifact paths in state"
    assert (tmp_path / "outputs" / "cosplay_test-schema.json.cosplay-quarantine").is_file()
    assert (tmp_path / "outputs" / "cosplay_test-solution.json.cosplay-quarantine").is_file()


# --------------------------------------------------------------------------- #
# 4. skip_paper early stop + process_memory + stage JSONL logs
# --------------------------------------------------------------------------- #
def test_skip_paper_process_memory_and_stage_logs(tmp_path: Path) -> None:
    _make_case(tmp_path, "mem_logs")
    writer_calls = {"count": 0}

    def writer_spy(brief: str) -> str:
        writer_calls["count"] += 1
        return "unexpected writer run"

    def modeler_valid(brief: str) -> AIMessage:
        sol_path = Path(re.search(r"SOLUTION_PATH=(\S+)", brief).group(1))
        sol_path.parent.mkdir(parents=True, exist_ok=True)
        sol_path.write_text(json.dumps(SP_FIXTURE), encoding="utf-8")
        return AIMessage(
            content="Valid candidate written.",
            tool_calls=[{"name": "execute_or_solver", "args": {"mode": "networkx"}, "id": "tc_mem"}],
        )

    g = build_adaptive_graph(
        agents={
            "or_analyst": _FakeWorker(_dummy_analyst),
            "or_modeler": _FakeWorker(modeler_valid),
            "or_writer": _FakeWorker(writer_spy),
            "or_reviewer": _FakeWorker(_dummy_reviewer),
        },
        race_tracks=2,
    )
    res = g.invoke(
        {
            "slug": "mem_logs",
            "workdir": str(tmp_path),
            "problem_id": "shortest_path",
            "problem_class": "shortest_path",
            "enable_horse_race": True,
            "skip_paper": True,
        }
    )
    assert writer_calls["count"] == 0
    assert res["lifecycle_status"] == "INDEPENDENTLY_VALIDATED"
    assert (tmp_path / "notes" / "mem_logs-lessons.md").is_file()

    lesson_file = tmp_path / "memory" / "lessons" / "les_auto_mem_logs.json"
    assert lesson_file.is_file(), "expected process_memory auto-draft lesson"
    lesson_doc = json.loads(lesson_file.read_text(encoding="utf-8"))
    for forbidden_key in FORBIDDEN_AUTHORITY:
        assert forbidden_key not in {k.lower() for k in lesson_doc.keys()}

    log_dir = tmp_path / "runs" / "mem_logs" / "agent_logs"
    for stage_name in ("analyst", "modeler_track_a", "modeler_track_b"):
        lp = log_dir / f"{stage_name}.jsonl"
        assert lp.is_file(), f"missing stage log: {lp}"
        lines = [ln for ln in lp.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert lines, f"empty stage log: {lp}"
        parsed = [json.loads(ln) for ln in lines]
        assert all(isinstance(item, dict) for item in parsed)


# --------------------------------------------------------------------------- #
# 5. solve.py _run_isolated_pipeline offline guard & adaptive graph bridge
# --------------------------------------------------------------------------- #
def test_solve_pipeline_isolated_fallback_uses_adaptive_graph(tmp_path: Path) -> None:
    from orpath.pipeline.solve import _run_isolated_pipeline

    _make_case(tmp_path, "iso_bridge")
    sp = tmp_path / "outputs" / "iso_bridge-schema.json"

    offline_res = _run_isolated_pipeline(
        tmp_path,
        {
            "slug": "iso_bridge",
            "problem_id": "shortest_path",
            "problem_class": "shortest_path",
            "live_subagent": False,
        },
        sp,
        "networkx",
    )
    assert offline_res is None

    def modeler_iso(brief: str) -> AIMessage:
        sol_path = Path(re.search(r"SOLUTION_PATH=(\S+)", brief).group(1))
        sol_path.parent.mkdir(parents=True, exist_ok=True)
        sol_path.write_text(json.dumps(SP_FIXTURE), encoding="utf-8")
        return AIMessage(
            content="Solved SP via isolated pipeline.",
            tool_calls=[{"name": "execute_or_solver", "args": {"mode": "networkx"}, "id": "tc_iso"}],
        )

    injected_agents = {
        "or_analyst": _FakeWorker(_dummy_analyst),
        "or_modeler": _FakeWorker(modeler_iso),
        "or_writer": _FakeWorker(_dummy_writer),
        "or_reviewer": _FakeWorker(_dummy_reviewer),
    }
    res = _run_isolated_pipeline(
        tmp_path,
        {
            "slug": "iso_bridge",
            "problem_id": "shortest_path",
            "problem_class": "shortest_path",
            "skip_paper": True,
            "agents": injected_agents,
        },
        sp,
        "networkx",
    )
    assert isinstance(res, dict)
    assert res["validation_ok"] is True
    assert sp.is_file()
    sol_out = json.loads((tmp_path / "outputs" / "iso_bridge-solution.json").read_text(encoding="utf-8"))
    assert sol_out["objective"] == 42
