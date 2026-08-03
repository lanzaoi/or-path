from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _install_root() -> Path:
    # orpath/gates.py → parents[1] == install root
    return Path(__file__).resolve().parents[1]


def tools_dir(root: Path | None = None) -> Path:
    """Prefer root/tools when present; else install-home/tools (workdir split)."""
    if root is not None:
        cand = Path(root) / "tools"
        if cand.is_dir():
            return cand
    try:
        from orpath.paths import resolve_tools_dir

        return resolve_tools_dir(root)
    except Exception:  # noqa: BLE001
        return _install_root() / "tools"


def run_py(script: Path, args: list[str], cwd: Path) -> tuple[int, str, str]:
    cmd = [sys.executable, str(script), *args]
    r = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    return r.returncode, r.stdout, r.stderr


def gate_schema(root: Path, schema_path: Path) -> tuple[bool, str]:
    code, out, err = run_py(tools_dir(root) / "gate_schema.py", [str(schema_path)], root)
    return code == 0, (out + err).strip()


def gate_r2(root: Path, draft: Path, solution: Path) -> tuple[bool, str]:
    code, out, err = run_py(
        tools_dir(root) / "r2_numeric_check.py",
        ["--draft", str(draft), "--solution", str(solution)],
        root,
    )
    return code == 0, (out + err).strip()


def gate_r1(root: Path, draft: Path, whitelist: Path) -> tuple[bool, str]:
    code, out, err = run_py(
        tools_dir(root) / "r1_cite_check.py",
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
    code, stdout, err = run_py(tools_dir(root) / "r1_claim_map.py", args, root)
    return code == 0, (stdout + err).strip()


def gate_validate(
    root: Path, problem_id: str, solution: Path, out: Path
) -> tuple[bool, dict[str, Any], str]:
    """Validate seam — tools/solve_dispatch.validate (ADR-0002)."""
    tools = tools_dir(root)
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    from solve_dispatch import validate as _validate  # noqa: WPS433

    return _validate(root, problem_id, solution, out)


def solve(
    root: Path,
    problem_id: str,
    mode: str,
    problem_class: str | None = None,
    extra_args: list[str] | None = None,
) -> tuple[bool, dict, str]:
    """Solve seam — tools/solve_dispatch.solve (ADR-0002)."""
    tools = tools_dir(root)
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    from solve_dispatch import solve as _solve  # noqa: WPS433

    return _solve(
        root,
        problem_id,
        mode,
        problem_class=problem_class,
        extra_args=extra_args,
    )
