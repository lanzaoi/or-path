"""OR-Path process memory — cross-run solve process & key points (not Skill, not optima).

Storage: knowledge/lessons/*.json (seedable) + optional local drafts under memory/lessons/.
Retrieval: class filter + token overlap + optional FTS later. No objective authority.
"""
from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Fields that must never be treated as authoritative answers in lessons
FORBIDDEN_AUTHORITY = frozenset(
    {
        "objective",
        "optimal",
        "optimal_value",
        "path",
        "tour",
        "routes",
        "best_cost",
        "objective_value",
    }
)

_TOKEN = re.compile(r"[a-z0-9_]{2,}", re.I)


def repo_root(start: Path | None = None) -> Path:
    if start is not None:
        return Path(start).resolve()
    return Path(__file__).resolve().parent.parent


def lessons_dirs(root: Path) -> list[Path]:
    """Search order: committed seeds first, then local drafts."""
    return [
        root / "knowledge" / "lessons",
        root / "memory" / "lessons",
    ]


def ensure_dirs(root: Path) -> None:
    for d in lessons_dirs(root):
        d.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN.findall(text or "")}


def strip_forbidden(data: dict[str, Any]) -> dict[str, Any]:
    """Drop authority numeric keys from a lesson dict (shallow + nested meta)."""
    out: dict[str, Any] = {}
    for k, v in data.items():
        if k.lower() in FORBIDDEN_AUTHORITY:
            continue
        if k == "numbers_mentioned" and isinstance(v, list):
            # keep only entries that carry source_path
            cleaned = []
            for item in v:
                if isinstance(item, dict) and item.get("source_path"):
                    cleaned.append(
                        {
                            "label": str(item.get("label") or "ref"),
                            "source_path": str(item["source_path"]),
                            "note": str(item.get("note") or "non-authoritative pointer"),
                        }
                    )
            out[k] = cleaned
            continue
        out[k] = v
    return out


def new_lesson(
    *,
    problem_class: str,
    summary: str,
    key_decisions: list[str] | None = None,
    pitfalls: list[str] | None = None,
    skills_used: list[str] | None = None,
    artifact_paths: list[str] | None = None,
    tags: list[str] | None = None,
    slug: str = "",
    lesson_id: str | None = None,
) -> dict[str, Any]:
    lid = lesson_id or f"les_{uuid.uuid4().hex[:12]}"
    body = {
        "id": lid,
        "schema": "orpath.lesson.v1",
        "slug": slug or "",
        "problem_class": (problem_class or "").strip().lower(),
        "created": _now(),
        "summary": (summary or "").strip(),
        "key_decisions": [str(x).strip() for x in (key_decisions or []) if str(x).strip()],
        "pitfalls": [str(x).strip() for x in (pitfalls or []) if str(x).strip()],
        "skills_used": [str(x).strip() for x in (skills_used or []) if str(x).strip()],
        "artifact_paths": [str(x).strip() for x in (artifact_paths or []) if str(x).strip()],
        "tags": [str(x).strip().lower() for x in (tags or []) if str(x).strip()],
    }
    return strip_forbidden(body)


def lesson_path(root: Path, lesson: dict[str, Any], *, local: bool = False) -> Path:
    ensure_dirs(root)
    base = lessons_dirs(root)[1] if local else lessons_dirs(root)[0]
    return base / f"{lesson['id']}.json"


