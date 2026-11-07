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
from pathlib import Path
from typing import Any, Literal, Mapping

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from orpath.agents.deterministic_nodes import (
    run_deterministic_validator,
    run_preflight_probe,
    validate_artifact,
)

__all__ = [
    "ADAPTIVE_NODES",
    "AdaptivePipelineState",
    "TIER_A_CLASSES",
    "build_adaptive_graph",
    "build_compiled_adaptive_graph",
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
    # deterministic doc gate
    doc_gate_ok: bool
    doc_gate_errors: list[str]
    # reviewer verdict
    review_verdict: str
    subproblem_done: list[str]


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

_MAX_BRIEF_LEDGER_BYTES = 4000


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
        f"- problem_file: {state.get('problem_file') or '-'}",
        f"- data_files: {state.get('data_files') or []}",
        "允许读写目录: outputs/ notes/ papers/ runs/",
    ]
    lines.extend(extra_lines)
    return "\n".join(lines)


def _invoke_agent(agent: Any, brief: str) -> str:
    """Invoke an elite worker in a brand-new isolated message list."""
    resp = agent.invoke({"messages": [HumanMessage(brief)]})
    msgs = resp.get("messages") if isinstance(resp, Mapping) else None
    if not msgs:
        return ""
    for msg in reversed(list(msgs)):
        if isinstance(msg, AIMessage):
            text = msg.content
            if isinstance(text, list):
                text = json.dumps(text, ensure_ascii=False, default=str)
            return str(text)[:8000]
    return ""


