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


def test_build_script_and_watch_html():
    """Verify build.py runs, enforces boot() presence, and generates valid watch.html."""
    build_py = WEB_DIR / "build.py"
    assert build_py.is_file(), "Missing build.py"

    import subprocess
    r = subprocess.run([sys.executable, str(build_py), "--force"], cwd=str(ROOT), capture_output=True, text=True)
    assert r.returncode == 0, f"build.py failed: {r.stderr}"
    assert "watch.html assembled successfully" in r.stdout

    watch_html = WEB_DIR / "watch.html"
    assert watch_html.is_file()
    content = watch_html.read_text(encoding="utf-8")
    assert "boot();" in content
    assert 'class="mode-studio"' in content


def test_p0_sinks_secured():
    """Verify all P0 attribute-injection sinks are escaped."""
    common_js = (JS_DIR / "common.js").read_text(encoding="utf-8")
    inspector_js = (JS_DIR / "inspector.js").read_text(encoding="utf-8")

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
    studio_js = (JS_DIR / "studio.js").read_text(encoding="utf-8")
    inspector_js = (JS_DIR / "inspector.js").read_text(encoding="utf-8")

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
    studio_js = (JS_DIR / "studio.js").read_text(encoding="utf-8")
    inspector_js = (JS_DIR / "inspector.js").read_text(encoding="utf-8")

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

    # Skip heavy inspector render in studio mode
    assert 'document.body.classList.contains("mode-studio")' in inspector_js

    # Result card objective honesty fallback
    assert "无解/求解受阻" in studio_js or "等待求解产物" in studio_js
    assert 'summary.objective_str || (res.solution?.objective != null ? `最优目标值: ${res.solution?.objective}` : "客观数值已锁定")' not in studio_js


def test_security_headers_and_csp():
    """Verify Content-Security-Policy header in server and meta tag in HTML."""
    watch_py = (ROOT / "scripts" / "orpath_watch.py").read_text(encoding="utf-8")
    assert "Content-Security-Policy" in watch_py

    watch_html = (WEB_DIR / "watch.html").read_text(encoding="utf-8")
    assert '<meta http-equiv="Content-Security-Policy"' in watch_html


def test_css_zero_transition_all():
    """Verify zero 'transition: all' antipatterns remain in any CSS module."""
    for css_file in CSS_DIR.glob("*.css"):
        text = css_file.read_text(encoding="utf-8")
        matches = re.findall(r"transition\s*:\s*all", text, re.IGNORECASE)
        assert len(matches) == 0, f"Found 'transition: all' in {css_file.name}: {matches}"


def test_modal_and_keyboard_shortcuts_and_a11y():
    """Verify ESC modal closing, Enter key submits, and aria-live announcements exist."""
    inspector_js = (JS_DIR / "inspector.js").read_text(encoding="utf-8")
    inspector_html = (HTML_DIR / "inspector.html").read_text(encoding="utf-8")
    common_js = (JS_DIR / "common.js").read_text(encoding="utf-8")

    assert 'e.key === "Escape"' in inspector_js
    assert 'e.key === "Enter"' in inspector_js
    assert 'aria-live="polite"' in inspector_html
    assert 'role="alert"' in inspector_html
    assert 'setAttribute("role", "status")' in common_js


def test_multidomain_agent_cockpit_rendered():
    """Verify Phase 6 multi-domain 6-agent cockpit metadata and dynamic rendering."""
    studio_js = (JS_DIR / "studio.js").read_text(encoding="utf-8")
    studio_html = (HTML_DIR / "studio.html").read_text(encoding="utf-8")
    studio_css = (CSS_DIR / "studio.css").read_text(encoding="utf-8")

    # 1. 10 domain swarms defined in DOMAIN_SWARM_PROFILES
    expected_domains = [
        "cutting", "routing", "scheduling", "project", "inventory",
        "facility", "rostering", "microgrid", "pricing", "finance"
    ]
    for d in expected_domains:
        assert f"{d}: {{" in studio_js, f"Missing domain {d} in studio.js"

    # 2. Dynamic renderDomainAgentStrip function present and handles 6 roles
    assert "function renderDomainAgentStrip" in studio_js
    assert "data-agent-role" in studio_js or "data-agent-role" in studio_html
    assert "ma-agent-workload" in studio_js or "ma-agent-workload" in studio_html
    assert "ma-workload-bar" in studio_js or "ma-workload-bar" in studio_html
    assert "ma-agent-tool" in studio_js or "ma-agent-tool" in studio_html

    # 3. CSS supports 6-column responsive layout
    assert "repeat(6, minmax(0, 1fr))" in studio_css

    # 4. studio.html includes the 6-agent strip elements
    assert "id=\"studioAgentStrip\"" in studio_html
    assert "agentCardSupervisor" in studio_html or "agentCard_lead" in studio_html
    assert "agentCardRealities" in studio_html
    assert "agentCardRedteam" in studio_html


def test_dynamic_visualization_components():
    """Verify Phase 6 dynamic Gantt chart, route map, and convergence Gap curves."""
    studio_js = (JS_DIR / "studio.js").read_text(encoding="utf-8")
    studio_html = (HTML_DIR / "studio.html").read_text(encoding="utf-8")
    studio_css = (CSS_DIR / "studio.css").read_text(encoding="utf-8")

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
    assert "window.syncStudioSnapshot" in studio_js

    # 3. Gantt features: Makespan red dashed line, machines, time units
    assert "Makespan = 55" in studio_js
    assert "M0 卧式铣床" in studio_js
    assert "solution.schedule" in studio_js

    # 4. Route map features: Depot, directed marker-end arrows, customer points
    assert "配送枢纽 (Depot)" in studio_js
    assert "marker-end" in studio_js
    assert "solution.routes" in studio_js

    # 5. Convergence curve: Optimality Gap shaded polygon, dual bounds
    assert "polygon points=" in studio_js
    assert "Gap: 0.00% 严密闭合" in studio_js

    # 6. CSS styles for visualization panels
    assert ".studio-viz-card" in studio_css
    assert ".viz-tabs" in studio_css
    assert ".viz-panel" in studio_css
    assert ".viz-tooltip-pill" in studio_css
    assert "id=\"vizInteractiveTooltip\"" in studio_html


def test_assembled_watch_html_contains_phase6_components():
    """Verify watch.html rebuilt with build.py contains all Phase 6 multi-domain components."""
    import subprocess
    r = subprocess.run([sys.executable, str(WEB_DIR / "build.py"), "--force"], cwd=str(ROOT), capture_output=True, text=True)
    assert r.returncode == 0

    watch_html = (WEB_DIR / "watch.html").read_text(encoding="utf-8")
    assert 'id="studioVizContainer"' in watch_html
    assert 'id="tabVizGantt"' in watch_html
    assert "renderDomainAgentStrip" in watch_html
    assert "renderGanttChart" in watch_html
    assert "renderRouteMap" in watch_html
    assert "renderConvergenceGapCurve" in watch_html
    assert "repeat(6, minmax(0, 1fr))" in watch_html



