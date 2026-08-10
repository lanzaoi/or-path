"""Shared fixture path resolution under ORPATH_HOME (relocatable)."""
from __future__ import annotations

import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
_HINT = _TOOLS.parent
if str(_HINT) not in sys.path:
    sys.path.insert(0, str(_HINT))

try:
    from orpath.paths import orpath_home
except ImportError:  # pragma: no cover
    def orpath_home() -> Path:  # type: ignore
        return _HINT


def root() -> Path:
    return orpath_home()


# Back-compat name used across tools
ROOT = root()


def fixture_dir(problem_id: str) -> Path:
    base_root = root()
    for base in (
        base_root / "eval_or_bench" / "instances",
        base_root / "fixtures" / "benchmarks",
        base_root / "fixtures" / "t3",
        base_root / "fixtures" / "t2",
        base_root / "fixtures" / "t1",
    ):
        p = base / problem_id
        if p.is_dir():
            return p
    raise FileNotFoundError(f"fixture not found for problem_id={problem_id} under {base_root}")


def fixture_file(problem_id: str, name: str) -> Path:
    d = fixture_dir(problem_id)
    path = d / name
    if not path.is_file():
        raise FileNotFoundError(f"missing {name} under {d}")
    return path
