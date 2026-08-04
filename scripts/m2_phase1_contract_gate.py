#!/usr/bin/env python3
"""M2 Phase 1 gate: polyomino domain contract + registration (no full solve e2e).

Checks:
1. Pi default model is deepseek-v4-flash
2. domain_registry aliases + canonical polyomino_cover
3. gate_schema accepts polyomino structural schema; rejects optima keys
4. gate_schema rejects unknown class
5. solve_dispatch registers polyomino adapter
6. unregistered fake class still blocked at schema
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def _py() -> str:
    cand = ROOT / ".venv-314" / "Scripts" / "python.exe"
    return str(cand) if cand.is_file() else sys.executable


def test_pi_model() -> None:
    from orpath.subagent_runtime import DEFAULT_MODEL, DEFAULT_PROVIDER

    if DEFAULT_PROVIDER != "deepseek":
        _fail(f"provider={DEFAULT_PROVIDER}")
    if DEFAULT_MODEL != "deepseek-v4-flash":
        _fail(f"DEFAULT_MODEL={DEFAULT_MODEL} (want deepseek-v4-flash)")
    settings = json.loads((ROOT / ".pi" / "settings.json").read_text(encoding="utf-8"))
    dm = (settings.get("subagents") or {}).get("defaultModel")
    if dm != "deepseek-v4-flash":
        _fail(f".pi/settings defaultModel={dm}")
    _ok(f"Pi model {DEFAULT_PROVIDER}/{DEFAULT_MODEL}")


def test_registry() -> None:
    from orpath.domain_registry import (
        is_polyomino_class,
        is_registered_solve_class,
        normalize_problem_class,
        schema_class_ok,
    )

    assert normalize_problem_class("polyomino") == "polyomino_cover"
    assert normalize_problem_class("POLYOMINO_COVER") == "polyomino_cover"
    assert is_polyomino_class("poly")
    assert is_registered_solve_class("polyomino")
    assert schema_class_ok("polyomino_cover")
    assert not schema_class_ok("made_up_domain_xyz")
    _ok("domain_registry aliases")


def test_gate_schema_polyomino() -> None:
    td = Path(tempfile.mkdtemp(prefix="m2p1-schema-"))
    good = {
        "problem_id": "polyomino_b_q1",
        "problem_class": "polyomino",
        "rows": 4,
        "cols": 4,
        "pieces": [{"id": "M"}, {"id": "D"}, {"id": "L3"}],
    }
    bad_opt = {
        **good,
        "problem_class": "polyomino_cover",
        "objective": 6,
        "placements": [],
    }
    # placements might not be forbidden key - objective is
    unknown = {
        "problem_id": "x",
        "problem_class": "quantum_anneal_fake",
        "nodes": ["a"],
    }
    # unknown without sp shape
    unknown2 = {"problem_id": "x", "problem_class": "quantum_anneal_fake", "foo": 1}

    gp = td / "good.json"
    bp = td / "bad.json"
    up = td / "unk.json"
    gp.write_text(json.dumps(good), encoding="utf-8")
    bp.write_text(json.dumps(bad_opt), encoding="utf-8")
    up.write_text(json.dumps(unknown2), encoding="utf-8")

    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONNOUSERSITE": "1"}
    env.pop("PYTHONHOME", None)
    r1 = subprocess.run(
        [_py(), str(ROOT / "tools" / "gate_schema.py"), str(gp)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if r1.returncode != 0:
        _fail(f"good schema should PASS: {r1.stderr} {r1.stdout}")
    r2 = subprocess.run(
        [_py(), str(ROOT / "tools" / "gate_schema.py"), str(bp)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if r2.returncode == 0:
        _fail("schema with objective should FAIL")
    if "forbidden" not in (r2.stderr or "").lower() and "objective" not in (r2.stderr or ""):
        _fail(f"expected forbidden objective: {r2.stderr}")
    r3 = subprocess.run(
        [_py(), str(ROOT / "tools" / "gate_schema.py"), str(up)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if r3.returncode == 0:
        _fail("unknown class should FAIL")
    _ok("gate_schema polyomino + forbid optima + unknown blocked")


def test_dispatch_registered() -> None:
    sys.path.insert(0, str(ROOT / "tools"))
    from solve_dispatch import ADAPTER_SCRIPTS, list_adapters

    ads = list_adapters()
    for k in ("polyomino", "polyomino_cover", "poly"):
        if k not in ads:
            _fail(f"missing adapter mode {k}")
        script = ROOT / "tools" / ads[k]
        if not script.is_file():
            _fail(f"adapter script missing {script}")
    if "solve_polyomino.py" not in ADAPTER_SCRIPTS.values():
        _fail("solve_polyomino.py not registered")
    _ok(f"dispatch polyomino → {ads['polyomino']}")


def test_docs() -> None:
    p = ROOT / "docs" / "m2-polyomino.md"
    if not p.is_file():
        _fail("missing docs/m2-polyomino.md")
    t = p.read_text(encoding="utf-8")
    for n in ("polyomino_cover", "phase 1", "ADAPTER", "deepseek-v4-flash"):
        if n.lower() not in t.lower() and n not in t:
            # deepseek optional in doc
            if n == "deepseek-v4-flash":
                continue
            _fail(f"docs missing {n}")
    _ok("docs/m2-polyomino.md")


def main() -> int:
    print("=== m2_phase1_contract_gate ===")
    os.environ.pop("PYTHONPATH", None)
    os.environ["PYTHONNOUSERSITE"] = "1"
    test_pi_model()
    test_registry()
    test_gate_schema_polyomino()
    test_dispatch_registered()
    test_docs()
    print("PASS m2_phase1_contract_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
