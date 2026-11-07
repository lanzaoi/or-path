#!/usr/bin/env python3
"""Independent recompute plus five DIMO tamper attacks for a microgrid dispatch solution.

The gate re-runs the strict microgrid validator
(``tools/validators/microgrid_dispatch.py::validate_microgrid``) on the frozen
candidate and then injects five deliberate attacks (protocol ``tamper_tests``):

  1. ``power_balance_violation_injection`` — zero a purchase/discharge interval so
     ``buy + pv + dis - ch < load`` and ``q1_power_balance`` fails
  2. ``soc_limit_breach_injection``        — push a SOC sample outside
     ``[1200, 10800]`` so ``q1_soc_bounds`` fails
  3. ``battery_efficiency_dynamics_tamper`` — shift a mid-horizon SOC sample so
     ``S_t != S_{t-1} + 0.9*ch - (1/0.9)*dis`` and ``q1_battery_dynamics`` fails
  4. ``daily_storage_imbalance_tamper``   — set ``S(144)`` to a value other than
     ``6000.0`` so ``q1_daily_storage_balance`` fails
  5. ``energy_cost_deflation_forgery``    — under-report ``total_purchase_cost``
     by more than 1 yuan so ``q1_cost_integrity`` fails

Robustness contract
-------------------

The tamper builders never raise on an unexpected schema.  A solution whose
shape does not match the strict microgrid envelope yields attacks with
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

from validators.microgrid_dispatch import validate_microgrid  # noqa: E402

__all__ = [
    "ATTACK_NAMES",
    "SCHEMA",
    "build_attacks",
    "main",
    "recompute",
    "run_redteam",
]

#: Report schema written by this gate.
SCHEMA = "orpath.microgrid_redteam.v1"

#: Canonical attack order (matches contracts/microgrid_collaboration_v1.json).
ATTACK_NAMES: tuple[str, ...] = (
    "power_balance_violation_injection",
    "soc_limit_breach_injection",
    "battery_efficiency_dynamics_tamper",
    "daily_storage_imbalance_tamper",
    "energy_cost_deflation_forgery",
)

#: Planning horizon of the deterministic day-ahead dispatch (144 ten-minute intervals).
INTERVALS = 144

#: Battery nameplate limits (kWh).
SOC_MIN_KWH = 1200.0
SOC_MAX_KWH = 10800.0

#: Round-trip / one-way efficiency used by the validator dynamics equation.
EFFICIENCY = 0.90

#: The deterministic LP fixes the closing storage at the initial 6000 kWh.
DAILY_STORAGE_KWH = 6000.0

#: Numeric tolerance for the red-team's independent envelope comparisons.
_EPS = 1e-6

#: Deflated cost offset (yuan) used by the cost-integrity forgery. Must exceed the
#: validator's 1.0 yuan integrity tolerance.
_DEFLATION_YUAN = 1000.0


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


def _num(value: Any, default: float = 0.0) -> float:
    """Coerce ``value`` to float with a safe default (never raises)."""
    if not _is_number(value):
        return default
    return float(value)


def _mapping(payload: Any) -> dict[str, Any]:
    """Return ``payload`` when it is a dict, else ``{}``."""
    return payload if isinstance(payload, dict) else {}


def _q1(payload: Any) -> dict[str, Any]:
    """Return the Q1 subproblem dict when present, else ``{}``."""
    q1 = _dig(payload, "subproblems", "q1")
    if q1 is None:
        q1 = _dig(payload, "q1")
    return q1 if isinstance(q1, dict) and q1 else {}


def _series(q1: Any, key: str) -> list[Any]:
    """Return the ``key`` series from ``q1`` when it is a list, else ``[]``."""
    if not isinstance(q1, dict):
        return []
    value = q1.get(key)
    return value if isinstance(value, list) else []


def _padded(series: list[Any], length: int = INTERVALS) -> list[float]:
    """Return a float series padded/truncated to ``length`` with zeros."""
    values = [_num(value) for value in series[:length]]
    while len(values) < length:
        values.append(0.0)
    return values


# --------------------------------------------------------------------------- #
# Tamper builders
# --------------------------------------------------------------------------- #
#
# Each builder takes the frozen solution and returns a ``(payload, applied,
# reason)`` triple and must never raise.

def _attack_power_balance_violation_injection(
    solution: Any,
) -> tuple[Any, bool, str | None]:
    """Zero one purchase/discharge interval so delivered power falls below load.

    Prefers an interval where ``pv - ch < load`` once the purchase and discharge
    terms are removed; this guarantees only ``q1_power_balance`` is exercised
    (the battery SOC sequence and reported cost stay untouched).
    """
    changed = _copy(solution)
    q1 = _q1(changed)
    if not q1:
        return changed, False, "q1 subproblem missing or empty"

    # Use the live series references so edits persist into ``changed``.
    buy = _series(q1, "purchase_kwh")
    dis = _series(q1, "discharge_kwh")
    ch = _series(q1, "charge_kwh")
    pv = _series(q1, "pv_kwh")
    load = _series(q1, "load_kwh")
    if len(buy) != INTERVALS or len(load) != INTERVALS:
        return changed, False, "purchase_kwh/load_kwh must have 144 intervals"

    ch_vals = _padded(ch)
    pv_vals = _padded(pv)
    load_vals = _padded(load)

    for t in range(INTERVALS):
        if not _is_number(buy[t]) or not _is_number(dis[t]):
            continue
        if _num(buy[t]) <= 0.0 and _num(dis[t]) <= 0.0:
            continue
        delivered = pv_vals[t] - ch_vals[t]
        if delivered < load_vals[t] - _EPS:
            buy[t] = 0.0
            dis[t] = 0.0
            return changed, True, None

    return changed, False, "no interval where zeroing purchase/discharge breaks power balance"


def _attack_soc_limit_breach_injection(solution: Any) -> tuple[Any, bool, str | None]:
    """Push one mid-horizon SOC sample above the 10800 kWh nameplate ceiling."""
    changed = _copy(solution)
    q1 = _q1(changed)
    if not q1:
        return changed, False, "q1 subproblem missing or empty"

    soc = _series(q1, "soc_kwh")
    if len(soc) != INTERVALS:
        return changed, False, "soc_kwh must have 144 intervals"

    index = INTERVALS // 2
    soc[index] = SOC_MAX_KWH + 2000.0  # 12800 kWh — clearly out of bounds
    return changed, True, None


def _attack_battery_efficiency_dynamics_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    """Shift a mid-horizon SOC sample so the efficiency recurrence breaks.

    The edited sample stays inside ``[1200, 10800]`` and is not the closing
    sample, so ``q1_soc_bounds`` and ``q1_daily_storage_balance`` remain intact
    while ``q1_battery_dynamics`` fails.
    """
    changed = _copy(solution)
    q1 = _q1(changed)
    if not q1:
        return changed, False, "q1 subproblem missing or empty"

    soc = _series(q1, "soc_kwh")
    if len(soc) != INTERVALS:
        return changed, False, "soc_kwh must have 144 intervals"

    index = INTERVALS // 2
    if index == INTERVALS - 1:
        index = INTERVALS - 2
    current = _num(soc[index])
    new_value = current + 100.0 if current + 100.0 <= SOC_MAX_KWH else current - 100.0
    if new_value < SOC_MIN_KWH:
        new_value = (SOC_MIN_KWH + SOC_MAX_KWH) / 2.0
    soc[index] = new_value
    return changed, True, None


def _attack_daily_storage_imbalance_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    """Set the closing SOC ``S(144)`` to a value other than 6000 kWh."""
    changed = _copy(solution)
    q1 = _q1(changed)
    if not q1:
        return changed, False, "q1 subproblem missing or empty"

    soc = _series(q1, "soc_kwh")
    if len(soc) != INTERVALS:
        return changed, False, "soc_kwh must have 144 intervals"

    soc[-1] = DAILY_STORAGE_KWH + 100.0  # 6100 kWh — violates the daily storage reset
    return changed, True, None


def _attack_energy_cost_deflation_forgery(solution: Any) -> tuple[Any, bool, str | None]:
    """Under-report the total purchase cost by more than the 1 yuan tolerance."""
    changed = _copy(solution)
    q1 = _q1(changed)
    if not q1:
        return changed, False, "q1 subproblem missing or empty"

    buy = _series(q1, "purchase_kwh")
    prices = _series(q1, "prices")
    if len(buy) != INTERVALS or len(prices) != INTERVALS:
        return changed, False, "purchase_kwh/prices must have 144 intervals"

    computed = sum(_num(b) * _num(p) for b, p in zip(buy, prices))
    forged = max(0.0, computed - _DEFLATION_YUAN)
    q1["total_purchase_cost"] = forged
    q1["total_cost"] = forged
    return changed, True, None


#: ``attack name -> builder`` in canonical order.
ATTACK_BUILDERS: dict[str, Callable[[Any], tuple[Any, bool, str | None]]] = {
    "power_balance_violation_injection": _attack_power_balance_violation_injection,
    "soc_limit_breach_injection": _attack_soc_limit_breach_injection,
    "battery_efficiency_dynamics_tamper": _attack_battery_efficiency_dynamics_tamper,
    "daily_storage_imbalance_tamper": _attack_daily_storage_imbalance_tamper,
    "energy_cost_deflation_forgery": _attack_energy_cost_deflation_forgery,
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
    """Run the strict microgrid validator over ``payload``.

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
        checks = validate_microgrid(problem_id, payload)
    except Exception as exc:  # noqa: BLE001 - malformed payload must not crash the gate
        return {
            "ok": False,
            "checks": [],
            "errors": [f"validator crashed on malformed payload: {type(exc).__name__}: {exc}"],
        }
    if not isinstance(checks, list):
        checks = []

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
    return "microgrid_dispatch"


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
    parser = argparse.ArgumentParser(description="Red-team a frozen microgrid dispatch solution")
    parser.add_argument(
        "--solution",
        type=Path,
        default=ROOT / "outputs" / "microgrid_dispatch-solution.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "microgrid_dispatch-redteam.json",
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
    print("PASS microgrid_redteam_gate" if report["ok"] else "FAIL microgrid_redteam_gate")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
