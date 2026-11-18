#!/usr/bin/env python3
"""Tier-A / Tier-B / Tier-C adaptive routing state machine (Plan 1.5).

Replaces the polling LLM supervisor (``transfer_to_*`` round-trips) with a
**pure-Python conditional edge function** driving the 4 elite worker factories
(``orpath.agents.workers``) and the deterministic gates
(``orpath.agents.deterministic_nodes``):

  * **Tier-A** (easy-exact classes: LP / convex QP / shortest path / max flow
    / Wagner-Whitin DP):
      preflight → analyst → modeler(exact) → deterministic_validator →
      table_renderer → writer → deterministic_doc_gate → END
      (optional reviewer attachment for the gold-standard closure);
  * **Tier-B** (hard combinatorial classes: VRPTW / JSSP / RCPSP / CFLP /
    rostering / bin packing / tube / polyomino / microgrid):
      preflight → analyst → modeler(bound + search) → deterministic_validator
      ⇄ (failure bounces back to modeler, capped by ``max_retries``) →
      table_renderer → writer → reviewer ⇄ (FATAL bounces back to writer);
  * **Tier-C** (multi-question progressive contests, e.g.
    ``subproblems = ["q1","q2","q3","q4"]``): after the analyst a
    ``tier_c_focus`` node launches isolated modeler sub-instances per question
    in a strict dependency order, passing cross-question state artifacts
    (residual ledgers, initial SOC) through ``notes/<slug>-ledger.json``; a
    per-question deterministic validator gates each question; once every
    question passes, the merged envelope is rendered, written and reviewed.

Acceptance contracts enforced by ``tools/test_adaptive_graph.py``:

  * Tier-A / Tier-B / Tier-C flow through exactly the documented node
    sequences (fake agents + REAL deterministic validators, fully offline);
  * modeler bounce-back and reviewer FATAL bounce-back are strictly bounded by
    ``max_retries`` — the graph always terminates (no polling loop, no hang);
  * every LLM stage invokes its agent in a fresh isolated message list whose
    brief carries **only file pointers + compact ledgers** — Feynman file
    handoffs, never cross-agent chat pollution.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Literal, Mapping

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from orpath.agents.callbacks import persist_agent_stage_log
from orpath.agents.deterministic_nodes import (
    run_deterministic_validator,
    run_preflight_probe,
    validate_artifact,
)

__all__ = [
    "ADAPTIVE_NODES",
    "ISOLATED_PIPELINE_NODES",
    "AdaptivePipelineState",
    "AdaptiveORState",
    "MultiAgentPipelineState",
    "TIER_A_CLASSES",
    "build_adaptive_graph",
    "build_compiled_adaptive_graph",
    "build_isolated_pipeline_graph",
    "build_compiled_isolated_pipeline",
    "adaptive_stage_map",
    "decide_tier",
    "render_truth_tables",
    "run_deterministic_doc_gate",
    "parse_review_reply",
]

#: Tier-A "easy-exact" problem classes (LP / convex QP / 最短路 / 最大流 / DP).
TIER_A_CLASSES = frozenset(
    {
        "shortest_path",
        "network_flow",
        "lot_sizing",
        "portfolio_opt",
        "stochastic_lp",
        "game_theory",
    }
)

try:  # TypedDict base from Plan 1.2
    from orpath.agents.core_state import CorePipelineState
except Exception:  # pragma: no cover
    from typing import TypedDict

    class CorePipelineState(TypedDict, total=False):  # type: ignore[misc]
        slug: str


class AdaptivePipelineState(CorePipelineState, total=False):  # type: ignore[misc]
    """Pointer-only state of the adaptive tier machine (superset of core)."""

    # deterministic-gate bookkeeping (Plan 1.4 outputs)
    preflight_ok: bool
    preflight_summary: str
    recomputed_objective: float | None
    validator_errors: list[str]
    # LLM stage summaries stay compact (detail lives in notes/ artifacts)
    tier: str
    analyst_summary: str
    modeler_summary: str
    reviewer_summary: str
    # artifacts
    tables_path: str
    ledger_path: str
    knowledge_pack_path: str
    retrieval_path: str
    lessons_path: str
    remediation_path: str
    analyst_brief_path: str
    tournament_path: str
    failure_report_path: str
    track_a_solution_path: str
    track_b_solution_path: str
    winning_track: str
    objective_sense: str
    # deterministic doc gate
    doc_gate_ok: bool
    doc_gate_errors: list[str]
    require_knowledge_citations: bool
    # reviewer verdict
    review_verdict: str
    subproblem_done: list[str]
    tier_c_results: dict[str, Any]
    # control & lifecycle fields shared across Deep Mode / isolated pipeline
    root: str
    solve_mode: str
    raw_problem_text: str
    summary: str
    skip_paper: bool
    run_mode: str
    enable_horse_race: bool
    enforce_anti_cosplay: bool
    cosplay_quarantined: list[str]
    lifecycle_status: str
    stage: str
    model_attempts: int
    writer_attempts: int
    model_repair_count: int
    max_model_repairs: int
    revision_count: int
    max_revisions: int
    deep_mode: bool
    deep_evolution: bool
    evo_round: int
    evo_target_rounds: int
    evo_max_rounds: int
    evo_promoted: bool
    incumbent_objective: float | None
    incumbent_available: bool
    evolution_ledger_path: str
    refinement_rounds: int
    max_refinement_rounds: int
    best_objective: float
    mutation_history: list[str]


AdaptiveORState = AdaptivePipelineState
MultiAgentPipelineState = AdaptivePipelineState


ADAPTIVE_NODES = (
    "preflight",
    "analyst",
    "modeler",
    "validator",
    "table_render",
    "writer",
    "doc_gate",
    "reviewer",
    "tier_c_focus",
    "fail_closed",
)
ISOLATED_PIPELINE_NODES: tuple[str, ...] = ADAPTIVE_NODES

_MAX_BRIEF_LEDGER_BYTES = 4000
_FORBIDDEN_SCHEMA_KEYS = frozenset(
    {
        "objective",
        "tour",
        "routes",
        "path",
        "optimal",
        "optimal_value",
        "placements",
        "answers",
        "values",
        "schedule",
    }
)
_MAXIMIZATION_CLASSES = frozenset(
    {
        "max_flow",
        "max_clique",
        "knapsack",
        "portfolio_opt",
        "interval_coverage",
    }
)

_RECURSION_LIMIT_SENTINEL = "sorry, need more steps to process this request"


def _is_recursion_exhausted_text(text: str | None) -> bool:
    """Return True when text is LangGraph's recursion-exhaustion fallback string."""
    low = str(text or "").strip().lower()
    if not low:
        return False
    return _RECURSION_LIMIT_SENTINEL in low


def _summarize_salvaged_solution(sol_path: Path, round_idx: int | None = None) -> str:
    """Build a factual concise summary from a solution artifact on disk."""
    prefix = f"R{round_idx} " if round_idx else ""
    if not sol_path.is_file():
        return f"{prefix}completed without summary note"
    try:
        doc = json.loads(sol_path.read_text(encoding="utf-8"))
        if isinstance(doc, Mapping):
            solver = str(doc.get("solver") or "custom_solver").strip()
            status = str(doc.get("status") or "-").strip()
            obj = doc.get("objective")
            return f"{prefix}{solver}: status={status}, objective={obj}"
    except Exception:
        pass
    return f"{prefix}solution artifact written to {sol_path.name}"


def _sanitize_hypothesis(raw_text: str | None, sol_path: Path, round_idx: int | None = None) -> str:
    """Replace empty/recursion-sentinel hypotheses with factual artifact metadata."""
    cleaned = str(raw_text or "").strip()
    if not cleaned or _is_recursion_exhausted_text(cleaned):
        return _summarize_salvaged_solution(sol_path, round_idx=round_idx)
    return cleaned[:160]


# --------------------------------------------------------------------------- #
# Tier classification — pure Python, no LLM
# --------------------------------------------------------------------------- #
def decide_tier(state: Mapping[str, Any]) -> str:
    """Deterministic tier decision: explicit override > subproblems > class map."""
    explicit = str(state.get("complexity_tier") or "").strip().upper()
    if explicit in ("A", "B", "C"):
        return explicit
    subs = [str(s).strip() for s in (state.get("subproblems") or []) if str(s).strip()]
    if subs:
        return "C"
    cls = str(state.get("problem_class") or "").strip().lower()
    if not cls:
        try:
            from orpath.domain_registry import normalize_problem_class

            cls = normalize_problem_class(cls) or ""
        except Exception:
            pass
    return "A" if cls in TIER_A_CLASSES else "B"


# --------------------------------------------------------------------------- #
# Agent runner (isolated fresh message list per invoke)
# --------------------------------------------------------------------------- #
def _resolve_root(state: Mapping[str, Any]) -> Path:
    raw = str(state.get("workdir") or "").strip()
    if raw:
        try:
            return Path(raw).expanduser().resolve()
        except OSError:
            return Path(raw).expanduser()
    env = os.environ.get("ORPATH_WORKDIR") or ""
    return Path(env).expanduser().resolve() if env else Path.cwd()


def _slug(state: Mapping[str, Any], root: Path) -> str:
    return str(state.get("slug") or "").strip() or root.name


def _format_num(v: Any) -> str:
    if v is None:
        return "-"
    try:
        f = float(v)
        if f == int(f):
            return str(int(f))
        return f"{f:g}"
    except (TypeError, ValueError):
        return str(v)[:120]


def _brief(state: Mapping[str, Any], workdir: Path, slug: str, extra_lines: list[str]) -> str:
    """Compact pointer-only task brief — no upstream agent transcripts."""
    pc = state.get("problem_class") or ""
    lines = [
        "[OR-Path 任务简报 (Task Brief)]",
        f"workdir={workdir} slug={slug}",
        f"problem_id={state.get('problem_id') or '-'}",
        f"problem_class={pc or '-'}",
        f"domain={state.get('domain_cartridge') or '-'}",
        f"complexity_tier={state.get('complexity_tier') or decide_tier(state)}",
        "上游工件 (仅文件指针，全文请自行调用 read_problem_file):",
        f"- profile_path: {state.get('profile_path') or '-'}",
        f"- knowledge_pack_path: {state.get('knowledge_pack_path') or '-'}",
        f"- retrieval_path: {state.get('retrieval_path') or '-'}",
        f"- lessons_path: {state.get('lessons_path') or '-'}",
        f"- problem_file: {state.get('problem_file') or '-'}",
        f"- data_files: {state.get('data_files') or []}",
    ]
    if state.get("remediation_path"):
        lines.append(f"- remediation_path: {state.get('remediation_path')}")
    lines.append("允许读写目录: outputs/ notes/ papers/ runs/")
    # Inline a compact pre-digested profile + statement excerpt so specialists
    # don't waste 15 LLM calls listing the repo and reading large files piecemeal.
    prof_raw = str(state.get("profile_path") or "").strip()
    if prof_raw and Path(prof_raw).is_file():
        try:
            pdoc = json.loads(Path(prof_raw).read_text(encoding="utf-8"))
            if isinstance(pdoc, Mapping):
                p_items = []
                for inp in (pdoc.get("input_files") or [])[:6]:
                    if isinstance(inp, Mapping):
                        p_items.append(f"{inp.get('file')}(fmt={inp.get('format')},rows={inp.get('rows')},sheets={list((inp.get('sheets') or {}).keys())[:3]})")
                if p_items:
                    lines.append("数据探针摘要: " + " ; ".join(p_items)[:900])
        except Exception:
            pass
    stmt_candidates = [str(state.get("problem_file") or "").strip()] + [
        str(df) for df in (state.get("data_files") or []) if str(df).lower().endswith((".txt", ".md", ".pdf", ".docx"))
    ]
    if not any(c and c != "-" for c in stmt_candidates):
        inbox_slug = workdir / "inbox" / str(state.get("slug") or "")
        if inbox_slug.is_dir():
            stmt_candidates.extend(
                str(p) for p in sorted(inbox_slug.rglob("*")) if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".md", ".txt"}
            )
    for cand in stmt_candidates:
        if not cand or cand == "-":
            continue
        cp = Path(cand) if Path(cand).is_absolute() else (workdir / cand)
        if cp.is_file():
            try:
                if cp.suffix.lower() in {".pdf", ".docx"}:
                    from tools.intake_assets import read_statement_text

                    raw_stmt = read_statement_text(cp, max_chars=4500)
                else:
                    raw_stmt = cp.read_text(encoding="utf-8", errors="replace")
                excerpt = re.sub(r"\s+", " ", raw_stmt).strip()[:3600]
                if excerpt:
                    lines.append(f"题面核心摘录({cp.name}): {excerpt}")
                break
            except Exception:
                pass
    lines.extend(extra_lines)
    return "\n".join(lines)


def _extract_ai_text(msgs: list[Any]) -> str:
    for msg in reversed(list(msgs)):
        if isinstance(msg, AIMessage):
            text = msg.content
            if isinstance(text, list):
                text = json.dumps(text, ensure_ascii=False, default=str)
            return str(text)[:8000]
        if isinstance(msg, Mapping) and msg.get("content"):
            return str(msg.get("content"))[:8000]
    return ""


