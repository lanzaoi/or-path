#!/usr/bin/env python3
"""routing collaboration team — thin cartridge-driven shim (Phase 2.4).

History: this module used to be ~900 lines of cloned protocol code (role
prompts, meta-schema validators, budget-ledger audits, six ReAct agent
factories and supervisor graph builders) copied verbatim across all ten
domain modules (~9,900 lines). It is now a thin shim: every protocol
constant, tool, factory and graph builder is assembled by
:func:`orpath.agents.cartridges.build_team_namespace` from the unified
``DomainCartridge`` registry and re-exported here under the historical
import surface.

Domain: Vehicle routing & delivery (PyVRP / HGS / VRPTW / TSP / shortest path / network flow).

Numbers Truth: numeric authority lives solely in ``tools/solve_*`` and
``tools/validate_solution.py``; this shim never invents or votes on values.
"""
from __future__ import annotations

from orpath.agents.cartridges import build_team_namespace

globals().update(build_team_namespace("routing").exports)
