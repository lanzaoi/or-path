#!/usr/bin/env python3
"""Multi-agent event listener for the OR-Path LangGraph pipeline.

``MultiAgentSnapshotCallback`` is a stateful ``langchain_core`` callback handler
that observes agent hand-offs and tool lifecycles in a running supervisor /
worker graph and keeps a compact, ordered event log (``self.events``) that a
Live Watch snapshot can consume without re-reading logs.

The four agent identities recognised here are the canonical node/role names
used across ``orpath.agents``:

  * ``supervisor``
  * ``or_researcher``
  * ``or_modeler``
  * ``or_verifier_writer``

An agent identity is resolved from three orthogonal signals so the handler is
robust across LangGraph / LangChain run representations:

  * ``serialized`` — the ``{"name": ..., "id": ...}`` dict a run reports;
  * ``tags``       — the tag list attached to a run (LangGraph nodes tag their
    runs with the node name);
  * ``metadata``   — structured metadata (e.g. ``ls_custom_run_id``).

Only *known* agent names produce ``agent_start`` / ``agent_end`` records, so the
many internal model / prompt chains a ReAct agent spawns are ignored and the
event log stays focused on agent-level transitions. Tool lifecycles are tracked
with a monotonically increasing ``step_index`` (one step per ``on_tool_start``)
so consumers can correlate a tool call with the agent that issued it and its
position in the run.

The module is import-safe offline: it only depends on ``langchain_core`` types
and the standard library, and never invokes an LLM.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

__all__ = [
    "KNOWN_AGENT_NAMES",
    "SUPERVISOR_NAME",
    "RESEARCHER_NAME",
    "MODELER_NAME",
    "VERIFIER_WRITER_NAME",
    "MultiAgentSnapshotCallback",
]

# Canonical agent / role names used across the OR-Path multi-agent pipeline.
SUPERVISOR_NAME = "supervisor"
RESEARCHER_NAME = "or_researcher"
MODELER_NAME = "or_modeler"
VERIFIER_WRITER_NAME = "or_verifier_writer"

#: Ordered tuple of recognised agent names. Order is the pipeline order for the
#: three workers; the supervisor sits first. Domain-specific teams (microgrid,
#: tube, routing, …) are recognised too so their agent_start/agent_end events are
#: captured by :class:`MultiAgentSnapshotCallback`.
KNOWN_AGENT_NAMES: tuple[str, ...] = (
    SUPERVISOR_NAME,
    RESEARCHER_NAME,
    MODELER_NAME,
    VERIFIER_WRITER_NAME,
    # Microgrid Dispatch domain team
    "or_microgrid_lead",
    "or_microgrid_auditor",
    "or_microgrid_exact_bound",
    "or_microgrid_heuristic",
    "or_microgrid_realities",
    "or_microgrid_redteam",
)

#: Default cap applied to free-form text captured from tool inputs / outputs.
_DEFAULT_TEXT_LIMIT = 500


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    """Return ``value`` if it is a dict, else ``{}`` (defensive cast)."""
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    """Return ``value`` as a list when it is a list/tuple, else ``[]``."""
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def summarize_text(value: Any, limit: int = _DEFAULT_TEXT_LIMIT) -> str:
    """Return a compact, bounded text summary of a tool input / output.

    ``str`` values are truncated with an explicit ``...[truncated]`` marker.
    Mappings / sequences are rendered via ``repr`` (stable, no JSON schema
    surprises) and likewise truncated. ``None`` becomes the empty string.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = repr(value)
    if limit is not None and limit >= 0 and len(text) > limit:
        text = text[:limit] + "...[truncated]"
    return text


