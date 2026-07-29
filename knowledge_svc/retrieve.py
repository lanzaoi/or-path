"""Retrieve CLI + library: seed | hybrid modes → notes/*-retrieval.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Literal

from knowledge_svc.bm25_index import BM25Index
from knowledge_svc.chunk_schema import (
    RetrievalArtifact,
    RetrievalHit,
    knowledge_dir,
    repo_root,
    write_json,
)
from knowledge_svc.fts_index import FTSIndex
from knowledge_svc.lightrag_adapter import LightRAGAdapter
from knowledge_svc.rrf_fuse import (
    DEFAULT_W_LEXICAL,
    DEFAULT_W_SEMANTIC,
    fuse_semantic_lexical,
    merge_lexical,
)
from knowledge_svc.seed_graph_query import query_all_classes, query_by_class, stats as seed_stats

KnowledgeMode = Literal["off", "seed", "hybrid"]


def retrieve(
    query: str,
    *,
    mode: KnowledgeMode = "hybrid",
    topk: int = 5,
    root: Path | None = None,
    problem_class: str | None = None,
    w_semantic: float = DEFAULT_W_SEMANTIC,
    w_lexical: float = DEFAULT_W_LEXICAL,
    force_stub: bool = True,
    embed_fn=None,
) -> RetrievalArtifact:
    """Run retrieval; empty hits stay empty (no fabricated cites)."""
    root = root or repo_root()
    q = (query or "").strip()
    seed_facts: list[dict[str, Any]] = []
    hits: list[RetrievalHit] = []

    if mode == "off":
        return RetrievalArtifact(query=q, knowledge_mode="off", hits=[], seed_facts=[])

    # Always attach seed when mode is seed or hybrid
    if problem_class:
        seed_facts = query_by_class(problem_class)
    else:
        # lightweight: all class summaries for seed mode; hybrid still includes facts
        try:
            seed_facts = query_all_classes()
        except FileNotFoundError:
            seed_facts = []

    if mode == "seed":
        # Represent seed nodes as soft hits for researcher mapping
        for fact in seed_facts:
            for node in fact.get("nodes") or []:
                if node.get("type") not in {"ProblemClass", "Solver", "Constraint", "Case"}:
                    continue
                nid = str(node.get("id") or "")
                label = str(node.get("label") or nid)
                summary = str((node.get("props") or {}).get("summary") or label)
                # simple relevance: token overlap with query
                score = _seed_score(q, label + " " + summary)
                if score <= 0 and q:
                    continue
                hits.append(
                    RetrievalHit(
                        chunk_id=nid,
                        score=score if q else 1.0,
                        backend="seed",
                        snippet=summary[:240],
                        source_path="knowledge/seed_graph/or_domain_seed.json",
                    )
                )
        hits.sort(key=lambda h: h.score, reverse=True)
        hits = hits[: max(1, topk)] if hits else []
        return RetrievalArtifact(
            query=q, knowledge_mode="seed", hits=hits, seed_facts=seed_facts
        )

    # hybrid
    bm25 = BM25Index(root=root)
    bm25.load()
    fts = FTSIndex(root=root)
    rag = LightRAGAdapter(root=root, force_stub=force_stub, embed_fn=embed_fn)

    bm25_hits = bm25.search(q, topk=max(topk * 3, 10)) if q else []
    fts_hits = fts.search(q, topk=max(topk * 3, 10)) if q else []
    lex = merge_lexical(bm25_hits, fts_hits, topk=max(topk * 3, 15))
    # restore backend labels: keep as fused lexical intermediate; re-query raw for RRF
    # Use equal-weight merge of bm25 and fts then fuse with semantic
    sem = rag.search(q, topk=max(topk * 3, 10)) if q else []
    fused = fuse_semantic_lexical(
        sem,
        lex,
        w_semantic=w_semantic,
        w_lexical=w_lexical,
        topk=topk,
    )
    return RetrievalArtifact(
        query=q,
        knowledge_mode="hybrid",
        hits=fused,
        seed_facts=seed_facts,
    )


def _seed_score(query: str, text: str) -> float:
    if not query:
        return 1.0
    q_tokens = {t.lower() for t in query.replace("-", " ").split() if t}
    t_tokens = {t.lower() for t in text.replace("-", " ").split() if t}
    if not q_tokens:
        return 0.0
    inter = q_tokens & t_tokens
    # also substring
    tl = text.lower()
    sub = sum(1 for t in q_tokens if t in tl)
    return float(len(inter) + 0.5 * sub)


def write_retrieval_artifact(path: Path, artifact: RetrievalArtifact) -> Path:
    write_json(path, artifact.to_dict())
    return path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="OR-Path knowledge retrieve")
    p.add_argument("--query", required=True, help="Search query")
    p.add_argument("--topk", type=int, default=5)
    p.add_argument(
        "--mode",
        choices=["seed", "hybrid", "off"],
        default="hybrid",
    )
    p.add_argument("--class", dest="problem_class", default=None)
    p.add_argument("--out", type=Path, default=None, help="Output JSON path")
    p.add_argument("--w-semantic", type=float, default=DEFAULT_W_SEMANTIC)
    p.add_argument("--w-lexical", type=float, default=DEFAULT_W_LEXICAL)
    args = p.parse_args(argv)

    try:
        art = retrieve(
            args.query,
            mode=args.mode,
            topk=args.topk,
            problem_class=args.problem_class,
            w_semantic=args.w_semantic,
            w_lexical=args.w_lexical,
        )
    except Exception as e:
        print(f"retrieve failed: {e}", file=sys.stderr)
        return 2

    payload = art.to_dict()
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        write_retrieval_artifact(args.out, art)
        print(f"wrote {args.out}", file=sys.stderr)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
