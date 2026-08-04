#!/usr/bin/env python3
"""Phase 1 gate: MinerU preprocess PDF→md→corpus + manifest (offline fixture OK)."""
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

    # wiring
    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    sh = (ROOT / "orpath.sh").read_text(encoding="utf-8", errors="replace")
    need("knowledge-mineru" in bat and "knowledge-preprocess" in bat, "bat mineru/preprocess")
    need("knowledge-mineru" in sh and "knowledge-preprocess" in sh, "sh mineru/preprocess")
    need((ROOT / "knowledge" / "inbox_pdf" / "README.md").is_file(), "inbox_pdf README")

    # preprocess offline fixture only (avoid scanning huge inbox)
    fix = ROOT / "knowledge" / "inbox_pdf" / "fixture_or_mineru_phase1.pdf"
    if not fix.is_file():
        # create fixture then process it
        subprocess.run(
            [str(py), "-m", "knowledge_svc.mineru_client", "--ensure-fixture", "--no-cloud"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    r = subprocess.run(
        [
            str(py),
            "-m",
            "knowledge_svc.mineru_client",
            "--pdf",
            str(fix if fix.is_file() else ROOT / "knowledge/inbox_pdf/fixture_or_mineru_phase1.pdf"),
            "--offline-fixture",
            "--no-cloud",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    # if single-pdf path failed, fall back to preprocess offline
    if r.returncode != 0:
        r = subprocess.run(
            [
                str(py),
                "-m",
                "knowledge_svc.mineru_client",
                "--preprocess",
                "--offline-fixture",
                "--no-cloud",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    out = (r.stdout or "") + (r.stderr or "")
    print(out[-1200:])
    need(r.returncode == 0, f"preprocess rc0 got {r.returncode}")
    need("MINERU_API_TOKEN" not in out or "token_masked" in out, "no raw token dump required")
    # must not print long secrets — if token in env, ensure not full echo
    tok = os.environ.get("MINERU_API_TOKEN") or ""
    if len(tok) > 12:
        need(tok not in out, "full token not in output")

    try:
        payload = json.loads(r.stdout)
    except json.JSONDecodeError:
        payload = {}
        need(False, "preprocess stdout json")

    # single-pdf vs batch preprocess shapes
    corpus_md = ""
    if payload.get("results"):
        corpus_md = str((payload.get("results") or [{}])[0].get("corpus_md") or "")
        n_ok = int(payload.get("n_ok") or 0)
    else:
        # process_pdf result
        corpus_md = str(payload.get("corpus_md") or "")
        n_ok = 1 if payload.get("status") == "OK" and corpus_md else 0
    need(n_ok >= 1, f"n_ok>=1 got {n_ok}")
    need(
        "corpus/papers" in corpus_md.replace("\\", "/") or "_from_mineru" in corpus_md,
        f"corpus_md {corpus_md}",
    )

    md_path = ROOT / corpus_md if corpus_md and not Path(corpus_md).is_absolute() else Path(corpus_md)
    if not md_path.is_file() and corpus_md:
        md_path = ROOT / Path(corpus_md)
    need(md_path.is_file(), f"md exists {md_path}")
    if md_path.is_file():
        text = md_path.read_text(encoding="utf-8", errors="replace")
        need("paper-mineru" in text or "Dijkstra" in text or "dijkstra" in text.lower(), "md content")

    man = ROOT / "notes" / "mineru-last.json"
    need(man.is_file(), "manifest notes/mineru-last.json")
    if man.is_file():
        m = json.loads(man.read_text(encoding="utf-8"))
        need(m.get("schema") == "orpath.mineru_manifest.v1", "manifest schema")
        n_ok = m.get("n_ok")
        if n_ok is None and isinstance(m.get("result"), dict):
            n_ok = 1 if m["result"].get("status") == "OK" else 0
        need(int(n_ok or 0) >= 1, "manifest n_ok")

    # Prefer existing indexes; only stub-ingest if retrieve fails (avoid full --clear on huge corpus)
    env_ing = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env_ing["PYTHONNOUSERSITE"] = "1"
    env_ing["ORPATH_KNOWLEDGE_EMBED"] = "stub"
    r2_out = ROOT / "notes" / "_phase1_mineru_retrieve.json"
    r2 = subprocess.run(
        [
            str(py),
            "-m",
            "knowledge_svc.retrieve",
            "--query",
            "Dijkstra networkx shortest path mineru fixture",
            "--mode",
            "hybrid",
            "--topk",
            "8",
            "--embed-mode",
            "stub",
            "--out",
            str(r2_out),
        ],
        cwd=str(ROOT),
        env=env_ing,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    if r2.returncode != 0 or not r2_out.is_file():
        # light rebuild without --clear first (incremental)
        r_ing = subprocess.run(
            [str(py), "-m", "knowledge_svc.ingest", "--embed-mode", "stub", "--no-incremental"],
            cwd=str(ROOT),
            env=env_ing,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=420,
        )
        need(r_ing.returncode == 0, f"ingest stub rc0 {r_ing.returncode}")
        r2 = subprocess.run(
            [
                str(py),
                "-m",
                "knowledge_svc.retrieve",
                "--query",
                "Dijkstra networkx shortest path mineru fixture",
                "--mode",
                "hybrid",
                "--topk",
                "8",
                "--embed-mode",
                "stub",
                "--out",
                str(r2_out),
            ],
            cwd=str(ROOT),
            env=env_ing,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
    need(r2.returncode == 0, f"retrieve rc0 {r2.returncode}")
    try:
        if r2_out.is_file():
            art = json.loads(r2_out.read_text(encoding="utf-8"))
        else:
            art = json.loads(r2.stdout)
    except json.JSONDecodeError:
        i = (r2.stdout or "").find("{")
        art = json.loads(r2.stdout[i:]) if i >= 0 else {}
    hits = art.get("hits") or []
    paths = " ".join(str(h.get("source_path") or "") for h in hits).replace("\\", "/")
    need(len(hits) >= 1, f"hits>=1 got {len(hits)}")
    need(
        "_from_mineru" in paths or "fixture_or_mineru" in paths or "corpus/papers" in paths,
        f"hit path {paths[:160]}",
    )

    # single-pdf CLI regression (same fixture)
    fix = ROOT / "knowledge" / "inbox_pdf" / "fixture_or_mineru_phase1.pdf"
    if not fix.is_file():
        fix = ROOT / "knowledge" / "inbox_pdf" / "fixtures" / "or_sample_01.pdf"
    need(fix.is_file(), "fixture pdf present after preprocess")
    r3 = subprocess.run(
        [
            str(py),
            "-m",
            "knowledge_svc.mineru_client",
            "--pdf",
            str(fix),
            "--offline-fixture",
            "--no-cloud",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    need(r3.returncode == 0, f"pdf cli rc0 {r3.returncode}")

    if fails:
        print("FAIL phase1_mineru_gate", fails)
        return 1
    print("PASS phase1_mineru_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
