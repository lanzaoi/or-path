#!/usr/bin/env python3
"""Offline tests for Phase 1: Single-Agent Fast Mode + On-Demand Paper + Retry/Quality Marking."""
from __future__ import annotations

import base64
import contextlib
import json
import os
import shutil
import socket
import sys
import threading
import urllib.error
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
SCRIPTS = ROOT / "scripts"
for _p in (str(ROOT), str(SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import orpath.control_plane as control_plane  # noqa: E402
import orpath.paper_workflow as paper_workflow  # noqa: E402
import orpath.pipeline.paper as paper_pipe  # noqa: E402
import orpath.pipeline.solve as solve_pipe  # noqa: E402
import orpath.run_orpath as run_orpath  # noqa: E402
import orpath_watch  # noqa: E402

pytestmark = pytest.mark.filterwarnings(
    "ignore:create_react_agent has been moved",
    "ignore:No supported",
)


@pytest.fixture(autouse=True)
def _restore_orpath_env():
    old_wd = os.environ.get("ORPATH_WORKDIR")
    old_home = os.environ.get("ORPATH_HOME")
    try:
        yield
    finally:
        if old_wd is None:
            os.environ.pop("ORPATH_WORKDIR", None)
        else:
            os.environ["ORPATH_WORKDIR"] = old_wd
        if old_home is None:
            os.environ.pop("ORPATH_HOME", None)
        else:
            os.environ["ORPATH_HOME"] = old_home

EXPECTED_TSP_OBJECTIVE = 154


def _post_json(url: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": raw}


def _get_json(url: str) -> tuple[int, dict[str, Any]]:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


@contextlib.contextmanager
def _serve(workdir: Path):
    handler = partial(
        orpath_watch.WatchHandler,
        home=workdir,
        workdir=workdir,
        directory=str(orpath_watch.WEB_DIR),
    )
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _import_tsp_folder(base: str, slug: str) -> None:
    prob_md = (
        "# 8工位巡检规划问题\n"
        "问题一：访问全部8个站点并回到起点，使巡检总路线最短。\n"
        "约束：站点不重复。"
    )
    coords = json.dumps({"coords": [{"id": i, "x": i * 10, "y": i * 5} for i in range(8)]})
    code, res = _post_json(
        base + "/api/intake/import",
        {
            "mode": "folder",
            "slug": slug,
            "files": [
                {
                    "rel_path": "problem.md",
                    "content_base64": base64.b64encode(prob_md.encode()).decode(),
                },
                {
                    "rel_path": "data/coords.json",
                    "content_base64": base64.b64encode(coords.encode()).decode(),
                },
            ],
        },
    )
    assert code == 200 and res.get("ok"), f"import failed: {res}"


def _import_unregistered_folder(base: str, slug: str) -> None:
    prob_md = "# 未知自定义调度场景\n无结构化算例矩阵，仅描述文字约束。"
    code, res = _post_json(
        base + "/api/intake/import",
        {
            "mode": "folder",
            "slug": slug,
            "files": [
                {
                    "rel_path": "problem.md",
                    "content_base64": base64.b64encode(prob_md.encode()).decode(),
                }
            ],
        },
    )
    assert code == 200 and res.get("ok"), f"import failed: {res}"


def _seed_tsp_case_workdir(wd: Path, slug: str) -> None:
    """Seed an inbox TSP case under ``wd/inbox/<slug>`` so tmp_path runs cleanly offline."""
    case_dir = wd / "inbox" / slug
    (case_dir / "data").mkdir(parents=True, exist_ok=True)
    (case_dir / "problem.md").write_text(
        "# 8工位巡检规划问题\n问题一：访问全部8个站点并回到起点，使巡检总路线最短。\n约束：站点不重复。\n",
        encoding="utf-8",
    )
    coords = {"coords": [{"id": i, "x": i * 10, "y": i * 5} for i in range(8)]}
    (case_dir / "data" / "coords.json").write_text(json.dumps(coords), encoding="utf-8")


# --------------------------------------------------------------------------- #
# 1. Graph skip_paper bypass + provenance stale-draft protection
# --------------------------------------------------------------------------- #
def test_skip_paper_bypasses_paper_nodes_and_protects_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slug = "fast-sp-skip"
    _seed_tsp_case_workdir(tmp_path, slug)

    # Pre-create stale drafts & paper to verify node_provenance does NOT promote them.
    drafts_dir = tmp_path / "outputs" / ".drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    (drafts_dir / f"{slug}-draft.md").write_text("# STALE DRAFT\n", encoding="utf-8")
    (drafts_dir / f"{slug}-cited.md").write_text("# STALE CITED\n", encoding="utf-8")
    (drafts_dir / f"{slug}-revised.md").write_text("# STALE REVISED\n", encoding="utf-8")
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    stale_paper = papers_dir / f"{slug}.md"
    stale_paper.write_text("STALE_PREEXISTING_PAPER\n", encoding="utf-8")

    called_paper_nodes: list[str] = []

    def _forbid(name: str):
        def _inner(_state: Any) -> dict[str, Any]:
            called_paper_nodes.append(name)
            raise AssertionError(f"{name} should be skipped when skip_paper=True")
        return _inner

    monkeypatch.setattr(paper_pipe, "node_draft_paper", _forbid("draft_paper"))
    monkeypatch.setattr(paper_pipe, "node_cite_pack", _forbid("cite_pack"))
    monkeypatch.setattr(paper_pipe, "node_review_pack", _forbid("review_pack"))
    monkeypatch.setattr(paper_pipe, "node_revise_or_done", _forbid("revise_or_done"))

    initial = control_plane.default_initial(
        root=tmp_path,
        slug=slug,
        problem_id=slug,
        problem_class="tsp",
        solve_mode="ortools",
        knowledge_mode="off",
        live_subagent=False,
        thread_id=slug,
        is_replay=False,
        replay_authorized=False,
        run_mode="fast",
        skip_paper=True,
    )
    app = control_plane.build_graph(checkpointer=None)
    final = app.invoke(initial)

    assert called_paper_nodes == []
    assert final.get("gate_validate_ok") is True
    assert final.get("run_mode") == "fast"
    assert final.get("skip_paper") is True
    assert final.get("paper_path") == ""
    assert final.get("paper_quality") == "skipped"
    # Pre-existing stale paper must NOT have been overwritten by stale drafts
    assert stale_paper.read_text(encoding="utf-8") == "STALE_PREEXISTING_PAPER\n"

    prov_path = Path(final["provenance_path"])
    assert prov_path.is_file()
    prov_text = prov_path.read_text(encoding="utf-8")
    assert "- Verification: PASS\n" in prov_text
    assert "PASS WITH NOTES" not in prov_text
    assert "- run_mode: fast\n" in prov_text
    assert "- skip_paper: True\n" in prov_text
    assert "- paper_quality: skipped\n" in prov_text


# --------------------------------------------------------------------------- #
# 2. Studio confirm fast mode + POST /api/studio/paper
# --------------------------------------------------------------------------- #
def test_studio_confirm_fast_skips_multiagent_and_defers_paper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ma_calls: list[Any] = []

    def _forbid_ma(*args: Any, **kwargs: Any) -> Any:
        ma_calls.append((args, kwargs))
        raise AssertionError("build_compiled_multiagent must NOT be called in fast mode")

    monkeypatch.setattr(control_plane, "build_compiled_multiagent", _forbid_ma)

    slug = "fast-tsp-studio"
    slug_blocked = "fast-blocked-studio"

    with _serve(tmp_path) as base:
        # Health check includes /api/studio/paper
        h_code, health = _get_json(base + "/api/health")
        assert h_code == 200
        assert "/api/studio/paper" in (health.get("endpoints") or [])

        # Missing solution -> /api/studio/paper returns 400
        m_code, m_res = _post_json(base + "/api/studio/paper", {"slug": "no-such-slug"})
        assert m_code == 400 and m_res.get("ok") is False

        # Scenario A: Registered TSP with omitted run_mode (defaults to fast + skip_paper=True)
        _import_tsp_folder(base, slug)
        c_code, c_res = _post_json(
            base + "/api/studio/confirm",
            {"slug": slug, "selected_options": {"q_algorithm": "ortools"}, "extra_prompt": ""},
        )
        assert c_code == 200 and c_res.get("ok") is True
        assert c_res.get("status") == "COMPLETED"
        assert c_res.get("run_mode") == "fast"
        assert c_res.get("skip_paper") is True
        assert c_res.get("paper_generated") is False
        assert c_res.get("paper_path") == ""
        assert c_res.get("paper_quality") == "skipped"
        assert c_res.get("data_source") == "case"
        assert c_res.get("blocked_reason") == ""
        assert (c_res.get("solution") or {}).get("objective") == EXPECTED_TSP_OBJECTIVE
        assert (c_res.get("validation") or {}).get("ok") is True
        assert ma_calls == []
        assert not (tmp_path / "papers" / f"{slug}.md").is_file()

        # On-demand deferred paper generation (offline -> template_render)
        p_code, p_res = _post_json(base + "/api/studio/paper", {"slug": slug})
        assert p_code == 200 and p_res.get("ok") is True, f"paper failed: {p_res}"
        assert p_res.get("paper_generated") is True
        assert p_res.get("paper_quality") == "template_render"
        assert Path(p_res["paper_path"]).is_file()
        assert isinstance(p_res.get("gate_r1_ok"), bool)
        assert isinstance(p_res.get("gate_r2_ok"), bool)

        # Scenario B: Blocked solve -> confirms BLOCKED, /api/studio/paper refuses with 400
        _import_unregistered_folder(base, slug_blocked)
        b_code, b_res = _post_json(
            base + "/api/studio/confirm",
            {"slug": slug_blocked, "selected_options": {}, "extra_prompt": ""},
        )
        assert b_code == 200 and b_res.get("status") == "BLOCKED"
        assert b_res.get("run_mode") == "fast"
        assert b_res.get("skip_paper") is True
        assert b_res.get("paper_generated") is False
        assert b_res.get("paper_quality") == "skipped"
        assert b_res.get("blocked_reason")

        bp_code, bp_res = _post_json(base + "/api/studio/paper", {"slug": slug_blocked})
        assert bp_code == 400 and bp_res.get("ok") is False
        assert "BLOCKED" in str(bp_res.get("error") or "")


def test_studio_paper_endpoint_marks_llm_writer_when_live_mocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slug = "live-paper-studio"
    sol_dir = tmp_path / "outputs"
    sol_dir.mkdir(parents=True, exist_ok=True)
    # Create a real TSP inbox case + solution/validate without paper
    _seed_tsp_case_workdir(tmp_path, slug)
    init = control_plane.default_initial(
        root=tmp_path,
        slug=slug,
        problem_id=slug,
        problem_class="tsp",
        solve_mode="ortools",
        knowledge_mode="off",
        live_subagent=False,
        thread_id=slug,
        is_replay=False,
        replay_authorized=False,
        run_mode="fast",
        skip_paper=True,
    )
    control_plane.build_graph(checkpointer=None).invoke(init)
    assert not (tmp_path / "papers" / f"{slug}.md").is_file()

    class _FakeMsg:
        def __init__(self, content: str) -> None:
            self.content = content

    class _FakeLLM:
        def invoke(self, _msgs: Any) -> _FakeMsg:
            sol = json.loads((tmp_path / "outputs" / f"{slug}-solution.json").read_text(encoding="utf-8"))
            obj = sol["objective"]
            body = (
                f"# Academic Paper for {slug}\n\n"
                f"## 1. Abstract & Key Indicators\n"
                f"Verified optimal shortest path objective = {obj}.\n\n"
                + ("## 2. Problem Statement\nDetailed OR model narrative.\n\n" * 20)
                + "## 3. Mathematical Formulation\n$$\\min \\sum w_{ij} x_{ij}$$\n\n"
                + "## 4. Solution Strategy\nDijkstra exact solver.\n\n"
                + f"## 5. Computational Results\nObjective = {obj} from `{tmp_path / 'outputs' / f'{slug}-solution.json'}`.\n\n"
                + "## 6. Limitations\nNone.\n"
            )
            return _FakeMsg(body)

    monkeypatch.setattr(paper_workflow, "is_live_paper_agent_enabled", lambda _s=None: True)
    monkeypatch.setattr(control_plane, "get_chat_model", lambda *a, **kw: _FakeLLM())

    with _serve(tmp_path) as base:
        code, res = _post_json(
            base + "/api/studio/paper",
            {"slug": slug, "force_live_agent": True},
        )
    assert code == 200 and res.get("ok") is True
    assert res.get("paper_generated") is True
    assert res.get("paper_quality") == "llm_writer"
    assert Path(res["paper_path"]).is_file()


# --------------------------------------------------------------------------- #
# 3. node_model single-agent fast mode on custom/unregistered problems
# --------------------------------------------------------------------------- #
def test_node_model_fast_mode_offline_fails_closed_without_isolated_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _forbid_isolated(*_a: Any, **_kw: Any) -> Any:
        raise AssertionError("_run_isolated_pipeline must NOT be called when run_mode='fast'")

    monkeypatch.setattr(solve_pipe, "_run_isolated_pipeline", _forbid_isolated)

    state = control_plane.default_initial(
        root=tmp_path,
        slug="custom-fast-off",
        problem_id="custom_fast_off",
        problem_class="custom_unregistered",
        solve_mode="",
        knowledge_mode="off",
        live_subagent=False,
        thread_id="custom-fast-off",
        is_replay=False,
        replay_authorized=False,
        run_mode="fast",
        skip_paper=True,
    )
    out = solve_pipe.node_model(state)  # type: ignore[arg-type]
    assert out["stage"] == "human_stop"
    assert out["human_required"] is True
    assert not (tmp_path / "outputs" / "custom-fast-off-schema.json").is_file()


def test_node_model_fast_mode_live_single_agent_modeler_validated_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _forbid_isolated(*_a: Any, **_kw: Any) -> Any:
        raise AssertionError("_run_isolated_pipeline must NOT be called when run_mode='fast'")

    monkeypatch.setattr(solve_pipe, "_run_isolated_pipeline", _forbid_isolated)

    # Mock create_modeler_agent to write a real custom_mip solution validated by validate_solution.py
    import orpath.agents.workers as workers

    created_agents: list[str] = []

    class _MockModelerAgent:
        def invoke(self, _inp: Any, config: Any = None) -> dict[str, Any]:
            assert config is not None and config.get("recursion_limit") >= 6
            out_dir = tmp_path / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            custom_val_p = out_dir / "custom-fast-live-custom-validate.json"
            custom_val_p.write_text(
                json.dumps({"ok": True, "objective": 15.0, "checks": [{"name": "c1", "ok": True}]}),
                encoding="utf-8",
            )
            sol_p = out_dir / "custom-fast-live-solution.json"
            sol_doc = {
                "problem_id": "custom_fast_live",
                "problem_class": "custom_mip",
                "solver": "highs",
                "source": "or_modeler_single_agent",
                "status": "OPTIMAL",
                "objective": 15.0,
                "validation_report": str(custom_val_p),
                "vars": {"x1": 2.0, "x2": 1.0},
                "meta": {"proven_optimal": True, "exact": True, "is_replay": False, "data_source": "case"},
            }
            sol_p.write_text(json.dumps(sol_doc, indent=2), encoding="utf-8")
            return {"messages": []}

    def _fake_create_modeler(*_a: Any, **_kw: Any) -> _MockModelerAgent:
        created_agents.append("or_modeler")
        return _MockModelerAgent()

    monkeypatch.setattr(control_plane, "get_chat_model", lambda *a, **kw: object())
    monkeypatch.setattr(workers, "create_modeler_agent", _fake_create_modeler)

    state = control_plane.default_initial(
        root=tmp_path,
        slug="custom-fast-live",
        problem_id="custom_fast_live",
        problem_class="custom_mip",
        solve_mode="",
        knowledge_mode="off",
        live_subagent=True,
        thread_id="custom-fast-live",
        is_replay=False,
        replay_authorized=False,
        run_mode="fast",
        skip_paper=True,
    )
    state["force_live_agent"] = True
    out = solve_pipe.node_model(state)  # type: ignore[arg-type]

    assert created_agents == ["or_modeler"]
    assert out["stage"] == "gate_schema"
    assert out["gate_subagent_ok"] is True
    assert Path(out["schema_path"]).is_file()
    assert Path(out["solution_path"]).is_file()
    assert Path(out["validate_path"]).is_file()


# --------------------------------------------------------------------------- #
# 4. invoke_with_backoff retry & paper_quality fallback marking
# --------------------------------------------------------------------------- #
def test_invoke_with_backoff_retries_transient_and_marks_template_render_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps: list[float] = []
    attempts = {"n": 0}

    class _FlakyModel:
        def invoke(self, _msgs: Any) -> dict[str, str]:
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise TimeoutError("simulated 504 timeout")
            return {"content": "ok"}

    res = control_plane.invoke_with_backoff(
        _FlakyModel(),
        ["hi"],
        max_retries=3,
        base_delay=0.5,
        sleep_fn=sleeps.append,
    )
    assert res == {"content": "ok"}
    assert attempts["n"] == 3
    assert sleeps == [0.5, 1.0]

    # Non-transient error raises immediately with zero retries
    non_transient_calls = {"n": 0}

    class _BadPromptModel:
        def invoke(self, _msgs: Any) -> Any:
            non_transient_calls["n"] += 1
            raise ValueError("invalid schema parameter")

    with pytest.raises(ValueError):
        control_plane.invoke_with_backoff(_BadPromptModel(), ["hi"], max_retries=3, sleep_fn=sleeps.append)
    assert non_transient_calls["n"] == 1

    # Always-failing live writer degrades cleanly to template_render + reason
    class _AlwaysTimeoutModel:
        def invoke(self, _msgs: Any) -> Any:
            raise TimeoutError("429 Too Many Requests")

    monkeypatch.setenv("ORPATH_LLM_MAX_RETRIES", "1")
    monkeypatch.setenv("ORPATH_LLM_RETRY_DELAY", "0")
    monkeypatch.setattr(paper_workflow, "is_live_paper_agent_enabled", lambda _s=None: True)

    sol_path = tmp_path / "outputs" / "t1_sp-solution.json"
    sol_path.parent.mkdir(parents=True, exist_ok=True)
    sol_doc = {
        "problem_id": "t1_sp",
        "problem_class": "shortest_path",
        "solver": "networkx",
        "status": "OPTIMAL",
        "objective": 7,
        "path": ["A", "B", "D"],
    }
    sol_path.write_text(json.dumps(sol_doc), encoding="utf-8")
    q_out: dict[str, Any] = {}
    draft_path = tmp_path / "outputs" / ".drafts" / "t1_sp-draft.md"
    with pytest.warns(RuntimeWarning):
        body = paper_workflow.draft_paper_with_writer(
            root=tmp_path,
            slug="t1_sp",
            problem_class="shortest_path",
            problem_id="t1_sp",
            solution=sol_doc,
            solution_path=str(sol_path),
            paper_path=draft_path,
            model=_AlwaysTimeoutModel(),
            state={"live_subagent": True, "force_live_agent": True},
            quality_out=q_out,
        )
    assert body and draft_path.is_file()
    assert q_out.get("paper_quality") == "template_render"
    assert "TimeoutError" in str(q_out.get("paper_degraded_reason") or "")


# --------------------------------------------------------------------------- #
# 5. CLI --run-mode fast --skip-paper and `paper` subcommand
# --------------------------------------------------------------------------- #
def test_cli_fast_mode_then_paper_subcommand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    slug = "cli-fast-sp"
    _seed_tsp_case_workdir(tmp_path, slug)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_orpath.py",
            "run",
            "--workdir",
            str(tmp_path),
            "--slug",
            slug,
            "--problem-id",
            slug,
            "--problem-class",
            "tsp",
            "--solve-mode",
            "ortools",
            "--knowledge-mode",
            "off",
            "--no-live-subagent",
            "--run-mode",
            "fast",
            "--skip-paper",
            "--fresh",
        ],
    )
    rc1 = run_orpath.main()
    out1 = json.loads(capsys.readouterr().out)
    assert rc1 == 0
    assert out1["run_mode"] == "fast"
    assert out1["skip_paper"] is True
    assert out1["paper_quality"] == "skipped"
    assert not (tmp_path / "papers" / f"{slug}.md").is_file()

    # Now run deferred `paper` subcommand
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_orpath.py",
            "paper",
            "--workdir",
            str(tmp_path),
            "--slug",
            slug,
            "--from-stage",
            "draft_paper",
            "--no-live-subagent",
        ],
    )
    rc2 = run_orpath.main()
    out2 = json.loads(capsys.readouterr().out)
    assert rc2 == 0
    assert out2["ok"] is True
    assert out2["paper_generated"] is True
    assert out2["paper_quality"] == "template_render"
    assert Path(out2["paper_path"]).is_file()


