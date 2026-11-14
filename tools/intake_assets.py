"""Unified structured asset & attachment extractor for OR-Path intake/studio.

Handles `.docx`, `.xlsx`, `.xlsm`, `.pdf`, `.csv`, `.tsv`, `.json`, `.md`, `.txt`
cleanly across Linux/Windows without ever falling back to raw ZIP binary reads.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = frozenset({".md", ".txt", ".text", ".markdown"})
DOCX_SUFFIXES = frozenset({".docx"})
PDF_SUFFIXES = frozenset({".pdf"})
SPREADSHEET_SUFFIXES = frozenset({".xlsx", ".xlsm"})
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"})
STATEMENT_SUFFIXES = TEXT_SUFFIXES | DOCX_SUFFIXES | PDF_SUFFIXES | IMAGE_SUFFIXES
READABLE_STATEMENT_SUFFIXES = TEXT_SUFFIXES | DOCX_SUFFIXES | PDF_SUFFIXES

DEFAULT_MAX_CHARS = 8000


def _validate_readable_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    if path.is_dir():
        raise IsADirectoryError(f"path is a directory, not a file: {path}")
    if not path.is_file():
        raise OSError(f"path is not a regular file: {path}")


def _truncate_text(text: str, max_chars: int | None) -> tuple[str, bool]:
    if max_chars is not None and max_chars > 0 and len(text) > max_chars:
        return text[:max_chars].rstrip() + f"\n\n... [truncated, total {len(text)} chars]", True
    return text, False


def _format_cell(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).replace("\r\n", " ").replace("\n", " ").strip()
    return s.replace("|", "\\|")


def extract_docx_text(
    path: Path,
    *,
    max_chars: int | None = DEFAULT_MAX_CHARS,
) -> tuple[str, int | None, list[str]]:
    """Extract paragraphs and Markdown tables from a `.docx` file."""
    _validate_readable_file(path)
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "docx extractor requires python-docx (pip install python-docx)"
        ) from exc

    warnings: list[str] = []
    try:
        doc = Document(str(path))
    except (PermissionError, IsADirectoryError):
        raise
    except Exception as exc:
        raise RuntimeError(f"failed to parse docx {path.name}: {exc}") from exc

    blocks: list[str] = []
    # Preserve document body order across paragraphs and tables when possible
    try:
        from docx.oxml.table import CT_Tbl
        from docx.oxml.text.paragraph import CT_P
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        body = doc.element.body
        for child in body.iterchildren():
            if isinstance(child, CT_P):
                p = Paragraph(child, doc)
                txt = (p.text or "").strip()
                if not txt:
                    continue
                style_name = str(getattr(getattr(p, "style", None), "name", "") or "").lower()
                if style_name.startswith("heading"):
                    digits = "".join(ch for ch in style_name if ch.isdigit())
                    lvl = min(max(int(digits) if digits else 2, 1), 6)
                    blocks.append(f"{'#' * lvl} {txt}")
                else:
                    blocks.append(txt)
            elif isinstance(child, CT_Tbl):
                tbl = Table(child, doc)
                rows_md: list[str] = []
                for r_idx, row in enumerate(tbl.rows):
                    cells = [_format_cell(c.text) for c in row.cells]
                    if not any(cells):
                        continue
                    rows_md.append("| " + " | ".join(cells) + " |")
                    if r_idx == 0:
                        rows_md.append("| " + " | ".join("---" for _ in cells) + " |")
                if rows_md:
                    blocks.append("\n".join(rows_md))
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"docx ordered traversal fallback: {exc}")
        for p in doc.paragraphs:
            txt = (p.text or "").strip()
            if txt:
                blocks.append(txt)
        for tbl in doc.tables:
            rows_md = []
            for r_idx, row in enumerate(tbl.rows):
                cells = [_format_cell(c.text) for c in row.cells]
                if any(cells):
                    rows_md.append("| " + " | ".join(cells) + " |")
                    if r_idx == 0:
                        rows_md.append("| " + " | ".join("---" for _ in cells) + " |")
            if rows_md:
                blocks.append("\n".join(rows_md))

    text = "\n\n".join(blocks).strip()
    if not text:
        warnings.append(f"docx has no readable paragraphs or tables: {path.name}")
    text, was_trunc = _truncate_text(text, max_chars)
    if was_trunc:
        warnings.append(f"docx truncated to {max_chars} chars")
    return text + ("\n" if text else ""), None, warnings


def probe_spreadsheet(
    path: Path,
    *,
    max_sheets: int = 12,
    max_cols: int = 50,
    max_sample_rows: int = 3,
    max_scan_rows: int = 100000,
) -> dict[str, Any]:
    """Safely inspect `.xlsx`/`.xlsm` schema without loading giant sheets into RAM."""
    _validate_readable_file(path)
    suf = path.suffix.lower()
    if suf not in SPREADSHEET_SUFFIXES:
        return {"error": f"unsupported spreadsheet suffix: {suf}", "sheets": []}

    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover
        return {"error": f"openpyxl missing: {exc}", "sheets": []}

    wb = None
    try:
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        sheet_names = list(wb.sheetnames)
        sheets_meta: list[dict[str, Any]] = []
        primary_columns: list[Any] = []
        primary_samples: list[list[Any]] = []
        primary_rows_est = 0

        for idx, sname in enumerate(sheet_names[:max_sheets]):
            ws = wb[sname]
            declared_rows = getattr(ws, "max_row", None)
            declared_cols = getattr(ws, "max_column", None)

            header: list[str] = []
            samples: list[list[str]] = []
            scanned = 0
            # Read header + small sample window; estimate row count conservatively
            limit_preview = 1 + max_sample_rows
            for row in ws.iter_rows(values_only=True):
                scanned += 1
                vals = list(row[:max_cols])
                if not header and any(v is not None and str(v).strip() != "" for v in vals):
                    header = [str(v).strip() if v is not None else "" for v in vals]
                elif header and len(samples) < max_sample_rows:
                    if any(v is not None and str(v).strip() != "" for v in vals):
                        samples.append([str(v).strip() if v is not None else "" for v in vals])
                if scanned >= limit_preview and declared_rows is not None:
                    break
                if scanned >= max_scan_rows:
                    break

            rows_est = int(declared_rows) if isinstance(declared_rows, int) and declared_rows > 0 else scanned
            cols_est = int(declared_cols) if isinstance(declared_cols, int) and declared_cols > 0 else len(header)
            if idx == 0:
                primary_columns = header
                primary_samples = samples
                primary_rows_est = rows_est
            sheets_meta.append(
                {
                    "name": sname,
                    "rows_est": rows_est,
                    "cols_est": cols_est,
                    "columns": header,
                    "sample_rows": samples,
                }
            )

        return {
            "sheet_names": sheet_names,
            "sheet_count": len(sheet_names),
            "sheets": sheets_meta,
            "columns": primary_columns,
            "sample_rows": primary_samples,
            "rows_count_est": primary_rows_est,
        }
    except (PermissionError, IsADirectoryError):
        raise
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "sheets": []}
    finally:
        if wb is not None:
            try:
                wb.close()
            except Exception:  # noqa: BLE001
                pass


def extract_spreadsheet_text(
    path: Path,
    *,
    max_chars: int | None = DEFAULT_MAX_CHARS,
    max_sheets: int = 12,
    max_cols: int = 50,
    max_sample_rows: int = 3,
) -> tuple[str, int | None, list[str]]:
    """Render concise structured Markdown preview for `.xlsx`/`.xlsm`."""
    _validate_readable_file(path)
    meta = probe_spreadsheet(
        path,
        max_sheets=max_sheets,
        max_cols=max_cols,
        max_sample_rows=max_sample_rows,
    )
    warnings: list[str] = []
    if meta.get("error"):
        raise RuntimeError(f"failed to read spreadsheet {path.name}: {meta['error']}")

    sheets = meta.get("sheets") or []
    lines: list[str] = [
        f"Spreadsheet `{path.name}` ({meta.get('sheet_count', len(sheets))} sheets: {', '.join(meta.get('sheet_names') or [])})"
    ]
    for sm in sheets:
        lines.append("")
        lines.append(
            f"### Sheet: {sm['name']} (rows≈{sm.get('rows_est')}, cols≈{sm.get('cols_est')})"
        )
        cols = sm.get("columns") or []
        if cols:
            lines.append("Columns: " + ", ".join(c or f"col_{i+1}" for i, c in enumerate(cols)))
        samples = sm.get("sample_rows") or []
        if samples:
            for r_i, srow in enumerate(samples, start=1):
                lines.append(f"- Row {r_i}: " + " | ".join(srow))

    text = "\n".join(lines).strip()
    text, was_trunc = _truncate_text(text, max_chars)
    if was_trunc:
        warnings.append(f"spreadsheet summary truncated to {max_chars} chars")
    return text + ("\n" if text else ""), meta.get("sheet_count"), warnings


def extract_pdf_text_safe(
    path: Path,
    *,
    max_chars: int | None = DEFAULT_MAX_CHARS,
    min_chars: int = 1,
) -> tuple[str, int | None, list[str]]:
    """Extract text layer from PDF safely using pypdf."""
    _validate_readable_file(path)
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pdf extractor requires pypdf (pip install pypdf)") from exc

    warnings: list[str] = []
    reader = PdfReader(str(path))
    n_pages = len(reader.pages)
    parts: list[str] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            t = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"page {i} extract failed: {exc}")
            t = ""
        if t.strip():
            parts.append(f"<!-- pdf page {i}/{n_pages} -->\n{t.strip()}")
    text = "\n\n".join(parts).strip()
    if len(text) < min_chars:
        warnings.append(f"pdf text layer short/empty ({len(text)} chars)")
    text, was_trunc = _truncate_text(text, max_chars)
    if was_trunc:
        warnings.append(f"pdf text truncated to {max_chars} chars")
    return text + ("\n" if text else ""), n_pages, warnings


def extract_csv_text(
    path: Path,
    *,
    max_chars: int | None = DEFAULT_MAX_CHARS,
    max_rows: int = 25,
) -> tuple[str, int | None, list[str]]:
    _validate_readable_file(path)
    raw = path.read_text(encoding="utf-8", errors="replace")[:32768]
    delim = "\t" if path.suffix.lower() == ".tsv" else ","
    rows = list(csv.reader(io.StringIO(raw), delimiter=delim))
    lines = [f"Tabular file `{path.name}` ({len(rows)} sampled rows):"]
    for row in rows[:max_rows]:
        lines.append("| " + " | ".join(_format_cell(c) for c in row[:50]) + " |")
    text, _ = _truncate_text("\n".join(lines).strip(), max_chars)
    return text + "\n", None, []


def extract_plain_text(
    path: Path,
    *,
    max_chars: int | None = DEFAULT_MAX_CHARS,
) -> tuple[str, int | None, list[str]]:
    _validate_readable_file(path)
    raw = path.read_text(encoding="utf-8", errors="replace")
    text, was_trunc = _truncate_text(raw, max_chars)
    warnings = [f"text truncated to {max_chars} chars"] if was_trunc else []
    return text, 1, warnings


def extract_asset_text(
    path: Path,
    *,
    max_chars: int | None = DEFAULT_MAX_CHARS,
) -> tuple[str, int | None, list[str]]:
    """Dispatch structured text extraction by suffix; never read binary archives as UTF-8."""
    path = Path(path)
    _validate_readable_file(path)
    suf = path.suffix.lower()
    if suf in DOCX_SUFFIXES:
        return extract_docx_text(path, max_chars=max_chars)
    if suf in SPREADSHEET_SUFFIXES:
        return extract_spreadsheet_text(path, max_chars=max_chars)
    if suf in PDF_SUFFIXES:
        return extract_pdf_text_safe(path, max_chars=max_chars)
    if suf in {".csv", ".tsv"}:
        return extract_csv_text(path, max_chars=max_chars)
    if suf in TEXT_SUFFIXES or suf in {".json", ".jsonl"}:
        return extract_plain_text(path, max_chars=max_chars)
    if suf == ".xls":
        raise RuntimeError(
            f"legacy binary .xls is not supported safely without xlrd conversion: {path.name}"
        )
    raise RuntimeError(f"unsupported binary or unknown asset suffix {suf!r}: {path.name}")


def read_statement_text(path: Path, *, max_chars: int = 4000) -> str:
    """Best-effort statement text reader for `.md`, `.txt`, `.docx`, `.pdf`. Returns '' on binary/error."""
    p = Path(path)
    try:
        _validate_readable_file(p)
        suf = p.suffix.lower()
        if suf in TEXT_SUFFIXES:
            return extract_plain_text(p, max_chars=max_chars)[0]
        if suf in DOCX_SUFFIXES:
            return extract_docx_text(p, max_chars=max_chars)[0]
        if suf in PDF_SUFFIXES:
            return extract_pdf_text_safe(p, max_chars=max_chars, min_chars=0)[0]
        return ""
    except (IsADirectoryError, PermissionError, OSError, RuntimeError):
        return ""
