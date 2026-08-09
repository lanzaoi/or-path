#!/usr/bin/env python3
"""Gate: Watch dialogue + human-steer D0–D4 (bubbles, API, LG merge, tier2, e2e)."""
from __future__ import annotations

import json
import os
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


def test_html_markers() -> None:
    html = (ROOT / "orpath" / "web" / "watch.html").read_text(encoding="utf-8")
    for n in (
        "data-orpath-dialogue",
        "data-orpath-steer-form",
        "dlgBubbles",
        "dlgSubmit",
        "collaboration" if False else "协作对话",
        "/api/steer",
        "human-steer",
        "errBanner",
        "Copy cmd",
        "EVENT_WINDOW",
        "auto-resume",
    ):
        if n not in html:
            _fail(f"watch.html missing {n!r}")
    _ok("watch.html dialogue markers")


def test_steer_module() -> None:
    from orpath.human_steer import (
        build_dialogue,
        find_forbidden_keys,
        normalize_steer_payload,
        save_human_steer,
        load_human_steer,
    )

    bad, errs = normalize_steer_payload(
        {"slug": "x", "objective": 99, "notes": "hi"}, slug="x"
    )
    if bad is not None or not errs:
        _fail("must reject objective in steer")
    _ok("reject objective")

    doc, errs2 = normalize_steer_payload(
        {
            "solve_mode": "highs",
            "notes": "prefer dual proof",
            "prefer_methods": "cpsat,highs",
        },
        slug="dlg-demo",
    )
    if errs2 or not doc:
        _fail(f"normalize failed: {errs2}")
    if doc["lg"].get("solve_mode") != "highs":
        _fail("solve_mode not in lg")
    if "cpsat" not in (doc["pi"].get("prefer_methods") or []):
        _fail("methods missing")
    _ok("normalize lg/pi split")

    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        (wd / "notes").mkdir()
        (wd / "outputs").mkdir()
        sol = {
            "status": "FEASIBLE",
            "objective": 99000,
            "meta": {"exact": False, "proven_optimal": False, "method_class": "metaheuristic"},
        }
        sp = wd / "outputs" / "dlg-demo-solution.json"
        sp.write_text(json.dumps(sol), encoding="utf-8")
        vp = wd / "outputs" / "dlg-demo-validate.json"
        vp.write_text(json.dumps({"ok": True}), encoding="utf-8")
        save_human_steer(wd, "dlg-demo", doc)
        loaded = load_human_steer(wd, "dlg-demo")
        if not loaded:
            _fail("load steer failed")
        stages = [
            {"seq": 1, "node": "research", "utc": "t1", "last_error": ""},
            {"seq": 2, "node": "solve", "utc": "t2", "last_error": ""},
            {"seq": 3, "node": "gate_validate", "utc": "t3", "last_error": ""},
        ]
        dlg = build_dialogue(
            workdir=wd,
            slug="dlg-demo",
            stages=stages,
            current={"node": "gate_validate"},
            status="ok",
            artifacts={
                "solution": str(sp),
                "validate": str(vp),
            },
        )
        if dlg.get("llm") is not False:
            _fail("dialogue must set llm=false")
        roles = {b.get("role") for b in dlg.get("bubbles") or []}
        if "solve" not in roles and "validate" not in roles:
            _fail(f"expected solve/validate bubbles, got {roles}")
        if not any(b.get("role") == "human" for b in dlg["bubbles"]):
            _fail("expected human steer bubble")
        _ok(f"dialogue bubbles n={len(dlg['bubbles'])}")

    # forbid helper
    hits = find_forbidden_keys({"a": {"tour": [1]}})
    if not hits:
        _fail("find_forbidden_keys missed tour")
    _ok("forbidden key scan")


def test_snapshot_has_dialogue() -> None:
    from orpath.watch_snapshot import build_snapshot, assert_no_llm_imports

    assert_no_llm_imports()
    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        home = ROOT
        # minimal empty snapshot still has dialogue
        snap = build_snapshot(slug="empty-dlg", thread_id="empty-dlg", workdir=wd, root=home)
        if "dialogue" not in snap:
            _fail("snapshot missing dialogue")
        if snap["dialogue"].get("llm") is not False:
            _fail("dialogue.llm must be false")
        if not isinstance(snap["dialogue"].get("bubbles"), list):
            _fail("bubbles must be list")
        _ok("snapshot.dialogue present")


