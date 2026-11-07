#!/usr/bin/env python3
"""Independent recompute plus five DIMO tamper attacks for a CFLP solution.

The gate re-runs the strict facility-location validator
(``tools/validators/extended_solvers.py::validate_facility_location``) on the
frozen candidate, adds two independent red-team-owned integrity checks (the
validator deliberately trusts the reported facility load and does not check
that every allocation points at an open facility), and then injects five
deliberate attacks (protocol ``tamper_tests``):

  1. ``facility_capacity_overflow_injection`` — raise an open facility's load
     above its capacity
  2. ``demand_undersatisfaction_tamper``     — set a customer's served fraction
     sum below 1.0
  3. ``closed_facility_allocation_cheat``    — point a customer at a facility
     that is not in ``open_facilities``
  4. ``cost_deflation_forgery``              — declare a total cost below the
     recomputed fixed-cost floor
  5. ``single_source_fractional_cheat``      — split a single-source customer
     allocation into two 0.5 fractions

Robustness contract
-------------------

The tamper builders never raise on an unexpected schema.  A solution whose
shape does not match the strict facility envelope yields attacks with
``applied: false`` and a human-readable ``reason`` instead of a
``KeyError``/``IndexError``/``TypeError``.  Because a tamper that could not be
constructed also cannot be demonstrated to be *blocked*, such an attack is
reported as ``rejected: false`` so the gate fails safely rather than silently
passing on an unverified assertion.

The tamper suite is factored into pure helpers so it can be unit tested
directly:

    build_attacks(solution)            -> [{attack, payload, applied, reason}]
    recompute(problem_id, payload)     -> validation report dict
    run_redteam(solution, problem_id)  -> report dict
    main(argv)                         -> exit code
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from validators.extended_solvers import validate_facility_location  # noqa: E402

__all__ = [
    "ATTACK_NAMES",
    "SCHEMA",
    "build_attacks",
    "main",
    "recompute",
    "run_redteam",
]

#: Report schema written by this gate.
SCHEMA = "orpath.facility_redteam.v1"

#: Canonical attack order (matches contracts/facility_collaboration_v1.json).
ATTACK_NAMES: tuple[str, ...] = (
    "facility_capacity_overflow_injection",
    "demand_undersatisfaction_tamper",
    "closed_facility_allocation_cheat",
    "cost_deflation_forgery",
    "single_source_fractional_cheat",
)

#: Numeric tolerance for the red-team's independent envelope comparisons.
_EPS = 1e-6


# --------------------------------------------------------------------------- #
# Defensive access helpers
# --------------------------------------------------------------------------- #

def _copy(solution: Any) -> Any:
    """Return a deep copy of ``solution``, degrading to ``{}`` on failure."""
    try:
        return deepcopy(solution)
    except Exception:  # noqa: BLE001 - never let copying abort the gate
        return {}


def _dig(container: Any, *path: Any) -> Any:
    """Follow ``path`` through nested dicts/sequences; ``None`` if unreachable.

    Every step tolerates a wrong container kind, a missing key and an
    out-of-range index, so a malformed solution can never raise here.
    """
    current = container
    for key in path:
        if isinstance(current, dict):
            if key not in current:
                return None
            current = current[key]
        elif isinstance(current, (list, tuple)):
            if isinstance(key, bool) or not isinstance(key, int):
                return None
            if key < 0 or key >= len(current):
                return None
            current = current[key]
        else:
            return None
    return current


def _is_number(value: Any) -> bool:
    """True for genuine ints/floats (``bool`` is excluded)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _allocation_rows(payload: Any) -> list[Any]:
    """Return the allocation rows (``allocations`` falling back to ``assignments``)."""
    if not isinstance(payload, dict):
        return []
    allocs = payload.get("allocations")
    if isinstance(allocs, list) and allocs:
        return allocs
    assigns = payload.get("assignments")
    if isinstance(assigns, list):
        return assigns
    return []


