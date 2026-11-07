"""Unit tests for the OR-Path supervisor (``orpath/agents/supervisor.py``).

Covers the supervisor-orchestrated multi-agent graph built on
``langgraph_supervisor.create_supervisor``:

  * ``build_supervisor_graph`` returns an un-compiled ``StateGraph``
  * the compiled graph exposes the supervisor node plus the three worker nodes
  * ``SupervisorState`` defines the stage-tracking flags/artifact paths and
    is wired in as the default ``state_schema``
  * ``build_compiled_supervisor`` accepts a checkpointer (or ``None``)
  * a custom prompt and a custom worker roster are honoured
  * the package ``__init__`` re-exports the supervisor surface

Graph construction is offline-safe: the shared model factory falls back to a
placeholder key and the tests never invoke the LLM.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, get_type_hints

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage  # noqa: E402
from langgraph.checkpoint.memory import MemorySaver  # noqa: E402
from langgraph.graph import MessagesState  # noqa: E402
from langgraph.graph.state import CompiledStateGraph, StateGraph  # noqa: E402

from orpath.agents.supervisor import (  # noqa: E402
    ACADEMIC_EXPECTED_SUPERVISOR_NODES,
    ACADEMIC_PIPELINE_STAGE_ORDER,
    DEFAULT_ACADEMIC_SUPERVISOR_PROMPT,
    DEFAULT_SUPERVISOR_PROMPT,
    EXPECTED_SUPERVISOR_NODES,
    ISOLATED_PIPELINE_NODES,
    MultiAgentPipelineState,
    SUPERVISOR_MAX_MESSAGE_CHARS,
    SUPERVISOR_NAME,
    SupervisorState,
    build_academic_supervisor_graph,
    build_compiled_academic_supervisor,
    build_compiled_isolated_pipeline,
    build_compiled_supervisor,
    build_isolated_pipeline_graph,
    build_supervisor_graph,
    get_default_supervisor_checkpointer,
    persist_agent_stage_log,
    supervisor_guard_post_hook,
    supervisor_trim_pre_model_hook,
)
from orpath.agents.workers import (  # noqa: E402
    ACADEMIC_WORKER_NAMES,
    MODELER_NAME,
    ANALYST_NAME,
    REVIEWER_NAME,
    VERIFIER_NAME,
    WORKER_AGENT_NAMES,
    WRITER_NAME,
    create_analyst_agent,
    get_academic_workers,
    get_default_workers,
)
from orpath.control_plane import get_chat_model  # noqa: E402

pytestmark = pytest.mark.filterwarnings(
    "ignore:create_react_agent has been moved"
)

EXPECTED_WORKER_NODES = (ANALYST_NAME, MODELER_NAME, WRITER_NAME, REVIEWER_NAME)


@pytest.fixture()
def model() -> Any:
    """A shared offline model instance for supervisor and worker construction."""
    return get_chat_model()


@pytest.fixture()
def workers(model: Any) -> list[Any]:
    return get_default_workers(model=model)


# --------------------------------------------------------------------------- #
# 1. build_supervisor_graph
# --------------------------------------------------------------------------- #
def test_build_supervisor_graph_returns_state_graph(model: Any) -> None:
    graph = build_supervisor_graph(model=model)
    assert isinstance(graph, StateGraph)
    assert not isinstance(graph, CompiledStateGraph)


def test_build_supervisor_graph_default_model_offline() -> None:
    """No model supplied → factory fallback keeps construction offline-safe."""
    graph = build_supervisor_graph()
    assert isinstance(graph, StateGraph)


def test_build_supervisor_graph_uses_default_prompt() -> None:
    graph = build_supervisor_graph()
    # ``create_supervisor`` bakes the prompt into the supervisor agent; both the
    # default constant and a sentinel prompt must be accepted without error.
    assert isinstance(DEFAULT_SUPERVISOR_PROMPT, str)
    assert len(DEFAULT_SUPERVISOR_PROMPT) > 0
    assert isinstance(graph, StateGraph)


def test_default_prompt_covers_pipeline_order_and_discipline() -> None:
    """The supervisor prompt must route analyst → modeler → writer → reviewer."""
    assert "or_analyst" in DEFAULT_SUPERVISOR_PROMPT
    assert "or_modeler" in DEFAULT_SUPERVISOR_PROMPT
    assert "or_writer" in DEFAULT_SUPERVISOR_PROMPT
    assert "or_reviewer" in DEFAULT_SUPERVISOR_PROMPT
    assert DEFAULT_SUPERVISOR_PROMPT.index("or_analyst") < DEFAULT_SUPERVISOR_PROMPT.index(
        "or_modeler"
    )
    assert DEFAULT_SUPERVISOR_PROMPT.index("or_modeler") < DEFAULT_SUPERVISOR_PROMPT.index(
        "or_writer"
    )
    assert DEFAULT_SUPERVISOR_PROMPT.index("or_writer") < DEFAULT_SUPERVISOR_PROMPT.index(
        "or_reviewer"
    )
    # Numbers Truth discipline.
    assert "Numbers Truth" in DEFAULT_SUPERVISOR_PROMPT
    assert "最优" in DEFAULT_SUPERVISOR_PROMPT


# --------------------------------------------------------------------------- #
# 2. Compiled graph topology
# --------------------------------------------------------------------------- #
def test_compiled_supervisor_contains_expected_nodes(model: Any) -> None:
    compiled = build_compiled_supervisor(model=model)
    nodes = set(compiled.nodes)
    assert {SUPERVISOR_NAME, *EXPECTED_WORKER_NODES} <= nodes


def test_expected_node_constant_matches_pipeline() -> None:
    assert EXPECTED_SUPERVISOR_NODES == (
        SUPERVISOR_NAME,
        ANALYST_NAME,
        MODELER_NAME,
        WRITER_NAME,
        REVIEWER_NAME,
    )


def test_compiled_supervisor_is_invokable(model: Any) -> None:
    compiled = build_compiled_supervisor(model=model)
    assert isinstance(compiled, CompiledStateGraph)
    assert hasattr(compiled, "invoke")


# --------------------------------------------------------------------------- #
# 3. Checkpointer support
# --------------------------------------------------------------------------- #
def test_compiled_supervisor_with_none_checkpointer(model: Any) -> None:
    compiled = build_compiled_supervisor(checkpointer=None, model=model)
    assert isinstance(compiled, CompiledStateGraph)
    assert SUPERVISOR_NAME in compiled.nodes


def test_compiled_supervisor_with_memory_checkpointer(model: Any) -> None:
    compiled = build_compiled_supervisor(checkpointer=MemorySaver(), model=model)
    assert isinstance(compiled, CompiledStateGraph)
    assert SUPERVISOR_NAME in compiled.nodes


def test_default_checkpointer_factory_returns_memory_saver() -> None:
    checkpointer = get_default_supervisor_checkpointer()
    assert isinstance(checkpointer, MemorySaver)


def test_checkpointer_is_wired_into_compiled_graph(model: Any) -> None:
    """A supplied checkpointer is attached to the compiled graph."""
    checkpointer = MemorySaver()
    compiled = build_compiled_supervisor(checkpointer=checkpointer, model=model)
    assert getattr(compiled, "checkpointer", None) is checkpointer


def test_none_checkpointer_leaves_graph_stateless(model: Any) -> None:
    compiled = build_compiled_supervisor(checkpointer=None, model=model)
    assert getattr(compiled, "checkpointer", None) is None


# --------------------------------------------------------------------------- #
# 4. Custom prompt + custom workers
# --------------------------------------------------------------------------- #
def test_custom_prompt_is_accepted(model: Any, workers: list[Any]) -> None:
    custom = "Custom supervisor prompt for tests only."
    graph = build_supervisor_graph(model=model, workers=workers, prompt=custom)
    assert isinstance(graph, StateGraph)
    compiled = graph.compile()
    assert SUPERVISOR_NAME in compiled.nodes


def test_custom_workers_roster_is_honoured(model: Any) -> None:
    """A single-agent roster yields a supervisor whose only worker is that agent."""
    single = create_analyst_agent(model=model)
    graph = build_supervisor_graph(model=model, workers=[single])
    compiled = graph.compile()
    assert SUPERVISOR_NAME in compiled.nodes
    assert ANALYST_NAME in compiled.nodes
    assert MODELER_NAME not in compiled.nodes
    assert REVIEWER_NAME not in compiled.nodes


def test_custom_workers_can_reorder_pipeline(model: Any) -> None:
    """Passing an explicit reordered roster keeps the caller's order."""
    from langgraph.prebuilt import create_react_agent

    from orpath.agents.workers import read_problem_file

    analyst = create_analyst_agent(model=model)
    writer = create_react_agent(
        model=model, tools=[read_problem_file], prompt="verify", name=WRITER_NAME
    )
    roster = [writer, analyst]
    graph = build_supervisor_graph(model=model, workers=roster)
    compiled = graph.compile()
    assert {ANALYST_NAME, WRITER_NAME} <= set(compiled.nodes)


