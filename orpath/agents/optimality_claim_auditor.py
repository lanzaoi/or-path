#!/usr/bin/env python3
"""Optimality Claim Auditor — Anti-Hallucination Governance Engine (Task 5.3).

Enforces the OR-Path "Numbers Truth" iron law:
No agent (Researcher, Modeler, Supervisor, Writer) may claim "globally optimal",
"proven optimal", or "全局最优解" in natural language reports unless backed by:
  1. An exact mathematical solver (CP-SAT, HiGHS, MIP, Simplex, B&B) with status == "OPTIMAL", OR
  2. An explicit dual lower-bound convergence proof with duality gap <= tolerance (1e-4).

Heuristic methods (ALNS, Genetic Algorithms, Local Search, Greedy) and unproven
approximations are strictly forbidden from claiming global mathematical optimality.
Any unproven claim is flagged as a VIOLATION, with automatic generation of
academically honest degraded wording ("best-found feasible solution" / "高质量可行解").
"""
from __future__ import annotations

import enum
import math
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

__all__ = [
    "ClaimSeverity",
    "OptimalityClaim",
    "ClaimAuditResult",
    "OptimalityClaimAuditor",
    "UnprovenOptimalityClaimError",
    "audit_text",
    "audit_report_text",
    "assert_no_unproven_claims",
]


class ClaimSeverity(str, enum.Enum):
    """Severity level of a detected optimality claim."""

    INFO = "info"            # Hedged or verified claim
    WARNING = "warning"      # Borderline / ambiguous phrasing
    VIOLATION = "violation"  # Unproven absolute optimality claim


class UnprovenOptimalityClaimError(ValueError):
    """Raised when an unproven optimality claim is asserted without proof."""


@dataclass
class OptimalityClaim:
    """A single detected optimality claim inside text."""

    term: str
    context: str
    line_number: int
    start_pos: int
    end_pos: int
    severity: ClaimSeverity
    remediation_suggestion: str
    is_hedged: bool = False
    is_negated: bool = False


@dataclass
class ClaimAuditResult:
    """Full outcome of an optimality claim audit."""

    passed: bool
    claims: list[OptimalityClaim]
    violations_count: int
    proof_verified: bool
    proof_source: str | None
    remediation_text: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """Convert result to a plain dictionary."""
        return {
            "passed": self.passed,
            "violations_count": self.violations_count,
            "proof_verified": self.proof_verified,
            "proof_source": self.proof_source,
            "claims": [
                {
                    "term": c.term,
                    "context": c.context,
                    "line": c.line_number,
                    "severity": c.severity.value,
                    "remediation": c.remediation_suggestion,
                    "hedged": c.is_hedged,
                    "negated": c.is_negated,
                }
                for c in self.claims
            ],
            "remediation_text": self.remediation_text,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Regex Patterns & Vocabulary
# ---------------------------------------------------------------------------

# Absolute / strong optimality patterns (Chinese)
_ZH_STRONG_CLAIMS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"全局最优解"), "当前探索的高质量可行解"),
    (re.compile(r"全局最优"), "当前找到的最优解"),
    (re.compile(r"已证明最优"), "已知高质量解"),
    (re.compile(r"理论最优解?"), "优质近似解"),
    (re.compile(r"数学最优解?"), "数值计算可行解"),
    (re.compile(r"严格最优解?"), "高质量可行解"),
    (re.compile(r"全局最佳"), "局部优质方案"),
    (re.compile(r"全局极小"), "局部极小"),
    (re.compile(r"全局极大"), "局部极大"),
    (re.compile(r"最优解"), "高质量可行解"),
]

# Absolute / strong optimality patterns (English)
_EN_STRONG_CLAIMS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bglobally\s+optimal\s+solution\b", re.I), "best-found feasible solution"),
    (re.compile(r"\bglobally\s+optimal\b", re.I), "best-found feasible"),
    (re.compile(r"\bproven\s+optimal\s+solution\b", re.I), "empirically best-found solution"),
    (re.compile(r"\bproven\s+optimal\b", re.I), "empirically best-found"),
    (re.compile(r"\bproven\s+optimality\b", re.I), "high-quality convergence"),
    (re.compile(r"\bexact\s+optimum\b", re.I), "heuristic incumbent"),
    (re.compile(r"\bstrictly\s+optimal\b", re.I), "high-quality feasible"),
    (re.compile(r"\bglobal\s+optimum\b", re.I), "local incumbent"),
    (re.compile(r"\boptimal\s+solution\b", re.I), "feasible candidate solution"),
    (re.compile(r"\btrue\s+optimum\b", re.I), "incumbent solution"),
]

