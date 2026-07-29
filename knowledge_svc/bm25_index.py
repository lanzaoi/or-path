"""BM25 lexical index (rank_bm25) with persistence under knowledge/bm25/."""

from __future__ import annotations

import json
import pickle
import re
from pathlib import Path
from typing import Any, Iterable, Sequence

from knowledge_svc.chunk_schema import Chunk, RetrievalHit, knowledge_dir, snippet


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


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

    def _rebuild(self) -> None:
        from rank_bm25 import BM25Okapi

        corpus = [tokenize(t) for t in self.texts]
        if not corpus:
            self._bm25 = None
            return
        # empty docs still need a token list
        corpus = [toks if toks else ["__empty__"] for toks in corpus]
        self._bm25 = BM25Okapi(corpus)

    def clear(self) -> None:
        self.chunk_ids = []
        self.texts = []
        self.meta = {}
        self._bm25 = None

    def add_chunks(self, chunks: Iterable[Chunk], *, rebuild: bool = True) -> int:
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
        return meta_path

    def load(self) -> bool:
        meta_path = self.index_dir / "bm25_meta.json"
        if not meta_path.is_file():
            return False
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        self.chunk_ids = list(payload.get("chunk_ids") or [])
        self.texts = list(payload.get("texts") or [])
        self.meta = dict(payload.get("meta") or {})
        pkl = self.index_dir / "bm25_model.pkl"
        if pkl.is_file():
            try:
                with pkl.open("rb") as f:
                    self._bm25 = pickle.load(f)
            except Exception:
                self._rebuild()
        else:
            self._rebuild()
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
        scores = self._bm25.get_scores(toks)
        ranked = sorted(enumerate(scores), key=lambda x: float(x[1]), reverse=True)
        hits: list[RetrievalHit] = []
        for idx, sc in ranked[: max(1, topk)]:
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
