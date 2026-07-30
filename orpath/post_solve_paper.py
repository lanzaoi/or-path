"""Compatibility shim — prefer orpath.paper_protocol (ADR-0004)."""
from __future__ import annotations

from orpath.paper_protocol import (  # noqa: F401
    base_state as _base_state,
    run_from_solution,
    run_post_solve_paper,
    summarize_paper_result,
)

__all__ = ["run_post_solve_paper", "run_from_solution", "summarize_paper_result"]
