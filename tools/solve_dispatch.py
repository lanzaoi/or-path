#!/usr/bin/env python3
"""Unified solve dispatch — one interface, many adapters (ADR-0002).

Callers (orpath.gates, CLIs) should use ``solve()`` / ``validate()`` here
instead of hard-coding tools/solve_*.py names.
"""
from __future__ import annotations

import contextlib
import importlib
import io
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
    # M2 phase 1: polyomino product registration
    "polyomino": "solve_polyomino.py",
    "polyomino_cover": "solve_polyomino.py",
    "poly": "solve_polyomino.py",
}


def _run_py(script: Path, args: list[str], cwd: Path) -> tuple[int, str, str]:
    cmd = [sys.executable, str(script), *args]
    r = subprocess.run(
        cmd, cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True
    )
    return r.returncode, r.stdout, r.stderr


def _try_in_proc(script_name: str, args: list[str]) -> tuple[bool, int, str, str]:
    mod_name = script_name.replace(".py", "")
    try:
        mod = importlib.import_module(mod_name)
        if hasattr(mod, "main"):
            buf_out = io.StringIO()
            buf_err = io.StringIO()
            with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
                code = mod.main(args)
            return True, code, buf_out.getvalue(), buf_err.getvalue()
    except Exception:
        pass
    return False, -1, "", ""


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
    if mode in ("polyomino", "polyomino_cover", "poly"):
        # solve_polyomino.py: positional problem_id + optional flags via extra_args
        return [problem_id, *extra]
    return [problem_id, *extra]


def _tube_out_dirs(root: Path) -> list[Path]:
    """Candidate dirs for tube q*-solution.json (workdir first, then install home).

    solve_tube_cut_b2026.py hardcodes OUT under the package install root; product
    runs often pass case workdir as ``root`` — must not miss install-home outputs.
    """
    root = Path(root).resolve()
    install = _ROOT.resolve()
    dirs: list[Path] = [root / "outputs" / "b-tube-cut"]
    alt = install / "outputs" / "b-tube-cut"
    if alt not in dirs:
        dirs.append(alt)
    return dirs


def _tube_envelope_from_outputs(root: Path, problem_id: str) -> dict[str, Any]:
    """Load q*-solution.json written by solve_tube_cut_b2026 into one envelope."""
    questions: dict[str, Any] = {}
    primary_obj = None
    status = "FEASIBLE"
    out_dir: Path | None = None
    for cand in _tube_out_dirs(root):
        if any((cand / f"{n}-solution.json").is_file() for n in ("q1", "q2", "q3", "q4")):
            out_dir = cand
            break
    if out_dir is None:
        out_dir = _tube_out_dirs(root)[0]
    for name in ("q1", "q2", "q3", "q4"):
        p = out_dir / f"{name}-solution.json"
        if not p.is_file():
            continue
        q = json.loads(p.read_text(encoding="utf-8"))
        questions[name] = q
        # prefer total_stock_length or total_stock_length_mm
        for key in ("total_stock_length_mm", "total_stock_length", "total_new_standard_stock_mm"):
            if name == "q3" and key in q and q[key] is not None:
                primary_obj = q[key]
                break
            if name == "q1" and primary_obj is None and key in q and q[key] is not None:
                primary_obj = q[key]
        st = str(q.get("status", status)).upper()
        if st in ("FEASIBLE", "OPTIMAL"):
            status = st
    if primary_obj is None:
        for alt in ("solution.json", "summary.json"):
            ap = out_dir / alt
            if ap.is_file():
                blob = json.loads(ap.read_text(encoding="utf-8"))
                if "objective" in blob:
                    primary_obj = blob["objective"]
                    questions["summary"] = blob
                    break
    if primary_obj is None:
        tried = ", ".join(str(d) for d in _tube_out_dirs(root))
        raise FileNotFoundError(
            f"tube outputs missing under [{tried}]; run tools/solve_tube_cut_b2026.py first"
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
            # Policy constants used by paper/R2 (not invented optima)
            "remnant_min_mm": 200.0,
            "stock_lengths_mm": [9000.0, 10000.0, 11000.0, 12000.0],
            "metrics": {
                "remnant_min_mm": 200.0,
                "stock_lengths_mm": [9000.0, 10000.0, 11000.0, 12000.0],
                "q1_total_stock_mm": (questions.get("q1") or {}).get("total_stock_length_mm")
                or (questions.get("q1") or {}).get("total_stock_length"),
                "q3_total_stock_mm": (questions.get("q3") or {}).get("total_stock_length_mm")
                or (questions.get("q3") or {}).get("total_stock_length"),
                "q4_total_stock_mm": (questions.get("q4") or {}).get("total_new_standard_stock_mm")
                or (questions.get("q4") or {}).get("total_stock_length_mm"),
            },
            "meta": {
                "exact": False,
                "proven_optimal": False,
                "method_class": "heuristic",
                "claim": "FEASIBLE BFD/heuristic; not proven OPTIMAL",
                "remnant_min_mm": 200.0,
                "stock_lengths_mm": [9000.0, 10000.0, 11000.0, 12000.0],
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
    pc_l = (problem_class or "").lower().strip()
    pid_l = (problem_id or "").lower()
    # auto-route domain adapters when mode is generic/unknown
    if mode_l not in ADAPTER_SCRIPTS:
        if "tube" in pid_l or pc_l in {"tube_cut", "tube", "cutting_stock", "cut_stock"}:
            mode_l = "tube"
        elif (
            "polyomino" in pid_l
            or pc_l in {"polyomino", "polyomino_cover", "poly", "polyomino_tiling", "tiling_cover"}
        ):
            mode_l = "polyomino"
        else:
            mode_l = "ortools"
    # class forces polyomino even if mode was ortools by default
    if mode_l == "ortools" and (
        pc_l in {"polyomino", "polyomino_cover", "poly"} or "polyomino" in pid_l
    ):
        mode_l = "polyomino"

    if mode_l not in ADAPTER_SCRIPTS:
        return False, {}, f"unknown solve mode: {mode}"

    script_name = ADAPTER_SCRIPTS[mode_l]
    # Adapters live next to this module (install tools/), not under case workdir.
    tools_dir = Path(__file__).resolve().parent
    script = tools_dir / script_name
    if not script.is_file():
        alt = root / "tools" / script_name
        if alt.is_file():
            script = alt
        else:
            return False, {}, f"adapter missing: {script}"

    args = _build_args(mode_l, problem_id, problem_class, extra_args)

    if mode_l in ("tube", "tube_bfd"):
        # Adapter uses install-root paths for CSV/OUT — run with install cwd.
        code, out, err = _run_py(script, args, _ROOT)
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
    handled, code, out, err = _try_in_proc(script_name, args)
    if not handled:
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
    tools_dir = Path(__file__).resolve().parent
    script = tools_dir / "validate_solution.py"
    if not script.is_file():
        script = root / "tools" / "validate_solution.py"
    code, stdout, err = _run_py(
        script,
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
