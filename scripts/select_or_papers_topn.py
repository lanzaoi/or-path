#!/usr/bin/env python3
"""Select high-quality OR papers from checkpoint — stricter filters for RAG.

Drops bio-inspired metaheuristic spam and off-topic high-cite hits.
"""
from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "knowledge"
CKPT = OUT / "or_paper_pool_checkpoint.json"
RAW = OUT / "or_paper_pool_raw.json"
TOP_JSON = OUT / "or_papers_top500.json"
TOP_MD = OUT / "or_papers_top500.md"
CSV_PATH = OUT / "or_papers_top500.csv"
N = 500
SOFT_CAP = 38

# Hard reject title patterns (common Crossref pollution / bio-inspired spam)
HARD_REJECT = re.compile(
    r"(?i)\b("
    r"numpy|pandas|scipy|pytorch|tensorflow|keras|"
    r"autodock|alphafold|bert\b|gpt-?[0-9]|imagenet|yolo\b|"
    r"whale optimization|harris hawks|grey wolf|gray wolf|"
    r"slime mould|slime mold|sparrow search|moth-?flame|moth flame|"
    r"butterfly optimization|dragonfly algorithm|ant lion|"
    r"salp swarm|crow search|cuckoo search|bat algorithm|"
    r"firefly algorithm|krill herd|flower pollination|"
    r"grasshopper optimization|emperor penguin|arctic tern|"
    r"chimp optimization|aquila optimizer|dandelion optimizer|"
    r"arithmetic optimization algorithm|sine cosine algorithm|"
    r"multi-?verse optimizer|teaching-?learning-?based|"
    r"covid-?19|sars-?cov|"
    r"deep learning for image|convolutional neural network for image"
    r")\b"
)

# Prefer true OR signal
OR_CORE = re.compile(
    r"(?i)\b("
    r"operations research|operational research|mathematical programming|"
    r"integer programming|linear programming|mixed[- ]integer|MILP|MIP\b|"
    r"branch[- ]and[- ]cut|branch[- ]and[- ]bound|branch[- ]and[- ]price|"
    r"column generation|benders decomposition|dantzig-?wolfe|lagrangian relaxation|"
    r"cutting plane|polyhedral|valid inequalit|"
    r"vehicle routing|traveling salesman|travelling salesman|TSP\b|VRP\b|"
    r"shortest path|maximum flow|max-?flow|min(?:imum)?[- ]cost flow|network simplex|"
    r"job[- ]shop|flow[- ]shop|machine scheduling|project scheduling|RCPSP|"
    r"stochastic programming|robust optimization|distributionally robust|"
    r"chance[- ]constrained|two[- ]stage stochastic|recourse|"
    r"convex optimization|semidefinite programming|SDP\b|second[- ]order cone|"
    r"constraint programming|constraint satisfaction|CP-?SAT|"
    r"bin packing|cutting stock|knapsack|"
    r"facility location|p-?median|set covering|set partitioning|"
    r"tabu search|large neighborhood|adaptive large neighborhood|"
    r"dynamic programming|approximate dynamic programming|markov decision|"
    r"submodular|matroid|matching algorithm|graph coloring|steiner tree|"
    r"newsvendor|inventory theory|EOQ\b|"
    r"queueing|queuing theory|"
    r"multiobjective optimization|multi-objective optimization|pareto|"
    r"goal programming|interior[- ]point|simplex method|"
    r"combinatorial optimization|nonlinear programming|"
    r"learning to branch|learning to cut|neural combinatorial|"
    r"OR tools|operations research survey|integer programming survey"
    r")\b"
)

# Mild OR-adjacent — keep only if venue strong or high OR_CORE already
OR_SOFT = re.compile(
    r"(?i)\b("
    r"optimiz|scheduling|routing|heuristic|metaheuristic|decomposition|"
    r"supply chain|inventory|network flow|duality|polytope|cutting|"
    r"packing|assignment problem|transportation problem"
    r")\b"
)

VENUE_STRONG = (
    "operations research",
    "operational research",
    "mathematics of operations research",
    "mathematical programming",
    "management science",
    "informs journal on computing",
    "informs journal on optimization",
    "european journal of operational research",
    "computers & operations research",
    "computers and operations research",
    "transportation science",
    "transportation research part b",
    "transportation research part c",
    "networks",
    "siam journal on optimization",
    "siam journal on control",
    "siam journal on computing",
    "annals of operations research",
    "or spectrum",
    "journal of scheduling",
    "constraints",
    "journal of global optimization",
    "optimization methods and software",
    "mathematical programming computation",
    "operations research letters",
    "naval research logistics",
    "iie transactions",
    "iise transactions",
    "production and operations management",
    "manufacturing & service operations",
    "manufacturing and service operations",
    "journal of the operational research society",
    "4or",
    "optimization and engineering",
    "computational optimization and applications",
    "discrete optimization",
    "euro journal on computational optimization",
    "journal of combinatorial optimization",
    "algorithmica",
    "mathematical methods of operations research",
)

