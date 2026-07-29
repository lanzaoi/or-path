"""Dual-write ingest: same chunk_id → BM25 + FTS + LightRAG/stub."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Sequence

from knowledge_svc.bm25_index import BM25Index
from knowledge_svc.chunk_schema import (
    Chunk,
    chunk_markdown,
    knowledge_dir,
    read_chunks_jsonl,
    repo_root,
    write_chunks_jsonl,
)
from knowledge_svc.fts_index import FTSIndex
from knowledge_svc.lightrag_adapter import LightRAGAdapter


def default_chunks_jsonl(root: Path | None = None) -> Path:
    return knowledge_dir(root) / "chunks" / "corpus_chunks.jsonl"


def load_markdown_file(path: Path, *, root: Path | None = None) -> list[Chunk]:
    text = path.read_text(encoding="utf-8")
    rel = str(path)
    try:
        rel = str(path.resolve().relative_to((root or repo_root()).resolve()))
    except ValueError:
        pass
    doc_id = path.stem
    title = None
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return chunk_markdown(text, doc_id=doc_id, source_path=rel.replace("\\", "/"), title=title)


def collect_corpus_chunks(
    corpus_dir: Path | None = None,
    *,
    root: Path | None = None,
) -> list[Chunk]:
    root = root or repo_root()
    cdir = corpus_dir or (knowledge_dir(root) / "corpus")
    chunks: list[Chunk] = []
    if not cdir.is_dir():
        return chunks
    for path in sorted(cdir.rglob("*")):
        if path.suffix.lower() in {".md", ".txt"} and path.is_file():
            chunks.extend(load_markdown_file(path, root=root))
    return chunks


def ingest_chunks(
    chunks: Sequence[Chunk],
    *,
    root: Path | None = None,
    persist_jsonl: Path | None = None,
    force_stub: bool = True,
    clear: bool = False,
    embed_fn=None,
) -> dict:
    """Dual-write chunks to BM25, FTS5, and semantic adapter."""
    root = root or repo_root()
    bm25 = BM25Index(root=root)
    fts = FTSIndex(root=root)
    rag = LightRAGAdapter(root=root, force_stub=force_stub, embed_fn=embed_fn)

    if clear:
        bm25.clear()
        fts.clear()
        rag.clear()

    chunk_list = list(chunks)
    n_bm25 = bm25.add_chunks(chunk_list)
    bm25.save()
    n_fts = fts.add_chunks(chunk_list)
    n_rag = rag.add_chunks(chunk_list)

    out_jsonl = persist_jsonl or default_chunks_jsonl(root)
    # merge with existing jsonl by chunk_id
    existing = {c.chunk_id: c for c in read_chunks_jsonl(out_jsonl)}
    for c in chunk_list:
        existing[c.chunk_id] = c
    write_chunks_jsonl(existing.values(), out_jsonl)

    return {
        "n_chunks": len(chunk_list),
        "bm25": n_bm25,
        "fts": n_fts,
        "semantic": n_rag,
        "semantic_mode": rag.mode,
        "chunks_jsonl": str(out_jsonl),
        "chunk_ids": [c.chunk_id for c in chunk_list],
    }


def ingest_corpus(
    *,
    root: Path | None = None,
    corpus_dir: Path | None = None,
    clear: bool = False,
    force_stub: bool = True,
    embed_fn=None,
) -> dict:
    chunks = collect_corpus_chunks(corpus_dir, root=root)
    return ingest_chunks(
        chunks,
        root=root,
        clear=clear,
        force_stub=force_stub,
        embed_fn=embed_fn,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Ingest corpus/md into hybrid indexes")
    p.add_argument("--corpus", type=Path, default=None, help="Corpus directory")
    p.add_argument("--clear", action="store_true", help="Clear indexes first")
    p.add_argument("--jsonl", type=Path, default=None, help="Chunks JSONL path")
    args = p.parse_args(argv)

    try:
        result = ingest_corpus(
            corpus_dir=args.corpus,
            clear=args.clear,
            force_stub=True,
        )
        if args.jsonl:
            # already written default; copy note
            result["requested_jsonl"] = str(args.jsonl)
        print(json.dumps(result, indent=2))
        if result["n_chunks"] == 0:
            print("warning: no chunks ingested", file=sys.stderr)
            return 1
        return 0
    except Exception as e:
        print(f"ingest failed: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
