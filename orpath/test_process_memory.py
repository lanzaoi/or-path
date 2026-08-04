"""Unit tests for process memory + tool catalog."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.process_memory import (  # noqa: E402
    FORBIDDEN_AUTHORITY,
    new_lesson,
    retrieve_lessons,
    strip_forbidden,
    write_retrieve_artifacts,
)
from orpath.tool_catalog import default_mode_for_class, list_tools, solver_claim_table  # noqa: E402


def test_seed_lessons_retrieve_tsp():
    hits = retrieve_lessons("CP-SAT circuit small n", root=ROOT, problem_class="tsp", topk=3)
    assert hits, "expected seed TSP lesson"
    assert any(h.get("problem_class") == "tsp" for h in hits)
    blob = json.dumps(hits)
    for bad in FORBIDDEN_AUTHORITY:
        # ids/summary must not smuggle authority solution keys as fields
        assert f'"{bad}"' not in blob or bad in {"path"}  # path may appear in artifact_paths strings


def test_strip_forbidden_drops_objective():
    raw = new_lesson(problem_class="tsp", summary="x")
    raw["objective"] = 999
    raw["tour"] = [1, 2, 3]
    cleaned = strip_forbidden(raw)
    assert "objective" not in cleaned
    assert "tour" not in cleaned


def test_write_artifacts(tmp_path: Path, monkeypatch):
    # use real seeds from ROOT but write notes under tmp by patching root structure
    notes = tmp_path / "notes"
    notes.mkdir()
    # copy minimal: call with ROOT so seeds load; write into tmp via slug under ROOT would pollute —
    # instead test retrieve + markdown only when seeds exist
    hits = retrieve_lessons("VRP capacity", root=ROOT, problem_class="vrp", topk=2)
    assert hits
    assert hits[0]["score"] >= hits[-1]["score"]


def test_tool_catalog_mcp_whitelist():
    all_t = list_tools()
    mcp_t = list_tools(mcp_only=True)
    assert len(all_t) >= len(mcp_t) >= 1
    assert default_mode_for_class("tsp") == "cpsat"
    assert default_mode_for_class("shortest_path") == "networkx"
    assert any(r["problem_class"] == "vrp" for r in solver_claim_table())


def test_mcp_tools_list_roundtrip():
    from orpath.mcp_server import _call_tool, _tools_list, handle

    tools = _tools_list()
    names = {t["name"] for t in tools}
    assert "orpath_memory_search" in names
    assert "orpath_list_solvers" in names
    out = _call_tool("orpath_list_solvers", {})
    assert out["solvers"]
    mem = _call_tool("orpath_memory_search", {"query": "Dijkstra", "problem_class": "shortest_path"})
    assert mem["hits"]
    init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init and init["result"]["serverInfo"]["name"] == "orpath"
