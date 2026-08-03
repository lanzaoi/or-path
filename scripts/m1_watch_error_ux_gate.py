#!/usr/bin/env python3
"""M1 Part 3 gate: Watch error UX (banner + copy + stage highlight).

Static checks on watch.html + snapshot.error block on synthetic stages.
Does not require a browser clipboard or LIVE Pi.
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


def test_html_markers() -> None:
    html = (ROOT / "orpath" / "web" / "watch.html").read_text(encoding="utf-8", errors="replace")
    for n in (
        "errBanner",
        "errCopy",
        "errJump",
        "errText",
        "errMeta",
        "Copy error",
        "Jump stage",
        "stageDetail",
        "has-err",
        "copyErrorText",
        "jumpToErrorStage",
        "errorPayload",
        "data-m1-error-panel",
        "navigator.clipboard",
    ):
        if n not in html:
            _fail(f"watch.html missing {n}")
    # still keep P5
    for n in ("Follow tail", "Pause", "EVENT_WINDOW", "errBanner"):
        if n not in html:
            _fail(f"P5 regression missing {n}")
    _ok("HTML error UX markers")


def test_snapshot_error_block() -> None:
    from orpath.paths import apply_workdir
    from orpath.watch_snapshot import build_snapshot, validate_snapshot_shape

    wd = Path(tempfile.mkdtemp(prefix="orpath-m1-err-"))
    apply_workdir(wd)
    slug = "m1-err"
    stages = wd / "runs" / slug / "stages"
    stages.mkdir(parents=True, exist_ok=True)

    def write_stage(seq: int, node: str, **extra: object) -> None:
        data = {
            "utc": f"2026-08-03T00:00:{seq:02d}+00:00",
            "node": node,
            "stage": node,
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
        }
        data.update(extra)
        name = f"{seq:04d}_{node}.json"
        (stages / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if seq == 2:
            (wd / "runs" / slug / "latest_snapshot.json").write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )

    write_stage(1, "orchestrate")
    write_stage(
        2,
        "gate_schema",
        last_error="FAIL: forbidden key present: path",
        human_required=True,
        schema_repair=2,
    )

    snap = build_snapshot(slug=slug, thread_id=slug, workdir=wd, root=ROOT)
    errs = validate_snapshot_shape(snap)
    if errs:
        _fail(f"shape: {errs}")
    err = snap.get("error") or {}
    if not err.get("has_error"):
        _fail(f"error.has_error false: {err}")
    if "forbidden" not in str(err.get("last_error") or ""):
        _fail(f"last_error missing: {err}")
    if err.get("stage_seq") is None:
        _fail(f"stage_seq missing: {err}")
    if "last_error=" not in str(err.get("copy_text") or ""):
        _fail(f"copy_text weak: {err.get('copy_text')}")
    if not (snap.get("current") or {}).get("has_error"):
        _fail("current.has_error missing")
    # stages carry last_error
    bad = [st for st in snap.get("stages") or [] if st.get("last_error")]
    if not bad:
        _fail("no stage last_error in L0")
    _ok(
        f"error block status={err.get('status')} seq={err.get('stage_seq')} "
        f"node={err.get('node')}"
    )

    # clean slug no false error
    slug2 = "m1-ok"
    st2 = wd / "runs" / slug2 / "stages"
    st2.mkdir(parents=True, exist_ok=True)
    (st2 / "0001_orchestrate.json").write_text(
        json.dumps(
            {
                "utc": "2026-08-03T00:00:00+00:00",
                "node": "orchestrate",
                "stage": "orchestrate",
                "thread_id": slug2,
                "slug": slug2,
                "human_required": False,
                "gate_schema_ok": True,
                "gate_validate_ok": True,
                "solver_tune": 0,
                "schema_repair": 0,
                "validate_repair": 0,
                "revise_count": 0,
                "paths": {},
                "last_error": "",
            }
        ),
        encoding="utf-8",
    )
    (wd / "runs" / slug2 / "latest_snapshot.json").write_text(
        (st2 / "0001_orchestrate.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    snap2 = build_snapshot(slug=slug2, thread_id=slug2, workdir=wd, root=ROOT)
    err2 = snap2.get("error") or {}
    if err2.get("has_error") and snap2.get("status") not in {"fail", "blocked"}:
        # may still be running/ok without error
        if err2.get("last_error"):
            _fail(f"false positive error: {err2}")
    _ok(f"clean slug status={snap2.get('status')} has_error={err2.get('has_error')}")


def test_no_llm() -> None:
    from orpath.watch_snapshot import assert_no_llm_imports

    assert_no_llm_imports(ROOT / "orpath" / "watch_snapshot.py")
    _ok("no LLM in watch_snapshot")


def main() -> int:
    print("=== m1_watch_error_ux_gate (Part 3) ===")
    os.environ.pop("PYTHONPATH", None)
    os.environ["PYTHONNOUSERSITE"] = "1"
    test_html_markers()
    test_snapshot_error_block()
    test_no_llm()
    # P5 regression
    r = subprocess.run(
        [_py(), str(ROOT / "scripts" / "p5_polish_gate.py")],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": "", "PYTHONNOUSERSITE": "1"},
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        _fail("p5_polish_gate regression")
    _ok("p5_polish_gate still PASS")
    print("PASS m1_watch_error_ux_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
