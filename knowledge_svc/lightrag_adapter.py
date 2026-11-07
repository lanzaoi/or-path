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

try:
    import numpy as _np
except Exception:  # pragma: no cover
    _np = None  # type: ignore[assignment]

# Process-level mtime-invalidated cache for SemanticStubIndex
_SEM_CACHE: dict[Path, dict[str, Any]] = {}
_LIGHTRAG_IMPORTABLE: bool | None = None


def _file_sig(p: Path) -> tuple[int, int]:
    try:
        st = p.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return (0, 0)


def _build_norm_matrix(vectors: dict[str, list[float]]) -> tuple[list[str], Any]:
    """Build normalized float32 matrix (N, D) + ordered chunk_ids when dims match."""
    if _np is None or not vectors:
        return [], None
    ids = list(vectors.keys())
    dim = len(vectors[ids[0]])
    if dim == 0 or any(len(vectors[cid]) != dim for cid in ids):
        return [], None
    mat = _np.asarray([vectors[cid] for cid in ids], dtype=_np.float32)
    norms = _np.linalg.norm(mat, axis=1, keepdims=True)
    norms = _np.where(norms > 1e-12, norms, 1.0)
    return ids, (mat / norms).astype(_np.float32, copy=False)


class SemanticStubIndex:
    """File-based chunk store + embedding vectors; vectorized cosine search."""

    def __init__(self, work_dir: Path) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_path = work_dir / "stub_chunks.jsonl"
        self.vectors_path = work_dir / "stub_vectors.json"
        self.npy_path = work_dir / "stub_vectors.npy"
        self.vec_ids_path = work_dir / "stub_vec_ids.json"
        self.meta_path = work_dir / "embed_meta.json"
        self._chunks: dict[str, dict[str, Any]] = {}
        self._vectors: dict[str, list[float]] = {}
        self._vec_ids: list[str] = []
        self._mat_norm: Any = None
        self._cow: bool = False
        self.last_embed_mode: str = "stub"
        self._load()

    def _disk_sig(self) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
        return (
            _file_sig(self.chunks_path),
            _file_sig(self.vectors_path),
            _file_sig(self.meta_path),
        )

    def _write_npy_sidecar(self, vec_ids: list[str], mat_norm: Any) -> None:
        if _np is None or mat_norm is None or not vec_ids:
            return
        try:
            tmp_ids = self.vec_ids_path.with_suffix(".json.tmp")
            tmp_ids.write_text(json.dumps(vec_ids, ensure_ascii=False), encoding="utf-8")
            tmp_ids.replace(self.vec_ids_path)
            with self.npy_path.open("wb") as f:
                _np.save(f, mat_norm, allow_pickle=False)
        except Exception as e:
            log.debug("optional npy sidecar write skipped: %s", e)

    def _ensure_vectors_dict(self) -> None:
        """Lazily populate self._vectors if loaded via fast .npy sidecar."""
        if self._vectors:
            return
        if self.vectors_path.is_file():
            try:
                self._vectors = json.loads(self.vectors_path.read_text(encoding="utf-8"))
                return
            except Exception:
                pass
        if self._mat_norm is not None and self._vec_ids:
            self._vectors = {
                cid: self._mat_norm[idx].tolist()
                for idx, cid in enumerate(self._vec_ids)
            }

    def _load(self) -> None:
        key = self.work_dir.resolve()
        sig = self._disk_sig()
        cached = _SEM_CACHE.get(key)
        if cached is not None and cached.get("sig") == sig:
            self._chunks = cached["chunks"]
            self._vectors = cached["vectors"]
            self._vec_ids = cached["vec_ids"]
            self._mat_norm = cached["mat_norm"]
            self.last_embed_mode = str(cached["last_embed_mode"])
            self._cow = True
            return

        self._chunks = {}
        self._vectors = {}
        self._vec_ids = []
        self._mat_norm = None
        self._cow = False

        if self.chunks_path.is_file():
            try:
                for line in self.chunks_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    d = json.loads(line)
                    self._chunks[d["chunk_id"]] = d
            except Exception as e:
                log.warning("corrupt stub_chunks.jsonl, resetting: %s", e)
                self._chunks.clear()

        loaded_fast_npy = False
        if (
            _np is not None
            and self.npy_path.is_file()
            and self.vec_ids_path.is_file()
            and (
                not self.vectors_path.is_file()
                or self.npy_path.stat().st_mtime_ns >= self.vectors_path.stat().st_mtime_ns
            )
        ):
            try:
                ids = json.loads(self.vec_ids_path.read_text(encoding="utf-8"))
                mat = _np.load(self.npy_path, allow_pickle=False)
                if isinstance(ids, list) and mat.ndim == 2 and mat.shape[0] == len(ids):
                    self._vec_ids = [str(x) for x in ids]
                    self._mat_norm = mat.astype(_np.float32, copy=False)
                    loaded_fast_npy = True
            except Exception:
                loaded_fast_npy = False

        if not loaded_fast_npy and self.vectors_path.is_file():
            try:
                self._vectors = json.loads(self.vectors_path.read_text(encoding="utf-8"))
                self._vec_ids, self._mat_norm = _build_norm_matrix(self._vectors)
                if self._mat_norm is not None:
                    self._write_npy_sidecar(self._vec_ids, self._mat_norm)
            except Exception as e:
                log.warning("corrupt stub_vectors.json, resetting: %s", e)
                self._vectors.clear()

        if self.meta_path.is_file():
            try:
                meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
                self.last_embed_mode = str(meta.get("embed_mode") or "stub")
            except Exception:
                pass

        _SEM_CACHE[key] = {
            "sig": self._disk_sig(),
            "chunks": dict(self._chunks),
            "vectors": dict(self._vectors),
            "vec_ids": list(self._vec_ids),
            "mat_norm": self._mat_norm,
            "last_embed_mode": self.last_embed_mode,
        }

    def _persist(self, *, embed_mode: str | None = None) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        tmp_chunks = self.chunks_path.with_suffix(".jsonl.tmp")
        with tmp_chunks.open("w", encoding="utf-8") as f:
            for d in self._chunks.values():
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        tmp_chunks.replace(self.chunks_path)

        tmp_vecs = self.vectors_path.with_suffix(".json.tmp")
        tmp_vecs.write_text(
            json.dumps(self._vectors, separators=(",", ":")),
            encoding="utf-8",
        )
        tmp_vecs.replace(self.vectors_path)

        self._vec_ids, self._mat_norm = _build_norm_matrix(self._vectors)
        if self._mat_norm is not None:
            self._write_npy_sidecar(self._vec_ids, self._mat_norm)
        else:
            for p in (self.npy_path, self.vec_ids_path):
                if p.is_file():
                    p.unlink()

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
        key = self.work_dir.resolve()
        _SEM_CACHE[key] = {
            "sig": self._disk_sig(),
            "chunks": dict(self._chunks),
            "vectors": dict(self._vectors),
            "vec_ids": list(self._vec_ids),
            "mat_norm": self._mat_norm,
            "last_embed_mode": self.last_embed_mode,
        }

    def clear(self) -> None:
        self._chunks = {}
        self._vectors = {}
        self._vec_ids = []
        self._mat_norm = None
        self._cow = False
        self.last_embed_mode = "stub"
        for p in (self.chunks_path, self.vectors_path, self.npy_path, self.vec_ids_path, self.meta_path):
            if p.is_file():
                p.unlink()
        _SEM_CACHE.pop(self.work_dir.resolve(), None)

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
        if self._cow:
            self._chunks = dict(self._chunks)
            self._vectors = dict(self._vectors)
            self._vec_ids = list(self._vec_ids)
            self._cow = False
        self._ensure_vectors_dict()
        texts = [c.text for c in chunk_list]
        if embed_fn is None:
            embed_fn = make_embed_fn("stub" if embed_mode != "live" else "live")
        used_mode = embed_mode
        try:
            vectors = embed_fn(texts)
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
        if not self._chunks and not self._vec_ids:
            self._load()
        if not self._vectors and self._mat_norm is None:
            return []
        effective_mode = embed_mode
        if self.last_embed_mode == "stub" and embed_mode != "live":
            effective_mode = "stub"
        if embed_fn is None or (self.last_embed_mode == "stub" and embed_mode == "stub"):
            embed_fn = make_embed_fn("stub" if effective_mode != "live" else "live")
        try:
            qv = embed_fn([query])[0]
            self.last_embed_mode = effective_mode
        except Exception:
            qv = MockEmbedder().embed_query(query)
            self.last_embed_mode = "stub"

        k = max(1, topk)
        if _np is not None and self._mat_norm is not None and len(qv) == self._mat_norm.shape[1]:
            qv_arr = _np.asarray(qv, dtype=_np.float32)
            qnorm = float(_np.linalg.norm(qv_arr))
            qv_unit = qv_arr / qnorm if qnorm > 1e-12 else _np.zeros_like(qv_arr)
            scores_arr = self._mat_norm @ qv_unit
            n = int(scores_arr.shape[0])
            if n <= k:
                top_idx = _np.argsort(-scores_arr)
            else:
                part = _np.argpartition(-scores_arr, k - 1)[:k]
                top_idx = part[_np.argsort(-scores_arr[part])]
            hits: list[RetrievalHit] = []
            for idx_i in top_idx:
                i = int(idx_i)
                cid = self._vec_ids[i]
                d = self._chunks.get(cid) or {}
                hits.append(
                    RetrievalHit(
                        chunk_id=cid,
                        score=float(scores_arr[i]),
                        backend="lightrag",
                        snippet=snippet(str(d.get("text") or "")),
                        source_path=d.get("source_path"),
                    )
                )
            return hits

        self._ensure_vectors_dict()
        scored: list[tuple[str, float]] = []
        qnorm = sum(float(x) * float(x) for x in qv) ** 0.5
        if qnorm > 0:
            qv_unit_list = [float(x) / qnorm for x in qv]
            nz = [(i, x) for i, x in enumerate(qv_unit_list) if x != 0.0]
        else:
            qv_unit_list = []
            nz = []
        if nz and len(nz) < len(qv_unit_list) // 2:
            qlen = len(qv_unit_list)
            for cid, vec in self._vectors.items():
                if len(vec) == qlen:
                    scored.append((cid, sum(x * vec[i] for i, x in nz)))
                else:
                    scored.append((cid, cosine_similarity(qv, vec)))
        else:
            for cid, vec in self._vectors.items():
                scored.append((cid, cosine_similarity(qv, vec)))
        scored.sort(key=lambda x: x[1], reverse=True)
        hits = []
        for cid, sc in scored[:k]:
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
        global _LIGHTRAG_IMPORTABLE
        if _LIGHTRAG_IMPORTABLE is None:
            try:
                import lightrag  # noqa: F401
                _LIGHTRAG_IMPORTABLE = True
            except Exception as e:
                log.info("lightrag import failed; using semantic stub: %s", e)
                _LIGHTRAG_IMPORTABLE = False
        if not _LIGHTRAG_IMPORTABLE:
            self.mode = "stub"
            return
        self.mode = "stub_with_lightrag_importable"
        self._rag = None

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
