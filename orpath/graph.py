"""Legacy T1 graph entry — ADR-0003: ControlPlane.build_graph."""
from __future__ import annotations

from typing import Any

from orpath.control_plane import build_graph as _build


def build_graph() -> Any:
    return _build(checkpointer=None)
