#!/usr/bin/env python3
"""Independent recompute plus five DIMO tamper attacks for a JSSP solution.

The gate re-runs the strict JSSP validator
(``tools/validators/extended_solvers.py::validate_jssp``) on the frozen
candidate, adds two independent integrity checks owned by the red team (per-job
operation completeness and ``schedule`` / ``machine_schedules`` cross-consistency),
and then injects five deliberate attacks (protocol ``tamper_tests``):

  1. ``machine_overlap_injection``     — move a task earlier so it overlaps its
                                         machine predecessor
  2. ``operation_precedence_inversion`` — move a later job operation before its
                                         predecessor ends
  3. ``setup_time_cheat``              — collapse a machine gap below the declared
                                         changeover delay (or inject a positive
                                         setup while leaving a zero gap)
  4. ``makespan_deflation``            — declare an objective below ``max(end)``
  5. ``job_omission_tamper``           — drop an operation from the schedule

Robustness contract
-------------------

The tamper builders never raise on an unexpected schema.  A solution whose
shape does not match the strict JSSP envelope yields attacks with ``applied:
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

from validators.extended_solvers import validate_jssp  # noqa: E402

__all__ = [
    "ATTACK_NAMES",
    "SCHEMA",
    "build_attacks",
    "main",
    "recompute",
    "run_redteam",
]

#: Report schema written by this gate.
SCHEMA = "orpath.scheduling_redteam.v1"

#: Canonical attack order (matches contracts/scheduling_collaboration_v1.json).
ATTACK_NAMES: tuple[str, ...] = (
    "machine_overlap_injection",
    "operation_precedence_inversion",
    "setup_time_cheat",
    "makespan_deflation",
    "job_omission_tamper",
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


def _task_job(task: Any) -> Any:
    """Return a task's job identifier, tolerating both envelope spellings."""
    if isinstance(task, dict):
        return task.get("job", task.get("job_id"))
    return None


def _task_op(task: Any) -> Any:
    """Return a task's operation index, tolerating both envelope spellings."""
    if isinstance(task, dict):
        return task.get("task", task.get("task_id"))
    return None


def _task_machine(task: Any) -> Any:
    """Return a task's machine identifier, tolerating both envelope spellings."""
    if isinstance(task, dict):
        return task.get("machine", task.get("machine_id"))
    return None


def _find_task_variants(
    changed: Any,
    job: Any,
    op: Any,
) -> list[dict[str, Any]]:
    """Return every dict task matching ``(job, op)`` in the envelope.

    ``schedule`` and ``machine_schedules`` hold independent deep copies, so a
    mutation must be applied to each variant to keep the cross-consistency
    check satisfied.  Never raises.
    """
    found: list[dict[str, Any]] = []
    if not isinstance(changed, dict):
        return found

    tasks = changed.get("schedule")
    if isinstance(tasks, list):
        for task in tasks:
            if isinstance(task, dict) and _task_job(task) == job and _task_op(task) == op:
                found.append(task)

    machine_schedules = changed.get("machine_schedules")
    if isinstance(machine_schedules, dict):
        for entries in machine_schedules.values():
            if not isinstance(entries, list):
                continue
            for task in entries:
                if isinstance(task, dict) and _task_job(task) == job and _task_op(task) == op:
                    found.append(task)
    return found


def _shift_task(changed: Any, reference: Any, start: float, end: float) -> None:
    """Set ``start``/``end`` on every variant of ``reference``."""
    if not isinstance(reference, dict):
        return
    job = _task_job(reference)
    op = _task_op(reference)
    for task in _find_task_variants(changed, job, op):
        task["start"] = start
        task["end"] = end


# --------------------------------------------------------------------------- #
# Independent integrity checks (owned by the red team)
# --------------------------------------------------------------------------- #

def _independent_jssp_checks(payload: Any) -> list[dict[str, Any]]:
    """Return red-team-owned integrity checks beyond ``validate_jssp``.

    These never raise and only add checks; they cannot mask a validator failure.
    """
    checks: list[dict[str, Any]] = []
    tasks = payload.get("schedule") if isinstance(payload, dict) else None

    # (a) Per-job operation completeness: operation indices must be the exact
    # contiguous range 0 .. k-1.  Deleting any non-last operation breaks it.
    if isinstance(tasks, list) and tasks:
        by_job: dict[Any, set[Any]] = {}
        for task in tasks:
            if isinstance(task, dict):
                by_job.setdefault(_task_job(task), set()).add(_task_op(task))
        complete = True
        detail: str | None = None
        for job, ops in by_job.items():
            if not ops:
                continue
            try:
                expected = set(range(len(ops)))
            except TypeError:
                complete = False
                detail = f"job {job!r} has non-integer operation indices"
                break
            if ops != expected:
                complete = False
                detail = f"job {job!r} operations {sorted(map(str, ops))} != {sorted(map(str, expected))}"
                break
        checks.append(
            {
                "name": "jssp_operation_completeness",
                "ok": complete,
                "detail": detail,
            }
        )
    else:
        checks.append(
            {
                "name": "jssp_operation_completeness",
                "ok": False,
                "detail": "schedule missing or empty",
            }
        )

    # (b) schedule <-> machine_schedules cross-consistency.
    machine_schedules = payload.get("machine_schedules") if isinstance(payload, dict) else None
    if isinstance(tasks, list) and tasks and isinstance(machine_schedules, dict) and machine_schedules:
        schedule_keys = {
            (
                _task_job(t),
                _task_op(t),
                _task_machine(t),
                t.get("start"),
                t.get("end"),
            )
            for t in tasks
            if isinstance(t, dict)
        }
        machine_keys: set[Any] = set()
        for entries in machine_schedules.values():
            if not isinstance(entries, list):
                continue
            for t in entries:
                if isinstance(t, dict):
                    machine_keys.add(
                        (
                            _task_job(t),
                            _task_op(t),
                            _task_machine(t),
                            t.get("start"),
                            t.get("end"),
                        )
                    )
        checks.append(
            {
                "name": "jssp_schedule_machine_schedule_consistency",
                "ok": bool(schedule_keys) and schedule_keys == machine_keys,
            }
        )

    return checks


