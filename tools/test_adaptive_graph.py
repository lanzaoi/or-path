#!/usr/bin/env python3
"""Unit tests for the Tier-A/B/C adaptive routing state machine (Plan 1.5).

Acceptance coverage:

  * Tier-A / Tier-B / Tier-C flow through exactly the documented node
    sequences (fake agents + REAL deterministic validators, fully offline);
  * validator bounce-back and reviewer FATAL bounce-back are strictly bounded
    by ``max_retries`` — the graph always terminates, never polls;
  * Tier-C launches isolated modeler sub-instances per question, carries the
    cross-question ledger (``notes/<slug>-ledger.json``), merges the
    collective envelope and gates the composite objective deterministically;
  * every LLM stage invokes with a brand-new single-message payload
    (``{"messages": [HumanMessage(brief)]}``) whose brief carries only file
    pointers + compact ledgers — no cross-agent context pollution;
  * the deterministic adjuncts (``render_truth_tables`` /
    ``run_deterministic_doc_gate`` / ``parse_review_reply``) are pure Python.

The full graph builds offline with the default worker factories too (no API
key required — ``get_chat_model()`` degrades to a placeholder client).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

pytestmark = pytest.mark.filterwarnings(
    "ignore:create_react_agent has been moved"
)

from orpath.agents.adaptive_graph import (  # noqa: E402
    ADAPTIVE_NODES,
    AdaptivePipelineState,
    build_adaptive_graph,
    build_compiled_adaptive_graph,
    decide_tier,
    parse_review_reply,
    render_truth_tables,
    run_deterministic_doc_gate,
)


# --------------------------------------------------------------------------- #
# offline harness
# --------------------------------------------------------------------------- #
class _FakeAgent:
    """Deterministic offline stand-in for a compiled ReAct worker."""

    def __init__(self, fn):
        self.fn = fn
        self.briefs: list[str] = []

    def invoke(self, payload, config=None):
        msgs = list(payload["messages"])
        # acceptance: every invoke runs on a brand-new local message list
        assert len(msgs) == 1 and isinstance(msgs[0], HumanMessage), "isolated fresh message list required"
        brief = str(msgs[0].content)
        self.briefs.append(brief)
        reply = self.fn(brief)
        return {"messages": [msgs[0], AIMessage(content=reply)]}


def _make_case(tmp_path: Path, slug: str, problem_text: str | None = None) -> None:
    d = tmp_path / "inbox" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "problem.md").write_text(
        problem_text or "# 最短路 / Shortest Path\n给定有向加权图，求 S 到 T 的最短路径。\n",
        encoding="utf-8",
    )
    (tmp_path / "outputs").mkdir(exist_ok=True)
    (tmp_path / "notes").mkdir(exist_ok=True)
    (tmp_path / "papers").mkdir(exist_ok=True)


SP_FIXTURE = ROOT / "fixtures" / "t1" / "shortest_path" / "solution.json"

# --- QUBO Max-Cut multi-question dataset for Tier-C (fully self-contained validator)
def _qubo(obj, cut_edges, partition):
    return {
        "problem_id": "qubo_contest",
        "problem_class": "qubo_ising",
        "status": "OPTIMAL",
        "objective": obj,
        "solver": "fake-tierc",
        "source": "fake.q",
        "mode": "max_cut",
        "cut_edges": cut_edges,
        "node_partition": partition,
    }


QUBO_SOLS = {
    "q1": _qubo(2, [[0, 1], [1, 2]], {"set_0": [0, 2], "set_1": [1]}),
    "q2": _qubo(2, [[0, 1], [2, 3]], {"set_0": [0, 2], "set_1": [1, 3]}),
    "q3": _qubo(3, [[3, 0], [3, 1], [3, 2]], {"set_0": [3], "set_1": [0, 1, 2]}),
}

GOOD_PAPER = (
    "# 摘要\n本文研究加权最短路问题，目标函数 objective=42，proven_optimal=True。\n"
    "## 问题重述与建模假设\n## 数学规划模型建立\n## 求解策略与算子选型\n"
    "## 数值计算结果与敏感性分析\n## 模型评价、优缺点与工业落地建议\n"
)


def _fakes(tmp_path, *, objective_ok=True, fatal_rounds=0, paper_kind="good", qubo=False):
    state = {"modeler": 0, "reviewer": 0, "writer": 0}

    def analyst(brief):
        return ANALYST_MARK + " tier-A 最短路研判（该正文不得流入下游 brief）"

    def modeler(brief):
        state["modeler"] += 1
        if qubo:
            qid = re.search(r"第 (\w+) 问", brief).group(1)
            target = Path(re.search(r"SOLUTION_PATH=(\S+)", brief).group(1))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(QUBO_SOLS[qid]))
            return f"focus call {state['modeler']} for {qid}"
        sol = json.loads(SP_FIXTURE.read_text(encoding="utf-8"))
        if not objective_ok:
            sol["objective"] = 999
        target = Path(re.search(r"SOLUTION_PATH=(\S+)", brief).group(1))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(sol))
        return f"modeler call {state['modeler']}"

    def writer(brief):
        state["writer"] += 1
        text = GOOD_PAPER
        if paper_kind == "revise-marker":
            text += "\n### REVISE 打回修改"
        if paper_kind == "unproven-claim":
            text = (
                "# 摘要\n本文给出全局最优解 objective=42。\n"
                "## 问题重述与建模假设\n## 数学规划模型建立\n## 求解策略与算子选型\n"
                "## 数值计算结果与敏感性分析\n## 模型评价、优缺点与工业落地建议\n"
            )
        target = Path(re.search(r"PAPER_PATH=(\S+)", brief).group(1))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return f"writer {state['writer']}"

    def reviewer(brief):
        state["reviewer"] += 1
        if state["reviewer"] <= fatal_rounds:
            verdict = "REVISE 打回修改"
            weak = f"- [W1] **FATAL:** 编造目标值（第{state['reviewer']}轮）\n"
        else:
            verdict = "Verdict: PASS 接受"
            weak = "- [W1] **MINOR:** 格式瑕疵\n"
        target = Path(re.search(r"REVIEW_PATH=(\S+)", brief).group(1))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"## Weaknesses\n{weak}## Verdict\n{verdict}")
        return verdict

    return (
        _FakeAgent(analyst),
        _FakeAgent(modeler),
        _FakeAgent(writer),
        _FakeAgent(reviewer),
        state,
    )


ANALYST_MARK = "ANALYST_INNER_MARKER"


def _stream(graph, state_dict):
    seen: list[str] = []
    merged: dict[str, dict] = {}
    for chunk in graph.stream(state_dict):
        seen.extend(chunk.keys())
        for k, update in chunk.items():
            if isinstance(update, dict) and isinstance(merged.get(k), dict):
                merged[k] = {**merged[k], **update}
            else:
                merged[k] = update
    return seen, merged


def _agents_dict(a, m, w, r):
    return {"or_analyst": a, "or_modeler": m, "or_writer": w, "or_reviewer": r}


# --------------------------------------------------------------------------- #
# 1. deterministic tier classification
# --------------------------------------------------------------------------- #
def test_decide_tier_class_mapping() -> None:
    assert decide_tier({"problem_class": "shortest_path"}) == "A"
    assert decide_tier({"problem_class": "network_flow"}) == "A"
    assert decide_tier({"problem_class": "lot_sizing"}) == "A"
    assert decide_tier({"problem_class": "portfolio_opt"}) == "A"
    assert decide_tier({"problem_class": "stochastic_lp"}) == "A"
    assert decide_tier({"problem_class": "game_theory"}) == "A"
    assert decide_tier({"problem_class": "jssp"}) == "B"
    assert decide_tier({"problem_class": "vrptw"}) == "B"
    assert decide_tier({"problem_class": "rcpsp"}) == "B"
    assert decide_tier({"problem_class": "microgrid_dispatch"}) == "B"


def test_decide_tier_subproblems_and_override() -> None:
    assert decide_tier({"problem_class": "shortest_path", "subproblems": ["q1", "q2"]}) == "C"
    assert decide_tier({"problem_class": "jssp", "complexity_tier": "A"}) == "A"
    assert decide_tier({"problem_class": "shortest_path"}) == "A"


def test_graph_nodes_and_stage_map() -> None:
    from orpath.agents.adaptive_graph import adaptive_stage_map

    g = build_adaptive_graph(agents={"or_analyst": _FakeAgent(lambda b: "x"),
                                     "or_modeler": _FakeAgent(lambda b: "x"),
                                     "or_writer": _FakeAgent(lambda b: "x"),
                                     "or_reviewer": _FakeAgent(lambda b: "x")})
    for name in ADAPTIVE_NODES:
        assert name in g.get_graph().nodes
    stage = adaptive_stage_map()
    assert stage["name"] == "orpath_adaptive"
    assert set(stage["nodes"]) == set(ADAPTIVE_NODES)


# --------------------------------------------------------------------------- #
# 2. Tier-A track
# --------------------------------------------------------------------------- #
def test_tier_a_sequence_and_validation(tmp_path: Path) -> None:
    _make_case(tmp_path, "sp-tierA")
    a, m, w, r, st = _fakes(tmp_path)
    g = build_adaptive_graph(agents=_agents_dict(a, m, w, r), max_retries=2)
    state = _state(tmp_path, "sp-tierA", "shortest_path")
    seen, node = _stream(g, state)

    assert seen == ["preflight", "analyst", "modeler", "validator", "table_render", "writer", "doc_gate"], seen
    assert node["validator"]["validation_ok"] is True
    assert node["validator"]["proven_optimal"] is True
    assert node["validator"]["objective_value"] == 42
    assert node["validator"]["recomputed_objective"] == 42
    tables = Path(node["table_render"]["tables_path"])
    assert tables.is_file() and "objective" in tables.read_text(encoding="utf-8")
    assert node["doc_gate"]["doc_gate_ok"] is True
    assert Path(node["doc_gate"]["paper_path"]).is_file()
    # isolated briefs: modeler brief carries pointers only, no analyst prose
    assert ANALYST_MARK not in m.briefs[0]
    assert "profile_path" in m.briefs[0]


def test_tier_a_optional_reviewer_attachment(tmp_path: Path) -> None:
    _make_case(tmp_path, "sp-tierA2")
    a, m, w, r, st = _fakes(tmp_path)
    g = build_adaptive_graph(agents=_agents_dict(a, m, w, r), tier_a_with_reviewer=True)
    seen, node = _stream(g, _state(tmp_path, "sp-tierA2", "shortest_path"))
    assert seen[-1] == "reviewer"
    assert node["reviewer"]["review_verdict"] == "PASS"
    assert Path(node["reviewer"]["review_path"]).is_file()


def test_tier_a_doc_gate_unproven_global_claim_rejected(tmp_path: Path) -> None:
    # validator honesty: unproven solution claiming 全局最优 gets bounced until capped
    _make_case(tmp_path, "sp-unproven")
    sol = json.loads(SP_FIXTURE.read_text(encoding="utf-8"))
    sol.pop("method", None)
    sol["status"] = "FEASIBLE"
    sol["proven_optimal"] = False
    sol["objective"] = 42  # feasible-track claim stays honest; not optimal
    # monkey-patch modeler fake to emit the FEASIBLE variant
    a, m, w, r, st = _fakes(tmp_path, paper_kind="unproven-claim", objective_ok=True)
    original_modeler = m.fn

    def modeler_feasible(brief):
        res = original_modeler(brief)
        p = Path(re.search(r"SOLUTION_PATH=(\S+)", brief).group(1))
        d = json.loads(p.read_text(encoding="utf-8"))
        d.pop("method", None)
        d["status"] = "FEASIBLE"
        d["proven_optimal"] = False
        d["objective"] = 42
        p.write_text(json.dumps(d))
        return res

    m.fn = modeler_feasible
    g = build_adaptive_graph(agents=_agents_dict(a, m, w, r), max_retries=1)
    seen, node = _stream(g, _state(tmp_path, "sp-unproven", "shortest_path"))
    assert seen[-1] == "fail_closed", seen
    assert node["doc_gate"]["doc_gate_ok"] is False
    assert any("全局最优" in e for e in node["doc_gate"]["doc_gate_errors"])
    assert Path(tmp_path / "notes" / "sp-unproven-failure.md").is_file()


# --------------------------------------------------------------------------- #
# 3. Tier-B track (bounded bounce-backs)
# --------------------------------------------------------------------------- #
def test_tier_b_validator_bounce_is_capped(tmp_path: Path) -> None:
    _make_case(tmp_path, "sp-tierB")
    a, m, w, r, st = _fakes(tmp_path, objective_ok=False)
    g = build_adaptive_graph(agents=_agents_dict(a, m, w, r), max_retries=2)
    seen, node = _stream(g, _state(tmp_path, "sp-tierB", "jssp"))
    assert st["modeler"] == 2 and seen[-1] == "fail_closed", (st, seen)
    assert "modeler" in seen and seen.count("modeler") == 2
    assert any(s == "validator" for s in seen)
    assert "writer" not in seen
    assert Path(tmp_path / "notes" / "sp-tierB-failure.md").is_file()


def test_tier_b_reviewer_fatal_bounce_is_capped(tmp_path: Path) -> None:
    _make_case(tmp_path, "sp-tierB2")
    a, m, w, r, st = _fakes(tmp_path, fatal_rounds=99)
    g = build_adaptive_graph(agents=_agents_dict(a, m, w, r), max_retries=2)
    seen, node = _stream(g, _state(tmp_path, "sp-tierB2", "jssp"))
    assert st["writer"] == 2 and st["reviewer"] == 2, (st, seen)
    assert seen[-1] == "fail_closed"
    assert node["reviewer"]["fatal_defects"]
    assert (tmp_path / "papers" / "sp-tierB2.md").is_file()
    assert (tmp_path / "papers" / "sp-tierB2-review.md").is_file()


# --------------------------------------------------------------------------- #
# 4. Tier-C track
# --------------------------------------------------------------------------- #
def _state(tmp_path: Path, slug: str, problem_class: str, **extra) -> dict:
    base = {"slug": slug, "workdir": str(tmp_path),
            "problem_id": "qubo_contest" if problem_class == "qubo_ising" else "shortest_path",
            "problem_class": problem_class, "max_retries": 2}
    base.update(extra)
    return base


def test_tier_c_multi_question_loop_with_ledger(tmp_path: Path) -> None:
    _make_case(tmp_path, "qubo-c")
    a, m, w, r, st = _fakes(tmp_path, qubo=True)
    g = build_adaptive_graph(agents=_agents_dict(a, m, w, r), max_retries=2)
    seen, node = _stream(g, _state(tmp_path, "qubo-c", "qubo_ising", subproblems=["q1", "q2", "q3"]))

    assert "tier_c_focus" in seen and seen[-1] == "reviewer", seen
    ledger_path = Path(node["tier_c_focus"]["ledger_path"])
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger["q1"]["ok"] and ledger["q2"]["ok"] and ledger["q3"]["ok"]

    merged = json.loads(Path(node["tier_c_focus"]["solution_path"]).read_text(encoding="utf-8"))
    assert merged["objective"] == 7.0
    assert merged["status"] == "OPTIMAL"
    assert set(merged["subproblems"]) == {"q1", "q2", "q3"}

    # per-question validator gates were applied (deterministic validators!)
    assert sum(1 for s in seen if s == "tier_c_focus") == 1
    for q in ("q1", "q2", "q3"):
        assert (tmp_path / "outputs" / f"qubo-c-{q}-validation.json").is_file()

    # cross-question state artifact carried on disk AND in the brief
    assert "ledger" in m.briefs[0]
    assert "focus call" not in m.briefs[1]  # q2 never saw q1's reply text
    assert ANALYST_MARK not in m.briefs[2]

    assert node["reviewer"]["review_verdict"] == "PASS"
    assert (tmp_path / "outputs" / "qubo-c-tables.md").is_file()


def test_tier_c_flash_failure_is_capped(tmp_path: Path) -> None:
    _make_case(tmp_path, "qubo-bad")

    def dead_modeler(brief):
        # never produce an artifact -> every question fails validation
        m_state["c"] += 1
        return f"flash call {m_state['c']}"

    m_state = {"c": 0}
    a, _, w, r, st = _fakes(tmp_path)
    m = _FakeAgent(dead_modeler)
    g = build_adaptive_graph(agents=_agents_dict(a, m, w, r), max_retries=2)
    seen, node = _stream(g, _state(tmp_path, "qubo-bad", "qubo_ising", subproblems=["q1", "q2"]))
    assert m_state["c"] == 4, f"bounded attempts expected: {m_state['c']}"
    assert seen[-1] == "fail_closed"
    ledger = json.loads(Path(node["tier_c_focus"]["ledger_path"]).read_text(encoding="utf-8"))
    assert ledger["q1"]["ok"] is False and ledger["q2"]["ok"] is False
    assert "writer" not in seen


# --------------------------------------------------------------------------- #
# 5. deterministic adjuncts
# --------------------------------------------------------------------------- #
def test_render_truth_tables_is_deterministic(tmp_path: Path) -> None:
    _make_case(tmp_path, "sp-det")
    sol = tmp_path / "outputs" / "sp-det-solution.json"
    sol.write_text(SP_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    st = {"slug": "sp-det", "workdir": str(tmp_path), "problem_id": "shortest_path",
          "solution_path": str(sol)}
    run_validator = None
    from orpath.agents.deterministic_nodes import run_deterministic_validator
    run_validator = run_deterministic_validator({**st, "problem_class": "shortest_path"})
    st["validate_path"] = run_validator["validate_path"]
    out1 = render_truth_tables(st)
    text1 = Path(out1["tables_path"]).read_text(encoding="utf-8")
    out2 = render_truth_tables(st)
    assert text1 == Path(out2["tables_path"]).read_text(encoding="utf-8")
    assert "42" in text1
    assert "recompute_objective" in text1


def test_doc_gate_keywords_and_numeric_binding(tmp_path: Path) -> None:
    paper = tmp_path / "papers" / "x.md"
    paper.parent.mkdir(parents=True, exist_ok=True)
    good = GOOD_PAPER
    paper.write_text(good, encoding="utf-8")
    ok = run_deterministic_doc_gate({
        "slug": "x", "workdir": str(tmp_path), "paper_path": str(paper),
        "objective_value": 42.0, "proven_optimal": True,
    })
    assert ok["doc_gate_ok"] and ok["doc_gate_errors"] == []

    missing_kw = good.replace("敏感性", "X")
    paper.write_text(missing_kw, encoding="utf-8")
    bad = run_deterministic_doc_gate({
        "slug": "x", "workdir": str(tmp_path), "paper_path": str(paper),
        "objective_value": 42.0, "proven_optimal": True,
    })
    assert not bad["doc_gate_ok"] and any("敏感性" in e for e in bad["doc_gate_errors"])


# --------------------------------------------------------------------------- #
# 6. offline build with real worker factories
# --------------------------------------------------------------------------- #
def test_graph_builds_offline_with_default_workers() -> None:
    """Default agent construction uses the offline-safe model factory."""
    g = build_compiled_adaptive_graph()
    for name in ADAPTIVE_NODES:
        assert name in g.get_graph().nodes
    assert g.nodes["modeler"].bound is not None
