#!/usr/bin/env python3
"""OR-Path L1 bootstrap: venv + pip + .env + demo seed + doctor."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_PY = (3, 10)


def _home() -> Path:
    return Path(os.environ.get("ORPATH_HOME") or ROOT).resolve()


def _workdir() -> Path:
    return Path(os.environ.get("ORPATH_WORKDIR") or _home()).resolve()


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> int:
    print(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(cwd or _home()), env=env)
    return int(r.returncode)


def check_python(py: str) -> None:
    r = subprocess.run(
        [py, "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}')"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise SystemExit(f"[ERROR] cannot run python: {py}")
    parts = tuple(int(x) for x in r.stdout.strip().split(".")[:3])
    if parts[0] < MIN_PY[0] or (parts[0] == MIN_PY[0] and parts[1] < MIN_PY[1]):
        raise SystemExit(f"[ERROR] Python >= {MIN_PY[0]}.{MIN_PY[1]} required, got {r.stdout.strip()}")
    print(f"  OK python {r.stdout.strip()} ({py})")


def venv_python(home: Path) -> Path:
    for dname in (".venv", ".venv-314"):
        cand = (
            home / dname / "Scripts" / "python.exe"
            if os.name == "nt"
            else home / dname / "bin" / "python"
        )
        if cand.is_file():
            return cand
    if os.name == "nt":
        return home / ".venv" / "Scripts" / "python.exe"
    return home / ".venv" / "bin" / "python"


def ensure_venv(home: Path, bootstrap_py: str) -> Path:
    vp = venv_python(home)
    if vp.is_file():
        print(f"  OK venv exists: {vp}")
        return vp
    venv_dir = vp.parents[1]
    print(f"  -> creating {venv_dir.name}")
    code = _run([bootstrap_py, "-m", "venv", str(venv_dir)], cwd=home)
    if code != 0 or not vp.is_file():
        raise SystemExit("[ERROR] venv creation failed")
    return vp


def pip_install(vp: Path, home: Path) -> None:
    req = home / "requirements.txt"
    if not req.is_file():
        raise SystemExit(f"[ERROR] missing {req}")
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONPATH"] = ""
    env["PYTHONHOME"] = ""
    code = _run([str(vp), "-m", "pip", "install", "-U", "pip"], cwd=home, env=env)
    if code != 0:
        raise SystemExit("[ERROR] pip upgrade failed")
    code = _run([str(vp), "-m", "pip", "install", "-r", str(req)], cwd=home, env=env)
    if code != 0:
        raise SystemExit(f"[ERROR] pip failed for {req}")
    ocr = home / "requirements-ocr.txt"
    if ocr.is_file():
        code = _run([str(vp), "-m", "pip", "install", "-r", str(ocr)], cwd=home, env=env)
        if code != 0:
            print("[WARN] optional OCR deps failed (rapidocr/opencv) — PDF text OCR still ok; image OCR limited")
    print("  OK pip install")


def ensure_env_file(home: Path) -> None:
    env_path = home / ".env"
    example = home / ".env.example"
    if env_path.is_file():
        print("  OK .env exists")
        return
    if example.is_file():
        shutil.copy2(example, env_path)
        print("  -> created .env from .env.example — edit XFYUN_API_KEY / DEEPSEEK_API_KEY for LLM studio")
    else:
        print("[WARN] no .env.example; skip .env create")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OR-Path bootstrap (L1 setup)")
    ap.add_argument("--skip-npm", action="store_true", help="legacy no-op flag kept for CLI compatibility")
    ap.add_argument("--skip-pip", action="store_true")
    ap.add_argument("--force-seed", action="store_true")
    ap.add_argument("--no-seed", action="store_true")
    ap.add_argument("--no-doctor", action="store_true")
    ap.add_argument("--python", default="", help="bootstrap python for venv create")
    args = ap.parse_args(argv)

    home = _home()
    work = _workdir()
    os.environ.setdefault("ORPATH_HOME", str(home))
    os.environ.setdefault("ORPATH_WORKDIR", str(work))

    print("OR-Path setup / bootstrap")
    print(f"  ORPATH_HOME    = {home}")
    print(f"  ORPATH_WORKDIR = {work}")

    boot_py = args.python or sys.executable
    check_python(boot_py)

    if not args.skip_pip:
        vp = ensure_venv(home, boot_py)
        pip_install(vp, home)
    else:
        vp = venv_python(home)
        if not vp.is_file():
            vp = Path(boot_py)
        print("  skip pip")

    ensure_env_file(home)

    if not args.no_seed:
        seed_py = str(vp if vp.is_file() else boot_py)
        seed_script = home / "scripts" / "install_demo_seed.py"
        cmd = [seed_py, str(seed_script)]
        if args.force_seed:
            cmd.append("--force")
        code = _run(cmd, cwd=home)
        if code != 0:
            print("[WARN] seed install non-zero", code)

    if not args.no_doctor:
        doc_py = str(vp if vp.is_file() else boot_py)
        doc = home / "scripts" / "orpath_doctor.py"
        print("  -> running doctor")
        code = _run([doc_py, str(doc)], cwd=home)
        if code != 0:
            print("[ERROR] doctor FAILED — fix above, then re-run: orpath setup")
            return code

    print()
    print("PASS: orpath setup")
    print("  Next:")
    print("    orpath.bat doctor")
    print("    START.bat / ./START.sh       (launch Web Studio)")
    print("    orpath.bat demo-m0 --slug m0")
    print("    orpath.bat watch --slug m0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[ERROR] setup aborted: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
