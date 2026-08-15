#!/usr/bin/env python3
"""OR-Path doctor: relocatable install health check (fail closed on multi-agent)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
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
    "or-tube-lead.md",
    "or-tube-geometry.md",
    "or-tube-q1q2.md",
    "or-tube-q3.md",
    "or-tube-q4.md",
    "or-tube-redteam.md",
]

MIN_PY = (3, 11)
MIN_NODE = (22, 19, 0)
PI_CLI = Path("runtime/node_modules/@earendil-works/pi-coding-agent/dist/cli.js")


def _ok(msg: str) -> None:
    print(f"  OK  {msg}")


def _bad(msg: str) -> None:
    print(f"  BAD {msg}")


def _warn(msg: str) -> None:
    print(f"  WARN {msg}")


def _hint_setup() -> None:
    print("  HINT fix: orpath.bat setup   (or: python scripts/bootstrap_orpath.py)")
    print("  HINT npm:  cd runtime && npm ci")
    print("  HINT pip:  .venv-314\\Scripts\\pip install -r requirements.txt")


def _node_path() -> tuple[str | None, bool]:
    node = shutil.which("node")
    if node:
        return node, True
    if os.name == "nt":
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        fallback = program_files / "nodejs" / "node.exe"
        if fallback.is_file():
            return str(fallback), False
    return None, False


def _node_ver(node: str | None) -> tuple[int, ...] | None:
    if not node:
        return None
    r = subprocess.run([node, "-p", "process.versions.node"], capture_output=True, text=True)
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", (r.stdout or "").strip())
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def main() -> int:
    home = orpath_home()
    work = orpath_workdir()
    print("OR-Path doctor")
    print(f"  ORPATH_HOME    = {home}")
    print(f"  ORPATH_WORKDIR = {work}")
    print(f"  env HOME set?  = {bool(os.environ.get('ORPATH_HOME'))}")
    print(f"  env WORKDIR?   = {bool(os.environ.get('ORPATH_WORKDIR'))}")
    print(f"  python         = {sys.version.split()[0]} ({sys.executable})")

    errors: list[str] = []
    warnings: list[str] = []

    # python version
    vi = sys.version_info
    if (vi.major, vi.minor) < MIN_PY:
        _bad(f"Python >= {MIN_PY[0]}.{MIN_PY[1]} required, got {vi.major}.{vi.minor}")
        errors.append("python_version")
    else:
        _ok(f"Python {vi.major}.{vi.minor}.{vi.micro}")

    # imports (product deps)
    for mod in (
        "langgraph",
        "langgraph.checkpoint.sqlite",
        "ortools",
        "networkx",
        "pydantic",
        "numpy",
        "pandas",
        "openpyxl",
    ):
        try:
            __import__(mod)
            _ok(f"import {mod}")
        except Exception as exc:  # noqa: BLE001
            _bad(f"import {mod}: {exc}")
            errors.append(f"import:{mod}")
            _hint_setup()

    # node
    node, node_from_path = _node_path()
    nv = _node_ver(node)
    pi_ok = (home / PI_CLI).is_file()
    if nv is None:
        if pi_ok:
            _warn("node not on PATH (ok if Pi runtime already installed)")
            warnings.append("node")
        else:
            _bad("node not on PATH — need Node >= 22.19 to npm install Pi")
            errors.append("node")
            _hint_setup()
    elif nv < MIN_NODE:
        msg = f"Node >= {'.'.join(map(str, MIN_NODE))} recommended, got {'.'.join(map(str, nv))}"
        if pi_ok:
            _warn(msg + " (Pi CLI present)")
            warnings.append("node_version")
        else:
            _bad(msg)
            errors.append("node_version")
    else:
        _ok(f"node {'.'.join(map(str, nv))} ({node})")
        if not node_from_path:
            _warn("Node is installed and system PATH is configured, but this process has a stale PATH snapshot; reopen the terminal/app")
            warnings.append("node_path_snapshot")

    # layout
    for rel in (
        "tools/solve_mock.py",
        "tools/validate_solution.py",
        "orpath/run_t2.py",
        "scripts/t2_gate.py",
        "scripts/t2_multiagent_isolation.py",
        str(PI_CLI).replace("\\", "/"),
        "pi.bat",
        "orpath/watch_snapshot.py",
        "scripts/orpath_watch.py",
        "orpath/web/watch.html",
        "scripts/bootstrap_orpath.py",
        "VERSION",
    ):
        p = home / rel
        if p.is_file():
            _ok(rel)
        else:
            _bad(f"missing {rel}")
            errors.append(rel)
            if "pi-coding-agent" in rel or rel.endswith("cli.js"):
                _hint_setup()

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

    # seed soft checks
    sol_btube = work / "outputs" / "live-btube-solution.json"
    sol_m0 = work / "outputs" / "m0-solution.json"
    seed_src = home / "demo" / "seed"
    if sol_btube.is_file():
        _ok("seed/face: outputs/live-btube-solution.json")
    else:
        _warn("no live-btube solution in workdir — run: orpath.bat setup  or  orpath.bat demo-seed")
        warnings.append("seed_live_btube")
        if (seed_src / "live-btube").is_dir():
            _warn(f"seed available at {seed_src / 'live-btube'}")
    if sol_m0.is_file():
        _ok("seed/m0: outputs/m0-solution.json")
    else:
        _warn("no m0 solution in workdir — setup/demo-seed or demo-m0")
        warnings.append("seed_m0")

    # .env soft
    env_path = home / ".env"
    if not env_path.is_file():
        _warn(".env missing — copy .env.example (LIVE needs DEEPSEEK_API_KEY)")
        warnings.append("env_missing")
    else:
        text = env_path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"(?m)^DEEPSEEK_API_KEY=\s*$", text) or "DEEPSEEK_API_KEY=" not in text:
            _warn("DEEPSEEK_API_KEY empty/missing — mock OK; LIVE multi-agent needs key")
            warnings.append("deepseek_key")
        else:
            _ok(".env has DEEPSEEK_API_KEY set")

    print()
    if errors:
        print("FAIL: orpath_doctor — multi-agent install incomplete:")
        for e in errors:
            print(f"  - {e}")
        _hint_setup()
        print("Do NOT open a random folder and cosplay roles.")
        print("Set ORPATH_HOME to this install root, or run orpath.bat from the install tree.")
        return 1

    if warnings:
        print(f"PASS: orpath_doctor ({len(warnings)} warning(s))")
    else:
        print("PASS: orpath_doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
