#!/usr/bin/env python3
"""Independent recompute plus five DIMO tamper attacks for a stochastic LP solution.

The gate re-runs the strict two-stage stochastic LP validator
(``tools/validators/extended_solvers.py::validate_stochastic_lp``) on the frozen
candidate (Birge & Louveaux farmer problem with recourse, solved via
``tools/solve_stochastic_lp.py``) and then injects five deliberate attacks
(protocol ``tamper_tests`` from contracts/pricing_collaboration_v1.json):

  1. ``first_stage_capacity_overflow``    — raise first-stage acres (wheat) so
     the total exceeds ``total_land_acres`` and ``first_stage_land_constraint``
     fails
  2. ``scenario_recourse_balance_tamper`` — zero a scenario's recourse purchase
     (or inflate a sale) so internal demand is not met and
     ``scenario_recourse_feasibility`` fails
  3. ``stochastic_inequality_forgery``   — forge ``RP > WS`` in the indicator
     block, breaking ``EVPI = WS - RP`` / ``VSS = RP - EEV`` and the fundamental
     ``WS >= RP >= EEV`` inequality so ``stochastic_indicators_consistency``
     fails
  4. ``expected_profit_inflation_forgery`` — over-report the objective by more
     than the 1.0-unit integrity tolerance so ``recompute_objective`` fails
  5. ``first_stage_cost_tamper``         — tamper ``first_stage_cost`` so it no
     longer matches the planting-cost recomputation and
     ``first_stage_cost_recompute`` fails

Attacks 1 and 2 additionally re-mask the forgeable arithmetic fields
(``first_stage_cost`` / ``objective``) so each payload stays *internally
consistent* and the structural check under test is the only failing check —
an attacker who forges the easy numbers but forgets the structural constraint
must still be caught.

Robustness contract
-------------------

The tamper builders never raise on an unexpected schema.  A solution whose
shape does not match the strict stochastic LP envelope yields attacks with
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

from validators.extended_solvers import validate_stochastic_lp  # noqa: E402

__all__ = [
    "ATTACK_NAMES",
    "SCHEMA",
    "build_attacks",
    "main",
    "recompute",
    "run_redteam",
]

#: Report schema written by this gate.
SCHEMA = "orpath.pricing_redteam.v1"

#: Canonical attack order (matches contracts/pricing_collaboration_v1.json).
ATTACK_NAMES: tuple[str, ...] = (
    "first_stage_capacity_overflow",
    "scenario_recourse_balance_tamper",
    "stochastic_inequality_forgery",
    "expected_profit_inflation_forgery",
    "first_stage_cost_tamper",
)

#: Default problem id for the pricing collaboration domain.
DEFAULT_PROBLEM_ID = "farmer_stochastic_lp"

#: Default candidate solution path (contract registry).
DEFAULT_SOLUTION_PATH = ROOT / "outputs" / "farmer_stochastic_lp-solution.json"

#: Default red-team report path (contract registry).
DEFAULT_OUT_PATH = ROOT / "outputs" / "farmer_stochastic_lp-redteam.json"

#: First-stage capacity overflow margin (acres).  The tampered allocation is
#: pushed at least this far beyond ``total_land_acres``.
_OVERFLOW_ACRES = 100.0

#: Balance-break margin (units of internal demand).  Tampered recourse
#: quantities break the demand balance by at least this much so the validator's
#: 1e-4 EPS can never mask the injection.
_BALANCE_MARGIN = 10.0

#: Objective / first-stage-cost forgery offset.  Must exceed the validator's
#: 1.0-unit integrity tolerance.
_FORGERY_OFFSET = 1000.0

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


def _num(value: Any, default: float = 0.0) -> float:
    """Coerce ``value`` to float with a safe default (never raises)."""
    if not _is_number(value):
        return default
    return float(value)


def _mapping(payload: Any) -> dict[str, Any]:
    """Return ``payload`` when it is a dict, else ``{}``."""
    return payload if isinstance(payload, dict) else {}


def _raw_problem(payload: Any) -> dict[str, Any]:
    """Return the frozen ``raw_problem`` block when present, else ``{}``."""
    raw = _mapping(payload).get("raw_problem")
    return raw if isinstance(raw, dict) and raw else {}


def _first_stage(payload: Any) -> dict[str, Any]:
    """Return the ``first_stage_decision`` mapping when present, else ``{}``."""
    first = _mapping(payload).get("first_stage_decision")
    return first if isinstance(first, dict) and first else {}


def _scenarios(payload: Any) -> list[Any]:
    """Return the ``scenarios`` list when present, else ``[]``."""
    scenarios = _mapping(payload).get("scenarios")
    return scenarios if isinstance(scenarios, list) else []


def _indicators(payload: Any) -> dict[str, Any]:
    """Return the ``stochastic_indicators`` mapping when present, else ``{}``."""
    ind = _mapping(payload).get("stochastic_indicators")
    return ind if isinstance(ind, dict) and ind else {}


def _crops(raw: dict[str, Any]) -> list[str]:
    """Return the crop roster from ``raw_problem`` with a safe fallback."""
    crops = raw.get("crops")
    if isinstance(crops, list) and crops:
        return [str(c) for c in crops]
    return ["wheat", "corn", "sugar_beets"]


def _scenario_net_revenue(sc: dict[str, Any], raw: dict[str, Any]) -> float:
    """Replicate the validator's per-scenario net revenue formula exactly."""
    prices = raw.get("selling_price") or {}
    purchase = raw.get("purchase_price") or {}
    return (
        _num(prices.get("wheat")) * _num(sc.get("wheat_sold"))
        + _num(prices.get("corn")) * _num(sc.get("corn_sold"))
        + _num(prices.get("sugar_beets_quota")) * _num(sc.get("sugar_beets_quota_sold"))
        + _num(prices.get("sugar_beets_excess")) * _num(sc.get("sugar_beets_excess_sold"))
        - _num(purchase.get("wheat")) * _num(sc.get("wheat_purchased"))
        - _num(purchase.get("corn")) * _num(sc.get("corn_purchased"))
    )


