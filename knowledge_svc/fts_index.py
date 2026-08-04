"""SQLite FTS5 lexical index under knowledge/fts/."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from knowledge_svc.chunk_schema import Chunk, RetrievalHit, knowledge_dir, snippet


class FTSIndex:
    def __init__(self, root: Path | None = None, index_dir: Path | None = None) -> None:
        self.index_dir = index_dir or (knowledge_dir(root) / "fts")
        self.db_path = self.index_dir / "chunks_fts.db"

    def _connect(self) -> sqlite3.Connection:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=60.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout=60000")
        except sqlite3.Error:
            pass
        return conn

    def ensure_schema(self, conn: sqlite3.Connection | None = None) -> None:
        own = conn is None
        c = conn or self._connect()
        try:
            c.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    chunk_id UNINDEXED,
                    doc_id UNINDEXED,
                    source_path UNINDEXED,
                    title UNINDEXED,
                    text,
                    tokenize = 'unicode61'
                );
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks_meta (
                    chunk_id TEXT PRIMARY KEY,
                    doc_id TEXT,
                    source_path TEXT,
                    title TEXT,
                    text TEXT
                );
                """
            )
            c.commit()
        finally:
            if own:
                c.close()

    def clear(self) -> None:
        """Clear rows without unlinking DB (Windows file-lock safe)."""
        if not self.db_path.is_file():
            return
        conn = self._connect()
        try:
            self.ensure_schema(conn)
            try:
                conn.execute("DELETE FROM chunks_fts")
            except sqlite3.Error:
                pass
            try:
                conn.execute("DELETE FROM chunks_meta")
            except sqlite3.Error:
                pass
            conn.commit()
        finally:
            conn.close()

    def add_chunks(self, chunks: Iterable[Chunk]) -> int:
        conn = self._connect()
        self.ensure_schema(conn)
        n = 0
        try:
            for ch in chunks:
                conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (ch.chunk_id,))
                conn.execute("DELETE FROM chunks_meta WHERE chunk_id = ?", (ch.chunk_id,))
                conn.execute(
                    """
                    INSERT INTO chunks_fts(chunk_id, doc_id, source_path, title, text)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        ch.chunk_id,
                        ch.doc_id,
                        ch.source_path,
                        ch.title or "",
                        ch.text,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO chunks_meta(chunk_id, doc_id, source_path, title, text)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        ch.chunk_id,
                        ch.doc_id,
                        ch.source_path,
                        ch.title or "",
                        ch.text,
                    ),
                )
                n += 1
            conn.commit()
        finally:
            conn.close()
        return n

    def search(self, query: str, topk: int = 5) -> list[RetrievalHit]:
        if not self.db_path.is_file():
            return []
        q = (query or "").strip()
        if not q:
            return []
        # Escape FTS5 special chars by quoting tokens simply
        # Prefer MATCH; fallback to LIKE if MATCH fails
        conn = self._connect()
        hits: list[RetrievalHit] = []
        try:
            self.ensure_schema(conn)
            try:
                # Build simple OR query from terms
                terms = [t for t in q.replace('"', " ").split() if t]
                if not terms:
                    return []
                fts_q = " OR ".join(f'"{t}"' for t in terms)
                rows = conn.execute(
                    """
                    SELECT chunk_id, source_path, text,
                           bm25(chunks_fts) AS rank
                    FROM chunks_fts
                    WHERE chunks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_q, max(1, topk)),
                ).fetchall()
                for r in rows:
                    # bm25 in sqlite is lower-is-better; invert for higher-is-better
                    rank = float(r["rank"])
                    score = 1.0 / (1.0 + max(rank, 0.0)) if rank >= 0 else -rank
                    hits.append(
                        RetrievalHit(
                            chunk_id=r["chunk_id"],
                            score=float(score),
                            backend="fts",
                            snippet=snippet(r["text"] or ""),
                            source_path=r["source_path"],
                        )
                    )
            except sqlite3.OperationalError:
                # LIKE fallback
                like = f"%{q}%"
                rows = conn.execute(
                    """
                    SELECT chunk_id, source_path, text FROM chunks_meta
                    WHERE text LIKE ?
                    LIMIT ?
                    """,
                    (like, max(1, topk)),
                ).fetchall()
                for i, r in enumerate(rows):
                    hits.append(
                        RetrievalHit(
                            chunk_id=r["chunk_id"],
                            score=1.0 / (i + 1),
                            backend="fts",
                            snippet=snippet(r["text"] or ""),
                            source_path=r["source_path"],
                        )
                    )
        finally:
            conn.close()
        return hits
