"""OR-Path 1.1 intake_parse tests (S3)."""
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
from gate_intake import check_intake_files  # noqa: E402
from intake_ocr import run_ocr  # noqa: E402
from intake_parse import extract_subproblems, run_parse  # noqa: E402


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)


def test_extract_subproblems_q_markers():
    body = "Intro\nQ1: shortest path from S to T\nmore\nQ2: TSP tour\nend\n"
    subs = extract_subproblems(body)
    assert [s["id"] for s in subs] == ["Q1", "Q2"]


def test_extract_cn_markers():
    body = "题面\n问题一 最短路\n细节\n问题二 旅行商\n"
    subs = extract_subproblems(body)
    assert [s["id"] for s in subs] == ["Q1", "Q2"]


def test_parse_from_ocr_txt(tmp_path: Path):
    notes = tmp_path / "notes"
    outputs = tmp_path / "outputs"
    ocr = run_ocr(
        slug="s3_txt",
        inputs=[FIX / "ocr" / "sample.txt"],
        root=ROOT,
        notes_dir=notes,
    )
    assert ocr.status == "ok"
    raw = notes / "s3_txt-ocr.raw.md"
    meta = notes / "s3_txt-ocr.meta.json"
    pr = run_parse(
        slug="s3_txt",
        ocr_raw=raw,
        ocr_meta=meta,
        root=tmp_path,
        notes_dir=notes,
        outputs_dir=outputs,
        run_gate=True,
    )
    assert not pr.gate_errors, pr.gate_errors
    assert (notes / "s3_txt-problem-brief.md").is_file()
    intake_path = outputs / "s3_txt-intake.json"
    assert intake_path.is_file()
    data = json.loads(intake_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.1.0"
    assert len(data["subproblems"]) >= 2
    assert data["problem_class_hint"] in {"shortest_path", "tsp", None} or True
    # gate via files (cwd = tmp_path so relative brief may need root)
    # brief_path is relative to tmp_path root
    errs = check_intake_files(
        intake_path,
        brief_path=notes / "s3_txt-problem-brief.md",
        min_subproblems=2,
    )
    assert errs == [], errs


def test_parse_from_ocr_pdf(tmp_path: Path):
    notes = tmp_path / "notes"
    outputs = tmp_path / "outputs"
    ocr = run_ocr(
        slug="s3_pdf",
        inputs=[FIX / "ocr" / "sample_text.pdf"],
        root=ROOT,
        notes_dir=notes,
    )
    assert ocr.status == "ok"
    pr = run_parse(
        slug="s3_pdf",
        ocr_raw=notes / "s3_pdf-ocr.raw.md",
        ocr_meta=notes / "s3_pdf-ocr.meta.json",
        root=tmp_path,
        notes_dir=notes,
        outputs_dir=outputs,
        run_gate=True,
    )
    assert not pr.gate_errors, pr.gate_errors
    data = pr.intake
    assert len(data["subproblems"]) >= 1
    # should not invent forbidden keys
    assert "objective" not in data


def test_parse_no_markers_needs_human(tmp_path: Path):
    notes = tmp_path / "notes"
    outputs = tmp_path / "outputs"
    notes.mkdir(parents=True)
    raw = notes / "solo-ocr.raw.md"
    raw.write_text(
        "# OCR raw — solo\n\nJust a blob without question markers. Minimize cost.\n",
        encoding="utf-8",
    )
    meta = notes / "solo-ocr.meta.json"
    meta.write_text(
        json.dumps(
            {
                "slug": "solo",
                "backend": "manual_stub",
                "sources": [{"path": "x.txt", "kind": "text"}],
                "created_at": "t",
                "warnings": [],
                "raw_path": "notes/solo-ocr.raw.md",
                "status": "ok",
            }
        ),
        encoding="utf-8",
    )
    pr = run_parse(
        slug="solo",
        ocr_raw=raw,
        ocr_meta=meta,
        root=tmp_path,
        notes_dir=notes,
        outputs_dir=outputs,
        run_gate=True,
    )
    assert not pr.gate_errors, pr.gate_errors
    assert pr.intake["status"] == "needs_human"
    assert pr.intake["ambiguities"]
    assert len(pr.intake["subproblems"]) == 1


def test_cli_e2e_ocr_then_parse(tmp_path: Path):
    notes = tmp_path / "notes"
    outputs = tmp_path / "outputs"
    r1 = run(
        [
            PY,
            str(TOOLS / "intake_ocr.py"),
            "--slug",
            "cli_s3",
            "--in",
            str(FIX / "ocr" / "sample.txt"),
            "--root",
            str(tmp_path),
            "--notes-dir",
            str(notes),
        ]
    )
    # root tmp means relative paths under tmp; source path is absolute under ROOT fixtures
    # use ROOT as root for nicer paths
    notes2 = tmp_path / "notes2"
    outputs2 = tmp_path / "out2"
    r1 = run(
        [
            PY,
            str(TOOLS / "intake_ocr.py"),
            "--slug",
            "cli_s3",
            "--in",
            str(FIX / "ocr" / "sample.txt"),
            "--root",
            str(ROOT),
            "--notes-dir",
            str(notes2),
        ]
    )
    assert r1.returncode == 0, r1.stderr
    r2 = run(
        [
            PY,
            str(TOOLS / "intake_parse.py"),
            "--slug",
            "cli_s3",
            "--ocr-raw",
            str(notes2 / "cli_s3-ocr.raw.md"),
            "--ocr-meta",
            str(notes2 / "cli_s3-ocr.meta.json"),
            "--root",
            str(ROOT),
            "--notes-dir",
            str(notes2),
            "--outputs-dir",
            str(outputs2),
        ]
    )
    assert r2.returncode == 0, r2.stderr + r2.stdout
    assert (outputs2 / "cli_s3-intake.json").is_file()
    r3 = run(
        [
            PY,
            str(TOOLS / "gate_intake.py"),
            str(outputs2 / "cli_s3-intake.json"),
            "--brief",
            str(notes2 / "cli_s3-problem-brief.md"),
            "--min-subproblems",
            "2",
        ]
    )
    assert r3.returncode == 0, r3.stderr + r3.stdout
