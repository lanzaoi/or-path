"""MinerU Cloud client + offline PDF/md → corpus papers path (v2/v3).

Cloud: MINERU_API_TOKEN; file-urls/batch → upload → poll (with retry).
Product path:
  knowledge/inbox_pdf/*.pdf
    → knowledge/mineru_out/<doc_id>/content.md
    → knowledge/corpus/papers/_from_mineru/<doc_id>.md
    → notes/mineru-last.json manifest

Offline: text extract (pypdf/pymupdf) or --offline-fixture.
Never print full tokens.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
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


def _safe_stem(name: str) -> str:
    s = Path(name).stem
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE).strip("_")
    return (s or "doc")[:80]


def _httpx():
    try:
        import httpx
    except ImportError as e:
        raise RuntimeError("httpx required for MinerU cloud") from e
    return httpx


def extract_text_from_pdf(pdf_path: Path) -> tuple[str | None, str]:
    """Best-effort local PDF text. Returns (text_or_none, backend)."""
    pdf_path = Path(pdf_path)
    for ext in (".md", ".txt"):
        side = pdf_path.with_suffix(ext)
        if side.is_file():
            return side.read_text(encoding="utf-8", errors="replace"), f"sidecar{ext}"

    try:
        import pymupdf  # type: ignore

        doc = pymupdf.open(pdf_path)
        parts = [page.get_text() for page in doc]
        doc.close()
        text = "\n".join(parts).strip()
        if text:
            return text, "pymupdf"
    except Exception:
        pass

    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(pdf_path))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        text = "\n".join(parts).strip()
        if text:
            return text, "pypdf"
    except Exception:
        pass

    return None, "none"


def write_minimal_pdf(path: Path, title: str = "OR-Path MinerU fixture") -> Path:
    """Write a tiny valid PDF (text as stream) for offline gates — no deps."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"BT /F1 12 Tf 72 720 Td ({title}) Tj ET"
    stream = content.encode("latin-1", errors="replace")
    objects = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
    )
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    path.write_bytes(bytes(out))
    return path


