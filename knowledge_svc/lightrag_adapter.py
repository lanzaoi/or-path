"""LightRAG adapter with file-based semantic index (stub or live embed).

If `lightrag` import or init fails, uses cosine similarity over stored
embeddings so hybrid retrieval still works offline/with mock embedder.

embed_mode: live | stub  (from ORPATH_KNOWLEDGE_EMBED=auto|live|stub)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from knowledge_svc.chunk_schema import Chunk, RetrievalHit, knowledge_dir, snippet, write_json
from knowledge_svc.embed_siliconflow import (
    MockEmbedder,
    cosine_similarity,
    make_embed_fn,
    resolve_embed_mode,
)

log = logging.getLogger(__name__)

EmbedFn = Callable[[Sequence[str]], list[list[float]]]


class SemanticStubIndex:
    """File-based chunk store + embedding vectors; cosine search."""

    def __init__(self, work_dir: Path) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_path = work_dir / "stub_chunks.jsonl"
        self.vectors_path = work_dir / "stub_vectors.json"
        self.meta_path = work_dir / "embed_meta.json"
        self._chunks: dict[str, dict[str, Any]] = {}
        self._vectors: dict[str, list[float]] = {}
        self.last_embed_mode: str = "stub"
        self._load()

    def _load(self) -> None:
        if self.chunks_path.is_file():
            for line in self.chunks_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                self._chunks[d["chunk_id"]] = d
        if self.vectors_path.is_file():
            self._vectors = json.loads(self.vectors_path.read_text(encoding="utf-8"))
        if self.meta_path.is_file():
            try:
                meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
                self.last_embed_mode = str(meta.get("embed_mode") or "stub")
            except Exception:
                pass

    def _persist(self, *, embed_mode: str | None = None) -> None:
        with self.chunks_path.open("w", encoding="utf-8") as f:
            for d in self._chunks.values():
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        write_json(self.vectors_path, self._vectors)
        if embed_mode:
            self.last_embed_mode = embed_mode
        write_json(
            self.meta_path,
            {
                "embed_mode": self.last_embed_mode,
                "n_chunks": len(self._chunks),
                "n_vectors": len(self._vectors),
            },
        )

    def clear(self) -> None:
        self._chunks.clear()
        self._vectors.clear()
        self.last_embed_mode = "stub"
        for p in (self.chunks_path, self.vectors_path, self.meta_path):
            if p.is_file():
                p.unlink()

    def add_chunks(
        self,
        chunks: Iterable[Chunk],
        *,
        embed_fn: EmbedFn | None = None,
        embed_mode: str = "stub",
    ) -> int:
        chunk_list = list(chunks)
        if not chunk_list:
            return 0
        texts = [c.text for c in chunk_list]
        if embed_fn is None:
            embed_fn = make_embed_fn("stub" if embed_mode != "live" else "live")
        used_mode = embed_mode
        try:
            vectors = embed_fn(texts)
            # if live fn fell back to mock vectors silently, still label requested mode;
            # callers set embed_mode honestly before call when using make_embed_fn.
        except Exception as e:
            log.warning("embed failed, MockEmbedder: %s", e)
            vectors = MockEmbedder().embed_texts(texts)
            used_mode = "stub"
        for c, vec in zip(chunk_list, vectors):
            self._chunks[c.chunk_id] = c.to_dict()
            self._vectors[c.chunk_id] = list(vec)
        self._persist(embed_mode=used_mode)
        return len(chunk_list)

    def search(
        self,
        query: str,
        topk: int = 5,
        *,
        embed_fn: EmbedFn | None = None,
        embed_mode: str = "stub",
    ) -> list[RetrievalHit]:
        if not self._chunks:
            self._load()
        if not self._vectors:
            return []
        if embed_fn is None:
            embed_fn = make_embed_fn("stub" if embed_mode != "live" else "live")
        try:
            qv = embed_fn([query])[0]
            self.last_embed_mode = embed_mode
        except Exception:
            qv = MockEmbedder().embed_query(query)
            self.last_embed_mode = "stub"
        scored: list[tuple[str, float]] = []
        for cid, vec in self._vectors.items():
            scored.append((cid, cosine_similarity(qv, vec)))
        scored.sort(key=lambda x: x[1], reverse=True)
        hits: list[RetrievalHit] = []
        for cid, sc in scored[: max(1, topk)]:
            d = self._chunks.get(cid) or {}
            hits.append(
                RetrievalHit(
                    chunk_id=cid,
                    score=float(sc),
                    backend="lightrag",
                    snippet=snippet(str(d.get("text") or "")),
                    source_path=d.get("source_path"),
                )
            )
        return hits


class LightRAGAdapter:
    """Best-effort LightRAG wrapper; falls back to SemanticStubIndex."""

    def __init__(
        self,
        root: Path | None = None,
        work_dir: Path | None = None,
        *,
        force_stub: bool | None = None,
        embed_fn: EmbedFn | None = None,
        embed_mode: str | None = None,
    ) -> None:
        self.work_dir = work_dir or (knowledge_dir(root) / "lightrag_ws")
        self.work_dir.mkdir(parents=True, exist_ok=True)

        if embed_mode is not None:
            resolved = embed_mode if embed_mode in ("live", "stub") else "stub"
            meta = {"requested": embed_mode, "resolved": resolved}
        else:
            req = "stub" if force_stub is True else None
            if force_stub is False:
                req = "live"
            resolved, meta = resolve_embed_mode(req)

        # force_stub=True wins
        if force_stub is True:
            resolved = "stub"
            meta = {**meta, "resolved": "stub", "forced_stub": True}

        self.embed_mode: str = resolved
        self.embed_meta: dict[str, Any] = meta
        self.embed_fn = embed_fn or make_embed_fn(resolved)  # type: ignore[arg-type]
        self.mode = "stub"
        self._rag: Any = None
        self.stub = SemanticStubIndex(self.work_dir / "semantic_stub")
        if force_stub is not True:
            self._try_init_lightrag()

    def _try_init_lightrag(self) -> None:
        try:
            import lightrag  # noqa: F401
        except Exception as e:
            log.info("lightrag import failed; using semantic stub: %s", e)
            self.mode = "stub"
            return
        self.mode = "stub_with_lightrag_importable"
        try:
            self._rag = None
            log.info(
                "lightrag package importable; dual-write uses semantic stub "
                "(extend LightRAGAdapter for full graph mode when LLM configured)"
            )
        except Exception as e:
            log.warning("lightrag init failed: %s", e)
            self.mode = "stub"

    def clear(self) -> None:
        self.stub.clear()

    def add_chunks(self, chunks: Iterable[Chunk]) -> int:
        n = self.stub.add_chunks(
            chunks, embed_fn=self.embed_fn, embed_mode=self.embed_mode
        )
        self.embed_mode = self.stub.last_embed_mode or self.embed_mode
        if self._rag is not None:
            try:
                for c in chunks:
                    insert = getattr(self._rag, "insert", None) or getattr(
                        self._rag, "ainsert", None
                    )
                    if callable(insert):
                        insert(c.text)
            except Exception as e:
                log.warning("lightrag insert failed (stub still holds data): %s", e)
        return n

    def search(self, query: str, topk: int = 5) -> list[RetrievalHit]:
        hits = self.stub.search(
            query, topk=topk, embed_fn=self.embed_fn, embed_mode=self.embed_mode
        )
        self.embed_mode = self.stub.last_embed_mode or self.embed_mode
        return hits
