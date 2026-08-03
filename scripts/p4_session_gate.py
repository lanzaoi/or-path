#!/usr/bin/env python3
"""P4 gate: ORPATH_PI_SESSION wiring + Watch tier2 surface.

Does NOT require live Pi API or pi-kanban install.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def test_docs_and_wiring() -> None:
    for rel in (
        "docs/p4-tier2-deep-look.md",
        "orpath/subagent_runtime.py",
        "orpath/watch_snapshot.py",
        "orpath/web/watch.html",
        "orpath.bat",
    ):
        if not (ROOT / rel).is_file():
            _fail(f"missing {rel}")
    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    if "p4-gate" not in bat and "p4_session" not in bat:
        _fail("orpath.bat missing p4-gate")
    html = (ROOT / "orpath/web/watch.html").read_text(encoding="utf-8", errors="replace")
    if "tier2" not in html and "Tier-2" not in html:
        _fail("watch.html missing Tier-2 UI")
    if "ORPATH_PI_SESSION" not in html and "pi_session" not in html:
        _fail("watch.html missing session badge markers")
    docs = (ROOT / "docs/p4-tier2-deep-look.md").read_text(encoding="utf-8", errors="replace")
    for n in ("ORPATH_PI_SESSION", "pi-kanban", "sessions"):
        if n not in docs:
            _fail(f"docs missing {n}")
    _ok("docs + bat + html wiring")


def test_session_flag_command() -> None:
    from orpath.subagent_runtime import (
        build_pi_command,
        pi_session_enabled,
        pi_sessions_root,
        resolve_no_session,
        spawn_lead,
        build_lead_prompt,
    )

    # Default CI: no_session
    os.environ.pop("ORPATH_PI_SESSION", None)
    assert resolve_no_session(None) is True
    assert pi_session_enabled() is False
    try:
        cmd0 = build_pi_command(ROOT, prompt="p4 gate hello")
    except RuntimeError as exc:
        # Pi missing in some sandboxes — still verify resolve + dry path
        _ok(f"build_pi_command skipped (env): {exc}")
        cmd0 = None
    if cmd0 is not None:
        if "--no-session" not in cmd0:
            _fail("default cmd must include --no-session")
        _ok("default --no-session present")

    # SESSION=1
    os.environ["ORPATH_PI_SESSION"] = "1"
    assert pi_session_enabled() is True
    assert resolve_no_session(None) is False
    try:
        cmd1 = build_pi_command(ROOT, prompt="p4 gate session on")
    except RuntimeError as exc:
        cmd1 = None
        _ok(f"SESSION=1 build skipped (env): {exc}")
    if cmd1 is not None:
        if "--no-session" in cmd1:
            _fail("ORPATH_PI_SESSION=1 must omit --no-session")
        _ok("SESSION=1 omits --no-session")

    # explicit override wins
    cmd_force = None
    try:
        cmd_force = build_pi_command(ROOT, prompt="x", no_session=True)
    except RuntimeError:
        pass
    if cmd_force is not None and "--no-session" not in cmd_force:
        _fail("explicit no_session=True must still add flag")
    if cmd_force is not None:
        _ok("explicit no_session=True wins")

    # dry_run lead headers
    os.environ["ORPATH_PI_SESSION"] = "1"
    brief = ROOT / "outputs" / ".agents" / "_p4_gate" / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text("p4 gate\n", encoding="utf-8")
    prompt = build_lead_prompt(
        stage="cite",
        slug="_p4_gate",
        brief_path=str(brief),
        required_agent="or-verifier",
        output_path="outputs/.drafts/_p4_gate.md",
    )
    try:
        res = spawn_lead(
            ROOT,
            slug="_p4_gate",
            stage="cite",
            prompt=prompt,
            dry_run=True,
            require_subagent_call=False,
        )
    except Exception as exc:  # noqa: BLE001
        _fail(f"dry spawn: {exc}")
    log = Path(res.log_path).read_text(encoding="utf-8", errors="replace")
    if "pi_session=on" not in log:
        _fail(f"dry log missing pi_session=on: {log[:400]}")
    if "sessions_root=" not in log:
        _fail("dry log missing sessions_root")
    if res.cmd and "--no-session" in res.cmd:
        _fail("dry SESSION=1 cmd still has --no-session")
    _ok(f"dry lead pi_session=on log={res.log_path}")

    # restore off
    os.environ["ORPATH_PI_SESSION"] = "0"
    res0 = spawn_lead(
        ROOT,
        slug="_p4_gate",
        stage="cite",
        prompt=prompt,
        dry_run=True,
        require_subagent_call=False,
    )
    log0 = Path(res0.log_path).read_text(encoding="utf-8", errors="replace")
    if "pi_session=off" not in log0:
        _fail("SESSION=0 dry log should say pi_session=off")
    if res0.cmd and "--no-session" not in res0.cmd:
        _fail("SESSION=0 cmd must include --no-session")
    _ok("SESSION=0 restores --no-session")

    root = pi_sessions_root()
    _ok(f"sessions_root={root}")


def test_watch_tier2() -> None:
    os.environ["ORPATH_PI_SESSION"] = "0"
    from orpath.watch_snapshot import build_snapshot

    snap = build_snapshot(slug="test", thread_id="test", workdir=ROOT, root=ROOT)
    t2 = snap.get("tier2") or {}
    if "sessions_root" not in t2:
        _fail("snapshot.tier2.sessions_root missing")
    if t2.get("pi_session_env") is not False:
        _fail("expected pi_session_env false when env=0")
    msgs = (snap.get("honesty") or {}).get("messages") or []
    if not any("tier2_session_off" in str(m) for m in msgs):
        _fail("honesty should mention tier2_session_off when SESSION=0")
    if "kanban_hint" not in t2:
        _fail("kanban_hint missing")
    _ok(
        f"tier2 sessions_root_exists={t2.get('sessions_root_exists')} "
        f"recent={len(t2.get('recent') or [])}"
    )

    os.environ["ORPATH_PI_SESSION"] = "1"
    snap1 = build_snapshot(slug="test", thread_id="test", workdir=ROOT, root=ROOT)
    if not (snap1.get("tier2") or {}).get("pi_session_env"):
        _fail("SESSION=1 should set tier2.pi_session_env")
    _ok("tier2.pi_session_env true when SESSION=1")
    os.environ["ORPATH_PI_SESSION"] = "0"


def main() -> int:
    print("=== p4_session_gate ===")
    print("ROOT =", ROOT)
    test_docs_and_wiring()
    test_session_flag_command()
    test_watch_tier2()
    print("PASS p4_session_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
