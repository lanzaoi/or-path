#!/usr/bin/env python3
"""Independent recompute plus five DIMO tamper attacks for a staff rostering solution.

The gate re-runs the strict rostering validator
(``tools/validators/extended_solvers.py::validate_staff_rostering``) on the
frozen candidate, adds a red-team-owned fairness-integrity check (the validator
deliberately does not recompute ``fairness_metrics`` from the roster), and then
injects five deliberate attacks (protocol ``tamper_tests``):

  1. ``understaffing_coverage_tamper``  — set an employee's shift on a tight
     day to ``Off`` so ``roster_daily_coverage`` fails
  2. ``shift_clash_tamper``            — extend an employee's roster with a
     spurious extra entry so ``roster_one_shift_per_day`` fails
  3. ``night_rest_violation_injection`` — force a Night shift on day ``d``
     followed by a Morning shift on day ``d+1`` so ``roster_night_shift_rest``
     fails
  4. ``consecutive_workday_overflow``   — force ``max_consecutive_days + 1``
     consecutive working days so ``roster_consecutive_days_limit`` fails
  5. ``fairness_metric_tamper``         — forge ``std_dev = -1.0`` (and a
     ``objective`` of ``0``) so the red-team ``fairness_metrics_integrity``
     check fails

Robustness contract
-------------------

The tamper builders never raise on an unexpected schema.  A solution whose
shape does not match the strict rostering envelope yields attacks with
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
import math
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from validators.extended_solvers import validate_staff_rostering  # noqa: E402

__all__ = [
    "ATTACK_NAMES",
    "SCHEMA",
    "build_attacks",
    "main",
    "recompute",
    "run_redteam",
]

#: Report schema written by this gate.
SCHEMA = "orpath.rostering_redteam.v1"

#: Canonical attack order (matches contracts/rostering_collaboration_v1.json).
ATTACK_NAMES: tuple[str, ...] = (
    "understaffing_coverage_tamper",
    "shift_clash_tamper",
    "night_rest_violation_injection",
    "consecutive_workday_overflow",
    "fairness_metric_tamper",
)

#: Working shifts (everything else is a rest day).
WORKING_SHIFTS: tuple[str, ...] = ("Morning", "Afternoon", "Night")

#: Numeric tolerance for the red-team's independent envelope comparisons.
_EPS = 1e-6

#: Tolerance for the reported vs. recomputed std_dev comparison (the solver
#: rounds to 4 decimals, so a small slack absorbs representation noise while
#: still catching forgeries like ``std_dev = -1.0``).
_STD_TOL = 1e-3


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


def _roster(payload: Any) -> dict[str, Any]:
    """Return the roster mapping when present, else ``{}``."""
    roster = _dig(payload, "roster")
    return roster if isinstance(roster, dict) and roster else {}


def _employee_names(roster: Any) -> list[str]:
    """Return roster employee names whose schedule is a list, sorted."""
    if not isinstance(roster, dict):
        return []
    return sorted(
        key for key, value in roster.items() if isinstance(value, list)
    )


def _num_days(payload: Any) -> int:
    """Derive the planning horizon the same way the validator does."""
    days = _dig(payload, "num_days")
    if _is_number(days) and int(days) > 0:
        return int(days)
    demands = _dig(payload, "shift_demands")
    if isinstance(demands, list):
        return len(demands)
    return 0


def _max_consecutive(payload: Any) -> int:
    """Derive ``max_consecutive_days`` with the validator's default of 5."""
    raw = _dig(payload, "max_consecutive_days")
    if _is_number(raw) and int(raw) >= 0:
        return int(raw)
    return 5


def _daily_demand(demands: Any, day: int) -> dict[str, Any]:
    """Return the demand dict for ``day`` (empty dict when absent/invalid)."""
    if not isinstance(demands, list):
        return {}
    if day < 0 or day >= len(demands):
        return {}
    entry = demands[day]
    return entry if isinstance(entry, dict) else {}


