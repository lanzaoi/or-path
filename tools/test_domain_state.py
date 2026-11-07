"""Plan 1.2 acceptance tests: CorePipelineState contract + 8 KB ceiling."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from orpath.agents.core_state import (
    MAX_CORE_STATE_BYTES,
    CorePipelineState,
    make_initial_core_state,
    sanitize_core_state,
    serialized_state_size_bytes,
)
from orpath.state import (
    ORPathState,
    core_state_to_orpath,
    make_initial_orpath_state,
    orpath_state_to_core,
)

CONTRACT_FIELDS = [
    "slug", "workdir", "problem_id", "problem_class", "domain_cartridge",
    "complexity_tier", "subproblems", "problem_file", "data_files",
    "profile_path", "research_path", "schema_path", "solution_path",
    "validate_path", "paper_path", "review_path", "validation_ok",
    "proven_optimal", "objective_value", "optimality_gap", "fatal_defects",
    "model_retry_count", "paper_retry_count", "max_retries", "last_error",
]


def test_core_pipeline_state_contract_fields():
    annot = CorePipelineState.__annotations__
    assert set(CONTRACT_FIELDS) <= set(annot), set(CONTRACT_FIELDS) - set(annot)
    init = make_initial_core_state(
        slug="t", workdir="/tmp/t", problem_id="p1",
        problem_class="TSP", domain_cartridge="routing", complexity_tier="B",
    )
    for field in CONTRACT_FIELDS:
        assert hasattr(init, "__getitem__")
        _ = init.get(field)


def test_orpath_state_aligned_fields():
    annot = ORPathState.__annotations__
    for field in ("domain_cartridge", "complexity_tier", "profile_path"):
        assert field in annot, field
    initial: ORPathState = make_initial_orpath_state()
    assert initial["domain_cartridge"] == ""
    assert initial["complexity_tier"] == ""
    assert initial["profile_path"] == ""
    json.dumps(initial)  # default init must be JSON-safe for SqliteSaver


def test_bidirectional_projection():
    or_state = make_initial_orpath_state()
    or_state.update({
        "slug": "big-tsp", "problem_id": "tsp-10000", "problem_class": "TSP",
        "domain_cartridge": "routing", "complexity_tier": "B",
        "profile_path": "/tmp/runs/big-tsp/profile.json",
        "solution_path": "/tmp/runs/big-tsp/solution.json",
        "gate_validate_ok": True, "gate_claim_ok": True,
    })
    core = orpath_state_to_core(or_state)
    assert core["slug"] == "big-tsp"
    assert core["domain_cartridge"] == "routing"
    assert core["complexity_tier"] == "B"
    assert core["profile_path"].endswith("profile.json")
    assert core["validation_ok"] is True and core["proven_optimal"] is True

    patch = core_state_to_orpath(core)
    assert patch["domain_cartridge"] == "routing"
    assert patch["complexity_tier"] == "B"
    assert patch["gate_validate_ok"] is True
    assert patch["gate_claim_ok"] is True
    json.dumps(patch)


def test_huge_problem_pointer_handoff_stays_under_8kb():
    """10k-node / 500 KB solution file lifecycle: pointers only, < 8 KB."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # 500 KB solution file + 10k-node coordinate dump on disk
        huge_solution = td / "solution.json"
        huge_solution.write_text(json.dumps({
            "tour": list(range(10_000)),
            "objective": 1234567.89,
            "raw": "x" * 500_000,
        }), encoding="utf-8")
        assert huge_solution.stat().st_size > 500_000

        # malicious state: raw problem text + giant arrays smuggled in
        dirty = make_initial_core_state(
            slug="huge-tsp", workdir=td.as_posix(), problem_id="tsp-10000",
            problem_class="TSP", domain_cartridge="routing", complexity_tier="C",
        )
        dirty["problem_file"] = td.as_posix() + "/problem.json"
        dirty["solution_path"] = huge_solution.as_posix()
        dirty["data_files"] = [f"{td}/nodes_{i}.csv" for i in range(10_000)]
        dirty["problem_text"] = "raw problem " * 50_000      # 600 KB payload
        dirty["solution"] = list(range(10_000))              # giant array
        dirty["last_error"] = "boom" * 10_000                # oversized string

        clean = sanitize_core_state(dirty)
        size = serialized_state_size_bytes(clean)
        assert size < MAX_CORE_STATE_BYTES, f"state is {size} bytes"

        # lifecycle: analyst -> modeler -> writer -> reviewer handoffs
        for stage, extra in (
            ("analyst", {"profile_path": f"{td}/profile.json",
                         "research_path": f"{td}/research.md"}),
            ("modeler", {"schema_path": f"{td}/schema.json",
                         "data_files": [f"{td}/nodes.csv"]}),
            ("writer", {"paper_path": f"{td}/paper.md"}),
            ("reviewer", {"review_path": f"{td}/review.json",
                          "validation_ok": True, "proven_optimal": False,
                          "objective_value": 1234567.89,
                          "optimality_gap": 0.37, "fatal_defects": []}),
        ):
            handoff = sanitize_core_state({**clean, **extra})
            ser = json.dumps(handoff, ensure_ascii=False, separators=(",", ":"))
            assert len(ser.encode("utf-8")) < MAX_CORE_STATE_BYTES
            # SqliteSaver stores exactly this shape of JSON blob
            assert json.loads(ser)["slug"] == "huge-tsp"

        # SqliteSaver-compatible persistence round-trip (JSON blob in sqlite)
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE checkpoints (id TEXT, blob TEXT)")
        blob = json.dumps(clean, ensure_ascii=False)
        conn.execute("INSERT INTO checkpoints VALUES (?, ?)", ("cp1", blob))
        (_, stored) = conn.execute("SELECT id, blob FROM checkpoints WHERE id='cp1'").fetchone()
        conn.close()
        restored = json.loads(stored)
        assert "problem_text" not in restored and "solution" not in restored
        assert restored["solution_path"].endswith("solution.json")
        assert restored["slug"] == "huge-tsp"
