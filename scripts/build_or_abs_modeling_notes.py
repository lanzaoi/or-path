#!/usr/bin/env python3
"""Build abstract + core-modeling short notes for Top500 (NO fulltext body).

Policy (copyright-minimizing):
- Use title / authors / venue / DOI / year / abstract only (API metadata).
- "Core modeling" bullets are short, abstract-derived method pointers — not paper body quotes.
- Does NOT copy PDF fulltext into corpus.

Outputs:
  knowledge/corpus/papers/lit_abs/rNNN_*.md
  knowledge/corpus/papers/lit_abs/_INDEX.md
  knowledge/or_lit_abs_manifest.json

Optionally relocates prior OA fulltext extracts out of corpus:
  knowledge/archive/oa_fulltext_hold/
"""
from __future__ import annotations

import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP = ROOT / "knowledge" / "or_papers_top500.json"
OUT = ROOT / "knowledge" / "corpus" / "papers" / "lit_abs"
MAN = ROOT / "knowledge" / "or_lit_abs_manifest.json"
HOLD = ROOT / "knowledge" / "archive" / "oa_fulltext_hold"
FROM_MINERU = ROOT / "knowledge" / "corpus" / "papers" / "_from_mineru"
MAILTO = "orpath-rag@users.noreply.github.com"
UA = f"OR-Path-abs-notes/1.0 (mailto:{MAILTO}; abstract-only RAG)"

OUT.mkdir(parents=True, exist_ok=True)

# strip very long residual fulltext if any sneaks in
MAX_ABS = 1800
MAX_MODEL_BULLETS = 6


def http_json(url: str, timeout: int = 45) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def clean_abs(s: str | None) -> str:
    if not s:
        return ""
    t = re.sub(r"<[^>]+>", " ", s)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > MAX_ABS:
        t = t[: MAX_ABS - 1].rsplit(" ", 1)[0] + "…"
    return t


def fetch_crossref_abs(doi: str) -> str:
    if not doi:
        return ""
    d = http_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}?mailto={MAILTO}")
    if not d:
        return ""
    msg = d.get("message") or {}
    return clean_abs(msg.get("abstract") or "")


def fetch_openalex_abs(doi: str) -> str:
    if not doi:
        return ""
    d = http_json(
        f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi)}?mailto={MAILTO}"
    )
    if not d:
        return ""
    inv = d.get("abstract_inverted_index") or {}
    if not inv:
        return ""
    pos = []
    for w, idxs in inv.items():
        for i in idxs:
            pos.append((i, w))
    pos.sort()
    return clean_abs(" ".join(w for _, w in pos))


def fetch_s2_abs(doi: str) -> str:
    if not doi:
        return ""
    d = http_json(
        "https://api.semanticscholar.org/graph/v1/paper/DOI:"
        + urllib.parse.quote(doi)
        + "?fields=abstract,title"
    )
    if not d:
        return ""
    return clean_abs(d.get("abstract") or "")


def resolve_abstract(p: dict) -> tuple[str, str]:
    """Return (abstract, source)."""
    existing = clean_abs(p.get("abstract_snip") or "")
    if len(existing) >= 80:
        return existing, "top500_snip"
    doi = (p.get("doi") or "").strip()
    # try openalex first (good inverted abstracts), then crossref, then s2
    for name, fn in (
        ("openalex", fetch_openalex_abs),
        ("crossref", fetch_crossref_abs),
        ("semanticscholar", fetch_s2_abs),
    ):
        try:
            a = fn(doi)
            time.sleep(0.05 + random.random() * 0.05)
        except Exception:
            a = ""
        if len(a) >= 60:
            return a, name
    if existing:
        return existing, "top500_snip_short"
    return "", "none"