def _assigned_on(roster: Any, names: list[str], day: int, shift: str) -> list[str]:
    """Return employees assigned ``shift`` on ``day`` (skips short schedules)."""
    assigned: list[str] = []
    for emp in names:
        schedule = roster.get(emp)
        if isinstance(schedule, list) and day < len(schedule):
            if schedule[day] == shift:
                assigned.append(emp)
    return assigned


def _work_counts(roster: Any) -> dict[str, int]:
    """Recompute per-employee working-shift counts from the roster."""
    counts: dict[str, int] = {}
    for emp, schedule in roster.items():
        if isinstance(schedule, (list, tuple)):
            counts[emp] = sum(1 for s in schedule if s in WORKING_SHIFTS)
    return counts


# --------------------------------------------------------------------------- #
# Independent integrity checks (owned by the red team)
# --------------------------------------------------------------------------- #

def _fairness_metrics_integrity(payload: Any, fairness: dict[str, Any]) -> dict[str, Any]:
    """Recompute ``fairness_metrics`` from the roster and compare.

    The strict validator never touches ``fairness_metrics``; this red-team
    check does, so a forged ``std_dev`` (including the mathematically
    impossible ``-1.0``) or an objective inconsistent with
    ``max_shifts - min_shifts`` is rejected.  Every comparison tolerates a
    missing optional field but never a wrong one.
    """
    roster = _roster(payload)
    if not roster:
        return {
            "name": "fairness_metrics_integrity",
            "ok": False,
            "detail": "roster missing or empty; fairness cannot be recomputed",
        }
    counts = _work_counts(roster)
    if not counts:
        return {
            "name": "fairness_metrics_integrity",
            "ok": False,
            "detail": "no employee has a list roster; fairness cannot be recomputed",
        }

    vals = list(counts.values())
    mean = sum(vals) / len(vals)
    std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
    min_shifts, max_shifts = min(vals), max(vals)

    problems: list[str] = []

    rep_std = fairness.get("std_dev")
    rep_var = fairness.get("variance")
    if rep_std is None and rep_var is None:
        problems.append("fairness_metrics reports neither std_dev nor variance")
    if rep_std is not None:
        if not _is_number(rep_std):
            problems.append("std_dev missing or not a number")
        elif float(rep_std) < 0.0:
            problems.append(f"std_dev {rep_std} is negative — statistically impossible")
        elif abs(float(rep_std) - round(std, 4)) > _STD_TOL:
            problems.append(f"std_dev {rep_std} != recomputed {round(std, 4)}")
    if rep_var is not None:
        if not _is_number(rep_var):
            problems.append("variance missing or not a number")
        elif float(rep_var) < 0.0:
            problems.append(f"variance {rep_var} is negative — statistically impossible")
        elif abs(float(rep_var) - round(std * std, 4)) > _STD_TOL:
            problems.append(f"variance {rep_var} != recomputed {round(std * std, 4)}")

    for key, recomputed in (("min_shifts", min_shifts), ("max_shifts", max_shifts)):
        reported = fairness.get(key)
        if reported is None:
            continue
        if not _is_number(reported) or int(reported) != recomputed:
            problems.append(f"{key} {reported} != recomputed {recomputed}")

    reported_counts = fairness.get("total_shifts_per_employee")
    if isinstance(reported_counts, dict):
        for emp, recomputed in counts.items():
            reported = reported_counts.get(emp)
            if not _is_number(reported) or int(reported) != recomputed:
                problems.append(
                    f"total_shifts_per_employee[{emp}] {reported} != recomputed {recomputed}"
                )
        for emp in reported_counts:
            if emp not in counts:
                problems.append(f"total_shifts_per_employee[{emp}] not present in roster")

    objective = _dig(payload, "objective")
    if _is_number(objective) and abs(float(objective) - (max_shifts - min_shifts)) > _EPS:
        problems.append(
            f"objective {objective} != max_shifts - min_shifts {max_shifts - min_shifts}"
        )

    return {
        "name": "fairness_metrics_integrity",
        "ok": not problems,
        "detail": "; ".join(problems) if problems else None,
    }