# --------------------------------------------------------------------------- #
# Tamper builders
# --------------------------------------------------------------------------- #
#
# Each builder takes the frozen solution and returns a ``(payload, applied,
# reason)`` triple and must never raise.

def _attack_machine_overlap_injection(solution: Any) -> tuple[Any, bool, str | None]:
    """Move a machine's second task earlier so it overlaps its predecessor."""
    changed = _copy(solution)
    tasks = _dig(changed, "schedule")
    if not isinstance(tasks, list) or len(tasks) < 2:
        return changed, False, "schedule missing or has fewer than two tasks"

    by_machine: dict[Any, list[dict[str, Any]]] = {}
    for task in tasks:
        if isinstance(task, dict):
            by_machine.setdefault(_task_machine(task), []).append(task)

    for m_tasks in by_machine.values():
        if len(m_tasks) < 2:
            continue
        ordered = sorted(m_tasks, key=lambda t: t.get("start", 0))
        first, second = ordered[0], ordered[1]
        if not _is_number(first.get("end")) or not _is_number(second.get("duration")):
            continue
        new_start = float(first["end"]) - 1.0
        new_end = new_start + float(second["duration"])
        _shift_task(changed, second, new_start, new_end)
        return changed, True, None
    return changed, False, "no machine with two schedulable tasks"


def _attack_operation_precedence_inversion(solution: Any) -> tuple[Any, bool, str | None]:
    """Move a later job operation to start before its predecessor ends."""
    changed = _copy(solution)
    tasks = _dig(changed, "schedule")
    if not isinstance(tasks, list) or len(tasks) < 2:
        return changed, False, "schedule missing or has fewer than two tasks"

    by_job: dict[Any, list[dict[str, Any]]] = {}
    for task in tasks:
        if isinstance(task, dict):
            by_job.setdefault(_task_job(task), []).append(task)

    for j_tasks in by_job.values():
        if len(j_tasks) < 2:
            continue
        ordered = sorted(j_tasks, key=lambda t: t.get("task", t.get("task_id", 0)))
        first, second = ordered[0], ordered[1]
        if not _is_number(first.get("end")) or not _is_number(second.get("duration")):
            continue
        new_start = float(first["end"]) - 1.0
        new_end = new_start + float(second["duration"])
        _shift_task(changed, second, new_start, new_end)
        return changed, True, None
    return changed, False, "no job with two schedulable operations"


def _attack_setup_time_cheat(solution: Any) -> tuple[Any, bool, str | None]:
    """Collapse a machine gap below the declared changeover delay."""
    changed = _copy(solution)
    tasks = _dig(changed, "schedule")
    if not isinstance(tasks, list) or len(tasks) < 2:
        return changed, False, "schedule missing or has fewer than two tasks"

    by_machine: dict[Any, list[dict[str, Any]]] = {}
    for task in tasks:
        if isinstance(task, dict):
            by_machine.setdefault(_task_machine(task), []).append(task)

    target: tuple[dict[str, Any], dict[str, Any]] | None = None
    for m_tasks in by_machine.values():
        if len(m_tasks) < 2:
            continue
        ordered = sorted(m_tasks, key=lambda t: t.get("start", 0))
        first, second = ordered[0], ordered[1]
        if _is_number(first.get("end")) and _is_number(second.get("duration")):
            target = (first, second)
            break
    if target is None:
        return changed, False, "no machine with two schedulable tasks"

    first, second = target
    # Guarantee a positive uniform setup so the validator's setup check is live,
    # even when the envelope declared no setup or a (JSON-flattened) dict setup.
    existing = changed.get("setup")
    if isinstance(existing, int) and not isinstance(existing, bool) and existing > 0:
        new_setup: Any = existing
    else:
        new_setup = 1
    changed["setup"] = new_setup

    new_start = float(first["end"])
    new_end = new_start + float(second["duration"])
    _shift_task(changed, second, new_start, new_end)
    return changed, True, None


