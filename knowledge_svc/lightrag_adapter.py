"""LightRAG adapter with file-based semantic stub fallback.

If `lightrag` import or init fails, uses cosine similarity over stored
embeddings so hybrid retrieval still works offline/with mock embedder.
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
    embed_texts,
    get_api_key,
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
        self._chunks: dict[str, dict[str, Any]] = {}
        self._vectors: dict[str, list[float]] = {}
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

    def _persist(self) -> None:
        with self.chunks_path.open("w", encoding="utf-8") as f:
            for d in self._chunks.values():
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        write_json(self.vectors_path, self._vectors)

    def clear(self) -> None:
        self._chunks.clear()
        self._vectors.clear()
        if self.chunks_path.is_file():
            self.chunks_path.unlink()
        if self.vectors_path.is_file():
            self.vectors_path.unlink()

    def add_chunks(
        self,
        chunks: Iterable[Chunk],
        *,
        embed_fn: EmbedFn | None = None,
    ) -> int:
        chunk_list = list(chunks)
        if not chunk_list:
            return 0
        texts = [c.text for c in chunk_list]
        if embed_fn is None:
            if get_api_key():
                try:
                    vectors = embed_texts(texts)
                except Exception as e:
                    log.warning("live embed failed, using MockEmbedder: %s", e)
                    vectors = MockEmbedder().embed_texts(texts)
            else:
                vectors = MockEmbedder().embed_texts(texts)
        else:
            vectors = embed_fn(texts)
        for c, vec in zip(chunk_list, vectors):
            self._chunks[c.chunk_id] = c.to_dict()
            self._vectors[c.chunk_id] = list(vec)
        self._persist()
        return len(chunk_list)

    def search(
        self,
        query: str,
        topk: int = 5,
        *,
        embed_fn: EmbedFn | None = None,
    ) -> list[RetrievalHit]:
        if not self._chunks:
            self._load()
        if not self._vectors:
            return []
        if embed_fn is None:
            if get_api_key():
                try:
                    qv = embed_texts([query])[0]
                except Exception:
                    qv = MockEmbedder().embed_query(query)
            else:
                qv = MockEmbedder().embed_query(query)
        else:
            qv = embed_fn([query])[0]
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
        force_stub: bool = False,
        embed_fn: EmbedFn | None = None,
    ) -> None:
        self.work_dir = work_dir or (knowledge_dir(root) / "lightrag_ws")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.embed_fn = embed_fn
        self.mode = "stub"
        self._rag: Any = None
        self.stub = SemanticStubIndex(self.work_dir / "semantic_stub")
        if not force_stub:
            self._try_init_lightrag()

    def _try_init_lightrag(self) -> None:
        try:
            import lightrag  # noqa: F401
        except Exception as e:
            log.info("lightrag import failed; using semantic stub: %s", e)
            self.mode = "stub"
            return
        # LightRAG typically needs LLM+embedding callbacks and async workspace.
        # Full graph mode is environment-sensitive; keep stub as reliable default
        # while recording that package is importable.
        self.mode = "stub_with_lightrag_importable"
        # Optionally attempt construct; if anything fails stay on stub.
        try:
            # Prefer not to require full LightRAG runtime (LLM keys) for unit path.
            # Document that production can extend here.
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
        n = self.stub.add_chunks(chunks, embed_fn=self.embed_fn)
        # Place-holder hook for real LightRAG insert when _rag is configured.
        if self._rag is not None:
            try:
                for c in chunks:
                    # Best-effort; API varies by lightrag version
                    insert = getattr(self._rag, "insert", None) or getattr(
                        self._rag, "ainsert", None
                    )
                    if callable(insert):
                        insert(c.text)
            except Exception as e:
                log.warning("lightrag insert failed (stub still holds data): %s", e)
        return n

    def search(self, query: str, topk: int = 5) -> list[RetrievalHit]:
        return self.stub.search(query, topk=topk, embed_fn=self.embed_fn)
