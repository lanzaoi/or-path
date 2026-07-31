#!/usr/bin/env python3
"""Problem-surface OCR for OR-Path 1.1 intake (tools only — not an Agent).

Backends (specs/problem-intake.md §4.1):
  1. manual_stub — .md / .txt (or force)
  2. pdf_text    — PDF text layer via pypdf
  3. paddleocr*  — images / scan PDFs (optional; clear fail if unavailable)

Writes:
  notes/<slug>-ocr.raw.md
  notes/<slug>-ocr.meta.json

Does NOT write problem-brief or intake.json (that is intake_parse / S3).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

TEXT_SUFFIXES = {".md", ".txt", ".text", ".markdown"}
PDF_SUFFIXES = {".pdf"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}

# Minimum extracted chars to accept a PDF as "has text layer"
_PDF_TEXT_MIN_CHARS = 20


@dataclass
class SourceResult:
    path: str
    kind: str
    backend: str
    pages: int | None = None
    sha256: str | None = None
    char_count: int = 0
    warning: str | None = None


@dataclass
class OcrResult:
    slug: str
    backend: str
    sources: list[SourceResult] = field(default_factory=list)
    created_at: str = ""
    warnings: list[str] = field(default_factory=list)
    raw_path: str = ""
    meta_path: str = ""
    raw_text: str = ""
    status: str = "ok"  # ok | error

    def meta_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "backend": self.backend,
            "sources": [asdict(s) for s in self.sources],
            "created_at": self.created_at,
            "warnings": list(self.warnings),
            "raw_path": self.raw_path,
            "status": self.status,
        }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel_or_str(path: Path, root: Path | None) -> str:
    try:
        if root is not None:
            return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        pass
    return str(path).replace("\\", "/")


def extract_manual_stub(path: Path) -> tuple[str, int | None, list[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return text, 1, []


def extract_pdf_text(path: Path) -> tuple[str, int | None, list[str]]:
    """Extract text layer from PDF. Raises RuntimeError if unusable."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pdf_text backend requires pypdf (pip install pypdf)"
        ) from exc

    warnings: list[str] = []
    reader = PdfReader(str(path))
    parts: list[str] = []
    n_pages = len(reader.pages)
    for i, page in enumerate(reader.pages, start=1):
        try:
            t = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 — page-level soft fail
            warnings.append(f"page {i} extract failed: {exc}")
            t = ""
        parts.append(f"<!-- pdf page {i}/{n_pages} -->\n{t}".rstrip())
    text = "\n\n".join(parts).strip() + ("\n" if parts else "")
    # strip tags for emptiness check
    plain = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
    if len(plain) < _PDF_TEXT_MIN_CHARS:
        raise RuntimeError(
            f"pdf_text: extracted only {len(plain)} chars (< {_PDF_TEXT_MIN_CHARS}); "
            "likely scan/image PDF — use paddleocr backend later"
        )
    return text, n_pages, warnings


def extract_paddleocr_placeholder(path: Path) -> tuple[str, int | None, list[str]]:
    """S2: interface only — images not yet wired to live Paddle/MCP."""
    raise RuntimeError(
        f"paddleocr backend not configured in S2 for {path.name}; "
        "use manual_stub (.txt/.md) or pdf_text (text-layer PDF). "
        "Image/scan OCR lands when paddle adapter is enabled."
    )


def choose_backend(path: Path, forced: str | None = None) -> str:
    if forced:
        return forced
    suf = path.suffix.lower()
    if suf in TEXT_SUFFIXES:
        return "manual_stub"
    if suf in PDF_SUFFIXES:
        return "pdf_text"
    if suf in IMAGE_SUFFIXES:
        return "paddleocr"
    # unknown: try text read
    return "manual_stub"


_EXTRACTORS: dict[str, Callable[[Path], tuple[str, int | None, list[str]]]] = {
    "manual_stub": extract_manual_stub,
    "pdf_text": extract_pdf_text,
    "paddleocr": extract_paddleocr_placeholder,
    "paddleocr_mcp": extract_paddleocr_placeholder,
}


