"""BM25 lexical index (rank_bm25) with persistence under knowledge/bm25/."""

from __future__ import annotations

import json
import pickle
import re
from pathlib import Path
from typing import Any, Iterable, Sequence

from knowledge_svc.chunk_schema import Chunk, RetrievalHit, knowledge_dir, snippet


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")

# Process-level mtime-invalidated cache: resolved_meta_path -> (sig, chunk_ids, texts, meta, bm25_obj, postings)
_BM25_CACHE: dict[Path, tuple[tuple[int, int, int, int], list[str], list[str], dict[str, dict[str, Any]], Any, dict[str, list[tuple[int, float]]]]] = {}


def _build_postings(bm25_obj: Any) -> dict[str, list[tuple[int, float]]]:
    """Precompute exact BM25Okapi inverted postings for O(postings) query scoring."""
    postings: dict[str, list[tuple[int, float]]] = {}
    if bm25_obj is None:
        return postings
    doc_freqs = getattr(bm25_obj, "doc_freqs", None)
    idf = getattr(bm25_obj, "idf", None)
    doc_len = getattr(bm25_obj, "doc_len", None)
    avgdl = float(getattr(bm25_obj, "avgdl", 1.0) or 1.0)
    k1 = float(getattr(bm25_obj, "k1", 1.5))
    b = float(getattr(bm25_obj, "b", 0.75))
    if not doc_freqs or not idf or not doc_len:
        return postings
    for idx, freqs in enumerate(doc_freqs):
        dl_norm = k1 * (1.0 - b + b * (float(doc_len[idx]) / avgdl))
        for term, tf in freqs.items():
            term_idf = float(idf.get(term, 0.0))
            if term_idf == 0.0 or not tf:
                continue
            contrib = term_idf * (float(tf) * (k1 + 1.0)) / (float(tf) + dl_norm)
            if contrib != 0.0:
                postings.setdefault(term, []).append((idx, contrib))
    return postings


def _bm25_disk_sig(meta_path: Path, pkl_path: Path) -> tuple[int, int, int, int] | None:
    try:
        ms = meta_path.stat()
    except OSError:
        return None
    try:
        ps = pkl_path.stat()
        p_m, p_s = ps.st_mtime_ns, ps.st_size
    except OSError:
        p_m, p_s = 0, 0
    return (ms.st_mtime_ns, ms.st_size, p_m, p_s)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


