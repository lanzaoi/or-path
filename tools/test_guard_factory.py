#!/usr/bin/env python3
"""Unit tests for the generic supervisor guard-hook factory.

Covers ``orpath/agents/guard_factory.py``, the domain-agnostic extraction of the
anti-early-stopping ``post_model_hook`` that previously lived as hand-rolled
closures inside ``orpath/agents/supervisor.py`` and
``orpath/agents/domains/tube.py``:

  * ``create_domain_guard_hook`` returns a deterministic ``post_model_hook``
  * ``worker_handoff_complete`` recognises every handoff shape in a transcript
  * ``default_guard_call_ids`` builds deterministic guard call ids
  * pass-through cases: empty state, non-AI last message, already-routing reply
  * full stage progression 1 → N
  * the earliest missing stage wins over later gaps
  * a bare reply is permitted *only* when every stage is complete
  * ``RemoveMessage`` vs append depending on whether the reply carries an ``id``
  * the factory is generic across arbitrary domain stage orders
  * the Tube B stage order is reproduced bit-for-bit by the factory

The tests never invoke an LLM; every case is pure state in / state out.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage  # noqa: E402

from orpath.agents.guard_factory import (  # noqa: E402
    DEFAULT_GUARD_CALL_ID_PREFIX,
    DEFAULT_TRANSFER_PREFIX,
    create_domain_guard_hook,
    default_guard_call_ids,
    worker_handoff_complete,
)
from orpath.agents.domains.tube import (  # noqa: E402
    TUBE_GEOMETRY_NAME,
    TUBE_GUARD_CALL_IDS,
    TUBE_PIPELINE_STAGE_ORDER,
    TUBE_Q1Q2_NAME,
    TUBE_Q3_NAME,
    TUBE_Q4_NAME,
    TUBE_REDTEAM_NAME,
    tube_guard_post_hook,
)

pytestmark = pytest.mark.filterwarnings("ignore:create_react_agent has been moved")

#: Canonical 3-stage synthetic pipeline used by the generic tests.
STAGES: tuple[str, ...] = ("stage_a", "stage_b", "stage_c")

#: Arbitrary stage orders for the cross-domain genericity test.
DOMAIN_STAGE_ORDERS: dict[str, tuple[str, ...]] = {
    "routing": ("or_routing_designer", "or_routing_solver", "or_routing_validator"),
    "scheduling": ("or_schedule_modeler", "or_schedule_solver", "or_schedule_redteam"),
    "microgrid": ("or_microgrid_sizing", "or_microgrid_dispatch", "or_microgrid_audit"),
    "cutting_stock": ("or_cut_pattern_search", "or_cut_pattern_pack", "or_cut_pattern_validate"),
}


# --------------------------------------------------------------------------- #
# Test doubles & helpers
# --------------------------------------------------------------------------- #
def _transfer(worker_name: str, call_id: str = "model_call") -> AIMessage:
    """Build an ``AIMessage`` that routes to ``transfer_to_<worker>``."""
    return AIMessage(
        content="",
        tool_calls=[{"name": f"transfer_to_{worker_name}", "args": {}, "id": call_id}],
    )


def _worker_reply(worker_name: str, content: str = "stage report") -> AIMessage:
    """Build a bare ``AIMessage`` attributed to a worker (no tool calls)."""
    return AIMessage(content=content, name=worker_name)


def _bare(content: str = "任务完成，最优值是 42", message_id: str | None = "bare_final") -> AIMessage:
    """Build the lazy lead reply the guard has to intercept."""
    return AIMessage(content=content, id=message_id)


def _update_messages(update: dict) -> list[Any]:
    return list(update.get("messages", []))


def _last_message(update: dict) -> Any:
    messages = _update_messages(update)
    return messages[-1] if messages else None


def _injected_tool_names(update: dict) -> list[str]:
    """Return every handoff tool-call name carried by ``update`` (empty if none)."""
    injected: list[str] = []
    for message in _update_messages(update):
        if isinstance(message, AIMessage):
            injected.extend(call["name"] for call in message.tool_calls or [])
    return injected


def _injected_tool_call_ids(update: dict) -> list[str]:
    """Return every guard-issued tool-call id carried by ``update``."""
    ids: list[str] = []
    for message in _update_messages(update):
        if isinstance(message, AIMessage):
            ids.extend(call["id"] for call in message.tool_calls or [])
    return ids


def _run_full_pipeline(
    hook: Callable[[Any], dict],
    stage_order: tuple[str, ...],
    lead_reply: str = "我先直接给结论",
) -> list[str]:
    """Drive ``hook`` through every stage, returning the ordered handoffs issued.

    Each injected handoff is followed by a worker-named reply, exactly as
    ``langgraph_supervisor`` would present the transcript after a worker finishes.
    """
    messages: list[Any] = [HumanMessage("求解"), _bare(lead_reply)]
    issued: list[str] = []
    for _ in stage_order:
        update = hook({"messages": messages})
        assert update, f"expected a handoff for {stage_order[len(issued)]}, got {update!r}"
        messages.extend(_update_messages(update))
        worker = _injected_tool_names(update)[0].removeprefix(f"{DEFAULT_TRANSFER_PREFIX}")
        messages.append(_worker_reply(worker))
        issued.append(worker)
    # Once every stage has run the lead's own reply must be allowed through.
    assert hook({"messages": messages}) == {}
    return issued


# --------------------------------------------------------------------------- #
# 1. Module surface
# --------------------------------------------------------------------------- #
def test_module_surface_exports_documented_api() -> None:
    import orpath.agents.guard_factory as guard_factory

    assert set(guard_factory.__all__) == {
        "DEFAULT_GUARD_CALL_ID_PREFIX",
        "DEFAULT_TRANSFER_PREFIX",
        "create_domain_guard_hook",
        "default_guard_call_ids",
        "worker_handoff_complete",
    }
    for symbol in guard_factory.__all__:
        assert hasattr(guard_factory, symbol)


def test_module_constants_match_langgraph_supervisor_conventions() -> None:
    assert DEFAULT_TRANSFER_PREFIX == "transfer_to_"
    assert DEFAULT_GUARD_CALL_ID_PREFIX == "guard_call_"


def test_factory_returns_a_post_model_hook() -> None:
    hook = create_domain_guard_hook(STAGES)
    assert callable(hook)
    assert hook({"messages": []}) == {}


# --------------------------------------------------------------------------- #
# 2. worker_handoff_complete
# --------------------------------------------------------------------------- #
def test_handoff_complete_is_false_for_empty_transcript() -> None:
    assert worker_handoff_complete([], STAGES[0]) is False


def test_handoff_complete_is_false_for_unrelated_transcript() -> None:
    messages = [
        HumanMessage("求解"),
        AIMessage("", tool_calls=[{"name": "transfer_to_stage_b", "args": {}, "id": "c1"}]),
        ToolMessage(content="ack", name="other_tool", tool_call_id="c1"),
    ]
    assert worker_handoff_complete(messages, "stage_a") is False
    assert worker_handoff_complete(messages, "stage_b") is True


def test_handoff_complete_recognises_worker_named_reply() -> None:
    assert worker_handoff_complete([_worker_reply(STAGES[0])], STAGES[0]) is True


def test_handoff_complete_recognises_direct_worker_tool_call() -> None:
    message = AIMessage("", tool_calls=[{"name": STAGES[0], "args": {}, "id": "c1"}])
    assert worker_handoff_complete([message], STAGES[0]) is True


def test_handoff_complete_recognises_transfer_tool_call() -> None:
    message = AIMessage("", tool_calls=[{"name": f"transfer_to_{STAGES[0]}", "args": {}, "id": "c1"}])
    assert worker_handoff_complete([message], STAGES[0]) is True


def test_handoff_complete_recognises_transfer_tool_acknowledgement() -> None:
    """A ``ToolMessage`` acknowledging the handoff counts even without the reply."""
    ack = ToolMessage(content="ack", name=f"transfer_to_{STAGES[0]}", tool_call_id="c1")
    assert worker_handoff_complete([ack], STAGES[0]) is True


def test_handoff_complete_accepts_dict_messages() -> None:
    assert worker_handoff_complete([{"type": "ai", "name": STAGES[0], "content": "r"}], STAGES[0]) is True
    assert worker_handoff_complete(
        [{"type": "ai", "content": "r", "tool_calls": [{"name": f"transfer_to_{STAGES[0]}", "args": {}, "id": "c1"}]}],
        STAGES[0],
    ) is True


def test_handoff_complete_honours_custom_transfer_prefix() -> None:
    message = AIMessage("", tool_calls=[{"name": f"delegate_to_{STAGES[0]}", "args": {}, "id": "c1"}])
    assert worker_handoff_complete([message], STAGES[0], "delegate_to_") is True
    assert worker_handoff_complete([message], STAGES[0]) is False


# --------------------------------------------------------------------------- #
# 3. default_guard_call_ids
# --------------------------------------------------------------------------- #
def test_default_guard_call_ids_are_deterministic() -> None:
    assert default_guard_call_ids(STAGES) == {
        "stage_a": "guard_call_stage_a",
        "stage_b": "guard_call_stage_b",
        "stage_c": "guard_call_stage_c",
    }
    assert default_guard_call_ids(STAGES) == default_guard_call_ids(STAGES)


def test_default_guard_call_ids_accepts_custom_prefix() -> None:
    assert default_guard_call_ids(STAGES, "chk_") == {
        "stage_a": "chk_stage_a",
        "stage_b": "chk_stage_b",
        "stage_c": "chk_stage_c",
    }


def test_default_guard_call_ids_of_empty_order_is_empty() -> None:
    assert default_guard_call_ids(()) == {}


# --------------------------------------------------------------------------- #
# 4. Pass-through cases (no guard action required)
# --------------------------------------------------------------------------- #
def test_guard_no_op_on_empty_state() -> None:
    assert create_domain_guard_hook(STAGES)({"messages": []}) == {}


def test_guard_no_op_when_messages_key_is_missing() -> None:
    assert create_domain_guard_hook(STAGES)({}) == {}


def test_guard_no_op_on_degenerate_state() -> None:
    """``state`` may be ``None`` from a defensive caller; still a clean no-op."""
    assert create_domain_guard_hook(STAGES)(None) == {}


def test_guard_no_op_when_last_message_is_human() -> None:
    hook = create_domain_guard_hook(STAGES)
    assert hook({"messages": [HumanMessage("求解 TSP"), HumanMessage("求解 CVRP")]}) == {}


def test_guard_no_op_when_last_message_is_a_tool_acknowledgement() -> None:
    hook = create_domain_guard_hook(STAGES)
    messages = [HumanMessage("求解"), _transfer(STAGES[0]), ToolMessage("ack", name="x", tool_call_id="c")]
    assert hook({"messages": messages}) == {}


def test_guard_no_op_when_last_message_already_routes() -> None:
    hook = create_domain_guard_hook(STAGES)
    routed = _transfer(STAGES[1], "model_call")
    assert hook({"messages": [HumanMessage("求解"), routed]}) == {}


def test_guard_no_op_when_lead_routes_before_any_stage() -> None:
    """The lead's own routing call is never second-guessed, even if incomplete."""
    hook = create_domain_guard_hook(STAGES)
    assert hook({"messages": [HumanMessage("求解"), _transfer(STAGES[0])]}) == {}


