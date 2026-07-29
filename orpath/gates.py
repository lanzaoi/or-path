from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


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


def gate_claim_map(
    root: Path,
    draft: Path,
    solution: Path,
    *,
    whitelist: Path | None = None,
    research: Path | None = None,
    retrieval: Path | None = None,
    out: Path | None = None,
) -> tuple[bool, str]:
    args = ["--draft", str(draft), "--solution", str(solution)]
    if whitelist:
        args.extend(["--whitelist", str(whitelist)])
    if research:
        args.extend(["--research", str(research)])
    if retrieval:
        args.extend(["--retrieval", str(retrieval)])
    if out:
        args.extend(["--out", str(out)])
    code, stdout, err = run_py(root / "tools" / "r1_claim_map.py", args, root)
    return code == 0, (stdout + err).strip()


def gate_validate(
    root: Path, problem_id: str, solution: Path, out: Path
) -> tuple[bool, dict[str, Any], str]:
    code, stdout, err = run_py(
        root / "tools" / "validate_solution.py",
        [
            "--problem-id",
            problem_id,
            "--solution",
            str(solution),
            "--out",
            str(out),
        ],
        root,
    )
    data: dict[str, Any] = {}
    try:
        data = json.loads(stdout) if stdout.strip() else json.loads(out.read_text(encoding="utf-8"))
    except Exception:
        data = {"ok": False, "errors": [err or stdout]}
    return code == 0 and bool(data.get("ok")), data, (stdout + err).strip()


def solve(
    root: Path,
    problem_id: str,
    mode: str,
    problem_class: str | None = None,
    extra_args: list[str] | None = None,
) -> tuple[bool, dict, str]:
    if mode == "mock":
        script = "solve_mock.py"
        args = [problem_id]
    elif mode == "networkx":
        script = "solve_networkx.py"
        args = [problem_id]
    elif mode == "cpsat":
        script = "solve_cpsat.py"
        args = [problem_id]
        if extra_args:
            args.extend(extra_args)
    elif mode == "highs":
        script = "solve_highs.py"
        args = [problem_id]
        if extra_args:
            args.extend(extra_args)
    else:
        script = "solve_ortools.py"
        args = [problem_id]
        if problem_class:
            args.extend(["--class", problem_class])
        if extra_args:
            args.extend(extra_args)
    code, out, err = run_py(root / "tools" / script, args, root)
    if code != 0:
        return False, {}, (err or out).strip()
    try:
        return True, json.loads(out), out
    except json.JSONDecodeError:
        return False, {}, (err or out).strip()
