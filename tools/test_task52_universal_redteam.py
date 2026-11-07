#!/usr/bin/env python3
"""Comprehensive test suite for the Universal Redteam Gate (Task 5.2).

Covers:
  - Single-domain runs (``--domain routing``, ``--domain scheduling``, ...)
    exit 0 and produce a well-formed report section.
  - The full 10-domain DIMO matrix passes and yields a compliant report
    (0 false positives, 50/50 attacks applied, 49 intercepted + the single
    documented Tube HASH fail-safe proven live by a positive control).
  - ``--strict`` mode: passes at 100% interception on tube-free subsets and
    fails honestly on the full matrix (the documented Tube fail-safe row).
  - Report output paths: explicit ``--out`` files are created with valid
    JSON and the canonical schema; the default path is honored.
  - CLI end-to-end via a real subprocess invocation.
  - Domain-certified operators: no DIMO mutation silently degrades to a
    generic heuristic fallback on the standard envelopes.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent

from scripts.universal_redteam_gate import (  # noqa: E402
    DOMAINS,
    REDTEAM_PROBLEM_IDS,
    SCHEMA,
    main,
    run_domain_section,
)

ALLOWED_STATUSES = {"intercepted", "unverified_failsafe", "missed", "not_applied", "error"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_report(path: Path) -> dict[str, Any]:
    """Load and validate the JSON report written by the gate."""
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert data["schema"] == SCHEMA
    return data


def _domain_section(report: dict[str, Any], domain: str) -> dict[str, Any]:
    """Extract one domain's section from a universal gate report."""
    sections = {str(s["domain"]): s for s in report["domains"]}
    assert domain in sections, f"{domain} missing from report"
    return sections[domain]


# ---------------------------------------------------------------------------
# 1. Single-domain runs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("domain", DOMAINS)
def test_single_domain_run_exits_zero(domain: str, tmp_path: Path) -> None:
    """``--domain <name>`` exits 0 for every supported domain."""
    out = tmp_path / f"universal_{domain}.json"
    assert main(["--domain", domain, "--out", str(out)]) == 0
    report = _load_report(out)
    assert report["ok"] is True
    assert report["verdict"] == "PASS"
    assert report["domains_tested"] == [domain]


@pytest.mark.parametrize("domain", DOMAINS)
def test_single_domain_report_wellformed(domain: str, tmp_path: Path) -> None:
    """Each single-domain report carries baseline, 5 DIMO rows and native gate."""
    out = tmp_path / f"universal_{domain}.json"
    assert main(["--domain", domain, "--out", str(out)]) == 0
    report = _load_report(out)
    section = _domain_section(report, domain)

    assert section["problem_id"] == REDTEAM_PROBLEM_IDS[domain]
    assert section["baseline"]["ok"] is True, section["baseline"]
    assert section["baseline"]["failed_checks"] == []

    rows = section["dimo_attacks"]
    assert len(rows) == 5
    mutation_types = [row["mutation_type"] for row in rows]
    assert mutation_types == [
        "conservation",
        "capacity",
        "precedence",
        "bound",
        "hash",
    ]
    for row in rows:
        assert row["status"] in ALLOWED_STATUSES
        assert row["applied"] is True
        assert row["tampered"] is True
        assert row["validator_ok"] is False or row["status"] == "unverified_failsafe"
        if row["status"] == "intercepted":
            assert row["failed_checks"], row

    native = section["native_gate"]
    assert native["attack_count"] == 5
    assert native["attacks_applied"] == 5


def test_single_domain_unknown_rejected(tmp_path: Path) -> None:
    """An unknown ``--domain`` value exits 1 without writing a report."""
    out = tmp_path / "never.json"
    assert main(["--domain", "bogus", "--out", str(out)]) == 1
    assert not out.exists()


# ---------------------------------------------------------------------------
# 2. Full 10-domain matrix
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def full_report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Run the full 10-domain matrix once per module and return the report."""
    out = tmp_path_factory.mktemp("universal_redteam") / "universal_full.json"
    assert main(["--out", str(out)]) == 0
    return _load_report(out)


def test_full_matrix_passes(full_report: dict[str, Any]) -> None:
    """The full 10-domain matrix passes with a compliant summary."""
    assert full_report["ok"] is True
    assert full_report["verdict"] == "PASS"
    assert full_report["strict"] is False
    summary = full_report["summary"]
    assert summary["domains_tested"] == 10
    assert summary["domain_errors"] == 0
    assert summary["baselines_ok"] == 10
    assert summary["baseline_false_positives"] == 0
    assert summary["total_attacks"] == 50
    assert summary["attacks_applied"] == 50
    assert summary["missed"] == 0
    assert summary["not_applied"] == 0
    assert summary["matrix_disagreements"] == []
    # Numbers Truth: the interception rate is recomputed from raw counts.
    assert summary["interception_rate"] == pytest.approx(
        summary["intercepted"] / summary["total_attacks"]
    )


def test_full_matrix_interception_accounting(full_report: dict[str, Any]) -> None:
    """49 intercepted + the single documented Tube HASH fail-safe = 50."""
    summary = full_report["summary"]
    assert summary["intercepted"] == 49
    assert summary["unverified_failsafe"] == 1
    assert summary["intercepted"] + summary["unverified_failsafe"] == 50

    for domain in DOMAINS:
        section = _domain_section(full_report, domain)
        unverified = [
            row for row in section["dimo_attacks"] if row["status"] == "unverified_failsafe"
        ]
        if domain == "tube":
            assert len(unverified) == 1
            assert unverified[0]["mutation_type"] == "hash"
            assert unverified[0]["operator"] == "input_hash_tamper"
        else:
            assert unverified == [], (domain, unverified)
            for row in section["dimo_attacks"]:
                assert row["status"] == "intercepted", (domain, row)


def test_tube_failsafe_positive_control_is_live(full_report: dict[str, Any]) -> None:
    """The documented Tube fail-safe is proven by a live positive control."""
    tube = _domain_section(full_report, "tube")
    control = tube["failsafe_positive_control"]
    assert control["check_live"] is True
    assert control["variant_baseline_strict_input_hashes_ok"] is True
    assert control["variant_tampered_strict_input_hashes_ok"] is False


def test_native_and_dimo_matrices_agree(full_report: dict[str, Any]) -> None:
    """Every domain's native gate replay agrees with its DIMO matrix."""
    for domain in DOMAINS:
        section = _domain_section(full_report, domain)
        native_unverified = set(section["native_gate"]["unverified_attacks"])
        dimo_failsafe_operators = {
            str(row["operator"])
            for row in section["dimo_attacks"]
            if row["status"] == "unverified_failsafe"
        }
        assert native_unverified == dimo_failsafe_operators, domain


