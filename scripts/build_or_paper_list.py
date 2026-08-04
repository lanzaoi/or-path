#!/usr/bin/env python3
"""Build real OR paper shortlist (metadata only).

Primary APIs: Crossref (polite pool) + arXiv
Optional: Semantic Scholar / OpenAlex if not rate-limited

No PDF downloads. Resumable checkpoint.
"""
from __future__ import annotations

import csv
import html
import json
import math
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

MAILTO = "orpath-rag@users.noreply.github.com"
CROSSREF = "https://api.crossref.org/works"
ARXIV = "http://export.arxiv.org/api/query"
S2 = "https://api.semanticscholar.org/graph/v1/paper/search"
OPENALEX = "https://api.openalex.org/works"

OUT = Path(__file__).resolve().parents[1] / "knowledge"
OUT.mkdir(parents=True, exist_ok=True)
CKPT = OUT / "or_paper_pool_checkpoint.json"
RAW = OUT / "or_paper_pool_raw.json"
TOP_JSON = OUT / "or_papers_top200.json"
TOP_MD = OUT / "or_papers_top200.md"
CSV_PATH = OUT / "or_papers_top200.csv"
LOG_NOTE = OUT / "or_paper_build_meta.json"

DOMAINS: dict[str, list[str]] = {
    "linear_programming": [
        "linear programming simplex",
        "interior-point method linear programming",
        "linear programming duality",
    ],
    "integer_programming": [
        "mixed-integer linear programming",
        "branch-and-cut integer programming",
        "cutting planes integer programming",
    ],
    "combinatorial_optimization": [
        "combinatorial optimization",
        "submodular optimization",
        "matroid optimization",
    ],
    "network_flows": [
        "maximum flow algorithm",
        "minimum cost flow",
        "shortest path algorithm",
    ],
    "tsp_routing": [
        "traveling salesman problem",
        "vehicle routing problem",
        "vehicle routing problem with time windows",
    ],
    "scheduling": [
        "machine scheduling",
        "job-shop scheduling",
        "resource-constrained project scheduling",
    ],
    "stochastic_or": [
        "stochastic programming",
        "robust optimization",
        "distributionally robust optimization",
    ],
    "dynamic_programming": [
        "dynamic programming",
        "approximate dynamic programming",
        "Markov decision process optimization",
    ],
    "nonlinear_convex": [
        "convex optimization",
        "semidefinite programming",
        "nonlinear programming algorithm",
    ],
    "metaheuristics": [
        "tabu search",
        "large neighborhood search",
        "metaheuristics combinatorial optimization",
    ],
    "multiobjective": [
        "multiobjective optimization",
        "NSGA-II",
        "goal programming",
    ],
    "game_theory_or": [
        "algorithmic game theory",
        "combinatorial auctions",
        "mechanism design optimization",
    ],
    "inventory_supply_chain": [
        "newsvendor model",
        "supply chain optimization",
        "facility location problem",
    ],
    "queuing_simulation": [
        "queueing theory",
        "simulation optimization",
        "discrete-event simulation",
    ],
    "column_generation_decomp": [
        "column generation",
        "Benders decomposition",
        "Dantzig-Wolfe decomposition",
    ],
    "constraint_programming": [
        "constraint programming",
        "constraint satisfaction problem",
        "constraint-based scheduling",
    ],
    "graph_or": [
        "graph coloring algorithm",
        "maximum matching algorithm",
        "Steiner tree problem",
    ],
    "cutting_packing": [
        "bin packing problem",
        "cutting stock problem",
        "knapsack problem algorithm",
    ],
    "ml_or_hybrid": [
        "machine learning combinatorial optimization",
        "neural combinatorial optimization",
        "learning to branch mixed-integer",
    ],
    "or_foundations_survey": [
        "operations research survey",
        "integer programming survey",
        "vehicle routing survey",
    ],
}