def run_ocr(
    *,
    slug: str,
    inputs: list[Path],
    root: Path | None = None,
    notes_dir: Path | None = None,
    force_backend: str | None = None,
) -> OcrResult:
    if not slug or not str(slug).strip():
        raise ValueError("slug required")
    if not inputs:
        raise ValueError("at least one --in file required")

    root_p = root.resolve() if root else None
    notes = notes_dir
    if notes is None:
        notes = (root_p / "notes") if root_p else Path("notes")
    notes.mkdir(parents=True, exist_ok=True)

    raw_path = notes / f"{slug}-ocr.raw.md"
    meta_path = notes / f"{slug}-ocr.meta.json"

    chunks: list[str] = []
    sources: list[SourceResult] = []
    warnings: list[str] = []
    backends_used: list[str] = []
    status = "ok"

    header = [
        f"# OCR raw — {slug}",
        "",
        f"> Generated by tools/intake_ocr.py — faithful extract, not a problem brief.",
        f"> created_at: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    chunks.append("\n".join(header))

    for raw_in in inputs:
        path = Path(raw_in)
        if not path.is_file():
            status = "error"
            warnings.append(f"missing file: {path}")
            continue

        backend = choose_backend(path, force_backend)
        extractor = _EXTRACTORS.get(backend)
        if extractor is None:
            status = "error"
            warnings.append(f"unknown backend {backend!r} for {path}")
            continue

        rel = _rel_or_str(path, root_p)
        try:
            text, pages, w = extractor(path)
        except Exception as exc:  # noqa: BLE001 — per-file error → overall error
            status = "error"
            msg = f"{backend} failed for {rel}: {exc}"
            warnings.append(msg)
            sources.append(
                SourceResult(
                    path=rel,
                    kind=_kind_for(path),
                    backend=backend,
                    pages=None,
                    sha256=_sha256_file(path),
                    char_count=0,
                    warning=str(exc),
                )
            )
            chunks.append(f"\n## Source: `{rel}`\n\n**ERROR ({backend}):** {exc}\n")
            continue

        warnings.extend(w)
        backends_used.append(backend)
        plain_len = len(text.strip())
        sources.append(
            SourceResult(
                path=rel,
                kind=_kind_for(path),
                backend=backend,
                pages=pages,
                sha256=_sha256_file(path),
                char_count=plain_len,
                warning=None,
            )
        )
        chunks.append(f"\n## Source: `{rel}`\n\nbackend: `{backend}`\n\n{text.rstrip()}\n")

    # primary backend label: single or mixed
    if not backends_used:
        primary = force_backend or "error"
        status = "error"
    elif len(set(backends_used)) == 1:
        primary = backends_used[0]
    else:
        primary = "mixed"

    raw_text = "\n".join(chunks).rstrip() + "\n"
    raw_path.write_text(raw_text, encoding="utf-8")

    result = OcrResult(
        slug=slug,
        backend=primary,
        sources=sources,
        created_at=datetime.now(timezone.utc).isoformat(),
        warnings=warnings,
        raw_path=_rel_or_str(raw_path, root_p),
        meta_path=_rel_or_str(meta_path, root_p),
        raw_text=raw_text,
        status=status,
    )
    meta_path.write_text(
        json.dumps(result.meta_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return result


def _kind_for(path: Path) -> str:
    suf = path.suffix.lower()
    if suf in TEXT_SUFFIXES:
        return "text"
    if suf in PDF_SUFFIXES:
        return "pdf"
    if suf in IMAGE_SUFFIXES:
        return "image"
    return "other"


def validate_ocr_meta(meta: dict[str, Any]) -> list[str]:
    """Light structural check for ocr.meta.json (S2)."""
    errs: list[str] = []
    for k in ("slug", "backend", "sources", "created_at", "raw_path"):
        if k not in meta:
            errs.append(f"missing meta field: {k}")
    if "sources" in meta:
        if not isinstance(meta["sources"], list) or not meta["sources"]:
            errs.append("sources must be non-empty array")
        else:
            for i, s in enumerate(meta["sources"]):
                if not isinstance(s, dict) or not str(s.get("path") or "").strip():
                    errs.append(f"sources[{i}].path required")
    if meta.get("status") not in (None, "ok", "error"):
        errs.append(f"bad status: {meta.get('status')!r}")
    return errs


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="OR-Path 1.1 intake OCR")
    p.add_argument("--slug", required=True, help="run slug")
    p.add_argument(
        "--in",
        dest="inputs",
        action="append",
        required=True,
        type=Path,
        help="input file (repeatable)",
    )
    p.add_argument(
        "--root",
        type=Path,
        default=None,
        help="repo/install root (paths in meta relative to this)",
    )
    p.add_argument(
        "--notes-dir",
        type=Path,
        default=None,
        help="override notes output directory",
    )
    p.add_argument(
        "--backend",
        default=None,
        choices=sorted(_EXTRACTORS.keys()),
        help="force backend for all inputs",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="print meta JSON to stdout",
    )
    args = p.parse_args(argv)

    try:
        result = run_ocr(
            slug=args.slug,
            inputs=list(args.inputs),
            root=args.root,
            notes_dir=args.notes_dir,
            force_backend=args.backend,
        )
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.meta_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"status={result.status} backend={result.backend}")
        print(f"raw={result.raw_path}")
        print(f"meta={result.meta_path}")
        if result.warnings:
            for w in result.warnings:
                print(f"warn: {w}", file=sys.stderr)

    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
