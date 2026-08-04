#!/usr/bin/env python3
"""Phase 5 (v2 thick) rollup gate: mineru + embed + scale + thick-hybrid + docs/closeout."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, env: dict, timeout: int = 420) -> tuple[int, str]:
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
    env.setdefault("ORPATH_KNOWLEDGE_EMBED", "stub")

    fails: list[str] = []

    def need(c: bool, msg: str) -> None:
        print(("PASS " if c else "FAIL ") + msg, flush=True)
        if not c:
            fails.append(msg)

    # --- static ---
    for rel in (
        "docs/archive/closeouts/knowledge-rag-v2-thick-closeout.md",
        "docs/archive/plans/2026-08-04_knowledge-rag-v2-thick.md",
        "scripts/phase1_mineru_gate.py",
        "scripts/phase2_embed_gate.py",
        "scripts/phase3_scale_gate.py",
        "scripts/phase4_thick_hybrid_gate.py",
        "scripts/phase5_thick_knowledge_gate.py",
        "knowledge/inbox_pdf/README.md",
        "knowledge/CORPUS.md",
        "knowledge/eval_queries.md",
        "knowledge/export_allowlist.txt",
    ):
        need((ROOT / rel).is_file(), f"file:{rel}")

    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    sh = (ROOT / "orpath.sh").read_text(encoding="utf-8", errors="replace")
    need("phase5-thick-gate" in bat or "phase5_thick" in bat, "bat phase5-thick")
    need("phase5-thick-gate" in sh or "phase5_thick" in sh, "sh phase5-thick")
    need("thick-hybrid-gate" in bat and "knowledge-preprocess" in bat, "bat thick+preprocess")

    orpath = (ROOT / "ORPATH.md").read_text(encoding="utf-8", errors="replace")
    need("phase5-thick" in orpath or "thick-hybrid-gate" in orpath, "ORPATH thick cmds")
    need("inbox_pdf" in orpath or "knowledge-preprocess" in orpath, "ORPATH pdf path")
    arch = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8", errors="replace")
    need("thick-hybrid" in arch or "embed_mode" in arch, "ARCHITECTURE thick/embed")
    specs = (ROOT / "specs" / "knowledge-and-retrieval.md").read_text(encoding="utf-8", errors="replace")
    need("embed_mode" in specs or "ORPATH_KNOWLEDGE_EMBED" in specs, "specs embed")
    need("MinerU" in specs or "mineru" in specs or "inbox" in specs.lower(), "specs mineru/upstream")

    closeout = (ROOT / "docs/archive/closeouts/knowledge-rag-v2-thick-closeout.md").read_text(
        encoding="utf-8", errors="replace"
    )
    need("CLOSED" in closeout and "PASS" in closeout, "closeout CLOSED PASS")
    need("完成度" in closeout or "completion" in closeout.lower(), "closeout completion table")
    # no promotional fine-tune
    tl = closeout.lower()
    promo = ("we fine-tune" in tl) or ("rag 训练模型" in tl)
    if "禁止" in closeout:
        promo = False
    need(not promo, "closeout no train promo")

    # --- subgates ---
    skip_thick = os.environ.get("ORPATH_PHASE5_SKIP_THICK", "").strip() in {"1", "true", "yes"}

    print("--- phase1_mineru_gate ---", flush=True)
    rc, out = run([str(py), str(ROOT / "scripts/phase1_mineru_gate.py")], env=env, timeout=180)
    need(rc == 0 and "PASS phase1_mineru_gate" in out, f"phase1 rc={rc}")

    print("--- phase2_embed_gate ---", flush=True)
    rc, out = run([str(py), str(ROOT / "scripts/phase2_embed_gate.py")], env=env, timeout=400)
    need(rc == 0 and "PASS phase2_embed_gate" in out, f"phase2 rc={rc}")

    print("--- phase3_scale_gate ---", flush=True)
    rc, out = run([str(py), str(ROOT / "scripts/phase3_scale_gate.py")], env=env, timeout=300)
    need(rc == 0 and "PASS phase3_scale_gate" in out, f"phase3 rc={rc}")

    print("--- knowledge_eval ---", flush=True)
    rc, out = run([str(py), str(ROOT / "scripts/knowledge_eval.py")], env=env, timeout=180)
    need(rc == 0 and "PASS knowledge_eval" in out, f"eval rc={rc}")
    ev = ROOT / "notes/knowledge-eval-last.json"
    need(ev.is_file(), "eval json")
    if ev.is_file():
        data = json.loads(ev.read_text(encoding="utf-8"))
        need(int(data.get("n_fail") or 0) == 0, f"eval fails {data.get('fail_ids')}")
        need(int(data.get("n_queries") or 0) >= 12, f"eval nq {data.get('n_queries')}")

    if skip_thick:
        print("SKIP thick-hybrid (ORPATH_PHASE5_SKIP_THICK=1)", flush=True)
        need(
            (ROOT / "notes/thick-hybrid-evidence.md").is_file()
            and (ROOT / "notes/thick-hybrid-sp-retrieval.json").is_file(),
            "preexisting thick evidence required when skip",
        )
    else:
        print("--- phase4_thick_hybrid_gate ---", flush=True)
        rc, out = run(
            [str(py), str(ROOT / "scripts/phase4_thick_hybrid_gate.py")],
            env=env,
            timeout=500,
        )
        print(out[-600:], flush=True)
        need(rc == 0 and "PASS phase4_thick_hybrid_gate" in out, f"phase4 rc={rc}")

    # claim ladder snapshot
    papers = list((ROOT / "knowledge/corpus/papers").rglob("*.md"))
    mineru = list((ROOT / "knowledge/corpus/papers/_from_mineru").glob("*.md"))
    ladder = {
        "rag_for_pi": True,
        "not_fine_tune": True,
        "optima_solve_validate_only": True,
        "mineru_preprocess_path": True,
        "embed_mode_live_or_stub": True,
        "papers_count": len(papers),
        "mineru_md_count": len(mineru),
        "thick_hybrid_slug": "thick-hybrid-sp",
        "no_rag_web_ui": True,
        "cognee_not_main": True,
    }
    lp = ROOT / "notes/knowledge-rag-v2-claim-ladder.json"
    lp.write_text(json.dumps(ladder, indent=2) + "\n", encoding="utf-8")
    need(lp.is_file(), "claim ladder written")
    need(len(papers) >= 40 and len(mineru) >= 10, f"scale papers={len(papers)} mineru={len(mineru)}")

    board = ROOT / "notes/phase5-thick-evidence.md"
    board.write_text(
        "\n".join(
            [
                "# Phase 5 · Knowledge RAG v2 thick evidence",
                "",
                "- closeout: `docs/archive/closeouts/knowledge-rag-v2-thick-closeout.md`",
                "- claim ladder: `notes/knowledge-rag-v2-claim-ladder.json`",
                "- thick: `notes/thick-hybrid-evidence.md`",
                "- eval: `notes/knowledge-eval-last.json`",
                f"- papers: {len(papers)} · mineru_md: {len(mineru)}",
                f"- gate: **{'PASS' if not fails else 'FAIL'}**",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("WROTE", board, flush=True)

    if fails:
        print("FAIL phase5_thick_knowledge_gate", fails, flush=True)
        return 1
    print("PASS phase5_thick_knowledge_gate", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
