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


def find_local_bge_m3_dir() -> Path | None:
    load_env()
    env_dir = (os.environ.get("LOCAL_BGE_M3_PATH") or "").strip()
    candidates: list[Path] = []
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.extend([
        Path("/home/lanzao/antigravity/jolly-hawking/models/bge_m3_onnx"),
        ROOT / "models" / "bge_m3_onnx",
    ])
    for cand in candidates:
        if (cand / "model_quantized.onnx").is_file() and (cand / "tokenizer.json").is_file():
            return cand
    return None


class LocalBGEM3Embedder:
    """Zero-cloud local BGE-M3 1024d ONNX embedder."""
    _instance: "LocalBGEM3Embedder | None" = None

    def __init__(self, model_dir: Path | str) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.model_dir = Path(model_dir)
        self.model_path = self.model_dir / "model_quantized.onnx"
        self.tokenizer_path = self.model_dir / "tokenizer.json"
        self.dim = DEFAULT_DIM

        if not self.model_path.is_file() or not self.tokenizer_path.is_file():
            raise FileNotFoundError(f"Local BGE-M3 ONNX files not found in {self.model_dir}")

        providers = ["CPUExecutionProvider"]
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 4
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.sess = ort.InferenceSession(str(self.model_path), sess_options=opts, providers=providers)
        self.tokenizer = Tokenizer.from_file(str(self.tokenizer_path))
        self.tokenizer.enable_truncation(max_length=512)

    @classmethod
    def get_instance(cls, model_dir: Path | str | None = None) -> "LocalBGEM3Embedder":
        if cls._instance is None:
            d = model_dir or find_local_bge_m3_dir()
            if not d:
                raise FileNotFoundError("Local BGE-M3 model directory not found")
            cls._instance = cls(d)
        return cls._instance

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        import numpy as np

        batch_size = 16
        all_vecs: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            encoded_list = [self.tokenizer.encode(t[:1500] if len(t) > 1500 else t) for t in chunk]
            max_len = max(len(e.ids) for e in encoded_list) if encoded_list else 1
            input_ids = np.zeros((len(chunk), max_len), dtype=np.int64)
            attn_mask = np.zeros((len(chunk), max_len), dtype=np.int64)
            for row_idx, e in enumerate(encoded_list):
                l = len(e.ids)
                input_ids[row_idx, :l] = e.ids
                attn_mask[row_idx, :l] = e.attention_mask

            out = self.sess.run(["dense_vecs"], {"input_ids": input_ids, "attention_mask": attn_mask})[0]
            norms = np.linalg.norm(out, axis=-1, keepdims=True)
            norms[norms == 0] = 1e-12
            normalized = (out / norms).tolist()
            all_vecs.extend(normalized)
        return all_vecs


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
    local_dir = find_local_bge_m3_dir()
    has_local = bool(local_dir)
    has_live = has_key or has_local
    meta: dict = {
        "requested": raw,
        "has_api_key": has_key,
        "has_local_onnx": has_local,
        "profile": prof,
        "profile_meta": prof_meta,
    }
    if raw == "stub":
        meta["resolved"] = "stub"
        return "stub", meta
    if raw == "live":
        if has_live:
            meta["resolved"] = "live"
            meta["backend"] = "local_onnx" if (has_local and not has_key) else "cloud"
            return "live", meta
        meta["resolved"] = "stub"
        meta["degraded"] = True
        meta["reason"] = "live_requested_but_SILICONFLOW_API_KEY_missing"
        return "stub", meta
    # auto (and research default)
    if has_key:
        meta["resolved"] = "live"
        meta["backend"] = "cloud"
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
    """Deterministic feature-hashed pseudo-embeddings for offline tests (dim 1024)."""

    def __init__(self, dim: int = DEFAULT_DIM) -> None:
        self.dim = dim

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        import re as _re

        out: list[list[float]] = []
        dim = self.dim
        for t in texts:
            vec = [0.0] * dim
            tokens = _re.findall(r"[a-z0-9_]+", (t or "").lower())
            if tokens:
                for tok in set(tokens):
                    d = hashlib.md5(tok.encode("utf-8")).digest()
                    for j in range(0, 16, 2):
                        idx = ((d[j] << 8) | d[j + 1]) % dim
                        vec[idx] += 1.0 if (d[j] & 1) else -1.0
            else:
                d = hashlib.sha256((t or "").encode("utf-8")).digest()
                for i in range(min(dim, 32)):
                    vec[i] = (d[i] / 255.0) * 2.0 - 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([round(v / norm, 5) for v in vec])
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
    """Return embedding vectors. Prefers local ONNX if present, then cloud API, then MockEmbedder."""
    texts = list(texts)
    if not texts:
        return []

    # 1. Local BGE-M3 ONNX check (Zero-Cloud preference or fallback)
    local_dir = find_local_bge_m3_dir()
    prefer_local = os.environ.get("ORPATH_EMBED_LOCAL", "1") == "1"
    key = api_key if api_key is not None else get_api_key()
    if local_dir and (prefer_local or not key or api_key == "local"):
        try:
            return LocalBGEM3Embedder.get_instance(local_dir).embed_texts(texts)
        except Exception:
            if not key and not allow_mock:
                raise

    if not key:
        if allow_mock:
            return MockEmbedder().embed_texts(texts)
        raise RuntimeError("SILICONFLOW_API_KEY not set and no local embedding model found")

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
