#!/usr/bin/env python3
"""Gate: Problem Intake & Solution Workbench (题面一键导入与全维查看工作台门禁).

Tests:
1. Static HTML assertions on orpath/web/watch.html:
   - Data attribute: data-orpath-problem-workbench
   - Workbench DOM ids: #problemWorkbench, #wbTitle, #wbPills, #wbTabs, #wbBody
   - Buttons: #btnOpenIntake, #btnToggleWorkbench, #wbBtnImport, #wbBtnRun
   - Modals: #intakeModal, #artifactModal
   - All 5 workbench tabs: overview, brief, schema, solution, paper
   - All 3 intake tabs: presets, upload, text
   - Dropzone elements: #upDropzone, #upFileInput
2. Snapshot unit contract:
   - snapshot.problem_view shape contract
   - snapshot.artifacts strictly dict[str, str | None]
   - historical seed inspection (live-btube: 4 subproblems, obj 99000, 16 passed checks)
   - missing slug honesty (has_problem=False, no throw)
3. HTTP server end-to-end (positive + negative):
   - GET /api/health includes new endpoints & problem_workbench flag
   - GET /api/problems returns >= 8 presets + cases
   - POST /api/intake/import mode=preset (live-btube + tube-surface fixture)
   - POST /api/intake/import mode=preset negative (unknown preset -> 400)
   - POST /api/intake/import mode=text (Q1..Q2 -> 200, stages created)
   - POST /api/intake/import mode=text negative (empty text -> 400)
   - POST /api/intake/import mode=upload (file_base64 -> 200)
   - POST /api/intake/import mode=upload negative (missing b64 -> 400)
   - POST /api/intake/import mode=invalid negative (-> 400)
   - GET /api/artifact positive (brief, solution)
   - GET /api/artifact negative (bad kind -> 400, missing file -> 404)
   - POST /api/intake/run (spawns run and stages grow to ok)
"""
from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orpath.watch_snapshot import (
    assert_no_llm_imports,
    build_snapshot,
    validate_snapshot_shape,
)


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def test_static_html() -> None:
    # 1. Modularity check (src/ split)
    src_dir = ROOT / "orpath" / "web" / "src"
    expected_src_files = [
        src_dir / "css" / "base.css",
        src_dir / "css" / "studio.css",
        src_dir / "css" / "inspector.css",
        src_dir / "html" / "header.html",
        src_dir / "html" / "studio.html",
        src_dir / "html" / "inspector.html",
        src_dir / "html" / "modals.html",
        src_dir / "js" / "common.js",
        src_dir / "js" / "inspector.js",
        src_dir / "js" / "studio.js",
    ]
    for p in expected_src_files:
        if not p.is_file():
            _fail(f"missing modular source file: {p.relative_to(ROOT)}")
    _ok(f"modular web source files verified (n={len(expected_src_files)})")

    # 2. Builder execution
    build_py = ROOT / "orpath" / "web" / "build.py"
    if not build_py.is_file():
        _fail("missing orpath/web/build.py")
    r = subprocess.run([sys.executable, str(build_py), "--force"], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        _fail(f"orpath/web/build.py execution failed: {r.stderr}")
    _ok("orpath/web/build.py execution PASS")

    html_path = ROOT / "orpath" / "web" / "watch.html"
    if not html_path.is_file():
        _fail("missing orpath/web/watch.html")
    text = html_path.read_text(encoding="utf-8", errors="replace")

    required_markers = [
        "data-orpath-problem-workbench",
        'id="problemWorkbench"',
        'id="wbTitle"',
        'id="wbPills"',
        'id="wbTabs"',
        'id="wbBody"',
        'id="btnOpenIntake"',
        'id="btnToggleWorkbench"',
        'id="wbBtnImport"',
        'id="wbBtnRun"',
        'id="intakeModal"',
        'id="artifactModal"',
        'data-wb-tab="overview"',
        'data-wb-tab="brief"',
        'data-wb-tab="schema"',
        'data-wb-tab="solution"',
        'data-wb-tab="paper"',
        'data-im-tab="presets"',
        'data-im-tab="upload"',
        'data-im-tab="text"',
        'id="upDropzone"',
        'id="upFileInput"',
        'id="btnDoUpload"',
        'id="btnDoTextImport"',
        "/api/problems",
        "/api/intake/import",
        "/api/artifact",
        "/api/intake/run",
        'id="btnModeStudio"',
        'id="btnModeInspector"',
        'id="studioContainer"',
        'id="studioDropzone"',
        'id="studioFileInput"',
        'id="studioPromptInput"',
        'id="btnStudioAnalyze"',
        'id="studioAnalysisCard"',
        'id="studioQuestionsBox"',
        'id="studioExtraPrompt"',
        'id="btnStudioConfirmSolve"',
        'id="studioResultCard"',
        'id="studioHeadline"',
        'id="studioObjective"',
        'id="studioValidation"',
        'id="studioDownloads"',
        "/api/studio/analyze",
        "/api/studio/confirm",
        "/api/artifact/download",
    ]
    for m in required_markers:
        if m not in text:
            _fail(f"watch.html missing required workbench marker: {m!r}")
    _ok(f"watch.html static markers verified (n={len(required_markers)})")


def test_snapshot_problem_view(workdir: Path) -> None:
    assert_no_llm_imports(ROOT / "orpath" / "watch_snapshot.py")

    # 1. Existing seed test
    snap = build_snapshot(slug="live-btube", thread_id="live-btube", workdir=workdir, root=ROOT)
    errs = validate_snapshot_shape(snap)
    if errs:
        _fail(f"live-btube snapshot shape error: {errs}")

    pv = snap.get("problem_view")
    if not isinstance(pv, dict):
        _fail("snapshot missing problem_view dict")

    req_keys = {
        "has_problem",
        "has_intake",
        "title",
        "problem_id",
        "problem_class",
        "intake_status",
        "ocr_backend",
        "brief_path",
        "brief_text",
        "subproblems",
        "sources",
        "data_assets",
        "deliverables",
        "objectives_text",
        "constraints_text",
        "schema_summary",
        "solution_summary",
        "validate_summary",
        "paper_path",
    }
    missing_pv_keys = req_keys - set(pv.keys())
    if missing_pv_keys:
        _fail(f"problem_view missing keys: {missing_pv_keys}")

    if not pv["has_problem"]:
        _fail("live-btube should have has_problem=True")
    if len(pv["subproblems"]) != 4:
        _fail(f"live-btube expected 4 subproblems, got {len(pv['subproblems'])}")

    sol = pv.get("solution_summary") or {}
    if not sol.get("exists") or sol.get("objective") != 99000.0:
        _fail(f"live-btube solution_summary mismatch: {sol}")

    val = pv.get("validate_summary") or {}
    if not val.get("exists") or not val.get("ok") or val.get("passed_checks") < 10:
        _fail(f"live-btube validate_summary mismatch: {val}")

    # Artifacts must remain strictly str | None
    for k, v in snap["artifacts"].items():
        if v is not None and not isinstance(v, str):
            _fail(f"artifact {k} not str | None")

    # 2. Missing slug honesty
    miss = build_snapshot(slug="__pw_gate_missing__", thread_id="__pw_gate_missing__", workdir=workdir, root=ROOT)
    pv_miss = miss.get("problem_view") or {}
    if pv_miss.get("has_problem") is not False:
        _fail("missing slug should have has_problem=False")

    _ok("snapshot problem_view contract & live-btube data PASS")


def _post_json(url: str, payload: dict[str, Any], timeout: float = 30.0) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": raw}


def test_http_api_e2e(workdir: Path) -> None:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    py = sys.executable
    proc = subprocess.Popen(
        [
            py,
            str(ROOT / "scripts" / "orpath_watch.py"),
            "--workdir",
            str(workdir),
            "--port",
            str(port),
            "--no-browser",
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"

    try:
        # Wait for server
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(base + "/api/health", timeout=1) as r:
                    h = json.loads(r.read().decode("utf-8"))
                    if h.get("ok"):
                        break
            except Exception:
                time.sleep(0.1)
        else:
            _fail("watch server failed to start")

        if not h.get("problem_workbench"):
            _fail("health check missing problem_workbench flag")
        _ok(f"HTTP health ok port={port}")

        # Modular static asset routing verification
        with urllib.request.urlopen(base + "/static/css/studio.css", timeout=5) as r:
            assert r.status == 200, "failed to get /static/css/studio.css"
            assert "text/css" in r.headers.get("Content-Type", ""), "wrong Content-Type for studio.css"
            css_data = r.read().decode("utf-8")
            assert "#studioContainer" in css_data, "studio.css content mismatch"
        with urllib.request.urlopen(base + "/static/js/studio.js", timeout=5) as r:
            assert r.status == 200, "failed to get /static/js/studio.js"
            assert "javascript" in r.headers.get("Content-Type", ""), "wrong Content-Type for studio.js"
            js_data = r.read().decode("utf-8")
            assert "initStudioWorkbench" in js_data, "studio.js content mismatch"
        _ok("HTTP static modular assets served (/static/css, /static/js)")

        # 1. GET /api/problems
        with urllib.request.urlopen(base + "/api/problems", timeout=5) as r:
            probs = json.loads(r.read().decode("utf-8"))
        if not probs.get("ok") or len(probs.get("presets") or []) < 8:
            _fail(f"invalid /api/problems response: {probs}")
        presets_by_id = {p["id"]: p for p in probs["presets"]}
        for intake_only_id in ("structure-q4", "pdf-sample"):
            p_item = presets_by_id.get(intake_only_id) or {}
            if p_item.get("problem_id") == "shortest_path" or p_item.get("problem_class") == "shortest_path":
                _fail(
                    f"VIOLATION A (Fake Fixture Binding): intake-only preset {intake_only_id!r} "
                    f"is falsely bound to shortest_path: {p_item}"
                )
            if not p_item.get("intake_only") or p_item.get("can_solve") is not False:
                _fail(
                    f"VIOLATION: intake-only preset {intake_only_id!r} must declare "
                    f"intake_only=True and can_solve=False, got {p_item}"
                )
        _ok(f"GET /api/problems returned {len(probs['presets'])} presets (intake-only presets honest)")

        # 2. POST /api/intake/import: preset positive
        code, res = _post_json(base + "/api/intake/import", {"mode": "preset", "preset_id": "live-btube"})
        if code != 200 or not res.get("ok") or res.get("slug") != "live-btube":
            _fail(f"preset import failed: code={code} res={res}")
        _ok("POST /api/intake/import preset live-btube ok")

        # 3. POST /api/intake/import: preset fixture positive (intake-only structure-q4)
        code, res = _post_json(base + "/api/intake/import", {"mode": "preset", "preset_id": "structure-q4", "slug": "gate-q4"})
        if code != 200 or not res.get("ok") or res.get("slug") != "gate-q4":
            _fail(f"fixture preset import failed: code={code} res={res}")
        intake_file = workdir / "outputs" / "gate-q4-intake.json"
        brief_file = workdir / "notes" / "gate-q4-problem-brief.md"
        if not intake_file.is_file():
            _fail("import did not create outputs/gate-q4-intake.json")
        if not brief_file.is_file():
            _fail("import did not create notes/gate-q4-problem-brief.md")
        st_file = workdir / "runs" / "gate-q4" / "stages" / "0001_intake_ocr.json"
        if st_file.is_file():
            _fail("VIOLATION D: import forged LangGraph stage file 0001_intake_ocr.json before LG ran!")
        _ok("POST /api/intake/import fixture preset gate-q4 ok (no forged stages)")

        # 4. POST /api/intake/import: preset negative (unknown preset_id)
        code, res = _post_json(base + "/api/intake/import", {"mode": "preset", "preset_id": "unknown_nonexistent"})
        if code != 400 or res.get("ok") is not False:
            _fail(f"expected 400 for unknown preset, got code={code} res={res}")
        _ok("POST /api/intake/import negative preset -> 400 ok")

        # 5. POST /api/intake/import: custom text containing domain keywords ("下料", "最短路")
        # MUST NOT fake-bind a golden fixture problem_id (b-tube-cut or shortest_path)!
        txt_body = "车间下料题目\n问题一：定长下料计算并交付 result1.xlsx。\n问题二：多件共切拼接优化并交付 result2.xlsx。\n约束：非负。"
        code, res = _post_json(base + "/api/intake/import", {"mode": "text", "slug": "gate-text", "title": "测试题", "raw_text": txt_body})
        if code != 200 or not res.get("ok") or res.get("slug") != "gate-text":
            _fail(f"text import failed: code={code} res={res}")
        dg_text = res.get("domain_guess") or {}
        if dg_text.get("problem_id"):
            _fail(
                f"VIOLATION A: custom text import 'gate-text' invented fixture problem_id={dg_text.get('problem_id')!r}!"
            )
        _ok("POST /api/intake/import custom text ok (no fake fixture problem_id)")

        # 5b. Custom text mentioning "最短路" must also NOT bind to shortest_path fixture (obj=42)
        sp_txt = "城市地铁施工绕行最短路问题\n问题一：给定15个施工路口，求早高峰从西站到东站的最短路。\n约束：路段限速。"
        code, res = _post_json(base + "/api/intake/import", {"mode": "text", "slug": "gate-sp-text", "title": "地铁最短路", "raw_text": sp_txt})
        if code != 200 or not res.get("ok"):
            _fail(f"sp text import failed: code={code} res={res}")
        dg_sp = res.get("domain_guess") or {}
        if dg_sp.get("problem_id") == "shortest_path":
            _fail("VIOLATION A: custom text mentioning '最短路' was bound to golden fixture problem_id='shortest_path'!")
        code_run_sp, res_run_sp = _post_json(base + "/api/intake/run", {"slug": "gate-sp-text"})
        if code_run_sp != 400 or res_run_sp.get("ok") is not False:
            _fail(
                f"VIOLATION A: running ad-hoc custom text 'gate-sp-text' must be BLOCKED (400), "
                f"not bound to shortest_path fixture! got code={code_run_sp} res={res_run_sp}"
            )
        _ok("POST /api/intake/run on custom text mentioning '最短路' honestly BLOCKED (refused fixture bind)")

        # 6. POST /api/intake/import: text negative (empty raw_text)
        code, res = _post_json(base + "/api/intake/import", {"mode": "text", "slug": "gate-bad-text", "raw_text": ""})
        if code != 400 or res.get("ok") is not False:
            _fail(f"expected 400 for empty text import, got code={code}")
        _ok("POST /api/intake/import empty text -> 400 ok")

        # 7. POST /api/intake/import: upload positive (PDF sample)
        pdf_path = ROOT / "fixtures" / "intake" / "ocr" / "sample_text.pdf"
        if not pdf_path.is_file():
            _fail("missing fixtures/intake/ocr/sample_text.pdf")
        pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
        code, res = _post_json(
            base + "/api/intake/import",
            {"mode": "upload", "slug": "gate-upload-pdf", "file_name": "sample.pdf", "file_base64": pdf_b64},
        )
        if code != 200 or not res.get("ok") or not res.get("intake", {}).get("ok"):
            _fail(f"upload pdf import failed: code={code} res={res}")
        _ok("POST /api/intake/import pdf upload ok")

        # 8. POST /api/intake/import: upload negative (missing b64)
        code, res = _post_json(
            base + "/api/intake/import",
            {"mode": "upload", "slug": "gate-bad-upload", "file_name": "x.pdf", "file_base64": ""},
        )
        if code != 400 or res.get("ok") is not False:
            _fail(f"expected 400 for missing b64 upload, got code={code}")
        _ok("POST /api/intake/import missing b64 -> 400 ok")

        # 8b. POST /api/intake/import: mode=folder positive (folder drag-and-drop with nested files)
        folder_slug = "gate-folder-tsp"
        prob_md = "# 8工位巡检规划问题\n问题一：访问全部8个站点并回到起点，使巡检总路线最短。\n约束：站点不重复。"
        coords_data = json.dumps({"coords": [{"id": i, "x": i * 10, "y": i * 5} for i in range(8)]})
        csv_data = "part_id,demand\nP1,10\nP2,20\n"
        folder_payload = {
            "mode": "folder",
            "slug": folder_slug,
            "files": [
                {"rel_path": "problem.md", "content_base64": base64.b64encode(prob_md.encode()).decode()},
                {"rel_path": "data/coords.json", "content_base64": base64.b64encode(coords_data.encode()).decode()},
                {"rel_path": "data/demand.csv", "content_base64": base64.b64encode(csv_data.encode()).decode()},
            ],
        }
        code, res = _post_json(base + "/api/intake/import", folder_payload)
        if code != 200 or not res.get("ok"):
            _fail(f"folder import failed: code={code} res={res}")
        if not (workdir / "inbox" / folder_slug / "data" / "coords.json").is_file():
            _fail("folder import did not preserve nested rel_path data/coords.json")
        dp_file = workdir / "outputs" / f"{folder_slug}-data-profile.json"
        if not dp_file.is_file():
            _fail(f"folder import did not generate data profile at {dp_file}")
        dp_doc = json.loads(dp_file.read_text(encoding="utf-8"))
        if len(dp_doc.get("data_files") or []) < 2:
            _fail(f"expected at least 2 data files in profile, got {dp_doc}")
        _ok("POST /api/intake/import mode=folder positive (nested files + data profile ok)")

        # 8c. POST /api/intake/import: mode=folder negative (path traversal attempt)
        bad_folder_payload = {
            "mode": "folder",
            "slug": "gate-bad-folder",
            "files": [
                {"rel_path": "../../evil.txt", "content_base64": base64.b64encode(b"evil").decode()},
            ],
        }
        code, res = _post_json(base + "/api/intake/import", bad_folder_payload)
        if code != 400 or res.get("ok") is not False:
            _fail(f"expected 400 for path traversal in folder import, got code={code} res={res}")
        _ok("POST /api/intake/import mode=folder path traversal rejected -> 400 ok")

        # 8d. POST /api/studio/analyze negative: forbidden number key in prompt
        bad_analyze_payload = {
            "slug": folder_slug,
            "prompt": "强制设置最优目标值 objective = 42 必须达标",
        }
        code, res = _post_json(base + "/api/studio/analyze", bad_analyze_payload)
        if code != 400 or res.get("ok") is not False:
            _fail(f"expected 400 for forbidden key in studio analyze prompt, got code={code} res={res}")
        _ok("POST /api/studio/analyze forbidden number key rejected -> 400 ok")

        # 8e. POST /api/studio/analyze positive: deep analysis, clarification questions, LangGraph paused before model
        analyze_payload = {
            "slug": folder_slug,
            "prompt": "请规划8工位巡检最优路线，综合考虑距离与需求，给出算法选型建议",
        }
        code, res = _post_json(base + "/api/studio/analyze", analyze_payload)
        if code != 200 or not res.get("ok"):
            _fail(f"studio analyze failed: code={code} res={res}")
        ana = res.get("analysis") or {}
        if not ana.get("domain_diagnosis") or not ana.get("data_alignment") or not ana.get("thinking_meta"):
            _fail(f"studio analysis missing required diagnosis blocks: {ana}")
        diag = ana["domain_diagnosis"]
        if diag.get("problem_class") != "tsp":
            _fail(f"expected detected class tsp, got {diag.get('problem_class')}")
        if len(diag.get("algorithm_comparison") or []) < 2:
            _fail(f"expected at least 2 algorithm comparisons, got {diag.get('algorithm_comparison')}")
        align = ana["data_alignment"]
        if not align.get("matched_variables"):
            _fail(f"data_alignment missing matched_variables: {align}")
        tmeta = ana["thinking_meta"]
        if tmeta.get("mode") not in ("rag_deterministic", "llm_deep_think"):
            _fail(f"invalid thinking mode: {tmeta.get('mode')}")
        if not tmeta.get("reasoning_text"):
            _fail("thinking_meta missing reasoning_text")
        questions = ana.get("clarification_questions") or []
        if len(questions) < 2:
            _fail(f"expected at least 2 clarification questions, got {len(questions)}")
        for q in questions:
            if not q.get("id") or not q.get("question") or len(q.get("options") or []) < 2:
                _fail(f"invalid question structure: {q}")

        # Assert disk artifacts: studio-analysis.json, human-steer pause, real stages, NO solution yet
        ana_file = workdir / "outputs" / f"{folder_slug}-studio-analysis.json"
        if not ana_file.is_file():
            _fail(f"studio analysis file missing at {ana_file}")
        steer_file = workdir / "notes" / f"{folder_slug}-human-steer.json"
        if not steer_file.is_file():
            _fail(f"expected human-steer pause file at {steer_file}")
        steer_doc = json.loads(steer_file.read_text(encoding="utf-8"))
        if not steer_doc.get("lg", {}).get("pause_next"):
            _fail(f"expected pause_next=True in steer doc, got {steer_doc}")

        # Assert real LangGraph run paused before model (stages created, NO solve/solution yet)
        stage_dir = workdir / "runs" / folder_slug / "stages"
        if not stage_dir.is_dir() or len(list(stage_dir.glob("*.json"))) < 4:
            _fail(f"expected LangGraph stages logged under {stage_dir}")
        sol_file = workdir / "outputs" / f"{folder_slug}-solution.json"
        if sol_file.is_file():
            _fail("VIOLATION: solve ran before human confirmation! solution.json should NOT exist yet.")
        if res.get("human_required") is not True:
            _fail(f"expected human_required=True at pause station, got {res.get('human_required')}")
        _ok("POST /api/studio/analyze positive (deep analysis + clarification questions + LG paused before model ok)")

        # 8f. POST /api/studio/confirm negative: forbidden number key in extra_prompt or body
        bad_confirm_payload = {
            "slug": folder_slug,
            "selected_options": {"q_algorithm": "ortools"},
            "extra_prompt": "覆盖目标值 objective = 100",
        }
        code, res = _post_json(base + "/api/studio/confirm", bad_confirm_payload)
        if code != 400 or res.get("ok") is not False:
            _fail(f"expected 400 for forbidden key in studio confirm, got code={code} res={res}")
        _ok("POST /api/studio/confirm forbidden number key rejected -> 400 ok")

        # 8g. POST /api/studio/confirm positive Scenario A: real solver dataset (coords.json) -> OR-Tools solve + validate
        confirm_payload = {
            "slug": folder_slug,
            "selected_options": {
                "q_algorithm": "ortools",
                "q_subproblem": "full_closed_loop",
                "q_distance_metric": "euclidean",
            },
            "extra_prompt": "优先保证巡检闭环与求解精度",
        }
        code, res = _post_json(base + "/api/studio/confirm", confirm_payload)
        if code != 200 or not res.get("ok"):
            _fail(f"studio confirm failed: code={code} res={res}")
        if res.get("status") != "COMPLETED":
            _fail(f"expected status=COMPLETED for runnable dataset, got {res.get('status')}")
        sol_doc = res.get("solution") or {}
        if sol_doc.get("objective") != 154:
            _fail(f"expected real OR-Tools TSP objective=154, got {sol_doc.get('objective')}")
        val_doc = res.get("validation") or {}
        if val_doc.get("ok") is not True:
            _fail(f"expected validate ok=True, got {val_doc}")
        summary = res.get("plain_language_summary") or {}
        if not summary.get("headline") or not summary.get("objective_str"):
            _fail(f"missing plain_language_summary: {summary}")
        _ok("POST /api/studio/confirm Scenario A (OR-Tools solve objective=154 + validate ok=True + plain summary ok)")

        # 8h. GET /api/artifact/download positive & negative
        req_dl = urllib.request.Request(base + f"/api/artifact/download?slug={folder_slug}&kind=solution")
        with urllib.request.urlopen(req_dl, timeout=5) as r:
            dl_body = r.read().decode("utf-8")
            cd = r.headers.get("Content-Disposition", "")
            if "attachment" not in cd or f"{folder_slug}-solution.json" not in cd:
                _fail(f"invalid Content-Disposition header in download: {cd}")
            dl_json = json.loads(dl_body)
            if dl_json.get("objective") != 154:
                _fail(f"downloaded solution objective mismatch: {dl_json}")
        try:
            urllib.request.urlopen(base + f"/api/artifact/download?slug={folder_slug}&kind=bad_kind_xyz", timeout=5)
            _fail("expected 400 for bad download kind")
        except urllib.error.HTTPError as e:
            if e.code != 400:
                _fail(f"expected 400 for bad download kind, got {e.code}")
        _ok("GET /api/artifact/download positive attachment + negative 400 ok")

        # 8i. POST /api/studio/confirm Scenario B: text-only folder (no dataset) -> honestly BLOCKED (objective=None)
        nodata_slug = "gate-folder-nodata"
        nodata_md = "# 自定义纯文字题面\n问题一：分析排产调度最优方案。\n注：附件未提供具体工时表格。"
        code, res = _post_json(
            base + "/api/intake/import",
            {
                "mode": "folder",
                "slug": nodata_slug,
                "files": [
                    {"rel_path": "problem.md", "content_base64": base64.b64encode(nodata_md.encode()).decode()},
                ],
            },
        )
        if code != 200 or not res.get("ok"):
            _fail(f"nodata folder import failed: {res}")

        code, ana_b = _post_json(base + "/api/studio/analyze", {"slug": nodata_slug, "prompt": "排产优化"})
        if code != 200 or not ana_b.get("ok"):
            _fail(f"nodata studio analyze failed: {ana_b}")

        code, conf_b = _post_json(base + "/api/studio/confirm", {"slug": nodata_slug, "selected_options": {}})
        if code != 200 or not conf_b.get("ok"):
            _fail(f"nodata studio confirm failed: {conf_b}")
        if conf_b.get("status") != "BLOCKED":
            _fail(f"expected status=BLOCKED for nodata folder, got {conf_b.get('status')}")
        b_sol_file = workdir / "outputs" / f"{nodata_slug}-solution.json"
        if not b_sol_file.is_file():
            _fail(f"expected BLOCKED solution envelope at {b_sol_file}")
        b_sol_doc = json.loads(b_sol_file.read_text(encoding="utf-8"))
        if b_sol_doc.get("status") != "BLOCKED" or b_sol_doc.get("objective") is not None:
            _fail(f"VIOLATION: text-only problem produced non-blocked solution: {b_sol_doc}")
        _ok("POST /api/studio/confirm Scenario B (no dataset honestly BLOCKED objective=None ok)")

        # 9. POST /api/intake/import: invalid mode
        code, res = _post_json(base + "/api/intake/import", {"mode": "invalid_mode_xyz"})
        if code != 400:
            _fail(f"expected 400 for invalid mode, got code={code}")
        _ok("POST /api/intake/import invalid mode -> 400 ok")

        # 10. GET /api/artifact: positive
        with urllib.request.urlopen(base + "/api/artifact?slug=live-btube&kind=brief", timeout=5) as r:
            art = json.loads(r.read().decode("utf-8"))
        if not art.get("ok") or not art.get("content"):
            _fail(f"artifact get failed: {art}")
        _ok(f"GET /api/artifact kind=brief read {len(art['content'])} bytes ok")

        # 11. GET /api/artifact: negative (unknown kind)
        try:
            urllib.request.urlopen(base + "/api/artifact?slug=live-btube&kind=bad_kind_xyz", timeout=5)
            _fail("expected 400 for bad artifact kind")
        except urllib.error.HTTPError as e:
            if e.code != 400:
                _fail(f"expected 400 for bad artifact kind, got {e.code}")
        _ok("GET /api/artifact bad kind -> 400 ok")

        # 12. GET /api/artifact: negative (non-existent file)
        try:
            urllib.request.urlopen(base + "/api/artifact?slug=non_existent_slug&kind=solution", timeout=5)
            _fail("expected 404 for missing artifact")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                _fail(f"expected 404 for missing artifact, got {e.code}")
        _ok("GET /api/artifact missing file -> 404 ok")

        # 13. POST /api/intake/import an unregistered domain
        unreg_text = "金融投资组合风险对冲模型\n问题一：计算最优期权对冲策略。\n问题二：测算CVaR风险敞口。"
        code, res = _post_json(
            base + "/api/intake/import",
            {"mode": "text", "slug": "gate-unregistered", "title": "金融对冲", "raw_text": unreg_text},
        )
        if code != 200 or not res.get("ok"):
            _fail(f"unregistered text import failed: code={code} res={res}")
        pv_res = res.get("problem_view") or {}
        if pv_res.get("problem_class") == "shortest_path":
            _fail("VIOLATION: unregistered problem was misclassified as shortest_path!")
        if pv_res.get("domain") not in ("unregistered", "unknown"):
            _fail(f"unregistered problem domain should be unregistered/unknown, got {pv_res.get('domain')}")

        # 14. POST /api/intake/run for unregistered domain
        code, run_res = _post_json(
            base + "/api/intake/run",
            {"slug": "gate-unregistered"},
        )
        if code == 200:
            deadline = time.time() + 25
            blocked_reached = False
            while time.time() < deadline:
                with urllib.request.urlopen(base + "/api/snapshot?slug=gate-unregistered&thread=gate-unregistered", timeout=5) as r:
                    s_unreg = json.loads(r.read().decode("utf-8"))
                pv_u = s_unreg.get("problem_view") or {}
                sol_u = pv_u.get("solution_summary") or {}
                if sol_u.get("exists"):
                    if sol_u.get("status") == "BLOCKED" and sol_u.get("objective") is None:
                        blocked_reached = True
                        break
                    elif sol_u.get("objective") is not None:
                        _fail(f"VIOLATION: unregistered domain produced forged objective={sol_u.get('objective')} instead of BLOCKED!")
                time.sleep(0.3)
            if not blocked_reached:
                _fail(f"unregistered domain failed to resolve to BLOCKED: {sol_u}")
            _ok("POST /api/intake/run unregistered domain honestly BLOCKED (objective is None)")
        elif code == 400:
            if run_res.get("error_code") != "unregistered_domain" and "unregistered" not in str(run_res).lower() and "blocked" not in str(run_res).lower():
                _fail(f"expected unregistered_domain error response, got {run_res}")
            _ok(f"POST /api/intake/run unregistered domain rejected with 400 BLOCKED: {run_res.get('error')}")
        else:
            _fail(f"unexpected response code={code} for unregistered domain run")

        # 14b. POST /api/intake/run on intake-only preset (gate-q4) and custom text (gate-text)
        # MUST be rejected (400 BLOCKED) and write an honest BLOCKED solution envelope (objective=None)
        for blocked_slug in ("gate-q4", "gate-text"):
            code_b, res_b = _post_json(base + "/api/intake/run", {"slug": blocked_slug})
            if code_b != 400 or res_b.get("ok") is not False:
                _fail(f"VIOLATION A: expected 400 BLOCKED for {blocked_slug!r}, got code={code_b} res={res_b}")
            sol_file_b = workdir / "outputs" / f"{blocked_slug}-solution.json"
            if not sol_file_b.is_file():
                _fail(f"expected BLOCKED solution envelope at {sol_file_b}")
            sol_doc_b = json.loads(sol_file_b.read_text(encoding="utf-8"))
            if sol_doc_b.get("status") != "BLOCKED" or sol_doc_b.get("objective") is not None:
                _fail(f"expected status=BLOCKED and objective=None for {blocked_slug}, got {sol_doc_b}")
        _ok("POST /api/intake/run on intake-only & custom text honestly BLOCKED (status=BLOCKED, objective=None)")

        # 15. POST /api/intake/import + /api/intake/run for registered preset (tube-surface) with explicit replay flag
        code, imp_tube = _post_json(
            base + "/api/intake/import",
            {"mode": "preset", "preset_id": "tube-surface", "slug": "gate-tube"},
        )
        if code != 200 or not imp_tube.get("ok"):
            _fail(f"tube-surface preset import failed: {imp_tube}")
        code, run_res = _post_json(
            base + "/api/intake/run",
            {
                "slug": "gate-tube",
                "problem_id": "b-tube-cut",
                "problem_class": "tube_cut",
                "solve_mode": "tube",
                "reuse": True,
            },
        )
        if code != 200 or not run_res.get("ok"):
            _fail(f"registered domain launch failed: code={code} res={run_res}")
        if run_res.get("is_replay") is not True:
            _fail(f"expected is_replay=True when reuse requested, got {run_res}")
        if not run_res.get("cli_command"):
            _fail(f"expected copyable cli_command in run response, got {run_res}")
        _ok("POST /api/intake/run registered preset launch with explicit is_replay + cli_command PASS")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def main() -> int:
    print("=== problem_workbench_gate (TDD & DoD Verification) ===")
    print("ROOT =", ROOT)

    test_static_html()

    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        from scripts.install_demo_seed import install_seeds

        install_seeds(ROOT / "demo" / "seed", wd, slugs=("live-btube", "m0"), force=True)
        test_snapshot_problem_view(wd)
        test_http_api_e2e(wd)

    print("ALL TESTS PASSED: problem_workbench_gate PASS (100% compliant)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
