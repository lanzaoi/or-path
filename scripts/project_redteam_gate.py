#!/usr/bin/env python3
"""Independent recompute plus five DIMO tamper attacks for an RCPSP solution.

The gate re-runs the strict RCPSP validator
(``tools/validators/extended_solvers.py::validate_rcpsp``) on the frozen
candidate, adds an independent resource-usage-profile recompute owned by the
red team, and then injects five deliberate attacks (protocol
``tamper_tests``):

  1. ``resource_capacity_overflow``   — inflate an activity's demand so a time
                                        slot exceeds the renewable capacity
  2. ``activity_precedence_inversion``— move a successor to start before its
                                        predecessor ends
  3. ``duration_inconsistency_cheat`` — break ``end - start == duration``
  4. ``makespan_deflation``           — declare an objective below ``max(end)``
  5. ``activity_omission_tamper``     — drop an activity from the schedule

Robustness contract
-------------------

The tamper builders never raise on an unexpected schema.  A solution whose
shape does not match the strict RCPSP envelope yields attacks with ``applied:
false`` and a human-readable ``reason`` instead of a
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

from validators.extended_solvers import validate_rcpsp  # noqa: E402

__all__ = [
    "ATTACK_NAMES",
    "SCHEMA",
    "build_attacks",
    "main",
    "recompute",
    "run_redteam",
]

#: Report schema written by this gate.
SCHEMA = "orpath.project_redteam.v1"

#: Canonical attack order (matches contracts/project_collaboration_v1.json).
ATTACK_NAMES: tuple[str, ...] = (
    "resource_capacity_overflow",
    "activity_precedence_inversion",
    "duration_inconsistency_cheat",
    "makespan_deflation",
    "activity_omission_tamper",
)


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


def _precedence_pair(pair: Any) -> tuple[int, int] | None:
    """Normalize a precedence entry to ``(u, v)``; accepts dict or ``[u, v]``."""
    try:
        if isinstance(pair, dict):
            u = int(pair.get("u", pair.get("from")))
            v = int(pair.get("v", pair.get("to")))
        else:
            u, v = int(pair[0]), int(pair[1])
        return u, v
    except (TypeError, ValueError, KeyError, IndexError):
        return None


# --------------------------------------------------------------------------- #
# Independent integrity checks (owned by the red team)
# --------------------------------------------------------------------------- #

def _independent_rcpsp_checks(payload: Any) -> list[dict[str, Any]]:
    """Return red-team-owned integrity checks beyond ``validate_rcpsp``.

    The one check here is the resource-usage timeline profile, which
    ``validate_rcpsp`` does *not* recompute: it compares the declared
    ``resource_usage`` against an independent recomputation from the raw
    schedule.  This never raises and only adds checks; it cannot mask a
    validator failure.
    """
    checks: list[dict[str, Any]] = []
    schedule = payload.get("schedule") if isinstance(payload, dict) else None
    declared = payload.get("resource_usage") if isinstance(payload, dict) else None

    if not isinstance(schedule, list) or not schedule:
        checks.append(
            {
                "name": "rcpsp_resource_usage_profile",
                "ok": False,
                "detail": "schedule missing or empty",
            }
        )
        return checks

    if not isinstance(declared, dict) or not declared:
        checks.append(
            {
                "name": "rcpsp_resource_usage_profile",
                "ok": True,
                "detail": "no declared resource_usage; skipped",
            }
        )
        return checks

    capacities = payload.get("resource_capacities")
    n_res = payload.get("num_resources")
    if not isinstance(n_res, int) or isinstance(n_res, bool):
        n_res = len(capacities) if isinstance(capacities, list) else 0

    starts: dict[int, int] = {}
    ends: dict[int, int] = {}
    demands: dict[int, list[int]] = {}
    horizon = 0
    for entry in schedule:
        if not isinstance(entry, dict):
            continue
        try:
            aid = int(entry["activity_id"])
            start = int(entry["start"])
            end = int(entry["end"])
        except (TypeError, ValueError, KeyError):
            continue
        starts[aid] = start
        ends[aid] = end
        raw_demands = entry.get("demands")
        demands[aid] = [int(d) for d in raw_demands] if isinstance(raw_demands, list) else []
        horizon = max(horizon, end)

    recomputed: dict[str, list[int]] = {}
    for r in range(n_res):
        loads = [0] * horizon
        for aid in starts:
            demand = demands[aid][r] if r < len(demands[aid]) else 0
            if demand > 0:
                for t in range(starts[aid], ends[aid]):
                    loads[t] += demand
        recomputed[f"R{r}"] = loads

    match = recomputed == declared
    checks.append(
        {
            "name": "rcpsp_resource_usage_profile",
            "ok": match,
            "detail": None if match else "declared resource_usage != recomputed profile",
        }
    )
    return checks


# --------------------------------------------------------------------------- #
# Tamper builders
# --------------------------------------------------------------------------- #
#
# Each builder takes the frozen solution and returns a ``(payload, applied,
# reason)`` triple and must never raise.

def _attack_resource_capacity_overflow(solution: Any) -> tuple[Any, bool, str | None]:
    """Inflate an activity's demand so some time slot exceeds capacity."""
    changed = _copy(solution)
    schedule = _dig(changed, "schedule")
    if not isinstance(schedule, list) or not schedule:
        return changed, False, "schedule missing or empty"
    capacities = _dig(changed, "resource_capacities")
    if not isinstance(capacities, list) or not capacities:
        return changed, False, "resource_capacities missing or empty"

    for entry in schedule:
        if not isinstance(entry, dict):
            continue
        demands = entry.get("demands")
        if not isinstance(demands, list) or not demands:
            continue
        start = entry.get("start")
        end = entry.get("end")
        if not _is_number(start) or not _is_number(end):
            continue
        if int(end) - int(start) <= 0:
            continue
        resource = 0
        cap = capacities[resource] if resource < len(capacities) else 0
        cap = int(cap) if _is_number(cap) else 0
        demands[resource] = cap + 1
        return changed, True, None
    return changed, False, "no activity with positive duration and demands"


