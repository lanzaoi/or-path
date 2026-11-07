#!/usr/bin/env python3
"""Canonical stage-tracking state schemas for OR-Path domain supervisors.

Every domain team in OR-Path (Tube B, routing, scheduling, microgrid, …) is
orchestrated by a centralized lead agent built with
``langgraph_supervisor.create_supervisor``.  Each lead needs the same trio of
state capabilities:

  * the LangGraph ``messages`` channel (plus ``remaining_steps`` for the
    underlying ``create_react_agent``);
  * explicit, machine-readable stage flags so callers can tell how far a run
    has progressed without re-parsing the transcript;
  * artifact pointers (paths to registers, solutions, validation reports, …)
    so downstream workers can locate files without the LLM having to recall
    them.

``SupervisorState`` (``orpath/agents/supervisor.py``) and
``TubeSupervisorState`` (``orpath/agents/domains/tube.py``) hand-roll these
schemas.  That duplication makes it easy for a new domain to drift out of
sync, so this module provides a single canonical base plus a factory:

    class TubeSupervisorState(DomainSupervisorState): ...        # hand-rolled
    DynState = create_domain_state_schema("tube")                # generated

``create_domain_state_schema`` merges the base fields with arbitrary
domain-specific extras and returns a *real* ``TypedDict`` subclass (created
through the same metaclass that ``MessagesState`` uses), which is what
``create_supervisor(state_schema=...)`` and LangGraph channel construction
expect.

``get_state_stage_progress`` turns that state into a plain, JSON-friendly
progress summary.  Stage completion is resolved in two steps:

  1. an explicit boolean flag on the state, if the domain schema declares one
     (``has_<stage>``, ``stage_<stage>``, ``<stage>_completed`` or a bare
     ``<stage>`` key);
  2. otherwise a transcript-based fallback via
     ``orpath.agents.guard_factory.worker_handoff_complete``.

The module is import-safe offline: it depends only on ``langchain_core`` and
``langgraph`` and never builds or calls an LLM.
"""
from __future__ import annotations

from typing import Annotated, Any, NotRequired

from langgraph.graph import MessagesState
from langgraph.managed.is_last_step import RemainingStepsManager

from orpath.agents.guard_factory import worker_handoff_complete

__all__ = [
    "DEFAULT_SCHEMA_SUFFIX",
    "STAGE_FLAG_KEY_TEMPLATES",
    "DomainSupervisorState",
    "create_domain_state_schema",
    "get_state_stage_progress",
]

#: Suffix appended to the capitalized ``domain_prefix`` to form a schema name.
DEFAULT_SCHEMA_SUFFIX = "SupervisorState"

#: Key templates checked (in order) when resolving an explicit stage flag.
STAGE_FLAG_KEY_TEMPLATES: tuple[str, ...] = (
    "{stage}",
    "has_{stage}",
    "stage_{stage}",
    "{stage}_completed",
    "completed_{stage}",
)


class DomainSupervisorState(MessagesState):
    """Canonical base stage-tracking state for any OR domain supervisor.

    Extends LangGraph's ``MessagesState`` with the quality-gate flags and
    artifact pointers that are common to every OR-Path domain team:

      * ``remaining_steps`` — required by the ``create_react_agent`` nested
        inside ``create_supervisor``; mirrors ``langgraph.prebuilt.AgentState``.
      * quality gates — ``audit_passed``, ``lower_bound_fixed``,
        ``incumbent_solved``, ``realities_applied``, ``redteam_passed`` let a
        caller (or an independent validator) read pipeline progress without
        parsing messages.
      * artifact pointers — absolute or workdir-relative paths to the
        assumption register, budget ledger, candidate solution, validation
        report, red-team report, audit report and experiment cards.
      * ``domain`` / ``problem_id`` — the minimal identity of the run.

    Domains that need extra fields should either subclass this class directly
    or use ``create_domain_state_schema`` to generate a typed subclass.
    """

    remaining_steps: NotRequired[Annotated[int, RemainingStepsManager]]
    audit_passed: bool = False
    lower_bound_fixed: bool = False
    incumbent_solved: bool = False
    realities_applied: bool = False
    redteam_passed: bool = False
    domain: str = ""
    problem_id: str = ""
    assumption_register_path: str = ""
    budget_ledger_path: str = ""
    candidate_solution_path: str = ""
    validation_report_path: str = ""
    redteam_report_path: str = ""
    audit_report_path: str = ""
    experiment_card_paths: list[str] = []


def _schema_class_name(domain_prefix: str) -> str:
    """Return the generated schema class name for ``domain_prefix``.

    ``"tube"`` → ``"TubeSupervisorState"``, ``"my_domain"`` →
    ``"MyDomainSupervisorState"``.  Empty/blank prefixes fall back to
    ``"DomainSupervisorState"``.
    """
    cleaned = "".join(part.capitalize() for part in domain_prefix.strip().split("_") if part)
    if not cleaned:
        cleaned = "Domain"
    return f"{cleaned}{DEFAULT_SCHEMA_SUFFIX}"