# Words that negate the claim in the preceding context window (e.g. "not optimal", "未能达到全局最优")
# Chinese negations are matched as substrings (no word boundaries in Chinese);
# English negations MUST be matched with word boundaries — the previous bare
# substring list matched "no" inside "now" and let an unproven claim such as
# "We now claim this is a globally optimal solution" pass as a disclaimer.
_NEGATION_PREFIXES = [
    "不", "未", "没", "非", "并非", "无法证明", "不保证", "难以保证", "不能保证", "未能",
    "无法", "难以", "没能", "谈不上", "算不上", "远未",
]

#: English negations matched on word boundaries (lowercased prefix window).
_NEGATION_RES: list[re.Pattern[str]] = [
    re.compile(
        r"(?<![a-z])(?:not|no|never|cannot|can'?t|cant|doesn'?t|does not|didn'?t"
        r"|don'?t|without|unproven|hardly|failed to prove)(?![a-z])",
        re.IGNORECASE,
    ),
    re.compile(r"\bnon-", re.IGNORECASE),
]

# Words that hedge / soften the claim (e.g. "近似最优", "near-optimal", "local optimum")
_HEDGE_PREFIXES = [
    "近似", "接近", "局部", "相对", "较优", "当前探索", "已知最好",
    "near", "approximate", "approximately", "local", "locally",
    "best-found", "best found", "candidate", "pseudo", "sub", "suboptimal",
]

# Exact solvers allowlist
_EXACT_SOLVER_KEYWORDS = {
    "cp-sat", "cpsat", "mip", "milp", "highs", "highspy", "scip", "gurobi",
    "cplex", "cbc", "glpk", "simplex", "branch_and_bound", "branch-and-bound",
    "branch_and_cut", "branch-and-cut", "networkx", "exact",
}

# Heuristic / metaheuristic keywords that disqualify optimality claims
_HEURISTIC_KEYWORDS = {
    "alns", "ga", "genetic", "heuristic", "metaheuristic", "greedy",
    "simulated_annealing", "local_search", "tabu", "vns", "aco", "pso",
    "mpc", "rolling_horizon", "rolling",
}


# ---------------------------------------------------------------------------
# OptimalityClaimAuditor Core Engine
# ---------------------------------------------------------------------------