def _default_agents(model: Any, cartridge_tools: Any, domain_directive: str) -> dict[str, Any]:
    from orpath.agents.workers import (
        ANALYST_NAME,
        MODELER_NAME,
        REVIEWER_NAME,
        WRITER_NAME,
        create_analyst_agent,
        create_modeler_agent,
        create_reviewer_agent,
        create_writer_agent,
    )

    # Phase 3.3: open custom MIP/CP questions ride the general_or cartridge —
    # mount the formulation-template / sandbox script authoring tools.
    general_or_tools = None
    if "general_or" in str(domain_directive or "") or (cartridge_tools is None):
        try:
            from orpath.agents.tools_or import GENERAL_OR_TOOLS

            general_or_tools = list(GENERAL_OR_TOOLS)
        except Exception:
            general_or_tools = None

    return {
        ANALYST_NAME: create_analyst_agent(model=model, cartridge_tools=cartridge_tools, domain_directive=domain_directive),
        MODELER_NAME: create_modeler_agent(model=model, cartridge_tools=cartridge_tools, domain_directive=domain_directive, extra_tools=general_or_tools),
        WRITER_NAME: create_writer_agent(model=model, domain_directive=domain_directive),
        REVIEWER_NAME: create_reviewer_agent(model=model, domain_directive=domain_directive),
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
        f"| proven_optimal | {bool((sol.get('meta') or {}).get('proven_optimal', sol.get('proven_optimal', sol.get('status', '').upper() == 'OPTIMAL')))} |",
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


def run_deterministic_doc_gate(state: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic closure gate for the writer artifact (0 LLM).

    Checks: paper exists; the six SOP chapters are all present (chapter-titled
    keywords, grouped with tolerant alternatives); declared objective value
    appears in the text (Numbers Truth binding); unproven-optimality papers
    must not claim 全局最优.
    """
    root = _resolve_root(state)
    paper_raw = state.get("paper_path") or ""
    paper = Path(paper_raw) if paper_raw else (root / "papers" / f"{_slug(state, root)}.md")
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
def build_adaptive_graph(
    model: Any = None,
    agents: Mapping[str, Any] | None = None,
    cartridge_tools: Any = None,
    domain_directive: str = "",
    max_retries: int = 3,
    tier_a_with_reviewer: bool = False,
    checkpointer: Any = None,
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

    Returns:
        Compiled ``StateGraph`` over ``AdaptivePipelineState``.
    """
    if agents is None:
        from orpath.control_plane import get_chat_model

        model = model if model is not None else get_chat_model()
        agents = _default_agents(model, cartridge_tools, domain_directive)
    else:
        agents = dict(agents)

    agent_map = {
        "analyst": agents.get("or_analyst"),
        "modeler": agents.get("or_modeler"),
        "writer": agents.get("or_writer"),
        "reviewer": agents.get("or_reviewer"),
    }
    for name, a in agent_map.items():
        if a is None:
            raise ValueError(f"agents['{name}'] (or_*) is required for the adaptive machine")

    common = {"max_retries": int(max_retries)}

    # --------------------------------------------------------------- nodes
    def node_preflight(state: AdaptivePipelineState) -> dict:
        return run_preflight_probe(state)

    def node_analyst(state: AdaptivePipelineState) -> dict:
        root, slug = _resolve_root(state), _slug(state, _resolve_root(state))
        brief = _brief(state, root, slug, [
            "职责: 题面精读 + 数据画像核对 + 数学分类确认 + Tier 分档建议 (严禁求解/猜解)。",
            "输出: 结构化分析结论(≤500字), 交 modeler 承接。",
        ])
        text = _invoke_agent(agent_map["analyst"], brief)
        (root / "notes").mkdir(parents=True, exist_ok=True)
        (root / "notes" / f"{slug}-analyst.md").write_text(text, encoding="utf-8")
        return {"analyst_summary": text[:2000], "tier": decide_tier({**state, **common})}

    def node_modeler(state: AdaptivePipelineState) -> dict:
        root = _resolve_root(state)
        slug = _slug(state, root)
        tier = decide_tier({**state, **common})
        domain = str(state.get("domain_cartridge") or "")
        general_or = domain == "general_or" or domain == ""
        extra_lines: list[str] = []
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
        if tier == "A":
            focus = (
                "求解模式: 精确求解 (成熟算子 exact)。使用 CP-SAT/HiGHS/NetworkX 等，"
                "将可独立校验的解工件写入 SOLUTION_PATH="
                + str(root / "outputs" / f"{slug}-solution.json") + " "
                + "(schema 先行，proven_optimal 如实标记)。"
            )
        else:
            focus = (
                "求解模式: 下界 + 搜索 (bound + search)。先求精确界/松弛下界再做启发式搜索，"
                "将可独立校验的解工件写入 SOLUTION_PATH="
                + str(root / "outputs" / f"{slug}-solution.json") + " "
                + "(status=FEASIBLE 时如实报告 gap，严禁声称全局最优)。"
            )
        brief = _brief(state, root, slug, [
            "职责: 构建 schema.json、调用已注册求解器或编写受控沙箱求解脚本、产出真实解工件。",
            focus,
            "完成: 将可独立校验的解工件写入指定路径，回复仅给一句结果摘要+工件路径。",
            *extra_lines,
        ])
        text = _invoke_agent(agent_map["modeler"], brief)
        (root / "notes").mkdir(parents=True, exist_ok=True)
        (root / "notes" / f"{slug}-modeler.md").write_text(text, encoding="utf-8")
        artifact = root / "outputs" / f"{slug}-solution.json"
        ok = artifact.is_file()
        return {
            "modeler_summary": text[:2000],
            "solution_path": str(artifact) if ok else "",
            "model_retry_count": int(state.get("model_retry_count") or 0) + 1,
            "last_error": "" if ok else "modeler produced no solution artifact",
        }

    def node_validator(state: AdaptivePipelineState) -> dict:
        updates = run_deterministic_validator(state)
        if not updates.get("validation_ok"):
            updates["last_error"] = (
                updates.get("last_error")
                or "; ".join(updates.get("validator_errors") or [])[:400]
                or "validation failed"
            )
        # Detail-only keys (domain_audit / validator_took_sec) stay on disk
        return {
            k: v for k, v in updates.items()
            if k not in ("domain_audit", "validator_took_sec")
        }

    def node_table_render(state: AdaptivePipelineState) -> dict:
        try:
            return render_truth_tables(state)
        except Exception as exc:  # noqa: BLE001
            return {"tables_path": "", "last_error": f"table renderer failed: {type(exc).__name__}: {exc}"}

    def node_writer(state: AdaptivePipelineState) -> dict:
        root = _resolve_root(state)
        slug = _slug(state, root)
        tables = state.get("tables_path") or str(root / "outputs" / f"{slug}-tables.md")
        paper = root / "papers" / f"{slug}.md"
        obj = state.get("objective_value")
        prov = state.get("proven_optimal")
        brief = _brief(state, root, slug, [
            "职责: 严格基于预渲染真值表撰写六章学术论文 (docs/or-paper-sop.md)。",
            f"真值表唯一数据来源: {tables}",
            f"目标值(以校验器为准): objective={obj} proven_optimal={prov}"
            + (" (未证明最优，必须如实声明)" if not prov else ""),
            f"必须调用 export_paper_markdown 写入: PAPER_PATH={paper}",
        ])
        text = _invoke_agent(agent_map["writer"], brief)
        if not paper.is_file():
            paper.parent.mkdir(parents=True, exist_ok=True)
            paper.write_text(text or "# (writer produced no content)\n", encoding="utf-8")
        return {
            "paper_path": str(paper),
            "paper_retry_count": int(state.get("paper_retry_count") or 0) + 1,
            "last_error": "",
        }

    def node_doc_gate(state: AdaptivePipelineState) -> dict:
        return run_deterministic_doc_gate(state)

    def node_reviewer(state: AdaptivePipelineState) -> dict:
        root = _resolve_root(state)
        slug = _slug(state, root)
        paper = Path(state.get("paper_path") or (root / "papers" / f"{slug}.md"))
        review_path = root / "papers" / f"{slug}-review.md"
        brief = _brief(state, root, slug, [
            "职责: 扮演严苛同行审稿人，按十项核对表检查论文与解工件。",
            f"待审论文: {paper}",
            f"确定性校验结论: validation_ok={state.get('validation_ok')} proven_optimal={state.get('proven_optimal')}",
            f"必须调用 export_paper_markdown 写入评审报告: REVIEW_PATH={review_path}",
            "输出 FATAL/MAJOR/MINOR 分级缺陷与 Verdict (PASS/REVISE)。",
        ])
        text = _invoke_agent(agent_map["reviewer"], brief)
        if not review_path.is_file():
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_text(text or "# (reviewer produced no content)\n", encoding="utf-8")
        verdict, fatal = parse_review_reply(text)
        return {
            "review_path": str(review_path),
            "review_verdict": verdict,
            "fatal_defects": fatal,
            "reviewer_summary": text[:2000],
            "last_error": "",
        }

    def node_tier_c_focus(state: AdaptivePipelineState) -> dict:
        root = _resolve_root(state)
        slug = _slug(state, root)
        tier = decide_tier({**state, **common})
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
            text = _invoke_agent(agent_map["modeler"], brief)
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
                ledger[q] = {"ok": False, "objective": obj, "errors": (data.get("errors") or [])[:3]}
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

        last_err = ""
        if failed:
            last_err = f"tier-c subproblem(s) failed: {failed}"
        return {
            "subproblem_done": done,
            "ledger_path": str(ledger_path),
            "modeler_summary": "\n---\n".join(summaries)[:4000],
            "solution_path": str(root_out / f"{slug}-solution.json") if merged else "",
            "objective_value": merged.get("objective"),
            "model_retry_count": int(state.get("model_retry_count") or 0) + 1,
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
        (root / "notes" / f"{slug}-failure.md").write_text(
            json.dumps(
                {
                    "reason": reason,
                    "last_error": reason,
                    "fatal_defects": state.get("fatal_defects") or [],
                    "validator_errors": state.get("validator_errors") or [],
                    "doc_gate_errors": state.get("doc_gate_errors") or [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return {"last_error": reason}

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
        lambda s: "writer" if s.get("tables_path") else "fail_closed",
        {"writer": "writer", "fail_closed": "fail_closed"},
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
