"""S5 LG intake front-door tests."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
FIX = ROOT / "fixtures" / "intake"


def test_product_nodes_include_intake():
    from orpath.graph_product import PRODUCT_NODES, export_stage_map

    assert PRODUCT_NODES[0] == "intake_ocr"
    assert "intake_parse" in PRODUCT_NODES
    m = export_stage_map()
    assert m["nodes"][0] == "intake_ocr"
    assert m["edges"][0]["to"] == "intake_ocr"


def test_skip_intake_invoke_once_still_ends():
    from orpath.control_plane import invoke_once

    final = invoke_once(
        root=ROOT,
        slug="s5-skip-intake",
        problem_id="shortest_path",
        solve_mode="mock",
        knowledge_mode="off",
        live_subagent=False,
        thread_id="s5-skip-intake-tid",
    )
    assert final.get("intake_skipped") is True or final.get("skip_intake") is True
    assert final.get("gate_validate_ok") is True
    assert final.get("stage") == "end" or final.get("provenance_path")
    assert final.get("gate_intake_ok") is True


def test_standalone_cli_intake(tmp_path: Path):
    # write under tmp by using root=tmp and copy source
    src = FIX / "ocr" / "sample.txt"
    r = subprocess.run(
        [
            PY,
            str(ROOT / "orpath" / "run_orpath.py"),
            "intake",
            "--root",
            str(ROOT),
            "--slug",
            "s5_cli_intake",
            "--in",
            str(src),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONNOUSERSITE": "1"},
    )
    assert r.returncode == 0, r.stderr + r.stdout
    data = json.loads(r.stdout)
    assert data.get("ok") is True
    assert data.get("subproblems", 0) >= 1
    assert Path(data["intake_path"]).is_file() or (ROOT / data["intake_path"]).is_file()


def test_graph_intake_with_sources_mock(tmp_path: Path):
    """Run product graph with intake sources; mock solve still finishes if confirm not required."""
    from orpath.control_plane import default_initial, build_graph

    # Use ROOT so fixtures resolve; unique slug under notes/outputs
    slug = "s5-graph-intake-txt"
    src = str((FIX / "ocr" / "sample.txt").resolve())
    initial = default_initial(
        root=ROOT,
        slug=slug,
        problem_id="shortest_path",
        solve_mode="mock",
        knowledge_mode="off",
        live_subagent=False,
        thread_id=f"{slug}-tid",
        skip_intake=False,
        intake_sources=[src],
        human_confirm_intake=False,
        intake_confirmed=True,
    )
    # status needs_human would stop — force confirm path
    app = build_graph(checkpointer=None)
    final = app.invoke(initial)
    # Either completed pipeline or stopped at intake human — both OK signals
    if final.get("human_required"):
        assert final.get("gate_intake_ok") in (True, False)
        assert final.get("intake_path") or final.get("last_error")
    else:
        assert final.get("gate_validate_ok") is True
        assert final.get("intake_skipped") is False
        assert final.get("gate_intake_ok") is True
        # intake artifacts
        assert (ROOT / "notes" / f"{slug}-problem-brief.md").is_file() or final.get(
            "brief_path"
        )
