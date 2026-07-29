"""Feynman-inspired claim ledger (deep port of workbench/claims.ts ideas).

Not a copy of TS sources — Python native for OR-Path:
- Explicit markers: Claim: / Finding: / Conclusion: / Verified:
- Stable claimId = sha256(scope:normalized)[:16]
- Status merge: failed > verified > unverified
- Gate checks (R1/R2/claim_map/research) attach as verification checks with claimId links
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal

ClaimStatus = Literal["unverified", "verified", "failed"]

CLAIM_MARKER = re.compile(
    r"^(?:[-*]\s+|\d+[.)]\s+|#{1,6}\s+)?(?:claim|finding|conclusion|verified)\s*:\s+(.+)$",
    re.I | re.M,
)
MAX_CLAIM_TEXT = 500
MAX_CLAIMS = 180


def normalize_claim_text(value: str) -> str:
    t = re.sub(r"\s+", " ", value or "").strip()
    t = t.strip("\"'`.;:")
    return t[:MAX_CLAIM_TEXT]


def claim_id_for_text(claim: str, scope: str = "workspace") -> str:
    normalized = normalize_claim_text(claim).lower()
    digest = hashlib.sha256(f"{scope}:{normalized}".encode("utf-8")).hexdigest()[:16]
    return f"claim:{digest}"


def _status_rank(status: ClaimStatus) -> int:
    return {"failed": 3, "verified": 2, "unverified": 1}.get(status, 1)


def extract_marker_claims(
    text: str,
    *,
    source_path: str,
    scope: str = "workspace",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in CLAIM_MARKER.finditer(text or ""):
        claim = normalize_claim_text(m.group(1))
        if not claim:
            continue
        status: ClaimStatus = "unverified"
        line = m.group(0)
        if re.match(r"(?:[-*]\s+|\d+[.)]\s+|#{1,6}\s+)?verified\s*:", line, re.I):
            status = "verified"
        out.append(
            {
                "id": claim_id_for_text(claim, scope),
                "claim": claim,
                "status": status,
                "source": "artifact",
                "sourcePath": source_path,
                "evidencePaths": [source_path],
                "checkIds": [],
                "detail": f"Claim marker extracted from {source_path}.",
            }
        )
        if len(out) >= 12:
            break
    return out


def merge_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for c in claims:
        cid = c.get("id") or claim_id_for_text(str(c.get("claim") or ""))
        cur = by_id.get(cid)
        if not cur:
            by_id[cid] = {
                **c,
                "id": cid,
                "evidencePaths": list(dict.fromkeys(c.get("evidencePaths") or [])),
                "checkIds": list(dict.fromkeys(c.get("checkIds") or [])),
            }
            continue
        if _status_rank(c.get("status") or "unverified") > _status_rank(cur.get("status") or "unverified"):
            cur["status"] = c["status"]
        cur["evidencePaths"] = sorted(
            set(cur.get("evidencePaths") or []) | set(c.get("evidencePaths") or [])
        )
        cur["checkIds"] = sorted(set(cur.get("checkIds") or []) | set(c.get("checkIds") or []))
        if not cur.get("detail") and c.get("detail"):
            cur["detail"] = c["detail"]
    rows = list(by_id.values())
    rows.sort(key=lambda r: (r.get("claim") or ""))
    return rows[:MAX_CLAIMS]


def checks_from_gates(
    *,
    slug: str,
    r1_ok: bool | None,
    r2_ok: bool | None,
    claim_map_ok: bool | None,
    research_ok: bool | None = None,
    validate_ok: bool | None = None,
    evidence_paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Turn OR-Path hard gates into verification checks linked to claim ids."""
    evid = evidence_paths or []
    pairs = [
        ("r1_whitelist", "All URLs in paper are whitelist-supported", r1_ok),
        ("r2_numeric", "All result numerics are solution-backed", r2_ok),
        ("claim_map", "Claim map contract holds (objective/URL/structure/honesty)", claim_map_ok),
        ("research_gate", "Research evidence table + retrieval consumption", research_ok),
        ("validate", "Solution recompute/validate gate passed", validate_ok),
    ]
    checks: list[dict[str, Any]] = []
    for cid, claim, ok in pairs:
        if ok is None:
            continue
        claim_n = normalize_claim_text(claim)
        status: ClaimStatus = "verified" if ok else "failed"
        checks.append(
            {
                "id": f"check:{slug}:{cid}",
                "title": cid,
                "claim": claim_n,
                "claimId": claim_id_for_text(claim_n, slug),
                "status": "pass" if ok else "fail",
                "evidencePaths": evid,
            }
        )
        # also emit claim row for merge
        checks[-1]["_claim_row"] = {
            "id": claim_id_for_text(claim_n, slug),
            "claim": claim_n,
            "status": status,
            "source": "verification",
            "sourceTitle": cid,
            "evidencePaths": evid,
            "checkIds": [f"check:{slug}:{cid}"],
            "detail": f"Gate {cid}={'pass' if ok else 'fail'}",
        }
    return checks


