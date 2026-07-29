"""MinerU Cloud client + offline curated-md → chunks path.

Cloud: MINERU_API_TOKEN; submit/poll when API known.
Offline: convert knowledge/corpus/*.md to chunks without cloud.
Never print full tokens.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from knowledge_svc.chunk_schema import (
    Chunk,
    chunk_markdown,
    knowledge_dir,
    repo_root,
    write_chunks_jsonl,
    write_json,
)
from knowledge_svc.embed_siliconflow import load_dotenv


# Documented MinerU Cloud patterns (mineru.net). Endpoints may evolve;
# client is best-effort and skips cleanly without token.
DEFAULT_BASE = "https://mineru.net/api/v4"


def get_token() -> str | None:
    load_dotenv()
    t = (os.environ.get("MINERU_API_TOKEN") or "").strip()
    return t or None


def get_base_url() -> str:
    load_dotenv()
    return (os.environ.get("MINERU_BASE_URL") or DEFAULT_BASE).rstrip("/")


def mask_token(token: str | None) -> str:
    if not token:
        return ""
    if len(token) <= 8:
        return "***"
    return token[:4] + "..." + token[-4:]


class MinerUClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        base_url: str | None = None,
        root: Path | None = None,
    ) -> None:
        self.token = token if token is not None else get_token()
        self.base_url = (base_url or get_base_url()).rstrip("/")
        self.root = root or repo_root()
        self.out_dir = knowledge_dir(self.root) / "mineru_out"

    @property
    def available(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("MINERU_API_TOKEN not set")
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def submit_file(self, pdf_path: Path, *, data_id: str | None = None) -> dict[str, Any]:
        """Submit a local PDF. Tries common MinerU Cloud batch upload patterns."""
        if not self.token:
            return {"status": "SKIP", "reason": "MINERU_API_TOKEN not set"}
        pdf_path = Path(pdf_path)
        if not pdf_path.is_file():
            raise FileNotFoundError(pdf_path)

        try:
            import httpx
        except ImportError as e:
            raise RuntimeError("httpx required") from e

        doc_id = data_id or pdf_path.stem
        # Pattern A: create task then upload (mineru.net style varies)
        # We attempt create-task with file bytes multipart as fallback chain.
        url_candidates = [
            f"{self.base_url}/extract/task",
            f"{self.base_url}/tasks",
            f"{self.base_url}/file-urls/batch",
        ]
        last_err = None
        with httpx.Client(timeout=120.0) as client:
            # Try batch file URL request first (common Cloud flow)
            try:
                r = client.post(
                    f"{self.base_url}/file-urls/batch",
                    headers=self._headers(),
                    json={
                        "files": [{"name": pdf_path.name, "data_id": doc_id}],
                        "model_version": "vlm",
                    },
                )
                if r.status_code < 400:
                    body = r.json()
                    # expected: upload urls + batch_id
                    return {
                        "status": "SUBMITTED",
                        "raw": body,
                        "doc_id": doc_id,
                        "endpoint": "file-urls/batch",
                    }
                last_err = f"HTTP {r.status_code}: {r.text[:200]}"
            except Exception as e:
                last_err = str(e)

            # Multipart fallback
            for url in url_candidates[:2]:
                try:
                    with pdf_path.open("rb") as f:
                        r = client.post(
                            url,
                            headers={"Authorization": f"Bearer {self.token}"},
                            files={"file": (pdf_path.name, f, "application/pdf")},
                            data={"data_id": doc_id},
                        )
                    if r.status_code < 400:
                        return {
                            "status": "SUBMITTED",
                            "raw": r.json() if r.headers.get("content-type", "").startswith("application/json") else {"text": r.text[:500]},
                            "doc_id": doc_id,
                            "endpoint": url,
                        }
                    last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                except Exception as e:
                    last_err = str(e)
        return {
            "status": "ERROR",
            "reason": last_err or "unknown",
            "doc_id": doc_id,
            "token_masked": mask_token(self.token),
        }

    def poll_task(
        self,
        task_id: str,
        *,
        timeout_s: float = 300.0,
        interval_s: float = 5.0,
    ) -> dict[str, Any]:
        if not self.token:
            return {"status": "SKIP", "reason": "MINERU_API_TOKEN not set"}
        try:
            import httpx
        except ImportError as e:
            raise RuntimeError("httpx required") from e

        deadline = time.time() + timeout_s
        urls = [
            f"{self.base_url}/extract/task/{task_id}",
            f"{self.base_url}/tasks/{task_id}",
        ]
        with httpx.Client(timeout=60.0) as client:
            while time.time() < deadline:
                for url in urls:
                    try:
                        r = client.get(url, headers=self._headers())
                        if r.status_code >= 400:
                            continue
                        body = r.json()
                        state = str(
                            body.get("state")
                            or body.get("status")
                            or (body.get("data") or {}).get("state")
                            or ""
                        ).lower()
                        if state in {"done", "success", "completed", "finished"}:
                            return {"status": "DONE", "raw": body, "task_id": task_id}
                        if state in {"failed", "error"}:
                            return {"status": "ERROR", "raw": body, "task_id": task_id}
                    except Exception:
                        continue
                time.sleep(interval_s)
        return {"status": "TIMEOUT", "task_id": task_id}

    def save_result(self, doc_id: str, markdown: str, meta: dict | None = None) -> Path:
        out = self.out_dir / doc_id
        out.mkdir(parents=True, exist_ok=True)
        md_path = out / "content.md"
        md_path.write_text(markdown, encoding="utf-8")
        if meta:
            write_json(out / "meta.json", meta)
        return md_path

    def chunks_from_markdown(
        self,
        md_path: Path,
        *,
        doc_id: str | None = None,
        mineru_job_id: str | None = None,
    ) -> list[Chunk]:
        text = md_path.read_text(encoding="utf-8")
        did = doc_id or md_path.parent.name
        try:
            rel = str(md_path.resolve().relative_to(self.root.resolve()))
        except ValueError:
            rel = str(md_path)
        title = None
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        chunks = chunk_markdown(
            text,
            doc_id=did,
            source_path=rel.replace("\\", "/"),
            title=title,
        )
        if mineru_job_id:
            for c in chunks:
                c.mineru_job_id = mineru_job_id
        return chunks

    def offline_corpus_to_chunks(
        self,
        corpus_dir: Path | None = None,
        *,
        write_jsonl: bool = True,
    ) -> dict[str, Any]:
        """Convert curated md in knowledge/corpus/ to chunks (no cloud)."""
        cdir = corpus_dir or (knowledge_dir(self.root) / "corpus")
        all_chunks: list[Chunk] = []
        files: list[str] = []
        if cdir.is_dir():
            for path in sorted(cdir.rglob("*.md")):
                files.append(str(path))
                # also mirror into mineru_out as offline "processed"
                did = path.stem
                dest = self.save_result(
                    did,
                    path.read_text(encoding="utf-8"),
                    meta={"source": "offline_corpus", "path": str(path)},
                )
                all_chunks.extend(self.chunks_from_markdown(dest, doc_id=did, mineru_job_id=None))
        out_jsonl = knowledge_dir(self.root) / "chunks" / "mineru_offline_chunks.jsonl"
        if write_jsonl:
            write_chunks_jsonl(all_chunks, out_jsonl)
        return {
            "status": "OK",
            "mode": "offline",
            "n_files": len(files),
            "n_chunks": len(all_chunks),
            "files": files,
            "chunks_jsonl": str(out_jsonl),
            "chunk_ids": [c.chunk_id for c in all_chunks],
        }

    def smoke(self) -> dict[str, Any]:
        """Prefer offline corpus path; attempt cloud only if token+PDF present."""
        offline = self.offline_corpus_to_chunks()
        result: dict[str, Any] = {"offline": offline, "cloud": None}
        if not self.token:
            result["cloud"] = {"status": "SKIP", "reason": "MINERU_API_TOKEN not set"}
            return result
        # look for a PDF in corpus
        pdfs = list((knowledge_dir(self.root) / "corpus").glob("*.pdf")) if (
            knowledge_dir(self.root) / "corpus"
        ).is_dir() else []
        if not pdfs:
            result["cloud"] = {
                "status": "SKIP",
                "reason": "no PDF in knowledge/corpus (token present)",
                "token_masked": mask_token(self.token),
            }
            return result
        sub = self.submit_file(pdfs[0])
        result["cloud"] = sub
        # If we got a task id, try poll briefly
        raw = sub.get("raw") or {}
        task_id = (
            raw.get("task_id")
            or raw.get("id")
            or (raw.get("data") or {}).get("task_id")
            or (raw.get("data") or {}).get("batch_id")
        )
        if task_id and sub.get("status") == "SUBMITTED":
            result["cloud_poll"] = self.poll_task(str(task_id), timeout_s=30.0, interval_s=5.0)
        return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="MinerU client (cloud + offline)")
    p.add_argument("--offline", action="store_true", help="Only offline corpus→chunks")
    p.add_argument("--smoke", action="store_true", help="Run smoke")
    p.add_argument("--pdf", type=Path, default=None, help="Submit PDF to cloud")
    args = p.parse_args(argv)
    client = MinerUClient()
    if args.pdf:
        out = client.submit_file(args.pdf)
    elif args.offline:
        out = client.offline_corpus_to_chunks()
    else:
        out = client.smoke()
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    if isinstance(out, dict) and out.get("status") == "ERROR":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