VENUE_OK = (
    "acm transactions on",
    "ieee transactions on automatic control",
    "ieee transactions on power",
    "automatica",
    "european journal of control",
    "journal of optimization theory",
    "optimization letters",
    "top ",
    "4or-a quarterly",
    "annals of mathematics",
    "acta numerica",
    "foundations and trends",
    "handbooks in operations research",
    "springer",
    "elsevier",
)


def venue_tier(venue: str) -> int:
    v = (venue or "").lower()
    if any(s in v for s in VENUE_STRONG):
        return 2
    if any(s in v for s in VENUE_OK):
        return 1
    if v in ("arxiv",):
        return 1
    return 0


def score(rec: dict) -> float:
    title = rec.get("title") or ""
    abstract = rec.get("abstract_snip") or ""
    venue = rec.get("venue") or ""
    blob = f"{title} {abstract} {venue} {' '.join(rec.get('concepts') or [])}"

    if HARD_REJECT.search(title):
        return -1.0

    core_hits = len(OR_CORE.findall(blob))
    soft_hits = len(OR_SOFT.findall(blob))
    vt = venue_tier(venue)

    # Must have real OR signal
    if core_hits == 0:
        if vt >= 2 and soft_hits >= 1:
            pass  # allow OR-journal soft papers
        elif vt >= 1 and soft_hits >= 2 and int(rec.get("cited_by_count") or 0) >= 200:
            pass
        else:
            return -1.0

    cites = int(rec.get("cited_by_count") or 0)
    year = int(rec.get("year") or 1990)
    if year < 1950 or year > 2026:
        return -1.0

    # arxiv with 0 cites: only if strong core + recent
    if cites == 0 and (rec.get("source_api") == "arxiv" or venue.lower() == "arxiv"):
        if core_hits < 2 or year < 2018:
            return -1.0
        cite_part = 1.5 + 0.15 * core_hits
    else:
        cite_part = math.log1p(cites)

    age = max(0, 2026 - year)
    recency = 1.0 / (1.0 + 0.07 * age)
    classic = 0.5 if cites >= 3000 else 0.3 if cites >= 800 else 0.15 if cites >= 250 else 0.0
    multi = 0.08 * max(0, len(rec.get("domains") or []) - 1)
    survey = 0.35 if re.search(r"(?i)\b(survey|review|tutorial|handbook|monograph)\b", title) else 0.0
    venue_b = {2: 0.85, 1: 0.25, 0: 0.0}[vt]
    core_b = min(0.6, 0.12 * core_hits)

    # Penalize vague "a novel optimization algorithm" without OR core nouns
    if re.search(r"(?i)novel .* optim", title) and core_hits < 2:
        cite_part *= 0.5

    return cite_part * (0.5 + 0.5 * recency) + classic + multi + survey + venue_b + core_b