def build_claim_ledger(
    *,
    slug: str,
    texts: list[tuple[str, str]],
    r1_ok: bool | None = None,
    r2_ok: bool | None = None,
    claim_map_ok: bool | None = None,
    research_ok: bool | None = None,
    validate_ok: bool | None = None,
) -> dict[str, Any]:
    """texts: list of (path, content)."""
    marker_claims: list[dict[str, Any]] = []
    for path, content in texts:
        marker_claims.extend(extract_marker_claims(content, source_path=path, scope=slug))

    evid = [p for p, _ in texts]
    checks = checks_from_gates(
        slug=slug,
        r1_ok=r1_ok,
        r2_ok=r2_ok,
        claim_map_ok=claim_map_ok,
        research_ok=research_ok,
        validate_ok=validate_ok,
        evidence_paths=evid,
    )
    gate_claims = [c.pop("_claim_row") for c in checks]
    claims = merge_claims(marker_claims + gate_claims)

    verified = sum(1 for c in claims if c.get("status") == "verified")
    failed = sum(1 for c in claims if c.get("status") == "failed")
    unverified = sum(1 for c in claims if c.get("status") == "unverified")

    # Feynman verificationState-ish rollup
    if failed:
        vstate = "failed"
    elif verified and unverified == 0:
        vstate = "verified"
    elif verified:
        vstate = "partial"
    elif checks:
        vstate = "not_checked" if all(c.get("status") == "pass" for c in checks) is False and not checks else "partial"
    else:
        vstate = "not_checked"
    # refine
    if failed:
        vstate = "failed"
    elif r1_ok is False or r2_ok is False or claim_map_ok is False:
        vstate = "failed"
    elif r1_ok and r2_ok and claim_map_ok:
        vstate = "verified" if unverified == 0 else "partial"
    elif any(x is False for x in (r1_ok, r2_ok, claim_map_ok, research_ok, validate_ok)):
        vstate = "failed"
    elif any(x is True for x in (r1_ok, r2_ok, claim_map_ok)):
        vstate = "partial"

    return {
        "schemaVersion": "orpath.claimLedger.v1",
        "slug": slug,
        "claimCount": len(claims),
        "summary": {
            "verified": verified,
            "failed": failed,
            "unverified": unverified,
        },
        "verificationState": vstate,
        "claims": claims,
        "checks": [
            {
                "id": c["id"],
                "title": c["title"],
                "claim": c["claim"],
                "claimId": c["claimId"],
                "status": c["status"],
                "evidencePaths": c.get("evidencePaths") or [],
            }
            for c in checks
        ],
    }


def write_claim_ledger(path: Path, ledger: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_verification_md(path: Path, ledger: dict[str, Any], *, extra: str = "") -> Path:
    """Feynman-style outputs/.drafts/<slug>-verification.md"""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Verification: {ledger.get('slug')}",
        "",
        f"- schema: `{ledger.get('schemaVersion')}`",
        f"- verificationState: **{ledger.get('verificationState')}**",
        f"- claimCount: {ledger.get('claimCount')}",
        f"- summary: {json.dumps(ledger.get('summary') or {}, ensure_ascii=False)}",
        "",
        "## Checks",
    ]
    for c in ledger.get("checks") or []:
        mark = "PASS" if c.get("status") == "pass" else "FAIL"
        sev = "FATAL" if mark == "FAIL" else "OK"
        lines.append(
            f"- **{sev}:** `{c.get('title')}` → {mark} (claimId=`{c.get('claimId')}`)"
        )
    lines += ["", "## Claims ledger"]
    for cl in ledger.get("claims") or []:
        lines.append(
            f"- `{cl.get('status')}` `{cl.get('id')}`: {cl.get('claim')}"
        )
    if extra:
        lines += ["", "## Notes", extra.strip()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def select_final_candidate(paths: dict[str, Path]) -> Path | None:
    """Feynman rule: revised if exists else cited else draft else paper."""
    for key in ("revised", "cited", "draft", "paper"):
        p = paths.get(key)
        if p and Path(p).is_file():
            return Path(p)
    return None
