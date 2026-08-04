"""SiliconFlow OpenAI-compatible embeddings (BAAI/bge-m3, dim 1024)."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import Callable, Literal, Sequence

# Never print secrets.

DEFAULT_MODEL = "BAAI/bge-m3"
DEFAULT_DIM = 1024
DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
ROOT = Path(__file__).resolve().parents[1]

EmbedMode = Literal["live", "stub"]
EmbedFn = Callable[[Sequence[str]], list[list[float]]]


def load_env(root: Path | None = None) -> None:
    try:
        from dotenv import load_dotenv as _load
    except ImportError:
        return
    env_path = (root or ROOT) / ".env"
    if env_path.is_file():
        _load(env_path, override=False)


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


def resolve_knowledge_profile(requested: str | None = None) -> tuple[str, dict]:
    """Resolve ORPATH_KNOWLEDGE_PROFILE=demo|research → (profile, meta)."""
    load_env()
    raw = (
        requested
        if requested is not None
        else (os.environ.get("ORPATH_KNOWLEDGE_PROFILE") or "demo")
    )
    raw = str(raw).strip().lower() or "demo"
    if raw not in {"demo", "research"}:
        meta = {"requested": raw, "resolved": "demo", "unknown_profile": True}
        return "demo", meta
    return raw, {"requested": raw, "resolved": raw}


def resolve_embed_mode(
    requested: str | None = None,
    *,
    profile: str | None = None,
) -> tuple[EmbedMode, dict]:
    """Resolve ORPATH_KNOWLEDGE_EMBED=live|stub|auto → (mode, meta).

    auto: live if SILICONFLOW_API_KEY else stub.
    live without key: degrade to stub (meta.degraded=True).
    profile=research + embed unset/auto: prefer live (same as auto when key present).
    """
    load_env()
    prof, prof_meta = resolve_knowledge_profile(profile)
    raw_env = (os.environ.get("ORPATH_KNOWLEDGE_EMBED") or "").strip().lower()
    if requested is not None:
        raw = str(requested).strip().lower() or "auto"
    elif raw_env:
        raw = raw_env
    elif prof == "research":
        # research profile defaults to auto (→ live with key)
        raw = "auto"
    else:
        raw = "auto"
    raw = raw or "auto"
    has_key = bool(get_api_key())
    meta: dict = {
        "requested": raw,
        "has_api_key": has_key,
        "profile": prof,
        "profile_meta": prof_meta,
    }
    if raw == "stub":
        meta["resolved"] = "stub"
        return "stub", meta
    if raw == "live":
        if has_key:
            meta["resolved"] = "live"
            return "live", meta
        meta["resolved"] = "stub"
        meta["degraded"] = True
        meta["reason"] = "live_requested_but_SILICONFLOW_API_KEY_missing"
        return "stub", meta
    # auto (and research default)
    if has_key:
        meta["resolved"] = "live"
        if prof == "research":
            meta["research_prefer_live"] = True
        return "live", meta
    meta["resolved"] = "stub"
    if prof == "research":
        meta["research_prefer_live"] = True
        meta["degraded"] = True
        meta["reason"] = "research_profile_but_no_api_key"
    return "stub", meta


def make_embed_fn(mode: EmbedMode, *, allow_live_fallback_to_mock: bool = True) -> EmbedFn:
    """Return embed_fn for the resolved mode."""
    if mode == "stub":
        mock = MockEmbedder()

        def _stub(texts: Sequence[str]) -> list[list[float]]:
            return mock.embed_texts(texts)

        return _stub

    def _live(texts: Sequence[str]) -> list[list[float]]:
        try:
            return embed_texts(texts, allow_mock=False)
        except Exception:
            if allow_live_fallback_to_mock:
                return MockEmbedder().embed_texts(texts)
            raise

    return _live


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
    mode, meta = resolve_embed_mode()
    if mode == "live":
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
        "embed_mode": mode,
        "embed_meta": meta,
    }
