"""OR-Path tool catalog — single inventory for agents, MCP, and docs generators."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

ToolKind = Literal["solve", "validate", "gate", "intake", "paper", "memory", "meta"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    kind: ToolKind
    script: str
    summary: str
    auto_in_pipeline: bool
    mcp_expose: bool  # whitelist for MCP server
    solve_modes: tuple[str, ...] = ()


# Product tools — keep mcp_expose narrow (read/meta/memory first).
TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "solve_dispatch",
        "solve",
        "tools/solve_dispatch.py",
        "Unified solve entry — mode adapters (networkx/cpsat/highs/ortools/polyomino/tube/mock)",
        True,
        False,
        ("mock", "networkx", "cpsat", "highs", "ortools", "polyomino", "tube"),
    ),
    ToolSpec(
        "solve_networkx",
        "solve",
        "tools/solve_networkx.py",
        "Shortest path Dijkstra exact",
        True,
        False,
        ("networkx",),
    ),
    ToolSpec(
        "solve_cpsat",
        "solve",
        "tools/solve_cpsat.py",
        "TSP CP-SAT exact (small n)",
        True,
        False,
        ("cpsat",),
    ),
    ToolSpec(
        "solve_highs",
        "solve",
        "tools/solve_highs.py",
        "TSP/tiny MIP exact via HiGHS",
        True,
        False,
        ("highs",),
    ),
    ToolSpec(
        "solve_ortools",
        "solve",
        "tools/solve_ortools.py",
        "Routing search — not proven optimal",
        True,
        False,
        ("ortools",),
    ),
    ToolSpec(
        "solve_polyomino",
        "solve",
        "tools/solve_polyomino.py",
        "Polyomino cover adapter",
        True,
        False,
        ("polyomino",),
    ),
    ToolSpec(
        "solve_tube",
        "solve",
        "tools/solve_tube_cut_b2026.py",
        "Tube cut BFD heuristic",
        True,
        False,
        ("tube",),
    ),
    ToolSpec(
        "solve_mock",
        "solve",
        "tools/solve_mock.py",
        "Fixture mock for CI",
        True,
        False,
        ("mock",),
    ),
    ToolSpec(
        "validate_solution",
        "validate",
        "tools/validate_solution.py",
        "Recompute / feasibility — numbers truth",
        True,
        True,
    ),
    ToolSpec(
        "gate_schema",
        "gate",
        "tools/gate_schema.py",
        "Schema gate — ban solution-shaped optima",
        True,
        False,
    ),
    ToolSpec(
        "intake_ocr",
        "intake",
        "tools/intake_ocr.py",
        "Problem intake OCR (no solve)",
        True,
        False,
    ),
    ToolSpec(
        "r1_cite_check",
        "paper",
        "tools/r1_cite_check.py",
        "Citation / claim checks",
        True,
        False,
    ),
    ToolSpec(
        "r2_numeric_check",
        "paper",
        "tools/r2_numeric_check.py",
        "Paper numeric consistency vs solution",
        True,
        False,
    ),
    ToolSpec(
        "process_memory_search",
        "memory",
        "orpath/process_memory.py",
        "Search past solve process lessons (not optima)",
        True,
        True,
    ),
    ToolSpec(
        "process_memory_record",
        "memory",
        "orpath/process_memory.py",
        "Record process lesson after a run",
        True,
        True,
    ),
    ToolSpec(
        "list_solvers",
        "meta",
        "orpath/tool_catalog.py",
        "List solve modes and claim ladder",
        False,
        True,
    ),
)



# Optional engines (pip-installed from OSS; not default dispatch modes)
OPTIONAL_ENGINES: tuple[ToolSpec, ...] = (
    ToolSpec("pyvrp", "solve", "pyvrp (pip)", "SOTA VRP HGS — optional, not default claim ladder", False, False, ()),
    ToolSpec("pyjobshop", "solve", "pyjobshop (pip)", "Job-shop CP scheduling", False, False, ()),
    ToolSpec("alns", "solve", "ALNS (pip)", "Adaptive LNS metaheuristic framework", False, False, ()),
    ToolSpec("vrplib", "meta", "vrplib (pip)", "VRP benchmark instance IO", False, False, ()),
    ToolSpec("stockpyl", "meta", "stockpyl (pip)", "Inventory optimization models", False, False, ()),
    ToolSpec("pulp", "meta", "pulp (pip)", "LP/MIP modeling API", False, False, ()),
    ToolSpec("mcp_ortools", "meta", "third_party/mcp-ortools", "OR-Tools MCP server", False, True, ()),
    ToolSpec("highs_mcp", "meta", "third_party/highs-mcp", "HiGHS MCP server (npm)", False, True, ()),
)


def list_tools(*, mcp_only: bool = False, include_optional: bool = True) -> list[dict[str, Any]]:
    rows = []
    pool = list(TOOLS) + (list(OPTIONAL_ENGINES) if include_optional else [])
    for t in pool:
        if mcp_only and not t.mcp_expose:
            continue
        rows.append(asdict(t))
    return rows


def solver_claim_table() -> list[dict[str, str]]:
    return [
        {"problem_class": "shortest_path", "default_mode": "networkx", "claim": "exact"},
        {"problem_class": "tsp", "default_mode": "cpsat", "claim": "exact; highs dual"},
        {"problem_class": "vrp", "default_mode": "ortools", "claim": "feasible not proven"},
        {"problem_class": "polyomino_cover", "default_mode": "polyomino", "claim": "adapter/CP-SAT"},
        {"problem_class": "tube_cut", "default_mode": "tube", "claim": "heuristic FEASIBLE"},
    ]


def default_mode_for_class(problem_class: str) -> str:
    pc = (problem_class or "").strip().lower()
    for row in solver_claim_table():
        if row["problem_class"] == pc:
            return row["default_mode"]
    if pc in {"vrp_tw", "cvrp"}:
        return "ortools"
    return "mock"


if __name__ == "__main__":
    import json

    print(json.dumps({"tools": list_tools(), "solvers": solver_claim_table()}, indent=2))
