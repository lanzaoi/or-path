#!/usr/bin/env python3
"""Unit tests for the OR-Path four elite specialist factories
(``orpath/agents/workers.py``).

Covers the Plan 1.3 rework of the worker layer:

  * ``or_analyst`` / ``or_modeler`` / ``or_writer`` / ``or_reviewer`` factories
    build into compiled LangGraph graphs with the right ``name`` and an
    isolated fresh message list per ``invoke``;
  * each factory exposes exactly the tool surface its role promises;
  * ``cartridge_tools`` are merged (and de-duplicated) onto the analyst /
    modeler tool surfaces at call time;
  * ``domain_directive`` fragments are injected into the system prompt, while
    an empty directive stays a byte-identical no-op;
  * the retired ``or_verifier_writer`` combined role and the legacy researcher
    relay name are absent from the roster;
  * ``read_problem_file`` reads, truncates and reports failures without raising;
  * ``export_paper_markdown`` persists a report (and reports I/O failures).

Agent construction is offline-safe: the shared model factory falls back to a
placeholder key, and the isolation tests use a deterministic fake chat model so
no network is ever touched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langchain_core.tools import BaseTool, tool  # noqa: E402

from orpath.agents.workers import (  # noqa: E402
    ACADEMIC_WORKER_NAMES,
    ANALYST_NAME,
    MODELER_NAME,
    READ_PROBLEM_FILE_MAX_CHARS,
    REVIEWER_NAME,
    WORKER_AGENT_NAMES,
    WRITER_NAME,
    append_domain_directive,
    create_analyst_agent,
    create_modeler_agent,
    create_reviewer_agent,
    create_writer_agent,
    export_paper_markdown,
    get_academic_workers,
    get_default_workers,
    read_problem_file,
)
from orpath.control_plane import get_chat_model  # noqa: E402

# ``create_react_agent`` is deprecated in LangGraph V1 (moved to
# ``langchain.agents.create_agent``) but is the explicitly required seam here,
# so silence only that one migration warning in test output.
pytestmark = pytest.mark.filterwarnings(
    "ignore:create_react_agent has been moved"
)

try:  # langgraph >= 1.x
    from langgraph.graph.state import CompiledStateGraph
except ImportError:  # pragma: no cover - langgraph < 1.x
    from langgraph.graph import CompiledStateGraph  # type: ignore

# Every env var the model factory consults, so resolution is deterministic.
ENV_KEYS = (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "XFYUN_API_KEY",
    "XFYUN_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
)

FACTORY = {
    "analyst": create_analyst_agent,
    "modeler": create_modeler_agent,
    "writer": create_writer_agent,
    "reviewer": create_reviewer_agent,
}
EXPECTED_NAME = {
    "analyst": ANALYST_NAME,
    "modeler": MODELER_NAME,
    "writer": WRITER_NAME,
    "reviewer": REVIEWER_NAME,
}


class _FakeToolBindingModel(FakeMessagesListChatModel):
    """Deterministic offline chat model that tolerates ``bind_tools``.

    ``create_react_agent`` unconditionally calls ``model.bind_tools(...)``;
    the stock fake raises ``NotImplementedError``. This subclass simply returns
    itself so agent construction + single-step ``invoke`` run fully offline.
    """

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_FakeToolBindingModel":  # noqa: ANN401
        return self


def _fake_model(*replies: str) -> Any:
    return _FakeToolBindingModel(
        responses=[AIMessage(content=r) for r in replies or ("done",)]
    )


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no ambient credentials leak into model resolution."""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture()
def model(clean_env: Any) -> Any:
    return get_chat_model()


@pytest.fixture(params=list(FACTORY))
def worker(request: pytest.FixtureRequest, model: Any) -> Any:
    """One agent per elite factory, all sharing the offline model instance."""
    return FACTORY[request.param](model=model)


def _worker_tools(agent: Any) -> list[str]:
    """Return the tool names actually bound into a compiled agent's tool node."""
    node = agent.nodes["tools"].bound
    return list(getattr(node, "tools_by_name", {}))


def _worker_prompt(agent: Any) -> str:
    """Extract the system prompt text from a compiled ReAct worker agent."""
    p = agent.nodes["agent"].bound.func.__closure__[6].cell_contents.first
    return str(p.invoke({"messages": []})[0].content)


def _payload(tool: BaseTool, **kwargs: Any) -> dict:
    return json.loads(tool.invoke(kwargs))


# --------------------------------------------------------------------------- #
# 1. Agent construction + naming
# --------------------------------------------------------------------------- #
def test_agents_return_compiled_state_graphs(worker: Any) -> None:
    assert isinstance(worker, CompiledStateGraph), (
        f"{worker} is not a CompiledStateGraph"
    )
    assert hasattr(worker, "invoke"), "agent graph must be invokable"
    assert hasattr(worker, "name"), "agent graph must expose a name"