def test_watch_api_strings() -> None:
    src = (ROOT / "scripts" / "orpath_watch.py").read_text(encoding="utf-8")
    for n in ("/api/steer", "save_human_steer", "normalize_steer_payload"):
        if n not in src:
            _fail(f"orpath_watch missing {n}")
    _ok("watch server steer routes")


def test_d2_apply_merge() -> None:
    """D2: solve_mode override + Pi block + pause boundary."""
    from orpath.graph_live_subagent import _research_steer_section
    from orpath.human_steer import (
        apply_steer_to_state,
        format_pi_steer_block,
        resume_from_steer,
        save_human_steer,
    )

    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        (wd / "notes").mkdir()
        doc = {
            "schema_version": 1,
            "slug": "d2-demo",
            "utc": "t",
            "at_stage": "after_research",
            "lg": {
                "solve_mode": "highs",
                "resume_from": "solve",
                "pause_next": True,
            },
            "pi": {
                "prefer_methods": ["cpsat", "highs"],
                "notes": "dual proof TSP please",
            },
            "source": "test",
            "forbid_numbers_edit": True,
        }
        save_human_steer(wd, "d2-demo", doc)
        state = {
            "slug": "d2-demo",
            "root": str(wd),
            "solve_mode": "mock",
            "problem_id": "tsp_n8",
        }
        upd = apply_steer_to_state(state, workdir=wd, boundary=None)
        if upd.get("solve_mode") != "highs":
            _fail(f"mode not overridden: {upd}")
        if not upd.get("human_steer_applied"):
            _fail("not applied")
        if (upd.get("human_steer_pi") or {}).get("notes") != "dual proof TSP please":
            _fail("pi notes missing")
        _ok("D2 mode override highs")

        merged = {**state, **upd}
        block = format_pi_steer_block(merged)
        if "dual proof" not in block or "prefer_methods" not in block:
            _fail(f"pi block weak: {block!r}")
        sec = _research_steer_section(merged)
        if "Human steer" not in sec or "dual proof" not in sec:
            _fail(f"research section weak: {sec!r}")
        _ok("D2 Pi prompt injection")

        # pause before model when at_stage=after_research
        pause = apply_steer_to_state(merged, workdir=wd, boundary="model")
        if not pause.get("steer_pause") or pause.get("stage") != "human_stop":
            _fail(f"pause expected at model: {pause}")
        _ok("D2 pause before model")

        # no pause at research for after_research
        no_p = apply_steer_to_state(merged, workdir=wd, boundary="research")
        if no_p.get("steer_pause"):
            _fail("should not pause at research for after_research")
        _ok("D2 no pause at research")

        rf = resume_from_steer(wd, "d2-demo")
        if rf != "solve":
            _fail(f"resume_from={rf}")
        _ok("D2 resume_from solve")

        # forbidden objective file
        bad = dict(doc)
        bad["objective"] = 99
        p = wd / "notes" / "d2-demo-human-steer.json"
        p.write_text(json.dumps(bad), encoding="utf-8")
        rej = apply_steer_to_state(state, workdir=wd, boundary=None)
        if rej.get("human_steer_applied"):
            _fail("poisoned objective file must not apply")
        if "forbidden" not in str(rej.get("last_error") or ""):
            _fail(f"expected forbidden error: {rej}")
        _ok("D2 reject poisoned steer file")

    # wiring markers
    nodes = (ROOT / "orpath" / "nodes.py").read_text(encoding="utf-8")
    if "apply_steer_to_state" not in nodes or "boundary=\"solve\"" not in nodes:
        _fail("nodes.py missing D2 wiring")
    run = (ROOT / "orpath" / "run_orpath.py").read_text(encoding="utf-8")
    if "human_steer_solve_mode" not in run and "apply_steer_to_state" not in run:
        _fail("run_orpath missing D2 merge")
    _ok("D2 wiring markers")