def _open_facility_ids(payload: Any) -> set[Any]:
    """Return the set of open facility ids declared in ``open_facilities``."""
    open_facs = payload.get("open_facilities") if isinstance(payload, dict) else None
    if not isinstance(open_facs, list):
        return set()
    ids: set[Any] = set()
    for fac in open_facs:
        if isinstance(fac, dict) and "facility_id" in fac:
            ids.add(fac["facility_id"])
    return ids


def _recomputed_fixed_cost(payload: Any) -> float:
    """Sum the reported fixed costs of the open facilities."""
    open_facs = payload.get("open_facilities") if isinstance(payload, dict) else None
    if not isinstance(open_facs, list):
        return 0.0
    total = 0.0
    for fac in open_facs:
        if isinstance(fac, dict) and _is_number(fac.get("fixed_cost")):
            total += float(fac["fixed_cost"])
    return total


# --------------------------------------------------------------------------- #
# Independent integrity checks (owned by the red team)
# --------------------------------------------------------------------------- #

def _independent_facility_checks(payload: Any) -> list[dict[str, Any]]:
    """Return red-team-owned integrity checks beyond ``validate_facility_location``.

    Two checks are added because the strict validator deliberately trusts the
    reported facility load and never verifies that every allocation points at
    an open facility:

    * ``network_topology_consistency`` — every ``served_by`` facility id must
      appear in ``open_facilities`` (catches the closed-facility cheat).
    * ``objective_costs_consistency`` — the declared objective must equal the
      envelope's own ``costs.total`` which must equal
      ``costs.fixed + costs.variable`` and the recomputed fixed-cost floor
      (catches cost deflation forgery).

    Both checks never raise and only add checks; they cannot mask a validator
    failure.
    """
    checks: list[dict[str, Any]] = []

    # -- network topology consistency -------------------------------------- #
    open_ids = _open_facility_ids(payload)
    rows = _allocation_rows(payload)

    if not open_ids:
        checks.append(
            {
                "name": "network_topology_consistency",
                "ok": False,
                "detail": "open_facilities missing or empty",
            }
        )
    elif not rows:
        checks.append(
            {
                "name": "network_topology_consistency",
                "ok": False,
                "detail": "allocations/assignments missing or empty",
            }
        )
    else:
        violations: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                violations.append("allocation row is not an object")
                continue
            customer = row.get("customer_id")
            for served in row.get("served_by") or []:
                if not isinstance(served, dict):
                    violations.append(f"customer {customer}: served_by entry not an object")
                    continue
                fac_id = served.get("facility_id")
                if fac_id not in open_ids:
                    violations.append(
                        f"customer {customer}: served_by closed facility {fac_id}"
                    )
        checks.append(
            {
                "name": "network_topology_consistency",
                "ok": not violations,
                "detail": "; ".join(violations) if violations else None,
            }
        )

    # -- objective / costs consistency ------------------------------------ #
    objective = payload.get("objective") if isinstance(payload, dict) else None
    costs = payload.get("costs") if isinstance(payload, dict) else None
    recomputed_fixed = _recomputed_fixed_cost(payload)

    problems: list[str] = []

    if not _is_number(objective):
        problems.append("objective missing or not a number")
    if not isinstance(costs, dict):
        problems.append("costs missing or not an object")
    else:
        total = costs.get("total")
        fixed = costs.get("fixed")
        variable = costs.get("variable")
        if not _is_number(total):
            problems.append("costs.total missing or not a number")
        else:
            if _is_number(objective) and abs(float(objective) - float(total)) > 1e-3:
                problems.append(
                    f"objective {objective} != costs.total {total}"
                )
            if _is_number(fixed) and _is_number(variable):
                if abs(float(total) - (float(fixed) + float(variable))) > 1e-3:
                    problems.append(
                        f"costs.total {total} != costs.fixed {fixed} + costs.variable {variable}"
                    )
            elif _is_number(fixed):
                if abs(float(total) - float(fixed)) > 1e-3:
                    problems.append(
                        f"costs.total {total} != costs.fixed {fixed} (variable missing)"
                    )
        if _is_number(fixed) and abs(float(fixed) - recomputed_fixed) > 1e-3:
            problems.append(
                f"costs.fixed {fixed} != recomputed open fixed sum {recomputed_fixed}"
            )

    if _is_number(objective) and abs(float(objective) - recomputed_fixed) < -1e-6:
        problems.append(
            f"objective {objective} below recomputed fixed-cost floor {recomputed_fixed}"
        )

    checks.append(
        {
            "name": "objective_costs_consistency",
            "ok": not problems,
            "detail": "; ".join(problems) if problems else None,
        }
    )
    return checks


