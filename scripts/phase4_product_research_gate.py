#!/usr/bin/env python3
"""v3 Phase4: product research-profile hybrid run (slug thick-research-sp).

Asserts hybrid retrieval from real papers grain + honest embed_mode/profile,
validate ok, research cites chunk_ids. Paper/claim_map failure is WARN only.
Light regression: v1 phase3_hybrid_pi_gate (not nested thick-hybrid full double).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLUG = "thick-research-sp"


def main() -> int:
    os.environ.setdefault("PYTHONNOUSERSITE", "1")
    os.environ.pop("PYTHONPATH", None)
    os.environ.pop("PYTHONHOME", None)
    os.environ["ORPATH_LIVE_SUBAGENT"] = "0"
    os.environ.setdefault("ORPATH_KNOWLEDGE_PROFILE", "research")
    os.environ.setdefault("ORPATH_KNOWLEDGE_EMBED", "auto")

    py = ROOT / ".venv-314" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    fails: list[str] = []
    warns: list[str] = []

    def need(c: bool, msg: str) -> None:
        print(("PASS " if c else "FAIL ") + msg)
        if not c:
            fails.append(msg)

    def warn(msg: str) -> None:
        print("WARN " + msg)
        warns.append(msg)

    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    sh = (ROOT / "orpath.sh").read_text(encoding="utf-8", errors="replace")
    need(
        "product-research-gate" in bat
        or "phase4-product-research" in bat
        or "phase4_product_research" in bat,
        "bat product-research wiring",
    )
    need(
        "product-research-gate" in sh
        or "phase4-product-research" in sh
        or "phase4_product_research" in sh,
        "sh product-research wiring",
    )
    need((ROOT / "scripts/phase3_hybrid_pi_gate.py").is_file(), "v1 phase3 gate present")
    need((ROOT / "scripts/phase4_thick_hybrid_gate.py").is_file(), "v2 thick-hybrid gate present")

    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONNOUSERSITE"] = "1"
    env["ORPATH_LIVE_SUBAGENT"] = "0"
    env["ORPATH_KNOWLEDGE_PROFILE"] = "research"
    # Gate speed: stub index rebuild; retrieve still resolves live query embed when key+auto
    env.setdefault("ORPATH_KNOWLEDGE_EMBED", "auto")

    # Ensure hybrid indexes (stub rebuild for speed; fingerprint incremental ok after)
    r_ing = subprocess.run(
        [
            str(py),
            "-m",
            "knowledge_svc.ingest",
            "--clear",
            "--embed-mode",
            "stub",
            "--profile",
            "research",
            "--no-incremental",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    need(r_ing.returncode == 0, f"ingest rc={r_ing.returncode} {(r_ing.stderr or '')[:160]}")

    stale = ROOT / "notes" / f"{SLUG}-research.md"
    if stale.is_file():
        stale.unlink()

    cmd = [
        str(py),
        str(ROOT / "orpath" / "run_t2.py"),
        "--problem-id",
        "shortest_path",
        "--problem-class",
        "shortest_path",
        "--slug",
        SLUG,
        "--thread-id",
        SLUG,
        "--solve-mode",
        "mock",
        "--knowledge-mode",
        "hybrid",
        "--no-live-subagent",
        "--fresh",
        "--force",
        "--root",
        str(ROOT),
    ]
    print("RUN", " ".join(cmd), flush=True)
    # Ensure child sees research profile
    env_run = dict(env)
    env_run["ORPATH_KNOWLEDGE_PROFILE"] = "research"
    env_run["ORPATH_KNOWLEDGE_EMBED"] = env.get("ORPATH_KNOWLEDGE_EMBED") or "auto"
    r = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env_run,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=420,
    )
    print((r.stdout or "")[-1400:], flush=True)
    if r.returncode != 0:
        print((r.stderr or "")[-600:], file=sys.stderr)
        # Numbers path may still be green if paper/claim failed
        warn(f"run_t2 rc={r.returncode} — continue evidence checks")

    notes = ROOT / "notes"
    ret_path = notes / f"{SLUG}-retrieval.json"
    res_path = notes / f"{SLUG}-research.md"
    sol = ROOT / "outputs" / f"{SLUG}-solution.json"
    val = ROOT / "outputs" / f"{SLUG}-validate.json"

    need(ret_path.is_file(), f"retrieval exists {ret_path}")
    art: dict = {}
    if ret_path.is_file():
        art = json.loads(ret_path.read_text(encoding="utf-8"))
        need(art.get("knowledge_mode") == "hybrid", "retrieval mode=hybrid")
        hits = art.get("hits") or []
        need(isinstance(hits, list) and len(hits) >= 1, f"hits>=1 got {len(hits)}")
        paths = [str(h.get("source_path") or "").replace("\\", "/") for h in hits]
        need(
            any("knowledge/corpus/papers" in p for p in paths),
            f"hit from papers grain: {paths[:4]}",
        )
        # Prefer non-synthetic grain (lit/ or curated, not only mineru_lecture_*)
        realish = [
            p
            for p in paths
            if "knowledge/corpus/papers" in p
            and "mineru_lecture_" not in p
        ]
        if realish:
            print("PASS preferred non-synthetic papers hit:", realish[0])
        else:
            warn("top hits only synthetic mineru_lecture_* (papers still required)")

        emb = str(art.get("embed_mode") or "")
        need(emb in {"stub", "live"}, f"embed_mode stub|live got {emb!r}")
        # research profile when env set — may appear on art or embed_meta
        prof = art.get("profile") or (art.get("embed_meta") or {}).get("profile")
        if prof:
            need(prof in {"research", "demo"}, f"profile field {prof}")
        else:
            warn("profile field absent on retrieval artifact (env still research)")
        need(bool(art.get("query")), "query non-empty")
        if art.get("index_fingerprint"):
            print("PASS index_fingerprint present")

    need(res_path.is_file(), f"research exists {res_path}")
    body = res_path.read_text(encoding="utf-8") if res_path.is_file() else ""
    need("Coverage Status" in body or "coverage" in body.lower(), "research Coverage Status")
    need(
        "retrieval" in body.lower()
        or "chunk" in body.lower()
        or str(ret_path).replace("\\", "/") in body.replace("\\", "/"),
        "research mentions retrieval/chunk",
    )
    ids = [str(h.get("chunk_id")) for h in (art.get("hits") or []) if h.get("chunk_id")]
    if ids:
        need(any(i in body for i in ids), "research cites at least one chunk_id")

    need(sol.is_file(), "solution.json")
    need(val.is_file(), "validate.json")
    if val.is_file():
        v = json.loads(val.read_text(encoding="utf-8"))
        need(bool(v.get("ok")), f"validate ok={v.get('ok')}")

    # Soft: paper path may fail claim_map on thick corpus
    paper = ROOT / "papers" / f"{SLUG}.md"
    if paper.is_file():
        print("PASS paper draft exists", paper)
    else:
        warn("paper md missing (non-blocking for numbers path)")

    board = notes / "thick-research-evidence.md"
    board.write_text(
        "\n".join(
            [
                "# Phase 4 · thick-research product evidence (v3)",
                "",
                f"- slug: `{SLUG}`",
                f"- profile: research (env `ORPATH_KNOWLEDGE_PROFILE`)",
                f"- retrieval: `{ret_path}`",
                f"- research: `{res_path}`",
                f"- solution: `{sol}`",
                f"- validate: `{val}`",
                f"- knowledge_mode: `{art.get('knowledge_mode')}`",
                f"- embed_mode: `{art.get('embed_mode')}`",
                f"- profile_field: `{art.get('profile') or (art.get('embed_meta') or {}).get('profile')}`",
                f"- index_fingerprint: `{art.get('index_fingerprint')}`",
                f"- hits: {len(art.get('hits') or [])}",
                f"- query: `{art.get('query')}`",
                "",
                "## Top hits",
                "",
            ]
            + [
                f"- `{h.get('chunk_id')}` ← `{h.get('source_path')}`"
                for h in (art.get("hits") or [])[:8]
            ]
            + [
                "",
                "## Regression",
                "",
                "- v1 `phase3-hybrid-gate` below must PASS (RAG/numbers path)",
                "- v2 `thick-hybrid-gate` remains separate command (not nested here for time)",
                "",
                f"warns: {warns}",
                f"gate product-research: **{'PASS' if not fails else 'FAIL'}**",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("WROTE", board)

    # v1 hybrid regression (RAG + validate)
    print("--- v1 phase3-hybrid-gate regression ---", flush=True)
    r2 = subprocess.run(
        [str(py), str(ROOT / "scripts/phase3_hybrid_pi_gate.py")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=420,
    )
    out2 = (r2.stdout or "") + (r2.stderr or "")
    print(out2[-800:], flush=True)
    need(r2.returncode == 0, f"v1 phase3-hybrid-gate rc0 {r2.returncode}")
    need("PASS phase3_hybrid_pi_gate" in out2, "v1 phase3-hybrid-gate PASS line")

    # Soft presence of v2 thick evidence (full re-run optional)
    if (ROOT / "notes/thick-hybrid-evidence.md").is_file():
        print("PASS v2 thick-hybrid-evidence.md present (prior)")
    else:
        warn("v2 thick-hybrid-evidence.md missing — run orpath.bat thick-hybrid-gate separately")

    if fails:
        print("FAIL phase4_product_research_gate", fails, "warns", warns)
        return 1
    print("PASS phase4_product_research_gate", f"warns={warns}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
