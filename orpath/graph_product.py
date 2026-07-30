"""Product LangGraph topology (T3).

Build via ControlPlane: ``orpath.control_plane.build_graph`` (ADR-0003).
This module owns edges/routing only; runners must not duplicate state seeds.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from orpath import nodes
from orpath.state import ORPathState

# Canonical node set for topology gates / export
PRODUCT_NODES = [
    "orchestrate",
    "retrieve",
    "bridge_pi",
    "research",
    "model",
    "gate_schema",
    "solve",
    "gate_validate",
    "human_stop",
    "explain",
    "draft_paper",
    "cite_pack",
    "review_pack",
    "revise_or_done",
    "provenance",
]


def _after_orchestrate(
    state: ORPathState,
) -> Literal["bridge_pi", "retrieve"]:
    att = state.get("bridge_attachment") or "before_research"
    if att == "before_retrieve":
        return "bridge_pi"
    return "retrieve"


def _after_bridge(
    state: ORPathState,
) -> Literal["retrieve", "research"]:
    att = state.get("bridge_attachment") or "before_research"
    if att == "before_retrieve":
        return "retrieve"
    return "research"


def _after_retrieve(state: ORPathState) -> Literal["bridge_pi", "research"]:
    att = state.get("bridge_attachment") or "before_research"
    if att == "before_research":
        return "bridge_pi"
    return "research"


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
) -> Literal["draft_paper", "cite_pack", "provenance", "human_stop"]:
    st = state.get("stage")
    if st == "draft_paper":
        return "draft_paper"
    if st == "cite_pack":
        return "cite_pack"
    if st == "human_stop":
        return "human_stop"
    return "provenance"


def build_graph_product(checkpointer: Any | None = None) -> Any:
    g: StateGraph = StateGraph(ORPathState)
    g.add_node("orchestrate", nodes.node_orchestrate)
    g.add_node("retrieve", nodes.node_retrieve)
    g.add_node("bridge_pi", nodes.node_bridge)
    g.add_node("research", nodes.node_research)
    g.add_node("model", nodes.node_model)
    g.add_node("gate_schema", nodes.node_gate_schema)
    g.add_node("solve", nodes.node_solve)
    g.add_node("gate_validate", nodes.node_gate_validate)
    g.add_node("human_stop", nodes.node_human_stop)
    g.add_node("explain", nodes.node_explain)
    g.add_node("draft_paper", nodes.node_draft_paper)
    g.add_node("cite_pack", nodes.node_cite_pack)
    g.add_node("review_pack", nodes.node_review_pack)
    g.add_node("revise_or_done", nodes.node_revise_or_done)
    g.add_node("provenance", nodes.node_provenance)

    g.add_edge(START, "orchestrate")
    g.add_conditional_edges(
        "orchestrate",
        _after_orchestrate,
        {"bridge_pi": "bridge_pi", "retrieve": "retrieve"},
    )
    g.add_conditional_edges(
        "bridge_pi",
        _after_bridge,
        {"retrieve": "retrieve", "research": "research"},
    )
    g.add_conditional_edges(
        "retrieve",
        _after_retrieve,
        {"bridge_pi": "bridge_pi", "research": "research"},
    )
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
    g.add_edge("draft_paper", "cite_pack")
    g.add_edge("cite_pack", "review_pack")
    g.add_edge("review_pack", "revise_or_done")
    g.add_conditional_edges(
        "revise_or_done",
        _after_revise,
        {
            "draft_paper": "draft_paper",
            "cite_pack": "cite_pack",
            "provenance": "provenance",
            "human_stop": "human_stop",
        },
    )
    g.add_edge("provenance", END)

    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()


def open_sqlite_checkpointer(db_path: Path) -> tuple[SqliteSaver, sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    try:
        saver.setup()
    except Exception:
        pass
    return saver, conn


def export_stage_map() -> dict[str, Any]:
    return {
        "name": "orpath_product",
        "nodes": list(PRODUCT_NODES),
        "edges": [
            {"from": "START", "to": "orchestrate"},
            {
                "from": "orchestrate",
                "to": ["bridge_pi", "retrieve"],
                "cond": "bridge_attachment",
            },
            {
                "from": "bridge_pi",
                "to": ["retrieve", "research"],
                "cond": "bridge_attachment",
            },
            {
                "from": "retrieve",
                "to": ["bridge_pi", "research"],
                "cond": "bridge_attachment",
            },
            {"from": "research", "to": "model"},
            {"from": "model", "to": "gate_schema"},
            {
                "from": "gate_schema",
                "to": ["solve", "model", "human_stop"],
                "cond": "schema_gate",
            },
            {"from": "solve", "to": "gate_validate"},
            {
                "from": "gate_validate",
                "to": ["explain", "solve", "model", "human_stop"],
                "cond": "validate_gate",
            },
            {"from": "human_stop", "to": "provenance"},
            {"from": "explain", "to": "draft_paper"},
            {"from": "draft_paper", "to": "cite_pack"},
            {"from": "cite_pack", "to": "review_pack"},
            {"from": "review_pack", "to": "revise_or_done"},
            {
                "from": "revise_or_done",
                "to": ["draft_paper", "cite_pack", "provenance", "human_stop"],
                "cond": "revise",
            },
            {"from": "provenance", "to": "END"},
        ],
        "checkpointer": "sqlite:runs/orpath.sqlite",
        "bridge_default_attachment": "before_research",
        "paper_pipeline": "draft→cite→review→revise(re-cite)→provenance",
    }


def write_stage_map_files(root: Path) -> None:
    data = export_stage_map()
    (root / "orpath" / "stage_map.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    mmd = [
        "flowchart TD",
        "  START --> orchestrate",
        "  orchestrate -->|before_retrieve| bridge_pi",
        "  orchestrate -->|default| retrieve",
        "  bridge_pi -->|before_retrieve| retrieve",
        "  bridge_pi -->|before_research| research",
        "  retrieve -->|before_research| bridge_pi",
        "  retrieve -->|before_retrieve done| research",
        "  research --> model --> gate_schema",
        "  gate_schema -->|ok| solve",
        "  gate_schema -->|repair| model",
        "  gate_schema -->|ceiling| human_stop",
        "  solve --> gate_validate",
        "  gate_validate -->|ok| explain",
        "  gate_validate -->|tune| solve",
        "  gate_validate -->|model repair| model",
        "  gate_validate -->|ceiling| human_stop",
        "  human_stop --> provenance",
        "  explain --> draft_paper --> cite_pack --> review_pack --> revise_or_done",
        "  revise_or_done -->|revise| draft_paper",
        "  revise_or_done -->|re-cite| cite_pack",
        "  revise_or_done -->|done| provenance",
        "  revise_or_done -->|HUMAN| human_stop",
        "  provenance --> END",
    ]
    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "t3-stage-map.mmd").write_text("\n".join(mmd) + "\n", encoding="utf-8")