def _independent_rostering_checks(payload: Any) -> list[dict[str, Any]]:
    """Return red-team-owned integrity checks beyond ``validate_staff_rostering``.

    Only one check is added — ``fairness_metrics_integrity`` — and only when
    the payload carries ``fairness_metrics`` (the solver envelope always does).
    It never raises and only adds checks; it cannot mask a validator failure.
    """
    checks: list[dict[str, Any]] = []
    fairness = _dig(payload, "fairness_metrics")
    if isinstance(fairness, dict):
        checks.append(_fairness_metrics_integrity(payload, fairness))
    return checks


# --------------------------------------------------------------------------- #
# Tamper builders
# --------------------------------------------------------------------------- #
#
# Each builder takes the frozen solution and returns a ``(payload, applied,
# reason)`` triple and must never raise.

def _attack_understaffing_coverage_tamper(
    solution: Any,
) -> tuple[Any, bool, str | None]:
    """Move one employee off a tight shift cell so daily coverage breaks.

    Prefers a (day, shift) cell where the assigned count exactly equals the
    demand (a single ``Off`` edit then drops coverage below demand); falls
    back to stripping an entire cell when no tight cell exists.  The edit
    preserves exactly one entry per day, so ``roster_one_shift_per_day``,
    night-rest and consecutive-days checks stay intact and only
    ``roster_daily_coverage`` fails.
    """
    changed = _copy(solution)
    roster = _roster(changed)
    if not roster:
        return changed, False, "roster missing or empty"
    names = _employee_names(roster)
    if not names:
        return changed, False, "no employee has a list roster"
    num_days = _num_days(changed)
    if num_days <= 0:
        return changed, False, "num_days missing or invalid"

    demands = _dig(changed, "shift_demands")

    # Preferred: a single-employee edit on a tight (day, shift) cell.
    for d in range(num_days):
        demand = _daily_demand(demands, d)
        for shift in WORKING_SHIFTS:
            need = demand.get(shift, 0)
            if not _is_number(need) or need <= 0:
                continue
            assigned = _assigned_on(roster, names, d, shift)
            if len(assigned) == int(need) and assigned:
                roster[assigned[0]][d] = "Off"
                return changed, True, None

    # Fallback: strip every employee from one positive-demand cell.
    for d in range(num_days):
        demand = _daily_demand(demands, d)
        for shift in WORKING_SHIFTS:
            need = demand.get(shift, 0)
            if not _is_number(need) or need <= 0:
                continue
            assigned = _assigned_on(roster, names, d, shift)
            if assigned:
                for emp in assigned:
                    roster[emp][d] = "Off"
                return changed, True, None

    return changed, False, "no positive shift demand to understaff"


def _attack_shift_clash_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    """Give an employee one spurious extra roster entry.

    Appending a trailing ``Off`` makes the schedule length ``num_days + 1``,
    so ``roster_one_shift_per_day`` fails while the first ``num_days`` entries
    (and therefore coverage, night-rest and consecutive-days checks) stay
    untouched.
    """
    changed = _copy(solution)
    roster = _roster(changed)
    if not roster:
        return changed, False, "roster missing or empty"
    names = _employee_names(roster)
    if not names:
        return changed, False, "no employee has a list roster"
    num_days = _num_days(changed)
    if num_days <= 0:
        return changed, False, "num_days missing or invalid"

    for emp in names:
        schedule = roster[emp]
        if len(schedule) != num_days:
            # The clash already exists; nothing further to inject.
            return changed, True, None
    roster[names[0]].append("Off")
    return changed, True, None


