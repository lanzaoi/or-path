#!/usr/bin/env python3
"""Single-Agent Empowerment & Numbers Truth 2.0 verification tests.

Verifies:
  1. Pure-Python coding tool suite (`orpath/agents/coding_tools.py`): pagination,
     .xlsx reading, allowlisted writes/edits, unique-match edits, grep/list,
     and safe Python shell execution + destructive command blocking.
  2. Worker & OR tool wiring (`orpath/agents/workers.py`, `tools_or.py`):
     all coding + solver + skill tools mounted, 500-char prompt cap lifted,
     offset pagination on `read_problem_file`, workdir-contained absolute
     paths accepted by `write_custom_solver_script`.
  3. Numbers Truth 2.0 (`scripts/custom_sandbox_gate.py`,
     `tools/validate_solution.py`, `orpath/agents/custom_mip.py`):
     clean independent validator passes, solver-import in validator rejected
     by AST anti-cheat, hardcoded fake JSON rejected by fresh subprocess rerun,
     reduction manifest + optimality honesty checked, continuous LP/MILP via
     `scipy.optimize.milp` solves fractional optima accurately.
  4. Multi-round self-repair loop (`orpath/pipeline/solve.py`) & live Studio
     confirm (`scripts/orpath_watch.py`) for unregistered problems.
"""
from __future__ import annotations

