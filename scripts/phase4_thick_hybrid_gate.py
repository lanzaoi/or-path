#!/usr/bin/env python3
"""Phase 4 (v2 thick): product hybrid run cites scaled papers + honest embed_mode.

Slug: thick-hybrid-sp
Also regression-runs v1 phase3_hybrid_pi_gate (must still PASS).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLUG = "thick-hybrid-sp"


def main() -> int:
    os.environ.setdefault("PYTHONNOUSERSITE", "1")
    os.environ.pop("PYTHONPATH", None)
    os.environ.pop("PYTHONHOME", None)
    os.environ["ORPATH_LIVE_SUBAGENT"] = "0"
    # Prefer stub for gate speed/reliability; live still allowed if env forces live
    os.environ.setdefault("ORPATH_KNOWLEDGE_EMBED", "stub")

    py = ROOT / ".venv-314" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    fails: list[str] = []

    def need(c: bool, msg: str) -> None:
        print(("PASS " if c else "FAIL ") + msg)
        if not c:
            fails.append(msg)

    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    sh = (ROOT / "orpath.sh").read_text(encoding="utf-8", errors="replace")
    need("thick-hybrid-gate" in bat or "phase4_thick" in bat, "bat thick-hybrid wiring")
    need("thick-hybrid-gate" in sh or "phase4_thick" in sh, "sh thick-hybrid wiring")
    need((ROOT / "scripts" / "phase3_hybrid_pi_gate.py").is_file(), "v1 phase3 gate present")

    # Rebuild indexes (stub) so papers/_from_mineru present
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONNOUSERSITE"] = "1"
    env["ORPATH_LIVE_SUBAGENT"] = "0"
    env.setdefault("ORPATH_KNOWLEDGE_EMBED", "stub")

    subprocess.run(
        [str(py), "-m", "knowledge_svc.ingest", "--clear", "--embed-mode", "stub"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )

    # Drop stale research so evidence table matches current retrieval
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
    r = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=360,
    )
    print((r.stdout or "")[-1200:], flush=True)
    need(r.returncode == 0, f"run_t2 rc0 got {r.returncode}")
    if r.returncode != 0:
        print((r.stderr or "")[-600:], file=sys.stderr)

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
            f"hit from papers main grain: {paths[:3]}",
        )
        # Prefer mineru path when present in corpus
        mineru_files = list((ROOT / "knowledge/corpus/papers/_from_mineru").glob("*.md"))
        if mineru_files:
            # soft preference: if any hit is _from_mineru OR research cites papers — already require papers
            has_m = any("_from_mineru" in p for p in paths)
            if has_m:
                print("PASS preferred _from_mineru hit present")
            else:
                print("INFO no _from_mineru in top hits (papers hit still required)")
        need("embed_mode" in art, f"embed_mode field present keys={list(art.keys())[:12]}")
        emb = str(art.get("embed_mode") or "")
        need(emb in {"stub", "live"}, f"embed_mode stub|live got {emb!r}")
        need(bool(art.get("query")), "query non-empty")

    need(res_path.is_file(), f"research exists {res_path}")
    body = res_path.read_text(encoding="utf-8") if res_path.is_file() else ""
    need("Coverage Status" in body or "coverage" in body.lower(), "research Coverage Status")
    need(
        "retrieval" in body.lower() or "chunk" in body.lower() or str(ret_path).replace("\\", "/") in body.replace("\\", "/"),
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

    # Evidence board
    board = notes / "thick-hybrid-evidence.md"
    board.write_text(
        "\n".join(
            [
                "# Phase 4 · thick-hybrid product evidence",
                "",
                f"- slug: `{SLUG}`",
                f"- retrieval: `{ret_path}`",
                f"- research: `{res_path}`",
                f"- solution: `{sol}`",
                f"- validate: `{val}`",
                f"- knowledge_mode: `{art.get('knowledge_mode')}`",
                f"- embed_mode: `{art.get('embed_mode')}` (stub|live — honest)",
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
                "- v1 `phase3-hybrid-gate` run below must PASS",
                "",
                f"gate thick: **{'PASS' if not fails else 'FAIL'}**",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("WROTE", board)

    # v1 regression
    print("--- v1 phase3-hybrid-gate regression ---", flush=True)
    r2 = subprocess.run(
        [str(py), str(ROOT / "scripts" / "phase3_hybrid_pi_gate.py")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=360,
    )
    out2 = (r2.stdout or "") + (r2.stderr or "")
    print(out2[-800:], flush=True)
    need(r2.returncode == 0, f"v1 phase3-hybrid-gate rc0 {r2.returncode}")
    need("PASS phase3_hybrid_pi_gate" in out2, "v1 phase3-hybrid-gate PASS line")

    if fails:
        print("FAIL phase4_thick_hybrid_gate", fails)
        return 1
    print("PASS phase4_thick_hybrid_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