def _attack_activity_precedence_inversion(solution: Any) -> tuple[Any, bool, str | None]:
    """Move a successor earlier so it starts before its predecessor ends."""
    changed = _copy(solution)
    schedule = _dig(changed, "schedule")
    if not isinstance(schedule, list) or not schedule:
        return changed, False, "schedule missing or empty"
    precedences = _dig(changed, "precedences")
    if not isinstance(precedences, list):
        return changed, False, "precedences missing or not a list"

    by_id: dict[int, dict[str, Any]] = {}
    for entry in schedule:
        if isinstance(entry, dict):
            try:
                by_id[int(entry["activity_id"])] = entry
            except (TypeError, ValueError, KeyError):
                continue

    for pair in precedences:
        uv = _precedence_pair(pair)
        if uv is None:
            continue
        u, v = uv
        predecessor = by_id.get(u)
        successor = by_id.get(v)
        if not isinstance(predecessor, dict) or not isinstance(successor, dict):
            continue
        end_u = predecessor.get("end")
        duration_v = successor.get("duration")
        start_v = successor.get("start")
        if not _is_number(end_u) or not _is_number(duration_v) or not _is_number(start_v):
            continue
        if int(end_u) <= 0:
            continue
        if int(start_v) < int(end_u):
            continue  # already inverted (not a valid clean solution)
        new_start = int(end_u) - 1
        successor["start"] = new_start
        successor["end"] = new_start + int(duration_v)
        return changed, True, None
    return changed, False, "no schedulable precedence pair available"


def _attack_duration_inconsistency_cheat(solution: Any) -> tuple[Any, bool, str | None]:
    """Break ``end - start == duration`` on an activity."""
    changed = _copy(solution)
    schedule = _dig(changed, "schedule")
    if not isinstance(schedule, list) or not schedule:
        return changed, False, "schedule missing or empty"

    for entry in schedule:
        if not isinstance(entry, dict):
            continue
        start = entry.get("start")
        end = entry.get("end")
        duration = entry.get("duration")
        if not _is_number(start) or not _is_number(end) or not _is_number(duration):
            continue
        if int(duration) <= 0:
            continue
        entry["end"] = int(start) + int(duration) + 1
        return changed, True, None
    return changed, False, "no activity with positive duration"


