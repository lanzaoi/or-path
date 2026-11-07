#!/usr/bin/env python3
"""Cross-team data lineage relay & artifact handoff protocol (Task 4.4).

Industrial-grade *artifact relay* protocol for multi-team composite OR
pipelines (LRP, IRP, PRP, Microgrid-Facility).  When one domain team hands
intermediate solutions to another (e.g. ``scheduling → inventory → routing``
in PRP), the relay protocol guarantees that:

  * **Integrity** — every relayed artifact set is fingerprinted with a stable
    SHA-256 payload hash *and* a binary Merkle root over the individual
    artifact leaves, so any silent mutation in transit is detected.
  * **Conservation** — the handoff carries a *conservation proof* recording
    each conserved quantity (demand mass, served mass, job counts, capacity
    sums, …) with its expected anchor value.  On verification the engine
    *re-measures* the quantity from the artifacts themselves (via declared
    dot-path ``measure`` specs) and audits it against the anchor — mass /
    demand drift is intercepted even when the attacker forges the
    integrity hashes.
  * **Chain continuity** — every verified relay issues a :class:`LineageReceipt`
    whose ``chain_hash`` is derived from the parent receipt's chain hash, so
    a PRP three-stage relay chain can be proven continuous end to end.
  * **Sequence safety** — timestamps and per-pipeline sequence numbers are
    monotonic; future timestamps, time reversal and old-stage replays are
    intercepted.
  * **Topology safety** — domain transitions are validated against the
    canonical composite pipeline topology (LRP/IRP/PRP/Microgrid-Facility),
    so reversed or unauthorised domain flows are rejected.

Protocol flow
-------------

    upstream team                relay engine                 downstream team
    ----------                 -----------------              ---------------
    (1) create_manifest(...)  ->  ArtifactRelayManifest         (pack & fingerprint)
    (2) verify_and_issue_receipt(m) -> LineageReceipt           (audit & sign)
    (3) downstream consumes artifacts, anchors the receipt id
    (4) next manifest carries parent_receipt_id = receipt.receipt_id

Numbers Truth: every conserved quantity and objective mentioned in a
manifest is *measured* from the raw artifact payloads — nothing is invented,
rounded or re-stated from prose.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

__all__ = [
    # errors
    "LineageRelayError",
    "RelayTamperError",
    "RelayConservationError",
    "RelayChainBrokenError",
    "RelaySequenceError",
    # core objects
    "ArtifactRelayManifest",
    "LineageReceipt",
    "LineageRelayEngine",
    # protocol constants
    "ALLOWED_DOMAIN_TRANSITIONS",
    "CONSERVATION_TOL",
    "DEFAULT_MAX_CLOCK_SKEW_SECONDS",
    "GENESIS_CHAIN_HASH",
    "SCHEMA_VERSION",
    # helpers
    "canonical_json",
    "stable_hash",
    "build_merkle_root",
    "artifact_leaf_hash",
    "parse_timestamp",
    "format_timestamp",
    "adapter_from_composite_handoff",
]

# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------
SCHEMA_VERSION = 1

#: Tolerance for float conservation audits (matches composite_lead).
CONSERVATION_TOL = 1e-6

#: A manifest timestamp may not lie further in the future than this many
#: seconds relative to the engine clock (tolerates scheduler clock skew).
DEFAULT_MAX_CLOCK_SKEW_SECONDS = 300.0

#: Chain hash of the genesis (rootless) receipt.
GENESIS_CHAIN_HASH = "genesis"

#: Canonical composite pipeline topologies: ``pipeline_id -> [(source, target)]``.
#: A relay manifest whose domain pair is absent from a known pipeline's list
#: is an illegal transition (reversed or unauthorised flow) and is rejected.
ALLOWED_DOMAIN_TRANSITIONS: dict[str, list[tuple[str, str]]] = {
    "LRP": [("facility", "routing")],
    "IRP": [("inventory", "routing")],
    "PRP": [("scheduling", "inventory"), ("inventory", "routing")],
    "MICROGRID_FACILITY": [("facility", "microgrid")],
}

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class LineageRelayError(Exception):
    """Base error for the lineage relay protocol."""


class RelayTamperError(LineageRelayError):
    """Payload was mutated in flight (hash / Merkle mismatch) or identity reused."""


class RelayConservationError(LineageRelayError):
    """A conserved quantity drifted between upstream and downstream (audit)."""


class RelayChainBrokenError(LineageRelayError):
    """The parent receipt linkage is forged, unknown or non-linear."""


class RelaySequenceError(LineageRelayError):
    """Timestamp / sequence regression, future timestamp or illegal transition."""


# ---------------------------------------------------------------------------
# Canonical serialisation & hashing
# ---------------------------------------------------------------------------
def _hash_default(obj: Any) -> Any:
    """Normalize non-JSON objects for stable hashing.

    numpy scalars/arrays are normalized via ``.tolist()`` / ``.item()`` so the
    digest depends on the *logical* payload, not on the numeric type
    representation (``np.int64(5)`` and ``5`` must hash identically).
    """
    tolist = getattr(obj, "tolist", None)
    if callable(tolist):
        try:
            return tolist()
        except Exception:  # noqa: BLE001
            pass
    item = getattr(obj, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:  # noqa: BLE001
            pass
    if isinstance(obj, (set, frozenset)):
        return sorted(obj, key=repr)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", "ignore")
    return str(obj)


def canonical_json(payload: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8 friendly."""
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        default=_hash_default,
    )


