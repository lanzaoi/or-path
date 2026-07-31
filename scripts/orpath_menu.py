#!/usr/bin/env python3
"""Host-agnostic OR-Path control menu (no OpenPi dependency)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / "orpath.bat"
PY = ROOT / ".venv-314" / "Scripts" / "python.exe"
if not PY.is_file():
    PY = Path(sys.executable)


def _run(args: list[str]) -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONNOUSERSITE", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("ORPATH_LIVE_SUBAGENT", "1")
    if os.name == "nt" and BAT.is_file():
        cmd = ["cmd", "/c", str(BAT), *args]
    else:
        cmd = [str(PY), str(ROOT / "orpath" / "run_orpath.py"), *args]
    print(">>", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


def _open_dir(rel: str) -> None:
    p = ROOT / rel
    p.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(p))  # type: ignore[attr-defined]
    else:
        subprocess.call(["xdg-open", str(p)])


def main() -> int:
    print()
    print("=== OR-Path menu (GUI-agnostic) ===")
    print(f"ROOT = {ROOT}")
    print(f"LIVE = {os.environ.get('ORPATH_LIVE_SUBAGENT', '1 (default)')}")
    print()
    print("  1) Intake only — file path")
    print("  2) Intake auto — inbox/")
    print("  3) Run full   — auto-intake + product graph (live MA default ON)")
    print("  4) GUI demo   — fixture intake + mock solve")
    print("  5) Run cheap  — --no-live-subagent fixture SP")
    print("  6) Open evidence folders (agents + runs)")
    print("  7) Doctor")
    print("  0) Quit")
    print()
    choice = (input("Select: ").strip() or "0")

    if choice == "0":
        return 0
    if choice == "1":
        path = input("Path to problem file: ").strip().strip('"')
        slug = input("Slug [menu-intake]: ").strip() or "menu-intake"
        if not path:
            print("no path")
            return 2
        return _run(["intake", "--slug", slug, "--in", path])
    if choice == "2":
        slug = input("Slug [menu-inbox]: ").strip() or "menu-inbox"
        return _run(["intake-auto", "--slug", slug])
    if choice == "3":
        slug = input("Slug [menu-full]: ").strip() or "menu-full"
        return _run(
            [
                "run-full",
                "--slug",
                slug,
                "--thread-id",
                slug,
                "--solve-mode",
                "mock",
            ]
        )
    if choice == "4":
        return _run(["gui-demo"])
    if choice == "5":
        os.environ["ORPATH_LIVE_SUBAGENT"] = "0"
        return _run(
            [
                "run",
                "--fresh",
                "--no-live-subagent",
                "--slug",
                "menu-cheap",
                "--thread-id",
                "menu-cheap",
                "--problem-id",
                "shortest_path",
                "--solve-mode",
                "mock",
            ]
        )
    if choice == "6":
        _open_dir("outputs/.agents")
        _open_dir("runs")
        print("opened outputs/.agents and runs")
        return 0
    if choice == "7":
        return _run(["doctor"])
    print("unknown choice")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