def _invoke_with_trace(
    agent: Any,
    brief: str,
    root: Path,
    slug: str,
    stage_name: str,
    *,
    wall_timeout_s: float | None = None,
    max_rec_limit: int | None = None,
) -> tuple[str, list[Any]]:
    """Invoke an elite worker in a fresh 1-message list and persist its stage JSONL log."""
    import concurrent.futures as _cf
    import contextvars as _cv
    import time as _time

    rec_limit = (
        int(max_rec_limit)
        if max_rec_limit and int(max_rec_limit) > 0
        else (26 if stage_name in ("analyst", "writer", "reviewer") else 32)
    )
    payload = {"messages": [HumanMessage(brief)]}
    try:
        import inspect

        sig = inspect.signature(agent.invoke)
        accepts_cfg = (
            "config" in sig.parameters
            or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        )
    except Exception:
        accepts_cfg = False

    agent_label = {
        "analyst": "or_analyst",
        "writer": "or_writer",
        "reviewer": "or_reviewer",
    }.get(stage_name, "or_modeler" if "modeler" in stage_name or "tier_c" in stage_name else f"or_{stage_name}")

    def _invoke_with_trace_abort_err(label: str, limit_s: float) -> TimeoutError:
        return TimeoutError(f"{label} exceeded {float(limit_s):.1f}s wall-clock ceiling")

    cancel_event = None
    partial_trace: list[dict[str, Any]] = []
    if wall_timeout_s is not None and float(wall_timeout_s) > 0:
        import threading as _th
        import time as _mono

        from langchain_core.callbacks import BaseCallbackHandler

        cancel_event = _th.Event()
        deadline_mono = _mono.monotonic() + float(wall_timeout_s)

        class _DeadlineCancelCallback(BaseCallbackHandler):
            raise_error: bool = True

            def _check(self, phase: str) -> None:
                if cancel_event.is_set() or _mono.monotonic() >= deadline_mono:
                    partial_trace.append({"stage": stage_name, "event": "wall_timeout_abort", "phase": phase})
                    try:
                        persist_agent_stage_log(root, slug, f"{stage_name}_timeout", partial_trace[-2:])
                    except Exception:
                        pass
                    raise _invoke_with_trace_abort_err(agent_label, float(wall_timeout_s))

            def on_llm_start(self, serialized: Any, prompts: Any, **kwargs: Any) -> Any:
                self._check("on_llm_start")

            def on_chat_model_start(self, serialized: Any, messages: Any, **kwargs: Any) -> Any:
                self._check("on_chat_model_start")

            def on_llm_new_token(self, token: str, **kwargs: Any) -> Any:
                self._check("on_llm_new_token")

            def on_tool_start(self, serialized: Any, input_str: str, **kwargs: Any) -> Any:
                name = (serialized or {}).get("name") if isinstance(serialized, Mapping) else str(serialized)
                partial_trace.append({"stage": stage_name, "event": "tool_start", "tool": name})
                self._check(f"on_tool_start:{name}")

            def on_tool_end(self, output: Any, **kwargs: Any) -> Any:
                partial_trace.append({"stage": stage_name, "event": "tool_end", "len": len(str(output or ""))})
                self._check("on_tool_end")

        deadline_cb: Any = _DeadlineCancelCallback()
    else:
        deadline_cb = None

    def _call_once() -> Any:
        if accepts_cfg:
            child_cfg: dict[str, Any] = {
                "recursion_limit": rec_limit,
                "run_name": agent_label,
                "metadata": {"agent": agent_label, "langgraph_node": stage_name},
            }
            if deadline_cb is not None:
                from langchain_core.runnables.config import merge_configs, var_child_runnable_config

                child_cfg["callbacks"] = [deadline_cb]
                child_cfg = merge_configs(var_child_runnable_config.get(), child_cfg)
            return agent.invoke(payload, config=child_cfg)
        return agent.invoke(payload)

    resp: Any = None
    for attempt in range(4):
        try:
            if wall_timeout_s is not None and float(wall_timeout_s) > 0:
                ex = _cf.ThreadPoolExecutor(max_workers=1)
                ctx = _cv.copy_context()
                fut = ex.submit(ctx.run, _call_once)
                try:
                    resp = fut.result(timeout=float(wall_timeout_s))
                except _cf.TimeoutError:
                    if cancel_event is not None:
                        cancel_event.set()
                    try:
                        persist_agent_stage_log(
                            root,
                            slug,
                            f"{stage_name}_timeout",
                            partial_trace or [{"stage": stage_name, "event": "wall_timeout", "limit_s": float(wall_timeout_s)}],
                        )
                    except Exception:
                        pass
                    raise
                finally:
                    ex.shutdown(wait=False, cancel_futures=True)
            else:
                resp = _call_once()
            break
        except _cf.TimeoutError as t_exc:
            raise _invoke_with_trace_abort_err(agent_label, float(wall_timeout_s)) from t_exc
        except TimeoutError:
            if cancel_event is not None and cancel_event.is_set():
                if partial_trace:
                    try:
                        persist_agent_stage_log(root, slug, f"{stage_name}_timeout", partial_trace)
                    except Exception:
                        pass
                raise
            if attempt < 1:
                _time.sleep(5.0 * (attempt + 1))
                continue
            raise
        except Exception as exc:
            msg = str(exc).lower()
            is_transient = (
                "429" in msg
                or "rate limit" in msg
                or "frequency limit" in msg
                or ("timed out" in msg and attempt < 1)
                or ("timeout" in msg and attempt < 1)
            )
            if is_transient and attempt < 3:
                _time.sleep(5.0 * (attempt + 1))
                continue
            raise
    msgs = list(resp.get("messages") or []) if isinstance(resp, Mapping) else [AIMessage(content=str(resp))]
    text = _extract_ai_text(msgs)
    try:
        persist_agent_stage_log(root, slug, stage_name, msgs or [{"stage": stage_name, "text": text}])
    except Exception:
        pass
    return text, msgs


def _invoke_agent(agent: Any, brief: str) -> str:
    """Invoke an elite worker in a brand-new isolated message list."""
    resp = agent.invoke({"messages": [HumanMessage(brief)]})
    msgs = resp.get("messages") if isinstance(resp, Mapping) else None
    if not msgs:
        return ""
    return _extract_ai_text(list(msgs))


def _has_tool_execution(msgs: list[Any]) -> bool:
    """Return True when the agent trace contains at least one real tool invocation."""
    for m in msgs:
        if getattr(m, "tool_calls", None):
            return True
        if getattr(m, "type", "") == "tool":
            return True
        if isinstance(m, Mapping):
            if m.get("tool_calls") or m.get("type") == "tool" or m.get("role") == "tool":
                return True
    return False


def _quarantine_file(path: Path) -> str | None:
    """Move an offending anti-cosplay artifact aside to ``<name>.cosplay-quarantine``."""
    if not path.is_file():
        return None
    q_path = path.with_name(path.name + ".cosplay-quarantine")
    try:
        path.replace(q_path)
        return str(q_path)
    except OSError:
        try:
            shutil.copy2(path, q_path)
            path.unlink()
            return str(q_path)
        except OSError:
            return None


def _check_and_quarantine_cosplay(
    msgs: list[Any],
    sol_path: Path,
    schema_path: Path,
    *,
    enforce: bool,
    fenced_executed: bool = False,
) -> tuple[bool, str, list[str]]:
    """Detect schema leaks or tool-free solution writes and quarantine fake artifacts."""
    if not enforce:
        return False, "", []

    reasons: list[str] = []
    quarantined: list[str] = []

    if schema_path.is_file():
        try:
            sdoc = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            sdoc = {}
        if isinstance(sdoc, Mapping):
            bad_keys = sorted(k for k in sdoc if str(k).lower() in _FORBIDDEN_SCHEMA_KEYS)
            if bad_keys:
                q_p = _quarantine_file(schema_path)
                if q_p:
                    quarantined.append(q_p)
                reasons.append(f"schema.json contains forbidden solution keys: {', '.join(bad_keys)}")

    if not fenced_executed and not _has_tool_execution(msgs) and sol_path.is_file():
        q_p = _quarantine_file(sol_path)
        if q_p:
            quarantined.append(q_p)
        reasons.append("modeler finished without calling solver or script execution tools")

    return bool(reasons), "; ".join(reasons), quarantined


def _build_dynamic_role_agent(
    role_key: str,
    model: Any,
    state: Mapping[str, Any],
    base_cartridge_tools: Any = None,
    base_directive: str = "",
) -> Any:
    """Construct an elite role worker dynamically bound to the active DomainCartridge."""
    from orpath.agents.cartridges import cartridge_tools as _get_cart_tools, resolve_cartridge
    from orpath.agents.tools_or import GENERAL_OR_TOOLS
    from orpath.agents.workers import (
        create_analyst_agent,
        create_modeler_agent,
        create_reviewer_agent,
        create_writer_agent,
    )

    pc_or_dom = str(state.get("domain_cartridge") or state.get("problem_class") or "").strip()
    cartridge = resolve_cartridge(pc_or_dom)
    ct_map = _get_cart_tools(cartridge.domain)
    domain_tools: list[Any] = [t for t in (ct_map.get("profile_tool"), ct_map.get("inspect_tool")) if t is not None]
    if base_cartridge_tools:
        extra_ct = base_cartridge_tools if isinstance(base_cartridge_tools, (list, tuple, set)) else [base_cartridge_tools]
        domain_tools.extend(extra_ct)

    checklist = " | ".join(cartridge.modeling_checklist)
    directive_parts = [p for p in (
        base_directive.strip(),
        f"DomainCartridge={cartridge.domain}; solver_modes={','.join(cartridge.solver_modes)}" + (f"; checklist={checklist}" if checklist else ""),
    ) if p]
    directive = "\n".join(directive_parts)

    if role_key == "analyst":
        return create_analyst_agent(model=model, cartridge_tools=domain_tools or None, domain_directive=directive)
    if role_key == "modeler":
        return create_modeler_agent(
            model=model,
            cartridge_tools=domain_tools or None,
            domain_directive=directive,
            extra_tools=list(GENERAL_OR_TOOLS),
        )
    if role_key == "writer":
        return create_writer_agent(
            model=model,
            cartridge_tools=domain_tools or None,
            domain_directive=directive,
        )
    if role_key == "reviewer":
        return create_reviewer_agent(
            model=model,
            cartridge_tools=domain_tools or None,
            domain_directive=directive,
        )
    raise ValueError(f"Unknown role key: {role_key}")


def _default_agents(model: Any, cartridge_tools: Any, domain_directive: str) -> dict[str, Any]:
    from orpath.agents.workers import (
        ANALYST_NAME,
        MODELER_NAME,
        REVIEWER_NAME,
        WRITER_NAME,
    )

    empty_state: dict[str, Any] = {}
    return {
        ANALYST_NAME: _build_dynamic_role_agent("analyst", model, empty_state, cartridge_tools, domain_directive),
        MODELER_NAME: _build_dynamic_role_agent("modeler", model, empty_state, cartridge_tools, domain_directive),
        WRITER_NAME: _build_dynamic_role_agent("writer", model, empty_state, cartridge_tools, domain_directive),
        REVIEWER_NAME: _build_dynamic_role_agent("reviewer", model, empty_state, cartridge_tools, domain_directive),
    }


