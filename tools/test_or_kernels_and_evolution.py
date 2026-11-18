#!/usr/bin/env python3
"""Comprehensive tests for universal OR kernels, Deep Evolution Ledger, LNS & domain isolation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

pytestmark = pytest.mark.filterwarnings(
    "ignore:create_react_agent has been moved"
)


def test_interval_coverage_pure_math_and_smoke_physics(tmp_path: Path) -> None:
    from scripts.custom_sandbox_gate import audit_validator_ast
    from tools.or_kernels.interval_coverage import (
        eval_smoke_masking_intervals,
        merge_intervals,
        sample_cylinder_surface,
        union_length,
    )

    merged = merge_intervals([(3.0, 5.0), (1.0, 3.5), (7.0, 7.0), (6.0, 8.0)])
    assert merged == [(1.0, 5.0), (6.0, 8.0)]
    assert union_length(merged) == pytest.approx(6.0, abs=1e-9)

    # Synthetic 3D LOS interception geometry: 2 stationary clouds near target cylinder
    t_grid = np.linspace(0.0, 10.0, 101)
    m_pos = np.column_stack([200.0 - 20.0 * t_grid, np.full_like(t_grid, 200.0), np.full_like(t_grid, 5.0)])
    tgt = sample_cylinder_surface(center_base=(0.0, 200.0, 0.0), radius=7.0, height=10.0, n_theta=8, n_z=3)

    # Cloud 0 covers cylinder center (0, 200, 5) strongly for t in [1, 4], Cloud 1 covers for t in [3, 7]
    smoke_centers = np.zeros((2, t_grid.size, 3), dtype=np.float64)
    smoke_centers[0, :, :] = np.array([15.0, 200.0, 5.0])
    smoke_centers[1, :, :] = np.array([15.0, 200.0, 5.0])
    active = np.zeros((2, t_grid.size), dtype=bool)
    active[0] = (t_grid >= 1.0) & (t_grid <= 4.0)
    active[1] = (t_grid >= 3.0) & (t_grid <= 7.0)

    ivs, dur = eval_smoke_masking_intervals(
        t_grid, m_pos, smoke_centers, active, tgt, cloud_radius=12.0
    )
    assert len(ivs) == 1
    assert 5.8 <= dur <= 6.2

    # Validator importing interval_coverage + doing file read + arithmetic/compare is allowed; importing nlp_minlp or lns_hybrid is banned
    sol_dummy = tmp_path / "dummy.json"
    sol_dummy.write_text("{}", encoding="utf-8")
    v_ok = tmp_path / "ok_val.py"
    v_ok.write_text(
        "import json, sys\nfrom pathlib import Path\n"
        "from tools.or_kernels.interval_coverage import merge_intervals, union_length\n"
        "data = json.loads(Path(sys.argv[1]).read_text())\n"
        "dur = union_length(merge_intervals([(0.0, 2.0), (1.0, 3.0)]))\n"
        "ok = abs(dur - 3.0) < 1e-6\n"
        "sys.exit(0 if ok else 1)\n",
        encoding="utf-8",
    )
    ok_res = audit_validator_ast(v_ok)
    assert ok_res["ok"] is True, ok_res

    v_bad = tmp_path / "bad_val.py"
    v_bad.write_text(
        "from tools.or_kernels.nlp_minlp import solve_box_nlp\n",
        encoding="utf-8",
    )
    bad_res = audit_validator_ast(v_bad)
    assert bad_res["ok"] is False


def test_nlp_minlp_and_lns_hybrid() -> None:
    from tools.or_kernels.lns_hybrid import select_max_union_subset
    from tools.or_kernels.nlp_minlp import solve_box_nlp, solve_minlp_decomposed

    # Constrained quadratic: min (x0 - 2)^2 + (x1 - 2)^2 s.t. x0 + x1 <= 2 (i.e. 2 - x0 - x1 >= 0) -> x=(1,1), f=2
    res_nlp = solve_box_nlp(
        lambda x: float((x[0] - 2.0) ** 2 + (x[1] - 2.0) ** 2),
        bounds=[(0.0, 3.0), (0.0, 3.0)],
        constraints=[lambda x: float(2.0 - x[0] - x[1])],
        maximize=False,
        n_lhs=32,
        global_method="de",
        popsize=8,
        maxiter=30,
        n_local_starts=3,
        time_limit_s=15.0,
        seed=7,
    )
    assert res_nlp["feasible"] is True
    assert res_nlp["proven_optimal"] is False  # non-convex solver never falsely claims proven global opt
    assert res_nlp["objective"] == pytest.approx(2.0, abs=1e-2)

    # Decomposed MINLP over two discrete branches z in [0, 1]
    res_minlp = solve_minlp_decomposed(
        discrete_candidates=[{"branch": 0}, {"branch": 1}],
        build_subproblem_fn=lambda cand: (
            (lambda x, b=cand["branch"]: float((x[0] - (1.0 if b == 0 else 2.5)) ** 2) + (5.0 if b == 0 else 0.2)),
            [(0.0, 4.0)],
            [],
        ),
        maximize=False,
    )
    assert res_minlp["ok"] is True
    assert res_minlp["best_discrete"] == {"branch": 1}
    assert res_minlp["objective"] == pytest.approx(0.2, abs=1e-2)

    # Exact CP-SAT weighted interval union subset
    sub = select_max_union_subset(
        {
            "A": [(0.0, 3.0), (5.0, 8.0)],  # len 6
            "B": [(2.0, 6.0)],              # fills middle only -> A+B gives [0,8]=8
            "C": [(7.0, 10.0)],             # A+C gives [0,3] + [5,10] = 3+5 = 8; Wait: make C [7.0, 11.0] -> 9.0
        },
        max_items=2,
    )
    # Re-test cleanly with C = [(7.0, 11.0)]
    sub = select_max_union_subset(
        {
            "A": [(0.0, 3.0), (5.0, 8.0)],
            "B": [(2.0, 6.0)],
            "C": [(7.0, 11.0)],
        },
        max_items=2,
    )
    assert sub["ok"] is True
    assert sub["proven_optimal"] is True
    assert set(sub["selected"]) == {"A", "C"}
    assert sub["union_length"] == pytest.approx(9.0, abs=1e-3)


def test_evolution_ledger_ratchet_and_fenced_extractor(tmp_path: Path) -> None:
    from orpath.agents.evolution_ledger import (
        best_solution_path,
        best_solver_path,
        extract_and_write_fenced_code,
        format_ledger_summary,
        load_ledger,
        normalize_target_rounds,
        record_experiment,
        round_timeout_budget,
    )

    assert round_timeout_budget(1) == 90
    assert round_timeout_budget(2) == 180
    assert round_timeout_budget(3) == 300
    assert round_timeout_budget(4) == 450
    assert round_timeout_budget(5) == 600
    assert round_timeout_budget(10) == 600
    assert normalize_target_rounds("99") == 10
    assert normalize_target_rounds("bad", default=5) == 5

    slug = "evo-demo"
    (tmp_path / "outputs").mkdir(parents=True, exist_ok=True)
    sol_p = tmp_path / "outputs" / f"{slug}-solution.json"
    solv_p = tmp_path / "outputs" / f"{slug}-custom_solver.py"

    # Good baseline via fenced extractor
    reply_ok = (
        "Here is baseline:\n"
        "```python\n"
        f"# file: outputs/{slug}-custom_solver.py\n"
        "def solve():\n    return 2.0\n"
        "```\n"
    )
    ext1 = extract_and_write_fenced_code(tmp_path, reply_ok)
    assert len(ext1) == 1 and ext1[0]["ok"] is True
    sol_p.write_text(json.dumps({"objective": 2.0, "status": "FEASIBLE"}), encoding="utf-8")

    r1 = record_experiment(
        tmp_path, slug,
        round_idx=1, strategy_stage="R1", hypothesis="baseline",
        timeout_budget_s=90, wall_time_s=1.2, objective=2.0,
        validation_ok=True, minimize=False, target_rounds=5,
        solver_script=solv_p, solution_path=sol_p,
    )
    assert r1["promoted"] is True
    assert best_solver_path(tmp_path, slug).is_file()
    assert best_solution_path(tmp_path, slug).is_file()

    # Broken syntax in R2 must be blocked by AST check and NEVER overwrite valid solver on disk
    reply_bad_syntax = (
        "```python\n"
        f"# file: outputs/{slug}-custom_solver.py\n"
        "def broken(:\n    pass\n"
        "```\n"
    )
    ext2 = extract_and_write_fenced_code(tmp_path, reply_bad_syntax)
    assert len(ext2) == 1 and ext2[0]["ok"] is False
    assert "return 2.0" in solv_p.read_text(encoding="utf-8")

    # Path traversal rejected
    ext_trav = extract_and_write_fenced_code(
        tmp_path, "```python\n# file: ../escape.py\nx=1\n```\n"
    )
    assert ext_trav[0]["ok"] is False

    # Invalid R2 (high fake obj 99.0 but validation_ok=False) must NOT promote incumbent
    sol_p.write_text(json.dumps({"objective": 99.0, "status": "FEASIBLE"}), encoding="utf-8")
    r2 = record_experiment(
        tmp_path, slug,
        round_idx=2, strategy_stage="R2", hypothesis="bad math",
        timeout_budget_s=180, wall_time_s=2.0, objective=99.0,
        validation_ok=False, minimize=False, target_rounds=5,
        solver_script=solv_p, solution_path=sol_p,
    )
    assert r2["promoted"] is False
    assert json.loads(best_solution_path(tmp_path, slug).read_text())["objective"] == 2.0

    # Valid R3 improving objective 2.0 -> 3.5 must promote incumbent
    sol_p.write_text(json.dumps({"objective": 3.5, "status": "FEASIBLE"}), encoding="utf-8")
    r3 = record_experiment(
        tmp_path, slug,
        round_idx=3, strategy_stage="R3", hypothesis="better",
        timeout_budget_s=300, wall_time_s=3.5, objective=3.5,
        validation_ok=True, minimize=False, target_rounds=5,
        solver_script=solv_p, solution_path=sol_p,
    )
    assert r3["promoted"] is True
    assert json.loads(best_solution_path(tmp_path, slug).read_text())["objective"] == 3.5

    md = format_ledger_summary(load_ledger(tmp_path, slug))
    assert "R3" in md and "3.5" in md


def test_knowledge_pack_domain_isolation() -> None:
    from orpath.agents.knowledge_pack import _filter_hits_by_domain

    noisy_hits = [
        {"chunk_id": "cvrp-1", "source_path": "knowledge/cvrp.md", "snippet": "pyvrp cvrp solomon routing"},
        {"chunk_id": "dijk-1", "source_path": "knowledge/sp.md", "snippet": "dijkstra shortest_path"},
        {"chunk_id": "poly-1", "source_path": "knowledge/poly.md", "snippet": "polyomino_cover exact cover"},
    ]
    clean_poly = _filter_hits_by_domain(noisy_hits, "polyomino_cover", ROOT, topk=5)
    cids = [h["chunk_id"] for h in clean_poly]
    assert "cvrp-1" not in cids and "dijk-1" not in cids
    assert "poly-1" in cids

    clean_nlp = _filter_hits_by_domain(noisy_hits[:2], "nlp_minlp", ROOT, topk=5)
    assert all("cvrp" not in h["chunk_id"] and "dijk" not in h["chunk_id"] for h in clean_nlp)
    assert any("nlp-minlp" in str(h.get("source_path") or "") for h in clean_nlp)


def test_polyomino_lns_window_and_hint(tmp_path: Path) -> None:
    from tools.solve_polyomino import solve_cover

    # Cover a 4x4 grid with standard NINE pieces, then pass placements as warm-start hint + LNS window
    pieces = ["I4", "L4", "T4", "S", "Z4", "L3", "I3", "D", "M"]
    res1 = solve_cover(
        rows=4, cols=4,
        piece_ids=pieces,
        reflect=True,
        time_limit_s=5.0, symmetry_break=True,
    )
    assert res1["status"] in {"OPTIMAL", "FEASIBLE"}
    assert len(res1["placements"]) >= 4

    res2 = solve_cover(
        rows=4, cols=4,
        piece_ids=pieces,
        reflect=True,
        time_limit_s=5.0, symmetry_break=True,
        hint_placements=res1["placements"],
        lns_window=3,
    )
    assert res2["status"] in {"OPTIMAL", "FEASIBLE"}
    assert res2["objective"] <= res1["objective"]


class _FakeAgent:
    def __init__(self, fn):
        self.fn = fn
        self.briefs: list[str] = []

    def invoke(self, payload, config=None):
        msgs = list(payload["messages"])
        assert len(msgs) == 1 and isinstance(msgs[0], HumanMessage)
        brief = str(msgs[0].content)
        self.briefs.append(brief)
        return {"messages": [msgs[0], AIMessage(content=self.fn(brief, len(self.briefs)))]}


def test_adaptive_graph_multi_round_evolution_and_early_stop(tmp_path: Path) -> None:
    from orpath.agents.adaptive_graph import build_adaptive_graph
    from orpath.agents.evolution_ledger import load_ledger

    slug = "smoke-evo"
    (tmp_path / "inbox" / slug).mkdir(parents=True, exist_ok=True)
    (tmp_path / "inbox" / slug / "problem.md").write_text(
        "# Smoke Masking Optimization\nMaximize masking interval union duration (s).\n",
        encoding="utf-8",
    )
    (tmp_path / "outputs").mkdir(exist_ok=True)
    (tmp_path / "notes").mkdir(exist_ok=True)
    (tmp_path / "papers").mkdir(exist_ok=True)

    sol_path = tmp_path / "outputs" / f"{slug}-solution.json"
    val_script = tmp_path / "outputs" / f"{slug}-custom-validate.py"
    val_report = tmp_path / "outputs" / f"{slug}-custom-validate.json"
    schema_path = tmp_path / "outputs" / f"{slug}-schema.json"

    def _analyst(_brief, _call_idx):
        return json.dumps({
            "problem_class": "interval_coverage",
            "tier": "B",
            "solve_mode": "auto",
            "rationale": "Interval union maximization",
        })

    def _modeler(_brief, call_idx):
        # Write schema + independent validator (reads solution, computes arithmetic interval length, writes custom-validate.json)
        schema_path.write_text(json.dumps({
            "problem_id": slug,
            "problem_class": "interval_coverage",
            "sense": "maximize",
        }), encoding="utf-8")
        val_script.write_text(
            "import json, sys\nfrom pathlib import Path\n"
            f"sol_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path({repr(str(sol_path))})\n"
            "s = json.loads(sol_file.read_text(encoding='utf-8'))\n"
            "ivs = s.get('intervals') or []\n"
            "recomp = sum(float(b) - float(a) for a, b in ivs)\n"
            "ok = recomp <= 5.0 and abs(recomp - float(s.get('objective') or 0)) < 1e-6\n"
            "rep = {'ok': ok, 'recomputed_objective': recomp}\n"
            f"Path({repr(str(val_report))}).write_text(json.dumps(rep), encoding='utf-8')\n"
            "print(json.dumps(rep))\n"
            "sys.exit(0 if ok else 1)\n",
            encoding="utf-8",
        )
        # Emit fenced custom solver script that writes solution.json + custom-validate.json per round
        if call_idx == 1:
            target_obj, ivs, proven = 1.5, [[0.0, 1.5]], False
        elif call_idx == 2:
            # Simulates invalid physics claim (9.0 > 5.0 -> validator fails, incumbent stays 1.5!)
            target_obj, ivs, proven = 9.0, [[0.0, 9.0]], False
        else:
            # R3 valid improvement + proven_optimal -> must early-stop at R3 (before target_rounds=5)
            target_obj, ivs, proven = 3.2, [[0.0, 3.2]], True
        return (
            "```python\n"
            f"# file: outputs/{slug}-custom_solver.py\n"
            "import json\nfrom pathlib import Path\n"
            f"sol_p = Path({repr(str(sol_path))})\n"
            f"rep_p = Path({repr(str(val_report))})\n"
            f"sol = {{'problem_id': {repr(slug)}, 'slug': {repr(slug)}, 'problem_class': 'interval_coverage', "
            f"'status': {'\"OPTIMAL\"' if proven else '\"FEASIBLE\"'}, 'objective': {target_obj}, "
            f"'intervals': {ivs!r}, "
            f"'validation_report': 'outputs/{slug}-custom-validate.json', "
            f"'proven_optimal': {proven}, 'solver': 'sandbox_evo', 'source': 'smoke'}}\n"
            "sol_p.write_text(json.dumps(sol), encoding='utf-8')\n"
            f"recomp = sum(float(b) - float(a) for a, b in {ivs!r})\n"
            "ok = recomp <= 5.0\n"
            "rep_p.write_text(json.dumps({'ok': ok, 'recomputed_objective': recomp}), encoding='utf-8')\n"
            "```\n"
            f"Round {call_idx} finished."
        )

    def _writer(_brief, _call_idx):
        p = tmp_path / "papers" / f"{slug}.md"
        p.write_text("# 烟幕遮蔽优化论文\n## 1. 问题重述\nOK\n## 2. 符号假设\nOK\n## 3. 模型建立\nOK\n## 4. 算法设计\nOK\n## 5. 结果分析\nOK\n## 6. 优缺点与推广\nOK\n", encoding="utf-8")
        return f"Wrote {p}"

    def _reviewer(_brief, _call_idx):
        return '{"verdict": "PASS", "fatal": [], "major": [], "minor": []}'

    agents = {
        "or_analyst": _FakeAgent(_analyst),
        "or_modeler": _FakeAgent(_modeler),
        "or_writer": _FakeAgent(_writer),
        "or_reviewer": _FakeAgent(_reviewer),
    }
    graph = build_adaptive_graph(agents=agents, max_retries=1)
    out = graph.invoke({
        "slug": slug,
        "workdir": str(tmp_path),
        "skip_paper": True,
        "enforce_anti_cosplay": False,
        "deep_evolution": True,
        "evo_target_rounds": 5,
        "evo_max_rounds": 10,
        "max_retries": 1,
    })
    assert out["validation_ok"] is True
    assert out["evo_round"] == 3  # early-stopped at proven_optimal=True
    assert len(agents["or_modeler"].briefs) == 3
    ledger = load_ledger(tmp_path, slug)
    assert len(ledger["rounds"]) == 3
    assert ledger["incumbent"]["objective"] == pytest.approx(3.2)


def test_watch_snapshot_includes_evolution(tmp_path: Path) -> None:
    from orpath.watch_snapshot import build_snapshot

    slug = "snap-evo"
    (tmp_path / "notes").mkdir(parents=True, exist_ok=True)
    evo_doc = {
        "schema": "orpath.evolution_ledger.v1",
        "slug": slug,
        "minimize": False,
        "target_rounds": 5,
        "max_rounds": 10,
        "incumbent": {"round": 2, "objective": 4.5},
        "rounds": [{"round": 1, "objective": 2.0, "validation_ok": True, "promoted": True}],
    }
    (tmp_path / "notes" / f"{slug}-experiments.json").write_text(json.dumps(evo_doc), encoding="utf-8")
    snap = build_snapshot(slug=slug, thread_id=slug, root=ROOT, workdir=tmp_path)
    assert isinstance(snap.get("evolution"), dict)
    assert snap["evolution"]["incumbent"]["objective"] == 4.5


def test_interval_coverage_kinematics_and_canonical_grid() -> None:
    import numpy as np

    from tools.or_kernels.interval_coverage import canonical_time_grid, eval_projectile_detonation

    tg = canonical_time_grid(t_max=70.0, dt=0.1)
    assert tg.shape == (701,)
    assert float(tg[0]) == 0.0 and float(tg[-1]) == pytest.approx(70.0)

    res = eval_projectile_detonation([17800.0, 0.0, 1800.0], 120.0, [-2.0, 0.0], 1.5, 3.6, g=9.8)
    assert res["det_time"] == pytest.approx(5.1)
    assert np.allclose(res["direction"], [-1.0, 0.0, 0.0])
    assert res["det_point"][0] == pytest.approx(17188.0)
    assert res["det_point"][2] == pytest.approx(1800.0 - 0.5 * 9.8 * (3.6**2))


def test_select_max_union_multi_target_regime_and_cooldown() -> None:
    from tools.or_kernels.lns_hybrid import select_max_union_subset

    # Carrier C1 has two mutually exclusive regimes:
    #   R1: items r1_a (covers T1:[0,4] at t=1.0), r1_b (covers T2:[0,5] at t=1.5 -> violates cooldown=1.0 with r1_a!)
    #   R2: items r2_a (covers T1:[0,3] at t=1.0), r2_b (covers T2:[1,5] at t=2.5 -> valid cooldown!)
    # Carrier C2 has one regime R3: r3_a (covers T1:[3,6], T2:[0,1] at t=4.0)
    target_intervals = {
        "r1_a": {"T1": [(0.0, 4.0)]},
        "r1_b": {"T2": [(0.0, 5.0)]},
        "r2_a": {"T1": [(0.0, 3.0)]},
        "r2_b": {"T2": [(1.0, 5.0)]},
        "r3_a": {"T1": [(3.0, 6.0)], "T2": [(0.0, 1.0)]},
    }
    regime_groups = {
        "C1": {
            "R1": (["r1_a", "r1_b"], 2),
            "R2": (["r2_a", "r2_b"], 2),
        },
        "C2": {
            "R3": (["r3_a"], 1),
        },
    }
    item_times = {
        "r1_a": ("C1", 1.0),
        "r1_b": ("C1", 1.5),
        "r2_a": ("C1", 1.0),
        "r2_b": ("C1", 2.5),
        "r3_a": ("C2", 4.0),
    }
    res = select_max_union_subset(
        target_intervals_by_item=target_intervals,
        regime_groups=regime_groups,
        item_times=item_times,
        min_separation=1.0,
        warm_start=["r2_a", "r2_b", "r3_a"],
    )
    assert res["ok"] is True
    assert res["proven_optimal"] is True
    assert set(res["selected"]) == {"r2_a", "r2_b", "r3_a"}
    assert res["selected_regimes"] == {"C1": "R2", "C2": "R3"}
    # T1: [0,3] U [3,6] = 6.0; T2: [1,5] U [0,1] = 5.0 -> total 11.0
    assert res["union_by_target"]["T1"] == pytest.approx(6.0, abs=1e-3)
    assert res["union_by_target"]["T2"] == pytest.approx(5.0, abs=1e-3)
    assert res["union_length"] == pytest.approx(11.0, abs=1e-3)


def test_milp_reduction_and_multistart_polish(tmp_path: Path) -> None:
    from orpath.agents.tools_or import list_available_solvers
    from scripts.custom_sandbox_gate import audit_validator_ast
    from tools.or_kernels.milp_reduction import (
        solve_assignment_milp,
        solve_budgeted_coverage_milp,
        solve_general_milp,
    )
    from tools.or_kernels.nlp_minlp import solve_multistart_polish

    # 1. General MILP: max 3*x0 + 5*x1 s.t. x0 + 2*x1 <= 4, x0,x1 in {0,1,2}
    gm = solve_general_milp(
        [3.0, 5.0],
        A_ub=[[1.0, 2.0]],
        b_ub=[4.0],
        bounds=[(0.0, 2.0), (0.0, 2.0)],
        integrality=[1, 1],
        maximize=True,
    )
    assert gm["ok"] is True
    assert gm["proven_optimal"] is True
    assert gm["objective"] == pytest.approx(11.0)
    assert gm["x"] == pytest.approx([2.0, 1.0])

    # 2. Budgeted coverage MILP with regime exclusivity
    cov = solve_budgeted_coverage_milp(
        {
            "a1": ["e1", "e2"],
            "a2": ["e3"],
            "b1": ["e1", "e3", "e4"],
        },
        universe_weights={"e1": 2.0, "e2": 2.0, "e3": 3.0, "e4": 1.0},
        regime_groups={"G1": {"R_A": (["a1", "a2"], 2), "R_B": (["b1"], 1)}},
        max_items=2,
    )
    assert cov["ok"] is True
    assert cov["proven_optimal"] is True
    assert set(cov["selected"]) == {"a1", "a2"}  # e1+e2+e3 = 7.0 vs b1 = 6.0
    assert cov["objective"] == pytest.approx(7.0)

    # Min-cost set cover
    sc = solve_budgeted_coverage_milp(
        {"s1": ["e1", "e2"], "s2": ["e2", "e3"], "s3": ["e1", "e2", "e3"]},
        item_costs={"s1": 2.0, "s2": 2.0, "s3": 3.5},
        cover_all=True,
    )
    assert sc["ok"] is True
    assert sc["selected"] == ["s3"]
    assert sc["objective"] == pytest.approx(3.5)

    # 3. Assignment MILP with conflict
    asg = solve_assignment_milp(
        [[1.0, 9.0], [2.0, 3.0]],
        conflicts=[((0, 0), (1, 1))],
    )
    assert asg["ok"] is True
    assert set(asg["assignments"]) == {(0, 1), (1, 0)}
    assert asg["objective"] == pytest.approx(11.0)

    # 4. Stage-3 multistart polish
    pol = solve_multistart_polish(
        lambda x: float((x[0] - 1.5) ** 2 + (x[1] - 0.5) ** 2),
        bounds=[(0.0, 3.0), (0.0, 3.0)],
        initial_points=[[0.8, 0.8]],
        constraints=[lambda x: float(1.5 - x[0] - x[1])],  # x0 + x1 <= 1.5
        maximize=False,
    )
    assert pol["ok"] is True
    assert pol["objective"] == pytest.approx(0.125, abs=1e-3)

    # 5. Validator gate bans milp_reduction, and list_available_solvers advertises or_kernels
    v_bad = tmp_path / "bad_milp_val.py"
    v_bad.write_text("from tools.or_kernels.milp_reduction import solve_general_milp\n", encoding="utf-8")
    assert audit_validator_ast(v_bad)["ok"] is False

    solvers_doc = json.loads(list_available_solvers.invoke({}))
    kernel_mods = [k["module"] for k in solvers_doc.get("or_kernels", [])]
    assert "tools.or_kernels.milp_reduction" in kernel_mods
    assert "tools.or_kernels.lns_hybrid" in kernel_mods


def test_infer_objective_sense_and_sentinel_rejection(tmp_path: Path) -> None:
    from orpath.agents.adaptive_graph import (
        _infer_objective_sense,
        _sanitize_hypothesis,
        parse_review_reply,
        run_deterministic_doc_gate,
    )

    slug = "sense-demo"
    (tmp_path / "notes").mkdir(parents=True, exist_ok=True)
    (tmp_path / "papers").mkdir(parents=True, exist_ok=True)
    analyst_p = tmp_path / "notes" / f"{slug}-analyst.md"
    analyst_p.write_text('{"objective_sense": "max", "Q1": "max len(union)"}\n', encoding="utf-8")

    # 1. Explicit objective_sense in analyst artifact wins for custom_mip
    assert _infer_objective_sense({"problem_class": "custom_mip"}, tmp_path, slug, []) == "max"
    # 2. Classic minimization class still defaults to min when no explicit field overrides
    assert _infer_objective_sense({"problem_class": "shortest_path"}, tmp_path, "other-slug", []) == "min"
    # 3. Statement cues infer max when no analyst/schema sense field exists
    prob_p = tmp_path / "problem.txt"
    prob_p.write_text("使有效遮蔽总时间尽可能长，最大化累计时长（最小间隔 1s）。", encoding="utf-8")
    assert _infer_objective_sense(
        {"problem_class": "custom_mip", "problem_file": str(prob_p)},
        tmp_path,
        "other-slug",
        [],
    ) == "max"

    # 4. LangGraph recursion-limit fallback string is never accepted as PASS or valid paper/hypothesis
    verdict, fatals = parse_review_reply("Sorry, need more steps to process this request.")
    assert verdict == "REVISE" and fatals

    bad_paper = tmp_path / "papers" / f"{slug}.md"
    bad_paper.write_text("Sorry, need more steps to process this request.", encoding="utf-8")
    dg = run_deterministic_doc_gate({"workdir": str(tmp_path), "slug": slug, "paper_path": str(bad_paper)})
    assert dg["doc_gate_ok"] is False

    sol_p = tmp_path / "sol.json"
    sol_p.write_text(json.dumps({"solver": "cpsat_union", "status": "FEASIBLE", "objective": 68.79}), encoding="utf-8")
    hyp = _sanitize_hypothesis("Sorry, need more steps to process this request.", sol_p, round_idx=5)
    assert "sorry" not in hyp.lower() and "68.79" in hyp


def test_render_truth_tables_extracts_custom_subproblem_scalars(tmp_path: Path) -> None:
    from orpath.agents.adaptive_graph import render_truth_tables

    slug = "sub-render"
    (tmp_path / "outputs").mkdir(parents=True, exist_ok=True)
    sol_p = tmp_path / "outputs" / f"{slug}-solution.json"
    sol_p.write_text(
        json.dumps({
            "problem_id": slug,
            "problem_class": "custom_mip",
            "status": "FEASIBLE",
            "objective": 6.0,
            "proven_optimal": False,
            "solver": "custom_test",
            "subproblems": {
                "Q1": {"duration_s": 1.4, "status": "FEASIBLE"},
                "Q2": {"total_duration_s": 4.6, "status": "FEASIBLE"},
            },
        }),
        encoding="utf-8",
    )
    res = render_truth_tables({"workdir": str(tmp_path), "slug": slug, "solution_path": str(sol_p)})
    md = Path(res["tables_path"]).read_text(encoding="utf-8")
    assert "| Q1 | 1.4 | FEASIBLE |" in md
    assert "| Q2 | 4.6 | FEASIBLE |" in md


def test_reviewer_retry_triggers_even_when_stale_review_file_exists(tmp_path: Path) -> None:
    """Pass #2 reviewer hitting recursion limit with stale pass #1 review on disk must trigger reviewer_retry."""
    from orpath.agents.adaptive_graph import build_adaptive_graph

    slug = "rev-stale"
    (tmp_path / "outputs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "papers").mkdir(parents=True, exist_ok=True)
    (tmp_path / "notes").mkdir(parents=True, exist_ok=True)

    sol_p = tmp_path / "outputs" / f"{slug}-solution.json"
    sol_p.write_text(
        json.dumps({"problem_id": "shortest_path", "problem_class": "shortest_path", "status": "OPTIMAL", "objective": 42, "solver": "fake", "path": ["S", "T"]}),
        encoding="utf-8",
    )
    paper_p = tmp_path / "papers" / f"{slug}.md"
    paper_p.write_text(
        "# 摘要\nobjective=42\n## 问题重述与建模假设\n## 数学规划模型建立\n## 求解策略与算子选型\n## 数值计算结果与敏感性分析\n## 模型评价、优缺点与工业落地建议\n",
        encoding="utf-8",
    )
    stale_rev = tmp_path / "papers" / f"{slug}-review.md"
    stale_rev.write_text("## Weaknesses\n- [W1] **FATAL:** old pass1 error\n## Verdict\nREVISE\n", encoding="utf-8")

    rev_calls: list[str] = []

    class _FakeRev:
        def invoke(self, payload, config=None):
            brief = str(payload["messages"][0].content)
            rev_calls.append(brief)
            if len(rev_calls) == 1:
                return {"messages": [payload["messages"][0], AIMessage(content="Sorry, need more steps to process this request.")]}
            return {"messages": [payload["messages"][0], AIMessage(content="## Summary\nFixed.\n## Verdict\nPASS\n")]}

    from langchain_core.messages import AIMessage

    g = build_adaptive_graph(agents={
        "or_analyst": _FakeRev(),
        "or_modeler": _FakeRev(),
        "or_writer": _FakeRev(),
        "or_reviewer": _FakeRev(),
    }, compile_graph=False)
    node_rev = g.nodes["reviewer"].runnable.func
    out = node_rev({
        "slug": slug,
        "workdir": str(tmp_path),
        "paper_path": str(paper_p),
        "validation_ok": True,
        "proven_optimal": True,
    })
    assert len(rev_calls) == 2
    assert "RETRY" in rev_calls[1]
    assert out["review_verdict"] == "PASS"
    assert not out["fatal_defects"]
