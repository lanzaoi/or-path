#!/usr/bin/env python3
"""Intake gate (OR-Path 1.1): intake.json contract + forbidden solution keys + brief heuristics.

See specs/problem-intake.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema_models import (  # noqa: E402
    FORBIDDEN_INTAKE_KEYS,
    INTAKE_ASSET_KINDS,
    INTAKE_SCHEMA_VERSION,
    INTAKE_STATUSES,
)

# Keys that mean "solver answer shape" — never allowed as JSON keys in intake,
# except bare `path` inside file-path objects (sources[] / data_assets[]).
_FILE_PATH_PARENTS = frozenset({"sources", "data_assets"})
_SOLUTION_SHAPE_ALWAYS = FORBIDDEN_INTAKE_KEYS - {"path"}


def walk_forbidden_intake_keys(
    obj: Any,
    found: set[str] | None = None,
    *,
    parent_key: str | None = None,
) -> set[str]:
    """Recursive forbidden-key scan for intake.json.

    `path` is allowed only as a field of objects nested under `sources` or
    `data_assets` (file paths). Top-level / arbitrary nested `path` (answer
    shape) is still forbidden — same spirit as modeler schema gate.
    """
    if found is None:
        found = set()
    if isinstance(obj, dict):
        allow_path = parent_key in _FILE_PATH_PARENTS
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in _SOLUTION_SHAPE_ALWAYS:
                found.add(lk)
            elif lk == "path" and not allow_path:
                found.add("path")
            # Children of a sources/data_assets *element* still use parent_key
            # of the array name only one level — pass array name when walking list items.
            walk_forbidden_intake_keys(v, found, parent_key=lk)
    elif isinstance(obj, list):
        for item in obj:
            # list under sources/data_assets: elements may have path
            walk_forbidden_intake_keys(item, found, parent_key=parent_key)
    return found


# Brief must carry these section *semantics* (heading match is flexible).
_BRIEF_SECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("sources", re.compile(r"^#{1,3}\s*.*\bsources?\b", re.I | re.M)),
    (
        "full_statement",
        re.compile(
            r"^#{1,3}\s*.*(full\s+problem|problem\s+statement|题面|题目全文|normalized)",
            re.I | re.M,
        ),
    ),
    (
        "subproblems",
        re.compile(r"^#{1,3}\s*.*(subproblems?|子问|问题\s*[一二三四1-9q])", re.I | re.M),
    ),
    (
        "data_assets",
        re.compile(r"^#{1,3}\s*.*(data\s+assets?|数据|附件)", re.I | re.M),
    ),
    (
        "objectives_qual",
        re.compile(r"^#{1,3}\s*.*(objectives?|目标)", re.I | re.M),
    ),
    (
        "constraints_qual",
        re.compile(r"^#{1,3}\s*.*(constraints?|约束)", re.I | re.M),
    ),
    (
        "deliverables",
        re.compile(r"^#{1,3}\s*.*(deliverables?|交付)", re.I | re.M),
    ),
    (
        "ambiguities",
        re.compile(r"^#{1,3}\s*.*(ambiguities|ocr\s*gaps?|歧义|不清|缺页)", re.I | re.M),
    ),
]

# Gold negative patterns: claimed numeric optima in brief prose (finite false positives OK).
_BRIEF_ANSWER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bobjective\s*=\s*-?\d", re.I),
    re.compile(r"\boptimal(?:_value|_cost)?\s*=\s*-?\d", re.I),
    re.compile(r"最优(?:解|值|总长|目标|费用|成本)\s*[=：:]\s*-?\d"),
    re.compile(r"(?:objective|optimal)\s*(?:value|cost)?\s*(?:is|was)\s*-?\d", re.I),
    re.compile(r"proven[_\s-]?optimal\s*[=：:]\s*true", re.I),
]


def _is_nonempty_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def check_intake_dict(
    data: dict[str, Any],
    *,
    min_subproblems: int | None = None,
    require_needs_human_if_ambiguities: bool = True,
) -> list[str]:
    """Validate intake.json object. Returns human-readable error list (empty = pass)."""
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["intake root must be object"]

    bad = walk_forbidden_intake_keys(data)
    for k in sorted(bad):
        errors.append(f"forbidden key present: {k}")

    def req(field: str) -> Any:
        if field not in data:
            errors.append(f"missing field: {field}")
            return None
        return data[field]

    slug = req("slug")
    if slug is not None and not _is_nonempty_str(slug):
        errors.append("slug must be non-empty string")

    ver = data.get("schema_version")
    if ver is None:
        errors.append("missing field: schema_version")
    elif str(ver) != INTAKE_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {INTAKE_SCHEMA_VERSION!r}, got {ver!r}"
        )

    status = data.get("status")
    if status is None:
        errors.append("missing field: status")
    elif str(status) not in INTAKE_STATUSES:
        errors.append(f"status must be one of {sorted(INTAKE_STATUSES)}, got {status!r}")

    for path_field in ("brief_path", "ocr_raw_path", "ocr_meta_path", "ocr_backend"):
        v = req(path_field)
        if v is not None and not _is_nonempty_str(v):
            errors.append(f"{path_field} must be non-empty string")

    sources = data.get("sources")
    if sources is None:
        errors.append("missing field: sources")
    elif not isinstance(sources, list):
        errors.append("sources must be array")
    else:
        for i, src in enumerate(sources):
            if not isinstance(src, dict):
                errors.append(f"sources[{i}] must be object")
                continue
            if not _is_nonempty_str(src.get("path")):
                errors.append(f"sources[{i}].path required")

    subs = data.get("subproblems")
    if subs is None:
        errors.append("missing field: subproblems")
    elif not isinstance(subs, list):
        errors.append("subproblems must be array")
    elif len(subs) < 1:
        errors.append("subproblems must contain at least 1 item")
    else:
        for i, sp in enumerate(subs):
            if not isinstance(sp, dict):
                errors.append(f"subproblems[{i}] must be object")
                continue
            if not _is_nonempty_str(sp.get("id")):
                errors.append(f"subproblems[{i}].id required")
            if not _is_nonempty_str(sp.get("title")):
                errors.append(f"subproblems[{i}].title required")
            md = sp.get("must_deliver", [])
            if md is None:
                md = []
            if not isinstance(md, list):
                errors.append(f"subproblems[{i}].must_deliver must be array")
            dr = sp.get("data_refs", [])
            if dr is None:
                dr = []
            if not isinstance(dr, list):
                errors.append(f"subproblems[{i}].data_refs must be array")
        if min_subproblems is not None and len(subs) < int(min_subproblems):
            errors.append(
                f"subproblems length {len(subs)} < required min_subproblems={min_subproblems}"
            )

    assets = data.get("data_assets")
    if assets is None:
        errors.append("missing field: data_assets")
    elif not isinstance(assets, list):
        errors.append("data_assets must be array")
    else:
        for i, a in enumerate(assets):
            if not isinstance(a, dict):
                errors.append(f"data_assets[{i}] must be object")
                continue
            if not _is_nonempty_str(a.get("path")):
                errors.append(f"data_assets[{i}].path required")
            kind = a.get("kind", "other")
            if kind is not None and str(kind) not in INTAKE_ASSET_KINDS:
                errors.append(
                    f"data_assets[{i}].kind must be one of {sorted(INTAKE_ASSET_KINDS)}"
                )

    for text_field in ("constraints_text", "objectives_text"):
        if text_field not in data:
            errors.append(f"missing field: {text_field}")
        elif not isinstance(data[text_field], str):
            errors.append(f"{text_field} must be string")

    for list_field in ("deliverables", "ambiguities"):
        if list_field not in data:
            errors.append(f"missing field: {list_field}")
        elif not isinstance(data[list_field], list):
            errors.append(f"{list_field} must be array")
        else:
            for j, item in enumerate(data[list_field]):
                if not isinstance(item, str):
                    errors.append(f"{list_field}[{j}] must be string")

    # hints optional but if present must be str or null
    for hint in ("problem_class_hint", "problem_id_hint"):
        if hint in data and data[hint] is not None and not isinstance(data[hint], str):
            errors.append(f"{hint} must be string or null")

    amb = data.get("ambiguities") if isinstance(data.get("ambiguities"), list) else []
    if (
        require_needs_human_if_ambiguities
        and amb
        and any(_is_nonempty_str(x) for x in amb)
        and str(data.get("status")) == "ok"
    ):
        errors.append(
            "status must be needs_human (or error) when ambiguities is non-empty"
        )

    return errors


def check_brief_text(text: str) -> list[str]:
    """Heuristic brief checks: required section headings + gold anti-answer patterns."""
    errors: list[str] = []
    if not isinstance(text, str) or not text.strip():
        return ["brief is empty"]

    for name, pat in _BRIEF_SECTION_PATTERNS:
        if not pat.search(text):
            errors.append(f"brief missing section semantics: {name}")

    for pat in _BRIEF_ANSWER_PATTERNS:
        m = pat.search(text)
        if m:
            snippet = m.group(0).replace("\n", " ")[:80]
            errors.append(f"brief looks like solution assertion: {snippet!r}")
            break
    return errors


def check_intake_files(
    intake_path: Path,
    *,
    brief_path: Path | None = None,
    min_subproblems: int | None = None,
    check_brief: bool = True,
    require_needs_human_if_ambiguities: bool = True,
) -> list[str]:
    errors: list[str] = []
    if not intake_path.is_file():
        return [f"file not found: {intake_path}"]
    try:
        data = json.loads(intake_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return ["intake root must be object"]

    errors.extend(
        check_intake_dict(
            data,
            min_subproblems=min_subproblems,
            require_needs_human_if_ambiguities=require_needs_human_if_ambiguities,
        )
    )

    if check_brief:
        bp = brief_path
        if bp is None and _is_nonempty_str(data.get("brief_path")):
            # Resolve relative to CWD first, then beside intake file, then repo-ish parents
            cand = Path(str(data["brief_path"]))
            if cand.is_file():
                bp = cand
            else:
                beside = intake_path.parent / cand.name
                if beside.is_file():
                    bp = beside
                else:
                    # try as relative from process cwd (caller usually sets repo root)
                    bp = cand
        if bp is None or not bp.is_file():
            errors.append(
                f"brief file not found (brief_path={data.get('brief_path')!r})"
            )
        else:
            errors.extend(check_brief_text(bp.read_text(encoding="utf-8")))

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OR-Path 1.1 intake gate")
    parser.add_argument("intake_path", type=Path, help="path to outputs/<slug>-intake.json")
    parser.add_argument(
        "--brief",
        type=Path,
        default=None,
        help="optional explicit brief path (default: intake.brief_path)",
    )
    parser.add_argument(
        "--min-subproblems",
        type=int,
        default=None,
        help="require at least N subproblems (fixture gold)",
    )
    parser.add_argument(
        "--no-brief",
        action="store_true",
        help="only check intake.json (skip brief file)",
    )
    parser.add_argument(
        "--allow-ok-with-ambiguities",
        action="store_true",
        help="do not require status=needs_human when ambiguities non-empty",
    )
    args = parser.parse_args(argv)

    errors = check_intake_files(
        args.intake_path,
        brief_path=args.brief,
        min_subproblems=args.min_subproblems,
        check_brief=not args.no_brief,
        require_needs_human_if_ambiguities=not args.allow_ok_with_ambiguities,
    )
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print("PASS: intake gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
