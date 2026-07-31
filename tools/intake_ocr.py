#!/usr/bin/env python3
"""Problem-surface OCR for OR-Path 1.1 intake (tools only — not an Agent).

Backends (specs/problem-intake.md §4.1 + openpi-boot plan):
  1. manual_stub — .md / .txt
  2. pdf_text    — PDF text layer via pypdf
  3. paddleocr   — images / scan PDFs via:
       a) ORPATH_PADDLEOCR_PYTHON (default: system Python311 paddleocr)
       b) paddleocr api CLI (cloud token PADDLEOCR_ACCESS_TOKEN)
       c) rapidocr-onnxruntime fallback (backend labeled rapidocr)

Writes:
  notes/<slug>-ocr.raw.md
  notes/<slug>-ocr.meta.json

Does NOT write problem-brief or intake.json (intake_parse / S3).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

TEXT_SUFFIXES = {".md", ".txt", ".text", ".markdown"}
PDF_SUFFIXES = {".pdf"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}

_PDF_TEXT_MIN_CHARS = 20
_OCR_MIN_CHARS = 4

# Default Windows install found on this machine (user ppocr / paddleocr 3.7)
_DEFAULT_PADDLE_PY = Path(
    os.environ.get(
        "ORPATH_PADDLEOCR_PYTHON",
        r"C:\Users\Lanzao\AppData\Local\Programs\Python\Python311\python.exe",
    )
)


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
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"page {i} extract failed: {exc}")
            t = ""
        parts.append(f"<!-- pdf page {i}/{n_pages} -->\n{t}".rstrip())
    text = "\n\n".join(parts).strip() + ("\n" if parts else "")
    plain = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
    if len(plain) < _PDF_TEXT_MIN_CHARS:
        raise RuntimeError(
            f"pdf_text: extracted only {len(plain)} chars (< {_PDF_TEXT_MIN_CHARS}); "
            "likely scan/image PDF — use paddleocr backend"
        )
    return text, n_pages, warnings


def _parse_paddle_predict_payload(data: Any) -> str:
    """Normalize paddleocr 3.x / legacy ocr() result to plain text."""
    lines: list[str] = []

    def from_rec_texts(obj: Any) -> None:
        if isinstance(obj, dict):
            for key in ("rec_texts", "texts", "text"):
                if key in obj and obj[key] is not None:
                    val = obj[key]
                    if isinstance(val, list):
                        for t in val:
                            if t is not None and str(t).strip():
                                lines.append(str(t).strip())
                    elif str(val).strip():
                        lines.append(str(val).strip())
            # nested json
            if "json" in obj and obj["json"] is not None:
                from_rec_texts(obj["json"])
            if "res" in obj:
                from_rec_texts(obj["res"])
        elif isinstance(obj, list):
            for item in obj:
                from_rec_texts(item)
        elif hasattr(obj, "json") and callable(getattr(obj, "json", None)):
            try:
                from_rec_texts(obj.json)
            except Exception:  # noqa: BLE001
                pass
        elif hasattr(obj, "rec_texts"):
            from_rec_texts({"rec_texts": getattr(obj, "rec_texts")})

    from_rec_texts(data)

    # legacy: [[box, (text, score)], ...]
    if not lines and isinstance(data, list):
        for block in data:
            if not block:
                continue
            if isinstance(block, list):
                for row in block:
                    if isinstance(row, (list, tuple)) and len(row) >= 2:
                        t = row[1]
                        if isinstance(t, (list, tuple)) and t:
                            lines.append(str(t[0]))
                        elif isinstance(t, str):
                            lines.append(t)

    return "\n".join(lines).strip()


def _ocr_via_paddle_python(path: Path, py_exe: Path) -> tuple[str, list[str]]:
    """Run paddleocr in a separate interpreter (user's ppocr install)."""
    if not py_exe.is_file():
        raise RuntimeError(f"paddle python not found: {py_exe}")

    script = r"""
import json, sys
from pathlib import Path
img = Path(sys.argv[1])
from paddleocr import PaddleOCR
# Prefer Chinese models; fall back lang=en if needed
errs = []
text = ""
for lang in ("ch", "en"):
    try:
        ocr = PaddleOCR(lang=lang)
        if hasattr(ocr, "predict"):
            raw = list(ocr.predict(str(img)))
        else:
            raw = ocr.ocr(str(img))
        # serialize lightly
        payload = []
        for item in raw:
            if hasattr(item, "json") and callable(item.json):
                try:
                    payload.append(item.json)
                    continue
                except Exception:
                    pass
            if hasattr(item, "rec_texts"):
                payload.append({"rec_texts": list(item.rec_texts or [])})
                continue
            if isinstance(item, dict):
                payload.append(item)
                continue
            # legacy list structure
            payload.append(item)
        print(json.dumps({"ok": True, "lang": lang, "payload": payload}, ensure_ascii=False))
        raise SystemExit(0)
    except Exception as e:
        errs.append(f"{lang}:{e}")
print(json.dumps({"ok": False, "error": " | ".join(errs)}, ensure_ascii=False))
raise SystemExit(1)
"""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(script)
        script_path = tf.name
    try:
        proc = subprocess.run(
            [str(py_exe), script_path, str(path.resolve())],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(os.environ.get("ORPATH_OCR_TIMEOUT", "180")),
            env={**os.environ, "PYTHONNOUSERSITE": "1", "PYTHONPATH": ""},
        )
    finally:
        try:
            Path(script_path).unlink(missing_ok=True)
        except OSError:
            pass

    out = (proc.stdout or "").strip().splitlines()
    # last JSON line
    payload_line = ""
    for line in reversed(out):
        if line.strip().startswith("{"):
            payload_line = line.strip()
            break
    if not payload_line:
        raise RuntimeError(
            f"paddle python failed rc={proc.returncode}: "
            f"{(proc.stderr or proc.stdout or '')[-500:]}"
        )
    data = json.loads(payload_line)
    if not data.get("ok"):
        raise RuntimeError(f"paddle python: {data.get('error')}")
    text = _parse_paddle_predict_payload(data.get("payload"))
    if len(text) < _OCR_MIN_CHARS:
        raise RuntimeError(f"paddle python returned too little text ({len(text)} chars)")
    return text, [f"paddle_python lang={data.get('lang')} exe={py_exe}"]


def _ocr_via_paddle_api_cli(path: Path) -> tuple[str, list[str]]:
    """Cloud / service via `paddleocr api` CLI if token configured."""
    token = (os.environ.get("PADDLEOCR_ACCESS_TOKEN") or os.environ.get("ORPATH_PADDLEOCR_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("paddleocr api: no PADDLEOCR_ACCESS_TOKEN / ORPATH_PADDLEOCR_TOKEN")

    exe = shutil.which("paddleocr") or str(
        Path(os.environ.get("ORPATH_PADDLEOCR_CLI", "")) 
        if os.environ.get("ORPATH_PADDLEOCR_CLI")
        else Path(r"C:\Users\Lanzao\AppData\Local\Programs\Python\Python311\Scripts\paddleocr.exe")
    )
    if not Path(exe).is_file() and not shutil.which(str(exe)):
        raise RuntimeError(f"paddleocr CLI not found: {exe}")

    out_json = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        cmd = [
            exe,
            "api",
            "--model_type",
            "ocr",
            "--file_path",
            str(path.resolve()),
            "--token",
            token,
            "--output",
            str(out_json),
        ]
        base = (os.environ.get("ORPATH_PADDLEOCR_BASE_URL") or "").strip()
        if base:
            cmd.extend(["--base_url", base])
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(os.environ.get("ORPATH_OCR_TIMEOUT", "300")),
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"paddleocr api rc={proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}"
            )
        if not out_json.is_file():
            raise RuntimeError("paddleocr api produced no output file")
        data = json.loads(out_json.read_text(encoding="utf-8"))
        text = _parse_paddle_predict_payload(data)
        if len(text) < _OCR_MIN_CHARS:
            # try common cloud shapes
            text2 = json.dumps(data, ensure_ascii=False)
            # last resort extract quoted Chinese/ascii runs
            raise RuntimeError(f"paddleocr api little text; keys={list(data)[:12] if isinstance(data, dict) else type(data)}")
        return text, ["paddleocr_api_cli"]
    finally:
        try:
            out_json.unlink(missing_ok=True)
        except OSError:
            pass


def _ocr_via_rapidocr(path: Path) -> tuple[str, list[str]]:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise RuntimeError(
            "rapidocr fallback requires rapidocr-onnxruntime in product venv"
        ) from exc
    engine = RapidOCR()
    result, _elapse = engine(str(path.resolve()))
    if not result:
        raise RuntimeError("rapidocr returned empty")
    lines = []
    for row in result:
        # row: [box, text, score]
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            lines.append(str(row[1]))
    text = "\n".join(lines).strip()
    if len(text) < _OCR_MIN_CHARS:
        raise RuntimeError(f"rapidocr too little text ({len(text)} chars)")
    return text, ["rapidocr-onnxruntime fallback"]


def _pdf_pages_to_images(path: Path, tmp: Path) -> list[Path]:
    """Render PDF pages to PNG via pypdfium2 or pymupdf if available."""
    # try pypdfium2
    try:
        import pypdfium2 as pdfium  # type: ignore

        pdf = pdfium.PdfDocument(str(path))
        outs: list[Path] = []
        for i in range(len(pdf)):
            page = pdf[i]
            pil = page.render(scale=2).to_pil()
            out = tmp / f"page_{i+1:03d}.png"
            pil.save(out)
            outs.append(out)
        return outs
    except Exception:
        pass
    try:
        import fitz  # type: ignore

        doc = fitz.open(str(path))
        outs = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            out = tmp / f"page_{i+1:03d}.png"
            pix.save(str(out))
            outs.append(out)
        doc.close()
        return outs
    except Exception as exc:
        raise RuntimeError(
            f"cannot rasterize PDF for OCR (install pypdfium2 or pymupdf): {exc}"
        ) from exc


def extract_image_ocr(path: Path) -> tuple[str, int | None, list[str]]:
    """OCR one image: paddle python → paddle api → rapidocr."""
    errors: list[str] = []
    py = Path(os.environ.get("ORPATH_PADDLEOCR_PYTHON", str(_DEFAULT_PADDLE_PY)))
    # allow skip paddle with ORPATH_OCR_BACKEND=rapidocr only via force

    try:
        text, w = _ocr_via_paddle_python(path, py)
        return text + "\n", 1, w
    except Exception as e:  # noqa: BLE001
        errors.append(f"paddle_python: {e}")

    try:
        text, w = _ocr_via_paddle_api_cli(path)
        return text + "\n", 1, w
    except Exception as e:  # noqa: BLE001
        errors.append(f"paddle_api: {e}")

    try:
        text, w = _ocr_via_rapidocr(path)
        # label as rapidocr so meta is honest (not fake paddle success)
        return text + "\n", 1, w + [f"prior_errors={';'.join(errors)[:400]}"]
    except Exception as e:  # noqa: BLE001
        errors.append(f"rapidocr: {e}")

    raise RuntimeError("all OCR backends failed: " + " || ".join(errors))


def extract_paddleocr(path: Path) -> tuple[str, int | None, list[str]]:
    """Images or scan PDFs via ppocr stack (user install + fallbacks)."""
    suf = path.suffix.lower()
    warnings: list[str] = []
    if suf in IMAGE_SUFFIXES:
        text, pages, w = extract_image_ocr(path)
        # detect which backend actually ran from warnings tags
        return text, pages, w

    if suf in PDF_SUFFIXES:
        # Prefer text layer first when auto path calls us only for failed pdf_text
        with tempfile.TemporaryDirectory(prefix="orpath-ocr-") as td:
            tmp = Path(td)
            pages_img = _pdf_pages_to_images(path, tmp)
            parts: list[str] = []
            for i, img in enumerate(pages_img, 1):
                t, _, w = extract_image_ocr(img)
                warnings.extend(w)
                parts.append(f"<!-- ocr page {i}/{len(pages_img)} -->\n{t.rstrip()}")
            text = "\n\n".join(parts) + "\n"
            plain = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
            if len(plain) < _OCR_MIN_CHARS:
                raise RuntimeError("paddleocr PDF raster OCR produced too little text")
            return text, len(pages_img), warnings

    raise RuntimeError(f"paddleocr: unsupported file type {path.suffix}")


def extract_rapidocr_only(path: Path) -> tuple[str, int | None, list[str]]:
    """Force rapidocr path (tests / no paddle)."""
    if path.suffix.lower() in PDF_SUFFIXES:
        with tempfile.TemporaryDirectory(prefix="orpath-ocr-") as td:
            imgs = _pdf_pages_to_images(path, Path(td))
            parts = []
            warns: list[str] = []
            for i, img in enumerate(imgs, 1):
                t, w = _ocr_via_rapidocr(img)
                warns.extend(w)
                parts.append(f"<!-- ocr page {i}/{len(imgs)} -->\n{t}")
            return "\n\n".join(parts) + "\n", len(imgs), warns
    t, w = _ocr_via_rapidocr(path)
    return t + "\n", 1, w


def choose_backend(path: Path, forced: str | None = None) -> str:
    if forced:
        return forced
    env_b = (os.environ.get("ORPATH_OCR_BACKEND") or "").strip().lower()
    if env_b in {"manual_stub", "pdf_text", "paddleocr", "rapidocr", "paddleocr_mcp"}:
        # only honor env force for matching kinds lightly
        if env_b == "rapidocr":
            return "rapidocr"
        if env_b in {"paddleocr", "paddleocr_mcp"}:
            if path.suffix.lower() in IMAGE_SUFFIXES | PDF_SUFFIXES:
                return "paddleocr"
        if env_b == "pdf_text" and path.suffix.lower() in PDF_SUFFIXES:
            return "pdf_text"
        if env_b == "manual_stub" and path.suffix.lower() in TEXT_SUFFIXES:
            return "manual_stub"

    suf = path.suffix.lower()
    if suf in TEXT_SUFFIXES:
        return "manual_stub"
    if suf in PDF_SUFFIXES:
        return "pdf_text"
    if suf in IMAGE_SUFFIXES:
        return "paddleocr"
    return "manual_stub"


_EXTRACTORS: dict[str, Callable[[Path], tuple[str, int | None, list[str]]]] = {
    "manual_stub": extract_manual_stub,
    "pdf_text": extract_pdf_text,
    "paddleocr": extract_paddleocr,
    "paddleocr_mcp": extract_paddleocr,  # same stack; MCP is external to this tool
    "rapidocr": extract_rapidocr_only,
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
        "> Generated by tools/intake_ocr.py — faithful extract, not a problem brief.",
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
        # PDF: try text layer first; on failure fall through to paddleocr automatically
        tried: list[str] = []
        text = ""
        pages: int | None = None
        w: list[str] = []
        used_backend = backend
        rel = _rel_or_str(path, root_p)

        def _run(b: str) -> tuple[str, int | None, list[str]]:
            ext = _EXTRACTORS.get(b)
            if ext is None:
                raise RuntimeError(f"unknown backend {b!r}")
            return ext(path)

        try:
            if backend == "pdf_text":
                try:
                    text, pages, w = _run("pdf_text")
                    used_backend = "pdf_text"
                except Exception as e1:  # noqa: BLE001
                    tried.append(f"pdf_text:{e1}")
                    text, pages, w = _run("paddleocr")
                    used_backend = "paddleocr"
                    w = list(w) + tried
            else:
                text, pages, w = _run(backend)
                used_backend = backend
                # if paddle path actually used rapidocr fallback, relabel
                if used_backend == "paddleocr" and any(
                    "rapidocr" in x.lower() for x in w
                ) and not any(x.startswith("paddle_python lang=") for x in w):
                    if any("rapidocr-onnxruntime" in x for x in w):
                        used_backend = "rapidocr"
        except Exception as exc:  # noqa: BLE001
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
        backends_used.append(used_backend)
        plain_len = len(text.strip())
        sources.append(
            SourceResult(
                path=rel,
                kind=_kind_for(path),
                backend=used_backend,
                pages=pages,
                sha256=_sha256_file(path),
                char_count=plain_len,
                warning=None,
            )
        )
        chunks.append(
            f"\n## Source: `{rel}`\n\nbackend: `{used_backend}`\n\n{text.rstrip()}\n"
        )

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
                # fail-close: placeholder must not look like success
                be = str(s.get("backend") or "")
                if "placeholder" in be.lower():
                    errs.append(f"sources[{i}].backend must not be placeholder")
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