def create_domain_state_schema(
    domain_prefix: str,
    extra_fields: dict[str, tuple[type, Any]] | None = None,
) -> type[DomainSupervisorState]:
    """Generate a typed ``DomainSupervisorState`` subclass for a domain.

    The returned class is a genuine ``TypedDict`` subclass built with the same
    metaclass that ``MessagesState`` uses, so it is accepted directly by
    ``create_supervisor(state_schema=...)`` and by LangGraph's channel
    machinery.

    Args:
        domain_prefix: Domain identifier used to build the class name, e.g.
            ``"tube"``, ``"routing"``, ``"microgrid"``.
        extra_fields: Optional mapping of ``field_name -> (annotation,
            default)`` merged on top of the canonical base fields.  Field names
            already present on ``DomainSupervisorState`` override the base
            declaration.  Defaults are stored as class attributes exactly like
            a hand-written ``TypedDict`` default.

    Returns:
        A newly created ``type`` (a ``TypedDict`` subclass of
        ``DomainSupervisorState``'s base).  Two calls return independent
        classes, so callers that need stable identity should cache the result.

    Raises:
        TypeError: If ``domain_prefix`` is not a string.
        ValueError: If ``extra_fields`` contains an entry whose value is not a
            two-tuple of ``(annotation, default)``.
    """
    if not isinstance(domain_prefix, str):
        raise TypeError(f"domain_prefix must be a str, got {type(domain_prefix).__name__}")

    merged: dict[str, Any] = dict(DomainSupervisorState.__annotations__)
    defaults: dict[str, Any] = {}

    for field_name, spec in (extra_fields or {}).items():
        if not isinstance(spec, tuple) or len(spec) != 2:
            raise ValueError(
                f"extra_fields['{field_name}'] must be a (annotation, default) 2-tuple, "
                f"got {spec!r}"
            )
        annotation, default = spec
        merged[field_name] = annotation
        defaults[field_name] = default

    namespace: dict[str, Any] = {
        "__annotations__": merged,
        "__module__": __name__,
        "__doc__": (
            f"Generated domain supervisor state schema for the "
            f"'{domain_prefix}' domain."
        ),
        **defaults,
    }

    # ``type(DomainSupervisorState)`` is the ``typing_extensions._TypedDictMeta``
    # used by ``MessagesState``; using it keeps the generated class a real
    # TypedDict (required/optional keys, channels, ``is_typeddict`` checks).
    metaclass = type(DomainSupervisorState)
    return metaclass(_schema_class_name(domain_prefix), (DomainSupervisorState,), namespace)


def _as_mapping(state: Any) -> dict[str, Any]:
    """Return ``state`` as a plain mapping, tolerating dict-like objects.

    ``MessagesState`` and TypedDict instances are real ``dict`` subclasses, but
    defensive callers may pass objects exposing ``.get``/``keys``.  Falling back
    to an empty mapping keeps ``get_state_stage_progress`` total.
    """
    if isinstance(state, dict):
        return state
    if hasattr(state, "get") and hasattr(state, "keys"):
        return dict(state)
    return {}


def _resolve_stage_flag(source: dict[str, Any], stage: str) -> bool | None:
    """Return an explicit boolean stage flag from ``source`` or ``None``.

    ``None`` means "no explicit flag declared", so the caller falls back to
    transcript-based detection.  The first template that matches a key wins.
    """
    for template in STAGE_FLAG_KEY_TEMPLATES:
        key = template.format(stage=stage)
        if key in source:
            return bool(source[key])
    return None


def get_state_stage_progress(
    state: dict | MessagesState,
    stage_order: tuple[str, ...],
) -> dict[str, Any]:
    """Summarize the pipeline progress carried by ``state``.

    The returned mapping is JSON-friendly and intended for the Live Watch
    dashboard and for tests; it contains no LLM output and never invents
    completion.  A stage is considered complete when either an explicit boolean
    flag on the state is set, or the transcript shows the stage was handed off
    to (see :func:`orpath.agents.guard_factory.worker_handoff_complete`).

    Args:
        state: Domain supervisor state.  Accepts a plain ``dict`` or a
            ``MessagesState``/``DomainSupervisorState`` instance.
        stage_order: Ordered stage/worker identifiers to evaluate, e.g.
            ``TUBE_PIPELINE_STAGE_ORDER``.

    Returns:
        A dict with the keys ``domain``, ``problem_id``, ``stage_order``,
        ``stages``, ``completed_stages``, ``missing_stages``,
        ``completed_count``, ``total_stages``, ``all_completed``,
        ``next_stage``, ``progress`` and ``message_count``.
        ``progress`` is a float in ``[0.0, 1.0]`` (``1.0`` for an empty
        ``stage_order``); ``next_stage`` is ``None`` when everything is done.
    """
    order = tuple(stage_order or ())
    source = _as_mapping(state)
    messages = list(source.get("messages") or [])

    stages: dict[str, bool] = {}
    for stage in order:
        explicit = _resolve_stage_flag(source, stage)
        stages[stage] = explicit if explicit is not None else worker_handoff_complete(messages, stage)

    completed = [stage for stage in order if stages[stage]]
    missing = [stage for stage in order if not stages[stage]]

    return {
        "domain": source.get("domain") or "",
        "problem_id": source.get("problem_id") or "",
        "stage_order": list(order),
        "stages": stages,
        "completed_stages": completed,
        "missing_stages": missing,
        "completed_count": len(completed),
        "total_stages": len(order),
        "all_completed": len(completed) == len(order),
        "next_stage": missing[0] if missing else None,
        "progress": (len(completed) / len(order)) if order else 1.0,
        "message_count": len(messages),
    }
