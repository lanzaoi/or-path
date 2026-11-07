#!/usr/bin/env python3
"""Independent recompute plus deliberate tamper attacks for a Tube solution.

The gate re-runs the strict Tube validator on the frozen candidate and then
injects five deliberate attacks (protocol ``tamper_tests``):

  1. ``numeric_cocut_inflation``   — inflate a Q2 co-cut saving
  2. ``q3_demand_deletion``        — drop a demanded tube from a Q3 sequence
  3. ``q4_inventory_injection``    — inject a phantom remnant into Q4 inventory
  4. ``invalid_lower_bound_claim`` — declare an impossible Q4 lower bound
  5. ``input_hash_tamper``         — corrupt the SHA-256 input manifest

Robustness contract
-------------------

The tamper builders never raise on an unexpected schema.  A solution whose
shape does not match the strict Tube envelope yields attacks with
``applied: false`` and a human-readable ``reason`` instead of a
``KeyError``/``IndexError``/``TypeError``.  Because a tamper that could not be
constructed also cannot be demonstrated to be *blocked*, such an attack is
reported as ``rejected: false`` so the gate fails safely rather than silently
passing on an unverified assertion.

The tamper suite is factored into pure helpers so it can be unit tested
directly:

    build_attacks(solution)              -> [{attack, payload, applied, reason}]
    recompute(problem_id, payload)       -> validation report dict
    run_redteam(solution, problem_id)    -> report dict
    main(argv)                           -> exit code
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

from validate_solution import validate  # noqa: E402

__all__ = [
    "ATTACK_NAMES",
    "SCHEMA",
    "build_attacks",
    "main",
    "recompute",
    "run_redteam",
]

#: Report schema written by this gate.
SCHEMA = "orpath.tube_redteam.v1"

#: Canonical attack order (matches contracts/tube_collaboration_v1.json).
ATTACK_NAMES: tuple[str, ...] = (
    "numeric_cocut_inflation",
    "q3_demand_deletion",
    "q4_inventory_injection",
    "invalid_lower_bound_claim",
    "input_hash_tamper",
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


# --------------------------------------------------------------------------- #
# Tamper builders
# --------------------------------------------------------------------------- #
#
# Each builder takes the frozen solution, returns a ``(payload, applied,
# reason)`` triple and must never raise.

def _attack_numeric_cocut_inflation(solution: Any) -> tuple[Any, bool, str | None]:
    changed = _copy(solution)
    stocks = _dig(changed, "questions", "q2", "stocks")
    if not isinstance(stocks, list) or not stocks:
        return changed, False, "questions.q2.stocks missing or empty"
    target = stocks[0]
    if not isinstance(target, dict) or not _is_number(target.get("co_cut_benefit_mm")):
        return changed, False, "questions.q2.stocks[0].co_cut_benefit_mm not numeric"
    target["co_cut_benefit_mm"] = float(target["co_cut_benefit_mm"]) + 1.0
    return changed, True, None


def _attack_q3_demand_deletion(solution: Any) -> tuple[Any, bool, str | None]:
    changed = _copy(solution)
    stocks = _dig(changed, "questions", "q3", "stocks")
    if not isinstance(stocks, list) or not stocks:
        return changed, False, "questions.q3.stocks missing or empty"
    target = stocks[0]
    if not isinstance(target, dict):
        return changed, False, "questions.q3.stocks[0] is not an object"
    sequence = target.get("sequence")
    if not isinstance(sequence, list) or not sequence:
        return changed, False, "questions.q3.stocks[0].sequence missing or empty"
    sequence.pop()
    return changed, True, None


def _attack_q4_inventory_injection(solution: Any) -> tuple[Any, bool, str | None]:
    changed = _copy(solution)
    batches = _dig(changed, "questions", "q4", "batches")
    if not isinstance(batches, list) or not batches:
        return changed, False, "questions.q4.batches missing or empty"
    target_index = 1 if len(batches) > 1 else 0
    batch = batches[target_index]
    if not isinstance(batch, dict):
        return changed, False, f"questions.q4.batches[{target_index}] is not an object"
    result = batch.get("result")
    if not isinstance(result, dict):
        return changed, False, f"questions.q4.batches[{target_index}].result missing"
    # Prefer the pre-batch ledger (that is what the material-balance chain is
    # recomputed against); fall back to the post-batch ledger.
    for key in ("inventory_before", "inventory_after"):
        ledger = result.get(key)
        if isinstance(ledger, list):
            ledger.append({"id": "REDTEAM-FAKE", "length_mm": 999.0})
            return changed, True, None
    return changed, False, "no inventory ledger list in q4 batch result"


def _attack_invalid_lower_bound_claim(solution: Any) -> tuple[Any, bool, str | None]:
    changed = _copy(solution)
    q4 = _dig(changed, "questions", "q4")
    if not isinstance(q4, dict):
        return changed, False, "questions.q4 missing or not an object"
    incumbent = q4.get("total_new_standard_stock_mm")
    if not _is_number(incumbent):
        incumbent = q4.get("total_stock_length_mm")
    if not _is_number(incumbent):
        return changed, False, "questions.q4 has no numeric incumbent total"
    optimality = q4.get("optimality")
    if not isinstance(optimality, dict):
        # A solution that never declared bounds still gets the impossible claim
        # injected, so the validator's bound-evidence check is exercised.
        optimality = {}
        q4["optimality"] = optimality
    optimality["lower_bound_mm"] = float(incumbent) + 1000.0
    return changed, True, None


def _attack_input_hash_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    changed = _copy(solution)
    hashes = _dig(changed, "model_snapshot", "input_sha256")
    if not isinstance(hashes, dict) or not hashes:
        return changed, False, "model_snapshot.input_sha256 missing or empty"
    first = next(iter(hashes))
    hashes[first] = "0" * 64
    return changed, True, None


#: ``attack name -> builder`` in canonical order.
ATTACK_BUILDERS: dict[str, Callable[[Any], tuple[Any, bool, str | None]]] = {
    "numeric_cocut_inflation": _attack_numeric_cocut_inflation,
    "q3_demand_deletion": _attack_q3_demand_deletion,
    "q4_inventory_injection": _attack_q4_inventory_injection,
    "invalid_lower_bound_claim": _attack_invalid_lower_bound_claim,
    "input_hash_tamper": _attack_input_hash_tamper,
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
    """Run the strict Tube validator, converting any crash into a rejection."""
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "checks": [],
            "errors": ["payload is not a JSON object"],
        }
    try:
        report = validate(problem_id, payload)
    except Exception as exc:  # noqa: BLE001 - malformed payload must not crash the gate
        return {
            "ok": False,
            "checks": [],
            "errors": [f"validator crashed on malformed payload: {type(exc).__name__}: {exc}"],
        }
    if not isinstance(report, dict):
        return {"ok": False, "checks": [], "errors": ["validator returned a non-object report"]}
    return report


def _problem_id(solution: Any, problem_id: str | None) -> str:
    if problem_id:
        return str(problem_id)
    if isinstance(solution, dict) and solution.get("problem_id"):
        return str(solution["problem_id"])
    return "tube_cut_b2026"


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
    parser = argparse.ArgumentParser(description="Red-team a frozen Tube solution")
    parser.add_argument(
        "--solution",
        type=Path,
        default=ROOT / "outputs" / "tube_cut_b2026-solution.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "tube_cut_b2026-redteam.json",
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
    print("PASS tube_redteam_gate" if report["ok"] else "FAIL tube_redteam_gate")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