def test_workers_argument_accepts_single_agent(model: Any) -> None:
    single = create_analyst_agent(model=model)
    graph = build_supervisor_graph(model=model, workers=single)
    compiled = graph.compile()
    assert {SUPERVISOR_NAME, ANALYST_NAME} <= set(compiled.nodes)


def test_empty_workers_falls_back_to_default(model: Any) -> None:
    graph = build_supervisor_graph(model=model, workers=[])
    compiled = graph.compile()
    assert {SUPERVISOR_NAME, *EXPECTED_WORKER_NODES} <= set(compiled.nodes)


def test_default_workers_roster_names() -> None:
    assert WORKER_AGENT_NAMES == (ANALYST_NAME, MODELER_NAME, WRITER_NAME, REVIEWER_NAME)


# --------------------------------------------------------------------------- #
# 5. Package re-exports
# --------------------------------------------------------------------------- #
def test_package_reexports_supervisor_surface() -> None:
    import orpath.agents as agents

    for name in (
        "build_supervisor_graph",
        "build_compiled_supervisor",
        "DEFAULT_SUPERVISOR_PROMPT",
        "SUPERVISOR_NAME",
        "EXPECTED_SUPERVISOR_NODES",
        "get_default_supervisor_checkpointer",
        "supervisor_guard_post_hook",
    ):
        assert hasattr(agents, name), f"orpath.agents is missing {name}"
    assert agents.DEFAULT_SUPERVISOR_PROMPT == DEFAULT_SUPERVISOR_PROMPT


def test_package_reexports_worker_surface() -> None:
    import orpath.agents as agents

    assert agents.WORKER_AGENT_NAMES == WORKER_AGENT_NAMES
    assert callable(agents.create_analyst_agent)
    assert callable(agents.create_modeler_agent)
    assert callable(agents.create_writer_agent)


# --------------------------------------------------------------------------- #
# 6. SupervisorState stage tracking
# --------------------------------------------------------------------------- #
STAGE_FLAG_FIELDS = ("has_researched", "has_modeled", "has_verified")
ARTIFACT_PATH_FIELDS = ("solution_path", "paper_path")


def test_supervisor_state_is_messages_state_subclass() -> None:
    assert SupervisorState.__orig_bases__ == (MessagesState,)
    assert "messages" in get_type_hints(SupervisorState)