def _attack_makespan_deflation(solution: Any) -> tuple[Any, bool, str | None]:
    """Declare an objective strictly below the recomputed makespan."""
    changed = _copy(solution)
    schedule = _dig(changed, "schedule")
    if not isinstance(schedule, list) or not schedule:
        return changed, False, "schedule missing or empty"

    ends = [
        float(entry["end"])
        for entry in schedule
        if isinstance(entry, dict) and _is_number(entry.get("end"))
    ]
    if not ends:
        return changed, False, "no numeric end times"

    forged = max(ends) - 1.0
    changed["objective"] = forged
    if "makespan" in changed:
        changed["makespan"] = forged
    return changed, True, None


def _attack_activity_omission_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    """Drop a non-dummy activity from the schedule, breaking completeness."""
    changed = _copy(solution)
    schedule = _dig(changed, "schedule")
    if not isinstance(schedule, list) or not schedule:
        return changed, False, "schedule missing or empty"

    for index, entry in enumerate(schedule):
        if not isinstance(entry, dict):
            continue
        duration = entry.get("duration")
        if _is_number(duration) and int(duration) > 0:
            schedule.pop(index)
            return changed, True, None
    return changed, False, "no activity with positive duration to omit"


def _attack_network_hash_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    """Forge the declared resource-usage profile signature (HASH-class attack).

    The ``resource_usage`` profile is a derived signature of the frozen
    ``schedule`` payload.  Bumping one profile entry without touching the
    payload forges that signature; the independent
    ``rcpsp_resource_usage_profile`` recompute rejects it.

    Registered for the universal DIMO engine (Task 5.2, mapping
    ``project -> hash -> network_hash_tamper``).  Deliberately kept out of
    :data:`ATTACK_NAMES`: the Phase-3 collaboration contract fixes the native
    replay at exactly five attacks.
    """
    changed = _copy(solution)
    usage = _dig(changed, "resource_usage")
    if not isinstance(usage, dict) or not usage:
        return changed, False, "resource_usage missing or empty"
    for profile in usage.values():
        if not isinstance(profile, list) or not profile:
            continue
        head = profile[0]
        if _is_number(head):
            profile[0] = head + 1.0
            return changed, True, "bumped resource_usage profile signature head +1.0"
    return changed, False, "resource_usage profiles carry no numeric entries"


#: ``attack name -> builder`` in canonical order.
ATTACK_BUILDERS: dict[str, Callable[[Any], tuple[Any, bool, str | None]]] = {
    "resource_capacity_overflow": _attack_resource_capacity_overflow,
    "activity_precedence_inversion": _attack_activity_precedence_inversion,
    "duration_inconsistency_cheat": _attack_duration_inconsistency_cheat,
    "makespan_deflation": _attack_makespan_deflation,
    "activity_omission_tamper": _attack_activity_omission_tamper,
    # DIMO HASH-class builder (Task 5.2); intentionally not in ATTACK_NAMES.
    "network_hash_tamper": _attack_network_hash_tamper,
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
    """Run the strict RCPSP validator plus the red-team integrity checks.

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
        checks = validate_rcpsp(problem_id, payload)
    except Exception as exc:  # noqa: BLE001 - malformed payload must not crash the gate
        return {
            "ok": False,
            "checks": [],
            "errors": [f"validator crashed on malformed payload: {type(exc).__name__}: {exc}"],
        }
    if not isinstance(checks, list):
        checks = []

    checks.extend(_independent_rcpsp_checks(payload))

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
    return "psplib_rcpsp"


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
    parser = argparse.ArgumentParser(description="Red-team a frozen RCPSP solution")
    parser.add_argument(
        "--solution",
        type=Path,
        default=ROOT / "outputs" / "psplib_rcpsp-solution.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "psplib_rcpsp-redteam.json",
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
    print("PASS project_redteam_gate" if report["ok"] else "FAIL project_redteam_gate")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
