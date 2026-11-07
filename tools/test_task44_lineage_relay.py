"""Unit tests for the cross-team lineage relay protocol (Task 4.4).

Covers:

  * canonical hashing, Merkle roots, timestamp parsing
  * :class:`ArtifactRelayManifest` / :class:`LineageReceipt` (de)serialisation
  * :class:`LineageRelayEngine` — packing, strict verification, receipt
    issuance, chain continuity, conservation audits, sequence safety
  * every relay exception class, triggered through realistic attacks
  * ``adapter_from_composite_handoff`` integration with the composite-lead
    handoff transformers (``transform_facility_to_routing``)
  * the adversarial CLI gate ``scripts/lineage_relay_gate.py`` (normal mode
    and ``--strict``)
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.agents.lineage_relay import (  # noqa: E402
    ALLOWED_DOMAIN_TRANSITIONS,
    CONSERVATION_TOL,
    GENESIS_CHAIN_HASH,
    ArtifactRelayManifest,
    LineageReceipt,
    LineageRelayEngine,
    LineageRelayError,
    RelayChainBrokenError,
    RelayConservationError,
    RelaySequenceError,
    RelayTamperError,
    adapter_from_composite_handoff,
    artifact_leaf_hash,
    build_merkle_root,
    canonical_json,
    format_timestamp,
    parse_timestamp,
    stable_hash,
)

GENESIS = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, start: datetime = GENESIS) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


# ---------------------------------------------------------------------------
# Hashing / Merkle / timestamps
# ---------------------------------------------------------------------------
def test_canonical_json_sorted_keys():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_stable_hash_deterministic_and_order_free():
    a = stable_hash({"x": [1, 2], "y": {"k": "v"}})
    b = stable_hash({"y": {"k": "v"}, "x": [1, 2]})
    assert a == b
    assert a != stable_hash({"x": [1, 2], "y": {"k": "w"}})
    assert len(a) == 64


def test_merkle_root_deterministic_and_sensitive():
    leaves = [stable_hash(f"leaf-{i}") for i in range(5)]
    root = build_merkle_root(leaves)
    assert root == build_merkle_root(deepcopy(leaves))  # deterministic
    assert root != build_merkle_root([leaves[0], *leaves[2:]])  # leaf change detected
    assert build_merkle_root([]) == hashlib.sha256(b"").hexdigest()
    assert build_merkle_root([leaves[0]]) == leaves[0]


def test_artifact_leaf_hash_isolates_payload():
    leaf = artifact_leaf_hash("a1", {"v": 1})
    assert leaf != artifact_leaf_hash("a2", {"v": 1})
    assert leaf != artifact_leaf_hash("a1", {"v": 2})


def test_parse_timestamp_formats():
    assert parse_timestamp("2026-01-01T00:00:00Z") == GENESIS
    assert parse_timestamp("2026-01-01T00:00:00+00:00") == GENESIS
    assert parse_timestamp("2026-01-01T08:00:00+08:00") == GENESIS
    assert parse_timestamp(0) == datetime(1970, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert parse_timestamp(GENESIS.timestamp()) == GENESIS
    assert parse_timestamp(GENESIS) == GENESIS
    assert format_timestamp("2026-01-01T00:00:00Z").startswith("2026-01-01T00:00:00")


def test_parse_timestamp_invalid():
    for bad in ("not-a-time", "", None, True, object()):
        with pytest.raises(LineageRelayError):
            parse_timestamp(bad)


# ---------------------------------------------------------------------------
# ArtifactRelayManifest
# ---------------------------------------------------------------------------
def _engine():
    return LineageRelayEngine(clock=FakeClock())


def _sample_manifest() -> ArtifactRelayManifest:
    engine = _engine()
    return engine.create_manifest(
        "scheduling", "inventory",
        {"upstream_solution": {"objective": 10.0}, "downstream_input": {"periods": 2}},
        pipeline_id="PRP",
        conservation_proof={"total_output": 10.0, "checks": ["mass"]},
    )


def test_manifest_roundtrip_dict_and_json():
    m = _sample_manifest()
    d = m.to_dict()
    m2 = ArtifactRelayManifest.from_dict(d)
    assert m2 == m
    m3 = ArtifactRelayManifest.from_json(m.to_json())
    assert m3 == m
    assert ArtifactRelayManifest.from_dict(json.loads(m.to_json())) == m


def test_manifest_hash_stable_over_serialisation():
    m = _sample_manifest()
    m2 = ArtifactRelayManifest.from_dict(m.to_dict())
    assert m2.recompute_payload_hash() == m.payload_hash
    assert m2.recompute_merkle_root() == m.merkle_root


def test_manifest_from_dict_strict_validation():
    m = _sample_manifest()
    bad = m.to_dict()
    del bad["manifest_id"]
    with pytest.raises(LineageRelayError):
        ArtifactRelayManifest.from_dict(bad)
    bad2 = m.to_dict()
    bad2["artifacts"] = [1, 2]
    with pytest.raises(LineageRelayError):
        ArtifactRelayManifest.from_dict(bad2)
    with pytest.raises(LineageRelayError):
        ArtifactRelayManifest.from_dict("not-a-dict")


def test_manifest_fingerprints_detect_mutation():
    m = _sample_manifest()
    mutated = deepcopy(m)
    mutated.artifacts["downstream_input"]["periods"] = 3
    assert mutated.recompute_payload_hash() != m.payload_hash
    assert mutated.recompute_merkle_root() != m.merkle_root


def test_manifest_deterministic_id():
    a = _engine().create_manifest("scheduling", "inventory", {"x": 1}, pipeline_id="PRP")
    b = _engine().create_manifest("scheduling", "inventory", {"x": 1}, pipeline_id="PRP")
    assert a.manifest_id == b.manifest_id


# ---------------------------------------------------------------------------
# LineageReceipt
# ---------------------------------------------------------------------------
def test_receipt_roundtrip_and_chain_hash():
    engine = _engine()
    manifest = engine.create_manifest(
        "scheduling", "inventory", {"x": 1}, pipeline_id="PRP")
    receipt = engine.verify_and_issue_receipt(manifest)
    r2 = LineageReceipt.from_dict(receipt.to_dict())
    assert r2 == receipt
    r3 = LineageReceipt.from_json(receipt.to_json())
    assert r3 == receipt
    assert r2.recompute_chain_hash() == receipt.chain_hash
    # chain hash is sensitive to receipt content
    tampered_ts = LineageReceipt.from_dict(receipt.to_dict())
    tampered_ts.verified_at = "2099-01-01T00:00:00+00:00"
    assert tampered_ts.recompute_chain_hash() != receipt.chain_hash


def test_receipt_from_dict_strict():
    engine = _engine()
    receipt = engine.verify_and_issue_receipt(
        engine.create_manifest("scheduling", "inventory", {"x": 1}, pipeline_id="PRP"))
    bad = receipt.to_dict()
    del bad["receipt_id"]
    with pytest.raises(LineageRelayError):
        LineageReceipt.from_dict(bad)
    bad2 = receipt.to_dict()
    bad2["conservation_ok"] = "yes"
    with pytest.raises(LineageRelayError):
        LineageReceipt.from_dict(bad2)


def test_receipt_chain_hash_links_parent():
    engine = LineageRelayEngine(clock=FakeClock())
    clock: FakeClock = engine._clock  # type: ignore[assignment]
    m1 = engine.create_manifest("scheduling", "inventory", {"x": 1}, pipeline_id="PRP")
    r1 = engine.verify_and_issue_receipt(m1)
    clock.advance(10)
    m2 = engine.create_manifest(
        "inventory", "routing", {"y": 2}, pipeline_id="PRP",
        parent_receipt_id=r1.receipt_id)
    r2 = engine.verify_and_issue_receipt(m2)
    assert r2.parent_receipt_id == r1.receipt_id
    assert r2.parent_chain_hash == r1.chain_hash
    assert r2.recompute_chain_hash() == r2.chain_hash
    tampered = LineageReceipt.from_dict(r2.to_dict())
    tampered.parent_chain_hash = "deadbeef"
    assert tampered.recompute_chain_hash() != r2.chain_hash


# ---------------------------------------------------------------------------
# Engine: create_manifest
# ---------------------------------------------------------------------------
def test_create_manifest_fields_and_normalised_proof():
    engine = _engine()
    manifest = engine.create_manifest(
        "scheduling", "inventory",
        {"a": 1},
        pipeline_id="PRP",
        conservation_proof={"total_output": 40.0, "num_jobs": 4,
                            "checks": ["job_count"]},
    )
    assert manifest.source_domain == "scheduling"
    assert manifest.target_domain == "inventory"
    assert manifest.pipeline_id == "PRP"
    assert manifest.sequence == 1
    assert manifest.parent_receipt_id is None
    assert manifest.timestamp.startswith("2026-01-01T00:00:00")
    checks = manifest.conservation_proof["checks"]
    assert set(checks) == {"total_output", "num_jobs"}
    assert checks["total_output"]["expected"] == 40.0
    assert checks["total_output"]["actual"] == 40.0
    assert checks["total_output"]["ok"] is True
    assert manifest.conservation_proof["check_names"] == ["job_count"]
    assert manifest.conservation_proof["summary"]["ok"] is True
    assert len(manifest.payload_hash) == 64
    assert len(manifest.merkle_root) == 64
    assert manifest.manifest_id.startswith("mf-")


def test_create_manifest_measure_measures_artifacts():
    engine = _engine()
    manifest = engine.create_manifest(
        "inventory", "routing",
        {"downstream_input": {"total_demand": 100.0}},
        pipeline_id="CUSTOM",
        conservation_proof={
            "checks": {
                "demand_total": {"expected": 100.0,
                                 "measure": "downstream_input.total_demand"}},
        },
    )
    check = manifest.conservation_proof["checks"]["demand_total"]
    assert check["actual"] == 100.0
    assert check["measure"] == "downstream_input.total_demand"
    assert check["ok"] is True


def test_create_manifest_measure_drift_records_not_ok():
    engine = _engine()
    manifest = engine.create_manifest(
        "inventory", "routing",
        {"downstream_input": {"total_demand": 95.0}},
        pipeline_id="CUSTOM",
        conservation_proof={
            "checks": {
                "demand_total": {"expected": 100.0,
                                 "measure": "downstream_input.total_demand"}},
        },
    )
    check = manifest.conservation_proof["checks"]["demand_total"]
    assert check["actual"] == 95.0
    assert check["ok"] is False
    assert manifest.conservation_proof["summary"]["ok"] is False


def test_create_manifest_invalid_inputs():
    engine = _engine()
    with pytest.raises(LineageRelayError):
        engine.create_manifest("", "inventory", {}, pipeline_id="PRP")
    with pytest.raises(LineageRelayError):
        engine.create_manifest("scheduling", "", {}, pipeline_id="PRP")
    with pytest.raises(LineageRelayError):
        engine.create_manifest("scheduling", "inventory", [], pipeline_id="PRP")
    with pytest.raises(LineageRelayError):
        engine.create_manifest("scheduling", "inventory", {}, pipeline_id="")
    with pytest.raises(LineageRelayError):
        engine.create_manifest(
            "inventory", "routing", {"x": 1}, pipeline_id="CUSTOM",
            conservation_proof={"checks": {"c": {"expected": 1.0}}})  # no actual/measure


def test_create_manifest_topology_guard():
    engine = _engine()
    # inverted transition on a known pipeline
    with pytest.raises(RelaySequenceError):
        engine.create_manifest("routing", "inventory", {"x": 1}, pipeline_id="PRP")
    # unauthorised transition on a known pipeline
    with pytest.raises(RelaySequenceError):
        engine.create_manifest("facility", "scheduling", {"x": 1}, pipeline_id="PRP")
    # unknown pipelines are unrestricted
    ok = engine.create_manifest("facility", "scheduling", {"x": 1}, pipeline_id="MY_PIPE")
    assert ok.source_domain == "facility"


def test_create_manifest_parent_receipt_validation():
    engine = LineageRelayEngine(clock=FakeClock())
    clock: FakeClock = engine._clock  # type: ignore[assignment]
    m1 = engine.create_manifest("scheduling", "inventory", {"x": 1}, pipeline_id="PRP")
    r1 = engine.verify_and_issue_receipt(m1)
    clock.advance(5)
    m2 = engine.create_manifest(
        "inventory", "routing", {"y": 2}, pipeline_id="PRP",
        parent_receipt_id=r1.receipt_id)
    r2 = engine.verify_and_issue_receipt(m2)
    clock.advance(5)
    # unknown parent
    with pytest.raises(RelayChainBrokenError):
        engine.create_manifest("inventory", "routing", {"z": 3}, pipeline_id="PRP",
                               parent_receipt_id="rc-unknown")
    # stale (non-head) parent
    with pytest.raises(RelayChainBrokenError):
        engine.create_manifest("inventory", "routing", {"z": 3}, pipeline_id="PRP",
                               parent_receipt_id=r1.receipt_id)
    # parent from another pipeline
    other = LineageRelayEngine(clock=FakeClock())
    mo = other.create_manifest("inventory", "routing", {"x": 1}, pipeline_id="IRP")
    ro = other.verify_and_issue_receipt(mo)
    with pytest.raises(RelayChainBrokenError):
        engine.create_manifest("inventory", "routing", {"z": 3}, pipeline_id="PRP",
                               parent_receipt_id=ro.receipt_id)
    # valid parent still works (head r2)
    m3 = engine.create_manifest(
        "inventory", "routing", {"z": 3}, pipeline_id="PRP",
        parent_receipt_id=r2.receipt_id)
    assert m3.parent_receipt_id == r2.receipt_id


def test_sequence_autoincrement_per_pipeline():
    engine = LineageRelayEngine(clock=FakeClock())
    clock: FakeClock = engine._clock  # type: ignore[assignment]
    m1 = engine.create_manifest("scheduling", "inventory", {"x": 1}, pipeline_id="PRP")
    clock.advance(1)
    m2 = engine.create_manifest("inventory", "routing", {"y": 2}, pipeline_id="PRP")
    assert m1.sequence == 1 and m2.sequence == 2
    # independent pipelines keep independent counters
    mi = engine.create_manifest("inventory", "routing", {"z": 3}, pipeline_id="IRP")
    assert mi.sequence == 1


# ---------------------------------------------------------------------------
# Engine: verify_and_issue_receipt
# ---------------------------------------------------------------------------
def test_verify_happy_path():
    engine = _engine()
    manifest = _sample_manifest()
    receipt = engine.verify_and_issue_receipt(manifest)
    assert receipt.status == "VERIFIED"
    assert receipt.conservation_ok is True
    assert receipt.manifest_id == manifest.manifest_id
    assert receipt.parent_receipt_id is None
    assert receipt.parent_chain_hash == GENESIS_CHAIN_HASH
    assert receipt.chain_hash == receipt.recompute_chain_hash()
    assert receipt.details["artifacts_count"] == 2
    assert receipt.details["pipeline_id"] == "PRP"
    assert engine.chain_head("PRP").receipt_id == receipt.receipt_id


def test_verify_accepts_dict_input():
    engine = _engine()
    manifest = _sample_manifest()
    receipt = engine.verify_and_issue_receipt(manifest.to_dict())
    assert receipt.status == "VERIFIED"


def test_verify_payload_tamper_blocked():
    engine = _engine()
    manifest = _sample_manifest()
    engine.verify_and_issue_receipt(manifest)
    tampered = deepcopy(manifest)
    tampered.artifacts["upstream_solution"]["objective"] = 999.0
    with pytest.raises(RelayTamperError):
        engine.verify_and_issue_receipt(tampered)


def test_verify_merkle_tamper_blocked():
    engine = _engine()
    manifest = _sample_manifest()
    tampered = deepcopy(manifest)
    tampered.merkle_root = "0" * 64
    with pytest.raises(RelayTamperError):
        engine.verify_and_issue_receipt(tampered)


def test_verify_conservation_drift_blocked():
    engine = _engine()
    manifest = engine.create_manifest(
        "inventory", "routing",
        {"downstream_input": {"total_demand": 95.0}},
        pipeline_id="CUSTOM",
        conservation_proof={
            "checks": {
                "demand_total": {"expected": 100.0,
                                 "measure": "downstream_input.total_demand"}},
        },
    )
    with pytest.raises(RelayConservationError):
        engine.verify_and_issue_receipt(manifest)


def test_verify_forged_ok_flag_blocked():
    engine = _engine()
    manifest = engine.create_manifest(
        "inventory", "routing",
        {"downstream_input": {"total_demand": 95.0}},
        pipeline_id="CUSTOM",
        conservation_proof={
            "checks": {"demand_total": {"expected": 100.0, "actual": 95.0,
                                        "tol": 1e-6, "ok": True}},
        },
    )
    with pytest.raises(RelayConservationError):
        engine.verify_and_issue_receipt(manifest)


def test_verify_hash_forgery_still_blocked_by_measure():
    engine = _engine()
    manifest = engine.create_manifest(
        "inventory", "routing",
        {"downstream_input": {"total_demand": 95.0}},
        pipeline_id="CUSTOM",
        conservation_proof={
            "checks": {
                "demand_total": {"expected": 100.0,
                                 "measure": "downstream_input.total_demand"}},
        },
    )
    # attacker re-forges both integrity fingerprints over the drifted payload
    manifest.payload_hash = manifest.recompute_payload_hash()
    manifest.merkle_root = manifest.recompute_merkle_root()
    with pytest.raises(RelayConservationError):
        engine.verify_and_issue_receipt(manifest)


def test_verify_stored_actual_mutation_blocked():
    engine = _engine()
    base = engine.create_manifest(
        "inventory", "routing",
        {"downstream_input": {"total_demand": 100.0}},
        pipeline_id="CUSTOM",
        conservation_proof={
            "checks": {
                "demand_total": {"expected": 100.0,
                                 "measure": "downstream_input.total_demand"}},
        },
    )
    engine.verify_and_issue_receipt(base)
    tampered = deepcopy(base)
    tampered.manifest_id = "mf-tampered-0001"
    tampered.conservation_proof["checks"]["demand_total"]["actual"] = 95.0
    tampered.payload_hash = tampered.recompute_payload_hash()
    with pytest.raises(RelayTamperError):
        engine.verify_and_issue_receipt(tampered)


def test_verify_future_timestamp_blocked():
    engine = LineageRelayEngine(clock=FakeClock())
    future = (GENESIS + timedelta(hours=24)).isoformat()
    manifest = engine.create_manifest(
        "scheduling", "inventory", {"x": 1}, pipeline_id="PRP",
        timestamp=future)
    with pytest.raises(RelaySequenceError):
        engine.verify_and_issue_receipt(manifest)


def test_verify_timestamp_regression_blocked():
    engine = LineageRelayEngine(clock=FakeClock())
    clock: FakeClock = engine._clock  # type: ignore[assignment]
    m1 = engine.create_manifest("scheduling", "inventory", {"x": 1}, pipeline_id="PRP")
    engine.verify_and_issue_receipt(m1)
    clock.advance(60)
    past = (clock.now - timedelta(hours=2)).isoformat()
    m2 = engine.create_manifest(
        "inventory", "routing", {"y": 2}, pipeline_id="PRP", timestamp=past)
    with pytest.raises(RelaySequenceError):
        engine.verify_and_issue_receipt(m2)


def test_verify_sequence_regression_blocked():
    engine = LineageRelayEngine(clock=FakeClock())
    clock: FakeClock = engine._clock  # type: ignore[assignment]
    m1 = engine.create_manifest("scheduling", "inventory", {"x": 1}, pipeline_id="PRP")
    engine.verify_and_issue_receipt(m1)
    clock.advance(5)
    m2 = engine.create_manifest(
        "inventory", "routing", {"y": 2}, pipeline_id="PRP", sequence=1)
    with pytest.raises(RelaySequenceError):
        engine.verify_and_issue_receipt(m2)


def test_verify_expected_parent_mismatch_blocked():
    engine = LineageRelayEngine(clock=FakeClock())
    clock: FakeClock = engine._clock  # type: ignore[assignment]
    m1 = engine.create_manifest("scheduling", "inventory", {"x": 1}, pipeline_id="PRP")
    r1 = engine.verify_and_issue_receipt(m1)
    clock.advance(5)
    m2 = engine.create_manifest(
        "inventory", "routing", {"y": 2}, pipeline_id="PRP",
        parent_receipt_id=r1.receipt_id)
    with pytest.raises(RelayChainBrokenError):
        engine.verify_and_issue_receipt(m2, expected_parent_receipt_id="rc-other")


def test_verify_replay_idempotent_and_id_reuse():
    engine = _engine()
    manifest = _sample_manifest()
    r1 = engine.verify_and_issue_receipt(manifest)
    r2 = engine.verify_and_issue_receipt(manifest)  # exact replay
    assert r1.receipt_id == r2.receipt_id
    forged = deepcopy(manifest)
    forged.artifacts["upstream_solution"]["objective"] = 123.0
    forged.payload_hash = forged.recompute_payload_hash()
    forged.merkle_root = forged.recompute_merkle_root()
    with pytest.raises(RelayTamperError):
        engine.verify_and_issue_receipt(forged)


# ---------------------------------------------------------------------------
# check_conservation / require_conservation
# ---------------------------------------------------------------------------
def test_check_conservation_float_int_and_drift():
    engine = _engine()
    assert engine.check_conservation("demand", 100, 100.0, 1e-6) is True
    assert engine.check_conservation("demand", 100.0, 99.9999995, 1e-6) is True
    assert engine.check_conservation("demand", 100.0, 95.0, 1e-6) is False
    assert engine.check_conservation("demand", 10, 10, tol=0.0) is True


def test_check_conservation_non_numeric():
    engine = _engine()
    with pytest.raises(LineageRelayError):
        engine.check_conservation("demand", "abc", 1.0)


def test_require_conservation_raises():
    engine = _engine()
    assert engine.require_conservation("demand", 5, 5) is True
    with pytest.raises(RelayConservationError):
        engine.require_conservation("demand", 100.0, 95.0)


# ---------------------------------------------------------------------------
# verify_lineage_chain
# ---------------------------------------------------------------------------
def _three_stage_chain(engine=None, clock=None):
    if engine is None:
        engine = LineageRelayEngine(clock=clock or FakeClock())
        clock = clock or engine._clock  # type: ignore[assignment]
    m1 = engine.create_manifest("scheduling", "inventory", {"x": 1}, pipeline_id="PRP")
    r1 = engine.verify_and_issue_receipt(m1)
    clock.advance(10)
    m2 = engine.create_manifest("inventory", "routing", {"y": 2}, pipeline_id="PRP",
                                parent_receipt_id=r1.receipt_id)
    r2 = engine.verify_and_issue_receipt(m2)
    clock.advance(10)
    m3 = engine.create_manifest("inventory", "routing", {"z": 3}, pipeline_id="PRP",
                                parent_receipt_id=r2.receipt_id)
    r3 = engine.verify_and_issue_receipt(m3)
    return engine, clock, [r1, r2, r3]


def test_verify_lineage_chain_valid():
    engine, _, receipts = _three_stage_chain()
    assert engine.verify_lineage_chain(receipts) is True
    # order-insensitive by verified_at
    assert engine.verify_lineage_chain(list(reversed(receipts))) is True
    # dict inputs accepted
    assert engine.verify_lineage_chain([r.to_dict() for r in receipts]) is True


def test_verify_lineage_chain_empty_and_tampered():
    engine, _, receipts = _three_stage_chain()
    assert engine.verify_lineage_chain([]) is False
    corrupted = LineageReceipt.from_dict(receipts[1].to_dict())
    corrupted.parent_chain_hash = "0" * 64
    assert engine.verify_lineage_chain([receipts[0], corrupted, receipts[2]]) is False
    corrupted_hash = LineageReceipt.from_dict(receipts[1].to_dict())
    corrupted_hash.chain_hash = "f" * 64
    assert engine.verify_lineage_chain([receipts[0], corrupted_hash, receipts[2]]) is False
    duplicated = [receipts[0], receipts[0], receipts[2]]
    assert engine.verify_lineage_chain(duplicated) is False
    dropped = [receipts[1], receipts[2]]
    assert engine.verify_lineage_chain(dropped) is False


def test_verify_lineage_chain_status_and_timestamp_guards():
    engine, _, receipts = _three_stage_chain()
    unverified = LineageReceipt.from_dict(receipts[0].to_dict())
    unverified.status = "PENDING"
    assert engine.verify_lineage_chain([unverified, receipts[1], receipts[2]]) is False
    bad_conservation = LineageReceipt.from_dict(receipts[0].to_dict())
    bad_conservation.conservation_ok = False
    assert engine.verify_lineage_chain([bad_conservation, receipts[1], receipts[2]]) is False
    same_ts = [receipts[0], LineageReceipt.from_dict(receipts[1].to_dict()), receipts[2]]
    same_ts[1].verified_at = receipts[0].verified_at
    assert engine.verify_lineage_chain(same_ts) is False


def test_verify_lineage_chain_standalone_forgery():
    # a fully forged two-receipt chain that is *not* engine-issued must still
    # verify when self-consistent (chain hashes recompute), and must fail when
    # the second receipt's link is damaged
    engine = _engine()
    m1 = engine.create_manifest("scheduling", "inventory", {"x": 1}, pipeline_id="PRP")
    r1 = LineageReceipt(
        receipt_id="rc-a", manifest_id=m1.manifest_id, chain_hash="",
        verified_at="2026-01-01T00:00:00+00:00", status="VERIFIED",
        conservation_ok=True, details={"pipeline_id": "PRP"},
        manifest_payload_hash=m1.payload_hash)
    r1.chain_hash = r1.recompute_chain_hash()
    m2 = engine.create_manifest("inventory", "routing", {"y": 2}, pipeline_id="PRP")
    r2 = LineageReceipt(
        receipt_id="rc-b", manifest_id=m2.manifest_id, chain_hash="",
        verified_at="2026-01-01T00:01:00+00:00", status="VERIFIED",
        conservation_ok=True, details={"pipeline_id": "PRP"},
        parent_receipt_id="rc-a", parent_chain_hash=r1.chain_hash,
        manifest_payload_hash=m2.payload_hash)
    r2.chain_hash = r2.recompute_chain_hash()
    assert engine.verify_lineage_chain([r1, r2]) is True
    r2_bad = LineageReceipt.from_dict(r2.to_dict())
    r2_bad.parent_chain_hash = "evil"
    assert engine.verify_lineage_chain([r1, r2_bad]) is False


# ---------------------------------------------------------------------------
# adapter_from_composite_handoff
# ---------------------------------------------------------------------------
def test_adapter_method_returns_manifest_and_receipt():
    engine = _engine()
    result = engine.adapter_from_composite_handoff(
        "scheduling", "inventory",
        {"objective": 10.0},
        {"periods": 2, "conservation": {"total_output": 10.0, "checks": ["mass"]}},
        pipeline_id="PRP",
    )
    assert isinstance(result, tuple)
    manifest, receipt = result
    assert receipt.status == "VERIFIED"
    assert set(manifest.artifacts) == {"upstream_solution", "downstream_input"}
    checks = manifest.conservation_proof["checks"]
    assert checks["total_output"]["expected"] == 10.0
    assert receipt.details["checks_passed"] == 1


def test_adapter_method_auto_verify_off():
    engine = _engine()
    manifest = engine.adapter_from_composite_handoff(
        "scheduling", "inventory", {"a": 1}, {"b": 2},
        pipeline_id="PRP", auto_verify=False)
    assert isinstance(manifest, ArtifactRelayManifest)
    assert engine.chain_head("PRP") is None


def test_adapter_module_level_function():
    manifest, receipt = adapter_from_composite_handoff(
        "facility", "routing", {"open_facility_ids": [1]},
        {"depot": {"id": 0}, "conservation": {"total_demand": 50.0}},
        pipeline_id="LRP")
    assert receipt.status == "VERIFIED"
    assert manifest.source_domain == "facility"


def test_adapter_explicit_conservation_overrides_embedded():
    engine = _engine()
    manifest, receipt = engine.adapter_from_composite_handoff(
        "scheduling", "inventory", {"a": 1},
        {"b": 2, "conservation": {"total_output": 10.0}},
        conservation={"total_output": 99.0},
        pipeline_id="PRP")
    checks = manifest.conservation_proof["checks"]
    assert checks["total_output"]["expected"] == 99.0
    assert receipt.status == "VERIFIED"


def test_adapter_prp_three_stage_chain_end_to_end():
    engine = LineageRelayEngine(clock=FakeClock())
    clock: FakeClock = engine._clock  # type: ignore[assignment]
    scheduling_sol = {"objective": 120.0, "jobs": [{"qty": 10.0} for _ in range(4)]}
    inventory_input = {"periods": 4,
                       "conservation": {"total_output": 40.0, "checks": ["mass"]}}
    _, r1 = engine.adapter_from_composite_handoff(
        "scheduling", "inventory", scheduling_sol, inventory_input, pipeline_id="PRP")
    clock.advance(30)
    inventory_sol = {"objective": 80.0,
                     "orders": [{"demand": 20.0} for _ in range(5)]}
    routing_input = {"clients": [{"id": i} for i in range(1, 6)],
                     "conservation": {"total_demand": 100.0, "checks": ["mass"]}}
    _, r2 = engine.adapter_from_composite_handoff(
        "inventory", "routing", inventory_sol, routing_input, pipeline_id="PRP",
        parent_receipt_id=r1.receipt_id)
    clock.advance(30)
    # independently recomputed anchors (Numbers Truth)
    assert sum(j["qty"] for j in scheduling_sol["jobs"]) == 40.0
    assert sum(o["demand"] for o in inventory_sol["orders"]) == 100.0
    assert engine.verify_lineage_chain([r1, r2]) is True
    assert r2.details["artifacts_count"] == 2


def test_adapter_integration_with_composite_lead_transformer():
    """Seamless handoff from composite_lead's facility → routing transformer."""
    from orpath.agents.composite_lead import transform_facility_to_routing

    facility_sol = {
        "problem_id": "cflp-demo",
        "open_facility_ids": [0],
        "open_facilities": [{"facility_id": 0, "capacity": 100.0, "load": 60.0}],
        "allocations": [
            {"customer_id": i, "demand": 20.0,
             "served_by": [{"facility_id": 0, "fraction": 1.0}]}
            for i in range(1, 4)
        ],
    }
    routing_input = transform_facility_to_routing(facility_sol)
    engine = _engine()
    manifest, receipt = engine.adapter_from_composite_handoff(
        "facility", "routing", facility_sol, routing_input, pipeline_id="LRP")
    assert receipt.status == "VERIFIED"
    assert receipt.conservation_ok is True
    # the transformer's conservation block was carried into the manifest
    proof_checks = manifest.conservation_proof["checks"]
    assert proof_checks["total_demand"]["expected"] == 60.0
    assert proof_checks["total_served"]["actual"] == 60.0
    assert manifest.conservation_proof["check_names"] == [
        "per_customer_fraction", "aggregate_mass", "facility_capacity"]


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------
def test_package_exports():
    import orpath.agents as agents
    for name in (
        "ArtifactRelayManifest", "LineageReceipt", "LineageRelayEngine",
        "LineageRelayError", "RelayTamperError", "RelayConservationError",
        "RelayChainBrokenError", "RelaySequenceError",
        "adapter_from_composite_handoff", "ALLOWED_DOMAIN_TRANSITIONS",
    ):
        assert hasattr(agents, name), name
        assert name in agents.__all__, name
    assert ("scheduling", "inventory") in ALLOWED_DOMAIN_TRANSITIONS["PRP"]
    assert ("facility", "microgrid") in ALLOWED_DOMAIN_TRANSITIONS["MICROGRID_FACILITY"]


