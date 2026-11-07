#!/usr/bin/env python3
"""Task 9 — Web Studio execution base: multi-agent engine + snapshot callback.

Verifies that ``scripts/orpath_watch.py`` `/api/studio/confirm`:

  1. instantiates the compiled multi-agent engine
     (``orpath.control_plane.build_compiled_multiagent``) and mounts
     ``MultiAgentSnapshotCallback(thread_id=slug, slug=slug, workdir=...)``
     during the solve flow;
  2. in multiagent mode (``ORPATH_ENGINE=multiagent`` or unspecified) still
     produces ``outputs/<slug>-solution.json`` and ``outputs/<slug>-validate.json``
     and the interface recognises the result (``status=COMPLETED``, real
     objective, validation ok) — the smooth fallback to ``build_graph`` keeps
     the canonical artifacts guaranteed when the multiagent run cannot
     complete (offline / CI regression);
  3. ``ORPATH_ENGINE=graph`` skips the multiagent path entirely and solves
     through the deterministic ``build_graph`` pipeline.

Everything is offline-safe: the multiagent attempt is bounded
(``ORPATH_MULTIAGENT_TIMEOUT``) and every test asserts the canonical
solution/validate artifacts exist regardless of which engine served the run.

Run:
    .venv/bin/python -m pytest tools/test_watch_multiagent_api.py -q -p no:langsmith
"""
from __future__ import annotations

import base64
import contextlib
import json
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
import orpath_watch  # noqa: E402
from orpath.agents.callbacks import (  # noqa: E402
    MultiAgentSnapshotCallback,
    SUPERVISOR_NAME,
)

pytestmark = pytest.mark.filterwarnings(
    "ignore:create_react_agent has been moved",
    "ignore:No supported",
)

#: Expected OR-Tools TSP objective for the 8-station fixture (Numbers Truth).
EXPECTED_OBJECTIVE = 154


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
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


@contextlib.contextmanager
def _serve(workdir: Path):
    """Start the Live Watch HTTP server in-process against ``workdir``."""
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
    """Folder drag-and-drop import of an 8-station TSP with coords.json."""
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
    assert code == 200 and res.get("ok"), f"folder import failed: {res}"


def _confirm(base: str, slug: str) -> tuple[int, dict[str, Any]]:
    return _post_json(
        base + "/api/studio/confirm",
        {
            "slug": slug,
            "selected_options": {"q_algorithm": "ortools"},
            "extra_prompt": "",
        },
    )


# --------------------------------------------------------------------------- #
# 1. Static wiring — orpath_watch.py studio confirm multi-agent seam
# --------------------------------------------------------------------------- #
def test_watch_source_wires_multiagent_engine_and_callback() -> None:
    """``/api/studio/confirm`` must import + mount the multi-agent engine seam."""
    src = (SCRIPTS / "orpath_watch.py").read_text(encoding="utf-8")

    # MultiAgentSnapshotCallback import from orpath.agents.callbacks
    assert "from orpath.agents.callbacks import" in src
    assert "MultiAgentSnapshotCallback" in src

    # build_compiled_multiagent import from orpath.control_plane
    assert "build_compiled_multiagent" in src

    # ORPATH_ENGINE env switch with multiagent-or-unspecified default
    assert "ORPATH_ENGINE" in src

    # Callback mounted with the canonical (thread_id, slug, workdir) contract
    assert "thread_id=slug, slug=slug, workdir=self._workdir" in src

    # Smooth fallback to the existing build_graph solve
    assert "build_graph(checkpointer=saver)" in src


def test_callback_mount_contract(tmp_path: Path) -> None:
    """The callback mount contract writes stage snapshots under the workdir."""
    cb = MultiAgentSnapshotCallback(thread_id="t-9", slug="s-9", workdir=tmp_path)
    assert cb.thread_id == "t-9"
    assert cb.slug == "s-9"
    assert cb.workdir == tmp_path

    snap = cb.write_stage_snapshot(SUPERVISOR_NAME, status="running")
    assert snap.is_file()
    doc = json.loads(snap.read_text(encoding="utf-8"))
    assert doc["node"] == SUPERVISOR_NAME
    assert doc["thread_id"] == "t-9"
    assert doc["slug"] == "s-9"

    # Per-slug agent log receives the stage line
    log = tmp_path / "outputs" / ".agents" / "s-9" / "s-9.log"
    assert log.is_file()
    assert "stage" in log.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# 2. Studio confirm instantiates the multiagent engine + callback (spy)