def test_agent_names_match_roles(worker: Any) -> None:
    assert worker.name in set(WORKER_AGENT_NAMES)
    assert worker.name.startswith("or_")


def test_each_factory_produces_expected_name(model: Any) -> None:
    assert create_analyst_agent(model=model).name == ANALYST_NAME == "or_analyst"
    assert create_modeler_agent(model=model).name == MODELER_NAME == "or_modeler"
    assert create_writer_agent(model=model).name == WRITER_NAME == "or_writer"
    assert create_reviewer_agent(model=model).name == REVIEWER_NAME == "or_reviewer"


def test_combined_role_retired_and_roster_is_four_elite() -> None:
    """Plan 1.3: no ``or_verifier_writer`` combined role, no researcher relay."""
    assert WORKER_AGENT_NAMES == (ANALYST_NAME, MODELER_NAME, WRITER_NAME, REVIEWER_NAME)
    assert "or_verifier_writer" not in WORKER_AGENT_NAMES
    assert "or_researcher" not in WORKER_AGENT_NAMES


def test_get_default_workers_order_and_names(clean_env: Any) -> None:
    """The default roster is the four elite workers in pipeline order."""
    workers = get_default_workers()
    assert isinstance(workers, list)
    assert [w.name for w in workers] == list(WORKER_AGENT_NAMES)
    assert all(isinstance(w, CompiledStateGraph) for w in workers)


def test_get_default_workers_accepts_shared_model(model: Any) -> None:
    workers = get_default_workers(model=model)
    assert len(workers) == 4
    assert [w.name for w in workers] == list(WORKER_AGENT_NAMES)


def test_get_academic_workers_roster(model: Any) -> None:
    workers = get_academic_workers(model=model)
    assert len(workers) == 5
    assert [w.name for w in workers] == list(ACADEMIC_WORKER_NAMES)
    assert ACADEMIC_WORKER_NAMES == (
        ANALYST_NAME,
        MODELER_NAME,
        "or_verifier",
        WRITER_NAME,
        REVIEWER_NAME,
    )


# --------------------------------------------------------------------------- #
# 2. Tool surfaces
# --------------------------------------------------------------------------- #
def test_analyst_tools(model: Any) -> None:
    tools = set(_worker_tools(create_analyst_agent(model=model)))
    assert {"read_problem_file", "search_or_knowledge"} <= tools


def test_modeler_tools(model: Any) -> None:
    tools = set(_worker_tools(create_modeler_agent(model=model)))
    assert {
        "list_available_solvers",
        "execute_or_solver",
        "execute_python_sandbox",
        "read_problem_file",
    } <= tools


def test_writer_tools(model: Any) -> None:
    tools = set(_worker_tools(create_writer_agent(model=model)))
    assert {"read_problem_file", "export_paper_markdown"} <= tools


def test_reviewer_tools(model: Any) -> None:
    tools = set(_worker_tools(create_reviewer_agent(model=model)))
    assert {"read_problem_file", "export_paper_markdown"} <= tools


def test_cartridge_tools_are_merged(model: Any) -> None:
    """``cartridge_tools`` mounts DomainCartridge tools onto the agent."""

    @tool
    def profile_scheduling_data() -> str:
        """A cartridge-bound domain tool."""
        return "profile"

    agent = create_analyst_agent(model=model, cartridge_tools=[profile_scheduling_data])
    tools = set(_worker_tools(agent))
    assert "profile_scheduling_data" in tools
    assert "read_problem_file" in tools


def test_cartridge_tools_are_de_duplicated(model: Any) -> None:
    """Passing an already-mounted tool must not duplicate the binding."""
    agent = create_modeler_agent(model=model, cartridge_tools=[read_problem_file])
    tools = _worker_tools(agent)
    assert tools.count("read_problem_file") == 1
    assert len(tools) == 4


def test_cartridge_tools_none_is_noop(model: Any) -> None:
    """``cartridge_tools=None`` keeps the default tool surface intact."""
    with_none = set(_worker_tools(create_analyst_agent(model=model, cartridge_tools=None)))
    default = set(_worker_tools(create_analyst_agent(model=model)))
    assert with_none == default


# --------------------------------------------------------------------------- #
# 3. domain_directive injection
# --------------------------------------------------------------------------- #
def test_append_domain_directive_empty_is_idempotent() -> None:
    prompt = "base prompt"
    assert append_domain_directive(prompt, "") == prompt
    assert append_domain_directive(prompt, None) == prompt
    assert append_domain_directive(prompt, "   ") == prompt


def test_append_domain_directive_appends_section() -> None:
    out = append_domain_directive("base prompt", "JSSP 需考虑换模时延 setup time。")
    assert out.startswith("base prompt")
    assert "领域专业建模指令" in out
    assert "JSSP 需考虑换模时延 setup time。" in out