OR_HINTS = re.compile(
    r"\b("
    r"optimiz|operations research|operational research|mathematical programming|"
    r"integer program|linear program|mixed.?integer|branch.?and.?cut|branch.?and.?bound|"
    r"column generation|benders|dantzig|lagrangian|cutting plane|"
    r"vehicle routing|traveling salesman|travelling salesman|shortest path|"
    r"network flow|maximum flow|min(?:imum)?.?cost flow|scheduling|job.?shop|"
    r"stochastic program|robust optim|convex optim|semidefinite|"
    r"constraint program|knapsack|bin packing|cutting stock|facility location|"
    r"inventory|supply chain|queueing|queuing|markov decision|dynamic program|"
    r"metaheuristic|tabu search|simulated annealing|large neighborhood|"
    r"combinatorial optim|submodular|matroid|polyhedral|decomposition|"
    r"pareto|multiobjective|multi-objective|newsvendor|simplex|interior.?point|"
    r"packing|routing|CP-SAT|MILP|MIP"
    r")\b",
    re.I,
)

NOISE = re.compile(
    r"\b(ImageNet classification|BERT|GPT-3 language|YOLO object detection|"
    r"AlphaFold protein|COVID-19 vaccine clinical trial)\b",
    re.I,
)

VENUE_BONUS_KEYS = (
    "operations research",
    "operational research",
    "mathematical programming",
    "management science",
    "mathematics of operations research",
    "informs journal",
    "european journal of operational",
    "computers & operations research",
    "computers and operations research",
    "transportation science",
    "networks",
    "siam journal",
    "annals of operations research",
    "or spectrum",
    "journal of scheduling",
    "constraints",
    "journal of global optimization",
    "optimization methods and software",
    "mathematical programming computation",
    "informs journal on computing",
    "transportation research",
)


def strip_tags(s: str | None) -> str:
    if not s:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def load_ckpt() -> dict:
    if CKPT.exists():
        return json.loads(CKPT.read_text(encoding="utf-8"))
    return {"done_keys": [], "papers": {}, "errors": []}


def save_ckpt(state: dict) -> None:
    CKPT.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def http_get(url: str, retries: int = 8) -> bytes:
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": f"OR-Path-paper-list/2.0 (mailto:{MAILTO}; research bibliography)",
                    "Accept": "*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                wait = min(120.0, 4.0 * (2**i) + random.uniform(0, 2))
                print(f"  429 sleep {wait:.1f}s")
                time.sleep(wait)
                continue
            if e.code in (500, 502, 503, 504):
                time.sleep(1.5 * (i + 1))
                continue
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            raise RuntimeError(f"HTTP {e.code}: {body}") from e
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.0 * (i + 1))
    raise RuntimeError(f"GET failed: {last}")


def http_json(url: str) -> dict:
    return json.loads(http_get(url).decode("utf-8"))


def merge(store: dict[str, dict], rec: dict) -> None:
    title = (rec.get("title") or "").strip()
    if len(title) < 8:
        return
    key = rec.get("doi") or rec.get("openalex_id") or rec.get("s2_id") or rec.get("arxiv_id")
    if not key:
        key = "t:" + re.sub(r"\W+", " ", title.lower()).strip()[:140]
    if key in store:
        prev = store[key]
        for d in rec.get("domains") or []:
            if d not in prev.setdefault("domains", []):
                prev["domains"].append(d)
        prev["cited_by_count"] = max(int(prev.get("cited_by_count") or 0), int(rec.get("cited_by_count") or 0))
        for f in (
            "abstract_snip",
            "venue",
            "doi",
            "openalex_id",
            "s2_id",
            "arxiv_id",
            "oa_url",
            "landing",
            "year",
        ):
            if not prev.get(f) and rec.get(f):
                prev[f] = rec[f]
        apis = set(x for x in (prev.get("source_api") or "").split("+") if x)
        if rec.get("source_api"):
            apis.add(rec["source_api"])
        prev["source_api"] = "+".join(sorted(apis))
        if (not prev.get("authors")) and rec.get("authors"):
            prev["authors"] = rec["authors"]
        return
    store[key] = rec


def fetch_crossref(query: str, rows: int, offset: int, sort: str | None = None, filt: str | None = None) -> list[dict]:
    params: dict[str, str] = {
        "query": query,
        "rows": str(rows),
        "offset": str(offset),
        "mailto": MAILTO,
        "select": "DOI,title,author,published-print,published-online,container-title,is-referenced-by-count,type,URL,abstract,score,publisher",
    }
    if sort:
        params["sort"] = sort
        params["order"] = "desc"
    if filt:
        params["filter"] = filt
    url = f"{CROSSREF}?{urllib.parse.urlencode(params)}"
    data = http_json(url)
    return ((data.get("message") or {}).get("items")) or []