# --------------------------------------------------------------------------- #
def test_studio_confirm_instantiates_multiagent_engine_and_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Confirm instantiates build_compiled_multiagent; on failure it falls back
    to build_graph and still produces the canonical solution/validate artifacts."""
    calls: list[Any] = []

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        raise RuntimeError("simulated offline multiagent failure")

    monkeypatch.setattr(control_plane, "build_compiled_multiagent", _spy)

    slug = "ma-tsp-spy"
    with _serve(tmp_path) as base:
        _import_tsp_folder(base, slug)
        code, res = _confirm(base, slug)

    assert code == 200 and res.get("ok"), f"confirm failed: {res}"
    # The multiagent engine was instantiated (build_compiled_multiagent called)
    assert len(calls) >= 1, "studio confirm did not instantiate the multiagent engine"
    # Smooth fallback kept the deterministic engine serving the run
    assert res.get("status") == "COMPLETED"
    assert res.get("engine") == "graph"

    # Canonical artifacts produced by the fallback solve
    sol_file = tmp_path / "outputs" / f"{slug}-solution.json"
    val_file = tmp_path / "outputs" / f"{slug}-validate.json"
    assert sol_file.is_file(), "solution.json was not produced"
    assert val_file.is_file(), "validate.json was not produced"
    sol_doc = json.loads(sol_file.read_text(encoding="utf-8"))
    assert sol_doc.get("objective") == EXPECTED_OBJECTIVE
    val_doc = json.loads(val_file.read_text(encoding="utf-8"))
    assert val_doc.get("ok") is True

    # Interface recognises the result
    assert (res.get("solution") or {}).get("objective") == EXPECTED_OBJECTIVE
    assert (res.get("validation") or {}).get("ok") is True
    assert (res.get("plain_language_summary") or {}).get("headline")

    # Callback was mounted and wrote snapshots during the solve flow
    log = tmp_path / "outputs" / ".agents" / slug / f"{slug}.log"
    assert log.is_file(), "MultiAgentSnapshotCallback did not write its agent log"
    assert "stage" in log.read_text(encoding="utf-8")
    supervisor_stages = list((tmp_path / "runs" / slug / "stages").glob("*_supervisor.json"))
    assert supervisor_stages, "no supervisor stage snapshot written by the callback"


# --------------------------------------------------------------------------- #
# 3. Multiagent mode (ORPATH_ENGINE=multiagent / unspecified) end-to-end
# --------------------------------------------------------------------------- #
def test_studio_confirm_multiagent_mode_produces_solution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With ORPATH_ENGINE=multiagent the endpoint still produces + recognises
    solution.json / validate.json (real engine attempt, fallback on offline)."""
    monkeypatch.setenv("ORPATH_ENGINE", "multiagent")

    slug = "ma-tsp-multiagent"
    with _serve(tmp_path) as base:
        _import_tsp_folder(base, slug)
        code, res = _confirm(base, slug)

    assert code == 200 and res.get("ok"), f"confirm failed: {res}"
    assert res.get("status") == "COMPLETED"
    # The multiagent engine is preferred; offline/CI regressions fall back.
    assert res.get("engine") in ("multiagent", "graph")

    sol_file = tmp_path / "outputs" / f"{slug}-solution.json"
    val_file = tmp_path / "outputs" / f"{slug}-validate.json"
    assert sol_file.is_file(), "solution.json was not produced"
    assert val_file.is_file(), "validate.json was not produced"
    sol_doc = json.loads(sol_file.read_text(encoding="utf-8"))
    assert sol_doc.get("objective") == EXPECTED_OBJECTIVE
    val_doc = json.loads(val_file.read_text(encoding="utf-8"))
    assert val_doc.get("ok") is True

    # Interface recognises the result
    assert (res.get("solution") or {}).get("objective") == EXPECTED_OBJECTIVE
    assert (res.get("validation") or {}).get("ok") is True

    # Callback snapshots written during the solve flow
    log = tmp_path / "outputs" / ".agents" / slug / f"{slug}.log"
    assert log.is_file(), "MultiAgentSnapshotCallback did not write its agent log"
    assert "stage" in log.read_text(encoding="utf-8")
    assert list((tmp_path / "runs" / slug / "stages").glob("*_supervisor.json"))


# --------------------------------------------------------------------------- #
# 4. ORPATH_ENGINE=graph skips the multiagent path
# --------------------------------------------------------------------------- #
def test_studio_confirm_engine_graph_skips_multiagent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ORPATH_ENGINE=graph solves deterministically without touching the engine."""
    monkeypatch.setenv("ORPATH_ENGINE", "graph")
    calls: list[Any] = []

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        raise AssertionError("build_compiled_multiagent must not be called for ORPATH_ENGINE=graph")

    monkeypatch.setattr(control_plane, "build_compiled_multiagent", _spy)

    slug = "ma-tsp-graph"
    with _serve(tmp_path) as base:
        _import_tsp_folder(base, slug)
        code, res = _confirm(base, slug)

    assert code == 200 and res.get("ok"), f"confirm failed: {res}"
    assert res.get("status") == "COMPLETED"
    assert res.get("engine") == "graph"
    assert calls == [], "multiagent engine was instantiated despite ORPATH_ENGINE=graph"

    sol_file = tmp_path / "outputs" / f"{slug}-solution.json"
    val_file = tmp_path / "outputs" / f"{slug}-validate.json"
    assert sol_file.is_file() and val_file.is_file()
    sol_doc = json.loads(sol_file.read_text(encoding="utf-8"))
    assert sol_doc.get("objective") == EXPECTED_OBJECTIVE


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:langsmith"]))