def test_supervisor_state_defines_stage_flags_and_artifacts() -> None:
    hints = get_type_hints(SupervisorState)
    for field in STAGE_FLAG_FIELDS:
        assert field in hints, f"SupervisorState missing {field}"
        assert hints[field] is bool, f"{field} must be typed bool"
    for field in ARTIFACT_PATH_FIELDS:
        assert field in hints, f"SupervisorState missing {field}"
        assert hints[field] is str, f"{field} must be typed str"


def test_supervisor_state_defaults_are_stage_agnostic() -> None:
    """Fresh schema defaults must indicate "not started" and "no artifact"."""
    assert SupervisorState.has_researched is False
    assert SupervisorState.has_modeled is False
    assert SupervisorState.has_verified is False
    assert SupervisorState.solution_path == ""
    assert SupervisorState.paper_path == ""


def test_build_supervisor_graph_uses_supervisor_state_by_default() -> None:
    graph = build_supervisor_graph()
    assert graph.state_schema is SupervisorState
    hints = get_type_hints(graph.state_schema)
    for field in (*STAGE_FLAG_FIELDS, *ARTIFACT_PATH_FIELDS):
        assert field in hints, f"graph state schema missing {field}"


def test_build_supervisor_graph_accepts_custom_state_schema() -> None:
    from typing import TypedDict

    class CustomState(TypedDict):
        messages: list[Any]
        remaining_steps: int
        custom_flag: bool

    graph = build_supervisor_graph(state_schema=CustomState)
    assert graph.state_schema is CustomState
    assert "custom_flag" in get_type_hints(graph.state_schema)


def test_compiled_supervisor_carries_stage_tracking_schema() -> None:
    compiled = build_compiled_supervisor()
    hints = get_type_hints(SupervisorState)
    assert {*STAGE_FLAG_FIELDS, *ARTIFACT_PATH_FIELDS} <= set(hints)
    assert compiled.input_schema is not None
    assert SUPERVISOR_NAME in compiled.nodes


def test_package_reexports_supervisor_state() -> None:
    import orpath.agents as agents

    assert hasattr(agents, "SupervisorState")
    assert agents.SupervisorState is SupervisorState
    assert "SupervisorState" in agents.__all__


# --------------------------------------------------------------------------- #
# 7. Anti-early-stopping & 4-stage ordering discipline
# --------------------------------------------------------------------------- #
ANTI_EARLY_STOP_KEYWORDS = (
    "严禁早停",
    "严禁",
    "提前收工",
    "严重系统故障",
)
FOUR_STAGE_KEYWORDS = ("阶段 1", "阶段 2", "阶段 3", "阶段 4")


def test_default_prompt_forbids_early_stopping() -> None:
    """The prompt must carry explicit anti-early-stopping warnings."""
    for keyword in ANTI_EARLY_STOP_KEYWORDS:
        assert keyword in DEFAULT_SUPERVISOR_PROMPT, f"missing anti-early-stop keyword: {keyword}"
    # The warning must forbid closing before modelling and verification.
    assert "不得跳步" in DEFAULT_SUPERVISOR_PROMPT


def test_default_prompt_defines_four_stage_order() -> None:
    """The prompt must define a hard 4-stage sequence, in order."""
    positions = [DEFAULT_SUPERVISOR_PROMPT.index(k) for k in FOUR_STAGE_KEYWORDS]
    assert positions == sorted(positions), positions
    # Each stage names its owning worker, in pipeline order.
    assert "阶段 1" in DEFAULT_SUPERVISOR_PROMPT and "or_analyst" in DEFAULT_SUPERVISOR_PROMPT
    assert "阶段 2" in DEFAULT_SUPERVISOR_PROMPT and "or_modeler" in DEFAULT_SUPERVISOR_PROMPT
    assert "阶段 3" in DEFAULT_SUPERVISOR_PROMPT and "or_writer" in DEFAULT_SUPERVISOR_PROMPT


def test_default_prompt_requires_verification_before_finish() -> None:
    """Stage 4 must only be reachable after verified output and exported paper."""
    assert "validate_solution_tool" in DEFAULT_SUPERVISOR_PROMPT
    assert "ok: true" in DEFAULT_SUPERVISOR_PROMPT
    assert "论文已导出" in DEFAULT_SUPERVISOR_PROMPT
    # The closing verdict is gated by the verification stage, not before it.
    stage4 = DEFAULT_SUPERVISOR_PROMPT.index("阶段 4")
    assert DEFAULT_SUPERVISOR_PROMPT.index("方可输出终结文本") > stage4


def test_default_prompt_requires_modeler_and_verifier_before_stop() -> None:
    """The anti-early-stop clause must name both mandatory stages."""
    assert "or_modeler" in DEFAULT_SUPERVISOR_PROMPT
    assert "or_writer" in DEFAULT_SUPERVISOR_PROMPT
    # The prohibition itself must invoke the verification requirement.
    assert "独立验算" in DEFAULT_SUPERVISOR_PROMPT


# --------------------------------------------------------------------------- #
# 8. Deterministic anti-early-stopping routing guard
# --------------------------------------------------------------------------- #
def _handoff(worker_name: str, call_id: str) -> AIMessage:
    """Build an AIMessage that calls ``transfer_to_<worker>``."""
    return AIMessage(
        content="",
        tool_calls=[{"name": f"transfer_to_{worker_name}", "args": {}, "id": call_id}],
    )


def _last_message(update: dict) -> Any:
    messages = update.get("messages", [])
    return messages[-1] if messages else None


def _guard_call_names(update: dict) -> list[str]:
    """Return the injected handoff tool-call names in ``update`` (empty if none)."""
    injected = []
    for message in update.get("messages", []):
        if isinstance(message, AIMessage):
            injected.extend(call["name"] for call in message.tool_calls or [])
    return injected


