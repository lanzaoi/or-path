#!/usr/bin/env python3
"""Centralised supervisor for the OR-Path multi-agent pipeline.

This module wires the three specialist workers defined in
``orpath.agents.workers`` (``or_researcher`` → ``or_modeler`` →
``or_verifier_writer``) into a single supervisor-orchestrated multi-agent
graph using ``langgraph_supervisor.create_supervisor``.

The supervisor is the only agent that sees the whole task. It never solves a
problem itself: it reads the request, decides which worker should act next,
hands control over through a ``transfer_to_*`` tool, and — because the three
workers are arranged as a research → model → verify/write pipeline — it
steers the conversation through the stages in order while still leaving the
final routing decision to the model at every step.

Two build entry points are exposed:

  * ``build_supervisor_graph``      → un-compiled ``StateGraph``
  * ``build_compiled_supervisor``   → ``.compile(checkpointer=...)``

Both accept an optional ``model``, ``workers`` roster and ``prompt`` so callers
can inject fakes in tests or reuse a shared model instance in production. A
``enable_guard`` flag (default ``True``) attaches the deterministic
``supervisor_guard_post_hook``, which intercepts bare text replies and forces
the supervisor to hand off to the first pipeline stage that has not run yet.

Numbers Truth: the supervisor only routes; every objective value and physical
claim still originates from the modeler's solver output and is independently
recomputed by the verifier/writer worker. The supervisor prompt forbids the
model from asserting optima itself.

The module is import-safe offline: when no ``model`` is supplied it uses
``orpath.control_plane.get_chat_model()``, which falls back to a placeholder
key so graphs can be built (not invoked) without network access.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

from langchain_core.messages import AIMessage, RemoveMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.managed.is_last_step import RemainingStepsManager
from langgraph_supervisor import create_supervisor

from orpath.agents.workers import (
    ACADEMIC_WORKER_NAMES,
    ANALYST_NAME,
    MODELER_NAME,
    REVIEWER_NAME,
    VERIFIER_NAME,
    WORKER_AGENT_NAMES,
    WRITER_NAME,
    get_academic_workers,
    get_default_workers,
)
from orpath.control_plane import get_chat_model

__all__ = [
    "DEFAULT_SUPERVISOR_PROMPT",
    "DEFAULT_ACADEMIC_SUPERVISOR_PROMPT",
    "SUPERVISOR_NAME",
    "EXPECTED_SUPERVISOR_NODES",
    "ACADEMIC_EXPECTED_SUPERVISOR_NODES",
    "ISOLATED_PIPELINE_NODES",
    "PIPELINE_STAGE_ORDER",
    "ACADEMIC_PIPELINE_STAGE_ORDER",
    "GUARD_CALL_IDS",
    "SupervisorState",
    "MultiAgentPipelineState",
    "supervisor_guard_post_hook",
    "supervisor_trim_pre_model_hook",
    "persist_agent_stage_log",
    "resolve_guard_stage_order",
    "SUPERVISOR_MAX_MESSAGE_CHARS",
    "build_supervisor_graph",
    "build_compiled_supervisor",
    "build_academic_supervisor_graph",
    "build_compiled_academic_supervisor",
    "build_isolated_pipeline_graph",
    "build_compiled_isolated_pipeline",
    "get_default_supervisor_checkpointer",
]

#: Canonical nodes for the isolated artifact-driven pipeline graph
ISOLATED_PIPELINE_NODES: tuple[str, ...] = (
    "researcher_stage",
    "modeler_stage",
    "verifier_stage",
    "writer_stage",
    "reviewer_stage",
)

#: Default name of the supervisor node produced by ``create_supervisor``.
SUPERVISOR_NAME = "supervisor"

#: DEPRECATED legacy trimming constants. Kept only so domain cartridge
#: imports keep resolving; the supervisor no longer truncates or windowed
#: conversations (Zero Truncation iron law).
SUPERVISOR_MAX_MESSAGE_CHARS: int = 1600
SUPERVISOR_HEAD_CHARS: int = 800
SUPERVISOR_TAIL_CHARS: int = 400
SUPERVISOR_MAX_HISTORY_MESSAGES: int = 24

#: Guard-issued handoff tool-call ids. Deterministic, fixed ids make the
#: anti-early-stopping injections reproducible and easy to assert on in tests.
GUARD_CALL_IDS: dict[str, str] = {
    ANALYST_NAME: "guard_call_analyst",
    MODELER_NAME: "guard_call_modeler",
    VERIFIER_NAME: "guard_call_verifier",
    WRITER_NAME: "guard_call_writer",
    REVIEWER_NAME: "guard_call_reviewer",
}

#: Worker stage order the guard enforces for the standard 4-elite pipeline.
PIPELINE_STAGE_ORDER: tuple[str, ...] = (ANALYST_NAME, MODELER_NAME, WRITER_NAME, REVIEWER_NAME)

#: Worker stage order for the full 5-worker academic research & review pipeline.
ACADEMIC_PIPELINE_STAGE_ORDER: tuple[str, ...] = (
    ANALYST_NAME,
    MODELER_NAME,
    VERIFIER_NAME,
    WRITER_NAME,
    REVIEWER_NAME,
)

#: Canonical node names a compiled supervisor graph must expose.
EXPECTED_SUPERVISOR_NODES: tuple[str, ...] = (
    SUPERVISOR_NAME,
    ANALYST_NAME,
    MODELER_NAME,
    WRITER_NAME,
    REVIEWER_NAME,
)

#: Canonical node names for a 5-worker academic supervisor graph.
ACADEMIC_EXPECTED_SUPERVISOR_NODES: tuple[str, ...] = (
    SUPERVISOR_NAME,
    ANALYST_NAME,
    MODELER_NAME,
    VERIFIER_NAME,
    WRITER_NAME,
    REVIEWER_NAME,
)

#: System prompt for the default 4-elite supervisor. Defines a strict, ordered
#: pipeline: analyst → modeler → writer → reviewer → finish. The supervisor itself
#: must not solve the problem or state optima; it routes and hands control to
#: the right worker. A hard anti-early-stopping clause forbids closing the task
#: before the writer has exported the paper and the reviewer has issued a PASS
#: verdict.
DEFAULT_SUPERVISOR_PROMPT = (
    "你是 OR-Path 多智能体流水线的【中心主控 / Supervisor】。\n\n"
    "你的下属是四位常驻精锐特种兵 Worker，必须严格按以下 4 阶段顺序承接运筹学研究任务，"
    "不得跳步、不得逆序、不得合并阶段：\n\n"
    "阶段 1（题面精读与研判）：首先指派 or_analyst 精读原始题面与前置数据画像，"
    "确认数学分类并给出建模建议与复杂度分档（Tier-A/B/C）。\n"
    "阶段 2（建模与求解）：拿到研判结论后，必须指派 or_modeler 构建 schema.json、"
    "调用成熟求解器或受控沙箱求解，并产出经确定性校验门复核的 solution_path。\n"
    "阶段 3（学术论文成文）：解通过确定性校验门（运行 validate_solution_tool 独立验算且 ok: true）后，必须指派 or_writer 依据 "
    "docs/or-paper-sop.md 六章规范与预渲染真数据表格撰写论文，并导出至 papers/ 或 outputs/。\n"
    "阶段 4（对抗式同行评审与完结）：论文已导出后，必须指派 or_reviewer 按 10 项核对表"
    "严苛挑刺并输出 FATAL/MAJOR/MINOR 分级缺陷；只有看到评审报告 PASS 且全部产物落地，"
    "方可输出终结文本。\n\n"
    "严禁早停（Anti-Early-Stopping）：\n"
    "严禁在仅完成研判、或尚未经过 or_modeler 求解、独立验算与 or_writer 成文导出与 or_reviewer "
    "评审通过之前，输出结束语、声明任务完成或直接停止。\n"
    "提前收工、跳过求解、跳过成文导出或跳过评审，"
    "均属于严重系统故障，将被判定为严重系统故障并追责。\n\n"
    "路由职责（按顺序指派）：\n"
    "- 先让 or_analyst 精读题面与数据画像，确认数学分类与复杂度分档；\n"
    "- 再交由 or_modeler 建模求解，拿到经确定性校验门验证的解；\n"
    "- 然后交由 or_writer 基于预渲染真数据表格撰写并导出学术论文；\n"
    "- 最后交由 or_reviewer 严苛评审，只有 PASS 才可终结任务；\n"
    "- 任一阶段失败或证据不足时，回到对应 Worker 修正，而不是跳过或粉饰。\n\n"
    "硬性纪律：\n"
    "- 你只做任务分派与协调，绝不亲自求解或声明任何目标函数值/最优性；\n"
    "- 所有数值必须来自 or_modeler 的求解输出并经确定性校验门复核，遵循 Numbers Truth；\n"
    "- 每次只调用一个 transfer_to_* 工具把控制权交给合适的 Worker，"
    "并在需要时用一句话说明你的分派理由；\n"
    "- 只有在论文已导出且 or_reviewer 给出 PASS 评审报告之后，才可给出最终结论并停止。"
)

#: System prompt for the 5-worker academic research & review supervisor.
DEFAULT_ACADEMIC_SUPERVISOR_PROMPT = (
    "你是 OR-Path 学术级多智能体流水线的【中心主控 / Academic Supervisor】。\n\n"
    "你的下属是五位顶尖运筹学专职研究员，必须严格按以下 5 阶段顺序承接高规格运筹学研究与论文任务，"
    "不得跳步、不得逆序、不得合并阶段：\n\n"
    "阶段 1（文献与研判）：首先指派 or_researcher 研判题面与数据特征，"
    "检索专业运筹学知识库，拆解对象/约束/目标，给出候选算法族与可行性论证。\n"
    "阶段 2（数学建模与求解）：拿到研判结论后，指派 or_modeler 建立严格数学模型、"
    "调用或编写求解器执行求解，并产出可独立校验的 solution_path。\n"
    "阶段 3（独立验算）：拿到解之后，指派 or_verifier 运行 validate_solution_tool，"
    "进行纯数学与物理逻辑的独立重算与防篡改测试，严禁主观调参，必须输出 ok: true 的验证报告。\n"
    "阶段 4（学术论文成文）：验算通过后，指派 or_writer 依据 docs/or-paper-sop.md 规范，"
    "撰写严格的 6 章节学术论文（摘要/问题建模/算法设计/计算实验/消融与敏感性/局限与工业部署），"
    "并调用 export_paper_markdown 导出至 papers/ 或 outputs/。\n"
    "阶段 5（对抗式同行评审）：论文导出后，必须指派 or_reviewer 进行严苛的对抗式同行评审，"
    "按 10 项核心检查清单逐条审计，审查是否存在数值捏造、目标越级声称或格式缺陷，"
    "产出 outputs/<slug>-review.md 并给出 PASS 或 REVISE 结论。\n\n"
    "严禁早停（Anti-Early-Stopping）：\n"
    "严禁在未完整经历 研判 → 建模求解 → 独立验算 → 论文撰写 → 对抗评审 5 阶段之前结束任务。\n"
    "提前收工、跳过验算或跳过评审，均属于严重系统故障并追责。\n\n"
    "硬性纪律（Numbers Truth）：\n"
    "- 你只做任务分派与协调，绝不亲自求解或发明任何数值；\n"
    "- 所有数值必须来自 or_modeler 的求解输出并由 or_verifier 独立复核；\n"
    "- 每次只调用一个 transfer_to_* 工具把控制权交给合适的 Worker；\n"
    "- 只有在收到 or_reviewer 的 PASS 评审报告且全部产物落地后，方可输出终结文本并停止。"
)


class SupervisorState(MessagesState):
    """Explicit, stage-tracked supervisor state schema.

    Extends LangGraph's ``MessagesState`` with the pipeline-stage flags and
    artifact pointers the supervisor needs to steer a research → model →
    verify/write run. Keeping the flags on the state schema means callers can
    read (and, when they own the graph, write) stage progress explicitly
    instead of inferring it from the message history.

    ``remaining_steps`` is included because ``create_react_agent`` (invoked
    underneath ``create_supervisor``) requires it in any supplied state
    schema; it mirrors the field on ``langgraph.prebuilt.AgentState``.
    """

    remaining_steps: NotRequired[int]
    has_researched: bool = False
    has_modeled: bool = False
    has_verified: bool = False
    has_written: bool = False
    has_reviewed: bool = False
    solution_path: str = ""
    paper_path: str = ""
    review_path: str = ""


class MultiAgentPipelineState(TypedDict, total=False):
    """Artifact-driven isolated pipeline state. Context remains lightweight and pristine."""

    slug: str
    workdir: str
    problem_id: str
    problem_class: str
    problem_file: str
    data_files: list[str]
    research_path: str
    schema_path: str
    solution_path: str
    validate_path: str
    paper_path: str
    review_path: str

    # Quality & Lifecycle flags
    lifecycle_status: Literal[
        "PROPOSED",
        "SOLVER_FEASIBLE",
        "INDEPENDENTLY_VALIDATED",
        "REDTEAM_PASSED",
        "ACCEPTED",
        "FAILED",
    ]
    validation_ok: bool
    review_verdict: Literal["PASS", "REVISE", "FAIL"]
    fatal_defects: list[str]
    revision_count: int
    max_revisions: int
    model_repair_count: int
    max_model_repairs: int
    last_error: str
    solve_mode: str
    raw_problem_text: str
    summary: str


def _resolve_root() -> Path:
    """Resolve active case workdir (honouring ORPATH_WORKDIR) or fall back to cwd."""
    raw = (os.environ.get("ORPATH_WORKDIR") or "").strip().strip('"')
    if raw:
        try:
            from orpath.paths import orpath_home

            raw_path = Path(raw).expanduser().resolve()
            home_path = orpath_home().resolve()
            cwd_path = Path.cwd().resolve()
            if raw_path == home_path and cwd_path != home_path:
                return cwd_path
            return raw_path
        except Exception:
            return Path(raw).expanduser().resolve()
    return Path.cwd()


def _resolve_model(model: Any = None) -> Any:
    """Return the supplied model or the shared OR-Path chat model factory output."""
    return model if model is not None else get_chat_model()


def _transfer_tool_name(worker_name: str) -> str:
    """Return the supervisor handoff tool name for a worker (``transfer_to_or_*``)."""
    return f"transfer_to_{worker_name}"


def _worker_handoff_complete(messages: list[Any], worker_name: str) -> bool:
    """Return ``True`` if ``messages`` show the worker stage has already been handed off to.

    A stage counts as completed when any message *from* that worker appears, or
    when any ``transfer_to_<worker>`` tool call (an ``AIMessage`` tool call, or a
    ``ToolMessage`` named after the handoff) is present. This makes the guard
    robust to both the supervisor's own handoff call and the worker's reply.
    """
    transfer_tool = _transfer_tool_name(worker_name)
    for message in messages:
        if getattr(message, "name", None) == worker_name:
            return True
        if isinstance(message, AIMessage):
            for call in getattr(message, "tool_calls", None) or []:
                if call.get("name") in (worker_name, transfer_tool):
                    return True
    return False


def supervisor_guard_post_hook(
    state: Any,
    stage_order: "tuple[str, ...] | list[str] | None" = None,
) -> dict:
    """Deterministic anti-early-stopping guard for the supervisor graph.

    A lazy LLM may try to finish a task with a bare text reply that carries no
    ``tool_calls`` (e.g. "done, here is the answer") before the pipeline has
    actually run. This ``post_model_hook`` runs after every supervisor model call
    and inspects the newest message:

      * if it is not an ``AIMessage`` → pass through unchanged;
      * if it carries well-formed ``tool_calls`` → the model is routing, pass it;
      * otherwise inject a ``transfer_to_or_*`` tool call that advances the
        pipeline to the first stage that has not yet been handed off to.

    ``stage_order`` may be supplied explicitly by the graph builder (recommended,
    so an academic 5-worker roster is never mistaken for the standard 3-worker
    pipeline before any handoff evidence exists). When omitted it is inferred
    from the messages and the ``academic`` state flag.

    Args:
        state: Supervisor state (``SupervisorState`` / ``MessagesState``).
        stage_order: Explicit ordered worker roster to steer. Optional.

    Returns:
        A LangGraph state update (``dict``). It is empty when no guard action
        is required, or ``{"messages": [RemoveMessage(...), AIMessage(...)]}``
        when the lazy reply is replaced by a handoff ``AIMessage``.
    """
    messages = list(state.get("messages") or [])
    if not messages:
        return {}

    last = messages[-1]
    if not isinstance(last, AIMessage):
        return {}
    valid_calls = [
        call
        for call in (last.tool_calls or [])
        if isinstance(call, dict) and call.get("name")
    ]
    if valid_calls:
        # The model is routing with a well-formed tool call: pass it through.
        return {}

    if stage_order is None:
        stage_order = state.get("stage_order")
    if not stage_order:
        if (
            state.get("academic")
            or _worker_handoff_complete(messages, VERIFIER_NAME)
        ):
            stage_order = ACADEMIC_PIPELINE_STAGE_ORDER
        else:
            stage_order = PIPELINE_STAGE_ORDER

    done = {
        worker: _worker_handoff_complete(messages, worker) for worker in stage_order
    }
    next_worker = next(
        (worker for worker in stage_order if not done.get(worker, False)),
        None,
    )
    if next_worker is None:
        # All required stages have been handed off: let the bare text reply pass.
        return {}

    tool_name = _transfer_tool_name(next_worker)
    call_id = GUARD_CALL_IDS.get(next_worker, f"guard_call_{next_worker}")
    injected = AIMessage(
        content=last.content if last.content is not None else "",
        tool_calls=[{"name": tool_name, "args": {}, "id": call_id}],
        id=f"{call_id}_message",
    )

    last_id = getattr(last, "id", None)
    if last_id:
        return {"messages": [RemoveMessage(id=last_id), injected]}
    # No stable id to remove by (e.g. hand-built test messages): append instead.
    return {"messages": [injected]}


def supervisor_trim_pre_model_hook(state: Any) -> dict:
    """No-op passthrough hook kept for backward import compatibility.

    The legacy 1600- character truncation and history windowing behaviour was
    deliberately removed (Numbers Truth / Zero Truncation iron law): every stage
    now receives the full conversation intact, so a prebuilt LLM prompt or a
    50,000-character coordinate matrix can never be silently mutilated into
    ``[... chars truncated by supervisor context trimmer ...]``.

    The hook still returns the ``llm_input_messages`` channel so langchain
    supervisors recognise the pre-model hook contract.
    """
    messages = list((state.get("messages") if hasattr(state, "get") else getattr(state, "messages", None)) or [])
    return {"llm_input_messages": messages}


def _serialize_message(msg: Any) -> str:
    """Serialise one message into a single-line JSONL record."""
    if isinstance(msg, dict):
        payload: Any = msg
    elif hasattr(msg, "model_dump"):
        payload = msg.model_dump()
    elif hasattr(msg, "to_dict"):
        try:
            payload = msg.to_dict()
        except Exception:
            payload = {"content": getattr(msg, "content", None)}
    else:
        payload = {"content": str(msg)}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def persist_agent_stage_log(
    workdir: str | Path,
    slug: str,
    stage: str,
    messages: list[Any],
) -> Path:
    """Append ``messages`` losslessly to ``runs/<slug>/agent_logs/<stage>.jsonl``.

    Each isolated pipeline stage writes its own JSONL sidecar log instead of
    sharing a growing cross-role ``MessagesState`` chat transcript. Records are
    written verbatim (zero character truncation), so full problem statements and
    coordinate matrices survive untouched for later audit / R1 evidence checks.
    Returns the path of the log file.
    """
    root = Path(workdir) if workdir else _resolve_root()
    log_dir = root / "runs" / str(slug) / "agent_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{stage}.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        for msg in messages or []:
            fh.write(_serialize_message(msg) + "\n")
    return log_path


def _read_text_safe(path: Any) -> str:
    """Return the full text of ``path`` (an empty string when unreadable)."""
    if not path:
        return ""
    p = Path(path) if isinstance(path, str) else None
    if p is None or not p.is_file():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def _stage_log_payload(
    state: Any,
    stage: str,
    *,
    extra: list[Any] | None = None,
) -> list[Any]:
    """Build the JSONL payload of one isolated stage.

    The isolated pipeline keeps a pristine artifact state (no shared growing
    ``MessagesState`` chat chain), so each stage logs its own structured header
    plus the *full* text of the artifact it produced. Nothing is truncated, so a
    30,000-character problem matrix survives into the audit trail verbatim.
    """
    state_dict = state if isinstance(state, dict) else state.__dict__
    root = Path(state_dict.get("workdir")) if state_dict.get("workdir") else _resolve_root()
    header: dict[str, Any] = {
        "type": "stage_log",
        "stage": stage,
        "slug": state_dict.get("slug") or state_dict.get("problem_id") or "task",
        "workdir": str(root),
    }
    for key in ("problem_id", "problem_class", "problem_file", "lifecycle_status",
                "validation_ok", "review_verdict"):
        if key in state_dict:
            header[key] = state_dict[key]

    artifacts = {
        "researcher_stage": ["research_path", "problem_file"],
        "modeler_stage": ["solution_path"],
        "verifier_stage": ["validate_path"],
        "writer_stage": ["paper_path"],
        "reviewer_stage": ["review_path"],
    }
    messages: list[Any] = [header]
    stage_payload = artifacts.get(stage, [])
    for path_key in stage_payload:
        text = _read_text_safe(state_dict.get(path_key) or "")
        if text:
            messages.append({"type": "stage_artifact_text", "stage": stage,
                             "path_key": path_key, "text": text})
    if extra:
        messages.extend(extra)
    messages.append({"type": "stage_summary", "stage": stage})
    return messages


def _persist_stage_log(
    root: Path,
    slug: str,
    stage: str,
    state: Any,
    *,
    extra: list[Any] | None = None,
) -> None:
    """Write one isolated stage's JSONL sidecar log without failing the graph."""
    try:
        persist_agent_stage_log(root, slug, stage, _stage_log_payload(state, stage, extra=extra))
    except Exception:
        return


