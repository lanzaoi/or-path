#!/usr/bin/env python3
"""OR-Path 1.1 intake gate runner (S1–S4).

S1: intake.json contract + forbidden keys + brief heuristics + fixtures.
S2: intake_ocr manual_stub + pdf_text.
S3: intake_parse OCR → problem-brief + intake.json (+ gate).
S4: full §9.2 checklist + skip_intake legacy + multi-Q structure + optional t1/t3 regression.

Env:
  INTAKE_GATE_FAST=1  — skip t1_gate / t3_lg_gate regression (dev loop only)
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
FIX = ROOT / "fixtures" / "intake"
TOOLS = ROOT / "tools"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env.pop("PYTHONPATH", None)
    return env


def main() -> int:
    env = child_env()
    checklist: list[tuple[str, bool, str]] = []

    def mark(item: str, ok: bool, detail: str = "") -> None:
        checklist.append((item, ok, detail))
        print(("OK  " if ok else "FAIL") + f" dod:{item}" + (f" — {detail}" if detail else ""))
        if not ok:
            fail(f"DoD item failed: {item} {detail}")

    # --- unit tests S1–S4 ---
    for test_mod in (
        TOOLS / "test_intake_gate.py",
        TOOLS / "test_intake_ocr.py",
        TOOLS / "test_intake_parse.py",
        TOOLS / "test_intake_s4.py",
    ):
        r = subprocess.run(
            [PY, "-m", "pytest", str(test_mod), "-q", "-p", "no:langsmith"],
            cwd=ROOT,
            env=env,
        )
        if r.returncode != 0:
            fail(f"pytest {test_mod.name} failed")

    # --- S1 CLI gold fixtures ---
    cases = [
        (
            "ok_fixture",
            [
                PY,
                str(TOOLS / "gate_intake.py"),
                str(FIX / "ok" / "intake.json"),
                "--min-subproblems",
                "2",
            ],
            0,
        ),
        (
            "bad_objective",
            [
                PY,
                str(TOOLS / "gate_intake.py"),
                str(FIX / "bad_objective" / "intake.json"),
                "--no-brief",
            ],
            1,
        ),
        (
            "bad_brief",
            [
                PY,
                str(TOOLS / "gate_intake.py"),
                str(FIX / "bad_brief" / "intake.json"),
            ],
            1,
        ),
        (
            "needs_human",
            [
                PY,
                str(TOOLS / "gate_intake.py"),
                str(FIX / "needs_human" / "intake.json"),
            ],
            0,
        ),
    ]
    for name, cmd, expect in cases:
        r = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True)
        if r.returncode != expect:
            print(r.stdout)
            print(r.stderr, file=sys.stderr)
            fail(f"CLI case {name}: expected exit {expect}, got {r.returncode}")
        print(f"OK cli:{name} exit={r.returncode}")

    mark("forbidden_keys_negative", True, "bad_objective exit=1")
    mark("brief_answer_negative", True, "bad_brief exit=1")
    mark("needs_human_fixture", True, "needs_human exit=0")
    mark("ok_fixture_min_subproblems", True, "ok min_sp=2")

    # --- legacy skip_intake ---
    sys.path.insert(0, str(TOOLS))
    from intake_s4_checks import legacy_skip_intake_ok  # noqa: E402

    leg_errs = legacy_skip_intake_ok(ROOT)
    mark("legacy_skip_intake", not leg_errs, "; ".join(leg_errs) if leg_errs else "t1 fixture path")

    # --- S2/S3/S4 OCR→parse→gate smokes ---
    with tempfile.TemporaryDirectory(prefix="orpath-intake-s4-") as td:
        notes = Path(td) / "notes"
        outputs = Path(td) / "outputs"

        # manual_stub + parse
        slug, src = "gate_txt", FIX / "ocr" / "sample.txt"
        r = subprocess.run(
            [
                PY,
                str(TOOLS / "intake_ocr.py"),
                "--slug",
                slug,
                "--in",
                str(src),
                "--root",
                str(ROOT),
                "--notes-dir",
                str(notes),
                "--json",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        if r.returncode != 0 or "manual_stub" not in r.stdout:
            print(r.stdout)
            print(r.stderr, file=sys.stderr)
            fail("manual_stub OCR smoke failed")
        mark("manual_stub_ocr", True, "sample.txt → raw+meta")

        r = subprocess.run(
            [
                PY,
                str(TOOLS / "intake_parse.py"),
                "--slug",
                slug,
                "--ocr-raw",
                str(notes / f"{slug}-ocr.raw.md"),
                "--ocr-meta",
                str(notes / f"{slug}-ocr.meta.json"),
                "--root",
                str(ROOT),
                "--notes-dir",
                str(notes),
                "--outputs-dir",
                str(outputs),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr, file=sys.stderr)
            fail("parse smoke txt failed")
        intake = outputs / f"{slug}-intake.json"
        brief = notes / f"{slug}-problem-brief.md"
        r = subprocess.run(
            [
                PY,
                str(TOOLS / "gate_intake.py"),
                str(intake),
                "--brief",
                str(brief),
                "--min-subproblems",
                "2",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            fail("gate after parse txt failed")
        mark("parse_brief_and_intake_json", True, "schema_version + sections via gate")
        mark("subproblems_min_gold", True, "txt min_sp=2")

        # pdf_text
        slug, src = "gate_pdf", FIX / "ocr" / "sample_text.pdf"
        r = subprocess.run(
            [
                PY,
                str(TOOLS / "intake_ocr.py"),
                "--slug",
                slug,
                "--in",
                str(src),
                "--root",
                str(ROOT),
                "--notes-dir",
                str(notes),
                "--json",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        if r.returncode != 0 or "pdf_text" not in r.stdout:
            print(r.stdout)
            print(r.stderr, file=sys.stderr)
            fail("pdf_text OCR smoke failed")
        mark("pdf_text_ocr", True, "sample_text.pdf")

        r = subprocess.run(
            [
                PY,
                str(TOOLS / "intake_parse.py"),
                "--slug",
                slug,
                "--ocr-raw",
                str(notes / f"{slug}-ocr.raw.md"),
                "--ocr-meta",
                str(notes / f"{slug}-ocr.meta.json"),
                "--root",
                str(ROOT),
                "--notes-dir",
                str(notes),
                "--outputs-dir",
                str(outputs),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        if r.returncode != 0:
            fail("parse smoke pdf failed")
        r = subprocess.run(
            [
                PY,
                str(TOOLS / "gate_intake.py"),
                str(outputs / f"{slug}-intake.json"),
                "--brief",
                str(notes / f"{slug}-problem-brief.md"),
                "--min-subproblems",
                "1",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        if r.returncode != 0:
            fail("gate after parse pdf failed")

        # multi-Q structure (contest-shaped Q1..Q4)
        slug, src = "struct_q4", FIX / "structure_q4" / "source.txt"
        if not src.is_file():
            fail(f"missing {src}")
        r = subprocess.run(
            [
                PY,
                str(TOOLS / "intake_ocr.py"),
                "--slug",
                slug,
                "--in",
                str(src),
                "--root",
                str(ROOT),
                "--notes-dir",
                str(notes),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        if r.returncode != 0:
            fail("structure OCR failed")
        r = subprocess.run(
            [
                PY,
                str(TOOLS / "intake_parse.py"),
                "--slug",
                slug,
                "--ocr-raw",
                str(notes / f"{slug}-ocr.raw.md"),
                "--ocr-meta",
                str(notes / f"{slug}-ocr.meta.json"),
                "--root",
                str(ROOT),
                "--notes-dir",
                str(notes),
                "--outputs-dir",
                str(outputs),
                "--json",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            fail("structure parse failed")
        import json

        data = json.loads(r.stdout)
        nsp = len(data.get("subproblems") or [])
        if nsp < 4:
            fail(f"structure subproblems {nsp} < 4")
        if any(k in data for k in ("objective", "tour", "routes", "path")):
            fail("structure intake has solution-shaped keys")
        r = subprocess.run(
            [
                PY,
                str(TOOLS / "gate_intake.py"),
                str(outputs / f"{slug}-intake.json"),
                "--brief",
                str(notes / f"{slug}-problem-brief.md"),
                "--min-subproblems",
                "4",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            fail("structure gate failed")
        mark("structure_multi_q", True, f"Q1..Q4 coverage n={nsp}")

    # --- contracts export ---
    contracts = ROOT / "contracts"
    if contracts.is_dir():
        r = subprocess.run(
            [
                PY,
                "-c",
                (
                    "import sys; "
                    f"sys.path.insert(0, r'{TOOLS}'); "
                    "from schema_models import export_json_schemas; "
                    f"export_json_schemas(r'{contracts}')"
                ),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            fail("export contracts/intake.json failed")
        if not (contracts / "intake.json").is_file():
            fail("missing contracts/intake.json")
        print("OK contracts/intake.json exported")

    # --- regression t1 + t3_lg (spec §9.1); skip with INTAKE_GATE_FAST=1 ---
    fast = (os.environ.get("INTAKE_GATE_FAST") or "").strip() in {"1", "true", "yes"}
    if fast:
        print("SKIP regression t1_gate/t3_lg_gate (INTAKE_GATE_FAST=1)")
        mark("regression_t1_t3", True, "skipped FAST")
    else:
        for name, script in (
            ("t1_gate", ROOT / "scripts" / "t1_gate.py"),
            ("t3_lg_gate", ROOT / "scripts" / "t3_lg_gate.py"),
        ):
            if not script.is_file():
                fail(f"missing {script}")
            print(f"RUN regression {name} ...")
            r = subprocess.run([PY, str(script)], cwd=ROOT, env=env)
            if r.returncode != 0:
                fail(f"regression {name} failed")
            print(f"OK regression:{name}")
        mark("regression_t1_t3", True, "t1_gate + t3_lg_gate")

    print("---")
    print("DoD checklist (§9.2):")
    for item, ok, detail in checklist:
        print(f"  [{'x' if ok else ' '}] {item}" + (f" ({detail})" if detail else ""))

    print("PASS: intake_gate (S1+S2+S3+S4 full §9.2)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
