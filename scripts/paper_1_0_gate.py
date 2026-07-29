#!/usr/bin/env python3
"""OR-Path paper protocol 1.0 gate = P0+P1+P2+P3 closeout checks."""
from __future__ import annotations

import json
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
    sys.path.insert(0, str(ROOT))

    # base P0/P1 paper_gate
    r = subprocess.run(
        [py, str(ROOT / "scripts" / "paper_gate.py")],
        cwd=str(ROOT),
        env=env(),
        text=True,
        capture_output=True,
    )
    print(r.stdout[-2500:] if r.stdout else "")
    if r.returncode != 0:
        print(r.stderr[-1500:] if r.stderr else "", file=sys.stderr)
        print("FAIL: nested paper_gate")
        return 1

    slug = "p0-paper-gate"
    fails: list[str] = []

    # P2 artifacts
    checks = {
        "versions": ROOT / "outputs" / ".artifacts" / f"{slug}-versions.json",
        "research_run": ROOT / "outputs" / ".drafts" / f"{slug}-research-run.json",
        "annotations": ROOT / "outputs" / ".drafts" / f"{slug}-annotations.json",
        "figure": ROOT / "outputs" / ".drafts" / f"{slug}-figure.html",
        "lab": ROOT / "outputs" / ".lab" / "CHANGELOG.md",
        "claim_ledger": ROOT / "outputs" / ".drafts" / f"{slug}-claim-ledger.json",
        "verification": ROOT / "outputs" / ".drafts" / f"{slug}-verification.md",
        "prov": ROOT / "outputs" / f"{slug}.provenance.md",
    }
    for k, p in checks.items():
        if not p.is_file():
            fails.append(f"missing {k}: {p}")
        else:
            print("OK", k, p.stat().st_size)

    # versions schema
    if checks["versions"].is_file():
        v = json.loads(checks["versions"].read_text(encoding="utf-8"))
        if v.get("schemaVersion") != "orpath.artifactVersions.v1":
            fails.append("versions schema")
        if int(v.get("versionCount") or 0) < 1:
            fails.append("versions empty")
        print("OK versions count", v.get("versionCount"), "deps", v.get("dependencyCount"))

    # research run validate
    from orpath.research_run import validate_research_run

    if checks["research_run"].is_file():
        run = json.loads(checks["research_run"].read_text(encoding="utf-8"))
        ok, errs = validate_research_run(run)
        print("research_run_valid", ok, errs)
        if not ok:
            fails.append("research_run:" + ";".join(errs))
        if run.get("constraints", {}).get("rawFullTextStored"):
            fails.append("rawFullTextStored true")

    # annotations schema
    if checks["annotations"].is_file():
        a = json.loads(checks["annotations"].read_text(encoding="utf-8"))
        if a.get("schema") != "orpath.annotations.v1":
            fails.append("annotations schema")

    # figure from solution numbers
    if checks["figure"].is_file():
        ft = checks["figure"].read_text(encoding="utf-8")
        if "objective=" not in ft:
            fails.append("figure missing objective")

    # lab changelog mentions slug
    if checks["lab"].is_file() and slug not in checks["lab"].read_text(encoding="utf-8"):
        fails.append("lab changelog missing slug")

    # P3: provenance must declare protocol stack
    if checks["prov"].is_file():
        pt = checks["prov"].read_text(encoding="utf-8")
        for needle in (
            "paper_protocol: P0+P1+P2+P3",
            "research_run",
            "artifact_versions",
            "final_candidate",
            "verificationState",
        ):
            if needle not in pt and needle.replace("_path", "") not in pt:
                # soft: research_run_path or research_run
                if needle == "research_run" and "research_run" in pt:
                    continue
                if needle == "artifact_versions" and "artifact_versions" in pt:
                    continue
                fails.append(f"prov missing {needle}")

    # unit: claim ledger + versions helpers
    from orpath.artifact_versions import record_versions
    from orpath.claim_ledger import claim_id_for_text
    from orpath.lab_continuity import write_solution_figure

    assert claim_id_for_text("x", "s").startswith("claim:")
    tmp = ROOT / "outputs" / ".drafts" / "_p3-fig-test.html"
    write_solution_figure(tmp, {"objective": 1, "status": "OK", "path": ["A", "B"]}, slug="t")
    if not tmp.is_file():
        fails.append("figure helper")
    else:
        tmp.unlink(missing_ok=True)
        tmp.with_suffix(".mmd").unlink(missing_ok=True)

    # t3 lg topology still green
    r2 = subprocess.run(
        [py, str(ROOT / "scripts" / "t3_lg_gate.py")],
        cwd=str(ROOT),
        env=env(),
        text=True,
        capture_output=True,
    )
    if r2.returncode != 0 or "PASS: t3_lg_gate" not in (r2.stdout or ""):
        fails.append("t3_lg_gate")
    else:
        print("OK t3_lg_gate")

    if fails:
        print("PAPER_1_0_FAIL")
        for f in fails:
            print("-", f)
        return 1
    print("PAPER_1_0_PASS")
    print("P2_PASS")
    print("P3_CLOSEOUT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