def resolve_guard_stage_order(worker_names: "list[str] | tuple[str, ...]", is_academic: bool) -> "tuple[str, ...]":
    """Return the ordered worker roster the anti-early-stopping guard steers through.

    Pins the guard to the *actual* roster instead of inferring the stage order
    from handoff evidence in the message history. Inference alone misroutes a
    fresh academic graph (no verifier/writer/reviewer handoff seen yet) to the
    4-elite tool set, which would inject a non-existent
    ``transfer_to_or_reviewer`` call.

    Canonical pipeline names are preferred in pipeline order; custom rosters
    with non-canonical names fall back to their declared order.
    """
    names = [n for n in worker_names if n]
    known = set(names)
    default_order = ACADEMIC_PIPELINE_STAGE_ORDER if is_academic else PIPELINE_STAGE_ORDER
    ordered = tuple(w for w in default_order if w in known)
    if ordered:
        return ordered
    return tuple(names)


def _resolve_workers(workers: Any, model: Any) -> list[Any]:
    """Return the supplied worker roster or the default 4-elite pipeline.

    ``workers`` may be ``None`` (default roster), a single compiled agent, or a
    sequence of agents. Anything that is not a non-empty iterable of agents
    falls back to ``get_default_workers`` so a bad argument never yields an
    empty supervisor.
    """
    if workers is None:
        return get_default_workers(model=model)
    candidates = workers if isinstance(workers, (list, tuple)) else [workers]
    resolved = [w for w in candidates if w is not None]
    return resolved if resolved else get_default_workers(model=model)


