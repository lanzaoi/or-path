#!/usr/bin/env python3
"""Independent recompute plus five DIMO tamper attacks for a Markowitz portfolio.

The gate re-runs the strict Markowitz validator
(``tools/validators/extended_solvers.py::validate_portfolio``) on the frozen
candidate (mean-variance portfolio optimization via
``tools/solve_portfolio.py``) and then injects five deliberate attacks
(protocol ``tamper_tests`` from ``contracts/finance_collaboration_v1.json``):

  1. ``weight_simplex_violation_injection`` — scale the allocations so their
     sum is 1.25 (or 0.75), breaking ``weights_sum_to_one``
  2. ``short_position_breach_injection``   — inject a -0.15 short position into
     a long-only plan, breaking ``long_only_bounds``
  3. ``sharpe_ratio_inflation_forgery``    — over-report the Sharpe ratio by
     +0.5, breaking ``sharpe_recomputation``
  4. ``variance_risk_deflation_forgery``  — under-report volatility / variance,
     breaking ``volatility_recompute`` (or the Sharpe identity when the raw
     covariance matrix is absent)
  5. ``discrete_lot_allocation_tamper``   — tamper integer share lots to include
     a fractional lot (or exceed the capital budget), breaking
     ``discrete_shares_integrality`` / ``discrete_capital_feasibility``

Attacks 1, 2 and 4 additionally re-mask the forgeable arithmetic
(expected return / volatility / Sharpe) so each payload stays *internally
consistent* and the structural check under test is the only failing check —
an attacker who forges the easy numbers but forgets the simplex / long-only /
variance constraint must still be caught.

Robustness contract
-------------------

The tamper builders never raise on an unexpected schema.  A solution whose
shape does not match the strict Markowitz envelope yields attacks with
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

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from validators.extended_solvers import validate_portfolio  # noqa: E402

__all__ = [
    "ATTACK_NAMES",
    "SCHEMA",
    "build_attacks",
    "main",
    "recompute",
    "run_redteam",
]

#: Report schema written by this gate.
SCHEMA = "orpath.finance_redteam.v1"

#: Canonical attack order (matches contracts/finance_collaboration_v1.json).
ATTACK_NAMES: tuple[str, ...] = (
    "weight_simplex_violation_injection",
    "short_position_breach_injection",
    "sharpe_ratio_inflation_forgery",
    "variance_risk_deflation_forgery",
    "discrete_lot_allocation_tamper",
)

#: Default problem id for the finance collaboration domain.
DEFAULT_PROBLEM_ID = "markowitz_portfolio"

#: Default candidate solution path (contract registry).
DEFAULT_SOLUTION_PATH = ROOT / "outputs" / "markowitz_portfolio-solution.json"

#: Default red-team report path (contract registry).
DEFAULT_OUT_PATH = ROOT / "outputs" / "markowitz_portfolio-redteam.json"

#: Simplex-break scaling factors tried by attack 1.
_SIMPLEX_SCALE_CANDIDATES: tuple[float, ...] = (1.25, 0.75)

#: Magnitude of the injected short position (attack 2).
_SHORT_POSITION = 0.15

#: Sharpe forgery offset (attack 3).
_SHARPE_FORGERY_OFFSET = 0.5

#: Volatility deflation factor (attack 4).
_VOL_DEFLATION_FACTOR = 0.5

#: Fractional lot deltas tried, largest first, for the discrete tamper (attack 5).
_LOT_DELTAS: tuple[float, ...] = (0.5, 0.25, 0.1, 0.01)


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


def _inputs(payload: Any) -> dict[str, Any]:
    """Return the frozen raw-input manifest when present, else ``{}``."""
    for key in ("inputs", "input_manifest", "raw_problem"):
        block = _mapping(payload).get(key)
        if isinstance(block, dict) and block:
            return block
    return _mapping(payload)


def _allocations(payload: Any) -> dict[str, Any]:
    """Return the ``allocations`` mapping when present, else ``{}``."""
    allocs = _mapping(payload).get("allocations")
    return allocs if isinstance(allocs, dict) and allocs else {}


def _returns_array(inputs: dict[str, Any], length: int) -> Any:
    """Return the expected-return vector as an ndarray, else ``None``."""
    value = inputs.get("expected_returns")
    if not isinstance(value, (list, tuple)) or len(value) != length:
        return None
    try:
        return np.asarray([float(v) for v in value], dtype=float)
    except (TypeError, ValueError):
        return None


def _cov_matrix(inputs: dict[str, Any], length: int) -> Any:
    """Return the covariance matrix as an ndarray, else ``None``."""
    value = inputs.get("cov_matrix")
    if not isinstance(value, (list, tuple)) or len(value) != length:
        return None
    try:
        matrix = np.asarray(value, dtype=float)
    except (TypeError, ValueError):
        return None
    if matrix.shape != (length, length) or not np.all(np.isfinite(matrix)):
        return None
    return matrix


def _risk_free(payload: Any, inputs: dict[str, Any]) -> float:
    """Resolve the risk-free rate from the payload or input manifest."""
    for candidate in (payload.get("risk_free_rate"), inputs.get("risk_free_rate")):
        if _is_number(candidate):
            return float(candidate)
    return 0.02


def _mask_metrics(
    changed: dict[str, Any],
    weights: dict[str, float],
    mu: Any,
    sigma: Any,
    risk_free: float,
) -> None:
    """Recompute expected return / volatility / Sharpe from ``weights``."""
    names = list(weights)
    if mu is None or sigma is None:
        return
    w = np.asarray([weights[n] for n in names], dtype=float)
    ret = float(np.dot(w, mu))
    vol = float(np.sqrt(max(float(np.dot(w, np.dot(sigma, w))), 0.0)))
    sharpe = (ret - risk_free) / vol if vol > 0 else 0.0
    changed["expected_return"] = round(ret, 6)
    changed["volatility"] = round(vol, 6)
    changed["sharpe_ratio"] = round(sharpe, 6)


# --------------------------------------------------------------------------- #
# Tamper builders
# --------------------------------------------------------------------------- #
#
# Each builder takes the frozen solution and returns a ``(payload, applied,
# reason)`` triple and must never raise.

def _attack_weight_simplex_violation_injection(
    solution: Any,
) -> tuple[Any, bool, str | None]:
    """Scale the allocations so their sum is no longer 1.0.

    The derived expected return / volatility / Sharpe are re-masked from the
    tampered weights (when the raw inputs are available) so only
    ``weights_sum_to_one`` fails.
    """
    changed = _copy(solution)
    if not isinstance(changed, dict):
        return changed, False, "solution is not a JSON object"
    allocs = _allocations(changed)
    if not allocs:
        return changed, False, "allocations missing or empty"

    inputs = _inputs(changed)
    names = list(allocs)
    mu = _returns_array(inputs, len(names))
    sigma = _cov_matrix(inputs, len(names))
    risk_free = _risk_free(changed, inputs)

    for scale in _SIMPLEX_SCALE_CANDIDATES:
        tampered = {k: round(float(v) * scale, 6) for k, v in allocs.items()}
        changed["allocations"] = tampered
        _mask_metrics(changed, tampered, mu, sigma, risk_free)
        if abs(sum(tampered.values()) - 1.0) > 1e-3:
            return changed, True, None
    # Degenerate fallback: force an obviously broken simplex sum.
    tampered = {k: round(float(v) * _SIMPLEX_SCALE_CANDIDATES[0], 6) for k, v in allocs.items()}
    changed["allocations"] = tampered
    _mask_metrics(changed, tampered, mu, sigma, risk_free)
    return changed, True, None


def _attack_short_position_breach_injection(
    solution: Any,
) -> tuple[Any, bool, str | None]:
    """Inject a -0.15 short position while preserving the unit-simplex sum.

    The shorted weight is redistributed to a second asset so
    ``weights_sum_to_one`` still holds; only ``long_only_bounds`` fails.
    """
    changed = _copy(solution)
    if not isinstance(changed, dict):
        return changed, False, "solution is not a JSON object"
    allocs = _allocations(changed)
    if not allocs:
        return changed, False, "allocations missing or empty"

    names = list(allocs)
    short_name = names[0]
    absorb_name = names[1] if len(names) > 1 else names[0]

    weights = {k: float(v) for k, v in allocs.items()}
    absorbed = weights[short_name] + _SHORT_POSITION
    weights[short_name] = -_SHORT_POSITION
    weights[absorb_name] += absorbed
    changed["allocations"] = {k: round(v, 6) for k, v in weights.items()}

    inputs = _inputs(changed)
    mu = _returns_array(inputs, len(names))
    sigma = _cov_matrix(inputs, len(names))
    risk_free = _risk_free(changed, inputs)
    _mask_metrics(changed, weights, mu, sigma, risk_free)
    return changed, True, None


def _attack_sharpe_ratio_inflation_forgery(solution: Any) -> tuple[Any, bool, str | None]:
    """Over-report the Sharpe ratio by ``_SHARPE_FORGERY_OFFSET``."""
    changed = _copy(solution)
    if not isinstance(changed, dict):
        return changed, False, "solution is not a JSON object"
    if not _is_number(changed.get("sharpe_ratio")):
        return changed, False, "sharpe_ratio missing or not numeric"
    changed["sharpe_ratio"] = round(
        _num(changed.get("sharpe_ratio")) + _SHARPE_FORGERY_OFFSET, 6
    )
    return changed, True, None


def _attack_variance_risk_deflation_forgery(solution: Any) -> tuple[Any, bool, str | None]:
    """Under-report volatility / variance.

    When the raw covariance matrix is available the Sharpe ratio is re-masked
    from the deflationed volatility so only ``volatility_recompute`` fails.
    Without the covariance matrix the Sharpe identity itself is broken.
    """
    changed = _copy(solution)
    if not isinstance(changed, dict):
        return changed, False, "solution is not a JSON object"
    if not _is_number(changed.get("volatility")):
        return changed, False, "volatility missing or not numeric"

    new_vol = _num(changed.get("volatility")) * _VOL_DEFLATION_FACTOR
    changed["volatility"] = round(new_vol, 6)

    inputs = _inputs(changed)
    sigma = _cov_matrix(inputs, len(_allocations(changed)))
    if sigma is None:
        # No covariance matrix: leave Sharpe untouched so the identity breaks.
        return changed, True, None

    ret = _num(changed.get("expected_return"))
    risk_free = _risk_free(changed, inputs)
    changed["sharpe_ratio"] = round((ret - risk_free) / new_vol, 6) if new_vol > 0 else 0.0
    return changed, True, None


def _attack_discrete_lot_allocation_tamper(
    solution: Any,
) -> tuple[Any, bool, str | None]:
    """Tamper an integer share lot to a fractional value (or over-budget).

    Prefers the fractional-lot injection and re-masks the leftover cash so only
    ``discrete_shares_integrality`` fails.  Falls back to a capital-exceeding
    integer lot when no fractional lot fits the budget.
    """
    changed = _copy(solution)
    if not isinstance(changed, dict):
        return changed, False, "solution is not a JSON object"
    discrete = changed.get("discrete_allocation")
    if not isinstance(discrete, dict) or not discrete:
        return changed, False, "discrete_allocation missing or empty"
    shares = discrete.get("shares")
    if not isinstance(shares, dict) or not shares:
        return changed, False, "discrete_allocation.shares missing or empty"
    prices = discrete.get("prices") or _inputs(changed).get("prices") or {}
    if not isinstance(prices, dict) or not prices:
        return changed, False, "prices missing: cannot verify capital feasibility"

    total_value = discrete.get("total_portfolio_value")
    total_value = _num(total_value) if _is_number(total_value) else None

    def _invested(current: dict[str, Any]) -> float:
        return sum(
            _num(current.get(name)) * _num(prices.get(name)) for name in current
        )

    def _mask(current: dict[str, Any], invested: float) -> None:
        discrete["leftover_cash"] = round(total_value - invested, 4)
        discrete["total_invested"] = round(invested, 4)

    # Prefer the cheapest asset and the smallest delta that still fits budget,
    # so only ``discrete_shares_integrality`` fails.
    ordered = sorted(shares, key=lambda n: _num(prices.get(n), float("inf")))
    for delta in _LOT_DELTAS:
        for name in ordered:
            qty = float(shares[name])
            tampered = {k: float(v) for k, v in shares.items()}
            tampered[name] = round(qty + delta, 4)
            invested = _invested(tampered)
            if total_value is None or invested <= total_value + 1e-6:
                shares[name] = tampered[name]
                _mask(shares, invested)
                return changed, True, None

    # Capital-exceed fallback on the cheapest asset.
    name = ordered[0]
    shares[name] = int(float(shares[name])) + 1_000_000
    invested = _invested(shares)
    discrete["leftover_cash"] = 0.0
    discrete["total_invested"] = round(invested, 4)
    return changed, True, None


#: ``attack name -> builder`` in canonical order.
ATTACK_BUILDERS: dict[str, Callable[[Any], tuple[Any, bool, str | None]]] = {
    "weight_simplex_violation_injection": _attack_weight_simplex_violation_injection,
    "short_position_breach_injection": _attack_short_position_breach_injection,
    "sharpe_ratio_inflation_forgery": _attack_sharpe_ratio_inflation_forgery,
    "variance_risk_deflation_forgery": _attack_variance_risk_deflation_forgery,
    "discrete_lot_allocation_tamper": _attack_discrete_lot_allocation_tamper,
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
    """Run the strict Markowitz validator over ``payload``.

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
        checks = validate_portfolio(problem_id, payload)
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
        description="Red-team a frozen Markowitz mean-variance portfolio solution"
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
    print("PASS finance_redteam_gate" if report["ok"] else "FAIL finance_redteam_gate")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
