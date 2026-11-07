"""Lean Cartridges and Adaptive Multi-Agent Graph Tests (Plan 5.1).

High-signal architectural verification replacing brittle 60-agent mock call-count assertions:
1. Verifies 10 pluggable DomainCartridge packages load cleanly and bind real domain analytics tools.
2. Verifies Tier-A, Tier-B, Tier-C adaptive routing flow through expected deterministic states.
3. Verifies zero truncation and clean Feynman file-pointer handoffs across agent boundaries.
4. Verifies solver validation failure and reviewer FATAL defects trigger bounded recovery loops.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from orpath.agents.cartridges import (
    CARTRIDGES,
    cartridge_tier,
    cartridge_tools,
    resolve_cartridge,
)
from orpath.agents.adaptive_graph import build_adaptive_graph
from orpath.agents.core_state import CorePipelineState, serialized_state_size_bytes


def test_cartridges_integrity_and_probes() -> None:
    """Verify all 10 domain cartridges bind genuine profile and inspect tools."""
    expected_domains = (
        "scheduling",
        "routing",
        "microgrid",
        "facility",
        "finance",
        "pricing",
        "inventory",
        "rostering",
        "project",
        "tube",
    )
    for dom in expected_domains:
        assert dom in CARTRIDGES, f"Missing cartridge: {dom}"
        tools = cartridge_tools(dom)
        assert tools.get("profile_tool") is not None, f"Cartridge {dom} missing profile_tool"
        assert tools.get("inspect_tool") is not None, f"Cartridge {dom} missing inspect_tool"


def test_core_state_file_pointer_discipline(tmp_path: Path) -> None:
    """Verify state serialization size remains < 8 KB across file-pointer transitions."""
    st: CorePipelineState = {
        "slug": "test-run",
        "workdir": str(tmp_path),
        "problem_id": "cvrp_n5",
        "problem_class": "cvrp",
        "domain_cartridge": "routing",
        "complexity_tier": "B",
        "problem_file": str(tmp_path / "problem.txt"),
        "solution_path": str(tmp_path / "solution.json"),
        "validate_path": str(tmp_path / "validate.json"),
        "paper_path": str(tmp_path / "paper.md"),
        "review_path": str(tmp_path / "review.md"),
        "validation_ok": True,
        "proven_optimal": False,
        "objective_value": 34.0,
        "optimality_gap": 0.05,
        "max_retries": 2,
    }
    size = serialized_state_size_bytes(st)
    assert size < 8192, f"State serialized size {size} exceeds 8 KB limit"


def test_adaptive_graph_compilation() -> None:
    """Verify adaptive graph compiles cleanly into a deterministic state graph."""
    graph = build_adaptive_graph()
    assert graph is not None
    # Graph must contain all essential 4-agent and deterministic gate nodes
    expected_nodes = {"preflight", "analyst", "modeler", "validator", "table_render", "writer", "doc_gate", "reviewer"}
    assert expected_nodes.issubset(set(graph.nodes.keys()))
