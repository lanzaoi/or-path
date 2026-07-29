"""Weighted Reciprocal Rank Fusion for hybrid retrieval."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping, Sequence

from knowledge_svc.chunk_schema import RetrievalHit, snippet


DEFAULT_W_SEMANTIC = 1.0
DEFAULT_W_LEXICAL = 0.4
DEFAULT_K = 60


def rrf_fuse(
    ranked_lists: Sequence[Sequence[RetrievalHit] | Sequence[Mapping]],
    *,
    weights: Sequence[float] | None = None,
    k: int = DEFAULT_K,
    topk: int = 10,
    backend: str = "rrf",
) -> list[RetrievalHit]:
    """Fuse multiple ranked hit lists via weighted RRF.

    score(d) = sum_i w_i * 1/(k + rank_i(d))  with rank starting at 1.
    """
    if not ranked_lists:
        return []
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    if len(weights) != len(ranked_lists):
        raise ValueError("weights length must match ranked_lists")

    scores: dict[str, float] = defaultdict(float)
    best: dict[str, RetrievalHit] = {}

    for w, hits in zip(weights, ranked_lists):
        for rank, h in enumerate(hits, start=1):
            if isinstance(h, RetrievalHit):
                hit = h
            else:
                hit = RetrievalHit.from_dict(h)  # type: ignore[arg-type]
            cid = hit.chunk_id
            scores[cid] += float(w) * (1.0 / (k + rank))
            prev = best.get(cid)
            if prev is None or (hit.snippet and len(hit.snippet) > len(prev.snippet or "")):
                best[cid] = hit

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    out: list[RetrievalHit] = []
    for cid, sc in ordered[: max(0, topk)]:
        base = best[cid]
        out.append(
            RetrievalHit(
                chunk_id=cid,
                score=float(sc),
                backend=backend,  # type: ignore[arg-type]
                snippet=base.snippet or snippet(""),
                source_path=base.source_path,
            )
        )
    return out


def fuse_semantic_lexical(
    semantic_hits: Sequence[RetrievalHit] | Sequence[Mapping],
    lexical_hits: Sequence[RetrievalHit] | Sequence[Mapping],
    *,
    w_semantic: float = DEFAULT_W_SEMANTIC,
    w_lexical: float = DEFAULT_W_LEXICAL,
    k: int = DEFAULT_K,
    topk: int = 10,
) -> list[RetrievalHit]:
    """Convenience: semantic list + single lexical list with default weights."""
    return rrf_fuse(
        [list(semantic_hits), list(lexical_hits)],
        weights=[w_semantic, w_lexical],
        k=k,
        topk=topk,
        backend="rrf",
    )


def merge_lexical(
    bm25_hits: Sequence[RetrievalHit],
    fts_hits: Sequence[RetrievalHit],
    *,
    topk: int = 20,
) -> list[RetrievalHit]:
    """Merge BM25 + FTS as equal-weight lexical pool before hybrid RRF."""
    return rrf_fuse(
        [list(bm25_hits), list(fts_hits)],
        weights=[1.0, 1.0],
        topk=topk,
        backend="rrf",
    )
