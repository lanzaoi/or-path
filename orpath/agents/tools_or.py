#!/usr/bin/env python3
"""LangChain Tools around the OR-Path solver stack (``tools/solve_dispatch.py``).

Wraps the hardcore OR solver library plus a Python sandbox as four standard
``langchain_core.tools`` ``@tool`` functions so any LangChain / LangGraph agent
(``langgraph-supervisor``, ``create_react_agent``, MCP-style binders) can
discover and call them:

  * ``list_available_solvers``  — which solver families / modes are registered
  * ``execute_or_solver``       — run any registered solver mode on a problem
  * ``validate_solution_tool``  — independent recompute validation
  * ``execute_python_sandbox``  — controlled ``python -c`` subprocess

Numbers Truth: objective values returned by ``execute_or_solver`` come strictly
from the adapter under ``tools/`` and are independently recomputed by
``validate_solution_tool`` (``tools/validate_solution.py``). This module never
invents optima — it only transports solver output and reports failure verbatim.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# Package layout: <root>/orpath/agents/tools_or.py → root is parents[2],
# the tools/ package sits beside it. Put both on sys.path so this module works
# whether it is imported as ``orpath.agents.tools_or`` or loaded by path.
ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "tools"
for _p in (str(ROOT), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langchain_core.tools import BaseTool, tool  # noqa: E402

try:  # preferred: package import (``tools.solve_dispatch``)
    from tools.solve_dispatch import (  # noqa: E402
        ADAPTER_SCRIPTS,
        list_adapters,
        solve as dispatch_solve,
        validate as dispatch_validate,
    )
except ImportError:  # pragma: no cover - flat-tools/ standalone installs
    from solve_dispatch import (  # type: ignore  # noqa: E402
        ADAPTER_SCRIPTS,
        list_adapters,
        solve as dispatch_solve,
        validate as dispatch_validate,
    )

__all__ = [
    "ALL_OR_TOOLS",
    "OR_TOOLS",
    "SKILL_TOOLS",
    "consult_or_skill",
    "execute_or_solver",
    "execute_python_sandbox",
    "get_or_tools",
    "get_problem_formulation_template",
    "list_available_solvers",
    "validate_solution_tool",
]

#: Default wall-clock budget for ``execute_python_sandbox``.
SANDBOX_DEFAULT_TIMEOUT_SEC = 30

#: Readable algorithm-family label per adapter script (falls back to the
#: script stem minus the ``solve_`` prefix / ``.py`` suffix).
_ADAPTER_FAMILY_LABELS: dict[str, str] = {
    "solve_mock.py": "mock",
    "solve_networkx.py": "networkx",
    "solve_cpsat.py": "cpsat",
    "solve_highs.py": "highs",
    "solve_ortools.py": "ortools",
    "solve_tube_cut_b2026.py": "tube",
    "solve_polyomino.py": "polyomino",
    "solve_microgrid.py": "microgrid",
    "solve_jssp.py": "jssp",
    "solve_binpack.py": "binpack",
    "solve_facility.py": "facility_location",
    "solve_portfolio.py": "portfolio",
    "solve_network_flow.py": "network_flow",
    "solve_qubo_ising.py": "qubo_ising",
    "solve_rcpsp.py": "rcpsp",
    "solve_staff_rostering.py": "staff_rostering",
    "solve_pyvrp.py": "pyvrp",
    "solve_lot_sizing.py": "lot_sizing",
    "solve_qap.py": "qap",
    "solve_graph_coloring.py": "graph_coloring",
    "solve_stochastic_lp.py": "stochastic_lp",
    "solve_max_clique.py": "max_clique",
    "solve_game_theory.py": "game_theory",
    "solve_hub_location.py": "hub_location",
}


def _json(payload: dict[str, Any]) -> str:
    """Serialize a tool payload (never raises on odd values)."""
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _resolve_root() -> Path:
    """Resolve active case workdir (honouring ORPATH_WORKDIR) or fall back to cwd."""
    raw = (os.environ.get("ORPATH_WORKDIR") or "").strip().strip('"')
    if raw:
        try:
            from orpath.paths import orpath_home

            raw_path = Path(raw).expanduser().resolve()
            home_path = orpath_home().resolve()
            cwd_path = Path.cwd().resolve()
            # If ORPATH_WORKDIR was polluted with home but cwd is an isolated test/case dir, prefer cwd.
            if raw_path == home_path and cwd_path != home_path:
                return cwd_path
            return raw_path
        except Exception:
            return Path(raw).expanduser().resolve()
    return Path.cwd()


def _registered_modes() -> dict[str, str]:
    """mode → adapter script, tolerating a missing ``ADAPTER_SCRIPTS`` attr."""
    try:
        if ADAPTER_SCRIPTS:
            return dict(ADAPTER_SCRIPTS)
        return dict(list_adapters())
    except Exception:  # pragma: no cover - defensive
        return {}


def _family_label(adapter: str) -> str:
    return _ADAPTER_FAMILY_LABELS.get(adapter) or adapter.removeprefix("solve_").removesuffix(".py")


@tool
def list_available_solvers() -> str:
    """List every OR-Path solver family and mode registered in tools/solve_dispatch.py.

    Call this first to discover what ``mode`` values ``execute_or_solver`` accepts.
    Returns a JSON document with the full mode table plus one entry per algorithm
    family (tsP/routing, jssp, binpack, facility, network_flow, tube, polyomino,
    microgrid, ...) grouped by adapter script.

    Returns:
        JSON string: ``{"success": true, "total_modes": N, "modes": [...],
        "families": [{"family", "adapter", "adapter_present", "modes"}]}``.
    """
    modes = _registered_modes()
    families: dict[str, dict[str, Any]] = {}
    for mode, adapter in modes.items():
        entry = families.setdefault(
            adapter,
            {
                "family": _family_label(adapter),
                "adapter": adapter,
                "adapter_path": str(TOOLS_DIR / adapter),
                "modes": [],
            },
        )
        entry["modes"].append(mode)

    families_out: list[dict[str, Any]] = []
    for adapter in sorted(families):
        entry = families[adapter]
        entry["modes"] = sorted(entry["modes"])
        entry["adapter_present"] = (TOOLS_DIR / adapter).is_file()
        families_out.append(entry)

    return _json(
        {
            "success": True,
            "total_modes": len(modes),
            "total_families": len(families_out),
            "modes": sorted(modes),
            "families": families_out,
        }
    )


@tool
def execute_or_solver(
    problem_id: str,
    mode: str,
    extra_args: str = "",
    slug: str = "",
) -> str:
    """Run an OR-Path solver for a problem and return its solution envelope.

    Dispatches to ``tools/solve_dispatch.py``, which routes ``mode`` to the right
    adapter under ``tools/`` (networkx, cpsat, highs, ortools, jssp, binpack,
    facility, network_flow, tube, polyomino, microgrid, pyvrp, qap, ...).

    On success the normalized solution dict is also persisted to
    ``outputs/<slug>-solution.json`` and the absolute/relative path is echoed
    back as ``solution_path`` so downstream tools (``validate_solution_tool``)
    can pick it up without another file handoff.

    Args:
        problem_id: Fixture / instance id, e.g. ``shortest_path``, ``tsp_n8``,
            ``jssp_taillard_67``. Some modes (tube, microgrid, staff_rostering)
            ignore it and rely on ``extra_args``.
        mode: Solver mode registered in ``tools/solve_dispatch.py``. Unknown
            modes fall back to ``ortools`` auto-routing, so a typo can still run.
        extra_args: Optional whitespace-separated extra CLI args forwarded
            verbatim to the adapter, e.g. ``--timeout 60 --gap 0.01``.
        slug: Optional file slug used for the persisted solution JSON. Defaults
            to ``problem_id`` when omitted or blank.

    Returns:
        JSON string with ``success`` (bool), ``solution`` (the normalized
        solution dict, ``{}`` on failure), ``solution_path`` (path to the
        persisted ``outputs/<slug>-solution.json``, ``""`` on failure) and
        ``detail`` (raw adapter stdout / stderr, or the exception message) so
        the agent can report failures without inventing an objective.
    """
    norm_mode = (mode or "").strip().lower()
    # Unknown modes are not rejected here: solve_dispatch auto-routes generic
    # problem classes, and any failure is surfaced through ``detail``.
    extra = extra_args.split() if extra_args else None
    root = _resolve_root()
    out_slug = (slug or "").strip() or problem_id
    out_path = Path("outputs") / f"{out_slug}-solution.json"
    target_path = root / out_path
    try:
        ok, solution, detail = dispatch_solve(
            root=root,
            problem_id=problem_id,
            mode=mode,
            extra_args=extra,
        )
    except Exception as exc:  # noqa: BLE001 - tools must never raise
        return _json(
            {
                "success": False,
                "problem_id": problem_id,
                "mode": mode,
                "solution": {},
                "solution_path": "",
                "detail": f"{type(exc).__name__}: {exc}",
            }
        )
    if bool(ok) and isinstance(solution, dict) and solution:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(_json(solution), encoding="utf-8")
    return _json(
        {
            "success": bool(ok),
            "problem_id": problem_id,
            "mode": norm_mode,
            "solution": solution,
            "solution_path": str(out_path) if bool(ok) and isinstance(solution, dict) and solution else "",
            "detail": detail,
        }
    )


@tool
def validate_solution_tool(problem_id: str, solution_path: str, output_path: str = "") -> str:
    """Independently recompute-check a solution JSON against its raw problem data.

    Delegates to ``tools/validate_solution.py`` via ``tools/solve_dispatch.validate``
    — the single validation seam of the project (Numbers Truth). A solver claim is
    only trusted once this tool reports ``ok``.

    Args:
        problem_id: Problem / fixture id used to locate the problem data and to
            name the default validation report.
        solution_path: Path to the ``solution.json`` to validate.
        output_path: Where to write the validation report. Defaults to
            ``<solution_path parent>/<problem_id>-validation.json``.

    Returns:
        JSON string with ``success``, ``ok`` (validator verdict), ``validation``
        (the validator report incl. per-check ``ok`` flags and recomputed
        objectives), ``output_path`` and ``detail`` (raw stdout/stderr).
    """
    root = _resolve_root()
    solution = Path(solution_path)
    if not solution.is_absolute():
        solution = root / solution
    out = Path(output_path) if output_path else solution.parent / f"{problem_id}-validation.json"
    if not out.is_absolute():
        out = root / out
    try:
        ok, data, detail = dispatch_validate(
            root=root,
            problem_id=problem_id,
            solution=solution,
            out=out,
        )
    except Exception as exc:  # noqa: BLE001 - tools must never raise
        return _json(
            {
                "success": False,
                "ok": False,
                "problem_id": problem_id,
                "solution_path": str(solution),
                "output_path": str(out),
                "validation": {},
                "detail": f"{type(exc).__name__}: {exc}",
            }
        )
    verdict = bool(data.get("ok")) if isinstance(data, dict) else False
    errors = (data.get("errors") or []) if isinstance(data, dict) else []
    checks = (data.get("checks") or []) if isinstance(data, dict) else []
    failed_checks = [c for c in checks if isinstance(c, dict) and not c.get("ok")]
    violations = [
        f"{c.get('name')}: {c.get('error') or c.get('detail') or 'failed'}"
        for c in failed_checks
    ] or [str(e) for e in errors]
    return _json(
        {
            "success": bool(ok) and verdict,
            "ok": verdict,
            "problem_id": problem_id,
            "solution_path": str(solution),
            "output_path": str(out),
            "validation": data,
            "constraint_violations": violations,
            "detail": detail,
        }
    )


@tool
def execute_python_sandbox(code: str, timeout_sec: int = SANDBOX_DEFAULT_TIMEOUT_SEC) -> str:
    """Execute a Python modelling snippet in a controlled subprocess.

    Runs ``sys.executable -c <code>`` with a wall-clock timeout and captures the
    result. Use it for exploratory modelling (building a graph, formatting a
    CP-SAT model, checking a fixture) before committing to a real solver run.
    The subprocess inherits the current working directory and environment.

    Args:
        code: Python source to execute, e.g. ``print(sum(range(10)))``.
        timeout_sec: Wall-clock timeout in seconds. Must be a positive integer.

    Returns:
        JSON string with ``success`` (bool, ``returncode == 0``), ``returncode``,
        ``stdout``, ``stderr`` and the ``timeout_sec`` actually used. On timeout
        ``success`` is false, ``returncode`` is null and ``timed_out`` is true.
    """
    try:
        timeout = int(timeout_sec)
    except (TypeError, ValueError):
        return _json(
            {
                "success": False,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "detail": f"timeout_sec must be an int, got {timeout_sec!r}",
            }
        )
    if timeout <= 0:
        return _json(
            {
                "success": False,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "detail": f"timeout_sec must be > 0, got {timeout}",
            }
        )

    root = _resolve_root()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return _json(
            {
                "success": False,
                "returncode": None,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "timed_out": True,
                "timeout_sec": timeout,
                "detail": f"sandbox timed out after {timeout}s",
            }
        )
    except Exception as exc:  # noqa: BLE001 - tools must never raise
        return _json(
            {
                "success": False,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "timeout_sec": timeout,
                "detail": f"{type(exc).__name__}: {exc}",
            }
        )

    return _json(
        {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "timed_out": False,
            "timeout_sec": timeout,
        }
    )


#: Every OR tool, ready for ``llm.bind_tools(OR_TOOLS)`` / ``create_tool_node``.
OR_TOOLS: tuple[BaseTool, ...] = (
    list_available_solvers,
    execute_or_solver,
    validate_solution_tool,
    execute_python_sandbox,
)


@tool
def consult_or_skill(topic: str, subtopic: str | None = None) -> str:
    """Consult the restored OR skill handbook and algorithm developer references.

    Searches knowledge/skills/ and knowledge/skills/references/ for algorithm guides,
    formulation patterns, solver best practices, and recipes.

    Args:
        topic: Search query or skill topic name (e.g. 'routing', 'cvrp', 'scheduling',
            'jssp', 'linear', 'mip', 'heuristics', 'alns', 'pyvrp', 'pyjobshop',
            'cuopt', 'production', 'inventory', 'polyomino', 'tube', 'microgrid', 'big-m').
        subtopic: Optional specific section header or subtopic to locate inside the skill.

    Returns:
        JSON string containing success, topic, matched_files, and relevant content/sections.
    """
    if not topic or not str(topic).strip():
        return _json({"success": False, "detail": "topic must not be empty"})

    root = _resolve_root()
    skills_dirs = [root / "knowledge" / "skills", ROOT / "knowledge" / "skills"]
    base_skills_dir = next((d for d in skills_dirs if d.is_dir()), None)
    if base_skills_dir is None:
        return _json({"success": False, "detail": "knowledge/skills directory not found"})

    query = str(topic).strip().lower()
    sub = str(subtopic).strip().lower() if subtopic else ""

    alias_map: dict[str, list[str]] = {
        "routing": ["references/routing_scheduling_and_networks.md", "pyvrp-engine/SKILL.md"],
        "vrp": ["references/routing_scheduling_and_networks.md", "pyvrp-engine/SKILL.md"],
        "cvrp": ["pyvrp-engine/SKILL.md", "references/routing_scheduling_and_networks.md"],
        "pyvrp": ["pyvrp-engine/SKILL.md"],
        "scheduling": ["references/routing_scheduling_and_networks.md", "pyjobshop-scheduling/SKILL.md"],
        "jssp": ["pyjobshop-scheduling/SKILL.md", "references/routing_scheduling_and_networks.md"],
        "pyjobshop": ["pyjobshop-scheduling/SKILL.md"],
        "production": ["production-scheduling/SKILL.md"],
        "inventory": ["inventory-demand-planning/SKILL.md"],
        "mip": ["references/linear_and_integer_optimization.md", "or-problems.md"],
        "lp": ["references/linear_and_integer_optimization.md", "or-problems.md"],
        "linear": ["references/linear_and_integer_optimization.md"],
        "heuristics": ["references/heuristics_and_metaheuristics.md", "alns-metaheuristic/SKILL.md"],
        "metaheuristics": ["references/heuristics_and_metaheuristics.md", "alns-metaheuristic/SKILL.md"],
        "alns": ["alns-metaheuristic/SKILL.md"],
        "solver": ["references/solver_integration_and_production.md"],
        "cuopt": ["cuopt-routing-api-python/SKILL.md", "cuopt-numerical-optimization-api/SKILL.md"],
        "formulation": ["references/problem_formulation_and_data.md", "or-problems.md"],
        "scope": ["references/or_algorithm_developer_scope.md"],
        "truth": ["or-numbers-truth/SKILL.md"],
        "numbers_truth": ["or-numbers-truth/SKILL.md"],
        "memory": ["or-process-memory/SKILL.md"],
        "process_memory": ["or-process-memory/SKILL.md"],
    }

    candidate_files: list[Path] = []
    for k, paths in alias_map.items():
        if k in query or query in k:
            for rel in paths:
                p = base_skills_dir / rel
                if p.is_file() and p not in candidate_files:
                    candidate_files.append(p)

    if not candidate_files:
        for p in sorted(base_skills_dir.rglob("*.md")):
            name_low = p.name.lower()
            parent_low = p.parent.name.lower()
            if query in name_low or query in parent_low:
                candidate_files.append(p)

    if not candidate_files:
        for p in sorted(base_skills_dir.rglob("*.md")):
            try:
                head = p.read_text(encoding="utf-8", errors="ignore")[:3000].lower()
                if query in head:
                    candidate_files.append(p)
                    if len(candidate_files) >= 5:
                        break
            except Exception:
                pass

    if not candidate_files:
        available_skills = [
            p.name for p in sorted(base_skills_dir.iterdir()) if p.is_dir()
        ]
        return _json({
            "success": False,
            "topic": topic,
            "detail": f"no skill found matching topic {topic!r}",
            "available_skills": available_skills,
        })

    target_file = candidate_files[0]
    full_text = target_file.read_text(encoding="utf-8", errors="replace")

    extracted_section = ""
    if sub:
        lines = full_text.splitlines()
        capturing = False
        captured_lines: list[str] = []
        capture_level = 2
        for line in lines:
            if line.startswith("#"):
                h_level = len(line.split()[0])
                h_text = line.lower()
                if sub in h_text:
                    capturing = True
                    capture_level = h_level
                    captured_lines.append(line)
                    continue
                elif capturing and h_level <= capture_level:
                    break
            if capturing:
                captured_lines.append(line)
        if captured_lines:
            extracted_section = "\n".join(captured_lines)

    content = extracted_section if extracted_section else full_text[:6000]

    return _json({
        "success": True,
        "topic": topic,
        "subtopic": subtopic or "",
        "skill_file": str(target_file.relative_to(base_skills_dir.parent)),
        "all_matched_files": [str(f.relative_to(base_skills_dir.parent)) for f in candidate_files[:5]],
        "content": content,
    })


@tool
def get_problem_formulation_template(problem_class: str) -> str:
    """Extract standard LaTeX mathematical programming formulations from or-problems.md.

    Provides canonical decision variables, objective functions, numbered constraints,
    and modeling notes for standard OR problem classes:
      * LP, MIP, IP, NLP
      * TSP, VRP, CVRP, VRPTW
      * Bin Packing, Cutting Stock, Tube Cut
      * Scheduling, JSSP, FJSSP, RCPSP
      * Shortest Path, Max Flow, Min Cost Flow, MST
      * Facility Location, Network Design
      * Newsvendor, Stochastic LP, Inventory / EOQ
      * Microgrid, Demand Response, Game Theory, Multi-Objective

    Args:
        problem_class: Problem category identifier, e.g. 'tsp', 'cvrp', 'jssp',
            'binpack', 'facility_location', 'microgrid', 'shortest_path'.

    Returns:
        JSON string containing success, problem_class, category, latex_formulation,
        variables, constraints, and modeling_notes.
    """
    if not problem_class or not str(problem_class).strip():
        return _json({"success": False, "detail": "problem_class must not be empty"})

    root = _resolve_root()
    skills_dirs = [root / "knowledge" / "skills", ROOT / "knowledge" / "skills"]
    base_skills_dir = next((d for d in skills_dirs if d.is_dir()), None)
    if base_skills_dir is None:
        return _json({"success": False, "detail": "knowledge/skills directory not found"})

    handbook = base_skills_dir / "or-problems.md"
    if not handbook.is_file():
        handbook = base_skills_dir / "or-modeling" / "references" / "or-problems.md"
    if not handbook.is_file():
        return _json({"success": False, "detail": "or-problems.md not found in knowledge base"})

    text = handbook.read_text(encoding="utf-8", errors="replace")
    sections = re.split(r"\n(?=###? )", text)

    pc_raw = str(problem_class).strip().lower()
    alias_map: dict[str, list[str]] = {
        "shortest_path": ["最短路径", "3.1"],
        "sp": ["最短路径", "3.1"],
        "tsp": ["旅行商", "2.1", "tsp"],
        "vrp": ["车辆路径", "2.2", "vrp"],
        "cvrp": ["车辆路径", "2.2", "vrp"],
        "vrptw": ["车辆路径", "2.2", "vrp"],
        "binpack": ["装箱", "2.3", "bin packing"],
        "bin_packing": ["装箱", "2.3", "bin packing"],
        "cutting_stock": ["装箱", "2.3", "bin packing"],
        "tube": ["装箱", "2.3", "bin packing"],
        "tube_cut": ["装箱", "2.3", "bin packing"],
        "jssp": ["调度问题", "2.4", "scheduling"],
        "fjssp": ["调度问题", "2.4", "scheduling"],
        "scheduling": ["调度问题", "2.4", "scheduling"],
        "facility_location": ["选址", "3.4", "11."],
        "facility": ["选址", "3.4", "11."],
        "cflp": ["选址", "3.4", "11."],
        "max_flow": ["最大流", "3.2"],
        "mst": ["最小生成树", "3.3"],
        "lp": ["线性规划", "1.1", "(lp)"],
        "mip": ["整数规划", "1.2", "(mip)"],
        "ip": ["整数规划", "1.2", "(ip)"],
        "nlp": ["非线性规划", "1.3", "(nlp)"],
        "stochastic": ["随机规划", "4."],
        "newsvendor": ["报童问题", "4.1"],
        "inventory": ["库存优化", "6."],
        "eoq": ["eoq", "6.1"],
        "game_theory": ["博弈论", "9."],
        "mdp": ["马尔可夫决策", "8.2"],
        "dp": ["动态规划", "13."],
        "mpc": ["滚动时域", "13.3"],
        "microgrid": ["滚动时域", "13.3", "17.2"],
        "microgrid_dispatch": ["滚动时域", "13.3", "17.2"],
        "robust": ["鲁棒优化", "14."],
        "multi_objective": ["多目标", "18."],
        "big_m": ["大m法"],
        "linearization": ["线性化技巧"],
    }

    match_keys = alias_map.get(pc_raw) or [pc_raw]

    matched_sec = None
    for sec in sections:
        header = sec.splitlines()[0].lower() if sec.splitlines() else ""
        if any(k.lower() in header for k in match_keys):
            matched_sec = sec
            break

    if not matched_sec:
        for sec in sections:
            sec_low = sec.lower()
            if any(k.lower() in sec_low for k in match_keys):
                matched_sec = sec
                break

    if not matched_sec:
        supported = sorted(list(alias_map.keys()))
        return _json({
            "success": False,
            "problem_class": problem_class,
            "detail": f"no formulation found for {problem_class!r}",
            "supported_classes": supported,
        })

    latex_matches = re.findall(r"```latex\s*\n(.*?)\n```", matched_sec, re.DOTALL)
    latex_formula = "\n\n".join(latex_matches) if latex_matches else ""

    lines = matched_sec.splitlines()
    header_line = lines[0] if lines else ""

    # Parse decision variables
    vars_list: list[str] = []
    for line in lines:
        s = line.strip()
        if "变量" in s or "variable" in s.lower():
            clean_s = re.sub(r"^\*+|\*+$", "", s).strip()
            vars_list.append(clean_s)
    if not vars_list and latex_formula:
        for line in latex_formula.splitlines():
            if any(term in line for term in (r"\in \{0, 1\}", r"\in \{0,1\}", r"\geq 0", r"\ge 0", r"\in \mathbb{R}", r"\in \mathbb{Z}")):
                clean_v = line.strip().lstrip("&").strip().rstrip(r"\\").strip()
                if clean_v and clean_v not in vars_list:
                    vars_list.append(f"${clean_v}$")
    variables_text = "\n".join(f"- {v}" for v in vars_list) if vars_list else "- Decision variables declared in mathematical formulation."

    # Parse constraints
    constraints_list: list[str] = []
    cons_idx = 1
    for m in re.finditer(r"\\text\{\((.*?)\)\}", latex_formula):
        c_label = m.group(1).strip()
        if c_label and c_label not in constraints_list:
            constraints_list.append(f"C{cons_idx}: {c_label}")
            cons_idx += 1
    for line in lines:
        s = line.strip()
        if s.startswith("- ") and ("约束" in s or "constraint" in s.lower()):
            clean_c = s.lstrip("- ").strip()
            if clean_c not in constraints_list:
                constraints_list.append(f"C{cons_idx}: {clean_c}")
                cons_idx += 1
    if not constraints_list and r"\text{s.t.}" in latex_formula:
        constraints_list.append("C1: System balance, capacity, and operational bounds as formulated in LaTeX.")
    constraints_text = "\n".join(f"- {c}" for c in constraints_list) if constraints_list else "- Structural constraints specified in formulation."

    # Parse modeling notes
    notes_list: list[str] = []
    for line in lines:
        s = line.strip()
        if any(k in s for k in ("变体", "特征", "说明", "算法", "求解器", "复杂度", "注意")):
            clean_n = re.sub(r"^\*+|\*+$", "", s).strip()
            if clean_n and clean_n not in notes_list:
                notes_list.append(clean_n)
    modeling_notes_text = "\n".join(f"- {n}" for n in notes_list) if notes_list else "- Standard mathematical programming formulation conforming to OR literature."

    return _json({
        "success": True,
        "problem_class": problem_class,
        "section_title": header_line.lstrip("#").strip(),
        "latex_formulation": latex_formula,
        "variables": variables_text,
        "constraints": constraints_text,
        "modeling_notes": modeling_notes_text,
        "content": matched_sec,
    })


#: Dedicated OR skill tools for literature, formulation templates and reference querying.
SKILL_TOOLS: tuple[BaseTool, ...] = (
    consult_or_skill,
    get_problem_formulation_template,
)

#: Complete suite of OR-Path solver and skill tools.
ALL_OR_TOOLS: tuple[BaseTool, ...] = OR_TOOLS + SKILL_TOOLS


def get_or_tools(include_skills: bool = False) -> list[BaseTool]:
    """Return the OR tool list (mutable copy, handy for agent wiring)."""
    return list(ALL_OR_TOOLS if include_skills else OR_TOOLS)


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    print(list_available_solvers.invoke({}))