def _attack_night_rest_violation_injection(solution: Any) -> tuple[Any, bool, str | None]:
    """Force a Night shift followed by a Morning shift on consecutive days.

    Prefers extending an existing Night shift (one-entry edit); otherwise
    forces a fresh ``Night -> Morning`` pair on the first two days.  Either
    way ``roster_night_shift_rest`` fails for the edited employee.
    """
    changed = _copy(solution)
    roster = _roster(changed)
    if not roster:
        return changed, False, "roster missing or empty"
    names = _employee_names(roster)
    if not names:
        return changed, False, "no employee has a list roster"
    num_days = _num_days(changed)
    if num_days < 2:
        return changed, False, "num_days < 2"

    for emp in names:
        schedule = roster[emp]
        if len(schedule) < 2:
            continue
        for d in range(min(num_days, len(schedule)) - 1):
            if schedule[d] == "Night" and schedule[d + 1] != "Morning":
                schedule[d + 1] = "Morning"
                return changed, True, None

    # No existing Night shift to extend: force a brand-new violation pair.
    for emp in names:
        schedule = roster[emp]
        if len(schedule) < 2:
            continue
        for d in range(min(num_days, len(schedule)) - 1):
            if not (schedule[d] == "Night" and schedule[d + 1] == "Morning"):
                schedule[d] = "Night"
                schedule[d + 1] = "Morning"
                return changed, True, None

    return changed, False, "no employee with >= 2 roster entries"


def _attack_consecutive_workday_overflow(solution: Any) -> tuple[Any, bool, str | None]:
    """Force ``max_consecutive_days + 1`` consecutive working days.

    Setting a window of ``max_consecutive_days + 1`` days to ``Morning`` makes
    the edited employee's longest work run exceed the limit, so
    ``roster_consecutive_days_limit`` fails.
    """
    changed = _copy(solution)
    roster = _roster(changed)
    if not roster:
        return changed, False, "roster missing or empty"
    names = _employee_names(roster)
    if not names:
        return changed, False, "no employee has a list roster"
    num_days = _num_days(changed)
    if num_days <= 0:
        return changed, False, "num_days missing or invalid"

    max_consec = _max_consecutive(changed)
    window = max_consec + 1
    if num_days < window:
        return changed, False, f"num_days {num_days} < required window {window}"

    for emp in names:
        schedule = roster[emp]
        if len(schedule) < window:
            continue
        for start in range(num_days - window + 1):
            for offset in range(window):
                schedule[start + offset] = "Morning"
            return changed, True, None
    return changed, False, "no employee roster long enough for the overflow window"


def _attack_fairness_metric_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    """Forge an impossible fairness report (``std_dev = -1.0``, ``objective = 0``).

    A negative standard deviation is mathematically impossible, and an
    objective of ``0`` claims perfect fairness; the red-team
    ``fairness_metrics_integrity`` check recomputes both from the roster and
    must reject the forgery.
    """
    changed = _copy(solution)
    fairness = _dig(changed, "fairness_metrics")
    if not isinstance(fairness, dict):
        return changed, False, "fairness_metrics missing or not an object"
    if not _roster(changed):
        return changed, False, "roster missing; fairness cannot be recomputed"

    fairness["std_dev"] = -1.0

    objective = _dig(changed, "objective")
    if _is_number(objective):
        changed["objective"] = 0.0
    return changed, True, None


#: ``attack name -> builder`` in canonical order.
ATTACK_BUILDERS: dict[str, Callable[[Any], tuple[Any, bool, str | None]]] = {
    "understaffing_coverage_tamper": _attack_understaffing_coverage_tamper,
    "shift_clash_tamper": _attack_shift_clash_tamper,
    "night_rest_violation_injection": _attack_night_rest_violation_injection,
    "consecutive_workday_overflow": _attack_consecutive_workday_overflow,
    "fairness_metric_tamper": _attack_fairness_metric_tamper,
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
    """Run the strict rostering validator plus the red-team integrity checks.

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
        checks = validate_staff_rostering(problem_id, payload)
    except Exception as exc:  # noqa: BLE001 - malformed payload must not crash the gate
        return {
            "ok": False,
            "checks": [],
            "errors": [f"validator crashed on malformed payload: {type(exc).__name__}: {exc}"],
        }
    if not isinstance(checks, list):
        checks = []

    checks.extend(_independent_rostering_checks(payload))

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
    return "staff_rostering"


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
    parser = argparse.ArgumentParser(description="Red-team a frozen staff rostering solution")
    parser.add_argument(
        "--solution",
        type=Path,
        default=ROOT / "outputs" / "staff_rostering-solution.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "staff_rostering-redteam.json",
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
    print("PASS rostering_redteam_gate" if report["ok"] else "FAIL rostering_redteam_gate")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