def stable_hash(payload: Any) -> str:
    """SHA-256 hex digest over the canonical JSON form of ``payload``."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def artifact_leaf_hash(artifact_id: str, artifact: Any) -> str:
    """Per-artifact Merkle leaf digest (stable over the artifact value)."""
    return stable_hash({"artifact_id": artifact_id, "artifact": artifact})


def build_merkle_root(leaf_hashes: list[str]) -> str:
    """Binary Merkle root over ordered leaf digests (odd levels duplicate the last).

    Deterministic: the root depends only on the multiset order given.  The
    empty tree root is the SHA-256 of the empty string.
    """
    layer = [str(h) for h in leaf_hashes]
    if not layer:
        return hashlib.sha256(b"").hexdigest()
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [stable_hash(a + b) for a, b in zip(layer[0::2], layer[1::2])]
    return layer[0]


# ---------------------------------------------------------------------------
# Timestamp helpers (all normalised to ISO-8601 UTC)
# ---------------------------------------------------------------------------
def parse_timestamp(value: Any) -> datetime:
    """Parse ISO-8601 / epoch-seconds / ``datetime`` into an aware UTC datetime."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, bool):
        raise LineageRelayError(f"invalid timestamp {value!r}: bool is not a timestamp")
    elif isinstance(value, (int, float)):
        try:
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise LineageRelayError(f"invalid timestamp {value!r}: {exc}") from exc
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as exc:
            raise LineageRelayError(f"invalid timestamp {value!r}: {exc}") from exc
    else:
        raise LineageRelayError(f"invalid timestamp {value!r}: unsupported type")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_timestamp(value: Any) -> str:
    """Normalise any supported timestamp to ISO-8601 UTC text."""
    return parse_timestamp(value).isoformat()


# ---------------------------------------------------------------------------
# Conservation proof schema
# ---------------------------------------------------------------------------
# Canonical form stored inside a manifest::
#
#   {
#     "checks": {
#        "<name>": {"expected": float, "actual": float,
#                   "measure": "<dot.path>" | None,
#                   "tol": float, "ok": bool}
#     },
#     "summary": {"expected_total": float, "actual_total": float, "ok": bool},
#     "check_names": [...]   # informational, composite-lead style
#   }
#
# ``expected`` is the anchor recorded when the upstream team computed the
# quantity from raw data; ``actual`` is what was observed in the artifacts.
# ``measure`` lets the verifier *re-measure* the quantity straight from the
# artifact payload, which defeats forged-hash conservation drift.

def _extract_measure(artifacts: Mapping[str, Any], measure: str) -> float:
    """Resolve a dot-path measure spec against the artifact payload."""
    node: Any = artifacts
    for part in str(measure).split("."):
        if isinstance(node, Mapping):
            if part not in node:
                raise LineageRelayError(f"conservation measure {measure!r}: missing key {part!r}")
            node = node[part]
        elif isinstance(node, (list, tuple)):
            try:
                node = node[int(part)]
            except (ValueError, IndexError) as exc:
                raise LineageRelayError(
                    f"conservation measure {measure!r}: bad index {part!r}"
                ) from exc
        else:
            raise LineageRelayError(
                f"conservation measure {measure!r}: cannot descend into {type(node).__name__}"
            )
    try:
        return float(node)
    except (TypeError, ValueError) as exc:
        raise LineageRelayError(
            f"conservation measure {measure!r}: non-numeric value {node!r}"
        ) from exc


def _close(a: float, b: float, tol: float) -> bool:
    return abs(float(a) - float(b)) <= tol


