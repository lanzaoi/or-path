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
    }
)


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
) -> tuple[str, list[Any]]:
    """Invoke an elite worker in a fresh 1-message list and persist its stage JSONL log."""
    resp = agent.invoke({"messages": [HumanMessage(brief)]})
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

    if not _has_tool_execution(msgs) and sol_path.is_file():
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
    subs = sol.get("subproblems") if isinstance(sol.get("subproblems"), dict) else {}
    if subs:
        out += ["| subproblem | objective | status |", "|---|---|---|"]
        for q, v in subs.items():
            if isinstance(v, dict):
                out.append(f"| {q} | {_format_num(v.get('objective', v.get('total_cost')))} | {v.get('status', '-')} |")
            else:
                out.append(f"| {q} | {_format_num(v)} | - |")
        out.append("")
    if not (routes or allocations or subs):
        out.append("(无领域分解数据；空真值表由确定性渲染器如实记录。)")

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

    Verdict resolution is strictly deterministic (no LLM): any genuine FATAL
    defect line (``[W*] FATAL:`` / ``**FATAL**`` / ``FATAL:``, excluding
    "未发现 FATAL" disclaimers) forces REVISE; otherwise an explicit
    ``Verdict`` line wins (PASS > REVISE). MAJOR/MINOR-only replies without an
    explicit verdict are treated as PASS so the boilerplate "Revision Plan"
    heading cannot generate false REVISE verdicts.
    """
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
def _infer_objective_sense(
    state: Mapping[str, Any],
    root: Path,
    slug: str,
    candidate_docs: list[Mapping[str, Any]],
) -> str:
    """Deterministically infer optimization direction ('min' or 'max')."""
    explicit = str(state.get("objective_sense") or "").strip().lower()
    if explicit in {"min", "minimize", "minimise"}:
        return "min"
    if explicit in {"max", "maximize", "maximise"}:
        return "max"

    schema_p = Path(str(state.get("schema_path") or (root / "outputs" / f"{slug}-schema.json")))
    if schema_p.is_file():
        try:
            sdoc = json.loads(schema_p.read_text(encoding="utf-8"))
            if isinstance(sdoc, Mapping):
                ss = str(sdoc.get("objective_sense") or sdoc.get("sense") or "").strip().lower()
                if ss in {"min", "minimize", "minimise"}:
                    return "min"
                if ss in {"max", "maximize", "maximise"}:
                    return "max"
        except Exception:
            pass

    for doc in candidate_docs:
        ss = str(doc.get("objective_sense") or doc.get("sense") or "").strip().lower()
        if ss in {"min", "minimize", "minimise"}:
            return "min"
        if ss in {"max", "maximize", "maximise"}:
            return "max"

    pc = str(state.get("problem_class") or "").strip().lower()
    return "max" if pc in _MAXIMIZATION_CLASSES else "min"


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
            "职责: 题面精读 + 数据画像核对 + 查阅 knowledge_pack_path 领域规约 + 数学分类确认 + Tier 分档建议 (严禁求解/猜解)。",
            "若题面包含多个递增子问题 (如 Q1/Q2/Q3), 请另起一行输出 SUBPROBLEMS=[\"q1\",\"q2\",\"q3\"]。",
            "输出: 结构化分析结论, 交 modeler 承接。",
        ])
        text, _msgs = _invoke_with_trace(_get_role_agent("analyst", state), brief, root, slug, "analyst")
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

        merged_state = {**state, **common, "subproblems": subs}
        out: dict[str, Any] = {
            "analyst_summary": text[:2000],
            "analyst_brief_path": str(analyst_p),
            "research_path": str(analyst_p),
            "tier": decide_tier(merged_state),
        }
        if subs:
            out["subproblems"] = subs
        return out

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
    ) -> tuple[str, list[str]]:
        max_cosplay_retries = 2 if enforce_cosplay else 0
        quarantined_all: list[str] = []
        brief_cur = base_brief
        last_text = ""
        for attempt_idx in range(max_cosplay_retries + 1):
            last_text, msgs = _invoke_with_trace(agent_obj, brief_cur, root, slug, stage_name)
            hit, reason, q_files = _check_and_quarantine_cosplay(
                msgs, sol_target, schema_path, enforce=enforce_cosplay
            )
            quarantined_all.extend(q_files)
            if not hit:
                return last_text, quarantined_all
            if attempt_idx < max_cosplay_retries:
                brief_cur = (
                    f"RETRY {attempt_idx + 1}/{max_cosplay_retries}: Previous output was quarantined to "
                    f".cosplay-quarantine ({reason}). You MUST call real solver/script tools "
                    f"(execute_or_solver / write_custom_solver_script / execute_custom_script / run_shell) "
                    f"and write ONLY structural formulation fields (never objective/tour/routes/path/optimal) "
                    f"into {schema_path}.\n\n{base_brief}"
                )
        return last_text, quarantined_all

    def node_modeler(state: AdaptivePipelineState) -> dict:
        root = _resolve_root(state)
        slug = _slug(state, root)
        (root / "outputs").mkdir(parents=True, exist_ok=True)
        (root / "notes").mkdir(parents=True, exist_ok=True)

        tier = decide_tier({**state, **common})
        domain = str(state.get("domain_cartridge") or "")
        general_or = domain == "general_or" or domain == ""
        schema_path = Path(str(state.get("schema_path") or (root / "outputs" / f"{slug}-schema.json")))
        canonical_sol = root / "outputs" / f"{slug}-solution.json"

        enforce_cosplay = bool(
            state.get("enforce_anti_cosplay")
            if state.get("enforce_anti_cosplay") is not None
            else using_default_agents
        )
        use_horse_race = bool(
            state.get("enable_horse_race")
            or race_tracks == 2
            or (using_default_agents and race_tracks != 1 and state.get("enable_horse_race") is not False)
            or ("or_modeler_track_a" in resolved_agents or "or_modeler_track_b" in resolved_agents)
        )

        extra_lines: list[str] = [
            "先验参考: 请优先查阅 knowledge_pack_path 中的标准数学规划范式、允许算子与历史防坑经验 (严禁将其当作算例数值答案)。"
        ]
        if state.get("remediation_path"):
            extra_lines.append(
                f"⚠️ 上轮独立验证器打回修复指令: 必须先读取靶向修复包 remediation_path: {state.get('remediation_path')} "
                f"并逐条消除错误: {'; '.join(str(x) for x in (state.get('validator_errors') or [])[:3])}"
            )
        if general_or:
            extra_lines.extend([
                "装备包: general_or (无现成专用适配器) — 自定义开放赛题闭环协议:",
                "  ① 先用 get_problem_formulation_template / consult_or_skill 从 knowledge/skills/or-problems.md "
                "取得最相近数学规划范式 (决策变量/目标/约束编号);",
                "  ② 用 write_custom_solver_script 把独立 Python 求解脚本写入 outputs/<slug>-custom_solver.py "
                "(ortools.sat.python.cp_model / highspy / pulp), 再用 execute_custom_script 运行;",
                "  ③ 把独立重算校验脚本写入 outputs/<slug>-custom-validate.py (脱离求解器变量, 直接用原始输入数据重算"
                "约束满足度与目标值), 运行并产出 outputs/<slug>-custom-validate.json;",
                "  ④ solution.json 必须携带 problem_class=custom_mip 与 validation_report 指针。",
                "严禁: 不得宣称 proven_optimal 除非 CP-SAT 返回 OPTIMAL; 不得抄写任何上游 agent 的对话文本。",
            ])

        quarantined_files: list[str] = list(state.get("cosplay_quarantined") or [])
        retry_next = int(state.get("model_retry_count") or 0) + 1

        if not use_horse_race:
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
            "last_error": "" if first_candidate else "both dual-track modelers produced no solution artifact",
        }

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
            return {
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

        all_errs: list[str] = []
        rem_path = ""
        for tname in ("track_a", "track_b"):
            tr = track_records.get(tname) or {}
            if tr.get("errors"):
                all_errs.extend(f"{tname}: {e}" for e in tr["errors"][:3])
            if not rem_path and tr.get("remediation_path"):
                rem_path = str(tr["remediation_path"])
        return {
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

    def node_table_render(state: AdaptivePipelineState) -> dict:
        try:
            rendered = render_truth_tables(state)
            if state.get("skip_paper"):
                rendered["lifecycle_status"] = "INDEPENDENTLY_VALIDATED"
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
            f"真值表唯一数据来源: {tables}",
            f"双轨赛马结果: tournament_path={state.get('tournament_path') or '-'} winner={state.get('winning_track') or '-'}",
            "文献引用纪律: 仅可引用真值表第4节与 knowledge_pack_path 中的真实文献锚点，严禁编造任何未验证外部文献。",
            f"目标值(以校验器为准): objective={obj} proven_optimal={prov}"
            + (" (未证明最优，严禁使用全局最优措辞，必须如实声明)" if not prov else ""),
            f"必须调用 export_paper_markdown / edit_file 写入: PAPER_PATH={paper}",
            *rev_notes,
        ])
        text, _msgs = _invoke_with_trace(_get_role_agent("writer", state), brief, root, slug, "writer")
        if not paper.is_file():
            paper.parent.mkdir(parents=True, exist_ok=True)
            paper.write_text(text or "# (writer produced no content)\n", encoding="utf-8")
        retry_w = int(state.get("paper_retry_count") or 0) + 1
        return {
            "paper_path": str(paper),
            "paper_retry_count": retry_w,
            "writer_attempts": retry_w,
            "revision_count": retry_w,
            "last_error": "",
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
        review_path = root / "papers" / f"{slug}-review.md"
        brief = _brief(state, root, slug, [
            "职责: 扮演严苛同行审稿人，调用 read_file / validate_solution_tool / run_shell 等核对工具后按十项核对表检查论文与解工件。",
            f"待审论文: {paper}",
            f"确定性校验结论: validation_ok={state.get('validation_ok')} proven_optimal={state.get('proven_optimal')}",
            f"必须调用 export_paper_markdown 写入评审报告: REVIEW_PATH={review_path}",
            "输出 FATAL/MAJOR/MINOR 分级缺陷与 Verdict (PASS/REVISE)。",
        ])
        text, _msgs = _invoke_with_trace(_get_role_agent("reviewer", state), brief, root, slug, "reviewer")
        if not review_path.is_file():
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_text(text or "# (reviewer produced no content)\n", encoding="utf-8")
        verdict, fatal = parse_review_reply(text)
        return {
            "review_path": str(review_path),
            "review_verdict": verdict,
            "fatal_defects": fatal,
            "reviewer_summary": text[:2000],
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
            text, _msgs = _invoke_with_trace(
                _get_role_agent("modeler", state),
                brief,
                root,
                slug,
                f"tier_c_{q}",
            )
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
        {"validator": "validator", "fail_closed": "fail_closed"},
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


def _after_modeler(state: Mapping[str, Any]) -> Literal["validator", "fail_closed"]:
    return "validator" if state.get("solution_path") else "fail_closed"


def _after_validator(state: Mapping[str, Any]) -> Literal["table_render", "modeler", "fail_closed"]:
    if state.get("validation_ok"):
        return "table_render"
    if _cap(state) < int(state.get("max_retries") or 3):
        return "modeler"
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
