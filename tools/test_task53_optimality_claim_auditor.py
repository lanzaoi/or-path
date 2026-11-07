#!/usr/bin/env python3
"""Comprehensive test suite for Optimality Claim Auditor (Task 5.3).

Covers:
  - Detection of Chinese & English strong optimality claims
  - Proof verification via exact solver status (CP-SAT, HiGHS, MIP)
  - Proof verification via duality gap <= tolerance
  - Rejection of unproven claims in heuristic / metaheuristic contexts (ALNS, GA, greedy)
  - Handling of honest negations (e.g. "not optimal", "未证明全局最优")
  - Handling of soft hedges (e.g. "near-optimal", "近似最优")
  - Automatic degradation remediation text generation
  - Exception raising via assert_no_unproven_claims
  - Result serialization via to_dict()
"""
from __future__ import annotations

import pytest

from orpath.agents.optimality_claim_auditor import (
    ClaimAuditResult,
    ClaimSeverity,
    OptimalityClaim,
    OptimalityClaimAuditor,
    UnprovenOptimalityClaimError,
    assert_no_unproven_claims,
    audit_report_text,
    audit_text,
)


# ---------------------------------------------------------------------------
# 1. Neutral Text & Clean Passes
# ---------------------------------------------------------------------------

def test_clean_text_no_claims():
    text = "本次计算完成，共探索了 50 种排产组合，获得了满足各项约束的有效可行方案。"
    res = audit_text(text)
    assert res.passed is True
    assert len(res.claims) == 0
    assert res.violations_count == 0
    assert "No optimality claims found" in res.summary


def test_clean_english_text():
    text = "The solver completed execution in 12.3 seconds, generating a valid schedule."
    res = audit_text(text)
    assert res.passed is True
    assert len(res.claims) == 0


# ---------------------------------------------------------------------------
# 2. Unproven Claim Detection (Violations)
# ---------------------------------------------------------------------------

def test_unproven_chinese_claims():
    text = "经过启发式搜索，我们得到了全局最优解，该方案成本最低。"
    res = audit_text(text)
    assert res.passed is False
    assert res.violations_count >= 1
    terms = [c.term for c in res.claims]
    assert "全局最优解" in terms
    assert "当前探索的高质量可行解" in res.remediation_text


def test_unproven_english_claims():
    text = "Our algorithm successfully discovered the globally optimal solution for this instance."
    res = audit_text(text)
    assert res.passed is False
    assert res.violations_count >= 1
    terms = [c.term for c in res.claims]
    assert any("globally optimal" in t.lower() for t in terms)
    assert "best-found feasible" in res.remediation_text


def test_heuristic_solver_forbidden_to_claim_optimal():
    text = "ALNS metaheuristic found the optimal solution after 500 iterations."
    solver_meta = {"solver": "alns-adaptive", "status": "FEASIBLE", "gap": 0.05}
    res = audit_text(text, solver_metadata=solver_meta)
    assert res.passed is False
    assert res.proof_verified is False
    assert res.violations_count >= 1


# ---------------------------------------------------------------------------
# 3. Verified Mathematical Proof (Legitimate Passes)
# ---------------------------------------------------------------------------

def test_verified_exact_solver_optimal():
    text = "经过 CP-SAT 严格求解，模型收敛并给出了全局最优解。"
    solver_meta = {"solver": "ortools-cpsat", "status": "OPTIMAL", "method_class": "exact"}
    res = audit_text(text, solver_metadata=solver_meta)
    assert res.passed is True
    assert res.proof_verified is True
    assert res.violations_count == 0
    assert any(c.severity == ClaimSeverity.INFO for c in res.claims)


def test_verified_duality_gap():
    text = "The branch-and-cut algorithm proved this to be the optimal solution with zero duality gap."
    solver_meta = {"gap": 0.0, "status": "OPTIMAL"}
    res = audit_text(text, solver_metadata=solver_meta)
    assert res.passed is True
    assert res.proof_verified is True
    assert res.violations_count == 0


def test_verified_lower_upper_bound_match():
    text = "当前解为最优解。"
    solver_meta = {"lower_bound": 1000.0, "upper_bound": 1000.0, "objective": 1000.0}
    res = audit_text(text, solver_metadata=solver_meta)
    assert res.passed is True
    assert res.proof_verified is True


def test_verified_explicit_flag():
    text = "The proven optimal solution has been certified by the independent auditor."
    envelope = {"proven_optimal": True}
    res = audit_text(text, solution_envelope=envelope)
    assert res.passed is True
    assert res.proof_verified is True


