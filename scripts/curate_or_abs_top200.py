#!/usr/bin/env python3
"""Freeze Top-200 lit_abs notes without thrashing APIs.

Uses already-known abstracts first; pads to 200 with high-rank title+modeling
notes explicitly marked abstract_unavailable (still no fulltext).
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP = ROOT / "knowledge" / "or_papers_top500.json"
MAN500 = ROOT / "knowledge" / "or_lit_abs_manifest.json"
OUT = ROOT / "knowledge" / "corpus" / "papers" / "lit_abs"
OVERFLOW = ROOT / "knowledge" / "archive" / "lit_abs_overflow"
MAN200 = ROOT / "knowledge" / "or_lit_abs_top200_manifest.json"
TARGET = 200
MAX_ABS = 1800


def clean_abs(s: str | None) -> str:
    if not s:
        return ""
    t = re.sub(r"<[^>]+>", " ", s)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > MAX_ABS:
        t = t[: MAX_ABS - 1].rsplit(" ", 1)[0] + "…"
    return t


def extract_abs_from_md(path: Path) -> str:
    t = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"## Abstract \(from public metadata APIs\)\n\n(.+?)\n\n##", t, re.S)
    if not m:
        return ""
    a = clean_abs(m.group(1))
    if "No public abstract" in a or "No abstract" in a:
        return ""
    return a if len(a) >= 60 else ""


def core_bullets(title: str, abstract: str, domains: list[str]) -> list[str]:
    blob = f"{title}. {abstract}".lower()
    bullets: list[str] = []

    def add(s: str) -> None:
        if s not in bullets and len(bullets) < 6:
            bullets.append(s)

    pairs = [
        (r"vehicle routing|vrp\b", "Problem class: vehicle routing / fleet tours."),
        (r"traveling salesman|travelling salesman|\btsp\b", "Problem class: TSP / tour sequencing."),
        (r"shortest path|dijkstra", "Problem class: shortest path on a network."),
        (r"job.?shop|machine scheduling|project scheduling|rcpsp", "Problem class: scheduling."),
        (r"bin packing|cutting stock|knapsack", "Problem class: packing / cutting / knapsack."),
        (r"facility location|set cover", "Problem class: location / covering."),
        (r"network flow|max(?:imum)? flow|min(?:imum)?[- ]cost flow", "Problem class: network flows."),
        (r"robust optim|distributionally robust|stochastic program|chance.constrain", "Uncertainty: robust/DRO/stochastic/chance constraints."),
        (r"mixed.?integer|milp|\bmip\b|integer program", "Model family: mixed-integer programming."),
        (r"linear program|interior.point|simplex", "Model family: linear / continuous LP."),
        (r"constraint program|cp-sat", "Model family: constraint programming / CP-SAT."),
        (r"column generation|branch.and.price|benders|lagrangian", "Method: decomposition (CG/Benders/Lagrangian/B&P)."),
        (r"branch.and.cut|cutting plane", "Method: branch-and-cut / cutting planes."),
        (r"dynamic program|bellman|markov decision", "Method: DP / MDP sequential decisions."),
        (r"tabu|large neighborhood|metaheuristic|genetic algorithm", "Method: metaheuristic / neighborhood search."),
        (r"convex optim|semidefinite|quadratic program", "Model family: convex / conic / QP."),
        (r"machine learning|learning to branch|neural combinatorial", "Hybrid: learning-assisted CO (no case optima from lit)."),
        (r"time window", "Key constraints: time windows."),
        (r"multiobjective|multi-objective|pareto", "Multi-objective / Pareto trade-offs."),
        (r"survey|review|tour d", "Document type: survey/review — use for landscape, not numeric answers."),
    ]
    for pat, msg in pairs:
        if re.search(pat, blob):
            add(msg)
    if not bullets:
        add(f"OR tags: {', '.join((domains or [])[:3]) or 'general_or'}. Literature pointer only.")
        add("Build model from problem text; numbers only via solve+validate.")
    add("RAG: method pointer only — never treat lit numbers as user-case optima.")
    return bullets


def write_note(p: dict, abstract: str, abs_src: str, out_rank: int, has_abs: bool) -> Path:
    rank = int(p.get("rank") or 0)
    title = (p.get("title") or "Untitled").strip()
    authors = ", ".join(p.get("authors") or [])[:200]
    domains = p.get("domains") or []
    primary = domains[0] if domains else "general_or"
    doi = (p.get("doi") or "").strip()
    dsafe = re.sub(r"[^\w.\-]+", "_", doi)[:28] if doi else "nodoi"
    path = OUT / f"t{out_rank:03d}_src{rank:03d}_{dsafe}.md"
    bullets = core_bullets(title, abstract, domains)
    lines = [
        f"# {title}",
        "",
        "- kind: paper-note",
        "- content_class: abstract_plus_modeling_sketch",
        f"- domain: {primary}",
        f"- domains_all: {', '.join(domains) if domains else primary}",
        f"- source: api-metadata ({abs_src})",
        f"- top200_rank: {out_rank}",
        f"- source_top500_rank: {rank}",
        f"- year: {p.get('year')}",
        f"- venue: {p.get('venue') or ''}",
        f"- citations_index: {p.get('cited_by_count')}",
        f"- has_public_abstract: {'yes' if has_abs else 'no'}",
        "- fulltext: no",
        "- copyright_policy: abstract+metadata only; no PDF body dump",
        "- numbers_policy: literature never authoritative optima; solve+validate only",
        "",
    ]
    if authors:
        lines.append(f"- authors: {authors}")
    if doi:
        lines.append(f"- doi: https://doi.org/{doi}")
    if p.get("arxiv_id"):
        lines.append(f"- arxiv: https://arxiv.org/abs/{p['arxiv_id']}")
    lines += ["", "## Abstract (from public metadata APIs)", ""]
    if has_abs:
        lines.append(abstract)
    else:
        lines.append(
            "_Public abstract not available via APIs at curation time. "
            "Modeling sketch below is title/venue-derived only._"
        )
    lines += ["", "## Core modeling sketch (from title+abstract only)", ""]
    for b in bullets:
        lines.append(f"- {b}")
    lines += ["", "## Not included", "", "- Full paper body / proofs / tables", "- Case optima numbers", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    papers = {int(p["rank"]): p for p in json.loads(TOP.read_text(encoding="utf-8"))["papers"]}
    man500 = json.loads(MAN500.read_text(encoding="utf-8")) if MAN500.exists() else {"items": {}}

    with_abs: list[tuple[int, str, str]] = []  # rank, abs, src
    without: list[int] = []

    # scan overflow + current out + top snip + man500
    search_dirs = [OUT, OVERFLOW]
    for rank in range(1, 501):
        p = papers[rank]
        abs_text = clean_abs(p.get("abstract_snip") or "")
        src = "top500_snip" if len(abs_text) >= 60 else "none"
        if len(abs_text) < 60:
            for d in search_dirs:
                if not d.exists():
                    continue
                for f in list(d.glob(f"r{rank:03d}_*.md")) + list(d.glob(f"*src{rank:03d}_*.md")) + list(
                    d.glob(f"t*_src{rank:03d}_*.md")
                ):
                    a = extract_abs_from_md(f)
                    if len(a) >= 60:
                        abs_text, src = a, "existing_note"
                        break
                if len(abs_text) >= 60:
                    break
        # man chars hint only
        if len(abs_text) >= 60:
            with_abs.append((rank, abs_text, src))
        else:
            without.append(rank)

    with_abs.sort(key=lambda x: x[0])
    print(f"with_abs={len(with_abs)} without={len(without)}", flush=True)

    selected: list[tuple[int, str, str, bool]] = []
    for rank, a, src in with_abs:
        if len(selected) >= TARGET:
            break
        selected.append((rank, a, src, True))

    # pad with high-ranked without abs (keep list quality)
    for rank in without:
        if len(selected) >= TARGET:
            break
        selected.append((rank, "", "unavailable", False))

    selected = selected[:TARGET]
    n_abs = sum(1 for *_, h in selected if h)
    print(f"selected={len(selected)} with_public_abs={n_abs}", flush=True)

    OVERFLOW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    # clear active lit_abs notes into overflow
    for f in list(OUT.glob("*.md")):
        if f.name == "_INDEX.md":
            f.unlink(missing_ok=True)
            continue
        dest = OVERFLOW / f.name
        if dest.exists():
            dest = OVERFLOW / f"{f.stem}_{int(time.time())}{f.suffix}"
        shutil.move(str(f), str(dest))

    items = {}
    for i, (rank, abs_text, src, has) in enumerate(selected, 1):
        p = papers[rank]
        path = write_note(p, abs_text, src, i, has)
        items[f"t{i:03d}"] = {
            "top200_rank": i,
            "source_top500_rank": rank,
            "title": p.get("title"),
            "doi": p.get("doi"),
            "abstract_source": src,
            "abstract_chars": len(abs_text) if has else 0,
            "has_public_abstract": has,
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "year": p.get("year"),
            "cited_by_count": p.get("cited_by_count"),
            "domains": p.get("domains"),
        }

    idx = [
        "# OR literature Top-200 — abstract + modeling only",
        "",
        "- kind: paper-note",
        "- content_class: index",
        f"- n: {len(items)}",
        f"- with_public_abstract: {n_abs}",
        f"- title_only_pad: {len(items) - n_abs}",
        "- fulltext: no",
        "",
        "## Notes",
        "",
    ]
    for k in sorted(items.keys()):
        v = items[k]
        flag = "ABS" if v["has_public_abstract"] else "TITLE"
        idx.append(
            f"- **T{v['top200_rank']:03d}** [{flag}] (src R{v['source_top500_rank']:03d}) "
            f"[{Path(v['path']).name}]({Path(v['path']).name}) — {v['title']}"
        )
    (OUT / "_INDEX.md").write_text("\n".join(idx) + "\n", encoding="utf-8")

    man = {
        "policy": "abstract_plus_modeling_sketch_only",
        "target": TARGET,
        "n": len(items),
        "with_public_abstract": n_abs,
        "title_only_pad": len(items) - n_abs,
        "out_dir": "knowledge/corpus/papers/lit_abs",
        "overflow_dir": "knowledge/archive/lit_abs_overflow",
        "items": items,
    }
    MAN200.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")

    corpus = ROOT / "knowledge" / "CORPUS.md"
    t = corpus.read_text(encoding="utf-8") if corpus.exists() else ""
    if "Top-200 abstract" not in t and "lit_abs Top-200" not in t:
        corpus.write_text(
            t.rstrip()
            + "\n\n## lit_abs Top-200 (active)\n\n"
            + "Active set: **200** notes in `corpus/papers/lit_abs/` "
            + f"(~{n_abs} with public abstract; rest title+modeling pad).\n"
            + "Overflow: `archive/lit_abs_overflow/`.\n"
            + "Manifest: `knowledge/or_lit_abs_top200_manifest.json`.\n\n",
            encoding="utf-8",
        )

    print("DONE", man["n"], "abs", n_abs, "pad", man["title_only_pad"], flush=True)


if __name__ == "__main__":
    main()