# ---------------------------------------------------------------------------
# 3. Strict mode
# ---------------------------------------------------------------------------

def test_strict_single_domain_passes(tmp_path: Path) -> None:
    """``--strict`` on a fully-intercepting domain exits 0 at 100% rate."""
    out = tmp_path / "universal_strict_routing.json"
    assert main(["--domain", "routing", "--strict", "--out", str(out)]) == 0
    report = _load_report(out)
    assert report["strict"] is True
    assert report["summary"]["interception_rate"] == 1.0
    assert report["summary"]["unverified_failsafe"] == 0


def test_strict_full_matrix_fails_honestly(tmp_path: Path) -> None:
    """``--strict`` on the full matrix exits 1: the Tube HASH row is unverified.

    The gate must never claim 100% interception while a mutation went
    unverified — strict mode fails safe instead of silently passing.
    """
    out = tmp_path / "universal_strict_full.json"
    assert main(["--strict", "--out", str(out)]) == 1
    report = _load_report(out)
    assert report["ok"] is False
    assert report["verdict"] == "FAIL"
    summary = report["summary"]
    assert summary["interception_rate"] < 1.0
    assert summary["unverified_failsafe"] == 1
    tube = _domain_section(report, "tube")
    failsafe_rows = [
        row for row in tube["dimo_attacks"] if row["status"] == "unverified_failsafe"
    ]
    assert [row["mutation_type"] for row in failsafe_rows] == ["hash"]


# ---------------------------------------------------------------------------
# 4. Report output paths
# ---------------------------------------------------------------------------

def test_report_written_to_explicit_path(tmp_path: Path) -> None:
    """``--out`` creates nested directories and writes valid schema JSON."""
    out = tmp_path / "nested" / "dir" / "universal_redteam_report.json"
    assert not out.parent.exists()
    assert main(["--domain", "scheduling", "--out", str(out)]) == 0
    assert out.is_file()
    report = _load_report(out)
    assert report["domains_tested"] == ["scheduling"]
    assert report["report_path"] == str(out)


def test_default_report_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The default report path ``outputs/universal_redteam_report.json`` is used."""
    monkeypatch.chdir(tmp_path)  # relative paths must resolve against ROOT, not cwd
    assert main(["--domain", "finance"]) == 0
    default_path = ROOT / "outputs" / "universal_redteam_report.json"
    assert default_path.is_file()
    report = _load_report(default_path)
    assert report["domains_tested"] == ["finance"]


# ---------------------------------------------------------------------------
# 5. Domain-certified operators (no silent generic fallback)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("domain", DOMAINS)
def test_dimo_operators_are_domain_certified(domain: str, tmp_path: Path) -> None:
    """Every DIMO row uses a domain-certified builder, never a generic fallback."""
    out = tmp_path / f"universal_op_{domain}.json"
    assert main(["--domain", domain, "--out", str(out)]) == 0
    report = _load_report(out)
    section = _domain_section(report, domain)
    for row in section["dimo_attacks"]:
        assert row["operator"] is not None
        assert not str(row["operator"]).startswith("generic_"), (domain, row)
        assert "Domain" in str(row["description"]), (domain, row)


def test_run_domain_section_tube_control() -> None:
    """Direct section eval: Tube positive control proves the check is live."""
    section = run_domain_section("tube")
    assert "error" not in section
    control = section["failsafe_positive_control"]
    assert control["check_live"] is True


# ---------------------------------------------------------------------------
# 6. CLI end-to-end (real subprocess)
# ---------------------------------------------------------------------------

def test_cli_subprocess_end_to_end(tmp_path: Path) -> None:
    """The script runs standalone: JSON report + single-line PASS verdict."""
    out = tmp_path / "cli_report.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "universal_redteam_gate.py"),
            "--domain",
            "scheduling",
            "--out",
            str(out),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert lines[-1] == "PASS universal_redteam_gate"
    report = json.loads("\n".join(lines[:-1]))
    assert report["schema"] == SCHEMA
    assert report["domains_tested"] == ["scheduling"]
    assert out.is_file()
    assert _load_report(out)["ok"] is True