import base64
import contextlib
import json
import os
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
from langchain_core.messages import AIMessage, HumanMessage

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
SCRIPTS = ROOT / "scripts"
for _p in (str(ROOT), str(TOOLS), str(SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import orpath.agents.coding_tools as coding_tools  # noqa: E402
import orpath.agents.tools_or as tools_or  # noqa: E402
import orpath.agents.workers as workers  # noqa: E402
import orpath.control_plane as cp  # noqa: E402
import orpath_watch  # noqa: E402
import scripts.custom_sandbox_gate as custom_sandbox_gate  # noqa: E402
import validate_solution as vs  # noqa: E402
from orpath.agents.custom_mip import custom_mip_solve  # noqa: E402

pytestmark = pytest.mark.filterwarnings(
    "ignore:create_react_agent has been moved",
    "ignore:No supported",
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
class _DummyChatModel:
    """Minimal offline chat model stub supporting bind_tools / invoke."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_DummyChatModel":
        return self

    def invoke(self, *args: Any, **kwargs: Any) -> AIMessage:
        return AIMessage(content="ok")


def _setup_workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for d in ("inbox", "outputs", "notes", "papers", "runs", "custom_solvers"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ORPATH_WORKDIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write_clean_custom_case(
    workdir: Path,
    slug: str,
    *,
    declared_obj: float = 10.5,
    validator_obj: float = 10.5,
    cheat_import: bool = False,
    fake_report_obj: float | None = None,
    status: str = "OPTIMAL",
    proven_optimal: bool = True,
    reduction_manifest: dict[str, Any] | None = None,
) -> tuple[Path, Path, Path]:
    """Write `<slug>-solution.json`, `<slug>-custom-validate.py`, and report JSON."""
    out_dir = workdir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    solver_path = out_dir / f"{slug}-custom-solver.py"
    solver_path.write_text(
        "import json\nprint(json.dumps({'objective': 10.5}))\n",
        encoding="utf-8",
    )

    val_py = out_dir / f"{slug}-custom-validate.py"
    cheat_line = "import ortools.linear_solver.pywraplp  # forbidden cheat\n" if cheat_import else ""
    val_code = f"""#!/usr/bin/env python3
import json
{cheat_line}from pathlib import Path

sol = json.loads(Path("outputs/{slug}-solution.json").read_text(encoding="utf-8"))
x = float(sol["variables"]["x"])
y = float(sol["variables"]["y"])
recomp = round(3.0 * x + 2.0 * y, 8)
ok = (x >= -1e-7) and (y >= -1e-7) and (x + y <= 4.0 + 1e-6) and (2.0 * x <= 5.0 + 1e-6)
# Recomputed value matches fixture truth unless testing tamper/mismatch
expected_val = {float(validator_obj)!r}
report = {{
    "ok": bool(ok),
    "problem_id": "{slug}",
    "objective": sol.get("objective"),
    "recomputed_objective": expected_val if abs(recomp - expected_val) < 1e-6 else expected_val,
    "original_constraints_ok": bool(ok),
    "checks": [
        {{"name": "capacity_1", "ok": x + y <= 4.0 + 1e-6}},
        {{"name": "capacity_2", "ok": 2.0 * x <= 5.0 + 1e-6}},
    ],
}}
Path("outputs/{slug}-custom-validate.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(report))
"""
    val_py.write_text(val_code, encoding="utf-8")

    rep_path = out_dir / f"{slug}-custom-validate.json"
    rep_obj = fake_report_obj if fake_report_obj is not None else validator_obj
    rep_data = {
        "ok": True,
        "problem_id": slug,
        "objective": declared_obj,
        "recomputed_objective": rep_obj,
        "original_constraints_ok": True,
        "checks": [{"name": "capacity_1", "ok": True}],
    }
    rep_path.write_text(json.dumps(rep_data, indent=2), encoding="utf-8")

    sol_path = out_dir / f"{slug}-solution.json"
    sol_data: dict[str, Any] = {
        "problem_id": slug,
        "problem_class": "custom_mip",
        "status": status,
        "objective": declared_obj,
        "solver": "custom_python_scipy",
        "source": "computed",
        "variables": {"x": 2.5, "y": 1.5},
        "validation_report": f"outputs/{slug}-custom-validate.json",
        "validator_script": f"outputs/{slug}-custom-validate.py",
        "solver_script": f"outputs/{slug}-custom-solver.py",
        "meta": {"proven_optimal": proven_optimal, "optimality_gap": 0.0 if proven_optimal else 0.05},
    }
    if reduction_manifest is not None:
        sol_data["reduction_manifest"] = reduction_manifest
    sol_path.write_text(json.dumps(sol_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return sol_path, rep_path, val_py


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


# --------------------------------------------------------------------------- #
# 1. Pure-Python Coding Tool Suite (`orpath/agents/coding_tools.py`)
# --------------------------------------------------------------------------- #
def test_coding_tools_read_file_pagination_and_xlsx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = _setup_workdir(tmp_path, monkeypatch)
    text_file = workdir / "inbox" / "lines.txt"
    text_file.write_text("\n".join(f"line-{i}" for i in range(1, 13)), encoding="utf-8")

    page1 = coding_tools.read_file.invoke({"file_path": "inbox/lines.txt", "offset": 1, "limit": 5})
    assert "total_lines=12" in page1
    assert "has_more=true" in page1
    assert "1: line-1" in page1
    assert "5: line-5" in page1
    assert "6: line-6" not in page1

    page3 = coding_tools.read_file.invoke({"file_path": "inbox/lines.txt", "offset": 11, "limit": 5})
    assert "has_more=false" in page3
    assert "11: line-11" in page3
    assert "12: line-12" in page3

    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Demand"
    ws["A1"] = "Node"
    ws["B1"] = "B42_DEMAND_199"
    xlsx_path = workdir / "inbox" / "sample.xlsx"
    wb.save(xlsx_path)

    xlsx_text = coding_tools.read_file.invoke({"file_path": "inbox/sample.xlsx"})
    assert "B42_DEMAND_199" in xlsx_text


def test_coding_tools_write_and_edit_allowlist_and_uniqueness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = _setup_workdir(tmp_path, monkeypatch)

    # Allowed relative + workdir-contained absolute paths
    res1 = json.loads(
        coding_tools.write_file.invoke(
            {"file_path": "outputs/note.txt", "content": "alpha\nbeta\ngamma\n"}
        )
    )
    assert res1["success"] is True

    abs_solver = str(workdir / "custom_solvers" / "helper.py")
    res2 = json.loads(
        coding_tools.write_file.invoke({"file_path": abs_solver, "content": "VAL = 1\nVAL_TWO = 1\n"})
    )
    assert res2["success"] is True
    assert Path(abs_solver).is_file()

    # Forbidden writes: source/code dirs and outside workdir
    for bad_path in (
        "orpath/pwn.py",
        "tools/pwn.py",
        "../outside_escape.py",
        "/tmp/outside_orpath_write_test.py",
    ):
        bad = json.loads(coding_tools.write_file.invoke({"file_path": bad_path, "content": "x"}))
        assert bad["success"] is False, f"expected write rejection for {bad_path}: {bad}"

    # edit_file: 0-match fails
    miss = json.loads(
        coding_tools.edit_file.invoke(
            {"file_path": "outputs/note.txt", "old_text": "does_not_exist", "new_text": "z"}
        )
    )
    assert miss["success"] is False

    # edit_file: >1 matches fails
    dup = json.loads(
        coding_tools.edit_file.invoke(
            {"file_path": abs_solver, "old_text": "= 1", "new_text": "= 2"}
        )
    )
    assert dup["success"] is False

    # edit_file: unique match succeeds
    ok_edit = json.loads(
        coding_tools.edit_file.invoke(
            {"file_path": "outputs/note.txt", "old_text": "beta", "new_text": "beta_updated"}
        )
    )
    assert ok_edit["success"] is True
    assert "beta_updated" in (workdir / "outputs" / "note.txt").read_text(encoding="utf-8")


def test_coding_tools_grep_list_and_shell_security(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = _setup_workdir(tmp_path, monkeypatch)
    (workdir / "outputs" / "find_me.py").write_text("TOKEN_UNIQUE_777 = 42\n", encoding="utf-8")
    (workdir / ".git").mkdir(exist_ok=True)
    (workdir / ".git" / "ignored.txt").write_text("TOKEN_UNIQUE_777\n", encoding="utf-8")

    listed = json.loads(coding_tools.list_files.invoke({"path": "outputs", "pattern": "*.py"}))
    assert listed["success"] is True
    assert any("find_me.py" in e["path"] for e in listed["entries"])

    grepped = json.loads(coding_tools.grep_search.invoke({"pattern": "TOKEN_UNIQUE_777", "path": "."}))
    assert grepped["success"] is True
    assert grepped["count"] == 1
    assert "find_me.py" in grepped["hits"][0]["file"]

    # run_shell runs python with ORPATH_WORKDIR set
    shell_ok = json.loads(
        coding_tools.run_shell.invoke(
            {"command": f'"{sys.executable}" -c "import os; print(os.environ.get(\'ORPATH_WORKDIR\'))"'}
        )
    )
    assert shell_ok["success"] is True
    assert str(workdir.resolve()) in shell_ok["stdout"]

    # run_shell blocks destructive patterns
    for dangerous in ("git reset --hard", "rm -rf /", "git clean -fd"):
        blocked = json.loads(coding_tools.run_shell.invoke({"command": dangerous}))
        assert blocked["success"] is False


# --------------------------------------------------------------------------- #
# 2. Workers & Tools Wiring (`workers.py`, `tools_or.py`)
# --------------------------------------------------------------------------- #
def test_workers_mount_coding_tools_and_expanded_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = _setup_workdir(tmp_path, monkeypatch)
    captured: list[dict[str, Any]] = []

    def _fake_react(model: Any, tools: list[Any], *, prompt: str = "", **kwargs: Any) -> dict[str, Any]:
        captured.append({"tools": tools, "prompt": prompt})
        return {"tools": tools, "prompt": prompt}

    monkeypatch.setattr(workers, "create_react_agent", _fake_react)
    model = _DummyChatModel()

    workers.create_modeler_agent(model=model)
    modeler_cap = captured[-1]
    modeler_names = {getattr(t, "name", "") for t in modeler_cap["tools"]}
    for expected in (
        "read_file",
        "write_file",
        "edit_file",
        "grep_search",
        "list_files",
        "run_shell",
        "write_custom_solver_script",
        "execute_custom_script",
        "validate_solution_tool",
        "consult_or_skill",
        "get_problem_formulation_template",
        "search_or_knowledge",
        "read_problem_file",
        "execute_or_solver",
        "execute_python_sandbox",
        "list_available_solvers",
    ):
        assert expected in modeler_names, f"missing modeler tool {expected}: {sorted(modeler_names)}"
    assert len(modeler_cap["tools"]) == 16

    workers.create_analyst_agent(model=model)
    analyst_cap = captured[-1]
    analyst_names = {getattr(t, "name", "") for t in analyst_cap["tools"]}
    for expected in ("read_file", "list_files", "grep_search", "read_problem_file", "consult_or_skill"):
        assert expected in analyst_names
    assert "500" not in analyst_cap["prompt"]
    assert "or-reduction-playbook" in analyst_cap["prompt"]

    # read_problem_file supports offset pagination + 32k default
    assert workers.READ_PROBLEM_FILE_MAX_CHARS == 32000
    long_txt = "ABCDE" * 30
    (workdir / "inbox" / "big.txt").write_text(long_txt, encoding="utf-8")
    slice2 = workers.read_problem_file.invoke({"file_path": "inbox/big.txt", "max_chars": 10, "offset": 5})
    assert "ABCDEABCDE" in slice2

    # write_custom_solver_script accepts workdir-contained absolute path inside tmp_path
    abs_target = str(workdir / "outputs" / "abs_solver.py")
    res_abs = json.loads(
        tools_or.write_custom_solver_script.invoke(
            {"script_path": abs_target, "code": "print('abs ok')\n"}
        )
    )
    assert res_abs["success"] is True
    assert Path(abs_target).is_file()


# --------------------------------------------------------------------------- #
# 3. Numbers Truth 2.0 (`custom_sandbox_gate.py`, `validate_solution.py`, `custom_mip.py`)
# --------------------------------------------------------------------------- #
def test_custom_sandbox_gate_passes_clean_scripts_and_validate_solution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = _setup_workdir(tmp_path, monkeypatch)
    slug = "clean-lp"
    sol_path, rep_path, _ = _write_clean_custom_case(workdir, slug)

    gate_res = custom_sandbox_gate.verify_custom_sandbox(
        workdir, slug, sol_path, report_path=rep_path, require_script=True
    )
    assert gate_res["ok"] is True, gate_res
    names = {c["name"]: c["ok"] for c in gate_res["checks"]}
    assert names.get("ast_anti_cheat") is True
    assert names.get("independent_rerun") is True
    assert names.get("optimality_honesty") is True

    sol_obj = json.loads(sol_path.read_text(encoding="utf-8"))
    val_res = vs.validate(slug, sol_obj, solution_path=sol_path)
    assert val_res["ok"] is True, val_res


def test_custom_sandbox_gate_blocks_solver_import_in_validator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = _setup_workdir(tmp_path, monkeypatch)
    slug = "cheat-ast"
    sol_path, rep_path, _ = _write_clean_custom_case(workdir, slug, cheat_import=True)

    gate_res = custom_sandbox_gate.verify_custom_sandbox(
        workdir, slug, sol_path, report_path=rep_path, require_script=True
    )
    assert gate_res["ok"] is False
    failed = {c["name"] for c in gate_res["checks"] if not c["ok"]}
    assert "ast_anti_cheat" in failed

    sol_obj = json.loads(sol_path.read_text(encoding="utf-8"))
    val_res = vs.validate(slug, sol_obj, solution_path=sol_path)
    assert val_res["ok"] is False


def test_custom_sandbox_gate_blocks_fake_hardcoded_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = _setup_workdir(tmp_path, monkeypatch)
    slug = "fake-json"
    # Declared objective & fake cached JSON both claim 999.0, while validator script recomputes 10.5
    sol_path, rep_path, _ = _write_clean_custom_case(
        workdir, slug, declared_obj=999.0, validator_obj=10.5, fake_report_obj=999.0
    )

    gate_res = custom_sandbox_gate.verify_custom_sandbox(
        workdir, slug, sol_path, report_path=rep_path, require_script=True
    )
    assert gate_res["ok"] is False
    failed = {c["name"] for c in gate_res["checks"] if not c["ok"]}
    assert "independent_rerun" in failed

    # Hardcoded stub validator performing no file read or arithmetic fails AST anti-cheat
    stub_slug = "stub-val"
    stub_sol, stub_rep, stub_py = _write_clean_custom_case(workdir, stub_slug)
    stub_py.write_text(
        'import json\nprint(json.dumps({"ok": True, "recomputed_objective": 10.5}))\n',
        encoding="utf-8",
    )
    gate_stub = custom_sandbox_gate.verify_custom_sandbox(
        workdir, stub_slug, stub_sol, report_path=stub_rep, require_script=True
    )
    assert gate_stub["ok"] is False
    stub_failed = {c["name"] for c in gate_stub["checks"] if not c["ok"]}
    assert "ast_anti_cheat" in stub_failed

    # Declared objective != recomputed objective fails validate_solution
    sol_path2, _, _ = _write_clean_custom_case(workdir, "mismatch-obj", declared_obj=99.0, validator_obj=10.5)
    sol_obj2 = json.loads(sol_path2.read_text(encoding="utf-8"))
    val_res2 = vs.validate("mismatch-obj", sol_obj2, solution_path=sol_path2)
    assert val_res2["ok"] is False


def test_custom_sandbox_gate_reduction_manifest_and_optimality_honesty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = _setup_workdir(tmp_path, monkeypatch)

    # Good reduction manifest + honest optimality
    sol_ok, rep_ok, _ = _write_clean_custom_case(
        workdir,
        "red-ok",
        reduction_manifest={
            "target_class": "min_cost_flow",
            "recomputed_original_objective": 10.5,
            "original_constraints_ok": True,
        },
    )
    res_ok = custom_sandbox_gate.verify_custom_sandbox(
        workdir, "red-ok", sol_ok, report_path=rep_ok, require_script=True
    )
    assert res_ok["ok"] is True, res_ok
    assert any(c["name"] == "reduction_manifest_check" and c["ok"] for c in res_ok["checks"])

    # Mismatched reduction manifest objective
    sol_bad_red, rep_bad_red, _ = _write_clean_custom_case(
        workdir,
        "red-bad",
        declared_obj=10.5,
        reduction_manifest={
            "target_class": "min_cost_flow",
            "recomputed_original_objective": 42.0,
            "original_constraints_ok": True,
        },
    )
    res_bad_red = custom_sandbox_gate.verify_custom_sandbox(
        workdir, "red-bad", sol_bad_red, report_path=rep_bad_red, require_script=True
    )
    assert res_bad_red["ok"] is False
    assert any(c["name"] == "reduction_manifest_check" and not c["ok"] for c in res_bad_red["checks"])

    # Dishonest OPTIMAL claim when proven_optimal is False
    sol_dishonest, rep_dishonest, _ = _write_clean_custom_case(
        workdir,
        "opt-lie",
        status="OPTIMAL",
        proven_optimal=False,
    )
    res_lie = custom_sandbox_gate.verify_custom_sandbox(
        workdir, "opt-lie", sol_dishonest, report_path=rep_dishonest, require_script=True
    )
    assert res_lie["ok"] is False
    assert any(c["name"] == "optimality_honesty" and not c["ok"] for c in res_lie["checks"])


def test_custom_mip_continuous_variables_fractional_optimum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = _setup_workdir(tmp_path, monkeypatch)
    slug = "cont-lp-test"
    instance = {
        "problem_id": slug,
        "slug": slug,
        "decision_vars": [
            {"id": "x", "kind": "cont", "domain": [0, 10]},
            {"id": "y", "kind": "cont", "domain": [0, 10]},
        ],
        "objective": {"sense": "max", "coeffs": {"x": 3.0, "y": 2.0}},
        "constraints": [
            {"id": "c1", "lhs": "x + y", "op": "<=", "rhs": 4.0},
            {"id": "c2", "lhs": "2*x", "op": "<=", "rhs": 5.0},
        ],
    }
    inst_path = workdir / "inbox" / f"{slug}-instance.json"
    inst_path.write_text(json.dumps(instance, indent=2), encoding="utf-8")

    res = custom_mip_solve(instance_path=inst_path, out_dir=workdir / "outputs")
    assert res["ok"] is True, res
    assert res["validator_ok"] is True, res
    assert res["objective"] == pytest.approx(10.5, abs=1e-6)
    assert res["values"]["x"] == pytest.approx(2.5, abs=1e-6)
    assert res["values"]["y"] == pytest.approx(1.5, abs=1e-6)

    sol_path = Path(res["solution_path"])
    sol_obj = json.loads(sol_path.read_text(encoding="utf-8"))
    val_rep = vs.validate(slug, sol_obj, solution_path=sol_path)
    assert val_rep["ok"] is True, val_rep


# --------------------------------------------------------------------------- #
# 4. Multi-Round Self-Repair & Studio Confirm Live Custom Flow
# --------------------------------------------------------------------------- #
def test_single_agent_self_repair_loop_in_product_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = _setup_workdir(tmp_path, monkeypatch)
    slug = "self-repair-case"
    (workdir / "inbox" / slug).mkdir(parents=True, exist_ok=True)
    (workdir / "inbox" / slug / "problem.txt").write_text(
        "Maximize 3*x + 2*y subject to x + y <= 4, 2*x <= 5, x, y >= 0 continuous.",
        encoding="utf-8",
    )

    seen_prompts: list[str] = []

    class _RepairMockAgent:
        def invoke(self, payload: dict[str, Any], config: Any = None) -> dict[str, Any]:
            msgs = payload.get("messages") or []
            last_text = str(getattr(msgs[-1], "content", "")) if msgs else ""
            seen_prompts.append(last_text)
            round_idx = len(seen_prompts)
            if round_idx == 1:
                # Round 1: intentionally produce tampered/mismatched validation report
                _write_clean_custom_case(
                    workdir, slug, declared_obj=99.0, validator_obj=10.5
                )
                return {
                    "messages": [
                        AIMessage(
                            content=json.dumps(
                                {
                                    "solution_path": f"outputs/{slug}-solution.json",
                                    "status": "OPTIMAL",
                                    "objective": 99.0,
                                }
                            )
                        )
                    ]
                }
            # Round 2: fix objective & validator cleanly
            _write_clean_custom_case(workdir, slug, declared_obj=10.5, validator_obj=10.5)
            return {
                "messages": [
                    AIMessage(
                        content=json.dumps(
                            {
                                "solution_path": f"outputs/{slug}-solution.json",
                                "status": "OPTIMAL",
                                "objective": 10.5,
                            }
                        )
                    )
                ]
            }

    monkeypatch.setattr(cp, "get_chat_model", lambda *a, **k: _DummyChatModel())
    monkeypatch.setattr(workers, "create_modeler_agent", lambda *a, **k: _RepairMockAgent())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-empowerment")
    monkeypatch.setenv("ORPATH_FAST_REPAIR_ROUNDS", "3")

    initial = cp.default_initial(
        root=workdir,
        slug=slug,
        problem_id=slug,
        problem_class="custom_mip",
        solve_mode="custom_mip",
        run_mode="fast",
        skip_paper=True,
        live_subagent=True,
        thread_id=f"{slug}-t1",
    )
    initial["force_live_agent"] = True
    app = cp.build_graph(checkpointer=None)
    final = app.invoke(initial)
    assert len(seen_prompts) == 2, f"expected 2 repair rounds, got {len(seen_prompts)}"
    assert final.get("gate_validate_ok") is True, final
    assert final.get("human_required") is False, final
    assert final.get("stage") == "end", final

    # Round 2 prompt carries gate failure feedback back into or_modeler
    assert any(
        tok in seen_prompts[1].lower()
        for tok in ("validate", "recompute_objective", "mismatch", "failed", "repair", "未通过")
    )


def test_studio_confirm_unregistered_problem_uses_live_single_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = _setup_workdir(tmp_path, monkeypatch)
    slug = "studio-custom-unreg"

    modeler_calls = {"count": 0}

    class _StudioCustomModeler:
        def invoke(self, payload: dict[str, Any], config: Any = None) -> dict[str, Any]:
            modeler_calls["count"] += 1
            _write_clean_custom_case(workdir, slug, declared_obj=10.5, validator_obj=10.5)
            return {
                "messages": [
                    AIMessage(
                        content=json.dumps(
                            {
                                "solution_path": f"outputs/{slug}-solution.json",
                                "status": "OPTIMAL",
                                "objective": 10.5,
                            }
                        )
                    )
                ]
            }

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-studio-empowerment")
    monkeypatch.setattr(cp, "get_chat_model", lambda *a, **k: _DummyChatModel())
    monkeypatch.setattr(workers, "create_modeler_agent", lambda *a, **k: _StudioCustomModeler())

    with _serve(workdir) as base:
        prob_text = (
            "Continuous Production Blending Optimization\n"
            "Choose continuous production rates x, y >= 0 to maximize 3*x + 2*y "
            "subject to x + y <= 4 and 2*x <= 5.\n"
        )
        code, imp = _post_json(
            base + "/api/intake/import",
            {
                "mode": "folder",
                "slug": slug,
                "files": [
                    {
                        "rel_path": "problem.txt",
                        "content_base64": base64.b64encode(prob_text.encode("utf-8")).decode("ascii"),
                    }
                ],
            },
        )
        assert code == 200 and imp.get("ok"), f"import failed: {imp}"

        c_code, c_res = _post_json(
            base + "/api/studio/confirm",
            {
                "slug": slug,
                "run_mode": "fast",
                "skip_paper": True,
                "live_subagent": True,
                "force_live_agent": True,
                "selected_options": {},
                "extra_prompt": "",
            },
        )
        assert c_code == 200, c_res
        assert modeler_calls["count"] >= 1, f"expected live modeler to run: {c_res}"
        assert c_res.get("status") == "COMPLETED", c_res
        assert c_res.get("objective") == pytest.approx(10.5, abs=1e-6)
        assert c_res["solution"]["objective"] == pytest.approx(10.5, abs=1e-6)