# ---------------------------------------------------------------------------
# 4. Negations and Hedged Phrasing
# ---------------------------------------------------------------------------

def test_negated_claim_is_honest():
    text = "受限于求解时间，本方案并不保证是全局最优解，但满足所有现实约束。"
    res = audit_text(text)
    assert res.passed is True
    assert res.violations_count == 0
    claim = res.claims[0]
    assert claim.is_negated is True
    assert claim.severity == ClaimSeverity.INFO


def test_english_negated_claim():
    text = "This candidate is not a globally optimal solution, but offers a practical dispatch."
    res = audit_text(text)
    assert res.passed is True
    assert res.violations_count == 0
    assert any(c.is_negated for c in res.claims)


def test_hedged_claim_passes():
    text = "通过遗传算法获得了近似最优解与较优的装箱分配。"
    res = audit_text(text)
    assert res.passed is True
    assert res.violations_count == 0
    assert any(c.is_hedged for c in res.claims)


def test_english_near_optimal_hedge():
    text = "We achieved a near-optimal solution with less than 2% deviation."
    res = audit_text(text)
    assert res.passed is True
    assert res.violations_count == 0


# ---------------------------------------------------------------------------
# 5. Assertion Enforcement & Remediation
# ---------------------------------------------------------------------------

def test_assert_no_unproven_claims_raises():
    text = "我们已经求得理论最优解。"
    with pytest.raises(UnprovenOptimalityClaimError) as exc_info:
        assert_no_unproven_claims(text)

    err_msg = str(exc_info.value)
    assert "Unproven optimality claims detected" in err_msg
    assert "优质近似解" in err_msg or "当前探索" in err_msg


def test_assert_no_unproven_claims_passes_when_clean():
    text = "本轮求解获得了高质量可行解。"
    res = assert_no_unproven_claims(text)
    assert res.passed is True


def test_to_dict_structure():
    text = "发现了全局最优。"
    res = audit_report_text(text)
    d = res.to_dict()
    assert d["passed"] is False
    assert d["violations_count"] >= 1
    assert isinstance(d["claims"], list)
    assert "remediation_text" in d
    assert "summary" in d


# --------------------------------------------------------------------------- #
# Regression: negation must be word-bounded (no substring "no" in "now") and
# must cover common Chinese disclaimers; heuristics stay strict.
# --------------------------------------------------------------------------- #
def test_english_no_is_not_matched_inside_words() -> None:
    """'now' / 'canonical' must not be read as the negation 'no'."""
    res = audit_text("We now claim this is a globally optimal solution for routing.")
    assert res.passed is False
    assert res.violations_count >= 1
    assert all(not c.is_negated for c in res.claims)

    res2 = audit_text("The canonical globally optimal solution is claimed.")
    assert res2.passed is False


def test_english_word_boundary_negation_still_detected() -> None:
    res = audit_text("This candidate is not a globally optimal solution.")
    assert res.passed is True
    assert any(c.is_negated for c in res.claims)


def test_chinese_disclaimer_wufa_is_negated() -> None:
    """'无法达到全局最优' is an honest disclaimer, not a violation."""
    res = audit_text("无法达到全局最优，当前为高质量可行解。")
    assert res.passed is True
    assert res.violations_count == 0
    assert any(c.is_negated for c in res.claims)


def test_chinese_disclaimer_weinan_is_negated() -> None:
    res = audit_text("难以达到全局最优解，仅给出可行方案。")
    assert res.passed is True
    assert any(c.is_negated for c in res.claims)


def test_sub_optimal_is_hedged() -> None:
    """'sub-optimal solution' must be recognized as a hedge, not a violation."""
    res = audit_text("This is a sub-optimal solution but satisfies constraints.")
    assert res.passed is True
    assert any(c.is_hedged for c in res.claims)


def test_gap_coercion_handles_strings_nan_and_garbage() -> None:
    auditor = OptimalityClaimAuditor()
    assert auditor.verify_mathematical_proof({"gap": "0"})[0] is True
    assert auditor.verify_mathematical_proof({"gap": "0.0000"})[0] is True
    assert auditor.verify_mathematical_proof({"gap": float("nan")})[0] is False
    assert auditor.verify_mathematical_proof({"gap": "abc"})[0] is False
    assert auditor.verify_mathematical_proof({"gap": None})[0] is False


def test_audit_text_tolerates_empty_and_non_string() -> None:
    assert audit_text("").passed is True
    assert audit_text(None).passed is True  # type: ignore[arg-type]