class OptimalityClaimAuditor:
    """Governance auditor that scans texts for unproven mathematical optimality claims."""

    def __init__(
        self,
        gap_tolerance: float = 1e-4,
        allow_hedged: bool = True,
    ) -> None:
        self.gap_tolerance = gap_tolerance
        self.allow_hedged = allow_hedged

    def verify_mathematical_proof(
        self,
        solver_metadata: Mapping[str, Any] | None = None,
        solution_envelope: Mapping[str, Any] | None = None,
        text_context: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if claims of global optimality have verifiable mathematical justification."""
        meta = dict(solver_metadata or {})
        env = dict(solution_envelope or {})

        # 1. Direct explicit boolean flag
        if meta.get("proven_optimal") is True or env.get("proven_optimal") is True:
            return True, "explicit proven_optimal == True"

        # 2. Check solver type & solver status
        solver_name = str(meta.get("solver") or env.get("solver") or "").lower()
        method_class = str(meta.get("method_class") or env.get("method_class") or "").lower()
        status = str(meta.get("status") or env.get("status") or "").upper()

        is_heuristic = any(h in solver_name or h in method_class for h in _HEURISTIC_KEYWORDS)
        is_exact = any(e in solver_name or e in method_class for e in _EXACT_SOLVER_KEYWORDS)

        # 3. Check duality gap if available
        gap = meta.get("gap") if "gap" in meta else env.get("gap")
        if gap is None and "optimality_gap" in meta:
            gap = meta["optimality_gap"]
        if gap is None and "optimality_gap" in env:
            gap = env["optimality_gap"]

        if gap is not None:
            try:
                gap_val = float(gap)  # accepts int, float and numeric strings
                if not math.isnan(gap_val) and not math.isinf(gap_val):
                    if abs(gap_val) <= self.gap_tolerance:
                        return True, f"verified duality gap {gap_val} <= tolerance {self.gap_tolerance}"
            except (TypeError, ValueError):
                pass  # non-numeric gap metadata: ignore rather than crash

        # Check lower_bound == upper_bound / objective.  Use explicit ``is None``
        # checks rather than ``or`` so that a legitimate zero bound is not
        # silently discarded (0 is falsy but is a valid numeric bound).
        lb = meta.get("lower_bound")
        if lb is None:
            lb = env.get("lower_bound")
        if lb is None:
            lb = meta.get("dual_bound")
        if lb is None:
            lb = env.get("dual_bound")
        ub = meta.get("upper_bound")
        if ub is None:
            ub = env.get("upper_bound")
        if ub is None:
            ub = meta.get("objective")
        if ub is None:
            ub = env.get("objective")
        if (
            isinstance(lb, (int, float))
            and isinstance(ub, (int, float))
            and not isinstance(lb, bool)
            and not isinstance(ub, bool)
        ):
            if abs(float(ub) - float(lb)) <= self.gap_tolerance * max(1.0, abs(float(ub))):
                return True, f"verified lower_bound {lb} matches upper_bound {ub} within tolerance"

        # 5. Exact solver with OPTIMAL status
        if is_exact and status == "OPTIMAL" and not is_heuristic:
            return True, f"exact solver {solver_name!r} verified with status OPTIMAL"

        # 6. Fallback: Check text context for explicit proof markers.
        #    NOTE: this is an *opt-in* escape hatch.  ``audit_text`` never
        #    forwards the claim text here (that would be self-referential);
        #    only callers that pass a dedicated proof-citation string reach
        #    this branch.  The patterns require an explicit numeric gap or
        #    bound-equality statement so an incidental phrase cannot
        #    self-certify a claim.
        if text_context:
            text_lower = text_context.lower()
            if re.search(r"gap\s*[:=]\s*0(\.0+)?\b", text_lower) or re.search(
                r"gap\s*<=\s*1e-\d+", text_lower
            ):
                return True, "text context contains explicit gap == 0 proof citation"
            if "下界与上界相等" in text_context or "下界与目标值一致" in text_context:
                return True, "text context contains lower == upper bound proof"

        return False, None

    def audit_text(
        self,
        text: str,
        solver_metadata: Mapping[str, Any] | None = None,
        solution_envelope: Mapping[str, Any] | None = None,
    ) -> ClaimAuditResult:
        """Audit natural language text for unproven optimality claims.

        Args:
            text: The report or message text to audit.
            solver_metadata: Optional solver parameters, method, status, gap.
            solution_envelope: Optional complete solution dictionary.

        Returns:
            A :class:`ClaimAuditResult` detailing claims found, severity, and remediation.
        """
        proof_verified, proof_source = self.verify_mathematical_proof(
            solver_metadata=solver_metadata,
            solution_envelope=solution_envelope,
            # Deliberately do NOT pass ``text`` as ``text_context``: the claim
            # text must never be its own proof.  Doing so would let a forged
            # sentence such as "...globally optimal (gap <= 1e-6)..."
            # self-certify and bypass the Numbers Truth iron law.  Machine
            # verification must come from solver metadata / solution envelope
            # (or an explicit, caller-supplied proof citation via the public
            # ``verify_mathematical_proof`` API).
        )

        claims: list[OptimalityClaim] = []
        if not isinstance(text, str) or not text:
            return ClaimAuditResult(
                passed=True,
                claims=[],
                violations_count=0,
                proof_verified=proof_verified,
                proof_source=proof_source,
                remediation_text="",
                summary="Audit PASSED: No optimality claims found in text.",
            )
        lines = text.splitlines(keepends=True)
        remediation_text = text

        patterns = _ZH_STRONG_CLAIMS + _EN_STRONG_CLAIMS

        current_char_offset = 0
        for line_idx, line in enumerate(lines, start=1):
            # Collect every candidate match on this line, then select the
            # longest non-overlapping ones.  Processing patterns in
            # declaration order alone lets a shorter sub-pattern (e.g.
            # "最优解") partially overlap a longer one ("已证明最优") and
            # double-count the same textual span.
            collected: list[tuple[int, int, str, str]] = []
            for pattern, suggestion in patterns:
                for match in pattern.finditer(line):
                    collected.append(
                        (match.start(), match.end(), match.group(0), suggestion)
                    )
            collected.sort(key=lambda c: (-(c[1] - c[0]), c[0]))

            occupied_spans: list[tuple[int, int]] = []
            for start, end, term, suggestion in collected:
                # Skip any match that overlaps an already-selected (longer) span.
                if any(not (end <= os or start >= oe) for os, oe in occupied_spans):
                    continue
                occupied_spans.append((start, end))

                # Inspect prefix window (up to 30 chars before match)
                prefix = line[max(0, start - 30):start].lower()
                immediate_prefix = line[max(0, start - 15):start].strip().lower().rstrip("- \t")

                is_neg = any(neg in prefix for neg in _NEGATION_PREFIXES) or any(
                    neg_re.search(prefix) for neg_re in _NEGATION_RES
                )
                is_hdg = any(immediate_prefix.endswith(hdg) or hdg == immediate_prefix for hdg in _HEDGE_PREFIXES)

                # If negated (e.g. "并非全局最优", "not optimal"), it's an honest disclaimer
                if is_neg:
                    severity = ClaimSeverity.INFO
                # If hedged (e.g. "近似全局最优", "near-optimal") and allowed
                elif is_hdg and self.allow_hedged:
                    severity = ClaimSeverity.INFO
                # If proof is mathematically verified
                elif proof_verified:
                    severity = ClaimSeverity.INFO
                else:
                    severity = ClaimSeverity.VIOLATION

                claim = OptimalityClaim(
                    term=term,
                    context=line.strip(),
                    line_number=line_idx,
                    start_pos=current_char_offset + start,
                    end_pos=current_char_offset + end,
                    severity=severity,
                    remediation_suggestion=suggestion,
                    is_hedged=is_hdg,
                    is_negated=is_neg,
                )
                claims.append(claim)

            current_char_offset += len(line)

        # Build clean remediation replacement if violations exist
        violations = [c for c in claims if c.severity == ClaimSeverity.VIOLATION]
        if violations and not proof_verified:
            # Replace each violation term with its suggestion
            for c in violations:
                remediation_text = remediation_text.replace(c.term, c.remediation_suggestion)

        passed = len(violations) == 0

        if passed:
            if claims:
                summary = f"Audit PASSED: {len(claims)} claim(s) found, all justified ({proof_source or 'hedged/disclaimed'})."
            else:
                summary = "Audit PASSED: No optimality claims found in text."
        else:
            summary = (
                f"Audit VIOLATION: Found {len(violations)} unproven optimality claim(s) without mathematical proof. "
                "Forbidden under Numbers Truth iron law."
            )

        return ClaimAuditResult(
            passed=passed,
            claims=claims,
            violations_count=len(violations),
            proof_verified=proof_verified,
            proof_source=proof_source,
            remediation_text=remediation_text,
            summary=summary,
        )

    def assert_no_unproven_claims(
        self,
        text: str,
        solver_metadata: Mapping[str, Any] | None = None,
        solution_envelope: Mapping[str, Any] | None = None,
    ) -> ClaimAuditResult:
        """Run audit and raise UnprovenOptimalityClaimError if any violation exists."""
        res = self.audit_text(
            text,
            solver_metadata=solver_metadata,
            solution_envelope=solution_envelope,
        )
        if not res.passed:
            details = "\n".join(
                f"  - Line {c.line_number}: {c.term!r} in context {c.context!r} -> Suggestion: {c.remediation_suggestion!r}"
                for c in res.claims
                if c.severity == ClaimSeverity.VIOLATION
            )
            raise UnprovenOptimalityClaimError(
                f"Unproven optimality claims detected ({res.violations_count} violation(s)):\n{details}\n"
                f"Remediated proposal:\n{res.remediation_text}"
            )
        return res


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

_GLOBAL_AUDITOR = OptimalityClaimAuditor()


def audit_text(
    text: str,
    solver_metadata: Mapping[str, Any] | None = None,
    solution_envelope: Mapping[str, Any] | None = None,
    gap_tolerance: float = 1e-4,
) -> ClaimAuditResult:
    """Audit natural language text using the global auditor."""
    auditor = _GLOBAL_AUDITOR if gap_tolerance == 1e-4 else OptimalityClaimAuditor(gap_tolerance=gap_tolerance)
    return auditor.audit_text(text, solver_metadata=solver_metadata, solution_envelope=solution_envelope)


def audit_report_text(
    text: str,
    solver_metadata: Mapping[str, Any] | None = None,
    solution_envelope: Mapping[str, Any] | None = None,
) -> ClaimAuditResult:
    """Alias for audit_text specifically intended for final solution reports."""
    return audit_text(text, solver_metadata=solver_metadata, solution_envelope=solution_envelope)


def assert_no_unproven_claims(
    text: str,
    solver_metadata: Mapping[str, Any] | None = None,
    solution_envelope: Mapping[str, Any] | None = None,
) -> ClaimAuditResult:
    """Enforce zero unproven claims or raise UnprovenOptimalityClaimError."""
    return _GLOBAL_AUDITOR.assert_no_unproven_claims(
        text, solver_metadata=solver_metadata, solution_envelope=solution_envelope
    )
