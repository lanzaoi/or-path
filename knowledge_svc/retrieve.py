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
    write_json,
)
from knowledge_svc.embed_siliconflow import resolve_embed_mode
from knowledge_svc.fts_index import FTSIndex
from knowledge_svc.lightrag_adapter import LightRAGAdapter
from knowledge_svc.rrf_fuse import (
    DEFAULT_W_LEXICAL,
    DEFAULT_W_SEMANTIC,
    fuse_semantic_lexical,
    merge_lexical,
)
from knowledge_svc.seed_graph_query import query_all_classes, query_by_class

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
    force_stub: bool | None = None,
    embed_mode: str | None = None,
    embed_fn=None,
) -> RetrievalArtifact:
    """Run retrieval; empty hits stay empty (no fabricated cites).

    embed_mode / ORPATH_KNOWLEDGE_EMBED: auto|live|stub
    force_stub=True forces stub; False tries live; None uses env auto.
    """
    from knowledge_svc.chunk_schema import repo_root

    root = root or repo_root()
    q = (query or "").strip()
    seed_facts: list[dict[str, Any]] = []
    hits: list[RetrievalHit] = []

    if mode == "off":
        art = RetrievalArtifact(query=q, knowledge_mode="off", hits=[], seed_facts=[])
        return art

    if problem_class:
        seed_facts = query_by_class(problem_class)
    else:
        try:
            seed_facts = query_all_classes()
        except FileNotFoundError:
            seed_facts = []

    if mode == "seed":
        for fact in seed_facts:
            for node in fact.get("nodes") or []:
                if node.get("type") not in {"ProblemClass", "Solver", "Constraint", "Case"}:
                    continue
                nid = str(node.get("id") or "")
                label = str(node.get("label") or nid)
                summary = str((node.get("props") or {}).get("summary") or label)
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
    rag = LightRAGAdapter(
        root=root,
        force_stub=force_stub,
        embed_fn=embed_fn,
        embed_mode=embed_mode,
    )

    bm25_hits = bm25.search(q, topk=max(topk * 3, 10)) if q else []
    fts_hits = fts.search(q, topk=max(topk * 3, 10)) if q else []
    lex = merge_lexical(bm25_hits, fts_hits, topk=max(topk * 3, 15))
    sem = rag.search(q, topk=max(topk * 3, 10)) if q else []
    fused = fuse_semantic_lexical(
        sem,
        lex,
        w_semantic=w_semantic,
        w_lexical=w_lexical,
        topk=topk,
    )
    art = RetrievalArtifact(
        query=q,
        knowledge_mode="hybrid",
        hits=fused,
        seed_facts=seed_facts,
    )
    # attach embed diagnostics on instance for callers
    art.embed_mode = rag.embed_mode  # type: ignore[attr-defined]
    art.embed_meta = rag.embed_meta  # type: ignore[attr-defined]
    art.semantic_mode = rag.mode  # type: ignore[attr-defined]
    try:
        from knowledge_svc.embed_siliconflow import resolve_knowledge_profile
        from knowledge_svc.ingest import fingerprint_path, index_fingerprint_str
        import json as _json

        prof, pmeta = resolve_knowledge_profile()
        art.profile = prof  # type: ignore[attr-defined]
        art.profile_meta = pmeta  # type: ignore[attr-defined]
        fp_path = fingerprint_path(root)
        if fp_path.is_file():
            fp = _json.loads(fp_path.read_text(encoding="utf-8"))
            art.index_fingerprint = index_fingerprint_str(fp)  # type: ignore[attr-defined]
    except Exception:
        pass
    return art


def artifact_to_payload(art: RetrievalArtifact) -> dict[str, Any]:
    payload = art.to_dict()
    for key in (
        "embed_mode",
        "embed_meta",
        "semantic_mode",
        "profile",
        "profile_meta",
        "index_fingerprint",
    ):
        if hasattr(art, key):
            payload[key] = getattr(art, key)
    return payload


def _seed_score(query: str, text: str) -> float:
    if not query:
        return 1.0
    q_tokens = {t.lower() for t in query.replace("-", " ").split() if t}
    t_tokens = {t.lower() for t in text.replace("-", " ").split() if t}
    if not q_tokens:
        return 0.0
    inter = q_tokens & t_tokens
    tl = text.lower()
    sub = sum(1 for t in q_tokens if t in tl)
    return float(len(inter) + 0.5 * sub)


def write_retrieval_artifact(path: Path, artifact: RetrievalArtifact) -> Path:
    write_json(path, artifact_to_payload(artifact))
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
    p.add_argument(
        "--embed-mode",
        choices=["auto", "live", "stub"],
        default=None,
        help="Override ORPATH_KNOWLEDGE_EMBED",
    )
    p.add_argument(
        "--profile",
        choices=["demo", "research"],
        default=None,
        help="Override ORPATH_KNOWLEDGE_PROFILE",
    )
    p.add_argument(
        "--force-stub",
        action="store_true",
        help="Force stub embeddings (legacy)",
    )
    args = p.parse_args(argv)

    if args.profile:
        import os

        os.environ["ORPATH_KNOWLEDGE_PROFILE"] = args.profile

    emb = args.embed_mode
    force_stub: bool | None = True if args.force_stub else None
    if emb == "stub":
        force_stub = True
    elif emb == "live":
        force_stub = False
    elif emb == "auto":
        force_stub = None

    try:
        art = retrieve(
            args.query,
            mode=args.mode,
            topk=args.topk,
            problem_class=args.problem_class,
            w_semantic=args.w_semantic,
            w_lexical=args.w_lexical,
            force_stub=force_stub,
            embed_mode=None if emb in (None, "auto") else emb,
        )
    except Exception as e:
        print(f"retrieve failed: {e}", file=sys.stderr)
        return 2

    payload = artifact_to_payload(art)
    if emb is None and force_stub is None:
        # ensure field always present for hybrid
        if args.mode == "hybrid" and "embed_mode" not in payload:
            mode_r, meta = resolve_embed_mode()
            payload["embed_mode"] = mode_r
            payload["embed_meta"] = meta
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        write_json(args.out, payload)
        print(f"wrote {args.out}", file=sys.stderr)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
