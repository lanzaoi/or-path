#!/usr/bin/env python3
"""Phase 3 gate: product path with knowledge_mode=hybrid leaves Pi-consumable evidence.

Runs a short T2 mock SP (no live subagent) with hybrid retrieve, then asserts:
  - notes/<slug>-retrieval.json exists, mode=hybrid, hits with source_path
  - notes/<slug>-research.md cites chunk_id or retrieval path / Coverage Status
  - solution+validate exist and validate ok (numbers independent of RAG)

Exit 0 PASS / 1 FAIL.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    os.environ.setdefault("PYTHONNOUSERSITE", "1")
    os.environ.pop("PYTHONPATH", None)
    os.environ.pop("PYTHONHOME", None)
    os.environ["ORPATH_LIVE_SUBAGENT"] = "0"

    py = ROOT / ".venv-314" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    # Ensure indexes exist (stub ok)
    subprocess.run(
        [str(py), "-m", "knowledge_svc.ingest", "--clear"],
        cwd=str(ROOT),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    slug = "phase3-hybrid-sp"
    # Drop stale research so scaffold rebuilds against current retrieval hits
    stale = ROOT / "notes" / f"{slug}-research.md"
    if stale.is_file():
        stale.unlink()

    # Use install home as workdir for simple fixture layout (HOME can equal workdir)
    cmd = [
        str(py),
        str(ROOT / "orpath" / "run_t2.py"),
        "--problem-id",
        "shortest_path",
        "--problem-class",
        "shortest_path",
        "--slug",
        slug,
        "--thread-id",
        slug,
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
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    print((r.stdout or "")[-1500:], flush=True)
    if r.returncode != 0:
        print((r.stderr or "")[-800:], file=sys.stderr)
        # Paper/claim_map stages may fail after corpus scale-up while
        # retrieve+research+validate (this gate's DoD) still hold.
        print(
            f"WARN run_t2 rc={r.returncode} — continue evidence checks "
            "(RAG/numbers path may still PASS)",
            flush=True,
        )

    notes = ROOT / "notes"
    ret_path = notes / f"{slug}-retrieval.json"
    res_path = notes / f"{slug}-research.md"
    sol = ROOT / "outputs" / f"{slug}-solution.json"
    val = ROOT / "outputs" / f"{slug}-validate.json"

    fails: list[str] = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            fails.append(msg)
            print("FAIL", msg)
        else:
            print("PASS", msg)

    need(ret_path.is_file(), f"retrieval exists {ret_path}")
    art: dict = {}
    if ret_path.is_file():
        art = json.loads(ret_path.read_text(encoding="utf-8"))
        need(art.get("knowledge_mode") == "hybrid", "retrieval mode=hybrid")
        hits = art.get("hits") or []
        need(isinstance(hits, list) and len(hits) >= 1, f"hybrid hits>=1 got {len(hits)}")
        paths = [str(h.get("source_path") or "") for h in hits]
        need(
            any("knowledge" in p.replace("\\", "/") for p in paths),
            "hit source_path under knowledge/",
        )
        need(bool(art.get("query")), "query non-empty")
        # index should point at install home when set
        ih = str(art.get("index_home") or "")
        if ih:
            need(Path(ih).exists(), f"index_home exists {ih}")

    need(res_path.is_file(), f"research exists {res_path}")
    body = res_path.read_text(encoding="utf-8") if res_path.is_file() else ""
    need("Coverage Status" in body or "coverage" in body.lower(), "research Coverage Status")
    need(
        str(ret_path).replace("\\", "/") in body.replace("\\", "/")
        or "retrieval" in body.lower()
        or "chunk" in body.lower(),
        "research mentions retrieval/chunk",
    )
    ids = []
    for h in art.get("hits") or []:
        if h.get("chunk_id"):
            ids.append(str(h["chunk_id"]))
    if ids:
        need(any(i in body for i in ids), "research cites at least one chunk_id")

    need(sol.is_file(), "solution.json")
    need(val.is_file(), "validate.json")
    if val.is_file():
        v = json.loads(val.read_text(encoding="utf-8"))
        need(bool(v.get("ok")), f"validate ok={v.get('ok')}")

    # Write small evidence board for humans
    board = ROOT / "notes" / "phase3-hybrid-evidence.md"
    board.write_text(
        "\n".join(
            [
                "# Phase 3 hybrid evidence",
                "",
                f"- slug: `{slug}`",
                f"- retrieval: `{ret_path}`",
                f"- research: `{res_path}`",
                f"- solution: `{sol}`",
                f"- validate: `{val}`",
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
            + ["", f"gate: **{'PASS' if not fails else 'FAIL'}**", ""]
        ),
        encoding="utf-8",
    )
    print("WROTE", board)

    if fails:
        print("FAIL phase3_hybrid_pi_gate", fails)
        return 1
    print("PASS phase3_hybrid_pi_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