class BM25Index:
    def __init__(self, root: Path | None = None, index_dir: Path | None = None) -> None:
        self.root = root
        self.index_dir = index_dir or (knowledge_dir(root) / "bm25")
        self.chunk_ids: list[str] = []
        self.texts: list[str] = []
        self.meta: dict[str, dict[str, Any]] = {}
        self._bm25 = None
        self._postings: dict[str, list[tuple[int, float]]] = {}
        self._cow = False

    def _rebuild(self) -> None:
        from rank_bm25 import BM25Okapi

        corpus = [tokenize(t) for t in self.texts]
        if not corpus:
            self._bm25 = None
            self._postings = {}
            return
        # empty docs still need a token list
        corpus = [toks if toks else ["__empty__"] for toks in corpus]
        self._bm25 = BM25Okapi(corpus)
        self._postings = _build_postings(self._bm25)

    def clear(self) -> None:
        self.chunk_ids = []
        self.texts = []
        self.meta = {}
        self._bm25 = None
        self._postings = {}
        meta_path = (self.index_dir / "bm25_meta.json").resolve()
        _BM25_CACHE.pop(meta_path, None)

    def add_chunks(self, chunks: Iterable[Chunk], *, rebuild: bool = True) -> int:
        if self._cow:
            self.chunk_ids = list(self.chunk_ids)
            self.texts = list(self.texts)
            self.meta = dict(self.meta)
            self._cow = False
        n = 0
        existing = set(self.chunk_ids)
        for c in chunks:
            if c.chunk_id in existing:
                # update in place
                idx = self.chunk_ids.index(c.chunk_id)
                self.texts[idx] = c.text
                self.meta[c.chunk_id] = {
                    "source_path": c.source_path,
                    "doc_id": c.doc_id,
                    "title": c.title,
                }
            else:
                self.chunk_ids.append(c.chunk_id)
                self.texts.append(c.text)
                self.meta[c.chunk_id] = {
                    "source_path": c.source_path,
                    "doc_id": c.doc_id,
                    "title": c.title,
                }
                existing.add(c.chunk_id)
            n += 1
        if rebuild:
            self._rebuild()
        return n

    def save(self) -> Path:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "chunk_ids": self.chunk_ids,
            "texts": self.texts,
            "meta": self.meta,
        }
        meta_path = self.index_dir / "bm25_meta.json"
        meta_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        # optional pickle of bm25 object for faster load
        if self._bm25 is None:
            self._rebuild()
        pkl = self.index_dir / "bm25_model.pkl"
        with pkl.open("wb") as f:
            pickle.dump(self._bm25, f)
        key = meta_path.resolve()
        sig = _bm25_disk_sig(meta_path, pkl)
        if not self._postings and self._bm25 is not None:
            self._postings = _build_postings(self._bm25)
        if sig is not None:
            _BM25_CACHE[key] = (sig, list(self.chunk_ids), list(self.texts), dict(self.meta), self._bm25, self._postings)
        else:
            _BM25_CACHE.pop(key, None)
        return meta_path

    def load(self) -> bool:
        meta_path = self.index_dir / "bm25_meta.json"
        pkl = self.index_dir / "bm25_model.pkl"
        sig = _bm25_disk_sig(meta_path, pkl)
        if sig is None:
            return False
        key = meta_path.resolve()
        cached = _BM25_CACHE.get(key)
        if cached is not None and cached[0] == sig:
            _, c_ids, c_texts, c_meta, c_bm25, c_postings = cached
            self.chunk_ids = c_ids
            self.texts = c_texts
            self.meta = c_meta
            self._bm25 = c_bm25
            self._postings = c_postings
            self._cow = True
            return True

        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        self.chunk_ids = list(payload.get("chunk_ids") or [])
        self.texts = list(payload.get("texts") or [])
        self.meta = dict(payload.get("meta") or {})
        if pkl.is_file():
            try:
                with pkl.open("rb") as f:
                    self._bm25 = pickle.load(f)
                self._postings = _build_postings(self._bm25)
            except Exception:
                self._rebuild()
        else:
            self._rebuild()
        sig_after = _bm25_disk_sig(meta_path, pkl) or sig
        _BM25_CACHE[key] = (sig_after, list(self.chunk_ids), list(self.texts), dict(self.meta), self._bm25, self._postings)
        return True

    def search(self, query: str, topk: int = 5) -> list[RetrievalHit]:
        if self._bm25 is None:
            if not self.load() and not self.chunk_ids:
                return []
            if self._bm25 is None:
                self._rebuild()
        if self._bm25 is None or not self.chunk_ids:
            return []
        toks = tokenize(query)
        if not toks:
            return []
        k = max(1, topk)
        if self._postings:
            acc: dict[int, float] = {}
            for tok in toks:
                plist = self._postings.get(tok)
                if plist:
                    for idx, contrib in plist:
                        acc[idx] = acc.get(idx, 0.0) + contrib
            if acc:
                ranked = sorted(acc.items(), key=lambda x: (x[1], -x[0]), reverse=True)[:k]
            else:
                ranked = [(idx, 0.0) for idx in range(min(k, len(self.chunk_ids)))]
        else:
            scores = self._bm25.get_scores(toks)
            ranked = sorted(enumerate(scores), key=lambda x: float(x[1]), reverse=True)[:k]
        hits: list[RetrievalHit] = []
        for idx, sc in ranked:
            cid = self.chunk_ids[idx]
            text = self.texts[idx]
            m = self.meta.get(cid) or {}
            hits.append(
                RetrievalHit(
                    chunk_id=cid,
                    score=float(sc),
                    backend="bm25",
                    snippet=snippet(text),
                    source_path=m.get("source_path"),
                )
            )
        # Prefer positive scores; if all zero still return top ranks for debugging recall
        positive = [h for h in hits if h.score > 0]
        return positive if positive else hits
