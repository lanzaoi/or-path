#!/usr/bin/env python3
"""Export selected skills + lessons into knowledge/corpus for Pi RAG (not training).

Writes markdown under:
  knowledge/corpus/skills/
  knowledge/corpus/lessons/

Never copies solution/validate JSON. Safe subset only.

Allowlist: knowledge/export_allowlist.txt (skill folder names).
Lessons: only schema == orpath.lesson.v1; reject objective authority fields.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SKILLS = (
    "or-numbers-truth",
    "or-solver-select",
    "or-process-memory",
    "or-modeling",
    "operations-research-algorithm-developer",
)

MAX_SKILL_BYTES = 80_000  # skip huge vendor dumps
LESSON_SCHEMA = "orpath.lesson.v1"

# Top-level keys that mark a JSON as solution-like / numeric authority dump
_FORBIDDEN_TOP_KEYS = frozenset(
    {
        "objective",
        "optimal",
        "optimal_value",
        "path",
        "tour",
        "routes",
        "placements",
        "solution",
    }
)


def _repo_root() -> Path:
    return ROOT


def load_skill_allowlist(root: Path) -> list[str]:
    """Load skill names from knowledge/export_allowlist.txt; fallback DEFAULT_SKILLS."""
    path = root / "knowledge" / "export_allowlist.txt"
    if not path.is_file():
        return list(DEFAULT_SKILLS)
    names: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        # strip inline comments
        if "#" in s:
            s = s.split("#", 1)[0].strip()
        if s:
            names.append(s)
    return names or list(DEFAULT_SKILLS)


def export_skills(root: Path, dest: Path, names: list[str]) -> dict:
    skills_root = root / ".pi" / "skills"
    dest.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    skipped: list[dict] = []
    for name in names:
        src = skills_root / name / "SKILL.md"
        if not src.is_file():
            alt = skills_root / f"{name}.md"
            src = alt if alt.is_file() else src
        if not src.is_file():
            skipped.append({"name": name, "reason": "missing_skill_md"})
            continue
        size = src.stat().st_size
        if size > MAX_SKILL_BYTES:
            skipped.append(
                {"name": name, "reason": "too_large", "bytes": size, "max": MAX_SKILL_BYTES}
            )
            continue
        text = src.read_text(encoding="utf-8", errors="replace")
        try:
            rel = src.relative_to(root).as_posix()
        except ValueError:
            rel = src.as_posix()
        out = dest / f"skill-{name}.md"
        header = (
            f"# Skill export: {name}\n\n"
            f"- kind: skill\n"
            f"- source_path: {rel}\n"
            f"- note: RAG **copy** for Pi retrieve only; "
            f"runtime skill loading still uses `.pi/skills/` (not this file).\n\n"
            "---\n\n"
        )
        out.write_text(header + text, encoding="utf-8")
        written.append(str(out.relative_to(root)).replace("\\", "/"))
    return {"written": written, "skipped": skipped}


def _lesson_looks_authoritative(data: dict) -> str | None:
    """Return reject reason if lesson must not enter RAG."""
    schema = str(data.get("schema") or "").strip()
    if schema != LESSON_SCHEMA:
        return f"schema_not_{LESSON_SCHEMA}"
    for k in _FORBIDDEN_TOP_KEYS:
        if k in data and data.get(k) is not None:
            return f"forbidden_top_key:{k}"
    # nested solution dump
    blob = json.dumps(data, ensure_ascii=False)
    if re.search(r'"objective"\s*:\s*[-+]?\d', blob) and "not authoritative" not in blob.lower():
        # allow mention in summary text only if no numeric objective field structure
        if '"objective":' in blob.replace(" ", "").lower():
            # check structured
            if isinstance(data.get("metrics"), dict) and "objective" in (data.get("metrics") or {}):
                return "metrics.objective"
            if isinstance(data.get("solution"), dict):
                return "nested_solution"
    return None


def _lesson_to_md(data: dict, src: Path) -> str:
    lid = data.get("id") or src.stem
    lines = [
        f"# Lesson: {lid}",
        "",
        "- kind: lesson",
        f"- source_path: {src.as_posix()}",
        f"- problem_class: {data.get('problem_class') or ''}",
        f"- schema: {data.get('schema') or ''}",
        "",
        "## Summary",
        "",
        str(data.get("summary") or "").strip() or "(none)",
        "",
    ]
    kd = data.get("key_decisions") or []
    if kd:
        lines += ["## Key decisions", ""]
        for x in kd:
            lines.append(f"- {x}")
        lines.append("")
    pits = data.get("pitfalls") or []
    if pits:
        lines += ["## Pitfalls", ""]
        for x in pits:
            lines.append(f"- {x}")
        lines.append("")
    tags = data.get("tags") or []
    if tags:
        lines += ["## Tags", "", ", ".join(str(t) for t in tags), ""]
    lines += [
        "## Authority",
        "",
        "Process memory only. **Not** numeric authority. Optima only from solve+validate.",
        "RAG holds a **searchable copy**; this is not a substitute for L0 solution JSON.",
        "",
    ]
    return "\n".join(lines)


def export_lessons(root: Path, dest: Path) -> dict:
    les_dir = root / "knowledge" / "lessons"
    dest.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    skipped: list[dict] = []
    if not les_dir.is_dir():
        return {"written": written, "skipped": skipped}
    for src in sorted(les_dir.glob("*.json")):
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            skipped.append({"file": src.name, "reason": f"json_error:{e}"})
            continue
        if not isinstance(data, dict):
            skipped.append({"file": src.name, "reason": "not_object"})
            continue
        reason = _lesson_looks_authoritative(data)
        if reason:
            skipped.append({"file": src.name, "reason": reason})
            continue
        try:
            rel = src.relative_to(root)
        except ValueError:
            rel = src
        md = _lesson_to_md(data, rel)
        out = dest / f"lesson-{src.stem}.md"
        out.write_text(md, encoding="utf-8")
        written.append(str(out.relative_to(root)).replace("\\", "/"))
    return {"written": written, "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument(
        "--skills",
        default="",
        help="Comma-separated override; default = knowledge/export_allowlist.txt",
    )
    ap.add_argument("--no-skills", action="store_true")
    ap.add_argument("--no-lessons", action="store_true")
    ap.add_argument(
        "--clear-exports",
        action="store_true",
        help="Remove corpus/skills and corpus/lessons before write",
    )
    ap.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="Override path to export_allowlist.txt",
    )
    args = ap.parse_args(argv)
    root = (args.root or _repo_root()).resolve()
    corpus = root / "knowledge" / "corpus"
    sk_dest = corpus / "skills"
    le_dest = corpus / "lessons"

    if args.clear_exports:
        for d in (sk_dest, le_dest):
            if d.is_dir():
                shutil.rmtree(d)

    if args.skills.strip():
        names = [x.strip() for x in args.skills.split(",") if x.strip()]
        allowlist_src = "cli --skills"
    elif args.allowlist:
        # load custom file
        text = args.allowlist.read_text(encoding="utf-8")
        names = [
            ln.split("#", 1)[0].strip()
            for ln in text.splitlines()
            if ln.split("#", 1)[0].strip()
        ]
        allowlist_src = str(args.allowlist)
    else:
        names = load_skill_allowlist(root)
        allowlist_src = "knowledge/export_allowlist.txt"

    out: dict = {
        "root": str(root),
        "allowlist_source": allowlist_src,
        "allowlist_skills": names,
        "max_skill_bytes": MAX_SKILL_BYTES,
        "lesson_schema_required": LESSON_SCHEMA,
        "skills": {"written": [], "skipped": []},
        "lessons": {"written": [], "skipped": []},
        "note": "RAG copies only; Pi runtime skills still load from .pi/skills/",
    }
    if not args.no_skills:
        out["skills"] = export_skills(root, sk_dest, names)
    if not args.no_lessons:
        out["lessons"] = export_lessons(root, le_dest)

    print(json.dumps(out, indent=2, ensure_ascii=False))
    n = len(out["skills"]["written"]) + len(out["lessons"]["written"])
    if n == 0:
        print("warning: nothing exported", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