def _expected_revenue(payload: Any, raw: dict[str, Any]) -> float:
    """Expected second-stage revenue over all scenarios (validator formula)."""
    total = 0.0
    for sc in _scenarios(payload):
        if not isinstance(sc, dict):
            continue
        total += _num(sc.get("probability")) * _scenario_net_revenue(sc, raw)
    return total


def _recomputed_first_stage_cost(payload: Any, raw: dict[str, Any]) -> float:
    """First-stage planting cost recomputed from acres and planting costs."""
    costs = raw.get("planting_cost_per_acre") or {}
    total = 0.0
    for crop, acres in _first_stage(payload).items():
        total += _num(costs.get(crop)) * _num(acres)
    return total


def _forged_objective(payload: Any, raw: dict[str, Any]) -> float:
    """Objective consistent with the (possibly tampered) payload arithmetic."""
    return _expected_revenue(payload, raw) - _recomputed_first_stage_cost(payload, raw)


# --------------------------------------------------------------------------- #
# Tamper builders
# --------------------------------------------------------------------------- #
#
# Each builder takes the frozen solution and returns a ``(payload, applied,
# reason)`` triple and must never raise.

def _attack_first_stage_capacity_overflow(
    solution: Any,
) -> tuple[Any, bool, str | None]:
    """Raise first-stage acres beyond ``total_land_acres``.

    The first-stage cost and the objective are re-masked so the payload stays
    internally consistent — only ``first_stage_land_constraint`` may fail.
    Raising wheat (or corn) never tightens any recourse balance; sugar beets is
    tried last because extra beet acres can tighten the quota constraint.
    """
    changed = _copy(solution)
    if not isinstance(changed, dict):
        return changed, False, "solution is not a JSON object"
    raw = _raw_problem(changed)
    if not raw:
        return changed, False, "raw_problem missing or empty"
    first = _first_stage(changed)
    if not first:
        return changed, False, "first_stage_decision missing or empty"

    crops = _crops(raw)
    total_land = _num(raw.get("total_land_acres"), 500.0)
    current_total = sum(_num(first.get(crop)) for crop in crops)
    overflow = max(_OVERFLOW_ACRES, (total_land - current_total) + _OVERFLOW_ACRES)
    demands = raw.get("internal_demand")
    demands = demands if isinstance(demands, dict) else {}
    quota = _num(raw.get("sugar_beet_quota"), 6000.0)

    raw_scenarios = {
        s.get("name"): s
        for s in (raw.get("scenarios") or [])
        if isinstance(s, dict)
    }
    scenarios = _scenarios(changed)

    def _yields(raw_s: dict[str, Any]) -> dict[str, Any]:
        yields = raw_s.get("yield_per_acre")
        return yields if isinstance(yields, dict) else {}

    def _scenario_balances_ok(acres: dict[str, float]) -> bool:
        """Check every scenario's recourse balances under ``acres``."""
        for sc in scenarios:
            if not isinstance(sc, dict):
                return False
            raw_s = raw_scenarios.get(sc.get("scenario"))
            if not isinstance(raw_s, dict):
                return False
            yields = _yields(raw_s)
            for crop in ("wheat", "corn"):
                if crop not in demands:
                    continue
                prod = _num(yields.get(crop)) * _num(acres.get(crop))
                if prod + _num(sc.get(f"{crop}_purchased")) - _num(sc.get(f"{crop}_sold")) < _num(demands[crop]) - _EPS:
                    return False
            beet_prod = _num(yields.get("sugar_beets")) * _num(acres.get("sugar_beets"))
            if (_num(sc.get("sugar_beets_quota_sold")) + _num(sc.get("sugar_beets_excess_sold")) > beet_prod + _EPS
                    or _num(sc.get("sugar_beets_quota_sold")) > quota + _EPS):
                return False
        return True

    candidates = [c for c in ("wheat", "corn", "sugar_beets") if c in crops] or crops
    chosen: str | None = None
    for crop in candidates:
        tampered = dict(first)
        tampered[crop] = round(_num(first.get(crop)) + overflow, 4)
        if _scenario_balances_ok(tampered):
            chosen = crop
            break
    if chosen is None:
        return changed, False, "no crop could be overflowed without breaking recourse balances"

    first[chosen] = round(_num(first.get(chosen)) + overflow, 4)
    # Re-mask the forgeable arithmetic so only the land constraint fails.
    changed["first_stage_cost"] = round(_recomputed_first_stage_cost(changed, raw), 4)
    changed["objective"] = round(_forged_objective(changed, raw), 4)
    return changed, True, None


