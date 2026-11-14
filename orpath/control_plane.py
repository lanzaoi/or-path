"""OR-Path ControlPlane — single entry for graph build + invoke (ADR-0003).

Interface (what callers learn):
  - build_graph(checkpointer=None)            → compiled product LangGraph
  - build_multiagent_graph(...)               → supervisor multi-agent StateGraph
  - build_compiled_multiagent(checkpointer=)  → compiled supervisor graph
  - default_initial(...)            → ORPathState seed dict
  - invoke_once(...)                → one-shot run (no checkpointer; T1/CI)
  - PRODUCT_NODES / stage map helpers (re-export)

Topology lives in graph_product.py; checkpointed CLI stays run_orpath.py.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph, StateGraph

from orpath.graph_product import (  # re-export seam
    PRODUCT_NODES,
    build_graph_product,
    export_stage_map,
    open_sqlite_checkpointer,
    write_stage_map_files,
)

# Provider precedence: DeepSeek > iFlytek Spark > OpenAI.
# ``base_url`` is the OpenAI-compatible chat-completions root (``.../v1``).
_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "xfyun": {
        "api_key_env": "XFYUN_API_KEY",
        "base_url_env": "XFYUN_BASE_URL",
        "base_url": "https://spark-api-open.xf-yun.com/v1",
        "model": "spark-x2.6",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "base_url": "",
        "model": "gpt-4o-mini",
    },
}
_PROVIDER_ORDER: tuple[str, ...] = ("deepseek", "xfyun", "openai")


def _resolve_provider(model: str) -> str:
    """Pick a provider from an explicit model hint, else the first env key present."""
    low = (model or "").strip().lower()
    if "spark" in low or "xf" in low:
        return "xfyun"
    if "deepseek" in low:
        return "deepseek"
    for provider in _PROVIDER_ORDER:
        if (os.environ.get(_PROVIDER_DEFAULTS[provider]["api_key_env"]) or "").strip():
            return provider
    return _PROVIDER_ORDER[0]


def get_chat_model(
    model_name: str | None = None,
    temperature: float = 0.2,
    http_client: Any = None,
    timeout: float | None = None,
) -> Any:
    """Return a configured ``ChatOpenAI`` instance.

    Compatible with DeepSeek, iFlytek Spark (XFYUN) and OpenAI-compatible endpoints.
    Resolution order for credentials is ``DEEPSEEK_API_KEY`` → ``XFYUN_API_KEY`` →
    ``OPENAI_API_KEY``; matching ``*_BASE_URL`` env vars are honoured when present.

    When no API key is configured a placeholder (``api_key="mock_key"``) is used so the
    object can be constructed offline (unit tests / local dry-runs).

    ``http_client`` optionally injects a dedicated ``httpx`` / ``httpx2`` client (used
    by the multi-agent attempt in the Web Studio so the LLM transport is
    timeout-bounded and never reuses stale pooled connections).
    """
    model = (model_name or "").strip()
    provider = _resolve_provider(model)
    spec = _PROVIDER_DEFAULTS[provider]

    api_key = (os.environ.get(spec["api_key_env"]) or "").strip()
    if not api_key:
        api_key = "mock_key"

    base_url = (os.environ.get(spec["base_url_env"]) or "").strip() or spec["base_url"]

    req_timeout = timeout
    if req_timeout is None:
        try:
            req_timeout = float(os.environ.get("ORPATH_LLM_TIMEOUT", "120.0"))
        except (ValueError, TypeError):
            req_timeout = 120.0

    kwargs: dict[str, Any] = {
        "model": model or spec["model"],
        "api_key": api_key,
        "temperature": temperature,
        "request_timeout": req_timeout,
    }
    if base_url:
        kwargs["base_url"] = base_url
    if http_client is not None:
        kwargs["http_client"] = http_client
    return ChatOpenAI(**kwargs)


def get_tiered_chat_model(
    role: Literal["fast", "reasoning"],
    temperature: float = 0.2,
    http_client: Any = None,
    timeout: float | None = None,
) -> Any:
    """Phase 3.4 — fast/reasoning dual-model routing.

    ``fast`` (or_analyst structured extraction, tool param assembly):
    reads ``ORPATH_FAST_MODEL``, falls back to the primary ``ORPATH_LLM_MODEL``
    then the provider default. ``reasoning`` (Tier-B/C modeler, writer
    formula derivation, reviewer deep review): reads ``ORPATH_REASONING_MODEL``,
    with the same cascade. Single-model installs work unchanged — both tiers
    resolve to the same provider default.
    """
    r = str(role or "fast").strip().lower()
    if r not in {"fast", "reasoning"}:
        raise ValueError(f"role must be 'fast' or 'reasoning', got {role!r}")
    env_key = "ORPATH_FAST_MODEL" if r == "fast" else "ORPATH_REASONING_MODEL"
    model = (os.environ.get(env_key) or "").strip()
    if not model:
        model = (os.environ.get("ORPATH_LLM_MODEL") or "").strip()
    return get_chat_model(
        model or None,
        temperature=temperature,
        http_client=http_client,
        timeout=timeout,
    )


def is_real_llm_configured() -> bool:
    """Return True if any supported LLM provider has a non-mock API key set."""
    for provider in _PROVIDER_ORDER:
        key = (os.environ.get(_PROVIDER_DEFAULTS[provider]["api_key_env"]) or "").strip()
        if key and key != "mock_key":
            return True
    return False


# Canonical stage predecessors for --from-stage (product graph)
PREDECESSORS: dict[str, str] = {
    "intake_ocr": "START",
    "intake_parse": "intake_ocr",
    "orchestrate": "intake_ocr",
    "retrieve": "orchestrate",
    "research": "retrieve",
    "model": "research",
    "gate_schema": "model",
    "solve": "gate_schema",
    "gate_validate": "solve",
    "explain": "gate_validate",
    "draft_paper": "explain",
    "cite_pack": "draft_paper",
    "review_pack": "cite_pack",
    "revise_or_done": "review_pack",
    "provenance": "revise_or_done",
}


def build_graph(checkpointer: Any | None = None) -> Any:
    """Build the **only** product pipeline graph."""
    return build_graph_product(checkpointer=checkpointer)


# Back-compat names used across gates/docs
build_graph_product_cp = build_graph  # alias


# --------------------------------------------------------------------------- #
# Deep Mode multi-agent pipeline seam (backed by adaptive_graph)
#
# ``orpath.agents.adaptive_graph`` lazily imports ``get_chat_model`` from this
# module, so builders below import lazily on call to avoid circular imports.
#
# Public names (kept stable for callers / e2e tests):
#   build_multiagent_graph    == build_isolated_pipeline_graph (uncompiled StateGraph)
#   build_compiled_multiagent == build_compiled_isolated_pipeline (CompiledStateGraph)
# --------------------------------------------------------------------------- #
def build_multiagent_graph(
    model: Any = None,
    workers: Any = None,
    prompt: str | None = None,
    state_schema: Any = None,
    enable_guard: bool = True,
    **kwargs: Any,
) -> Any:
    """Build the unified 4-agent adaptive Deep Mode StateGraph (un-compiled)."""
    from orpath.agents.adaptive_graph import build_isolated_pipeline_graph as _build_isolated

    return _build_isolated(model=model, **kwargs)


def build_compiled_multiagent(
    checkpointer: Any = None,
    model: Any = None,
    workers: Any = None,
    prompt: str | None = None,
    state_schema: Any = None,
    enable_guard: bool = True,
    **kwargs: Any,
) -> Any:
    """Build and compile the unified 4-agent adaptive Deep Mode graph."""
    from orpath.agents.adaptive_graph import build_compiled_isolated_pipeline as _compile_isolated

    return _compile_isolated(checkpointer=checkpointer, model=model, **kwargs)


def build_isolated_pipeline_graph(
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> Any:
    """Build the unified adaptive Deep Mode StateGraph (un-compiled)."""
    from orpath.agents.adaptive_graph import build_isolated_pipeline_graph as _build_isolated

    return _build_isolated(model=model, checkpointer=checkpointer, **kwargs)


def build_compiled_isolated_pipeline(
    checkpointer: Any = None,
    model: Any = None,
    **kwargs: Any,
) -> Any:
    """Build and compile the unified adaptive Deep Mode StateGraph."""
    from orpath.agents.adaptive_graph import build_compiled_isolated_pipeline as _compile_isolated

    return _compile_isolated(checkpointer=checkpointer, model=model, **kwargs)


def db_path(root: Path) -> Path:
    return Path(root) / "runs" / "orpath.sqlite"


def thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def default_initial(
    *,
    root: Path,
    slug: str,
    problem_id: str,
    problem_class: str = "",
    solve_mode: str = "mock",
    knowledge_mode: str = "hybrid",
    live_pi: bool = False,
    live_subagent: bool | None = None,
    thread_id: str,
    bridge_attachment: str = "before_research",
    skip_intake: bool = True,
    intake_sources: list[str] | None = None,
    intake_assets_dir: str = "",
    human_confirm_intake: bool = False,
    intake_confirmed: bool = False,
    is_replay: bool = False,
    fixture_ref: str = "",
    replay_authorized: bool | None = None,
    run_mode: str = "deep",
    skip_paper: bool | None = None,
    paper_quality: str = "",
) -> dict[str, Any]:
    """Canonical ORPathState seed for product runs."""
    root = Path(root)
    fref = (fixture_ref or "").strip()
    explicit_replay = bool(is_replay or fref or os.environ.get("ORPATH_FIXTURE_REPLAY") == "1")
    has_intake = (not skip_intake) or bool(intake_sources) or bool((intake_assets_dir or "").strip())
    if replay_authorized is not None:
        auth_replay = bool(replay_authorized)
    elif has_intake:
        auth_replay = explicit_replay
    else:
        auth_replay = explicit_replay or bool((problem_id or "").strip())
    if auth_replay and not fref and (problem_id or "").strip():
        fref = str(problem_id).strip()
    data_source = "fixture" if explicit_replay else ("case" if has_intake else "")
    return {
        "slug": slug,
        "problem_id": problem_id,
        "problem_class": problem_class,
        "solve_mode": solve_mode,
        "knowledge_mode": knowledge_mode,
        "root": str(root),
        "stage": "start",
        "revise_count": 0,
        "max_revise": 2,
        "schema_repair": 0,
        "max_schema_repair": 2,
        "validate_repair": 0,
        "max_validate_repair": 2,
        "solver_tune": 0,
        "max_solver_tune": 3,
        "human_required": False,
        "schema_path": "",
        "solution_path": "",
        "validate_path": "",
        "research_path": "",
        "retrieval_path": "",
        "explain_path": "",
        "paper_path": "",
        "review_path": "",
        "provenance_path": "",
        "plan_path": "",
        "cited_path": "",
        "last_error": "",
        "gate_schema_ok": False,
        "gate_validate_ok": False,
        "gate_r1_ok": False,
        "gate_r2_ok": False,
        "gate_claim_ok": True,
        "gate_subagent_ok": None,
        "review_fatal": 0,
        "live_pi": bool(live_pi),
        "live_subagent": live_subagent,
        "thread_id": thread_id,
        "bridge_attachment": bridge_attachment,
        "bridge_path": "",
        "bridge_ok": False,
        "bridge_skipped": True,
        "orpath_checkpoint_id": "",
        "runs_dir": str(root / "runs" / thread_id),
        "artifact_manifest_path": "",
        "last_snapshot_path": "",
        "pipeline": "product",
        # 1.1 intake — default skip keeps T1–T3 paths green
        "skip_intake": bool(skip_intake),
        "intake_skipped": bool(skip_intake),
        "intake_sources": list(intake_sources or []),
        "intake_assets_dir": intake_assets_dir or "",
        "ocr_raw_path": "",
        "ocr_meta_path": "",
        "intake_path": "",
        "brief_path": "",
        "gate_intake_ok": True if skip_intake else False,
        "human_confirm_intake": bool(human_confirm_intake),
        "intake_confirmed": bool(intake_confirmed),
        "is_replay": bool(is_replay or (explicit_replay and auth_replay)),
        "fixture_ref": fref,
        "replay_authorized": bool(auth_replay),
        "blocked_reason": "",
        "data_source": data_source,
        "run_mode": "fast" if str(run_mode or "").strip().lower() == "fast" else "deep",
        "skip_paper": bool(skip_paper) if skip_paper is not None else False,
        "paper_quality": str(paper_quality or ""),
        "paper_degraded_reason": "",
    }


def _is_transient_llm_error(exc: BaseException) -> bool:
    """Return True when exc looks like a transient LLM/network error safe to retry."""
    if isinstance(exc, TimeoutError):
        return True
    name = type(exc).__name__.lower()
    if any(tok in name for tok in ("timeout", "ratelimit", "apiconnection", "internalserver", "serviceunavailable", "remoteprotocol")):
        return True
    status = getattr(exc, "status_code", None)
    if status in (408, 429, 500, 502, 503, 504):
        return True
    msg = str(exc).lower()
    transient_markers = (
        "timed out",
        "timeout",
        "rate limit",
        "too many requests",
        "429",
        "502",
        "503",
        "504",
        "500",
        "bad gateway",
        "service unavailable",
        "gateway timeout",
        "connection reset",
        "connection aborted",
        "temporarily unavailable",
        "remote protocol",
        "eof occurred",
    )
    return any(m in msg for m in transient_markers)


def invoke_with_backoff(
    model: Any,
    payload: Any,
    *,
    config: dict[str, Any] | None = None,
    max_retries: int | None = None,
    base_delay: float | None = None,
    sleep_fn: Any = None,
) -> Any:
    """Invoke a LangChain model or compiled agent with exponential backoff on transient errors.

    Controlled via ``ORPATH_LLM_MAX_RETRIES`` (default 3) and
    ``ORPATH_LLM_RETRY_DELAY`` (default 2.0 seconds).
    """
    if max_retries is None:
        try:
            max_retries = max(0, int(os.environ.get("ORPATH_LLM_MAX_RETRIES", "3")))
        except ValueError:
            max_retries = 3
    if base_delay is None:
        try:
            base_delay = max(0.0, float(os.environ.get("ORPATH_LLM_RETRY_DELAY", "2.0")))
        except ValueError:
            base_delay = 2.0
    sleeper = sleep_fn or time.sleep
    log = logging.getLogger(__name__)

    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            if config is not None:
                return model.invoke(payload, config=config)
            return model.invoke(payload)
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries or not _is_transient_llm_error(exc):
                raise
            delay = min(30.0, base_delay * (2 ** attempt))
            log.warning(
                "Transient LLM error on attempt %d/%d (%s: %s); retrying in %.2fs",
                attempt + 1,
                max_retries + 1,
                type(exc).__name__,
                exc,
                delay,
            )
            if delay > 0:
                sleeper(delay)
    assert last_exc is not None
    raise last_exc


def summarize_run(final: dict[str, Any], *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compact JSON summary for CLIs / gates."""
    out = {
        "stage": final.get("stage"),
        "human_required": final.get("human_required"),
        "revise_count": final.get("revise_count"),
        "gate_r1_ok": final.get("gate_r1_ok"),
        "gate_r2_ok": final.get("gate_r2_ok"),
        "gate_validate_ok": final.get("gate_validate_ok"),
        "gate_subagent_ok": final.get("gate_subagent_ok"),
        "solution_path": final.get("solution_path"),
        "paper_path": final.get("paper_path"),
        "provenance_path": final.get("provenance_path"),
        "last_error": final.get("last_error"),
        "pipeline": final.get("pipeline") or "product",
        "thread_id": final.get("thread_id"),
        "run_mode": final.get("run_mode", "deep"),
        "skip_paper": bool(final.get("skip_paper", False)),
        "paper_quality": final.get("paper_quality", ""),
        "paper_degraded_reason": final.get("paper_degraded_reason", ""),
    }
    if extra:
        out.update(extra)
    return out


