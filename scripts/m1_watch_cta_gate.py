#!/usr/bin/env python3
"""M1 Part 4 gate: next_actions CTA (resume/from-stage) on HUMAN/fail.

Pure rules in watch_snapshot — no LLM. HTML must list Copy cmd controls.
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


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def _py() -> str:
    cand = ROOT / ".venv-314" / "Scripts" / "python.exe"
    return str(cand) if cand.is_file() else sys.executable


def test_html() -> None:
    html = (ROOT / "orpath" / "web" / "watch.html").read_text(encoding="utf-8", errors="replace")
    for n in (
        "nextActions",
        "next_actions",
        "renderNextActions",
        "data-m1-next-actions",
        "Copy cmd",
        "auto-resume",
    ):
        if n not in html:
            _fail(f"html missing {n}")
    _ok("HTML next_actions markers")


def test_next_actions_rules() -> None:
    from orpath.paths import apply_workdir
    from orpath.watch_snapshot import (
        _build_next_actions,
        assert_no_llm_imports,
        build_snapshot,
        validate_snapshot_shape,
    )

    assert_no_llm_imports(ROOT / "orpath" / "watch_snapshot.py")
    _ok("no LLM")

    # unit: schema failure
    acts = _build_next_actions(
        slug="s1",
        thread_id="s1",
        workdir=ROOT,
        home=ROOT,
        current={
            "human_required": True,
            "last_error": "FAIL: forbidden key present: path",
            "node": "gate_schema",
            "counters": {"schema_repair": 2, "validate_repair": 0, "solver_tune": 0, "revise_count": 0},
        },
        stages=[],
        status="blocked",
        error={
            "has_error": True,
            "last_error": "FAIL: forbidden key present: path",
            "node": "gate_schema",
            "human_required": True,
        },
    )
    if not acts:
        _fail("schema fail should yield next_actions")
    cmds = " ".join(a["command"] for a in acts)
    if "--from-stage gate_schema" not in cmds and "--from-stage model" not in cmds:
        _fail(f"missing from-stage schema/model: {cmds}")
    if "orpath.bat watch" not in cmds:
        _fail("must include watch CTA")
    if "orpath.bat run --resume" not in cmds:
        _fail("must include resume")
    _ok(f"schema CTAs n={len(acts)}")

    # unit: validate
    acts2 = _build_next_actions(
        slug="s2",
        thread_id="s2",
        workdir=ROOT,
        home=ROOT,
        current={
            "human_required": False,
            "last_error": "unknown class tube_cut",
            "node": "gate_validate",
            "counters": {"schema_repair": 0, "validate_repair": 1, "solver_tune": 0, "revise_count": 0},
        },
        stages=[],
        status="fail",
        error={"has_error": True, "last_error": "unknown class tube_cut", "node": "gate_validate"},
    )
    c2 = " ".join(a["command"] for a in acts2)
    if "--from-stage solve" not in c2 and "--from-stage gate_validate" not in c2:
        _fail(f"validate path missing: {c2}")
    _ok("validate CTAs")

    # unit: workdir flag when != home
    wd = Path(tempfile.mkdtemp(prefix="orpath-m1-cta-wd-"))
    acts3 = _build_next_actions(
        slug="s3",
        thread_id="s3",
        workdir=wd,
        home=ROOT,
        current={"human_required": True, "last_error": "human_required", "node": "human_stop", "counters": {}},
        stages=[],
        status="blocked",
        error={"has_error": True, "last_error": "human_required", "human_required": True},
    )
    c3 = " ".join(a["command"] for a in acts3)
    if "--workdir" not in c3:
        _fail(f"workdir flag missing: {c3}")
    _ok("workdir flag in CTAs")

    # unit: clean ok → empty
    acts4 = _build_next_actions(
        slug="ok",
        thread_id="ok",
        workdir=ROOT,
        home=ROOT,
        current={"human_required": False, "last_error": "", "node": "provenance", "counters": {}},
        stages=[],
        status="ok",
        error={"has_error": False, "last_error": ""},
    )
    if acts4:
        _fail(f"ok status should have no CTAs: {acts4}")
    _ok("clean ok → no CTAs")

    # integration snapshot
    apply_workdir(wd)
    slug = "m1-cta"
    stages = wd / "runs" / slug / "stages"
    stages.mkdir(parents=True, exist_ok=True)
    fail = {
        "utc": "2026-08-03T00:00:00+00:00",
        "node": "gate_schema",
        "stage": "model",
        "thread_id": slug,
        "slug": slug,
        "human_required": True,
        "gate_schema_ok": False,
        "gate_validate_ok": False,
        "solver_tune": 0,
        "schema_repair": 2,
        "validate_repair": 0,
        "revise_count": 0,
        "paths": {},
        "last_error": "schema repair exhausted: FAIL: forbidden key",
    }
    (stages / "0001_gate_schema.json").write_text(json.dumps(fail), encoding="utf-8")
    (wd / "runs" / slug / "latest_snapshot.json").write_text(json.dumps(fail), encoding="utf-8")
    snap = build_snapshot(slug=slug, thread_id=slug, workdir=wd, root=ROOT)
    if validate_snapshot_shape(snap):
        _fail(f"shape {validate_snapshot_shape(snap)}")
    na = snap.get("next_actions") or []
    if not na:
        _fail("snapshot next_actions empty")
    if not (snap.get("error") or {}).get("next_actions"):
        _fail("error.next_actions missing")
    for a in na:
        if not a.get("command") or not a.get("title"):
            _fail(f"bad action {a}")
    _ok(f"snapshot next_actions n={len(na)} first={na[0].get('title')}")


def main() -> int:
    print("=== m1_watch_cta_gate (Part 4) ===")
    os.environ.pop("PYTHONPATH", None)
    os.environ["PYTHONNOUSERSITE"] = "1"
    test_html()
    test_next_actions_rules()
    # Part3 still green
    r = subprocess.run(
        [_py(), str(ROOT / "scripts" / "m1_watch_error_ux_gate.py")],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": "", "PYTHONNOUSERSITE": "1"},
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        _fail("part3 error_ux gate regression")
    _ok("part3 error_ux still PASS")
    print("PASS m1_watch_cta_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