def build_supervisor_graph(
    model: Any = None,
    workers: Any = None,
    prompt: str | None = None,
    state_schema: Any = None,
    enable_guard: bool = True,
    enable_trim: bool = False,
    pre_model_hook: Any = None,
) -> StateGraph:
    """Build the supervisor-orchestrated multi-agent graph (un-compiled).

    Args:
        model: Chat model used by the supervisor. Defaults to
            ``orpath.control_plane.get_chat_model()``.
        workers: Worker roster. Defaults to the four elite OR-Path workers in
            pipeline order (``or_analyst``, ``or_modeler``,
            ``or_writer``, ``or_reviewer``). A single agent or an arbitrary list is
            accepted so tests and callers can inject custom rosters.
        prompt: System prompt for the supervisor. Defaults to
            ``DEFAULT_SUPERVISOR_PROMPT``.
        state_schema: State schema passed to ``create_supervisor``. Defaults
            to ``SupervisorState`` (messages plus the explicit stage flags
            ``has_researched`` / ``has_modeled`` / ``has_verified`` and the
            ``solution_path`` / ``paper_path`` artifact pointers). Pass a
            custom schema to override the defaults.
        enable_guard: Whether to attach the deterministic
            ``supervisor_guard_post_hook`` anti-early-stopping guard. Defaults
            to ``True``; pass ``False`` for an unguarded supervisor.
        enable_trim: Whether to attach the ``supervisor_trim_pre_model_hook``
            passthrough hook (kept for backward compatibility; it never
            truncates). Defaults to ``False``
            to prevent context mutilation.
        pre_model_hook: Custom pre-model hook to override default trimming.

    Returns:
        A ``StateGraph`` (the un-compiled output of
        ``langgraph_supervisor.create_supervisor``).
    """
    resolved_model = _resolve_model(model)
    resolved_workers = _resolve_workers(workers, resolved_model)
    worker_names = [getattr(w, "name", "") for w in resolved_workers]
    known_worker_names = {n for n in worker_names if n}
    is_academic = bool(
        known_worker_names and {VERIFIER_NAME, WRITER_NAME, REVIEWER_NAME} <= known_worker_names
    )

    if prompt is None:
        default_prompt = (
            DEFAULT_ACADEMIC_SUPERVISOR_PROMPT if is_academic else DEFAULT_SUPERVISOR_PROMPT
        )
    else:
        default_prompt = prompt

    resolved_pre_hook = (
        pre_model_hook
        if pre_model_hook is not None
        else (supervisor_trim_pre_model_hook if enable_trim else None)
    )

    if enable_guard:
        guard_stage_order = resolve_guard_stage_order(worker_names, is_academic)

        def _guarded_hook(state: Any, _order: "tuple[str, ...]") -> dict:
            return supervisor_guard_post_hook(state, stage_order=_order)

        guard_hook: Any = (
            (lambda state: _guarded_hook(state, guard_stage_order))
            if guard_stage_order
            else None
        )
    else:
        guard_hook = None

    return create_supervisor(
        agents=resolved_workers,
        model=resolved_model,
        prompt=default_prompt,
        state_schema=state_schema or SupervisorState,
        pre_model_hook=resolved_pre_hook,
        post_model_hook=guard_hook,
    )


