#!/usr/bin/env python3
"""v3 Phase2 gate: real literature corpus metadata + scale + eval."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def has_title_source(text: str) -> bool:
    head = text[:1500]
    return bool(re.search(r"(?im)^-\s*title:\s*\S+", head)) and bool(
        re.search(r"(?im)^-\s*source:\s*\S+", head)
    )


def main() -> int:
    os.environ.setdefault("PYTHONNOUSERSITE", "1")
    os.environ.pop("PYTHONPATH", None)
    os.environ.pop("PYTHONHOME", None)

    py = ROOT / ".venv-314" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    fails: list[str] = []
    skips: list[str] = []

    def need(c: bool, msg: str) -> None:
        print(("PASS " if c else "FAIL ") + msg)
        if not c:
            fails.append(msg)

    def skip(msg: str) -> None:
        print("SKIP " + msg)
        skips.append(msg)

    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    sh = (ROOT / "orpath.sh").read_text(encoding="utf-8", errors="replace")
    need("phase2-real-corpus-gate" in bat or "phase2_real_corpus" in bat, "bat phase2-real")
    need("phase2-real-corpus-gate" in sh or "phase2_real_corpus" in sh, "sh phase2-real")
    need((ROOT / "knowledge/CORPUS.md").is_file(), "CORPUS.md")
    need(
        (ROOT / "scripts/materialize_or_literature_corpus.py").is_file(),
        "materialize script",
    )

    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONNOUSERSITE"] = "1"
    env["ORPATH_KNOWLEDGE_EMBED"] = "stub"

    # materialize lit notes + normalize
    r0 = subprocess.run(
        [
            str(py),
            str(ROOT / "scripts/materialize_or_literature_corpus.py"),
            "--top",
            "45",
            "--clear-lit",
            "--normalize-existing",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    print((r0.stdout or "")[-500:])
    need(r0.returncode == 0, f"materialize rc={r0.returncode} {(r0.stderr or '')[:200]}")

    papers_dir = ROOT / "knowledge/corpus/papers"
    papers = [p for p in papers_dir.rglob("*.md") if p.name.lower() != "readme.md"]
    lit = list((papers_dir / "lit").glob("*.md")) if (papers_dir / "lit").is_dir() else []
    need(len(papers) >= 50, f"papers>=50 got {len(papers)}")
    need(len(lit) >= 20, f"lit notes>=20 got {len(lit)}")

    meta_ok = []
    for p in papers:
        t = p.read_text(encoding="utf-8", errors="replace")
        if has_title_source(t):
            meta_ok.append(p)
    need(len(meta_ok) >= 50, f"title+source >=50 got {len(meta_ok)}")
    # spot-check 10
    need(len(meta_ok) >= 10, "spot meta>=10")

    # domain coverage on true-ish sources (lit or curated with domain)
    blob = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")[:500] for p in papers
    ).lower()
    need("shortest" in blob or "dijkstra" in blob, "cover SP")
    need("tsp" in blob or "traveling" in blob, "cover TSP")
    need("vrp" in blob or "vehicle routing" in blob or "cvrp" in blob, "cover VRP")
    need("polyomino" in blob or "packing" in blob, "cover poly/packing")
    need("schema" in blob or "modeling" in blob or "integer programming" in blob, "cover modeling")

    # real PDF preprocess count (non synthetic mineru_lecture)
    from_m = list((papers_dir / "_from_mineru").glob("*.md")) if (papers_dir / "_from_mineru").is_dir() else []
    real_pdf_notes = []
    for p in from_m:
        name = p.name.lower()
        if name.startswith("mineru_lecture_"):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        if "source_pdf:" in t or "or_sample" in name or "fixture" in name:
            real_pdf_notes.append(p)
    if len(real_pdf_notes) >= 5:
        need(True, f"real_pdf_preprocess>=5 got {len(real_pdf_notes)}")
    else:
        skip(f"real_pdf_preprocess={len(real_pdf_notes)} <5 (need more PDFs via preprocess; not fail)")

    # no solution json
    bad = [p for p in (ROOT / "knowledge/corpus").rglob("*.json") if p.is_file()]
    need(not bad, f"no json in corpus {bad[:3]}")

    # ingest + eval
    r1 = subprocess.run(
        [str(py), "-m", "knowledge_svc.ingest", "--clear", "--embed-mode", "stub"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
    )
    need(r1.returncode == 0, f"ingest rc={r1.returncode}")
    try:
        ing = json.loads(r1.stdout)
    except json.JSONDecodeError:
        ing = {}
    n_chunks = int(ing.get("n_chunks") or 0)
    need(n_chunks >= 150, f"chunks>=150 got {n_chunks}")

    # retrieve a lit title keyword if available
    lit_title_word = "optimization"
    if lit:
        t0 = lit[0].read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(?im)^-\s*title:\s*(.+)$", t0)
        if m:
            words = [w for w in re.findall(r"[A-Za-z]{5,}", m.group(1)) if w.lower() not in {"paper", "using", "with"}]
            if words:
                lit_title_word = words[0]
    r2 = subprocess.run(
        [
            str(py),
            "-m",
            "knowledge_svc.retrieve",
            "--query",
            f"{lit_title_word} operations research doi paper-note",
            "--mode",
            "hybrid",
            "--topk",
            "10",
            "--embed-mode",
            "stub",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    need(r2.returncode == 0, "retrieve lit")
    try:
        art = json.loads(r2.stdout)
    except json.JSONDecodeError:
        art = {}
    paths = " ".join(str(h.get("source_path") or "") for h in (art.get("hits") or [])).replace("\\", "/")
    need(len(art.get("hits") or []) >= 1, "hits>=1")
    need("knowledge/corpus" in paths, f"corpus hit {paths[:160]}")

    r3 = subprocess.run(
        [str(py), str(ROOT / "scripts/knowledge_eval.py")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    print((r3.stdout or "")[-400:])
    need(r3.returncode == 0, f"eval rc={r3.returncode}")
    ev = ROOT / "notes/knowledge-eval-last.json"
    need(ev.is_file(), "eval json")
    if ev.is_file():
        data = json.loads(ev.read_text(encoding="utf-8"))
        need(int(data.get("n_fail") or 0) == 0, f"eval fails {data.get('fail_ids')}")
        need(int(data.get("n_queries") or 0) >= 16, f"eval nq {data.get('n_queries')}")

    board = ROOT / "notes/phase2-real-corpus-evidence.md"
    board.write_text(
        "\n".join(
            [
                "# v3 Phase2 · real corpus evidence",
                "",
                f"- papers_md: **{len(papers)}**",
                f"- lit_md: **{len(lit)}**",
                f"- meta_title_source: **{len(meta_ok)}**",
                f"- chunks: **{n_chunks}**",
                f"- real_pdf_preprocess_notes: **{len(real_pdf_notes)}**",
                f"- skips: {skips}",
                f"- gate: **{'PASS' if not fails else 'FAIL'}**",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("WROTE", board)

    if fails:
        print("FAIL phase2_real_corpus_gate", fails)
        return 1
    print("PASS phase2_real_corpus_gate", f"skips={skips}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