def core_modeling_bullets(title: str, abstract: str, domains: list[str]) -> list[str]:
    """Heuristic method pointers from title+abstract only — short, non-verbatim body."""
    blob = f"{title}. {abstract}".lower()
    bullets: list[str] = []

    def add(s: str) -> None:
        if s not in bullets and len(bullets) < MAX_MODEL_BULLETS:
            bullets.append(s)

    # problem class
    if re.search(r"vehicle routing|vrp|capacitated.*rout", blob):
        add("Problem class: vehicle routing / fleet routing (capacity, tours, depots).")
    if re.search(r"traveling salesman|travelling salesman|\btsp\b", blob):
        add("Problem class: TSP / tour sequencing on a complete or metric graph.")
    if re.search(r"shortest path|dijkstra|bellman", blob):
        add("Problem class: shortest-path / path-finding on a network.")
    if re.search(r"job.?shop|machine scheduling|project scheduling|rcpsp", blob):
        add("Problem class: scheduling (machines/jobs/resources over time).")
    if re.search(r"bin packing|cutting stock|knapsack|packing", blob):
        add("Problem class: packing / cutting / knapsack-style selection under capacity.")
    if re.search(r"facility location|p-median|set cover|set partition", blob):
        add("Problem class: location / covering / set-partition structure.")
    if re.search(r"network flow|max(?:imum)? flow|min(?:imum)?[- ]cost flow", blob):
        add("Problem class: network flows (max-flow / min-cost flow).")
    if re.search(r"markov decision|mdp\b|reinforcement learning", blob):
        add("Problem class: sequential decisions (MDP / learning control).")
    if re.search(r"robust optim|distributionally robust|chance.constrain|stochastic program", blob):
        add("Uncertainty model: robust / DRO / chance-constraint / stochastic programming.")
    if re.search(r"multiobjective|multi-objective|pareto", blob):
        add("Objective structure: multi-objective / Pareto trade-offs.")

    # formulation / algorithm family
    if re.search(r"mixed.?integer|milp|\bmip\b|integer program", blob):
        add("Model family: mixed-integer (linear) programming.")
    if re.search(r"linear program|\blp\b|simplex|interior.point", blob):
        add("Model family: linear programming / continuous convex polyhedron.")
    if re.search(r"constraint program|cp-sat|sat\b", blob):
        add("Model family: constraint programming / CP-SAT style discrete constraints.")
    if re.search(r"column generation|branch.and.price|dantzig-wolfe", blob):
        add("Decomposition: column generation / branch-and-price / Dantzig–Wolfe.")
    if re.search(r"benders", blob):
        add("Decomposition: Benders cuts (master + subproblem).")
    if re.search(r"lagrangian", blob):
        add("Relaxation: Lagrangian dual / subgradient style bounds.")
    if re.search(r"branch.and.cut|cutting plane|valid inequal", blob):
        add("Exact MIP engine ideas: branch-and-cut / cutting planes / valid inequalities.")
    if re.search(r"dynamic program|bellman", blob):
        add("Method: dynamic programming / Bellman recursion.")
    if re.search(r"tabu search|large neighborhood|alns|metaheuristic|genetic algorithm|simulated annealing", blob):
        add("Method: metaheuristic / local-search neighborhood exploration.")
    if re.search(r"semidefinite|second.order cone|convex optim|quadratic program", blob):
        add("Model family: convex / conic / quadratic continuous optimization.")
    if re.search(r"machine learning|graph neural|learning to branch|neural combinatorial", blob):
        add("Hybrid: learning-assisted combinatorial optimization (features/policies, not numeric optima).")

    # decision variables / constraints cues (generic, no numbers)
    if re.search(r"time window", blob):
        add("Key constraints: time windows on visits/services.")
    if re.search(r"capacity", blob):
        add("Key constraints: capacity (vehicle/machine/bin).")
    if re.search(r"precedence|sequence.dependent", blob):
        add("Key constraints: precedence / sequencing.")

    if not bullets:
        dom = ", ".join(domains[:3]) if domains else "general_or"
        add(f"OR topic tags: {dom}. Use as literature pointer only; no authoritative optima.")
        add("Modeling discipline: decision vars + constraints + objective from problem text; numbers only via solve+validate.")

    add("RAG use: method/formulation pointer only — do not treat literature numbers as case optima.")
    return bullets[:MAX_MODEL_BULLETS]


def stem_for(rank: int, title: str, doi: str) -> str:
    base = re.sub(r"[^\w\-]+", "_", (title or "paper").lower()).strip("_")[:40]
    if doi:
        d = re.sub(r"[^\w.\-]+", "_", doi)[:28]
        return f"r{rank:03d}_{d}"
    return f"r{rank:03d}_{base}"