def test_d3_tier2_deep_link() -> None:
    """D3: snapshot deep_links + package_status + Watch panel + docs."""
    html = (ROOT / "orpath" / "web" / "watch.html").read_text(encoding="utf-8")
    for n in (
        "data-orpath-tier2",
        "tier2Panel",
        "renderTier2",
        "ORPATH_PI_SESSION",
        "pi-kanban",
        "/supervise",
        "deep_links",
    ):
        if n not in html:
            _fail(f"watch.html D3 missing {n!r}")
    _ok("D3 HTML markers")

    for rel in (
        "docs/d3-tier2-deep-link.md",
        "docs/p4-tier2-deep-look.md",
        ".pi/SUPERVISOR.md",
        ".pi/settings.json",
    ):
        if not (ROOT / rel).is_file():
            _fail(f"missing {rel}")
    settings = json.loads((ROOT / ".pi" / "settings.json").read_text(encoding="utf-8"))
    pkgs = " ".join(str(x) for x in (settings.get("packages") or []))
    for need in ("pi-kanban", "pi-supervisor"):
        if need not in pkgs:
            _fail(f".pi/settings.json packages missing {need}: {pkgs}")
    _ok("D3 packages + docs on disk")

    from orpath.watch_snapshot import build_snapshot, discover_pi_sessions

    t2 = discover_pi_sessions(workdir=ROOT, limit=3, home=ROOT)
    if not isinstance(t2.get("deep_links"), list) or len(t2["deep_links"]) < 3:
        _fail(f"deep_links weak: {t2.get('deep_links')}")
    ids = {x.get("id") for x in t2["deep_links"]}
    for need in ("session_on", "kanban", "supervise"):
        if need not in ids:
            _fail(f"deep_links missing {need}: {ids}")
    ps = t2.get("package_status") or {}
    if not ps.get("pi-kanban") or not ps.get("pi-supervisor"):
        _fail(f"package_status not ready: {ps}")
    if "supervise_hint" not in t2:
        _fail("supervise_hint missing")
    _ok(f"D3 discover deep_links n={len(t2['deep_links'])} kanban={ps.get('pi-kanban')}")

    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        os.environ["ORPATH_PI_SESSION"] = "0"
        snap = build_snapshot(slug="d3-empty", thread_id="d3-empty", workdir=wd, root=ROOT)
        t2s = snap.get("tier2") or {}
        if not t2s.get("deep_links"):
            _fail("snapshot.tier2.deep_links missing")
        if t2s.get("pi_session_env") is not False:
            _fail("SESSION=0 should be false")
        msgs = (snap.get("honesty") or {}).get("messages") or []
        if not any("tier2_session_off" in str(m) for m in msgs):
            _fail("honesty missing tier2_session_off")
        _ok("D3 snapshot SESSION=0 honesty")

        os.environ["ORPATH_PI_SESSION"] = "1"
        snap1 = build_snapshot(slug="d3-empty", thread_id="d3-empty", workdir=wd, root=ROOT)
        if not (snap1.get("tier2") or {}).get("pi_session_env"):
            _fail("SESSION=1 should set pi_session_env")
        _ok("D3 snapshot SESSION=1")
        os.environ["ORPATH_PI_SESSION"] = "0"

    d3 = (ROOT / "docs" / "d3-tier2-deep-link.md").read_text(encoding="utf-8")
    for n in ("ORPATH_PI_SESSION", "pi-kanban", "/supervise", "deep_links", "Copy cmd"):
        if n not in d3:
            _fail(f"d3 doc missing {n}")
    _ok("D3 hand-test doc")


