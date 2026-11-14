#!/usr/bin/env python3
"""Integration tests for ControlPlane isolated multi-agent entry points."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph, StateGraph

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from orpath.agents.adaptive_graph import (  # noqa: E402
    ISOLATED_PIPELINE_NODES,
    build_compiled_isolated_pipeline,
    build_isolated_pipeline_graph,
)
from orpath.control_plane import (  # noqa: E402
    build_compiled_isolated_pipeline as cp_compiled_isolated,
    build_compiled_multiagent,
    build_isolated_pipeline_graph as cp_isolated_graph,
    build_multiagent_graph,
)

EXPECTED_ISOLATED_NODES: frozenset[str] = frozenset({"__start__", *ISOLATED_PIPELINE_NODES})


def _state_schema(graph: Any) -> Any:
    schema = getattr(graph, "state_schema", None)
    if schema is not None:
        return schema
    builder = getattr(graph, "builder", None)
    if builder is not None:
        schema = getattr(builder, "state_schema", None)
        if schema is not None:
            return schema
    raise AssertionError("graph exposes no state_schema")


def _schema_field_names(schema: Any) -> set[str]:
    annotations = getattr(schema, "__annotations__", None)
    if annotations:
        return set(annotations)
    if isinstance(schema, dict):
        return set(schema)
    raise AssertionError(f"cannot read fields from state schema: {schema!r}")


def test_control_plane_exposes_multiagent_builders() -> None:
    import orpath.control_plane as control_plane

    assert callable(build_multiagent_graph)
    assert callable(build_compiled_multiagent)
    assert callable(cp_isolated_graph)
    assert callable(cp_compiled_isolated)
    assert "build_multiagent_graph" in control_plane.__all__
    assert "build_compiled_multiagent" in control_plane.__all__
    assert isinstance(build_multiagent_graph(), StateGraph)
    assert isinstance(build_compiled_multiagent(), CompiledStateGraph)


def test_compiled_multiagent_has_isolated_topology() -> None:
    compiled = build_compiled_multiagent()
    assert isinstance(compiled, CompiledStateGraph)
    assert set(compiled.nodes) == EXPECTED_ISOLATED_NODES
    assert hasattr(compiled, "invoke")
    assert hasattr(compiled, "stream")


def test_compiled_multiagent_checkpointers(tmp_path: Path) -> None:
    assert getattr(build_compiled_multiagent(checkpointer=None), "checkpointer", None) is None

    mem = MemorySaver()
    assert getattr(build_compiled_multiagent(checkpointer=mem), "checkpointer", None) is mem

    db_path = tmp_path / "multiagent_e2e.sqlite"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    try:
        from_alias = build_compiled_multiagent(checkpointer=saver)
        from_isolated = build_compiled_isolated_pipeline(checkpointer=saver)
        assert getattr(from_alias, "checkpointer", None) is saver
        assert set(from_alias.nodes) == EXPECTED_ISOLATED_NODES
        assert set(from_alias.nodes) == set(from_isolated.nodes)
    finally:
        conn.close()
    assert db_path.exists() and db_path.stat().st_size > 0


def test_isolated_pipeline_state_schema() -> None:
    for app in (build_compiled_multiagent(), build_compiled_isolated_pipeline()):
        fields = _schema_field_names(_state_schema(app))
        for key in ("slug", "workdir", "solution_path", "validate_path", "paper_path", "review_path", "review_verdict"):
            assert key in fields
    assert isinstance(build_isolated_pipeline_graph(), StateGraph)
