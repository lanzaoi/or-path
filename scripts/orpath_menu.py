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
    # Windows console: force UTF-8 when possible so Chinese/menu text shows.
    if os.name == "nt":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    print()
    print("=== OR-Path menu ===")
    print(f"ROOT = {ROOT}")
    print(f"LIVE = {os.environ.get('ORPATH_LIVE_SUBAGENT', '1 (default)')}")
    print()
    print("  1) Intake only - file path")
    print("  2) Intake auto - inbox/")
    print("  3) Run full   - auto-intake + product graph (live MA default ON)")
    print("  4) GUI demo   - fixture intake + mock solve")
    print("  5) Run cheap  - --no-live-subagent fixture SP")
    print("  6) Live Watch - 实时过程台 (product face)")
    print("  7) Watch-run  - 边跑边看 P3 (watch + mock run)")
    print("  8) Demo M0    - mock numbers + V0/M0 evidence checklist")
    print("  9) Open evidence folders (agents + runs) [debug only]")
    print("  d) Doctor")
    print("  0) Quit")
    print()
    try:
        choice = (input("Select: ").strip() or "0")
    except (EOFError, KeyboardInterrupt):
        print()
        return 0

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
        slug = input("Slug [test]: ").strip() or "test"
        thread = input(f"Thread-id [{slug}]: ").strip() or slug
        wd = input("Workdir [install default]: ").strip()
        args = ["watch", "--slug", slug, "--thread-id", thread]
        if wd:
            args.extend(["--workdir", wd])
        return _run(args)
    if choice == "7":
        slug = input("Slug [auto p3-...]: ").strip()
        live = (input("LIVE subagent? [y/N]: ").strip().lower() in {"y", "yes", "1"})
        keep = (input("Keep watch after run? [Y/n]: ").strip().lower() not in {"n", "no", "0"})
        wd = input("Workdir [install default]: ").strip()
        args = ["watch-run"]
        if slug:
            args.extend(["--slug", slug, "--thread-id", slug])
        if live:
            args.append("--live")
        if keep:
            args.append("--keep-watch")
        if wd:
            args.extend(["--workdir", wd])
        return _run(args)
    if choice == "8":
        slug = input("Slug [m0]: ").strip() or "m0"
        return _run(["demo-m0", "--slug", slug, "--no-live"])
    if choice == "9":
        _open_dir("outputs/.agents")
        _open_dir("runs")
        print("opened outputs/.agents and runs (debug; face = menu 6/7)")
        return 0
    if choice.lower() in {"d", "doctor"}:
        return _run(["doctor"])
    print("unknown choice")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
