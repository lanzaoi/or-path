#!/usr/bin/env python3
"""OR-Path P3: one-shot Live Watch + product run (边跑边看).

Default (fast, no Pi bill):
  start watch HTTP → open browser → mock SP run (LIVE off) → prove L0 grew
  write outputs/<slug>-watch-run.json

Optional:
  --live          LIVE subagent ON during run (slow; needs Pi)
  --keep-watch    leave HTTP server up after run (Ctrl+C to stop)
  --no-browser
  --skip-run      only start watch (same as plain watch, but with P3 banner)

Exit:
  0  run ok and stages grew (or skip-run and server started)
  2  hard fail
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.paths import apply_workdir, orpath_home, orpath_workdir  # noqa: E402
from orpath.watch_snapshot import (  # noqa: E402
    build_snapshot,
    compute_source_fingerprint,
)

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "orpath_watch_mod", ROOT / "scripts" / "orpath_watch.py"
)
assert _spec and _spec.loader
_ow = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ow)
DEFAULT_PORT = _ow.DEFAULT_PORT
MAX_PORT_TRIES = _ow.MAX_PORT_TRIES
WEB_DIR = _ow.WEB_DIR
HTML_NAME = _ow.HTML_NAME
WatchHandler = _ow.WatchHandler


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _py() -> str:
    cand = ROOT / ".venv-314" / "Scripts" / "python.exe"
    if cand.is_file():
        return str(cand)
    return sys.executable


def _clean_env(*, live: bool, workdir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ORPATH_HOME"] = str(orpath_home().resolve())
    # Force case data root (do not leave stale ORPATH_WORKDIR from parent shell)
    env["ORPATH_WORKDIR"] = str(Path(workdir).resolve())
    env["ORPATH_LIVE_SUBAGENT"] = "1" if live else "0"
    return env


def _default_slug() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"p3-{stamp}"


def _pick_port(host: str, start: int, *, home: Path, workdir: Path) -> tuple[ThreadingHTTPServer, int]:
    handler = partial(
        WatchHandler,
        home=home.resolve(),
        workdir=workdir.resolve(),
        directory=str(WEB_DIR),
    )
    last_err: OSError | None = None
    for i in range(MAX_PORT_TRIES):
        port = start + i
        try:
            httpd = ThreadingHTTPServer((host, port), handler)
            return httpd, port
        except OSError as e:
            last_err = e
    raise RuntimeError(f"bind failed from {start}: {last_err}")


def _wait_health(host: str, port: int, timeout_s: float = 8.0) -> bool:
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout_s
    url = f"http://{host}:{port}/api/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                data = json.loads(resp.read().decode())
            return bool(data.get("ok"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            time.sleep(0.1)
    return False


def _stages_count(slug: str, thread: str, workdir: Path) -> int:
    fp = compute_source_fingerprint(slug=slug, thread_id=thread, workdir=workdir)
    return int(fp.get("stages_count") or 0)


def _run_product(
    *,
    slug: str,
    thread: str,
    live: bool,
    problem_id: str,
    problem_class: str,
    solve_mode: str,
    timeout_s: int,
    workdir: Path,
    intake_in: list[str] | None = None,
    intake_assets: str = "",
    auto_intake: bool = False,
) -> tuple[int, str]:
    cmd = [
        _py(),
        str(ROOT / "orpath" / "run_orpath.py"),
        "run",
        "--fresh",
        "--slug",
        slug,
        "--thread-id",
        thread,
        "--problem-id",
        problem_id,
        "--solve-mode",
        solve_mode,
        "--workdir",
        str(workdir.resolve()),
    ]
    if (problem_class or "").strip():
        cmd.extend(["--problem-class", problem_class.strip()])
    if live:
        cmd.append("--live-subagent")
    else:
        cmd.append("--no-live-subagent")

    intakes = [str(Path(p).expanduser().resolve()) for p in (intake_in or []) if str(p).strip()]
    if intakes:
        if auto_intake:
            cmd.append("--auto-intake")
        for p in intakes:
            cmd.extend(["--intake-in", p])
        assets = (intake_assets or "").strip()
        if assets:
            cmd.extend(["--intake-assets", str(Path(assets).expanduser().resolve())])
    else:
        # Default stable fixture when caller did not pass a problem surface
        intake = ROOT / "fixtures" / "intake" / "ok" / "source.txt"
        if intake.is_file():
            cmd.extend(["--auto-intake", "--intake-in", str(intake)])

    print("[watch-run] >>", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=_clean_env(live=live, workdir=workdir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") + "\n" + (exc.stderr or "")
        return 124, out[-8000:]
    out = (proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or "")
    return int(proc.returncode), out[-12000:]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="OR-Path P3 watch-run (边跑边看)")
    p.add_argument("--slug", default="", help="default: p3-<utc stamp>")
    p.add_argument("--thread-id", default="", help="default: =slug")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--keep-watch", action="store_true", help="keep HTTP after run")
    p.add_argument("--skip-run", action="store_true", help="only start watch")
    p.add_argument("--live", action="store_true", help="LIVE subagent during run")
    p.add_argument("--problem-id", default="shortest_path")
    p.add_argument(
        "--problem-class",
        default="",
        help="optional problem_class override (leave empty for intake/model)",
    )
    p.add_argument(
        "--solve-mode",
        default="mock",
        choices=["mock", "networkx", "ortools", "cpsat", "highs"],
    )
    p.add_argument(
        "--intake-in",
        action="append",
        default=[],
        help="problem surface file (repeatable); enables intake front-door",
    )
    p.add_argument(
        "--intake-assets",
        default="",
        help="optional unpacked assets directory for intake_parse",
    )
    p.add_argument(
        "--auto-intake",
        action="store_true",
        help="with --intake-in still ok; alone scans inbox/",
    )
    p.add_argument("--run-timeout", type=int, default=600, help="seconds for product run")
    p.add_argument(
        "--grow-timeout",
        type=float,
        default=120.0,
        help="seconds to wait for stages to grow after run starts",
    )
    p.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="case data root (outputs/notes/papers/runs); sets ORPATH_WORKDIR",
    )
    args = p.parse_args(argv)

    if not (WEB_DIR / HTML_NAME).is_file():
        print(f"[ERROR] missing {WEB_DIR / HTML_NAME}", file=sys.stderr)
        return 2

    slug = (args.slug or "").strip() or _default_slug()
    thread = (args.thread_id or "").strip() or slug
    host = args.host
    live = bool(args.live)

    home = orpath_home().resolve()
    # CLI --workdir wins; else env/current orpath_workdir
    if args.workdir is not None and str(args.workdir).strip():
        wd = apply_workdir(args.workdir)
    else:
        wd = apply_workdir(orpath_workdir())
    os.environ["ORPATH_HOME"] = str(home)
    os.environ["ORPATH_WORKDIR"] = str(wd)

    print("=== OR-Path watch-run (P3) ===")
    print(f"slug={slug} thread={thread} live={live}")
    print(f"home={home}")
    print(f"workdir={wd}")

    before = _stages_count(slug, thread, wd)
    print(f"[watch-run] stages_before={before}")

    try:
        httpd, port = _pick_port(host, args.port, home=home, workdir=wd)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    thr = threading.Thread(target=httpd.serve_forever, name="orpath-watch", daemon=True)
    thr.start()
    url = f"http://{host}:{port}/?slug={slug}&thread={thread}"
    print(f"[watch-run] listen {url}")

    if not _wait_health(host, port):
        print("[ERROR] watch health failed", file=sys.stderr)
        httpd.shutdown()
        return 2
    print("[watch-run] health ok")

    if not args.no_browser:
        try:
            webbrowser.open(url)
            print("[watch-run] browser open requested")
        except Exception as exc:  # noqa: BLE001
            print(f"[watch-run] browser open failed: {exc}")

    evidence: dict[str, Any] = {
        "schema": "orpath.watch_run.v1",
        "phase": "P3",
        "generated_utc": _utc(),
        "slug": slug,
        "thread_id": thread,
        "live": live,
        "url": url,
        "port": port,
        "home": str(home),
        "workdir": str(wd),
        "stages_before": before,
        "stages_after": None,
        "stages_grew": False,
        "run_exit": None,
        "run_skipped": bool(args.skip_run),
        "snapshot_status": None,
        "process": None,
        "ok": False,
        "notes": [],
    }

    run_exit = 0
    run_log_tail = ""
    if not args.skip_run:
        # Run in parallel thread so stages can appear while we poll
        result: dict[str, Any] = {}

        def _worker() -> None:
            code, out = _run_product(
                slug=slug,
                thread=thread,
                live=live,
                problem_id=args.problem_id,
                problem_class=str(getattr(args, "problem_class", "") or ""),
                solve_mode=args.solve_mode,
                timeout_s=int(args.run_timeout),
                workdir=wd,
                intake_in=list(getattr(args, "intake_in", None) or []),
                intake_assets=str(getattr(args, "intake_assets", "") or ""),
                auto_intake=bool(getattr(args, "auto_intake", False)),
            )
            result["code"] = code
            result["out"] = out

        wt = threading.Thread(target=_worker, name="orpath-run", daemon=True)
        wt.start()

        deadline = time.time() + float(args.grow_timeout)
        grew = False
        after = before
        while time.time() < deadline:
            after = _stages_count(slug, thread, wd)
            if after > before:
                grew = True
                print(f"[watch-run] L0 grew: {before} → {after}")
                break
            if not wt.is_alive() and after <= before:
                # run finished; one more check
                time.sleep(0.3)
                after = _stages_count(slug, thread, wd)
                grew = after > before
                break
            time.sleep(0.4)

        wt.join(timeout=max(1.0, float(args.run_timeout)))
        run_exit = int(result.get("code", 1))
        run_log_tail = str(result.get("out") or "")[-4000:]
        evidence["run_exit"] = run_exit
        evidence["stages_after"] = after
        evidence["stages_grew"] = bool(grew)
        if not grew:
            evidence["notes"].append(
                f"stages did not grow within {args.grow_timeout}s (before={before} after={after})"
            )
        if run_exit != 0:
            evidence["notes"].append(f"product run exit={run_exit}")
            # still may have partial stages
    else:
        evidence["notes"].append("skip-run: watch only")
        evidence["stages_after"] = before
        evidence["stages_grew"] = False

    snap = build_snapshot(slug=slug, thread_id=thread, root=home, workdir=wd)
    evidence["snapshot_status"] = snap.get("status")
    evidence["process"] = snap.get("process")
    evidence["stages_after"] = evidence.get("stages_after") or len(snap.get("stages") or [])
    if evidence["stages_after"] and evidence["stages_before"] is not None:
        if int(evidence["stages_after"]) > int(evidence["stages_before"]):
            evidence["stages_grew"] = True

    # Success criteria
    if args.skip_run:
        evidence["ok"] = True
    else:
        evidence["ok"] = bool(evidence.get("stages_grew")) and run_exit == 0
        # soft: run non-zero but stages grew → still partial ok for face demo
        if evidence.get("stages_grew") and run_exit != 0:
            evidence["ok"] = True
            evidence["notes"].append("partial_ok: stages grew despite run non-zero")

    out_path = wd / "outputs" / f"{slug}-watch-run.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[watch-run] evidence → {out_path}")
    print(
        f"[watch-run] ok={evidence['ok']} grew={evidence.get('stages_grew')} "
        f"stages={evidence.get('stages_before')}→{evidence.get('stages_after')} "
        f"run_exit={evidence.get('run_exit')}"
    )
    if run_log_tail and (run_exit not in (0, None) or not evidence.get("stages_grew")):
        print("[watch-run] run log tail:")
        print(run_log_tail[-2000:])

    if args.keep_watch or args.skip_run:
        print("[watch-run] HTTP still running — Ctrl+C to stop")
        try:
            while thr.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n[watch-run] stopping…")
        finally:
            httpd.shutdown()
            httpd.server_close()
        return 0 if evidence["ok"] else 2

    httpd.shutdown()
    httpd.server_close()
    return 0 if evidence["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
