#!/usr/bin/env python3
"""Automated regression tests for OR-Path Frontend Health & Security.

Validates the fixes for issues documented in outputs/frontend_health_report.md:
- P0: Attribute injection sinks (statusClass, data-seq, obj=).
- P1: Functional bugs (file-picker IDs, file count element, iconFor("gate"), fetchToken race).
- P2: Memory budgets, recursion depth guards, skipping inspector render in studio mode.
- Design: Zero 'transition: all' antipatterns in src/css/*.css.
- Packaging: build.py incremental check & marker integrity in watch.html.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "orpath" / "web"
SRC_DIR = WEB_DIR / "src"
CSS_DIR = SRC_DIR / "css"
JS_DIR = SRC_DIR / "js"
HTML_DIR = SRC_DIR / "html"


def _read_bundle(base: Path, pattern: str) -> str:
    files = sorted(base.glob(pattern))
    assert files, f"Expected files matching {pattern} in {base}"
    return "\n".join(p.read_text(encoding="utf-8") for p in files)


def _studio_js() -> str:
    return _read_bundle(JS_DIR / "studio", "*.js")


def _watch_js() -> str:
    return _read_bundle(JS_DIR / "watch", "*.js")


def _studio_css() -> str:
    return _read_bundle(CSS_DIR / "studio", "*.css")


def _studio_html() -> str:
    return _read_bundle(HTML_DIR / "studio", "*.html")


def _watch_html() -> str:
    return _read_bundle(HTML_DIR / "watch", "*.html")


def test_build_script_and_dual_pages():
    """Verify build.py builds isolated watch.html and studio.html pages."""
    build_py = WEB_DIR / "build.py"
    assert build_py.is_file(), "Missing build.py"

    import subprocess
    r = subprocess.run([sys.executable, str(build_py), "--force"], cwd=str(ROOT), capture_output=True, text=True)
    assert r.returncode == 0, f"build.py failed: {r.stderr}"
    assert "watch.html assembled successfully" in r.stdout
    assert "studio.html assembled successfully" in r.stdout

    watch_html = WEB_DIR / "watch.html"
    studio_html = WEB_DIR / "studio.html"
    assert watch_html.is_file()
    assert studio_html.is_file()

    w_content = watch_html.read_text(encoding="utf-8")
    s_content = studio_html.read_text(encoding="utf-8")
    assert "boot();" in w_content
    assert "boot();" in s_content
    assert 'class="mode-inspector"' in w_content
    assert 'class="mode-studio"' in s_content
    assert 'id="watch-root"' in w_content
    assert 'id="studio-root"' in s_content

    # Dual-page isolation: studio.html has no Watch polling; watch.html has no studio workbench JS/CSS
    assert "function fetchSnapshot" not in s_content
    assert "POLL_MS" not in s_content
    assert "function initStudioWorkbench" not in w_content
    assert "DOMAIN_SWARM_PROFILES" not in s_content
    assert "DOMAIN_SWARM_PROFILES" not in w_content


def test_p0_sinks_secured():
    """Verify all P0 attribute-injection sinks are escaped."""
    common_js = (JS_DIR / "common.js").read_text(encoding="utf-8")
    inspector_js = _watch_js()

    # 1. statusClass must escape output
    assert 'return "badge st-" + esc(' in common_js

    # 2. data-seq must be escaped
    assert 'data-seq="${esc(st.seq)}"' in inspector_js
    assert 'data-seq="${st.seq}"' not in inspector_js

    # 3. selector interpolation must use CSS.escape
    assert 'CSS.escape(String(last.seq))' in inspector_js
    assert 'CSS.escape(String(selectedStageSeq))' in inspector_js

    # 4. c.objective in problem catalog must be escaped
    assert 'obj=${esc(c.objective)}' in inspector_js
    assert 'obj=${c.objective}' not in inspector_js


def test_p1_functional_bugs_fixed():
    """Verify P1 bugs identified in audit are fixed."""
    common_js = (JS_DIR / "common.js").read_text(encoding="utf-8")
    studio_js = _studio_js()
    inspector_js = _watch_js()

    # 1. iconFor("gate") must return door emoji, not " entr"
    assert 'gate: "🚪"' in common_js
    assert '" entr"' not in common_js

    # 2. Studio file picker buttons aligned with studio.html
    assert '$("btnPickFolder")' in studio_js
    assert '$("btnPickFiles")' in studio_js

    # 3. File ready element updated
    assert '$("studioFileReadyText")' in studio_js

    # 4. fetchSnapshot concurrency sequence token
    assert "let fetchToken = 0;" in inspector_js
    assert "const myToken = ++fetchToken;" in inspector_js
    assert "if (myToken !== fetchToken) return;" in inspector_js

    # 5. dialogue steer prefer_methods handles string or array without crash
    assert "Array.isArray(pm) ? pm.join" in inspector_js
    assert '(pi.prefer_methods || []).join(", ")' not in inspector_js

    # 6. URL construction and slug reading inside try block
    assert "async function fetchSnapshot(force) {" in inspector_js
    idx_func = inspector_js.find("async function fetchSnapshot(force) {")
    idx_try = inspector_js.find("try {", idx_func)
    idx_p = inspector_js.find("new URLSearchParams()", idx_func)
    assert idx_try < idx_p, "URLSearchParams must be initialized inside the try block"


def test_p2_memory_and_dead_state_cleanup():
    """Verify memory budgets, studio mode optimizations, and dead state removal."""
    common_js = (JS_DIR / "common.js").read_text(encoding="utf-8")
    studio_js = _studio_js()
    inspector_js = _watch_js()

    # Dead state removed
    assert "let pollMode" not in common_js
    assert "let lastEventsAdded" not in common_js
    assert "let dlgFollow" not in common_js

    # File budgeting in studio
    assert "MAX_STUDIO_FILES" in studio_js
    assert "MAX_STUDIO_TOTAL_BYTES" in studio_js
    assert "MAX_STUDIO_FILE_BYTES" in studio_js
    assert "MAX_RECURSION_DEPTH" in studio_js

    # Byte cap check in input listeners
    assert "curBytes + (f.size || 0) > MAX_STUDIO_TOTAL_BYTES" in studio_js

    # AbortControllers for asynchronous operations
    assert "analyzeAbortController" in studio_js
    assert "artifactAbortController" in inspector_js

    # Decoupled JS/Modals invariants: Watch polling lives in watch/*, shared intake in intake.js
    assert "function setAppMode" not in common_js
    assert "const POLL_MS" not in common_js
    assert "const POLL_MS" in inspector_js
    assert "orpathIntakeImport" in (JS_DIR / "intake.js").read_text(encoding="utf-8")
    assert "orpathIntakeImport" in studio_js
    assert "orpathIntakeImport" in inspector_js
    assert (HTML_DIR / "watch" / "modals.html").is_file()
    assert not (HTML_DIR / "modals_studio.html").exists()
    assert not (HTML_DIR / "modals.html").exists()

    # Result card objective honesty fallback
    assert "无解/求解受阻" in studio_js or "等待求解产物" in studio_js
    assert 'summary.objective_str || (res.solution?.objective != null ? `最优目标值: ${res.solution?.objective}` : "客观数值已锁定")' not in studio_js


def test_security_headers_and_csp():
    """Verify Content-Security-Policy header in server, meta tags in both pages, and /studio HTTP route."""
    watch_py = (ROOT / "scripts" / "orpath_watch.py").read_text(encoding="utf-8")
    assert "Content-Security-Policy" in watch_py
    assert '"/studio"' in watch_py

    for page_name in ("watch.html", "studio.html"):
        html_text = (WEB_DIR / page_name).read_text(encoding="utf-8")
        assert '<meta http-equiv="Content-Security-Policy"' in html_text


def test_css_zero_transition_all():
    """Verify zero 'transition: all' antipatterns remain in any CSS module."""
    css_files = list(CSS_DIR.rglob("*.css"))
    assert css_files
    for css_file in css_files:
        text = css_file.read_text(encoding="utf-8")
        matches = re.findall(r"transition\s*:\s*all", text, re.IGNORECASE)
        assert len(matches) == 0, f"Found 'transition: all' in {css_file}: {matches}"


def test_modal_and_keyboard_shortcuts_and_a11y():
    """Verify ESC modal closing, Enter key submits, and aria-live announcements exist."""
    inspector_js = _watch_js()
    inspector_html = (HTML_DIR / "watch" / "shell.html").read_text(encoding="utf-8")
    common_js = (JS_DIR / "common.js").read_text(encoding="utf-8")

    assert 'e.key === "Escape"' in inspector_js
    assert 'e.key === "Enter"' in inspector_js
    assert 'aria-live="polite"' in inspector_html
    assert 'role="alert"' in inspector_html
    assert 'setAttribute("role", "status")' in common_js


def test_dual_mode_and_lean_4agent_cockpit():
    """Verify Fast Mode 4-step strip, Deep Lean 4-Agent strip, on-demand paper, and removal of 6-card legacy clutter."""
    studio_js = _studio_js()
    studio_html = _studio_html()
    studio_css = _studio_css()
    header_html = (HTML_DIR / "header.html").read_text(encoding="utf-8")

    # 1. Legacy 6-card fake swarm profiles & CSS stripped
    assert "DOMAIN_SWARM_PROFILES" not in studio_js
    assert "renderDomainAgentStrip" not in studio_js
    assert "studioAgentStrip" not in studio_html
    assert "ma-agent-card" not in studio_css

    # 2. 10 domain visualization badges kept in lightweight lookup
    expected_domains = [
        "cutting", "routing", "scheduling", "project", "inventory",
        "facility", "rostering", "microgrid", "pricing", "finance"
    ]
    for d in expected_domains:
        assert f"{d}:" in studio_js, f"Missing domain {d} in DOMAIN_BADGES"

    # 3. Dual-mode Run Switcher (Fast 4-step vs Deep Lean 4-Agent) + CSS 4-column responsive strip
    assert 'id="btnRunModeFast"' in studio_html
    assert 'id="btnRunModeDeep"' in studio_html
    assert 'id="studioFastProgress"' in studio_html
    assert 'id="studioDeepStrip"' in studio_html
    for agent_id in ("deepCardAnalyst", "deepCardModeler", "deepCardWriter", "deepCardReviewer"):
        assert agent_id in studio_html
    assert "repeat(4, minmax(0, 1fr))" in studio_css
    assert "setPipelineStage" in studio_js
    assert "skip_paper:" in studio_js

    # 4. On-demand paper button & multi-page header links
    assert 'id="btnStudioGeneratePaper"' in studio_html
    assert "/api/studio/paper" in studio_js
    assert 'href="/studio"' in header_html
    assert 'href="/"' in header_html


def test_dynamic_visualization_components():
    """Verify Phase 6 dynamic Gantt chart, route map, and convergence Gap curves."""
    studio_js = _studio_js()
    studio_html = _studio_html()
    studio_css = _studio_css()

    # 1. HTML Visualization Container & Tabs
    assert 'id="studioVizContainer"' in studio_html
    assert 'id="vizDomainBadge"' in studio_html
    assert 'id="tabVizGantt"' in studio_html
    assert 'id="tabVizRoutes"' in studio_html
    assert 'id="tabVizGap"' in studio_html
    assert 'id="vizPanelGantt"' in studio_html
    assert 'id="vizPanelRoutes"' in studio_html
    assert 'id="vizPanelGap"' in studio_html

    # 2. JS Renderers for all 3 panels
    assert "function renderGanttChart" in studio_js
    assert "function renderRouteMap" in studio_js
    assert "function renderConvergenceGapCurve" in studio_js
    assert "function renderVisualizations" in studio_js
    assert "function initVizTabsOnce" in studio_js
    assert "function showVizTooltip" in studio_js
    assert "window.syncStudioSnapshot" not in studio_js

    # 3. Gantt features: Numbers Truth guard, machine scheduling, makespan
    assert "Numbers Truth" in studio_js
    assert "solution.schedule" in studio_js
    assert "Makespan =" in studio_js

    # 4. Route map features: Route planning, customer points, stops
    assert "solution.routes" in studio_js
    assert "route-node" in studio_js

    # 5. Convergence curve: Dual bounds, real gap trajectory, Numbers Truth guard
    assert "gap_history" in studio_js
    assert "Gap:" in studio_js

    # 6. CSS styles for visualization panels
    assert ".studio-viz-card" in studio_css
    assert ".viz-tabs" in studio_css
    assert ".viz-panel" in studio_css
    assert ".viz-tooltip-pill" in studio_css
    assert "id=\"vizInteractiveTooltip\"" in studio_html


def test_assembled_pages_contain_viz_and_watch_components():
    """Verify watch.html and studio.html rebuilt with build.py contain their respective components."""
    import subprocess
    r = subprocess.run([sys.executable, str(WEB_DIR / "build.py"), "--force"], cwd=str(ROOT), capture_output=True, text=True)
    assert r.returncode == 0

    studio_html = (WEB_DIR / "studio.html").read_text(encoding="utf-8")
    assert 'id="studio-root"' in studio_html
    assert 'id="studioVizContainer"' in studio_html
    assert 'id="tabVizGantt"' in studio_html
    assert 'id="studioFastProgress"' in studio_html
    assert 'id="studioDeepStrip"' in studio_html
    assert 'id="btnStudioGeneratePaper"' in studio_html
    assert "renderGanttChart" in studio_html
    assert "renderRouteMap" in studio_html
    assert "renderConvergenceGapCurve" in studio_html
    assert "repeat(4, minmax(0, 1fr))" in studio_html

    watch_html = (WEB_DIR / "watch.html").read_text(encoding="utf-8")
    assert 'id="watch-root"' in watch_html
    assert 'id="inspectorContainer"' in watch_html
    assert 'id="intakeModal"' in watch_html
    assert 'id="artifactModal"' in watch_html


def test_http_routes_watch_and_studio(tmp_path: Path):
    """Verify orpath_watch serves watch.html on GET / and studio.html on GET /studio."""
    import threading
    import urllib.request
    from scripts.orpath_watch import make_server

    server = make_server(workdir=tmp_path, home=ROOT, host="127.0.0.1", port=0)
    port = int(server.server_address[1])
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
            assert resp.status == 200
            body_watch = resp.read().decode("utf-8")
            assert 'id="watch-root"' in body_watch
            assert 'id="studio-root"' not in body_watch
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/studio", timeout=5) as resp:
            assert resp.status == 200
            body_studio = resp.read().decode("utf-8")
            assert 'id="studio-root"' in body_studio
            assert 'id="watch-root"' not in body_studio
    finally:
        server.shutdown()
        server.server_close()


def test_no_blocking_hitl_gates(tmp_path: Path):
    """Verify blocking HITL confirmation/pause gates are removed across UI and steer state."""
    import json
    from orpath.human_steer import apply_steer_to_state

    studio_js = _studio_js()
    studio_html = _studio_html()
    inspector_html = _watch_html()
    inspector_js = _watch_js()

    # Studio auto-chains analyze -> executeStudioSolve without waiting for human gate
    assert "async function executeStudioSolve" in studio_js
    assert "await executeStudioSolve(signal);" in studio_js
    assert "安全停靠等您把关" not in studio_html
    assert '"待确认"' not in studio_js

    # Inspector UI has no blocking pause boundary selectors
    assert 'id="dlgAtStage"' not in inspector_html
    assert 'id="dlgPause"' not in inspector_html
    assert 'dlgAtStage' not in inspector_js
    assert 'dlgPause' not in inspector_js

    # Even if an old steer file contains pause_next=True, pipeline does not stall
    notes = tmp_path / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    (notes / "s1-human-steer.json").write_text(
        json.dumps({"slug": "s1", "at_stage": "after_research", "lg": {"pause_next": True, "solve_mode": "ortools"}}),
        encoding="utf-8",
    )
    upd = apply_steer_to_state({"slug": "s1", "workdir": str(tmp_path)}, workdir=tmp_path, boundary="model")
    assert upd.get("steer_pause") is False
    assert "human_required" not in upd


def test_frontend_modular_layout():
    """Verify frontend source tree uses focused feature modules (<=450L) and valid Watch renderBadges."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("orpath_web_build", str(WEB_DIR / "build.py"))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    for legacy in (
        JS_DIR / "studio.js",
        JS_DIR / "inspector.js",
        CSS_DIR / "studio.css",
        CSS_DIR / "inspector.css",
        HTML_DIR / "studio.html",
        HTML_DIR / "inspector.html",
        HTML_DIR / "modals_watch.html",
    ):
        assert not legacy.exists(), f"Legacy monolithic file still present: {legacy}"

    for page_name, cfg in mod.PAGES.items():
        for group in ("css", "html", "js"):
            for path in cfg[group]:
                assert path.is_file(), f"Missing {page_name} {group} source: {path}"
                line_count = len(path.read_text(encoding="utf-8").splitlines())
                assert line_count <= 450, f"Module {path.relative_to(SRC_DIR)} exceeds 450 lines ({line_count})"

    watch_state = (JS_DIR / "watch" / "state.js").read_text(encoding="utf-8")
    assert "function renderBadges(s)" in watch_state
    assert "function boot()" in (JS_DIR / "watch" / "boot.js").read_text(encoding="utf-8")
    assert "function boot()" in (JS_DIR / "studio" / "boot.js").read_text(encoding="utf-8")