def write_or_sample_fixture_pdf(path: Path) -> Path:
    """Slightly richer text-layer PDF for cloud+local gates (public OR notes, not contest)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Multi-line text via simple Tj - keep ASCII for latin-1 stream
    lines = [
        "OR-Path sample lecture note",
        "Shortest path Dijkstra networkx",
        "TSP Routing CP-SAT circuit",
        "CVRP capacity multi vehicle",
        "Polyomino cover CP-SAT",
        "Objective only from solve validate",
        "Not a contest paper PDF",
    ]
    # Build content stream with multiple Td lines
    parts = ["BT /F1 11 Tf 50 750 Td"]
    for i, line in enumerate(lines):
        safe = re.sub(r"[()\\]", " ", line)[:80]
        if i == 0:
            parts.append(f"({safe}) Tj")
        else:
            parts.append(f"0 -16 Td ({safe}) Tj")
    parts.append("ET")
    content = " ".join(parts)
    stream = content.encode("latin-1", errors="replace")
    objects = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
    )
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    path.write_bytes(bytes(out))
    return path


def _dig(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _extract_md_from_zip_bytes(data: bytes) -> str | None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return None
    # prefer full.md / *.md
    names = zf.namelist()
    preferred = [n for n in names if n.lower().endswith("full.md")]
    preferred += [n for n in names if n.lower().endswith(".md")]
    for n in preferred:
        try:
            raw = zf.read(n)
            text = raw.decode("utf-8", errors="replace").strip()
            if text:
                return text
        except Exception:
            continue
    return None


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
        self.kdir = knowledge_dir(self.root)
        self.out_dir = self.kdir / "mineru_out"
        self.inbox_dir = self.kdir / "inbox_pdf"
        self.fixtures_dir = self.inbox_dir / "fixtures"
        self.corpus_papers = self.kdir / "corpus" / "papers"
        self.from_mineru = self.corpus_papers / "_from_mineru"
        self.manifest_path = self.root / "notes" / "mineru-last.json"
        self.manifest_alt = self.out_dir / "manifest.json"

    @property
    def available(self) -> bool:
        return bool(self.token)

    def _headers(self, *, json_body: bool = True) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("MINERU_API_TOKEN not set")
        h = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        json_body: dict | None = None,
        retries: int = 3,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        httpx = _httpx()
        last_err = "unknown"
        for attempt in range(max(1, retries)):
            try:
                with httpx.Client(timeout=timeout) as client:
                    r = client.request(
                        method,
                        url,
                        headers=self._headers(json_body=json_body is not None),
                        json=json_body,
                    )
                if r.status_code in {429, 502, 503, 504}:
                    last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if r.status_code >= 400:
                    return {
                        "status": "ERROR",
                        "http_status": r.status_code,
                        "reason": r.text[:400],
                        "url": url,
                    }
                try:
                    body = r.json()
                except Exception:
                    return {
                        "status": "ERROR",
                        "reason": f"non_json:{r.text[:200]}",
                        "http_status": r.status_code,
                        "url": url,
                    }
                return {"status": "OK", "raw": body, "http_status": r.status_code, "url": url}
            except Exception as e:
                last_err = str(e)
                time.sleep(1.0 * (attempt + 1))
        return {"status": "ERROR", "reason": last_err, "url": url}

    def submit_file(self, pdf_path: Path, *, data_id: str | None = None) -> dict[str, Any]:
        """Submit local PDF for cloud parse (batch URL flow preferred)."""
        if not self.token:
            return {"status": "SKIP", "reason": "MINERU_API_TOKEN not set"}
        pdf_path = Path(pdf_path)
        if not pdf_path.is_file():
            raise FileNotFoundError(pdf_path)

        doc_id = data_id or _safe_stem(pdf_path.name)
        # Preferred: file-urls/batch
        req = self._request_json(
            "POST",
            f"{self.base_url}/file-urls/batch",
            json_body={
                "files": [{"name": pdf_path.name, "data_id": doc_id}],
                "model_version": os.environ.get("MINERU_MODEL_VERSION") or "vlm",
                "enable_formula": True,
                "enable_table": True,
            },
            retries=3,
        )
        if req.get("status") == "OK":
            raw = req.get("raw") or {}
            data = raw.get("data") if isinstance(raw, dict) else None
            return {
                "status": "SUBMITTED",
                "raw": raw,
                "doc_id": doc_id,
                "endpoint": "file-urls/batch",
                "batch_id": (data or {}).get("batch_id") if isinstance(data, dict) else None,
                "file_urls": (data or {}).get("file_urls") if isinstance(data, dict) else None,
            }

        # Fallback multipart extract/task
        httpx = _httpx()
        last_err = req.get("reason")
        try:
            with httpx.Client(timeout=120.0) as client:
                with pdf_path.open("rb") as f:
                    r = client.post(
                        f"{self.base_url}/extract/task",
                        headers={"Authorization": f"Bearer {self.token}"},
                        files={"file": (pdf_path.name, f, "application/pdf")},
                        data={"data_id": doc_id},
                    )
                if r.status_code < 400:
                    body = r.json() if "json" in r.headers.get("content-type", "") else {"text": r.text[:500]}
                    return {
                        "status": "SUBMITTED",
                        "raw": body,
                        "doc_id": doc_id,
                        "endpoint": "extract/task",
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

    def upload_to_presigned(self, upload_url: str, pdf_path: Path) -> dict[str, Any]:
        httpx = _httpx()
        try:
            data = Path(pdf_path).read_bytes()
            # Presigned OSS URLs are signature-sensitive: do NOT send Authorization
            # or a mismatched Content-Type (often must be absent or octet-stream).
            last_err = "unknown"
            with httpx.Client(timeout=180.0) as client:
                for headers in (
                    None,
                    {"Content-Type": "application/octet-stream"},
                    {"Content-Type": "application/pdf"},
                ):
                    try:
                        r = client.put(upload_url, content=data, headers=headers)
                    except Exception as e:
                        last_err = str(e)
                        continue
                    if r.status_code < 400:
                        return {
                            "status": "OK",
                            "http_status": r.status_code,
                            "headers_mode": "none" if headers is None else headers.get("Content-Type"),
                        }
                    last_err = f"HTTP {r.status_code}: {r.text[:200]}"
            return {"status": "ERROR", "reason": last_err}
        except Exception as e:
            return {"status": "ERROR", "reason": str(e)}

    def poll_task(
        self,
        task_id: str,
        *,
        timeout_s: float = 300.0,
        interval_s: float = 5.0,
    ) -> dict[str, Any]:
        if not self.token:
            return {"status": "SKIP", "reason": "MINERU_API_TOKEN not set"}
        deadline = time.time() + timeout_s
        urls = [
            f"{self.base_url}/extract/task/{task_id}",
            f"{self.base_url}/tasks/{task_id}",
            f"{self.base_url}/extract-results/batch/{task_id}",
            f"{self.base_url}/extract/task/batch/{task_id}",
        ]
        last_body: Any = None
        while time.time() < deadline:
            for url in urls:
                res = self._request_json("GET", url, json_body=None, retries=1, timeout=60.0)
                if res.get("status") != "OK":
                    continue
                body = res.get("raw") or {}
                last_body = body
                data = body.get("data") if isinstance(body, dict) else None
                state = ""
                if isinstance(data, dict):
                    state = str(data.get("state") or data.get("status") or "")
                if not state and isinstance(body, dict):
                    state = str(body.get("state") or body.get("status") or "")
                state = state.lower()
                # batch extract_result list
                if isinstance(data, dict) and data.get("extract_result"):
                    er = data["extract_result"]
                    if isinstance(er, list) and er:
                        st = str(er[0].get("state") or er[0].get("status") or "").lower()
                        if st in {"done", "success", "completed", "finished"}:
                            return {"status": "DONE", "raw": body, "task_id": task_id, "endpoint": url}
                        if st in {"failed", "error"}:
                            return {"status": "ERROR", "raw": body, "task_id": task_id}
                if state in {"done", "success", "completed", "finished"}:
                    return {"status": "DONE", "raw": body, "task_id": task_id, "endpoint": url}
                if state in {"failed", "error"}:
                    return {"status": "ERROR", "raw": body, "task_id": task_id}
            time.sleep(interval_s)
        return {"status": "TIMEOUT", "task_id": task_id, "raw": last_body}

    def _download_markdown_from_result(self, poll: dict[str, Any]) -> tuple[str | None, str, str | None]:
        """Try to obtain markdown from poll payload. Returns (md, how, zip_url)."""
        raw = poll.get("raw") or {}
        data = raw.get("data") if isinstance(raw, dict) else raw
        zip_url = None
        # Direct path: MinerU batch extract_result[].full_zip_url
        if isinstance(data, dict):
            er = data.get("extract_result")
            if isinstance(er, list):
                for item in er:
                    if not isinstance(item, dict):
                        continue
                    fu = item.get("full_zip_url") or item.get("zip_url")
                    if fu:
                        zip_url = str(fu)
                        break
                    md_inline = item.get("md") or item.get("markdown") or item.get("content")
                    if isinstance(md_inline, str) and len(md_inline.strip()) > 40:
                        return md_inline.strip(), "extract_result_inline", zip_url

        candidates: list[str] = []

        def walk(obj: Any, depth: int = 0) -> None:
            if depth > 6:
                return
            if isinstance(obj, dict):
                for k, v in obj.items():
                    lk = str(k).lower()
                    if lk in {"md", "markdown", "content", "full_md"} and isinstance(v, str) and len(v) > 40:
                        candidates.append(v)
                    if lk in {"full_zip_url", "zip_url", "url", "file_url", "md_url"} and isinstance(v, str):
                        if v.startswith("http"):
                            candidates.append("URL:" + v)
                    walk(v, depth + 1)
            elif isinstance(obj, list):
                for it in obj[:20]:
                    walk(it, depth + 1)

        walk(data)
        for c in candidates:
            if not c.startswith("URL:") and len(c.strip()) > 40:
                return c.strip(), "inline_md", zip_url

        urls = []
        if zip_url:
            urls.append(zip_url)
        for c in candidates:
            if c.startswith("URL:"):
                urls.append(c[4:])

        httpx = _httpx()
        last_err = None
        for url in urls:
            for attempt in range(3):
                try:
                    with httpx.Client(timeout=180.0, follow_redirects=True) as client:
                        r = client.get(url)
                    if r.status_code >= 400:
                        last_err = f"HTTP {r.status_code}"
                        time.sleep(1.0 * (attempt + 1))
                        continue
                    ct = r.headers.get("content-type", "")
                    if "zip" in ct or url.lower().endswith(".zip") or r.content[:2] == b"PK":
                        md = _extract_md_from_zip_bytes(r.content)
                        if md:
                            return md, "zip_md", url
                        last_err = "zip_no_md"
                    else:
                        text = r.text.strip()
                        if text and ("#" in text[:200] or len(text) > 80):
                            return text, "url_text", url
                        last_err = "empty_body"
                except Exception as e:
                    last_err = str(e)
                    time.sleep(1.0 * (attempt + 1))
        return None, f"none:{last_err or 'no_url'}", zip_url

    def cloud_extract_pdf(
        self,
        pdf_path: Path,
        *,
        timeout_s: float | None = None,
        data_id: str | None = None,
    ) -> dict[str, Any]:
        """Full cloud path: submit → upload → poll → markdown (best-effort hardened)."""
        if not self.token:
            return {"status": "SKIP", "reason": "MINERU_API_TOKEN not set", "backend": "cloud"}
        pdf_path = Path(pdf_path)
        doc_id = data_id or _safe_stem(pdf_path.name)
        timeout_s = float(timeout_s or os.environ.get("MINERU_POLL_TIMEOUT_S") or 300)

        sub = self.submit_file(pdf_path, data_id=doc_id)
        if sub.get("status") != "SUBMITTED":
            return {
                "status": sub.get("status") or "ERROR",
                "reason": sub.get("reason"),
                "backend": "cloud",
                "submit": sub,
                "doc_id": doc_id,
                "token_masked": mask_token(self.token),
            }

        upload_info = None
        urls = sub.get("file_urls") or []
        if isinstance(urls, list) and urls:
            upload_url = urls[0] if isinstance(urls[0], str) else (urls[0] or {}).get("url")
            if upload_url:
                upload_info = self.upload_to_presigned(str(upload_url), pdf_path)
                if upload_info.get("status") != "OK":
                    return {
                        "status": "ERROR",
                        "reason": f"upload_failed:{upload_info.get('reason')}",
                        "backend": "cloud",
                        "submit": {k: v for k, v in sub.items() if k != "raw"},
                        "upload": upload_info,
                        "doc_id": doc_id,
                        "token_masked": mask_token(self.token),
                    }

        raw = sub.get("raw") or {}
        data = raw.get("data") if isinstance(raw, dict) else {}
        task_id = (
            sub.get("batch_id")
            or (data or {}).get("batch_id")
            or (data or {}).get("task_id")
            or raw.get("task_id")
            or raw.get("id")
        )
        poll = None
        if task_id:
            poll = self.poll_task(str(task_id), timeout_s=timeout_s, interval_s=5.0)
        else:
            poll = {"status": "ERROR", "reason": "no_task_or_batch_id", "raw": raw}

        md = None
        how = "none"
        zip_url = None
        if poll.get("status") == "DONE":
            md, how, zip_url = self._download_markdown_from_result(poll)

        # sanitize raw for return (no token)
        safe_sub = {
            "status": sub.get("status"),
            "endpoint": sub.get("endpoint"),
            "doc_id": doc_id,
            "batch_id": sub.get("batch_id") or task_id,
            "http_hint": _dig(raw, "code") or _dig(raw, "msg") or _dig(raw, "message"),
        }
        if md:
            return {
                "status": "OK",
                "backend": "cloud",
                "extract_backend": f"mineru_cloud:{how}",
                "markdown": md,
                "doc_id": doc_id,
                "cloud_job_id": str(task_id) if task_id else None,
                "full_zip_url": zip_url,
                "submit": safe_sub,
                "upload": upload_info,
                "poll_status": poll.get("status"),
                "token_masked": mask_token(self.token),
            }
        # Pipeline reached DONE but zip/md download failed (e.g. CDN SSL) —
        # still surface job id + zip url for evidence; caller may fall back offline.
        return {
            "status": "PARTIAL" if poll.get("status") == "DONE" else ("ERROR" if poll.get("status") != "TIMEOUT" else "TIMEOUT"),
            "reason": how if how.startswith("none") else f"cloud_done_but_no_md poll={poll.get('status')} how={how}",
            "backend": "cloud",
            "doc_id": doc_id,
            "cloud_job_id": str(task_id) if task_id else None,
            "full_zip_url": zip_url,
            "submit": safe_sub,
            "upload": upload_info,
            "poll_status": poll.get("status"),
            "token_masked": mask_token(self.token),
        }

    def save_result(self, doc_id: str, markdown: str, meta: dict | None = None) -> Path:
        out = self.out_dir / doc_id
        out.mkdir(parents=True, exist_ok=True)
        md_path = out / "content.md"
        md_path.write_text(markdown, encoding="utf-8")
        if meta:
            write_json(out / "meta.json", meta)
        return md_path

    def _corpus_md_path(self, doc_id: str) -> Path:
        self.from_mineru.mkdir(parents=True, exist_ok=True)
        return self.from_mineru / f"{doc_id}.md"

    def publish_to_corpus(
        self,
        doc_id: str,
        markdown: str,
        *,
        source_pdf: str,
        mode: str,
        extract_backend: str,
        cloud_job_id: str | None = None,
        title: str | None = None,
    ) -> Path:
        """Write Pi-ingestible md under corpus/papers/_from_mineru/."""
        title_line = title or doc_id
        header_bits = [
            f"# {title_line}",
            "",
            "- kind: paper-mineru",
            f"- source_pdf: {source_pdf}",
            f"- preprocess_mode: {mode}",
            f"- extract_backend: {extract_backend}",
        ]
        if cloud_job_id:
            header_bits.append(f"- cloud_job_id: {cloud_job_id}")
        header_bits += [
            "- note: RAG text for Pi retrieve; not numeric authority.",
            "",
            "---",
            "",
        ]
        header = "\n".join(header_bits)
        body = markdown if markdown.strip() else "(empty extract)\n"
        if body.lstrip().startswith("#") and "kind: paper-mineru" not in body[:900]:
            lines = body.splitlines()
            insert_at = 1 if lines and lines[0].startswith("#") else 0
            meta_block = [
                "",
                "- kind: paper-mineru",
                f"- source_pdf: {source_pdf}",
                f"- preprocess_mode: {mode}",
                f"- extract_backend: {extract_backend}",
            ]
            if cloud_job_id:
                meta_block.append(f"- cloud_job_id: {cloud_job_id}")
            meta_block.append("")
            lines[insert_at:insert_at] = meta_block
            text = "\n".join(lines)
            if not text.endswith("\n"):
                text += "\n"
        elif "kind: paper-mineru" in body[:900]:
            text = body if body.endswith("\n") else body + "\n"
        else:
            text = header + body
            if not text.endswith("\n"):
                text += "\n"
        dest = self._corpus_md_path(doc_id)
        dest.write_text(text, encoding="utf-8")
        return dest

    def process_pdf(
        self,
        pdf_path: Path,
        *,
        offline_fixture: bool = False,
        prefer_cloud: bool = True,
        cloud_required: bool = False,
        cloud_timeout_s: float | None = None,
    ) -> dict[str, Any]:
        """PDF → mineru_out + corpus/papers/_from_mineru md."""
        pdf_path = Path(pdf_path)
        if not pdf_path.is_file():
            return {
                "status": "ERROR",
                "reason": f"not_found:{pdf_path}",
                "source_pdf": str(pdf_path),
            }
        doc_id = _safe_stem(pdf_path.name)
        source_rel = str(pdf_path)
        try:
            source_rel = str(pdf_path.resolve().relative_to(self.root.resolve())).replace(
                "\\", "/"
            )
        except ValueError:
            source_rel = str(pdf_path).replace("\\", "/")

        mode = "offline"
        extract_backend = "none"
        markdown = ""
        cloud_info: dict[str, Any] | None = None
        cloud_job_id = None

        # Cloud path: full extract when preferred and token present
        if prefer_cloud and self.token and not offline_fixture:
            cloud_info = self.cloud_extract_pdf(
                pdf_path, timeout_s=cloud_timeout_s, data_id=doc_id
            )
            if cloud_info.get("status") == "OK" and cloud_info.get("markdown"):
                markdown = str(cloud_info["markdown"])
                extract_backend = str(cloud_info.get("extract_backend") or "mineru_cloud")
                mode = "cloud"
                cloud_job_id = cloud_info.get("cloud_job_id")
            elif cloud_required:
                return {
                    "status": cloud_info.get("status") or "ERROR",
                    "reason": cloud_info.get("reason") or "cloud_required_failed",
                    "source_pdf": source_rel,
                    "doc_id": doc_id,
                    "cloud": {k: v for k, v in (cloud_info or {}).items() if k != "markdown"},
                    "token_masked": mask_token(self.token),
                }

        if not markdown:
            text, backend = extract_text_from_pdf(pdf_path)
            if text:
                markdown = text
                extract_backend = backend
                mode = "offline_extract"
            elif offline_fixture:
                markdown = (
                    f"# Offline fixture extract: {doc_id}\n\n"
                    f"This markdown was produced by OR-Path offline fixture "
                    f"(no MinerU cloud / no PDF text layer).\n\n"
                    f"## Domain hints\n\n"
                    f"- shortest path Dijkstra networkx\n"
                    f"- operations research modeling checklist\n"
                    f"- objective only from solve validate\n\n"
                    f"## Source\n\n"
                    f"- pdf: `{source_rel}`\n"
                )
                extract_backend = "offline_fixture"
                mode = "offline_fixture"
            else:
                return {
                    "status": "ERROR",
                    "reason": "no_text_extract; retry with --offline-fixture or install pypdf/pymupdf or provide sidecar .md or cloud",
                    "source_pdf": source_rel,
                    "doc_id": doc_id,
                    "cloud": {k: v for k, v in (cloud_info or {}).items() if k != "markdown"}
                    if cloud_info
                    else None,
                    "token_masked": mask_token(self.token),
                }

        # strip heavy cloud markdown from result meta
        cloud_meta = None
        if cloud_info:
            cloud_meta = {k: v for k, v in cloud_info.items() if k != "markdown"}

        out_md = self.save_result(
            doc_id,
            markdown,
            meta={
                "source_pdf": source_rel,
                "mode": mode,
                "extract_backend": extract_backend,
                "cloud_job_id": cloud_job_id,
                "cloud": cloud_meta,
            },
        )
        corpus_md = self.publish_to_corpus(
            doc_id,
            markdown,
            source_pdf=source_rel,
            mode=mode,
            extract_backend=extract_backend,
            cloud_job_id=str(cloud_job_id) if cloud_job_id else None,
        )
        try:
            corpus_rel = str(corpus_md.resolve().relative_to(self.root.resolve())).replace(
                "\\", "/"
            )
            out_rel = str(out_md.resolve().relative_to(self.root.resolve())).replace("\\", "/")
        except ValueError:
            corpus_rel = str(corpus_md).replace("\\", "/")
            out_rel = str(out_md).replace("\\", "/")

        return {
            "status": "OK",
            "doc_id": doc_id,
            "source_pdf": source_rel,
            "mode": mode,
            "extract_backend": extract_backend,
            "backend": "cloud" if mode == "cloud" else "offline",
            "cloud_job_id": cloud_job_id,
            "out_md": out_rel,
            "corpus_md": corpus_rel,
            "cloud": cloud_meta,
            "token_masked": mask_token(self.token),
            "n_chars": len(markdown),
        }

    def process_inbox(
        self,
        *,
        offline_fixture: bool = False,
        prefer_cloud: bool = True,
        cloud_required: bool = False,
        include_fixtures: bool = True,
    ) -> dict[str, Any]:
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        seen: set[str] = set()
        pdfs: list[Path] = []
        # Top-level + recursive subdirs (e.g. inbox_pdf/or_fulltext/*.pdf)
        patterns = [
            self.inbox_dir.glob("*.pdf"),
            self.inbox_dir.glob("*.PDF"),
            self.inbox_dir.rglob("*.pdf"),
            self.inbox_dir.rglob("*.PDF"),
        ]
        if include_fixtures and self.fixtures_dir.is_dir():
            patterns += [self.fixtures_dir.glob("*.pdf"), self.fixtures_dir.glob("*.PDF")]
        for it in patterns:
            for p in sorted(it):
                if not p.is_file():
                    continue
                key = str(p.resolve()).lower()
                if key in seen:
                    continue
                seen.add(key)
                pdfs.append(p)
        results = []
        for pdf in pdfs:
            results.append(
                self.process_pdf(
                    pdf,
                    offline_fixture=offline_fixture,
                    prefer_cloud=prefer_cloud,
                    cloud_required=cloud_required,
                )
            )
        ok_n = sum(1 for r in results if r.get("status") == "OK")
        cloud_ok = sum(1 for r in results if r.get("mode") == "cloud")
        return {
            "status": "OK" if ok_n else ("EMPTY" if not pdfs else "ERROR"),
            "inbox": str(self.inbox_dir),
            "n_pdf": len(pdfs),
            "n_ok": ok_n,
            "n_cloud_ok": cloud_ok,
            "results": results,
            "token_masked": mask_token(self.token),
            "has_token": bool(self.token),
        }

    def ensure_offline_fixture_pdf(self) -> Path:
        """Create inbox fixture PDF + sidecar md for reliable gates."""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        pdf = self.inbox_dir / "fixture_or_mineru_phase1.pdf"
        side = self.inbox_dir / "fixture_or_mineru_phase1.md"
        write_minimal_pdf(pdf, title="OR-Path MinerU Phase1 Fixture")
        side.write_text(
            "# OR-Path MinerU Phase1 fixture note\n\n"
            "- kind: paper-mineru\n"
            "- domain: shortest_path\n\n"
            "## Content\n\n"
            "Shortest path Dijkstra networkx solver notes for hybrid retrieve smoke.\n"
            "CP-SAT and CVRP capacity may appear in other papers.\n"
            "Numbers authority remains solve+validate only.\n",
            encoding="utf-8",
        )
        return pdf

    def ensure_sample_fixture_pdf(self) -> Path:
        """Real-ish sample PDF under fixtures/ (text layer; public OR notes, not contest)."""
        self.fixtures_dir.mkdir(parents=True, exist_ok=True)
        pdf = self.fixtures_dir / "or_sample_01.pdf"
        write_or_sample_fixture_pdf(pdf)
        # optional sidecar for offline certainty
        side = self.fixtures_dir / "or_sample_01.md"
        if not side.is_file():
            side.write_text(
                "# OR-Path sample lecture note\n\n"
                "- kind: paper-mineru\n"
                "- title: OR-Path sample lecture note\n"
                "- source: curated-fixture\n"
                "- domain: general_or\n\n"
                "## Topics\n\n"
                "- Shortest path Dijkstra networkx\n"
                "- TSP Routing CP-SAT circuit\n"
                "- CVRP capacity multi vehicle\n"
                "- Polyomino cover CP-SAT\n"
                "- Objective only from solve validate\n",
                encoding="utf-8",
            )
        return pdf

    def write_manifest(self, payload: dict[str, Any]) -> Path:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        doc = {
            "schema": "orpath.mineru_manifest.v1",
            "ts": datetime.now(timezone.utc).isoformat(),
            "token_masked": mask_token(self.token),
            "has_token": bool(self.token),
            **payload,
        }
        blob = json.dumps(doc, ensure_ascii=False, default=str)
        if self.token and self.token in blob:
            blob = blob.replace(self.token, mask_token(self.token))
            doc = json.loads(blob)
        write_json(self.manifest_path, doc)
        write_json(self.manifest_alt, doc)
        return self.manifest_path

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
        cdir = corpus_dir or (knowledge_dir(self.root) / "corpus")
        all_chunks: list[Chunk] = []
        files: list[str] = []
        if cdir.is_dir():
            for path in sorted(cdir.rglob("*.md")):
                if path.name.lower() in {"readme.md"}:
                    continue
                files.append(str(path))
                did = path.stem
                dest = self.save_result(
                    did,
                    path.read_text(encoding="utf-8"),
                    meta={"source": "offline_corpus", "path": str(path)},
                )
                all_chunks.extend(
                    self.chunks_from_markdown(dest, doc_id=did, mineru_job_id=None)
                )
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
        offline = self.offline_corpus_to_chunks()
        result: dict[str, Any] = {"offline": offline, "cloud": None}
        if not self.token:
            result["cloud"] = {"status": "SKIP", "reason": "MINERU_API_TOKEN not set"}
            return result
        sample = self.ensure_sample_fixture_pdf()
        result["cloud"] = self.cloud_extract_pdf(sample, timeout_s=60.0)
        if result["cloud"].get("markdown"):
            result["cloud"] = {k: v for k, v in result["cloud"].items() if k != "markdown"}
            result["cloud"]["markdown_chars"] = "redacted"
        return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="MinerU preprocess (cloud + offline → corpus)")
    p.add_argument("--offline", action="store_true", help="Legacy: corpus md→chunks jsonl")
    p.add_argument("--smoke", action="store_true", help="Run legacy smoke")
    p.add_argument("--pdf", type=Path, default=None, help="Process one PDF → corpus")
    p.add_argument("--inbox", action="store_true", help="Process knowledge/inbox_pdf/*.pdf")
    p.add_argument(
        "--offline-fixture",
        action="store_true",
        help="Allow fixture extract when PDF has no text layer; ensure fixture PDF if inbox empty",
    )
    p.add_argument(
        "--ensure-fixture",
        action="store_true",
        help="Write fixture PDF+sidecar into inbox_pdf",
    )
    p.add_argument(
        "--ensure-sample",
        action="store_true",
        help="Write fixtures/or_sample_01.pdf (+sidecar)",
    )
    p.add_argument(
        "--no-cloud",
        action="store_true",
        help="Do not attempt MinerU cloud",
    )
    p.add_argument(
        "--cloud",
        action="store_true",
        help="Prefer cloud; with token try full cloud extract (v3)",
    )
    p.add_argument(
        "--cloud-required",
        action="store_true",
        help="Fail if cloud extract does not yield markdown",
    )
    p.add_argument(
        "--preprocess",
        action="store_true",
        help="Inbox(+fixtures) process + write manifest (product entry)",
    )
    p.add_argument("--timeout", type=float, default=None, help="Cloud poll timeout seconds")
    args = p.parse_args(argv)
    client = MinerUClient()

    prefer_cloud = (args.cloud or not args.no_cloud) and not args.no_cloud
    if args.cloud:
        prefer_cloud = True
    if args.no_cloud:
        prefer_cloud = False

    if args.ensure_fixture:
        pdf = client.ensure_offline_fixture_pdf()
        out = {"status": "OK", "fixture_pdf": str(pdf)}
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 0

    if args.ensure_sample:
        pdf = client.ensure_sample_fixture_pdf()
        out = {"status": "OK", "sample_pdf": str(pdf)}
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 0

    if args.preprocess or args.inbox:
        if args.offline_fixture and not list(client.inbox_dir.glob("*.pdf")):
            client.ensure_offline_fixture_pdf()
        if args.cloud or args.preprocess:
            client.ensure_sample_fixture_pdf()
        out = client.process_inbox(
            offline_fixture=args.offline_fixture or (args.preprocess and not args.cloud_required),
            prefer_cloud=prefer_cloud,
            cloud_required=args.cloud_required,
        )
        man = client.write_manifest({"action": "preprocess_inbox", **out})
        out["manifest"] = str(man)
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        if out.get("status") == "ERROR":
            return 2
        if out.get("status") == "EMPTY" and not args.offline_fixture:
            print("warning: inbox empty — place PDFs in knowledge/inbox_pdf/", file=sys.stderr)
            return 1
        return 0

    if args.pdf:
        out = client.process_pdf(
            args.pdf,
            offline_fixture=args.offline_fixture,
            prefer_cloud=prefer_cloud,
            cloud_required=args.cloud_required,
            cloud_timeout_s=args.timeout,
        )
        man = client.write_manifest(
            {
                "action": "process_pdf",
                "status": out.get("status"),
                "backend": out.get("backend") or out.get("mode"),
                "extract_backend": out.get("extract_backend"),
                "cloud_job_id": out.get("cloud_job_id"),
                "n_pdf": 1,
                "n_ok": 1 if out.get("status") == "OK" else 0,
                "result": out,
            }
        )
        out["manifest"] = str(man)
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 0 if out.get("status") == "OK" else 2

    if args.offline:
        out = client.offline_corpus_to_chunks()
    elif args.smoke:
        out = client.smoke()
    else:
        out = client.smoke()
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    if isinstance(out, dict) and out.get("status") == "ERROR":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
