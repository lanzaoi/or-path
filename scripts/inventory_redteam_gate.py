#!/usr/bin/env python3
"""Independent recompute plus five DIMO tamper attacks for a lot-sizing solution.

The gate re-runs the strict lot-sizing validator
(``tools/validators/extended_solvers.py::validate_lot_sizing``) on the frozen
candidate, adds an independent envelope-consistency check owned by the red team
(top-level ``production`` / ``inventory`` / ``setup_actions`` series must match
the per-period ``schedule`` rows), and then injects five deliberate attacks
(protocol ``tamper_tests``):

  1. ``flow_balance_violation_injection`` — tamper a period's production (or
     inventory) so ``I_{t-1} + x_t - I_t == d_t`` is broken
  2. ``setup_evasion_tamper``            — set ``setup = False`` (and zero the
     setup charge) on a period with ``x_t > 0``
  3. ``capacity_overflow_injection``     — raise ``x_t`` above the per-period
     capacity
  4. ``safety_stock_deficit_tamper``     — lower ``I_t`` below the safety-stock
     floor
  5. ``cost_deflation_forgery``          — declare an objective strictly below
     the recomputed total cost

Robustness contract
-------------------

The tamper builders never raise on an unexpected schema.  A solution whose
shape does not match the strict lot-sizing envelope yields attacks with
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

from validators.extended_solvers import validate_lot_sizing  # noqa: E402

__all__ = [
    "ATTACK_NAMES",
    "SCHEMA",
    "build_attacks",
    "main",
    "recompute",
    "run_redteam",
]

#: Report schema written by this gate.
SCHEMA = "orpath.inventory_redteam.v1"

#: Canonical attack order (matches contracts/inventory_collaboration_v1.json).
ATTACK_NAMES: tuple[str, ...] = (
    "flow_balance_violation_injection",
    "setup_evasion_tamper",
    "capacity_overflow_injection",
    "safety_stock_deficit_tamper",
    "cost_deflation_forgery",
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


def _period_index(entry: Any) -> int | None:
    """Return the 0-based schedule index for a row, tolerating bad ``period``."""
    if not isinstance(entry, dict):
        return None
    try:
        return int(entry.get("period", 0)) - 1
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Independent integrity checks (owned by the red team)
# --------------------------------------------------------------------------- #

def _independent_inventory_checks(payload: Any) -> list[dict[str, Any]]:
    """Return red-team-owned integrity checks beyond ``validate_lot_sizing``.

    The single check here is envelope-series consistency: the top-level
    ``production`` / ``inventory`` / ``setup_actions`` lists must agree with
    the per-period ``schedule`` rows.  ``validate_lot_sizing`` recomputes
    costs and flow balance from the schedule but never cross-checks these
    parallel series, so an attacker who edits one and not the other would slip
    past the validator alone.  This check never raises and only adds checks;
    it cannot mask a validator failure.
    """
    checks: list[dict[str, Any]] = []
    schedule = payload.get("schedule") if isinstance(payload, dict) else None

    if not isinstance(schedule, list) or not schedule:
        checks.append(
            {
                "name": "inventory_envelope_series_consistency",
                "ok": False,
                "detail": "schedule missing or empty",
            }
        )
        return checks

    def _series(key: str) -> list[Any] | None:
        vals = payload.get(key) if isinstance(payload, dict) else None
        if not isinstance(vals, list) or len(vals) != len(schedule):
            return None
        return vals

    production = _series("production")
    inventory = _series("inventory")
    setup_actions = _series("setup_actions")

    mismatch: str | None = None

    if production is not None:
        for i, s in enumerate(schedule):
            if isinstance(s, dict) and _is_number(s.get("production")):
                if abs(float(s["production"]) - float(production[i])) > _EPS:
                    mismatch = f"production[{i}]: schedule {s['production']} != envelope {production[i]}"
                    break

    if mismatch is None and inventory is not None:
        for i, s in enumerate(schedule):
            if isinstance(s, dict) and _is_number(s.get("inventory")):
                if abs(float(s["inventory"]) - float(inventory[i])) > _EPS:
                    mismatch = f"inventory[{i}]: schedule {s['inventory']} != envelope {inventory[i]}"
                    break

    if mismatch is None and setup_actions is not None:
        for i, s in enumerate(schedule):
            if isinstance(s, dict):
                expected = 1 if s.get("setup") else 0
                reported = setup_actions[i]
                if not _is_number(reported) or int(reported) != expected:
                    mismatch = f"setup_actions[{i}]: schedule {expected} != envelope {reported}"
                    break

    checks.append(
        {
            "name": "inventory_envelope_series_consistency",
            "ok": mismatch is None,
            "detail": mismatch,
        }
    )
    return checks


# --------------------------------------------------------------------------- #
# Tamper builders
# --------------------------------------------------------------------------- #
#
# Each builder takes the frozen solution and returns a ``(payload, applied,
# reason)`` triple and must never raise.

def _attack_flow_balance_violation_injection(
    solution: Any,
) -> tuple[Any, bool, str | None]:
    """Tamper a period's production (+1.0) to break flow balance.

    The lot-sizing flow balance is ``I_{t-1} + x_t - I_t == d_t``.  Raising
    ``x_t`` by a small delta while leaving ``I_t`` and ``d_t`` untouched makes
    the left-hand side exceed the right-hand side by exactly that delta, so the
    validator's ``lot_sizing_flow_balance`` check must fail.
    """
    changed = _copy(solution)
    schedule = _dig(changed, "schedule")
    if not isinstance(schedule, list) or not schedule:
        return changed, False, "schedule missing or empty"

    # Prefer a setup period (production > 0); fall back to the first row.
    target: dict[str, Any] | None = None
    for entry in schedule:
        if isinstance(entry, dict) and _is_number(entry.get("production")):
            if float(entry["production"]) > 0.0:
                target = entry
                break
    if target is None:
        target = schedule[0] if isinstance(schedule[0], dict) else None
    if not isinstance(target, dict):
        return changed, False, "no schedule row to tamper"

    target["production"] = float(target.get("production", 0.0)) + 1.0
    return changed, True, None


def _attack_setup_evasion_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    """Set ``setup = False`` (and zero the charge) on a period with ``x_t > 0``.

    The validator's ``lot_sizing_setup_consistency`` check requires
    ``x_t > 0`` implies ``setup == 1``; clearing the flag on a producing
    period must therefore be rejected.  The top-level ``setup_actions`` series
    is updated in lockstep so the evasion looks internally consistent — the
    catch comes from the validator, not the envelope cross-check.
    """
    changed = _copy(solution)
    schedule = _dig(changed, "schedule")
    if not isinstance(schedule, list) or not schedule:
        return changed, False, "schedule missing or empty"

    for entry in schedule:
        if not isinstance(entry, dict):
            continue
        if not _is_number(entry.get("production")):
            continue
        if float(entry["production"]) <= 0.0:
            continue
        entry["setup"] = False
        entry["setup_cost"] = 0.0
        setup_actions = _dig(changed, "setup_actions")
        if isinstance(setup_actions, list) and len(setup_actions) == len(schedule):
            idx = _period_index(entry)
            if idx is not None and 0 <= idx < len(setup_actions):
                setup_actions[idx] = 0
        return changed, True, None
    return changed, False, "no period with positive production"


def _attack_capacity_overflow_injection(solution: Any) -> tuple[Any, bool, str | None]:
    """Raise a period's production above the per-period capacity.

    When the envelope declares a numeric ``capacity``, the validator's
    ``lot_sizing_capacity_respected`` check requires ``x_t <= capacity``;
    injecting ``x_t = capacity + 1`` must be rejected.  A setup period is
    preferred so the attack isolates the capacity violation rather than also
    tripping setup consistency.
    """
    changed = _copy(solution)
    capacity = _dig(changed, "capacity")
    if not _is_number(capacity):
        return changed, False, "capacity missing or not a number"
    schedule = _dig(changed, "schedule")
    if not isinstance(schedule, list) or not schedule:
        return changed, False, "schedule missing or empty"

    target: dict[str, Any] | None = None
    for entry in schedule:
        if isinstance(entry, dict) and entry.get("setup"):
            target = entry
            break
    if target is None:
        target = schedule[0] if isinstance(schedule[0], dict) else None
    if not isinstance(target, dict):
        return changed, False, "no schedule row to tamper"

    target["production"] = float(capacity) + 1.0
    return changed, True, None


def _attack_safety_stock_deficit_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    """Lower a period's inventory below the safety-stock floor.

    The validator's ``lot_sizing_safety_stock`` check requires
    ``I_t >= safety_stock`` for every period; setting ``I_t`` to
    ``safety_stock - 1`` must be rejected.
    """
    changed = _copy(solution)
    safety_stock = _dig(changed, "safety_stock")
    if not _is_number(safety_stock):
        return changed, False, "safety_stock missing or not a number"
    schedule = _dig(changed, "schedule")
    if not isinstance(schedule, list) or not schedule:
        return changed, False, "schedule missing or empty"

    target = schedule[0] if isinstance(schedule[0], dict) else None
    if not isinstance(target, dict):
        return changed, False, "no schedule row to tamper"

    target["inventory"] = float(safety_stock) - 1.0
    return changed, True, None


def _attack_cost_deflation_forgery(solution: Any) -> tuple[Any, bool, str | None]:
    """Declare an objective strictly below the recomputed total cost.

    Forging ``objective - 100`` (and the parallel ``costs.total`` /
    ``metrics.objective`` fields, when present) must be rejected by the
    validator's ``lot_sizing_objective_match`` check, which recomputes the
    total cost from the raw rates and the delivered schedule.
    """
    changed = _copy(solution)
    objective = _dig(changed, "objective")
    if not _is_number(objective):
        return changed, False, "objective missing or not a number"

    forged = float(objective) - 100.0
    changed["objective"] = forged

    costs = _dig(changed, "costs")
    if isinstance(costs, dict) and _is_number(costs.get("total")):
        costs["total"] = forged

    metrics = _dig(changed, "metrics")
    if isinstance(metrics, dict) and _is_number(metrics.get("objective")):
        metrics["objective"] = forged

    return changed, True, None


#: ``attack name -> builder`` in canonical order.
ATTACK_BUILDERS: dict[str, Callable[[Any], tuple[Any, bool, str | None]]] = {
    "flow_balance_violation_injection": _attack_flow_balance_violation_injection,
    "setup_evasion_tamper": _attack_setup_evasion_tamper,
    "capacity_overflow_injection": _attack_capacity_overflow_injection,
    "safety_stock_deficit_tamper": _attack_safety_stock_deficit_tamper,
    "cost_deflation_forgery": _attack_cost_deflation_forgery,
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
    """Run the strict lot-sizing validator plus the red-team integrity checks.

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
        checks = validate_lot_sizing(problem_id, payload)
    except Exception as exc:  # noqa: BLE001 - malformed payload must not crash the gate
        return {
            "ok": False,
            "checks": [],
            "errors": [f"validator crashed on malformed payload: {type(exc).__name__}: {exc}"],
        }
    if not isinstance(checks, list):
        checks = []

    checks.extend(_independent_inventory_checks(payload))

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
    return "wagner_whitin_clsp"


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
    parser = argparse.ArgumentParser(description="Red-team a frozen lot-sizing solution")
    parser.add_argument(
        "--solution",
        type=Path,
        default=ROOT / "outputs" / "wagner_whitin_clsp-solution.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "wagner_whitin_clsp-redteam.json",
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
    print("PASS inventory_redteam_gate" if report["ok"] else "FAIL inventory_redteam_gate")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
