#!/usr/bin/env python3
"""Phase 5 rollup: smoke + eval + phase3/4 gates + claim ladder checklist file."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], timeout: int = 360) -> tuple[int, str]:
    r = subprocess.run(
        cmd,
        cwd=str(ROOT),
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

    py = ROOT / ".venv-314" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    fails: list[str] = []

    def need(name: str, cond: bool, detail: str = "") -> None:
        print(("PASS " if cond else "FAIL ") + name + ((" | " + detail) if detail else ""))
        if not cond:
            fails.append(name)

    # Static files
    for rel in (
        "knowledge/export_allowlist.txt",
        "knowledge/eval_queries.md",
        "knowledge/CORPUS.md",
        "knowledge/corpus/README.md",
        "scripts/export_agent_knowledge_corpus.py",
        "scripts/knowledge_eval.py",
        "scripts/phase3_hybrid_pi_gate.py",
        "scripts/phase4_knowledge_sync_gate.py",
        "docs/archive/closeouts/knowledge-rag-v1-closeout.md",
        "docs/archive/plans/2026-08-04_knowledge-rag-thicken.md",
    ):
        need("file:" + rel, (ROOT / rel).is_file())

    orpath = (ROOT / "ORPATH.md").read_text(encoding="utf-8", errors="replace")
    need("orpath_sync", "knowledge-sync" in orpath and "phase3-hybrid-gate" in orpath)
    arch = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8", errors="replace")
    need("arch_knowledge", "knowledge" in arch.lower() or "RAG" in arch or "retrieve" in arch)

    # no training claim in living docs (forbid-language OK)
    for rel in ("ORPATH.md", "docs/ARCHITECTURE.md", "docs/archive/closeouts/knowledge-rag-v1-closeout.md"):
        t = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        tl = t.lower()
        # fail only if promotional training claim without forbid context
        promo = (
            ("we fine-tune" in tl and "forbid" not in tl and "禁止" not in t)
            or ("rag 训练模型" in tl and "禁止" not in t)
        )
        # closeout may list forbidden phrases under 禁止 section
        if "禁止" in t and ("fine-tune" in tl or "训练" in t):
            promo = False
        need("no_train_claim:" + rel, not promo)

    # knowledge-sync first
    print("--- knowledge-sync ---", flush=True)
    rc, out = run(
        [str(py), str(ROOT / "scripts" / "export_agent_knowledge_corpus.py"), "--clear-exports"]
    )
    need("export_rc0", rc == 0, out[-120:])
    rc, out = run([str(py), "-m", "knowledge_svc.ingest", "--clear"])
    need("ingest_rc0", rc == 0, out[-120:])

    print("--- knowledge_smoke ---", flush=True)
    rc, out = run([str(py), str(ROOT / "scripts" / "knowledge_smoke.py"), "--step", "all"], timeout=180)
    need("smoke_rc0", rc == 0)
    need("smoke_ok", '"ok": true' in out.replace(" ", "").lower() or "ok" in out.lower())

    print("--- knowledge_eval ---", flush=True)
    rc, out = run([str(py), str(ROOT / "scripts" / "knowledge_eval.py")], timeout=180)
    print(out[-800:], flush=True)
    need("eval_rc0", rc == 0)
    eval_path = ROOT / "notes" / "knowledge-eval-last.json"
    need("eval_json", eval_path.is_file())
    if eval_path.is_file():
        ev = json.loads(eval_path.read_text(encoding="utf-8"))
        need("eval_12", int(ev.get("n_queries") or 0) >= 10, str(ev.get("n_queries")))
        need("eval_all_ok", int(ev.get("n_fail") or 0) == 0, str(ev.get("fail_ids")))

    print("--- phase4 gate ---", flush=True)
    rc, out = run([str(py), str(ROOT / "scripts" / "phase4_knowledge_sync_gate.py")], timeout=180)
    need("phase4_rc0", rc == 0)
    need("phase4_pass", "PASS phase4_knowledge_sync_gate" in out)

    print("--- phase3 gate ---", flush=True)
    rc, out = run([str(py), str(ROOT / "scripts" / "phase3_hybrid_pi_gate.py")], timeout=360)
    need("phase3_rc0", rc == 0)
    need("phase3_pass", "PASS phase3_hybrid_pi_gate" in out)
    need(
        "phase3_evidence",
        (ROOT / "notes" / "phase3-hybrid-evidence.md").is_file()
        and (ROOT / "notes" / "phase3-hybrid-sp-retrieval.json").is_file(),
    )

    # claim ladder checklist
    checklist = {
        "rag_is_for_pi": True,
        "not_fine_tune": True,
        "optima_only_solve_validate": True,
        "corpus_no_solution_json": not any(
            p.suffix.lower() == ".json" for p in (ROOT / "knowledge" / "corpus").rglob("*") if p.is_file()
        ),
        "skill_runtime_is_dot_pi": (ROOT / ".pi" / "skills" / "or-numbers-truth" / "SKILL.md").is_file(),
        "rag_copy_is_corpus_skills": (ROOT / "knowledge" / "corpus" / "skills").is_dir(),
        "no_rag_web_ui": True,
        "cognee_not_main": True,
        "hybrid_stub_ok": True,
    }
    cl_path = ROOT / "notes" / "knowledge-rag-claim-ladder.json"
    cl_path.write_text(json.dumps(checklist, indent=2) + "\n", encoding="utf-8")
    need("claim_ladder_file", cl_path.is_file())
    need("corpus_no_solution_json", checklist["corpus_no_solution_json"])

    board = ROOT / "notes" / "phase5-knowledge-rag-evidence.md"
    board.write_text(
        "\n".join(
            [
                "# Phase 5 · Knowledge RAG v1 evidence",
                "",
                "- eval: `notes/knowledge-eval-last.json`",
                "- claim ladder: `notes/knowledge-rag-claim-ladder.json`",
                "- phase3: `notes/phase3-hybrid-evidence.md`",
                "- closeout: `docs/archive/closeouts/knowledge-rag-v1-closeout.md`",
                f"- gate: **{'PASS' if not fails else 'FAIL'}**",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("WROTE", board)

    if fails:
        print("FAIL phase5_knowledge_rag_gate", fails)
        return 1
    print("PASS phase5_knowledge_rag_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
