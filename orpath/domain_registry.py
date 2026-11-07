"""OR-Path domain / problem_class registry (M2 phase 1).

Canonical classes + aliases. Product claim requires:
adapter in solve_dispatch + schema whitelist + (later) validate.
"""
from __future__ import annotations

from typing import Iterable

# Canonical product classes (schema / solve / validate) - 10 Core Solvers
CANONICAL_CLASSES: frozenset[str] = frozenset(
    {
        "shortest_path",
        "tsp",
        "vrp",
        "tube_cut",
        "polyomino_cover",
        "microgrid_dispatch",
        "jssp",
        "bin_packing",
        "facility_location",
        "portfolio_opt",
        "network_flow",
        "qubo_ising",
        "rcpsp",
        "staff_rostering",
        "pyvrp",
        "lot_sizing",
        "qap",
        "graph_coloring",
        "stochastic_lp",
        "max_clique",
        "game_theory",
        "hub_location",
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
    "microgrid": "microgrid_dispatch",
    "energy_storage": "microgrid_dispatch",
    "smart_grid": "microgrid_dispatch",
    "microgrid_mpc": "microgrid_dispatch",
    "power_dispatch": "microgrid_dispatch",
    # Extended 6 solvers aliases
    "job_shop": "jssp",
    "jobshop": "jssp",
    "scheduling": "jssp",
    "fjssp": "jssp",
    "flexible_job_shop": "jssp",
    "flexible_jssp": "jssp",
    "binpack": "bin_packing",
    "bin_pack": "bin_packing",
    "knapsack": "bin_packing",
    "packing": "bin_packing",
    "facility": "facility_location",
    "cflp": "facility_location",
    "flp": "facility_location",
    "location": "facility_location",
    "portfolio": "portfolio_opt",
    "markowitz": "portfolio_opt",
    "asset_allocation": "portfolio_opt",
    "max_flow_matching": "network_flow",
    "bipartite_matching": "network_flow",
    "min_cost_flow": "network_flow",
    "netflow": "network_flow",
    "qubo": "qubo_ising",
    "ising": "qubo_ising",
    "max_cut": "qubo_ising",
    "annealing": "qubo_ising",
    # RCPSP (project scheduling) aliases
    "project_scheduling": "rcpsp",
    "psplib": "rcpsp",
    # Staff rostering aliases
    "staff_rostering": "staff_rostering",
    "nurse_scheduling": "staff_rostering",
    "rostering": "staff_rostering",
    "shift_scheduling": "staff_rostering",
    # Advanced VRP / PDP aliases
    "pyvrp": "pyvrp",
    "vrp_pdp": "pyvrp",
    "pdp": "pyvrp",
    "vrptw": "pyvrp",
    "pickup_delivery": "pyvrp",
    # Multi-period lot sizing aliases
    "lot_sizing": "lot_sizing",
    "inventory_planning": "lot_sizing",
    "wagner_whitin": "lot_sizing",
    "mrp": "lot_sizing",
    "clsp": "lot_sizing",
    "ulsp": "lot_sizing",
    # Quadratic Assignment Problem (facility layout) aliases
    "qap": "qap",
    "quadratic_assignment": "qap",
    "facility_layout": "qap",
    "qaplib": "qap",
    # Graph coloring (chromatic number) aliases
    "graph_coloring": "graph_coloring",
    "vertex_coloring": "graph_coloring",
    "vcp": "graph_coloring",
    "coloring": "graph_coloring",
    "dimacs_col": "graph_coloring",
    # Two-stage stochastic programming aliases
    "stochastic_lp": "stochastic_lp",
    "stochastic_programming": "stochastic_lp",
    "stochastic": "stochastic_lp",
    "two_stage_lp": "stochastic_lp",
    "farmer": "stochastic_lp",
    "farmer_problem": "stochastic_lp",
    # Max Clique / Max Independent Set aliases (mode distinguishes the side)
    "max_clique": "max_clique",
    "clique": "max_clique",
    "maximum_clique": "max_clique",
    "max_independent_set": "max_clique",
    "mis": "max_clique",
    "independent_set": "max_clique",
    # Bimatrix game / Nash equilibrium aliases
    "game_theory": "game_theory",
    "game": "game_theory",
    "nash": "game_theory",
    "nash_equilibrium": "game_theory",
    "bimatrix": "game_theory",
    # p-Hub Location Problem (CAB benchmarks) aliases
    "hub_location": "hub_location",
    "hub": "hub_location",
    "hlp": "hub_location",
    "p_hub": "hub_location",
    "phub": "hub_location",
    "usahlp": "hub_location",
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
        "microgrid_dispatch",
        "jssp",
        "bin_packing",
        "facility_location",
        "portfolio_opt",
        "network_flow",
        "qubo_ising",
        "rcpsp",
        "staff_rostering",
        "pyvrp",
        "lot_sizing",
        "qap",
        "graph_coloring",
        "stochastic_lp",
        "max_clique",
        "game_theory",
        "hub_location",
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

MICROGRID_SOLVE_MODES: frozenset[str] = frozenset(
    {
        "microgrid",
        "microgrid_dispatch",
        "energy_storage",
    }
)

MICROGRID_SCHEMA_KEYS: frozenset[str] = frozenset(
    {
        "battery",
        "storage",
        "pv",
        "load",
        "prices",
        "grid",
        "time_horizon",
        "intervals",
        "efficiency",
        "capacity",
        "max_power",
        "subproblems",
        "questions",
        "constraints",
        "case_dir",
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