# --------------------------------------------------------------------------- #
# 5. Stage progression 1 → N
# --------------------------------------------------------------------------- #
def test_guard_walks_every_stage_in_order() -> None:
    hook = create_domain_guard_hook(STAGES)
    assert _run_full_pipeline(hook, STAGES) == list(STAGES)


def test_guard_walks_five_stage_tube_order() -> None:
    hook = create_domain_guard_hook(TUBE_PIPELINE_STAGE_ORDER, guard_call_ids=TUBE_GUARD_CALL_IDS)
    assert _run_full_pipeline(hook, TUBE_PIPELINE_STAGE_ORDER) == list(TUBE_PIPELINE_STAGE_ORDER)


def test_guard_progression_issues_expected_call_ids() -> None:
    hook = create_domain_guard_hook(STAGES)
    messages = [HumanMessage("求解")]
    for index, worker in enumerate(STAGES):
        messages.append(_worker_reply(worker))
        messages.append(_bare(f"阶段 {worker} 之后我直接总结", f"m_{index}"))
        if index == len(STAGES) - 1:
            # Every stage has run: the final bare reply must be allowed through.
            assert hook({"messages": messages}) == {}
            continue
        expected = STAGES[index + 1]
        update = hook({"messages": messages})
        assert _injected_tool_call_ids(update) == [f"guard_call_{expected}"]
        assert _last_message(update).id == f"guard_call_{expected}_message"


