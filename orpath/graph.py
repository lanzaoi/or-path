from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from orpath import nodes
from orpath.state import ORPathState


def _route_after_schema(state: ORPathState) -> Literal["solve", "model"]:
    if state.get("gate_schema_ok"):
        return "solve"
    return "model"


def _route_after_revise(state: ORPathState) -> Literal["draft_paper", "provenance"]:
    if state.get("stage") == "draft_paper":
        return "draft_paper"
    return "provenance"


def build_graph() -> Any:
    g: StateGraph = StateGraph(ORPathState)
    g.add_node("orchestrate", nodes.node_orchestrate)
    g.add_node("research", nodes.node_research)
    g.add_node("model", nodes.node_model)
    g.add_node("gate_schema", nodes.node_gate_schema)
    g.add_node("solve", nodes.node_solve)
    g.add_node("explain", nodes.node_explain)
    g.add_node("draft_paper", nodes.node_draft_paper)
    g.add_node("review_pack", nodes.node_review_pack)
    g.add_node("revise_or_done", nodes.node_revise_or_done)
    g.add_node("provenance", nodes.node_provenance)

    g.add_edge(START, "orchestrate")
    g.add_edge("orchestrate", "research")
    g.add_edge("research", "model")
    g.add_edge("model", "gate_schema")
    g.add_conditional_edges(
        "gate_schema",
        _route_after_schema,
        {"solve": "solve", "model": "model"},
    )
    g.add_edge("solve", "explain")
    g.add_edge("explain", "draft_paper")
    g.add_edge("draft_paper", "review_pack")
    g.add_edge("review_pack", "revise_or_done")
    g.add_conditional_edges(
        "revise_or_done",
        _route_after_revise,
        {"draft_paper": "draft_paper", "provenance": "provenance"},
    )
    g.add_edge("provenance", END)
    return g.compile()
