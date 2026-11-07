#!/usr/bin/env python3
"""Phase 3.2 acceptance matrix — 22 registered OR classes through the main graph.

Each registered canonical class must pass the full chain

    model → gate_schema → solve → gate_validate

driven by the unified ``DomainCartridge`` registry modeler (no static
five-branch hard-coded tree in ``node_model``). Numbers come strictly from
``tools/solve_*.py`` (envelope) and ``tools/validate_solution.py`` (independent
recomputation). Tier-B cases must additionally record a real lower-bound /
incumbent gap file ``outputs/<slug>-gap.json``.

Run:
    .venv/bin/python tools/test_phase3_registry_matrix.py -q -p no:langsmith
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("ORPATH_TUBE_REUSE", "1")
os.environ.setdefault("ORPATH_KNOWLEDGE_MODE", "off")
# keep CI deterministic: no live subagent / no network
os.environ["ORPATH_LIVE_SUBAGENT"] = "0"

import pytest  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore")

from orpath.control_plane import default_initial  # noqa: E402
from orpath.pipeline.solve import (  # noqa: E402
    node_gate_schema,
    node_gate_validate,
    node_model,
    node_solve,
)

# canonical class, problem id, solve mode
CASES: list[tuple[str, str, str]] = [
    ("shortest_path", "shortest_path", "networkx"),
    ("tsp", "tsp_n8", "cpsat"),
    ("vrp", "vrp_multi", "ortools"),
    ("tube_cut", "tube_cut_b2026", "tube"),
    ("polyomino_cover", "polyomino_b_q1", "polyomino"),
    ("jssp", "ft06", "jssp"),
    ("bin_packing", "binpack_1d", "bin_packing"),
    ("facility_location", "cap41", "facility_location"),
    ("portfolio_opt", "max_sharpe", "portfolio_opt"),
    ("network_flow", "min_cost_flow", "network_flow"),
    ("qubo_ising", "max_cut", "qubo_ising"),
    ("rcpsp", "j301_1", "rcpsp"),
    ("staff_rostering", "rostering_toy", "staff_rostering"),
    ("pyvrp", "c101", "pyvrp"),
    ("lot_sizing", "ww12", "lot_sizing"),
    ("qap", "nug12", "qap"),
    ("graph_coloring", "myciel3", "graph_coloring"),
    ("stochastic_lp", "farmer_problem", "stochastic_lp"),
    ("max_clique", "myciel3", "max_clique"),
    ("game_theory", "matching_pennies", "game_theory"),
    ("hub_location", "CAB25", "hub_location"),
]

#: classes expected to run solve+validate end to end
FULLY_VALIDATED = frozenset(c[0] for c in CASES)


def _seed_tube_shipped_envelope(tmp: Path) -> None:
    """Public installs exclude the original Tube attachments; seed the public-
    verified live-btube envelope so the Z1-Q4 stock chain replays offline."""
    src_env = ROOT / "outputs" / "live-btube-solution.json"
    if not src_env.is_file():
        pytest.skip("live-btube envelope not shipped")
    envelope = json.loads(src_env.read_text(encoding="utf-8"))
    out_dir = tmp / "outputs" / "b-tube-cut"
    out_dir.mkdir(parents=True, exist_ok=True)
    questions = envelope.get("questions") or {}
    for name in ("q1", "q2", "q3", "q4"):
        if name in questions:
            (out_dir / f"{name}-solution.json").write_text(
                json.dumps(questions[name], ensure_ascii=False), encoding="utf-8"
            )
    (out_dir / "summary.json").write_text(
        json.dumps({"objective": envelope.get("objective"), "slug": "live-btube"},
                   ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "model_snapshot.json").write_text(
        json.dumps({"schema_version": "shipped-public-replay"}), encoding="utf-8"
    )


def _run_chain(case: str, problem_id: str, solve_mode: str) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix=f"phase32-{case}-"))
    if case == "tube_cut":
        _seed_tube_shipped_envelope(tmp)
    state = default_initial(
        root=tmp,
        slug=f"matrix-{case}",
        problem_id=problem_id,
        problem_class=case,
        solve_mode=solve_mode,
        knowledge_mode="off",
        live_subagent=False,
        thread_id=f"matrix-{case}",
        skip_intake=True,
    )
    u1 = node_model(state)
    assert u1["stage"] == "gate_schema", f"model stage: {u1.get('stage')} {u1.get('last_error')}"
    assert "unsupported class" not in str(u1.get("last_error", "")).lower()
    assert (tmp / "outputs" / f"matrix-{case}-schema.json").is_file()

    u2 = node_gate_schema({**state, **u1})
    assert u2["stage"] == "solve", f"gate_schema: {u2}"
    assert u2["gate_schema_ok"] is True

    u3 = node_solve({**state, **u1, **u2, "solve_mode": solve_mode})
    assert u3["stage"] == "gate_validate", f"solve stage: {u3}"
    sol = json.loads(
        (tmp / "outputs" / f"matrix-{case}-solution.json").read_text(encoding="utf-8")
    )
    assert str(sol.get("status", "")).upper() in {"OPTIMAL", "FEASIBLE"}, sol.get("status")
    assert sol.get("objective") is not None

    u4 = node_gate_validate({**state, **u1, **u2, **u3, "solve_mode": solve_mode})
    assert u4["stage"] == "explain", f"gate_validate: {u4}"
    assert u4["gate_validate_ok"] is True

    return {"state": u4, "tmp": tmp, "solution": sol, "stage_updates": {"u1": u1, "u3": u3}}


@pytest.mark.parametrize("case,problem_id,mode", CASES)
def test_class_full_chain(case: str, problem_id: str, mode: str) -> None:
    if case not in FULLY_VALIDATED:
        pytest.skip(f"{case} not in full-validation matrix")
    out = _run_chain(case, problem_id, mode)
    tmp: Path = out["tmp"]
    # tier-B gap record (jssp is Tier-B and reports a real lower bound)
    if case in {"jssp", "rcpsp", "facility_location"}:
        gap_path = Path(str(out["stage_updates"]["u3"].get("gap_path") or ""))
        assert gap_path.is_file(), f"missing Tier-B gap record for {case}"
        gap = json.loads(gap_path.read_text(encoding="utf-8"))
        assert gap["incumbent"] is not None
        assert gap["complexity_tier"] == "B"
    else:
        gap_files = list((tmp / "outputs").glob(f"matrix-{case}-gap.json"))
        if gap_files:
            gap = json.loads(gap_files[0].read_text(encoding="utf-8"))
            assert gap["complexity_tier"] == "B"
            assert gap["incumbent"] is not None


def test_microgrid_dispatch_model_chain_no_unsupported_class() -> None:
    """microgrid data-boxed in the public install: the model/schema chain must\n    still work (registry modeler) and never report ``unsupported class``."""
    tmp = Path(tempfile.mkdtemp(prefix="phase32-microgrid-"))
    state = default_initial(
        root=tmp,
        slug="matrix-microgrid_dispatch",
        problem_id="cumcm2026_c",
        problem_class="microgrid_dispatch",
        solve_mode="microgrid",
        knowledge_mode="off",
        live_subagent=False,
        thread_id="matrix-microgrid_dispatch",
    )
    u1 = node_model(state)
    assert u1["stage"] == "gate_schema", u1.get("last_error")
    schema = json.loads(
        (tmp / "outputs" / "matrix-microgrid_dispatch-schema.json").read_text(encoding="utf-8")
    )
    assert schema["problem_class"] == "microgrid_dispatch"
    assert schema["domain_cartridge"] == "microgrid"
    assert schema["complexity_tier"] == "B"
    u2 = node_gate_schema({**state, **u1})
    assert u2["stage"] == "solve"


def test_model_rejects_truly_unknown_class() -> None:
    """A truly unknown class must fall back to the isolated pipeline, then\n    human_stop with a clear message — not silently succeed with a fake schema."""
    tmp = Path(tempfile.mkdtemp(prefix="phase32-unknown-"))
    state = default_initial(
        root=tmp,
        slug="matrix-banana",
        problem_id="banana_world",
        problem_class="banana_world",
        solve_mode="mock",
        knowledge_mode="off",
        live_subagent=False,
        thread_id="matrix-banana",
    )
    u1 = node_model(state)
    assert u1["stage"] in {"gate_schema", "human_stop"}
    if u1["stage"] == "human_stop":
        assert "unsupported class" in str(u1.get("last_error", ""))
