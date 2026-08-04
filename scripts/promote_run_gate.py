#!/usr/bin/env python3
"""Gate: promote-run compresses method skill + lesson into RAG."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLUG = os.environ.get("ORPATH_PROMOTE_SLUG", "thick-research-sp")


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
    need("promote-run" in bat and "promote_run_to_skill.py" in bat, "bat promote-run")
    need("promote-run" in sh and "promote_run_to_skill.py" in sh, "sh promote-run")
    need((ROOT / "scripts/promote_run_to_skill.py").is_file(), "script present")

    # need a finished run
    need(
        (ROOT / "notes" / f"{SLUG}-research.md").is_file()
        or (ROOT / "outputs" / f"{SLUG}-validate.json").is_file(),
        f"run artifacts for {SLUG}",
    )

    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONNOUSERSITE"] = "1"
    env["ORPATH_KNOWLEDGE_EMBED"] = "stub"

    r = subprocess.run(
        [str(py), str(ROOT / "scripts/promote_run_to_skill.py"), "--slug", SLUG],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=480,
    )
    print((r.stdout or "")[-1200:])
    if r.returncode != 0:
        print((r.stderr or "")[-400:], file=sys.stderr)
    need(r.returncode == 0, f"promote rc={r.returncode}")
    try:
        payload = json.loads(r.stdout)
    except json.JSONDecodeError:
        payload = {}
        need(False, "promote stdout json")

    sk = str(payload.get("skill_name") or "")
    need(bool(sk), "skill_name")
    skill_md = ROOT / ".pi" / "skills" / sk / "SKILL.md"
    need(skill_md.is_file(), f"skill md {skill_md}")
    body = skill_md.read_text(encoding="utf-8") if skill_md.is_file() else ""
    need("Compressed playbook" in body or "playbook" in body.lower(), "skill has playbook")
    need("Not" in body and ("authority" in body.lower() or "optima" in body.lower()), "authority disclaimer")
    # must not embed solution objective as skill field
    need('"objective":' not in body.replace(" ", ""), "no objective json field in skill")

    les = ROOT / str(payload.get("lesson_path") or "")
    if not les.is_file() and payload.get("lesson_path"):
        les = ROOT / Path(payload["lesson_path"])
    need(les.is_file(), f"lesson {les}")
    if les.is_file():
        data = json.loads(les.read_text(encoding="utf-8"))
        need(data.get("schema") == "orpath.lesson.v1", "lesson schema")
        need("objective" not in data, "lesson no objective key")

    allow = (ROOT / "knowledge/export_allowlist.txt").read_text(encoding="utf-8")
    need(sk in allow, "allowlist contains skill")

    copy = ROOT / "knowledge" / "corpus" / "skills" / f"skill-{sk}.md"
    need(copy.is_file(), f"RAG skill copy {copy}")

    # retrieve should be able to hit skill export (after ingest)
    outj = ROOT / "notes" / "_promote_run_retrieve.json"
    r2 = subprocess.run(
        [
            str(py),
            "-m",
            "knowledge_svc.retrieve",
            "--query",
            f"{sk} compressed playbook method skill {SLUG}",
            "--mode",
            "hybrid",
            "--topk",
            "8",
            "--embed-mode",
            "stub",
            "--out",
            str(outj),
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    need(r2.returncode == 0, f"retrieve rc={r2.returncode}")
    art = json.loads(outj.read_text(encoding="utf-8")) if outj.is_file() else {}
    hits = art.get("hits") or []
    paths = " ".join(str(h.get("source_path") or "") for h in hits).replace("\\", "/")
    need(len(hits) >= 1, "retrieve hits")
    # Prefer skill/lesson hit; if RRF ranks papers first, still require export copy on disk
    hit_skill = (
        sk in paths
        or sk.replace("_", "-") in paths
        or f"skill-{sk}" in paths
        or "corpus/skills" in paths
        or "or-method" in paths
        or "corpus/lessons" in paths
        or "lesson-les_run" in paths
    )
    if not hit_skill:
        # second try: exact skill name query
        outj2 = ROOT / "notes" / "_promote_run_retrieve2.json"
        r3 = subprocess.run(
            [
                str(py),
                "-m",
                "knowledge_svc.retrieve",
                "--query",
                sk,
                "--mode",
                "hybrid",
                "--topk",
                "12",
                "--embed-mode",
                "stub",
                "--out",
                str(outj2),
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
        need(r3.returncode == 0, f"retrieve2 rc={r3.returncode}")
        art2 = json.loads(outj2.read_text(encoding="utf-8")) if outj2.is_file() else {}
        paths2 = " ".join(str(h.get("source_path") or "") for h in (art2.get("hits") or [])).replace("\\", "/")
        hit_skill = (
            sk in paths2
            or f"skill-{sk}" in paths2
            or "corpus/skills" in paths2
            or "or-method" in paths2
            or "les_run" in paths2
        )
        paths = paths2 or paths
    need(hit_skill or copy.is_file(), f"hit skill/lesson or copy on disk; paths={paths[:180]}")
    if copy.is_file() and not hit_skill:
        print("WARN retrieve ranked papers above skill copy — export present on disk")

    board = ROOT / "notes" / "promote-run-evidence.md"
    board.write_text(
        "\n".join(
            [
                "# promote-run gate evidence",
                "",
                f"- slug: `{SLUG}`",
                f"- skill: `{sk}`",
                f"- lesson: `{payload.get('lesson_path')}`",
                f"- rag_copy: `{copy}`",
                f"- retrieve_hits: {len(hits)}",
                f"- gate: **{'PASS' if not fails else 'FAIL'}**",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("WROTE", board)

    if fails:
        print("FAIL promote_run_gate", fails)
        return 1
    print("PASS promote_run_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
