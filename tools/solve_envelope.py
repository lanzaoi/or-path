#!/usr/bin/env python3
"""Solve envelope — single contract for all solve adapters (ADR-0002).

Required interface (what callers/tests learn):
  status, objective, source, problem_id
  + one of: path | tour | routes | stocks | plan | questions
  + meta.exact / meta.proven_optimal / meta.method_class

Adapters live under tools/solve_*.py; scripts/ are thin CLIs only.
"""
from __future__ import annotations

from typing import Any

REQUIRED_TOP = ("status", "objective", "source")
SOLUTION_SHAPE_KEYS = (
    "path",
    "tour",
    "routes",
    "stocks",
    "plan",
    "questions",
    "assignments",
    "bins",
)
METHOD_CLASSES = frozenset({"exact", "metaheuristic", "fixture", "heuristic"})


def ensure_meta(data: dict[str, Any], *, mode: str | None = None) -> dict[str, Any]:
    """Fill meta.* without inventing optimality for heuristic tracks."""
    out = dict(data)
    meta = dict(out.get("meta") or {})
    mode = (mode or out.get("solve_mode") or "").lower()

    if "exact" not in meta:
        if mode in ("networkx", "cpsat", "highs"):
            meta["exact"] = True
        elif mode in ("ortools", "tube", "tube_bfd"):
            meta["exact"] = False
        elif mode == "mock" or out.get("solver") == "fixture-mock":
            meta["exact"] = False
            meta.setdefault("method_class", "fixture")
        else:
            # inherit status OPTIMAL only if already proven track
            meta["exact"] = bool(meta.get("proven_optimal"))

    if "proven_optimal" not in meta:
        if meta.get("exact") and str(out.get("status", "")).upper() == "OPTIMAL":
            meta["proven_optimal"] = True
        else:
            meta["proven_optimal"] = False

    if "method_class" not in meta:
        if meta.get("proven_optimal"):
            meta["method_class"] = "exact"
        elif mode == "mock" or out.get("solver") == "fixture-mock":
            meta["method_class"] = "fixture"
        elif mode in ("tube", "tube_bfd") or "tube" in str(out.get("source", "")):
            meta["method_class"] = "heuristic"
        else:
            meta["method_class"] = "metaheuristic" if not meta.get("exact") else "exact"

    mc = str(meta.get("method_class") or "")
    if mc not in METHOD_CLASSES:
        meta["method_class"] = "metaheuristic"

    out["meta"] = meta
    return out


def validate_envelope(data: Any) -> tuple[bool, list[str]]:
    """Return (ok, errors). Does not recompute geometry — that is validate_solution."""
    errs: list[str] = []
    if not isinstance(data, dict):
        return False, ["envelope must be a JSON object"]

    for k in REQUIRED_TOP:
        if k not in data:
            errs.append(f"missing key: {k}")

    status = str(data.get("status", "")).upper()

    if "objective" in data:
        obj = data["objective"]
        if obj is None and status == "BLOCKED":
            pass
        elif not isinstance(obj, (int, float)) or isinstance(obj, bool):
            errs.append("objective must be number")

    if status and status not in {
        "OPTIMAL",
        "FEASIBLE",
        "INFEASIBLE",
        "ERROR",
        "UNKNOWN",
        "BLOCKED",
    }:
        errs.append(f"unusual status: {data.get('status')}")

    has_shape = any(k in data for k in SOLUTION_SHAPE_KEYS)
    # tube multi-question packs may nest under questions
    if not has_shape and not data.get("problem_id"):
        errs.append("missing problem_id and solution shape keys")

    meta = data.get("meta")
    if meta is not None:
        if not isinstance(meta, dict):
            errs.append("meta must be object")
        else:
            for bk in ("exact", "proven_optimal"):
                if bk in meta and not isinstance(meta[bk], bool):
                    errs.append(f"meta.{bk} must be bool")

    # Hard law: never claim proven optimal without exact
    if isinstance(data.get("meta"), dict):
        if data["meta"].get("proven_optimal") and not data["meta"].get("exact"):
            errs.append("meta.proven_optimal=true requires meta.exact=true")

    return len(errs) == 0, errs


def normalize_solution(data: dict[str, Any], *, mode: str | None = None) -> dict[str, Any]:
    """Apply meta defaults + light class inference."""
    out = ensure_meta(data, mode=mode)
    if "problem_class" not in out:
        if out.get("path"):
            out["problem_class"] = "shortest_path"
        elif out.get("tour"):
            out["problem_class"] = "tsp"
        elif out.get("routes"):
            out["problem_class"] = "vrp"
        elif "tube" in str(out.get("problem_id", "")) or "tube" in str(out.get("source", "")):
            out["problem_class"] = "tube_cut"
    return out
