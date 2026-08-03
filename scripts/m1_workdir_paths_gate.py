#!/usr/bin/env python3
"""M1 Part 1 gate: workdir path contract (no full product run).

Checks:
1. paths helpers: apply_workdir / layout / home≠workdir isolation
2. build_snapshot reads stages only from given workdir (no install bleed)
3. fixture_search_roots includes install home when root is empty workdir
4. tools resolve from install when workdir has no tools/
5. run_orpath exposes --workdir
6. inventory of known artifact writers (documentation assert)
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


def test_paths_contract() -> Path:
    from orpath.paths import (
        ARTIFACT_DIR_RELS,
        apply_workdir,
        fixture_search_roots,
        orpath_home,
        orpath_workdir,
        resolve_tools_dir,
    )

    home = orpath_home()
    if home != ROOT.resolve() and not (home / "orpath").is_dir():
        _fail(f"orpath_home unexpected: {home}")
    _ok(f"orpath_home={home}")

    td = Path(tempfile.mkdtemp(prefix="orpath-m1-wd-"))
    # clear env bleed
    old = os.environ.get("ORPATH_WORKDIR")
    try:
        os.environ.pop("ORPATH_WORKDIR", None)
        wd = apply_workdir(td)
        if wd != td.resolve():
            _fail(f"apply_workdir resolve {wd} != {td.resolve()}")
        if os.environ.get("ORPATH_WORKDIR") != str(wd):
            _fail("ORPATH_WORKDIR not set by apply_workdir")
        for rel in ARTIFACT_DIR_RELS:
            if not (wd / rel).is_dir():
                _fail(f"missing layout {rel}")
        _ok(f"layout under {wd}")

        if orpath_workdir() != wd:
            _fail("orpath_workdir after apply != applied")
        roots = fixture_search_roots(wd)
        if home.resolve() not in roots:
            _fail(f"fixture_search_roots missing home: {roots}")
        _ok(f"fixture_search_roots={roots}")

        tools = resolve_tools_dir(wd)
        if not (tools / "gate_schema.py").is_file():
            _fail(f"resolve_tools_dir bad: {tools}")
        if tools == wd / "tools":
            _fail("tools should not be empty workdir/tools")
        _ok(f"tools_dir={tools}")
    finally:
        if old is None:
            os.environ.pop("ORPATH_WORKDIR", None)
        else:
            os.environ["ORPATH_WORKDIR"] = old
    return td


def test_snapshot_isolation(wd: Path) -> None:
    from orpath.watch_snapshot import build_snapshot, validate_snapshot_shape

    slug = "m1-iso-a"
    stages = wd / "runs" / slug / "stages"
    stages.mkdir(parents=True, exist_ok=True)
    (stages / "0001_orchestrate.json").write_text(
        json.dumps(
            {
                "utc": "2026-08-03T00:00:00+00:00",
                "node": "orchestrate",
                "stage": "orchestrate",
                "thread_id": slug,
                "slug": slug,
                "human_required": False,
                "gate_schema_ok": False,
                "gate_validate_ok": False,
                "solver_tune": 0,
                "schema_repair": 0,
                "validate_repair": 0,
                "revise_count": 0,
                "paths": {},
                "last_error": "",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (wd / "runs" / slug / "latest_snapshot.json").write_text(
        (stages / "0001_orchestrate.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    # Poison install-root with same slug stages that must NOT be preferred
    # when workdir is explicit (we only pass workdir=wd).
    snap = build_snapshot(slug=slug, thread_id=slug, workdir=wd, root=ROOT)
    errs = validate_snapshot_shape(snap)
    if errs:
        _fail(f"shape: {errs}")
    if not snap.get("stages"):
        _fail("expected stages from temp workdir")
    if Path(snap.get("workdir") or "").resolve() != wd.resolve():
        _fail(f"snap.workdir {snap.get('workdir')} != {wd}")
    if Path(snap.get("home") or "").resolve() != ROOT.resolve():
        # home may equal install
        if "orpath" not in str(snap.get("home")):
            _fail(f"snap.home odd: {snap.get('home')}")
    if snap["status"] == "no_product_run":
        _fail("should not be no_product_run")
    _ok(f"snapshot isolation stages={len(snap['stages'])} workdir={snap.get('workdir')}")

    # Empty other workdir must not see stages
    wd2 = Path(tempfile.mkdtemp(prefix="orpath-m1-wd2-"))
    from orpath.paths import ensure_workdir_layout

    ensure_workdir_layout(wd2)
    snap2 = build_snapshot(slug=slug, thread_id=slug, workdir=wd2, root=ROOT)
    if snap2.get("stages"):
        _fail("other workdir must not see stages")
    if snap2["status"] != "no_product_run":
        _fail(f"expected no_product_run got {snap2['status']}")
    _ok("negative workdir isolation")


def test_run_orpath_cli_flag() -> None:
    r = subprocess.run(
        [_py(), str(ROOT / "orpath" / "run_orpath.py"), "run", "-h"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "", "PYTHONNOUSERSITE": "1"},
    )
    help_t = (r.stdout or "") + (r.stderr or "")
    if "--workdir" not in help_t:
        _fail("run_orpath missing --workdir in help")
    _ok("run_orpath --workdir in help")


def test_writer_inventory() -> None:
    """Sanity: known modules that touch outputs/runs still exist (checklist)."""
    required = [
        ROOT / "orpath" / "nodes.py",
        ROOT / "orpath" / "run_orpath.py",
        ROOT / "orpath" / "watch_snapshot.py",
        ROOT / "orpath" / "paths.py",
        ROOT / "scripts" / "orpath_watch_run.py",
        ROOT / "orpath" / "gates.py",
        ROOT / "tools" / "solve_dispatch.py",
    ]
    for p in required:
        if not p.is_file():
            _fail(f"missing writer inventory path {p}")
    # nodes uses state root for artifacts; fixtures via fixture_search_roots
    nodes = (ROOT / "orpath" / "nodes.py").read_text(encoding="utf-8")
    if "fixture_search_roots" not in nodes:
        _fail("nodes._fixture_base should use fixture_search_roots")
    gates = (ROOT / "orpath" / "gates.py").read_text(encoding="utf-8")
    if "tools_dir" not in gates and "resolve_tools_dir" not in gates:
        _fail("gates should resolve tools via tools_dir helper")
    sd = (ROOT / "tools" / "solve_dispatch.py").read_text(encoding="utf-8")
    if "Path(__file__).resolve().parent" not in sd:
        _fail("solve_dispatch should resolve tools next to __file__")
    _ok("writer inventory + fixture/tools home split markers")


def main() -> int:
    print("=== m1_workdir_paths_gate (Part 1) ===")
    print("ROOT =", ROOT)
    # avoid host pollution
    os.environ.pop("PYTHONPATH", None)
    os.environ["PYTHONNOUSERSITE"] = "1"

    wd = test_paths_contract()
    test_snapshot_isolation(wd)
    test_run_orpath_cli_flag()
    test_writer_inventory()

    # regression: watch_snapshot still no LLM
    from orpath.watch_snapshot import assert_no_llm_imports

    assert_no_llm_imports(ROOT / "orpath" / "watch_snapshot.py")
    _ok("watch_snapshot no LLM")

    print("PASS m1_workdir_paths_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
