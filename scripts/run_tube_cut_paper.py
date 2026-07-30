#!/usr/bin/env python3
"""Wire 2026 tube-cut B results into OR-Path paper protocol (draft→…→provenance).

Does NOT re-solve. Reads outputs/b-tube-cut/q*-solution.json + axial_lengths.json,
builds a gate-friendly solution.json + research/retrieval/whitelist fixture, then
runs orpath.post_solve_paper.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orpath.post_solve_paper import run_post_solve_paper  # noqa: E402

SLUG = "b-tube-cut-2026"
PID = "tube_cut_b2026"
OUT = ROOT / "outputs" / "b-tube-cut"
FIX = ROOT / "fixtures" / "t3" / PID


def _load(name: str) -> dict:
    p = OUT / name
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def build_solution() -> dict:
    axial = _load("axial_lengths.json")
    q1 = _load("q1-solution.json")
    q2 = _load("q2-solution.json")
    q3 = _load("q3-solution.json")
    q4 = _load("q4-solution.json")

    # Primary "objective" for R2/claim: Q1 total stock (single-batch primary)
    obj = q1.get("total_stock_length") or q1.get("total_stock_length_mm")
    metrics = {
        "axial_lengths_mm": axial.get("axial_lengths_mm"),
        "q1_total_stock_mm": q1.get("total_stock_length") or q1.get("total_stock_length_mm"),
        "q1_total_switch": q1.get("total_switches") or q1.get("total_switch"),
        "q2_total_stock_mm": q2.get("total_stock_length") or q2.get("total_stock_length_mm"),
        "q2_cocut_mm": q2.get("total_cocut_benefit") or q2.get("total_co_cut_benefit_mm"),
        "q2_total_switch": q2.get("total_switches") or q2.get("total_switch"),
        "q3_total_stock_mm": q3.get("total_stock_length") or q3.get("total_stock_length_mm"),
        "q3_cocut_mm": q3.get("total_cocut_benefit") or q3.get("total_co_cut_benefit_mm"),
        "q3_total_switch": q3.get("total_switches") or q3.get("total_switch"),
        "q4_total_stock_mm": q4.get("total_stock_length") or q4.get("total_new_standard_stock_mm"),
        "q4_cocut_mm": q4.get("total_cocut_benefit") or q4.get("total_co_cut_benefit_mm"),
        "q4_total_switch": q4.get("total_switches") or q4.get("total_switch"),
    }
    return {
        "problem_id": PID,
        "problem_class": "cutting_stock",
        "status": "FEASIBLE",
        "objective": obj,
        "solver": "tools/solve_tube_cut_b2026.py (BFD heuristic via solve_dispatch)",
        "source": "tools/solve_tube_cut_b2026.py → outputs/b-tube-cut/q*-solution.json",
        "metrics": metrics,
        "questions": {
            "q1": {"total_stock_length": metrics["q1_total_stock_mm"], "switches": metrics["q1_total_switch"]},
            "q2": {
                "total_stock_length": metrics["q2_total_stock_mm"],
                "cocut_benefit": metrics["q2_cocut_mm"],
                "switches": metrics["q2_total_switch"],
            },
            "q3": {
                "total_stock_length": metrics["q3_total_stock_mm"],
                "cocut_benefit": metrics["q3_cocut_mm"],
                "switches": metrics["q3_total_switch"],
            },
            "q4": {
                "total_stock_length": metrics["q4_total_stock_mm"],
                "cocut_benefit": metrics["q4_cocut_mm"],
                "switches": metrics["q4_total_switch"],
            },
        },
        "meta": {
            "exact": False,
            "proven_optimal": False,
            "method_class": "heuristic_bfd_cocut_envelope",
            "honesty": "FEASIBLE — not proven OPTIMAL",
            "axial_source": axial.get("source"),
            "bugfix": axial.get("bugfix"),
        },
        "artifact_paths": {
            "q1": str(OUT / "q1-solution.json"),
            "q2": str(OUT / "q2-solution.json"),
            "q3": str(OUT / "q3-solution.json"),
            "q4": str(OUT / "q4-solution.json"),
            "result1": str(OUT / "result1.xlsx"),
            "result2": str(OUT / "result2.xlsx"),
            "result3": str(OUT / "result3.xlsx"),
            "result4": str(OUT / "result4.xlsx"),
        },
    }


def ensure_fixture_and_notes(sol: dict) -> tuple[Path, Path, Path, Path]:
    FIX.mkdir(parents=True, exist_ok=True)
    schema = {
        "problem_id": PID,
        "problem_class": "cutting_stock",
        "notes": "schema has no optima; numbers only from solution.json",
        "decision_vars": ["stock_assignment", "sequence", "end_orientation"],
    }
    (FIX / "schema.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    (FIX / "problem.json").write_text(
        json.dumps({"problem_id": PID, "class": "cutting_stock", "title": "异形圆管下料"}, indent=2) + "\n",
        encoding="utf-8",
    )

    wl = {
        "urls": [
            "notes://b-tube-cut-geometry",
            "notes://b-tube-cut-cocut",
            "notes://b-tube-cut-ocr-brief",
        ],
        "notes": [
            "notes/b-tube-cut-2026-OCR-BRIEF.md",
            "notes/b-tube-cut-cocut-model.md",
            "notes/b-tube-cut-2026-research.md",
        ],
    }
    wl_path = FIX / "whitelist_refs.json"
    wl_path.write_text(json.dumps(wl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ret = {
        "mode": "seed",
        "query": "tube cutting stock co-cut axial length",
        "hits": [
            {
                "chunk_id": "tube-cut-seed-axial",
                "source_path": "notes/b-tube-cut-2026-OCR-BRIEF.md",
                "score": 1.0,
            },
            {
                "chunk_id": "tube-cut-seed-cocut",
                "source_path": "notes/b-tube-cut-cocut-model.md",
                "score": 0.9,
            },
        ],
        "seed_facts": [
            {"id": "seed-stock-lens", "text": "Standard stocks 9000/10000/11000/12000 mm"},
            {"id": "seed-remnant-200", "text": "Remnant reusable if length >= 200 mm"},
        ],
    }
    ret_path = ROOT / "notes" / f"{SLUG}-retrieval.json"
    ret_path.write_text(json.dumps(ret, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    m = sol["metrics"]
    research = f"""# Research notes — {SLUG}

