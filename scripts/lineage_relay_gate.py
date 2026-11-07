#!/usr/bin/env python3
"""Adversarial gate for the cross-team lineage relay protocol (Task 4.4).

End-to-end red-team gate for ``orpath/agents/lineage_relay.py``.  The gate
first runs *normal* relay flows — a canonical PRP three-stage chain
(scheduling → inventory → routing) and an extended three-relay chain
(scheduling → inventory → routing → execution) — and then injects five
classes of relay attacks:

  1. ``payload_tamper``          — mutate relayed artifacts in flight;
                                   Merkle / payload-hash mismatch must intercept.
  2. ``chain_break``             — forged or damaged parent receipt linkage;
                                   chain continuity must be broken/intercepted.
  3. ``conservation_violation``  — drift a conserved quantity (demand / output
                                   drift), even with re-forged integrity hashes;
                                   the conservation audit must intercept.
  4. ``transition_inversion_replay`` — reversed / unauthorised domain flows,
                                   stale-stage replay and manifest-id reuse.
  5. ``timestamp_sequence_anomaly`` — future timestamps and time regressions.

Contract: every attack is intercepted (100%) and the normal flow passes
(100%).  ``--strict`` additionally requires the *expected* error class on
every interception and zero warnings; otherwise any ``LineageRelayError``
class counts as a successful interception.

Usage::

    python scripts/lineage_relay_gate.py [--strict] [--out PATH]

Exit code 0 = gate passes, 1 = gate fails.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Load the relay module directly so the gate never depends on the agent
# package's LangChain-heavy import surface.
_SPEC = importlib.util.spec_from_file_location(
    "lineage_relay_mod", ROOT / "orpath" / "agents" / "lineage_relay.py"
)
relay = importlib.util.module_from_spec(_SPEC)  # type: ignore[arg-type]
sys.modules[_SPEC.name] = relay  # required by dataclasses on Python >= 3.14
_SPEC.loader.exec_module(relay)

__all__ = [
    "ATTACK_NAMES",
    "FakeClock",
    "build_normal_flows",
    "run_attacks",
    "run_gate",
    "main",
]

ATTACK_NAMES = (
    "payload_tamper",
    "chain_break",
    "conservation_violation",
    "transition_inversion_replay",
    "timestamp_sequence_anomaly",
)

GENESIS_UTC = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    """Deterministic injectable clock for the relay engine."""

    def __init__(self, start: datetime = GENESIS_UTC) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class _Intercepted(Exception):
    """Signal raised by an attack builder when the attack was correctly blocked."""


# ---------------------------------------------------------------------------
# Normal flows
# ---------------------------------------------------------------------------
def _scheduling_solution() -> dict[str, Any]:
    return {
        "problem_id": "prp-demo-scheduling",
        "status": "OPTIMAL",
        "objective": 120.0,
        "jobs": [{"job_id": f"J{i}", "qty": 10.0} for i in range(1, 5)],
    }


def _inventory_input() -> dict[str, Any]:
    return {
        "periods": 4,
        "production_plan": [{"period": p, "qty": 10.0} for p in range(1, 5)],
        "conservation": {
            "total_output": 40.0,
            "num_jobs": 4,
            "num_periods": 4,
            "checks": ["job_count", "period_mass_balance"],
        },
    }


def _inventory_solution() -> dict[str, Any]:
    return {
        "problem_id": "prp-demo-inventory",
        "status": "OPTIMAL",
        "objective": 80.0,
        "orders": [{"customer_id": i, "demand": 20.0} for i in range(1, 6)],
        "conservation": {
            "total_demand": 100.0,
            "total_shipped": 100.0,
            "num_periods": 4,
            "checks": ["aggregate_mass"],
        },
    }


def _routing_input() -> dict[str, Any]:
    return {
        "depot": {"id": 0, "name": "Depot_1", "x": 0.0, "y": 0.0},
        "clients": [
            {"id": i, "name": f"C{i}", "x": float(i * 10), "y": 0.0, "demand": 20.0}
            for i in range(1, 6)
        ],
        "capacity": 200.0,
        "conservation": {
            "total_demand": 100.0,
            "total_shipped": 100.0,
            "num_clients": 5,
            "checks": ["aggregate_mass"],
        },
    }


def _routing_solution() -> dict[str, Any]:
    return {
        "problem_id": "prp-demo-routing",
        "status": "OPTIMAL",
        "objective": 250.0,
        "routes": [{"vehicle": v, "visits": [0, 1, 2]} for v in range(1, 4)],
    }


def _delivery_confirmation() -> dict[str, Any]:
    return {
        "delivered": [{"customer_id": i, "qty": 20.0} for i in range(1, 6)],
        "conservation": {
            "total_demand": 100.0,
            "total_delivered": 100.0,
            "num_clients": 5,
            "checks": ["aggregate_mass"],
        },
    }


def build_normal_flows(engine: relay.LineageRelayEngine, clock: FakeClock) -> dict[str, Any]:
    """Run the canonical PRP chain plus an extended three-relay chain.

    Numbers Truth: every conserved quantity is independently recomputed from
    the raw artifact payloads — nothing is invented.
    """
    # -- PRP canonical chain: scheduling → inventory → routing --------------
    m1, r1 = engine.adapter_from_composite_handoff(
        "scheduling", "inventory", _scheduling_solution(), _inventory_input(),
        pipeline_id="PRP",
    )
    clock.advance(30)
    m2, r2 = engine.adapter_from_composite_handoff(
        "inventory", "routing", _inventory_solution(), _routing_input(),
        pipeline_id="PRP", parent_receipt_id=r1.receipt_id,
    )
    prp_chain_ok = engine.verify_lineage_chain([r1, r2])

    # -- extended three-relay chain (CUSTOM pipeline) ------------------------
    m1b, r1b = engine.adapter_from_composite_handoff(
        "scheduling", "inventory", _scheduling_solution(), _inventory_input(),
        pipeline_id="CUSTOM",
    )
    clock.advance(30)
    m2b, r2b = engine.adapter_from_composite_handoff(
        "inventory", "routing", _inventory_solution(), _routing_input(),
        pipeline_id="CUSTOM", parent_receipt_id=r1b.receipt_id,
    )
    clock.advance(30)
    m3b, r3b = engine.adapter_from_composite_handoff(
        "routing", "execution", _routing_solution(), _delivery_confirmation(),
        pipeline_id="CUSTOM", parent_receipt_id=r2b.receipt_id,
    )
    clock.advance(30)
    chain3_ok = engine.verify_lineage_chain([r1b, r2b, r3b])

    # independently recomputed conservation anchors (Numbers Truth)
    recomputed = {
        "scheduling_output": sum(float(j["qty"]) for j in _scheduling_solution()["jobs"]),
        "inventory_demand": sum(float(o["demand"]) for o in _inventory_solution()["orders"]),
        "routing_delivered": sum(float(d["qty"]) for d in _delivery_confirmation()["delivered"]),
        "composite_objective": round(
            float(_scheduling_solution()["objective"])
            + float(_inventory_solution()["objective"])
            + float(_routing_solution()["objective"]),
            6,
        ),
    }

    normal_ok = (
        prp_chain_ok
        and chain3_ok
        and all(r.status == "VERIFIED" and r.conservation_ok
                for r in (r1, r2, r1b, r2b, r3b))
        and r2.parent_receipt_id == r1.receipt_id
        and r2b.parent_receipt_id == r1b.receipt_id
        and r3b.parent_receipt_id == r2b.receipt_id
        and recomputed["scheduling_output"] == 40.0
        and recomputed["inventory_demand"] == 100.0
        and recomputed["routing_delivered"] == 100.0
        and recomputed["composite_objective"] == 450.0
    )
    return {
        "engine": engine,
        "clock": clock,
        "artifacts": {
            "scheduling_solution": _scheduling_solution(),
            "inventory_input": _inventory_input(),
            "inventory_solution": _inventory_solution(),
            "routing_input": _routing_input(),
            "routing_solution": _routing_solution(),
            "delivery_confirmation": _delivery_confirmation(),
        },
        "prp": {"manifests": [m1, m2], "receipts": [r1, r2], "chain_ok": prp_chain_ok},
        "chain3": {"manifests": [m1b, m2b, m3b], "receipts": [r1b, r2b, r3b],
                   "chain_ok": chain3_ok},
        "recomputed": recomputed,
        "normal_ok": normal_ok,
    }


# ---------------------------------------------------------------------------
# Attack suite
# ---------------------------------------------------------------------------
def _attack_result(name: str, description: str, expected_error: str, fn) -> dict[str, Any]:
    """Execute one attack builder and record whether it was intercepted."""
    try:
        fn()
    except _Intercepted as exc:
        return {
            "attack": name,
            "description": description,
            "expected_error": expected_error,
            "raised_error": "chain rejected",
            "detail": str(exc),
            "intercepted": True,
        }
    except relay.LineageRelayError as exc:
        return {
            "attack": name,
            "description": description,
            "expected_error": expected_error,
            "raised_error": type(exc).__name__,
            "intercepted": True,
        }
    except Exception as exc:  # noqa: BLE001 - an unexpected crash is a gate failure
        return {
            "attack": name,
            "description": description,
            "expected_error": expected_error,
            "raised_error": f"{type(exc).__name__}: {exc}",
            "intercepted": False,
        }
    return {
        "attack": name,
        "description": description,
        "expected_error": expected_error,
        "raised_error": "none",
        "intercepted": False,
    }


def attack_payload_tamper(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    """Attack 1: mutate relayed artifacts in flight — hash/Merkle must fail."""
    engine: relay.LineageRelayEngine = scenario["engine"]
    manifests = scenario["chain3"]["manifests"]

    def _tamper_payload() -> None:
        tampered = deepcopy(manifests[1])  # inventory → routing
        tampered.artifacts["downstream_input"]["capacity"] = 999.0  # silent mutation
        engine.verify_and_issue_receipt(tampered)

    def _tamper_merkle_only() -> None:
        tampered = deepcopy(manifests[1])
        tampered.merkle_root = relay.stable_hash({"forged": "merkle"})
        engine.verify_and_issue_receipt(tampered)

    def _tamper_signed_conservation() -> None:
        # craft a measure-anchored manifest, verify it cleanly, then mutate the
        # *signed* stored actual and re-forge the payload hash
        base = engine.create_manifest(
            "inventory", "routing",
            {"downstream_input": {"total_demand": 100.0}},
            pipeline_id="CUSTOM",
            conservation_proof={
                "checks": {
                    "demand_total": {
                        "expected": 100.0,
                        "measure": "downstream_input.total_demand",
                    },
                },
            },
        )
        engine.verify_and_issue_receipt(base)
        tampered = deepcopy(base)
        tampered.manifest_id = "mf-tampered-conservation-0001"
        tampered.conservation_proof["checks"]["demand_total"]["actual"] = 95.0
        tampered.payload_hash = tampered.recompute_payload_hash()
        engine.verify_and_issue_receipt(tampered)

    return [
        _attack_result(
            "payload_tamper",
            "mutated routing artifact capacity in flight",
            "RelayTamperError", _tamper_payload),
        _attack_result(
            "payload_tamper",
            "replaced Merkle root with a forged root",
            "RelayTamperError", _tamper_merkle_only),
        _attack_result(
            "payload_tamper",
            "mutated signed conservation stored actual (re-forged hash)",
            "RelayTamperError", _tamper_signed_conservation),
    ]


def attack_chain_break(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    """Attack 2: forge / damage parent receipt linkage — chain must break."""
    engine: relay.LineageRelayEngine = scenario["engine"]
    receipts = scenario["chain3"]["receipts"]

    def _forged_parent_id() -> None:
        engine.create_manifest(
            "inventory", "routing",
            {"downstream_input": scenario["artifacts"]["routing_input"]},
            pipeline_id="CUSTOM",
            parent_receipt_id="rc-forged-000000000000",
        )

    def _broken_chain_hash() -> None:
        # corrupt the second receipt's parent_chain_hash → chain continuity fails
        corrupted = relay.LineageReceipt.from_dict(receipts[1].to_dict())
        corrupted.parent_chain_hash = relay.stable_hash({"forged": "parent"})
        if engine.verify_lineage_chain([receipts[0], corrupted, receipts[2]]):
            raise AssertionError("chain with damaged parent_chain_hash unexpectedly verified")
        raise _Intercepted("chain rejected: damaged parent_chain_hash")

    def _missing_link() -> None:
        # drop the first receipt: the second now points at a missing parent
        if engine.verify_lineage_chain([receipts[1], receipts[2]]):
            raise AssertionError("chain without its genesis unexpectedly verified")
        raise _Intercepted("chain rejected: missing genesis link")

    def _stale_parent_slot() -> None:
        # forge a manifest claiming a stale (non-head) receipt as its parent
        stale = relay.LineageReceipt.from_dict(receipts[0].to_dict())
        engine.create_manifest(
            "inventory", "routing",
            {"downstream_input": {"depot": {"id": 0}, "clients": [], "capacity": 200.0}},
            pipeline_id="CUSTOM",
            parent_receipt_id=stale.receipt_id,
        )

    return [
        _attack_result(
            "chain_break",
            "manifest claiming an unknown parent receipt id",
            "RelayChainBrokenError", _forged_parent_id),
        _attack_result(
            "chain_break",
            "receipt chain with damaged parent_chain_hash",
            "chain rejected", _broken_chain_hash),
        _attack_result(
            "chain_break",
            "receipt chain missing its genesis link",
            "chain rejected", _missing_link),
        _attack_result(
            "chain_break",
            "manifest claiming a stale non-head parent receipt",
            "RelayChainBrokenError", _stale_parent_slot),
    ]


def attack_conservation_violation(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    """Attack 3: drift a conserved quantity — the audit must intercept."""
    engine: relay.LineageRelayEngine = scenario["engine"]

    def _drifted_demand_flag_forged() -> None:
        manifest = engine.create_manifest(
            "inventory", "routing",
            {"downstream_input": {"total_demand": 95.0, "total_shipped": 95.0}},
            pipeline_id="CUSTOM",
            conservation_proof={
                "checks": {
                    "demand_total": {"expected": 100.0, "actual": 95.0,
                                     "tol": 1e-6, "ok": True},  # forged ok flag
                },
            },
        )
        engine.verify_and_issue_receipt(manifest)

    def _drifted_demand_measure_audit() -> None:
        # attacker drifts the artifacts AND re-forges payload hash + Merkle root
        manifest = engine.create_manifest(
            "inventory", "routing",
            {"downstream_input": {"total_demand": 95.0, "total_shipped": 95.0}},
            pipeline_id="CUSTOM",
            conservation_proof={
                "checks": {
                    "demand_total": {
                        "expected": 100.0,
                        "measure": "downstream_input.total_demand",
                    },
                },
            },
        )
        manifest.payload_hash = manifest.recompute_payload_hash()
        manifest.merkle_root = manifest.recompute_merkle_root()
        engine.verify_and_issue_receipt(manifest)

    def _drifted_output_measure() -> None:
        manifest = engine.create_manifest(
            "scheduling", "inventory",
            {"downstream_input": {"total_output": 39.0, "total_demand": 40.0}},
            pipeline_id="CUSTOM",
            conservation_proof={
                "checks": {
                    "output_total": {"expected": 40.0, "measure": "downstream_input.total_output"},
                    "demand_total": {"expected": 40.0, "measure": "downstream_input.total_demand"},
                },
            },
        )
        engine.verify_and_issue_receipt(manifest)

    return [
        _attack_result(
            "conservation_violation",
            "demand drift 100 → 95 with forged ok flag",
            "RelayConservationError", _drifted_demand_flag_forged),
        _attack_result(
            "conservation_violation",
            "demand drift with re-forged payload hash and Merkle root",
            "RelayConservationError", _drifted_demand_measure_audit),
        _attack_result(
            "conservation_violation",
            "output drift 40 → 39 measured straight from artifacts",
            "RelayConservationError", _drifted_output_measure),
    ]


def attack_transition_inversion_replay(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    """Attack 4: reversed/unauthorised transitions, stale replay, id reuse."""
    engine: relay.LineageRelayEngine = scenario["engine"]
    manifests = scenario["chain3"]["manifests"]

    def _inverted_transition() -> None:
        # routing → inventory is the inverted direction of the PRP chain
        engine.create_manifest(
            "routing", "inventory",
            {"downstream_input": {"depot": {"id": 0}}},
            pipeline_id="PRP",
        )

    def _unauthorized_transition() -> None:
        # facility → scheduling is not part of any canonical pipeline topology
        engine.create_manifest(
            "facility", "scheduling",
            {"downstream_input": {"jobs": []}},
            pipeline_id="PRP",
        )

    def _stale_stage_replay() -> None:
        # re-pack of stage-2 content with a stale sequence on the busy pipeline
        manifest = engine.create_manifest(
            "inventory", "routing",
            {"downstream_input": scenario["artifacts"]["routing_input"]},
            pipeline_id="CUSTOM",
            sequence=2,  # below the pipeline's verified head (stale replay)
        )
        engine.verify_and_issue_receipt(manifest)

    def _manifest_id_reuse() -> None:
        head_receipt = engine.chain_head("CUSTOM")
        assert head_receipt is not None
        forged = relay.ArtifactRelayManifest.from_dict(manifests[2].to_dict())
        forged.artifacts["upstream_solution"]["objective"] = 1.0  # different content
        forged.parent_receipt_id = head_receipt.receipt_id  # anchor to current head
        forged.timestamp = scenario["clock"].now.isoformat()
        forged.sequence = 100  # ahead of the pipeline head (not a sequence attack)
        forged.payload_hash = forged.recompute_payload_hash()
        forged.merkle_root = forged.recompute_merkle_root()
        engine.verify_and_issue_receipt(forged)

    return [
        _attack_result(
            "transition_inversion_replay",
            "inverted domain transition routing → inventory in PRP",
            "RelaySequenceError", _inverted_transition),
        _attack_result(
            "transition_inversion_replay",
            "unauthorised transition facility → scheduling in PRP",
            "RelaySequenceError", _unauthorized_transition),
        _attack_result(
            "transition_inversion_replay",
            "stale stage-2 manifest replayed after stage-3",
            "RelaySequenceError", _stale_stage_replay),
        _attack_result(
            "transition_inversion_replay",
            "manifest id reused with different payload",
            "RelayTamperError", _manifest_id_reuse),
    ]


def attack_timestamp_sequence_anomaly(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    """Attack 5: future timestamps and time regressions."""
    engine: relay.LineageRelayEngine = scenario["engine"]
    clock: FakeClock = scenario["clock"]

    def _future_timestamp() -> None:
        manifest = engine.create_manifest(
            "inventory", "routing",
            {"downstream_input": {"depot": {"id": 0}}},
            pipeline_id="CUSTOM",
            timestamp=clock.now + timedelta(hours=24),  # 24h in the future
        )
        engine.verify_and_issue_receipt(manifest)

    def _timestamp_regression() -> None:
        manifest = engine.create_manifest(
            "inventory", "routing",
            {"downstream_input": {"depot": {"id": 0}}},
            pipeline_id="CUSTOM",
            timestamp=clock.now - timedelta(hours=2),  # time reversal
        )
        engine.verify_and_issue_receipt(manifest)

    def _sequence_regression() -> None:
        manifest = engine.create_manifest(
            "inventory", "routing",
            {"downstream_input": {"depot": {"id": 0}}},
            pipeline_id="CUSTOM",
            sequence=1,  # below the pipeline's verified head
        )
        engine.verify_and_issue_receipt(manifest)

    return [
        _attack_result(
            "timestamp_sequence_anomaly",
            "manifest timestamp 24h in the future",
            "RelaySequenceError", _future_timestamp),
        _attack_result(
            "timestamp_sequence_anomaly",
            "manifest timestamp regressed 2h into the past",
            "RelaySequenceError", _timestamp_regression),
        _attack_result(
            "timestamp_sequence_anomaly",
            "manifest sequence below the pipeline head",
            "RelaySequenceError", _sequence_regression),
    ]


# ---------------------------------------------------------------------------
# Gate driver
# ---------------------------------------------------------------------------
def run_attacks(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for suite in (
        attack_payload_tamper,
        attack_chain_break,
        attack_conservation_violation,
        attack_transition_inversion_replay,
        attack_timestamp_sequence_anomaly,
    ):
        results.extend(suite(scenario))
    return results


def run_gate(strict: bool = False) -> dict[str, Any]:
    clock = FakeClock()
    engine = relay.LineageRelayEngine(clock=clock)
    scenario = build_normal_flows(engine, clock)
    attacks = run_attacks(scenario)

    intercepted = sum(1 for a in attacks if a["intercepted"])
    total = len(attacks)
    warnings: list[str] = []
    for a in attacks:
        if not a["intercepted"]:
            warnings.append(f"attack not intercepted: {a['attack']} — {a['description']}")
        elif strict and a["raised_error"] != a["expected_error"]:
            warnings.append(
                f"strict mode: {a['attack']} raised {a['raised_error']} "
                f"(expected {a['expected_error']})"
            )

    normal_ok = bool(scenario["normal_ok"])
    interception_rate = intercepted / total if total else 0.0
    gate_ok = normal_ok and interception_rate == 1.0 and not (strict and warnings)

    return {
        "gate": "lineage_relay_gate",
        "strict": strict,
        "ok": gate_ok,
        "normal_flow": {
            "pipeline": "PRP (scheduling → inventory → routing) + extended 3-relay chain",
            "prp_chain_continuous": scenario["prp"]["chain_ok"],
            "chain3_continuous": scenario["chain3"]["chain_ok"],
            "relays_verified": len(scenario["chain3"]["receipts"]) + len(scenario["prp"]["receipts"]),
            "receipts": [r.to_dict() for r in scenario["chain3"]["receipts"]],
            "recomputed_conservation": scenario["recomputed"],
        },
        "attacks_total": total,
        "attacks_intercepted": intercepted,
        "interception_rate": interception_rate,
        "normal_pass_rate": 1.0 if normal_ok else 0.0,
        "attacks": attacks,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adversarial gate for the lineage relay protocol")
    parser.add_argument("--strict", action="store_true",
                        help="require the exact expected error class per attack and zero warnings")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "outputs" / "lineage_relay_gate_report.json",
                        help="where to write the JSON gate report")
    args = parser.parse_args(argv)

    report = run_gate(strict=args.strict)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        "PASS lineage_relay_gate"
        if report["ok"] else "FAIL lineage_relay_gate"
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
