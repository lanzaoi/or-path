#!/usr/bin/env python3
"""Thin CLI for tube-cut — authoritative adapter is tools/solve_tube_cut_b2026.py (ADR-0002)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tools" / "solve_tube_cut_b2026.py"


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if not ADAPTER.is_file():
        print(f"error: missing adapter {ADAPTER}", file=sys.stderr)
        return 2
    r = subprocess.run([sys.executable, str(ADAPTER), *argv], cwd=ROOT)
    if r.returncode != 0:
        return int(r.returncode)
    sys.path.insert(0, str(ROOT / "tools"))
    from solve_dispatch import _tube_envelope_from_outputs  # noqa: E402
    from solve_envelope import validate_envelope  # noqa: E402

    try:
        data = _tube_envelope_from_outputs(ROOT, "tube_cut_b2026")
    except Exception as exc:  # noqa: BLE001
        print(f"envelope error: {exc}", file=sys.stderr)
        return 1
    ok, errs = validate_envelope(data)
    if not ok:
        print("envelope: " + "; ".join(errs), file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
