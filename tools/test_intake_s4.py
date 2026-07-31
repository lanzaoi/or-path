"""S4 checks: skip_intake legacy + multi-Q structure smoke."""
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
from intake_ocr import run_ocr  # noqa: E402
from intake_parse import run_parse  # noqa: E402
from intake_s4_checks import (  # noqa: E402
    brief_has_product_sections,
    legacy_skip_intake_ok,
    structure_coverage_from_intake,
)
from gate_intake import check_intake_files  # noqa: E402


def test_legacy_skip_intake():
    errs = legacy_skip_intake_ok(ROOT)
    assert errs == [], errs


def test_structure_q4_ocr_parse_gate(tmp_path: Path):
    src = FIX / "structure_q4" / "source.txt"
    assert src.is_file()
    notes = tmp_path / "notes"
    outputs = tmp_path / "outputs"
    ocr = run_ocr(slug="struct_q4", inputs=[src], root=ROOT, notes_dir=notes)
    assert ocr.status == "ok"
    pr = run_parse(
        slug="struct_q4",
        ocr_raw=notes / "struct_q4-ocr.raw.md",
        ocr_meta=notes / "struct_q4-ocr.meta.json",
        root=tmp_path,
        notes_dir=notes,
        outputs_dir=outputs,
        run_gate=True,
    )
    assert not pr.gate_errors, pr.gate_errors
    data = pr.intake
    assert len(data["subproblems"]) >= 4, data["subproblems"]
    assert structure_coverage_from_intake(data, min_subproblems=4) == []
    brief = (notes / "struct_q4-problem-brief.md").read_text(encoding="utf-8")
    assert brief_has_product_sections(brief) == []
    # same spirit as gate_intake anti-answer heuristics
    import re

    assert not re.search(r"\bobjective\s*=\s*-?\d", brief, re.I)
    assert not re.search(r"最优(?:解|值)\s*[=：:]\s*-?\d", brief)
    errs = check_intake_files(
        outputs / "struct_q4-intake.json",
        brief_path=notes / "struct_q4-problem-brief.md",
        min_subproblems=4,
    )
    assert errs == [], errs


def test_cli_structure_q4(tmp_path: Path):
    notes = tmp_path / "notes"
    outputs = tmp_path / "outputs"
    r1 = subprocess.run(
        [
            PY,
            str(TOOLS / "intake_ocr.py"),
            "--slug",
            "cli_q4",
            "--in",
            str(FIX / "structure_q4" / "source.txt"),
            "--root",
            str(ROOT),
            "--notes-dir",
            str(notes),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert r1.returncode == 0, r1.stderr
    r2 = subprocess.run(
        [
            PY,
            str(TOOLS / "intake_parse.py"),
            "--slug",
            "cli_q4",
            "--ocr-raw",
            str(notes / "cli_q4-ocr.raw.md"),
            "--ocr-meta",
            str(notes / "cli_q4-ocr.meta.json"),
            "--root",
            str(ROOT),
            "--notes-dir",
            str(notes),
            "--outputs-dir",
            str(outputs),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert r2.returncode == 0, r2.stderr + r2.stdout
    data = json.loads(r2.stdout)
    assert len(data["subproblems"]) >= 4