def test_guard_hook_is_exported() -> None:
    import orpath.agents.supervisor as supervisor_module

    assert "supervisor_guard_post_hook" in supervisor_module.__all__
    assert supervisor_module.supervisor_guard_post_hook is supervisor_guard_post_hook


def test_guard_no_op_on_empty_state() -> None:
    assert supervisor_guard_post_hook({"messages": []}) == {}


def test_guard_no_op_when_last_message_is_not_ai() -> None:
    update = supervisor_guard_post_hook({"messages": [HumanMessage("求解 TSP")]})
    assert update == {}


def test_guard_no_op_when_last_message_already_routes() -> None:
    routed = _handoff(ANALYST_NAME, "model_call")
    update = supervisor_guard_post_hook({"messages": [HumanMessage("求解"), routed]})
    assert update == {}


def test_guard_injects_analyst_handoff_when_stage_missing() -> None:
    bare = AIMessage(content="任务完成，最优值是 42", id="late_final")
    update = supervisor_guard_post_hook({"messages": [HumanMessage("求解"), bare]})

    messages = update["messages"]
    assert len(messages) == 2
    assert isinstance(messages[0], RemoveMessage) and messages[0].id == "late_final"
    injected = messages[1]
    assert isinstance(injected, AIMessage)
    assert _guard_call_names(update) == ["transfer_to_or_analyst"]
    assert injected.tool_calls[0]["args"] == {}
    assert injected.tool_calls[0]["id"] == "guard_call_analyst"
    assert "任务完成" in injected.content


def test_guard_injects_modeler_handoff_after_analyst() -> None:
    messages = [
        HumanMessage("求解"),
        AIMessage(content="research report", name=ANALYST_NAME),
        AIMessage(content="done", id="bare"),
    ]
    update = supervisor_guard_post_hook({"messages": messages})
    assert _guard_call_names(update) == ["transfer_to_or_modeler"]
    assert _last_message(update).tool_calls[0]["id"] == "guard_call_modeler"


def test_guard_injects_writer_handoff_after_modeler() -> None:
    messages = [
        HumanMessage("求解"),
        AIMessage(content="a", name=ANALYST_NAME),
        AIMessage(content="m", name=MODELER_NAME),
        AIMessage(content="final", id="bare"),
    ]
    update = supervisor_guard_post_hook({"messages": messages})
    assert _guard_call_names(update) == ["transfer_to_or_writer"]
    assert _last_message(update).tool_calls[0]["id"] == "guard_call_writer"


def test_guard_recognises_handoff_tool_calls_not_just_worker_messages() -> None:
    """A stage counts done when ``transfer_to_<worker>`` was invoked, even if the
    worker reply is a plain ``ToolMessage`` and no worker-named AIMessage exists."""
    messages = [
        HumanMessage("求解"),
        _handoff(ANALYST_NAME, "call_r"),
        ToolMessage(content="r", name="transfer_to_or_analyst", tool_call_id="call_r"),
        _handoff(MODELER_NAME, "call_m"),
        ToolMessage(content="m", name="transfer_to_or_modeler", tool_call_id="call_m"),
        AIMessage(content="bare final", id="bare"),
    ]
    update = supervisor_guard_post_hook({"messages": messages})
    assert _guard_call_names(update) == ["transfer_to_or_writer"]


def test_guard_allows_bare_reply_only_after_all_four_stages() -> None:
    messages = [
        HumanMessage("求解"),
        AIMessage(content="a", name=ANALYST_NAME),
        AIMessage(content="m", name=MODELER_NAME),
        AIMessage(content="w", name=WRITER_NAME),
        AIMessage(content="v", name=REVIEWER_NAME),
        AIMessage(content="final answer", id="final"),
    ]
    assert supervisor_guard_post_hook({"messages": messages}) == {}


def test_guard_prefers_earliest_missing_stage() -> None:
    """Analyst only done → modeler is the first missing stage (not writer)."""
    messages = [
        HumanMessage("求解"),
        AIMessage(content="r", name=ANALYST_NAME),
        AIMessage(content="bare", id="bare"),
    ]
    update = supervisor_guard_post_hook({"messages": messages})
    assert _guard_call_names(update) == ["transfer_to_or_modeler"]


def test_guard_appends_when_last_message_has_no_id() -> None:
    bare = AIMessage(content="done")  # no id
    update = supervisor_guard_post_hook({"messages": [HumanMessage("求解"), bare]})
    assert _guard_call_names(update) == ["transfer_to_or_analyst"]


def test_build_supervisor_graph_enable_guard_compiles(model: Any) -> None:
    graph = build_supervisor_graph(model=model, enable_guard=True)
    assert isinstance(graph, StateGraph)
    compiled = graph.compile()
    assert {SUPERVISOR_NAME, *EXPECTED_WORKER_NODES} <= set(compiled.nodes)


def test_build_supervisor_graph_enable_guard_defaults_to_true(model: Any) -> None:
    # Default build (no enable_guard arg) must carry the guard and still compile.
    graph = build_supervisor_graph(model=model)
    compiled = graph.compile()
    assert {SUPERVISOR_NAME, *EXPECTED_WORKER_NODES} <= set(compiled.nodes)


def test_build_supervisor_graph_disable_guard_compiles(model: Any) -> None:
    graph = build_supervisor_graph(model=model, enable_guard=False)
    assert isinstance(graph, StateGraph)
    compiled = graph.compile()
    assert {SUPERVISOR_NAME, *EXPECTED_WORKER_NODES} <= set(compiled.nodes)


def test_build_compiled_supervisor_guard_switch(model: Any) -> None:
    guarded = build_compiled_supervisor(model=model, enable_guard=True)
    unguarded = build_compiled_supervisor(model=model, enable_guard=False)
    for compiled in (guarded, unguarded):
        assert isinstance(compiled, CompiledStateGraph)
        assert {SUPERVISOR_NAME, *EXPECTED_WORKER_NODES} <= set(compiled.nodes)