def test_guard_progression_via_transfer_acknowledgements() -> None:
    """Handoffs recorded only through ``transfer_to_*`` acknowledgements still advance."""
    hook = create_domain_guard_hook(STAGES)
    messages = [HumanMessage("求解")]
    for worker in STAGES[:-1]:
        messages.append(_transfer(worker, f"call_{worker}"))
        messages.append(ToolMessage("ack", name=f"transfer_to_{worker}", tool_call_id=f"call_{worker}"))
    messages.append(_bare("我来总结"))
    update = hook({"messages": messages})
    assert _injected_tool_names(update) == [f"transfer_to_{STAGES[-1]}"]


# --------------------------------------------------------------------------- #
# 6. Earliest missing stage wins
# --------------------------------------------------------------------------- #
def test_guard_prefers_earliest_missing_stage() -> None:
    hook = create_domain_guard_hook(STAGES)
    messages = [
        HumanMessage("求解"),
        _worker_reply("stage_b"),
        _worker_reply("stage_c"),
        _bare("跳过 stage_a 直接给结论"),
    ]
    assert _injected_tool_names(hook({"messages": messages})) == ["transfer_to_stage_a"]


def test_guard_prefers_first_gap_when_several_are_missing() -> None:
    hook = create_domain_guard_hook(("w1", "w2", "w3", "w4"))
    messages = [
        HumanMessage("求解"),
        _worker_reply("w2"),
        _worker_reply("w4"),
        _bare("w1 和 w3 都没做"),
    ]
    assert _injected_tool_names(hook({"messages": messages})) == ["transfer_to_w1"]


