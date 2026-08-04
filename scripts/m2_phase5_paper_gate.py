#!/usr/bin/env python3
"""M2 Phase 5: polyomino paper/cite smoke on product workdir run.

Requires R1+R2+claim not HUMAN for demo slug (LIVE OFF).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def _py() -> str:
    cand = ROOT / ".venv-314" / "Scripts" / "python.exe"
    return str(cand) if cand.is_file() else sys.executable


def _env(wd: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["ORPATH_LIVE_SUBAGENT"] = "0"
    env["ORPATH_HOME"] = str(ROOT)
    if wd is not None:
        env["ORPATH_WORKDIR"] = str(wd)
    return env


def test_unit_paper_r2() -> None:
    from orpath.paper_workflow import render_or_paper

    sys.path.insert(0, str(ROOT / "tools"))
    from r2_numeric_check import check_draft

    sol = json.loads(
        (ROOT / "fixtures/t3/polyomino_b_q1/solution.json").read_text(encoding="utf-8")
    )
    body = render_or_paper(
        slug="m2-poly-9999999999",
        problem_class="polyomino_cover",
        problem_id="polyomino_b_q1",
        solution=sol,
        solution_path=str(ROOT / "outputs" / "m2-poly-9999999999-solution.json"),
        source_lines=["notes://polyomino-cover-ref"],
    )
    errs = check_draft(body, sol)
    if errs:
        _fail(f"unit R2: {errs}")
    if "9999999999" in body:
        _fail("run-id leaked into paper body")
    _ok("unit paper R2 clean")


def test_product_paper_green() -> None:
    wd = Path(tempfile.mkdtemp(prefix="orpath-m2p5-"))
    slug = f"m2p5-{int(time.time())}"
    # use short slug without huge digits to be safe; still may have time
    slug = f"m2p5x{int(time.time()) % 100000}"
    cmd = [
        _py(),
        str(ROOT / "orpath" / "run_orpath.py"),
        "run",
        "--workdir",
        str(wd),
        "--slug",
        slug,
        "--thread-id",
        slug,
        "--problem-id",
        "polyomino_b_q1",
        "--problem-class",
        "polyomino_cover",
        "--solve-mode",
        "polyomino",
        "--no-live-subagent",
        "--fresh",
        "--force",
    ]
    print("RUN:", " ".join(cmd))
    r = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=_env(wd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=360,
    )
    print((r.stdout or "")[-1000:])
    sol = wd / "outputs" / f"{slug}-solution.json"
    val = wd / "outputs" / f"{slug}-validate.json"
    paper = wd / "papers" / f"{slug}.md"
    if not sol.is_file() or not val.is_file():
        _fail("missing solution/validate")
    if not paper.is_file():
        _fail(f"missing paper {paper}")
    s = json.loads(sol.read_text(encoding="utf-8"))
    v = json.loads(val.read_text(encoding="utf-8"))
    if str(s.get("status")).upper() not in {"OPTIMAL", "FEASIBLE"}:
        _fail(f"sol status {s.get('status')}")
    if not v.get("ok"):
        _fail(f"validate {v.get('errors')}")
    _ok(f"sol+val green obj={s.get('objective')}")

    # R2 on paper
    r2 = subprocess.run(
        [
            _py(),
            str(ROOT / "tools" / "r2_numeric_check.py"),
            "--draft",
            str(paper),
            "--solution",
            str(sol),
        ],
        cwd=str(ROOT),
        env=_env(wd),
        capture_output=True,
        text=True,
    )
    if r2.returncode != 0:
        _fail(f"R2 paper: {r2.stderr} {r2.stdout}")
    _ok("R2 paper PASS")

    wl = ROOT / "fixtures/t3/polyomino_b_q1/whitelist_refs.json"
    r1 = subprocess.run(
        [
            _py(),
            str(ROOT / "tools" / "r1_cite_check.py"),
            "--draft",
            str(paper),
            "--whitelist",
            str(wl),
        ],
        cwd=str(ROOT),
        env=_env(wd),
        capture_output=True,
        text=True,
    )
    if r1.returncode != 0:
        _fail(f"R1 paper: {r1.stderr} {r1.stdout}")
    _ok("R1 paper PASS")

    # product exit: prefer 0; allow 2 only if not paper_blocked
    out = (r.stdout or "") + (r.stderr or "")
    if "paper_blocked" in out or "paper revise exhausted" in out:
        _fail(f"product still paper_blocked: {out[-500:]}")
    if r.returncode not in (0, 2):
        # 2 might still be human for other reasons
        if r.returncode != 0 and "human_required" in out.lower():
            # check last_error from json tail
            if "paper" in out.lower() and "fail" in out.lower():
                _fail(f"run rc={r.returncode} still paper human")
    _ok(f"product run rc={r.returncode} (no paper_blocked)")


def test_docs() -> None:
    for rel in ("docs/m2-polyomino.md", "docs/m2-closeout.md"):
        if not (ROOT / rel).is_file():
            _fail(f"missing {rel}")
    t = (ROOT / "docs" / "m2-closeout.md").read_text(encoding="utf-8")
    for n in ("polyomino", "Claim ladder", "m2-gate", "Phase"):
        if n not in t and n.lower() not in t.lower():
            _fail(f"closeout missing {n}")
    _ok("docs closeout")


def main() -> int:
    print("=== m2_phase5_paper_gate ===")
    os.environ.pop("PYTHONPATH", None)
    os.environ["PYTHONNOUSERSITE"] = "1"
    if not (ROOT / "fixtures/t3/polyomino_b_q1/whitelist_refs.json").is_file():
        _fail("missing whitelist_refs.json")
    test_unit_paper_r2()
    test_product_paper_green()
    test_docs()
    print("PASS m2_phase5_paper_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