def extract_cr(it: dict, domain: str, query: str) -> dict:
    title_l = it.get("title") or []
    title = title_l[0] if title_l else ""
    authors = []
    for a in (it.get("author") or [])[:12]:
        name = " ".join(x for x in [a.get("given"), a.get("family")] if x)
        if name:
            authors.append(name)
    year = None
    for k in ("published-print", "published-online"):
        parts = ((it.get(k) or {}).get("date-parts") or [[None]])[0]
        if parts and parts[0]:
            year = int(parts[0])
            break
    venue_l = it.get("container-title") or []
    return {
        "source_api": "crossref",
        "doi": it.get("DOI") or "",
        "title": title.strip(),
        "year": year,
        "cited_by_count": int(it.get("is-referenced-by-count") or 0),
        "type": it.get("type") or "journal-article",
        "authors": authors,
        "venue": venue_l[0] if venue_l else "",
        "is_oa": False,
        "oa_url": it.get("URL"),
        "landing": it.get("URL"),
        "abstract_snip": strip_tags(it.get("abstract") or "")[:500],
        "query": query,
        "domains": [domain],
        "s2_id": None,
        "openalex_id": None,
        "arxiv_id": None,
        "concepts": [],
        "topics": [],
    }


def fetch_arxiv_raw(search_query: str, start: int = 0, max_results: int = 100, sort_by: str = "relevance") -> list[dict]:
    params = {
        "search_query": search_query,
        "start": str(start),
        "max_results": str(max_results),
        "sortBy": sort_by,
        "sortOrder": "descending",
    }
    url = f"{ARXIV}?{urllib.parse.urlencode(params)}"
    raw = http_get(url)
    root = ET.fromstring(raw)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in root.findall("a:entry", ns):
        title = re.sub(r"\s+", " ", (e.findtext("a:title", default="", namespaces=ns) or "").strip())
        summary = re.sub(r"\s+", " ", (e.findtext("a:summary", default="", namespaces=ns) or "").strip())
        published = e.findtext("a:published", default="", namespaces=ns) or ""
        year = int(published[:4]) if published[:4].isdigit() else None
        authors = [
            (a.findtext("a:name", default="", namespaces=ns) or "").strip()
            for a in e.findall("a:author", ns)
        ]
        authors = [a for a in authors if a][:12]
        id_url = e.findtext("a:id", default="", namespaces=ns) or ""
        arxiv_id = id_url.rstrip("/").split("/abs/")[-1] if "/abs/" in id_url else id_url
        doi = ""
        doi_el = e.find("{http://arxiv.org/schemas/atom}doi")
        if doi_el is not None and doi_el.text:
            doi = doi_el.text.strip()
        out.append(
            {
                "source_api": "arxiv",
                "doi": doi,
                "title": title,
                "year": year,
                "cited_by_count": 0,
                "type": "preprint",
                "authors": authors,
                "venue": "arXiv",
                "is_oa": True,
                "oa_url": id_url,
                "landing": id_url,
                "abstract_snip": summary[:500],
                "query": search_query,
                "domains": [],
                "s2_id": None,
                "openalex_id": None,
                "arxiv_id": arxiv_id,
                "concepts": [],
                "topics": [],
            }
        )
    return out


def try_s2(query: str, limit: int = 100, offset: int = 0) -> list[dict]:
    params = {
        "query": query,
        "limit": str(min(limit, 100)),
        "offset": str(offset),
        "fields": "title,year,citationCount,authors,venue,externalIds,url,abstract,openAccessPdf,fieldsOfStudy,paperId",
    }
    url = f"{S2}?{urllib.parse.urlencode(params)}"
    data = http_json(url)
    return data.get("data") or []


def extract_s2(p: dict, domain: str, query: str) -> dict:
    authors = [a.get("name") for a in (p.get("authors") or [])[:12] if a.get("name")]
    ext = p.get("externalIds") or {}
    return {
        "source_api": "semanticscholar",
        "doi": ext.get("DOI") or "",
        "title": (p.get("title") or "").strip(),
        "year": p.get("year"),
        "cited_by_count": int(p.get("citationCount") or 0),
        "type": "article",
        "authors": authors,
        "venue": p.get("venue") or "",
        "is_oa": bool((p.get("openAccessPdf") or {}).get("url")),
        "oa_url": (p.get("openAccessPdf") or {}).get("url") or p.get("url"),
        "landing": p.get("url"),
        "abstract_snip": (p.get("abstract") or "")[:500],
        "query": query,
        "domains": [domain],
        "s2_id": p.get("paperId"),
        "openalex_id": None,
        "arxiv_id": ext.get("ArXiv"),
        "concepts": [],
        "topics": p.get("fieldsOfStudy") or [],
    }