# --------------------------------------------------------------------------- #
# Tamper builders
# --------------------------------------------------------------------------- #
#
# Each builder takes the frozen solution and returns a ``(payload, applied,
# reason)`` triple and must never raise.

def _attack_facility_capacity_overflow_injection(
    solution: Any,
) -> tuple[Any, bool, str | None]:
    """Raise an open facility's load above its capacity.

    The validator's ``facility_capacity_respected`` check requires
    ``load <= capacity + EPS`` for every open facility; setting
    ``load = capacity + 1`` must therefore be rejected.
    """
    changed = _copy(solution)
    open_facs = _dig(changed, "open_facilities")
    if not isinstance(open_facs, list) or not open_facs:
        return changed, False, "open_facilities missing or empty"

    for fac in open_facs:
        if not isinstance(fac, dict):
            continue
        capacity = fac.get("capacity")
        if not _is_number(capacity):
            continue
        fac["load"] = float(capacity) + 1.0
        return changed, True, None
    return changed, False, "no open facility with a numeric capacity"


def _attack_demand_undersatisfaction_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    """Set a customer's served fraction sum below 1.0.

    The validator's ``demand_fully_satisfied`` check requires every customer's
    ``sum(served_by fractions) == 1.0``; replacing the sole fraction with 0.7
    must be rejected.
    """
    changed = _copy(solution)
    rows = _allocation_rows(changed)
    if not rows:
        return changed, False, "allocations/assignments missing or empty"

    for row in rows:
        if not isinstance(row, dict):
            continue
        served = row.get("served_by")
        if not isinstance(served, list) or not served:
            continue
        first = served[0]
        if not isinstance(first, dict):
            continue
        first["fraction"] = 0.7
        return changed, True, None
    return changed, False, "no allocation with a served_by entry"


def _attack_closed_facility_allocation_cheat(solution: Any) -> tuple[Any, bool, str | None]:
    """Point a customer at a facility that is not open.

    The red-team ``network_topology_consistency`` check requires every
    ``served_by`` facility id to appear in ``open_facilities``; rewriting a
    customer's facility id to ``max(open_ids) + 1`` must be rejected.
    """
    changed = _copy(solution)
    open_ids = _open_facility_ids(changed)
    if not open_ids:
        return changed, False, "open_facilities missing or empty"
    rows = _allocation_rows(changed)
    if not rows:
        return changed, False, "allocations/assignments missing or empty"

    closed_id = max(int(fid) for fid in open_ids if _is_number(fid)) + 1

    for row in rows:
        if not isinstance(row, dict):
            continue
        served = row.get("served_by")
        if not isinstance(served, list) or not served:
            continue
        first = served[0]
        if not isinstance(first, dict):
            continue
        first["facility_id"] = closed_id
        return changed, True, None
    return changed, False, "no allocation with a served_by entry"