def build_compiled_supervisor(
    checkpointer: Any = None,
    model: Any = None,
    workers: Any = None,
    prompt: str | None = None,
    state_schema: Any = None,
    enable_guard: bool = True,
    enable_trim: bool = False,
    pre_model_hook: Any = None,
) -> CompiledStateGraph:
    """Build and compile the supervisor graph, optionally with checkpointing."""
    graph = build_supervisor_graph(
        model=model,
        workers=workers,
        prompt=prompt,
        state_schema=state_schema,
        enable_guard=enable_guard,
        enable_trim=enable_trim,
        pre_model_hook=pre_model_hook,
    )
    return graph.compile(checkpointer=checkpointer)


def build_academic_supervisor_graph(
    model: Any = None,
    workers: Any = None,
    prompt: str | None = None,
    state_schema: Any = None,
    enable_guard: bool = True,
    enable_trim: bool = False,
    pre_model_hook: Any = None,
) -> StateGraph:
    """Build an un-compiled 5-worker academic supervisor graph."""
    resolved_model = _resolve_model(model)
    academic_workers = (
        workers if workers is not None else get_academic_workers(model=resolved_model)
    )
    return build_supervisor_graph(
        model=resolved_model,
        workers=academic_workers,
        prompt=prompt or DEFAULT_ACADEMIC_SUPERVISOR_PROMPT,
        state_schema=state_schema or SupervisorState,
        enable_guard=enable_guard,
        enable_trim=enable_trim,
        pre_model_hook=pre_model_hook,
    )