# ---------------------------------------------------------------------------
# Adversarial CLI gate
# ---------------------------------------------------------------------------
def _run_gate(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "lineage_relay_gate.py"), *args],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        capture_output=True,
    )


def test_gate_normal_mode_passes():
    result = _run_gate([])
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout[result.stdout.index("{"):result.stdout.rindex("}") + 1])
    assert report["ok"] is True
    assert report["attacks_total"] >= 5
    assert report["attacks_intercepted"] == report["attacks_total"]
    assert report["interception_rate"] == 1.0
    assert report["normal_pass_rate"] == 1.0
    assert report["normal_flow"]["prp_chain_continuous"] is True
    assert report["normal_flow"]["chain3_continuous"] is True
    covered = {a["attack"] for a in report["attacks"]}
    assert covered == {
        "payload_tamper", "chain_break", "conservation_violation",
        "transition_inversion_replay", "timestamp_sequence_anomaly",
    }


def test_gate_strict_mode_passes():
    result = _run_gate(["--strict"])
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout[result.stdout.index("{"):result.stdout.rindex("}") + 1])
    assert report["strict"] is True
    assert report["ok"] is True
    assert report["warnings"] == []


def test_gate_report_file_written():
    out = ROOT / "outputs" / "lineage_relay_gate_report.json"
    assert out.is_file()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["gate"] == "lineage_relay_gate"