def _attack_scenario_recourse_balance_tamper(
    solution: Any,
) -> tuple[Any, bool, str | None]:
    """Break a scenario's internal demand balance.

    Prefers zeroing a structurally required recourse purchase (the classic
    "forgot to buy enough wheat/corn" forgery); falls back to inflating a sale
    beyond what production can cover.  The objective is re-masked so the payload
    stays internally consistent — only ``scenario_recourse_feasibility`` may
    fail.
    """
    changed = _copy(solution)
    if not isinstance(changed, dict):
        return changed, False, "solution is not a JSON object"
    raw = _raw_problem(changed)
    if not raw:
        return changed, False, "raw_problem missing or empty"
    scenarios = _scenarios(changed)
    if not scenarios:
        return changed, False, "scenarios missing or empty"
    first = _first_stage(changed)
    if not first:
        return changed, False, "first_stage_decision missing or empty"

    demands = raw.get("internal_demand")
    demands = demands if isinstance(demands, dict) else {}
    raw_scenarios = {
        s.get("name"): s
        for s in (raw.get("scenarios") or [])
        if isinstance(s, dict)
    }

    def _production(sc: dict[str, Any], raw_s: dict[str, Any], crop: str) -> float:
        yields = raw_s.get("yield_per_acre")
        if not isinstance(yields, dict):
            return 0.0
        return _num(yields.get(crop)) * _num(first.get(crop))

    def _mask_objective(idx: int) -> None:
        """Re-mask the objective to the validator's early-break accumulation.

        ``validate_stochastic_lp`` accumulates expected revenue only for
        scenarios that pass the recourse balances and breaks at the first
        failing scenario, so the tampered scenario's revenue never enters the
        recomputation.  Masking to the revenue of the preceding scenarios keeps
        the payload internally consistent — only the structural balance check
        may fail.
        """
        expected = 0.0
        for prev in scenarios[:idx]:
            if isinstance(prev, dict):
                expected += _num(prev.get("probability")) * _scenario_net_revenue(prev, raw)
        changed["objective"] = round(expected - _recomputed_first_stage_cost(changed, raw), 4)

    # 1) Zero a purchase that is structurally required to meet demand.
    for idx, sc in enumerate(scenarios):
        if not isinstance(sc, dict):
            continue
        raw_s = raw_scenarios.get(sc.get("scenario"))
        if not isinstance(raw_s, dict):
            continue
        for crop in ("wheat", "corn"):
            if crop not in demands:
                continue
            if _num(sc.get(f"{crop}_purchased")) <= _EPS:
                continue
            if _production(sc, raw_s, crop) - _num(sc.get(f"{crop}_sold")) < _num(demands[crop]) - _EPS:
                sc[f"{crop}_purchased"] = 0.0
                _mask_objective(idx)
                return changed, True, None

    # 2) Inflate a sale beyond what production can cover.
    for idx, sc in enumerate(scenarios):
        if not isinstance(sc, dict):
            continue
        raw_s = raw_scenarios.get(sc.get("scenario"))
        if not isinstance(raw_s, dict):
            continue
        for crop in ("wheat", "corn"):
            if crop not in demands:
                continue
            prod = _production(sc, raw_s, crop)
            sold = _num(sc.get(f"{crop}_sold"))
            slack = prod - sold - _num(demands[crop])
            if slack < -_EPS:
                continue  # already infeasible — nothing to break
            sc[f"{crop}_sold"] = round(sold + slack + _BALANCE_MARGIN, 4)
            _mask_objective(idx)
            return changed, True, None

    return changed, False, "no scenario quantity could be tampered to break internal demand"