# --------------------------------------------------------------------------- #
# 9. Zero Truncation: passthrough pre-model hook + per-stage JSONL sidecar logs
# --------------------------------------------------------------------------- #
BIG_TEXT = (
    "30k-character problem statement: coordinates and demands follow. "
    + "ROW_" + "1.2934,4.8712; " * 2400
)
TRUNCATION_NOTE = "truncated by supervisor context trimmer"
PAIRED_MARKERS = (TRUNCATION_NOTE, "chars omitted", "omitted chars", "truncated")


def _count_truncation_markers(payload: str) -> int:
    """Return how many truncation markers appear anywhere in ``payload``."""
    return sum(payload.count(marker) for marker in PAIRED_MARKERS)


def test_trim_hook_exported_and_lossless() -> None:
    import orpath.agents as agents_pkg
    import orpath.agents.supervisor as supervisor_module

    assert "supervisor_trim_pre_model_hook" in supervisor_module.__all__
    assert "supervisor_trim_pre_model_hook" in agents_pkg.__all__
    assert "persist_agent_stage_log" in supervisor_module.__all__
    assert callable(supervisor_trim_pre_model_hook)
    assert callable(persist_agent_stage_log)


def test_trim_hook_empty_state() -> None:
    assert supervisor_trim_pre_model_hook({"messages": []}) == {"llm_input_messages": []}


def test_trim_hook_is_noop_passthroughity_zero_truncation() -> None:
    messages = [
        HumanMessage("求解小规模问题"),
        AIMessage(BIG_TEXT, name=ANALYST_NAME, id="ai_huge"),
    ]
    res = supervisor_trim_pre_model_hook({"messages": messages})
    assert res == {"llm_input_messages": messages}
    assert "messages" not in res


def test_trim_hook_preserves_oversized_text_verbatim() -> None:
    huge_text = "A" * (SUPERVISOR_MAX_MESSAGE_CHARS * 20)
    messages = [
        HumanMessage(content="求解"),
        AIMessage(content=huge_text, name=ANALYST_NAME, id="ai_huge"),
    ]
    res = supervisor_trim_pre_model_hook({"messages": messages})
    assert "llm_input_messages" in res
    assert "messages" not in res

    llm_msgs = res["llm_input_messages"]
    assert len(llm_msgs) == 2
    # The whole 32,000-character payload survives untouched.
    assert llm_msgs[1].content == huge_text
    assert _count_truncation_markers(llm_msgs[1].content) == 0
    assert llm_msgs[1].id == "ai_huge"


def test_trim_hook_preserves_long_history_intact() -> None:
    messages = [HumanMessage(content="初始任务要求", id="msg_0")]
    for i in range(1, 60):
        if i == 20:
            messages.append(
                AIMessage(
                    content="",
                    tool_calls=[{"name": "tool_x", "args": {}, "id": "call_20"}],
                    id="ai_call_20",
                )
            )
        elif i == 21:
            messages.append(ToolMessage(content="tool output", tool_call_id="call_20", id="tool_20"))
        else:
            messages.append(HumanMessage(content=f"msg_{i}", id=f"msg_{i}"))

    res = supervisor_trim_pre_model_hook({"messages": messages})
    llm_msgs = res["llm_input_messages"]
    assert len(llm_msgs) == len(messages)
    assert [m.id for m in llm_msgs] == [m.id for m in messages]


def test_trim_hook_handles_dict_messages_without_truncation() -> None:
    huge_text = "B" * (SUPERVISOR_MAX_MESSAGE_CHARS * 30)
    state = {
        "messages": [
            {"role": "user", "content": "问题定义"},
            {"role": "assistant", "content": huge_text},
        ]
    }
    res = supervisor_trim_pre_model_hook(state)
    assert "llm_input_messages" in res
    assert "messages" not in res
    assert res["llm_input_messages"][1]["content"] == huge_text
    assert _count_truncation_markers(json.dumps(res["llm_input_messages"], ensure_ascii=False)) == 0


def test_trim_hook_handles_list_content_blocks_verbatim() -> None:
    huge_text = "C" * (SUPERVISOR_MAX_MESSAGE_CHARS * 25)
    messages = [HumanMessage(content=[{"type": "text", "text": huge_text}])]
    res = supervisor_trim_pre_model_hook({"messages": messages})
    block = res["llm_input_messages"][0].content[0]
    assert block["type"] == "text"
    assert block["text"] == huge_text
    assert _count_truncation_markers(block["text"]) == 0


def test_plan_1_1_stage_log_persists_30000_chars_verbatim(tmp_path: Path) -> None:
    slug = "plan11_zero_truncation"
    stage = "researcher_stage"
    payload_messages = [
        HumanMessage(content="题面: " + BIG_TEXT, id="m0"),
        {"role": "user", "content": "矩阵: " + BIG_TEXT},
    ]
    assert len(BIG_TEXT) > 30_000

    log_path = persist_agent_stage_log(tmp_path, slug, stage, payload_messages)

    assert log_path.is_file()
    assert log_path == tmp_path / "runs" / slug / "agent_logs" / f"{stage}.jsonl"
    raw = log_path.read_text(encoding="utf-8")
    assert _count_truncation_markers(raw) == 0
    # Every character of both messages is still on disk.
    assert raw.count(BIG_TEXT) == len(payload_messages)


