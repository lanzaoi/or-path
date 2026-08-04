#!/usr/bin/env python3
"""Phase 4 gate: allowlist export + lesson filter + knowledge-sync + hybrid hit skill/lesson paths."""
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

    allow = ROOT / "knowledge" / "export_allowlist.txt"
    need(allow.is_file(), "export_allowlist.txt exists")
    text = allow.read_text(encoding="utf-8") if allow.is_file() else ""
    need("or-numbers-truth" in text, "allowlist has or-numbers-truth")

    # dirty lesson must be rejected
    dirty = ROOT / "knowledge" / "lessons" / "_phase4_reject_test.json"
    dirty.write_text(
        json.dumps(
            {
                "id": "bad_obj",
                "schema": "orpath.lesson.v1",
                "summary": "should reject",
                "objective": 42,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    wrong_schema = ROOT / "knowledge" / "lessons" / "_phase4_wrong_schema.json"
    wrong_schema.write_text(
        json.dumps({"id": "ws", "schema": "other", "summary": "no"}, indent=2) + "\n",
        encoding="utf-8",
    )

    try:
        r = subprocess.run(
            [str(py), str(ROOT / "scripts" / "export_agent_knowledge_corpus.py"), "--clear-exports"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        need(r.returncode == 0, f"export rc0 got {r.returncode}")
        payload = json.loads(r.stdout)
        need(payload.get("allowlist_source") or payload.get("allowlist_skills"), "export reports allowlist")
        sk = payload.get("skills") or {}
        written_sk = sk.get("written") if isinstance(sk, dict) else sk
        if isinstance(written_sk, list):
            need(any("or-numbers-truth" in str(x) for x in written_sk), "exported numbers-truth skill")
        les = payload.get("lessons") or {}
        skipped = les.get("skipped") if isinstance(les, dict) else []
        reasons = " ".join(json.dumps(s) for s in (skipped or []))
        need("forbidden_top_key:objective" in reasons or "objective" in reasons, f"dirty lesson skipped: {reasons[:200]}")
        need("schema_not_" in reasons or "wrong_schema" in reasons or "schema" in reasons, "wrong schema skipped")
        # written lessons should not include bad files
        written_le = les.get("written") if isinstance(les, dict) else []
        need(not any("phase4_reject" in str(x) for x in (written_le or [])), "no dirty lesson written")

        # ingest
        r2 = subprocess.run(
            [str(py), "-m", "knowledge_svc.ingest", "--clear"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        need(r2.returncode == 0, f"ingest rc0 {r2.returncode}")

        # hybrid queries
        def hits_for(q: str) -> list[dict]:
            r3 = subprocess.run(
                [str(py), "-m", "knowledge_svc.retrieve", "--query", q, "--mode", "hybrid", "--topk", "8"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if r3.returncode != 0:
                return []
            try:
                art = json.loads(r3.stdout)
            except json.JSONDecodeError:
                i = r3.stdout.find("{")
                art = json.loads(r3.stdout[i:]) if i >= 0 else {}
            return list(art.get("hits") or [])

        h1 = hits_for("objective only from solve validate numbers truth")
        paths1 = " ".join(str(h.get("source_path") or "") for h in h1).replace("\\", "/")
        need(len(h1) >= 1, "query numbers hits>=1")
        need(
            "corpus/skills" in paths1 or "skill-or-numbers" in paths1 or "numbers_truth" in paths1 or "validate_recompute" in paths1,
            f"numbers-related path {paths1[:120]}",
        )

        h2 = hits_for("polyomino_cover CP-SAT lesson")
        paths2 = " ".join(str(h.get("source_path") or "") for h in h2).replace("\\", "/")
        need(len(h2) >= 1, "query poly hits>=1")
        need(
            "lesson" in paths2 or "polyomino" in paths2 or "corpus/lessons" in paths2 or "corpus/papers" in paths2,
            f"poly path {paths2[:120]}",
        )

        # no solution json in corpus
        bad = [p for p in (ROOT / "knowledge" / "corpus").rglob("*.json") if p.is_file()]
        need(not bad, f"no json in corpus {bad}")

        # skill runtime path still .pi
        need((ROOT / ".pi" / "skills" / "or-numbers-truth" / "SKILL.md").is_file(), "runtime skill file remains")

        # bat/sh knowledge-sync label
        bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
        sh = (ROOT / "orpath.sh").read_text(encoding="utf-8", errors="replace")
        need("knowledge-sync" in bat, "bat knowledge-sync")
        need("knowledge-sync" in sh, "sh knowledge-sync")

    finally:
        for p in (dirty, wrong_schema):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass

    if fails:
        print("FAIL phase4_knowledge_sync_gate", fails)
        return 1
    print("PASS phase4_knowledge_sync_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
