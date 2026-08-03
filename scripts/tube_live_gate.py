#!/usr/bin/env python3
"""Tube LIVE close gate — schema + tube validate on disk (no full LIVE Pi).

Default targets slug=live-btube artifacts from contest B tube-cut run.
Exit 0 only if:
- schema gate PASS (cutting_stock/tube_cut structural OK; string path keys OK)
- solution is tube tool FEASIBLE (not SP mock 42)
- validate_solution ok for tube_cut
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _py() -> str:
    cand = ROOT / ".venv-314" / "Scripts" / "python.exe"
    return str(cand) if cand.is_file() else sys.executable


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def main() -> int:
    print("=== tube_live_gate ===")
    slug = "live-btube"
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        slug = sys.argv[1]
    schema = ROOT / "outputs" / f"{slug}-schema.json"
    sol = ROOT / "outputs" / f"{slug}-solution.json"
    val_out = ROOT / "outputs" / f"{slug}-validate.json"

    if not schema.is_file():
        _fail(f"missing {schema}")
    if not sol.is_file():
        _fail(f"missing {sol}")

    env = {**dict(**{k: v for k, v in __import__("os").environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}),
           "PYTHONNOUSERSITE": "1"}
    r = subprocess.run(
        [_py(), str(ROOT / "tools" / "gate_schema.py"), str(schema)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        _fail(f"gate_schema: {(r.stdout or '') + (r.stderr or '')}")
    _ok("gate_schema PASS")

    r2 = subprocess.run(
        [
            _py(),
            str(ROOT / "tools" / "validate_solution.py"),
            "--problem-id",
            "b-tube-cut",
            "--solution",
            str(sol),
            "--out",
            str(val_out),
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if r2.returncode != 0:
        _fail(f"validate: {(r2.stdout or '')[-500:]}")
    rep = json.loads(val_out.read_text(encoding="utf-8"))
    if not rep.get("ok"):
        _fail(f"validate not ok: {rep.get('errors')}")
    _ok(f"validate ok class={rep.get('problem_class')}")

    sol_o = json.loads(sol.read_text(encoding="utf-8"))
    if sol_o.get("objective") == 42:
        _fail("objective looks like SP mock gold 42")
    src = str(sol_o.get("source") or "")
    if "tube" not in src.lower() and "tube" not in str(sol_o.get("solver") or "").lower():
        _fail(f"solution source not tube: {src}")
    if str(sol_o.get("status") or "").upper() not in {"FEASIBLE", "OPTIMAL"}:
        _fail(f"bad status {sol_o.get('status')}")
    _ok(
        f"solution status={sol_o.get('status')} objective={sol_o.get('objective')} "
        f"source={src}"
    )

    # sub evidence optional but preferred
    agents = ROOT / "outputs" / ".agents" / slug
    if agents.is_dir():
        sys.path.insert(0, str(ROOT))
        from orpath.subagent_dispatch import detect_subagent_calls

        hit = False
        for lg in agents.glob("*-lead-*.log"):
            t = lg.read_bytes()[-200000:].decode("utf-8", "replace")
            h, _ = detect_subagent_calls(t)
            if h:
                hit = True
                break
        if hit:
            _ok("true subagent toolCall evidence on slug")
        else:
            print("NOTE: no subagent detect on this slug (core numbers still PASS)")
    print("PASS tube_live_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
