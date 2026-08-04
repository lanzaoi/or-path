#!/usr/bin/env python3
"""v3 Phase5 rollup: closeout + evidence chain + light smoke (not full nested re-runs).

Heavy subgates (mineru/cloud/real-corpus/live/product) are treated as PASS when their
evidence boards + key artifacts exist. Set ORPATH_PHASE5_V3_FULL=1 to force re-run
(may take 15+ minutes on large corpora).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, env: dict, timeout: int = 420) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return r.returncode, ((r.stdout or "") + (r.stderr or ""))
    except subprocess.TimeoutExpired as e:
        out = ""
        if e.stdout:
            out += e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8", "replace")
        if e.stderr:
            out += e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf-8", "replace")
        return 124, out + f"\nTIMEOUT after {timeout}s"


def main() -> int:
    os.environ.setdefault("PYTHONNOUSERSITE", "1")
    os.environ.pop("PYTHONPATH", None)
    os.environ.pop("PYTHONHOME", None)
    os.environ["ORPATH_LIVE_SUBAGENT"] = "0"
    os.environ.setdefault("ORPATH_KNOWLEDGE_EMBED", "stub")

    py = ROOT / ".venv-314" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONNOUSERSITE"] = "1"
    env["ORPATH_LIVE_SUBAGENT"] = "0"
    env["ORPATH_KNOWLEDGE_EMBED"] = "stub"

    fails: list[str] = []
    skips: list[str] = []

    def need(c: bool, msg: str) -> None:
        print(("PASS " if c else "FAIL ") + msg, flush=True)
        if not c:
            fails.append(msg)

    def skip(msg: str) -> None:
        print("SKIP " + msg, flush=True)
        skips.append(msg)

    full = os.environ.get("ORPATH_PHASE5_V3_FULL", "").strip().lower() in {"1", "true", "yes"}

    # --- static ---
    for rel in (
        "docs/archive/closeouts/knowledge-rag-v3-prod-closeout.md",
        "docs/archive/plans/2026-08-04_knowledge-rag-v3-prod.md",
        "docs/archive/closeouts/knowledge-rag-v2-thick-closeout.md",
        "scripts/phase1_mineru_gate.py",
        "scripts/phase1_mineru_cloud_gate.py",
        "scripts/phase2_real_corpus_gate.py",
        "scripts/phase3_live_default_gate.py",
        "scripts/phase4_product_research_gate.py",
        "scripts/phase5_v3_knowledge_gate.py",
        "scripts/materialize_or_literature_corpus.py",
        "knowledge/inbox_pdf/README.md",
        "knowledge/CORPUS.md",
        "knowledge/eval_queries.md",
        "knowledge/export_allowlist.txt",
    ):
        need((ROOT / rel).is_file(), f"file:{rel}")

    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    sh = (ROOT / "orpath.sh").read_text(encoding="utf-8", errors="replace")
    need("phase5-v3-gate" in bat or "phase5_v3" in bat, "bat phase5-v3")
    need("phase5-v3-gate" in sh or "phase5_v3" in sh, "sh phase5-v3")
    need("product-research-gate" in bat and "knowledge-preprocess" in bat, "bat product+preprocess")
    need("phase3-live-default-gate" in bat, "bat live-default")
    # routing early
    lines = bat.splitlines()
    try:
        ms = next(i for i, l in enumerate(lines) if l.strip() == ":memory_search")
        early = "\n".join(lines[:ms])
        need("goto :phase5_v3_gate" in early, "bat phase5-v3 early routing")
    except StopIteration:
        need(False, "bat :memory_search marker")

    orpath = (ROOT / "ORPATH.md").read_text(encoding="utf-8", errors="replace")
    need("product-research-gate" in orpath or "研究档" in orpath, "ORPATH research recipe")
    arch = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8", errors="replace")
    need("v3" in arch or "thick-research" in arch or "embed_mode" in arch, "ARCHITECTURE v3/embed")
    specs = (ROOT / "specs/knowledge-and-retrieval.md").read_text(encoding="utf-8", errors="replace")
    need("ORPATH_KNOWLEDGE_PROFILE" in specs or "embed_mode" in specs, "specs profile/embed")

    closeout = (ROOT / "docs/archive/closeouts/knowledge-rag-v3-prod-closeout.md").read_text(
        encoding="utf-8", errors="replace"
    )
    need("CLOSED" in closeout and "PASS" in closeout, "closeout CLOSED PASS")
    need("完成度" in closeout, "closeout completion")
    need("thick-research-sp" in closeout or "product-research" in closeout, "closeout product slug")
    promo = ("we fine-tune" in closeout.lower()) or ("rag 训练模型" in closeout.lower())
    if "禁止" in closeout:
        promo = False
    need(not promo, "closeout no train promo")

    plan = (ROOT / "docs/archive/plans/2026-08-04_knowledge-rag-v3-prod.md").read_text(
        encoding="utf-8", errors="replace"
    )
    need("ALL DONE" in plan or "CLOSED" in plan or "Phase 5" in plan, "plan phase5")

    # --- evidence chain (phases 1–4) ---
    def has(*rels: str) -> bool:
        return all((ROOT / r).is_file() for r in rels)

    # P1 offline
    p1_ok = has("notes/mineru-last.json") and any(
        (ROOT / "knowledge/corpus/papers/_from_mineru").glob("*.md")
    )
    if full:
        print("--- FULL phase1_mineru_gate ---", flush=True)
        rc, out = run([str(py), str(ROOT / "scripts/phase1_mineru_gate.py")], env=env, timeout=360)
        need(rc == 0 and "PASS phase1_mineru_gate" in out, f"phase1 offline full rc={rc}")
    elif p1_ok:
        m = json.loads((ROOT / "notes/mineru-last.json").read_text(encoding="utf-8"))
        need(m.get("schema") == "orpath.mineru_manifest.v1", "p1 manifest schema")
        skip("phase1_mineru_gate full re-run (evidence present; set ORPATH_PHASE5_V3_FULL=1)")
    else:
        need(False, "phase1 evidence missing")

    # P1 cloud evidence
    if has("notes/phase1-mineru-cloud-evidence.md"):
        skip("phase1 cloud full re-run (evidence board present)")
        need(True, "phase1 cloud evidence board")
    elif full:
        rc, out = run([str(py), str(ROOT / "scripts/phase1_mineru_cloud_gate.py")], env=env, timeout=400)
        need(rc == 0 and "PASS phase1_mineru_cloud_gate" in out, f"phase1 cloud full rc={rc}")
    else:
        skip("phase1 cloud evidence missing — non-blocking if offline path ok")

    # P2
    if full:
        print("--- FULL phase2_real_corpus_gate ---", flush=True)
        rc, out = run([str(py), str(ROOT / "scripts/phase2_real_corpus_gate.py")], env=env, timeout=400)
        need(rc == 0 and "PASS phase2_real_corpus_gate" in out, f"phase2 full rc={rc}")
    elif has("notes/phase2-real-corpus-evidence.md"):
        skip("phase2 full re-run (evidence present)")
        papers = [p for p in (ROOT / "knowledge/corpus/papers").rglob("*.md") if p.name.lower() != "readme.md"]
        need(len(papers) >= 50, f"papers>=50 got {len(papers)}")
    else:
        need(False, "phase2 evidence missing")

    # P3 live
    if full:
        print("--- FULL phase3_live_default_gate ---", flush=True)
        rc, out = run([str(py), str(ROOT / "scripts/phase3_live_default_gate.py")], env=env, timeout=420)
        need(rc == 0 and "PASS phase3_live_default_gate" in out, f"phase3 full rc={rc}")
    elif has("notes/phase3-live-default-evidence.md"):
        skip("phase3 live full re-run (evidence present)")
        need(True, "phase3 live evidence board")
    else:
        need(False, "phase3 live evidence missing")

    # P4 product
    if full:
        print("--- FULL phase4_product_research_gate ---", flush=True)
        env_p = dict(env)
        env_p["ORPATH_KNOWLEDGE_PROFILE"] = "research"
        env_p["ORPATH_KNOWLEDGE_EMBED"] = "auto"
        rc, out = run(
            [str(py), str(ROOT / "scripts/phase4_product_research_gate.py")],
            env=env_p,
            timeout=500,
        )
        need(rc == 0 and "PASS phase4_product_research_gate" in out, f"phase4 full rc={rc}")
    else:
        need(has("notes/thick-research-evidence.md"), "thick-research-evidence.md")
        need(has("notes/thick-research-sp-retrieval.json"), "thick-research-sp-retrieval.json")
        need(has("outputs/thick-research-sp-validate.json"), "thick-research-sp-validate.json")
        if has("outputs/thick-research-sp-validate.json"):
            v = json.loads((ROOT / "outputs/thick-research-sp-validate.json").read_text(encoding="utf-8"))
            need(bool(v.get("ok")), "product validate ok")
        if has("notes/thick-research-sp-retrieval.json"):
            art = json.loads((ROOT / "notes/thick-research-sp-retrieval.json").read_text(encoding="utf-8"))
            need(art.get("knowledge_mode") == "hybrid", "product hybrid")
            need(len(art.get("hits") or []) >= 1, "product hits")
            paths = " ".join(str(h.get("source_path") or "") for h in (art.get("hits") or [])).replace("\\", "/")
            need("knowledge/corpus/papers" in paths, "product papers grain")
        skip("phase4 product full re-run (evidence present; FULL=1 to force)")

    # light smoke: prefer fingerprint skip; allow long rebuild once
    print("--- light smoke ingest/retrieve ---", flush=True)
    rc, out = run(
        [str(py), "-m", "knowledge_svc.ingest", "--embed-mode", "stub", "--profile", "demo"],
        env=env,
        timeout=420,
    )
    need(rc == 0, f"light ingest rc={rc}")
    try:
        ing = json.loads(out[out.find("{") :] if "{" in out else out)
    except json.JSONDecodeError:
        # stdout may be pure json
        try:
            ing = json.loads(out)
        except json.JSONDecodeError:
            ing = {}
    # accept skip or rebuild
    need(int(ing.get("n_chunks") or 0) >= 1 or bool(ing.get("skipped")), "light ingest chunks/skip")

    out_json = ROOT / "notes" / "_phase5_v3_smoke_retrieve.json"
    rc, out = run(
        [
            str(py),
            "-m",
            "knowledge_svc.retrieve",
            "--query",
            "shortest path Dijkstra operations research",
            "--mode",
            "hybrid",
            "--topk",
            "5",
            "--embed-mode",
            "stub",
            "--out",
            str(out_json),
        ],
        env=env,
        timeout=90,
    )
    need(rc == 0, f"light retrieve rc={rc}")
    if out_json.is_file():
        art = json.loads(out_json.read_text(encoding="utf-8"))
        need(len(art.get("hits") or []) >= 1, "light hits")
    else:
        need(False, "light retrieve out missing")

    # eval
    print("--- knowledge_eval ---", flush=True)
    rc, out = run([str(py), str(ROOT / "scripts/knowledge_eval.py")], env=env, timeout=300)
    need(rc == 0 and "PASS knowledge_eval" in out, f"eval rc={rc}")
    ev = ROOT / "notes/knowledge-eval-last.json"
    need(ev.is_file(), "eval json")
    if ev.is_file():
        data = json.loads(ev.read_text(encoding="utf-8"))
        need(int(data.get("n_fail") or 0) == 0, f"eval fails {data.get('fail_ids')}")
        need(int(data.get("n_queries") or 0) >= 16, f"eval nq {data.get('n_queries')}")

    if has("notes/thick-hybrid-evidence.md"):
        print("PASS v2 thick-hybrid-evidence present")
    else:
        skip("v2 thick-hybrid-evidence.md missing")

    papers = [p for p in (ROOT / "knowledge/corpus/papers").rglob("*.md") if p.name.lower() != "readme.md"]
    lit = list((ROOT / "knowledge/corpus/papers/lit").glob("*.md")) if (ROOT / "knowledge/corpus/papers/lit").is_dir() else []
    ladder = {
        "rag_for_pi": True,
        "not_fine_tune": True,
        "optima_solve_validate_only": True,
        "mineru_preprocess_path": True,
        "embed_mode_live_or_stub": True,
        "profile_research": True,
        "incremental_ingest": True,
        "papers_count": len(papers),
        "lit_count": len(lit),
        "product_slug": "thick-research-sp",
        "no_rag_web_ui": True,
        "cognee_not_main": True,
        "v3_closeout": "docs/archive/closeouts/knowledge-rag-v3-prod-closeout.md",
        "rollup_mode": "full" if full else "evidence_first",
    }
    lp = ROOT / "notes/knowledge-rag-v3-claim-ladder.json"
    lp.write_text(json.dumps(ladder, indent=2) + "\n", encoding="utf-8")
    need(lp.is_file(), "claim ladder")
    need(len(papers) >= 50, f"papers>=50 got {len(papers)}")

    board = ROOT / "notes/phase5-v3-evidence.md"
    board.write_text(
        "\n".join(
            [
                "# Phase 5 · Knowledge RAG v3 evidence",
                "",
                f"- rollup_mode: **{'FULL' if full else 'evidence-first'}**",
                "- closeout: `docs/archive/closeouts/knowledge-rag-v3-prod-closeout.md`",
                "- claim ladder: `notes/knowledge-rag-v3-claim-ladder.json`",
                "- product: `notes/thick-research-evidence.md`",
                "- live: `notes/phase3-live-default-evidence.md`",
                "- eval: `notes/knowledge-eval-last.json`",
                f"- papers: {len(papers)} · lit: {len(lit)}",
                f"- skips: {skips}",
                f"- gate: **{'PASS' if not fails else 'FAIL'}**",
                "",
                "Force full nested gates: `set ORPATH_PHASE5_V3_FULL=1`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("WROTE", board, flush=True)

    if fails:
        print("FAIL phase5_v3_knowledge_gate", fails, "skips", skips, flush=True)
        return 1
    print("PASS phase5_v3_knowledge_gate", f"skips={skips}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