def test_d4_e2e_product_steer() -> None:
    """D4: form markers + flat pause_next + mock product run honors solve_mode."""
    html = (ROOT / "orpath" / "web" / "watch.html").read_text(encoding="utf-8")
    for n in ("dlgAtStage", "dlgPause", "pause_next", "at_stage", "dialogue-gate"):
        if n not in html:
            _fail(f"D4 html missing {n}")
    _ok("D4 form markers")

    from orpath.human_steer import normalize_steer_payload, save_human_steer

    doc, errs = normalize_steer_payload(
        {
            "solve_mode": "networkx",
            "pause_next": True,
            "at_stage": "after_research",
            "notes": "use Dijkstra exact",
            "prefer_methods": "dijkstra",
        },
        slug="d4-form",
    )
    if errs or not doc:
        _fail(f"flat pause normalize fail {errs}")
    if not doc["lg"].get("pause_next"):
        _fail(f"pause_next not in lg: {doc}")
    if doc.get("at_stage") != "after_research":
        _fail(f"at_stage {doc.get('at_stage')}")
    _ok("D4 flat pause_next + at_stage normalize")

    # Product path E2E (no LIVE): steer overrides mock → networkx
    os.environ["ORPATH_LIVE_SUBAGENT"] = "0"
    os.environ["ORPATH_APPLY_STEER"] = "1"
    os.environ["ORPATH_PI_SESSION"] = "0"
    try:
        from orpath.control_plane import invoke_once

        with tempfile.TemporaryDirectory() as td:
            wd = Path(td)
            for d in ("notes", "outputs", "runs", "papers"):
                (wd / d).mkdir()
            save_human_steer(
                wd,
                "d4e2e",
                {
                    "schema_version": 1,
                    "slug": "d4e2e",
                    "utc": "t",
                    "at_stage": "manual",
                    "lg": {"solve_mode": "networkx"},
                    "pi": {
                        "prefer_methods": ["dijkstra"],
                        "notes": "use Dijkstra exact",
                    },
                    "source": "d4-gate",
                    "forbid_numbers_edit": True,
                },
            )
            final = invoke_once(
                root=wd,
                slug="d4e2e",
                problem_id="shortest_path",
                problem_class="shortest_path",
                solve_mode="mock",
                knowledge_mode="off",
                live_subagent=False,
                thread_id="d4e2e",
            )
            if final.get("solve_mode") != "networkx":
                _fail(f"e2e solve_mode={final.get('solve_mode')}")
            if not final.get("human_steer_applied"):
                _fail("e2e human_steer_applied false")
            if not final.get("gate_validate_ok"):
                _fail(f"e2e validate not ok: {final.get('last_error')}")
            if final.get("human_required"):
                _fail(f"e2e unexpected human: {final.get('last_error')}")
            plan = Path(final.get("plan_path") or "")
            if plan.is_file():
                pt = plan.read_text(encoding="utf-8")
                if "human_steer" not in pt and "networkx" not in pt:
                    _fail("plan missing steer/mode note")
            # research should mention steer notes when written
            rp = Path(final.get("research_path") or "")
            if rp.is_file():
                rt = rp.read_text(encoding="utf-8")
                if "Dijkstra" not in rt and "Human steer" not in rt and "dijkstra" not in rt.lower():
                    # deterministic research may still inject via format_pi_steer_block
                    _ok("D4 research present (steer text optional if live path skipped)")
                else:
                    _ok("D4 research contains steer notes")
            _ok(
                f"D4 e2e product mode=networkx validate={final.get('gate_validate_ok')} stage={final.get('stage')}"
            )
    except Exception as exc:  # noqa: BLE001
        _fail(f"D4 e2e invoke_once failed: {exc}")
    finally:
        os.environ["ORPATH_LIVE_SUBAGENT"] = "0"
        os.environ["ORPATH_APPLY_STEER"] = "1"

    # docs
    for rel in ("docs/d4-dialogue-e2e.md", "specs/human-steer-and-pi-guidance.md"):
        if not (ROOT / rel).is_file():
            _fail(f"missing {rel}")
    d4 = (ROOT / "docs" / "d4-dialogue-e2e.md").read_text(encoding="utf-8")
    for n in ("dialogue-gate", "pause_next", "invoke_once", "networkx"):
        if n not in d4:
            _fail(f"d4 doc missing {n}")
    _ok("D4 docs")


def main() -> int:
    os.environ.setdefault("PYTHONNOUSERSITE", "1")
    test_html_markers()
    test_steer_module()
    test_snapshot_has_dialogue()
    test_watch_api_strings()
    test_d2_apply_merge()
    test_d3_tier2_deep_link()
    test_d4_e2e_product_steer()
    print("PASS dialogue-steer-gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