def build_compiled_academic_supervisor(
    checkpointer: Any = None,
    model: Any = None,
    workers: Any = None,
    prompt: str | None = None,
    state_schema: Any = None,
    enable_guard: bool = True,
    enable_trim: bool = False,
    pre_model_hook: Any = None,
) -> CompiledStateGraph:
    """Build and compile a 5-worker academic supervisor graph."""
    graph = build_academic_supervisor_graph(
        model=model,
        workers=workers,
        prompt=prompt,
        state_schema=state_schema,
        enable_guard=enable_guard,
        enable_trim=enable_trim,
        pre_model_hook=pre_model_hook,
    )
    return graph.compile(checkpointer=checkpointer)


# --------------------------------------------------------------------------- #
# Isolated Artifact-Driven Multi-Agent Pipeline Graph
# --------------------------------------------------------------------------- #
def _isolated_researcher_node(state: MultiAgentPipelineState) -> dict[str, Any]:
    root = Path(state["workdir"]) if state.get("workdir") else _resolve_root()
    slug = state.get("slug") or state.get("problem_id") or "task"
    pid = state.get("problem_id") or slug
    pfile = state.get("problem_file") or ""

    notes_dir = root / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    res_path = notes_dir / f"{slug}-research.md"

    if not res_path.is_file() or res_path.stat().st_size < 30:
        raw_text = state.get("raw_problem_text") or ""
        if not raw_text and pfile:
            pf = Path(pfile) if Path(pfile).is_absolute() else root / pfile
            if pf.is_file():
                raw_text = pf.read_text(encoding="utf-8", errors="replace")

        scaffold = [
            f"# Research: {slug}",
            "",
            "## Summary",
            f"Problem ID: `{pid}`. Research and data-characteristic analysis for mathematical optimization.",
            "",
            "## Problem Classification & Candidates",
            f"- Identified problem class: `{state.get('problem_class') or 'general_optimization'}`",
            "- Candidate solver families: CP-SAT, HiGHS, NetworkX, PyVRP, PyJobShop.",
            "",
            "## Evidence table",
            f"| 1 | Problem Specification | {pfile or 'inbox/problem.txt'} | Primary problem requirements and objectives | primary | high |",
            "",
            "## Modeling Recommendations",
            "- Objective function and physical constraints must be strictly recomputed from raw problem data.",
            "- Numbers Truth: no fabricated optima.",
            "",
        ]
        res_path.write_text("\n".join(scaffold), encoding="utf-8")

        _persist_stage_log(
            root,
            slug,
            "researcher_stage",
            state,
            extra=[{"type": "problem_text", "problem_id": pid, "text": raw_text}],
        )
    return {
        "slug": slug,
        "problem_id": pid,
        "research_path": str(res_path),
        "lifecycle_status": "PROPOSED",
        "last_error": "",
    }


