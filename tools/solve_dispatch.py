#!/usr/bin/env python3
"""Unified solve dispatch — one interface, many adapters (ADR-0002).

Callers (orpath.gates, CLIs) should use ``solve()`` / ``validate()`` here
instead of hard-coding tools/solve_*.py names.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# tools/ on path when run as script
_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from solve_envelope import normalize_solution, validate_envelope  # noqa: E402

# mode → adapter script under tools/
ADAPTER_SCRIPTS: dict[str, str] = {
    "mock": "solve_mock.py",
    "networkx": "solve_networkx.py",
    "cpsat": "solve_cpsat.py",
    "highs": "solve_highs.py",
    "ortools": "solve_ortools.py",
    "tube": "solve_tube_cut_b2026.py",
    "tube_bfd": "solve_tube_cut_b2026.py",
}


def _run_py(script: Path, args: list[str], cwd: Path) -> tuple[int, str, str]:
    cmd = [sys.executable, str(script), *args]
    r = subprocess.run(cmd, cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True)
    return r.returncode, r.stdout, r.stderr


def _build_args(
    mode: str,
    problem_id: str,
    problem_class: str | None,
    extra_args: list[str] | None,
) -> list[str]:
    extra = list(extra_args or [])
    if mode == "mock":
        return [problem_id, *extra]
    if mode == "networkx":
        return [problem_id, *extra]
    if mode in ("cpsat", "highs"):
        return [problem_id, *extra]
    if mode == "ortools":
        args = [problem_id]
        if problem_class:
            args.extend(["--class", problem_class])
        args.extend(extra)
        return args
    if mode in ("tube", "tube_bfd"):
        # full batch tool; problem_id unused by CLI today
        return list(extra)
    return [problem_id, *extra]


def _tube_envelope_from_outputs(root: Path, problem_id: str) -> dict[str, Any]:
    """Load q*-solution.json written by solve_tube_cut_b2026 into one envelope."""
    out_dir = root / "outputs" / "b-tube-cut"
    questions: dict[str, Any] = {}
    primary_obj = None
    status = "FEASIBLE"
    for name in ("q1", "q2", "q3", "q4"):
        p = out_dir / f"{name}-solution.json"
        if not p.is_file():
            continue
        q = json.loads(p.read_text(encoding="utf-8"))
        questions[name] = q
        if name == "q3" and "total_stock_length_mm" in q:
            primary_obj = q["total_stock_length_mm"]
        elif name == "q1" and primary_obj is None and "total_stock_length_mm" in q:
            primary_obj = q["total_stock_length_mm"]
        st = str(q.get("status", status)).upper()
        if st in ("FEASIBLE", "OPTIMAL"):
            status = st
    if primary_obj is None:
        # try DONE metrics file
        for alt in ("solution.json", "summary.json"):
            ap = out_dir / alt
            if ap.is_file():
                blob = json.loads(ap.read_text(encoding="utf-8"))
                if "objective" in blob:
                    primary_obj = blob["objective"]
                    questions["summary"] = blob
                    break
    if primary_obj is None:
        raise FileNotFoundError(
            f"tube outputs missing under {out_dir}; run tools/solve_tube_cut_b2026.py first"
        )
    env = {
        "problem_id": problem_id or "tube_cut_b2026",
        "problem_class": "tube_cut",
        "status": status,
        "objective": primary_obj,
        "source": "tools/solve_tube_cut_b2026.py",
        "solver": "tube-bfd",
        "questions": questions,
        "outputs_dir": str(out_dir),
        "meta": {
            "exact": False,
            "proven_optimal": False,
            "method_class": "heuristic",
            "claim": "FEASIBLE BFD/heuristic; not proven OPTIMAL",
        },
    }
    return normalize_solution(env, mode="tube")


def solve(
    root: Path,
    problem_id: str,
    mode: str,
    problem_class: str | None = None,
    extra_args: list[str] | None = None,
    *,
    normalize: bool = True,
) -> tuple[bool, dict[str, Any], str]:
    """Run adapter and return (ok, solution_dict, raw_text)."""
    root = Path(root)
    mode_l = (mode or "mock").lower().strip()
    # auto-route tube problem ids
    if mode_l not in ADAPTER_SCRIPTS:
        if "tube" in problem_id.lower() or (problem_class or "").lower() in {
            "tube_cut",
            "tube",
        }:
            mode_l = "tube"
        else:
            mode_l = "ortools" if mode_l not in ADAPTER_SCRIPTS else mode_l

    if mode_l not in ADAPTER_SCRIPTS:
        return False, {}, f"unknown solve mode: {mode}"

    script_name = ADAPTER_SCRIPTS[mode_l]
    script = root / "tools" / script_name
    if not script.is_file():
        return False, {}, f"adapter missing: {script}"

    args = _build_args(mode_l, problem_id, problem_class, extra_args)

    if mode_l in ("tube", "tube_bfd"):
        code, out, err = _run_py(script, args, root)
        raw = (out + "\n" + err).strip()
        if code != 0:
            return False, {}, raw or f"tube solver exit {code}"
        try:
            data = _tube_envelope_from_outputs(root, problem_id or "tube_cut_b2026")
        except Exception as exc:  # noqa: BLE001
            return False, {}, f"tube envelope: {exc}\n{raw[:500]}"
        if normalize:
            data = normalize_solution(data, mode=mode_l)
        ok_e, e_errs = validate_envelope(data)
        if not ok_e:
            return False, data, "envelope: " + "; ".join(e_errs)
        return True, data, raw

    code, out, err = _run_py(script, args, root)
    if code != 0:
        return False, {}, (err or out).strip()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return False, {}, (err or out).strip()
    if not isinstance(data, dict):
        return False, {}, "adapter returned non-object JSON"
    if normalize:
        data = normalize_solution(data, mode=mode_l)
        # stamp source if missing
        data.setdefault("source", f"tools/{script_name}")
        data.setdefault("problem_id", problem_id)
    ok_e, e_errs = validate_envelope(data)
    if not ok_e:
        return False, data, "envelope: " + "; ".join(e_errs)
    return True, data, out


def validate(
    root: Path,
    problem_id: str,
    solution: Path,
    out: Path,
) -> tuple[bool, dict[str, Any], str]:
    """Delegate to validate_solution.py (single validate seam)."""
    root = Path(root)
    code, stdout, err = _run_py(
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
        data = (
            json.loads(stdout)
            if stdout.strip()
            else json.loads(Path(out).read_text(encoding="utf-8"))
        )
    except Exception:
        data = {"ok": False, "errors": [err or stdout]}
    return code == 0 and bool(data.get("ok")), data, (stdout + err).strip()


def list_adapters() -> dict[str, str]:
    return dict(ADAPTER_SCRIPTS)


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="OR-Path unified solve dispatch (ADR-0002)")
    p.add_argument("problem_id")
    p.add_argument(
        "--mode",
        default="mock",
        choices=sorted(ADAPTER_SCRIPTS.keys()),
    )
    p.add_argument("--class", dest="problem_class", default="")
    p.add_argument("--root", type=Path, default=_ROOT)
    args, rest = p.parse_known_args(argv)
    ok, data, raw = solve(
        args.root,
        args.problem_id,
        args.mode,
        problem_class=args.problem_class or None,
        extra_args=rest or None,
    )
    if not ok:
        print(raw or json.dumps(data), file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
