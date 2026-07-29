#!/usr/bin/env python3
"""Run Pi agent stage with deepseek-v4-pro; log stdout/stderr."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "runtime/node_modules/@earendil-works/pi-coding-agent/dist/cli.js"


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    load_env()
    if len(sys.argv) < 4:
        print("usage: run_pi_stage.py <agent> <prompt_file> <log_file>", file=sys.stderr)
        return 2
    agent = sys.argv[1]
    prompt_file = Path(sys.argv[2])
    log_file = Path(sys.argv[3])
    prompt = prompt_file.read_text(encoding="utf-8")
    model = os.environ.get("ORPATH_PI_MODEL", "deepseek-v4-pro")
    cmd = [
        "node",
        str(CLI),
        "-p",
        "--provider",
        "deepseek",
        "--model",
        model,
        "--no-session",
        "-a",
        agent,
        prompt,
    ]
    log_file.parent.mkdir(parents=True, exist_ok=True)
    print(f"RUN agent={agent} model={model}", flush=True)
    with log_file.open("w", encoding="utf-8", errors="replace") as lf:
        lf.write(f"$ {' '.join(cmd[:8])} ... prompt_len={len(prompt)}\n")
        lf.flush()
        p = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            timeout=540,
        )
        lf.write(p.stdout or "")
        lf.write("\n--- STDERR ---\n")
        lf.write(p.stderr or "")
        lf.write(f"\n--- EXIT {p.returncode} ---\n")
    print(f"EXIT {p.returncode} log={log_file}", flush=True)
    if p.stdout:
        print(p.stdout[-2000:])
    if p.stderr:
        print(p.stderr[-1000:], file=sys.stderr)
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
