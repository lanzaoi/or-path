#!/usr/bin/env python3
"""Parse OCR raw → problem-brief.md + intake.json (OR-Path 1.1 S3).

Default path = deterministic template + light regex (specs/problem-intake.md §5.3-A).
Does NOT call solve / modeler. Does NOT invent objective numbers.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_intake import check_brief_text, check_intake_dict  # noqa: E402
from schema_models import INTAKE_SCHEMA_VERSION  # noqa: E402

# --- subproblem markers ---
_Q_LINE = re.compile(
    r"(?im)^(?:#{1,6}\s*)?(?:问题\s*([一二三四五六七八九十\d]+)|"
    r"(?:sub\s*)?problem\s*([0-9]+)|"
    r"q\s*([0-9]+))\s*[:：.、\)]?\s*(.*)$"
)
_Q_INLINE = re.compile(
    r"(?i)\b(?:q\s*([0-9]+)|problem\s*([0-9]+)|问题\s*([一二三四五六七八九十\d]+))\b"
)

_CN_NUM = {
    "一": "1",
    "二": "2",
    "三": "3",
    "四": "4",
    "五": "5",
    "六": "6",
    "七": "7",
    "八": "8",
    "九": "9",
    "十": "10",
}

_ASSET_KIND = {
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".stp": "stp",
    ".step": "stp",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".tif": "image",
    ".tiff": "image",
    ".md": "other",
    ".txt": "other",
}

_DELIVER_HINTS = re.compile(
    r"(?i)(result\d*\.xlsx|solution\.json|schema\.json|\.xlsx|\.csv|报告|论文|deliver)"
)
_OBJ_HINTS = re.compile(
    r"(?i)(minimi[sz]e|maximi[sz]e|最小|最大|主目标|次目标|objective(?!\s*=\s*\d))"
)
_CONSTR_HINTS = re.compile(
    r"(?i)(constraint|约束|capacity|容量|time\s*window|非负|return to|回到)"
)


def _rel(path: Path, root: Path | None) -> str:
    try:
        if root is not None:
            return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        pass
    return str(path).replace("\\", "/")


def _norm_qnum(raw: str) -> str:
    raw = raw.strip()
    if raw.isdigit():
        return raw
    if raw in _CN_NUM:
        return _CN_NUM[raw]
    # 十一 etc. — fallback keep
    return raw


def _strip_ocr_chrome(text: str) -> str:
    """Drop intake_ocr header chrome; keep source bodies."""
    lines = text.splitlines()
    out: list[str] = []
    skip_header = True
    for line in lines:
        if skip_header and line.startswith("# OCR raw"):
            continue
        if skip_header and (line.startswith(">") or line.strip() == ""):
            continue
        skip_header = False
        # drop backend-only lines
        if re.match(r"^backend:\s*`?", line.strip()):
            continue
        out.append(line)
    body = "\n".join(out).strip()
    # remove html page markers but keep text
    body = re.sub(r"<!--\s*pdf page.*?-->", "", body)
    return body.strip() + "\n"


def extract_subproblems(body: str) -> list[dict[str, Any]]:
    """Split body into Q1..Qn blocks via heading-like markers."""
    matches = list(_Q_LINE.finditer(body))
    if not matches:
        # try inline-only presence
        ids = []
        for m in _Q_INLINE.finditer(body):
            n = m.group(1) or m.group(2) or m.group(3)
            if n:
                ids.append(_norm_qnum(n))
        uniq = []
        for i in ids:
            if i not in uniq:
                uniq.append(i)
        if uniq:
            return [
                {
                    "id": f"Q{n}",
                    "title": f"Subproblem Q{n} (marker only; body not split)",
                    "must_deliver": ["model then solve later"],
                    "data_refs": [],
                    "notes": "Detected marker without clear section split.",
                }
                for n in uniq
            ]
        return []

    subs: list[dict[str, Any]] = []
    for i, m in enumerate(matches):
        nraw = m.group(1) or m.group(2) or m.group(3) or str(i + 1)
        n = _norm_qnum(nraw)
        title_rest = (m.group(4) or "").strip() or f"Subproblem Q{n}"
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        chunk = body[start:end].strip()
        # deliverable hints in chunk
        delivers = sorted({x.group(0) for x in _DELIVER_HINTS.finditer(chunk)})
        if not delivers:
            delivers = ["model description", "solver-backed answer at solve stage"]
        notes = chunk[:400] + ("…" if len(chunk) > 400 else "")
        subs.append(
            {
                "id": f"Q{n}",
                "title": title_rest[:200],
                "must_deliver": delivers[:12],
                "data_refs": [],
                "notes": notes or None,
            }
        )
    # stable unique by id (first wins)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for sp in subs:
        if sp["id"] in seen:
            continue
        seen.add(sp["id"])
        out.append(sp)
    return out


def guess_problem_class_hint(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\bvrp\b|vehicle routing|多车|车辆路径", t):
        return "vrp"
    if re.search(r"\btsp\b|traveling salesman|旅行商", t):
        return "tsp"
    if re.search(r"shortest\s*path|最短路", t):
        return "shortest_path"
    return None


def extract_bulletish(text: str, pattern: re.Pattern[str], limit: int = 8) -> list[str]:
    hits: list[str] = []
    for line in text.splitlines():
        s = line.strip().lstrip("-*•").strip()
        if not s:
            continue
        if pattern.search(s):
            hits.append(s[:240])
        if len(hits) >= limit:
            break
    return hits


def scan_assets(assets_dir: Path | None, root: Path | None) -> list[dict[str, Any]]:
    if assets_dir is None or not assets_dir.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for p in sorted(assets_dir.rglob("*")):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        kind = _ASSET_KIND.get(p.suffix.lower(), "other")
        role = "unknown"
        name_l = p.name.lower()
        if "template" in name_l or name_l.startswith("result"):
            role = "result_template"
        elif "demand" in name_l or "需求" in p.name:
            role = "demand_table"
        elif kind in {"csv", "stp"}:
            role = "geometry" if kind == "stp" else "unknown"
        items.append(
            {
                "path": _rel(p, root),
                "kind": kind,
                "role": role,
            }
        )
        if len(items) >= 200:
            break
    return items


def _sources_from_meta(meta: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in meta.get("sources") or []:
        if not isinstance(s, dict):
            continue
        path = s.get("path")
        if not path:
            continue
        item: dict[str, Any] = {"path": str(path)}
        if s.get("kind"):
            item["kind"] = s["kind"]
        if s.get("pages") is not None:
            item["pages"] = s["pages"]
        if s.get("sha256"):
            item["sha256"] = s["sha256"]
        out.append(item)
    return out


def build_brief(
    *,
    slug: str,
    body: str,
    sources: list[dict[str, Any]],
    subproblems: list[dict[str, Any]],
    data_assets: list[dict[str, Any]],
    objectives: list[str],
    constraints: list[str],
    deliverables: list[str],
    ambiguities: list[str],
    ocr_backend: str,
) -> str:
    src_lines = []
    for s in sources:
        src_lines.append(f"- `{s.get('path')}` ({s.get('kind') or 'source'})")
    if not src_lines:
        src_lines = ["- (no sources listed in OCR meta)"]

    if subproblems:
        sp_lines = []
        for sp in subproblems:
            sp_lines.append(f"### {sp['id']}")
            sp_lines.append(sp.get("title") or "")
            if sp.get("notes"):
                sp_lines.append("")
                sp_lines.append(str(sp["notes"])[:800])
            sp_lines.append("")
            md = sp.get("must_deliver") or []
            if md:
                sp_lines.append("Must deliver later: " + "; ".join(str(x) for x in md))
            sp_lines.append("")
        sp_block = "\n".join(sp_lines).rstrip()
    else:
        sp_block = (
            "### Q1\n"
            "Single undivided statement (no Q1/Q2 markers found in OCR). "
            "Treat as one modeling task until human splits subproblems.\n"
        )

    if data_assets:
        da_lines = [f"- `{a['path']}` — kind={a.get('kind')}, role={a.get('role')}" for a in data_assets]
    else:
        da_lines = ["- (none registered; attach via --assets if available)"]

    obj_lines = [f"- {o}" for o in objectives] or [
        "- Qualitative: optimize the criteria stated in the problem text (no numeric optima here)."
    ]
    con_lines = [f"- {c}" for c in constraints] or [
        "- See problem statement; constraints not auto-extracted as a clean list."
    ]
    del_lines = [f"- {d}" for d in deliverables] or [
        "- Modeling schema (no optima)",
        "- Solver-backed solution JSON after solve stage",
    ]
    amb_lines = [f"- {a}" for a in ambiguities] or ["- None detected by deterministic parse."]

    # keep statement truncated for huge OCR
    statement = body.strip()
    if len(statement) > 6000:
        statement = statement[:6000] + "\n\n…[truncated for brief; full text in ocr.raw]…"

    return f"""# Problem brief — {slug}

