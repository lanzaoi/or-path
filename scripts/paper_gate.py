#!/usr/bin/env python3
"""P0+P1 paper_gate: draft→cite→review + claim_map + research + plan ledger."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def env() -> dict:
    e = dict(os.environ)
    e["PYTHONNOUSERSITE"] = "1"
    e["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    e.pop("PYTHONPATH", None)
    return e


def main() -> int:
    py = sys.executable
    slug = "p0-paper-gate"
    cmd = [
        py,
        str(ROOT / "orpath" / "run_orpath.py"),
        "run",
        "--problem-id",
        "shortest_path",
        "--solve-mode",
        "mock",
        "--knowledge-mode",
        "seed",
        "--slug",
        slug,
        "--thread-id",
        slug,
        "--fresh",
    ]
    r = subprocess.run(cmd, cwd=str(ROOT), env=env(), text=True, capture_output=True)
    print(r.stdout[-2500:] if r.stdout else "")
    if r.returncode != 0:
        print(r.stderr[-2500:] if r.stderr else "", file=sys.stderr)
        print("FAIL: run_orpath", r.returncode)
        return 1

    fails: list[str] = []
    checks = {
        "plan": ROOT / "outputs" / ".plans" / f"{slug}.md",
        "draft": ROOT / "outputs" / ".drafts" / f"{slug}-draft.md",
        "cited": ROOT / "outputs" / ".drafts" / f"{slug}-cited.md",
        "claim_map": ROOT / "outputs" / ".drafts" / f"{slug}-claim-map.json",
        "claim_ledger": ROOT / "outputs" / ".drafts" / f"{slug}-claim-ledger.json",
        "verification": ROOT / "outputs" / ".drafts" / f"{slug}-verification.md",
        "paper": ROOT / "papers" / f"{slug}.md",
        "review": ROOT / "outputs" / f"{slug}-review.md",
        "prov": ROOT / "outputs" / f"{slug}.provenance.md",
        "research": ROOT / "notes" / f"{slug}-research.md",
    }
    for k, p in checks.items():
        if not p.is_file():
            fails.append(f"missing {k}: {p}")
        else:
            print("OK", k, p.stat().st_size)

    plan = checks["plan"].read_text(encoding="utf-8") if checks["plan"].is_file() else ""
    if "stage=" not in plan:
        fails.append("plan missing stage logs")
    if "stage=`cite`" not in plan and "cite" not in plan:
        fails.append("plan missing cite stage")

    if checks["review"].is_file() and "Inline Annotations" not in checks["review"].read_text(
        encoding="utf-8"
    ):
        fails.append("review missing Inline Annotations")
    if checks["research"].is_file() and "Coverage Status" not in checks["research"].read_text(
        encoding="utf-8"
    ):
        fails.append("research missing Coverage Status")
    if checks["paper"].is_file() and "Validation" not in checks["paper"].read_text(encoding="utf-8"):
        fails.append("paper missing Validation section")
    if checks["cited"].is_file() and "Claim map" not in checks["cited"].read_text(encoding="utf-8"):
        fails.append("cited missing Claim map footer")
    if checks["claim_ledger"].is_file():
        import json

        led = json.loads(checks["claim_ledger"].read_text(encoding="utf-8"))
        if led.get("schemaVersion") != "orpath.claimLedger.v1":
            fails.append("claim_ledger schema")
        if not led.get("claims"):
            fails.append("claim_ledger empty claims")
        if not any(str(c.get("id", "")).startswith("claim:") for c in led.get("claims") or []):
            fails.append("claim_ledger missing claim: ids")
        print("OK ledger claims", led.get("claimCount"), "vstate", led.get("verificationState"))
    if checks["verification"].is_file():
        vt = checks["verification"].read_text(encoding="utf-8")
        if "verificationState" not in vt or "Checks" not in vt:
            fails.append("verification.md incomplete")
    if checks["prov"].is_file():
        pt = checks["prov"].read_text(encoding="utf-8")
        if "final_candidate" not in pt and "final_candidate_path" not in pt:
            fails.append("provenance missing final_candidate")
        if "verificationState" not in pt:
            fails.append("provenance missing verificationState")

    sm = (ROOT / "orpath" / "stage_map.json").read_text(encoding="utf-8")
    if "cite_pack" not in sm:
        fails.append("stage_map missing cite_pack")

    # product nodes include cite
    sys.path.insert(0, str(ROOT))
    from orpath.graph_product import PRODUCT_NODES

    if "cite_pack" not in PRODUCT_NODES:
        fails.append("PRODUCT_NODES missing cite_pack")
    if len(PRODUCT_NODES) != 15:
        fails.append(f"expected 15 product nodes got {len(PRODUCT_NODES)}")

    # claim map CLI on paper
    r_cm = subprocess.run(
        [
            py,
            str(ROOT / "tools" / "r1_claim_map.py"),
            "--draft",
            str(checks["paper"]),
            "--solution",
            str(ROOT / "outputs" / f"{slug}-solution.json"),
            "--whitelist",
            str(ROOT / "fixtures" / "t1" / "shortest_path" / "whitelist_refs.json"),
            "--research",
            str(checks["research"]),
            "--retrieval",
            str(ROOT / "notes" / f"{slug}-retrieval.json"),
        ],
        cwd=str(ROOT),
        env=env(),
        text=True,
        capture_output=True,
    )
    print("claim_map_cli", r_cm.returncode, (r_cm.stdout or "").strip())
    if r_cm.returncode != 0:
        fails.append("claim_map_cli:" + (r_cm.stderr or r_cm.stdout)[:300])

    r2 = subprocess.run(
        [
            py,
            str(ROOT / "tools" / "gate_research.py"),
            "--research",
            str(checks["research"]),
            "--retrieval",
            str(ROOT / "notes" / f"{slug}-retrieval.json"),
            "--knowledge-mode",
            "seed",
        ],
        cwd=str(ROOT),
        env=env(),
        text=True,
        capture_output=True,
    )
    print(r2.stdout.strip())
    if r2.returncode != 0:
        fails.append("gate_research:" + (r2.stderr or r2.stdout)[:200])

    # negative: claim map catches bad objective
    bad = ROOT / "outputs" / ".drafts" / "p0-bad-claim.md"
    bad.write_text(
        checks["paper"].read_text(encoding="utf-8").replace("objective = `42`", "objective = `99999`")
        + "\nWe are globally optimal forever.\n",
        encoding="utf-8",
    )
    r_bad = subprocess.run(
        [
            py,
            str(ROOT / "tools" / "r1_claim_map.py"),
            "--draft",
            str(bad),
            "--solution",
            str(ROOT / "outputs" / f"{slug}-solution.json"),
            "--whitelist",
            str(ROOT / "fixtures" / "t1" / "shortest_path" / "whitelist_refs.json"),
        ],
        cwd=str(ROOT),
        env=env(),
        text=True,
        capture_output=True,
    )
    print("claim_map_neg", r_bad.returncode)
    if r_bad.returncode == 0:
        fails.append("claim_map should fail on 99999 + global optimal")

    if fails:
        print("PAPER_GATE_FAIL")
        for f in fails:
            print("-", f)
        return 1
    print("PAPER_GATE_PASS")
    print("P0_PAPER_GATE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