# --------------------------------------------------------------------------- #
# Regression: numpy-typed payloads hash identically; timestamps / tol / sequence
# type errors are wrapped as LineageRelayError instead of crashing.
# --------------------------------------------------------------------------- #
def test_stable_hash_numpy_matches_python_scalars() -> None:
    np = pytest.importorskip("numpy")
    assert stable_hash({"a": 5}) == stable_hash({"a": np.int64(5)})
    assert stable_hash({"a": 1.5}) == stable_hash({"a": np.float64(1.5)})
    assert stable_hash({"a": [1, 2]}) == stable_hash({"a": np.array([1, 2])})
    assert canonical_json({"a": 5}) == canonical_json({"a": np.int64(5)})


def test_parse_timestamp_rejects_overflow_and_nan() -> None:
    for bad in (float("inf"), float("nan"), 1e300, -1e300):
        with pytest.raises(LineageRelayError):
            parse_timestamp(bad)


def test_parse_timestamp_rejects_bool_and_bad_type() -> None:
    with pytest.raises(LineageRelayError):
        parse_timestamp(True)
    with pytest.raises(LineageRelayError):
        parse_timestamp(object())


def test_create_manifest_rejects_non_integer_sequence() -> None:
    engine = LineageRelayEngine(clock=lambda: GENESIS)
    with pytest.raises(LineageRelayError):
        engine.create_manifest(
            source_domain="facility", target_domain="routing",
            artifacts={"a": 1}, pipeline_id="LRP", sequence="not-a-number",
        )


def test_audit_rejects_non_numeric_tolerance() -> None:
    engine = LineageRelayEngine(clock=lambda: GENESIS)
    proof = {"checks": {"mass": {"expected": 1.0, "actual": 1.0, "tol": "bad"}}}
    with pytest.raises(LineageRelayError):
        engine.verify_and_issue_receipt(
            engine.create_manifest(
                source_domain="facility", target_domain="routing",
                artifacts={"a": 1}, pipeline_id="LRP",
                conservation_proof=proof,
            )
        )


def test_numpy_artifacts_pass_integrity_roundtrip() -> None:
    """numpy-typed artifact values must survive the pack/verify roundtrip."""
    np = pytest.importorskip("numpy")
    engine = LineageRelayEngine(clock=lambda: GENESIS)
    manifest = engine.create_manifest(
        source_domain="facility", target_domain="routing",
        artifacts={"demands": np.array([1.0, 2.0, 3.0]), "count": np.int64(3)},
        pipeline_id="LRP",
    )
    receipt = engine.verify_and_issue_receipt(manifest)
    assert receipt.status == "VERIFIED"
    # replay with identical content returns the stored receipt
    again = engine.verify_and_issue_receipt(manifest)
    assert again.receipt_id == receipt.receipt_id
