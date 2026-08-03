#!/usr/bin/env python3
"""V0 Phase A gate: watch_snapshot aggregator (no HTTP / no LLM).

Exit 0 only if:
- snapshot shape contract holds
- historical product slug with stages yields non-empty L0 (prefer slug=test)
- missing slug → status=no_product_run, no throw
- cosplay synthetic log → subagent_detected false / cosplay honesty
- watch_snapshot.py has no LLM SDK imports
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orpath.watch_snapshot import (  # noqa: E402
    SCHEMA_VERSION,
    assert_no_llm_imports,
    build_snapshot,
    parse_lead_events,
    validate_snapshot_shape,
)


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def _pick_slug_with_stages(workdir: Path) -> str | None:
    runs = workdir / "runs"
    if not runs.is_dir():
        return None
    # prefer test
    if (runs / "test" / "stages").is_dir() and any((runs / "test" / "stages").glob("*.json")):
        return "test"
    for d in sorted(runs.iterdir()):
        if d.is_dir() and (d / "stages").is_dir() and any((d / "stages").glob("*.json")):
            return d.name
    return None


def test_no_llm() -> None:
    assert_no_llm_imports(ROOT / "orpath" / "watch_snapshot.py")
    _ok("no LLM imports in watch_snapshot.py")


def test_shape_and_history(workdir: Path) -> None:
    slug = _pick_slug_with_stages(workdir)
    if not slug:
        _fail("no runs/*/stages fixtures found under workdir — cannot gate L0")
    snap = build_snapshot(slug=slug, thread_id=slug, workdir=workdir, root=ROOT)
    errs = validate_snapshot_shape(snap)
    if errs:
        _fail(f"shape errors: {errs}")
    if snap["schema_version"] != SCHEMA_VERSION:
        _fail("schema_version")
    if not snap["stages"]:
        _fail(f"expected non-empty stages for slug={slug}")
    if snap["status"] == "no_product_run":
        _fail("status should not be no_product_run when stages exist")
    _ok(f"history L0 slug={slug} stages={len(snap['stages'])} status={snap['status']}")
    _ok(f"current node={snap['current'].get('node')} counters={snap['current'].get('counters')}")
    # dispatches optional but if agents exist should parse
    agents = workdir / "outputs" / ".agents" / slug
    if agents.is_dir() and any(agents.glob("*.log")):
        if not snap["dispatches"]:
            _fail("agents has logs but dispatches empty")
        _ok(f"dispatches={len(snap['dispatches'])} events={len(snap['events'])}")
        # at least one real subagent on test slug historically
        any_hit = any(d.get("subagent_detected") for d in snap["dispatches"])
        _ok(f"subagent_detected_any={any_hit}")
        th = snap["thinking"]["status"]
        if th not in {"available", "thinking_unavailable"}:
            _fail(f"bad thinking status {th}")
        _ok(f"thinking.status={th}")
    # artifacts paths are strings or null
    for k, v in snap["artifacts"].items():
        if v is not None and not isinstance(v, str):
            _fail(f"artifact {k} not str|None")
    _ok(f"artifacts keys={list(snap['artifacts'].keys())}")


def test_missing_slug(workdir: Path) -> None:
    snap = build_snapshot(
        slug="__watch_snapshot_missing_slug__",
        thread_id="__watch_snapshot_missing_slug__",
        workdir=workdir,
        root=ROOT,
    )
    errs = validate_snapshot_shape(snap)
    if errs:
        _fail(f"missing slug shape: {errs}")
    if snap["status"] != "no_product_run":
        _fail(f"expected no_product_run got {snap['status']}")
    if snap["stages"]:
        _fail("missing slug should have empty stages")
    if not snap["honesty"].get("bare_pi"):
        _fail("honesty.bare_pi expected")
    _ok("missing slug → no_product_run")


def test_cosplay_synthetic() -> None:
    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        slug = "cosplay-demo"
        agents = wd / "outputs" / ".agents" / slug
        agents.mkdir(parents=True)
        # no stages → still test dispatch honesty path with agents only
        (wd / "runs" / slug / "stages").mkdir(parents=True)
        stage = {
            "utc": "2026-01-01T00:00:00+00:00",
            "node": "research",
            "stage": "research",
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
        (wd / "runs" / slug / "stages" / "0001_research.json").write_text(
            json.dumps(stage, indent=2), encoding="utf-8"
        )
        log = agents / "research-lead-20260101T000000Z.log"
        # prose cosplay only — no toolCall
        log.write_text(
            "I am the researcher subagent and I finished the research.\n"
            "No tools needed; here is my analysis.\n",
            encoding="utf-8",
        )
        harness = {
            "skipped": False,
            "gate_subagent_ok": False,
            "harness": "no_write_lead+json+anti_cosplay",
            "tools": "read,bash,subagent",
            "log_path": str(log),
            "subagent_calls_detected": False,
            "call_evidence": [],
            "error": "",
        }
        (agents / "research-harness.json").write_text(
            json.dumps(harness, indent=2), encoding="utf-8"
        )

        snap = build_snapshot(slug=slug, thread_id=slug, workdir=wd, root=wd)
        errs = validate_snapshot_shape(snap)
        if errs:
            _fail(f"cosplay shape: {errs}")
        if not snap["stages"]:
            _fail("cosplay fixture stages empty")
        d0 = next((d for d in snap["dispatches"] if d["stage"] == "research"), None)
        if not d0:
            _fail("expected research dispatch")
        if d0.get("subagent_detected"):
            _fail("cosplay log must not detect subagent")
        if not d0.get("cosplay"):
            _fail("expected cosplay=true when tools claim subagent but no toolCall")
        # must not look like a successful MA node only
        if d0.get("subagent_detected") is True:
            _fail("false MA")
        _ok("cosplay synthetic → detected=false cosplay=true")

        # positive control: real toolName line
        log.write_text(
            '{"type":"tool_execution_start","toolName":"subagent","args":{"agent":"or-researcher"}}\n',
            encoding="utf-8",
        )
        harness["subagent_calls_detected"] = True
        (agents / "research-harness.json").write_text(
            json.dumps(harness, indent=2), encoding="utf-8"
        )
        snap2 = build_snapshot(slug=slug, thread_id=slug, workdir=wd, root=wd)
        d1 = next(d for d in snap2["dispatches"] if d["stage"] == "research")
        if not d1.get("subagent_detected"):
            _fail("positive subagent tool_execution_start not detected")
        if d1.get("cosplay"):
            _fail("positive should not be cosplay")
        _ok("positive subagent toolCall detected")


def test_parse_events_unit() -> None:
    sample = "\n".join(
        [
            '{"type":"tool_execution_start","toolName":"read","args":{"path":"x.md"}}',
            '{"type":"tool_execution_end","toolName":"read","result":{"content":[{"type":"text","text":"hello"}]}}',
            '{"type":"turn_end","message":{"role":"assistant","content":[{"type":"thinking","thinking":"plan A"},{"type":"text","text":"done"}]}}',
        ]
    )
    evs, th, _roles = parse_lead_events(sample, dispatch_id="model")
    kinds = [e["kind"] for e in evs]
    if "tool" not in kinds or "tool_result" not in kinds:
        _fail(f"expected tool events got {kinds}")
    if not th:
        _fail("thinking should be found")
    if not any(e["kind"] == "thinking" for e in evs):
        _fail("thinking event missing")
    _ok(f"parse_lead_events kinds={kinds}")


def test_p2_sub_process_readable(workdir: Path) -> None:
    """P2: subagent dispatch + tool/assistant events + optional transcript children."""
    from collections import Counter

    slug = _pick_slug_with_stages(workdir)
    if not slug:
        _fail("no slug with stages for P2")
    snap = build_snapshot(slug=slug, thread_id=slug, workdir=workdir, root=ROOT)
    proc = snap.get("process") or {}
    hits = [d for d in snap["dispatches"] if d.get("subagent_detected")]
    if not hits:
        # still require event kinds on any lead if agents exist
        agents = workdir / "outputs" / ".agents" / slug
        if agents.is_dir() and any(agents.glob("*.log")):
            _fail(f"P2 expected ≥1 subagent_detected dispatch on slug={slug}")
        _ok("P2 skip: no agents logs")
        return
    kinds = Counter(e.get("kind") for e in snap["events"])
    toolish = kinds.get("tool", 0) + kinds.get("tool_result", 0) + kinds.get("assistant", 0)
    if toolish < 3:
        _fail(f"P2 need ≥3 tool/assistant-class events got {dict(kinds)}")
    th = snap["thinking"]["status"]
    if th not in {"available", "thinking_unavailable"}:
        _fail(f"P2 thinking status {th}")
    # children optional but if .pi-subagents exists should try
    children_n = int(proc.get("children_count") or 0)
    sub_ev = int(proc.get("sub_events") or 0)
    _ok(
        f"P2 slug={slug} sub_dispatches={len(hits)} toolish={toolish} "
        f"thinking={th} children={children_n} sub_events={sub_ev}"
    )
    # cosplay must not claim detected
    for d in snap["dispatches"]:
        if d.get("cosplay") and d.get("subagent_detected"):
            _fail("cosplay row must not be subagent_detected")
    # process block present
    if "event_kinds" not in proc:
        _fail("process.event_kinds missing")
    # transcript parse unit if any child path
    for d in hits:
        for ch in d.get("children") or []:
            tp = ch.get("transcript_path")
            if tp:
                abs_p = workdir / tp
                if not abs_p.is_file():
                    abs_p = ROOT / tp
                if abs_p.is_file():
                    from orpath.watch_snapshot import parse_transcript_events

                    tevs, _ = parse_transcript_events(
                        abs_p, dispatch_id=d["stage"], agent=str(ch.get("agent") or "x")
                    )
                    if not tevs:
                        _fail(f"transcript parse empty {tp}")
                    if not any(e.get("source") == "sub" for e in tevs):
                        _fail("transcript events source!=sub")
                    _ok(f"P2 transcript events={len(tevs)} path={tp}")
                    return
    _ok("P2 no matched transcript on disk (lead L2 still ok)")


def test_p1_fingerprint_and_growing_log() -> None:
    """P1: fingerprint dirty on stage growth; events grow when log grows."""
    from orpath.watch_snapshot import compute_source_fingerprint, read_log_text

    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        slug = "p1-grow"
        stages = wd / "runs" / slug / "stages"
        agents = wd / "outputs" / ".agents" / slug
        stages.mkdir(parents=True)
        agents.mkdir(parents=True)

        def write_stage(n: int, node: str) -> None:
            stage = {
                "utc": f"2026-01-01T00:00:{n:02d}+00:00",
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
            (stages / f"{n:04d}_{node}.json").write_text(
                json.dumps(stage, indent=2), encoding="utf-8"
            )

        write_stage(1, "orchestrate")
        fp1 = compute_source_fingerprint(slug=slug, thread_id=slug, workdir=wd)
        if fp1["stages_count"] != 1:
            _fail(f"stages_count expected 1 got {fp1['stages_count']}")
        if not fp1.get("fingerprint"):
            _fail("missing fingerprint")

        write_stage(2, "research")
        fp2 = compute_source_fingerprint(slug=slug, thread_id=slug, workdir=wd)
        if fp2["stages_count"] != 2:
            _fail("stages_count should grow")
        if fp2["fingerprint"] == fp1["fingerprint"]:
            _fail("fingerprint must change when stages grow")
        _ok(f"P1 fingerprint dirty {fp1['fingerprint']} → {fp2['fingerprint']}")

        log = agents / "research-lead-20260101T000000Z.log"
        line1 = (
            '{"type":"tool_execution_start","toolName":"read","args":{"path":"a.md"}}\n'
        )
        log.write_text(line1, encoding="utf-8")
        snap_a = build_snapshot(slug=slug, thread_id=slug, workdir=wd, root=wd)
        if "poll" not in snap_a:
            _fail("snapshot missing poll (P1)")
        n_a = len(snap_a["events"])
        if n_a < 1:
            _fail("expected events after first log line")
        fp_a = snap_a["poll"]["fingerprint"]

        line2 = (
            '{"type":"tool_execution_end","toolName":"read","result":{"content":[{"type":"text","text":"hi"}]}}\n'
            '{"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":"done"}]}}\n'
        )
        with log.open("a", encoding="utf-8") as f:
            f.write(line2)
        snap_b = build_snapshot(
            slug=slug,
            thread_id=slug,
            workdir=wd,
            root=wd,
            prev_fingerprint=fp_a,
            prev_events_count=n_a,
        )
        n_b = len(snap_b["events"])
        if n_b < n_a:
            _fail(f"events should grow {n_a} → {n_b}")
        if snap_b["poll"].get("dirty") is not True:
            _fail("poll.dirty expected True after log append")
        added = snap_b["poll"].get("events_added")
        if added is None or added < 0:
            _fail(f"events_added expected non-neg got {added}")
        # second build with same prev should still have >= events
        snap_c = build_snapshot(slug=slug, thread_id=slug, workdir=wd, root=wd)
        if len(snap_c["events"]) < n_b:
            _fail("second full build lost events")
        _ok(f"P1 growing log events {n_a} → {n_b} added={added}")

        # incremental offset read
        text_full, sz, trunc = read_log_text(log)
        if trunc:
            _fail("small log should not truncate")
        text_inc, sz2, _ = read_log_text(log, from_offset=len(line1.encode("utf-8")))
        if "tool_execution_end" not in text_inc:
            _fail("from_offset should see appended lines")
        if sz2 != sz:
            _fail("size mismatch")
        _ok("P1 read_log_text from_offset")


def test_live_off_honesty(workdir: Path) -> None:
    prev = os.environ.get("ORPATH_LIVE_SUBAGENT")
    try:
        os.environ["ORPATH_LIVE_SUBAGENT"] = "0"
        snap = build_snapshot(slug="__none__", thread_id="__none__", workdir=workdir)
        if snap["live_subagent"] is not False:
            _fail("live_subagent should be False when env=0")
        if not snap["honesty"].get("live_off"):
            _fail("honesty.live_off expected")
        _ok("LIVE=0 honesty")
    finally:
        if prev is None:
            os.environ.pop("ORPATH_LIVE_SUBAGENT", None)
        else:
            os.environ["ORPATH_LIVE_SUBAGENT"] = prev


def main() -> int:
    print("=== watch_snapshot_gate (Phase A) ===")
    print("ROOT =", ROOT)
    workdir = ROOT
    test_no_llm()
    test_parse_events_unit()
    test_shape_and_history(workdir)
    test_missing_slug(workdir)
    test_cosplay_synthetic()
    test_p1_fingerprint_and_growing_log()
    test_p2_sub_process_readable(workdir)
    test_live_off_honesty(workdir)
    print("PASS watch_snapshot_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
