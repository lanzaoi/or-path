#!/usr/bin/env python3
"""OR-Path doctor: relocatable install health check (fail closed on multi-agent)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT_HINT = Path(__file__).resolve().parents[1]
if str(ROOT_HINT) not in sys.path:
    sys.path.insert(0, str(ROOT_HINT))

from orpath.paths import agents_dir, orpath_home, orpath_workdir, pi_settings_path  # noqa: E402

REQUIRED_AGENTS = [
    "or-orchestrator.md",
    "or-researcher.md",
    "or-modeler.md",
    "or-writer.md",
    "or-verifier.md",
    "or-reviewer.md",
]


def _ok(msg: str) -> None:
    print(f"  OK  {msg}")


def _bad(msg: str) -> None:
    print(f"  BAD {msg}")


def main() -> int:
    home = orpath_home()
    work = orpath_workdir()
    print("OR-Path doctor")
    print(f"  ORPATH_HOME    = {home}")
    print(f"  ORPATH_WORKDIR = {work}")
    print(f"  env HOME set?  = {bool(os.environ.get('ORPATH_HOME'))}")
    print(f"  env WORKDIR?   = {bool(os.environ.get('ORPATH_WORKDIR'))}")

    errors: list[str] = []

    # layout
    for rel in (
        "tools/solve_mock.py",
        "tools/validate_solution.py",
        "orpath/run_t2.py",
        "scripts/t2_gate.py",
        "scripts/t2_multiagent_isolation.py",
        "runtime/node_modules/@earendil-works/pi-coding-agent/dist/cli.js",
        "pi.bat",
        "orpath/watch_snapshot.py",
        "scripts/orpath_watch.py",
        "orpath/web/watch.html",
    ):
        p = home / rel
        if p.is_file():
            _ok(rel)
        else:
            _bad(f"missing {rel}")
            errors.append(rel)

    # agents
    ad = agents_dir(home)
    if not ad.is_dir():
        _bad(f"missing agents dir {ad}")
        errors.append("agents_dir")
    else:
        for name in REQUIRED_AGENTS:
            if (ad / name).is_file():
                _ok(f".pi/agents/{name}")
            else:
                _bad(f"missing .pi/agents/{name}")
                errors.append(name)

    # settings packages
    sp = pi_settings_path(home)
    if not sp.is_file():
        _bad(f"missing {sp}")
        errors.append("settings")
    else:
        try:
            data = json.loads(sp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            _bad(f"settings JSON: {exc}")
            errors.append("settings_json")
            data = {}
        pkgs = [str(x) for x in (data.get("packages") or [])]
        if any("pi-subagents" in x for x in pkgs):
            _ok(f"packages include pi-subagents ({pkgs})")
        else:
            _bad(f"pi-subagents not in packages: {pkgs}")
            errors.append("pi-subagents")

    # specs law present
    if (home / "specs" / "README.md").is_file():
        _ok("specs/README.md")
    else:
        _bad("specs/README.md missing")
        errors.append("specs")

    # workdir writable
    try:
        work.mkdir(parents=True, exist_ok=True)
        probe = work / ".orpath_doctor_write_probe"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
        _ok(f"workdir writable: {work}")
    except OSError as exc:
        _bad(f"workdir not writable: {exc}")
        errors.append("workdir")

    print()
    if errors:
        print("FAIL: orpath_doctor — multi-agent install incomplete:")
        for e in errors:
            print(f"  - {e}")
        print("Do NOT run OpenPi on a random folder and cosplay roles.")
        print("Set ORPATH_HOME to this install root, or run orpath.bat from the install tree.")
        return 1

    print("PASS: orpath_doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