def invoke_once(
    *,
    root: Path,
    slug: str,
    problem_id: str,
    problem_class: str = "",
    solve_mode: str = "mock",
    knowledge_mode: str = "off",
    live_pi: bool = False,
    live_subagent: bool | None = False,
    thread_id: str | None = None,
    bridge_attachment: str = "before_research",
    is_replay: bool = False,
    fixture_ref: str = "",
    replay_authorized: bool | None = None,
    run_mode: str = "deep",
    skip_paper: bool | None = None,
    paper_quality: str = "",
) -> dict[str, Any]:
    """One-shot product run without Sqlite checkpointer (T1 / ad-hoc CI)."""
    root = Path(root).resolve()
    tid = thread_id or f"{slug}-{uuid.uuid4().hex[:8]}"
    initial = default_initial(
        root=root,
        slug=slug,
        problem_id=problem_id,
        problem_class=problem_class,
        solve_mode=solve_mode,
        knowledge_mode=knowledge_mode,
        live_pi=live_pi,
        live_subagent=live_subagent,
        thread_id=tid,
        bridge_attachment=bridge_attachment,
        is_replay=is_replay,
        fixture_ref=fixture_ref,
        replay_authorized=replay_authorized,
        run_mode=run_mode,
        skip_paper=skip_paper,
        paper_quality=paper_quality,
    )
    app = build_graph(checkpointer=None)
    return app.invoke(initial)


__all__ = [
    # product graph
    "PREDECESSORS",
    "build_compiled_isolated_pipeline",
    "build_compiled_multiagent",
    "build_graph",
    "build_graph_product",
    "build_isolated_pipeline_graph",
    "build_multiagent_graph",
    # shared helpers
    "db_path",
    "default_initial",
    "export_stage_map",
    "get_chat_model",
    "invoke_once",
    "invoke_with_backoff",
    "is_real_llm_configured",
    "open_sqlite_checkpointer",
    "PRODUCT_NODES",
    "summarize_run",
    "thread_config",
    "write_stage_map_files",
]