def _attack_stochastic_inequality_forgery(solution: Any) -> tuple[Any, bool, str | None]:
    """Forge ``RP > WS`` in the stochastic indicator block.

    Breaks both ``EVPI = WS - RP`` and the fundamental ``WS >= RP >= EEV``
    inequality so ``stochastic_indicators_consistency`` fails.
    """
    changed = _copy(solution)
    if not isinstance(changed, dict):
        return changed, False, "solution is not a JSON object"
    indicators = _indicators(changed)
    if not indicators:
        return changed, False, "stochastic_indicators missing or empty"
    ws = indicators.get("WS")
    if not _is_number(ws):
        return changed, False, "stochastic_indicators.WS missing or not numeric"
    indicators["RP"] = round(_num(ws) + 100.0, 4)
    return changed, True, None


def _attack_expected_profit_inflation_forgery(solution: Any) -> tuple[Any, bool, str | None]:
    """Over-report the objective by more than the validator's integrity tolerance."""
    changed = _copy(solution)
    if not isinstance(changed, dict):
        return changed, False, "solution is not a JSON object"
    if not _is_number(changed.get("objective")):
        return changed, False, "objective missing or not numeric"
    changed["objective"] = round(_num(changed.get("objective")) + _FORGERY_OFFSET, 4)
    return changed, True, None


def _attack_first_stage_cost_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    """Tamper ``first_stage_cost`` so it no longer matches the planting-cost recomputation."""
    changed = _copy(solution)
    if not isinstance(changed, dict):
        return changed, False, "solution is not a JSON object"
    if not _is_number(changed.get("first_stage_cost")):
        return changed, False, "first_stage_cost missing or not numeric"
    changed["first_stage_cost"] = round(_num(changed.get("first_stage_cost")) + _FORGERY_OFFSET, 4)
    return changed, True, None


#: ``attack name -> builder`` in canonical order.
ATTACK_BUILDERS: dict[str, Callable[[Any], tuple[Any, bool, str | None]]] = {
    "first_stage_capacity_overflow": _attack_first_stage_capacity_overflow,
    "scenario_recourse_balance_tamper": _attack_scenario_recourse_balance_tamper,
    "stochastic_inequality_forgery": _attack_stochastic_inequality_forgery,
    "expected_profit_inflation_forgery": _attack_expected_profit_inflation_forgery,
    "first_stage_cost_tamper": _attack_first_stage_cost_tamper,
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
    """Run the strict stochastic LP validator over ``payload``.

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
        checks = validate_stochastic_lp(problem_id, payload)
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
    return DEFAULT_PROBLEM_ID


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
    parser = argparse.ArgumentParser(
        description="Red-team a frozen two-stage stochastic LP solution"
    )
    parser.add_argument("--solution", type=Path, default=DEFAULT_SOLUTION_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_PATH)
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
    print("PASS pricing_redteam_gate" if report["ok"] else "FAIL pricing_redteam_gate")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