# ---------------------------------------------------------------------------
# ArtifactRelayManifest
# ---------------------------------------------------------------------------
@dataclass
class ArtifactRelayManifest:
    """One cross-team artifact relay shipment.

    Fields
    ------
    manifest_id
        Unique relay shipment identifier (``mf-…``).
    source_domain / target_domain
        Upstream / downstream domain team identifiers.
    pipeline_id
        Composite pipeline the relay belongs to (``"PRP"``, ``"LRP"``, …).
    timestamp
        ISO-8601 UTC creation timestamp.
    artifacts
        Mapping ``artifact_id -> payload`` relayed to the downstream team.
    conservation_proof
        Canonical conservation audit block (see module docstring).
    merkle_root
        Binary Merkle root over per-artifact leaf digests.
    payload_hash
        Stable SHA-256 over the full canonical manifest payload.
    parent_receipt_id
        Receipt issued for the previous relay of the same pipeline.
    sequence
        Per-pipeline monotonic relay counter.
    """

    manifest_id: str
    source_domain: str
    target_domain: str
    pipeline_id: str
    timestamp: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    conservation_proof: dict[str, Any] = field(default_factory=dict)
    merkle_root: str = ""
    payload_hash: str = ""
    parent_receipt_id: str | None = None
    sequence: int = 0
    schema_version: int = SCHEMA_VERSION

    # -- fingerprints ---------------------------------------------------------
    def canonical_payload(self) -> dict[str, Any]:
        """The hashable content of the manifest (excludes the fingerprints)."""
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "source_domain": self.source_domain,
            "target_domain": self.target_domain,
            "pipeline_id": self.pipeline_id,
            "timestamp": self.timestamp,
            "parent_receipt_id": self.parent_receipt_id,
            "sequence": self.sequence,
            "artifacts": self.artifacts,
            "conservation_proof": self.conservation_proof,
        }

    def recompute_payload_hash(self) -> str:
        """Recompute the stable SHA-256 payload hash from current content."""
        return stable_hash(self.canonical_payload())

    def recompute_merkle_root(self) -> str:
        """Recompute the Merkle root over the current artifacts (key order)."""
        leaves = [
            artifact_leaf_hash(key, self.artifacts[key])
            for key in sorted(self.artifacts, key=str)
        ]
        return build_merkle_root(leaves)

    # -- (de)serialisation -----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "source_domain": self.source_domain,
            "target_domain": self.target_domain,
            "pipeline_id": self.pipeline_id,
            "timestamp": self.timestamp,
            "parent_receipt_id": self.parent_receipt_id,
            "sequence": self.sequence,
            "artifacts": self.artifacts,
            "conservation_proof": self.conservation_proof,
            "merkle_root": self.merkle_root,
            "payload_hash": self.payload_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ArtifactRelayManifest":
        """Rebuild a manifest from a serialised dict (strict key validation)."""
        if not isinstance(data, Mapping):
            raise LineageRelayError("manifest dict must be a mapping")
        required = (
            "manifest_id", "source_domain", "target_domain", "pipeline_id",
            "timestamp", "merkle_root", "payload_hash",
        )
        missing = [k for k in required if k not in data]
        if missing:
            raise LineageRelayError(f"manifest missing required key(s): {missing}")
        artifacts = data.get("artifacts", {})
        if not isinstance(artifacts, Mapping):
            raise LineageRelayError("manifest 'artifacts' must be a mapping")
        proof = data.get("conservation_proof", {})
        if not isinstance(proof, Mapping):
            raise LineageRelayError("manifest 'conservation_proof' must be a mapping")
        try:
            sequence = int(data.get("sequence", 0))
        except (TypeError, ValueError) as exc:
            raise LineageRelayError("manifest 'sequence' must be an integer") from exc
        parent = data.get("parent_receipt_id")
        return cls(
            manifest_id=str(data["manifest_id"]),
            source_domain=str(data["source_domain"]),
            target_domain=str(data["target_domain"]),
            pipeline_id=str(data["pipeline_id"]),
            timestamp=str(data["timestamp"]),
            artifacts=dict(artifacts),
            conservation_proof=dict(proof),
            merkle_root=str(data["merkle_root"]),
            payload_hash=str(data["payload_hash"]),
            parent_receipt_id=None if parent is None else str(parent),
            sequence=sequence,
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str)

    @classmethod
    def from_json(cls, text: str) -> "ArtifactRelayManifest":
        return cls.from_dict(json.loads(text))


