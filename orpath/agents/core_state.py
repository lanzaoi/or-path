"""Unified strong-typed artifact-pointer state contract (Plan 1.2).

``CorePipelineState`` is the Feynman file-handoff state shared by the product
main graph and the 4-agent execution flow. It carries **only** scalar
summaries and on-disk artifact pointers — never raw problem text, giant
solution arrays, or chat history (see ``sanitize_core_state``).
"""
from __future__ import annotations

import json
from typing import Any, Literal, Mapping

try:  # Python 3.11+
    from typing import TypedDict
except ImportError:  # pragma: no cover
    from typing_extensions import TypedDict

#: Hard ceiling for the serialized core state (bytes of compact JSON).
MAX_CORE_STATE_BYTES = 8192

#: Keys that must never carry oversized payloads into the state.
_PAYLOAD_KEYS = frozenset(
    {"problem_text", "solution", "solution_array", "raw_data", "matrix",
     "messages", "chat_history", "prompt", "paper_body", "coords"}
)


class CorePipelineState(TypedDict, total=False):
    """Strong-typed pointer-only pipeline state (all keys optional)."""

    slug: str
    workdir: str
    problem_id: str
    problem_class: str
    domain_cartridge: str
    complexity_tier: Literal["A", "B", "C"]
    subproblems: list[str]
    # Artifact disk pointers (raw text / giant arrays FORBIDDEN here)
    problem_file: str
    data_files: list[str]
    profile_path: str
    knowledge_pack_path: str
    retrieval_path: str
    lessons_path: str
    remediation_path: str
    research_path: str
    schema_path: str
    solution_path: str
    validate_path: str
    paper_path: str
    review_path: str
    # Deterministic gates & self-heal counters
    validation_ok: bool
    proven_optimal: bool
    objective_value: float | None
    optimality_gap: float | None
    fatal_defects: list[str]
    model_retry_count: int
    paper_retry_count: int
    max_retries: int
    last_error: str


def make_initial_core_state(
    slug: str = "",
    workdir: str = "",
    problem_id: str = "",
    problem_class: str = "",
    domain_cartridge: str = "",
    complexity_tier: str = "",
    max_retries: int = 3,
) -> CorePipelineState:
    """Factory for a fresh, pointer-only pipeline state."""
    state: CorePipelineState = {
        "slug": slug,
        "workdir": workdir,
        "problem_id": problem_id,
        "problem_class": problem_class,
        "domain_cartridge": domain_cartridge,
        "subproblems": [],
        "data_files": [],
        "fatal_defects": [],
        "validation_ok": False,
        "proven_optimal": False,
        "objective_value": None,
        "optimality_gap": None,
        "model_retry_count": 0,
        "paper_retry_count": 0,
        "max_retries": max_retries,
        "last_error": "",
    }
    if complexity_tier in ("A", "B", "C"):
        state["complexity_tier"] = complexity_tier  # type: ignore[literal-required]
    return state


def serialized_state_size_bytes(state: Mapping[str, Any]) -> int:
    """Compact-JSON byte size of a state mapping (UTF-8)."""
    return len(json.dumps(dict(state), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def sanitize_core_state(state: Mapping[str, Any]) -> CorePipelineState:
    """Strip/reject oversized payloads; keep only pointers + scalar summaries.

    Keys listed in ``_PAYLOAD_KEYS`` (or values exceeding 4096 chars /
    512-element arrays) are dropped, preventing raw text or giant solution
    arrays from ever entering the checkpointed state.
    """
    out: CorePipelineState = {}
    for key, value in state.items():
        if key in _PAYLOAD_KEYS:
            continue
        if isinstance(value, (str,)) and len(value) > 4096:
            continue  # path pointers are short; long strings are payloads
        if isinstance(value, (list, tuple)):
            if len(value) > 512:
                continue
            value = list(value)
        if isinstance(value, dict):
            continue  # dicts (e.g. steer snapshots) never belong in core state
        out[key] = value  # type: ignore[literal-required]
    if serialized_state_size_bytes(out) > MAX_CORE_STATE_BYTES:  # pragma: no cover
        raise ValueError("sanitized core state still exceeds MAX_CORE_STATE_BYTES")
    return out