def main() -> None:
    state = json.loads(CKPT.read_text(encoding="utf-8"))
    pool = list((state.get("papers") or {}).values())
    print(f"pool={len(pool)}")

    for r in pool:
        r["score"] = score(r)
    rel = [p for p in pool if p["score"] >= 0]
    rel.sort(key=lambda x: (-x["score"], -(x.get("cited_by_count") or 0)))
    print(f"relevant_strict={len(rel)}")

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
        if all(counts[d] >= SOFT_CAP for d in ds):
            deferred.append(p)
            continue
        selected.append(p)
        seen.add(t)
        for d in ds:
            counts[d] += 1
        if len(selected) >= N:
            break
    if len(selected) < N:
        for p in deferred:
            t = tk(p.get("title") or "")
            if t in seen:
                continue
            selected.append(p)
            seen.add(t)
            if len(selected) >= N:
                break

    selected.sort(key=lambda x: x["score"], reverse=True)
    for i, p in enumerate(selected, 1):
        p["rank"] = i

    # Backfill missing years from DOI patterns / common book series (Crossref gaps on chapters)
    DOI_YEAR_HINTS = {
        "10.1007/978-0-387-77778-8": 2008,
        "10.1007/0-387-25486-2": 2005,
        "10.1007/1-84628-137-7": 2005,
        "10.1007/bfb0006528": 1978,
    }
    for p in selected:
        if p.get("year"):
            continue
        doi = (p.get("doi") or "").lower()
        for prefix, y in DOI_YEAR_HINTS.items():
            if doi.startswith(prefix):
                p["year"] = y
                break
        if not p.get("year") and re.search(r"real\.(\d{4})\.", doi):
            p["year"] = int(re.search(r"real\.(\d{4})\.", doi).group(1))

    RAW.write_text(
        json.dumps(
            {
                "source": "Crossref + arXiv checkpoint",
                "note": "Strict OR filter. Metadata only. Not fabricated.",
                "pool_unique": len(pool),
                "relevant_strict": len(rel),
                "selected": len(selected),
                "domain_counts": dict(sorted(counts.items())),
                "papers_relevant_head": rel[:3000],
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
                "source": "Crossref + arXiv real metadata",
                "selection": (
                    f"strict OR core/venue filter from pool {len(pool)} / strict-rel {len(rel)}; "
                    f"score=cites*recency+venue+core; domain soft-cap={SOFT_CAP}; top {N}"
                ),
                "domain_counts": dict(sorted(counts.items())),
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
            link = (
                p.get("oa_url")
                or p.get("landing")
                or (f"https://doi.org/{p['doi']}" if p.get("doi") else "")
            )
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
        "# 运筹学论文择优清单（Top 500 · 严格 OR 过滤）",
        "",
        "> **来源**: Crossref + arXiv 真实 API 元数据（**未虚构 · 未下载 PDF**）  ",
        f"> **候选池**: 去重 **{len(pool)}** · 严格 OR 相关 **{len(rel)}** · **择优 {len(selected)}**  ",
        "> **过滤**: 剔除生物启发式刷榜算法 / NumPy 等跑题高引；强化 OR 核心词 + INFORMS/MP/EJOR 等期刊加权  ",
        f"> **多样性**: 子域软上限 {SOFT_CAP}/域  ",
        "> **文件**: `knowledge/or_papers_top500.md` · `.json` · `.csv`  ",
        "> **脚本**: `scripts/select_or_papers_topn.py`",
        "",
        "## 子域覆盖（选中计数）",
        "",
    ]
    for d, c in sorted(counts.items(), key=lambda x: -x[1]):
        lines.append(f"- `{d}`: {c}")
    lines += ["", "---", "", "## 清单", ""]

    for p in selected:
        authors = ", ".join(p.get("authors") or [])[:160]
        doi = p.get("doi") or ""
        link = p.get("oa_url") or p.get("landing") or ""
        lines.append(f"### {p['rank']}. {p['title']}")
        lines.append("")
        lines.append(
            f"- **Year**: {p.get('year')} · **Citations**: {p.get('cited_by_count')} · "
            f"**API**: {p.get('source_api')}"
        )
        if authors:
            lines.append(f"- **Authors**: {authors}")
        if p.get("venue"):
            lines.append(f"- **Venue**: {p['venue']}")
        lines.append(f"- **Domains**: {', '.join(p.get('domains') or [])}")
        if doi:
            lines.append(f"- **DOI**: https://doi.org/{doi}")
        if p.get("arxiv_id"):
            lines.append(f"- **arXiv**: https://arxiv.org/abs/{p['arxiv_id']}")
        if link and not doi:
            lines.append(f"- **Link**: {link}")
        elif link and doi and "doi.org" not in link:
            lines.append(f"- **Link**: {link}")
        if p.get("abstract_snip"):
            snip = str(p["abstract_snip"]).replace("\n", " ")
            lines.append(f"- **Abstract**: {snip[:260]}…")
        lines.append(f"- **Score**: {float(p.get('score') or 0):.3f}")
        lines.append("")

    lines += [
        "## 局限",
        "",
        "1. 上万篇为 API 检索命中去重池，非人工精读全文。",
        "2. Crossref 引用数通常低于 Google Scholar。",
        "3. 严格规则可能漏掉交叉学科好文，也可能放过边缘文——入库前建议抽检。",
        "4. 通用方法向；非竞赛最优解库。",
        "",
    ]
    TOP_MD.write_text("\n".join(lines), encoding="utf-8")

    # overwrite selector script path note already done
    print("selected", len(selected), "strict_rel", len(rel))
    print("domains", dict(sorted(counts.items(), key=lambda x: -x[1])))
    print("TOP20:")
    for p in selected[:20]:
        print(
            f"{p['rank']:3d} y={p.get('year')} c={int(p.get('cited_by_count') or 0):6d} "
            f"vt={(p.get('venue') or '')[:40]:40s} | {(p.get('title') or '')[:75]}"
        )
    # sanity: how many strong venues
    strong = sum(1 for p in selected if venue_tier(p.get("venue") or "") >= 2)
    with_doi = sum(1 for p in selected if p.get("doi"))
    print(f"strong_venue={strong} with_doi={with_doi}")


if __name__ == "__main__":
    main()
