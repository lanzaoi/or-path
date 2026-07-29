from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_py(script: Path, args: list[str], cwd: Path) -> tuple[int, str, str]:
    cmd = [sys.executable, str(script), *args]
    r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    return r.returncode, r.stdout, r.stderr


def gate_schema(root: Path, schema_path: Path) -> tuple[bool, str]:
    code, out, err = run_py(root / "tools" / "gate_schema.py", [str(schema_path)], root)
    return code == 0, (out + err).strip()


def gate_r2(root: Path, draft: Path, solution: Path) -> tuple[bool, str]:
    code, out, err = run_py(
        root / "tools" / "r2_numeric_check.py",
        ["--draft", str(draft), "--solution", str(solution)],
        root,
    )
    return code == 0, (out + err).strip()


def gate_r1(root: Path, draft: Path, whitelist: Path) -> tuple[bool, str]:
    code, out, err = run_py(
        root / "tools" / "r1_cite_check.py",
        ["--draft", str(draft), "--whitelist", str(whitelist)],
        root,
    )
    return code == 0, (out + err).strip()


def solve(root: Path, problem_id: str, mode: str) -> tuple[bool, dict, str]:
    script = "solve_mock.py" if mode == "mock" else "solve_ortools.py"
    code, out, err = run_py(root / "tools" / script, [problem_id], root)
    if code != 0:
        return False, {}, (err or out).strip()
    return True, json.loads(out), out
