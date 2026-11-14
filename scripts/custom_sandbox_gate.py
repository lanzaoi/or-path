#!/usr/bin/env python3
"""Numbers Truth 2.0 deterministic gate for custom & reduced optimization solutions.

Performs physical-isolation auditing and live independent recomputation without
any LLM involvement:

  1. ``ast_anti_cheat`` — parses ``<slug>-custom-validate.py`` via Python AST,
     rejecting any import of solver packages or solver scripts as well as
     no-op hardcoded ``{"ok": true}`` validators.
  2. ``independent_rerun`` — re-executes the validator script in a fresh
     subprocess and re-reads ``<slug>-custom-validate.json`` from disk.
  3. ``reduction_manifest_check`` — verifies ``reduction_manifest`` objective
     and original-domain constraints when a problem was reduced to a standard solver.
  4. ``optimality_honesty`` — forbids claiming ``status="OPTIMAL"`` when
     ``meta.proven_optimal`` is explicitly ``False``.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

BANNED_VALIDATOR_IMPORT_ROOTS: frozenset[str] = frozenset(
    {
        "ortools",
        "highspy",
        "pulp",
        "gurobipy",
        "cplex",
        "pyvrp",
        "alns",
        "dimod",
        "pyjobshop",
        "py3dbp",
        "rectpack",
    }
)


def _resolve_existing_path(
    raw: str | Path | None,
    *,
    root: Path,
    solution_path: Path | None = None,
) -> Path | None:
    if not raw:
        return None
    cand = Path(str(raw))
    if cand.is_file():
        return cand.resolve()
    search_bases: list[Path] = [root]
    if solution_path is not None:
        sp = solution_path.resolve()
        search_bases.extend([sp.parent, sp.parent.parent, sp.parent.parent.parent])
    for base in search_bases:
        joined = base / cand
        if joined.is_file():
            return joined.resolve()
    return None


def _derive_slug_candidates(slug: str, sol: dict[str, Any], solution_path: Path) -> list[str]:
    out: list[str] = []
    stem = solution_path.stem
    stem_slug = stem[: -len("-solution")] if stem.endswith("-solution") else ""
    for item in (slug, sol.get("slug"), sol.get("problem_id"), stem_slug):
        s = str(item or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _locate_validator_script(
    root: Path,
    slug: str,
    sol: dict[str, Any],
    solution_path: Path,
) -> Path | None:
    explicit = _resolve_existing_path(
        sol.get("validator_script"), root=root, solution_path=solution_path
    )
    if explicit is not None:
        return explicit

    for s in _derive_slug_candidates(slug, sol, solution_path):
        for name in (f"{s}-custom-validate.py", f"{s}-custom_validate.py"):
            for base in (solution_path.parent, root / "outputs"):
                cand = base / name
                if cand.is_file():
                    return cand.resolve()
    return None


def _locate_report_path(
    root: Path,
    slug: str,
    sol: dict[str, Any],
    solution_path: Path,
    explicit_report: Path | None,
) -> Path | None:
    if explicit_report is not None:
        return explicit_report
    val_rep = sol.get("validation_report")
    if val_rep:
        resolved = _resolve_existing_path(val_rep, root=root, solution_path=solution_path)
        if resolved is not None:
            return resolved
        cand = Path(str(val_rep))
        return cand if cand.is_absolute() else (root / cand)
    for s in _derive_slug_candidates(slug, sol, solution_path):
        for base in (solution_path.parent, root / "outputs"):
            cand = base / f"{s}-custom-validate.json"
            if cand.is_file():
                return cand.resolve()
    return solution_path.parent / f"{slug}-custom-validate.json"


def _is_banned_module_name(mod_name: str) -> bool:
    low = (mod_name or "").strip().lower()
    if not low:
        return False
    top = low.split(".")[0]
    if top in BANNED_VALIDATOR_IMPORT_ROOTS:
        return True
    if "custom_solver" in low or "custom-solver" in low:
        return True
    return False


def audit_validator_ast(script_path: Path) -> dict[str, Any]:
    """Statically audit a custom validator script with Python AST."""
    try:
        src = script_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"name": "ast_anti_cheat", "ok": False, "detail": f"unreadable script: {exc}"}

    try:
        tree = ast.parse(src, filename=str(script_path))
    except SyntaxError as exc:
        return {"name": "ast_anti_cheat", "ok": False, "detail": f"SyntaxError: {exc}"}

    banned_imports: list[str] = []
    has_arithmetic_or_compare = False
    has_file_read = False
    imports_scipy_solver = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_banned_module_name(alias.name):
                    banned_imports.append(alias.name)
                if alias.name.startswith("scipy.optimize"):
                    imports_scipy_solver = True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if _is_banned_module_name(mod):
                banned_imports.append(mod)
            if mod.startswith("scipy.optimize"):
                imports_scipy_solver = True
            for alias in node.names:
                if _is_banned_module_name(f"{mod}.{alias.name}" if mod else alias.name):
                    banned_imports.append(alias.name)
                if alias.name in {"milp", "linprog"}:
                    imports_scipy_solver = True
        elif isinstance(node, (ast.BinOp, ast.AugAssign, ast.Compare)):
            has_arithmetic_or_compare = True
        elif isinstance(node, ast.Call):
            fn = node.func
            fn_name = ""
            if isinstance(fn, ast.Name):
                fn_name = fn.id
            elif isinstance(fn, ast.Attribute):
                fn_name = fn.attr
            if fn_name in {"read_text", "read_bytes", "load", "loads", "open"}:
                has_file_read = True
            if fn_name in {"__import__", "import_module"} and node.args:
                arg0 = node.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                    if _is_banned_module_name(arg0.value) or "scipy.optimize" in arg0.value:
                        banned_imports.append(arg0.value)
            if fn_name in {"sum", "math"}:
                has_arithmetic_or_compare = True

    if banned_imports or imports_scipy_solver:
        found = sorted(set(banned_imports + (["scipy.optimize"] if imports_scipy_solver else [])))
        return {
            "name": "ast_anti_cheat",
            "ok": False,
            "detail": f"validator imports forbidden solver module(s): {found}",
        }
    if not has_file_read:
        return {
            "name": "ast_anti_cheat",
            "ok": False,
            "detail": "validator does not read instance/solution inputs from disk",
        }
    if not has_arithmetic_or_compare:
        return {
            "name": "ast_anti_cheat",
            "ok": False,
            "detail": "validator performs no arithmetic or constraint comparisons (likely hardcoded stub)",
        }
    return {"name": "ast_anti_cheat", "ok": True, "script": str(script_path)}


def _check_reduction_manifest(sol: dict[str, Any]) -> dict[str, Any]:
    rm = sol.get("reduction_manifest")
    if not isinstance(rm, dict):
        return {"name": "reduction_manifest_check", "ok": True, "skipped": True}

    declared = sol.get("objective")
    recomputed = rm.get("recomputed_original_objective")
    try:
        obj_ok = math.isclose(
            float(declared),
            float(recomputed),
            rel_tol=1e-5,
            abs_tol=1e-5,
        )
    except (TypeError, ValueError):
        return {
            "name": "reduction_manifest_check",
            "ok": False,
            "detail": (
                f"invalid reduction objective comparison declared={declared!r} "
                f"recomputed_original_objective={recomputed!r}"
            ),
        }
    if not obj_ok:
        return {
            "name": "reduction_manifest_check",
            "ok": False,
            "detail": f"reduction objective mismatch declared={declared} recomputed={recomputed}",
        }

    orig_cons = rm.get("original_constraints")
    if orig_cons is not None:
        if isinstance(orig_cons, list):
            if not orig_cons:
                return {
                    "name": "reduction_manifest_check",
                    "ok": False,
                    "detail": "reduction_manifest.original_constraints list must not be empty",
                }
            bad = [
                c
                for c in orig_cons
                if not (bool(c.get("ok")) if isinstance(c, dict) else bool(c))
            ]
            if bad:
                return {
                    "name": "reduction_manifest_check",
                    "ok": False,
                    "detail": f"failed original_constraints in reduction_manifest: {bad[:3]}",
                }
        elif isinstance(orig_cons, dict):
            if not orig_cons or not all(bool(v) for v in orig_cons.values()):
                return {
                    "name": "reduction_manifest_check",
                    "ok": False,
                    "detail": "failed or empty original_constraints mapping in reduction_manifest",
                }

    return {"name": "reduction_manifest_check", "ok": True, "recomputed": recomputed}


def _check_optimality_honesty(sol: dict[str, Any]) -> dict[str, Any]:
    status_up = str(sol.get("status") or "").strip().upper()
    meta = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
    if status_up == "OPTIMAL" and meta.get("proven_optimal") is False:
        return {
            "name": "optimality_honesty",
            "ok": False,
            "detail": "status='OPTIMAL' contradicts meta.proven_optimal=False (use status='FEASIBLE')",
        }
    return {"name": "optimality_honesty", "ok": True}


def verify_custom_sandbox(
    root: Path,
    slug: str,
    solution_path: Path,
    report_path: Path | None = None,
    require_script: bool = False,
) -> dict[str, Any]:
    """Run AST anti-cheat, fresh validator rerun, reduction audit & optimality check."""
    root = Path(root).resolve()
    solution_path = Path(solution_path).resolve()
    checks: list[dict[str, Any]] = []

    if not solution_path.is_file():
        checks.append({"name": "solution_exists", "ok": False, "detail": f"missing {solution_path}"})
        return {"ok": False, "checks": checks, "report": None, "validator_script": None}

    try:
        sol = json.loads(solution_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        checks.append({"name": "solution_json", "ok": False, "detail": f"invalid JSON: {exc}"})
        return {"ok": False, "checks": checks, "report": None, "validator_script": None}

    if not isinstance(sol, dict):
        checks.append({"name": "solution_json", "ok": False, "detail": "solution must be JSON object"})
        return {"ok": False, "checks": checks, "report": None, "validator_script": None}

    val_script = _locate_validator_script(root, slug, sol, solution_path)
    rep_path = _locate_report_path(root, slug, sol, solution_path, report_path)
    fresh_report: dict[str, Any] | None = None

    if val_script is not None and val_script.is_file():
        ast_res = audit_validator_ast(val_script)
        checks.append(ast_res)
        if ast_res["ok"]:
            env = dict(os.environ)
            env["ORPATH_WORKDIR"] = str(root)
            env.setdefault("CUSTOM_MIP_OUT_DIR", str(solution_path.parent))
            try:
                proc = subprocess.run(
                    [sys.executable, str(val_script)],
                    cwd=str(root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except subprocess.TimeoutExpired:
                checks.append(
                    {
                        "name": "independent_rerun",
                        "ok": False,
                        "detail": f"validator script timed out after 60s: {val_script.name}",
                    }
                )
                proc = None

            if proc is not None:
                if proc.returncode != 0:
                    err_tail = (proc.stderr or proc.stdout or "").strip()[-800:]
                    checks.append(
                        {
                            "name": "independent_rerun",
                            "ok": False,
                            "detail": f"validator exited {proc.returncode}: {err_tail}",
                        }
                    )
                elif rep_path is None or not rep_path.is_file():
                    checks.append(
                        {
                            "name": "independent_rerun",
                            "ok": False,
                            "detail": f"validator ran but report not found at {rep_path}",
                        }
                    )
                else:
                    try:
                        fresh_report = json.loads(rep_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError) as exc:
                        checks.append(
                            {
                                "name": "independent_rerun",
                                "ok": False,
                                "detail": f"fresh report invalid JSON: {exc}",
                            }
                        )
                        fresh_report = None

                    if isinstance(fresh_report, dict):
                        rep_ok = bool(fresh_report.get("ok"))
                        decl = sol.get("objective")
                        recomp = (
                            fresh_report.get("recomputed_objective")
                            if fresh_report.get("recomputed_objective") is not None
                            else fresh_report.get("objective")
                        )
                        try:
                            obj_agree = math.isclose(
                                float(decl), float(recomp), rel_tol=1e-5, abs_tol=1e-5
                            )
                        except (TypeError, ValueError):
                            obj_agree = False
                        checks.append(
                            {
                                "name": "independent_rerun",
                                "ok": bool(rep_ok and obj_agree),
                                "report_ok": rep_ok,
                                "declared_objective": decl,
                                "recomputed_objective": recomp,
                                "detail": (
                                    None
                                    if (rep_ok and obj_agree)
                                    else f"rerun mismatch/failure ok={rep_ok} declared={decl!r} recomputed={recomp!r}"
                                ),
                            }
                        )
    elif require_script:
        checks.append(
            {
                "name": "ast_anti_cheat",
                "ok": False,
                "detail": f"missing custom validator script for slug={slug!r}",
            }
        )
        checks.append(
            {
                "name": "independent_rerun",
                "ok": False,
                "detail": f"cannot rerun missing custom validator script for slug={slug!r}",
            }
        )

    if isinstance(sol.get("reduction_manifest"), dict):
        checks.append(_check_reduction_manifest(sol))

    checks.append(_check_optimality_honesty(sol))

    overall_ok = all(bool(c.get("ok")) for c in checks)
    return {
        "ok": overall_ok,
        "checks": checks,
        "report": fresh_report,
        "validator_script": str(val_script) if val_script is not None else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OR-Path Numbers Truth 2.0 custom sandbox gate")
    parser.add_argument("--workdir", type=Path, default=Path.cwd())
    parser.add_argument("--slug", required=True)
    parser.add_argument("--solution", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument(
        "--no-require-script",
        dest="require_script",
        action="store_false",
        default=True,
    )
    args = parser.parse_args(argv)

    root = args.workdir.resolve()
    sol_path = args.solution or (root / "outputs" / f"{args.slug}-solution.json")
    if not sol_path.is_absolute():
        sol_path = (root / sol_path).resolve()

    res = verify_custom_sandbox(
        root=root,
        slug=args.slug,
        solution_path=sol_path,
        report_path=args.report,
        require_script=bool(args.require_script),
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