def try_openalex(query: str) -> list[dict]:
    params = {
        "search": query,
        "filter": "type:article|review",
        "sort": "cited_by_count:desc",
        "per_page": "50",
        "select": "id,doi,display_name,publication_year,cited_by_count,type,authorships,primary_location,open_access,concepts,topics,abstract_inverted_index,is_retracted,language",
        "mailto": MAILTO,
    }
    url = f"{OPENALEX}?{urllib.parse.urlencode(params)}"
    data = http_json(url)
    return data.get("results") or []


def extract_oa(w: dict, domain: str, query: str) -> dict:
    authors = []
    for a in (w.get("authorships") or [])[:12]:
        name = (a.get("author") or {}).get("display_name")
        if name:
            authors.append(name)
    loc = w.get("primary_location") or {}
    src = ((loc.get("source") or {}).get("display_name")) or ""
    oa = w.get("open_access") or {}
    inv = w.get("abstract_inverted_index") or {}
    pos = []
    for word, idxs in inv.items():
        for i in idxs:
            pos.append((i, word))
    pos.sort()
    abstract = " ".join(x for _, x in pos)[:500]
    return {
        "source_api": "openalex",
        "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
        "title": strip_tags(w.get("display_name") or ""),
        "year": w.get("publication_year"),
        "cited_by_count": int(w.get("cited_by_count") or 0),
        "type": w.get("type"),
        "authors": authors,
        "venue": src,
        "is_oa": bool(oa.get("is_oa")),
        "oa_url": oa.get("oa_url") or loc.get("pdf_url") or loc.get("landing_page_url"),
        "landing": loc.get("landing_page_url"),
        "abstract_snip": abstract,
        "query": query,
        "domains": [domain],
        "s2_id": None,
        "openalex_id": w.get("id"),
        "arxiv_id": None,
        "concepts": [c.get("display_name") for c in (w.get("concepts") or [])[:8] if c.get("display_name")],
        "topics": [t.get("display_name") for t in (w.get("topics") or [])[:5] if t.get("display_name")],
    }


def score(rec: dict) -> float:
    topics = rec.get("topics") or []
    topics_s = " ".join(map(str, topics)) if isinstance(topics, list) else str(topics)
    blob = " ".join(
        [
            rec.get("title") or "",
            rec.get("abstract_snip") or "",
            " ".join(rec.get("concepts") or []),
            topics_s,
            rec.get("venue") or "",
        ]
    )
    if NOISE.search(rec.get("title") or ""):
        return -1.0
    hits = len(OR_HINTS.findall(blob))
    low = blob.lower()
    if hits == 0 and not any(
        k in low
        for k in (
            "optim",
            "program",
            "routing",
            "schedul",
            "integer",
            "convex",
            "heuristic",
            "packing",
            "knapsack",
            "flow",
            "queue",
            "benders",
            "column generation",
            "matroid",
            "submodular",
        )
    ):
        return -1.0
    cites = int(rec.get("cited_by_count") or 0)
    year = int(rec.get("year") or 1990)
    cite_part = math.log1p(cites)
    if cites == 0 and rec.get("source_api") == "arxiv":
        cite_part = 1.0 + 0.12 * hits
    age = max(0, 2026 - year)
    recency = 1.0 / (1.0 + 0.075 * age)
    classic = 0.45 if cites >= 2000 else 0.28 if cites >= 500 else 0.14 if cites >= 150 else 0.0
    multi = 0.1 * max(0, len(rec.get("domains") or []) - 1)
    survey = 0.28 if re.search(r"\b(survey|review|tutorial|handbook)\b", rec.get("title") or "", re.I) else 0.0
    venue = (rec.get("venue") or "").lower()
    vb = 0.4 if any(v in venue for v in VENUE_BONUS_KEYS) else 0.0
    return cite_part * (0.55 + 0.45 * recency) + classic + multi + survey + vb + 0.07 * hits


