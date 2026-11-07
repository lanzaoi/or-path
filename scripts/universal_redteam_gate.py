#!/usr/bin/env python3
"""Universal Redteam Gate (Task 5.2) — one-click 10-domain DIMO adversarial gate.

Runs the unified invariant-mutation red-team matrix across all ten OR-Path
vertical domains (tube, routing, scheduling, project, inventory, facility,
rostering, microgrid, pricing, finance):

  1. Build the *standard frozen solution envelope* for each domain with the
     real local solvers (Numbers Truth: no invented numbers anywhere).
  2. Recompute every pristine envelope through the domain red-team gate's
     independent validator — compliant data must pass 100% (0 false
     positives).
  3. Inject the five canonical DIMO invariant mutations
     (CONSERVATION, CAPACITY, PRECEDENCE, BOUND, HASH) via
     ``orpath.agents.dimo_mutator.DIMOMutator`` and feed each mutated
     payload into the domain gate's validator (``recompute``).
  4. Replay each domain gate's native five-attack matrix (``run_redteam``)
     and require it to agree with the DIMO matrix.
  5. Aggregate interception statistics and emit a structured JSON report.

Interception accounting (honest by construction)
------------------------------------------------
Every injected mutation lands in exactly one bucket:

  * ``intercepted``        — the domain validator rejected the mutated payload.
  * ``unverified_failsafe``— the mutation was applied but the validator
                            cannot verify it on this envelope.  The only
                            documented case is Tube ``HASH`` on the synthetic
                            manifest: ``synthetic://`` URI digests are
                            deliberately never re-hashed (the raw competition
                            attachments never entered Git), so the gate
                            refuses to claim a block it cannot verify.  This
                            row is *proven live* by a positive control that
                            re-points the manifest at a real repository file
                            and shows the strict input-hash recompute catches
                            the tampered digest.
  * ``missed``             — an applied mutation that the validator did NOT
                            reject and that is not a documented fail-safe.
                            Any ``missed`` row fails the gate.
  * ``not_applied``        — a mutation that could not be constructed on the
                            envelope (also fails the gate: an attack that
                            cannot be built cannot be demonstrated blocked).

Exit codes
----------
  0 — every baseline passed, no uncaught mutations, native/DIMO matrices
      agree, and (in ``--strict`` mode) the interception rate is exactly
      100% with zero unverified rows.
  1 — any baseline false positive, missed/not-applied mutation, matrix
      disagreement, envelope-build failure, or (in ``--strict`` mode) an
      interception rate below 100%.

Usage
-----
    python scripts/universal_redteam_gate.py                       # all 10 domains
    python scripts/universal_redteam_gate.py --domain routing      # single domain
    python scripts/universal_redteam_gate.py --strict --out outputs/universal_redteam_report.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tools"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from orpath.agents.dimo_mutator import (  # noqa: E402
    DIMOMutator,
    MutationType,
    stable_hash,
)

__all__ = [
    "SCHEMA",
    "DOMAINS",
    "REDTEAM_PROBLEM_IDS",
    "DOCUMENTED_FAILSAFES",
    "build_standard_envelope",
    "load_domain_gate",
    "main",
    "run_domain_section",
]

#: Report schema written by this gate.
SCHEMA = "orpath.universal_redteam.v1"

#: The ten supported OR-Path vertical domains (mirrors
#: ``orpath.agents.dimo_mutator.SUPPORTED_DOMAINS``).
DOMAINS: tuple[str, ...] = (
    "tube",
    "routing",
    "scheduling",
    "project",
    "inventory",
    "facility",
    "rostering",
    "microgrid",
    "pricing",
    "finance",
)

#: Frozen problem id used when recomputing each domain's envelope (same ids
#: the Phase-3 regression matrix replays the red-team gates with).
REDTEAM_PROBLEM_IDS: dict[str, str] = {
    "tube": "synthetic_tube",
    "routing": "pyvrp_vrptw",
    "scheduling": "jssp_ft06",
    "project": "psplib_rcpsp",
    "inventory": "lot_sizing_clsp60",
    "facility": "cflp_sscflp",
    "rostering": "staff_rostering",
    "microgrid": "microgrid_dispatch",
    "pricing": "farmer_stochastic_lp",
    "finance": "markowitz_portfolio",
}

#: The single documented fail-safe row: on the synthetic Tube manifest the
#: HASH tamper (``input_hash_tamper``) is applied but unverifiable, because
#: ``synthetic://`` digests are deliberately never re-hashed.  Proven live by
#: a positive control against a real-file manifest variant.
DOCUMENTED_FAILSAFES: frozenset[tuple[str, MutationType]] = frozenset(
    {("tube", MutationType.HASH)}
)


# ---------------------------------------------------------------------------
# Envelope construction (Numbers Truth: built by the real local solvers)
# ---------------------------------------------------------------------------

def load_domain_gate(domain: str) -> Any:
    """Import and return the ``scripts.<domain>_redteam_gate`` module."""
    return importlib.import_module(f"scripts.{domain}_redteam_gate")


def build_standard_envelope(domain: str) -> dict[str, Any]:
    """Build the standard frozen solution envelope for ``domain``.

    Envelopes are produced by the real local solvers and the canonical
    geometry builders shared with the Phase-3 regression matrix — the exact
    same construction ``tools/test_phase3_full_regression.domain_envelopes``
    uses, so the universal gate replays the certified matrices.

    Args:
        domain: One of :data:`DOMAINS`.

    Returns:
        The frozen solution envelope (a JSON-serializable dict).

    Raises:
        ValueError: If ``domain`` is not a supported domain.
        ImportError: If the envelope builder or solver cannot be imported.
    """
    dom = domain.strip().lower()
    if dom == "tube":
        from tools.test_phase3_full_regression import _build_tube_envelope

        return _build_tube_envelope()
    if dom == "routing":
        from tools.test_phase3_full_regression import _build_routing_envelope

        return _build_routing_envelope(load_domain_gate("routing"))
    if dom == "microgrid":
        from tools.test_phase3_full_regression import _build_microgrid_envelope

        return _build_microgrid_envelope()
    if dom == "scheduling":
        from solve_jssp import solve_jssp

        return solve_jssp("ft06", time_limit_s=30)
    if dom == "project":
        from solve_rcpsp import solve_rcpsp

        return solve_rcpsp(time_limit_s=30)
    if dom == "inventory":
        from solve_lot_sizing import solve_lot_sizing

        return solve_lot_sizing(method="mip", capacity=60.0, problem_id="lot_sizing_clsp60")
    if dom == "facility":
        from solve_facility import solve_facility_location

        return solve_facility_location(single_source=True, time_limit_s=10)
    if dom == "rostering":
        from solve_staff_rostering import solve_staff_rostering

        return solve_staff_rostering(num_employees=8, num_days=14, time_limit_s=10)
    if dom == "pricing":
        from solve_stochastic_lp import solve_stochastic_lp

        return solve_stochastic_lp()
    if dom == "finance":
        from solve_portfolio import solve_portfolio

        return solve_portfolio(objective_type="max_sharpe", total_portfolio_value=100000.0)
    raise ValueError(f"unsupported domain {domain!r}; allowed: {list(DOMAINS)}")


# ---------------------------------------------------------------------------
# Tube fail-safe positive control
# ---------------------------------------------------------------------------

def _check_ok(report: dict[str, Any], name: str) -> bool | None:
    """Return the ``ok`` flag of the named check inside a validator report."""
    for check in report.get("checks") or []:
        if isinstance(check, dict) and check.get("name") == name:
            return bool(check.get("ok"))
    return None


def tube_failsafe_positive_control(gate: Any, envelope: dict[str, Any]) -> dict[str, Any]:
    """Prove the Tube strict input-hash recompute is live (fail-safe evidence).

    The synthetic manifest's ``synthetic://`` digests are deliberately never
    re-hashed, so the HASH tamper is unverifiable there.  This control
    re-points the manifest at a real repository file (whose digest *is*
    recomputed) and shows that the same tamper is rejected — documenting
    that the unverifiable row is a manifest-policy fail-safe, not a dead
    check.
    """
    rel = "fixtures/t3/tube_cut_b2026/problem.json"
    path = ROOT / rel
    control: dict[str, Any] = {
        "manifest_path": rel,
        "description": (
            "Synthetic manifest URIs are deliberately not re-hashed; the "
            "strict input-hash check is proven live against a real-file "
            "manifest variant of the same envelope."
        ),
    }
    if not path.is_file():
        control["check_live"] = False
        control["note"] = f"real fixture missing: {rel}"
        return control

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    variant = deepcopy(envelope)
    variant["model_snapshot"]["input_sha256"] = {rel: digest}
    baseline = gate.recompute("synthetic_tube", variant)
    baseline_ok = _check_ok(baseline, "strict_input_hashes")

    tampered = deepcopy(variant)
    tampered["model_snapshot"]["input_sha256"][rel] = "0" * 64
    tampered_report = gate.recompute("synthetic_tube", tampered)
    tampered_ok = _check_ok(tampered_report, "strict_input_hashes")

    control["variant_baseline_strict_input_hashes_ok"] = baseline_ok
    control["variant_tampered_strict_input_hashes_ok"] = tampered_ok
    control["check_live"] = baseline_ok is True and tampered_ok is False
    return control


# ---------------------------------------------------------------------------
# Per-domain evaluation
# ---------------------------------------------------------------------------

def _failed_checks(report: dict[str, Any]) -> list[str]:
    """Names of failed checks inside a validator report."""
    return [
        str(check.get("name"))
        for check in report.get("checks") or []
        if isinstance(check, dict) and not check.get("ok")
    ]


def run_domain_section(domain: str, envelope: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate one domain: baseline, DIMO matrix, and native gate replay.

    Args:
        domain: One of :data:`DOMAINS`.
        envelope:
            Optional pre-built standard solution envelope.  When omitted the
            envelope is built with :func:`build_standard_envelope`; callers
            that already hold a certified envelope (e.g. the OR Swarms master
            gate replaying cached envelopes in ``--quick`` mode) may inject it
            so the certified DIMO matrix replays *that* payload verbatim.

    Returns:
        A report section dict with the keys ``domain``, ``problem_id``,
        ``baseline``, ``dimo_attacks``, ``native_gate`` and ``failsafe_control``
        (Tube only).  Any unexpected failure is captured as an ``error`` key
        so the gate fails safely instead of crashing.
    """
    dom = domain.strip().lower()
    pid = REDTEAM_PROBLEM_IDS[dom]
    section: dict[str, Any] = {
        "domain": dom,
        "gate_module": f"scripts.{dom}_redteam_gate",
        "problem_id": pid,
    }
    try:
        gate = load_domain_gate(dom)
        if envelope is None:
            envelope = build_standard_envelope(dom)
        section["envelope_hash"] = stable_hash(envelope)

        # 1) Baseline: compliant data must recompute cleanly (0 false positives).
        baseline = gate.recompute(pid, envelope)
        section["baseline"] = {
            "ok": bool(baseline.get("ok")),
            "check_count": len(baseline.get("checks") or []),
            "failed_checks": _failed_checks(baseline),
        }

        # 2) DIMO mutation matrix: inject the 5 invariant mutations and feed
        #    each mutated payload into the domain validator.
        mutator = DIMOMutator(default_domain=dom)
        rows: list[dict[str, Any]] = []
        for m_type in MutationType:
            row: dict[str, Any] = {
                "mutation_type": m_type.value,
                "applied": False,
                "tampered": False,
                "intercepted": False,
                "status": "not_applied",
                "operator": None,
                "description": None,
                "failed_checks": [],
                "validator_ok": None,
            }
            try:
                result = mutator.mutate(envelope, m_type, domain=dom)
                row["operator"] = result.operator_name
                row["description"] = result.description
                row["applied"] = bool(result.applied)
                row["tampered"] = bool(result.is_tampered)
                row["original_hash"] = result.original_hash
                row["mutated_hash"] = result.mutated_hash

                if not (result.applied and result.is_tampered):
                    row["status"] = "not_applied"
                    row["description"] = (
                        f"mutation could not be constructed: {result.description}"
                    )
                else:
                    vreport = gate.recompute(pid, result.mutated_data)
                    row["validator_ok"] = bool(vreport.get("ok"))
                    row["failed_checks"] = _failed_checks(vreport)
                    if not row["validator_ok"]:
                        row["intercepted"] = True
                        row["status"] = "intercepted"
                    elif (dom, m_type) in DOCUMENTED_FAILSAFES:
                        row["status"] = "unverified_failsafe"
                    else:
                        row["status"] = "missed"
            except Exception as exc:  # noqa: BLE001 - gate fails safe, never crashes
                row["status"] = "error"
                row["description"] = f"mutation raised {type(exc).__name__}: {exc}"
            rows.append(row)
        section["dimo_attacks"] = rows

        # 3) Native gate replay (the gate's own certified 5-attack matrix).
        native = gate.run_redteam(envelope, pid)
        section["native_gate"] = {
            "ok": bool(native.get("ok")),
            "attack_count": int(native.get("attack_count") or 0),
            "attacks_applied": int(native.get("attacks_applied") or 0),
            "unverified_attacks": [
                str(row.get("attack"))
                for row in native.get("attacks") or []
                if row.get("applied") and not row.get("rejected")
            ],
        }

        # 4) Tube: positive control proving the documented fail-safe is live.
        if dom == "tube":
            section["failsafe_positive_control"] = tube_failsafe_positive_control(
                gate, envelope
            )
    except Exception as exc:  # noqa: BLE001 - captured per domain, gate fails safe
        section["error"] = f"{type(exc).__name__}: {exc}"
    return section


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _summarize(sections: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-domain sections into summary statistics."""
    total = applied = intercepted = failsafe = missed = not_applied = errors = 0
    baselines_ok = 0
    baseline_false_positives = 0
    native_ok = 0
    native_failsafe = 0
    matrix_disagreements: list[str] = []

    for section in sections:
        dom = str(section.get("domain"))
        if "error" in section:
            errors += 1
            continue
        baseline = section.get("baseline") or {}
        if baseline.get("ok"):
            baselines_ok += 1
        else:
            baseline_false_positives += 1

        dimo_failsafe_operators: set[str] = set()
        for row in section.get("dimo_attacks") or []:
            total += 1
            if row.get("applied") and row.get("tampered"):
                applied += 1
            else:
                not_applied += 1
                missed += 1  # an unconstructible attack is an uncaught mutation
                continue
            if row.get("intercepted"):
                intercepted += 1
            elif row.get("status") == "unverified_failsafe":
                failsafe += 1
                dimo_failsafe_operators.add(str(row.get("operator")))
            else:
                missed += 1

        native = section.get("native_gate") or {}
        if native.get("ok"):
            native_ok += 1
        else:
            native_failsafe += 1
        if int(native.get("attacks_applied") or 0) != 5:
            matrix_disagreements.append(f"{dom}: native attacks_applied != 5")
        if set(native.get("unverified_attacks") or []) != dimo_failsafe_operators:
            matrix_disagreements.append(
                f"{dom}: native unverified {sorted(native.get('unverified_attacks') or [])} "
                f"!= DIMO unverified {sorted(dimo_failsafe_operators)}"
            )

    rate = (intercepted / total) if total else 0.0
    return {
        "domains_tested": len(sections),
        "domain_errors": errors,
        "baselines_ok": baselines_ok,
        "baseline_false_positives": baseline_false_positives,
        "total_attacks": total,
        "attacks_applied": applied,
        "intercepted": intercepted,
        "unverified_failsafe": failsafe,
        "missed": missed,
        "not_applied": not_applied,
        "interception_rate": round(rate, 6),
        "native_gates_ok": native_ok,
        "native_gates_failsafe": native_failsafe,
        "matrix_disagreements": matrix_disagreements,
    }


def _expected_failsafe_count(domains: list[str]) -> int:
    """Number of documented fail-safe rows expected among ``domains``."""
    return sum(
        1 for dom in domains if (dom.strip().lower(), MutationType.HASH) in DOCUMENTED_FAILSAFES
    )


def build_report(domains: list[str], strict: bool) -> dict[str, Any]:
    """Run the universal red-team matrix and return the full report dict.

    Args:
        domains: Domains to test (a subset of :data:`DOMAINS`).
        strict: Require a 100% interception rate with zero unverified rows.

    Returns:
        The report dict (schema :data:`SCHEMA`) with ``ok``/``verdict`` keys.
    """
    started = time.time()
    sections = [run_domain_section(dom) for dom in domains]
    summary = _summarize(sections)

    expected_failsafes = _expected_failsafe_count(domains)
    tube_control_ok = True
    for section in sections:
        if section.get("domain") == "tube" and "failsafe_positive_control" in section:
            tube_control_ok = bool(section["failsafe_positive_control"].get("check_live"))

    base_ok = (
        summary["domain_errors"] == 0
        and summary["baseline_false_positives"] == 0
        and summary["missed"] == 0
        and summary["not_applied"] == 0
        and summary["unverified_failsafe"] == expected_failsafes
        and not summary["matrix_disagreements"]
        and tube_control_ok
    )
    strict_ok = (
        summary["interception_rate"] == 1.0
        and summary["unverified_failsafe"] == 0
        and summary["missed"] == 0
        and summary["not_applied"] == 0
    )
    ok = base_ok and (strict_ok if strict else True)

    return {
        "schema": SCHEMA,
        "generated_by": "scripts/universal_redteam_gate.py",
        "strict": bool(strict),
        "domains_tested": list(domains),
        "elapsed_seconds": round(time.time() - started, 3),
        "summary": summary,
        "domains": sections,
        "ok": bool(ok),
        "verdict": "PASS" if ok else "FAIL",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_out(out: Path) -> Path:
    """Resolve ``--out`` relative to the repository root."""
    return out if out.is_absolute() else ROOT / out


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code (0 pass, 1 fail)."""
    parser = argparse.ArgumentParser(
        description="Universal 10-domain DIMO invariant red-team gate (Task 5.2)"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help=(
            "Test a single domain (one of: "
            + ", ".join(DOMAINS)
            + "). Omitted => scan and test all 10 domains."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require a 100%% interception rate with zero unverified rows.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/universal_redteam_report.json"),
        help="Report output path (default: outputs/universal_redteam_report.json).",
    )
    args = parser.parse_args(argv)

    if args.domain is not None:
        dom = args.domain.strip().lower()
        if dom not in DOMAINS:
            print(
                f"FAIL universal_redteam_gate: unknown domain {args.domain!r}; "
                f"allowed: {list(DOMAINS)}",
                file=sys.stderr,
            )
            return 1
        domains = [dom]
    else:
        domains = list(DOMAINS)

    report = build_report(domains, strict=args.strict)

    out_path = _resolve_out(args.out)
    report["report_path"] = str(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("PASS universal_redteam_gate" if report["ok"] else "FAIL universal_redteam_gate")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