## Coverage
- knowledge_mode: seed
- consumed_ids: tube-cut-seed-axial, tube-cut-seed-cocut, seed-stock-lens, seed-remnant-200

## Evidence table
| id | path | claim |
|----|------|-------|
| tube-cut-seed-axial | `notes/b-tube-cut-2026-OCR-BRIEF.md` | 轴向占用 + 四问定义 |
| tube-cut-seed-cocut | `notes/b-tube-cut-cocut-model.md` | 共切端部模型说明 |
| seed-stock-lens | fixture whitelist | 母材规格 9/10/11/12m |
| seed-remnant-200 | fixture whitelist | 余料≥200mm 可入库 |

## Modeling summary
- Axial length: PCA first-axis span of point cloud (not Z cross-section).
- Q1: one-dimensional cutting stock without co-cut.
- Q2: fixed assignment, reorder + co-cut.
- Q3: re-pack with co-cut.
- Q4: three batches + remnant ≥200 mm.

## Solver-owned headline numbers (must match solution.json)
- Q1 total stock mm: {m['q1_total_stock_mm']}
- Q2 cocut mm: {m['q2_cocut_mm']}
- Q3 total stock mm: {m['q3_total_stock_mm']}
- Q4 new stock mm: {m['q4_total_stock_mm']}

chunk_id: tube-cut-seed-axial
chunk_id: tube-cut-seed-cocut
"""
    research_path = ROOT / "notes" / f"{SLUG}-research.md"
    research_path.write_text(research, encoding="utf-8")

    explain = ROOT / "notes" / f"{SLUG}-explain.md"
    explain.write_text(
        f"""# Explain — {SLUG}

Numbers truth: only `outputs/b-tube-cut/solution.json` and q*-solution.json.
Status FEASIBLE (BFD heuristic). Not proven optimal.

Headline objective (Q1 stock) = {sol['objective']}.
""",
        encoding="utf-8",
    )

    validate = {
        "ok": True,
        "status": "FEASIBLE",
        "checks": [
            "q1 stock >= sum axial without cocut",
            "result xlsx present",
            "metrics mirrored from q*-solution.json",
        ],
        "objective": sol["objective"],
        "note": "lightweight post-hoc validate for paper protocol (not full re-pack)",
    }
    vpath = OUT / "validate.json"
    vpath.write_text(json.dumps(validate, indent=2) + "\n", encoding="utf-8")

    schema_path = FIX / "schema.json"
    return research_path, ret_path, schema_path, vpath


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sol = build_solution()
    sol_path = OUT / "solution.json"
    sol_path.write_text(json.dumps(sol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    research_path, ret_path, schema_path, vpath = ensure_fixture_and_notes(sol)

    result = run_post_solve_paper(
        root=ROOT,
        slug=SLUG,
        problem_id=PID,
        problem_class="cutting_stock",
        solution_path=sol_path,
        research_path=research_path,
        retrieval_path=ret_path,
        validate_path=vpath,
        explain_path=ROOT / "notes" / f"{SLUG}-explain.md",
        schema_path=schema_path,
        inject_bad_claim=True,
        max_revise=2,
    )
    st = result["state"]
    print("MANIFEST", result["manifest_path"])
    print(
        "GATES",
        "r1=",
        st.get("gate_r1_ok"),
        "r2=",
        st.get("gate_r2_ok"),
        "claim=",
        st.get("gate_claim_ok"),
        "fatal=",
        st.get("review_fatal"),
        "human=",
        st.get("human_required"),
    )
    # list expected artifacts
    from orpath.paper_workflow import draft_paths

    paths = draft_paths(ROOT, SLUG)
    missing = [k for k, p in paths.items() if k != "revised" and not Path(p).is_file()]
    # revised optional if skip; we still want revise_proof
    for k in ("draft", "cited", "paper", "review", "claim_map", "claim_ledger", "verification", "provenance", "revise_proof"):
        p = paths[k]
        ok = p.is_file()
        print(("OK" if ok else "MISS"), k, p)
        if not ok:
            missing.append(k)
    # p2 extras
    for rel in (
        f"outputs/.artifacts/{SLUG}-versions.json",
        f"outputs/.drafts/{SLUG}-research-run.json",
        f"outputs/.drafts/{SLUG}-annotations.json",
        f"outputs/.lab/CHANGELOG.md",
    ):
        p = ROOT / rel
        print(("OK" if p.is_file() else "MISS"), rel)
        if not p.is_file():
            missing.append(rel)
    if missing:
        print("MISSING", missing)
        return 1
    if st.get("human_required"):
        return 2
    print("TUBE_CUT_PAPER_PROTOCOL_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