def test_plan_1_1_isolated_pipeline_stage_logs_have_zero_truncation(tmp_path: Path) -> None:
    """Isolated pipeline stages must write sidecar logs with zero truncation."""
    import json as _json

    from orpath.agents.supervisor import _isolated_researcher_node

    slug = "plan11_isolated_stage_log"
    inbox = tmp_path / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "problem.txt").write_text("题面: " + BIG_TEXT, encoding="utf-8")
    state: dict[str, Any] = {
        "workdir": str(tmp_path),
        "slug": slug,
        "problem_id": slug,
        "problem_class": "network_optimization",
        "problem_file": "inbox/problem.txt",
        "messages": [HumanMessage(content="题面: " + BIG_TEXT, id="m0")],
    }

    research_state = _isolated_researcher_node(state)
    assert research_state["slug"] == slug

    log_path = tmp_path / "runs" / slug / "agent_logs" / "researcher_stage.jsonl"
    assert log_path.is_file()
    raw = log_path.read_text(encoding="utf-8")
    assert _count_truncation_markers(raw) == 0
    assert raw.count(BIG_TEXT) == 1

    records = [_json.loads(line) for line in raw.splitlines() if line.strip()]
    assert records[0]["type"] == "stage_log"
    assert records[0]["stage"] == "researcher_stage"
    assert records[-1]["type"] == "stage_summary"
    assert records[-1]["stage"] == "researcher_stage"
    problem_records = [r for r in records if r.get("type") == "problem_text"]
    assert problem_records, records
    assert problem_records[0]["text"] == "题面: " + BIG_TEXT


def test_plan_1_1_isolated_graph_nodes_trace_without_truncation(tmp_path: Path) -> None:
    slug = "plan11_graph_trace"
    graph = build_compiled_isolated_pipeline(checkpointer=MemorySaver())
    state: MultiAgentPipelineState = {
        "workdir": str(tmp_path),
        "slug": slug,
        "problem_id": slug,
        "problem_class": "linear_programming",
        "messages": [HumanMessage(content="题面: " + BIG_TEXT, id="m0")],
    }

    inbox = tmp_path / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "problem.txt").write_text("题面: " + BIG_TEXT, encoding="utf-8")
    state["problem_file"] = "inbox/problem.txt"

    final = graph.invoke(state, config={"configurable": {"thread_id": "t1"}})
    assert final["lifecycle_status"] in {"FAILED", "ACCEPTED", "PROPOSED"}

    log_dir = tmp_path / "runs" / slug / "agent_logs"
    research_log = log_dir / "researcher_stage.jsonl"
    assert research_log.is_file()
    research_text = research_log.read_text(encoding="utf-8")
    assert _count_truncation_markers(research_text) == 0
    # The 30,000+ character problem statement survives verbatim in the log.
    assert research_text.count(BIG_TEXT) >= 1
    for log_path in log_dir.glob("*.jsonl"):
        assert _count_truncation_markers(log_path.read_text(encoding="utf-8")) == 0


def test_build_supervisor_graph_trim_options(model: Any) -> None:
    trimmed = build_compiled_supervisor(model=model, enable_trim=True)
    untrimmed = build_compiled_supervisor(model=model, enable_trim=False)
    for compiled in (trimmed, untrimmed):
        assert isinstance(compiled, CompiledStateGraph)
        assert {SUPERVISOR_NAME, *EXPECTED_WORKER_NODES} <= set(compiled.nodes)
# --------------------------------------------------------------------------- #
# 10. Academic 5-worker Supervisor Pipeline
# --------------------------------------------------------------------------- #
def test_academic_supervisor_graph_construction(model: Any) -> None:
    graph = build_academic_supervisor_graph(model=model)
    assert isinstance(graph, StateGraph)
    compiled = build_compiled_academic_supervisor(model=model)
    assert isinstance(compiled, CompiledStateGraph)
    for node in ACADEMIC_EXPECTED_SUPERVISOR_NODES:
        assert node in compiled.nodes


def test_academic_prompt_and_nodes_constants() -> None:
    assert len(ACADEMIC_PIPELINE_STAGE_ORDER) == 5
    assert ACADEMIC_PIPELINE_STAGE_ORDER == (
        ANALYST_NAME,
        MODELER_NAME,
        VERIFIER_NAME,
        WRITER_NAME,
        REVIEWER_NAME,
    )
    assert ACADEMIC_EXPECTED_SUPERVISOR_NODES == (
        SUPERVISOR_NAME,
        ANALYST_NAME,
        MODELER_NAME,
        VERIFIER_NAME,
        WRITER_NAME,
        REVIEWER_NAME,
    )
    for expected in ("阶段 1", "阶段 2", "阶段 3", "阶段 4", "阶段 5", "严禁早停", "or_reviewer"):
        assert expected in DEFAULT_ACADEMIC_SUPERVISOR_PROMPT


def test_supervisor_state_academic_fields() -> None:
    hints = get_type_hints(SupervisorState)
    assert hints["has_written"] is bool
    assert hints["has_reviewed"] is bool
    assert hints["review_path"] is str
    assert SupervisorState.has_written is False
    assert SupervisorState.has_reviewed is False
    assert SupervisorState.review_path == ""


