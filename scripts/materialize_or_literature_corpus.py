#!/usr/bin/env python3
"""Materialize OR paper shortlist → knowledge/corpus/papers/lit/*.md (Pi RAG).

Reads knowledge/or_papers_top500.json (or top200). Does NOT download PDFs by default.
Each note gets kind/title/source/domain frontmatter for Phase2 metadata gates.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOMAIN_MAP = {
    "tsp_routing": "tsp",
    "network_flows": "shortest_path",
    "graph_or": "shortest_path",
    "cutting_packing": "polyomino_cover",
    "scheduling": "general_or",
    "integer_programming": "general_or",
    "linear_programming": "general_or",
    "column_generation_decomp": "vrp",
    "constraint_programming": "general_or",
    "combinatorial_optimization": "general_or",
    "metaheuristics": "general_or",
    "dynamic_programming": "general_or",
    "inventory_supply_chain": "general_or",
    "stochastic_or": "general_or",
    "or_foundations_survey": "general_or",
    "nonlinear_convex": "general_or",
    "multiobjective": "general_or",
    "queuing_simulation": "general_or",
    "game_theory_or": "general_or",
    "ml_or_hybrid": "general_or",
}


def _safe_stem(s: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE).strip("_")
    return (s or "paper")[:72]


def _domain_of(p: dict) -> str:
    q = str(p.get("query") or p.get("domain") or p.get("primary_domain") or "").lower()
    for k, v in DOMAIN_MAP.items():
        if k in q:
            return v
    # title heuristics
    t = str(p.get("title") or "").lower()
    if "vehicle routing" in t or "cvrp" in t or "vrp" in t:
        return "vrp"
    if "traveling salesman" in t or "tsp" in t:
        return "tsp"
    if "shortest path" in t or "dijkstra" in t:
        return "shortest_path"
    if "polyomino" in t or "packing" in t:
        return "polyomino_cover"
    return "general_or"


def load_papers(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.get("papers") or [])
    return []


def prefer_or_order(papers: list[dict]) -> list[dict]:
    """Prefer OR-ish domains / titles over pure NumPy fame."""
    prefer_keys = (
        "tsp",
        "routing",
        "vehicle",
        "scheduling",
        "integer programming",
        "linear programming",
        "column generation",
        "constraint programming",
        "cutting",
        "packing",
        "shortest path",
        "network flow",
        "branch-and",
        "or-tools",
        "cplex",
        "gurobi",
        "optimization",
        "operations research",
    )

    def score(p: dict) -> tuple:
        t = str(p.get("title") or "").lower()
        q = str(p.get("query") or "").lower()
        blob = t + " " + q
        hit = sum(1 for k in prefer_keys if k in blob)
        cites = int(p.get("cited_by_count") or 0)
        year = int(p.get("year") or 0)
        return (-hit, -min(cites, 5000), -year)

    return sorted(papers, key=score)


def write_note(out_dir: Path, p: dict, idx: int) -> Path | None:
    title = (p.get("title") or "").strip()
    if not title or len(title) < 8:
        return None
    doi = (p.get("doi") or "").strip()
    year = p.get("year") or ""
    source_api = p.get("source_api") or "shortlist"
    oa = p.get("oa_url") or p.get("landing") or (f"https://doi.org/{doi}" if doi else "")
    authors = p.get("authors") or []
    if isinstance(authors, list):
        authors_s = ", ".join(str(a) for a in authors[:8])
        if len(authors) > 8:
            authors_s += ", et al."
    else:
        authors_s = str(authors)
    venue = p.get("venue") or ""
    abstract = (p.get("abstract_snip") or p.get("abstract") or "").strip()
    domain = _domain_of(p)
    stem = _safe_stem(f"lit_{idx:03d}_{title[:40]}")
    path = out_dir / f"{stem}.md"
    body = f"""# {title}

- kind: paper-note
- title: {title}
- source: doi:{doi if doi else "shortlist"}
- source_api: {source_api}
- domain: {domain}
- year: {year}
- date: {date.today().isoformat()}
- venue: {venue}
- authors: {authors_s}
- landing: {oa}
- note: Bibliography note for Pi hybrid retrieve — **not** full PDF text; not numeric authority.

