#!/usr/bin/env python3
"""OR-Path Live Watch HTTP face (V0 Tier-1 + P1 poll + model pref).

  GET  /                         → orpath/web/watch.html
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
import json
import os
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orpath.human_steer import (  # noqa: E402
    build_steer_cta,
    load_human_steer,
    normalize_steer_payload,
    save_human_steer,
    steer_path,
)
from orpath.paths import orpath_home, orpath_workdir  # noqa: E402
from orpath.watch_snapshot import (  # noqa: E402
    build_snapshot,
    compute_source_fingerprint,
)

WEB_DIR = ROOT / "orpath" / "web"
HTML_NAME = "watch.html"
DEFAULT_PORT = 8765
MAX_PORT_TRIES = 20
SSE_INTERVAL_S = 0.5


class WatchHandler(SimpleHTTPRequestHandler):
    server_version = "ORPathWatch/0.3-apple"

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
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _qs_slug_thread(self, qs: dict) -> tuple[str, str]:
        slug = (qs.get("slug") or ["test"])[0].strip() or "test"
        thread = (qs.get("thread") or qs.get("thread_id") or [slug])[0].strip() or slug
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

        if path != "/api/model":
            self.send_error(404, "not found")
            return
        provider = str(body.get("provider") or "").strip()
        model = str(body.get("model") or "").strip()
        if not model:
            self._send_json(400, {"ok": False, "error": "model required"})
            return
        try:
            from orpath.pi_model_pref import set_pi_model_pref

            info = set_pi_model_pref(
                provider=provider or "deepseek",
                model=model,
                home=self._home,
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
                from orpath.pi_model_pref import get_pi_model_pref

                m = get_pi_model_pref(home=self._home)
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
                    ],
                    "dialogue": True,
                },
            )
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
                from orpath.pi_model_pref import get_pi_model_pref

                info = get_pi_model_pref(home=self._home)
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
                    from orpath.pi_model_pref import get_pi_model_pref

                    snap["pi_model"] = get_pi_model_pref(home=self._home)
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
            self._send_html_file(WEB_DIR / HTML_NAME)
            return

        self.send_error(404, "not found")

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
    url = f"http://{host}:{bound_port}/?{q}"
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
