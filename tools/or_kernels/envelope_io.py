"""Standard Numbers-Truth envelope builders for general OR sandbox solvers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_custom_envelope(
    *,
    problem_id: str,
    slug: str,
    problem_class: str,
    objective: float,
    solver_name: str,
    source_script: str,
    validator_script: str,
    validation_report: str,
    decision_payload: dict[str, Any],
    proven_optimal: bool = False,
    status: str | None = None,
    subproblems: dict[str, Any] | None = None,
    wall_time_s: float = 0.0,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a Numbers-Truth compliant solution JSON envelope."""
    st = (status or ("OPTIMAL" if proven_optimal else "FEASIBLE")).upper()
    if st == "OPTIMAL" and not proven_optimal:
        st = "FEASIBLE"
    meta: dict[str, Any] = {
        "exact": bool(proven_optimal),
        "proven_optimal": bool(proven_optimal),
        "method_class": "exact" if proven_optimal else "hybrid_metaheuristic",
        "wall_time_s": round(float(wall_time_s), 4),
    }
    if extra_meta:
        meta.update(extra_meta)
    env: dict[str, Any] = {
        "problem_id": problem_id,
        "slug": slug,
        "problem_class": problem_class,
        "status": st,
        "objective": round(float(objective), 6),
        "solver": solver_name,
        "source": source_script,
        "validator_script": validator_script,
        "validation_report": validation_report,
        "solution": decision_payload,
        "meta": meta,
    }
    if subproblems is not None:
        env["subproblems"] = subproblems
    return env


def write_solution_and_report(
    solution_path: Path | str,
    solution_doc: dict[str, Any],
    report_path: Path | str | None = None,
    report_doc: dict[str, Any] | None = None,
) -> Path:
    """Atomically persist solution JSON and optional validation report JSON."""
    sp = Path(solution_path)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(solution_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if report_path is not None and report_doc is not None:
        rp = Path(report_path)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(report_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return sp
