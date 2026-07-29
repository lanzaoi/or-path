from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from orpath import nodes_t2 as nodes
from orpath.state import ORPathState


def _after_schema(state: ORPathState) -> Literal["solve", "model", "human_stop"]:
    st = state.get("stage")
    if st == "human_stop":
        return "human_stop"
    if state.get("gate_schema_ok"):
        return "solve"
    if st == "model":
        return "model"
    return "human_stop"


def _after_validate(
    state: ORPathState,
) -> Literal["explain", "solve", "model", "human_stop"]:
    st = state.get("stage")
    if st == "explain":
        return "explain"
    if st == "solve":
        return "solve"
    if st == "model":
        return "model"
    return "human_stop"


def _after_revise(
    state: ORPathState,
) -> Literal["draft_paper", "provenance", "human_stop"]:
    st = state.get("stage")
    if st == "draft_paper":
        return "draft_paper"
    if st == "human_stop":
        return "human_stop"
    return "provenance"


def build_graph_t2() -> Any:
    g: StateGraph = StateGraph(ORPathState)
    g.add_node("orchestrate", nodes.node_orchestrate)
    g.add_node("retrieve", nodes.node_retrieve)
    g.add_node("research", nodes.node_research)
    g.add_node("model", nodes.node_model)
    g.add_node("gate_schema", nodes.node_gate_schema)
    g.add_node("solve", nodes.node_solve)
    g.add_node("gate_validate", nodes.node_gate_validate)
    g.add_node("human_stop", nodes.node_human_stop)
    g.add_node("explain", nodes.node_explain)
    g.add_node("draft_paper", nodes.node_draft_paper)
    g.add_node("review_pack", nodes.node_review_pack)
    g.add_node("revise_or_done", nodes.node_revise_or_done)
    g.add_node("provenance", nodes.node_provenance)

    g.add_edge(START, "orchestrate")
    g.add_edge("orchestrate", "retrieve")
    g.add_edge("retrieve", "research")
    g.add_edge("research", "model")
    g.add_edge("model", "gate_schema")
    g.add_conditional_edges(
        "gate_schema",
        _after_schema,
        {"solve": "solve", "model": "model", "human_stop": "human_stop"},
    )
    g.add_edge("solve", "gate_validate")
    g.add_conditional_edges(
        "gate_validate",
        _after_validate,
        {
            "explain": "explain",
            "solve": "solve",
            "model": "model",
            "human_stop": "human_stop",
        },
    )
    g.add_edge("human_stop", "provenance")
    g.add_edge("explain", "draft_paper")
    g.add_edge("draft_paper", "review_pack")
    g.add_edge("review_pack", "revise_or_done")
    g.add_conditional_edges(
        "revise_or_done",
        _after_revise,
        {
            "draft_paper": "draft_paper",
            "provenance": "provenance",
            "human_stop": "human_stop",
        },
    )
    g.add_edge("provenance", END)
    return g.compile()
