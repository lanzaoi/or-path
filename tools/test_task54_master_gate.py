#!/usr/bin/env python3
"""Comprehensive test suite for OR Swarms Master CI Gate (Task 5.4).

Covers:
  - Section 1: Meta-Schema & Contract Compliance
  - Section 2: Golden Envelopes & Solvers Health
  - Section 3: Composite Lead & Lineage Relay Continuity
  - Section 4: Universal DIMO Redteam Interception
  - Section 5: Natural Language Optimality Claim Audit
  - Section 6: Multi-Domain Control Plane Integrity
  - End-to-end Master Gate execution & JSON report structure
  - CLI execution via subprocess with --quick and custom --out
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from scripts.or_swarms_master_gate import (
    run_master_gate,
    run_section1_meta_contracts,
    run_section2_solvers_health,
    run_section3_lineage_relay,
    run_section4_universal_redteam,
    run_section5_optimality_claims,
    run_section6_control_plane,
)


def test_section1_meta_contracts():
    res = run_section1_meta_contracts()
    assert res["ok"] is True
    assert res["domains_checked"] == 10
    assert len(res["results"]) == 10


def test_section2_solvers_health():
    res = run_section2_solvers_health(quick=True)
    assert res["ok"] is True
    assert res["domains_checked"] == 10
    for item in res["results"]:
        assert item["ok"] is True
        assert item["status"] in ("OPTIMAL", "FEASIBLE")


def test_section3_lineage_relay():
    res = run_section3_lineage_relay()
    assert res["ok"] is True
    assert res["chain_verified"] is True
    assert res["tamper_intercepted"] is True


def test_section4_universal_redteam():
    res = run_section4_universal_redteam(strict=False)
    assert res["ok"] is True
    assert res["intercepted"] >= 49
    assert res["baselines_ok"] == 10


def test_section5_optimality_claims():
    res = run_section5_optimality_claims()
    assert res["ok"] is True
    assert res["proven_claim_passed"] is True
    assert res["unproven_claim_rejected"] is True
    assert res["exception_enforced"] is True


def test_section6_control_plane():
    res = run_section6_control_plane()
    assert res["ok"] is True
    assert len(res["compiled_domains"]) == 10
    assert len(res["compiled_composites"]) == 3


def test_run_master_gate_end_to_end():
    report = run_master_gate(quick=True)
    assert report["ok"] is True
    assert report["gate"] == "or_swarms_master_gate"
    assert report["summary"]["total_sections"] == 6
    assert report["summary"]["passed_sections"] == 6
    assert report["summary"]["failed_sections"] == 0


def test_master_gate_cli_subprocess(tmp_path: Path):
    out_file = tmp_path / "custom_master_report.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "or_swarms_master_gate.py"), "--quick", "--out", str(out_file)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0, f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "PASS or_swarms_master_gate" in proc.stdout
    assert "TOTAL VERDICT: PASS" in proc.stdout

    assert out_file.exists()
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["ok"] is True
    assert saved["summary"]["passed_sections"] == 6