def _attack_cost_deflation_forgery(solution: Any) -> tuple[Any, bool, str | None]:
    """Declare a total cost below the recomputed fixed-cost floor.

    Forging ``objective - 100`` (and the parallel ``costs.total`` /
    ``metrics.objective`` fields, when present) must be rejected: the
    red-team ``objective_costs_consistency`` check requires
    ``costs.total == costs.fixed + costs.variable`` and the validator's
    ``facility_cost_positive`` check requires ``objective >= fixed_cost``.
    """
    changed = _copy(solution)
    objective = _dig(changed, "objective")
    if not _is_number(objective):
        return changed, False, "objective missing or not a number"

    recomputed_fixed = _recomputed_fixed_cost(changed)
    forged = min(float(objective) - 100.0, recomputed_fixed - 1.0)

    changed["objective"] = forged

    costs = _dig(changed, "costs")
    if isinstance(costs, dict) and _is_number(costs.get("total")):
        costs["total"] = forged

    metrics = _dig(changed, "metrics")
    if isinstance(metrics, dict) and _is_number(metrics.get("objective")):
        metrics["objective"] = forged

    return changed, True, None


def _attack_single_source_fractional_cheat(solution: Any) -> tuple[Any, bool, str | None]:
    """Split a single-source customer allocation into two 0.5 fractions.

    The validator's ``single_source_binary`` check requires exactly one served
    entry with fraction 1.0 when ``single_source`` is set; replacing the sole
    entry with two 0.5 entries must be rejected.  Only meaningful for
    single-source envelopes — a plain CFLP solution legitimately splits
    demand, so the attack reports ``applied: false`` there.
    """
    changed = _copy(solution)
    is_single_source = bool(changed.get("single_source")) or changed.get("mode") == "sscflp"
    if not is_single_source:
        return changed, False, "solution is not single-source"

    open_ids = _open_facility_ids(changed)
    if not open_ids:
        return changed, False, "open_facilities missing or empty"
    rows = _allocation_rows(changed)
    if not rows:
        return changed, False, "allocations/assignments missing or empty"

    open_id_list = sorted(int(fid) for fid in open_ids if _is_number(fid))

    for row in rows:
        if not isinstance(row, dict):
            continue
        served = row.get("served_by")
        if not isinstance(served, list) or len(served) != 1:
            continue
        first = served[0]
        if not isinstance(first, dict):
            continue
        original_id = first.get("facility_id")
        # Prefer two genuinely distinct open facilities; fall back to a
        # duplicated source when only one facility is open.
        if len(open_id_list) >= 2 and original_id in open_id_list:
            other = next(fid for fid in open_id_list if fid != original_id)
        else:
            other = original_id
        served.clear()
        served.append({"facility_id": original_id, "fraction": 0.5})
        served.append({"facility_id": other, "fraction": 0.5})
        return changed, True, None
    return changed, False, "no single-source allocation to split"


#: ``attack name -> builder`` in canonical order.
ATTACK_BUILDERS: dict[str, Callable[[Any], tuple[Any, bool, str | None]]] = {
    "facility_capacity_overflow_injection": _attack_facility_capacity_overflow_injection,
    "demand_undersatisfaction_tamper": _attack_demand_undersatisfaction_tamper,
    "closed_facility_allocation_cheat": _attack_closed_facility_allocation_cheat,
    "cost_deflation_forgery": _attack_cost_deflation_forgery,
    "single_source_fractional_cheat": _attack_single_source_fractional_cheat,
}


def build_attacks(solution: Any) -> list[dict[str, Any]]:
    """Build every tamper payload from ``solution`` without ever raising.

    Args:
        solution: The frozen candidate (any JSON-ish value).

    Returns:
        One record per entry in :data:`ATTACK_NAMES` with the keys ``attack``,
        ``payload``, ``applied`` and ``reason``.  ``applied`` is ``False`` when
        the underlying schema could not support the injection; ``reason``
        explains why.
    """
    attacks: list[dict[str, Any]] = []
    for name in ATTACK_NAMES:
        builder = ATTACK_BUILDERS[name]
        payload: Any = _copy(solution)
        applied = False
        reason: str | None = None
        try:
            payload, applied, reason = builder(solution)
        except Exception as exc:  # noqa: BLE001 - defensive by contract
            payload = _copy(solution)
            applied, reason = False, f"attack builder raised {type(exc).__name__}: {exc}"
        attacks.append(
            {
                "attack": name,
                "payload": payload,
                "applied": bool(applied),
                "reason": reason,
            }
        )
    return attacks


