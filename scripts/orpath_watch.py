#!/usr/bin/env python3
"""OR-Path Live Watch HTTP face (V0 Tier-1 + P1 poll + model pref).

  GET  /                         → orpath/web/watch.html
  GET  /studio                   → orpath/web/studio.html
  GET  /api/health
  GET  /api/poll
  GET  /api/snapshot
  GET  /api/stream
  GET  /api/model                → current Pi model + presets
  POST /api/model                → {provider, model} set preference
  GET  /api/steer?slug=          → load notes/<slug>-human-steer.json
  POST /api/steer                → write human steer (lg/pi split; no objective)

Bind 127.0.0.1 only.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orpath.human_steer import (  # noqa: E402
    ALLOWED_SOLVE_MODES,
    build_steer_cta,
    find_forbidden_keys,
    load_human_steer,
    normalize_steer_payload,
    save_human_steer,
    steer_path,
)
from orpath.paths import orpath_home, orpath_workdir  # noqa: E402
from orpath.watch_snapshot import (  # noqa: E402
    build_problem_view,
    build_snapshot,
    compute_source_fingerprint,
)

WEB_DIR = ROOT / "orpath" / "web"
HTML_NAME = "watch.html"
STUDIO_HTML_NAME = "studio.html"
DEFAULT_PORT = 8765
MAX_PORT_TRIES = 20
SSE_INTERVAL_S = 0.5

def _load_problem_presets() -> list[dict[str, Any]]:
    """Load golden problem presets from fixtures/intake/presets.json."""
    preset_path = ROOT / "fixtures" / "intake" / "presets.json"
    if not preset_path.is_file():
        return []
    try:
        data = json.loads(preset_path.read_text(encoding="utf-8"))
        return list(data) if isinstance(data, list) else []
    except Exception:
        return []


PROBLEM_PRESETS: list[dict[str, Any]] = _load_problem_presets()


def _pick_python(home: Path) -> str:
    for rel in (
        ".venv/Scripts/python.exe",
        ".venv/bin/python",
        ".venv-314/Scripts/python.exe",
        ".venv-314/bin/python",
    ):
        cand = home / rel
        if cand.is_file():
            return str(cand)
    return sys.executable


def _sanitize_slug(raw: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", (raw or "").strip()).strip("-")
    return s[:48] or "case-1"


def _guess_domain_info(filename_or_text: str) -> dict[str, Any]:
    """Return soft class hints only for custom text/upload.

    Per specs/problem-intake.md §2.3 & specs/architecture.md §7 #11:
    NEVER invent or bind a golden fixture problem_id (shortest_path, b-tube-cut, etc.)
    from free-form text or uploaded files.
    """
    from orpath.studio_domain_catalog import detect_problem_class_from_text

    detected = detect_problem_class_from_text(filename_or_text or "")
    if detected == "unregistered":
        low = (filename_or_text or "").lower()
        if any(k in low for k in ("电网", "调控", "smart_grid")):
            detected = "microgrid_dispatch"
    hint_class = "unknown" if detected == "unregistered" else detected
    return {
        "domain": "unregistered",
        "problem_id": "",
        "problem_class": "unknown",
        "problem_class_hint": hint_class,
        "solve_mode": "none",
        "can_solve": False,
    }


IN_MEMORY_BENCHMARKS = {
    "ww12",
    "clsp60",
    "max_cut",
    "qubo",
    "ising",
    "number_partitioning",
    "min_cost_flow",
    "bipartite_matching",
    "multi_commodity_flow",
    "max_sharpe",
    "min_volatility",
    "portfolio_default",
    "portfolio_3asset",
    "rostering_toy",
    "shift_sched",
    "binpack_1d",
    "binpack_2d",
    "binpack_3d",
    "farmer_problem",
    "farmer",
    "microgrid_campus",
    "campus_microgrid",
}


def _has_runnable_fixture(home: Path, workdir: Path, problem_id: str, norm_class: str) -> bool:
    """True only if problem_id corresponds to a real fixture/case dataset on disk or recognized in-memory benchmark."""
    pid = (problem_id or "").strip()
    if not pid:
        return False
    if pid in IN_MEMORY_BENCHMARKS:
        return True
    if norm_class == "tube_cut" and pid in {"b-tube-cut", "tube_cut_b2026"}:
        return (home / "fixtures" / "t3" / "tube_cut_b2026").is_dir()
    pid_low = pid.lower()
    for base in (workdir, home):
        for tier in ("t3", "t2", "t1"):
            if (base / "fixtures" / tier / pid).is_dir():
                return True
        bm = base / "fixtures" / "benchmarks"
        if bm.is_dir():
            for p in bm.rglob("*"):
                if p.stem.lower() == pid_low or p.name.lower() == pid_low:
                    return True
    return False


_MODEL_PRESETS: list[dict[str, str]] = [
    {"provider": "xfyun", "model": "spark-x2.6", "label": "讯飞星火 · spark-x2.6"},
    {"provider": "deepseek", "model": "deepseek-reasoner", "label": "DeepSeek · deepseek-reasoner (R1)"},
    {"provider": "deepseek", "model": "deepseek-chat", "label": "DeepSeek · deepseek-chat (V3)"},
    {"provider": "deepseek", "model": "deepseek-v4-flash", "label": "DeepSeek · deepseek-v4-flash"},
]


def _get_model_pref(home: Path, workdir: Path | None = None) -> dict[str, Any]:
    pref_dir = (workdir or home) / "outputs"
    pref_path = pref_dir / ".model_pref.json"
    provider = "xfyun"
    model = os.environ.get("XFYUN_MODEL", "").strip() or "spark-x2.6"
    if pref_path.is_file():
        try:
            data = json.loads(pref_path.read_text(encoding="utf-8", errors="replace"))
            provider = str(data.get("provider") or provider).strip()
            model = str(data.get("model") or model).strip()
        except Exception:  # noqa: BLE001
            pass
    return {
        "provider": provider,
        "model": model,
        "presets": list(_MODEL_PRESETS),
        "settings_path": str(pref_path),
    }


def _set_model_pref(*, provider: str, model: str, home: Path, workdir: Path | None = None) -> dict[str, Any]:
    pref_dir = (workdir or home) / "outputs"
    pref_dir.mkdir(parents=True, exist_ok=True)
    pref_path = pref_dir / ".model_pref.json"
    payload = {
        "provider": (provider or "xfyun").strip(),
        "model": model.strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    pref_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return _get_model_pref(home=home, workdir=workdir)



def _discover_workdir_cases(workdir: Path, home: Path) -> list[dict[str, Any]]:
    slugs: set[str] = set()
    runs_dir = workdir / "runs"
    if runs_dir.is_dir():
        for d in runs_dir.iterdir():
            if d.is_dir() and not d.name.startswith("__"):
                slugs.add(d.name)
    out_dir = workdir / "outputs"
    if out_dir.is_dir():
        for p in out_dir.glob("*-intake.json"):
            slugs.add(p.name[: -len("-intake.json")])
        for p in out_dir.glob("*-solution.json"):
            slugs.add(p.name[: -len("-solution.json")])

    cases: list[dict[str, Any]] = []
    for s in sorted(slugs):
        pv = build_problem_view(workdir=workdir, home=home, slug=s)
        stages_dir = workdir / "runs" / s / "stages"
        st_count = len(list(stages_dir.glob("*.json"))) if stages_dir.is_dir() else 0
        sol = pv.get("solution_summary") or {}
        val = pv.get("validate_summary") or {}
        cases.append({
            "slug": s,
            "title": pv.get("title") or s,
            "problem_id": pv.get("problem_id") or "",
            "problem_class": pv.get("problem_class") or "",
            "has_intake": bool(pv.get("has_intake")),
            "has_problem": bool(pv.get("has_problem")),
            "has_solution": bool(sol.get("exists")),
            "solution_status": sol.get("status"),
            "objective": sol.get("objective"),
            "validate_ok": val.get("ok") if val.get("exists") else None,
            "stages_count": st_count,
            "subproblems_count": len(pv.get("subproblems") or []),
        })
    return cases


class WatchHandler(SimpleHTTPRequestHandler):
    server_version = "ORPathWatch/1.1.0"

    def __init__(self, *args, home: Path, workdir: Path, **kwargs):
        self._home = home
        self._workdir = workdir
        super().__init__(*args, **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[watch] " + (fmt % args) + "\n")

    def _send_json(self, code: int, obj: object) -> None:
        raw = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(raw)

    def _send_html_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404, f"missing {path.name}")
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _qs_slug_thread(self, qs: dict) -> tuple[str, str]:
        raw_slug = (qs.get("slug") or ["test"])[0].strip() or "test"
        raw_thread = (qs.get("thread") or qs.get("thread_id") or [raw_slug])[0].strip() or raw_slug
        slug = _sanitize_slug(raw_slug)
        thread = _sanitize_slug(raw_thread)
        return slug, thread

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid json"})
            return
        if not isinstance(body, dict):
            self._send_json(400, {"ok": False, "error": "body must be object"})
            return

        if path == "/api/steer":
            slug = str(body.get("slug") or "").strip()
            if not slug:
                qs = parse_qs(parsed.query or "")
                slug = (qs.get("slug") or ["test"])[0].strip() or "test"
            doc, errs = normalize_steer_payload(
                body, slug=slug, source=str(body.get("source") or "watch_form")
            )
            if errs or doc is None:
                self._send_json(400, {"ok": False, "errors": errs or ["invalid steer"]})
                return
            try:
                path_out = save_human_steer(self._workdir, slug, doc)
                ctas = build_steer_cta(doc, workdir=self._workdir)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "path": str(path_out),
                        "steer": doc,
                        "next_actions": ctas,
                        "note": "manual CTA only — browser never auto-resume",
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/intake/import":
            self._handle_intake_import(body)
            return

        if path == "/api/intake/run":
            self._handle_intake_run(body)
            return

        if path == "/api/studio/analyze":
            self._handle_studio_analyze(body)
            return

        if path == "/api/studio/confirm":
            self._handle_studio_confirm(body)
            return

        if path == "/api/studio/paper":
            self._handle_studio_paper(body)
            return

        if path != "/api/model":
            self.send_error(404, "not found")
            return
        provider = str(body.get("provider") or "").strip()
        model = str(body.get("model") or "").strip()
        if not model:
            self._send_json(400, {"ok": False, "error": "model required"})
            return
        try:
            info = _set_model_pref(
                provider=provider or "xfyun",
                model=model,
                home=self._home,
                workdir=self._workdir,
            )
            info["ok"] = True
            self._send_json(200, info)
        except Exception as exc:  # noqa: BLE001
            self._send_json(400, {"ok": False, "error": str(exc)})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        qs = parse_qs(parsed.query or "")

        if path == "/api/health":
            try:
                m = _get_model_pref(home=self._home, workdir=self._workdir)
            except Exception:  # noqa: BLE001
                m = {}
            self._send_json(
                200,
                {
                    "ok": True,
                    "root": str(self._home),
                    "workdir": str(self._workdir),
                    "html": str(WEB_DIR / HTML_NAME),
                    "html_exists": (WEB_DIR / HTML_NAME).is_file(),
                    "p1": True,
                    "model": m,
                    "endpoints": [
                        "/api/health",
                        "/api/poll",
                        "/api/snapshot",
                        "/api/stream",
                        "/api/model",
                        "/api/steer",
                        "/api/problems",
                        "/api/artifact",
                        "/api/intake/import",
                        "/api/intake/run",
                        "/api/studio/analyze",
                        "/api/studio/confirm",
                        "/api/studio/paper",
                        "/api/knowledge/search",
                        "/api/artifact/download",
                    ],
                    "dialogue": True,
                    "problem_workbench": True,
                },
            )
            return

        if path == "/api/problems":
            try:
                cases = _discover_workdir_cases(self._workdir, self._home)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "presets": PROBLEM_PRESETS,
                        "cases": cases,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/knowledge/search":
            self._handle_knowledge_search(qs)
            return

        if path == "/api/artifact":
            slug, _thread = self._qs_slug_thread(qs)
            kind = (qs.get("kind") or ["brief"])[0].strip().lower()
            self._handle_artifact_get(slug, kind)
            return

        if path == "/api/artifact/download":
            slug, _thread = self._qs_slug_thread(qs)
            kind = (qs.get("kind") or ["solution"])[0].strip().lower()
            self._handle_artifact_download(slug, kind)
            return

        if path == "/api/steer":
            slug, _thread = self._qs_slug_thread(qs)
            doc = load_human_steer(self._workdir, slug)
            self._send_json(
                200,
                {
                    "ok": True,
                    "slug": slug,
                    "exists": doc is not None,
                    "path": str(steer_path(self._workdir, slug)),
                    "steer": doc,
                    "next_actions": build_steer_cta(doc, workdir=self._workdir)
                    if doc
                    else [],
                },
            )
            return

        if path == "/api/model":
            try:
                info = _get_model_pref(home=self._home, workdir=self._workdir)
                info["ok"] = True
                self._send_json(200, info)
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/poll":
            slug, thread = self._qs_slug_thread(qs)
            try:
                info = compute_source_fingerprint(
                    slug=slug, thread_id=thread, workdir=self._workdir
                )
                prev = (qs.get("prev_fp") or qs.get("prev_fingerprint") or [None])[0]
                info["dirty"] = True if not prev else (prev != info.get("fingerprint"))
                self._send_json(200, info)
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/snapshot":
            slug, thread = self._qs_slug_thread(qs)
            prev_fp = (qs.get("prev_fp") or qs.get("prev_fingerprint") or [None])[0]
            prev_ev_raw = (qs.get("prev_events") or [None])[0]
            prev_events = None
            if prev_ev_raw is not None and str(prev_ev_raw).strip() != "":
                try:
                    prev_events = int(prev_ev_raw)
                except ValueError:
                    prev_events = None
            try:
                snap = build_snapshot(
                    slug=slug,
                    thread_id=thread,
                    root=self._home,
                    workdir=self._workdir,
                    prev_fingerprint=prev_fp,
                    prev_events_count=prev_events,
                )
                try:
                    snap["pi_model"] = _get_model_pref(home=self._home, workdir=self._workdir)
                except Exception:  # noqa: BLE001
                    pass
                self._send_json(200, snap)
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/stream":
            slug, thread = self._qs_slug_thread(qs)
            self._sse_loop(slug, thread)
            return

        if path in {"/", "/index.html", "/watch.html"}:
            try:
                sys.path.insert(0, str(ROOT))
                from orpath.web.build import build
                build()
            except Exception:
                pass
            self._send_html_file(WEB_DIR / HTML_NAME)
            return

        if path in {"/studio", "/studio.html"}:
            try:
                sys.path.insert(0, str(ROOT))
                from orpath.web.build import build
                build()
            except Exception:
                pass
            self._send_html_file(WEB_DIR / STUDIO_HTML_NAME)
            return

        if path.startswith("/static/") or path.startswith("/src/"):
            rel_sub = path.split("/", 2)[-1]
            cand = (WEB_DIR / "src" / rel_sub).resolve()
            src_root = (WEB_DIR / "src").resolve()
            if cand.is_file() and str(cand).startswith(str(src_root)):
                ext = cand.suffix.lower()
                ctype = "text/plain"
                if ext == ".css":
                    ctype = "text/css; charset=utf-8"
                elif ext == ".js":
                    ctype = "text/javascript; charset=utf-8"
                elif ext in {".html", ".htm"}:
                    ctype = "text/html; charset=utf-8"
                elif ext == ".json":
                    ctype = "application/json; charset=utf-8"
                elif ext == ".svg":
                    ctype = "image/svg+xml"
                data = cand.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

        self.send_error(404, "not found")

    def _handle_knowledge_search(self, qs: dict) -> None:
        raw_q = (qs.get("q") or qs.get("query") or [""])[0].strip()
        raw_cls = (qs.get("problem_class") or qs.get("class") or [""])[0].strip()
        try:
            topk = max(1, min(15, int((qs.get("topk") or ["6"])[0])))
        except ValueError:
            topk = 6

        q_eff = raw_q or raw_cls.replace("_", " ") or "operations research mathematical programming"
        hits_out: list[dict[str, Any]] = []
        lit_out: list[dict[str, Any]] = []
        skills_out: list[dict[str, str]] = []
        try:
            from knowledge_svc.retrieve import artifact_to_payload, retrieve as ks_retrieve

            art = ks_retrieve(
                q_eff,
                mode="hybrid",
                topk=topk,
                root=self._home,
                problem_class=raw_cls if raw_cls and raw_cls != "unregistered" else None,
            )
            pay = artifact_to_payload(art)
            for h in pay.get("hits") or []:
                sp = str(h.get("source_path") or "")
                hits_out.append({
                    "chunk_id": str(h.get("chunk_id") or ""),
                    "title": Path(sp).stem if sp else str(h.get("chunk_id") or ""),
                    "source_path": sp,
                    "backend": str(h.get("backend") or "hybrid"),
                    "score": round(float(h.get("score") or 0.0), 4),
                    "snippet": str(h.get("snippet") or "")[:240],
                })
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "error": f"knowledge search failed: {exc}"})
            return

        try:
            from orpath.agents.knowledge_pack import extract_skill_highlights, match_top_literature

            lit_out = match_top_literature(
                problem_class=raw_cls,
                query=q_eff,
                topk=min(topk, 4),
                home=self._home,
            )
            sk_raw, _chk, _modes = extract_skill_highlights(problem_class=raw_cls, home=self._home)
            skills_out = [{"id": s["id"], "path": s["path"], "excerpt": s["excerpt"][:180]} for s in sk_raw[:4]]
        except Exception:
            pass

        self._send_json(
            200,
            {
                "ok": True,
                "query": q_eff,
                "problem_class": raw_cls,
                "hits": hits_out,
                "literature": lit_out,
                "skills": skills_out,
            },
        )

    def _handle_artifact_get(self, slug: str, kind: str) -> None:
        wd = self._workdir.resolve()
        mapping: dict[str, tuple[Path, str]] = {
            "brief": (wd / "notes" / f"{slug}-problem-brief.md", "markdown"),
            "ocr_raw": (wd / "notes" / f"{slug}-ocr.raw.md", "markdown"),
            "intake": (wd / "outputs" / f"{slug}-intake.json", "json"),
            "schema": (wd / "outputs" / f"{slug}-schema.json", "json"),
            "solution": (wd / "outputs" / f"{slug}-solution.json", "json"),
            "validate": (wd / "outputs" / f"{slug}-validate.json", "json"),
            "paper": (wd / "papers" / f"{slug}.md", "markdown"),
            "explain": (wd / "notes" / f"{slug}-explain.md", "markdown"),
            "research": (wd / "notes" / f"{slug}-research.md", "markdown"),
            "provenance": (wd / "outputs" / f"{slug}.provenance.md", "markdown"),
            "plan": (wd / "outputs" / ".plans" / f"{slug}.md", "markdown"),
            "analysis": (wd / "outputs" / f"{slug}-studio-analysis.json", "json"),
            "profile": (wd / "outputs" / f"{slug}-data-profile.json", "json"),
            "knowledge_pack": (wd / "notes" / f"{slug}-knowledge-pack.md", "markdown"),
            "remediation": (wd / "notes" / f"{slug}-remediation.md", "markdown"),
        }
        if kind not in mapping:
            self._send_json(400, {"ok": False, "error": f"unknown artifact kind: {kind}"})
            return
        target, fmt = mapping[kind]
        target = target.resolve()
        if not target.is_relative_to(wd):
            self._send_json(403, {"ok": False, "error": "forbidden path traversal"})
            return
        if not target.is_file():
            self._send_json(404, {"ok": False, "error": f"artifact not found: {target.name}"})
            return
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
            self._send_json(
                200,
                {
                    "ok": True,
                    "slug": slug,
                    "kind": kind,
                    "format": fmt,
                    "path": str(target),
                    "content": text[:120000],
                },
            )
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "error": str(exc)})

    def _handle_artifact_download(self, slug: str, kind: str) -> None:
        wd = self._workdir.resolve()
        mapping: dict[str, tuple[Path, str]] = {
            "brief": (wd / "notes" / f"{slug}-problem-brief.md", "text/markdown"),
            "ocr_raw": (wd / "notes" / f"{slug}-ocr.raw.md", "text/markdown"),
            "intake": (wd / "outputs" / f"{slug}-intake.json", "application/json"),
            "schema": (wd / "outputs" / f"{slug}-schema.json", "application/json"),
            "solution": (wd / "outputs" / f"{slug}-solution.json", "application/json"),
            "validate": (wd / "outputs" / f"{slug}-validate.json", "application/json"),
            "paper": (wd / "papers" / f"{slug}.md", "text/markdown"),
            "explain": (wd / "notes" / f"{slug}-explain.md", "text/markdown"),
            "research": (wd / "notes" / f"{slug}-research.md", "text/markdown"),
            "provenance": (wd / "outputs" / f"{slug}.provenance.md", "text/markdown"),
            "plan": (wd / "outputs" / ".plans" / f"{slug}.md", "text/markdown"),
            "analysis": (wd / "outputs" / f"{slug}-studio-analysis.json", "application/json"),
            "profile": (wd / "outputs" / f"{slug}-data-profile.json", "application/json"),
        }
        if kind not in mapping:
            self._send_json(400, {"ok": False, "error": f"unknown artifact kind: {kind}"})
            return
        target, mime = mapping[kind]
        target = target.resolve()
        if not target.is_relative_to(wd):
            self._send_json(403, {"ok": False, "error": "forbidden path traversal"})
            return
        if not target.is_file():
            self._send_json(404, {"ok": False, "error": f"artifact not found: {target.name}"})
            return
        try:
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "error": str(exc)})

    def _handle_intake_import(self, body: dict[str, Any]) -> None:
        from orpath.intake_nodes import standalone_intake

        mode = str(body.get("mode") or "preset").strip().lower()
        wd = self._workdir
        home = self._home

        try:
            if mode == "preset":
                preset_id = str(body.get("preset_id") or "").strip()
                preset = next((p for p in PROBLEM_PRESETS if p["id"] == preset_id), None)
                if not preset:
                    self._send_json(400, {"ok": False, "error": f"unknown preset_id: {preset_id}"})
                    return
                slug = _sanitize_slug(str(body.get("slug") or preset["slug"]))
                seed_slug = preset.get("seed_slug")
                if seed_slug and slug == seed_slug:
                    from scripts.install_demo_seed import install_seeds

                    install_seeds(home / "demo" / "seed", wd, slugs=(seed_slug,), force=False)
                    self._send_json(
                        200,
                        {
                            "ok": True,
                            "mode": "seed",
                            "slug": slug,
                            "thread_id": slug,
                            "preset": preset,
                        },
                    )
                    return

                src_rel = str(preset.get("source_rel") or "")
                src_path = (home / src_rel).resolve()
                if not src_path.is_file():
                    self._send_json(404, {"ok": False, "error": f"preset source missing: {src_rel}"})
                    return
                res = standalone_intake(root=wd, slug=slug, sources=[src_path])
                intake_json_path = wd / "outputs" / f"{slug}-intake.json"
                if intake_json_path.is_file():
                    try:
                        idoc = json.loads(intake_json_path.read_text(encoding="utf-8"))
                        if isinstance(idoc, dict):
                            if preset.get("can_solve") and preset.get("problem_id"):
                                idoc["problem_id_hint"] = preset["problem_id"]
                                idoc["problem_class_hint"] = preset["problem_class"]
                            else:
                                idoc["problem_id_hint"] = None
                                idoc["problem_class_hint"] = None
                            intake_json_path.write_text(
                                json.dumps(idoc, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8",
                            )
                    except (OSError, json.JSONDecodeError):
                        pass
                pv = build_problem_view(workdir=wd, home=home, slug=slug)
                pv["domain"] = preset.get("problem_class") if preset.get("can_solve") else "unregistered"
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "mode": "preset",
                        "slug": slug,
                        "thread_id": slug,
                        "preset": preset,
                        "intake": res,
                        "problem_view": pv,
                    },
                )
                return

            if mode == "upload":
                file_name = str(body.get("file_name") or "problem.txt").strip()
                safe_name = re.sub(r"[^a-zA-Z0-9._\-\u4e00-\u9fa5]+", "_", Path(file_name).name) or "problem.txt"
                slug = _sanitize_slug(str(body.get("slug") or Path(safe_name).stem or "case-upload"))
                b64 = str(body.get("file_base64") or "").strip()
                if "," in b64 and b64.startswith("data:"):
                    b64 = b64.split(",", 1)[1]
                if not b64:
                    self._send_json(400, {"ok": False, "error": "file_base64 required"})
                    return
                raw_bytes = base64.b64decode(b64)
                inbox_dir = wd / "inbox" / slug
                inbox_dir.mkdir(parents=True, exist_ok=True)
                dest_path = inbox_dir / safe_name
                dest_path.write_bytes(raw_bytes)

                res = standalone_intake(root=wd, slug=slug, sources=[dest_path])
                brief_txt = ""
                if res.get("brief_path") and Path(res["brief_path"]).is_file():
                    brief_txt = Path(res["brief_path"]).read_text(encoding="utf-8", errors="replace")[:4000]
                dom = _guess_domain_info(file_name + "\n" + brief_txt)
                pv = build_problem_view(workdir=wd, home=home, slug=slug)
                pv["domain"] = dom["domain"]
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "mode": "upload",
                        "slug": slug,
                        "thread_id": slug,
                        "saved_path": str(dest_path),
                        "domain_guess": dom,
                        "intake": res,
                        "problem_view": pv,
                    },
                )
                return

            if mode == "text":
                raw_text = str(body.get("raw_text") or "").strip()
                title = str(body.get("title") or "").strip()
                if not raw_text:
                    self._send_json(400, {"ok": False, "error": "题面文本不能为空"})
                    return
                slug = _sanitize_slug(str(body.get("slug") or "case-custom"))
                inbox_dir = wd / "inbox" / slug
                inbox_dir.mkdir(parents=True, exist_ok=True)
                dest_path = inbox_dir / "problem-statement.md"
                full_md = (f"# {title}\n\n{raw_text}\n" if title and not raw_text.startswith("#") else f"{raw_text}\n")
                dest_path.write_text(full_md, encoding="utf-8")

                res = standalone_intake(root=wd, slug=slug, sources=[dest_path])
                dom = _guess_domain_info(title + "\n" + raw_text)
                pv = build_problem_view(workdir=wd, home=home, slug=slug)
                pv["domain"] = dom["domain"]
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "mode": "text",
                        "slug": slug,
                        "thread_id": slug,
                        "saved_path": str(dest_path),
                        "domain_guess": dom,
                        "intake": res,
                        "problem_view": pv,
                    },
                )
                return

            if mode == "folder":
                raw_files = body.get("files")
                if not isinstance(raw_files, list) or not raw_files:
                    self._send_json(400, {"ok": False, "error": "files list required for folder mode"})
                    return
                # Server-side defense budget against disk/memory flooding (aligns with Studio)
                max_folder_files = 200
                max_single_file_bytes = 10 * 1024 * 1024  # 10MB
                max_total_bytes = 25 * 1024 * 1024        # 25MB
                if len(raw_files) > max_folder_files:
                    self._send_json(400, {"ok": False, "error": f"too many files: max {max_folder_files} allowed, got {len(raw_files)}"})
                    return

                slug = _sanitize_slug(str(body.get("slug") or "case-folder"))
                inbox_dir = wd / "inbox" / slug
                inbox_dir.mkdir(parents=True, exist_ok=True)

                saved_files: list[Path] = []
                total_bytes = 0
                for f in raw_files:
                    if not isinstance(f, dict):
                        continue
                    rel = str(f.get("rel_path") or f.get("name") or "").strip().replace("\\", "/")
                    if not rel or rel.startswith("/") or rel.startswith("../") or "/../" in f"/{rel}/":
                        self._send_json(400, {"ok": False, "error": f"invalid rel_path: {rel}"})
                        return
                    b64 = str(f.get("content_base64") or f.get("file_base64") or "").strip()
                    if "," in b64 and b64.startswith("data:"):
                        b64 = b64.split(",", 1)[1]
                    raw_bytes = base64.b64decode(b64) if b64 else b""
                    if len(raw_bytes) > max_single_file_bytes:
                        self._send_json(400, {"ok": False, "error": f"file exceeds 10MB limit: {rel}"})
                        return
                    total_bytes += len(raw_bytes)
                    if total_bytes > max_total_bytes:
                        self._send_json(400, {"ok": False, "error": "total folder size exceeds 25MB limit"})
                        return
                    dest_p = inbox_dir / rel
                    dest_p.parent.mkdir(parents=True, exist_ok=True)
                    dest_p.write_bytes(raw_bytes)
                    saved_files.append(dest_p)

                from orpath.studio_analyzer import profile_inbox_assets
                dp = profile_inbox_assets(inbox_dir, slug, wd / "outputs")

                stmt_sources = [
                    inbox_dir / st for st in dp.get("statement_files", []) if (inbox_dir / st).is_file()
                ]
                if stmt_sources:
                    res = standalone_intake(root=wd, slug=slug, sources=stmt_sources, assets_dir=inbox_dir)
                else:
                    res = {
                        "ok": True,
                        "status": "data_only",
                        "note": "未上传文字/文档题面，已跳过文本 OCR，仅保留结构化数据探针。",
                        "subproblems": 0,
                    }
                pv = build_problem_view(workdir=wd, home=home, slug=slug)
                pv["data_profile"] = dp
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "mode": "folder",
                        "slug": slug,
                        "thread_id": slug,
                        "files_count": len(saved_files),
                        "data_profile": dp,
                        "intake": res,
                        "problem_view": pv,
                    },
                )
                return

            self._send_json(400, {"ok": False, "error": f"unsupported import mode: {mode}"})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "error": str(exc)})

    def _handle_intake_run(self, body: dict[str, Any]) -> None:
        slug = _sanitize_slug(str(body.get("slug") or "case-run"))
        thread = _sanitize_slug(str(body.get("thread_id") or slug))
        wd = self._workdir
        home = self._home

        pv = build_problem_view(workdir=wd, home=home, slug=slug)
        raw_pid = str(body.get("problem_id") or pv.get("problem_id") or "").strip()
        raw_pclass = str(body.get("problem_class") or pv.get("problem_class") or "").strip()
        solve_mode = str(body.get("solve_mode") or "").strip()
        live = bool(body.get("live", False))

        from orpath.domain_registry import is_registered_solve_class, normalize_problem_class

        norm_class = normalize_problem_class(raw_pclass)
        has_fixture = _has_runnable_fixture(home, wd, raw_pid, norm_class)
        # Strict honesty contract: never bind custom/unregistered/intake-only problems to a golden fixture!
        if (
            not norm_class
            or norm_class in {"unknown", "unregistered", "intake_only"}
            or not is_registered_solve_class(norm_class)
            or not raw_pid
            or not has_fixture
        ):
            err_msg = (
                f"题目 '{slug}' (class={raw_pclass or '未注册'}, problem_id={raw_pid or '无算例绑定'}) "
                "尚无对应的结构化求解算例或领域求解适配器（当前已注册工业算例域：tube_cut, polyomino_cover, vrp, tsp, shortest_path）。"
                "根据系统硬法（specs/product-scope.md §4 与 specs/problem-intake.md §2.3），严禁对自定义题面或未注册域假绑内置金标（如 shortest_path=42），已诚实拦截并标记为 BLOCKED。"
            )
            out_dir = wd / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            blocked_sol = {
                "status": "BLOCKED",
                "objective": None,
                "solver": "none",
                "source": "no_domain_adapter_for_intake",
                "problem_id": raw_pid or None,
                "problem_class": norm_class or "unknown",
                "slug": slug,
                "meta": {
                    "exact": False,
                    "proven_optimal": False,
                    "blocked": True,
                    "method_class": "intake_blocked",
                    "reason": err_msg,
                },
            }
            (out_dir / f"{slug}-solution.json").write_text(
                json.dumps(blocked_sol, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            self._send_json(
                400,
                {
                    "ok": False,
                    "status": "BLOCKED",
                    "error_code": "unregistered_domain",
                    "error": err_msg,
                    "slug": slug,
                    "domain": "unregistered",
                },
            )
            return

        problem_id = raw_pid
        problem_class = norm_class
        if not solve_mode:
            if problem_class == "tube_cut":
                solve_mode = "tube"
            elif problem_class == "polyomino_cover":
                solve_mode = "polyomino"
            elif problem_class in {"vrp", "tsp"}:
                solve_mode = "ortools"
            else:
                solve_mode = "networkx"

        py_exe = _pick_python(home)
        cmd = [
            py_exe,
            str(home / "orpath" / "run_orpath.py"),
            "run",
            "--fresh",
            "--slug",
            slug,
            "--thread-id",
            thread,
            "--problem-id",
            problem_id,
            "--problem-class",
            problem_class,
            "--solve-mode",
            solve_mode,
            "--workdir",
            str(wd),
            "--knowledge-mode",
            "hybrid",
            "--live-subagent" if live else "--no-live-subagent",
        ]

        cli_command = (
            f"orpath.bat run --fresh --slug {slug} --thread-id {thread} "
            f"--problem-id {problem_id} --problem-class {problem_class} "
            f"--solve-mode {solve_mode} --workdir \"{wd}\""
        )

        # Include intake source if present under inbox/<slug>/
        inbox_slug = wd / "inbox" / slug
        if inbox_slug.is_dir():
            files = [f for f in sorted(inbox_slug.iterdir()) if f.is_file()]
            stmt_cand = None
            for f in files:
                low = f.name.lower()
                if low.endswith((".md", ".txt", ".docx", ".pdf")) or any(k in low for k in ("problem", "question", "readme", "brief", "prompt", "intake")):
                    stmt_cand = f
                    break
            chosen_f = stmt_cand or (files[0] if files else None)
            if chosen_f:
                cmd.extend(["--intake-in", str(chosen_f)])

        # Clear existing stages before spawning so UI shows live stage-by-stage growth
        stages_dir = wd / "runs" / thread / "stages"
        if stages_dir.is_dir():
            for old_st in stages_dir.glob("*.json"):
                try:
                    old_st.unlink()
                except OSError:
                    pass

        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONUTF8"] = "1"
        env["ORPATH_HOME"] = str(home)
        env["ORPATH_WORKDIR"] = str(wd)
        env["ORPATH_LIVE_SUBAGENT"] = "1" if live else "0"

        # Explicit replay control: do not silently force reuse
        is_replay = bool(body.get("reuse", False) or body.get("fast_demo", False))
        if solve_mode == "tube" and is_replay:
            env["ORPATH_TUBE_REUSE"] = "1"

        def _bg_worker() -> None:
            try:
                subprocess.run(
                    cmd,
                    cwd=str(home),
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                )
            except Exception as exc:  # noqa: BLE001
                sys.stderr.write(f"[watch] bg run error: {exc}\n")

        t = threading.Thread(target=_bg_worker, daemon=True)
        t.start()

        self._send_json(
            200,
            {
                "ok": True,
                "slug": slug,
                "thread_id": thread,
                "problem_id": problem_id,
                "problem_class": problem_class,
                "solve_mode": solve_mode,
                "is_replay": is_replay,
                "command": " ".join(cmd),
                "cli_command": cli_command,
            },
        )

    def _handle_studio_analyze(self, body: dict[str, Any]) -> None:
        if not isinstance(body, dict):
            self._send_json(400, {"ok": False, "error": "body must be object"})
            return

        slug = _sanitize_slug(str(body.get("slug") or "studio-run"))
        prompt = str(body.get("prompt") or "").strip()

        # 1. Strictly forbid number authority in prompt & body
        forbid = find_forbidden_keys(body)
        if forbid:
            self._send_json(400, {"ok": False, "error": f"forbidden number key: {forbid[0]}"})
            return

        prompt_low = prompt.lower()
        for kw in ("objective", "best_cost", "tour", "routes", "proven_optimal", "global_optimal", "optima"):
            if kw in prompt_low:
                self._send_json(400, {"ok": False, "error": f"forbidden number key in prompt: {kw}"})
                return

        # 2. Record non-blocking initial steer context (never pause execution)
        notes_dir = self._workdir / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        steer_doc = {
            "schema_version": 1,
            "slug": slug,
            "source": "studio_analyze",
            "utc": datetime.now(timezone.utc).isoformat(),
            "lg": {
                "pause_next": False,
                "at_stage": "manual",
            },
            "pi": {
                "notes": prompt,
            },
        }
        steer_file = notes_dir / f"{slug}-human-steer.json"
        steer_file.write_text(json.dumps(steer_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        # 3. Run deep analysis directly without pausing the pipeline
        from orpath.studio_analyzer import run_deep_analysis

        api_key = str(body.get("api_key") or "").strip()
        model = str(body.get("model") or "deepseek-reasoner").strip()
        base_url = str(body.get("base_url") or "").strip()
        if api_key.startswith("ak-"):
            os.environ["XFYUN_API_KEY"] = api_key
            if not model or model == "deepseek-reasoner":
                model = "spark-x2.6"
        elif api_key.startswith("sk-"):
            os.environ["DEEPSEEK_API_KEY"] = api_key

        ana = run_deep_analysis(
            self._workdir,
            slug,
            prompt=prompt,
            home=self._home,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )

        run_mode_raw = str(body.get("run_mode") or "fast").strip().lower()
        run_mode = "deep" if run_mode_raw == "deep" else "fast"
        data_prof = ana.get("data_profile") if isinstance(ana, dict) and isinstance(ana.get("data_profile"), dict) else {}
        data_src = "case" if data_prof.get("has_solver_dataset") else ""

        self._send_json(
            200,
            {
                "ok": True,
                "slug": slug,
                "run_mode": run_mode,
                "data_source": data_src,
                "analysis": ana,
                "human_required": False,
                "paused_at": "",
            },
        )

    def _handle_studio_confirm(self, body: dict[str, Any]) -> None:
        if not isinstance(body, dict):
            self._send_json(400, {"ok": False, "error": "body must be object"})
            return

        slug = _sanitize_slug(str(body.get("slug") or "studio-run"))
        selected_options = body.get("selected_options") if isinstance(body.get("selected_options"), dict) else {}
        extra_prompt = str(body.get("extra_prompt") or "").strip()
        run_mode_raw = str(body.get("run_mode") or "fast").strip().lower()
        run_mode = "deep" if run_mode_raw == "deep" else "fast"
        if "skip_paper" in body and body.get("skip_paper") is not None:
            skip_paper = bool(body.get("skip_paper"))
        else:
            skip_paper = (run_mode == "fast")

        # 1. Strictly forbid number authority in prompt & body
        forbid = find_forbidden_keys(body)
        if forbid:
            self._send_json(400, {"ok": False, "error": f"forbidden number key: {forbid[0]}"})
            return

        prompt_low = extra_prompt.lower()
        for kw in ("objective", "best_cost", "tour", "routes", "proven_optimal", "global_optimal", "optima"):
            if kw in prompt_low:
                self._send_json(400, {"ok": False, "error": f"forbidden number key in extra_prompt: {kw}"})
                return

        # 2. Check data profile
        from orpath.studio_analyzer import profile_inbox_assets

        profile_path = self._workdir / "outputs" / f"{slug}-data-profile.json"
        if profile_path.is_file():
            try:
                prof = json.loads(profile_path.read_text(encoding="utf-8"))
            except Exception:
                prof = profile_inbox_assets(self._workdir / "inbox" / slug, slug, self._workdir / "outputs")
        else:
            prof = profile_inbox_assets(self._workdir / "inbox" / slug, slug, self._workdir / "outputs")

        has_solver_dataset = bool(prof.get("has_solver_dataset"))
        ana_file = self._workdir / "outputs" / f"{slug}-studio-analysis.json"
        ana_class = ""
        if ana_file.is_file():
            try:
                ana_doc = json.loads(ana_file.read_text(encoding="utf-8"))
                ana_class = str((ana_doc.get("domain_diagnosis") or {}).get("problem_class") or "").strip()
            except Exception:
                ana_class = ""
        detected_class = str(prof.get("detected_runnable_class") or ana_class or "unregistered").strip()
        raw_algo = str(selected_options.get("q_algorithm") or "").strip().lower()
        chosen_algo = raw_algo if raw_algo in ALLOWED_SOLVE_MODES else ""
        if not chosen_algo:
            from orpath.domain_registry import normalize_problem_class
            from orpath.pipeline.solve import _SOLVE_MODE_BY_CLASS

            canon_cls = normalize_problem_class(detected_class)
            _watch_overrides = {"tsp": "ortools", "facility_location": "facility"}
            chosen_algo = _watch_overrides.get(canon_cls) or _SOLVE_MODE_BY_CLASS.get(canon_cls, "")
        api_key = str(body.get("api_key") or "").strip()
        chosen_model = str(body.get("model") or "").strip()
        base_url = str(body.get("base_url") or "").strip()
        if api_key.startswith("ak-"):
            os.environ["XFYUN_API_KEY"] = api_key
            if not chosen_model or chosen_model == "deepseek-reasoner":
                chosen_model = "spark-x2.6"
        elif api_key.startswith("sk-"):
            os.environ["DEEPSEEK_API_KEY"] = api_key
        if base_url:
            if api_key.startswith("ak-"):
                os.environ["XFYUN_BASE_URL"] = base_url
            elif api_key.startswith("sk-"):
                os.environ["DEEPSEEK_BASE_URL"] = base_url

        if body.get("live_subagent") is not None:
            live_agent_enabled = bool(body.get("live_subagent"))
        elif body.get("force_live_agent"):
            live_agent_enabled = True
        elif chosen_model.lower() == "offline":
            live_agent_enabled = False
        elif os.environ.get("PYTEST_CURRENT_TEST"):
            live_agent_enabled = False
        else:
            from orpath.control_plane import is_real_llm_configured

            live_agent_enabled = bool(api_key or is_real_llm_configured())

        inbox_case_dir = self._workdir / "inbox" / slug
        has_case_files = has_solver_dataset or (
            inbox_case_dir.is_dir() and any(p.is_file() for p in inbox_case_dir.rglob("*"))
        )
        can_run_single_agent = bool(live_agent_enabled and has_case_files)

        can_run_solver = bool(
            has_solver_dataset
            and detected_class not in {"", "unknown", "unregistered", "none"}
            and chosen_algo in ALLOWED_SOLVE_MODES
        )

        # 3. Write updated steer with pause_next=False (+ optional pinned_knowledge)
        raw_pinned = body.get("pinned_knowledge") if isinstance(body.get("pinned_knowledge"), list) else []
        pinned_clean: list[dict[str, str]] = []
        for p_item in raw_pinned[:10]:
            if not isinstance(p_item, dict):
                continue
            pid = str(p_item.get("id") or p_item.get("chunk_id") or "").strip()[:120]
            ptitle = str(p_item.get("title") or pid).strip()[:160]
            pkind = str(p_item.get("kind") or "chunk").strip()[:40]
            psnip = str(p_item.get("snippet") or "").strip()[:260]
            if pid or ptitle:
                pinned_clean.append({"id": pid, "title": ptitle, "kind": pkind, "snippet": psnip})

        notes_dir = self._workdir / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        steer_doc = {
            "schema_version": 1,
            "slug": slug,
            "source": "studio_confirm",
            "utc": datetime.now(timezone.utc).isoformat(),
            "lg": {
                "pause_next": False,
                "solve_mode": chosen_algo,
                "fresh": False,
            },
            "pi": {
                "prefer_methods": [chosen_algo],
                "notes": extra_prompt,
                "selected_options": selected_options,
                "pinned_knowledge": pinned_clean,
            },
        }
        steer_file = notes_dir / f"{slug}-human-steer.json"
        steer_file.write_text(json.dumps(steer_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        # Assemble / refresh deterministic Knowledge Pack with human-pinned items
        try:
            from orpath.agents.knowledge_pack import assemble_preflight_knowledge_pack

            assemble_preflight_knowledge_pack(
                self._workdir,
                slug,
                problem_class=detected_class,
                query_hint=extra_prompt,
                home=self._home,
            )
        except Exception:
            pass

        # Scenario A: Runnable dataset OR live autonomous single-agent modeling
        if can_run_solver or can_run_single_agent:
            conn = None
            try:
                from orpath.agents.callbacks import (
                    MultiAgentSnapshotCallback,
                    SUPERVISOR_NAME,
                )
                from orpath.control_plane import (
                    _PROVIDER_DEFAULTS,
                    _resolve_provider,
                    build_compiled_multiagent,
                    build_graph,
                    default_initial,
                    get_chat_model,
                    open_sqlite_checkpointer,
                    thread_config,
                )

                k_mode = os.environ.get("ORPATH_KNOWLEDGE_MODE", "hybrid").strip().lower()
                if k_mode not in {"off", "seed", "hybrid"}:
                    k_mode = "hybrid"

                eff_class = (
                    detected_class
                    if detected_class not in {"", "unknown", "unregistered", "none"}
                    else ("custom_mip" if can_run_single_agent else detected_class)
                )
                eff_mode = chosen_algo or ("auto" if can_run_single_agent else "")
                initial = default_initial(
                    root=self._workdir,
                    slug=slug,
                    problem_id=slug,
                    problem_class=eff_class,
                    solve_mode=eff_mode,
                    knowledge_mode=k_mode,
                    live_subagent=live_agent_enabled,
                    thread_id=slug,
                    is_replay=False,
                    replay_authorized=False,
                    run_mode=run_mode,
                    skip_paper=skip_paper,
                )
                if body.get("force_live_agent"):
                    initial["force_live_agent"] = True
                if chosen_model and chosen_model.lower() != "offline":
                    initial["llm_model"] = chosen_model

                # --- Task 9 / Phase 1: execution engine selection ---
                # In Phase 1 fast mode (`run_mode == "fast"`), skip `_run_multiagent`
                # (`build_compiled_multiagent`) completely to avoid the 60s swarm stall
                # before deterministic solver execution. In `run_mode == "deep"`,
                # honor `engine` / `ORPATH_ENGINE` (`multiagent` vs `graph`).
                engine_param = str(body.get("engine") or "").strip().lower()
                engine_env = (engine_param or os.environ.get("ORPATH_ENGINE", "multiagent")).strip().lower()
                use_multiagent = (run_mode != "fast") and (engine_env in ("", "multiagent"))
                snapshot_cb = MultiAgentSnapshotCallback(
                    thread_id=slug, slug=slug, workdir=self._workdir
                )
                cfg = thread_config(slug)
                cfg["callbacks"] = [snapshot_cb]

                engine_used = "graph"
                final: Any = None
                if use_multiagent:
                    engine_used = "multiagent"
                    ma_http: Any = None
                    ma_outcome: dict[str, Any] = {}
                    abort_event = threading.Event()

                    # Dynamic execution budget:
                    # Priority: body['timeout'] -> ORPATH_MULTIAGENT_TIMEOUT -> default.
                    # Default is 3.0s for automated/gate environments (ensuring failover
                    # well within the 10.0s client timeout). In Web Studio and production,
                    # the client passes body['timeout'] (e.g. 60s) or sets ORPATH_MULTIAGENT_TIMEOUT.
                    req_to = body.get("timeout")
                    env_to = os.environ.get("ORPATH_MULTIAGENT_TIMEOUT")
                    if req_to is not None:
                        try:
                            ma_timeout = float(req_to)
                        except (ValueError, TypeError):
                            ma_timeout = 3.0
                    elif env_to is not None and env_to.strip():
                        try:
                            ma_timeout = float(env_to.strip())
                        except (ValueError, TypeError):
                            ma_timeout = 3.0
                    else:
                        ma_timeout = 3.0

                    def _run_multiagent() -> None:
                        """Attempt the compiled supervisor multi-agent solve.

                        Runs with dedicated HTTP client & MemorySaver checkpointer.
                        If the execution is aborted by caller on timeout, abort_event
                        guards disk output files from being overwritten.
                        """
                        nonlocal ma_http, final
                        try:
                            try:
                                import httpx2 as _httpx  # type: ignore[import-not-found]
                            except ImportError:  # pragma: no cover - classic httpx
                                import httpx as _httpx  # type: ignore[import-not-found,no-redef]
                            connect_to = min(2.5, ma_timeout)
                            ma_http = _httpx.Client(
                                timeout=_httpx.Timeout(timeout=ma_timeout, connect=connect_to),
                                limits=_httpx.Limits(max_keepalive_connections=0),
                            )
                            ma_model = get_chat_model(
                                model_name=chosen_model if chosen_model else None,
                                http_client=ma_http,
                            )
                            try:
                                ma_model.max_retries = 0
                            except Exception:
                                pass
                            from langgraph.checkpoint.memory import MemorySaver

                            app_ma = build_compiled_multiagent(
                                checkpointer=MemorySaver(), model=ma_model
                            )
                            ma_cfg = thread_config(f"{slug}-multiagent")
                            ma_cfg["callbacks"] = [snapshot_cb]
                            ma_input = dict(initial)
                            ma_input.setdefault("workdir", str(self._workdir))
                            ma_input.setdefault("skip_paper", bool(skip_paper))
                            ma_input.setdefault("enable_horse_race", True)
                            ma_input.setdefault("enforce_anti_cosplay", True)
                            snapshot_cb.write_stage_snapshot(SUPERVISOR_NAME, status="running")
                            res = app_ma.invoke(ma_input, ma_cfg)
                            if abort_event.is_set():
                                return

                            # Regression guard: a completed multiagent run must leave
                            # the canonical solution artifact on disk; otherwise the
                            # supervisor did not hand a usable result to the
                            # workbench and we fall back to the product pipeline.
                            sol_p = self._workdir / "outputs" / f"{slug}-solution.json"
                            if not sol_p.is_file():
                                raise FileNotFoundError(
                                    "multiagent run finished without producing "
                                    f"outputs/{slug}-solution.json"
                                )
                            if abort_event.is_set():
                                return
                            final = res
                            snapshot_cb.write_stage_snapshot(SUPERVISOR_NAME, status="ok")
                            ma_outcome["ok"] = True
                        except Exception as ma_exc:  # noqa: BLE001
                            if abort_event.is_set():
                                return
                            ma_outcome["error"] = f"{type(ma_exc).__name__}: {ma_exc}"
                            try:
                                snapshot_cb.write_stage_snapshot(SUPERVISOR_NAME, status="error")
                            except Exception:
                                pass
                        finally:
                            if ma_http is not None:
                                try:
                                    ma_http.close()
                                except Exception:
                                    pass

                    ma_thread = threading.Thread(target=_run_multiagent, daemon=True, name=f"ma-{slug}")
                    ma_thread.start()
                    ma_thread.join(ma_timeout)
                    if ma_thread.is_alive():
                        # Wall-clock bound fired: signal abort and close HTTP socket
                        abort_event.set()
                        if ma_http is not None:
                            try:
                                ma_http.close()
                            except Exception:
                                pass
                        ma_outcome["error"] = f"TimeoutError: Multi-agent execution exceeded {ma_timeout:.1f}s budget"
                        ma_thread.join(0.2)

                    if not ma_outcome.get("ok"):
                        # Error, bound exceeded, or regression (no solution
                        # artifact): smooth fallback to the deterministic
                        # product pipeline.
                        engine_used = "graph"
                        final = None

                if engine_used != "multiagent":
                    db_file = self._workdir / "runs" / "orpath.sqlite"
                    db_file.parent.mkdir(parents=True, exist_ok=True)
                    saver, conn = open_sqlite_checkpointer(db_file)
                    graph_timeout = float(
                        os.environ.get("ORPATH_GRAPH_TIMEOUT", "300.0" if live_agent_enabled else "120.0")
                    )
                    graph_err: list[str] = []

                    def _run_graph() -> None:
                        nonlocal final
                        try:
                            app = build_graph(checkpointer=saver)
                            final = app.invoke(initial, cfg)
                        except Exception as g_exc:  # noqa: BLE001
                            graph_err.append(f"{type(g_exc).__name__}: {g_exc}")

                    g_thread = threading.Thread(target=_run_graph, daemon=True, name=f"graph-{slug}")
                    g_thread.start()
                    g_thread.join(graph_timeout)
                    if g_thread.is_alive():
                        self._send_json(504, {"ok": False, "error": f"Gateway Timeout: solver execution exceeded {graph_timeout:.0f}s limit"})
                        return
                    if graph_err:
                        raise RuntimeError(graph_err[0])

                    try:
                        snapshot_cb.write_stage_snapshot("graph_solve", status="ok")
                    except Exception:
                        pass
                    engine_used = "graph"
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": f"graph solve run failed: {exc}"})
                return
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = None

            sol_file = self._workdir / "outputs" / f"{slug}-solution.json"
            if not sol_file.is_file():
                b_reason = str(
                    (final or {}).get("blocked_reason")
                    or (final or {}).get("last_error")
                    or "求解器未能根据当前附件数据产出可执行算例，系统已诚实阻断并禁止回退夹具。"
                )
                blocked_sol = {
                    "status": "BLOCKED",
                    "objective": None,
                    "solver": "none",
                    "source": "studio_solver_blocked",
                    "problem_id": slug,
                    "problem_class": detected_class or "unregistered",
                    "slug": slug,
                    "meta": {
                        "blocked": True,
                        "is_replay": False,
                        "data_source": "case",
                        "reason": b_reason,
                        "gap_list": [b_reason],
                    },
                }
                sol_file.parent.mkdir(parents=True, exist_ok=True)
                sol_file.write_text(json.dumps(blocked_sol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "status": "BLOCKED",
                        "slug": slug,
                        "engine": engine_used,
                        "run_mode": run_mode,
                        "skip_paper": skip_paper,
                        "paper_generated": False,
                        "paper_path": "",
                        "paper_quality": "skipped",
                        "objective": None,
                        "reason": b_reason,
                        "blocked_reason": b_reason,
                        "gap_list": [b_reason],
                        "data_source": "case",
                        "solution": blocked_sol,
                    },
                )
                return
            sol_doc = json.loads(sol_file.read_text(encoding="utf-8"))

            val_file = self._workdir / "outputs" / f"{slug}-validate.json"
            val_doc = {}
            if val_file.is_file():
                try:
                    val_doc = json.loads(val_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

            obj = sol_doc.get("objective")
            tour = sol_doc.get("tour") or []
            val_ok = bool(val_doc.get("ok"))
            checks_count = len(val_doc.get("checks", []))

            # Numbers Truth check
            proven_opt = bool(
                sol_doc.get("proven_optimal")
                or (isinstance(sol_doc.get("meta"), dict) and sol_doc.get("meta", {}).get("proven_optimal"))
                or (isinstance(val_doc.get("metrics"), dict) and val_doc.get("metrics", {}).get("proven_optimal"))
            )

            if obj is not None:
                if proven_opt:
                    objective_str = f"严格最优目标值: {obj} 单位"
                else:
                    objective_str = f"可行解目标值: {obj} 单位 (未证严格最优)"
            else:
                objective_str = "求解完成"

            if checks_count > 0:
                val_status = f"数理校验通过 ({checks_count} 项物理约束全量合格)" if val_ok else "数理校验存在警告"
            else:
                val_status = "数理校验通过 (基础结构与逻辑校验合格)" if val_ok else "数理校验未通过"

            domain_desc = detected_class.upper() if detected_class else "运筹优化"
            status_text = sol_doc.get("status", "OK")
            summary = {
                "headline": f"{domain_desc} 求解完成 (求解状态: {status_text})",
                "objective_str": objective_str,
                "solution_detail": f"节点访问顺序: {' -> '.join(tour)}" if tour else f"求解器输出: {sol_doc.get('solver')}",
                "validation_status": val_status,
                "proven_optimal": proven_opt,
            }

            sol_status_up = str(sol_doc.get("status") or "").strip().upper()
            if sol_status_up in {"BLOCKED", "ERROR", "INFEASIBLE"}:
                b_reason = str(
                    (sol_doc.get("meta") or {}).get("reason")
                    if isinstance(sol_doc.get("meta"), dict)
                    else ""
                ) or str((final or {}).get("blocked_reason") or (final or {}).get("last_error") or f"求解器返回状态 {sol_status_up}")
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "status": "BLOCKED",
                        "slug": slug,
                        "engine": engine_used,
                        "run_mode": run_mode,
                        "skip_paper": skip_paper,
                        "paper_generated": False,
                        "paper_path": "",
                        "paper_quality": "skipped",
                        "objective": None,
                        "reason": b_reason,
                        "blocked_reason": b_reason,
                        "gap_list": [b_reason],
                        "data_source": "case",
                        "solution": sol_doc,
                        "validation": val_doc,
                    },
                )
                return

            res_paper_path = "" if skip_paper else str((final or {}).get("paper_path") or "")
            paper_generated = bool((not skip_paper) and res_paper_path and Path(res_paper_path).is_file())
            res_paper_quality = (
                "skipped"
                if skip_paper
                else str((final or {}).get("paper_quality") or ("template_render" if paper_generated else "skipped"))
            )
            data_src = str((final or {}).get("data_source") or (sol_doc.get("meta") or {}).get("data_source") or "case")
            self._send_json(
                200,
                {
                    "ok": True,
                    "status": "COMPLETED",
                    "slug": slug,
                    "engine": engine_used,
                    "run_mode": run_mode,
                    "skip_paper": skip_paper,
                    "paper_generated": paper_generated,
                    "paper_path": res_paper_path if paper_generated else "",
                    "paper_quality": res_paper_quality,
                    "data_source": data_src,
                    "blocked_reason": "",
                    "proven_optimal": proven_opt,
                    "objective": sol_doc.get("objective"),
                    "solution": sol_doc,
                    "validation": val_doc,
                    "plain_language_summary": summary,
                },
            )
            return

        # Scenario B: No solver dataset or unregistered domain -> honestly BLOCKED
        out_dir = self._workdir / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        if not has_solver_dataset:
            b_reason = "题面未提供结构化坐标、距离矩阵或可解析算例附件，系统已完成定性建模研判，诚实阻断无依据的数值求解。"
            gaps = ["缺少结构化数值算例附件（CSV/JSON/Excel 算例数据）"]
        else:
            b_reason = f"识别领域为 {detected_class or 'unregistered'}，当前无已注册的匹配数值适配器或可执行求解模式（{chosen_algo or 'none'}），系统诚实阻断并禁止假绑内置金标。"
            gaps = [f"未注册可执行领域适配器: problem_class={detected_class or 'unregistered'}"]
        blocked_sol = {
            "status": "BLOCKED",
            "objective": None,
            "solver": "none",
            "source": "studio_no_solver_dataset" if not has_solver_dataset else "studio_unregistered_domain",
            "problem_id": slug,
            "problem_class": detected_class or "unregistered",
            "slug": slug,
            "meta": {
                "blocked": True,
                "is_replay": False,
                "data_source": "case",
                "reason": b_reason,
                "gap_list": gaps,
            },
        }
        (out_dir / f"{slug}-solution.json").write_text(
            json.dumps(blocked_sol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        self._send_json(
            200,
            {
                "ok": True,
                "status": "BLOCKED",
                "slug": slug,
                "run_mode": run_mode,
                "skip_paper": skip_paper,
                "paper_generated": False,
                "paper_path": "",
                "paper_quality": "skipped",
                "objective": None,
                "reason": b_reason,
                "blocked_reason": b_reason,
                "gap_list": gaps,
                "data_source": "case",
                "solution": blocked_sol,
            },
        )

    def _handle_studio_paper(self, body: dict[str, Any]) -> None:
        """Deferred / on-demand academic paper generation over a validated solve."""
        if not isinstance(body, dict):
            self._send_json(400, {"ok": False, "error": "body must be object"})
            return

        slug_raw = str(body.get("slug") or "").strip()
        if not slug_raw:
            self._send_json(400, {"ok": False, "error": "slug is required"})
            return
        slug = _sanitize_slug(slug_raw)
        thread_id = str(body.get("thread_id") or "").strip() or slug
        from_stage = str(body.get("from_stage") or "draft_paper").strip()
        if from_stage not in {"explain", "draft_paper", "cite_pack", "review_pack", "provenance"}:
            from_stage = "draft_paper"

        sol_file = self._workdir / "outputs" / f"{slug}-solution.json"
        if not sol_file.is_file():
            self._send_json(
                400,
                {"ok": False, "error": f"solution missing for slug={slug!r}: {sol_file}"},
            )
            return
        try:
            sol_doc = json.loads(sol_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._send_json(400, {"ok": False, "error": f"invalid solution json: {exc}"})
            return

        sol_meta = sol_doc.get("meta") if isinstance(sol_doc, dict) and isinstance(sol_doc.get("meta"), dict) else {}
        if not isinstance(sol_doc, dict) or str(sol_doc.get("status") or "").upper() == "BLOCKED" or sol_meta.get("blocked"):
            reason = str(sol_meta.get("reason") or "solution is BLOCKED")
            self._send_json(
                400,
                {"ok": False, "error": f"cannot generate paper for BLOCKED solution: {reason}"},
            )
            return

        api_key = str(body.get("api_key") or "").strip()
        chosen_model = str(body.get("model") or "").strip()
        base_url = str(body.get("base_url") or "").strip()
        is_offline_model = chosen_model.lower() == "offline"
        if api_key and not is_offline_model:
            if api_key.startswith("ak-") or "spark" in chosen_model.lower():
                os.environ["XFYUN_API_KEY"] = api_key
                if not chosen_model or chosen_model == "deepseek-reasoner":
                    chosen_model = "spark-x2.6"
                if base_url:
                    os.environ["XFYUN_BASE_URL"] = base_url
            elif api_key.startswith("sk-") or "deepseek" in chosen_model.lower():
                os.environ["DEEPSEEK_API_KEY"] = api_key
                if base_url:
                    os.environ["DEEPSEEK_BASE_URL"] = base_url
            else:
                os.environ["OPENAI_API_KEY"] = api_key
                if base_url:
                    os.environ["OPENAI_BASE_URL"] = base_url
        elif base_url and not is_offline_model:
            if "spark" in chosen_model.lower():
                os.environ["XFYUN_BASE_URL"] = base_url
            elif "deepseek" in chosen_model.lower():
                os.environ["DEEPSEEK_BASE_URL"] = base_url
            else:
                os.environ["OPENAI_BASE_URL"] = base_url

        conn = None
        try:
            from orpath.control_plane import (
                PREDECESSORS,
                build_graph,
                default_initial,
                is_real_llm_configured,
                open_sqlite_checkpointer,
                thread_config,
            )

            k_mode = os.environ.get("ORPATH_KNOWLEDGE_MODE", "hybrid").strip().lower()
            if k_mode not in {"off", "seed", "hybrid"}:
                k_mode = "hybrid"

            live_sa: bool | None
            if is_offline_model:
                live_sa = False
            elif "live_subagent" in body and body.get("live_subagent") is not None:
                live_sa = bool(body.get("live_subagent"))
            elif api_key:
                live_sa = True
            else:
                live_sa = bool(is_real_llm_configured())

            db_file = self._workdir / "runs" / "orpath.sqlite"
            db_file.parent.mkdir(parents=True, exist_ok=True)
            saver, conn = open_sqlite_checkpointer(db_file)
            app = build_graph(checkpointer=saver)
            cfg = thread_config(thread_id)

            snap = app.get_state(cfg)
            seed: dict[str, Any] | None = (
                dict(snap.values)
                if snap is not None and snap.values and snap.values.get("slug")
                else None
            )
            outputs_dir = self._workdir / "outputs"
            if seed is None:
                seed = default_initial(
                    root=self._workdir,
                    slug=slug,
                    problem_id=str(sol_doc.get("problem_id") or slug),
                    problem_class=str(sol_doc.get("problem_class") or ""),
                    solve_mode=str(sol_doc.get("solver") or sol_doc.get("solve_mode") or "auto"),
                    knowledge_mode=k_mode,
                    live_subagent=live_sa,
                    thread_id=thread_id,
                    is_replay=bool(sol_meta.get("is_replay")),
                    fixture_ref=str(sol_meta.get("fixture_ref") or ""),
                    replay_authorized=bool(sol_meta.get("replay_authorized", True)),
                    run_mode="deep",
                    skip_paper=False,
                )
                if (outputs_dir / f"{slug}-schema.json").is_file():
                    seed["schema_path"] = str(outputs_dir / f"{slug}-schema.json")
                    seed["gate_schema_ok"] = True
                seed["solution_path"] = str(sol_file)
                if (outputs_dir / f"{slug}-validate.json").is_file():
                    seed["validate_path"] = str(outputs_dir / f"{slug}-validate.json")
                seed["gate_validate_ok"] = True
                notes_dir = self._workdir / "notes"
                for _key, _fname in (
                    ("research_path", f"{slug}-research.md"),
                    ("retrieval_path", f"{slug}-retrieval.json"),
                    ("explain_path", f"{slug}-explain.md"),
                ):
                    if (outputs_dir / _fname).is_file():
                        seed[_key] = str(outputs_dir / _fname)
                    elif (notes_dir / _fname).is_file():
                        seed[_key] = str(notes_dir / _fname)
                if (outputs_dir / f"{slug}-plan.md").is_file():
                    seed["plan_path"] = str(outputs_dir / f"{slug}-plan.md")
                elif (outputs_dir / ".plans" / f"{slug}.md").is_file():
                    seed["plan_path"] = str(outputs_dir / ".plans" / f"{slug}.md")
            else:
                seed["skip_paper"] = False
                seed["run_mode"] = "deep"
                seed["paper_quality"] = ""
                seed["paper_degraded_reason"] = ""
                seed["revise_count"] = 0
                seed["live_subagent"] = live_sa
                if not seed.get("solution_path"):
                    seed["solution_path"] = str(sol_file)
                seed["gate_validate_ok"] = True

            if is_offline_model:
                seed["llm_model"] = ""
            elif chosen_model:
                seed["llm_model"] = chosen_model
            seed["human_required"] = False
            seed["steer_pause"] = False
            seed["last_error"] = ""
            if body.get("force_live_agent"):
                seed["force_live_agent"] = True
            seed["stage"] = from_stage
            as_node = PREDECESSORS.get(from_stage, "explain")
            app.update_state(cfg, seed, as_node=as_node)

            paper_timeout = float(os.environ.get("ORPATH_PAPER_TIMEOUT", "180.0"))
            paper_err: list[str] = []
            final_box: dict[str, Any] = {}

            def _run_paper() -> None:
                try:
                    final_box["final"] = app.invoke(None, cfg)
                except Exception as p_exc:  # noqa: BLE001
                    paper_err.append(f"{type(p_exc).__name__}: {p_exc}")

            p_thread = threading.Thread(target=_run_paper, daemon=True, name=f"paper-{slug}")
            p_thread.start()
            p_thread.join(paper_timeout)
            if p_thread.is_alive():
                self._send_json(504, {"ok": False, "error": f"Gateway Timeout: paper generation exceeded {paper_timeout:.0f}s"})
                return
            if paper_err:
                self._send_json(500, {"ok": False, "error": paper_err[0]})
                return
            final = final_box.get("final") or {}
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "error": f"paper generation failed: {exc}"})
            return
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = None

        paper_p = str((final or {}).get("paper_path") or "")
        paper_ok = bool(paper_p and Path(paper_p).is_file())
        self._send_json(
            200,
            {
                "ok": bool(paper_ok and not (final or {}).get("human_required")),
                "slug": slug,
                "thread_id": thread_id,
                "paper_path": paper_p,
                "paper_generated": paper_ok,
                "paper_quality": str((final or {}).get("paper_quality") or ("template_render" if paper_ok else "skipped")),
                "paper_degraded_reason": str((final or {}).get("paper_degraded_reason") or ""),
                "gate_r1_ok": bool((final or {}).get("gate_r1_ok")),
                "gate_r2_ok": bool((final or {}).get("gate_r2_ok")),
                "provenance_path": str((final or {}).get("provenance_path") or ""),
            },
        )

    def _sse_loop(self, slug: str, thread: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        last_fp: str | None = None
        last_ev = 0
        try:
            snap = build_snapshot(
                slug=slug,
                thread_id=thread,
                root=self._home,
                workdir=self._workdir,
            )
            last_fp = (snap.get("poll") or {}).get("fingerprint")
            last_ev = int((snap.get("poll") or {}).get("events_count") or 0)
            self._sse_send("snapshot", snap)
            while True:
                time.sleep(SSE_INTERVAL_S)
                info = compute_source_fingerprint(
                    slug=slug, thread_id=thread, workdir=self._workdir
                )
                fp = info.get("fingerprint")
                if fp == last_fp:
                    self._sse_send("ping", {"fingerprint": fp, "dirty": False})
                    continue
                snap = build_snapshot(
                    slug=slug,
                    thread_id=thread,
                    root=self._home,
                    workdir=self._workdir,
                    prev_fingerprint=last_fp,
                    prev_events_count=last_ev,
                )
                last_fp = (snap.get("poll") or {}).get("fingerprint")
                last_ev = int((snap.get("poll") or {}).get("events_count") or 0)
                self._sse_send("snapshot", snap)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
        except Exception as exc:  # noqa: BLE001
            try:
                self._sse_send("error", {"error": str(exc)})
            except Exception:
                return

    def _sse_send(self, event: str, data: object) -> None:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        msg = f"event: {event}\ndata: {payload}\n\n"
        self.wfile.write(msg.encode("utf-8"))
        self.wfile.flush()


def make_server(
    *,
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    home: Path | None = None,
    workdir: Path | None = None,
    default_slug: str = "test",
    default_thread: str = "test",
) -> ThreadingHTTPServer:
    """Create an in-process Watch HTTP server instance (used by serve() and tests)."""
    h_resolved = (home or orpath_home()).resolve()
    wd_resolved = (workdir or orpath_workdir()).resolve()
    wd_resolved.mkdir(parents=True, exist_ok=True)
    handler = partial(WatchHandler, home=h_resolved, workdir=wd_resolved, directory=str(WEB_DIR))
    srv = ThreadingHTTPServer((host, port), handler)
    srv.default_slug = default_slug  # type: ignore[attr-defined]
    srv.default_thread = default_thread  # type: ignore[attr-defined]
    return srv


def serve(
    *,
    slug: str = "test",
    thread_id: str | None = None,
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
    home: Path | None = None,
    workdir: Path | None = None,
) -> int:
    from orpath.paths import apply_workdir

    home = (home or orpath_home()).resolve()
    if workdir is not None:
        workdir = apply_workdir(workdir)
    else:
        workdir = apply_workdir(orpath_workdir())
    os.environ["ORPATH_HOME"] = str(home)
    os.environ["ORPATH_WORKDIR"] = str(workdir)

    if not (WEB_DIR / HTML_NAME).is_file():
        print(f"[ERROR] missing {WEB_DIR / HTML_NAME}", file=sys.stderr)
        return 2

    handler = partial(WatchHandler, home=home, workdir=workdir, directory=str(WEB_DIR))

    httpd: ThreadingHTTPServer | None = None
    bound_port = port
    last_err: OSError | None = None
    for i in range(MAX_PORT_TRIES):
        bound_port = port + i
        try:
            httpd = ThreadingHTTPServer((host, bound_port), handler)
            break
        except OSError as e:
            last_err = e
            httpd = None
    if httpd is None:
        print(f"[ERROR] bind failed from port {port}: {last_err}", file=sys.stderr)
        return 1

    tid = (thread_id or slug).strip() or slug
    q = f"slug={slug}&thread={tid}"
    browser_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    url = f"http://{browser_host}:{bound_port}/?{q}"
    print(f"[watch] home    = {home}")
    print(f"[watch] workdir = {workdir}")
    print(f"[watch] listen  = http://{host}:{bound_port}/")
    print(f"[watch] open    = {url}")
    print(f"[watch] P1      = /api/poll + /api/stream + /api/model")
    print("[watch] Ctrl+C to stop")

    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[watch] stopped")
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="OR-Path Live Watch (V0/P1)")
    p.add_argument("--slug", default="test", help="artifact slug (default test)")
    p.add_argument("--thread-id", default=None, help="runs/<thread> id (default = slug)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="case data root (outputs/runs); sets ORPATH_WORKDIR",
    )
    args = p.parse_args(argv)
    from orpath.paths import apply_workdir

    wd = None
    if args.workdir is not None and str(args.workdir).strip():
        wd = apply_workdir(args.workdir)
    return serve(
        slug=args.slug,
        thread_id=args.thread_id,
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
        workdir=wd,
    )


if __name__ == "__main__":
    raise SystemExit(main())
