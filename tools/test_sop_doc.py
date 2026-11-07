#!/usr/bin/env python3
"""Tests for docs/or-paper-sop.md — OR paper SOP soft-rubric doc.

Verifies the SOP distilled from the legacy R1/R2 hard gates and the Claim
evidence-chain mechanism exists, is substantial, and covers the six required
chapters plus the 10-item Reviewer self-check.

Run:
    .venv/bin/python -m pytest tools/test_sop_doc.py
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOP = ROOT / "docs" / "or-paper-sop.md"


@pytest.fixture(scope="module")
def sop_text() -> str:
    if not SOP.is_file():
        pytest.fail(f"SOP doc missing: {SOP}")
    return SOP.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Existence & richness
# ---------------------------------------------------------------------------

def test_sop_file_exists():
    assert SOP.is_file(), f"expected docs/or-paper-sop.md at {SOP}"


def test_sop_is_substantial(sop_text: str):
    size = SOP.stat().st_size
    assert size > 2000, f"SOP too small ({size} bytes); expected > 2000"
    assert len(sop_text) > 2000
    # Must have real structure, not a stub.
    assert sop_text.count("\n#") >= 4, "SOP should have multiple top-level sections"
    assert sop_text.count("- **") >= 8, "SOP should have dense bullet content"


# ---------------------------------------------------------------------------
# Required headings / keywords (R1/R2 + Claim evolution)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "needle",
    [
        "数字真实性",
        "Numbers Truth",
        "自审核对清单",
        "数学规划模型",
        "证据链闭环",
        "证据溯源",
        "文献引用",
        "数据溯源",
        "敏感性分析",
        "软指引",
    ],
)
def test_sop_contains_key_term(sop_text: str, needle: str):
    assert needle in sop_text, f"SOP missing required term: {needle}"


@pytest.mark.parametrize(
    "heading",
    [
        "一、引言与核心原则",
        "二、运筹优化学术报告标准结构",
        "三、数字真实性核验规范",
        "四、事实主张与证据溯源",
        "五、文献引用与数据溯源规范",
        "六、Verifier / Reviewer 智能体自审核对清单",
    ],
)
def test_sop_has_required_chapter(sop_text: str, heading: str):
    assert heading in sop_text, f"SOP missing chapter heading: {heading}"


# ---------------------------------------------------------------------------
# Standard paper structure sub-sections
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "needle",
    [
        "摘要与关键指标速览",
        "问题重述与工程/物理假设",
        "决策变量",
        "目标函数",
        "约束集合",
        "求解策略与算子选型",
        "数值计算结果与敏感性分析",
        "模型评价、优缺点与工业落地建议",
    ],
)
def test_sop_covers_standard_structure(sop_text: str, needle: str):
    assert needle in sop_text, f"SOP missing structure element: {needle}"


# ---------------------------------------------------------------------------
# 10-item Review Rubric Checklist
# ---------------------------------------------------------------------------

CHECKLIST_ITEMS = [
    "结构完整",
    "数字真实性",
    "独立重算",
    "最优性诚实声明",
    "数学规划模型自洽",
    "Claim 证据链闭环",
    "引用合规",
    "敏感性分析真实",
    "求解策略说明",
    "局限性与落地建议",
]


def test_sop_has_ten_item_checklist(sop_text: str):
    chapter6 = sop_text.split("六、Verifier")[1] if "六、Verifier" in sop_text else sop_text
    missing = [item for item in CHECKLIST_ITEMS if item not in chapter6]
    assert not missing, f"checklist missing items: {missing}"


def test_checklist_uses_pass_warn_fail(sop_text: str):
    """Each rubric item must offer a three-tier judgment."""
    chapter6 = sop_text.split("六、Verifier")[1] if "六、Verifier" in sop_text else sop_text
    for tier in ("PASS", "WARN", "FAIL"):
        assert tier in chapter6, f"checklist missing tier: {tier}"


# ---------------------------------------------------------------------------
# Provenance / hard-gate linkage
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "needle",
    [
        "r2_numeric_check",
        "r1_cite_check",
        "r1_claim_map",
        "claim_ledger",
        "validate_solution",
        "solution.json",
    ],
)
def test_sop_links_to_hard_gates(sop_text: str, needle: str):
    assert needle in sop_text, f"SOP missing linkage to: {needle}"