def save_lesson(root: Path, lesson: dict[str, Any], *, local: bool = True) -> Path:
    lesson = strip_forbidden(lesson)
    path = lesson_path(root, lesson, local=local)
    path.write_text(json.dumps(lesson, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_all_lessons(root: Path) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for d in lessons_dirs(root):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            data = strip_forbidden(data)
            lid = str(data.get("id") or p.stem)
            if lid in seen:
                continue
            seen.add(lid)
            data["id"] = lid
            data["_path"] = str(p)
            out.append(data)
    return out


def _score_lesson(lesson: dict[str, Any], query: str, problem_class: str | None) -> float:
    pc = (problem_class or "").strip().lower()
    lpc = str(lesson.get("problem_class") or "").lower()
    score = 0.0
    if pc and lpc == pc:
        score += 5.0
    elif pc and pc in lpc:
        score += 2.0
    blob = " ".join(
        [
            str(lesson.get("summary") or ""),
            " ".join(lesson.get("key_decisions") or []),
            " ".join(lesson.get("pitfalls") or []),
            " ".join(lesson.get("tags") or []),
            " ".join(lesson.get("skills_used") or []),
            str(lesson.get("slug") or ""),
        ]
    )
    qt = _tokens(query)
    if not qt:
        return score if score else 0.01
    bt = _tokens(blob)
    if not bt:
        return score
    overlap = len(qt & bt)
    score += overlap * 1.5
    # light IDF-ish: reward denser matches
    if overlap:
        score += overlap / max(len(qt), 1)
    return score


def retrieve_lessons(
    query: str,
    *,
    root: Path | None = None,
    problem_class: str | None = None,
    topk: int = 5,
) -> list[dict[str, Any]]:
    """Rank lessons by class match + token overlap. Empty query still returns class hits."""
    root = root or repo_root()
    lessons = load_all_lessons(root)
    scored: list[tuple[float, dict[str, Any]]] = []
    for les in lessons:
        sc = _score_lesson(les, query or "", problem_class)
        if sc <= 0:
            continue
        scored.append((sc, les))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, Any]] = []
    for sc, les in scored[: max(1, topk)]:
        item = dict(les)
        item["score"] = round(float(sc), 4)
        out.append(item)
    return out


def lessons_to_markdown(lessons: list[dict[str, Any]], *, query: str = "") -> str:
    lines = [
        "# Process memory lessons",
        "",
        "> Process & key points only — **not** authoritative optima. Numbers → solution path + validate.",
        "",
    ]
    if query:
        lines.append(f"Query: `{query}`")
        lines.append("")
    if not lessons:
        lines.append("_No matching lessons._")
        lines.append("")
        return "\n".join(lines)
    for i, les in enumerate(lessons, 1):
        lines.append(f"## {i}. {les.get('id')} (score={les.get('score', '?')})")
        lines.append(f"- class: `{les.get('problem_class')}`")
        if les.get("slug"):
            lines.append(f"- slug: `{les.get('slug')}`")
        lines.append(f"- summary: {les.get('summary')}")
        if les.get("key_decisions"):
            lines.append("- key_decisions:")
            for d in les["key_decisions"]:
                lines.append(f"  - {d}")
        if les.get("pitfalls"):
            lines.append("- pitfalls:")
            for d in les["pitfalls"]:
                lines.append(f"  - {d}")
        if les.get("artifact_paths"):
            lines.append("- artifacts: " + ", ".join(f"`{p}`" for p in les["artifact_paths"]))
        if les.get("_path"):
            lines.append(f"- source: `{les.get('_path')}`")
        lines.append("")
    return "\n".join(lines)


