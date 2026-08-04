#!/usr/bin/env python3
"""Promote a finished run → compressed Skill + lesson → RAG (long-term process memory).

Reads notes/outputs for <slug>, compresses *process* key points (not optima), writes:
  .pi/skills/or-method-<class>-<slug>/SKILL.md
  knowledge/lessons/les_run_<slug>.json
  knowledge/export_allowlist.txt (append skill name)
Optional: export + ingest so hybrid retrieve can hit the skill copy.

Authority: numbers still only solve+validate. Skill/lesson are process memory.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.process_memory import (  # noqa: E402
    FORBIDDEN_AUTHORITY,
    new_lesson,
    save_lesson,
    strip_forbidden,
)
from orpath.tool_catalog import default_mode_for_class  # noqa: E402

_SLUG_SAFE = re.compile(r"[^a-z0-9]+")
_OBJ_NUM = re.compile(
    r"\b(objective|optimal_value|best_cost)\s*[:=]\s*[-+]?\d",
    re.I,
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug_safe(s: str) -> str:
    s = (s or "").strip().lower().replace("\\", "-").replace("/", "-")
    s = _SLUG_SAFE.sub("-", s).strip("-")
    return (s or "run")[:48]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _read_text(path: Path, limit: int = 12000) -> str:
    if not path.is_file():
        return ""
    try:
        t = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return t[:limit]


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _bullet_clean(line: str) -> str | None:
    s = line.strip().lstrip("-*•").strip()
    if not s or len(s) < 8:
        return None
    if _OBJ_NUM.search(s):
        return None
    # drop pure graph weight dumps
    if re.search(r"→\s*\d+\s*$", s) and "weight" in s.lower():
        return None
    low = s.lower()
    for bad in FORBIDDEN_AUTHORITY:
        if low.startswith(bad + "=") or low.startswith(bad + ":"):
            return None
    return s[:240]


def _extract_from_research(text: str) -> tuple[list[str], list[str]]:
    decisions: list[str] = []
    pitfalls: list[str] = []
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if section in {
            "findings",
            "modeling recommendations",
            "summary",
            "coverage status",
        }:
            b = _bullet_clean(line if line.startswith(("-", "*", "•")) or line[:1].isdigit() else f"- {line}")
            if not b:
                continue
            if "do not" in b.lower() or "never" in b.lower() or "forbid" in b.lower():
                if b not in pitfalls:
                    pitfalls.append(b)
            else:
                if b not in decisions and len(decisions) < 12:
                    decisions.append(b)
    return decisions, pitfalls


def _papers_from_retrieval(art: dict[str, Any], *, max_n: int = 8) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for h in art.get("hits") or []:
        if not isinstance(h, dict):
            continue
        sp = str(h.get("source_path") or "").replace("\\", "/")
        if "knowledge/corpus/papers" not in sp and "papers/" not in sp:
            continue
        cid = str(h.get("chunk_id") or "")
        out.append(
            {
                "chunk_id": cid,
                "source_path": sp,
                "note": "retrieval hit — process context only",
            }
        )
        if len(out) >= max_n:
            break
    return out


def _schema_playbook(schema: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    pc = str(schema.get("problem_class") or "")
    if pc:
        lines.append(f"problem_class={pc}")
    psm = schema.get("preferred_solve_mode")
    if psm:
        lines.append(f"preferred_solve_mode={psm}")
    else:
        d = default_mode_for_class(pc) if pc else ""
        if d:
            lines.append(f"default_mode_for_class={d}")
    # structural keys only (no big blobs)
    for k in ("source", "target", "weight_key", "vehicle_count", "depot"):
        if k in schema and schema[k] is not None and not isinstance(schema[k], (list, dict)):
            lines.append(f"schema_field {k} present")
    lines.append("schema must not carry path/tour/routes/objective as answers")
    return lines


def collect_run(root: Path, slug: str) -> dict[str, Any]:
    notes = root / "notes"
    outputs = root / "outputs"
    research = _read_text(notes / f"{slug}-research.md")
    retrieval = _read_json(notes / f"{slug}-retrieval.json")
    schema = _read_json(outputs / f"{slug}-schema.json")
    validate = _read_json(outputs / f"{slug}-validate.json")
    solution = _read_json(outputs / f"{slug}-solution.json")
    # never use solution numbers in skill body
    solve_mode = str(
        solution.get("solve_mode")
        or solution.get("mode")
        or schema.get("preferred_solve_mode")
        or ""
    )
    pc = str(
        schema.get("problem_class")
        or validate.get("problem_class")
        or retrieval.get("problem_class")
        or ""
    ).lower()
    if not pc and research:
        m = re.search(r"problem class\s*\n\s*([a-z0-9_]+)", research, re.I)
        if m:
            pc = m.group(1).lower()
    val_ok = bool(validate.get("ok")) if validate else False
    dec_r, pit_r = _extract_from_research(research)
    decisions = _schema_playbook(schema) if schema else []
    for d in dec_r:
        if d not in decisions:
            decisions.append(d)
    if solve_mode:
        decisions.insert(0, f"solve_mode_used={solve_mode}")
    decisions.append("numbers accepted only after validate recompute")
    pitfalls = list(pit_r)
    if not val_ok and validate:
        err = "; ".join(str(e) for e in (validate.get("errors") or [])[:3]) or "validate not ok"
        pitfalls.append(f"validate issue: {err[:160]}")
    pitfalls.append("Do not invent objective/path in prose or skill text")
    papers = _papers_from_retrieval(retrieval)
    artifacts = []
    for p in (
        notes / f"{slug}-research.md",
        notes / f"{slug}-retrieval.json",
        outputs / f"{slug}-schema.json",
        outputs / f"{slug}-validate.json",
        # solution path as pointer only — not embedded numbers
        outputs / f"{slug}-solution.json",
    ):
        if p.is_file():
            artifacts.append(_rel(root, p))
    return {
        "slug": slug,
        "problem_class": pc or "unknown",
        "solve_mode": solve_mode,
        "validate_ok": val_ok,
        "decisions": decisions[:14],
        "pitfalls": pitfalls[:10],
        "papers": papers,
        "artifacts": artifacts,
        "knowledge_mode": str(retrieval.get("knowledge_mode") or ""),
        "embed_mode": str(retrieval.get("embed_mode") or ""),
    }


def skill_name_for(slug: str, problem_class: str) -> str:
    return f"or-method-{_slug_safe(problem_class)}-{_slug_safe(slug)}"


def render_skill_md(meta: dict[str, Any], *, skill_name: str) -> str:
    pc = meta["problem_class"]
    slug = meta["slug"]
    desc = (
        f"Compressed OR method from run `{slug}` ({pc}). "
        f"Process playbook only — not numeric authority. Use after similar {pc} cases."
    )[:400]
    lines = [
        "---",
        f"name: {skill_name}",
        f"description: {desc}",
        "---",
        "",
        f"# Method skill: `{skill_name}`",
        "",
        "> **Long-term process memory** (compressed).  ",
        "> **Not** L0 solution authority. Optima only from solve tools + validate.",
        "",
        "## Provenance",
        "",
        f"- source_run_slug: `{slug}`",
        f"- problem_class: `{pc}`",
        f"- solve_mode: `{meta.get('solve_mode') or 'unknown'}`",
        f"- validate_ok: `{meta.get('validate_ok')}`",
        f"- promoted_at: `{_now()}`",
        f"- knowledge_mode: `{meta.get('knowledge_mode') or ''}`",
        f"- embed_mode: `{meta.get('embed_mode') or ''}`",
        "",
        "## Compressed playbook",
        "",
    ]
    for d in meta.get("decisions") or []:
        lines.append(f"- {d}")
    lines += ["", "## Pitfalls", ""]
    for p in meta.get("pitfalls") or []:
        lines.append(f"- {p}")
    papers = meta.get("papers") or []
    lines += ["", "## Papers / corpus hits (with this run)", ""]
    if papers:
        for p in papers:
            lines.append(f"- `{p.get('source_path')}`" + (f" (chunk `{p.get('chunk_id')}`)" if p.get("chunk_id") else ""))
    else:
        lines.append("- _(no papers grain hits recorded)_")
    lines += ["", "## Artifact pointers (disk)", ""]
    for a in meta.get("artifacts") or []:
        lines.append(f"- `{a}`")
    lines += [
        "",
        "## How to use next time",
        "",
        f"1. If problem_class≈`{pc}`, load this skill for process checklist.",
        "2. Still run solve + validate; never copy numbers from this file.",
        "3. Hybrid RAG may also retrieve the exported copy under `knowledge/corpus/skills/`.",
        "",
        "## Authority",
        "",
        "- Skill = compressed method / checklist.",
        "- Lesson JSON (same promote) = searchable process memory.",
        "- Solution JSON path is a pointer only — open validate/solution for numbers.",
        "",
    ]
    return "\n".join(lines)


def write_skill(root: Path, skill_name: str, body: str) -> Path:
    d = root / ".pi" / "skills" / skill_name
    d.mkdir(parents=True, exist_ok=True)
    path = d / "SKILL.md"
    path.write_text(body, encoding="utf-8")
    return path


def ensure_allowlist(root: Path, skill_name: str) -> Path:
    path = root / "knowledge" / "export_allowlist.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    names = {
        ln.split("#", 1)[0].strip()
        for ln in existing.splitlines()
        if ln.split("#", 1)[0].strip()
    }
    if skill_name not in names:
        if existing and not existing.endswith("\n"):
            existing += "\n"
        if "# promoted run methods" not in existing:
            existing += "\n# promoted run methods (auto)\n"
        existing += f"{skill_name}\n"
        path.write_text(existing, encoding="utf-8")
    return path


def write_lesson(root: Path, meta: dict[str, Any], *, skill_name: str) -> Path:
    papers = [p.get("source_path") for p in (meta.get("papers") or []) if p.get("source_path")]
    summary = (
        f"Promoted method from run `{meta['slug']}` class={meta['problem_class']} "
        f"mode={meta.get('solve_mode') or '?'}: "
        + ("validate OK. " if meta.get("validate_ok") else "validate not OK. ")
        + f"Skill `{skill_name}` + {len(papers)} paper hit(s)."
    )
    tags = [
        meta["problem_class"],
        "promoted",
        "method_skill",
        "validate_ok" if meta.get("validate_ok") else "validate_fail",
    ]
    if meta.get("solve_mode"):
        tags.append(str(meta["solve_mode"]))
    les = new_lesson(
        problem_class=meta["problem_class"],
        summary=summary,
        key_decisions=list(meta.get("decisions") or [])[:10],
        pitfalls=list(meta.get("pitfalls") or [])[:8],
        skills_used=["or-numbers-truth", "or-solver-select", skill_name],
        artifact_paths=list(meta.get("artifacts") or []) + papers[:8],
        tags=tags,
        slug=meta["slug"],
        lesson_id=f"les_run_{_slug_safe(meta['slug'])}",
    )
    # committed knowledge/lessons so export_lessons picks it up
    return save_lesson(root, strip_forbidden(les), local=False)


def run_export_ingest(root: Path, *, py: Path, do_ingest: bool) -> dict[str, Any]:
    env = {k: v for k, v in __import__("os").environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONNOUSERSITE"] = "1"
    env["ORPATH_KNOWLEDGE_EMBED"] = env.get("ORPATH_KNOWLEDGE_EMBED") or "stub"
    out: dict[str, Any] = {}
    r1 = subprocess.run(
        [str(py), str(root / "scripts" / "export_agent_knowledge_corpus.py"), "--clear-exports"],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    out["export_rc"] = r1.returncode
    try:
        out["export"] = json.loads(r1.stdout) if r1.stdout.strip().startswith("{") else {"raw": (r1.stdout or "")[:500]}
    except json.JSONDecodeError:
        out["export"] = {"raw": (r1.stdout or "")[:500]}
    if do_ingest:
        r2 = subprocess.run(
            [
                str(py),
                "-m",
                "knowledge_svc.ingest",
                "--embed-mode",
                "stub",
                "--no-incremental",
            ],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=420,
        )
        out["ingest_rc"] = r2.returncode
        try:
            out["ingest"] = json.loads(r2.stdout) if r2.stdout.strip().startswith("{") else {}
        except json.JSONDecodeError:
            out["ingest"] = {}
    return out


def promote(
    root: Path,
    slug: str,
    *,
    sync: bool = True,
    ingest: bool = True,
    skill_name: str | None = None,
) -> dict[str, Any]:
    meta = collect_run(root, slug)
    if meta["problem_class"] == "unknown" and not meta["artifacts"]:
        raise FileNotFoundError(f"no run artifacts for slug={slug!r} under notes/outputs")
    name = skill_name or skill_name_for(slug, meta["problem_class"])
    body = render_skill_md(meta, skill_name=name)
    skill_path = write_skill(root, name, body)
    allow = ensure_allowlist(root, name)
    lesson_path = write_lesson(root, meta, skill_name=name)
    # board
    board = root / "notes" / f"{slug}-promoted-method.md"
    board.write_text(
        "\n".join(
            [
                f"# Promoted method · `{slug}`",
                "",
                f"- skill: `{_rel(root, skill_path)}`",
                f"- skill_name: `{name}`",
                f"- lesson: `{_rel(root, lesson_path)}`",
                f"- allowlist: `{_rel(root, allow)}`",
                f"- papers: {len(meta.get('papers') or [])}",
                f"- validate_ok: {meta.get('validate_ok')}",
                "",
                "Long-term memory = this skill (+ lesson RAG copy). Not solution JSON.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result: dict[str, Any] = {
        "status": "OK",
        "slug": slug,
        "skill_name": name,
        "skill_path": _rel(root, skill_path),
        "lesson_path": _rel(root, lesson_path),
        "allowlist": _rel(root, allow),
        "board": _rel(root, board),
        "n_papers": len(meta.get("papers") or []),
        "validate_ok": meta.get("validate_ok"),
        "problem_class": meta.get("problem_class"),
    }
    if sync:
        py = root / ".venv-314" / "Scripts" / "python.exe"
        if not py.is_file():
            py = Path(sys.executable)
        result["sync"] = run_export_ingest(root, py=py, do_ingest=ingest)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slug", required=True, help="Finished run slug (notes/outputs prefix)")
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--skill-name", default=None, help="Override skill folder name")
    ap.add_argument("--no-sync", action="store_true", help="Only write skill+lesson+allowlist")
    ap.add_argument("--no-ingest", action="store_true", help="Export only, skip ingest")
    args = ap.parse_args(argv)
    root = (args.root or ROOT).resolve()
    try:
        out = promote(
            root,
            args.slug.strip(),
            sync=not args.no_sync,
            ingest=not args.no_ingest and not args.no_sync,
            skill_name=args.skill_name,
        )
    except FileNotFoundError as e:
        print(json.dumps({"status": "ERROR", "error": str(e)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