def test_guard_academic_pipeline_enforces_5_stages() -> None:
    base_state: dict[str, Any] = {"academic": True}

    # 1. Bare reply with no stages -> transfer to analyst
    update1 = supervisor_guard_post_hook({**base_state, "messages": [HumanMessage("task"), AIMessage("done", id="m1")]})
    assert _guard_call_names(update1) == ["transfer_to_or_analyst"]

    # 2. Researcher done -> transfer to modeler
    msgs2 = [
        HumanMessage("task"),
        AIMessage("res", name=ANALYST_NAME),
        AIMessage("done", id="m2"),
    ]
    update2 = supervisor_guard_post_hook({**base_state, "messages": msgs2})
    assert _guard_call_names(update2) == ["transfer_to_or_modeler"]

    # 3. Modeler done -> transfer to verifier
    msgs3 = [
        HumanMessage("task"),
        AIMessage("res", name=ANALYST_NAME),
        AIMessage("mod", name=MODELER_NAME),
        AIMessage("done", id="m3"),
    ]
    update3 = supervisor_guard_post_hook({**base_state, "messages": msgs3})
    assert _guard_call_names(update3) == ["transfer_to_or_verifier"]

    # 4. Verifier done -> transfer to writer
    msgs4 = [
        HumanMessage("task"),
        AIMessage("res", name=ANALYST_NAME),
        AIMessage("mod", name=MODELER_NAME),
        AIMessage("ver", name=VERIFIER_NAME),
        AIMessage("done", id="m4"),
    ]
    update4 = supervisor_guard_post_hook({**base_state, "messages": msgs4})
    assert _guard_call_names(update4) == ["transfer_to_or_writer"]

    # 5. Writer done -> transfer to reviewer
    msgs5 = [
        HumanMessage("task"),
        AIMessage("res", name=ANALYST_NAME),
        AIMessage("mod", name=MODELER_NAME),
        AIMessage("ver", name=VERIFIER_NAME),
        AIMessage("wri", name=WRITER_NAME),
        AIMessage("done", id="m5"),
    ]
    update5 = supervisor_guard_post_hook({**base_state, "messages": msgs5})
    assert _guard_call_names(update5) == ["transfer_to_or_reviewer"]

    # 6. All 5 stages done -> allow bare reply
    msgs6 = [
        HumanMessage("task"),
        AIMessage("res", name=ANALYST_NAME),
        AIMessage("mod", name=MODELER_NAME),
        AIMessage("ver", name=VERIFIER_NAME),
        AIMessage("wri", name=WRITER_NAME),
        AIMessage("rev", name=REVIEWER_NAME),
        AIMessage("completed", id="m6"),
    ]
    update6 = supervisor_guard_post_hook({**base_state, "messages": msgs6})
    assert update6 == {}


def test_package_reexports_academic_surface() -> None:
    import orpath.agents as agents

    assert hasattr(agents, "build_academic_supervisor_graph")
    assert hasattr(agents, "build_compiled_academic_supervisor")
    assert hasattr(agents, "DEFAULT_ACADEMIC_SUPERVISOR_PROMPT")
    assert hasattr(agents, "ACADEMIC_PIPELINE_STAGE_ORDER")
    assert hasattr(agents, "ACADEMIC_EXPECTED_SUPERVISOR_NODES")
    assert hasattr(agents, "create_verifier_agent")
    assert hasattr(agents, "create_writer_agent")
    assert hasattr(agents, "create_reviewer_agent")
    assert hasattr(agents, "get_academic_workers")


# --------------------------------------------------------------------------- #
# 11. Isolated Artifact-Driven Pipeline Graph & Adversarial Backtracking
# --------------------------------------------------------------------------- #
def test_isolated_pipeline_graph_nodes_and_topology() -> None:
    graph = build_isolated_pipeline_graph()
    assert isinstance(graph, StateGraph)
    compiled = build_compiled_isolated_pipeline()
    assert isinstance(compiled, CompiledStateGraph)
    for node in ISOLATED_PIPELINE_NODES:
        assert node in compiled.nodes


def test_isolated_pipeline_state_fields() -> None:
    hints = get_type_hints(MultiAgentPipelineState)
    for expected in (
        "slug",
        "problem_id",
        "problem_class",
        "research_path",
        "solution_path",
        "validate_path",
        "paper_path",
        "review_path",
        "lifecycle_status",
        "validation_ok",
        "review_verdict",
        "fatal_defects",
        "revision_count",
        "max_revisions",
        "model_repair_count",
        "max_model_repairs",
    ):
        assert expected in hints, f"MultiAgentPipelineState missing field: {expected}"


def test_isolated_pipeline_checkpointer() -> None:
    saver = MemorySaver()
    compiled = build_compiled_isolated_pipeline(checkpointer=saver)
    assert getattr(compiled, "checkpointer", None) is saver


def test_isolated_verification_backtracking_to_modeler() -> None:
    from orpath.agents.supervisor import _after_isolated_verification

    # 1. Validation ok -> advance to writer_stage
    assert _after_isolated_verification({"validation_ok": True}) == "writer_stage"

    # 2. Validation failed, repair count < max -> backtrack to modeler_stage
    assert _after_isolated_verification({"validation_ok": False, "model_repair_count": 0, "max_model_repairs": 2}) == "modeler_stage"
    assert _after_isolated_verification({"validation_ok": False, "model_repair_count": 1, "max_model_repairs": 2}) == "modeler_stage"

    # 3. Validation failed, repairs exhausted -> terminate (__end__)
    assert _after_isolated_verification({"validation_ok": False, "model_repair_count": 2, "max_model_repairs": 2}) == "__end__"


def test_isolated_review_backtracking_to_writer_and_modeler() -> None:
    from orpath.agents.supervisor import _after_isolated_review

    # 1. Review PASS -> terminate (__end__)
    assert _after_isolated_review({"review_verdict": "PASS"}) == "__end__"

    # 2. Review REVISE with non-numerical defect -> backtrack to writer_stage
    state_writer = {
        "review_verdict": "REVISE",
        "fatal_defects": ["FATAL: Missing mandatory section ## Problem statement"],
        "revision_count": 0,
        "max_revisions": 2,
    }
    assert _after_isolated_review(state_writer) == "writer_stage"

    # 3. Review REVISE with numerical / solver defect -> backtrack to modeler_stage
    state_modeler = {
        "review_verdict": "REVISE",
        "fatal_defects": ["FATAL: Numeric claim 123.4 does not match solver output"],
        "revision_count": 0,
        "max_revisions": 2,
    }
    assert _after_isolated_review(state_modeler) == "modeler_stage"

    # 4. Review REVISE but revisions exhausted -> terminate (__end__)
    state_exhausted = {
        "review_verdict": "REVISE",
        "fatal_defects": ["FATAL: Optimality hype unproven"],
        "revision_count": 2,
        "max_revisions": 2,
    }
    assert _after_isolated_review(state_exhausted) == "__end__"