def test_analyst_domain_directive_reaches_prompt(model: Any) -> None:
    plain = _worker_prompt(create_analyst_agent(model=model))
    directive = "领域建模约定：本算例为柔性作业车间调度 (FJSSP)，必须预留换模时延约束接口。"
    injected = _worker_prompt(
        create_analyst_agent(model=model, domain_directive=directive)
    )
    assert directive in injected
    assert directive not in plain
    assert "领域专业建模指令" in injected
    assert "领域专业建模指令" not in plain


def test_modeler_domain_directive_reaches_prompt(model: Any) -> None:
    directive = "领域建模约定：MILP 切片必须输出余料账本 (residual ledger)。"
    injected = _worker_prompt(
        create_modeler_agent(model=model, domain_directive=directive)
    )
    assert directive in injected
    assert "领域专业建模指令" in injected


def test_writer_reviewer_domain_directive_reaches_prompt(model: Any) -> None:
    directive = "领域约定：评审需核对调度甘特图工件。"
    w = _worker_prompt(create_writer_agent(model=model, domain_directive=directive))
    r = _worker_prompt(create_reviewer_agent(model=model, domain_directive=directive))
    assert directive in w and "领域专业建模指令" in w
    assert directive in r and "领域专业建模指令" in r


# --------------------------------------------------------------------------- #
# 4. Isolated fresh message list per invoke ("互不串味")
# --------------------------------------------------------------------------- #
def test_factories_invoke_in_isolated_message_lists() -> None:
    """Each elite factory invokes in a brand-new local message list that carries
    only the caller's task brief — no cross-agent context pollution."""
    roster = {
        ANALYST_NAME: create_analyst_agent(model=_fake_model("analyst brief echo")),
        MODELER_NAME: create_modeler_agent(model=_fake_model("modeler brief echo")),
        WRITER_NAME: create_writer_agent(model=_fake_model("writer brief echo")),
        REVIEWER_NAME: create_reviewer_agent(model=_fake_model("reviewer brief echo")),
    }

    seen: dict[str, set[str]] = {name: set() for name in roster}
    for name, agent in roster.items():
        result = agent.invoke({"messages": [HumanMessage(f"task brief {name}")]})
        contents = {
            c.content
            for m in result["messages"]
            for c in [m]
            if isinstance(c.content, str)
        }
        # The only brief present is this agent's own: ``seen`` self-entry is
        # skipped (its own brief legitimately appears); every other agent's
        # brief must be absent from this fresh message list.
        for other in seen:
            if other == name:
                continue
            assert not any(
                f"task brief {other}" in content for content in contents
            ), f"{name} leaked {other}'s context"
        seen[name] = contents
        # Every invoke starts fresh: exactly the injected HumanMessage + reply.
        assert result["messages"][0].content == f"task brief {name}"
        assert len(result["messages"]) == 2

    # Factories are independent instances: invoking one never mutates another.
    again = roster[ANALYST_NAME].invoke({"messages": [HumanMessage("second analyst brief")]})
    assert again["messages"][0].content == "second analyst brief"
    assert len(again["messages"]) == 2


def test_cartridge_injection_does_not_break_isolation() -> None:
    """Injecting cartridge tools + directives keeps the agent invocable offline."""

    @tool
    def profile_microgrid_data() -> str:
        """A cartridge-bound domain tool."""
        return "profile"

    agent = create_modeler_agent(
        model=_fake_model("modeler done"),
        cartridge_tools=[profile_microgrid_data],
        domain_directive="微电网算例：注意 SOC 守恒。",
    )
    result = agent.invoke({"messages": [HumanMessage("solve the microgrid case")]})
    assert result["messages"][0].content == "solve the microgrid case"
    assert "modeler done" in result["messages"][-1].content


# --------------------------------------------------------------------------- #
# 5. read_problem_file
# --------------------------------------------------------------------------- #
def test_read_problem_file_is_base_tool() -> None:
    assert isinstance(read_problem_file, BaseTool)
    assert set(read_problem_file.args_schema.model_fields) == {"file_path", "max_chars"}
    assert read_problem_file.args_schema.model_fields["file_path"].is_required()


def test_read_problem_file_reads_file(tmp_path: Path) -> None:
    target = tmp_path / "problem.md"
    target.write_text("hello OR-Path\nsecond line\n", encoding="utf-8")

    out = read_problem_file.invoke({"file_path": str(target)})
    assert "file_path=" in out
    assert "truncated=false" in out
    assert "hello OR-Path" in out
    assert "second line" in out


def test_read_problem_file_default_limit_matches_constant(tmp_path: Path) -> None:
    target = tmp_path / "big.txt"
    target.write_text("x" * 500, encoding="utf-8")
    out = read_problem_file.invoke({"file_path": str(target)})
    assert f"max_chars={READ_PROBLEM_FILE_MAX_CHARS}" in out