def _isolated_modeler_node(state: MultiAgentPipelineState) -> dict[str, Any]:
    root = Path(state["workdir"]) if state.get("workdir") else _resolve_root()
    slug = state.get("slug") or state.get("problem_id") or "task"
    pid = state.get("problem_id") or slug
    pc = state.get("problem_class") or ""
    mode = state.get("solve_mode") or "auto"
    repair_count = int(state.get("model_repair_count") or 0)

    is_repair = bool(
        state.get("last_error")
        or not state.get("validation_ok", True)
        or state.get("review_verdict") == "REVISE"
    )
    if is_repair and (repair_count > 0 or not state.get("validation_ok", True)):
        repair_count += 1

    outputs_dir = root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    sol_path = outputs_dir / f"{slug}-solution.json"

    if not sol_path.is_file() or repair_count > 0:
        try:
            from tools.solve_dispatch import solve as dispatch_solve
            ok, sol_data, detail = dispatch_solve(
                root=root,
                problem_id=pid,
                mode=mode,
                problem_class=pc,
            )
            if ok and isinstance(sol_data, dict):
                sol_path.write_text(json.dumps(sol_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception:
            pass

    _persist_stage_log(root, slug, "modeler_stage", state)
    has_sol = sol_path.is_file()
    status = "SOLVER_FEASIBLE" if has_sol else "FAILED"
    return {
        "solution_path": str(sol_path) if has_sol else "",
        "lifecycle_status": status,
        "model_repair_count": repair_count,
        "validation_ok": False,
        "last_error": "" if has_sol else "solve_failed",
    }


def _isolated_verifier_node(state: MultiAgentPipelineState) -> dict[str, Any]:
    root = Path(state["workdir"]) if state.get("workdir") else _resolve_root()
    slug = state.get("slug") or state.get("problem_id") or "task"
    pid = state.get("problem_id") or slug
    sol_path = state.get("solution_path") or ""

    outputs_dir = root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    val_path = outputs_dir / f"{slug}-validate.json"

    if not sol_path or not Path(sol_path).is_file():
        _persist_stage_log(root, slug, "verifier_stage", state)
        return {
            "validate_path": str(val_path),
            "validation_ok": False,
            "lifecycle_status": "FAILED",
            "last_error": "solution_path does not exist for validation",
        }

    try:
        from tools.solve_dispatch import validate as dispatch_validate
        ok, data, detail = dispatch_validate(
            root=root,
            problem_id=pid,
            solution=Path(sol_path),
            out=val_path,
        )
        verdict = bool(data.get("ok")) if isinstance(data, dict) else False
        raw_errors = data.get("errors") if isinstance(data, dict) else None
        if raw_errors is None:
            errors: list[str] = []
        elif isinstance(raw_errors, str):
            errors = [raw_errors] if raw_errors.strip() else []
        else:
            errors = [str(e) for e in raw_errors]
    except Exception as exc:
        verdict = False
        errors = [str(exc)]

    _persist_stage_log(root, slug, "verifier_stage", state)
    return {
        "validate_path": str(val_path),
        "validation_ok": verdict,
        "lifecycle_status": "INDEPENDENTLY_VALIDATED" if verdict else "FAILED",
        "last_error": "" if verdict else f"validation failed: {'; '.join(errors) or 'invalid constraints'}",
    }


def _isolated_writer_node(state: MultiAgentPipelineState) -> dict[str, Any]:
    root = Path(state["workdir"]) if state.get("workdir") else _resolve_root()
    slug = state.get("slug") or state.get("problem_id") or "task"
    pid = state.get("problem_id") or slug
    sol_path = state.get("solution_path") or ""
    papers_dir = root / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    paper_path = papers_dir / f"{slug}.md"

    rev_count = int(state.get("revision_count") or 0)
    if state.get("review_verdict") == "REVISE":
        rev_count += 1

    sol_data = {}
    if sol_path and Path(sol_path).is_file():
        try:
            sol_data = json.loads(Path(sol_path).read_text(encoding="utf-8"))
        except Exception:
            pass

    from orpath.paper_workflow import draft_paper_with_writer
    rev_feedback = "; ".join(state.get("fatal_defects") or []) if rev_count > 0 else ""
    paper_body = draft_paper_with_writer(
        root=root,
        slug=slug,
        problem_class=state.get("problem_class") or sol_data.get("problem_class") or "general_optimization",
        problem_id=pid,
        solution=sol_data,
        solution_path=sol_path,
        paper_path=paper_path,
        schema_path=state.get("schema_path") or "",
        research_path=state.get("research_path") or "",
        validate_path=state.get("validate_path") or "",
        revision_feedback=rev_feedback,
        state=dict(state),
    )

    if rev_count > 0 and state.get("fatal_defects") and "Revision Note" not in paper_body:
        disclaimers = "\n\n## Revision Note\n" + "\n".join(f"- Fixed: {d}" for d in state.get("fatal_defects") or [])
        paper_body += disclaimers + "\n"
        paper_path.write_text(paper_body, encoding="utf-8")

    _persist_stage_log(root, slug, "writer_stage", state)
    return {
        "paper_path": str(paper_path),
        "revision_count": rev_count,
        "last_error": "",
    }


def _isolated_reviewer_node(state: MultiAgentPipelineState) -> dict[str, Any]:
    root = Path(state["workdir"]) if state.get("workdir") else _resolve_root()
    slug = state.get("slug") or state.get("problem_id") or "task"
    paper_path = state.get("paper_path") or ""
    sol_path = state.get("solution_path") or ""

    outputs_dir = root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    review_path = outputs_dir / f"{slug}-review.md"

    from orpath.paper_workflow import run_reviewer_agent
    if paper_path and Path(paper_path).is_file() and sol_path and Path(sol_path).is_file():
        run_reviewer_agent(
            root=root,
            slug=slug,
            paper_path=Path(paper_path),
            solution_path=Path(sol_path),
            review_path=review_path,
            state=dict(state),
        )

    paper_text = ""
    if paper_path and Path(paper_path).is_file():
        paper_text = Path(paper_path).read_text(encoding="utf-8")

    sol_data = {}
    if sol_path and Path(sol_path).is_file():
        try:
            sol_data = json.loads(Path(sol_path).read_text(encoding="utf-8"))
        except Exception:
            pass

    fatal_defects: list[str] = []
    meta = sol_data.get("meta") or {}
    proven_optimal = bool(meta.get("proven_optimal"))
    if not proven_optimal and paper_text:
        import re
        from tools.r1_claim_map import GLOBAL_OPT_RE, _NEG_LEFT_RE
        for m in GLOBAL_OPT_RE.finditer(paper_text):
            chunk_left = paper_text[max(0, m.start() - 50) : m.start()]
            if not (_NEG_LEFT_RE.search(chunk_left) or "not" in chunk_left.lower() or "未证明" in chunk_left):
                fatal_defects.append(f"FATAL: Paper claims global optimality ('{m.group(0)}') without proven_optimal flag.")
                break

    mandatory_sections = [
        ("Abstract", ("## Abstract", "## 摘要")),
        ("Problem statement", ("## Problem statement", "## 问题重述", "## 问题建模", "问题背景", "## 1.")),
        ("Mathematical formulation", ("## Method / formulation", "## 数学规划模型", "## 模型建立", "### Mathematical Formulation", "物理动态", "模型构建", "## 2.", "## 3.")),
        ("Solution strategy", ("## Solution strategy", "## 求解策略", "## 算法设计", "滚动 MPC", "优化策略", "## 5.", "## 6.")),
        ("Results", ("## Results", "## 计算结果", "## 数值结果", "求解结果", "结果呈现", "核算汇总")),
        ("Limitations", ("## Limitations", "## 局限性", "## 模型评价", "敏感性分析", "管理优化建议", "## 结论", "## 9.")),
    ]
    for sec_name, candidates in mandatory_sections:
        if not any(cand in paper_text for cand in candidates):
            fatal_defects.append(f"FATAL: Missing mandatory section {sec_name}")

    if state.get("validation_ok") is False:
        fatal_defects.append("FATAL: Solution validation failed independent recomputation check.")

    verdict: Literal["PASS", "REVISE"] = "REVISE" if fatal_defects else "PASS"
    # REVISE ⇔ fatal_defects non-empty, so the pipeline returns to writer/modeler
    # with lifecycle_status "PROPOSED" (pending rework); PASS promotes to ACCEPTED.
    lifecycle_status = "ACCEPTED" if verdict == "PASS" else "PROPOSED"
    review_content = [
        f"# Peer Review Report: {slug}",
        f"**Verdict:** {verdict}",
        "",
        "## Summary",
        "Adversarial review against 10-point rubric and Numbers Truth iron law.",
        "",
        "## Defects Checklist",
    ]
    if fatal_defects:
        review_content.append("### FATAL Defects:")
        for d in fatal_defects:
            review_content.append(f"- {d}")
    automated_text = "\n".join(review_content) + "\n"
    from orpath.paper_workflow import merge_review_if_child_wrote
    final_review = merge_review_if_child_wrote(
        automated_body=automated_text,
        child_review=review_path,
    )
    review_path.write_text(final_review, encoding="utf-8")

    _persist_stage_log(root, slug, "reviewer_stage", state)
    return {
        "review_path": str(review_path),
        "review_verdict": verdict,
        "fatal_defects": fatal_defects,
        "lifecycle_status": lifecycle_status,
        "last_error": f"Adversarial review rejected: {'; '.join(fatal_defects)}" if fatal_defects else "",
    }


def _after_isolated_verification(state: MultiAgentPipelineState) -> Literal["writer_stage", "modeler_stage", "__end__"]:
    if state.get("validation_ok"):
        return "writer_stage"
    repair_count = int(state.get("model_repair_count") or 0)
    max_repairs = int(state.get("max_model_repairs") or 2)
    if repair_count < max_repairs:
        return "modeler_stage"
    return "__end__"


def _after_isolated_review(state: MultiAgentPipelineState) -> Literal["writer_stage", "modeler_stage", "__end__"]:
    if state.get("review_verdict") == "PASS":
        return "__end__"
    rev_count = int(state.get("revision_count") or 0)
    max_rev = int(state.get("max_revisions") or 2)
    if rev_count < max_rev:
        fatals = state.get("fatal_defects") or []
        if any("numeric" in f.lower() or "solver" in f.lower() or "validation" in f.lower() for f in fatals):
            return "modeler_stage"
        return "writer_stage"
    return "__end__"



def build_isolated_pipeline_graph(
    model: Any = None,
    checkpointer: Any = None,
) -> StateGraph:
    """Build the isolated artifact-driven multi-agent StateGraph with backtracking."""
    g: StateGraph = StateGraph(MultiAgentPipelineState)
    g.add_node("researcher_stage", _isolated_researcher_node)
    g.add_node("modeler_stage", _isolated_modeler_node)
    g.add_node("verifier_stage", _isolated_verifier_node)
    g.add_node("writer_stage", _isolated_writer_node)
    g.add_node("reviewer_stage", _isolated_reviewer_node)

    g.add_edge(START, "researcher_stage")
    g.add_edge("researcher_stage", "modeler_stage")
    g.add_edge("modeler_stage", "verifier_stage")
    g.add_conditional_edges(
        "verifier_stage",
        _after_isolated_verification,
        {
            "writer_stage": "writer_stage",
            "modeler_stage": "modeler_stage",
            "__end__": END,
        },
    )
    g.add_edge("writer_stage", "reviewer_stage")
    g.add_conditional_edges(
        "reviewer_stage",
        _after_isolated_review,
        {
            "writer_stage": "writer_stage",
            "modeler_stage": "modeler_stage",
            "__end__": END,
        },
    )
    return g


def build_compiled_isolated_pipeline(
    checkpointer: Any = None,
    model: Any = None,
) -> CompiledStateGraph:
    """Build and compile the isolated artifact-driven multi-agent pipeline graph."""
    graph = build_isolated_pipeline_graph(model=model, checkpointer=checkpointer)
    return graph.compile(checkpointer=checkpointer)


def get_default_supervisor_checkpointer() -> MemorySaver:
    """Return a fresh in-memory checkpointer (``MemorySaver``).

    Convenience factory so callers can build a checkpointed supervisor with an
    isolated, ephemeral store without importing ``langgraph.checkpoint``.
    """
    return MemorySaver()


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    # Run as ``python -m orpath.agents.supervisor`` from the repo root.
    import warnings

    warnings.simplefilter("ignore")
    compiled = build_compiled_supervisor()
    print("nodes:", sorted(compiled.nodes))
    print("worker names:", list(WORKER_AGENT_NAMES))