def write_note(p: dict, abstract: str, abs_src: str) -> Path:
    rank = int(p.get("rank") or 0)
    title = (p.get("title") or "Untitled").strip()
    authors = ", ".join(p.get("authors") or [])[:200]
    domains = p.get("domains") or []
    primary = domains[0] if domains else "general_or"
    bullets = core_modeling_bullets(title, abstract, domains)
    doi = (p.get("doi") or "").strip()
    path = OUT / f"{stem_for(rank, title, doi)}.md"

    lines = [
        f"# {title}",
        "",
        "- kind: paper-note",
        "- content_class: abstract_plus_modeling_sketch",
        f"- domain: {primary}",
        f"- domains_all: {', '.join(domains) if domains else primary}",
        f"- source: api-metadata ({abs_src})",
        f"- rank_in_top500: {rank}",
        f"- year: {p.get('year')}",
        f"- venue: {p.get('venue') or ''}",
        f"- citations_index: {p.get('cited_by_count')}",
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
    if abstract:
        lines.append(abstract)
    else:
        lines.append("_No public abstract found via Crossref/OpenAlex/S2. Title/venue only._")
    lines += ["", "## Core modeling sketch (derived from title+abstract only)", ""]
    for b in bullets:
        lines.append(f"- {b}")
    lines += [
        "",
        "## Not included",
        "",
        "- Full paper body / figures / tables / proofs",
        "- Any claimed optimal objective for user cases",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def hold_fulltext_extracts() -> dict:
    """Move prior r*.md fulltext extracts out of active corpus."""
    HOLD.mkdir(parents=True, exist_ok=True)
    moved = []
    if not FROM_MINERU.is_dir():
        return {"moved": 0, "paths": []}
    for p in list(FROM_MINERU.glob("*.md")):
        # only rank extracts like r001_....md — not README/policy/fixtures
        if not re.match(r"^r\d{3}_", p.name, flags=re.I) and not re.match(r"^r\d{3}\.md$", p.name, flags=re.I):
            continue
        dest = HOLD / p.name
        # avoid clobber
        if dest.exists():
            dest = HOLD / f"{p.stem}_{int(time.time())}{p.suffix}"
        p.replace(dest)
        moved.append(str(dest.relative_to(ROOT)).replace("\\", "/"))
    # leave a README in hold
    (HOLD / "README.md").write_text(
        "# OA fulltext hold\n\n"
        "Previously extracted OA PDF fulltexts moved here to keep primary corpus\n"
        "on **abstract + modeling sketch** only (copyright-minimizing).\n"
        "Not deleted. Re-introduce only with explicit policy change.\n",
        encoding="utf-8",
    )
    # marker in _from_mineru (avoid r*.md glob on case-insensitive FS)
    note = FROM_MINERU / "FULLTEXT_POLICY.md"
    note.write_text(
        "# Fulltext policy\n\n"
        "Batch OA fulltext rank extracts were moved to "
        "`knowledge/archive/oa_fulltext_hold/`.\n"
        "Active literature notes: `../lit_abs/` (abstract + modeling sketch only).\n"
        "Fixtures may remain here for gates.\n",
        encoding="utf-8",
    )
    return {"moved": len(moved), "paths": moved[:20], "hold": str(HOLD)}


def main() -> None:
    papers = json.loads(TOP.read_text(encoding="utf-8"))["papers"]
    # clear previous lit_abs
    for old in OUT.glob("r*.md"):
        old.unlink()

    hold_info = hold_fulltext_extracts()
    print("held fulltext", hold_info.get("moved"), flush=True)

    items = {}
    written = []

    def one(p: dict) -> tuple[str, dict, Path | None]:
        rank = int(p.get("rank") or 0)
        key = f"r{rank:03d}"
        abs_text, src = resolve_abstract(p)
        path = write_note(p, abs_text, src)
        rec = {
            "rank": rank,
            "title": p.get("title"),
            "doi": p.get("doi"),
            "abstract_source": src,
            "abstract_chars": len(abs_text),
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        }
        return key, rec, path

    # concurrent abstract fetch
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(one, p) for p in papers]
        done = 0
        for fut in as_completed(futs):
            key, rec, path = fut.result()
            items[key] = rec
            if path:
                written.append(path)
            done += 1
            if done % 50 == 0:
                print(f"progress {done}/{len(papers)}", flush=True)

    # index
    idx_lines = [
        "# OR literature — abstract + modeling sketches (Top 500)",
        "",
        "- kind: paper-note",
        "- content_class: index",
        "- fulltext: no",
        "- policy: abstract/metadata + short modeling bullets only",
        "",
        f"- notes: {len(written)}",
        f"- with_abstract_ge_60: {sum(1 for v in items.values() if v.get('abstract_chars', 0) >= 60)}",
        "",
        "## Files",
        "",
    ]
    for k in sorted(items.keys()):
        v = items[k]
        idx_lines.append(
            f"- [{k}]({Path(v['path']).name}) — abs_chars={v.get('abstract_chars')} src={v.get('abstract_source')} — {v.get('title')}"
        )
    (OUT / "_INDEX.md").write_text("\n".join(idx_lines) + "\n", encoding="utf-8")

    man = {
        "policy": "abstract_plus_modeling_sketch_only",
        "n": len(items),
        "with_abstract_ge_60": sum(1 for v in items.values() if v.get("abstract_chars", 0) >= 60),
        "out_dir": str(OUT.relative_to(ROOT)).replace("\\", "/"),
        "fulltext_held": hold_info,
        "items": items,
    }
    MAN.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")

    # CORPUS.md blurb
    corpus = ROOT / "knowledge" / "CORPUS.md"
    t = corpus.read_text(encoding="utf-8") if corpus.exists() else ""
    block = (
        "\n## lit_abs — abstract + modeling only (copyright-minimizing)\n\n"
        "| Path | Role |\n|------|------|\n"
        "| `corpus/papers/lit_abs/*.md` | Top500 abstract + core modeling sketch |\n"
        "| `archive/oa_fulltext_hold/` | Prior OA fulltext extracts held out of active corpus |\n\n"
        "No paywalled body text. Numbers still only from solve+validate.\n"
    )
    if "lit_abs — abstract" not in t:
        corpus.write_text(t.rstrip() + "\n" + block + "\n", encoding="utf-8")

    print(
        "DONE",
        "notes",
        len(written),
        "abs>=60",
        man["with_abstract_ge_60"],
        "held_fulltext",
        hold_info.get("moved"),
    )


if __name__ == "__main__":
    main()
