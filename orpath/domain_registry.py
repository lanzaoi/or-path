"""OR-Path domain / problem_class registry (M2 phase 1).

Canonical classes + aliases. Product claim requires:
adapter in solve_dispatch + schema whitelist + (later) validate.
"""
from __future__ import annotations

from typing import Iterable

# Canonical product classes (schema / solve / validate)
CANONICAL_CLASSES: frozenset[str] = frozenset(
    {
        "shortest_path",
        "tsp",
        "vrp",
        "tube_cut",
        "polyomino_cover",
    }
)

# alias → canonical
CLASS_ALIASES: dict[str, str] = {
    "sp": "shortest_path",
    "shortest": "shortest_path",
    "tube": "tube_cut",
    "tube_bfd": "tube_cut",
    "cutting_stock": "tube_cut",
    "cut_stock": "tube_cut",
    "polyomino": "polyomino_cover",
    "polyomino_tiling": "polyomino_cover",
    "tiling_cover": "polyomino_cover",
    "poly": "polyomino_cover",
}

# Classes with a registered solve adapter mode name in ADAPTER_SCRIPTS
# (keep in sync with tools/solve_dispatch.py)
REGISTERED_SOLVE_CLASSES: frozenset[str] = frozenset(
    {
        "shortest_path",
        "tsp",
        "vrp",
        "tube_cut",
        "polyomino_cover",
    }
)

# solve_mode names that map to polyomino adapter
POLYOMINO_SOLVE_MODES: frozenset[str] = frozenset(
    {
        "polyomino",
        "polyomino_cover",
        "poly",
    }
)

POLYOMINO_SCHEMA_KEYS: frozenset[str] = frozenset(
    {
        "board",
        "board_ref",
        "rows",
        "cols",
        "grid",
        "cells",
        "removed",
        "pieces",
        "piece_types",
        "piece_ids",
        "max_counts",
        "inventory",
        "allow_reflect",
        "max_uncovered",
        "task",
        "subproblems",
        "questions",
    }
)


def normalize_problem_class(raw: str | None) -> str:
    """Lowercase + alias fold; empty stays empty."""
    if raw is None:
        return ""
    pc = str(raw).strip().lower()
    if not pc:
        return ""
    return CLASS_ALIASES.get(pc, pc)


def is_known_class(raw: str | None) -> bool:
    pc = normalize_problem_class(raw)
    return pc in CANONICAL_CLASSES or pc in CLASS_ALIASES.values()


def is_registered_solve_class(raw: str | None) -> bool:
    return normalize_problem_class(raw) in REGISTERED_SOLVE_CLASSES


def is_polyomino_class(raw: str | None) -> bool:
    return normalize_problem_class(raw) == "polyomino_cover"


def schema_class_ok(raw: str | None) -> bool:
    """True if gate_schema should accept this problem_class (known product shape)."""
    pc = normalize_problem_class(raw)
    return pc in CANONICAL_CLASSES


def iter_polyomino_aliases() -> Iterable[str]:
    yield "polyomino_cover"
    for a, c in CLASS_ALIASES.items():
        if c == "polyomino_cover":
            yield a