## Sources
{chr(10).join(src_lines)}
- ocr_backend: `{ocr_backend}`

## Full problem statement (normalized)
{statement}

## Subproblems (Q1…Qn)
{sp_block}

## Data assets
{chr(10).join(da_lines)}

## Objectives (qualitative)
{chr(10).join(obj_lines)}

## Constraints (qualitative)
{chr(10).join(con_lines)}

## Deliverables
{chr(10).join(del_lines)}

## Ambiguities / OCR gaps
{chr(10).join(amb_lines)}

## Non-goals for intake
- No objective / optimal numeric claims
- No calling solvers or writing solution.json
- Soft class hints are not a validated schema
"""


@dataclass
class ParseResult:
    slug: str
    status: str
    brief_path: str
    intake_path: str
    intake: dict[str, Any] = field(default_factory=dict)
    brief_text: str = ""
    gate_errors: list[str] = field(default_factory=list)


def run_parse(
    *,
    slug: str,
    ocr_raw: Path,
    ocr_meta: Path | None = None,
    root: Path | None = None,
    notes_dir: Path | None = None,
    outputs_dir: Path | None = None,
    assets_dir: Path | None = None,
    run_gate: bool = True,
) -> ParseResult:
    if not slug or not str(slug).strip():
        raise ValueError("slug required")
    if not ocr_raw.is_file():
        raise FileNotFoundError(f"ocr raw not found: {ocr_raw}")

    root_p = root.resolve() if root else None
    notes = notes_dir or ((root_p / "notes") if root_p else Path("notes"))
    outputs = outputs_dir or ((root_p / "outputs") if root_p else Path("outputs"))
    notes.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    raw_text = ocr_raw.read_text(encoding="utf-8", errors="replace")
    body = _strip_ocr_chrome(raw_text)

    meta: dict[str, Any] = {}
    meta_path = ocr_meta
    if meta_path is None:
        # conventional sibling
        cand = ocr_raw.with_name(ocr_raw.name.replace("-ocr.raw.md", "-ocr.meta.json"))
        if cand.is_file():
            meta_path = cand
        else:
            sib = ocr_raw.parent / f"{slug}-ocr.meta.json"
            if sib.is_file():
                meta_path = sib
    if meta_path and meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    ocr_backend = str(meta.get("backend") or "unknown")
    sources = _sources_from_meta(meta)
    if not sources:
        sources = [{"path": _rel(ocr_raw, root_p), "kind": "text"}]

    data_assets = scan_assets(assets_dir, root_p)
    # also register source files as assets when they look like data
    for s in sources:
        p = str(s.get("path") or "")
        suf = Path(p).suffix.lower()
        if suf in _ASSET_KIND and not any(a["path"] == p for a in data_assets):
            data_assets.append(
                {
                    "path": p,
                    "kind": _ASSET_KIND.get(suf, "other"),
                    "role": "problem_statement"
                    if suf in {".txt", ".md"}
                    else "unknown",
                }
            )

    subs = extract_subproblems(body)
    ambiguities: list[str] = []
    if meta.get("warnings"):
        for w in meta["warnings"]:
            ambiguities.append(f"OCR warning: {w}")
    if meta.get("status") == "error":
        ambiguities.append("OCR meta status=error")
    if not subs:
        ambiguities.append(
            "No explicit Q1/Q2/问题N markers found; emitted single synthetic Q1 covering full text"
        )
        subs = [
            {
                "id": "Q1",
                "title": "Full statement (unsplit)",
                "must_deliver": [
                    "model description",
                    "solver-backed answer at solve stage",
                ],
                "data_refs": [a["path"] for a in data_assets[:5]],
                "notes": body[:500] + ("…" if len(body) > 500 else ""),
            }
        ]

    # attach data_refs default
    for sp in subs:
        if not sp.get("data_refs"):
            sp["data_refs"] = [a["path"] for a in data_assets[:8]]

    objectives = extract_bulletish(body, _OBJ_HINTS)
    constraints = extract_bulletish(body, _CONSTR_HINTS)
    deliverables: list[str] = []
    for sp in subs:
        for d in sp.get("must_deliver") or []:
            if d not in deliverables:
                deliverables.append(str(d))
    for m in _DELIVER_HINTS.finditer(body):
        t = m.group(0)
        if t not in deliverables:
            deliverables.append(t)

    status = "ok"
    if ambiguities:
        # OCR gaps / unsplit → needs_human per gate rule when non-empty
        status = "needs_human"

    brief_path = notes / f"{slug}-problem-brief.md"
    intake_path = outputs / f"{slug}-intake.json"
    brief_rel = _rel(brief_path, root_p)
    raw_rel = _rel(ocr_raw, root_p)
    meta_rel = _rel(meta_path, root_p) if meta_path and meta_path.is_file() else ""

    brief_text = build_brief(
        slug=slug,
        body=body,
        sources=sources,
        subproblems=subs,
        data_assets=data_assets,
        objectives=objectives,
        constraints=constraints,
        deliverables=deliverables,
        ambiguities=ambiguities,
        ocr_backend=ocr_backend,
    )
    brief_path.write_text(brief_text, encoding="utf-8")

    intake: dict[str, Any] = {
        "slug": slug,
        "schema_version": INTAKE_SCHEMA_VERSION,
        "status": status,
        "sources": sources,
        "subproblems": [
            {
                "id": sp["id"],
                "title": sp["title"],
                "must_deliver": list(sp.get("must_deliver") or []),
                "data_refs": list(sp.get("data_refs") or []),
                **({"notes": sp["notes"]} if sp.get("notes") else {}),
            }
            for sp in subs
        ],
        "data_assets": data_assets,
        "constraints_text": "; ".join(constraints)
        if constraints
        else "See brief Constraints section (auto-extract sparse).",
        "objectives_text": "; ".join(objectives)
        if objectives
        else "See brief Objectives section (qualitative only).",
        "deliverables": deliverables,
        "ambiguities": ambiguities,
        "brief_path": brief_rel,
        "ocr_raw_path": raw_rel,
        "ocr_meta_path": meta_rel or raw_rel.replace("-ocr.raw.md", "-ocr.meta.json"),
        "ocr_backend": ocr_backend,
        "problem_class_hint": guess_problem_class_hint(body),
        "problem_id_hint": None,
    }

    intake_path.write_text(
        json.dumps(intake, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    gate_errors: list[str] = []
    if run_gate:
        gate_errors.extend(check_intake_dict(intake, min_subproblems=1))
        gate_errors.extend(check_brief_text(brief_text))

    return ParseResult(
        slug=slug,
        status=status if not gate_errors else "error",
        brief_path=brief_rel,
        intake_path=_rel(intake_path, root_p),
        intake=intake,
        brief_text=brief_text,
        gate_errors=gate_errors,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="OR-Path 1.1 intake parse (OCR → brief+json)")
    p.add_argument("--slug", required=True)
    p.add_argument("--ocr-raw", type=Path, required=True, help="notes/<slug>-ocr.raw.md")
    p.add_argument("--ocr-meta", type=Path, default=None)
    p.add_argument("--root", type=Path, default=None)
    p.add_argument("--notes-dir", type=Path, default=None)
    p.add_argument("--outputs-dir", type=Path, default=None)
    p.add_argument("--assets", type=Path, default=None, help="optional unpacked assets dir")
    p.add_argument("--no-gate", action="store_true", help="skip gate_intake self-check")
    p.add_argument("--json", action="store_true", help="print intake.json to stdout")
    args = p.parse_args(argv)

    try:
        result = run_parse(
            slug=args.slug,
            ocr_raw=args.ocr_raw,
            ocr_meta=args.ocr_meta,
            root=args.root,
            notes_dir=args.notes_dir,
            outputs_dir=args.outputs_dir,
            assets_dir=args.assets,
            run_gate=not args.no_gate,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.intake, indent=2, ensure_ascii=False))
    else:
        print(f"status={result.status}")
        print(f"brief={result.brief_path}")
        print(f"intake={result.intake_path}")
        print(f"subproblems={len(result.intake.get('subproblems') or [])}")

    if result.gate_errors:
        for e in result.gate_errors:
            print(f"FAIL gate: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