def _write_valid_custom_mip_artifacts(root: Path, slug: str, objective: float = 42.0) -> tuple[Path, Path, Path]:
    outputs_dir = root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    rep_rel = f"outputs/{slug}-custom-validate.json"
    rep_path = root / rep_rel
    rep_path.write_text(
        json.dumps({"ok": True, "objective": objective, "checks": [{"name": "c1", "ok": True}]}, indent=2),
        encoding="utf-8",
    )
    sol_path = outputs_dir / f"{slug}-solution.json"
    sol_path.write_text(
        json.dumps(
            {
                "problem_id": slug,
                "problem_class": "custom_mip",
                "status": "OPTIMAL",
                "objective": objective,
                "solver": "custom_mip",
                "source": "or_modeler_single_agent",
                "validation_report": rep_rel,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    schema_path = outputs_dir / f"{slug}-schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "slug": slug,
                "problem_id": slug,
                "problem_class": "custom_mip",
                "preferred_solve_mode": "auto",
                "constraints": ["x + y <= 4"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return sol_path, schema_path, rep_path


def test_fast_mode_custom_mip_full_graph_end_to_end(tmp_path: Path, monkeypatch) -> None:
    """Full build_graph() custom_mip fast mode passes schema/validate/explain/provenance cleanly."""
    from orpath.control_plane import build_graph, default_initial
    import orpath.control_plane as cp
    import orpath.agents.workers as workers

    slug = "custom-fast-e2e"
    prob_file = tmp_path / "inbox" / slug / "problem.txt"
    prob_file.parent.mkdir(parents=True, exist_ok=True)
    prob_file.write_text("Maximize 6x + 5y subject to x + y <= 7, x,y >= 0.\n", encoding="utf-8")

    monkeypatch.setenv("ORPATH_WORKDIR", str(tmp_path))
    monkeypatch.setattr(cp, "is_real_llm_configured", lambda: False)

    captured_calls: list[dict[str, Any]] = []

    class _DummyModel:
        def bind_tools(self, tools, **kwargs):
            return self

        def invoke(self, *args, **kwargs):
            return None

    def _fake_get_chat_model(*, model_name=None, temperature=0.2, http_client=None, timeout=None):
        captured_calls.append({"model_name": model_name, "timeout": timeout})
        return _DummyModel()

    class _FakeModelerAgent:
        def invoke(self, payload, config=None):
            _write_valid_custom_mip_artifacts(tmp_path, slug, objective=42.0)
            return {"messages": []}

    monkeypatch.setattr(cp, "get_chat_model", _fake_get_chat_model)
    monkeypatch.setattr(workers, "create_modeler_agent", lambda **kwargs: _FakeModelerAgent())

    app = build_graph()
    init_state = default_initial(
        root=tmp_path,
        slug=slug,
        problem_id=slug,
        problem_class="custom_mip",
        solve_mode="auto",
        knowledge_mode="off",
        live_subagent=True,
        thread_id=f"t-{slug}",
        run_mode="fast",
        skip_paper=True,
    )
    init_state["problem_file"] = str(prob_file)
    init_state["llm_model"] = "spark-x2.6"
    init_state["force_live_agent"] = True

    final = app.invoke(init_state, {"configurable": {"thread_id": f"t-{slug}"}})

    assert captured_calls, "expected single-agent modeler to request get_chat_model"
    assert captured_calls[0]["model_name"] == "spark-x2.6"
    assert captured_calls[0]["timeout"] is not None and 5.0 <= captured_calls[0]["timeout"] <= 120.0
    assert final["stage"] == "end"
    assert final.get("human_required") is False
    assert final.get("gate_schema_ok") is True
    assert final.get("gate_validate_ok") is True
    assert final.get("paper_quality") == "skipped"
    assert not final.get("paper_path")
    assert not (tmp_path / "papers" / f"{slug}.md").exists()
    prov_path = tmp_path / "outputs" / f"{slug}.provenance.md"
    assert prov_path.is_file()
    prov_text = prov_path.read_text(encoding="utf-8")
    assert "Verification: PASS" in prov_text
    assert "PASS WITH NOTES" not in prov_text


def test_fast_mode_custom_mip_unvalidated_solution_cleaned_and_fails_closed(tmp_path: Path, monkeypatch) -> None:
    """Unvalidated solution from fast or_modeler is removed and fails closed to human_stop."""
    from orpath.control_plane import build_graph, default_initial
    import orpath.control_plane as cp
    import orpath.agents.workers as workers

    slug = "custom-fast-bad"
    monkeypatch.setenv("ORPATH_WORKDIR", str(tmp_path))
    monkeypatch.setattr(cp, "is_real_llm_configured", lambda: False)

    class _DummyModel:
        def bind_tools(self, tools, **kwargs):
            return self

    class _FakeBadModeler:
        def invoke(self, payload, config=None):
            out = tmp_path / "outputs"
            out.mkdir(parents=True, exist_ok=True)
            # Missing validation_report and custom-validate.json -> gate_validate MUST fail
            (out / f"{slug}-solution.json").write_text(
                json.dumps({"problem_id": slug, "problem_class": "custom_mip", "status": "OPTIMAL", "objective": 999}),
                encoding="utf-8",
            )
            (out / f"{slug}-schema.json").write_text(
                json.dumps({"slug": slug, "problem_id": slug, "problem_class": "custom_mip", "constraints": ["x >= 0"]}),
                encoding="utf-8",
            )
            return {"messages": []}

    monkeypatch.setattr(cp, "get_chat_model", lambda **kwargs: _DummyModel())
    monkeypatch.setattr(workers, "create_modeler_agent", lambda **kwargs: _FakeBadModeler())

    app = build_graph()
    init_state = default_initial(
        root=tmp_path,
        slug=slug,
        problem_id=slug,
        problem_class="custom_mip",
        solve_mode="auto",
        knowledge_mode="off",
        live_subagent=True,
        thread_id=f"t-{slug}",
        run_mode="fast",
        skip_paper=True,
    )
    init_state["force_live_agent"] = True

    final = app.invoke(init_state, {"configurable": {"thread_id": f"t-{slug}"}})
    assert final["stage"] == "end"
    assert final.get("human_required") is True
    assert not (tmp_path / "outputs" / f"{slug}-solution.json").exists()
    assert not (tmp_path / "outputs" / f"{slug}-schema.json").exists()


def test_studio_paper_endpoint_model_routing_and_offline_override(tmp_path: Path, monkeypatch) -> None:
    """POST /api/studio/paper passes chosen model to writer/reviewer and honors model='offline'."""
    import threading
    import urllib.request
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    import orpath.control_plane as cp
    from scripts.orpath_watch import make_server

    slug = "paper-route-case"
    _write_valid_custom_mip_artifacts(tmp_path, slug, objective=42.0)
    # Seed validated report & retrieval whitelist so R1/R2 gates have crisp inputs
    (tmp_path / "outputs" / f"{slug}-validate.json").write_text(
        json.dumps({"ok": True, "problem_id": slug, "checks": [{"name": "envelope", "ok": True}]}),
        encoding="utf-8",
    )
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    (notes_dir / f"{slug}-research.md").write_text(
        "# Research Notes\nRef [R1] `notes://seed-custom` custom MIP benchmark.\n",
        encoding="utf-8",
    )
    (notes_dir / f"{slug}-retrieval.json").write_text(
        json.dumps(
            {
                "query": slug,
                "whitelist_refs": ["notes://seed-custom", f"outputs/{slug}-solution.json"],
                "hits": [{"ref": "notes://seed-custom", "title": "Seed Custom MIP"}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("ORPATH_WORKDIR", str(tmp_path))
    monkeypatch.setattr(cp, "is_real_llm_configured", lambda: True)

    seen_models: list[str | None] = []
    writer_body = (
        "# Academic Paper: Custom MIP\n\n"
        "## 1. Abstract\n"
        "We obtain optimal objective 42.0 (notes://custom_mip-ref) [R1] (notes://paper-route-case-research).\n\n"
        "## 2. Problem Statement\nMaximize linear objective subject to linear constraints.\n\n"
        "## 3. Mathematical Formulation\n$$\\max 6x + 5y$$\n\n"
        "## 4. Solution Strategy\nBranch and bound custom MIP.\n\n"
        "## 5. Verified Computational Results\nReported objective is 42.0 with OPTIMAL status.\n\n"
        "## 6. Limitations\nSingle-instance baseline.\n"
    ) + (" Additional rigorous methodology analysis paragraph.\n" * 20)

    class _FakeChatModel(BaseChatModel):
        @property
        def _llm_type(self) -> str:
            return "fake-phase1"

        def bind_tools(self, tools, **kwargs):
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            txt = "\n".join(str(getattr(m, "content", m)) for m in messages)
            if "peer review" in txt.lower():
                content = "# Peer Review\nVerdict: PASS\n- Numbers Truth verified (42.0).\n" + ("Detail.\n" * 15)
            else:
                content = writer_body
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    def _fake_get_chat_model(*, model_name=None, temperature=0.2, http_client=None, timeout=None):
        seen_models.append(model_name)
        return _FakeChatModel()

    monkeypatch.setattr(cp, "get_chat_model", _fake_get_chat_model)

    srv = make_server(host="127.0.0.1", port=0, workdir=tmp_path, default_slug=slug, default_thread=f"t-{slug}")
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        def _post(path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}{path}",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))

        # Case 1: Explicit spark model + force_live_agent without monkeypatching is_live_paper_agent_enabled
        code1, res1 = _post(
            "/api/studio/paper",
            {
                "slug": slug,
                "thread_id": f"t-{slug}-live",
                "model": "spark-x2.6",
                "api_key": "ak-test-key",
                "force_live_agent": True,
                "from_stage": "draft_paper",
            },
        )
        assert code1 == 200
        assert res1["ok"] is True, f"res1={res1}"
        assert res1["paper_generated"] is True
        assert res1["paper_quality"] == "llm_writer"
        assert "spark-x2.6" in seen_models

        # Case 2: model='offline' forces template_render even when is_real_llm_configured() is True
        seen_models.clear()
        code2, res2 = _post(
            "/api/studio/paper",
            {
                "slug": slug,
                "thread_id": f"t-{slug}-offline",
                "model": "offline",
                "from_stage": "draft_paper",
            },
        )
        assert code2 == 200
        assert res2["ok"] is True
        assert res2["paper_generated"] is True
        assert res2["paper_quality"] == "template_render"
        assert seen_models == []
    finally:
        srv.shutdown()
        srv.server_close()


def test_cli_orpath_paper_picks_up_notes_and_plans_without_checkpoint(tmp_path: Path, monkeypatch) -> None:
    """orpath paper CLI finds notes/ and outputs/.plans/ artifacts when no SQLite checkpoint exists."""
    import sys
    from orpath.run_orpath import main as cli_main

    slug = "cli-paper-notes"
    _write_valid_custom_mip_artifacts(tmp_path, slug, objective=42.0)
    (tmp_path / "outputs" / f"{slug}-validate.json").write_text(
        json.dumps({"ok": True, "problem_id": slug, "checks": [{"name": "envelope", "ok": True}]}),
        encoding="utf-8",
    )
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    (notes_dir / f"{slug}-research.md").write_text(
        "# Research\nCustom MIP notes [R1] (`notes://cli-seed`).\n",
        encoding="utf-8",
    )
    (notes_dir / f"{slug}-retrieval.json").write_text(
        json.dumps({"whitelist_refs": ["notes://cli-seed", f"outputs/{slug}-solution.json"], "hits": []}),
        encoding="utf-8",
    )
    plans_dir = tmp_path / "outputs" / ".plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    (plans_dir / f"{slug}.md").write_text("# Plan\nStep 1: validate\n", encoding="utf-8")

    monkeypatch.setenv("ORPATH_WORKDIR", str(tmp_path))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "orpath",
            "paper",
            "--workdir",
            str(tmp_path),
            "--slug",
            slug,
            "--from-stage",
            "draft_paper",
            "--no-live-subagent",
        ],
    )
    rc = cli_main()
    assert rc == 0
    assert (tmp_path / "papers" / f"{slug}.md").is_file()
    assert (tmp_path / "outputs" / f"{slug}.provenance.md").is_file()
