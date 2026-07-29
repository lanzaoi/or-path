"""SiliconFlow OpenAI-compatible embeddings (BAAI/bge-m3, dim 1024)."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import Sequence

# Never print secrets.

DEFAULT_MODEL = "BAAI/bge-m3"
DEFAULT_DIM = 1024
DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
ROOT = Path(__file__).resolve().parents[1]


def load_env(root: Path | None = None) -> None:
    try:
        from dotenv import load_dotenv as _load
    except ImportError:
        return
    env_path = (root or ROOT) / ".env"
    if env_path.is_file():
        _load(env_path, override=False)


# alias used by mineru/cognee clients
def load_dotenv(root: Path | None = None) -> None:
    load_env(root)


def get_api_key() -> str | None:
    load_env()
    key = (os.environ.get("SILICONFLOW_API_KEY") or os.environ.get("SF_API_KEY") or "").strip()
    return key or None


def get_base_url() -> str:
    load_env()
    base = (os.environ.get("SILICONFLOW_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")
    if base.endswith("/embeddings"):
        base = base[: -len("/embeddings")].rstrip("/")
    return base


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        fx = float(x)
        fy = float(y)
        dot += fx * fy
        na += fx * fx
        nb += fy * fy
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


class MockEmbedder:
    """Deterministic hash-based pseudo-embeddings for offline tests (dim 1024)."""

    def __init__(self, dim: int = DEFAULT_DIM) -> None:
        self.dim = dim

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).digest()
            raw = h
            while len(raw) < self.dim * 4:
                raw += hashlib.sha256(raw).digest()
            vec = []
            for i in range(self.dim):
                b = raw[i % len(raw)]
                vec.append((b / 255.0) * 2.0 - 1.0)
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


def embed_texts(
    texts: Sequence[str],
    *,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float = 60.0,
    allow_mock: bool = False,
) -> list[list[float]]:
    """Return embedding vectors. If allow_mock and no key/HTTP fail → MockEmbedder."""
    texts = list(texts)
    if not texts:
        return []
    key = api_key if api_key is not None else get_api_key()
    if not key:
        if allow_mock:
            return MockEmbedder().embed_texts(texts)
        raise RuntimeError("SILICONFLOW_API_KEY not set")

    base = (base_url or get_base_url()).rstrip("/")
    url = f"{base}/embeddings"
    try:
        import httpx
    except ImportError as e:
        if allow_mock:
            return MockEmbedder().embed_texts(texts)
        raise RuntimeError("httpx required for embeddings") from e

    out: list[list[float]] = []
    batch_size = 16
    try:
        with httpx.Client(timeout=timeout) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                resp = client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": model, "input": batch, "encoding_format": "float"},
                )
                if resp.status_code >= 400:
                    raise RuntimeError(
                        f"embedding HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                data = resp.json()
                items = sorted(data.get("data") or [], key=lambda x: x.get("index", 0))
                for it in items:
                    emb = it.get("embedding")
                    if not isinstance(emb, list):
                        raise RuntimeError("malformed embedding response")
                    out.append([float(x) for x in emb])
        if len(out) != len(texts):
            raise RuntimeError(f"expected {len(texts)} embeddings, got {len(out)}")
        return out
    except Exception:
        if allow_mock:
            return MockEmbedder().embed_texts(texts)
        raise


def embed_query(text: str, **kwargs) -> list[float]:
    return embed_texts([text], **kwargs)[0]


def embed_probe(text: str = "OR-Tools VRP capacity") -> dict:
    """Smoke helper returning metadata (for t2_gate_cloud)."""
    if get_api_key():
        vecs = embed_texts([text], allow_mock=False)
        mock = False
    else:
        vecs = embed_texts([text], allow_mock=True)
        mock = True
    return {
        "ok": bool(vecs),
        "dim": len(vecs[0]) if vecs else 0,
        "n": len(vecs),
        "model": DEFAULT_MODEL,
        "mock": mock,
    }
