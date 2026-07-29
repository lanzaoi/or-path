"""Cognee Cloud client — smoke write + search.

Laws:
- Never store authoritative objective / tour / routes.
- Solve path must not read Cognee for numeric truth.
Config: COGNEE_API_KEY, COGNEE_BASE_URL
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

from knowledge_svc.embed_siliconflow import load_dotenv

# Patterns that look like authoritative solution dumps (not mere discussion).
_FORBIDDEN_RE = re.compile(
    r"""(?ix)
    (?:\"|\')?objective(?:_value)?(?:\"|\')?\s*[:=]\s*-?\d
    |(?:\"|\')?optimal_(?:value|cost|objective)(?:\"|\')?\s*[:=]
    |\"tour\"\s*:\s*\[
    |\"routes\"\s*:\s*\[
    |\"path\"\s*:\s*\[
    |solution\.json
    """
)


def get_api_key() -> str | None:
    load_dotenv()
    k = (os.environ.get("COGNEE_API_KEY") or "").strip()
    return k or None


def get_base_url() -> str | None:
    load_dotenv()
    b = (os.environ.get("COGNEE_BASE_URL") or "").strip().rstrip("/")
    return b or None


def mask_secret(s: str | None) -> str:
    if not s:
        return ""
    if len(s) <= 8:
        return "***"
    return s[:4] + "..." + s[-4:]


def assert_safe_memory_text(text: str) -> None:
    """Reject texts that look like authoritative solution dumps."""
    if _FORBIDDEN_RE.search(text or ""):
        raise ValueError(
            "refusing to store text that looks like authoritative objective/solution"
        )


class CogneeClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        dataset: str = "orpath-lessons",
        use_env: bool = True,
    ) -> None:
        if use_env:
            self.api_key = api_key if api_key is not None else get_api_key()
            self.base_url = base_url if base_url is not None else get_base_url()
        else:
            self.api_key = api_key
            self.base_url = base_url
        self.dataset = dataset
        # Local smoke store when cloud unavailable (still exercises API shape)
        self._local: list[dict[str, Any]] = []

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.base_url)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("COGNEE_API_KEY not set")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def write_lesson(self, text: str, *, meta: dict | None = None) -> dict[str, Any]:
        """Write a lesson / preference. Never objectives."""
        assert_safe_memory_text(text)
        entry = {
            "id": str(uuid.uuid4()),
            "dataset": self.dataset,
            "text": text,
            "meta": meta or {"kind": "lesson"},
        }
        if not self.available:
            self._local.append(entry)
            return {
                "status": "LOCAL_OK",
                "reason": "COGNEE_API_KEY/BASE_URL missing; stored in-process only",
                "entry_id": entry["id"],
                "dataset": self.dataset,
            }

        try:
            import httpx
        except ImportError as e:
            raise RuntimeError("httpx required") from e

        # Best-effort REST shapes used by Cognee Cloud variants
        paths = [
            "/api/add",
            "/api/v1/add",
            "/api/datasets/data",
            "/add",
        ]
        last_err = None
        with httpx.Client(timeout=60.0) as client:
            for path in paths:
                url = f"{self.base_url}{path}"
                try:
                    r = client.post(
                        url,
                        headers=self._headers(),
                        json={
                            "dataset_name": self.dataset,
                            "data": text,
                            "text": text,
                            "metadata": entry["meta"],
                        },
                    )
                    if r.status_code < 400:
                        body: Any
                        try:
                            body = r.json()
                        except Exception:
                            body = {"text": r.text[:300]}
                        return {
                            "status": "OK",
                            "endpoint": path,
                            "entry_id": entry["id"],
                            "dataset": self.dataset,
                            "raw": body,
                            "key_masked": mask_secret(self.api_key),
                        }
                    last_err = f"{path} HTTP {r.status_code}: {r.text[:200]}"
                except Exception as e:
                    last_err = f"{path}: {e}"
        # Fall back to local so smoke still demonstrates write path
        self._local.append(entry)
        return {
            "status": "LOCAL_FALLBACK",
            "reason": last_err or "cloud write failed",
            "entry_id": entry["id"],
            "dataset": self.dataset,
            "key_masked": mask_secret(self.api_key),
        }

    def search(self, query: str, *, topk: int = 5) -> dict[str, Any]:
        q = (query or "").strip()
        if not self.available:
            hits = []
            q_tokens = [t for t in q.lower().split() if t]
            for e in self._local:
                tl = e["text"].lower()
                if not q_tokens or all(t in tl for t in q_tokens) or any(t in tl for t in q_tokens):
                    hits.append(
                        {
                            "id": e["id"],
                            "text": e["text"][:300],
                            "score": 1.0,
                            "backend": "cognee_local",
                        }
                    )
            return {
                "status": "LOCAL_OK",
                "hits": hits[:topk],
                "dataset": self.dataset,
            }

        try:
            import httpx
        except ImportError as e:
            raise RuntimeError("httpx required") from e

        paths = [
            "/api/search",
            "/api/v1/search",
            "/search",
        ]
        last_err = None
        with httpx.Client(timeout=60.0) as client:
            for path in paths:
                url = f"{self.base_url}{path}"
                try:
                    r = client.post(
                        url,
                        headers=self._headers(),
                        json={
                            "query": q,
                            "dataset_name": self.dataset,
                            "top_k": topk,
                        },
                    )
                    if r.status_code < 400:
                        try:
                            body = r.json()
                        except Exception:
                            body = {"text": r.text[:300]}
                        return {
                            "status": "OK",
                            "endpoint": path,
                            "raw": body,
                            "dataset": self.dataset,
                            "key_masked": mask_secret(self.api_key),
                        }
                    last_err = f"{path} HTTP {r.status_code}: {r.text[:200]}"
                except Exception as e:
                    last_err = f"{path}: {e}"

        # local fallback search
        hits = []
        q_tokens = [t for t in q.lower().split() if t]
        for e in self._local:
            tl = e["text"].lower()
            if not q_tokens or any(t in tl for t in q_tokens):
                hits.append(
                    {
                        "id": e["id"],
                        "text": e["text"][:300],
                        "score": 1.0,
                        "backend": "cognee_local",
                    }
                )
        return {
            "status": "LOCAL_FALLBACK",
            "reason": last_err,
            "hits": hits[:topk],
            "dataset": self.dataset,
            "key_masked": mask_secret(self.api_key),
        }

    def smoke(self) -> dict[str, Any]:
        lesson = (
            "OR-Path lesson: prefer multi-vehicle capacity VRP over single vehicle; "
            "never treat memory as source of optimal objective values; "
            "numbers truth is solve tools + validate only."
        )
        w = self.write_lesson(lesson, meta={"kind": "lesson", "topic": "vrp_capacity"})
        s = self.search("VRP capacity multi-vehicle", topk=3)
        return {
            "write": w,
            "search": s,
            "cloud_configured": self.available,
            "dataset": self.dataset,
        }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cognee Cloud smoke client")
    p.add_argument("--smoke", action="store_true", default=True)
    p.add_argument("--write", type=str, default=None, help="Write lesson text")
    p.add_argument("--search", type=str, default=None, help="Search query")
    args = p.parse_args(argv)
    client = CogneeClient()
    try:
        if args.write:
            out = client.write_lesson(args.write)
        elif args.search:
            out = client.search(args.search)
        else:
            out = client.smoke()
    except ValueError as e:
        print(json.dumps({"status": "REJECTED", "reason": str(e)}))
        return 2
    except Exception as e:
        print(f"cognee failed: {e}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