## Abstract / snippet

{abstract if abstract else "(no abstract in shortlist metadata)"}

## Why in OR-Path corpus

Curated from `knowledge/or_papers_top*.json` shortlist for research-context retrieval.
Solver optima remain solve+validate only.

## Cite keys

- DOI: `{doi or "n/a"}`
- API: `{source_api}`
"""
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path


def normalize_existing_papers(papers_dir: Path) -> int:
    """Ensure kind/title/source lines on curated md (non-destructive)."""
    n = 0
    for path in sorted(papers_dir.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        head = text[:1200]
        if re.search(r"(?im)^-\s*title:\s*\S+", head) and re.search(
            r"(?im)^-\s*source:\s*\S+", head
        ):
            continue
        lines = text.splitlines()
        title = path.stem.replace("_", " ")
        for ln in lines[:5]:
            if ln.startswith("# "):
                title = ln[2:].strip()
                break
        kind = "paper-note"
        if "paper-mineru" in head or "_from_mineru" in str(path).replace("\\", "/"):
            kind = "paper-mineru"
        source = "curated"
        if "doi:" in head.lower():
            m = re.search(r"doi:[\w./-]+", head, re.I)
            if m:
                source = m.group(0)
        elif "source_pdf:" in head:
            m = re.search(r"source_pdf:\s*(\S+)", head)
            if m:
                source = f"path:{m.group(1)}"
        meta = [
            f"- kind: {kind}",
            f"- title: {title}",
            f"- source: {source}",
        ]
        # insert after first heading
        if lines and lines[0].startswith("#"):
            insert_at = 1
            # skip existing blank
            while insert_at < len(lines) and not lines[insert_at].strip():
                insert_at += 1
            block = [""] + meta + [""]
            # avoid dup kind lines clutter - only if missing title
            lines[insert_at:insert_at] = block
            path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
            n += 1
        else:
            path.write_text("# " + title + "\n\n" + "\n".join(meta) + "\n\n" + text)
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--list",
        type=Path,
        default=ROOT / "knowledge" / "or_papers_top500.json",
        help="Shortlist JSON",
    )
    ap.add_argument("--top", type=int, default=40, help="How many lit notes to write")
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "knowledge" / "corpus" / "papers" / "lit",
        help="Output directory",
    )
    ap.add_argument("--normalize-existing", action="store_true", help="Stamp title/source on corpus papers")
    ap.add_argument("--clear-lit", action="store_true", help="Remove previous lit/*.md first")
    args = ap.parse_args(argv)

    if not args.list.is_file():
        # fallback top200
        alt = ROOT / "knowledge" / "or_papers_top200.json"
        if alt.is_file():
            args.list = alt
        else:
            print(f"FAIL shortlist missing: {args.list}", file=sys.stderr)
            return 2

    papers = load_papers(args.list)
    papers = prefer_or_order(papers)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.clear_lit:
        for p in args.out.glob("*.md"):
            p.unlink()

    written: list[str] = []
    seen_doi: set[str] = set()
    for p in papers:
        if len(written) >= args.top:
            break
        doi = str(p.get("doi") or "").lower()
        if doi and doi in seen_doi:
            continue
        if doi:
            seen_doi.add(doi)
        path = write_note(args.out, p, len(written) + 1)
        if path:
            written.append(str(path.relative_to(ROOT)).replace("\\", "/"))

    norm = 0
    if args.normalize_existing:
        norm = normalize_existing_papers(ROOT / "knowledge" / "corpus" / "papers")

    out = {
        "status": "OK",
        "shortlist": str(args.list).replace("\\", "/"),
        "n_written": len(written),
        "out_dir": str(args.out).replace("\\", "/"),
        "normalized_existing": norm,
        "files": written[:20],
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    man = ROOT / "notes" / "lit-materialize-last.json"
    man.parent.mkdir(parents=True, exist_ok=True)
    man.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
