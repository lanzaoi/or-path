#!/usr/bin/env python3
"""Phase 3.3 — custom MIP sandbox: generated solver + independent validator.

When ``or_analyst`` classifies an open contest question as a custom mixed
integer / combinatorial program with **no registered adapter**, the modeler
loads the ``general_or`` cartridge. This module implements the deterministic
heart of that closed loop:

  1. a structured mini-MIP instance JSON (decision vars + linear objective +
     linear constraints);
  2. ``custom_mip_solve`` — generates an independent CP-SAT solver script
     ``outputs/<slug>-custom-solver.py`` and an **independent recompute**
     validator script ``outputs/<slug>-custom-validate.py`` from the instance
     spec, runs the solver, then runs the validator;
  3. the solution envelope carries ``validation_report`` pointing at the
     deterministic report so ``tools/validate_solution.py`` (custom branch)
     can re-verify objective agreement without importing solver variables.

Numbers Truth: objective values come exclusively from the CP-SAT run; the
validator script is authored against the raw instance data, never importing
the solver.

Instance JSON schema (canonical mini-MIP):

    {
      "problem_id": "custom_res_alloc",
      "slug": "custom-res-alloc",
      "decision_vars": [
        {"id": "x", "kind": "int", "domain": [0, 5]},
        {"id": "y", "kind": "int", "domain": [0, 5]}
      ],
      "objective": {"sense": "min", "coeffs": {"x": 2.0, "y": 3.0}},
      "constraints": [
        {"id": "c1", "lhs": "2*x + y", "op": "<=", "rhs": 10.0}
      ]
    }
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

__all__ = ["parse_linear", "custom_mip_solve", "build_solver_script", "build_validator_script"]

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def parse_linear(expr: str) -> dict[str, float]:
    """Parse a linear expression ``2*x + y - 3`` → ``{"x": 2.0, "y": 1.0, "__const__": -3.0}``."""
    expr = (expr or "").replace(" ", "").replace("*", "")
    coeffs: dict[str, float] = {}
    i = 0
    n = len(expr)
    sign = 1.0
    while i < n:
        ch = expr[i]
        if ch == "+":
            sign = 1.0
            i += 1
            continue
        if ch == "-":
            sign = -1.0
            i += 1
            continue
        j = i
        while j < n and (expr[j].isdigit() or expr[j] in ".eE"):
            j += 1
        num_txt = expr[i:j]
        num = float(num_txt) if num_txt else 1.0  # bare var → coefficient 1
        if j >= n or not (expr[j].isalpha() or expr[j] == "_"):
            coeffs["__const__"] = coeffs.get("__const__", 0.0) + sign * num
            i = j
            continue
        k = j
        while k < n and (expr[k].isalnum() or expr[k] == "_"):
            k += 1
        var = expr[j:k]
        coeffs[var] = coeffs.get(var, 0.0) + sign * num
        sign = 1.0
        i = k
    return coeffs


def _vars_of(coeffs: dict[str, float]) -> list[str]:
    return [k for k in coeffs if k != "__const__"]


def build_solver_script(instance: dict[str, Any]) -> str:
    """Generate an independent OR-Tools CP-SAT solver script from the instance spec."""
    slug = instance.get("slug") or instance.get("problem_id") or "custom_mip"
    decision_vars = instance.get("decision_vars") or []
    obj = instance.get("objective") or {}
    constraints = instance.get("constraints") or []
    sense = str(obj.get("sense") or "min").lower()
    if sense not in {"min", "max"}:
        raise ValueError(f"objective sense must be min|max, got {sense!r}")

    lines: list[str] = []
    lines.append("#!/usr/bin/env python3")
    lines.append("# OR-Path Phase 3.3 custom_mip solver script (generated, no solver imports in validator)")
    lines.append("import json")
    lines.append("import math")
    lines.append("import os")
    lines.append("import sys")
    lines.append("from pathlib import Path")
    lines.append("")
    lines.append("OUT_DIR = Path(os.environ.get('CUSTOM_MIP_OUT_DIR', str(Path(__file__).resolve().parent)))")
    lines.append("instance = json.loads((OUT_DIR / 'instance.json').read_text(encoding='utf-8'))")
    lines.append("slug = instance.get('slug') or 'custom_mip'")
    lines.append("OUT_DIR.mkdir(parents=True, exist_ok=True)")
    lines.append("")
    lines.append("from ortools.sat.python import cp_model")
    lines.append("model = cp_model.CpModel()")
    lines.append("VARS = {}")
    for dv in decision_vars:
        var_id = str(dv["id"])
        dom = dv.get("domain") or [0, 1]
        kind = str(dv.get("kind") or "int")
        lb, ub = int(float(dom[0])), int(float(dom[1]))
        if kind == "bool":
            lb, ub = 0, 1
        lines.append(f"VARS['{var_id}'] = model.new_int_var({lb}, {ub}, '{var_id}')")
    lines.append("")
    lines.append("def eval_expr(expr):")
    lines.append("    total = float(expr.get('__const__') or 0.0)")
    lines.append("    for v, c in expr.items():")
    lines.append("        if v == '__const__':")
    lines.append("            continue")
    lines.append("        total += float(c) * VARS[v]")
    lines.append("    return total")
    lines.append("")
    lines.append("def coeffs_of(expr_str):")
    lines.append("    import re as _re")
    lines.append("    expr = expr_str.replace(' ', '').replace('*', '')")
    lines.append("    coeffs = {}")
    lines.append("    i = 0")
    lines.append("    n = len(expr)")
    lines.append("    sign = 1.0")
    lines.append("    while i < n:")
    lines.append("        ch = expr[i]")
    lines.append("        if ch == '+':")
    lines.append("            sign = 1.0; i += 1; continue")
    lines.append("        if ch == '-':")
    lines.append("            sign = -1.0; i += 1; continue")
    lines.append("        j = i")
    lines.append("        while j < n and (expr[j].isdigit() or expr[j] in '.eE'):")
    lines.append("            j += 1")
    lines.append("        num = float(expr[i:j]) if expr[i:j] else 1.0")
    lines.append("        if j >= n or not (expr[j].isalpha() or expr[j] == '_'):")
    lines.append("            coeffs['__const__'] = coeffs.get('__const__', 0.0) + sign * num")
    lines.append("            i = j; continue")
    lines.append("        k = j")
    lines.append("        while k < n and (expr[k].isalnum() or expr[k] == '_'):")
    lines.append("            k += 1")
    lines.append("        coeffs[expr[j:k]] = coeffs.get(expr[j:k], 0.0) + sign * num")
    lines.append("        sign = 1.0; i = k")
    lines.append("    return coeffs")
    lines.append("")
    lines.append("SCALE = 1000")
    lines.append("")
    lines.append("def scaled_expr(expr):")
    lines.append("    # CP-SAT needs integer coefficients: scale floats by SCALE.")
    lines.append("    terms = []")
    lines.append("    for v, c in expr.items():")
    lines.append("        if v == '__const__':")
    lines.append("            continue")
    lines.append("        coeff = int(round(float(c) * SCALE))")
    lines.append("        if coeff != 0:")
    lines.append("            terms.append(coeff * VARS[v])")
    lines.append("    const = int(round(float(expr.get('__const__') or 0.0) * SCALE))")
    lines.append("    return terms, const")
    lines.append("")
    lines.append("obj_expr = {k: float(v) for k, v in (instance['objective']['coeffs'] or {}).items()}")
    lines.append("obj_expr['__const__'] = float(instance['objective'].get('constant') or 0.0)")
    lines.append("obj_terms, obj_const = scaled_expr(obj_expr)")
    lines.append("model.minimize(sum(obj_terms) + obj_const)" if sense == "min" else "model.maximize(sum(obj_terms) + obj_const)")
    lines.append("")
    lines.append("for con in instance['constraints']:")
    lines.append("    coeffs = coeffs_of(con['lhs'])")
    lines.append("    terms, lhs_const = scaled_expr(coeffs)")
    lines.append("    lhs = sum(terms) + lhs_const")
    lines.append("    rhs = int(round(float(con['rhs']) * SCALE))")
    lines.append("    op = str(con.get('op') or '<=')")
    lines.append("    if op == '<=':")
    lines.append("        model.add(lhs <= rhs)")
    lines.append("    elif op == '>=':")
    lines.append("        model.add(lhs >= rhs)")
    lines.append("    elif op == '==':")
    lines.append("        model.add(lhs == rhs)")
    lines.append("    else:")
    lines.append("        raise ValueError(f'unknown constraint op {op!r}')")
    lines.append("")
    lines.append("solver = cp_model.CpSolver()")
    lines.append("solver.parameters.max_time_in_seconds = float(os.environ.get('CUSTOM_MIP_TIMEOUT', '30'))")
    lines.append("solver.parameters.num_search_workers = 1")
    lines.append("status = solver.solve(model)")
    lines.append("")
    lines.append("if status == cp_model.OPTIMAL:")
    lines.append("    status_name = 'OPTIMAL'")
    lines.append("elif status == cp_model.FEASIBLE:")
    lines.append("    status_name = 'FEASIBLE'")
    lines.append("else:")
    lines.append("    status_name = 'INFEASIBLE' if status == cp_model.INFEASIBLE else 'UNKNOWN'")
    lines.append("")
    lines.append("values = {dv['id']: (int(solver.value(VARS[dv['id']])) if dv.get('kind') != 'cont' else float(solver.value(VARS[dv['id']]))) for dv in instance['decision_vars']}")
    lines.append("obj_val = (sum(int(round(float(c) * SCALE)) * float(values[v]) for v, c in (instance['objective']['coeffs'] or {}).items() if float(c) != 0.0) + int(round(float(instance['objective'].get('constant') or 0.0) * SCALE))) / SCALE")
    lines.append("envelope = {")
    lines.append("    'problem_id': instance.get('problem_id'),")
    lines.append("    'problem_class': 'custom_mip',")
    lines.append("    'slug': instance.get('slug'),")
    lines.append("    'status': status_name,")
    lines.append("    'objective': round(float(obj_val), 6),")
    lines.append("    'solver': 'ortools-cpsat-custom-sandbox',")
    lines.append("    'source': 'tools/solve_dispatch',")
    lines.append("    'values': values,")
    lines.append("    'validation_report': f'outputs/{slug}-custom-validate.json',")
    lines.append("    'meta': {'exact': status_name == 'OPTIMAL', 'proven_optimal': status_name == 'OPTIMAL', 'method_class': 'exact' if status_name == 'OPTIMAL' else 'heuristic'},")
    lines.append("}")
    lines.append("sol_path = OUT_DIR / f'{instance.get('slug', 'custom_mip')}-solution.json'")
    lines.append("sol_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding='utf-8')")
    lines.append("print(json.dumps({'ok': status_name in ('OPTIMAL', 'FEASIBLE'), 'status': status_name, 'objective': envelope['objective'], 'values': values, 'solution_path': str(sol_path)}, ensure_ascii=False))")
    lines.append("")
    return "\n".join(lines)


def build_validator_script(instance: dict[str, Any]) -> str:
    """Generate the independent recompute validator (never imports the solver)."""
    lines: list[str] = []
    lines.append("#!/usr/bin/env python3")
    lines.append("# OR-Path Phase 3.3 custom_mip VALIDATOR — recomputes objective & constraints")
    lines.append("# strictly from the raw instance + solution values. No solver imports.")
    lines.append("import json")
    lines.append("import math")
    lines.append("import os")
    lines.append("from pathlib import Path")
    lines.append("")
    lines.append("OUT_DIR = Path(os.environ.get('CUSTOM_MIP_OUT_DIR', str(Path(__file__).resolve().parent)))")
    lines.append("instance = json.loads((OUT_DIR / 'instance.json').read_text(encoding='utf-8'))")
    lines.append("slug = instance.get('slug') or 'custom_mip'")
    lines.append("sol = json.loads((OUT_DIR / f'{slug}-solution.json').read_text(encoding='utf-8'))")
    lines.append("")
    lines.append("def coeffs_of(expr_str):")
    lines.append("    expr = expr_str.replace(' ', '').replace('*', '')")
    lines.append("    coeffs = {}")
    lines.append("    i = 0")
    lines.append("    n = len(expr)")
    lines.append("    sign = 1.0")
    lines.append("    while i < n:")
    lines.append("        ch = expr[i]")
    lines.append("        if ch == '+':")
    lines.append("            sign = 1.0; i += 1; continue")
    lines.append("        if ch == '-':")
    lines.append("            sign = -1.0; i += 1; continue")
    lines.append("        j = i")
    lines.append("        while j < n and (expr[j].isdigit() or expr[j] in '.eE'):")
    lines.append("            j += 1")
    lines.append("        num = float(expr[i:j]) if expr[i:j] else 1.0")
    lines.append("        if j >= n or not (expr[j].isalpha() or expr[j] == '_'):")
    lines.append("            coeffs['__const__'] = coeffs.get('__const__', 0.0) + sign * num")
    lines.append("            i = j; continue")
    lines.append("        k = j")
    lines.append("        while k < n and (expr[k].isalnum() or expr[k] == '_'):")
    lines.append("            k += 1")
    lines.append("        coeffs[expr[j:k]] = coeffs.get(expr[j:k], 0.0) + sign * num")
    lines.append("        sign = 1.0; i = k")
    lines.append("    return coeffs")
    lines.append("")
    lines.append("values = sol.get('values') or {}")
    lines.append("checks = []")
    lines.append("")
    lines.append("obj = instance['objective']")
    lines.append("recomputed = sum(float(c) * float(values[v]) for v, c in (obj['coeffs'] or {}).items()) + float(obj.get('constant') or 0.0)")
    lines.append("declared = float(sol['objective'])")
    lines.append("obj_ok = math.isclose(recomputed, declared, rel_tol=1e-6, abs_tol=1e-6)")
    lines.append("checks.append({'name': 'recompute_objective', 'ok': obj_ok, 'expected': declared, 'got': recomputed})")
    lines.append("")
    lines.append("for con in instance['constraints']:")
    lines.append("    coeffs = coeffs_of(con['lhs'])")
    lines.append("    lhs = sum(float(c) * float(values[v]) for v, c in coeffs.items() if v != '__const__') + float(coeffs.get('__const__') or 0.0)")
    lines.append("    rhs = float(con['rhs'])")
    lines.append("    op = str(con.get('op') or '<=')")
    lines.append("    if op == '<=':")
    lines.append("        ok = lhs <= rhs + 1e-6")
    lines.append("    elif op == '>=':")
    lines.append("        ok = lhs >= rhs - 1e-6")
    lines.append("    elif op == '==':")
    lines.append("        ok = math.isclose(lhs, rhs, rel_tol=1e-6, abs_tol=1e-6)")
    lines.append("    else:")
    lines.append("        ok = False")
    lines.append("    checks.append({'name': f'constraint_{con.get(\"id\")}', 'ok': bool(ok), 'lhs': lhs, 'op': op, 'rhs': rhs})")
    lines.append("")
    lines.append("# semantic domain check: variables inside declared domain")
    lines.append("for dv in instance['decision_vars']:")
    lines.append("    v = dv['id']")
    lines.append("    val = float(values.get(v, -1))")
    lines.append("    dom = dv.get('domain') or [0, 1]")
    lines.append("    checks.append({'name': f'domain_{v}', 'ok': float(dom[0]) <= val <= float(dom[1]), 'value': val, 'domain': dom})")
    lines.append("")
    lines.append("ok = all(c['ok'] for c in checks) and str(sol.get('status', '')).upper() in ('OPTIMAL', 'FEASIBLE')")
    lines.append("report = {'ok': ok, 'objective': declared, 'recomputed_objective': recomputed, 'slug': slug, 'problem_class': 'custom_mip', 'checks': checks}")
    lines.append("rep_path = OUT_DIR / f'{slug}-custom-validate.json'")
    lines.append("rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')")
    lines.append("print(json.dumps({'ok': ok, 'objective': declared, 'report': str(rep_path)}, ensure_ascii=False))")
    lines.append("")
    return "\n".join(lines)


def custom_mip_solve(
    *,
    instance_path: str | Path,
    out_dir: str | Path,
    timeout_sec: int = 60,
) -> dict[str, Any]:
    """Generate solver+validator scripts from the instance spec, run both.

    Returns ``{ok, status, objective, values, solution_path, validate_path,
    solver_script, validator_script}``.
    """
    instance_path = Path(instance_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    instance = json.loads(instance_path.read_text(encoding="utf-8"))
    slug = str(instance.get("slug") or instance.get("problem_id") or "custom_mip")
    instance.setdefault("slug", slug)
    # instance spec must live next to the scripts for reproducible paths
    inst_out = out_dir / "instance.json"
    inst_out.write_text(json.dumps(instance, ensure_ascii=False, indent=2), encoding="utf-8")

    solver_script = build_solver_script(instance)
    validator_script = build_validator_script(instance)
    solver_path = out_dir / f"{slug}-custom-solver.py"
    validate_path = out_dir / f"{slug}-custom-validate.py"
    solver_path.write_text(solver_script, encoding="utf-8")
    validate_path.write_text(validator_script, encoding="utf-8")

    env = dict(os.environ)
    env["CUSTOM_MIP_OUT_DIR"] = str(out_dir)
    env["CUSTOM_MIP_TIMEOUT"] = str(int(timeout_sec))
    try:
        proc = subprocess.run(
            [sys.executable, str(solver_path)],
            capture_output=True,
            text=True,
            timeout=max(int(timeout_sec), 10),
            env=env,
            cwd=str(out_dir.parent),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"solver timed out after {timeout_sec}s"}
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or proc.stdout or "solver failed").strip()[:2000]}
    try:
        sol_summary = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"ok": False, "error": f"solver stdout not JSON: {proc.stdout[:500]}"}

    try:
        proc2 = subprocess.run(
            [sys.executable, str(validate_path)],
            capture_output=True,
            text=True,
            timeout=max(int(timeout_sec), 10),
            env=env,
            cwd=str(out_dir.parent),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"validator timed out after {timeout_sec}s"}
    if proc2.returncode != 0:
        return {"ok": False, "error": (proc2.stderr or proc2.stdout or "validator failed").strip()[:2000]}
    try:
        val_summary = json.loads(proc2.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"ok": False, "error": f"validator stdout not JSON: {proc2.stdout[:500]}"}

    return {
        "ok": bool(sol_summary.get("ok") and val_summary.get("ok")),
        "status": sol_summary.get("status"),
        "objective": sol_summary.get("objective"),
        "values": sol_summary.get("values"),
        "solution_path": sol_summary.get("solution_path"),
        "validate_path": validate_path.resolve().as_posix(),
        "validate_report": f"outputs/{slug}-custom-validate.json",
        "solver_script": solver_path.resolve().as_posix(),
        "validator_script": validate_path.resolve().as_posix(),
        "validator_ok": bool(val_summary.get("ok")),
        "stdout": sol_summary,
        "validator_stdout": val_summary,
    }
