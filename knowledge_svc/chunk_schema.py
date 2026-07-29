"""Chunk / RetrievalHit helpers aligned with contracts and tools.schema_models."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

Backend = Literal["lightrag", "bm25", "fts", "seed", "rrf"]
KnowledgeMode = Literal["off", "seed", "hybrid"]


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    source_path: str
    page: int | None = None
    mineru_job_id: str | None = None
    title: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None or k in ("chunk_id", "doc_id", "text", "source_path")}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Chunk:
        return cls(
            chunk_id=str(data["chunk_id"]),
            doc_id=str(data["doc_id"]),
            text=str(data["text"]),
            source_path=str(data["source_path"]),
            page=data.get("page"),
            mineru_job_id=data.get("mineru_job_id"),
            title=data.get("title"),
        )


@dataclass
class RetrievalHit:
    chunk_id: str
    score: float
    backend: Backend
    snippet: str
    source_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "chunk_id": self.chunk_id,
            "score": float(self.score),
            "backend": self.backend,
            "snippet": self.snippet,
        }
        if self.source_path is not None:
            d["source_path"] = self.source_path
        return d

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RetrievalHit:
        return cls(
            chunk_id=str(data["chunk_id"]),
            score=float(data["score"]),
            backend=data["backend"],  # type: ignore[arg-type]
            snippet=str(data.get("snippet") or ""),
            source_path=data.get("source_path"),
        )


@dataclass
class RetrievalArtifact:
    query: str
    knowledge_mode: KnowledgeMode
    hits: list[RetrievalHit] = field(default_factory=list)
    seed_facts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "knowledge_mode": self.knowledge_mode,
            "hits": [h.to_dict() for h in self.hits],
            "seed_facts": list(self.seed_facts),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RetrievalArtifact:
        hits = [RetrievalHit.from_dict(h) for h in (data.get("hits") or [])]
        return cls(
            query=str(data.get("query") or ""),
            knowledge_mode=data.get("knowledge_mode") or "off",  # type: ignore[arg-type]
            hits=hits,
            seed_facts=list(data.get("seed_facts") or []),
        )


def repo_root() -> Path:
    """knowledge_svc/ lives at <repo>/knowledge_svc."""
    return Path(__file__).resolve().parent.parent


def knowledge_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "knowledge"


def stable_chunk_id(doc_id: str, text: str, index: int = 0) -> str:
    """Deterministic chunk_id from doc + content + ordinal."""
    h = hashlib.sha256(f"{doc_id}\n{index}\n{text}".encode("utf-8")).hexdigest()[:16]
    safe_doc = re.sub(r"[^a-zA-Z0-9_-]+", "_", doc_id)[:48]
    return f"{safe_doc}_{index:04d}_{h}"


def snippet(text: str, max_len: int = 240) -> str:
    t = " ".join((text or "").split())
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def chunk_markdown(
    text: str,
    *,
    doc_id: str,
    source_path: str,
    title: str | None = None,
    max_chars: int = 900,
    overlap: int = 80,
) -> list[Chunk]:
    """Split markdown/plain text into overlapping character windows."""
    body = (text or "").strip()
    if not body:
        return []
    # Prefer paragraph boundaries when possible
    paras = re.split(r"\n\s*\n", body)
    pieces: list[str] = []
    buf = ""
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if len(buf) + len(p) + 2 <= max_chars:
            buf = f"{buf}\n\n{p}".strip() if buf else p
        else:
            if buf:
                pieces.append(buf)
            if len(p) <= max_chars:
                buf = p
            else:
                # hard-split long paragraph
                start = 0
                while start < len(p):
                    end = min(len(p), start + max_chars)
                    pieces.append(p[start:end])
                    if end >= len(p):
                        break
                    start = max(0, end - overlap)
                buf = ""
    if buf:
        pieces.append(buf)

    chunks: list[Chunk] = []
    for i, piece in enumerate(pieces):
        chunks.append(
            Chunk(
                chunk_id=stable_chunk_id(doc_id, piece, i),
                doc_id=doc_id,
                text=piece,
                source_path=source_path,
                title=title,
            )
        )
    return chunks


def write_chunks_jsonl(chunks: Iterable[Chunk], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
            n += 1
    return n


def read_chunks_jsonl(path: Path) -> list[Chunk]:
    if not path.is_file():
        return []
    out: list[Chunk] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(Chunk.from_dict(json.loads(line)))
    return out


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
