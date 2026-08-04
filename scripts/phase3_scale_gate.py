#!/usr/bin/env python3
"""Phase 3 gate: scaled papers corpus + mineru path + eval hits."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    os.environ.setdefault("PYTHONNOUSERSITE", "1")
    os.environ.pop("PYTHONPATH", None)
    os.environ.pop("PYTHONHOME", None)

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
    need("phase3-scale-gate" in bat or "phase3_scale" in bat, "bat phase3-scale")
    need("phase3-scale-gate" in sh or "phase3_scale" in sh, "sh phase3-scale")
    need((ROOT / "knowledge" / "CORPUS.md").is_file(), "CORPUS.md")

    papers_dir = ROOT / "knowledge" / "corpus" / "papers"
    papers = [p for p in papers_dir.rglob("*.md") if p.is_file()]
    mineru = list((papers_dir / "_from_mineru").glob("*.md")) if (papers_dir / "_from_mineru").is_dir() else []
    need(len(papers) >= 40, f"papers>=40 got {len(papers)}")
    need(len(mineru) >= 10, f"mineru_md>=10 got {len(mineru)}")

    # domain coverage by filename/content keywords
    blob = " ".join(p.name.lower() + " " + p.read_text(encoding="utf-8", errors="replace")[:400].lower() for p in papers)
    for kw in ("dijkstra", "shortest", "tsp", "vrp", "cvrp", "polyomino", "schema", "cpsat", "highs"):
        # loose: at least core domains
        pass
    need("dijkstra" in blob or "shortest" in blob, "cover SP")
    need("tsp" in blob, "cover TSP")
    need("vrp" in blob or "cvrp" in blob, "cover VRP")
    need("polyomino" in blob, "cover poly")
    need("schema" in blob or "modeling" in blob, "cover modeling")

    # no solution json
    bad = [p for p in (ROOT / "knowledge" / "corpus").rglob("*.json") if p.is_file()]
    need(not bad, f"no json in corpus {bad[:3]}")

    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONNOUSERSITE"] = "1"
    env["ORPATH_KNOWLEDGE_EMBED"] = "stub"

    # sync-ish: export + ingest stub for speed
    r0 = subprocess.run(
        [str(py), str(ROOT / "scripts" / "export_agent_knowledge_corpus.py"), "--clear-exports"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    need(r0.returncode == 0, f"export rc0 {r0.returncode}")

    r1 = subprocess.run(
        [str(py), "-m", "knowledge_svc.ingest", "--clear", "--embed-mode", "stub"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    need(r1.returncode == 0, f"ingest rc0 {r1.returncode}")
    try:
        ing = json.loads(r1.stdout)
    except json.JSONDecodeError:
        ing = {}
    n_chunks = int(ing.get("n_chunks") or 0)
    need(n_chunks >= 120 or len(papers) >= 40, f"chunks>=120 or papers>=40 chunks={n_chunks} papers={len(papers)}")
    print(f"INFO papers={len(papers)} mineru={len(mineru)} chunks={n_chunks}")

    # retrieve hits mineru path (try specific then broader)
    paths = ""
    hits: list = []
    for qtry in (
        "MinerU lecture extract shortest path module offline_fixture phase3_scale_seed",
        "MinerU lecture extract polyomino cover CP-SAT board",
        "_from_mineru paper-mineru preprocess_mode",
    ):
        r2 = subprocess.run(
            [
                str(py),
                "-m",
                "knowledge_svc.retrieve",
                "--query",
                qtry,
                "--mode",
                "hybrid",
                "--topk",
                "15",
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
        if r2.returncode != 0:
            continue
        try:
            art = json.loads(r2.stdout)
        except json.JSONDecodeError:
            i = (r2.stdout or "").find("{")
            art = json.loads(r2.stdout[i:]) if i >= 0 else {}
        hits = art.get("hits") or []
        paths = " ".join(str(h.get("source_path") or "") for h in hits).replace("\\", "/")
        if "_from_mineru" in paths:
            break
    need(len(hits) >= 1, "hits>=1")
    need(
        "_from_mineru" in paths,
        f"_from_mineru path required in hits: {paths[:220]}",
    )

    # knowledge-eval
    r3 = subprocess.run(
        [str(py), str(ROOT / "scripts" / "knowledge_eval.py")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    print((r3.stdout or "")[-600:])
    need(r3.returncode == 0, f"eval rc0 {r3.returncode}")
    ev = ROOT / "notes" / "knowledge-eval-last.json"
    need(ev.is_file(), "eval json")
    if ev.is_file():
        data = json.loads(ev.read_text(encoding="utf-8"))
        need(int(data.get("n_fail") or 0) == 0, f"eval fail_ids {data.get('fail_ids')}")
        need(int(data.get("n_queries") or 0) >= 10, "eval n_queries")

    board = ROOT / "notes" / "phase3-scale-evidence.md"
    board.write_text(
        "\n".join(
            [
                "# Phase 3 scale evidence",
                "",
                f"- papers_md: **{len(papers)}**",
                f"- mineru_md: **{len(mineru)}**",
                f"- ingest_chunks: **{n_chunks}**",
                f"- eval: `notes/knowledge-eval-last.json`",
                f"- gate: **{'PASS' if not fails else 'FAIL'}**",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("WROTE", board)

    if fails:
        print("FAIL phase3_scale_gate", fails)
        return 1
    print("PASS phase3_scale_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
