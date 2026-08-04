"""Dual-write ingest: same chunk_id → BM25 + FTS + LightRAG/stub.

v3 Phase3: incremental skip when corpus fingerprints unchanged (--clear forces full).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from knowledge_svc.bm25_index import BM25Index
from knowledge_svc.chunk_schema import (
    Chunk,
    chunk_markdown,
    knowledge_dir,
    read_chunks_jsonl,
    repo_root,
    write_chunks_jsonl,
    write_json,
)
from knowledge_svc.embed_siliconflow import resolve_embed_mode, resolve_knowledge_profile
from knowledge_svc.fts_index import FTSIndex
from knowledge_svc.lightrag_adapter import LightRAGAdapter


def default_chunks_jsonl(root: Path | None = None) -> Path:
    return knowledge_dir(root) / "chunks" / "corpus_chunks.jsonl"


def fingerprint_path(root: Path | None = None) -> Path:
    return knowledge_dir(root) / "chunks" / "ingest_fingerprint.json"


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


def iter_corpus_files(corpus_dir: Path) -> list[Path]:
    files: list[Path] = []
    if not corpus_dir.is_dir():
        return files
    for path in sorted(corpus_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name.lower() in {"readme.md", "readme.txt", ".gitkeep"}:
            continue
        if path.suffix.lower() in {".md", ".txt"}:
            files.append(path)
    return files


def file_fingerprint(path: Path, *, root: Path) -> dict[str, Any]:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    try:
        rel = str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        rel = str(path).replace("\\", "/")
    st = path.stat()
    return {
        "path": rel,
        "sha256": digest,
        "size": st.st_size,
        # mtime kept for humans only — NOT part of files_sha256 (Windows mtime noise)
        "mtime_ns": getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
    }


def corpus_fingerprint(corpus_dir: Path, *, root: Path) -> dict[str, Any]:
    files = iter_corpus_files(corpus_dir)
    entries = [file_fingerprint(p, root=root) for p in files]
    # Content-only identity (path + sha256 + size)
    identity = [{"path": e["path"], "sha256": e["sha256"], "size": e["size"]} for e in entries]
    blob = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return {
        "schema": "orpath.ingest_fingerprint.v1",
        "n_files": len(entries),
        "files_sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        "files": entries,
    }


def index_fingerprint_str(fp: dict[str, Any] | None) -> str:
    if not fp:
        return ""
    return str(fp.get("files_sha256") or "")


def collect_corpus_chunks(
    corpus_dir: Path | None = None,
    *,
    root: Path | None = None,
) -> list[Chunk]:
    root = root or repo_root()
    cdir = corpus_dir or (knowledge_dir(root) / "corpus")
    chunks: list[Chunk] = []
    for path in iter_corpus_files(cdir):
        chunks.extend(load_markdown_file(path, root=root))
    return chunks


def ingest_chunks(
    chunks: Sequence[Chunk],
    *,
    root: Path | None = None,
    persist_jsonl: Path | None = None,
    force_stub: bool | None = None,
    embed_mode: str | None = None,
    clear: bool = False,
    embed_fn=None,
    fingerprint: dict[str, Any] | None = None,
    incremental_meta: dict[str, Any] | None = None,
) -> dict:
    """Dual-write chunks to BM25, FTS5, and semantic adapter."""
    root = root or repo_root()
    bm25 = BM25Index(root=root)
    fts = FTSIndex(root=root)
    rag = LightRAGAdapter(
        root=root,
        force_stub=force_stub,
        embed_fn=embed_fn,
        embed_mode=embed_mode,
    )

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
    existing = {c.chunk_id: c for c in read_chunks_jsonl(out_jsonl)}
    for c in chunk_list:
        existing[c.chunk_id] = c
    write_chunks_jsonl(existing.values(), out_jsonl)

    if fingerprint is not None:
        fp_path = fingerprint_path(root)
        fp_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(fp_path, fingerprint)

    result = {
        "n_chunks": len(chunk_list),
        "bm25": n_bm25,
        "fts": n_fts,
        "semantic": n_rag,
        "semantic_mode": rag.mode,
        "embed_mode": rag.embed_mode,
        "embed_meta": rag.embed_meta,
        "chunks_jsonl": str(out_jsonl),
        "chunk_ids": [c.chunk_id for c in chunk_list],
        "index_fingerprint": index_fingerprint_str(fingerprint),
        "incremental": False,
        "n_skipped_files": 0,
        "skipped": False,
    }
    if incremental_meta:
        result.update(incremental_meta)
    return result


def ingest_corpus(
    *,
    root: Path | None = None,
    corpus_dir: Path | None = None,
    clear: bool = False,
    force_stub: bool | None = None,
    embed_mode: str | None = None,
    embed_fn=None,
    incremental: bool = True,
) -> dict:
    root = root or repo_root()
    cdir = corpus_dir or (knowledge_dir(root) / "corpus")
    t0 = time.perf_counter()
    fp = corpus_fingerprint(cdir, root=root)
    fp_path = fingerprint_path(root)
    prev = None
    if fp_path.is_file():
        try:
            prev = json.loads(fp_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = None

    if (
        incremental
        and not clear
        and prev
        and index_fingerprint_str(prev) == index_fingerprint_str(fp)
        and default_chunks_jsonl(root).is_file()
    ):
        existing = list(read_chunks_jsonl(default_chunks_jsonl(root)))
        # still resolve embed mode for honest reporting
        mode, meta = resolve_embed_mode(embed_mode)
        if force_stub is True:
            mode, meta = "stub", {**meta, "forced_stub": True}
        elapsed = time.perf_counter() - t0
        return {
            "n_chunks": len(existing),
            "bm25": 0,
            "fts": 0,
            "semantic": 0,
            "semantic_mode": "skipped",
            "embed_mode": mode,
            "embed_meta": meta,
            "chunks_jsonl": str(default_chunks_jsonl(root)),
            "chunk_ids": [c.chunk_id for c in existing[:20]],
            "index_fingerprint": index_fingerprint_str(fp),
            "incremental": True,
            "skipped": True,
            "n_skipped_files": int(fp.get("n_files") or 0),
            "n_files": int(fp.get("n_files") or 0),
            "elapsed_s": round(elapsed, 4),
            "reason": "fingerprint_unchanged",
        }

    chunks = collect_corpus_chunks(cdir, root=root)
    result = ingest_chunks(
        chunks,
        root=root,
        clear=clear,
        force_stub=force_stub,
        embed_mode=embed_mode,
        embed_fn=embed_fn,
        fingerprint=fp,
        incremental_meta={
            "incremental": incremental and not clear,
            "skipped": False,
            "n_skipped_files": 0,
            "n_files": int(fp.get("n_files") or 0),
            "elapsed_s": round(time.perf_counter() - t0, 4),
            "reason": "full_rebuild" if clear or not prev else "fingerprint_changed",
        },
    )
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Ingest corpus/md into hybrid indexes")
    p.add_argument("--corpus", type=Path, default=None, help="Corpus directory")
    p.add_argument("--clear", action="store_true", help="Clear indexes first (full rebuild)")
    p.add_argument("--jsonl", type=Path, default=None, help="Chunks JSONL path")
    p.add_argument(
        "--embed-mode",
        choices=["auto", "live", "stub"],
        default=None,
        help="Override ORPATH_KNOWLEDGE_EMBED (default auto / research profile)",
    )
    p.add_argument(
        "--profile",
        choices=["demo", "research"],
        default=None,
        help="Override ORPATH_KNOWLEDGE_PROFILE",
    )
    p.add_argument("--force-stub", action="store_true", help="Force stub embeddings")
    p.add_argument(
        "--no-incremental",
        action="store_true",
        help="Always rebuild even if fingerprint matches",
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
        result = ingest_corpus(
            corpus_dir=args.corpus,
            clear=args.clear,
            force_stub=force_stub,
            embed_mode=None if emb in (None, "auto") else emb,
            incremental=not args.no_incremental,
        )
        prof, pmeta = resolve_knowledge_profile()
        result["profile"] = prof
        result["profile_meta"] = pmeta
        if args.jsonl:
            result["requested_jsonl"] = str(args.jsonl)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        if result["n_chunks"] == 0 and not result.get("skipped"):
            print("warning: no chunks ingested", file=sys.stderr)
            return 1
        return 0
    except Exception as e:
        print(f"ingest failed: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
