#!/usr/bin/env python3
"""OR-Path doctor: core OR solver + validator + Web Studio health check."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT_HINT = Path(__file__).resolve().parents[1]
if str(ROOT_HINT) not in sys.path:
    sys.path.insert(0, str(ROOT_HINT))

from orpath.paths import orpath_home, orpath_workdir  # noqa: E402

MIN_PY = (3, 10)


def _ok(msg: str) -> None:
    print(f"  OK  {msg}")


def _bad(msg: str) -> None:
    print(f"  BAD {msg}")


def _warn(msg: str) -> None:
    print(f"  WARN {msg}")


def _hint_setup() -> None:
    print("  HINT fix: orpath.bat setup   (or: python scripts/bootstrap_orpath.py)")
    print("  HINT pip: .venv/bin/pip install -r requirements.txt")


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
        "highspy",
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

    # core assets layout (solvers, validators, Web Studio, launchers)
    for rel in (
        "START.bat",
        "START.sh",
        "tools/solve_ortools.py",
        "tools/solve_highs.py",
        "tools/solve_networkx.py",
        "tools/solve_polyomino.py",
        "tools/solve_polyomino_q3.py",
        "tools/solve_tube_cut_b2026.py",
        "tools/tube_optimization.py",
        "tools/solve_microgrid.py",
        "tools/microgrid_reporting.py",
        "tools/validate_solution.py",
        "scripts/b_tube_solve.py",
        "scripts/b_tube_geometry.py",
        "orpath/studio_analyzer.py",
        "orpath/watch_snapshot.py",
        "scripts/orpath_watch.py",
        "orpath/web/watch.html",
        "orpath/web/studio.html",
        "scripts/bootstrap_orpath.py",
        "VERSION",
    ):
        p = home / rel
        if p.is_file():
            _ok(rel)
        else:
            _bad(f"missing {rel}")
            errors.append(rel)

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
        _warn(".env missing — copy .env.example (Web Studio LLM needs XFYUN_API_KEY or DEEPSEEK_API_KEY)")
        warnings.append("env_missing")
    else:
        text = env_path.read_text(encoding="utf-8", errors="replace")
        has_xfyun = bool(re.search(r"(?m)^XFYUN_API_KEY=\s*\S+", text))
        has_deepseek = bool(re.search(r"(?m)^DEEPSEEK_API_KEY=\s*\S+", text))
        if has_xfyun or has_deepseek:
            _ok(".env has LLM API key configured")
        else:
            _warn("XFYUN_API_KEY / DEEPSEEK_API_KEY empty — deterministic solvers OK; LLM intake needs key")
            warnings.append("api_key")

    print()
    if errors:
        print("FAIL: orpath_doctor — install check incomplete:")
        for e in errors:
            print(f"  - {e}")
        _hint_setup()
        return 1

    if warnings:
        print(f"PASS: orpath_doctor ({len(warnings)} warning(s))")
    else:
        print("PASS: orpath_doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
