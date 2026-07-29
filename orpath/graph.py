"""Legacy T1 graph entry — ADR-0001: delegates to product graph."""
from __future__ import annotations

from typing import Any

from orpath.graph_product import build_graph_product


def build_graph() -> Any:
    """Build the product pipeline graph (no checkpointer)."""
    return build_graph_product(checkpointer=None)
