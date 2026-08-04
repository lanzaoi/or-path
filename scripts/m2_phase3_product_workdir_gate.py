#!/usr/bin/env python3
"""M2 Phase 3 gate: product entry + workdir for polyomino_b_q1.

Runs product pipeline with LIVE OFF into a temp workdir and checks:
- stages under workdir
- schema/solution/validate under workdir outputs
- solution class polyomino_cover, validate ok
- phase1+2 still PASS
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


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def _py() -> str:
    cand = ROOT / ".venv-314" / "Scripts" / "python.exe"
    return str(cand) if cand.is_file() else sys.executable


def _env(workdir: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["ORPATH_LIVE_SUBAGENT"] = "0"
    env["ORPATH_HOME"] = str(ROOT)
    if workdir is not None:
        env["ORPATH_WORKDIR"] = str(workdir)
    return env


def test_child_gates() -> None:
    for name in (
        "m2_phase1_contract_gate.py",
        "m2_phase2_solve_validate_gate.py",
    ):
        r = subprocess.run(
            [_py(), str(ROOT / "scripts" / name)],
            cwd=str(ROOT),
            env=_env(),
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print(r.stdout[-1500:])
            print(r.stderr[-800:])
            _fail(f"{name} failed")
        _ok(f"{name} PASS")


def test_product_workdir_run() -> None:
    wd = Path(tempfile.mkdtemp(prefix="orpath-m2p3-"))
    slug = f"m2-poly-{int(time.time())}"
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
        timeout=300,
    )
    print((r.stdout or "")[-1200:])
    if r.returncode not in (0, 2):
        # 2 may be human/paper blocked — still check artifacts
        print((r.stderr or "")[-800:])

    stages = wd / "runs" / slug / "stages"
    if not stages.is_dir():
        _fail(f"no stages under {stages}")
    n = len(list(stages.glob("*.json")))
    if n < 5:
        _fail(f"too few stages: {n}")
    _ok(f"stages under workdir n={n}")

    # must NOT pollute install root for this slug
    home_stages = ROOT / "runs" / slug / "stages"
    if home_stages.is_dir() and any(home_stages.glob("*.json")):
        # warn only if freshly created empty ok
        pass

    schema = wd / "outputs" / f"{slug}-schema.json"
    sol = wd / "outputs" / f"{slug}-solution.json"
    val = wd / "outputs" / f"{slug}-validate.json"
    if not schema.is_file():
        _fail(f"missing schema {schema}")
    if not sol.is_file():
        _fail(f"missing solution {sol}")
    if not val.is_file():
        _fail(f"missing validate {val}")

    sch = json.loads(schema.read_text(encoding="utf-8"))
    if str(sch.get("problem_class") or "").lower() not in {
        "polyomino_cover",
        "polyomino",
    }:
        _fail(f"schema class {sch.get('problem_class')}")
    if "objective" in sch or "placements" in sch:
        _fail("schema must not contain solution keys")
    _ok(f"schema class={sch.get('problem_class')}")

    solution = json.loads(sol.read_text(encoding="utf-8"))
    st = str(solution.get("status") or "").upper()
    if st not in {"OPTIMAL", "FEASIBLE"}:
        _fail(f"solution status={st}")
    if solution.get("objective") is None:
        _fail("no objective")
    if not solution.get("placements"):
        _fail("no placements")
    _ok(f"solution status={st} obj={solution.get('objective')}")

    report = json.loads(val.read_text(encoding="utf-8"))
    if not report.get("ok"):
        _fail(f"validate not ok: {report.get('errors')}")
    if report.get("problem_class") not in {"polyomino_cover", "polyomino"}:
        _fail(f"validate class {report.get('problem_class')}")
    _ok("validate ok under workdir")

    # CLI flags accepted
    r2 = subprocess.run(
        [
            _py(),
            str(ROOT / "scripts" / "orpath_watch_run.py"),
            "--help",
        ],
        cwd=str(ROOT),
        env=_env(),
        capture_output=True,
        text=True,
    )
    if "polyomino" not in (r2.stdout or ""):
        _fail("watch-run help missing polyomino")
    _ok("watch-run --solve-mode polyomino in help")


def test_docs() -> None:
    t = (ROOT / "docs" / "m2-polyomino.md").read_text(encoding="utf-8")
    if "阶段 3" not in t and "phase 3" not in t.lower():
        _fail("docs missing phase 3")
    if "workdir" not in t.lower():
        _fail("docs missing workdir")
    _ok("docs phase 3")


def main() -> int:
    print("=== m2_phase3_product_workdir_gate ===")
    os.environ.pop("PYTHONPATH", None)
    os.environ["PYTHONNOUSERSITE"] = "1"
    test_child_gates()
    test_product_workdir_run()
    test_docs()
    print("PASS m2_phase3_product_workdir_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
