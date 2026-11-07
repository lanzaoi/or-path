#!/usr/bin/env python3
"""Generic anti-early-stopping guard hooks for LangGraph supervisors.

Domain supervisors built on ``langgraph_supervisor.create_supervisor`` are prone
to one specific failure mode: a lazy lead agent answers a request with a bare
text reply (no ``tool_calls``) before the required specialist stages have
actually run.  ``orpath/agents/supervisor.py`` and
``orpath/agents/domains/tube.py`` each shipped a hand-rolled
``*_guard_post_hook`` closing over a hard-coded stage order.

This module extracts that logic into a single, domain-agnostic factory so any
new domain team (routing, scheduling, microgrid, cutting stock, …) can enforce
its own stage order without copy-pasting the hook:

    from orpath.agents.guard_factory import create_domain_guard_hook

    hook = create_domain_guard_hook(
        stage_order=ROUTING_PIPELINE_STAGE_ORDER,
        guard_call_ids=ROUTING_GUARD_CALL_IDS,
    )
    create_supervisor(..., post_model_hook=hook)

Behaviour contract of the produced ``post_model_hook``
------------------------------------------------------

Given the supervisor state produced after a model call:

* ``messages`` empty (or missing) → ``{}`` (pass through).
* newest message is not an ``AIMessage`` → ``{}``.
* newest ``AIMessage`` already carries ``tool_calls`` → ``{}`` (the lead is
  routing, never second-guess it).
* otherwise the hook computes which stages in ``stage_order`` have already been
  handed off to.  The *first* stage that is still missing wins (so a skipped
  early stage is re-injected even when later stages are done).
* if every stage is complete → ``{}``: a bare final reply is permitted.
* otherwise an ``AIMessage`` is injected that calls
  ``transfer_prefix + next_worker``.  The lazy reply is preserved as the
  injected message's ``content`` so the lead's own words are not silently lost.
* when the lazy reply carries a stable ``id`` it is replaced via
  ``RemoveMessage``; when it has no ``id`` the injection is appended instead,
  because there is nothing addressable to remove.

The module is import-safe offline: it depends only on ``langchain_core`` and
never builds a model.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from langchain_core.messages import AIMessage, RemoveMessage

__all__ = [
    "DEFAULT_GUARD_CALL_ID_PREFIX",
    "DEFAULT_TRANSFER_PREFIX",
    "create_domain_guard_hook",
    "default_guard_call_ids",
    "worker_handoff_complete",
]

#: Prefix used by ``langgraph_supervisor`` for the built-in handoff tools.
DEFAULT_TRANSFER_PREFIX: str = "transfer_to_"

#: Fallback prefix for deterministic guard-issued tool-call ids.
DEFAULT_GUARD_CALL_ID_PREFIX: str = "guard_call_"


def _message_fields(message: Any) -> tuple[Any, list[Any], bool]:
    """Return ``(name, tool_calls, is_ai)`` for a BaseMessage or dict message.

    LangGraph state always carries real ``BaseMessage`` instances, but accepting
    dicts keeps the guard usable from tests and from lightweight state adapters.
    """
    if isinstance(message, dict):
        name = message.get("name")
        tool_calls = list(message.get("tool_calls") or [])
        is_ai = message.get("type") == "ai" or "tool_calls" in message
        return name, tool_calls, is_ai
    return (
        getattr(message, "name", None),
        list(getattr(message, "tool_calls", None) or []),
        isinstance(message, AIMessage),
    )


def _tool_call_name(call: Any) -> "str | None":
    """Return the called tool name from a tool-call entry in any known shape.

    Handles LangChain ``ToolCall`` dicts (``{"name": ...}``), raw OpenAI-style
    entries (``{"function": {"name": ...}}``) and plain objects exposing
    ``.name``. Returns ``None`` for unrecognized shapes instead of raising.
    """
    if isinstance(call, dict):
        name = call.get("name")
        if name:
            return str(name)
        fn = call.get("function")
        if isinstance(fn, dict) and fn.get("name"):
            return str(fn["name"])
    else:
        name = getattr(call, "name", None)
        if name:
            return str(name)
    return None


def worker_handoff_complete(
    messages: list[Any],
    worker_name: str,
    transfer_prefix: str = DEFAULT_TRANSFER_PREFIX,
) -> bool:
    """Return ``True`` if ``messages`` show the stage for ``worker_name`` ran.

    A stage counts as completed when any of the following appears anywhere in
    the transcript:

    * a message whose ``name`` is ``worker_name`` (the worker's own reply);
    * an ``AIMessage`` tool call named ``worker_name`` (direct delegation);
    * an ``AIMessage`` tool call named ``transfer_prefix + worker_name`` (the
      supervisor's built-in handoff tool);
    * a non-AI message named after the handoff tool (the ``ToolMessage``
      acknowledgement of a completed handoff).

    Both the supervisor's own ``transfer_to_*`` call *and* the worker's reply
    are accepted so the guard is robust to which of the two landed last.

    Args:
        messages: Transcript messages to inspect (``BaseMessage`` or dict).
        worker_name: Stage/worker identifier being checked.
        transfer_prefix: Prefix of the handoff tool name (default
            ``"transfer_to_"``).

    Returns:
        ``True`` when the stage has been handed off to, else ``False``.
    """
    transfer_tool = f"{transfer_prefix}{worker_name}"
    for message in messages:
        name, tool_calls, is_ai = _message_fields(message)
        if name == worker_name:
            return True
        if not is_ai and name == transfer_tool:
            return True
        if is_ai:
            for call in tool_calls:
                if _tool_call_name(call) in (worker_name, transfer_tool):
                    return True
    return False


def default_guard_call_ids(
    stage_order: tuple[str, ...],
    call_id_prefix: str = DEFAULT_GUARD_CALL_ID_PREFIX,
) -> dict[str, str]:
    """Build a deterministic ``worker -> guard tool-call id`` mapping.

    Args:
        stage_order: Ordered worker/stage identifiers.
        call_id_prefix: Prefix for generated ids.

    Returns:
        A plain ``dict`` mapping each worker to ``prefix + worker``.
    """
    return {worker: f"{call_id_prefix}{worker}" for worker in stage_order}


def create_domain_guard_hook(
    stage_order: tuple[str, ...],
    guard_call_ids: Mapping[str, str] | None = None,
    transfer_prefix: str = DEFAULT_TRANSFER_PREFIX,
) -> Callable[[Any], dict]:
    """Create a ``post_model_hook`` enforcing ``stage_order`` for any domain.

    Args:
        stage_order: Ordered worker identifiers the lead must hand off to, in
            pipeline order.  An empty tuple disables enforcement entirely (bare
            replies always pass) unless the state supplies its own
            ``stage_order``.
        guard_call_ids: Optional ``worker -> tool-call id`` map for the
            injected handoffs.  Workers absent from the map fall back to
            ``"guard_call_<worker>"``.  The mapping is read only, never
            mutated.
        transfer_prefix: Prefix of the handoff tool name.  Defaults to the
            ``langgraph_supervisor`` convention ``"transfer_to_"``.

    Returns:
        A ``post_model_hook(state) -> dict`` state update.  The returned dict is
        ``{}`` when no guard action is required, otherwise
        ``{"messages": [RemoveMessage(...), AIMessage(...)]}`` (or just the
        injected ``AIMessage`` when the replaced message has no ``id``).

    Notes:
        The hook is pure and deterministic: identical state yields identical
        updates, which keeps stage enforcement reproducible across runs.
    """
    bound_order = tuple(stage_order or ())
    resolved_call_ids = dict(guard_call_ids) if guard_call_ids else default_guard_call_ids(bound_order)

    def domain_guard_post_hook(state: Any) -> dict:
        raw_messages = state.get("messages") if hasattr(state, "get") else None
        messages = list(raw_messages or [])
        if not messages:
            return {}

        last = messages[-1]
        if not isinstance(last, AIMessage):
            return {}
        if last.tool_calls:
            return {}

        order = bound_order
        if not order:
            fallback = state.get("stage_order") if hasattr(state, "get") else None
            order = tuple(fallback or ())

        done = {
            worker: worker_handoff_complete(messages, worker, transfer_prefix)
            for worker in order
        }
        next_worker = next((worker for worker in order if not done.get(worker, False)), None)
        if next_worker is None:
            # Every stage has been handed off: let the bare text reply pass.
            return {}

        call_id = resolved_call_ids.get(
            next_worker, f"{DEFAULT_GUARD_CALL_ID_PREFIX}{next_worker}"
        )
        tool_name = f"{transfer_prefix}{next_worker}"
        injected = AIMessage(
            content=last.content if last.content is not None else "",
            tool_calls=[{"name": tool_name, "args": {}, "id": call_id}],
            id=f"{call_id}_message",
        )

        last_id = getattr(last, "id", None)
        if last_id:
            return {"messages": [RemoveMessage(id=last_id), injected]}
        # No stable id to remove by (e.g. hand-built test messages): append.
        return {"messages": [injected]}

    return domain_guard_post_hook