def write_retrieve_artifacts(
    root: Path,
    slug: str,
    *,
    query: str,
    problem_class: str | None,
    topk: int = 5,
) -> tuple[Path, Path, list[dict[str, Any]]]:
    """Write notes/<slug>-lessons.json + .md for the pipeline."""
    notes = root / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    hits = retrieve_lessons(query, root=root, problem_class=problem_class, topk=topk)
    jpath = notes / f"{slug}-lessons.json"
    mpath = notes / f"{slug}-lessons.md"
    art = {
        "schema": "orpath.lessons_retrieve.v1",
        "query": query,
        "problem_class": problem_class or "",
        "hits": hits,
    }
    jpath.write_text(json.dumps(art, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    mpath.write_text(lessons_to_markdown(hits, query=query), encoding="utf-8")
    return jpath, mpath, hits


def record_from_run(
    root: Path,
    *,
    slug: str,
    problem_class: str,
    summary: str,
    key_decisions: list[str] | None = None,
    pitfalls: list[str] | None = None,
    artifact_paths: list[str] | None = None,
    skills_used: list[str] | None = None,
    tags: list[str] | None = None,
    local: bool = True,
) -> Path:
    les = new_lesson(
        problem_class=problem_class,
        summary=summary,
        key_decisions=key_decisions,
        pitfalls=pitfalls,
        skills_used=skills_used,
        artifact_paths=artifact_paths,
        tags=tags,
        slug=slug,
    )
    return save_lesson(root, les, local=local)


def auto_draft_after_validate(
    root: Path,
    state: dict[str, Any],
    *,
    gate_ok: bool,
) -> Path | None:
    """Best-effort lesson draft after validate (process only)."""
    slug = str(state.get("slug") or "")
    pc = str(state.get("problem_class") or "")
    if not slug or not pc:
        return None
    mode = str(state.get("solve_mode") or "")
    paths = [
        p
        for p in (
            state.get("schema_path"),
            state.get("solution_path"),
            state.get("validate_path"),
            state.get("research_path"),
        )
        if p
    ]
    if gate_ok:
        summary = (
            f"Run `{slug}` class={pc} mode={mode}: validate OK. "
            f"Process: research→model→solve({mode})→validate."
        )
        decisions = [
            f"preferred/solve_mode used: {mode}",
            "numbers accepted only after validate recompute",
        ]
        pitfalls: list[str] = []
        tags = [pc, mode, "validate_ok"]
    else:
        err = str(state.get("last_error") or "validate failed")[:200]
        summary = f"Run `{slug}` class={pc} mode={mode}: validate FAIL — {err}"
        decisions = [f"attempted mode={mode}"]
        pitfalls = [err, "do not invent objective to paper over fail"]
        tags = [pc, mode, "validate_fail"]
    return record_from_run(
        root,
        slug=slug,
        problem_class=pc,
        summary=summary,
        key_decisions=decisions,
        pitfalls=pitfalls,
        artifact_paths=[str(p) for p in paths],
        skills_used=["or-solver-select", "or-numbers-truth"],
        tags=tags,
        local=True,
    )


def _cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="orpath.process_memory")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="Search process lessons")
    s.add_argument("--query", default="")
    s.add_argument("--class", dest="problem_class", default="")
    s.add_argument("--topk", type=int, default=5)
    s.add_argument("--root", default="")
    s.add_argument("--json", action="store_true")

    r = sub.add_parser("record", help="Record a process lesson (local)")
    r.add_argument("--slug", default="")
    r.add_argument("--class", dest="problem_class", required=True)
    r.add_argument("--summary", required=True)
    r.add_argument("--decision", action="append", default=[])
    r.add_argument("--pitfall", action="append", default=[])
    r.add_argument("--tag", action="append", default=[])
    r.add_argument("--root", default="")
    r.add_argument("--seed", action="store_true", help="Write under knowledge/lessons (committed)")

    a = sub.add_parser("list", help="List all lessons")
    a.add_argument("--root", default="")

    args = p.parse_args(argv)
    root = Path(args.root).resolve() if getattr(args, "root", "") else repo_root()

    if args.cmd == "search":
        hits = retrieve_lessons(
            args.query, root=root, problem_class=args.problem_class or None, topk=args.topk
        )
        if args.json:
            print(json.dumps(hits, indent=2, ensure_ascii=False))
        else:
            print(lessons_to_markdown(hits, query=args.query))
        return 0
    if args.cmd == "record":
        path = record_from_run(
            root,
            slug=args.slug,
            problem_class=args.problem_class,
            summary=args.summary,
            key_decisions=args.decision,
            pitfalls=args.pitfall,
            tags=args.tag,
            local=not args.seed,
        )
        print(path)
        return 0
    if args.cmd == "list":
        for les in load_all_lessons(root):
            print(f"{les.get('id')}\t{les.get('problem_class')}\t{les.get('summary', '')[:80]}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli())
