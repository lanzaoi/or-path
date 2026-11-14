"""Phase 0 verification tests: truth chain (fail-closed + replay auth), unified docx/xlsx assets, and Studio BLOCKED UI."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _make_sample_docx(path: Path, paragraphs: list[str], table_rows: list[list[str]] | None = None) -> None:
    from docx import Document

    doc = Document()
    doc.add_heading("运筹学赛题说明", level=1)
    for p in paragraphs:
        doc.add_paragraph(p)
    if table_rows:
        tbl = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
        for r_i, row in enumerate(table_rows):
            for c_i, val in enumerate(row):
                tbl.cell(r_i, c_i).text = val
    doc.save(str(path))


def _make_sample_xlsx(path: Path) -> None:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "光伏负荷与电价"
    ws.append(["时段", "负荷_kW", "光伏_kW", "分时电价_元"])
    ws.append(["00:00", 120, 0, 0.35])
    ws.append(["12:00", 260, 180, 1.12])
    ws.append(["18:00", 310, 20, 1.45])
    ws2 = wb.create_sheet("储能参数")
    ws2.append(["参数名", "数值", "单位"])
    ws2.append(["额定容量", 500, "kWh"])
    wb.save(str(path))
    wb.close()


def test_docx_and_xlsx_extraction_no_binary_dump(tmp_path: Path) -> None:
    from tools.intake_assets import (
        extract_asset_text,
        probe_spreadsheet,
        read_statement_text,
    )
    from tools.intake_ocr import run_ocr, validate_ocr_meta

    docx_p = tmp_path / "题面.docx"
    xlsx_p = tmp_path / "附件1.xlsx"
    _make_sample_docx(
        docx_p,
        ["某园区微网包含光伏与储能电池系统，请最小化日综合用电成本。"],
        [["设备", "上限"], ["BESS", "200kW"]],
    )
    _make_sample_xlsx(xlsx_p)

    d_text, _, d_warn = extract_asset_text(docx_p)
    assert "某园区微网包含光伏与储能电池系统" in d_text
    assert "| 设备 | 上限 |" in d_text
    assert "| BESS | 200kW |" in d_text
    assert "PK\x03\x04" not in d_text
    assert "\x00" not in d_text

    meta = probe_spreadsheet(xlsx_p)
    assert meta["sheet_names"] == ["光伏负荷与电价", "储能参数"]
    assert meta["columns"][:4] == ["时段", "负荷_kW", "光伏_kW", "分时电价_元"]
    assert len(meta["sample_rows"]) == 3

    x_text, pages, _ = extract_asset_text(xlsx_p)
    assert pages == 2
    assert "光伏负荷与电价" in x_text
    assert "储能参数" in x_text
    assert "PK\x03\x04" not in x_text

    assert "微网" in read_statement_text(docx_p)

    # intake_ocr handles docx + xlsx without binary ZIP corruption
    notes = tmp_path / "notes"
    ocr = run_ocr(slug="p0_docs", inputs=[docx_p, xlsx_p], root=tmp_path, notes_dir=notes)
    assert ocr.status == "ok", ocr.warnings
    assert ocr.backend == "mixed"
    raw = (notes / "p0_docs-ocr.raw.md").read_text(encoding="utf-8")
    assert "某园区微网" in raw
    assert "光伏负荷与电价" in raw
    assert "PK" not in raw[:50]
    meta_doc = json.loads((notes / "p0_docs-ocr.meta.json").read_text(encoding="utf-8"))
    assert validate_ocr_meta(meta_doc) == []
    assert [s["kind"] for s in meta_doc["sources"]] == ["docx", "xlsx"]


def test_intake_assets_edge_cases(tmp_path: Path) -> None:
    from tools.intake_assets import extract_asset_text, read_statement_text

    d = tmp_path / "adir"
    d.mkdir()
    with pytest.raises(IsADirectoryError):
        extract_asset_text(d)
    assert read_statement_text(d) == ""
    assert read_statement_text(tmp_path / "missing.docx") == ""

    bad_docx = tmp_path / "corrupt.docx"
    bad_docx.write_bytes(b"not-a-real-zip")
    assert read_statement_text(bad_docx) == ""


def test_studio_analyzer_reads_docx_xlsx_and_classifies_chinese(tmp_path: Path) -> None:
    from orpath.studio_analyzer import profile_inbox_assets, run_deep_analysis

    # 1. Polyomino Chinese docx + unregistered attachment
    inbox1 = tmp_path / "inbox" / "cn_poly"
    inbox1.mkdir(parents=True)
    _make_sample_docx(inbox1 / "B题.docx", ["多联骨牌铺放问题：用9种多联骨牌覆盖给定棋盘。"])
    _make_sample_xlsx(inbox1 / "棋盘参数.xlsx")
    out_dir = tmp_path / "outputs"
    prof1 = profile_inbox_assets(inbox1, "cn_poly", out_dir)
    assert "B题.docx" in prof1["statement_files"]
    assert prof1["data_files"][0]["sheet_names"] == ["光伏负荷与电价", "储能参数"]
    ana1 = run_deep_analysis(
        slug="cn_poly",
        prompt="",
        workdir=tmp_path,
        home=ROOT,
        model="offline",
    )
    assert ana1["domain_diagnosis"]["problem_class"] == "polyomino_cover"

    # 2. Microgrid Chinese docx
    inbox2 = tmp_path / "inbox" / "cn_mg"
    inbox2.mkdir(parents=True)
    _make_sample_docx(inbox2 / "C题.docx", ["校园微网光伏与储能电站协调调度优化。"])
    profile_inbox_assets(inbox2, "cn_mg", out_dir)
    ana2 = run_deep_analysis(
        slug="cn_mg",
        prompt="",
        workdir=tmp_path,
        home=ROOT,
        model="offline",
    )
    assert ana2["domain_diagnosis"]["problem_class"] == "microgrid_dispatch"

    # 3. Unregistered Chinese docx -> must NOT become tsp or shortest_path!
    inbox3 = tmp_path / "inbox" / "cn_unknown"
    inbox3.mkdir(parents=True)
    _make_sample_docx(inbox3 / "未知题.docx", ["给定一组生态演化耦合动力学方程，试分析稳态吸引子分岔特性。"])
    profile_inbox_assets(inbox3, "cn_unknown", out_dir)
    ana3 = run_deep_analysis(
        slug="cn_unknown",
        prompt="",
        workdir=tmp_path,
        home=ROOT,
        model="offline",
    )
    assert ana3["domain_diagnosis"]["problem_class"] == "unregistered"
    assert ana3["domain_diagnosis"]["recommended_algorithm"] == "none"


def test_fail_closed_no_shortest_path_fallback_and_blocked_routes_human_stop(tmp_path: Path) -> None:
    from orpath.control_plane import build_graph, default_initial
    from orpath.graph_product import _after_validate
    from orpath.pipeline.common import _fixture_base, _infer_class
    from orpath.pipeline.research import _minimal_profile
    from orpath.pipeline.solve import node_gate_validate, node_solve
    from tools.solve_dispatch import solve as dispatch_solve
    from tools.validate_solution import validate as val_solution

    # Empty problem_id must NEVER resolve _fixture_base to inbox/
    (tmp_path / "inbox").mkdir(parents=True)
    assert _fixture_base(tmp_path, "", allow_fixture=False) is None
    assert _infer_class(tmp_path, "", None, allow_fixture=False) == "unknown"

    # _minimal_profile must NOT mix fixtures/t1/shortest_path when allow_fixture=False
    prof = _minimal_profile(tmp_path, "no-fix", "shortest_path", "", [], allow_fixture=False)
    assert not any("fixtures" in f for f in prof.get("data_files") or [])

    # Full graph run with empty problem_id / unknown class must stop at human_stop, never solve shortest_path=42 or generate paper
    for d in ("outputs", "notes", "runs", "papers"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    init_unk = default_initial(
        root=tmp_path,
        slug="phase0-unk",
        problem_id="",
        problem_class="",
        solve_mode="",
        knowledge_mode="off",
        live_subagent=False,
        thread_id="phase0-unk",
        is_replay=False,
        replay_authorized=False,
    )
    app = build_graph(checkpointer=None)
    final_unk = app.invoke(init_unk)
    assert final_unk.get("human_required") is True
    assert final_unk.get("gate_validate_ok") is False
    assert not (tmp_path / "papers" / "phase0-unk.md").is_file()
    sol_p = tmp_path / "outputs" / "phase0-unk-solution.json"
    if sol_p.is_file():
        sol_doc = json.loads(sol_p.read_text(encoding="utf-8"))
        assert sol_doc.get("objective") != 42

    # Intake run claiming problem_id="shortest_path" WITHOUT replay auth must be BLOCKED & routed to human_stop
    init_spoof = default_initial(
        root=tmp_path,
        slug="phase0-spoof",
        problem_id="shortest_path",
        problem_class="shortest_path",
        solve_mode="mock",
        knowledge_mode="off",
        live_subagent=False,
        thread_id="phase0-spoof",
        skip_intake=False,
        intake_sources=[str(tmp_path / "inbox")],
        is_replay=False,
        replay_authorized=False,
    )
    u_solve = node_solve(init_spoof)
    assert u_solve.get("solve_refused") is True
    u_val = node_gate_validate({**init_spoof, **u_solve})
    assert u_val.get("stage") == "human_stop"
    assert u_val.get("human_required") is True
    assert _after_validate({**init_spoof, **u_solve, **u_val}) == "human_stop"
    assert not (tmp_path / "papers" / "phase0-spoof.md").is_file()

    # Unknown solve_mode must fail, NOT silently fall back to ortools
    ok, _sol, err = dispatch_solve(ROOT, "tsp_n8", mode="nonexistent_mode_xyz", problem_class="tsp")
    assert ok is False
    assert "unknown solve mode" in err

    # validate_solution without class must NOT default to shortest_path
    vrep = val_solution("custom_xyz", {"status": "OPTIMAL", "objective": 10, "solver": "x"})
    assert vrep["problem_class"] == "unregistered"
    assert vrep["ok"] is False


def test_solve_polyomino_refuses_silent_4x4_fallback_without_replay() -> None:
    r_blk = subprocess.run(
        [sys.executable, str(TOOLS / "solve_polyomino.py"), "nonexistent_polyomino_board"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert r_blk.returncode == 0
    doc_blk = json.loads(r_blk.stdout)
    assert doc_blk["status"] == "BLOCKED"
    assert doc_blk["objective"] is None
    assert doc_blk["meta"]["blocked_code"] == "missing_board_data"

    r_rep = subprocess.run(
        [sys.executable, str(TOOLS / "solve_polyomino.py"), "nonexistent_polyomino_board", "--is-replay"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert r_rep.returncode == 0
    doc_rep = json.loads(r_rep.stdout)
    assert doc_rep["status"] == "OPTIMAL"
    assert doc_rep["meta"]["is_replay"] is True


def test_run_orpath_cli_no_shortest_path_default() -> None:
    # Calling run_orpath.py run without --problem-id / --is-replay must fail closed (exit 2 human_stop), NOT solve shortest_path=42
    import tempfile

    with tempfile.TemporaryDirectory(prefix="phase0-cli-") as td:
        r = subprocess.run(
            [
                sys.executable,
                str(ROOT / "orpath" / "run_orpath.py"),
                "run",
                "--workdir",
                td,
                "--slug",
                "cli-no-default",
                "--thread-id",
                "cli-no-default",
                "--knowledge-mode",
                "off",
                "--no-live-subagent",
                "--fresh",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert r.returncode == 2, r.stdout + r.stderr
        summary = json.loads(r.stdout)
        assert summary["human_required"] is True
        assert summary["gate_validate_ok"] is False
        assert not summary.get("paper_path")


def test_studio_blocked_ui_markers() -> None:
    studio_js = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((ROOT / "orpath" / "web" / "src" / "js" / "studio").glob("*.js"))
    )
    studio_html = (ROOT / "orpath" / "web" / "studio.html").read_text(encoding="utf-8")
    for text in (studio_js, studio_html):
        assert "求解已诚实阻断" in text
        assert "求解已诚实阻断（未通过数值条件）" in text
        assert "求解受阻，未通过数值求解" in text
        assert "无解/求解受阻" in text
        assert "等待求解产物" in text
        assert "studioResultBanner" in text
        assert "is-blocked" in text
        assert "data_source" in text


def test_no_attachment_filename_microgrid_hijack_and_watch_http_roundtrip(tmp_path: Path) -> None:
    import base64
    import threading
    import urllib.request

    import openpyxl
    from orpath.studio_analyzer import profile_inbox_assets, run_deep_analysis
    from scripts.orpath_watch import make_server

    # 1. Polyomino docx + generic 附件1.xlsx must NOT hijack to microgrid_dispatch
    inbox_poly = tmp_path / "inbox" / "cn_poly_att"
    inbox_poly.mkdir(parents=True)
    _make_sample_docx(inbox_poly / "B题.docx", ["多联骨牌铺放问题：用9种多联骨牌覆盖给定棋盘。"])
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "棋盘障碍"
    ws.append(["row", "col", "blocked"])
    ws.append([1, 2, 1])
    wb.save(str(inbox_poly / "附件1.xlsx"))
    wb.close()

    prof = profile_inbox_assets(inbox_poly, "cn_poly_att", tmp_path / "outputs")
    assert prof["detected_runnable_class"] is None
    assert prof["has_solver_dataset"] is False
    ana = run_deep_analysis(workdir=tmp_path, slug="cn_poly_att", home=ROOT, model="offline")
    assert ana["domain_diagnosis"]["problem_class"] == "polyomino_cover"

    # 2. Live Watch HTTP round-trip: import (docx + 附件1.xlsx) -> analyze -> confirm -> honest BLOCKED (200, not 500)
    wd_http = tmp_path / "watch_wd"
    for d in ("outputs", "notes", "runs", "papers", "inbox"):
        (wd_http / d).mkdir(parents=True, exist_ok=True)
    server = make_server(host="127.0.0.1", port=0, home=ROOT, workdir=wd_http)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    def _post(path: str, body: dict) -> tuple[int, dict]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    try:
        docx_b64 = base64.b64encode((inbox_poly / "B题.docx").read_bytes()).decode("ascii")
        xlsx_b64 = base64.b64encode((inbox_poly / "附件1.xlsx").read_bytes()).decode("ascii")

        c_imp, r_imp = _post(
            "/api/intake/import",
            {
                "mode": "folder",
                "slug": "http-poly-att",
                "files": [
                    {"rel_path": "B题.docx", "content_base64": docx_b64},
                    {"rel_path": "附件1.xlsx", "content_base64": xlsx_b64},
                ],
            },
        )
        assert c_imp == 200 and r_imp["ok"] is True

        c_ana, r_ana = _post("/api/studio/analyze", {"slug": "http-poly-att", "prompt": ""})
        assert c_ana == 200 and r_ana["ok"] is True
        assert r_ana["analysis"]["domain_diagnosis"]["problem_class"] == "polyomino_cover"

        c_conf, r_conf = _post(
            "/api/studio/confirm",
            {"slug": "http-poly-att", "selected_options": {"q_algorithm": "polyomino"}, "timeout": 1.0},
        )
        assert c_conf == 200 and r_conf["ok"] is True
        assert r_conf["status"] == "BLOCKED"
        assert r_conf["objective"] is None
        assert r_conf["data_source"] == "case"
        assert r_conf["blocked_reason"]
        assert not (wd_http / "papers" / "http-poly-att.md").is_file()
    finally:
        server.shutdown()
        server.server_close()


def test_no_fixture_leak_in_model_provenance_workers_microgrid_and_preflight(tmp_path: Path) -> None:
    from orpath.agents.deterministic_nodes import _preflight
    from orpath.agents.workers import read_problem_file
    from orpath.control_plane import default_initial
    from orpath.pipeline.solve import node_gate_validate, node_model

    for d in ("outputs", "notes", "runs", "papers", "inbox"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    # 1. node_model must NOT leak fixtures/t1/shortest_path into schema.json when replay_authorized=False
    init = default_initial(
        root=tmp_path,
        slug="no-leak-model",
        problem_id="shortest_path",
        problem_class="shortest_path",
        solve_mode="networkx",
        knowledge_mode="off",
        live_subagent=False,
        thread_id="no-leak-model",
        is_replay=False,
        replay_authorized=False,
    )
    res_m = node_model(init)
    schema = json.loads(Path(res_m["schema_path"]).read_text(encoding="utf-8"))
    assert not schema.get("fixture_ref")
    assert not schema.get("nodes")

    # 2. node_gate_validate must block spoofed fixture-mock solution on intake run
    spoof_sol = tmp_path / "outputs" / "spoof-solution.json"
    spoof_sol.write_text(
        json.dumps(
            {
                "status": "OPTIMAL",
                "objective": 42,
                "solver": "fixture-mock",
                "source": "tools/solve_mock.py",
                "problem_id": "shortest_path",
                "problem_class": "shortest_path",
                "path": ["S", "A", "T"],
                "meta": {"exact": False, "proven_optimal": False, "is_replay": True},
            }
        ),
        encoding="utf-8",
    )
    spoof_state = {
        **init,
        "slug": "spoof",
        "skip_intake": False,
        "intake_sources": [str(tmp_path / "inbox")],
        "solution_path": str(spoof_sol),
    }
    res_gv = node_gate_validate(spoof_state)  # type: ignore[arg-type]
    assert res_gv["stage"] == "human_stop"
    assert res_gv["human_required"] is True
    assert res_gv["gate_validate_ok"] is False
    assert "provenance" in res_gv["blocked_reason"]

    # 3. workers.read_problem_file must parse .docx & .xlsx cleanly without ZIP binary garbage
    docx_p = tmp_path / "inbox" / "worker_test.docx"
    xlsx_p = tmp_path / "inbox" / "worker_data.xlsx"
    _make_sample_docx(docx_p, ["多联骨牌覆盖测试题面"])
    _make_sample_xlsx(xlsx_p)
    out_docx = read_problem_file.invoke({"file_path": str(docx_p)})
    out_xlsx = read_problem_file.invoke({"file_path": str(xlsx_p)})
    assert "多联骨牌覆盖测试题面" in out_docx and "PK\x03\x04" not in out_docx
    assert "光伏负荷与电价" in out_xlsx and "PK\x03\x04" not in out_xlsx

    # 4. solve_microgrid.py without --is-replay on missing dataset returns BLOCKED (never silent fixture)
    r_mg = subprocess.run(
        [sys.executable, str(TOOLS / "solve_microgrid.py"), "missing_mg", "--case-dir", str(tmp_path / "no_dir")],
        cwd=ROOT,
        env={**__import__("os").environ, "ORPATH_WORKDIR": str(tmp_path)},
        text=True,
        capture_output=True,
    )
    assert r_mg.returncode == 0
    mg_doc = json.loads(r_mg.stdout)
    assert mg_doc["status"] == "BLOCKED"
    assert mg_doc["objective"] is None

    # 5. _preflight reads .docx statement even when problem_text is a short generic prompt
    case_dir = tmp_path / "inbox" / "generic_prompt_case"
    case_dir.mkdir(parents=True)
    _make_sample_docx(case_dir / "题面.docx", ["某园区微网光伏储能系统调度优化。"])
    pf_res = _preflight(
        {
            "workdir": str(tmp_path),
            "slug": "generic_prompt_case",
            "problem_text": "请帮我求解这道赛题",
            "data_files": [str(case_dir / "题面.docx")],
        },
        0.0,
    )
    assert pf_res["problem_class"] == "microgrid_dispatch"