def test_guard_rejects_later_stage_substitution() -> None:
    """Completing a later stage never satisfies an unmet earlier one."""
    hook = create_domain_guard_hook(("first", "second"))
    messages = [HumanMessage("求解"), _worker_reply("second"), _bare("final")]
    assert _injected_tool_names(hook({"messages": messages})) == ["transfer_to_first"]


# --------------------------------------------------------------------------- #
# 7. Bare reply permitted ONLY when every stage is complete
# --------------------------------------------------------------------------- #
def test_bare_reply_blocked_until_every_stage_is_complete() -> None:
    hook = create_domain_guard_hook(STAGES)
    for completed in range(len(STAGES)):
        messages = [HumanMessage("求解")]
        messages.extend(_worker_reply(worker) for worker in STAGES[:completed])
        messages.append(_bare("我以为已经做完了", f"partial_{completed}"))
        update = hook({"messages": messages})
        assert update != {}, f"{completed} stages done must still be guarded"
        assert _injected_tool_names(update) == [f"transfer_to_{STAGES[completed]}"]


def test_bare_reply_allowed_only_after_all_three_stages() -> None:
    hook = create_domain_guard_hook(STAGES)
    messages = [HumanMessage("求解")]
    messages.extend(_worker_reply(worker) for worker in STAGES)
    messages.append(_bare("最终结论", "final"))
    assert hook({"messages": messages}) == {}


def test_bare_reply_allowed_when_all_stages_routed_by_transfer_tool() -> None:
    hook = create_domain_guard_hook(STAGES)
    messages = [HumanMessage("求解")]
    for index, worker in enumerate(STAGES):
        messages.append(_transfer(worker, f"call_{index}"))
    messages.append(_bare("最终结论", "final"))
    assert hook({"messages": messages}) == {}


def test_empty_stage_order_allows_bare_reply() -> None:
    hook = create_domain_guard_hook(())
    assert hook({"messages": [HumanMessage("求解"), _bare("没有强制阶段")]}) == {}


def test_stage_order_from_state_is_used_when_bound_order_is_empty() -> None:
    hook = create_domain_guard_hook(())
    state = {"messages": [HumanMessage("求解"), _bare("final", "s1")], "stage_order": ("x_first", "x_second")}
    assert _injected_tool_names(hook(state)) == ["transfer_to_x_first"]


def test_bound_stage_order_wins_over_state_stage_order() -> None:
    hook = create_domain_guard_hook(STAGES)
    state = {"messages": [HumanMessage("求解"), _bare("final", "s2")], "stage_order": ("zzz",)}
    assert _injected_tool_names(hook(state)) == ["transfer_to_stage_a"]