# --------------------------------------------------------------------------- #
# Deterministic adjuncts
# --------------------------------------------------------------------------- #
def render_truth_tables(state: Mapping[str, Any]) -> dict[str, Any]:
    """Pre-render verified truth tables/figures around solver output (0 LLM)."""
    root = _resolve_root(state)
    slug = _slug(state, root)
    (root / "outputs").mkdir(parents=True, exist_ok=True)
    solution_path = state.get("solution_path") or ""
    if not solution_path or not (root / solution_path if not Path(solution_path).is_absolute() else Path(solution_path)).is_file():
        sol = {}
        src = str(solution_path or "-")
    else:
        p = Path(solution_path)
        sol = json.loads(p.read_text(encoding="utf-8"))
        src = str(p)
    validate_path = state.get("validate_path")
    val = {}
    if validate_path:
        vp = Path(validate_path)
        if vp.is_file():
            try:
                val = json.loads(vp.read_text(encoding="utf-8"))
            except Exception:
                val = {}

    out = [
        f"# {slug} 验证真值表 (Python 确定性渲染)",
        "",
        f"- solution: `{src}`",
        f"- validation: `{validate_path or '-'}`",
        f"- generator: `orpath.agents.adaptive_graph.render_truth_tables` (0 LLM tokens)",
        "",
        "## 1. 解包膜 (Envelope)",
        "",
        "| 项目 | 值 |",
        "|---|---|",
        f"| problem_id | {sol.get('problem_id', '-')} |",
        f"| problem_class | {sol.get('problem_class', '-')} |",
        f"| status | {sol.get('status', '-')} |",
        f"| objective (声明值) | {_format_num(sol.get('objective'))} |",
        f"| recomputed_objective | {_format_num(val.get('recomputed_objective')) if val else _format_num(sol.get('objective'))} |",
        f"| proven_optimal | {bool((sol.get('meta') or {}).get('proven_optimal', sol.get('proven_optimal', False)))} |",
        f"| solver | {sol.get('solver', '-')} |",
        f"| solve_time_sec | {sol.get('solve_time_sec', '-')} |",
        "",
        "## 2. 独立重算校验 (Independent Recomputation)",
        "",
        "| 校验项 | ok | detail / expected |",
        "|---|---|---|",
    ]
    checks = val.get("checks") or []
    if checks:
        for c in checks:
            detail = c.get("detail") or ""
            if not detail and "expected" in c:
                detail = f"expected={c.get('expected')} got={c.get('got')}"
            out.append(f"| {c.get('name', '-')} | {c.get('ok')} | {str(detail)[:220].replace('|', '\\|') or '-'} |")
    else:
        out.append("| (no validation report present) | - | - |")
    out.append("")
    out.append(f"**validation ok:** {val.get('ok', '-')}；**errors:** {val.get('errors', '-')}")

    # domain breakdown
    out += ["", "## 3. 领域分解 (Domain Breakdown)", ""]
    routes = sol.get("routes") if isinstance(sol.get("routes"), list) else []
    if routes:
        out += ["| route | stops | distance | load | duration |", "|---|---|---|---|---|"]
        for r in routes:
            out.append(
                f"| {r.get('route_id', '-')} | {r.get('num_stops', len(r.get('visits') or []))} "
                f"| {_format_num(r.get('distance'))} | {_format_num(r.get('load'))} | {_format_num(r.get('duration'))} |"
            )
        out.append("")
    allocations = sol.get("allocations") if isinstance(sol.get("allocations"), dict) else None
    if allocations:
        out += ["| asset | weight |", "|---|---|"]
        for k, v in list(allocations.items())[:50]:
            out.append(f"| {k} | {_format_num(v)} |")
        out.append("")
    subs_raw = sol.get("subproblems")
    subs_rows: list[tuple[str, str, str]] = []
    if isinstance(subs_raw, dict):
        for q, v in subs_raw.items():
            if isinstance(v, dict):
                val = None
                for vk in (
                    "objective",
                    "value",
                    "total_cost",
                    "total",
                    "duration_s",
                    "total_duration_s",
                    "recomputed_duration_s",
                    "coverage",
                    "coverage_M1",
                    "cost",
                    "score",
                ):
                    if v.get(vk) is not None:
                        val = v.get(vk)
                        break
                if val is None:
                    for k2, v2 in v.items():
                        if k2 not in ("id", "name", "status") and isinstance(v2, (int, float)) and not isinstance(v2, bool):
                            val = v2
                            break
                subs_rows.append((str(q), _format_num(val), str(v.get("status", "-"))))
            else:
                subs_rows.append((str(q), _format_num(v), "-"))
    elif isinstance(subs_raw, list):
        for idx, item in enumerate(subs_raw):
            if not isinstance(item, dict):
                subs_rows.append((f"sub_{idx + 1}", _format_num(item), "-"))
                continue
            sid = str(item.get("id") or item.get("name") or f"sub_{idx + 1}")
            val = None
            for vk in ("objective", "total", "total_cost", "coverage_M1", "coverage", "value"):
                if item.get(vk) is not None:
                    val = item.get(vk)
                    break
            if val is None:
                for k, v in item.items():
                    if k not in ("id", "name", "status") and isinstance(v, (int, float)) and not isinstance(v, bool):
                        val = v
                        break
            subs_rows.append((sid, _format_num(val), str(item.get("status", "-"))))
    if subs_rows:
        out += ["| subproblem | objective | status |", "|---|---|---|"]
        for sid, val_str, st_str in subs_rows:
            out.append(f"| {sid} | {val_str} | {st_str} |")
        out.append("")
    if not (routes or allocations or subs_rows):
        out.append("(无领域分解数据；空真值表由确定性渲染器如实记录。)")

    # Section 3.5: Deep Evolution multi-round ledger if present (0 LLM)
    exp_p = root / "notes" / f"{slug}-experiments.json"
    if exp_p.is_file():
        try:
            from orpath.agents.evolution_ledger import format_ledger_summary

            exp_doc = json.loads(exp_p.read_text(encoding="utf-8"))
            if isinstance(exp_doc, dict) and (exp_doc.get("rounds") or []):
                out += ["", format_ledger_summary(exp_doc), ""]
        except Exception:
            pass

    # Section 4: deterministic knowledge & bibliography anchors (0 LLM)
    out += ["", "## 4. 知识库方法先验与真实文献锚点 (Verified Knowledge & Literature Anchors)", ""]
    ret_raw = str(state.get("retrieval_path") or "").strip()
    ret_file = Path(ret_raw) if ret_raw else (root / "notes" / f"{slug}-retrieval.json")
    ret_hits: list[dict[str, Any]] = []
    if ret_file.is_file():
        try:
            ret_doc = json.loads(ret_file.read_text(encoding="utf-8"))
            ret_hits = [h for h in (ret_doc.get("hits") or []) if isinstance(h, dict)]
        except Exception:
            ret_hits = []
    if ret_hits:
        out += ["| chunk_id | source_path | score |", "|---|---|---|"]
        for rh in ret_hits[:5]:
            out.append(
                f"| `{rh.get('chunk_id', '-')}` | `{rh.get('source_path', '-')}` | {_format_num(rh.get('score'))} |"
            )
        out.append("")

    lit_items: list[dict[str, Any]] = []
    try:
        from orpath.agents.knowledge_pack import match_top_literature

        pc_lit = str(sol.get("problem_class") or state.get("problem_class") or "")
        dom_lit = str(state.get("domain_cartridge") or "")
        lit_items = match_top_literature(pc_lit, dom_lit, topk=3)
    except Exception:
        lit_items = []
    if lit_items:
        for lit in lit_items:
            doi_part = f" (DOI: `{lit['doi']}`)" if lit.get("doi") else ""
            out.append(f"- **{lit['cite_label']}**: *{lit['title']}*, {lit['venue']}.{doi_part}")
    if not (ret_hits or lit_items):
        out.append("(无召回文献锚点；严禁编造外部引用。)")

    # Section 5: Dual-Track Tournament Comparison (only when tournament.json exists)
    tourn_raw = str(state.get("tournament_path") or "").strip()
    tourn_file = Path(tourn_raw) if tourn_raw else (root / "notes" / f"{slug}-tournament.json")
    if tourn_file.is_file():
        try:
            tdoc = json.loads(tourn_file.read_text(encoding="utf-8"))
        except Exception:
            tdoc = None
        if isinstance(tdoc, dict) and isinstance(tdoc.get("tracks"), dict):
            out += [
                "",
                "## 5. 双轨算法赛马实证对比 (Dual-Track Tournament Comparison)",
                "",
                f"- objective_sense: `{tdoc.get('objective_sense', 'min')}` | winning_track: `{tdoc.get('winner') or '-'}`",
                "",
                "| Track | Strategy | Solver | Status | Declared Objective | Recomputed Objective | Proven Optimal | Validator Gate | Tournament Result |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
            for tname in ("track_a", "track_b"):
                tr = (tdoc["tracks"] or {}).get(tname) or {}
                out.append(
                    f"| {tname} | {tr.get('strategy', '-')} | {tr.get('solver', '-')} | {tr.get('status', '-')} "
                    f"| {_format_num(tr.get('declared_objective'))} | {_format_num(tr.get('recomputed_objective'))} "
                    f"| {bool(tr.get('proven_optimal'))} | {tr.get('validation_ok')} | {tr.get('tournament_result', '-')} |"
                )

    text = "\n".join(out) + "\n"
    tables_path = (root / "outputs" / f"{slug}-tables.md").resolve()
    tables_path.write_text(text, encoding="utf-8")
    return {"tables_path": str(tables_path)}


REQUIRED_PAPER_KEYWORD_GROUPS: tuple[tuple[str, ...], ...] = (
    ("摘要",),
    ("假设",),
    ("数学规划模型",),
    ("求解策略",),
    ("敏感性",),
    ("局限性", "优缺点", "落地建议"),
)

_FAKE_CITE_RE = re.compile(r"\[FakeRef[^\]]*\]|\bFakeRef\b|\(\s*2099\s*\)|\[\s*[^\]]*2099[^\]]*\]", re.IGNORECASE)


def run_deterministic_doc_gate(state: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic closure gate for the writer artifact (0 LLM).

    Checks: paper exists; the six SOP chapters are all present (chapter-titled
    keywords, grouped with tolerant alternatives); declared objective value
    appears in the text (Numbers Truth binding); unproven-optimality papers
    must not claim 全局最优; fabricated placeholder citations are rejected;
    optional strict retrieval-anchor binding when require_knowledge_citations=True.
    """
    root = _resolve_root(state)
    slug = _slug(state, root)
    paper_raw = state.get("paper_path") or ""
    paper = Path(paper_raw) if paper_raw else (root / "papers" / f"{slug}.md")
    if not paper.is_file():
        return {"doc_gate_ok": False, "doc_gate_errors": [f"paper not found: {paper}"], "last_error": "paper not found"}
    text = paper.read_text(encoding="utf-8", errors="replace")
    if not text.strip() or _is_recursion_exhausted_text(text):
        return {
            "doc_gate_ok": False,
            "doc_gate_errors": ["paper is empty or contains recursion-limit fallback placeholder"],
            "last_error": "invalid paper content",
        }
    errors: list[str] = []
    for group in REQUIRED_PAPER_KEYWORD_GROUPS:
        if not any(kw in text for kw in group):
            errors.append(f"missing required section keywords: {'/'.join(group)}")
    objective = state.get("objective_value")
    if objective is not None:
        v = float(objective)
        candidates = {str(v), f"{v:.2f}", f"{v:.4f}", f"{v:.6f}", f"{v:.10g}"}
        if v == int(v):
            candidates.add(str(int(v)))
        if not any(c in text for c in candidates):
            errors.append(f"declared objective {v} not present in paper (Numbers Truth binding)")
    if not state.get("proven_optimal") and "全局最优" in text:
        errors.append("proven_optimal=False but paper claims 全局最优 (optimality honesty violation)")
    if _FAKE_CITE_RE.search(text):
        errors.append("fabricated citation placeholder detected in paper (伪造引用占位符)")
    if state.get("require_knowledge_citations"):
        ret_raw = str(state.get("retrieval_path") or "").strip()
        ret_file = Path(ret_raw) if ret_raw else (root / "notes" / f"{slug}-retrieval.json")
        anchors: set[str] = set()
        if ret_file.is_file():
            try:
                rdoc = json.loads(ret_file.read_text(encoding="utf-8"))
                for h in rdoc.get("hits") or []:
                    if not isinstance(h, dict):
                        continue
                    cid = str(h.get("chunk_id") or "").strip()
                    sp = str(h.get("source_path") or "").strip()
                    if cid:
                        anchors.add(cid)
                    if sp:
                        stem = Path(sp).stem
                        if len(stem) >= 4:
                            anchors.add(stem)
            except Exception:
                pass
        if anchors and not any(a in text for a in anchors):
            errors.append("missing verified knowledge/literature citation anchor from retrieval_path (缺少知识库真实文献锚点)")
    return {"doc_gate_ok": not errors, "doc_gate_errors": errors, "paper_path": str(paper.resolve())}


_FATAL_LINE_RE = re.compile(r"\[W\d+[)\]]\s*\**\s*FATAL|FATAL\s*[:：]|\*\*FATAL\*\*")
_NO_FATAL_RE = re.compile(r"(无|没有|未发现|未检出|未见)\s*FATAL|no FATAL|without FATAL")


def parse_review_reply(text: str) -> tuple[str, list[str]]:
    """Deterministically parse a reviewer reply: verdict + FATAL defects.

    Verdict resolution is strictly deterministic (no LLM): empty or
    recursion-exhausted replies force REVISE; any genuine FATAL defect line
    (``[W*] FATAL:`` / ``**FATAL**`` / ``FATAL:``, excluding "未发现 FATAL"
    disclaimers) forces REVISE; otherwise an explicit ``Verdict`` line wins
    (PASS > REVISE). MAJOR/MINOR-only replies without an explicit verdict are
    treated as PASS so the boilerplate "Revision Plan" heading cannot generate
    false REVISE verdicts.
    """
    if not text or not text.strip() or _is_recursion_exhausted_text(text):
        return "REVISE", ["FATAL: reviewer produced empty or recursion-exhausted response"]
    fatal_lines: list[str] = []
    for line in text.splitlines():
        if _NO_FATAL_RE.search(line):
            continue
        if _FATAL_LINE_RE.search(line):
            fatal_lines.append(line.strip().lstrip("-* ").strip()[:200])
    fatal_lines = fatal_lines[:5]
    verdict_line: str | None = None
    for line in text.splitlines():
        low = line.lower().lstrip("#* ").strip()
        if low.startswith("verdict"):
            verdict_line = line
            break
    if fatal_lines:
        verdict = "REVISE"
    elif verdict_line:
        up = verdict_line.upper()
        verdict = "PASS" if "PASS" in up else ("REVISE" if "REVISE" in up else ("PASS"))
    else:
        # No explicit Verdict line: a bare "REVISE 打回" reply without any
        # FATAL tag still counts as rejection (the boilerplate "Revision
        # Plan" heading does not contain the token "REVISE").
        verdict = "REVISE" if "REVISE" in text.upper() else "PASS"
    if verdict == "REVISE" and not fatal_lines:
        fatal_lines = ["reviewer requested REVISE without explicit FATAL tag"]
    return verdict, fatal_lines


# --------------------------------------------------------------------------- #
# Graph builder
# --------------------------------------------------------------------------- #
_EXPLICIT_SENSE_RE = re.compile(
    r"""(?:["']?objective_sense["']?|["']?sense["']?)\s*[:=]\s*["']?(min(?:imize|imise)?|max(?:imize|imise)?)["']?""",
    re.IGNORECASE,
)
_OBJ_MAX_CUE_RE = re.compile(
    r"(?:\bmaximize\b|\bmaximise\b|\bmaximization\b|\bmax\s*[_{(]|max_\{|最大化|尽可能长|尽可能大|尽可能多|尽可能高|有效.{0,8}时间.{0,8}长)",
    re.IGNORECASE,
)
_OBJ_MIN_CUE_RE = re.compile(
    r"(?:\bminimize\b|\bminimise\b|\bminimization\b|\bmin\s*[_{(]|min_\{|最小化|尽可能短|尽可能小|尽可能少|尽可能低|总(?:成本|费用|距离|耗时)最小)",
    re.IGNORECASE,
)
_KNOWN_MINIMIZATION_CLASSES = frozenset(
    {
        "shortest_path",
        "tsp",
        "cvrp",
        "vrptw",
        "jssp",
        "fjssp",
        "rcpsp",
        "binpack",
        "cflp",
        "facility_location",
        "hub_location",
        "lotsizing",
        "staff_rostering",
        "microgrid",
    }
)


def _normalize_sense_token(raw: Any) -> str | None:
    low = str(raw or "").strip().lower()
    if low in {"min", "minimize", "minimise"}:
        return "min"
    if low in {"max", "maximize", "maximise"}:
        return "max"
    return None


def _infer_objective_sense(
    state: Mapping[str, Any],
    root: Path,
    slug: str,
    candidate_docs: list[Mapping[str, Any]],
) -> str:
    """Deterministically infer optimization direction ('min' or 'max')."""
    if (s := _normalize_sense_token(state.get("objective_sense"))):
        return s

    sdoc: Mapping[str, Any] = {}
    schema_p = Path(str(state.get("schema_path") or (root / "outputs" / f"{slug}-schema.json")))
    if schema_p.is_file():
        try:
            loaded = json.loads(schema_p.read_text(encoding="utf-8"))
            if isinstance(loaded, Mapping):
                sdoc = loaded
        except Exception:
            sdoc = {}
    if (s := _normalize_sense_token(sdoc.get("objective_sense") or sdoc.get("sense"))):
        return s

    for doc in candidate_docs:
        meta = doc.get("meta") if isinstance(doc.get("meta"), Mapping) else {}
        if (s := _normalize_sense_token(doc.get("objective_sense") or doc.get("sense") or meta.get("objective_sense"))):
            return s

    pc = str(state.get("problem_class") or sdoc.get("problem_class") or "").strip().lower()
    if pc in _MAXIMIZATION_CLASSES:
        return "max"

    analyst_texts: list[str] = []
    for cand_ap in (
        Path(str(state.get("analyst_brief_path") or "")),
        Path(str(state.get("research_path") or "")),
        root / "notes" / f"{slug}-analyst.md",
    ):
        if cand_ap.name and cand_ap.is_file():
            try:
                analyst_texts.append(cand_ap.read_text(encoding="utf-8", errors="replace")[:12000])
                break
            except OSError:
                pass
    if state.get("analyst_summary"):
        analyst_texts.append(str(state.get("analyst_summary")))

    for atext in analyst_texts:
        m = _EXPLICIT_SENSE_RE.search(atext)
        if m and (s := _normalize_sense_token(m.group(1))):
            return s

    if pc in _KNOWN_MINIMIZATION_CLASSES:
        return "min"

    # Generic / custom / NLP classes: inspect objective text in schema, analyst report, and statement.
    cue_sources: list[str] = []
    for k in ("objective", "objective_description", "goal"):
        if sdoc.get(k):
            cue_sources.append(json.dumps(sdoc.get(k), ensure_ascii=False))
    cue_sources.extend(analyst_texts)
    if state.get("raw_problem_text"):
        cue_sources.append(str(state.get("raw_problem_text"))[:8000])
    pf = str(state.get("problem_file") or "").strip()
    if pf and Path(pf).is_file():
        try:
            cue_sources.append(Path(pf).read_text(encoding="utf-8", errors="replace")[:8000])
        except OSError:
            pass

    max_hits = 0
    min_hits = 0
    for blob in cue_sources:
        max_hits += len(_OBJ_MAX_CUE_RE.findall(blob))
        min_hits += len(_OBJ_MIN_CUE_RE.findall(blob))
    if max_hits > min_hits:
        return "max"
    return "min"


def build_adaptive_graph(
    model: Any = None,
    agents: Mapping[str, Any] | None = None,
    cartridge_tools: Any = None,
    domain_directive: str = "",
    max_retries: int = 3,
    tier_a_with_reviewer: bool = False,
    checkpointer: Any = None,
    race_tracks: int | None = None,
    compile_graph: bool = True,
) -> Any:
    """Compile the Tier-A/B/C adaptive state machine.

    Args:
        model: shared chat model for default agent construction.
        agents: optional per-name agent overrides
            (``{"or_analyst": ..., "or_modeler": ..., "or_writer": ...,
            "or_reviewer": ...}``) — test seams inject offline fake agents.
        cartridge_tools / domain_directive: DomainCartridge injection passed
            to the analyst / modeler factories.
        max_retries: strict bounce-back ceiling for modeler & writer loops.
        tier_a_with_reviewer: attach the reviewer after the Tier-A doc gate.
        checkpointer: optional LangGraph checkpointer.
        race_tracks: optional override for dual-track modeler horse-racing (2=dual, 1=single, None=auto).

    Returns:
        Compiled ``StateGraph`` over ``AdaptivePipelineState``.
    """
    using_default_agents = agents is None
    if using_default_agents:
        from orpath.control_plane import get_chat_model

        model = model if model is not None else get_chat_model()
        resolved_agents = _default_agents(model, cartridge_tools, domain_directive)
    else:
        resolved_agents = dict(agents or {})

    agent_map = {
        "analyst": resolved_agents.get("or_analyst"),
        "modeler": resolved_agents.get("or_modeler"),
        "writer": resolved_agents.get("or_writer"),
        "reviewer": resolved_agents.get("or_reviewer"),
    }
    for name, a in agent_map.items():
        if a is None:
            raise ValueError(f"agents['{name}'] (or_*) is required for the adaptive machine")

    dynamic_agent_cache: dict[tuple[str, str], Any] = {}

    def _get_role_agent(role_key: str, state: Mapping[str, Any], override_name: str = "") -> Any:
        if override_name and override_name in resolved_agents:
            return resolved_agents[override_name]
        if not using_default_agents:
            return agent_map[role_key]
        dom_key = str(state.get("domain_cartridge") or state.get("problem_class") or "").strip().lower()
        cache_key = (role_key, dom_key)
        if dom_key and dom_key != "general_or":
            if cache_key not in dynamic_agent_cache:
                dynamic_agent_cache[cache_key] = _build_dynamic_role_agent(
                    role_key,
                    model,
                    state,
                    base_cartridge_tools=cartridge_tools,
                    base_directive=domain_directive,
                )
            return dynamic_agent_cache[cache_key]
        return agent_map[role_key]

    common = {"max_retries": int(max_retries)}

    # --------------------------------------------------------------- nodes
    def node_preflight(state: AdaptivePipelineState) -> dict:
        updates = run_preflight_probe(state)
        root = _resolve_root({**dict(state), **updates})
        slug = _slug({**dict(state), **updates}, root)
        pc = str(updates.get("problem_class") or state.get("problem_class") or "").strip()
        pid = str(state.get("problem_id") or slug).strip()
        if not updates.get("lessons_path"):
            try:
                from orpath import process_memory as _pm

                _, md_path, _ = _pm.write_retrieve_artifacts(
                    root,
                    slug,
                    query=f"{pc} {pid}".strip() or slug,
                    problem_class=pc or None,
                )
                updates["lessons_path"] = str(md_path)
            except Exception:
                pass
        updates.setdefault("research_path", str(root / "notes" / f"{slug}-analyst.md"))
        return updates

    def node_analyst(state: AdaptivePipelineState) -> dict:
        root = _resolve_root(state)
        slug = _slug(state, root)
        brief = _brief(state, root, slug, [
            "职责: 题面精读 + 数据画像核对 + 领域规约确认 + 数学分类与 Tier 分档 (严禁求解/猜解)。",
            "效率纪律: 简报已附数据探针摘要与题面摘录，严禁调用 `list_files('.')` 或 `read_file` 重读 `profile.json`！仅在缺失参数时调用 `profile_<domain>_data(problem_id=slug)` 或 `read_problem_file(..., max_chars=2500)`（合计 ≤1 次工具调用），随后直接输出精简结构化 JSON 工程规格。",
            "优化方向要求: 必须在 JSON 中显式输出 `\"objective_sense\": \"max\"` 或 `\"min\"`（最大化目标填 `\"max\"`，最小化目标填 `\"min\"`）。",
            "分问拆解约束: 仅当题目确属必须跨批继承动态物理状态的序贯规划 (排除 microgrid_dispatch / tube_cut / 可在同一套 Python 脚本内共核求解的多问赛题如几何轨迹/规划), 才在末尾另起一行输出 SUBPROBLEMS=[\"q1\",\"q2\",...]；常规多问建模题请勿输出 SUBPROBLEMS, 交由后续 modeler 统一编写一体化求解器闭环完成。",
            "输出: 结构化分析结论, 交 modeler 承接。",
        ])
        try:
            text, _msgs = _invoke_with_trace(
                _get_role_agent("analyst", state),
                brief,
                root,
                slug,
                "analyst",
                wall_timeout_s=360.0,
            )
        except TimeoutError as exc:
            text = f"# analyst interrupted ({exc})\n"
        (root / "notes").mkdir(parents=True, exist_ok=True)
        analyst_p = root / "notes" / f"{slug}-analyst.md"
        analyst_p.write_text(text, encoding="utf-8")

        subs = list(state.get("subproblems") or [])
        if not subs and text:
            m_sub = re.search(r"SUBPROBLEMS\s*=\s*(\[[^\]]+\])", text)
            if m_sub:
                try:
                    parsed_subs = json.loads(m_sub.group(1))
                    if isinstance(parsed_subs, list) and len(parsed_subs) > 1:
                        subs = [str(x).strip() for x in parsed_subs if str(x).strip()]
                except Exception:
                    pass

        merged_state = {**state, **common, "subproblems": subs, "analyst_brief_path": str(analyst_p)}
        inferred_sense = _infer_objective_sense(merged_state, root, slug, [])
        out: dict[str, Any] = {
            "analyst_summary": text[:2000],
            "analyst_brief_path": str(analyst_p),
            "research_path": str(analyst_p),
            "objective_sense": inferred_sense,
            "tier": decide_tier(merged_state),
        }
        if subs:
            out["subproblems"] = subs
        return out

    def _maybe_run_fenced_scripts(
        text: str,
        root: Path,
        slug: str,
        sol_target: Path,
        timeout_budget_s: int,
    ) -> bool:
        """Extract ```python blocks, AST-check syntax, write to disk, and run if needed."""
        try:
            from orpath.agents.evolution_ledger import (
                MAX_SCRIPT_TIMEOUT_SEC,
                extract_and_write_fenced_code,
            )
        except Exception:
            return False

        default_rel = f"outputs/{slug}-custom_solver.py"
        pre_mtime = sol_target.stat().st_mtime if sol_target.is_file() else 0.0
        extracted = extract_and_write_fenced_code(root, text, default_rel_path=default_rel)
        written_py = [item for item in extracted if item.get("ok") and str(item.get("path", "")).endswith(".py")]
        if not written_py:
            return False

        import subprocess as _sp
        import sys as _sys

        cap_to = min(MAX_SCRIPT_TIMEOUT_SEC, max(30, int(timeout_budget_s)))
        env = dict(os.environ)
        env["ORPATH_WORKDIR"] = str(root)
        ran_any = False

        # Execute solver script(s) first (non-validator), then validator script(s)
        solver_paths = [
            Path(item["abs_path"])
            for item in written_py
            if "validate" not in str(item["path"]).lower()
        ]
        val_paths = [
            Path(item["abs_path"])
            for item in written_py
            if "validate" in str(item["path"]).lower()
        ]
        if not val_paths:
            cand_val = root / "outputs" / f"{slug}-custom-validate.py"
            if cand_val.is_file():
                val_paths.append(cand_val)

        canonical_sol = root / "outputs" / f"{slug}-solution.json"
        for sp_py in solver_paths:
            if not sp_py.is_file():
                continue
            try:
                _sp.run(
                    [_sys.executable, str(sp_py)],
                    cwd=str(root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=cap_to,
                )
                ran_any = True
            except Exception:
                pass
        if not sol_target.is_file() and canonical_sol.is_file() and sol_target != canonical_sol:
            try:
                shutil.copy2(canonical_sol, sol_target)
            except OSError:
                pass
        for vp_py in val_paths:
            if not vp_py.is_file():
                continue
            try:
                _sp.run(
                    [_sys.executable, str(vp_py)],
                    cwd=str(root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=min(120, cap_to),
                )
                ran_any = True
            except Exception:
                pass
        post_mtime = sol_target.stat().st_mtime if sol_target.is_file() else 0.0
        return bool(ran_any and (post_mtime > pre_mtime or sol_target.is_file()))

    def _salvage_disk_scripts(root: Path, slug: str, sol_target: Path, timeout_budget_s: int) -> bool:
        """Run existing outputs/<slug>-custom_solver.py + validator if modeler stalled mid-loop."""
        import subprocess as _sp
        import sys as _sys

        sp = root / "outputs" / f"{slug}-custom_solver.py"
        vp = root / "outputs" / f"{slug}-custom-validate.py"
        if not sp.is_file():
            return False
        cap_to = min(600, max(30, int(timeout_budget_s)))
        env = dict(os.environ)
        env["ORPATH_WORKDIR"] = str(root)
        try:
            _sp.run([_sys.executable, str(sp)], cwd=str(root), env=env, capture_output=True, text=True, timeout=cap_to)
        except Exception:
            pass
        canonical_sol = root / "outputs" / f"{slug}-solution.json"
        if not sol_target.is_file() and canonical_sol.is_file() and sol_target != canonical_sol:
            try:
                shutil.copy2(canonical_sol, sol_target)
            except OSError:
                pass
        if vp.is_file():
            try:
                _sp.run([_sys.executable, str(vp)], cwd=str(root), env=env, capture_output=True, text=True, timeout=min(120, cap_to))
            except Exception:
                pass
        return sol_target.is_file()

    def _run_modeler_track(
        agent_obj: Any,
        base_brief: str,
        root: Path,
        slug: str,
        stage_name: str,
        sol_target: Path,
        schema_path: Path,
        *,
        enforce_cosplay: bool,
        timeout_budget_s: int = 180,
        max_rec_limit: int = 20,
    ) -> tuple[str, list[str]]:
        max_cosplay_retries = 2 if enforce_cosplay else 0
        quarantined_all: list[str] = []
        brief_cur = base_brief
        last_text = ""
        invoke_wall = min(1500.0, max(900.0, float(timeout_budget_s) + 600.0))
        timeout_retries_used = 0
        for attempt_idx in range(max_cosplay_retries + 1):
            pre_mtime = sol_target.stat().st_mtime if sol_target.is_file() else 0.0
            msgs: list[Any] = []
            try:
                last_text, msgs = _invoke_with_trace(
                    agent_obj,
                    brief_cur,
                    root,
                    slug,
                    stage_name,
                    wall_timeout_s=invoke_wall,
                    max_rec_limit=max_rec_limit,
                )
            except Exception as exc:
                err_name = type(exc).__name__.lower()
                err_msg = str(exc).lower()
                recoverable = (
                    "timeout" in err_name
                    or "timeout" in err_msg
                    or "recursion" in err_name
                    or "recursion" in err_msg
                )
                if not recoverable:
                    raise
                last_text = f"modeler stage interrupted ({type(exc).__name__}: {exc})"
                salvaged = _salvage_disk_scripts(root, slug, sol_target, timeout_budget_s)
                if salvaged:
                    return last_text + " [salvaged disk solver]", quarantined_all
                if attempt_idx < max_cosplay_retries and timeout_retries_used < 1:
                    timeout_retries_used += 1
                    brief_cur = (
                        f"RETRY (previous attempt stalled/hit step limit: {type(exc).__name__}): "
                        f"SKIP all exploration! Do NOT call list_files/read_file/grep_search/execute_python_sandbox. "
                        f"Immediately write concise `outputs/{slug}-custom_solver.py` + `outputs/{slug}-custom-validate.py` "
                        f"via `write_custom_solver_script`, run both with `execute_custom_script`, then call `validate_solution_tool`.\n\n"
                        + base_brief
                    )
                    continue
                return last_text, quarantined_all
            post_mtime = sol_target.stat().st_mtime if sol_target.is_file() else 0.0
            fenced_executed = False
            if post_mtime <= pre_mtime:
                fenced_executed = _maybe_run_fenced_scripts(
                    last_text, root, slug, sol_target, timeout_budget_s
                )
            if not sol_target.is_file():
                _salvage_disk_scripts(root, slug, sol_target, timeout_budget_s)
            if _is_recursion_exhausted_text(last_text):
                if sol_target.is_file():
                    last_text = _summarize_salvaged_solution(sol_target)
                elif attempt_idx < max_cosplay_retries and timeout_retries_used < 1:
                    timeout_retries_used += 1
                    brief_cur = (
                        f"RETRY (previous attempt exhausted step limit without writing solution): "
                        f"SKIP all exploration! Do NOT call list_files/read_file/grep_search/execute_python_sandbox. "
                        f"Immediately write concise `outputs/{slug}-custom_solver.py` + `outputs/{slug}-custom-validate.py` "
                        f"via `write_custom_solver_script`, run both with `execute_custom_script`, then call `validate_solution_tool`.\n\n"
                        + base_brief
                    )
                    continue
                else:
                    last_text = "modeler exhausted step limit without producing a solution artifact"
            hit, reason, q_files = _check_and_quarantine_cosplay(
                msgs,
                sol_target,
                schema_path,
                enforce=enforce_cosplay,
                fenced_executed=fenced_executed,
            )
            quarantined_all.extend(q_files)
            if not hit:
                return last_text, quarantined_all
            if attempt_idx < max_cosplay_retries:
                brief_cur = (
                    f"RETRY {attempt_idx + 1}/{max_cosplay_retries}: Previous output was quarantined to "
                    f".cosplay-quarantine ({reason}). You MUST call real solver/script tools "
                    f"(execute_or_solver / write_custom_solver_script / execute_custom_script / run_shell) "
                    f"or emit `# file: outputs/{slug}-custom_solver.py` and write ONLY structural formulation fields "
                    f"(never objective/tour/routes/path/optimal) into {schema_path}.\n\n{base_brief}"
                )
        return last_text, quarantined_all

    def node_modeler(state: AdaptivePipelineState) -> dict:
        import time as _time
        from orpath.agents.evolution_ledger import (
            MAX_DEEP_ROUNDS,
            MAX_SCRIPT_TIMEOUT_SEC,
            best_solver_path,
            format_ledger_summary,
            get_stage_directive,
            load_ledger,
            normalize_target_rounds,
            round_timeout_budget,
        )

        root = _resolve_root(state)
        slug = _slug(state, root)
        (root / "outputs").mkdir(parents=True, exist_ok=True)
        (root / "notes").mkdir(parents=True, exist_ok=True)

        tier = decide_tier({**state, **common})
        domain = str(state.get("domain_cartridge") or "")
        pc_low = str(state.get("problem_class") or "").strip().lower()
        general_or = (
            domain in {"", "general_or", "nlp"}
            or pc_low in {"custom_mip", "custom", "general_optimization", "custom_reduced", "nlp_minlp", "interval_coverage", "general_or"}
        )
        schema_path = Path(str(state.get("schema_path") or (root / "outputs" / f"{slug}-schema.json")))
        canonical_sol = root / "outputs" / f"{slug}-solution.json"

        evo_enabled = bool(state.get("deep_evolution")) or normalize_target_rounds(state.get("evo_target_rounds"), default=1) > 1
        evo_target = normalize_target_rounds(state.get("evo_target_rounds"), default=5 if state.get("deep_evolution") else 1)
        evo_max = min(MAX_DEEP_ROUNDS, max(evo_target, int(state.get("evo_max_rounds") or MAX_DEEP_ROUNDS)))
        prev_round = int(state.get("evo_round") or 0)
        cur_round = prev_round + 1
        stage_code, stage_directive = get_stage_directive(cur_round)
        budget_s = round_timeout_budget(cur_round, max_cap=MAX_SCRIPT_TIMEOUT_SEC) if evo_enabled else 180
        round_started = _time.monotonic()

        custom_solver_p = root / "outputs" / f"{slug}-custom_solver.py"
        inc_solver_p = best_solver_path(root, slug)
        if cur_round >= 2 and inc_solver_p.is_file():
            try:
                shutil.copy2(inc_solver_p, custom_solver_p)
            except OSError:
                pass

        enforce_cosplay = bool(
            state.get("enforce_anti_cosplay")
            if state.get("enforce_anti_cosplay") is not None
            else using_default_agents
        )
        use_horse_race = bool(
            (state.get("enable_horse_race") and not (evo_enabled and cur_round >= 2))
            or race_tracks == 2
            or ("or_modeler_track_a" in resolved_agents or "or_modeler_track_b" in resolved_agents)
        )

        inbox_dir = root / "inbox" / slug
        inbox_files = (
            sorted(p.relative_to(root).as_posix() for p in inbox_dir.rglob("*") if p.is_file())[:12]
            if inbox_dir.is_dir()
            else []
        )

        has_existing_custom = bool(cur_round >= 2 and custom_solver_p.is_file())
        extra_lines: list[str] = [
            (
                f"增量修复启动: 第 {cur_round} 轮已有 `outputs/{slug}-custom_solver.py`；**严禁再重复 read_file research/knowledge_pack 或调用 `list_files('.')`**，仅按下方报错精确定位片段 `edit_file` 后立即跑通！"
                if has_existing_custom
                else (
                    f"输入文件清单(已定位): {inbox_files}；请先仅 read_file 本题研究报告 `{state.get('research_path') or f'notes/{slug}-analyst.md'}`，严禁调用 `list_files('.')` / `grep_search` 翻查无关目录或 `tools/` 源码。"
                    if inbox_files
                    else "先验参考: 仅在必要时查阅 research_path / knowledge_pack_path；简报已附题面摘要与数据路径，严禁反复调用 list_files('.')。"
                )
            ),
            *(
                [
                    f"效率纪律: 本题已匹配领域算子 ({pc_low or domain})，请构建结构化 schema.json 并优先调用 execute_or_solver 与 validate_solution_tool 闭环真算。"
                    + (
                        " 若为 polyomino_cover 多轮深化，可传入 extra_args='--hint-solution outputs/" + f"{slug}-best_solution.json --lns-window 12 --symmetry-break --time-limit-s {budget_s}'。"
                        if pc_low == "polyomino_cover" and cur_round >= 2 and (root / "outputs" / f"{slug}-best_solution.json").is_file()
                        else ""
                    )
                ]
                if not general_or
                else []
            ),
        ]
        if evo_enabled:
            sense = _infer_objective_sense(state, root, slug, [])
            ledger = load_ledger(root, slug, minimize=(sense != "max"), target_rounds=evo_target, max_rounds=evo_max)
            extra_lines.append(
                f"🚀 Deep 自主进化第 {cur_round}/{evo_target} 轮 (上限 {evo_max} 轮, 本轮脚本最长 {budget_s}s): "
                f"[{stage_code}] {stage_directive}"
            )
            if cur_round >= 2 and (ledger.get("rounds") or []):
                extra_lines.append(format_ledger_summary(ledger))
                inc_doc = ledger.get("incumbent") if isinstance(ledger.get("incumbent"), dict) else {}
                inc_val = inc_doc.get("objective")
                if sense == "max" and isinstance(inc_val, (int, float)) and abs(float(inc_val)) <= 1e-9:
                    extra_lines.append(
                        "🚨 警告: 上轮最大化目标仍停留在 0.0 退化平凡解！本轮必须先逐行核对题面坐标符号、航向角约定、离散网格步长与碰撞/遮蔽条件，并先用域内解析可行点验算得严格 > 0 的基线目标后，再启动局部或混合寻优。"
                    )
                if custom_solver_p.is_file():
                    extra_lines.append(
                        f"增量改进纪律: 当前快照已恢复到 outputs/{slug}-custom_solver.py；优先修复仍为 0.0 或未满足多主体约束的子问（用域内解析初值/低维分解替代盲目高维随机盒；多载体循环必须参数化 `for agent_id in allowed_agents:` 严禁硬编码单一载体 ID；同一载体跨目标须共享一致物理状态、累计产能/弹数上限与冷却间隔），"
                        f"直接 read_file 相关片段后用 edit_file 做几十行局部升级（禁止另写多余 probe 脚本或从头全量重写；若上轮 custom-validate.py 报错或离散网格步长不一致须同步对齐），"
                        f"然后迅速执行 solver -> validate -> validate_solution_tool（≤8 步内收尾）。"
                    )
        if state.get("remediation_path"):
            rem_digest = ""
            rem_file = Path(str(state.get("remediation_path")))
            if not rem_file.is_absolute():
                rem_file = root / rem_file
            if rem_file.is_file():
                try:
                    rem_digest = rem_file.read_text(encoding="utf-8", errors="replace")[:1100].strip()
                except OSError:
                    rem_digest = ""
            extra_lines.append(
                f"⚠️ 上轮独立验证器打回修复指令 (remediation_path={state.get('remediation_path')}): "
                f"{'; '.join(str(x) for x in (state.get('validator_errors') or [])[:4])}"
                + (f"\n--- 靶向修复摘要 ---\n{rem_digest}" if rem_digest else "")
            )
        if general_or:
            extra_lines.extend([
                "装备包: 三阶段物理离散规约 + 通用数学规划内核 (tools.or_kernels) 闭环协议:",
                f"  ① 严禁反复 read_file/grep_search 翻源码，严禁在 execute_python_sandbox 里跑计算或调试！务必精简代码（`custom_solver.py` ≤220行、`custom-validate.py` ≤120行），每次工具调用只写 1 个文件。**多问全覆与多目标覆盖律：若题面包含多个子问题（如 Q1..QK），`custom_solver.py` 与 `custom-validate.py` 必须逐一求解并独立验算全部子问，严禁遗漏任一子问，并在 `build_custom_envelope(..., subproblems={{...}})` 中完整记录各子问客观数值与附件交付文件；若包含多个服务对象/目标，Stage 1 必须为每个目标单独生成可达锚点候选列（严禁只围绕单一目标采样导致其余目标零覆盖）！** 对耦合多实体/多目标组合连续混合题，严禁把 >12 维变量直接塞进盲目 DE：应先 Stage 1 (NumPy 物理前向离散建列) -> Stage 2 (CP-SAT/HiGHS MILP 精确求组合骨架与上界) -> Stage 3 (`solve_multistart_polish` / 低维 `solve_box_nlp` 局部抛光)，全脚本控制在 {max(45, int(budget_s * 0.85))}s 内完成，多子问按比例分配 `time_limit_s`（所有子问 `time_limit_s` 之和 ≤ {max(30, int(budget_s * 0.65))}s）:",
                "     - `tools.or_kernels.milp_reduction`: `solve_general_milp(c, *, A_ub=None, b_ub=None, A_eq=None, b_eq=None, bounds=None, integrality=None, maximize=False, time_limit_s=30.0)` / `solve_budgeted_coverage_milp(item_coverages, *, universe_weights=None, item_costs=None, max_items=None, budget=None, cover_all=False, regime_groups=None, conflicts=())` / `solve_assignment_milp(...)`",
                "     - `tools.or_kernels.lns_hybrid`: `select_max_union_subset(intervals_by_item=None, *, target_intervals_by_item=None, target_weights=None, max_items=None, group_caps=None, regime_groups=None, conflicts=(), item_times=None, min_separation=0.0, warm_start=(), time_limit_s=30.0)` -> 返回 `{'selected', 'selected_regimes', 'union_length', 'union_by_target', 'proven_optimal'}`（原生支持多目标独立时间轴、同载体单一工况互斥 `regime_groups={carrier: {reg: (items, cap)}}` 与 `min_separation` 冷却间隔！）",
                "     - `tools.or_kernels.nlp_minlp`: `solve_box_nlp(obj_fn, bounds, *, maximize=False, constraints=(), n_lhs=96, global_method='de', popsize=12, maxiter=120, n_local_starts=5, time_limit_s=..., initial_points=())` -> 返回 `{'x', 'objective', 'feasible', 'ok'}`（键名是 `'objective'` 非 `'fun'`；**注意约束遵循 SciPy SLSQP 口径：可行域为 `c(x) >= 0`，切勿写反符号！**）；Stage 3 精修用 `solve_multistart_polish(obj_fn, bounds, initial_points, *, maximize=False, constraints=(), time_limit_s=10.0)`",
                "     - `tools.or_kernels.interval_coverage`: `canonical_time_grid(t_max, dt)` / `eval_projectile_detonation(origin_t0, speed, direction_xy, release_time, det_delay, g=9.8)` (其中 `origin_t0` 必须是载体 `t=0` 初始坐标，严禁提前加上 `v*release_time` 再传入导致双重位移!) -> 前向运动学强制保证 **`det_time == release_time + det_delay`** 与单位航向（严禁 clamp `release_time=max(0,...)` 却不更新 `det_time`!）；`sample_cylinder_surface(...)` / `eval_smoke_masking_intervals(...)` -> **通用离散与仿真一致律：solver 终算与 custom-validate 必须使用完全相同的时间/空间步长 `dt`、采样密度与固定随机种子**",
                f"     - `from tools.or_kernels.envelope_io import build_custom_envelope, write_solution_and_report` -> `env = build_custom_envelope(problem_id=..., slug=..., problem_class=..., objective=..., solver_name=..., source_script=..., validator_script=..., validation_report='outputs/{slug}-custom-validate.json', decision_payload=..., proven_optimal=False, subproblems=..., wall_time_s=...); write_solution_and_report('outputs/{slug}-solution.json', env)` -> **⚠️ `build_custom_envelope` 只返回 dict 不写磁盘，必须调用 `write_solution_and_report` 落盘！必填非空 `validation_report`（严禁传 `\"\"`）**；生成的 JSON 把 `decision_payload` 存在顶层键 **`\"solution\"`**（不是 `\"decision_payload\"`!；可选调用 `get_problem_formulation_template`）",
                f"  ② 依次写入：`outputs/{slug}-schema.json`（含 `\"objective_sense\": \"max\"|\"min\"`，仅结构不含解）-> `outputs/{slug}-custom_solver.py`（写入 `outputs/{slug}-solution.json`）-> `outputs/{slug}-custom-validate.py`；",
                f"  ③ 物理隔离校验脚本 `outputs/{slug}-custom-validate.py` **必须无命令行参数可直接运行**（读 `outputs/{slug}-solution.json`，取 `pl = env.get('solution') or {{}}` 匹配 solver 写入键名，写 `outputs/{slug}-custom-validate.json` `{{\"ok\": bool, \"objective\": float, \"checks\": [...]}}`），采用与 solver 一致的 `canonical_time_grid` 重算物理与区间并集，严禁导入 scipy.optimize / ortools / highspy / pulp / custom_solver / nlp_minlp / lns_hybrid / milp_reduction；",
                f"  ④ 闭环运行：依次调 `execute_custom_script('outputs/{slug}-custom_solver.py', timeout_sec={budget_s})` -> `execute_custom_script('outputs/{slug}-custom-validate.py', timeout_sec=60)` -> `validate_solution_tool`；校验通过后直接用 1 句话总结本轮算法假设与目标值，报错则用 `edit_file` 修补失败行，禁止改用 execute_python_sandbox。",
                "严禁: 不得宣称 proven_optimal=True 除非精确求解器返回 OPTIMAL 且 Gap=0; 不得抄写上游对话。",
            ])

        quarantined_files: list[str] = list(state.get("cosplay_quarantined") or [])
        retry_next = int(state.get("model_retry_count") or 0) + 1

        if not use_horse_race:
            if evo_enabled and cur_round >= 2 and (root / "outputs" / f"{slug}-best_solution.json").is_file():
                if canonical_sol.is_file():
                    try:
                        canonical_sol.unlink()
                    except OSError:
                        pass
            if tier == "A":
                focus = (
                    "求解模式: 精确求解 (成熟算子 exact)。使用 CP-SAT/HiGHS/NetworkX 等，"
                    "将可独立校验的解工件写入 SOLUTION_PATH="
                    + str(canonical_sol)
                    + " (schema 先行，proven_optimal 如实标记)。"
                )
            else:
                focus = (
                    "求解模式: 下界 + 搜索 (bound + search)。先求精确界/松弛下界再做启发式搜索，"
                    "将可独立校验的解工件写入 SOLUTION_PATH="
                    + str(canonical_sol)
                    + " (status=FEASIBLE 时如实报告 gap，严禁声称全局最优)。"
                )
            brief = _brief(state, root, slug, [
                "职责: 构建 schema.json、调用已注册求解器或编写受控沙箱求解脚本、产出真实解工件。",
                focus,
                "完成: 将可独立校验的解工件写入指定路径，回复仅给一句结果摘要+工件路径。",
                *extra_lines,
            ])
            text, q_files = _run_modeler_track(
                _get_role_agent("modeler", state),
                brief,
                root,
                slug,
                "modeler",
                canonical_sol,
                schema_path,
                enforce_cosplay=enforce_cosplay,
                timeout_budget_s=budget_s,
                max_rec_limit=30 if cur_round == 1 else 24,
            )
            quarantined_files.extend(q_files)
            (root / "notes" / f"{slug}-modeler.md").write_text(text, encoding="utf-8")
            ok = canonical_sol.is_file()
            return {
                "modeler_summary": text[:2000],
                "schema_path": str(schema_path) if schema_path.is_file() else str(state.get("schema_path") or ""),
                "solution_path": str(canonical_sol) if ok else "",
                "cosplay_quarantined": quarantined_files,
                "model_retry_count": retry_next,
                "model_attempts": retry_next,
                "evo_round": cur_round,
                "evo_target_rounds": evo_target,
                "evo_max_rounds": evo_max,
                "last_error": "" if ok else "modeler produced no solution artifact",
            }

        # Dual-Track Modeler Horse-Racing (Track A: Exact/Reduction vs Track B: Bound+Heuristic/Search)
        track_a_sol = root / "outputs" / f"{slug}-track_a-solution.json"
        track_b_sol = root / "outputs" / f"{slug}-track_b-solution.json"
        for stale in (track_a_sol, track_b_sol, canonical_sol):
            if stale.is_file():
                try:
                    stale.unlink()
                except OSError:
                    pass

        brief_a = _brief(state, root, slug, [
            "TRACK=track_a (双轨赛马 · 精确建模/数学规约轨 Exact / Reduction Track):",
            "职责: 构建不含解字段的纯结构化 schema.json；优先采用精确 MILP/LP/CP-SAT/SciPy-MILP 或数学规约映射到 27 求解器求解。",
            f"写入候选解工件: SOLUTION_PATH={track_a_sol} (如实标记 proven_optimal 与 solver)。",
            "完成: 仅回复一句 Track A 结果摘要与解路径。",
            *extra_lines,
        ])
        agent_a = _get_role_agent("modeler", state, override_name="or_modeler_track_a")
        text_a, q_a = _run_modeler_track(
            agent_a,
            brief_a,
            root,
            slug,
            "modeler_track_a",
            track_a_sol,
            schema_path,
            enforce_cosplay=enforce_cosplay,
        )
        quarantined_files.extend(q_a)
        if not track_a_sol.is_file() and canonical_sol.is_file():
            try:
                canonical_sol.replace(track_a_sol)
            except OSError:
                pass
        if canonical_sol.is_file():
            try:
                canonical_sol.unlink()
            except OSError:
                pass

        brief_b = _brief(state, root, slug, [
            "TRACK=track_b (双轨赛马 · 松弛界+启发式搜索/分解轨 Bound + Heuristic Track):",
            "职责: 求取松弛下界/上界，并采用独立启发式、邻域搜索、拉格朗日松弛或自定义分解算法独立求解（用于与 Track A 赛马交叉验证）。",
            f"写入候选解工件: SOLUTION_PATH={track_b_sol} (若为启发式/限时搜索，必须设置 proven_optimal=false, status='FEASIBLE')。",
            "完成: 仅回复一句 Track B 结果摘要与解路径。",
            *extra_lines,
        ])
        agent_b = _get_role_agent("modeler", state, override_name="or_modeler_track_b")
        text_b, q_b = _run_modeler_track(
            agent_b,
            brief_b,
            root,
            slug,
            "modeler_track_b",
            track_b_sol,
            schema_path,
            enforce_cosplay=enforce_cosplay,
        )
        quarantined_files.extend(q_b)
        if not track_b_sol.is_file() and canonical_sol.is_file():
            try:
                canonical_sol.replace(track_b_sol)
            except OSError:
                pass

        combined_summary = f"[Track A]\n{text_a}\n\n[Track B]\n{text_b}"
        (root / "notes" / f"{slug}-modeler.md").write_text(combined_summary, encoding="utf-8")

        first_candidate = ""
        if track_a_sol.is_file():
            first_candidate = str(track_a_sol)
        elif track_b_sol.is_file():
            first_candidate = str(track_b_sol)
        elif canonical_sol.is_file():
            first_candidate = str(canonical_sol)

        return {
            "modeler_summary": combined_summary[:2000],
            "schema_path": str(schema_path) if schema_path.is_file() else str(state.get("schema_path") or ""),
            "track_a_solution_path": str(track_a_sol) if track_a_sol.is_file() else "",
            "track_b_solution_path": str(track_b_sol) if track_b_sol.is_file() else "",
            "solution_path": first_candidate,
            "cosplay_quarantined": quarantined_files,
            "model_retry_count": retry_next,
            "model_attempts": retry_next,
            "evo_round": cur_round,
            "evo_target_rounds": evo_target,
            "evo_max_rounds": evo_max,
            "last_error": "" if first_candidate else "both dual-track modelers produced no solution artifact",
        }

    def _record_evo_round(
        state: Mapping[str, Any],
        root: Path,
        slug: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        from orpath.agents.evolution_ledger import (
            MAX_SCRIPT_TIMEOUT_SEC,
            best_solution_path,
            get_stage_directive,
            ledger_path,
            normalize_target_rounds,
            record_experiment,
            round_timeout_budget,
        )

        evo_enabled = bool(state.get("deep_evolution")) or normalize_target_rounds(state.get("evo_target_rounds"), default=1) > 1
        if not evo_enabled:
            return updates
        cur_r = max(1, int(state.get("evo_round") or 1))
        t_r = normalize_target_rounds(state.get("evo_target_rounds"), default=5)
        stage_code, _ = get_stage_directive(cur_r)
        sol_p_raw = str(updates.get("solution_path") or state.get("solution_path") or "").strip()
        sol_p = Path(sol_p_raw) if sol_p_raw else (root / "outputs" / f"{slug}-solution.json")
        cdocs: list[Mapping[str, Any]] = []
        wall_t = 0.0
        if sol_p.is_file():
            try:
                cdoc = json.loads(sol_p.read_text(encoding="utf-8"))
                if isinstance(cdoc, dict):
                    cdocs.append(cdoc)
                    wall_t = float((cdoc.get("meta") or {}).get("wall_time_s") or cdoc.get("solve_time_sec") or 0.0)
            except Exception:
                pass
        sense = str(updates.get("objective_sense") or _infer_objective_sense(state, root, slug, cdocs))
        obj_v = updates.get("recomputed_objective")
        if obj_v is None:
            obj_v = updates.get("objective_value")
        obj_f = float(obj_v) if isinstance(obj_v, (int, float)) and not isinstance(obj_v, bool) else None
        val_ok = bool(updates.get("validation_ok") and obj_f is not None)
        solver_script = root / "outputs" / f"{slug}-custom_solver.py"
        gap_raw = updates.get("optimality_gap")
        gap_f = float(gap_raw) if isinstance(gap_raw, (int, float)) and not isinstance(gap_raw, bool) else None
        rec_res = record_experiment(
            root,
            slug,
            round_idx=cur_r,
            strategy_stage=stage_code,
            hypothesis=_sanitize_hypothesis(
                updates.get("modeler_summary") or state.get("modeler_summary"),
                sol_p,
                round_idx=cur_r,
            ),
            timeout_budget_s=round_timeout_budget(cur_r, max_cap=MAX_SCRIPT_TIMEOUT_SEC),
            wall_time_s=wall_t,
            objective=obj_f,
            best_bound=None,
            gap=gap_f,
            proven_optimal=bool(updates.get("proven_optimal")),
            validation_ok=val_ok,
            minimize=(sense != "max"),
            target_rounds=t_r,
            solver_script=solver_script if solver_script.is_file() else None,
            solution_path=sol_p if val_ok and sol_p.is_file() else None,
            error_summary="; ".join(str(x) for x in (updates.get("validator_errors") or [])[:2]),
        )
        inc = (rec_res.get("ledger") or {}).get("incumbent") or {}
        b_sol = best_solution_path(root, slug)
        updates["evo_promoted"] = bool(rec_res.get("promoted"))
        updates["incumbent_objective"] = inc.get("objective")
        updates["incumbent_available"] = bool(b_sol.is_file())
        updates["evolution_ledger_path"] = str(ledger_path(root, slug))
        return updates

    def node_validator(state: AdaptivePipelineState) -> dict:
        root = _resolve_root(state)
        slug = _slug(state, root)
        (root / "outputs").mkdir(parents=True, exist_ok=True)
        (root / "notes").mkdir(parents=True, exist_ok=True)

        track_a_raw = str(state.get("track_a_solution_path") or "").strip()
        track_b_raw = str(state.get("track_b_solution_path") or "").strip()

        if not track_a_raw and not track_b_raw:
            updates = run_deterministic_validator(state)
            if updates.get("validation_ok"):
                val_src = Path(str(updates.get("validate_path") or (root / "outputs" / f"{slug}-validation.json")))
                val_alias = root / "outputs" / f"{slug}-validate.json"
                if val_src.is_file() and val_src.resolve() != val_alias.resolve():
                    try:
                        shutil.copy2(val_src, val_alias)
                    except OSError:
                        pass
                updates["lifecycle_status"] = "INDEPENDENTLY_VALIDATED"
            else:
                updates["lifecycle_status"] = "FAILED"
                updates["last_error"] = (
                    updates.get("last_error")
                    or "; ".join(updates.get("validator_errors") or [])[:400]
                    or "validation failed"
                )
            updates = _record_evo_round(state, root, slug, updates)
            return {
                k: v for k, v in updates.items()
                if k not in ("domain_audit", "validator_took_sec")
            }

        # Dual-Track Deterministic Tournament Gate
        track_defs = [
            ("track_a", "Exact / Reduction", Path(track_a_raw) if track_a_raw else root / "outputs" / f"{slug}-track_a-solution.json"),
            ("track_b", "Bound + Heuristic / Search", Path(track_b_raw) if track_b_raw else root / "outputs" / f"{slug}-track_b-solution.json"),
        ]
        cand_docs: list[Mapping[str, Any]] = []
        track_records: dict[str, dict[str, Any]] = {}
        valid_candidates: list[dict[str, Any]] = []
        canonical_validation = root / "outputs" / f"{slug}-validation.json"
        canonical_validate = root / "outputs" / f"{slug}-validate.json"
        canonical_sol = root / "outputs" / f"{slug}-solution.json"

        for tname, strategy, cpath in track_defs:
            if not cpath.is_file():
                track_records[tname] = {
                    "strategy": strategy,
                    "path": str(cpath),
                    "solver": "-",
                    "status": "MISSING",
                    "declared_objective": None,
                    "recomputed_objective": None,
                    "proven_optimal": False,
                    "validation_ok": False,
                    "tournament_result": "MISSING",
                    "errors": ["candidate solution artifact missing"],
                }
                continue

            try:
                cdoc = json.loads(cpath.read_text(encoding="utf-8"))
                if isinstance(cdoc, dict):
                    cand_docs.append(cdoc)
                else:
                    cdoc = {}
            except Exception:
                cdoc = {}

            res = run_deterministic_validator({**dict(state), "solution_path": str(cpath)})
            t_val_path = root / "outputs" / f"{slug}-{tname}-validate.json"
            if canonical_validation.is_file():
                try:
                    shutil.copy2(canonical_validation, t_val_path)
                except OSError:
                    pass

            ok = bool(res.get("validation_ok"))
            obj_cmp = res.get("recomputed_objective")
            if obj_cmp is None:
                obj_cmp = res.get("objective_value")
            is_num = isinstance(obj_cmp, (int, float)) and not isinstance(obj_cmp, bool)
            val_ok = bool(ok and is_num)

            rec = {
                "strategy": strategy,
                "path": str(cpath),
                "validate_path": str(t_val_path) if t_val_path.is_file() else "",
                "solver": str(cdoc.get("solver") or "-"),
                "status": str(cdoc.get("status") or "-"),
                "declared_objective": res.get("objective_value"),
                "recomputed_objective": res.get("recomputed_objective"),
                "proven_optimal": bool(res.get("proven_optimal")),
                "optimality_gap": res.get("optimality_gap"),
                "validation_ok": val_ok,
                "tournament_result": "PENDING" if val_ok else "DISQUALIFIED",
                "errors": list(res.get("validator_errors") or []),
                "remediation_path": str(res.get("remediation_path") or ""),
            }
            track_records[tname] = rec
            if val_ok:
                valid_candidates.append({"track": tname, "score_obj": float(obj_cmp), **rec})

        sense = _infer_objective_sense(state, root, slug, cand_docs)
        winner_rec: dict[str, Any] | None = None
        if valid_candidates:
            winner_rec = valid_candidates[0]
            for cand in valid_candidates[1:]:
                diff = cand["score_obj"] - winner_rec["score_obj"]
                better = (diff > 1e-6) if sense == "max" else (diff < -1e-6)
                tie_opt = abs(diff) <= 1e-6 and cand["proven_optimal"] and not winner_rec["proven_optimal"]
                if better or tie_opt:
                    winner_rec = cand

            wname = winner_rec["track"]
            for tname, rec in track_records.items():
                if rec["validation_ok"]:
                    rec["tournament_result"] = "WINNER" if tname == wname else "RUNNER_UP"
        else:
            wname = ""

        tournament_path = root / "notes" / f"{slug}-tournament.json"
        tournament_doc = {
            "slug": slug,
            "objective_sense": sense,
            "winner": wname or None,
            "tracks": track_records,
        }
        tournament_path.write_text(json.dumps(tournament_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        if winner_rec is not None:
            w_sol_p = Path(winner_rec["path"])
            if w_sol_p.is_file():
                shutil.copy2(w_sol_p, canonical_sol)
            w_val_p = Path(winner_rec.get("validate_path") or "")
            if w_val_p.is_file():
                shutil.copy2(w_val_p, canonical_validate)
                shutil.copy2(w_val_p, canonical_validation)
            updates_dual = {
                "solution_path": str(canonical_sol),
                "validate_path": str(canonical_validate if canonical_validate.is_file() else canonical_validation),
                "tournament_path": str(tournament_path),
                "winning_track": wname,
                "objective_sense": sense,
                "validation_ok": True,
                "proven_optimal": bool(winner_rec["proven_optimal"]),
                "objective_value": winner_rec["declared_objective"],
                "recomputed_objective": winner_rec["recomputed_objective"],
                "optimality_gap": winner_rec["optimality_gap"],
                "validator_errors": [],
                "remediation_path": "",
                "lifecycle_status": "INDEPENDENTLY_VALIDATED",
                "last_error": "",
            }
            return _record_evo_round(state, root, slug, updates_dual)

        all_errs: list[str] = []
        rem_path = ""
        for tname in ("track_a", "track_b"):
            tr = track_records.get(tname) or {}
            if tr.get("errors"):
                all_errs.extend(f"{tname}: {e}" for e in tr["errors"][:3])
            if not rem_path and tr.get("remediation_path"):
                rem_path = str(tr["remediation_path"])
        fail_dual = {
            "tournament_path": str(tournament_path),
            "winning_track": "",
            "objective_sense": sense,
            "validation_ok": False,
            "proven_optimal": False,
            "validator_errors": all_errs,
            "remediation_path": rem_path,
            "lifecycle_status": "FAILED",
            "last_error": "; ".join(all_errs)[:400] or "all dual-track candidates failed validation",
        }
        return _record_evo_round(state, root, slug, fail_dual)

    def node_table_render(state: AdaptivePipelineState) -> dict:
        root = _resolve_root(state)
        slug = _slug(state, root)
        effective_state: dict[str, Any] = dict(state)
        evo_enabled = bool(effective_state.get("deep_evolution")) or int(effective_state.get("evo_target_rounds") or 1) > 1
        if evo_enabled:
            from orpath.agents.evolution_ledger import best_solution_path

            best_sol = best_solution_path(root, slug)
            canonical_sol = root / "outputs" / f"{slug}-solution.json"
            if best_sol.is_file():
                try:
                    shutil.copy2(best_sol, canonical_sol)
                    effective_state["solution_path"] = str(canonical_sol)
                    v_updates = run_deterministic_validator(effective_state)
                    effective_state.update({
                        k: v for k, v in v_updates.items()
                        if k not in ("domain_audit", "validator_took_sec")
                    })
                except Exception:
                    pass
        try:
            rendered = render_truth_tables(effective_state)
            if effective_state.get("skip_paper"):
                rendered["lifecycle_status"] = "INDEPENDENTLY_VALIDATED"
            for sync_k in ("solution_path", "validate_path", "validation_ok", "objective_value", "recomputed_objective", "proven_optimal", "optimality_gap"):
                if sync_k in effective_state and sync_k not in rendered:
                    rendered[sync_k] = effective_state[sync_k]
            return rendered
        except Exception as exc:  # noqa: BLE001
            return {"tables_path": "", "last_error": f"table renderer failed: {type(exc).__name__}: {exc}"}

    def node_writer(state: AdaptivePipelineState) -> dict:
        root = _resolve_root(state)
        slug = _slug(state, root)
        tables = state.get("tables_path") or str(root / "outputs" / f"{slug}-tables.md")
        paper = root / "papers" / f"{slug}.md"
        obj = state.get("objective_value")
        prov = state.get("proven_optimal")
        rev_notes: list[str] = []
        if state.get("doc_gate_errors"):
            rev_notes.append(f"上轮 doc_gate 缺陷: {'; '.join(str(x) for x in state['doc_gate_errors'])}")
        if state.get("fatal_defects"):
            rev_notes.append(f"上轮审稿打回 FATAL 缺陷: {'; '.join(str(x) for x in state['fatal_defects'])}")
        if rev_notes and paper.is_file():
            rev_notes.append(f"请用 read_file 阅读 {paper} 并用 edit_file 或 export_paper_markdown 逐项外科修复上述缺陷。")
        brief = _brief(state, root, slug, [
            "职责: 严格基于预渲染真值表撰写六章学术论文 (docs/or-paper-sop.md)。",
            "效率纪律: 务必精简工具步数！只需调用 `read_file` 阅读一次真值表（返修时可再读一次现有论文），随后立即调用 `export_paper_markdown` 一次性写出完整六章论文到 PAPER_PATH；严禁浏览仓库目录或大量翻读源码脚本。",
            f"真值表唯一数据来源: {tables}",
            f"双轨赛马结果: tournament_path={state.get('tournament_path') or '-'} winner={state.get('winning_track') or '-'}",
            "文献引用纪律: 仅可引用真值表第4节与 knowledge_pack_path 中的真实文献锚点，严禁编造任何未验证外部文献。",
            f"目标值(以校验器为准): objective={obj} proven_optimal={prov}"
            + (" (未证明最优，严禁使用全局最优措辞，必须如实声明)" if not prov else ""),
            f"必须调用 export_paper_markdown / edit_file 写入: PAPER_PATH={paper}",
            *rev_notes,
        ])
        pre_mtime = paper.stat().st_mtime if paper.is_file() else 0.0
        try:
            text, _msgs = _invoke_with_trace(
                _get_role_agent("writer", state),
                brief,
                root,
                slug,
                "writer",
                wall_timeout_s=600.0,
                max_rec_limit=28,
            )
        except TimeoutError as exc:
            text = paper.read_text(encoding="utf-8", errors="replace") if paper.is_file() else f"# (writer timeout: {exc})\n"

        # Guard against LangGraph recursion-limit exhaustion without leaving bogus placeholder on disk.
        fresh_paper = paper.is_file() and paper.stat().st_mtime > pre_mtime
        if paper.is_file():
            try:
                disk_text = paper.read_text(encoding="utf-8", errors="replace")
                if _is_recursion_exhausted_text(disk_text):
                    paper.unlink()
                    fresh_paper = False
            except OSError:
                pass
        if (not fresh_paper) and _is_recursion_exhausted_text(text):
            tables_excerpt = ""
            tables_p = Path(tables)
            if tables_p.is_file():
                try:
                    tables_excerpt = tables_p.read_text(encoding="utf-8", errors="replace")[:12000]
                except OSError:
                    tables_excerpt = ""
            retry_brief = _brief(state, root, slug, [
                "RETRY (上次因工具步数耗尽未落盘论文): 严禁调用 read_file / list_files / grep_search / run_shell！",
                f"请直接依据下方完整真值表，立刻调用一次 `export_paper_markdown` 将完整六章学术论文写入 PAPER_PATH={paper}！",
                f"目标值: objective={obj} proven_optimal={prov}",
                *rev_notes,
                "--- 预渲染真值表全文/摘要 ---",
                tables_excerpt or "(真值表为空，请如实写明)",
            ])
            try:
                text, _msgs = _invoke_with_trace(
                    _get_role_agent("writer", state),
                    retry_brief,
                    root,
                    slug,
                    "writer_retry",
                    wall_timeout_s=420.0,
                    max_rec_limit=16,
                )
            except TimeoutError as exc:
                text = f"# (writer retry timeout: {exc})\n"
            fresh_paper = paper.is_file() and paper.stat().st_mtime > pre_mtime

        if not paper.is_file():
            cleaned_w = (text or "").strip()
            if cleaned_w and not _is_recursion_exhausted_text(cleaned_w) and not cleaned_w.startswith("# (writer"):
                paper.parent.mkdir(parents=True, exist_ok=True)
                paper.write_text(text, encoding="utf-8")
        retry_w = int(state.get("paper_retry_count") or 0) + 1
        writer_err = "" if paper.is_file() else "writer exhausted steps or timed out before writing paper"
        return {
            "paper_path": str(paper),
            "paper_retry_count": retry_w,
            "writer_attempts": retry_w,
            "revision_count": retry_w,
            "last_error": writer_err,
        }

    def node_doc_gate(state: AdaptivePipelineState) -> dict:
        updates = run_deterministic_doc_gate(state)
        if updates.get("doc_gate_ok") and decide_tier(state) == "A" and not tier_a_with_reviewer:
            updates["lifecycle_status"] = "ACCEPTED"
        return updates

    def node_reviewer(state: AdaptivePipelineState) -> dict:
        root = _resolve_root(state)
        slug = _slug(state, root)
        paper = Path(state.get("paper_path") or (root / "papers" / f"{slug}.md"))
        tables = Path(state.get("tables_path") or (root / "outputs" / f"{slug}-tables.md"))
        review_path = root / "papers" / f"{slug}-review.md"

        # Hard pre-check: missing, empty, or recursion-sentinel paper is an automatic FATAL rejection.
        paper_body = ""
        if paper.is_file():
            try:
                paper_body = paper.read_text(encoding="utf-8", errors="replace")
            except OSError:
                paper_body = ""
        if not paper.is_file() or not paper_body.strip() or _is_recursion_exhausted_text(paper_body):
            err_rev = (
                "## Summary\n待审论文缺失、为空或仅包含步数耗尽占位符，无法通过学术评审。\n\n"
                "## Weaknesses\n- [W1] **FATAL:** 待审论文未完整生成（缺失或为空）。\n\n"
                "## Verdict\nREVISE\n\n"
                "## Revision Plan\n请重新运行 writer 生成完整六章论文并写入指定路径。\n"
            )
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_text(err_rev, encoding="utf-8")
            verdict, fatal = parse_review_reply(err_rev)
            return {
                "review_path": str(review_path),
                "review_verdict": verdict,
                "fatal_defects": fatal,
                "reviewer_summary": err_rev[:2000],
                "lifecycle_status": "PROPOSED",
                "last_error": "missing or invalid paper rejected before review",
            }

        brief = _brief(state, root, slug, [
            "职责: 扮演严苛同行审稿人，按十项核对表检查论文与解工件并出具分级评审意见。",
            f"效率纪律: 确定性验证已执行 (`validation_ok={state.get('validation_ok')}`)。严禁陷入漫长重算循环！仅调用 `read_file` 阅读 `{paper}` 与 `{tables}`（最多2~4次工具调用），随后立即调用 `export_paper_markdown` 写入 `REVIEW_PATH={review_path}`！",
            "包膜约定说明: 对包含多个独立子问题 (subproblems: Q1..Qk) 的建模案例，校验包膜中的标量 `objective` 常为校验器核对用的子问题分项汇总值；只要论文清晰分列各子问独立指标并如实界定汇总检验口径，不应以『校验包膜使用了汇总 scalar』单独判定 FATAL。",
            f"待审论文: {paper}",
            f"真值表路径: {tables}",
            f"确定性校验结论: validation_ok={state.get('validation_ok')} proven_optimal={state.get('proven_optimal')}",
            f"必须调用 export_paper_markdown 写入评审报告: REVIEW_PATH={review_path}",
            "输出 FATAL/MAJOR/MINOR 分级缺陷与 Verdict (PASS/REVISE)。",
        ])
        pre_rev_mtime = review_path.stat().st_mtime if review_path.is_file() else 0.0
        try:
            text, _msgs = _invoke_with_trace(
                _get_role_agent("reviewer", state),
                brief,
                root,
                slug,
                "reviewer",
                wall_timeout_s=360.0,
                max_rec_limit=36,
            )
        except TimeoutError as exc:
            text = f"Verdict: REVISE\n- [FATAL] reviewer timed out: {exc}\n"

        fresh_rev = review_path.is_file() and review_path.stat().st_mtime > pre_rev_mtime
        if review_path.is_file():
            try:
                disk_chk = review_path.read_text(encoding="utf-8", errors="replace")
                if _is_recursion_exhausted_text(disk_chk):
                    review_path.unlink()
                    fresh_rev = False
            except OSError:
                pass
        if (not fresh_rev) and _is_recursion_exhausted_text(text):
            tables_excerpt = ""
            if tables.is_file():
                try:
                    tables_excerpt = tables.read_text(encoding="utf-8", errors="replace")[:5000]
                except OSError:
                    tables_excerpt = ""
            paper_excerpt = (
                paper_body
                if len(paper_body) <= 16000
                else (paper_body[:10000] + "\n\n... [middle truncated for size] ...\n\n" + paper_body[-6000:])
            )
            retry_brief = _brief(state, root, slug, [
                "RETRY (上次因工具步数耗尽未写入评审报告): 严禁调用 read_file / list_files / grep_search / run_shell！",
                f"请直接基于下方论文与真值表摘要，立即调用一次 `export_paper_markdown` 写入评审报告到 REVIEW_PATH={review_path}！",
                f"确定性校验结论: validation_ok={state.get('validation_ok')} proven_optimal={state.get('proven_optimal')}",
                "--- 待审论文内容 ---",
                paper_excerpt,
                "--- 真值表摘要 ---",
                tables_excerpt or "-",
            ])
            try:
                text, _msgs = _invoke_with_trace(
                    _get_role_agent("reviewer", state),
                    retry_brief,
                    root,
                    slug,
                    "reviewer_retry",
                    wall_timeout_s=300.0,
                    max_rec_limit=16,
                )
            except TimeoutError as exc:
                text = f"Verdict: REVISE\n- [FATAL] reviewer retry timed out: {exc}\n"
            fresh_rev = review_path.is_file() and review_path.stat().st_mtime > pre_rev_mtime

        if not fresh_rev:
            cleaned_r = (text or "").strip()
            if not cleaned_r or _is_recursion_exhausted_text(cleaned_r):
                text = (
                    "## Summary\n审稿人未能完成评审报告（步数耗尽或输出为空）。\n\n"
                    "## Weaknesses\n- [W1] **FATAL:** reviewer failed to produce valid review report.\n\n"
                    "## Verdict\nREVISE\n"
                )
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_text(text, encoding="utf-8")
        review_body = text
        if fresh_rev and review_path.is_file():
            try:
                disk_rev = review_path.read_text(encoding="utf-8", errors="replace")
                if disk_rev.strip():
                    review_body = disk_rev
            except OSError:
                pass
        verdict, fatal = parse_review_reply(review_body)
        return {
            "review_path": str(review_path),
            "review_verdict": verdict,
            "fatal_defects": fatal,
            "reviewer_summary": review_body[:2000],
            "lifecycle_status": "ACCEPTED" if (verdict == "PASS" and not fatal) else "PROPOSED",
            "last_error": "",
        }

    def node_tier_c_focus(state: AdaptivePipelineState) -> dict:
        root = _resolve_root(state)
        slug = _slug(state, root)
        subs = [str(s).strip() for s in (state.get("subproblems") or []) if str(s).strip()]
        done = [str(q) for q in (state.get("subproblem_done") or [])]
        root_out = root / "outputs"
        root_nt = root / "notes"
        root_out.mkdir(parents=True, exist_ok=True)
        root_nt.mkdir(parents=True, exist_ok=True)
        ledger_path = root_nt / f"{slug}-ledger.json"
        ledger: dict[str, Any] = {}
        if ledger_path.is_file():
            try:
                ledger = json.loads(ledger_path.read_text(encoding="utf-8")) or {}
            except Exception:
                ledger = {}

        todo = [q for q in subs if q not in done]
        failed: list[str] = []
        summaries: list[str] = []
        for q in todo:
            qpath = root_out / f"{slug}-{q}.json"
            brief = _brief(state, root, slug, [
                f"任务: 攻坚 Tier-C 第 {q} 问 (第 {done.index(q) + 1 if q in done else len(done) + 1}/{len(subs)} 批)。",
                f"跨问状态工件账本 ledger: {ledger_path}",
                f"上一批账本内容: {json.dumps(ledger, ensure_ascii=False)[:_MAX_BRIEF_LEDGER_BYTES]}",
                "要求: 继承上一批余料/初始 SOC 等状态，将本题解工件写入 SOLUTION_PATH="
                + str(qpath)
                + " 并同步更新账本；禁止回头篡改已通过子问。",
                "完成后回复: 结果摘要+本题工件路径+账本更新摘要。",
            ])
            # Fresh isolated message list per question — zero cross-question context pollution.
            try:
                text, _msgs = _invoke_with_trace(
                    _get_role_agent("modeler", state),
                    brief,
                    root,
                    slug,
                    f"tier_c_{q}",
                    wall_timeout_s=600.0,
                )
            except TimeoutError as exc:
                text = f"tier_c_{q} timeout: {exc}"
            summaries.append(text[:800])
            if not qpath.is_file():
                failed.append(q)
                ledger[q] = {"ok": False, "error": "artifact missing"}
                ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                continue
            try:
                sol = json.loads(qpath.read_text(encoding="utf-8"))
            except Exception:
                sol = {}
            ok, data, _raw = validate_artifact(root, str(state.get("problem_id") or slug), qpath, root_out / f"{slug}-{q}-validation.json")
            obj = sol.get("objective")
            try:
                obj = float(obj) if obj is not None else None
            except (TypeError, ValueError):
                obj = None
            if ok:
                done.append(q)
                ledger[q] = {"ok": True, "objective": obj, "status": sol.get("status", "-")}
            else:
                failed.append(q)
                q_errs = (data.get("errors") or [])[:3]
                rem_p = ""
                try:
                    from orpath.agents import knowledge_pack as _kp

                    rem_res = _kp.build_error_remediation_pack(
                        root,
                        f"{slug}-{q}",
                        problem_class=str(state.get("problem_class") or ""),
                        validator_errors=q_errs,
                        retry_round=int(state.get("model_retry_count") or 0) + 1,
                    )
                    rem_p = str(rem_res.get("remediation_path") or "")
                except Exception:
                    rem_p = ""
                ledger[q] = {"ok": False, "objective": obj, "errors": q_errs, "remediation_path": rem_p}
            ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        merged: dict[str, Any] = {}
        if not failed:
            objs = [ledger[q]["objective"] for q in subs if isinstance(ledger.get(q, {}).get("objective"), (int, float))]
            merged = {
                "problem_id": state.get("problem_id") or slug,
                "problem_class": state.get("problem_class") or "",
                "status": "OPTIMAL" if all(
                    str(ledger.get(q, {}).get("status", "-")).upper() == "OPTIMAL" for q in subs
                ) else "FEASIBLE",
                "objective": sum(float(o) for o in objs) if len(objs) == len(subs) else None,
                "solver": "adaptive_graph.tier_c_merge",
                "source": "collective subproblem envelopes",
                "proven_optimal": False,
                "subproblems": {q: dict(ledger[q]) for q in subs if q in ledger},
            }
            merged_path = root_out / f"{slug}-solution.json"
            merged_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            try:
                from orpath import process_memory as _pm

                _pm.auto_draft_after_validate(
                    root,
                    {
                        **dict(state),
                        "slug": slug,
                        "problem_class": str(state.get("problem_class") or "general_or"),
                        "solution_path": str(merged_path),
                        "solve_mode": "adaptive_graph.tier_c_merge",
                    },
                    gate_ok=True,
                )
            except Exception:
                pass

        last_err = ""
        if failed:
            last_err = f"tier-c subproblem(s) failed: {failed}"
        retry_next = int(state.get("model_retry_count") or 0) + 1
        return {
            "subproblem_done": done,
            "ledger_path": str(ledger_path),
            "tier_c_results": ledger,
            "modeler_summary": "\n---\n".join(summaries)[:4000],
            "solution_path": str(root_out / f"{slug}-solution.json") if merged else "",
            "objective_value": merged.get("objective"),
            "validation_ok": bool(merged),
            "lifecycle_status": "INDEPENDENTLY_VALIDATED" if merged else "FAILED",
            "model_retry_count": retry_next,
            "model_attempts": retry_next,
            "last_error": last_err,
        }

    def node_fail_closed(state: AdaptivePipelineState) -> dict:
        root = _resolve_root(state)
        slug = _slug(state, root)
        reasons = [str(state.get("last_error") or "pipeline failed")]
        if state.get("doc_gate_errors"):
            reasons.append("doc_gate: " + " | ".join(str(e) for e in state["doc_gate_errors"]))
        if state.get("validator_errors"):
            reasons.append("validator: " + " | ".join(str(e) for e in state["validator_errors"])[:400])
        reason = "; ".join(reasons)[:800]
        (root / "notes").mkdir(parents=True, exist_ok=True)
        failure_file = root / "notes" / f"{slug}-failure.md"
        failure_file.write_text(
            json.dumps(
                {
                    "reason": reason,
                    "last_error": reason,
                    "fatal_defects": state.get("fatal_defects") or [],
                    "validator_errors": state.get("validator_errors") or [],
                    "doc_gate_errors": state.get("doc_gate_errors") or [],
                    "cosplay_quarantined": state.get("cosplay_quarantined") or [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return {
            "last_error": reason,
            "failure_report_path": str(failure_file),
            "lifecycle_status": "FAILED",
        }

    # --------------------------------------------------------------- edges
    g: StateGraph = StateGraph(AdaptivePipelineState)
    g.add_node("preflight", node_preflight)
    g.add_node("analyst", node_analyst)
    g.add_node("modeler", node_modeler)
    g.add_node("validator", node_validator)
    g.add_node("table_render", node_table_render)
    g.add_node("writer", node_writer)
    g.add_node("doc_gate", node_doc_gate)
    g.add_node("reviewer", node_reviewer)
    g.add_node("tier_c_focus", node_tier_c_focus)
    g.add_node("fail_closed", node_fail_closed)

    g.add_edge(START, "preflight")
    g.add_edge("preflight", "analyst")
    g.add_conditional_edges(
        "analyst",
        _after_analyst,
        {"tier_c_focus": "tier_c_focus", "modeler": "modeler"},
    )
    g.add_conditional_edges(
        "modeler",
        _after_modeler,
        {"validator": "validator", "modeler": "modeler", "fail_closed": "fail_closed"},
    )
    g.add_conditional_edges(
        "validator",
        _after_validator,
        {"table_render": "table_render", "modeler": "modeler", "fail_closed": "fail_closed"},
    )
    g.add_conditional_edges(
        "tier_c_focus",
        _after_focus,
        {"table_render": "table_render", "tier_c_focus": "tier_c_focus", "fail_closed": "fail_closed"},
    )
    g.add_conditional_edges(
        "table_render",
        _after_table_render,
        {"writer": "writer", "fail_closed": "fail_closed", "END_H": END},
    )
    g.add_conditional_edges(
        "writer",
        _after_writer,
        {"doc_gate": "doc_gate", "reviewer": "reviewer"},
    )
    g.add_conditional_edges(
        "doc_gate",
        lambda s: _after_doc_gate(s, bool(tier_a_with_reviewer)),
        {"writer": "writer", "reviewer": "reviewer", "fail_closed": "fail_closed", "END_H": END},
    )
    g.add_conditional_edges(
        "reviewer",
        _after_reviewer,
        {"writer": "writer", "fail_closed": "fail_closed", "END_H": END},
    )
    g.add_edge("fail_closed", END)

    if not compile_graph:
        return g
    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()


# --------------------------------------------------------------------------- #
# pure-Python routers (replace LLM supervisor polling)
# --------------------------------------------------------------------------- #
def _cap(state: Mapping[str, Any], counter_key: str = "model_retry_count") -> int:
    try:
        return int(state.get(counter_key) or 0)
    except (TypeError, ValueError):
        return 0


def _after_analyst(state: Mapping[str, Any]) -> Literal["tier_c_focus", "modeler"]:
    return "tier_c_focus" if decide_tier(state) == "C" else "modeler"


def _after_modeler(state: Mapping[str, Any]) -> Literal["validator", "modeler", "fail_closed"]:
    if state.get("solution_path"):
        return "validator"
    evo_enabled = bool(state.get("deep_evolution")) or int(state.get("evo_target_rounds") or 1) > 1
    if evo_enabled:
        # Always pass through node_validator in evolution mode so failed rounds are
        # recorded in the experiment ledger and incumbent restoration stays centralized.
        return "validator"
    if _cap(state) < int(state.get("max_retries") or 3):
        return "modeler"
    return "fail_closed"


def _after_validator(state: Mapping[str, Any]) -> Literal["table_render", "modeler", "fail_closed"]:
    evo_enabled = bool(state.get("deep_evolution")) or int(state.get("evo_target_rounds") or 1) > 1
    if not evo_enabled:
        if state.get("validation_ok"):
            return "table_render"
        if _cap(state) < int(state.get("max_retries") or 3):
            return "modeler"
        return "fail_closed"

    cur_r = max(1, int(state.get("evo_round") or 1))
    t_r = max(1, min(10, int(state.get("evo_target_rounds") or 5)))
    m_r = max(t_r, min(10, int(state.get("evo_max_rounds") or 10)))

    # Early exit ONLY when exact optimality with zero gap is genuinely proven
    # (never early-exit on a degenerate 0.0 maximization outcome).
    obj_val = state.get("recomputed_objective")
    if obj_val is None:
        obj_val = state.get("objective_value")
    zero_max_degenerate = (
        str(state.get("objective_sense") or "").strip().lower() == "max"
        and isinstance(obj_val, (int, float))
        and not isinstance(obj_val, bool)
        and abs(float(obj_val)) <= 1e-9
    )
    if (
        not zero_max_degenerate
        and state.get("validation_ok")
        and (state.get("proven_optimal") is True or state.get("optimality_gap") == 0.0)
    ):
        return "table_render"

    if cur_r < t_r:
        return "modeler"
    if t_r <= cur_r < m_r and bool(state.get("evo_promoted")):
        return "modeler"

    if state.get("validation_ok") or state.get("incumbent_available"):
        return "table_render"
    return "fail_closed"


def _after_focus(state: Mapping[str, Any]) -> Literal["table_render", "tier_c_focus", "fail_closed"]:
    subs = [str(s).strip() for s in (state.get("subproblems") or []) if str(s).strip()]
    done = {str(q) for q in (state.get("subproblem_done") or [])}
    if subs and all(q in done for q in subs):
        return "table_render"
    if _cap(state) < int(state.get("max_retries") or 3):
        return "tier_c_focus"
    return "fail_closed"


def _after_table_render(state: Mapping[str, Any]) -> Literal["writer", "fail_closed", "END_H"]:
    if not state.get("tables_path"):
        return "fail_closed"
    if state.get("skip_paper"):
        return "END_H"
    return "writer"


def _after_writer(state: Mapping[str, Any]) -> Literal["doc_gate", "reviewer"]:
    return "doc_gate" if decide_tier(state) == "A" else "reviewer"


def _after_doc_gate(state: Mapping[str, Any], tier_a_with_reviewer: bool = False) -> Literal["writer", "reviewer", "fail_closed", "END_H"]:
    if not state.get("doc_gate_ok"):
        if _cap(state, "paper_retry_count") < int(state.get("max_retries") or 3):
            return "writer"
        return "fail_closed"
    if decide_tier(state) == "A" and bool(tier_a_with_reviewer):
        return "reviewer"
    return "END_H"


def _after_reviewer(state: Mapping[str, Any]) -> Literal["writer", "fail_closed", "END_H"]:
    fatal = list(state.get("fatal_defects") or [])
    if not fatal:
        return "END_H"
    if _cap(state, "paper_retry_count") < int(state.get("max_retries") or 3):
        return "writer"
    return "fail_closed"


def build_compiled_adaptive_graph(
    model: Any = None,
    agents: Mapping[str, Any] | None = None,
    cartridge_tools: Any = None,
    domain_directive: str = "",
    max_retries: int = 3,
    tier_a_with_reviewer: bool = False,
    checkpointer: Any = None,
    race_tracks: int | None = None,
) -> Any:
    """Compile + freeze defaults (product seam analogous to ADR-0003)."""
    return build_adaptive_graph(
        model=model,
        agents=agents,
        cartridge_tools=cartridge_tools,
        domain_directive=domain_directive,
        max_retries=max_retries,
        tier_a_with_reviewer=tier_a_with_reviewer,
        checkpointer=checkpointer,
        race_tracks=race_tracks,
    )


def build_isolated_pipeline_graph(
    model: Any = None,
    checkpointer: Any = None,
    *,
    agents: Mapping[str, Any] | None = None,
    cartridge_tools: Any = None,
    domain_directive: str = "",
    max_retries: int = 3,
    tier_a_with_reviewer: bool = False,
    race_tracks: int | None = None,
) -> StateGraph:
    """Unified Deep Mode uncompiled StateGraph alias backed by :func:`build_adaptive_graph`."""
    return build_adaptive_graph(
        model=model,
        agents=agents,
        cartridge_tools=cartridge_tools,
        domain_directive=domain_directive,
        max_retries=max_retries,
        tier_a_with_reviewer=tier_a_with_reviewer,
        checkpointer=checkpointer,
        race_tracks=race_tracks,
        compile_graph=False,
    )


def build_compiled_isolated_pipeline(
    checkpointer: Any = None,
    model: Any = None,
    *,
    agents: Mapping[str, Any] | None = None,
    cartridge_tools: Any = None,
    domain_directive: str = "",
    max_retries: int = 3,
    tier_a_with_reviewer: bool = False,
    race_tracks: int | None = None,
) -> Any:
    """Compiled Deep Mode pipeline alias backed by :func:`build_compiled_adaptive_graph`."""
    return build_compiled_adaptive_graph(
        model=model,
        agents=agents,
        cartridge_tools=cartridge_tools,
        domain_directive=domain_directive,
        max_retries=max_retries,
        tier_a_with_reviewer=tier_a_with_reviewer,
        checkpointer=checkpointer,
        race_tracks=race_tracks,
    )


def adaptive_stage_map() -> dict[str, Any]:
    _END = "__end__"
    return {
        "name": "orpath_adaptive",
        "state": "AdaptivePipelineState (CorePipelineState superset)",
        "nodes": list(ADAPTIVE_NODES),
        "edges": [
            {"from": "START", "to": "preflight"},
            {"from": "preflight", "to": "analyst"},
            {"from": "analyst", "to": ["tier_c_focus|C", "modeler|A/B"], "cond": "decide_tier"},
            {"from": "modeler", "to": ["validator", "fail_closed|missing artifact"]},
            {
                "from": "validator",
                "to": ["table_render|ok", "modeler|fail & retry budget", "fail_closed|capped"],
                "cond": "validation_ok / model_retry_count",
            },
            {
                "from": "tier_c_focus",
                "to": [
                    "table_render|all questions ok",
                    "tier_c_focus|partial & budget left",
                    "fail_closed|capped",
                ],
                "cond": "subproblem_done / model_retry_count",
            },
            {"from": "table_render", "to": ["writer", "fail_closed|render error"]},
            {"from": "writer", "to": ["doc_gate|tier A", "reviewer|tier B/C"]},
            {
                "from": "doc_gate",
                "to": ["writer|gate fail & budget", "fail_closed|capped", "reviewer|tier A opt-in", _END + "|pass"],
                "cond": "doc_gate_ok / paper_retry_count",
            },
            {
                "from": "reviewer",
                "to": ["writer|FATAL & budget", "fail_closed|capped", _END + "|PASS"],
                "cond": "fatal_defects / paper_retry_count",
            },
            {"from": "fail_closed", "to": _END},
        ],
        "retry_budget": "model_retry_count & paper_retry_count < max_retries (never unbounded)",
    }


if __name__ == "__main__":  # pragma: no cover - manual smoke
    import warnings

    warnings.simplefilter("ignore")
    print(json.dumps(adaptive_stage_map(), ensure_ascii=False, indent=2))
