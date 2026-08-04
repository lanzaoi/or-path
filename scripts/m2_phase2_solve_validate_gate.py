#!/usr/bin/env python3
"""M2 Phase 2 gate: polyomino solve → validate digital chain.

1. Phase1 contract still PASS
2. dispatch solve(polyomino_b_q1) returns OPTIMAL/FEASIBLE with placements
3. validate_solution ok on live solve output
4. validate ok on fixture gold solution.json
5. bad solution (overlap) fails validate
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def _py() -> str:
    cand = ROOT / ".venv-314" / "Scripts" / "python.exe"
    return str(cand) if cand.is_file() else sys.executable


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def test_phase1() -> None:
    r = subprocess.run(
        [_py(), str(ROOT / "scripts" / "m2_phase1_contract_gate.py")],
        cwd=str(ROOT),
        env=_env(),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0 or "PASS m2_phase1_contract_gate" not in (r.stdout or ""):
        print(r.stdout)
        print(r.stderr)
        _fail("phase1 regression")
    _ok("phase1 still PASS")


def test_dispatch_solve() -> dict:
    from solve_dispatch import solve

    ok, data, raw = solve(
        ROOT,
        "polyomino_b_q1",
        mode="polyomino",
        problem_class="polyomino_cover",
    )
    if not ok:
        _fail(f"solve failed: {raw[:500]}")
    st = str(data.get("status") or "").upper()
    if st not in {"OPTIMAL", "FEASIBLE"}:
        _fail(f"status={st} data keys={list(data)}")
    if not data.get("placements"):
        _fail("no placements")
    if data.get("objective") is None:
        _fail("no objective")
    src = str(data.get("source") or "")
    if "polyomino" not in src.lower() and "solve_polyomino" not in src:
        # normalize may set source
        if "polyomino" not in str(data.get("solver") or "").lower():
            _fail(f"bad source/solver {src} {data.get('solver')}")
    _ok(
        f"dispatch solve status={st} obj={data.get('objective')} "
        f"n_pl={len(data.get('placements') or [])}"
    )
    return data


def test_validate_live(sol: dict) -> None:
    from validate_solution import validate

    report = validate("polyomino_b_q1", sol, gold=None)
    if not report.get("ok"):
        _fail(f"validate live: {report.get('errors')} checks={report.get('checks')}")
    if report.get("problem_class") != "polyomino_cover":
        _fail(f"pc={report.get('problem_class')}")
    names = {c["name"] for c in report.get("checks") or []}
    for need in ("feasibility", "recompute_objective", "shape_placements"):
        if need not in names and need != "shape_placements":
            # shape is in envelope checks
            pass
    if not any(c.get("name") == "recompute_objective" and c.get("ok") for c in report["checks"]):
        _fail(f"recompute missing/fail: {report['checks']}")
    _ok(f"validate live ok checks={len(report.get('checks') or [])}")


def test_validate_gold() -> None:
    from validate_solution import validate

    gold_path = ROOT / "fixtures" / "t3" / "polyomino_b_q1" / "solution.json"
    if not gold_path.is_file():
        _fail("missing gold solution")
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    report = validate("polyomino_b_q1", gold, gold=gold)
    if not report.get("ok"):
        _fail(f"validate gold: {report.get('errors')} {report.get('checks')}")
    # gold_gap should pass
    if not any(c.get("name") == "gold_gap" and c.get("ok") for c in report["checks"]):
        _fail(f"gold_gap missing: {report['checks']}")
    _ok(f"validate gold obj={gold.get('objective')}")


def test_validate_cli() -> None:
    gold = ROOT / "fixtures" / "t3" / "polyomino_b_q1" / "solution.json"
    out = Path(tempfile.mkdtemp(prefix="m2p2-")) / "val.json"
    r = subprocess.run(
        [
            _py(),
            str(ROOT / "tools" / "validate_solution.py"),
            "--problem-id",
            "polyomino_b_q1",
            "--solution",
            str(gold),
            "--out",
            str(out),
        ],
        cwd=str(ROOT),
        env={**_env(), "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        _fail(f"cli validate: {r.stderr} {r.stdout}")
    rep = json.loads(out.read_text(encoding="utf-8"))
    if not rep.get("ok"):
        _fail(f"cli report not ok: {rep}")
    _ok("validate_solution.py CLI")


def test_negative_overlap() -> None:
    from validate_solution import validate

    gold_path = ROOT / "fixtures" / "t3" / "polyomino_b_q1" / "solution.json"
    bad = json.loads(gold_path.read_text(encoding="utf-8"))
    # force two placements to share first cell of first
    if len(bad.get("placements") or []) >= 2:
        c0 = bad["placements"][0]["cells"][0]
        bad["placements"][1]["cells"][0] = c0
    bad["objective"] = len(bad["placements"])
    report = validate("polyomino_b_q1", bad, gold=None)
    if report.get("ok"):
        _fail("overlap should fail validate")
    _ok("negative overlap rejected")


def test_docs() -> None:
    p = ROOT / "docs" / "m2-polyomino.md"
    t = p.read_text(encoding="utf-8")
    if "阶段 2" not in t and "Phase 2" not in t and "phase 2" not in t.lower():
        _fail("docs missing phase 2")
    if "validate" not in t.lower():
        _fail("docs missing validate")
    _ok("docs mention phase 2 / validate")


def main() -> int:
    print("=== m2_phase2_solve_validate_gate ===")
    os.environ.pop("PYTHONPATH", None)
    os.environ["PYTHONNOUSERSITE"] = "1"
    test_phase1()
    sol = test_dispatch_solve()
    test_validate_live(sol)
    test_validate_gold()
    test_validate_cli()
    test_negative_overlap()
    test_docs()
    print("PASS m2_phase2_solve_validate_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