# --------------------------------------------------------------------------- #
# 8. RemoveMessage vs append
# --------------------------------------------------------------------------- #
def test_guard_replaces_id_bearing_reply_via_remove_message() -> None:
    hook = create_domain_guard_hook(STAGES)
    update = hook({"messages": [HumanMessage("求解"), _bare("任务完成", "late_final")]})

    messages = _update_messages(update)
    assert len(messages) == 2
    assert isinstance(messages[0], RemoveMessage)
    assert messages[0].id == "late_final"
    assert isinstance(messages[1], AIMessage)
    assert messages[1].id == "guard_call_stage_a_message"
    assert _injected_tool_names(update) == ["transfer_to_stage_a"]


def test_guard_appends_when_reply_has_no_id() -> None:
    hook = create_domain_guard_hook(STAGES)
    update = hook({"messages": [HumanMessage("求解"), AIMessage("done")]})

    messages = _update_messages(update)
    assert len(messages) == 1
    assert not any(isinstance(message, RemoveMessage) for message in messages)
    assert isinstance(messages[0], AIMessage)
    assert messages[0].id == "guard_call_stage_a_message"
    assert _injected_tool_names(update) == ["transfer_to_stage_a"]


def test_guard_preserves_lazy_reply_content_on_replace() -> None:
    hook = create_domain_guard_hook(STAGES)
    update = hook({"messages": [HumanMessage("求解"), _bare("最优值是 42，任务完成", "c1")]})
    assert _last_message(update).content == "最优值是 42，任务完成"


def test_guard_preserves_lazy_reply_content_on_append() -> None:
    hook = create_domain_guard_hook(STAGES)
    update = hook({"messages": [HumanMessage("求解"), AIMessage("最优值是 42")]})
    assert _last_message(update).content == "最优值是 42"


def test_guard_maps_none_content_to_empty_string() -> None:
    """`AIMessage.content`` is typed as a non-optional string, so ``None`` can only
    appear through a bypass such as ``model_copy(update=...)``. The factory still
    mirrors the reference guards and normalises it to ``""`` rather than
    propagating a ``None`` into the injected handoff."""
    hook = create_domain_guard_hook(STAGES)
    degenerate = AIMessage("x", id="c1").model_copy(update={"content": None})
    assert degenerate.content is None
    update = hook({"messages": [HumanMessage("求解"), degenerate]})
    assert _last_message(update).content == ""


# --------------------------------------------------------------------------- #
# 9. Injection details
# --------------------------------------------------------------------------- #
def test_guard_injects_empty_args_tool_call() -> None:
    hook = create_domain_guard_hook(STAGES)
    update = hook({"messages": [HumanMessage("求解"), _bare("done", "c1")]})
    call = _last_message(update).tool_calls[0]
    assert call["name"] == "transfer_to_stage_a"
    assert call["args"] == {}
    assert call["id"] == "guard_call_stage_a"


def test_guard_uses_explicit_call_ids_and_falls_back_to_default() -> None:
    hook = create_domain_guard_hook(STAGES, guard_call_ids={"stage_b": "custom_b_id"})

    stage_b_update = hook(
        {"messages": [HumanMessage("求解"), _worker_reply("stage_a"), _bare("done", "c2")]}
    )
    assert _injected_tool_call_ids(stage_b_update) == ["custom_b_id"]
    assert _last_message(stage_b_update).id == "custom_b_id_message"

    stage_a_update = hook({"messages": [HumanMessage("求解"), _bare("done", "c1")]})
    assert _injected_tool_call_ids(stage_a_update) == ["guard_call_stage_a"]


def test_guard_honours_custom_transfer_prefix() -> None:
    hook = create_domain_guard_hook(STAGES, transfer_prefix="delegate_to_")
    update = hook({"messages": [HumanMessage("求解"), _bare("done", "c1")]})
    assert _injected_tool_names(update) == ["delegate_to_stage_a"]
    assert _last_message(update).tool_calls[0]["id"] == "guard_call_stage_a"


def test_guard_accepts_list_stage_order() -> None:
    hook = create_domain_guard_hook(list(STAGES))
    assert _injected_tool_names(hook({"messages": [HumanMessage("求解"), _bare("done", "c1")]})) == [
        "transfer_to_stage_a"
    ]