# ---------------------------------------------------------------------------
# LineageReceipt
# ---------------------------------------------------------------------------
@dataclass
class LineageReceipt:
    """Lineage credential issued after a successful manifest verification.

    The ``chain_hash`` links this receipt to its parent receipt's chain hash,
    so a full relay chain can be audited for continuity by recomputing every
    chain hash from the receipt contents alone.
    """

    receipt_id: str
    manifest_id: str
    chain_hash: str
    verified_at: str
    status: str
    conservation_ok: bool
    details: dict[str, Any] = field(default_factory=dict)
    parent_receipt_id: str | None = None
    parent_chain_hash: str = GENESIS_CHAIN_HASH
    manifest_payload_hash: str = ""

    def recompute_chain_hash(self) -> str:
        """Recompute the chained SHA-256 digest from receipt content."""
        return stable_hash(
            {
                "receipt_id": self.receipt_id,
                "manifest_payload_hash": self.manifest_payload_hash,
                "parent_chain_hash": self.parent_chain_hash,
                "verified_at": self.verified_at,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "manifest_id": self.manifest_id,
            "chain_hash": self.chain_hash,
            "verified_at": self.verified_at,
            "status": self.status,
            "conservation_ok": self.conservation_ok,
            "details": self.details,
            "parent_receipt_id": self.parent_receipt_id,
            "parent_chain_hash": self.parent_chain_hash,
            "manifest_payload_hash": self.manifest_payload_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LineageReceipt":
        if not isinstance(data, Mapping):
            raise LineageRelayError("receipt dict must be a mapping")
        required = ("receipt_id", "manifest_id", "chain_hash", "verified_at", "status")
        missing = [k for k in required if k not in data]
        if missing:
            raise LineageRelayError(f"receipt missing required key(s): {missing}")
        parent = data.get("parent_receipt_id")
        conservation = data.get("conservation_ok", True)
        if not isinstance(conservation, bool):
            raise LineageRelayError("receipt 'conservation_ok' must be a bool")
        return cls(
            receipt_id=str(data["receipt_id"]),
            manifest_id=str(data["manifest_id"]),
            chain_hash=str(data["chain_hash"]),
            verified_at=str(data["verified_at"]),
            status=str(data["status"]),
            conservation_ok=conservation,
            details=dict(data.get("details", {})),
            parent_receipt_id=None if parent is None else str(parent),
            parent_chain_hash=str(data.get("parent_chain_hash", GENESIS_CHAIN_HASH)),
            manifest_payload_hash=str(data.get("manifest_payload_hash", "")),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str)

    @classmethod
    def from_json(cls, text: str) -> "LineageReceipt":
        return cls.from_dict(json.loads(text))


# ---------------------------------------------------------------------------
# Conservation proof normalisation & audit
# ---------------------------------------------------------------------------
def _normalise_conservation_proof(
    proof: Any,
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalise any accepted conservation input into the canonical schema.

    Accepted inputs
    --------------
    * ``None`` — empty proof (no conserved quantities declared).
    * Composite-lead style ``{"total_demand": 100.0, "total_served": 100.0,
      "num_clients": 5, "checks": ["aggregate_mass", …]}`` — every numeric
      field becomes a self-anchored check (``expected == actual``); the
      check-name list is preserved under ``check_names``.
    * Flat ``{name: number}`` mapping.
    * Canonical ``{"checks": {name: {…}}}`` with per-check entries that may
      carry ``expected``/``actual``/``measure``/``tol``/``ok``.
    """
    if proof is None:
        return {"checks": {}, "summary": {"expected_total": 0.0, "actual_total": 0.0, "ok": True}}
    if not isinstance(proof, Mapping):
        raise LineageRelayError("conservation proof must be a mapping")

    check_names: list[str] = []
    raw_checks: dict[str, Any] = {}
    if "checks" in proof:
        checks_field = proof["checks"]
        if isinstance(checks_field, Mapping):
            raw_checks.update(checks_field)
        elif isinstance(checks_field, (list, tuple)):
            check_names = [str(c) for c in checks_field]
            for key, value in proof.items():
                if key == "checks":
                    continue
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                raw_checks[str(key)] = value
        else:
            raise LineageRelayError("conservation proof 'checks' must be a mapping or list")
    else:
        for key, value in proof.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            raw_checks[str(key)] = value

    checks: dict[str, Any] = {}
    for name, entry in raw_checks.items():
        if isinstance(entry, Mapping):
            expected = entry.get("expected")
            actual = entry.get("actual")
            measure = entry.get("measure")
            try:
                tol = float(entry.get("tol", CONSERVATION_TOL))
            except (TypeError, ValueError) as exc:
                raise LineageRelayError(
                    f"conservation check {name!r} has non-numeric 'tol' {entry.get('tol')!r}"
                ) from exc
            if expected is None and actual is None:
                raise LineageRelayError(
                    f"conservation check {name!r} needs 'expected' and/or 'actual'"
                )
            if expected is None:
                expected = actual
            if actual is None and measure is None:
                raise LineageRelayError(
                    f"conservation check {name!r} needs 'actual' or a 'measure'"
                )
            if measure is not None:
                actual = _extract_measure(artifacts, str(measure))
            expected_f = float(expected)
            actual_f = float(actual)
            checks[name] = {
                "expected": expected_f,
                "actual": actual_f,
                "measure": str(measure) if measure is not None else None,
                "tol": tol,
                "ok": _close(actual_f, expected_f, tol),
            }
        elif isinstance(entry, bool) or not isinstance(entry, (int, float)):
            raise LineageRelayError(
                f"conservation check {name!r} must be numeric or a mapping, got {type(entry).__name__}"
            )
        else:
            value_f = float(entry)
            checks[name] = {
                "expected": value_f,
                "actual": value_f,
                "measure": None,
                "tol": CONSERVATION_TOL,
                "ok": True,
            }

    expected_total = round(sum(c["expected"] for c in checks.values()), 12)
    actual_total = round(sum(c["actual"] for c in checks.values()), 12)
    all_ok = all(c["ok"] for c in checks.values()) and _close(
        expected_total, actual_total, CONSERVATION_TOL
    )
    normalised = {
        "checks": checks,
        "summary": {
            "expected_total": expected_total,
            "actual_total": actual_total,
            "ok": bool(all_ok),
        },
    }
    if check_names:
        normalised["check_names"] = check_names
    return normalised


def _audit_conservation_proof(
    proof: Mapping[str, Any],
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-audit a (possibly forged) conservation proof against the artifacts.

    Raises :class:`RelayConservationError` on any drift and
    :class:`RelayTamperError` when a declared measure re-measurement disagrees
    with the proof's stored ``actual`` (content mutated after signing).
    Returns the audit summary.
    """
    checks = proof.get("checks") or {}
    if not isinstance(checks, Mapping):
        raise LineageRelayError("conservation proof 'checks' must be a mapping")

    recomputed_actual_total = 0.0
    for name, entry in checks.items():
        if isinstance(entry, Mapping):
            expected = entry.get("expected")
            actual = entry.get("actual")
            measure = entry.get("measure")
            try:
                tol = float(entry.get("tol", CONSERVATION_TOL))
            except (TypeError, ValueError) as exc:
                raise LineageRelayError(
                    f"conservation check {name!r} has non-numeric 'tol' {entry.get('tol')!r}"
                ) from exc
            stored_ok = entry.get("ok", None)
        elif isinstance(entry, bool) or not isinstance(entry, (int, float)):
            raise LineageRelayError(
                f"conservation check {name!r} has unsupported entry type {type(entry).__name__}"
            )
        else:
            expected = actual = float(entry)
            measure = None
            tol = CONSERVATION_TOL
            stored_ok = None
        if expected is None and actual is None:
            raise LineageRelayError(f"conservation check {name!r} lacks 'expected' and 'actual'")
        if expected is None:
            expected = actual
        if measure is not None:
            measured = _extract_measure(artifacts, str(measure))
            if actual is not None and not _close(measured, float(actual), tol):
                raise RelayTamperError(
                    f"conservation check {name!r}: stored actual {actual!r} ≠ re-measured "
                    f"{measured!r} via {measure!r} (content mutated after signing)"
                )
            actual = measured
        actual_f = float(actual)
        expected_f = float(expected)
        drift = not _close(actual_f, expected_f, tol)
        if stored_ok is False or (stored_ok is not None and stored_ok != (not drift)):
            raise RelayConservationError(
                f"conservation audit failed for {name!r}: expected {expected_f!r} "
                f"actual {actual_f!r} tol={tol} (forged ok flag={stored_ok!r})"
            )
        if drift:
            raise RelayConservationError(
                f"conservation audit failed for {name!r}: expected {expected_f!r} "
                f"≠ actual {actual_f!r} (drift {actual_f - expected_f:+.6g}, tol={tol})"
            )
        recomputed_actual_total += actual_f

    summary = proof.get("summary")
    checks_ok = all(
        (not isinstance(e, Mapping)) or e.get("ok", True) for e in checks.values()
    )
    expected_total = 0.0
    for entry in checks.values():
        if isinstance(entry, Mapping) and entry.get("expected") is not None:
            expected_total += float(entry["expected"])
        elif not isinstance(entry, Mapping):
            expected_total += float(entry)
    if summary:
        if not summary.get("ok", True):
            raise RelayConservationError("conservation audit failed: proof summary 'ok' is false")
        expected_total = float(summary.get("expected_total", expected_total))
    if not _close(recomputed_actual_total, expected_total, CONSERVATION_TOL):
        raise RelayConservationError(
            "conservation audit failed for summary: recomputed actual total "
            f"{recomputed_actual_total!r} ≠ expected total {expected_total!r}"
        )
    if not checks_ok:
        raise RelayConservationError("conservation audit failed: proof carries an 'ok=false' check")
    return {
        "checks_passed": len(checks),
        "expected_total": expected_total,
        "actual_total": round(recomputed_actual_total, 12),
    }


# ---------------------------------------------------------------------------
# LineageRelayEngine
# ---------------------------------------------------------------------------
class LineageRelayEngine:
    """Artifact relay protocol engine: pack, verify, issue and chain.

    Parameters
    ----------
    clock
        Optional ``Callable[[], datetime | str | float]`` supplying "now" for
        timestamp sanity checks and receipt issuance (test seam).
    max_clock_skew_seconds
        Maximum tolerated future offset between manifest timestamps and the
        engine clock.
    """

    def __init__(
        self,
        clock: Callable[[], Any] | None = None,
        max_clock_skew_seconds: float = DEFAULT_MAX_CLOCK_SKEW_SECONDS,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.max_clock_skew_seconds = float(max_clock_skew_seconds)
        # protocol state
        self._issued_receipts: dict[str, LineageReceipt] = {}
        self._issued_manifests: dict[str, str] = {}      # manifest_id -> payload_hash
        self._pipeline_head: dict[str, str] = {}         # pipeline_id -> receipt_id
        self._pipeline_last_ts: dict[str, datetime] = {}
        self._pipeline_sequence: dict[str, int] = {}
        self._verified_sequence: dict[str, int] = {}

    # -- helpers ---------------------------------------------------------------
    @property
    def now(self) -> datetime:
        return parse_timestamp(self._clock())

    def chain_head(self, pipeline_id: str) -> LineageReceipt | None:
        """Return the current receipt chain head for a pipeline (``None`` if empty)."""
        receipt_id = self._pipeline_head.get(pipeline_id)
        return self._issued_receipts.get(receipt_id) if receipt_id is not None else None

    def _next_sequence(self, pipeline_id: str) -> int:
        return int(self._pipeline_sequence.get(pipeline_id, 0)) + 1

    def _check_transition(self, source: str, target: str, pipeline_id: str) -> None:
        allowed = ALLOWED_DOMAIN_TRANSITIONS.get(pipeline_id.upper())
        if allowed is not None and (source, target) not in allowed:
            raise RelaySequenceError(
                f"illegal domain transition {source!r} → {target!r} in pipeline "
                f"{pipeline_id!r}; allowed: {allowed}"
            )

    def _validate_parent_receipt(
        self,
        parent_receipt_id: str | None,
        pipeline_id: str,
    ) -> LineageReceipt | None:
        if parent_receipt_id is None:
            return None
        parent = self._issued_receipts.get(parent_receipt_id)
        if parent is None:
            raise RelayChainBrokenError(
                f"parent receipt {parent_receipt_id!r} is unknown to the relay engine"
            )
        if parent.details.get("pipeline_id") != pipeline_id:
            raise RelayChainBrokenError(
                f"parent receipt {parent_receipt_id!r} belongs to pipeline "
                f"{parent.details.get('pipeline_id')!r}, not {pipeline_id!r}"
            )
        head = self._pipeline_head.get(pipeline_id)
        if head is not None and parent_receipt_id != head:
            raise RelayChainBrokenError(
                f"parent receipt {parent_receipt_id!r} is not the current chain head "
                f"{head!r} of pipeline {pipeline_id!r} (non-linear / stale replay)"
            )
        return parent

    # -- conservation ----------------------------------------------------------
    def check_conservation(
        self,
        name: str,
        in_val: Any,
        out_val: Any,
        tol: float = CONSERVATION_TOL,
    ) -> bool:
        """Return ``True`` when ``in_val`` and ``out_val`` agree within ``tol``."""
        try:
            a = float(in_val)
            b = float(out_val)
        except (TypeError, ValueError) as exc:
            raise LineageRelayError(
                f"conservation check {name!r}: non-numeric values {in_val!r}/{out_val!r}"
            ) from exc
        return abs(a - b) <= float(tol)

    def require_conservation(
        self,
        name: str,
        in_val: Any,
        out_val: Any,
        tol: float = CONSERVATION_TOL,
    ) -> bool:
        """Like :meth:`check_conservation` but raise on drift."""
        if not self.check_conservation(name, in_val, out_val, tol):
            raise RelayConservationError(
                f"conservation violation for {name!r}: in={in_val!r} out={out_val!r} (tol={tol})"
            )
        return True

    # -- packing ---------------------------------------------------------------
    def create_manifest(
        self,
        source_domain: str,
        target_domain: str,
        artifacts: Mapping[str, Any],
        pipeline_id: str = "CUSTOM",
        conservation_proof: Mapping[str, Any] | None = None,
        timestamp: Any = None,
        parent_receipt_id: str | None = None,
        sequence: int | None = None,
        manifest_id: str | None = None,
    ) -> ArtifactRelayManifest:
        """Pack upstream artifacts into a relay manifest with fingerprints.

        Computes the stable SHA-256 ``payload_hash`` and the binary
        ``merkle_root`` over the artifact leaves, normalises the conservation
        proof (measuring declared quantities straight from the artifacts) and
        validates the domain transition topology.
        """
        if not isinstance(source_domain, str) or not source_domain.strip():
            raise LineageRelayError("source_domain must be a non-empty string")
        if not isinstance(target_domain, str) or not target_domain.strip():
            raise LineageRelayError("target_domain must be a non-empty string")
        if not isinstance(pipeline_id, str) or not pipeline_id.strip():
            raise LineageRelayError("pipeline_id must be a non-empty string")
        if not isinstance(artifacts, Mapping):
            raise LineageRelayError("artifacts must be a mapping artifact_id -> payload")

        self._check_transition(source_domain, target_domain, pipeline_id)
        parent = self._validate_parent_receipt(parent_receipt_id, pipeline_id)

        proof = _normalise_conservation_proof(conservation_proof, artifacts)

        ts = format_timestamp(timestamp) if timestamp is not None else self.now.isoformat()
        if sequence is not None:
            try:
                seq = int(sequence)
            except (TypeError, ValueError) as exc:
                raise LineageRelayError(
                    f"sequence must be an integer, got {sequence!r}"
                ) from exc
        else:
            seq = self._next_sequence(pipeline_id)
        if seq <= 0:
            raise LineageRelayError(f"sequence must be a positive integer, got {seq!r}")
        if seq > self._pipeline_sequence.get(pipeline_id, 0):
            self._pipeline_sequence[pipeline_id] = seq

        if manifest_id is None:
            manifest_id = "mf-" + stable_hash(
                {
                    "source": source_domain,
                    "target": target_domain,
                    "pipeline": pipeline_id,
                    "sequence": seq,
                    "timestamp": ts,
                    "artifact_keys": sorted(artifacts, key=str),
                }
            )[:16]

        artifacts_dict = {str(k): v for k, v in artifacts.items()}
        manifest = ArtifactRelayManifest(
            manifest_id=str(manifest_id),
            source_domain=source_domain,
            target_domain=target_domain,
            pipeline_id=pipeline_id,
            timestamp=ts,
            artifacts=artifacts_dict,
            conservation_proof=proof,
            parent_receipt_id=None if parent is None else parent.receipt_id,
            sequence=seq,
        )
        manifest.payload_hash = manifest.recompute_payload_hash()
        manifest.merkle_root = manifest.recompute_merkle_root()
        return manifest

    # -- verification & receipt issuance ---------------------------------------
    def verify_and_issue_receipt(
        self,
        manifest: ArtifactRelayManifest | Mapping[str, Any],
        expected_parent_receipt_id: str | None = None,
    ) -> LineageReceipt:
        """Strictly verify a relay manifest and issue a :class:`LineageReceipt`.

        Audits, in order:

        1. **Integrity** — recomputed ``payload_hash`` and ``merkle_root``
           must match the manifest's fingerprints (tamper interception).
        2. **Conservation** — every check is re-measured from the artifacts
           and audited against its anchor (drift interception).
        3. **Topology** — the domain transition must be allowed for the
           pipeline (inversion / unauthorised flow interception).
        4. **Timestamp & sequence** — no future timestamps beyond clock
           skew, no regressions per pipeline, no stale replays.
        5. **Chain linkage** — ``parent_receipt_id`` must be the engine-issued
           current head of the pipeline (chain-break interception).
        6. **Replay** — re-verifying an identical manifest returns the stored
           receipt; reusing a manifest id with different content is rejected.
        """
        m = manifest if isinstance(manifest, ArtifactRelayManifest) else ArtifactRelayManifest.from_dict(manifest)

        # --- 1. integrity -----------------------------------------------------
        if m.recompute_payload_hash() != m.payload_hash:
            raise RelayTamperError(
                f"payload tamper detected in manifest {m.manifest_id!r}: recomputed "
                f"{m.recompute_payload_hash()[:12]}… ≠ declared {m.payload_hash[:12]}…"
            )
        if m.recompute_merkle_root() != m.merkle_root:
            raise RelayTamperError(
                f"artifact tamper detected in manifest {m.manifest_id!r}: Merkle root "
                f"recomputed {m.recompute_merkle_root()[:12]}… ≠ declared "
                f"{m.merkle_root[:12]}…"
            )

        # --- 2. replay / identity reuse ------------------------------------------
        stored_payload = self._issued_manifests.get(m.manifest_id)
        if stored_payload is not None:
            if stored_payload == m.payload_hash:
                return self._receipt_for(m.manifest_id)
            raise RelayTamperError(
                f"manifest id {m.manifest_id!r} replayed with different content "
                f"(stored {stored_payload[:12]}…, got {m.payload_hash[:12]}…)"
            )

        # --- 3. conservation audit --------------------------------------------
        audit = _audit_conservation_proof(m.conservation_proof, m.artifacts)

        # --- 4. topology -------------------------------------------------------
        self._check_transition(m.source_domain, m.target_domain, m.pipeline_id)

        # --- 5. timestamp & sequence sanity -------------------------------------
        ts = parse_timestamp(m.timestamp)
        now = self.now
        if ts > now + timedelta(seconds=self.max_clock_skew_seconds):
            raise RelaySequenceError(
                f"timestamp anomaly in manifest {m.manifest_id!r}: {ts.isoformat()} lies "
                f"in the future beyond the {self.max_clock_skew_seconds}s clock-skew bound"
            )
        last_ts = self._pipeline_last_ts.get(m.pipeline_id)
        if last_ts is not None and ts < last_ts:
            raise RelaySequenceError(
                f"timestamp regression in manifest {m.manifest_id!r}: {ts.isoformat()} "
                f"< last verified {last_ts.isoformat()} for pipeline {m.pipeline_id!r}"
            )
        last_seq = int(self._verified_sequence.get(m.pipeline_id, 0))
        if m.sequence <= last_seq:
            raise RelaySequenceError(
                f"sequence regression in manifest {m.manifest_id!r}: sequence {m.sequence} "
                f"<= last verified {last_seq} for pipeline {m.pipeline_id!r} (stale replay)"
            )

        # --- 6. chain linkage ---------------------------------------------------
        parent = self._validate_parent_receipt(m.parent_receipt_id, m.pipeline_id)
        if expected_parent_receipt_id is not None and m.parent_receipt_id != expected_parent_receipt_id:
            raise RelayChainBrokenError(
                f"manifest {m.manifest_id!r} declares parent {m.parent_receipt_id!r} but the "
                f"pipeline expects {expected_parent_receipt_id!r}"
            )

        # --- issue the receipt ----------------------------------------------------
        verified_at = now.isoformat()
        parent_chain_hash = GENESIS_CHAIN_HASH if parent is None else parent.chain_hash
        receipt_id = "rc-" + stable_hash(
            {
                "manifest_id": m.manifest_id,
                "verified_at": verified_at,
                "parent_chain_hash": parent_chain_hash,
            }
        )[:16]
        receipt = LineageReceipt(
            receipt_id=receipt_id,
            manifest_id=m.manifest_id,
            chain_hash="",
            verified_at=verified_at,
            status="VERIFIED",
            conservation_ok=True,
            details={
                "pipeline_id": m.pipeline_id,
                "source_domain": m.source_domain,
                "target_domain": m.target_domain,
                "artifacts_count": len(m.artifacts),
                "sequence": m.sequence,
                "merkle_root": m.merkle_root,
                **audit,
            },
            parent_receipt_id=None if parent is None else parent.receipt_id,
            parent_chain_hash=parent_chain_hash,
            manifest_payload_hash=m.payload_hash,
        )
        receipt.chain_hash = receipt.recompute_chain_hash()

        # --- commit protocol state ------------------------------------------------
        self._issued_receipts[receipt_id] = receipt
        self._issued_manifests[m.manifest_id] = m.payload_hash
        self._pipeline_head[m.pipeline_id] = receipt_id
        if last_ts is None or ts > last_ts:
            self._pipeline_last_ts[m.pipeline_id] = ts
        self._verified_sequence[m.pipeline_id] = m.sequence
        if m.sequence > self._pipeline_sequence.get(m.pipeline_id, 0):
            self._pipeline_sequence[m.pipeline_id] = m.sequence
        return receipt

    def _receipt_for(self, manifest_id: str) -> LineageReceipt:
        """Return the stored receipt for an already-issued manifest."""
        for receipt in self._issued_receipts.values():
            if receipt.manifest_id == manifest_id:
                return receipt
        raise RelayChainBrokenError(f"no receipt issued for manifest {manifest_id!r}")

    # -- chain verification ------------------------------------------------------
    def verify_lineage_chain(self, receipts: list[LineageReceipt | Mapping[str, Any]]) -> bool:
        """Verify cross-stage relay-chain continuity (e.g. a PRP three-stage chain).

        The chain is valid iff every receipt is ``VERIFIED``, every chain hash
        recomputes from its content, ``verified_at`` timestamps are strictly
        increasing, the first receipt is a genesis receipt and each subsequent
        receipt links to the previous one via ``parent_receipt_id`` and
        ``parent_chain_hash``.
        """
        try:
            parsed = [
                r if isinstance(r, LineageReceipt) else LineageReceipt.from_dict(r)
                for r in receipts
            ]
        except LineageRelayError:
            return False
        if not parsed:
            return False

        ordered = sorted(parsed, key=lambda r: parse_timestamp(r.verified_at))
        seen: set[str] = set()
        previous: LineageReceipt | None = None
        previous_ts: datetime | None = None
        for receipt in ordered:
            if receipt.receipt_id in seen:
                return False
            seen.add(receipt.receipt_id)
            if receipt.status != "VERIFIED":
                return False
            if not receipt.conservation_ok:
                return False
            if receipt.chain_hash != receipt.recompute_chain_hash():
                return False
            ts = parse_timestamp(receipt.verified_at)
            if previous_ts is not None and ts <= previous_ts:
                return False
            if previous is None:
                if receipt.parent_receipt_id is not None:
                    return False
                if receipt.parent_chain_hash != GENESIS_CHAIN_HASH:
                    return False
            else:
                if receipt.parent_receipt_id != previous.receipt_id:
                    return False
                if receipt.parent_chain_hash != previous.chain_hash:
                    return False
            previous = receipt
            previous_ts = ts
        return True

    # -- composite-lead adapter ---------------------------------------------------
    def adapter_from_composite_handoff(
        self,
        upstream_domain: str,
        downstream_domain: str,
        upstream_solution: Mapping[str, Any],
        downstream_input: Mapping[str, Any],
        conservation: Mapping[str, Any] | None = None,
        pipeline_id: str = "CUSTOM",
        timestamp: Any = None,
        parent_receipt_id: str | None = None,
        auto_verify: bool = True,
    ) -> ArtifactRelayManifest | tuple[ArtifactRelayManifest, LineageReceipt]:
        """Bridge one ``composite_lead`` handoff into the relay protocol.

        Packs the upstream solution envelope and the transformed downstream
        input as the relay artifacts, reusing the handoff's own ``conservation``
        block (the transformers embed it in the downstream input) as the
        conservation proof.  Returns the manifest, or ``(manifest, receipt)``
        when ``auto_verify`` is true.
        """
        artifacts = {
            "upstream_solution": dict(upstream_solution),
            "downstream_input": dict(downstream_input),
        }
        if conservation is None and isinstance(downstream_input, Mapping):
            proof = downstream_input.get("conservation")
            conservation = proof if isinstance(proof, Mapping) else None
        manifest = self.create_manifest(
            source_domain=upstream_domain,
            target_domain=downstream_domain,
            artifacts=artifacts,
            pipeline_id=pipeline_id,
            conservation_proof=conservation,
            timestamp=timestamp,
            parent_receipt_id=parent_receipt_id,
        )
        if not auto_verify:
            return manifest
        receipt = self.verify_and_issue_receipt(
            manifest, expected_parent_receipt_id=parent_receipt_id
        )
        return manifest, receipt


def adapter_from_composite_handoff(
    upstream_domain: str,
    downstream_domain: str,
    upstream_solution: Mapping[str, Any],
    downstream_input: Mapping[str, Any],
    conservation: Mapping[str, Any] | None = None,
    pipeline_id: str = "CUSTOM",
    timestamp: Any = None,
    parent_receipt_id: str | None = None,
    auto_verify: bool = True,
    engine: LineageRelayEngine | None = None,
    clock: Callable[[], Any] | None = None,
) -> ArtifactRelayManifest | tuple[ArtifactRelayManifest, LineageReceipt]:
    """Module-level convenience wrapper around :meth:`LineageRelayEngine.adapter_from_composite_handoff`.

    Uses a fresh ephemeral engine unless one is supplied; the pipeline-scoped
    engine should be used when chain continuity across stages matters.
    """
    eng = engine if engine is not None else LineageRelayEngine(clock=clock)
    return eng.adapter_from_composite_handoff(
        upstream_domain=upstream_domain,
        downstream_domain=downstream_domain,
        upstream_solution=upstream_solution,
        downstream_input=downstream_input,
        conservation=conservation,
        pipeline_id=pipeline_id,
        timestamp=timestamp,
        parent_receipt_id=parent_receipt_id,
        auto_verify=auto_verify,
    )