class MultiAgentSnapshotCallback(BaseCallbackHandler):
    """Stateful listener recording agent hand-offs and tool lifecycles.

    The handler is intentionally *append-only*: every recognised lifecycle
    transition appends one structured dict to ``self.events`` and mutates a small
    amount of counter state. ``get_events()`` returns the live list (callers
    should ``list(...)`` it if they intend to mutate).

    Attributes:
        thread_id: LangGraph thread identifier stamped on every event.
        slug: Workspace / run slug stamped on every event.
        workdir: Optional workspace directory (``Path``). Stored resolved but
            never required for the callback to function.
        events: Ordered list of structured event records.
        current_agent: Name of the most recently *started* recognised agent, or
            ``None`` before the first agent starts.
        step_index: Monotonic tool counter, incremented once per
            ``on_tool_start``.
        stage_index: Monotonic stage counter, incremented once per
            ``write_stage_snapshot`` call.
        last_error: Latest error message captured from a failed chain/tool
            run, or ``None`` when the last observed run was successful.
    """

    def __init__(
        self,
        thread_id: str = "default",
        slug: str = "default",
        workdir: Path | str | None = None,
    ) -> None:
        """Create a callback handler.

        Args:
            thread_id: LangGraph thread identifier stamped on every event.
            slug: Run/workspace slug stamped on every event.
            workdir: Optional workspace directory. Accepts ``str`` or
                ``Path``; ``None`` leaves the callback without a workdir.
        """
        super().__init__()
        self.thread_id = thread_id
        self.slug = slug
        self.workdir = Path(workdir).expanduser() if workdir is not None else None
        self.events: list[dict[str, Any]] = []
        self.current_agent: str | None = None
        self.step_index: int = 0
        self.stage_index: int = 0
        self.last_error: str | None = None
        # run_id -> recognised agent name (populated on agent chain start).
        self._agent_runs: dict[UUID, str] = {}
        # run_id -> (tool name, step index) (populated on tool start).
        self._tool_runs: dict[UUID, tuple[str, int]] = {}

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _resolve_agent_name(
        self,
        serialized: Any,
        tags: Any,
        metadata: Any,
    ) -> str | None:
        """Return the recognised agent name encoded in the run signals, else ``None``.

        Resolution order:

        1. exact match against ``KNOWN_AGENT_NAMES`` from any candidate string
           (serialised ``name``/``id``, tag, metadata value);
        2. substring match (e.g. a node tagged ``"node:or_researcher"``), while
           ignoring tool-handoff tokens such as ``transfer_to_or_researcher``
           which carry an agent name but are tools, not chains.
        """
        candidates: list[str] = []
        serialized_dict = _as_dict(serialized)
        for key in ("name", "id"):
            value = serialized_dict.get(key)
            if isinstance(value, str):
                candidates.append(value)
        for tag in _as_list(tags):
            if isinstance(tag, str):
                candidates.append(tag)
        metadata_dict = _as_dict(metadata)
        for key in ("agent", "name", "role", "ls_custom_run_id"):
            value = metadata_dict.get(key)
            if isinstance(value, str):
                candidates.append(value)

        known = set(KNOWN_AGENT_NAMES)
        for candidate in candidates:
            if candidate in known:
                return candidate

        for known_name in KNOWN_AGENT_NAMES:
            for candidate in candidates:
                if "transfer_to_" in candidate:
                    continue
                if known_name in candidate:
                    return known_name
        return None

    def _resolve_tool_name(
        self,
        serialized: Any,
        tags: Any,
        metadata: Any,
    ) -> str | None:
        """Return the tool name encoded in the run signals, else ``None``.

        Priority is ``serialized['name']`` (the canonical signal a LangChain
        tool reports), then ``serialized['id']``, then structured metadata,
        then tags. Only the fallbacks scan tag lists because those carry unrelated
        LangChain bookkeeping tags (``ls1``, ``tool``, ...).
        """
        serialized_dict = _as_dict(serialized)
        for key in ("name", "tool_name", "id"):
            value = serialized_dict.get(key)
            if isinstance(value, str) and value:
                return value

        candidates: list[str] = []
        metadata_dict = _as_dict(metadata)
        for key in ("tool_name", "name"):
            value = metadata_dict.get(key)
            if isinstance(value, str) and value:
                candidates.append(value)
        for tag in _as_list(tags):
            if isinstance(tag, str) and not tag.startswith("ls"):
                candidates.append(tag)

        for candidate in candidates:
            if candidate:
                return candidate
        return None

    def _record(self, event: dict[str, Any]) -> None:
        """Append a structured event, stamping the thread/slug context."""
        event.setdefault("thread_id", self.thread_id)
        event.setdefault("slug", self.slug)
        self.events.append(event)
        self._append_log(event)

    # ------------------------------------------------------------------ #
    # Real-time disk persistence
    # ------------------------------------------------------------------ #
    def _log_path(self) -> Path:
        """Return the per-slug agent log path (``outputs/.agents/<slug>/<slug>.log``)."""
        assert self.workdir is not None  # guarded by callers
        return self.workdir / "outputs" / ".agents" / self.slug / f"{self.slug}.log"

    def _append_log(self, event: dict[str, Any]) -> None:
        """Append a standard JSONL event line to the per-slug agent log.

        The log is created lazily and its parent directories are created
        with ``mkdir(parents=True, exist_ok=True)``. The line is a single
        self-contained JSON object so it can be tailed or replayed without a
        custom parser.
        """
        if self.workdir is None:
            return
        line = {
            "utc": _utc_now_iso(),
            "event": event.get("kind"),
            "agent": event.get("agent"),
            "tool": event.get("tool"),
            "step": event.get("step"),
            "thread_id": self.thread_id,
            "slug": self.slug,
        }
        log_path = self._log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")

    def write_stage_snapshot(
        self,
        node_name: str | None = None,
        status: str = "ok",
    ) -> Path:
        """Increment the stage counter and persist a stage snapshot to disk.

        The snapshot is written to
        ``runs/<thread_id>/stages/<NNNN>_<node>.json`` (parents auto-created)
        and a matching ``stage`` line is appended to the per-slug agent log so
        Live Watch can observe the latest state without re-reading the whole
        event log.

        Args:
            node_name: Node / agent name used in the file name and ``node``
                field. Falls back to ``current_agent`` then ``"supervisor"``.
            status: Lifecycle status stamped on the snapshot (``"ok"``,
                ``"error"``, ...).

        Returns:
            The path of the written JSON snapshot.

        Raises:
            ValueError: if the handler has no ``workdir`` configured.
        """
        if self.workdir is None:
            raise ValueError(
                "write_stage_snapshot requires a configured workdir"
            )

        self.stage_index += 1
        stage = self.stage_index
        node = node_name or self.current_agent or SUPERVISOR_NAME

        stages_dir = self.workdir / "runs" / self.thread_id / "stages"
        stages_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = stages_dir / f"{stage:04d}_{node}.json"

        snapshot = {
            "utc": _utc_now_iso(),
            "node": node,
            "stage": stage,
            "thread_id": self.thread_id,
            "slug": self.slug,
            "step_index": self.step_index,
            "status": status,
            "current_agent": self.current_agent,
            "last_error": self.last_error,
        }
        snapshot_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, default=str, indent=2),
            encoding="utf-8",
        )

        self._append_log({
            "kind": "stage",
            "agent": node,
            "step": self.step_index,
        })
        return snapshot_path

    # ------------------------------------------------------------------ #
    # BaseCallbackHandler lifecycle
    # ------------------------------------------------------------------ #
    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Record an ``agent_start`` event when a recognised agent chain begins."""
        agent = self._resolve_agent_name(serialized, tags, metadata)
        if agent is None:
            return None

        self.current_agent = agent
        self._agent_runs[run_id] = agent
        self._record(
            {
                "t": _utc_now_iso(),
                "kind": "agent_start",
                "agent": agent,
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "step": self.step_index,
            }
        )
        return None

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Record an ``agent_end`` event when a recognised agent chain ends."""
        agent = self._agent_runs.get(run_id)
        if agent is None:
            return None

        self._record(
            {
                "t": _utc_now_iso(),
                "kind": "agent_end",
                "agent": agent,
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "step": self.step_index,
            }
        )
        # Keep the on-disk stage log fresh as soon as an agent finishes.
        if self.workdir is not None:
            self.write_stage_snapshot(node_name=agent, status="ok")
        return None

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Record the error message and emit an ``error`` stage snapshot."""
        self.last_error = f"{type(error).__name__}: {error}"
        self._record(
            {
                "t": _utc_now_iso(),
                "kind": "chain_error",
                "agent": self.current_agent,
                "error": self.last_error,
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "step": self.step_index,
            }
        )
        if self.workdir is not None:
            self.write_stage_snapshot(node_name=self.current_agent, status="error")
        return None

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Record a ``tool_start`` event and advance ``step_index`` by one."""
        tool_name = self._resolve_tool_name(serialized, tags, metadata) or "unknown_tool"
        self.step_index += 1
        step = self.step_index
        self._tool_runs[run_id] = (tool_name, step)
        self._record(
            {
                "t": _utc_now_iso(),
                "kind": "tool_start",
                "agent": self.current_agent,
                "tool": tool_name,
                "input": summarize_text(input_str),
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "step": step,
            }
        )
        return None

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Record a ``tool_end`` event with a bounded summary of the output."""
        tool_run = self._tool_runs.get(run_id)
        if tool_run is None:
            return None

        tool_name, step = tool_run
        self._record(
            {
                "t": _utc_now_iso(),
                "kind": "tool_end",
                "agent": self.current_agent,
                "tool": tool_name,
                "output": summarize_text(output),
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "step": step,
            }
        )
        # Keep the on-disk stage log fresh after each tool completes.
        if self.workdir is not None:
            self.write_stage_snapshot(node_name=None, status="ok")
        return None

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Record the error message and emit an ``error`` stage snapshot."""
        self.last_error = f"{type(error).__name__}: {error}"
        self._record(
            {
                "t": _utc_now_iso(),
                "kind": "tool_error",
                "agent": self.current_agent,
                "error": self.last_error,
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "step": self.step_index,
            }
        )
        if self.workdir is not None:
            self.write_stage_snapshot(node_name=self.current_agent, status="error")
        return None

    # ------------------------------------------------------------------ #
    # Public accessors
    # ------------------------------------------------------------------ #
    def get_events(self) -> list[dict[str, Any]]:
        """Return the ordered list of recorded lifecycle events."""
        return self.events

    def agent_events(self, agent: str) -> list[dict[str, Any]]:
        """Return the agent-lifecycle events (start/end) for ``agent``.

        Only ``agent_start`` / ``agent_end`` records are returned; tool events
        that merely carry the ``agent`` attribution are intentionally excluded.
        """
        return [
            event
            for event in self.events
            if event.get("kind") in ("agent_start", "agent_end")
            and event.get("agent") == agent
        ]

    def tool_events(self) -> list[dict[str, Any]]:
        """Return only the tool-lifecycle events (start + end)."""
        return [
            event
            for event in self.events
            if event.get("kind") in ("tool_start", "tool_end")
        ]


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    import uuid

    from orpath.agents.callbacks import MultiAgentSnapshotCallback

    cb = MultiAgentSnapshotCallback(thread_id="t-demo", slug="demo")
    cb.on_chain_start({"name": "supervisor"}, {}, run_id=uuid.uuid4())
    cb.on_chain_start({"name": "or_modeler"}, {}, run_id=uuid.uuid4())
    tool_run = uuid.uuid4()
    cb.on_tool_start({"name": "execute_or_solver"}, "mode=networkx", run_id=tool_run)
    cb.on_tool_end("ok", run_id=tool_run)
    for event in cb.get_events():
        print(event["kind"], event.get("agent"), event.get("tool"), event.get("step"))