def test_guard_does_not_mutate_caller_state_or_call_id_map() -> None:
    call_ids = default_guard_call_ids(STAGES)
    snapshot = dict(call_ids)
    hook = create_domain_guard_hook(STAGES, guard_call_ids=call_ids)

    bare = _bare("done", "c1")
    state = {"messages": [HumanMessage("求解"), bare]}
    first = hook(state)
    assert hook(state) == first
    assert state["messages"][-1] is bare
    assert call_ids == snapshot


# --------------------------------------------------------------------------- #
# 10. Cross-domain genericity
# --------------------------------------------------------------------------- #
def test_factory_is_generic_across_domains() -> None:
    for domain, stage_order in DOMAIN_STAGE_ORDERS.items():
        hook = create_domain_guard_hook(stage_order)
        assert _run_full_pipeline(hook, stage_order), domain


def test_factory_enforces_arbitrary_single_stage_domain() -> None:
    hook = create_domain_guard_hook(("solo_worker",))
    blocked = hook({"messages": [HumanMessage("求解"), _bare("done", "c1")]})
    assert _injected_tool_names(blocked) == ["transfer_to_solo_worker"]
    assert hook({"messages": [HumanMessage("求解"), _worker_reply("solo_worker"), _bare("done", "c2")]}) == {}


def test_factory_distinguishes_domains_with_same_prefix() -> None:
    """Two domains sharing worker basenames must not cross-contaminate."""
    tube_hook = create_domain_guard_hook(TUBE_PIPELINE_STAGE_ORDER)
    generic_hook = create_domain_guard_hook(("or_tube_geometry", "extra_stage"))

    tube_state = {"messages": [HumanMessage("求解"), _worker_reply(TUBE_GEOMETRY_NAME), _bare("done", "t1")]}
    generic_state = {"messages": [HumanMessage("求解"), _worker_reply(TUBE_GEOMETRY_NAME), _bare("done", "g1")]}

    assert _injected_tool_names(tube_hook(tube_state)) == ["transfer_to_or_tube_q1q2"]
    assert _injected_tool_names(generic_hook(generic_state)) == ["transfer_to_extra_stage"]


# --------------------------------------------------------------------------- #
# 11. Tube B stage-order compatibility
# --------------------------------------------------------------------------- #
def _tube_factory_hook() -> Callable[[Any], dict]:
    return create_domain_guard_hook(TUBE_PIPELINE_STAGE_ORDER, guard_call_ids=TUBE_GUARD_CALL_IDS)


def test_tube_stage_order_is_the_canonical_tube_pipeline() -> None:
    assert TUBE_PIPELINE_STAGE_ORDER == (
        TUBE_GEOMETRY_NAME,
        TUBE_Q1Q2_NAME,
        TUBE_Q3_NAME,
        TUBE_Q4_NAME,
        TUBE_REDTEAM_NAME,
    )


def test_tube_guard_hook_requires_geometry_first() -> None:
    hook = _tube_factory_hook()
    update = hook({"messages": [HumanMessage("run"), _bare("done", "t1")]})
    assert _injected_tool_names(update) == ["transfer_to_or_tube_geometry"]
    assert _last_message(update).tool_calls[0]["id"] == "guard_call_tube_geometry"


def test_tube_guard_hook_walks_geometry_to_redteam() -> None:
    hook = _tube_factory_hook()
    messages = [HumanMessage("run")]
    for worker in TUBE_PIPELINE_STAGE_ORDER[:-1]:
        messages.append(_worker_reply(worker))
        messages.append(_bare("done", f"m_{worker}"))
        update = hook({"messages": messages})
        assert update, f"{worker} done must advance the pipeline"
        nxt = TUBE_PIPELINE_STAGE_ORDER[TUBE_PIPELINE_STAGE_ORDER.index(worker) + 1]
        assert _injected_tool_names(update) == [f"transfer_to_{nxt}"]
        assert _injected_tool_call_ids(update) == [TUBE_GUARD_CALL_IDS[nxt]]

    # redteam is the terminal stage: its reply plus a bare reply must pass through.
    messages.append(_worker_reply(TUBE_REDTEAM_NAME))
    messages.append(_bare("completed", "final"))
    assert hook({"messages": messages}) == {}