def recompute(problem_id: str, payload: Any) -> dict[str, Any]:
    """Run the strict facility-location validator plus the red-team integrity checks.

    Any validator crash on a malformed payload is converted into a rejection so
    the gate never propagates an exception.
    """
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "checks": [],
            "errors": ["payload is not a JSON object"],
        }
    try:
        checks = validate_facility_location(problem_id, payload)
    except Exception as exc:  # noqa: BLE001 - malformed payload must not crash the gate
        return {
            "ok": False,
            "checks": [],
            "errors": [f"validator crashed on malformed payload: {type(exc).__name__}: {exc}"],
        }
    if not isinstance(checks, list):
        checks = []

    checks.extend(_independent_facility_checks(payload))

    failed = [str(check.get("name")) for check in checks if not check.get("ok")]
    return {
        "ok": not failed,
        "checks": checks,
        "errors": [f"failed checks: {failed}"] if failed else [],
    }


def _problem_id(solution: Any, problem_id: str | None) -> str:
    if problem_id:
        return str(problem_id)
    if isinstance(solution, dict) and solution.get("problem_id"):
        return str(solution["problem_id"])
    return "beasley_cflp"


def run_redteam(solution: Any, problem_id: str | None = None) -> dict[str, Any]:
    """Recompute the frozen solution and replay the five tamper attacks."""
    pid = _problem_id(solution, problem_id)
    if not isinstance(solution, dict):
        original: dict[str, Any] = {
            "ok": False,
            "checks": [],
            "errors": ["solution is not a JSON object"],
        }
    else:
        original = recompute(pid, solution)

    results: list[dict[str, Any]] = []
    for attack in build_attacks(solution):
        name = attack["attack"]
        if not attack["applied"]:
            results.append(
                {
                    "attack": name,
                    "applied": False,
                    "rejected": False,
                    "reason": attack["reason"],
                    "failed_checks": [],
                }
            )
            continue
        report = recompute(pid, attack["payload"])
        failed_checks = [
            str(check.get("name"))
            for check in report.get("checks") or []
            if not check.get("ok")
        ]
        results.append(
            {
                "attack": name,
                "applied": True,
                "rejected": not bool(report.get("ok")),
                "failed_checks": failed_checks,
            }
        )

    passed = bool(original.get("ok")) and all(row["rejected"] for row in results)
    return {
        "schema": SCHEMA,
        "problem_id": pid,
        "original_recompute_ok": bool(original.get("ok")),
        "original_check_count": len(original.get("checks") or []),
        "attacks": results,
        "attack_count": len(results),
        "attacks_applied": sum(1 for row in results if row["applied"]),
        "ok": passed,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Red-team a frozen CFLP solution")
    parser.add_argument(
        "--solution",
        type=Path,
        default=ROOT / "outputs" / "beasley_cflp-solution.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "beasley_cflp-redteam.json",
    )
    args = parser.parse_args(argv)
    if not args.solution.is_file():
        print(f"FAIL: missing frozen solution {args.solution}", file=sys.stderr)
        return 1
    try:
        solution = json.loads(args.solution.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - malformed file must not crash
        print(f"FAIL: invalid JSON in {args.solution}: {exc}", file=sys.stderr)
        return 1

    report = run_redteam(solution)
    report["solution_path"] = str(args.solution.resolve())

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("PASS facility_redteam_gate" if report["ok"] else "FAIL facility_redteam_gate")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