def _attack_makespan_deflation(solution: Any) -> tuple[Any, bool, str | None]:
    """Declare an objective strictly below the recomputed makespan."""
    changed = _copy(solution)
    tasks = _dig(changed, "schedule")
    if not isinstance(tasks, list) or not tasks:
        return changed, False, "schedule missing or empty"

    ends = [
        float(t["end"])
        for t in tasks
        if isinstance(t, dict) and _is_number(t.get("end"))
    ]
    if not ends:
        return changed, False, "no numeric end times"

    forged = max(ends) - 1.0
    changed["objective"] = forged
    if "makespan" in changed:
        changed["makespan"] = forged
    return changed, True, None


def _attack_job_omission_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    """Drop a non-last operation from its job's schedule and machine view."""
    changed = _copy(solution)
    tasks = _dig(changed, "schedule")
    if not isinstance(tasks, list) or not tasks:
        return changed, False, "schedule missing or empty"

    by_job: dict[Any, list[dict[str, Any]]] = {}
    for task in tasks:
        if isinstance(task, dict):
            by_job.setdefault(_task_job(task), []).append(task)

    for j_tasks in by_job.values():
        if len(j_tasks) < 2:
            continue
        ordered = sorted(j_tasks, key=lambda t: t.get("task", t.get("task_id", 0)))
        victim = ordered[0]
        job = _task_job(victim)
        op = _task_op(victim)

        schedule = changed.get("schedule")
        if isinstance(schedule, list):
            for task in list(schedule):
                if isinstance(task, dict) and _task_job(task) == job and _task_op(task) == op:
                    schedule.remove(task)

        machine_schedules = changed.get("machine_schedules")
        if isinstance(machine_schedules, dict):
            for entries in machine_schedules.values():
                if not isinstance(entries, list):
                    continue
                for task in list(entries):
                    if isinstance(task, dict) and _task_job(task) == job and _task_op(task) == op:
                        entries.remove(task)
        return changed, True, None
    return changed, False, "no job with two operations"


def _attack_matrix_hash_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    """Forge the derived machine-timeline signature (HASH-class attack).

    The ``machine_schedules`` view is a derived signature of the frozen
    ``schedule`` payload.  Shifting one signature entry without touching the
    payload forges that signature; the independent
    ``jssp_schedule_machine_schedule_consistency`` recompute rejects it.

    Registered for the universal DIMO engine (Task 5.2, mapping
    ``scheduling -> hash -> matrix_hash_tamper``).  Deliberately kept out of
    :data:`ATTACK_NAMES`: the Phase-3 collaboration contract fixes the native
    replay at exactly five attacks.
    """
    changed = _copy(solution)
    machine_schedules = _dig(changed, "machine_schedules")
    if not isinstance(machine_schedules, dict) or not machine_schedules:
        return changed, False, "machine_schedules missing or empty"
    for entries in machine_schedules.values():
        if not isinstance(entries, list) or not entries:
            continue
        first = entries[0]
        if not isinstance(first, dict):
            continue
        start = first.get("start")
        if _is_number(start):
            first["start"] = start + 1.0
            return changed, True, "shifted machine_schedules signature entry start +1.0"
        end = first.get("end")
        if _is_number(end):
            first["end"] = end + 1.0
            return changed, True, "shifted machine_schedules signature entry end +1.0"
    return changed, False, "machine_schedules entries carry no numeric start/end"


#: ``attack name -> builder`` in canonical order.
ATTACK_BUILDERS: dict[str, Callable[[Any], tuple[Any, bool, str | None]]] = {
    "machine_overlap_injection": _attack_machine_overlap_injection,
    "operation_precedence_inversion": _attack_operation_precedence_inversion,
    "setup_time_cheat": _attack_setup_time_cheat,
    "makespan_deflation": _attack_makespan_deflation,
    "job_omission_tamper": _attack_job_omission_tamper,
    # DIMO HASH-class builder (Task 5.2); intentionally not in ATTACK_NAMES.
    "matrix_hash_tamper": _attack_matrix_hash_tamper,
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
    """Run the strict JSSP validator plus the red-team integrity checks.

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
        checks = validate_jssp(problem_id, payload)
    except Exception as exc:  # noqa: BLE001 - malformed payload must not crash the gate
        return {
            "ok": False,
            "checks": [],
            "errors": [f"validator crashed on malformed payload: {type(exc).__name__}: {exc}"],
        }
    if not isinstance(checks, list):
        checks = []

    checks.extend(_independent_jssp_checks(payload))

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
    return "pyjobshop_jssp"


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
    parser = argparse.ArgumentParser(description="Red-team a frozen JSSP solution")
    parser.add_argument(
        "--solution",
        type=Path,
        default=ROOT / "outputs" / "pyjobshop_jssp-solution.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "pyjobshop_jssp-redteam.json",
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
    print("PASS scheduling_redteam_gate" if report["ok"] else "FAIL scheduling_redteam_gate")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