def test_package_reexports_isolated_pipeline() -> None:
    import orpath.agents as agents

    assert hasattr(agents, "build_isolated_pipeline_graph")
    assert hasattr(agents, "build_compiled_isolated_pipeline")
    assert hasattr(agents, "MultiAgentPipelineState")
    assert hasattr(agents, "ISOLATED_PIPELINE_NODES")


def test_isolated_verifier_failure_marks_status_failed(tmp_path: Path) -> None:
    from orpath.agents.supervisor import _isolated_verifier_node

    # Non-existent solution
    res = _isolated_verifier_node({
        "slug": "test_task",
        "solution_path": str(tmp_path / "nonexistent.json"),
    })
    assert res["validation_ok"] is False
    assert res["lifecycle_status"] == "FAILED"
    assert "solution_path does not exist" in res["last_error"]


def test_isolated_writer_and_reviewer_flow(tmp_path: Path) -> None:
    import json
    from orpath.agents.supervisor import _isolated_reviewer_node, _isolated_writer_node

    # Create dummy solution
    sol_p = tmp_path / "sol.json"
    sol_p.write_text(json.dumps({
        "status": "FEASIBLE",
        "objective": 42.0,
        "solver": "ortools",
        "meta": {"proven_optimal": False},
    }), encoding="utf-8")

    state = {
        "slug": "flow_test",
        "problem_id": "flow_test",
        "problem_class": "tsp",
        "solution_path": str(sol_p),
    }

    # Writer node
    writer_res = _isolated_writer_node(state)
    assert Path(writer_res["paper_path"]).is_file()
    paper_text = Path(writer_res["paper_path"]).read_text(encoding="utf-8")
    assert "## Abstract" in paper_text or "## 摘要" in paper_text
    assert "## Problem statement" in paper_text or "## 问题建模" in paper_text

    # Reviewer node
    state["paper_path"] = writer_res["paper_path"]
    state["validation_ok"] = True
    reviewer_res = _isolated_reviewer_node(state)
    assert Path(reviewer_res["review_path"]).is_file()
    assert reviewer_res["review_verdict"] == "PASS"
    assert reviewer_res["lifecycle_status"] == "ACCEPTED"


def test_isolated_reviewer_catches_unproven_optimality(tmp_path: Path) -> None:
    import json
    from orpath.agents.supervisor import _isolated_reviewer_node

    sol_p = tmp_path / "sol.json"
    sol_p.write_text(json.dumps({
        "status": "FEASIBLE",
        "objective": 42.0,
        "meta": {"proven_optimal": False},
    }), encoding="utf-8")

    paper_p = tmp_path / "paper.md"
    paper_p.write_text(
        "## Abstract\nOverview\n"
        "## Problem statement\nProblem\n"
        "## Method / formulation\nFormulation\n"
        "## Solution strategy\nStrategy\n"
        "## Results\nThis method achieved the globally optimal solution without doubt.\n"
        "## Limitations\nNone\n",
        encoding="utf-8"
    )

    state = {
        "slug": "opt_test",
        "solution_path": str(sol_p),
        "paper_path": str(paper_p),
        "validation_ok": True,
    }
    reviewer_res = _isolated_reviewer_node(state)
    assert reviewer_res["review_verdict"] == "REVISE"
    assert any("global optimality" in d for d in reviewer_res["fatal_defects"])


def test_node_solve_reuses_multiagent_solution(tmp_path: Path) -> None:
    import json
    from orpath.pipeline.solve import node_solve

    out_dir = tmp_path / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    sol_p = out_dir / "custom_task-solution.json"
    sol_p.write_text(json.dumps({
        "status": "FEASIBLE",
        "objective": 123.45,
        "solver": "custom_cp_sat",
    }), encoding="utf-8")

    state = {
        "workdir": str(tmp_path),
        "slug": "custom_task",
        "problem_id": "custom_p1",
        "problem_class": "custom_unregistered_class",
        "solve_mode": "auto",
        "gate_subagent_ok": True,
        "solution_path": str(sol_p),
    }

    res = node_solve(state)
    assert res["stage"] == "gate_validate"
    assert res["solution_path"] == str(sol_p)
    # Ensure it didn't overwrite the solution file
    saved = json.loads(sol_p.read_text(encoding="utf-8"))
    assert saved["objective"] == 123.45
    assert saved["solver"] == "custom_cp_sat"


def test_node_revise_or_done_routes_to_draft_paper_on_fatal(tmp_path: Path) -> None:
    import json
    from orpath.pipeline.paper import node_revise_or_done

    out_dir = tmp_path / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    sol_p = out_dir / "rev_test-solution.json"
    sol_p.write_text(json.dumps({"status": "FEASIBLE", "objective": 10.0, "meta": {"proven_optimal": False}}), encoding="utf-8")

    paper_p = tmp_path / "papers" / "rev_test.md"
    paper_p.parent.mkdir(parents=True, exist_ok=True)
    paper_p.write_text("# Paper\nSome draft", encoding="utf-8")

    state = {
        "workdir": str(tmp_path),
        "slug": "rev_test",
        "problem_id": "rev_test",
        "paper_path": str(paper_p),
        "solution_path": str(sol_p),
        "gate_r1_ok": False,
        "gate_r2_ok": False,
        "gate_claim_ok": False,
        "review_fatal": 1,
        "revise_count": 0,
        "max_revise": 2,
    }

    res = node_revise_or_done(state)
    assert res["stage"] == "draft_paper"
    assert res["revise_count"] == 1





