"""Unit tests for the OR-Path multi-agent event listener.

Covers ``orpath/agents/callbacks.py`` — the stateful
``MultiAgentSnapshotCallback`` LangChain callback handler that records agent
hand-offs and tool lifecycles for a Live Watch snapshot:

  * construction / parameter storage (``thread_id``, ``slug``, ``workdir``)
  * ``on_chain_start`` / ``on_chain_end`` produce structured ``agent_start`` /
    ``agent_end`` records
  * ``on_tool_start`` / ``on_tool_end`` produce structured ``tool_start`` /
    ``tool_end`` records and advance ``step_index``
  * ``current_agent`` follows agent switches
  * non-agent internal chains are ignored so the log stays agent-focused
  * recognition works from ``serialized``, ``tags`` and ``metadata`` signals
  * ``get_events`` returns the full ordered event list

These tests never touch the network or invoke an LLM: the handler is pure
event plumbing over ``langchain_core`` types.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langchain_core.callbacks import BaseCallbackHandler  # noqa: E402

from orpath.agents.callbacks import (  # noqa: E402
    KNOWN_AGENT_NAMES,
    MODELER_NAME,
    RESEARCHER_NAME,
    MultiAgentSnapshotCallback,
    SUPERVISOR_NAME,
    VERIFIER_WRITER_NAME,
)


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture()
def callback() -> MultiAgentSnapshotCallback:
    return MultiAgentSnapshotCallback(thread_id="thread-1", slug="slug-1")


def _chain_start(cb: MultiAgentSnapshotCallback, name: str, **kwargs) -> "object":
    run_id = kwargs.pop("run_id", uuid4())
    cb.on_chain_start({"name": name}, {"input": "x"}, run_id=run_id, **kwargs)
    return run_id


# --------------------------------------------------------------------------- #
# 1. Construction / parameter storage
# --------------------------------------------------------------------------- #
def test_is_base_callback_handler() -> None:
    cb = MultiAgentSnapshotCallback()
    assert isinstance(cb, BaseCallbackHandler)


def test_init_defaults() -> None:
    cb = MultiAgentSnapshotCallback()
    assert cb.thread_id == "default"
    assert cb.slug == "default"
    assert cb.workdir is None
    assert cb.events == []
    assert cb.current_agent is None
    assert cb.step_index == 0


def test_init_custom_params_stored(tmp_path: Path) -> None:
    cb = MultiAgentSnapshotCallback(thread_id="t-9", slug="s-9", workdir=tmp_path)
    assert cb.thread_id == "t-9"
    assert cb.slug == "s-9"
    assert cb.workdir == tmp_path


def test_init_accepts_string_workdir(tmp_path: Path) -> None:
    cb = MultiAgentSnapshotCallback(workdir=str(tmp_path))
    assert isinstance(cb.workdir, Path)
    assert cb.workdir == tmp_path


def test_known_agent_names_cover_pipeline() -> None:
    assert set(KNOWN_AGENT_NAMES) == {
        SUPERVISOR_NAME,
        RESEARCHER_NAME,
        MODELER_NAME,
        VERIFIER_WRITER_NAME,
    }


# --------------------------------------------------------------------------- #
# 2. Chain lifecycle -> agent_start / agent_end
# --------------------------------------------------------------------------- #
def test_chain_start_records_agent_start(callback: MultiAgentSnapshotCallback) -> None:
    run_id = _chain_start(callback, RESEARCHER_NAME)

    assert len(callback.events) == 1
    event = callback.events[0]
    assert event["kind"] == "agent_start"
    assert event["agent"] == RESEARCHER_NAME
    assert event["thread_id"] == "thread-1"
    assert event["slug"] == "slug-1"
    assert event["run_id"] == str(run_id)
    assert event["step"] == 0


def test_chain_end_records_agent_end_for_same_run(
    callback: MultiAgentSnapshotCallback,
) -> None:
    run_id = _chain_start(callback, MODELER_NAME)
    callback.on_chain_end({"output": "done"}, run_id=run_id)

    assert [e["kind"] for e in callback.events] == ["agent_start", "agent_end"]
    assert callback.events[1]["agent"] == MODELER_NAME
    assert callback.events[1]["run_id"] == str(run_id)


def test_chain_end_without_start_is_ignored(callback: MultiAgentSnapshotCallback) -> None:
    callback.on_chain_end({"output": "orphan"}, run_id=uuid4())
    assert callback.events == []


def test_non_agent_chain_is_ignored(callback: MultiAgentSnapshotCallback) -> None:
    _chain_start(callback, "model_request")
    _chain_start(callback, "prompt_builder")
    assert callback.events == []
    assert callback.current_agent is None


# --------------------------------------------------------------------------- #
# 3. Agent switching updates current_agent
# --------------------------------------------------------------------------- #
def test_current_agent_updates_on_switch(callback: MultiAgentSnapshotCallback) -> None:
    _chain_start(callback, RESEARCHER_NAME)
    assert callback.current_agent == RESEARCHER_NAME

    _chain_start(callback, MODELER_NAME)
    assert callback.current_agent == MODELER_NAME

    _chain_start(callback, VERIFIER_WRITER_NAME)
    assert callback.current_agent == VERIFIER_WRITER_NAME

    starts = [e for e in callback.events if e["kind"] == "agent_start"]
    assert [e["agent"] for e in starts] == [
        RESEARCHER_NAME,
        MODELER_NAME,
        VERIFIER_WRITER_NAME,
    ]


def test_supervisor_chain_recognised(callback: MultiAgentSnapshotCallback) -> None:
    _chain_start(callback, SUPERVISOR_NAME)
    assert callback.current_agent == SUPERVISOR_NAME


# --------------------------------------------------------------------------- #
# 4. Tool lifecycle -> tool_start / tool_end + step_index
# --------------------------------------------------------------------------- #
def test_tool_lifecycle_records_start_and_end(callback: MultiAgentSnapshotCallback) -> None:
    _chain_start(callback, MODELER_NAME)
    tool_run = uuid4()
    callback.on_tool_start({"name": "execute_or_solver"}, "mode=networkx", run_id=tool_run)
    callback.on_tool_end("solver ok", run_id=tool_run)

    kinds = [e["kind"] for e in callback.events]
    assert kinds == ["agent_start", "tool_start", "tool_end"]

    start = callback.events[1]
    assert start["tool"] == "execute_or_solver"
    assert start["input"] == "mode=networkx"
    assert start["agent"] == MODELER_NAME

    end = callback.events[2]
    assert end["tool"] == "execute_or_solver"
    assert end["output"] == "solver ok"
    assert end["agent"] == MODELER_NAME


def test_step_index_increments_per_tool_start(callback: MultiAgentSnapshotCallback) -> None:
    assert callback.step_index == 0

    callback.on_tool_start({"name": "execute_or_solver"}, "mode=networkx", run_id=uuid4())
    assert callback.step_index == 1

    callback.on_tool_start(
        {"name": "transfer_to_or_verifier_writer"}, "{}", run_id=uuid4()
    )
    assert callback.step_index == 2

    callback.on_tool_start({"name": "read_problem_file"}, "x.md", run_id=uuid4())
    assert callback.step_index == 3

    steps = [e["step"] for e in callback.events if e["kind"] == "tool_start"]
    assert steps == [1, 2, 3]


def test_step_index_unchanged_by_chain_events(callback: MultiAgentSnapshotCallback) -> None:
    run_id = _chain_start(callback, MODELER_NAME)
    callback.on_chain_end({"output": "ok"}, run_id=run_id)
    assert callback.step_index == 0


def test_tool_end_without_start_is_ignored(callback: MultiAgentSnapshotCallback) -> None:
    callback.on_tool_end("orphan", run_id=uuid4())
    assert callback.events == []
    assert callback.step_index == 0


def test_transfer_handoff_tool_recognised(callback: MultiAgentSnapshotCallback) -> None:
    _chain_start(callback, SUPERVISOR_NAME)
    callback.on_tool_start(
        {"name": "transfer_to_or_researcher"}, "{}", run_id=uuid4()
    )
    assert callback.events[-1]["tool"] == "transfer_to_or_researcher"
    assert callback.events[-1]["agent"] == SUPERVISOR_NAME


def test_tool_name_from_metadata_fallback(callback: MultiAgentSnapshotCallback) -> None:
    callback.on_tool_start(
        {"name": ""}, "{}", run_id=uuid4(), metadata={"tool_name": "execute_or_solver"}
    )
    assert callback.events[-1]["tool"] == "execute_or_solver"


def test_tool_output_summary_is_bounded(callback: MultiAgentSnapshotCallback) -> None:
    tool_run = uuid4()
    callback.on_tool_start({"name": "execute_or_solver"}, "{}", run_id=tool_run)
    callback.on_tool_end({"result": "y" * 2000}, run_id=tool_run)
    output = callback.events[-1]["output"]
    assert "truncated" in output
    assert len(output) < 2000


# --------------------------------------------------------------------------- #
# 5. Recognition from tags / metadata
# --------------------------------------------------------------------------- #
def test_agent_recognised_from_tags(callback: MultiAgentSnapshotCallback) -> None:
    _chain_start(callback, "LangChain", tags=["node:or_modeler", "ls1"])
    assert callback.current_agent == MODELER_NAME
    assert callback.events[-1]["agent"] == MODELER_NAME


def test_agent_recognised_from_metadata(callback: MultiAgentSnapshotCallback) -> None:
    _chain_start(callback, "LangChain", metadata={"agent": VERIFIER_WRITER_NAME})
    assert callback.events[-1]["agent"] == VERIFIER_WRITER_NAME


def test_transfer_to_tag_does_not_register_agent(callback: MultiAgentSnapshotCallback) -> None:
    _chain_start(callback, "LangChain", tags=["transfer_to_or_researcher"])
    assert callback.events == []
    assert callback.current_agent is None


# --------------------------------------------------------------------------- #
# 6. get_events / helpers
# --------------------------------------------------------------------------- #
def test_get_events_returns_all_ordered_events(callback: MultiAgentSnapshotCallback) -> None:
    _chain_start(callback, SUPERVISOR_NAME)
    _chain_start(callback, MODELER_NAME)
    callback.on_tool_start({"name": "execute_or_solver"}, "{}", run_id=uuid4())

    events = callback.get_events()
    assert isinstance(events, list)
    assert [e["kind"] for e in events] == ["agent_start", "agent_start", "tool_start"]


def test_agent_events_and_tool_events_filters(callback: MultiAgentSnapshotCallback) -> None:
    _chain_start(callback, MODELER_NAME)
    tool_run = uuid4()
    callback.on_tool_start({"name": "execute_or_solver"}, "{}", run_id=tool_run)
    callback.on_tool_end("ok", run_id=tool_run)

    assert len(callback.agent_events(MODELER_NAME)) == 1
    assert len(callback.tool_events()) == 2
    assert callback.tool_events()[0]["kind"] == "tool_start"
    assert callback.tool_events()[1]["kind"] == "tool_end"


# --------------------------------------------------------------------------- #
# 7. Real-time stage snapshots & agent log
# --------------------------------------------------------------------------- #
_SNAPSHOT_FIELDS = (
    "utc",
    "node",
    "stage",
    "thread_id",
    "slug",
    "step_index",
    "status",
    "current_agent",
    "last_error",
)


def test_write_stage_snapshot_creates_stage_json(tmp_path: Path) -> None:
    cb = MultiAgentSnapshotCallback(thread_id="thread-1", slug="slug-1", workdir=tmp_path)
    cb.current_agent = MODELER_NAME

    path = cb.write_stage_snapshot(node_name=MODELER_NAME, status="ok")

    assert path == tmp_path / "runs" / "thread-1" / "stages" / f"0001_{MODELER_NAME}.json"
    assert path.exists()

    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(_SNAPSHOT_FIELDS).issubset(data)
    assert data["utc"]
    datetime.fromisoformat(data["utc"])  # valid ISO-8601
    assert data["node"] == MODELER_NAME
    assert data["stage"] == 1
    assert data["thread_id"] == "thread-1"
    assert data["slug"] == "slug-1"
    assert data["step_index"] == 0
    assert data["status"] == "ok"
    assert data["current_agent"] == MODELER_NAME
    assert data["last_error"] is None


def test_stage_index_increments_and_names_files(tmp_path: Path) -> None:
    cb = MultiAgentSnapshotCallback(workdir=tmp_path)

    first = cb.write_stage_snapshot(node_name="supervisor")
    second = cb.write_stage_snapshot(node_name="supervisor")

    assert cb.stage_index == 2
    assert first.name == "0001_supervisor.json"
    assert second.name == "0002_supervisor.json"
    assert second.parent == first.parent


def test_write_stage_snapshot_falls_back_to_supervisor(tmp_path: Path) -> None:
    cb = MultiAgentSnapshotCallback(workdir=tmp_path)

    path = cb.write_stage_snapshot()

    assert path.name == "0001_supervisor.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["node"] == "supervisor"
    assert data["current_agent"] is None


def test_write_stage_snapshot_requires_workdir() -> None:
    cb = MultiAgentSnapshotCallback()
    with pytest.raises(ValueError):
        cb.write_stage_snapshot()


def test_chain_end_auto_writes_stage_snapshot(tmp_path: Path) -> None:
    cb = MultiAgentSnapshotCallback(thread_id="thread-1", slug="slug-1", workdir=tmp_path)
    run_id = _chain_start(cb, MODELER_NAME)
    cb.on_chain_end({"output": "done"}, run_id=run_id)

    stages_dir = tmp_path / "runs" / "thread-1" / "stages"
    assert stages_dir.is_dir()
    files = sorted(stages_dir.glob("0001_*.json"))
    assert len(files) == 1
    assert files[0].name == f"0001_{MODELER_NAME}.json"

    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["node"] == MODELER_NAME
    assert data["status"] == "ok"


def test_tool_end_auto_writes_stage_snapshot(tmp_path: Path) -> None:
    cb = MultiAgentSnapshotCallback(thread_id="thread-1", slug="slug-1", workdir=tmp_path)
    run_id = _chain_start(cb, MODELER_NAME)
    cb.on_chain_end({"output": "done"}, run_id=run_id)
    tool_run = uuid4()
    cb.on_tool_start({"name": "execute_or_solver"}, "{}", run_id=tool_run)
    cb.on_tool_end("solver ok", run_id=tool_run)

    stages_dir = tmp_path / "runs" / "thread-1" / "stages"
    files = sorted(stages_dir.glob("*.json"))
    # agent end -> stage 0001, tool end -> stage 0002
    assert [f.name for f in files] == [
        f"0001_{MODELER_NAME}.json",
        f"0002_{MODELER_NAME}.json",
    ]
    assert cb.step_index == 1
    assert json.loads(files[1].read_text(encoding="utf-8"))["step_index"] == 1


def test_chain_error_writes_error_snapshot(tmp_path: Path) -> None:
    cb = MultiAgentSnapshotCallback(workdir=tmp_path)
    _chain_start(cb, RESEARCHER_NAME)
    cb.on_chain_error(RuntimeError("boom"), run_id=uuid4())

    assert cb.last_error is not None
    assert "boom" in cb.last_error
    data = json.loads(
        (tmp_path / "runs" / cb.thread_id / "stages" / f"0001_{RESEARCHER_NAME}.json")
        .read_text(encoding="utf-8")
    )
    assert data["status"] == "error"
    assert data["last_error"] == cb.last_error


def test_agent_log_file_created_and_appended(tmp_path: Path) -> None:
    cb = MultiAgentSnapshotCallback(thread_id="thread-1", slug="slug-1", workdir=tmp_path)
    run_id = _chain_start(cb, SUPERVISOR_NAME)
    cb.on_chain_end({"output": "done"}, run_id=run_id)

    log_path = tmp_path / "outputs" / ".agents" / "slug-1" / "slug-1.log"
    assert log_path.exists()

    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines, "log should not be empty"
    records = [json.loads(ln) for ln in lines]
    assert any(rec.get("event") == "stage" for rec in records)
    stage_records = [rec for rec in records if rec.get("event") == "stage"]
    assert stage_records[0]["thread_id"] == "thread-1"
    assert stage_records[0]["slug"] == "slug-1"


def test_log_append_is_incremental(tmp_path: Path) -> None:
    cb = MultiAgentSnapshotCallback(workdir=tmp_path)
    cb.write_stage_snapshot(node_name="supervisor")
    cb.write_stage_snapshot(node_name="supervisor")

    log_path = tmp_path / "outputs" / ".agents" / cb.slug / f"{cb.slug}.log"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2


def test_no_workdir_does_not_write(tmp_path: Path) -> None:
    cb = MultiAgentSnapshotCallback(workdir=None)
    run_id = _chain_start(cb, SUPERVISOR_NAME)
    cb.on_chain_end({"output": "done"}, run_id=run_id)

    assert cb.stage_index == 0
    assert cb.events  # in-memory events still recorded
    assert list(tmp_path.glob("runs/**")) == []
    assert list(tmp_path.glob("outputs/**")) == []
