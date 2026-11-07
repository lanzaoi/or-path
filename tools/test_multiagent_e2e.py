#!/usr/bin/env python3
"""End-to-end integration tests for the ControlPlane multi-agent entry points.

These tests exercise the public seam added in Task 6:

  * ``orpath.control_plane.build_multiagent_graph``
  * ``orpath.control_plane.build_compiled_multiagent``

They cover the four integration concerns requested for the E2E gate:

  1. **Import surface** — both aliases are importable from
     ``orpath.control_plane`` and listed in ``__all__``.
  2. **Full graph structure** — the compiled supervisor graph exposes the
     ``__start__`` node, the ``supervisor`` node and the four elite pipeline workers
     (``or_analyst`` → ``or_modeler`` → ``or_writer`` → ``or_reviewer``).
  3. **Persistence** — ``SqliteSaver`` (and ``MemorySaver``) checkpointers are
     accepted and wired into the compiled graph.
  4. **State schema** — the graph's ``state_schema`` declares a ``messages``
     field (LangChain message history).

Everything is offline-safe: the supervisor factory falls back to a placeholder
API key and the tests never invoke the LLM.

Run:
    .venv/bin/python -m pytest tools/test_multiagent_e2e.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402
from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402
from langgraph.graph.state import CompiledStateGraph, StateGraph  # noqa: E402

from orpath.agents.supervisor import (  # noqa: E402
    EXPECTED_SUPERVISOR_NODES,
    SUPERVISOR_NAME,
    build_compiled_supervisor,
    build_supervisor_graph,
)
from orpath.agents.workers import (  # noqa: E402
    ANALYST_NAME,
    MODELER_NAME,
    REVIEWER_NAME,
    WORKER_AGENT_NAMES,
    WRITER_NAME,
)
from orpath.control_plane import (  # noqa: E402
    build_compiled_multiagent,
    build_multiagent_graph,
)

pytestmark = pytest.mark.filterwarnings(
    "ignore:create_react_agent has been moved",
    "ignore:No supported",
)

#: Every node a fully-compiled default supervisor graph must contain.
EXPECTED_MULTIAGENT_NODES: frozenset[str] = frozenset(
    {"__start__", SUPERVISOR_NAME, *WORKER_AGENT_NAMES}
)


def _state_schema(graph: Any) -> Any:
    """Return a graph's state schema across LangGraph API variants.

    Un-compiled ``StateGraph`` exposes ``.state_schema``; compiled
    ``CompiledStateGraph`` exposes it through ``.builder.state_schema``. Accept
    either so the test stays valid across LangGraph releases.
    """
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
    """Best-effort extraction of TypedDict field names from a schema object."""
    annotations = getattr(schema, "__annotations__", None)
    if annotations:
        return set(annotations)
    # Fallback: some schemas expose a plain dict of fields.
    if isinstance(schema, dict):
        return set(schema)
    raise AssertionError(f"cannot read fields from state schema: {schema!r}")


# --------------------------------------------------------------------------- #
# 1. Import surface (ControlPlane re-export contract)
# --------------------------------------------------------------------------- #
def test_control_plane_exposes_multiagent_builders() -> None:
    """The two aliases must be importable from the ControlPlane entry point."""
    assert callable(build_multiagent_graph)
    assert callable(build_compiled_multiagent)


def test_control_plane_all_lists_multiagent_builders() -> None:
    """Both aliases belong to the public ``__all__`` surface."""
    import orpath.control_plane as control_plane

    assert "build_multiagent_graph" in control_plane.__all__
    assert "build_compiled_multiagent" in control_plane.__all__


def test_control_plane_builders_delegate_to_supervisor() -> None:
    """The aliases build the same graph objects as the supervisor module."""
    from orpath.control_plane import (
        build_compiled_multiagent as alias_compiled,
        build_multiagent_graph as alias_graph,
    )

    assert alias_graph is build_multiagent_graph
    assert alias_compiled is build_compiled_multiagent
    assert isinstance(alias_graph(), StateGraph)
    assert isinstance(alias_compiled(), CompiledStateGraph)


# --------------------------------------------------------------------------- #
# 2. Full compiled graph structure
# --------------------------------------------------------------------------- #
def test_build_multiagent_graph_returns_state_graph() -> None:
    graph = build_multiagent_graph()
    assert isinstance(graph, StateGraph)
    assert not isinstance(graph, CompiledStateGraph)
    # The un-compiled builder materialises the worker + supervisor nodes but not
    # the synthetic ``__start__`` node (that appears only after compilation).
    assert set(graph.nodes) >= {SUPERVISOR_NAME, *WORKER_AGENT_NAMES}


def test_compiled_multiagent_has_full_topology() -> None:
    compiled = build_compiled_multiagent()
    assert isinstance(compiled, CompiledStateGraph)
    # Exact node set: __start__ + supervisor + the four elite workers.
    assert set(compiled.nodes) == EXPECTED_MULTIAGENT_NODES
    # The supervisor node must exist alongside the pipeline workers.
    assert SUPERVISOR_NAME in compiled.nodes
    assert {ANALYST_NAME, MODELER_NAME, WRITER_NAME, REVIEWER_NAME} <= set(compiled.nodes)


def test_compiled_multiagent_topology_matches_supervisor_constant() -> None:
    compiled = build_compiled_multiagent()
    assert EXPECTED_SUPERVISOR_NODES == (SUPERVISOR_NAME, *WORKER_AGENT_NAMES)
    assert set(EXPECTED_SUPERVISOR_NODES) <= set(compiled.nodes)


def test_compiled_multiagent_is_invokable() -> None:
    compiled = build_compiled_multiagent()
    assert hasattr(compiled, "invoke")
    assert hasattr(compiled, "stream")


def test_compiled_multiagent_edges_route_to_supervisor() -> None:
    """Every worker routes back to the supervisor (hub topology)."""
    compiled = build_compiled_multiagent()
    edges = set(compiled.builder.edges)
    assert ("__start__", SUPERVISOR_NAME) in edges
    for worker in WORKER_AGENT_NAMES:
        assert (worker, SUPERVISOR_NAME) in edges


def test_compiled_multiagent_no_checkpointer_is_stateless() -> None:
    compiled = build_compiled_multiagent(checkpointer=None)
    assert getattr(compiled, "checkpointer", None) is None


# --------------------------------------------------------------------------- #
# 3. Persistence — checkpointer support
# --------------------------------------------------------------------------- #
def test_compiled_multiagent_with_memory_checkpointer() -> None:
    checkpointer = MemorySaver()
    compiled = build_compiled_multiagent(checkpointer=checkpointer)
    assert isinstance(compiled, CompiledStateGraph)
    assert getattr(compiled, "checkpointer", None) is checkpointer


def test_compiled_multiagent_with_sqlite_saver(tmp_path: Path) -> None:
    """A real on-disk ``SqliteSaver`` compiles and is wired into the graph."""
    db_path = tmp_path / "multiagent_e2e.sqlite"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    try:
        compiled = build_compiled_multiagent(checkpointer=saver)
        assert isinstance(compiled, CompiledStateGraph)
        assert getattr(compiled, "checkpointer", None) is saver
        # Full topology is preserved with persistence enabled.
        assert set(compiled.nodes) == EXPECTED_MULTIAGENT_NODES
    finally:
        conn.close()
    # ``setup()`` materialises the checkpoint tables on disk.
    assert db_path.exists() and db_path.stat().st_size > 0


def test_compiled_multiagent_matches_supervisor_checkpointer_wiring(
    tmp_path: Path,
) -> None:
    """Alias and supervisor builder accept checkpointers identically."""
    db_path = tmp_path / "shared.sqlite"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    try:
        from_alias = build_compiled_multiagent(checkpointer=saver)
        from_supervisor = build_compiled_supervisor(checkpointer=saver)
        assert isinstance(from_alias, CompiledStateGraph)
        assert isinstance(from_supervisor, CompiledStateGraph)
        assert set(from_alias.nodes) == set(from_supervisor.nodes)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# 4. State schema — messages field
# --------------------------------------------------------------------------- #
def test_uncompiled_multiagent_state_schema_contains_messages() -> None:
    schema = _state_schema(build_multiagent_graph())
    fields = _schema_field_names(schema)
    assert "messages" in fields, f"state schema missing 'messages': {fields}"


def test_compiled_multiagent_state_schema_contains_messages() -> None:
    compiled = build_compiled_multiagent()
    schema = _state_schema(compiled)
    fields = _schema_field_names(schema)
    assert "messages" in fields, f"state schema missing 'messages': {fields}"


def test_compiled_multiagent_state_schema_matches_supervisor() -> None:
    compiled = build_compiled_multiagent()
    assert _schema_field_names(_state_schema(compiled)) == set(
        _schema_field_names(_state_schema(build_supervisor_graph()))
    )


# --------------------------------------------------------------------------- #
# 5. Cross-checks against the supervisor module surface
# --------------------------------------------------------------------------- #
def test_expected_node_constant_is_complete() -> None:
    """The supervisor node constant must cover the whole pipeline roster."""
    assert EXPECTED_SUPERVISOR_NODES == (
        SUPERVISOR_NAME,
        ANALYST_NAME,
        MODELER_NAME,
        WRITER_NAME,
        REVIEWER_NAME,
    )


# --------------------------------------------------------------------------- #
# 6. Artifact-driven isolated pipeline graph (Feynman seam)
# --------------------------------------------------------------------------- #
def test_control_plane_exposes_isolated_pipeline_builders() -> None:
    from orpath.control_plane import (
        build_compiled_isolated_pipeline,
        build_isolated_pipeline_graph,
    )

    assert callable(build_isolated_pipeline_graph)
    assert callable(build_compiled_isolated_pipeline)
    assert isinstance(build_isolated_pipeline_graph(), StateGraph)
    assert isinstance(build_compiled_isolated_pipeline(), CompiledStateGraph)


def test_isolated_pipeline_nodes_and_topology() -> None:
    from orpath.agents.supervisor import ISOLATED_PIPELINE_NODES
    from orpath.control_plane import build_compiled_isolated_pipeline

    app = build_compiled_isolated_pipeline()
    expected = {"__start__", *ISOLATED_PIPELINE_NODES}
    assert set(app.nodes) == expected


def test_isolated_pipeline_state_schema() -> None:
    from orpath.control_plane import build_compiled_isolated_pipeline

    app = build_compiled_isolated_pipeline()
    schema = _state_schema(app)
    fields = _schema_field_names(schema)
    assert "slug" in fields
    assert "solution_path" in fields
    assert "validate_path" in fields
    assert "paper_path" in fields
    assert "review_path" in fields
    assert "review_verdict" in fields


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:langsmith"]))
