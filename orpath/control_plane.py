"""OR-Path ControlPlane — single entry for graph build + invoke (ADR-0003).

Interface (what callers learn):
  - build_graph(checkpointer=None)            → compiled product LangGraph
  - build_multiagent_graph(...)               → supervisor multi-agent StateGraph
  - build_compiled_multiagent(checkpointer=)  → compiled supervisor graph
  - build_domain_supervisor_graph(domain, ...)     → 10-domain supervisor StateGraph
  - build_compiled_domain_supervisor(domain, ...)  → compiled domain supervisor
  - build_composite_supervisor(composite_type, ...) → compiled LRP/PRP/... pipeline
  - dispatch_supervisor_for_problem(data, text, filename) → auto-routed supervisor
  - default_initial(...)            → ORPathState seed dict
  - invoke_once(...)                → one-shot run (no checkpointer; T1/CI)
  - PRODUCT_NODES / stage map helpers (re-export)

Topology lives in graph_product.py; checkpointed CLI stays run_orpath.py.
Legacy shims: graph.py, graph_t2.py, run_t1.py, run_t2.py.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:  # pragma: no cover — annotations only, keeps import graph acyclic
    from orpath.agents.meta_router import DomainRouteResult

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
# Multi-agent supervisor re-export seam
#
# ``orpath.agents.supervisor`` and every ``orpath.agents.domains.*`` module
# import ``get_chat_model`` from this module, so a module-level
# ``from orpath.agents.<...> import ...`` would be a circular import (and would
# break ``import orpath.agents`` for tools/test_supervisor.py). All supervisor
# builders below therefore import lazily on first call, preserving the
# ControlPlane entry-point contract without changing import order.
#
# Public names (kept stable for callers / e2e tests):
#   build_multiagent_graph    == build_supervisor_graph
#   build_compiled_multiagent == build_compiled_supervisor
# --------------------------------------------------------------------------- #
def build_multiagent_graph(
    model: Any = None,
    workers: Any = None,
    prompt: str | None = None,
    state_schema: Any = None,
    enable_guard: bool = True,
    **kwargs: Any,
) -> Any:
    """Build the supervisor-orchestrated multi-agent graph (un-compiled).

    Re-export of ``orpath.agents.supervisor.build_supervisor_graph``. Accepts an
    optional ``model``, ``workers`` roster, ``prompt``, ``state_schema`` and
    ``enable_guard``; when omitted the supervisor factory falls back to the
    offline-safe shared chat model.
    """
    from orpath.agents.supervisor import build_supervisor_graph

    return build_supervisor_graph(
        model=model,
        workers=workers,
        prompt=prompt,
        state_schema=state_schema,
        enable_guard=enable_guard,
        **kwargs,
    )


def build_compiled_multiagent(
    checkpointer: Any = None,
    model: Any = None,
    workers: Any = None,
    prompt: str | None = None,
    state_schema: Any = None,
    enable_guard: bool = True,
    **kwargs: Any,
) -> Any:
    """Build and compile the supervisor multi-agent graph.

    Re-export of ``orpath.agents.supervisor.build_compiled_supervisor``. Pass a
    LangGraph checkpointer (``MemorySaver`` / ``SqliteSaver``, ...) for a
    persistent graph; pass ``None`` for an ephemeral one.
    """
    from orpath.agents.supervisor import build_compiled_supervisor

    return build_compiled_supervisor(
        checkpointer=checkpointer,
        model=model,
        workers=workers,
        prompt=prompt,
        state_schema=state_schema,
        enable_guard=enable_guard,
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# Domain supervisor dispatch registry (Task 4.3)
#
# One canonical registry mapping each of the 10 standard OR domains to the
# module that builds its domain-specific multi-agent supervisor team. The
# dynamic factories below resolve a domain string against this registry and
# lazily import the matching builder, so callers never import domain modules
# directly (circular-import constraint, see header above).
# --------------------------------------------------------------------------- #
DOMAIN_TUBE = "tube"
DOMAIN_ROUTING = "routing"
DOMAIN_SCHEDULING = "scheduling"
DOMAIN_PROJECT = "project"
DOMAIN_INVENTORY = "inventory"
DOMAIN_FACILITY = "facility"
DOMAIN_ROSTERING = "rostering"
DOMAIN_MICROGRID = "microgrid"
DOMAIN_PRICING = "pricing"
DOMAIN_FINANCE = "finance"

#: domain → (module path, un-compiled builder, compiled builder).
_DOMAIN_SUPERVISOR_MODULES: dict[str, tuple[str, str, str]] = {
    DOMAIN_TUBE: ("orpath.agents.domains.tube",
                  "build_tube_supervisor_graph",
                  "build_compiled_tube_supervisor"),
    DOMAIN_ROUTING: ("orpath.agents.domains.routing",
                     "build_routing_supervisor_graph",
                     "build_compiled_routing_supervisor"),
    DOMAIN_SCHEDULING: ("orpath.agents.domains.scheduling",
                        "build_scheduling_supervisor_graph",
                        "build_compiled_scheduling_supervisor"),
    DOMAIN_PROJECT: ("orpath.agents.domains.project",
                     "build_project_supervisor_graph",
                     "build_compiled_project_supervisor"),
    DOMAIN_INVENTORY: ("orpath.agents.domains.inventory",
                       "build_inventory_supervisor_graph",
                       "build_compiled_inventory_supervisor"),
    DOMAIN_FACILITY: ("orpath.agents.domains.facility",
                      "build_facility_supervisor_graph",
                      "build_compiled_facility_supervisor"),
    DOMAIN_ROSTERING: ("orpath.agents.domains.rostering",
                       "build_rostering_supervisor_graph",
                       "build_compiled_rostering_supervisor"),
    DOMAIN_MICROGRID: ("orpath.agents.domains.microgrid",
                       "build_microgrid_supervisor_graph",
                       "build_compiled_microgrid_supervisor"),
    DOMAIN_PRICING: ("orpath.agents.domains.pricing",
                     "build_pricing_supervisor_graph",
                     "build_compiled_pricing_supervisor"),
    DOMAIN_FINANCE: ("orpath.agents.domains.finance",
                     "build_finance_supervisor_graph",
                     "build_compiled_finance_supervisor"),
}

#: Canonical order of the 10 supported domain supervisors.
SUPPORTED_DOMAIN_SUPERVISORS: tuple[str, ...] = tuple(_DOMAIN_SUPERVISOR_MODULES)


def _normalize_domain(domain: str) -> str:
    """Validate *domain* and return its canonical key.

    Raises ``ValueError`` listing the legal domains when the input is unknown.
    """
    key = str(domain or "").strip().lower()
    if key not in _DOMAIN_SUPERVISOR_MODULES:
        raise ValueError(
            f"unknown domain {domain!r}; supported domains: "
            f"{list(SUPPORTED_DOMAIN_SUPERVISORS)}"
        )
    return key


def build_domain_supervisor_graph(
    domain: str,
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> StateGraph:
    """Build the un-compiled multi-agent supervisor graph for one domain.

    Parameters
    ----------
    domain
        One of the 10 canonical OR domains: ``tube``, ``routing``,
        ``scheduling``, ``project``, ``inventory``, ``facility``,
        ``rostering``, ``microgrid``, ``pricing``, ``finance``. Unknown
        domains raise ``ValueError``.
    model
        Chat model injected into every domain worker. Defaults to the
        offline-safe shared factory (``get_chat_model()``).
    checkpointer
        Accepted for signature symmetry with
        :func:`build_compiled_domain_supervisor`; ignored for the
        un-compiled graph (compile first, then attach a checkpointer).
    **kwargs
        Forwarded to the domain builder (``workers``, ``prompt``,
        ``state_schema``, ``enable_guard``, ``enable_trim``,
        ``pre_model_hook``, ``supervisor_name``).

    Returns
    -------
    StateGraph
        The un-compiled domain supervisor graph (supervisor lead +
        five specialist workers = 6 nodes).
    """
    key = _normalize_domain(domain)
    module_name, graph_fn, _ = _DOMAIN_SUPERVISOR_MODULES[key]
    module = __import__(module_name, fromlist=[graph_fn])
    builder = getattr(module, graph_fn)
    return builder(model=model, **kwargs)


def build_compiled_domain_supervisor(
    domain: str,
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> CompiledStateGraph:
    """Build and compile the domain supervisor graph for one domain.

    Same domain resolution rules as :func:`build_domain_supervisor_graph`;
    the compiled graph additionally honours ``checkpointer`` (pass a
    LangGraph checkpointer such as ``MemorySaver`` / ``SqliteSaver`` for a
    persistent run, or ``None`` for an ephemeral one).
    """
    key = _normalize_domain(domain)
    module_name, _, compiled_fn = _DOMAIN_SUPERVISOR_MODULES[key]
    module = __import__(module_name, fromlist=[compiled_fn])
    builder = getattr(module, compiled_fn)
    return builder(checkpointer=checkpointer, model=model, **kwargs)


# --------------------------------------------------------------------------- #
# Per-domain convenience aliases
#
# Each pair is a thin delegation to the dynamic factory above, kept as stable
# public names for callers that prefer the explicit domain spelling.
# --------------------------------------------------------------------------- #
def build_tube_supervisor_graph(
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> StateGraph:
    """Build the Tube B domain supervisor graph (un-compiled)."""
    return build_domain_supervisor_graph(
        DOMAIN_TUBE, model=model, checkpointer=checkpointer, **kwargs
    )


def build_compiled_tube_supervisor(
    checkpointer: Any = None,
    model: Any = None,
    **kwargs: Any,
) -> CompiledStateGraph:
    """Build and compile the Tube B domain supervisor graph."""
    return build_compiled_domain_supervisor(
        DOMAIN_TUBE, model=model, checkpointer=checkpointer, **kwargs
    )


def build_routing_supervisor_graph(
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> StateGraph:
    """Build the Routing domain supervisor graph (un-compiled)."""
    return build_domain_supervisor_graph(
        DOMAIN_ROUTING, model=model, checkpointer=checkpointer, **kwargs
    )


def build_compiled_routing_supervisor(
    checkpointer: Any = None,
    model: Any = None,
    **kwargs: Any,
) -> CompiledStateGraph:
    """Build and compile the Routing domain supervisor graph."""
    return build_compiled_domain_supervisor(
        DOMAIN_ROUTING, model=model, checkpointer=checkpointer, **kwargs
    )


def build_scheduling_supervisor_graph(
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> StateGraph:
    """Build the Scheduling (JSSP) domain supervisor graph (un-compiled)."""
    return build_domain_supervisor_graph(
        DOMAIN_SCHEDULING, model=model, checkpointer=checkpointer, **kwargs
    )


def build_compiled_scheduling_supervisor(
    checkpointer: Any = None,
    model: Any = None,
    **kwargs: Any,
) -> CompiledStateGraph:
    """Build and compile the Scheduling (JSSP) domain supervisor graph."""
    return build_compiled_domain_supervisor(
        DOMAIN_SCHEDULING, model=model, checkpointer=checkpointer, **kwargs
    )


def build_project_supervisor_graph(
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> StateGraph:
    """Build the Project (RCPSP) domain supervisor graph (un-compiled)."""
    return build_domain_supervisor_graph(
        DOMAIN_PROJECT, model=model, checkpointer=checkpointer, **kwargs
    )


def build_compiled_project_supervisor(
    checkpointer: Any = None,
    model: Any = None,
    **kwargs: Any,
) -> CompiledStateGraph:
    """Build and compile the Project (RCPSP) domain supervisor graph."""
    return build_compiled_domain_supervisor(
        DOMAIN_PROJECT, model=model, checkpointer=checkpointer, **kwargs
    )


def build_inventory_supervisor_graph(
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> StateGraph:
    """Build the Inventory (lot-sizing) domain supervisor graph (un-compiled)."""
    return build_domain_supervisor_graph(
        DOMAIN_INVENTORY, model=model, checkpointer=checkpointer, **kwargs
    )


def build_compiled_inventory_supervisor(
    checkpointer: Any = None,
    model: Any = None,
    **kwargs: Any,
) -> CompiledStateGraph:
    """Build and compile the Inventory (lot-sizing) domain supervisor graph."""
    return build_compiled_domain_supervisor(
        DOMAIN_INVENTORY, model=model, checkpointer=checkpointer, **kwargs
    )


def build_facility_supervisor_graph(
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> StateGraph:
    """Build the Facility (location) domain supervisor graph (un-compiled)."""
    return build_domain_supervisor_graph(
        DOMAIN_FACILITY, model=model, checkpointer=checkpointer, **kwargs
    )


def build_compiled_facility_supervisor(
    checkpointer: Any = None,
    model: Any = None,
    **kwargs: Any,
) -> CompiledStateGraph:
    """Build and compile the Facility (location) domain supervisor graph."""
    return build_compiled_domain_supervisor(
        DOMAIN_FACILITY, model=model, checkpointer=checkpointer, **kwargs
    )


def build_rostering_supervisor_graph(
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> StateGraph:
    """Build the Rostering domain supervisor graph (un-compiled)."""
    return build_domain_supervisor_graph(
        DOMAIN_ROSTERING, model=model, checkpointer=checkpointer, **kwargs
    )


def build_compiled_rostering_supervisor(
    checkpointer: Any = None,
    model: Any = None,
    **kwargs: Any,
) -> CompiledStateGraph:
    """Build and compile the Rostering domain supervisor graph."""
    return build_compiled_domain_supervisor(
        DOMAIN_ROSTERING, model=model, checkpointer=checkpointer, **kwargs
    )


def build_microgrid_supervisor_graph(
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> StateGraph:
    """Build the Microgrid domain supervisor graph (un-compiled)."""
    return build_domain_supervisor_graph(
        DOMAIN_MICROGRID, model=model, checkpointer=checkpointer, **kwargs
    )


def build_compiled_microgrid_supervisor(
    checkpointer: Any = None,
    model: Any = None,
    **kwargs: Any,
) -> CompiledStateGraph:
    """Build and compile the Microgrid domain supervisor graph."""
    return build_compiled_domain_supervisor(
        DOMAIN_MICROGRID, model=model, checkpointer=checkpointer, **kwargs
    )


def build_pricing_supervisor_graph(
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> StateGraph:
    """Build the Pricing domain supervisor graph (un-compiled)."""
    return build_domain_supervisor_graph(
        DOMAIN_PRICING, model=model, checkpointer=checkpointer, **kwargs
    )


def build_compiled_pricing_supervisor(
    checkpointer: Any = None,
    model: Any = None,
    **kwargs: Any,
) -> CompiledStateGraph:
    """Build and compile the Pricing domain supervisor graph."""
    return build_compiled_domain_supervisor(
        DOMAIN_PRICING, model=model, checkpointer=checkpointer, **kwargs
    )


def build_finance_supervisor_graph(
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> StateGraph:
    """Build the Finance domain supervisor graph (un-compiled)."""
    return build_domain_supervisor_graph(
        DOMAIN_FINANCE, model=model, checkpointer=checkpointer, **kwargs
    )


def build_compiled_finance_supervisor(
    checkpointer: Any = None,
    model: Any = None,
    **kwargs: Any,
) -> CompiledStateGraph:
    """Build and compile the Finance domain supervisor graph."""
    return build_compiled_domain_supervisor(
        DOMAIN_FINANCE, model=model, checkpointer=checkpointer, **kwargs
    )


# --------------------------------------------------------------------------- #
# Composite supervisor (Task 4.3)
# --------------------------------------------------------------------------- #
COMPOSITE_LRP = "LRP"
COMPOSITE_IRP = "IRP"
COMPOSITE_PRP = "PRP"
COMPOSITE_MICROGRID_FACILITY = "MICROGRID_FACILITY"
COMPOSITE_CUSTOM = "CUSTOM"

#: Canonical composite problem classes accepted by the composite lead.
SUPPORTED_COMPOSITE_TYPES: tuple[str, ...] = (
    COMPOSITE_LRP,
    COMPOSITE_IRP,
    COMPOSITE_PRP,
    COMPOSITE_MICROGRID_FACILITY,
    COMPOSITE_CUSTOM,
)

#: Composite domain chain (as produced by ``meta_router.route_problem``) →
#: canonical composite class. ``CUSTOM`` is the fallback for unknown chains.
_COMPOSITE_CHAIN_TYPES: dict[tuple[str, ...], str] = {
    (DOMAIN_FACILITY, DOMAIN_ROUTING): COMPOSITE_LRP,
    (DOMAIN_INVENTORY, DOMAIN_ROUTING): COMPOSITE_IRP,
    (DOMAIN_SCHEDULING, DOMAIN_INVENTORY, DOMAIN_ROUTING): COMPOSITE_PRP,
    (DOMAIN_FACILITY, DOMAIN_MICROGRID): COMPOSITE_MICROGRID_FACILITY,
}


def build_composite_supervisor(
    composite_type: str,
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> CompiledStateGraph:
    """Build and compile the cross-domain composite supervisor graph.

    Parameters
    ----------
    composite_type
        One of ``SUPPORTED_COMPOSITE_TYPES``: ``LRP``, ``IRP``, ``PRP``,
        ``MICROGRID_FACILITY`` or ``CUSTOM``. Unknown types raise
        ``ValueError``. ``CUSTOM`` additionally requires ``domain_chain``.
    model
        Accepted for interface symmetry with the domain factories; the
        composite pipeline is deterministic (solver-backed, no LLM).
    checkpointer
        LangGraph checkpointer forwarded to the compiled composite graph.
    **kwargs
        Forwarded to ``orpath.agents.composite_lead.build_compiled_composite_supervisor``
        (``domain_chain``, ``domain_executors``).

    Returns
    -------
    CompiledStateGraph
    """
    key = str(composite_type or "").strip().upper()
    if key not in SUPPORTED_COMPOSITE_TYPES:
        raise ValueError(
            f"unknown composite_type {composite_type!r}; supported types: "
            f"{list(SUPPORTED_COMPOSITE_TYPES)}"
        )
    from orpath.agents.composite_lead import (
        build_compiled_composite_supervisor as _build_composite,
    )

    return _build_composite(
        composite_type=key,
        checkpointer=checkpointer,
        **kwargs,
    )


def dispatch_supervisor_for_problem(
    data: Any = None,
    text: str = "",
    filename: str = "",
    model: Any = None,
    checkpointer: Any = None,
) -> tuple[Any, "DomainRouteResult"]:
    """Auto-route an OR problem and build the matching compiled supervisor.

    Runs the Meta-Router (``orpath.agents.meta_router.route_problem``) over the
    structured payload / free text / filename, then:

      * single-domain verdict → ``build_compiled_domain_supervisor`` for that
        domain;
      * composite verdict (e.g. LRP / PRP) → ``build_composite_supervisor``
        for the matching composite class.

    Parameters
    ----------
    data
        Structured problem payload (dict / JSON string / pydantic-like).
    text
        Free-text problem description.
    filename
        Problem file name.
    model
        Optional chat model forwarded to the router's LLM fallback probe and
        to the domain supervisor workers.
    checkpointer
        LangGraph checkpointer forwarded to the compiled supervisor.

    Returns
    -------
    tuple
        ``(compiled_graph, route_result)`` where ``route_result`` is the
        underlying ``DomainRouteResult``.
    """
    from orpath.agents.meta_router import route_problem

    route_result = route_problem(data=data, text=text, filename=filename, model=model)

    if route_result.is_composite:
        chain = tuple(route_result.composite_domains)
        composite_type = _COMPOSITE_CHAIN_TYPES.get(chain, COMPOSITE_CUSTOM)
        kwargs: dict[str, Any] = {}
        if composite_type == COMPOSITE_CUSTOM:
            kwargs["domain_chain"] = list(chain)
        compiled = build_composite_supervisor(
            composite_type,
            model=model,
            checkpointer=checkpointer,
            **kwargs,
        )
    else:
        compiled = build_compiled_domain_supervisor(
            route_result.domain,
            model=model,
            checkpointer=checkpointer,
        )
    return compiled, route_result


def build_isolated_pipeline_graph(
    model: Any = None,
    checkpointer: Any = None,
    **kwargs: Any,
) -> Any:
    """Build the artifact-driven isolated multi-agent pipeline graph (un-compiled)."""
    from orpath.agents.supervisor import build_isolated_pipeline_graph as _build_isolated

    return _build_isolated(model=model, checkpointer=checkpointer, **kwargs)


def build_compiled_isolated_pipeline(
    checkpointer: Any = None,
    model: Any = None,
    **kwargs: Any,
) -> Any:
    """Build and compile the artifact-driven isolated multi-agent pipeline graph."""
    from orpath.agents.supervisor import build_compiled_isolated_pipeline as _compile_isolated

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
) -> dict[str, Any]:
    """Canonical ORPathState seed for product runs."""
    root = Path(root)
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
    }


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
    # domain supervisor registry (Task 4.3)
    "build_compiled_domain_supervisor",
    "build_domain_supervisor_graph",
    "build_tube_supervisor_graph",
    "build_compiled_tube_supervisor",
    "build_routing_supervisor_graph",
    "build_compiled_routing_supervisor",
    "build_scheduling_supervisor_graph",
    "build_compiled_scheduling_supervisor",
    "build_project_supervisor_graph",
    "build_compiled_project_supervisor",
    "build_inventory_supervisor_graph",
    "build_compiled_inventory_supervisor",
    "build_facility_supervisor_graph",
    "build_compiled_facility_supervisor",
    "build_rostering_supervisor_graph",
    "build_compiled_rostering_supervisor",
    "build_microgrid_supervisor_graph",
    "build_compiled_microgrid_supervisor",
    "build_pricing_supervisor_graph",
    "build_compiled_pricing_supervisor",
    "build_finance_supervisor_graph",
    "build_compiled_finance_supervisor",
    "SUPPORTED_DOMAIN_SUPERVISORS",
    "DOMAIN_TUBE",
    "DOMAIN_ROUTING",
    "DOMAIN_SCHEDULING",
    "DOMAIN_PROJECT",
    "DOMAIN_INVENTORY",
    "DOMAIN_FACILITY",
    "DOMAIN_ROSTERING",
    "DOMAIN_MICROGRID",
    "DOMAIN_PRICING",
    "DOMAIN_FINANCE",
    # composite supervisor (Task 4.3)
    "build_composite_supervisor",
    "dispatch_supervisor_for_problem",
    "COMPOSITE_LRP",
    "COMPOSITE_IRP",
    "COMPOSITE_PRP",
    "COMPOSITE_MICROGRID_FACILITY",
    "COMPOSITE_CUSTOM",
    "SUPPORTED_COMPOSITE_TYPES",
    # shared helpers
    "db_path",
    "default_initial",
    "export_stage_map",
    "get_chat_model",
    "invoke_once",
    "is_real_llm_configured",
    "open_sqlite_checkpointer",
    "PRODUCT_NODES",
    "summarize_run",
    "thread_config",
    "write_stage_map_files",
]
