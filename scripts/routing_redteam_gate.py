#!/usr/bin/env python3
"""Independent recompute plus five DIMO tamper attacks for a routing solution.

The gate re-runs the strict PyVRP validator
(``tools/validators/extended_solvers.py::validate_pyvrp``) on the frozen
candidate, adds an independent coordinate-integrity hash check, and then
injects five deliberate attacks (protocol ``tamper_tests``):

  1. ``capacity_overflow_injection`` — overload a client demand beyond capacity
  2. ``client_omission_tamper``      — drop a client visit from a route
  3. ``time_window_inversion``       — break visit chronology (end > next start)
  4. ``distance_forgery``            — deflate the declared objective distance
  5. ``coordinate_hash_tamper``      — corrupt the declared coordinate hash

Robustness contract
-------------------

The tamper builders never raise on an unexpected schema.  A solution whose
shape does not match the strict PyVRP envelope yields attacks with
``applied: false`` and a human-readable ``reason`` instead of a
``KeyError``/``IndexError``/``TypeError``.  Because a tamper that could not be
constructed also cannot be demonstrated to be *blocked*, such an attack is
reported as ``rejected: false`` so the gate fails safely rather than silently
passing on an unverified assertion.

The tamper suite is factored into pure helpers so it can be unit tested
directly:

    coordinate_integrity_hash(payload) -> sha256 hexdigest or None
    build_attacks(solution)            -> [{attack, payload, applied, reason}]
    recompute(problem_id, payload)     -> validation report dict
    run_redteam(solution, problem_id)  -> report dict
    main(argv)                         -> exit code
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from validators.extended_solvers import validate_pyvrp  # noqa: E402

__all__ = [
    "ATTACK_NAMES",
    "SCHEMA",
    "build_attacks",
    "coordinate_integrity_hash",
    "main",
    "recompute",
    "run_redteam",
]

#: Report schema written by this gate.
SCHEMA = "orpath.routing_redteam.v1"

#: Canonical attack order (matches contracts/routing_collaboration_v1.json).
ATTACK_NAMES: tuple[str, ...] = (
    "capacity_overflow_injection",
    "client_omission_tamper",
    "time_window_inversion",
    "distance_forgery",
    "coordinate_hash_tamper",
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


def coordinate_integrity_hash(payload: Any) -> str | None:
    """Return a SHA-256 hex digest over the frozen coordinate manifest.

    The manifest is the depot coordinates plus every client's coordinates keyed
    by client name, canonically serialized with sorted keys.  This is the hash
    the auditor freezes and the red team independently recomputes; it is *not*
    recomputed by ``validate_pyvrp`` (which only checks route structure), so the
    red-team gate owns this integrity check.

    Args:
        payload: The frozen solution envelope (any JSON-ish value).

    Returns:
        The hex digest, or ``None`` when the payload has no coordinates.
    """
    if not isinstance(payload, dict):
        return None

    depot = payload.get("raw_depot")
    depot_coords = depot.get("coords") if isinstance(depot, dict) else None

    clients = payload.get("raw_clients")
    client_map: dict[str, Any] = {}
    if isinstance(clients, list):
        for client in clients:
            if isinstance(client, dict) and client.get("name") is not None:
                client_map[str(client["name"])] = client.get("coords")

    canonical = {"depot": depot_coords, "clients": client_map}
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Tamper builders
# --------------------------------------------------------------------------- #
#
# Each builder takes the frozen solution, returns a ``(payload, applied,
# reason)`` triple and must never raise.

def _attack_capacity_overflow_injection(solution: Any) -> tuple[Any, bool, str | None]:
    changed = _copy(solution)
    capacity = _dig(changed, "vehicle_capacity")
    capacity = capacity if _is_number(capacity) else 200
    capacity = int(capacity)

    routes = _dig(changed, "routes")
    if not isinstance(routes, list) or not routes:
        return changed, False, "routes missing or empty"

    for route in routes:
        visits = route.get("visits") if isinstance(route, dict) else None
        if not isinstance(visits, list):
            continue
        for visit in visits:
            if isinstance(visit, dict) and visit.get("type") == "client":
                visit["demand"] = capacity + 1
                return changed, True, None
    return changed, False, "no client visit to overload"


def _attack_client_omission_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    changed = _copy(solution)
    routes = _dig(changed, "routes")
    if not isinstance(routes, list) or not routes:
        return changed, False, "routes missing or empty"

    for route in routes:
        visits = route.get("visits") if isinstance(route, dict) else None
        if not isinstance(visits, list):
            continue
        for visit in visits:
            if isinstance(visit, dict) and visit.get("type") == "client":
                visits.remove(visit)
                return changed, True, None
    return changed, False, "no client visit to omit"


def _attack_time_window_inversion(solution: Any) -> tuple[Any, bool, str | None]:
    changed = _copy(solution)
    routes = _dig(changed, "routes")
    if not isinstance(routes, list) or not routes:
        return changed, False, "routes missing or empty"

    for route in routes:
        visits = route.get("visits") if isinstance(route, dict) else None
        if not isinstance(visits, list) or len(visits) < 2:
            continue
        for index in range(len(visits) - 1):
            current = visits[index] if isinstance(visits[index], dict) else {}
            nxt = visits[index + 1] if isinstance(visits[index + 1], dict) else {}
            curr_start = nxt.get("start_time")
            if not _is_number(curr_start):
                continue
            # Make the previous stop end strictly after the next start.
            current["end_time"] = float(curr_start) + 1.0
            return changed, True, None
    return changed, False, "no chronological pair available"


def _attack_distance_forgery(solution: Any) -> tuple[Any, bool, str | None]:
    changed = _copy(solution)
    routes = _dig(changed, "routes")
    recomputed = 0
    if isinstance(routes, list):
        for route in routes:
            if isinstance(route, dict) and _is_number(route.get("distance")):
                recomputed += int(route["distance"])
    if recomputed == 0:
        return changed, False, "no numeric route distances to forge"
    # Deflate both the envelope objective and total_distance so the sum-of-routes
    # check disagrees with the declared objective.
    forged = recomputed - 5
    changed["objective"] = forged
    changed["total_distance"] = forged
    return changed, True, None


def _attack_coordinate_hash_tamper(solution: Any) -> tuple[Any, bool, str | None]:
    changed = _copy(solution)
    if not isinstance(changed, dict) or "input_coordinates_sha256" not in changed:
        return changed, False, "input_coordinates_sha256 missing"
    changed["input_coordinates_sha256"] = "0" * 64
    return changed, True, None


#: ``attack name -> builder`` in canonical order.
ATTACK_BUILDERS: dict[str, Callable[[Any], tuple[Any, bool, str | None]]] = {
    "capacity_overflow_injection": _attack_capacity_overflow_injection,
    "client_omission_tamper": _attack_client_omission_tamper,
    "time_window_inversion": _attack_time_window_inversion,
    "distance_forgery": _attack_distance_forgery,
    "coordinate_hash_tamper": _attack_coordinate_hash_tamper,
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
    """Run the strict PyVRP validator plus the coordinate-hash integrity check.

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
        checks = validate_pyvrp(problem_id, payload)
    except Exception as exc:  # noqa: BLE001 - malformed payload must not crash the gate
        return {
            "ok": False,
            "checks": [],
            "errors": [f"validator crashed on malformed payload: {type(exc).__name__}: {exc}"],
        }
    if not isinstance(checks, list):
        checks = []

    # Independent coordinate-integrity recompute (not performed by validate_pyvrp).
    declared = payload.get("input_coordinates_sha256")
    computed = coordinate_integrity_hash(payload)
    if isinstance(declared, str) and declared:
        hash_ok = computed is not None and declared == computed
        checks.append(
            {
                "name": "pyvrp_coordinate_integrity_hash",
                "ok": hash_ok,
                "detail": None if hash_ok else "declared coordinate hash mismatch",
            }
        )
    else:
        checks.append(
            {
                "name": "pyvrp_coordinate_integrity_hash",
                "ok": True,
                "detail": "no declared hash; skipped",
            }
        )

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
    return "pyvrp_vrptw"


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
    parser = argparse.ArgumentParser(description="Red-team a frozen routing solution")
    parser.add_argument(
        "--solution",
        type=Path,
        default=ROOT / "outputs" / "pyvrp_vrptw-solution.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "pyvrp_vrptw-redteam.json",
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
    print("PASS routing_redteam_gate" if report["ok"] else "FAIL routing_redteam_gate")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