def test_read_problem_file_truncates(tmp_path: Path) -> None:
    target = tmp_path / "long.txt"
    target.write_text("0123456789", encoding="utf-8")

    out = read_problem_file.invoke({"file_path": str(target), "max_chars": 4})
    assert "truncated=true" in out
    assert "returned=4" in out
    # only the first four characters of the body are present
    assert "0123" in out
    assert "456789" not in out.split("---", 1)[1]


def test_read_problem_file_missing_file_reports_error(tmp_path: Path) -> None:
    out = read_problem_file.invoke({"file_path": str(tmp_path / "nope.txt")})
    assert "error=file_not_found" in out


def test_read_problem_file_directory_reports_error(tmp_path: Path) -> None:
    out = read_problem_file.invoke({"file_path": str(tmp_path)})
    assert "error=is_a_directory" in out


# --------------------------------------------------------------------------- #
# 6. export_paper_markdown
# --------------------------------------------------------------------------- #
def test_export_paper_markdown_is_base_tool() -> None:
    assert isinstance(export_paper_markdown, BaseTool)
    assert set(export_paper_markdown.args_schema.model_fields) == {"output_path", "content"}
    assert export_paper_markdown.args_schema.model_fields["output_path"].is_required()


def test_export_paper_markdown_writes_content(tmp_path: Path) -> None:
    target = tmp_path / "paper.md"
    content = "# Title\n\nBody text\n"
    payload = _payload(export_paper_markdown, output_path=str(target), content=content)

    assert payload["success"] is True
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == content
    assert payload["bytes"] == target.stat().st_size
    assert payload["lines"] == len(content.splitlines())


def test_export_paper_markdown_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "papers" / "deep" / "q3.md"
    payload = _payload(export_paper_markdown, output_path=str(target), content="body")
    assert payload["success"] is True
    assert target.read_text(encoding="utf-8") == "body"


def test_export_paper_markdown_reports_failure(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked.md"
    blocked.write_text("occupies the file name", encoding="utf-8")
    payload = _payload(export_paper_markdown, output_path=str(blocked / "child.md"), content="x")
    assert payload["success"] is False
    assert "detail" in payload and payload["detail"]


# --------------------------------------------------------------------------- #
# 7. Elite prompt specifications & anti-overstepping
# --------------------------------------------------------------------------- #
def test_analyst_prompt_profile_classification_and_tiering(model: Any) -> None:
    agent = create_analyst_agent(model=model)
    prompt = _worker_prompt(agent)
    assert "Analyst" in prompt or "or_analyst" in prompt
    assert "read_problem_file" in prompt
    assert "数据画像" in prompt
    assert "数学分类" in prompt
    assert "Tier-A" in prompt and "Tier-B" in prompt
    assert "防角色越界" in prompt or "Anti-Overstepping" in prompt
    assert "严禁编写任何求解代码" in prompt
    assert "严禁猜解" in prompt
    assert "500" in prompt


def test_modeler_prompt_schema_gap_and_no_hand_solved_values(model: Any) -> None:
    agent = create_modeler_agent(model=model)
    prompt = _worker_prompt(agent)
    assert "schema.json" in prompt
    assert "list_available_solvers" in prompt
    assert "execute_or_solver" in prompt
    assert "execute_python_sandbox" in prompt
    assert "proven_optimal" in prompt
    assert "下界与 Gap" in prompt
    assert "严禁手写解 JSON 数值" in prompt
    assert "防角色越界" in prompt or "Anti-Overstepping" in prompt


def test_writer_prompt_prerendered_tables_and_six_chapters(model: Any) -> None:
    agent = create_writer_agent(model=model)
    prompt = _worker_prompt(agent)
    assert "docs/or-paper-sop.md" in prompt or "六章" in prompt
    assert "预渲染" in prompt
    assert "摘要" in prompt
    assert "LaTeX" in prompt
    assert "敏感性分析" in prompt
    assert "export_paper_markdown" in prompt


def test_reviewer_prompt_ten_point_rubric_and_graded_defects(model: Any) -> None:
    agent = create_reviewer_agent(model=model)
    prompt = _worker_prompt(agent)
    assert "十项" in prompt or "十项严苛自审核对清单" in prompt
    assert "FATAL" in prompt
    assert "MAJOR" in prompt
    assert "MINOR" in prompt
    assert "PASS" in prompt and "REVISE" in prompt
    assert "outputs/<slug>-review.md" in prompt or "review.md" in prompt


if __name__ == "__main__":  # pragma: no cover - manual smoke
    import warnings

    warnings.simplefilter("ignore")
    for worker in get_default_workers():
        print(type(worker).__name__, "->", worker.name)