def test_tube_guard_hook_matches_reference_on_canonical_flows() -> None:
    """The factory reproduces ``tube_guard_post_hook`` exactly on realistic flows."""
    hook = _tube_factory_hook()
    states = [
        {"messages": []},
        {"messages": [HumanMessage("run")]},
        {"messages": [HumanMessage("run"), _transfer(TUBE_GEOMETRY_NAME, "c0")]},
        {"messages": [HumanMessage("run"), _worker_reply(TUBE_GEOMETRY_NAME)]},
        {"messages": [HumanMessage("run"), _worker_reply(TUBE_GEOMETRY_NAME), _bare("done", "m1")]},
        {
            "messages": [
                HumanMessage("run"),
                _worker_reply(TUBE_GEOMETRY_NAME),
                _worker_reply(TUBE_Q1Q2_NAME),
                _bare("done", "m2"),
            ]
        },
        {
            "messages": [
                HumanMessage("run"),
                _worker_reply(TUBE_GEOMETRY_NAME),
                _worker_reply(TUBE_Q1Q2_NAME),
                _worker_reply(TUBE_Q3_NAME),
                _worker_reply(TUBE_Q4_NAME),
                _bare("done", "m3"),
            ]
        },
        {
            "messages": [
                HumanMessage("run"),
                *[_worker_reply(worker) for worker in TUBE_PIPELINE_STAGE_ORDER],
                _bare("completed", "m4"),
            ]
        },
    ]
    for state in states:
        assert hook(state) == tube_guard_post_hook(state), state


def test_tube_guard_hook_treats_transfer_acknowledgement_as_completed() -> None:
    """Documented superset: a handoff ``ToolMessage`` alone satisfies the stage."""
    hook = _tube_factory_hook()
    messages = [
        HumanMessage("run"),
        _transfer(TUBE_GEOMETRY_NAME, "c1"),
        ToolMessage("ack", name="transfer_to_or_tube_geometry", tool_call_id="c1"),
        _bare("done", "t1"),
    ]
    assert _injected_tool_names(hook({"messages": messages})) == ["transfer_to_or_tube_q1q2"]


def test_tube_guard_hook_allows_final_bare_reply_after_redteam() -> None:
    hook = _tube_factory_hook()
    messages = [
        HumanMessage("run"),
        *[_worker_reply(worker) for worker in TUBE_PIPELINE_STAGE_ORDER],
        _bare("redteam passed", "final"),
    ]
    assert hook({"messages": messages}) == {}


# --------------------------------------------------------------------------- #
# Robustness: non-dict tool-call shapes must not crash or under-detect.
# --------------------------------------------------------------------------- #
class _FakeToolCall:
    """An object-style tool call exposing ``.name`` but no ``.get``."""

    def __init__(self, name: str) -> None:
        self.name = name


def _ai_dict(tool_calls: list[Any], content: str = "") -> dict:
    """Build a raw dict AI-message (bypasses langchain tool_call validation)."""
    return {"type": "ai", "content": content, "tool_calls": tool_calls}


def test_handoff_complete_handles_object_style_tool_calls() -> None:
    """Object tool calls (no ``.get``) must not raise AttributeError."""
    msg = _ai_dict([_FakeToolCall("transfer_to_stage_a")])
    assert worker_handoff_complete([msg], "stage_a") is True
    assert worker_handoff_complete([msg], "stage_b") is False


def test_handoff_complete_handles_openai_nested_tool_calls() -> None:
    """Raw OpenAI-style ``{"function": {"name": ...}}`` entries are recognized."""
    msg = _ai_dict(
        [{"type": "function", "function": {"name": "transfer_to_stage_a", "arguments": "{}"}}]
    )
    assert worker_handoff_complete([msg], "stage_a") is True


def test_handoff_complete_handles_garbage_tool_calls_gracefully() -> None:
    """Garbage tool-call entries return False rather than raising."""
    msg = _ai_dict(["not-a-call", {"unrelated": True}, None])
    assert worker_handoff_complete([msg], "stage_a") is False


def test_guard_hook_injects_after_object_style_transfer() -> None:
    """The guard recognizes an object-style transfer as a completed stage."""
    hook = create_domain_guard_hook(stage_order=STAGES)
    messages = [
        HumanMessage("run"),
        _ai_dict([_FakeToolCall("transfer_to_stage_a")]),
        AIMessage(content="lazy", id="m1"),
    ]
    # stage_a done via object tool call; stage_b is the earliest missing.
    assert _injected_tool_names(hook({"messages": messages})) == ["transfer_to_stage_b"]