def select_top(pool: list[dict], n: int = 200, soft_cap: int = 16):
    for r in pool:
        r["score"] = score(r)
    rel = [p for p in pool if p["score"] >= 0]
    rel.sort(key=lambda x: (-x["score"], -(x.get("cited_by_count") or 0)))
    counts: dict[str, int] = defaultdict(int)
    selected: list[dict] = []
    deferred: list[dict] = []
    seen: set[str] = set()

    def tk(t: str) -> str:
        return re.sub(r"\W+", " ", (t or "").lower()).strip()

    for p in rel:
        t = tk(p.get("title") or "")
        if not t or t in seen:
            continue
        ds = p.get("domains") or ["misc"]
        if all(counts[d] >= soft_cap for d in ds):
            deferred.append(p)
            continue
        selected.append(p)
        seen.add(t)
        for d in ds:
            counts[d] += 1
        if len(selected) >= n:
            break
    if len(selected) < n:
        for p in deferred:
            t = tk(p.get("title") or "")
            if t in seen:
                continue
            selected.append(p)
            seen.add(t)
            if len(selected) >= n:
                break
    selected.sort(key=lambda x: x["score"], reverse=True)
    for i, p in enumerate(selected, 1):
        p["rank"] = i
    return selected, dict(counts), rel


def write_all(rel: list[dict], selected: list[dict], counts: dict, errors: list, meta: dict) -> None:
    RAW.write_text(
        json.dumps(
            {
                "source": "Crossref + arXiv (+ S2/OpenAlex if available)",
                "note": "Metadata only, no PDF download, not fabricated",
                "pool_size": len(rel),
                "meta": meta,
                "errors": errors[-200:],
                "papers": rel[:4000],
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    TOP_JSON.write_text(
        json.dumps(
            {
                "n": len(selected),
                "domain_counts": dict(sorted(counts.items())),
                "selection": "score=log(cites)*recency + classic/survey/venue + OR keywords; domain soft-cap",
                "papers": selected,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "rank",
                "title",
                "year",
                "citations",
                "authors",
                "venue",
                "doi",
                "domains",
                "source_api",
                "link",
                "score",
            ]
        )
        for p in selected:
            link = p.get("oa_url") or p.get("landing") or (f"https://doi.org/{p['doi']}" if p.get("doi") else "")
            w.writerow(
                [
                    p.get("rank"),
                    p.get("title"),
                    p.get("year"),
                    p.get("cited_by_count"),
                    "; ".join(p.get("authors") or [])[:220],
                    p.get("venue"),
                    p.get("doi"),
                    "|".join(p.get("domains") or []),
                    p.get("source_api"),
                    link,
                    f"{float(p.get('score') or 0):.3f}",
                ]
            )

    lines = [
        "# 运筹学论文择优清单（Top 200）",
        "",
        "> **来源**: Crossref + arXiv（+ 可用时的 Semantic Scholar / OpenAlex）——**真实 API 元数据，未虚构**  ",
        "> **未下载 PDF**；仅书目清单。  ",
        "> **流程**: 20 运筹子域 × 多查询 ×（相关排序 + 高被引排序 + 近年过滤）→ 去重 → OR 相关度/期刊加权 → 域多样性软上限 → **200**  ",
        f"> **相关候选池**: **{len(rel)}** 篇  ",
        f"> **脚本**: `scripts/build_or_paper_list.py`  ",
        f"> **JSON/CSV**: `knowledge/or_papers_top200.json` · `knowledge/or_papers_top200.csv`",
        "",
        "## 子域覆盖（选中计数）",
        "",
    ]
    for d, c in sorted(counts.items(), key=lambda x: -x[1]):
        lines.append(f"- `{d}`: {c}")
    lines += ["", "---", "", "## Top 200 清单", ""]
    for p in selected:
        authors = ", ".join(p.get("authors") or [])[:160]
        doi = p.get("doi") or ""
        link = p.get("oa_url") or p.get("landing") or ""
        lines.append(f"### {p['rank']}. {p['title']}")
        lines.append("")
        lines.append(
            f"- **Year**: {p.get('year')} · **Citations**: {p.get('cited_by_count')} · "
            f"**Type**: {p.get('type')} · **API**: {p.get('source_api')}"
        )
        if authors:
            lines.append(f"- **Authors**: {authors}")
        if p.get("venue"):
            lines.append(f"- **Venue**: {p['venue']}")
        lines.append(f"- **Domains**: {', '.join(p.get('domains') or [])}")
        if doi:
            lines.append(f"- **DOI**: https://doi.org/{doi}")
        if p.get("s2_id"):
            lines.append(f"- **Semantic Scholar**: https://www.semanticscholar.org/paper/{p['s2_id']}")
        if p.get("openalex_id"):
            lines.append(f"- **OpenAlex**: {p['openalex_id']}")
        if p.get("arxiv_id"):
            lines.append(f"- **arXiv**: https://arxiv.org/abs/{p['arxiv_id']}")
        if link:
            lines.append(f"- **Link**: {link}")
        if p.get("abstract_snip"):
            snip = str(p["abstract_snip"]).replace("\n", " ")
            lines.append(f"- **Abstract**: {snip[:300]}…")
        lines.append(f"- **Score**: {float(p.get('score') or 0):.3f}")
        lines.append("")
    lines += [
        "## 局限（诚实说明）",
        "",
        "1. 「约 2000 篇」指多源检索命中去重后的**候选池规模**，不是人工精读 2000 篇全文。",
        "2. 引用数来自 Crossref `is-referenced-by-count` 等，常低于 Google Scholar。",
        "3. 相关度为启发式；入库 RAG 前建议按域再人工抽检。",
        "4. 清单偏**通用方法/经典+前沿**，不是某道竞赛题的最优解库。",
        "",
    ]
    TOP_MD.write_text("\n".join(lines), encoding="utf-8")
    LOG_NOTE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    state = load_ckpt()
    papers: dict[str, dict] = state.get("papers") or {}
    done = set(state.get("done_keys") or [])
    errors: list[str] = list(state.get("errors") or [])
    stats: dict[str, int] = defaultdict(int)

    def persist() -> None:
        save_ckpt({"done_keys": sorted(done), "papers": papers, "errors": errors[-500:]})

    def mark(key: str) -> None:
        done.add(key)
        persist()

    print(f"Resume done={len(done)} pool={len(papers)}")

    # -------- Phase A: Crossref bulk --------
    # 3 strategies × offsets → aim large pool
    strategies = [
        ("rel0", None, None, 0),
        ("rel50", None, None, 50),
        ("rel100", None, None, 100),
        ("cite0", "is-referenced-by-count", "type:journal-article,from-pub-date:1970-01-01", 0),
        ("cite50", "is-referenced-by-count", "type:journal-article,from-pub-date:1970-01-01", 50),
        ("recent_cite", "is-referenced-by-count", "type:journal-article,from-pub-date:2016-01-01", 0),
    ]

    for domain, queries in DOMAINS.items():
        for q in queries:
            for name, sort, filt, offset in strategies:
                key = f"cr||{domain}||{q}||{name}||{offset}"
                if key in done:
                    continue
                print(f"CR [{domain}] {name}@{offset}: {q}")
                try:
                    rows = fetch_crossref(q, rows=50, offset=offset, sort=sort, filt=filt)
                    for it in rows:
                        # skip non-content types
                        t = (it.get("type") or "").lower()
                        if t in ("component", "peer-review", "journal-issue"):
                            continue
                        merge(papers, extract_cr(it, domain, q))
                    stats["cr_rows"] += len(rows)
                    print(f"  +{len(rows)} pool={len(papers)}")
                    mark(key)
                except Exception as e:  # noqa: BLE001
                    msg = f"{key}: {e}"
                    print(" ERR", msg)
                    errors.append(msg)
                    # permanent skip on 400
                    if "HTTP 400" in str(e):
                        mark(key)
                time.sleep(0.25)
        print(f"== CR domain {domain} pool={len(papers)}")

    # -------- Phase B: arXiv math.OC / cs.DS frontier --------
    arxiv_jobs = [
        ("nonlinear_convex", 'cat:math.OC AND ti:"convex"', "relevance"),
        ("stochastic_or", 'cat:math.OC AND (ti:"robust optimization" OR ti:"stochastic programming")', "submittedDate"),
        ("integer_programming", 'all:"mixed integer" AND (cat:math.OC OR cat:cs.DS)', "relevance"),
        ("tsp_routing", 'ti:"vehicle routing" OR ti:"traveling salesman"', "submittedDate"),
        ("ml_or_hybrid", 'ti:"combinatorial optimization" AND (ti:learning OR ti:neural OR ti:reinforcement)', "submittedDate"),
        ("column_generation_decomp", 'all:"column generation" OR all:"Benders decomposition"', "relevance"),
        ("network_flows", 'ti:"maximum flow" OR ti:"minimum cost flow" OR ti:"shortest path"', "relevance"),
        ("cutting_packing", 'ti:"bin packing" OR ti:"cutting stock" OR ti:knapsack', "relevance"),
        ("scheduling", 'ti:"job shop" OR ti:"project scheduling" OR all:"resource-constrained"', "relevance"),
        ("constraint_programming", 'all:"constraint programming" OR all:CP-SAT', "submittedDate"),
        ("combinatorial_optimization", "cat:math.OC AND ti:combinatorial", "relevance"),
        ("dynamic_programming", 'all:"approximate dynamic programming" OR all:"Markov decision"', "relevance"),
        ("metaheuristics", 'all:"large neighborhood search" OR all:"tabu search" optimization', "relevance"),
        ("graph_or", 'ti:"graph coloring" OR ti:"Steiner tree" OR ti:"maximum matching"', "relevance"),
        ("inventory_supply_chain", 'all:"facility location" OR all:newsvendor OR all:"supply chain" optimization', "relevance"),
    ]
    for domain, aq, sort_by in arxiv_jobs:
        for start in (0, 100):
            key = f"arxiv||{domain}||{aq}||{start}"
            if key in done:
                continue
            print(f"arXiv [{domain}] start={start}")
            try:
                rows = fetch_arxiv_raw(aq, start=start, max_results=100, sort_by=sort_by)
                for r in rows:
                    r["domains"] = [domain]
                    merge(papers, r)
                stats["arxiv_rows"] += len(rows)
                print(f"  +{len(rows)} pool={len(papers)}")
                mark(key)
            except Exception as e:  # noqa: BLE001
                msg = f"{key}: {e}"
                print(" ERR", msg)
                errors.append(msg)
            time.sleep(3.1)

    # -------- Phase C: light S2 (skip whole phase if first call 429x) --------
    s2_ok = True
    for domain, queries in DOMAINS.items():
        if not s2_ok:
            break
        q = queries[0]
        key = f"s2||{domain}||{q}||0"
        if key in done:
            continue
        print(f"S2 [{domain}]: {q}")
        try:
            rows = try_s2(q, limit=100, offset=0)
            for p in rows:
                merge(papers, extract_s2(p, domain, q))
            stats["s2_rows"] += len(rows)
            print(f"  +{len(rows)} pool={len(papers)}")
            mark(key)
            time.sleep(1.2)
        except Exception as e:  # noqa: BLE001
            msg = f"{key}: {e}"
            print(" ERR", msg)
            errors.append(msg)
            if "429" in str(e) or "HTTP 429" in str(e):
                print("S2 rate-limited — skip remaining S2")
                s2_ok = False
            mark(key)

    # -------- Phase D: OpenAlex fill if pool still small --------
    if len(papers) < 1600:
        print("OpenAlex fill…")
        for domain, queries in DOMAINS.items():
            q = queries[0]
            key = f"oa||{domain}||{q}"
            if key in done:
                continue
            print(f"OA [{domain}]: {q}")
            try:
                rows = try_openalex(q)
                for w in rows:
                    if w.get("is_retracted"):
                        continue
                    merge(papers, extract_oa(w, domain, q))
                stats["oa_rows"] += len(rows)
                print(f"  +{len(rows)} pool={len(papers)}")
            except Exception as e:  # noqa: BLE001
                msg = f"{key}: {e}"
                print(" ERR", msg)
                errors.append(msg)
            mark(key)
            time.sleep(3.0)

    pool = list(papers.values())
    selected, counts, rel = select_top(pool, n=200, soft_cap=16)
    meta = {
        "unique_raw": len(pool),
        "relevant_pool": len(rel),
        "selected": len(selected),
        "stats": dict(stats),
        "done_jobs": len(done),
        "errors_n": len(errors),
    }
    write_all(rel, selected, counts, errors, meta)
    persist()
    print("DONE meta=", meta)
    print("DOMAIN", counts)
    print("TOP10:")
    for p in selected[:10]:
        print(f" {p['rank']:3d} cites={p.get('cited_by_count')} {p.get('year')} | {p.get('title')[:100]}")


if __name__ == "__main__":
    main()
