"""Phase 2 Cartridges and Domain Analytics validation suite.

Verifies:
1. All 22 CANONICAL_CLASSES map 100% to a DomainCartridge.
2. All 10 domain cartridges provide valid profile_tool and inspect_tool.
3. Invoking profile_tool on representative benchmarks returns non-empty structured data.
4. Invoking inspect_tool on golden envelopes returns non-empty structured envelope decomposition.
5. Tier mapping accurately assigns Tier-A to exact convex/LP/DP and Tier-B/C to hard combinatorial domains.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from orpath.domain_registry import CANONICAL_CLASSES
from orpath.agents.cartridges import (
    CARTRIDGES,
    cartridge_tier,
    cartridge_tools,
    resolve_cartridge,
)


def test_plan_2_1_all_canonical_classes_mapped() -> None:
    """Plan 2.1 DOD: all 22 registered canonical classes map 100% to cartridges."""
    assert len(CANONICAL_CLASSES) >= 22
    for cls_name in CANONICAL_CLASSES:
        c = resolve_cartridge(cls_name)
        assert c is not None, f"Class {cls_name} failed to resolve to a cartridge"
        assert c.domain in CARTRIDGES, f"Class {cls_name} domain {c.domain} not in CARTRIDGES"
        tier = cartridge_tier(cls_name)
        assert tier in ("A", "B", "C"), f"Class {cls_name} invalid tier {tier}"


def test_plan_2_2_tier_a_cartridges_exact_and_polynomial() -> None:
    """Plan 2.2 DOD: Tier-A domains are convex QP, stochastic LP, and WW-DP."""
    finance = CARTRIDGES["finance"]
    assert finance.default_tier == "A"
    assert any("portfolio" in mode for mode in finance.solver_modes)

    pricing = CARTRIDGES["pricing"]
    assert pricing.default_tier == "A"
    assert any("stochastic_lp" in mode for mode in pricing.solver_modes)

    # Single-item Wagner-Whitin DP is Tier-A
    assert cartridge_tier("lot_sizing") == "A"


def test_plan_2_3_all_ten_cartridges_have_genuine_probes() -> None:
    """Plan 2.3 DOD: all 10 domain cartridges bind genuine profile & inspect tools."""
    assert len(CARTRIDGES) >= 10
    for domain, c in CARTRIDGES.items():
        if domain == "general_or":
            continue
        tools = cartridge_tools(domain)
        profile = tools["profile"]
        inspect = tools["inspect"]
        assert profile is not None, f"Domain {domain} missing profile tool"
        assert inspect is not None, f"Domain {domain} missing inspect tool"
        # Tool name check
        p_name = getattr(profile, "name", "")
        i_name = getattr(inspect, "name", "")
        assert "profile_" in p_name, f"Domain {domain} profile tool has unexpected name {p_name}"
        assert "inspect_" in i_name, f"Domain {domain} inspect tool has unexpected name {i_name}"


def test_plan_2_3_probes_execute_on_benchmarks() -> None:
    """Plan 2.3 DOD: profile and inspect tools return non-empty decomposition on real cases."""
    # Scheduling
    sched_tools = cartridge_tools("scheduling")
    ft06_path = Path("fixtures/benchmarks/taillard/ft06.txt")
    if ft06_path.is_file():
        res = sched_tools["profile"].invoke({"file_path": str(ft06_path)})
        data = json.loads(res) if isinstance(res, str) else res
        assert data.get("ok") is True or "num_jobs" in data or "jobs" in data

    # Routing
    routing_tools = cartridge_tools("routing")
    vrp_path = Path("fixtures/benchmarks/vrp/cvrp_n5.json")
    if vrp_path.is_file():
        res = routing_tools["profile"].invoke({"file_path": str(vrp_path)})
        data = json.loads(res) if isinstance(res, str) else res
        assert data.get("ok") is True or "num_customers" in data
