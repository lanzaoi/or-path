"""OR-Path 1.1 intake_ocr tests (S2)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
PY = sys.executable
FIX = ROOT / "fixtures" / "intake"

sys.path.insert(0, str(TOOLS))
from intake_ocr import (  # noqa: E402
    choose_backend,
    run_ocr,
    validate_ocr_meta,
)


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)


def test_choose_backend():
    assert choose_backend(Path("a.txt")) == "manual_stub"
    assert choose_backend(Path("a.PDF")) == "pdf_text"
    assert choose_backend(Path("x.png")) == "paddleocr"
    assert choose_backend(Path("x.png"), forced="manual_stub") == "manual_stub"


def test_manual_stub_writes(tmp_path: Path):
    src = FIX / "ocr" / "sample.txt"
    notes = tmp_path / "notes"
    res = run_ocr(
        slug="s2_txt",
        inputs=[src],
        root=ROOT,
        notes_dir=notes,
    )
    assert res.status == "ok"
    assert res.backend == "manual_stub"
    raw = notes / "s2_txt-ocr.raw.md"
    meta = notes / "s2_txt-ocr.meta.json"
    assert raw.is_file() and "Q1" in raw.read_text(encoding="utf-8")
    data = json.loads(meta.read_text(encoding="utf-8"))
    assert validate_ocr_meta(data) == []
    assert data["slug"] == "s2_txt"
    assert data["sources"][0]["backend"] == "manual_stub"
    assert data["sources"][0]["sha256"]
    assert data["sources"][0]["char_count"] > 0


def test_pdf_text_writes(tmp_path: Path):
    src = FIX / "ocr" / "sample_text.pdf"
    assert src.is_file()
    notes = tmp_path / "notes"
    res = run_ocr(
        slug="s2_pdf",
        inputs=[src],
        root=ROOT,
        notes_dir=notes,
    )
    assert res.status == "ok", res.warnings
    assert res.backend == "pdf_text"
    text = (notes / "s2_pdf-ocr.raw.md").read_text(encoding="utf-8")
    assert "shortest path" in text.lower() or "Shortest" in text or "Q1" in text
    meta = json.loads((notes / "s2_pdf-ocr.meta.json").read_text(encoding="utf-8"))
    assert meta["sources"][0]["kind"] == "pdf"
    assert (meta["sources"][0].get("pages") or 0) >= 1


def test_mixed_txt_pdf(tmp_path: Path):
    res = run_ocr(
        slug="s2_mix",
        inputs=[FIX / "ocr" / "sample.txt", FIX / "ocr" / "sample_text.pdf"],
        root=ROOT,
        notes_dir=tmp_path / "notes",
    )
    assert res.status == "ok"
    assert res.backend == "mixed"
    assert len(res.sources) == 2


def test_image_ocr_scan_sample(tmp_path: Path):
    """Real image OCR via ppocr stack or rapidocr fallback (not placeholder)."""
    src = FIX / "ocr" / "scan_sample.png"
    assert src.is_file(), "fixtures/intake/ocr/scan_sample.png required"
    notes = tmp_path / "notes"
    res = run_ocr(
        slug="s2_scan",
        inputs=[src],
        root=ROOT,
        notes_dir=notes,
        force_backend="paddleocr",
    )
    assert res.status == "ok", res.warnings
    assert res.backend in {"paddleocr", "rapidocr", "mixed"}
    assert "placeholder" not in res.backend.lower()
    text = (notes / "s2_scan-ocr.raw.md").read_text(encoding="utf-8")
    assert "Question" in text or "shortest" in text.lower() or "Q1" in text
    meta = json.loads((notes / "s2_scan-ocr.meta.json").read_text(encoding="utf-8"))
    assert validate_ocr_meta(meta) == []
    assert meta["sources"][0]["char_count"] > 0


def test_image_garbage_errors(tmp_path: Path):
    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nnot-a-real-png")
    res = run_ocr(
        slug="s2_img",
        inputs=[img],
        root=tmp_path,
        notes_dir=tmp_path / "notes",
    )
    assert res.status == "error"
    assert res.warnings


def test_cli_manual_stub(tmp_path: Path):
    notes = tmp_path / "notes"
    r = run(
        [
            PY,
            str(TOOLS / "intake_ocr.py"),
            "--slug",
            "cli_txt",
            "--in",
            str(FIX / "ocr" / "sample.txt"),
            "--root",
            str(ROOT),
            "--notes-dir",
            str(notes),
            "--json",
        ]
    )
    assert r.returncode == 0, r.stderr + r.stdout
    meta = json.loads(r.stdout)
    assert meta["status"] == "ok"
    assert (notes / "cli_txt-ocr.raw.md").is_file()


def test_cli_pdf(tmp_path: Path):
    notes = tmp_path / "notes"
    r = run(
        [
            PY,
            str(TOOLS / "intake_ocr.py"),
            "--slug",
            "cli_pdf",
            "--in",
            str(FIX / "ocr" / "sample_text.pdf"),
            "--root",
            str(ROOT),
            "--notes-dir",
            str(notes),
        ]
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "pdf_text" in r.stdout


def test_missing_file_errors(tmp_path: Path):
    res = run_ocr(
        slug="missing",
        inputs=[tmp_path / "nope.txt"],
        root=tmp_path,
        notes_dir=tmp_path / "notes",
    )
    assert res.status == "error"
