#!/usr/bin/env python3
"""Unified solve dispatch — one interface, many adapters (ADR-0002).

Callers (orpath.gates, CLIs) should use ``solve()`` / ``validate()`` here
instead of hard-coding tools/solve_*.py names.
"""
from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# tools/ on path when run as script
_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from solve_envelope import normalize_solution, validate_envelope  # noqa: E402

# mode → adapter script under tools/
ADAPTER_SCRIPTS: dict[str, str] = {
    "mock": "solve_mock.py",
    "networkx": "solve_networkx.py",
    "cpsat": "solve_cpsat.py",
    "highs": "solve_highs.py",
    "ortools": "solve_ortools.py",
    "tube": "solve_tube_cut_b2026.py",
    "tube_cut": "solve_tube_cut_b2026.py",
    "tube_bfd": "solve_tube_cut_b2026.py",
    # M2 phase 1: polyomino product registration
    "polyomino": "solve_polyomino.py",
    "polyomino_cover": "solve_polyomino.py",
    "poly": "solve_polyomino.py",
    # Microgrid industrial solver registration
    "microgrid": "solve_microgrid.py",
    "microgrid_dispatch": "solve_microgrid.py",
    # Extended 6 industrial solvers
    "jssp": "solve_jssp.py",
    "job_shop": "solve_jssp.py",
    "fjssp": "solve_jssp.py",
    "bin_packing": "solve_binpack.py",
    "binpack": "solve_binpack.py",
    "facility_location": "solve_facility.py",
    "facility": "solve_facility.py",
    "portfolio_opt": "solve_portfolio.py",
    "portfolio": "solve_portfolio.py",
    "network_flow": "solve_network_flow.py",
    "qubo_ising": "solve_qubo_ising.py",
    "qubo": "solve_qubo_ising.py",
    # RCPSP project scheduling (PSPLib *.sm via CP-SAT)
    "rcpsp": "solve_rcpsp.py",
    # Staff rostering (shift scheduling, CP-SAT)
    "staff_rostering": "solve_staff_rostering.py",
    # Advanced VRP / PDP (PyVRP + VRPLIB)
    "pyvrp": "solve_pyvrp.py",
    "vrp_pdp": "solve_pyvrp.py",
    "pdp": "solve_pyvrp.py",
    "vrptw": "solve_pyvrp.py",
    # Multi-period lot sizing (WW-DP / SCIP CLSP)
    "lot_sizing": "solve_lot_sizing.py",
    "inventory_planning": "solve_lot_sizing.py",
    "wagner_whitin": "solve_lot_sizing.py",
    "clsp": "solve_lot_sizing.py",
    "mrp": "solve_lot_sizing.py",
    # Quadratic Assignment Problem (facility layout, SciPy FAQ + 2-opt)
    "qap": "solve_qap.py",
    "quadratic_assignment": "solve_qap.py",
    "facility_layout": "solve_qap.py",
    "qaplib": "solve_qap.py",
    # Graph coloring (chromatic number, DIMACS .col, DSATUR + CP-SAT)
    "graph_coloring": "solve_graph_coloring.py",
    "vertex_coloring": "solve_graph_coloring.py",
    "vcp": "solve_graph_coloring.py",
    "coloring": "solve_graph_coloring.py",
    "dimacs_col": "solve_graph_coloring.py",
    # Two-Stage Stochastic LP (Birge & Louveaux Farmer Problem)
    "stochastic_lp": "solve_stochastic_lp.py",
    "stochastic_programming": "solve_stochastic_lp.py",
    "stochastic": "solve_stochastic_lp.py",
    "two_stage_lp": "solve_stochastic_lp.py",
    "farmer": "solve_stochastic_lp.py",
    "farmer_problem": "solve_stochastic_lp.py",
    # Max Clique / Max Independent Set (NetworkX + CP-SAT, DIMACS .col)
    "max_clique": "solve_max_clique.py",
    "clique": "solve_max_clique.py",
    "maximum_clique": "solve_max_clique.py",
    "max_independent_set": "solve_max_clique.py",
    "mis": "solve_max_clique.py",
    "independent_set": "solve_max_clique.py",
    # Bimatrix game / Nash equilibrium (nashpy)
    "game_theory": "solve_game_theory.py",
    "game": "solve_game_theory.py",
    "nash": "solve_game_theory.py",
    "nash_equilibrium": "solve_game_theory.py",
    "bimatrix": "solve_game_theory.py",
    # p-Hub Location Problem (CAB benchmarks, OR-Tools MIP)
    "hub_location": "solve_hub_location.py",
    "hub": "solve_hub_location.py",
    "hlp": "solve_hub_location.py",
    "p_hub": "solve_hub_location.py",
    "phub": "solve_hub_location.py",
    "usahlp": "solve_hub_location.py",
}


def _run_py(script: Path, args: list[str], cwd: Path) -> tuple[int, str, str]:
    cmd = [sys.executable, str(script), *args]
    env = os.environ.copy()
    env["ORPATH_WORKDIR"] = str(cwd)
    try:
        r = subprocess.run(
            cmd, cwd=cwd, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=120
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"subprocess timed out after 120s: {' '.join(str(c) for c in cmd)}"


def _try_in_proc(script_name: str, args: list[str]) -> tuple[bool, int, str, str]:
    mod_name = script_name.replace(".py", "")
    try:
        mod = importlib.import_module(mod_name)
        if hasattr(mod, "main"):
            buf_out = io.StringIO()
            buf_err = io.StringIO()
            with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
                try:
                    code = mod.main(args)
                    if code is None:
                        code = 0
                except SystemExit as se:
                    code = se.code if isinstance(se.code, int) else (0 if se.code is None else 1)
                except Exception:
                    return False, -1, "", ""
            return True, code, buf_out.getvalue(), buf_err.getvalue()
    except Exception:
        pass
    return False, -1, "", ""


def _find_case_dir(
    root: Path | None,
    problem_id: str | None,
    mode: str | None = None,
) -> Path | None:
    """Find case directory under inbox/<problem_id> or inbox/<slug> in root or cwd."""
    roots: list[Path] = []
    if root is not None:
        try:
            roots.append(Path(root).resolve())
        except Exception:
            pass
    try:
        cwd = Path.cwd().resolve()
        if cwd not in roots:
            roots.append(cwd)
    except Exception:
        pass
    try:
        install_root = _ROOT.resolve()
        if install_root not in roots:
            roots.append(install_root)
    except Exception:
        pass

    pid = (problem_id or "").strip()
    mode_l = (mode or "").strip().lower()
    slugs: list[str] = []
    if pid:
        slugs.append(pid)
        slugs.append(pid.lower())
        cleaned = pid.lower()
        for prefix in ("microgrid_", "microgrid-", "microgrid", "tube_", "tube-", "tube"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip("_-")
        if cleaned and cleaned not in slugs:
            slugs.append(cleaned)

        parts = [p for p in pid.replace("-", "_").split("_") if p]
        if parts:
            last = parts[-1].lower()
            slugs.extend([
                last,
                f"problem_{last}",
                f"Problem_{last.upper()}",
                f"{last.upper()}题",
                f"{last}题",
                last.upper(),
            ])
            if len(parts) >= 2:
                sub = "_".join(parts[1:])
                slugs.append(sub)
                slugs.append(sub.lower())

    # Mode-based and domain-based candidate slugs
    is_microgrid = mode_l in ("microgrid", "microgrid_dispatch") or "microgrid" in pid.lower()
    is_tube = mode_l in ("tube", "tube_cut", "tube_bfd") or "tube" in pid.lower()

    if is_microgrid:
        slugs.extend([
            "microgrid",
            "cumcm2026_c",
            "Problem_C",
            "problem_c",
            "C题",
            "c题",
            "case_c",
            "case-c",
        ])
    if is_tube:
        slugs.extend([
            "tube",
            "tube_cut",
            "cumcm2026_b",
            "Problem_B",
            "problem_b",
            "B题",
            "b题",
            "case_b",
            "case-b",
        ])

    seen_slugs: set[str] = set()
    unique_slugs: list[str] = []
    for s in slugs:
        if s and s not in seen_slugs:
            seen_slugs.add(s)
            unique_slugs.append(s)

    for base in roots:
        inbox = base / "inbox"
        if not inbox.is_dir():
            continue
        # Pass 1: exact slug match
        for slug in unique_slugs:
            cand = inbox / slug
            if cand.is_dir():
                return cand.resolve()

        # Pass 2: semantic directory scan
        try:
            for item in sorted(inbox.iterdir()):
                if not item.is_dir():
                    continue
                name_l = item.name.lower()
                # Exact case-insensitive match
                if pid and name_l == pid.lower():
                    return item.resolve()
                # Domain matches
                if is_microgrid and (
                    any(k in name_l for k in ("microgrid", "cumcm2026_c", "problem_c", "c题"))
                    or name_l in ("c", "case_c", "case-c")
                ):
                    return item.resolve()
                if is_tube and (
                    any(k in name_l for k in ("tube", "cumcm2026_b", "problem_b", "b题"))
                    or name_l in ("b", "case_b", "case-b")
                ):
                    return item.resolve()
                # Substring match only with length >= 4 to avoid 1-letter false positives
                if pid and len(pid) >= 4 and len(name_l) >= 4:
                    if pid.lower() in name_l or name_l in pid.lower():
                        return item.resolve()
        except OSError:
            pass
    return None


def _build_args(
    mode: str,
    problem_id: str,
    problem_class: str | None,
    extra_args: list[str] | None,
    root: Path | None = None,
) -> list[str]:
    extra = list(extra_args or [])
    has_case_dir = any(
        a in ("--case-dir", "--case_dir") or a.startswith(("--case-dir=", "--case_dir="))
        for a in extra
    )
    if not has_case_dir and mode in ("microgrid", "microgrid_dispatch", "tube", "tube_cut", "tube_bfd"):
        case_dir = _find_case_dir(root, problem_id, mode=mode)
        if case_dir is not None:
            extra.extend(["--case-dir", str(case_dir)])
    if mode == "mock":
        return [problem_id, *extra]
    if mode == "networkx":
        return [problem_id, *extra]
    if mode in ("cpsat", "highs"):
        return [problem_id, *extra]
    if mode == "ortools":
        args = [problem_id]
        if problem_class:
            args.extend(["--class", problem_class])
        args.extend(extra)
        return args
    if mode in ("tube", "tube_cut", "tube_bfd", "microgrid", "microgrid_dispatch"):
        # batch tools; problem_id unused by CLI today
        return list(extra)
    if mode in ("jssp", "job_shop", "fjssp"):
        if problem_id and not any(a in extra for a in ("--instance", "-i")):
            return ["--instance", problem_id, *extra]
        return list(extra)
    if mode == "rcpsp":
        if problem_id and not any(a in extra for a in ("--instance", "-i")):
            return ["--instance", problem_id, *extra]
        return list(extra)
    if mode in ("qap", "quadratic_assignment", "facility_layout", "qaplib"):
        if problem_id and not any(a in extra for a in ("--fixture", "-f")):
            return ["--fixture", problem_id, *extra]
        return list(extra)
    if mode in ("graph_coloring", "vertex_coloring", "vcp", "coloring", "dimacs_col"):
        if problem_id and not any(a in extra for a in ("--fixture", "-f")):
            return ["--fixture", problem_id, *extra]
        return list(extra)
    if mode in ("lot_sizing", "inventory_planning", "wagner_whitin", "clsp", "mrp"):
        pid_clean = (problem_id or "").lower().replace("lot_sizing_", "")
        if pid_clean in ("ww12", "clsp60") and not any(a in extra for a in ("--benchmark", "-b")):
            return ["--benchmark", pid_clean, *extra]
        return list(extra)
    if mode in ("facility_location", "facility"):
        pid_clean = (problem_id or "").lower().replace("cflp-", "").replace("cflp_", "")
        if pid_clean.startswith("cap") and not any(a in extra for a in ("--benchmark", "-b")):
            return ["--benchmark", pid_clean, *extra]
        return list(extra)
    if mode in ("qubo_ising", "qubo"):
        pid_clean = (problem_id or "").lower()
        if pid_clean in ("max_cut", "number_partitioning", "qubo", "ising"):
            return ["--mode", pid_clean, *extra]
        return list(extra)
    if mode == "network_flow":
        pid_clean = (problem_id or "").lower()
        if pid_clean in ("min_cost_flow", "bipartite_matching", "multi_commodity_flow"):
            return ["--mode", pid_clean, *extra]
        return list(extra)
    if mode in ("bin_packing", "binpack"):
        pid_clean = (problem_id or "").lower()
        if pid_clean in ("3d", "2d", "1d", "binpack_3d", "binpack_2d", "binpack_1d"):
            return ["--mode", pid_clean.replace("binpack_", ""), *extra]
        return list(extra)
    if mode in ("portfolio_opt", "portfolio"):
        pid_clean = (problem_id or "").lower()
        if pid_clean in ("max_sharpe", "min_volatility", "efficient_risk", "efficient_return", "max_quadratic_utility"):
            return ["--objective", pid_clean, *extra]
        return list(extra)
    if mode in ("pyvrp", "vrp_pdp", "pdp", "vrptw"):
        if problem_id and not any(a in extra for a in ("--solomon", "--input", problem_id)):
            return [problem_id, *extra]
        return list(extra)
    if mode in (
        "stochastic_lp",
        "stochastic_programming",
        "stochastic",
        "two_stage_lp",
        "farmer",
        "farmer_problem",
    ):
        if problem_id:
            return [problem_id, *extra]
        return list(extra)
    if mode == "staff_rostering":
        return list(extra)
    if mode in (
        "max_clique",
        "clique",
        "maximum_clique",
        "max_independent_set",
        "mis",
        "independent_set",
        "game_theory",
        "game",
        "nash",
        "nash_equilibrium",
        "bimatrix",
    ):
        # solve_max_clique.py / solve_game_theory.py: positional problem_id
        # + optional flags via extra_args
        return [problem_id, *extra]
    if mode in ("hub_location", "hub", "hlp", "p_hub", "phub", "usahlp"):
        # solve_hub_location.py: positional problem_id + optional flags
        return [problem_id, *extra]
    if mode in ("polyomino", "polyomino_cover", "poly"):
        # solve_polyomino.py: positional problem_id + optional flags via extra_args
        return [problem_id, *extra]
    return [problem_id, *extra]


def _tube_out_dirs(root: Path) -> list[Path]:
    """Candidate dirs for tube q*-solution.json (workdir first, then install home).

    solve_tube_cut_b2026.py hardcodes OUT under the package install root; product
    runs often pass case workdir as ``root`` — must not miss install-home outputs.
    """
    root = Path(root).resolve()
    install = _ROOT.resolve()
    dirs: list[Path] = [root / "outputs" / "b-tube-cut"]
    alt = install / "outputs" / "b-tube-cut"
    if alt not in dirs:
        dirs.append(alt)
    return dirs


def _tube_envelope_from_outputs(root: Path, problem_id: str) -> dict[str, Any]:
    """Load q*-solution.json written by solve_tube_cut_b2026 into one envelope."""
    questions: dict[str, Any] = {}
    primary_obj = None
    status = "FEASIBLE"
    out_dir: Path | None = None
    for cand in _tube_out_dirs(root):
        if any((cand / f"{n}-solution.json").is_file() for n in ("q1", "q2", "q3", "q4")):
            out_dir = cand
            break
    if out_dir is None:
        out_dir = _tube_out_dirs(root)[0]
    for name in ("q1", "q2", "q3", "q4"):
        p = out_dir / f"{name}-solution.json"
        if not p.is_file():
            continue
        q = json.loads(p.read_text(encoding="utf-8"))
        questions[name] = q
        # prefer total_stock_length or total_stock_length_mm
        for key in ("total_stock_length_mm", "total_stock_length", "total_new_standard_stock_mm"):
            if name == "q3" and key in q and q[key] is not None:
                primary_obj = q[key]
                break
            if name == "q1" and primary_obj is None and key in q and q[key] is not None:
                primary_obj = q[key]
        st = str(q.get("status", status)).upper()
        if st in ("FEASIBLE", "OPTIMAL"):
            status = st
    if primary_obj is None:
        for alt in ("solution.json", "summary.json"):
            ap = out_dir / alt
            if ap.is_file():
                blob = json.loads(ap.read_text(encoding="utf-8"))
                if "objective" in blob:
                    primary_obj = blob["objective"]
                    questions["summary"] = blob
                    break
    if primary_obj is None:
        tried = ", ".join(str(d) for d in _tube_out_dirs(root))
        raise FileNotFoundError(
            f"tube outputs missing under [{tried}]; run tools/solve_tube_cut_b2026.py first"
        )
    snapshot_path = out_dir / "model_snapshot.json"
    if not snapshot_path.is_file():
        raise FileNotFoundError(
            f"tube model snapshot missing: {snapshot_path}; stale pre-v2 outputs are not valid"
        )
    model_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    env = {
            "problem_id": problem_id or "tube_cut_b2026",
            "problem_class": "tube_cut",
            "status": status,
            "objective": primary_obj,
            "source": "tools/solve_tube_cut_b2026.py",
            "solver": "tube-cg-cpsat-alns-beam",
            "questions": questions,
            "model_snapshot": model_snapshot,
            "outputs_dir": str(out_dir),
            # Policy constants used by paper/R2 (not invented optima)
            "remnant_min_mm": 200.0,
            "stock_lengths_mm": [9000.0, 10000.0, 11000.0, 12000.0],
            "metrics": {
                "remnant_min_mm": 200.0,
                "stock_lengths_mm": [9000.0, 10000.0, 11000.0, 12000.0],
                "q1_total_stock_mm": (questions.get("q1") or {}).get("total_stock_length_mm")
                or (questions.get("q1") or {}).get("total_stock_length"),
                "q3_total_stock_mm": (questions.get("q3") or {}).get("total_stock_length_mm")
                or (questions.get("q3") or {}).get("total_stock_length"),
                "q4_total_stock_mm": (questions.get("q4") or {}).get("total_new_standard_stock_mm")
                or (questions.get("q4") or {}).get("total_stock_length_mm"),
            },
            "meta": {
                "exact": False,
                "proven_optimal": False,
                "method_class": "heuristic",
                "claim": "FEASIBLE mixed-stock/ALNS/beam solution; not proven OPTIMAL",
                "remnant_min_mm": 200.0,
                "stock_lengths_mm": [9000.0, 10000.0, 11000.0, 12000.0],
            },
        }
    return normalize_solution(env, mode="tube")


def solve(
    root: Path,
    problem_id: str,
    mode: str,
    problem_class: str | None = None,
    extra_args: list[str] | None = None,
    *,
    normalize: bool = True,
) -> tuple[bool, dict[str, Any], str]:
    """Run adapter and return (ok, solution_dict, raw_text)."""
    root = Path(root)
    mode_l = (mode or "mock").lower().strip()
    pc_l = (problem_class or "").lower().strip()
    pid_l = (problem_id or "").lower()
    # auto-route domain adapters when mode is generic/unknown
    if mode_l not in ADAPTER_SCRIPTS:
        if "tube" in pid_l or pc_l in {"tube_cut", "tube", "cutting_stock", "cut_stock"}:
            mode_l = "tube"
        elif (
            "polyomino" in pid_l
            or pc_l in {"polyomino", "polyomino_cover", "poly", "polyomino_tiling", "tiling_cover"}
        ):
            mode_l = "polyomino"
        elif "microgrid" in pid_l or pc_l in {"microgrid_dispatch", "microgrid", "energy_storage"}:
            mode_l = "microgrid"
        elif "jssp" in pid_l or "fjssp" in pid_l or pc_l in {"jssp", "job_shop", "jobshop", "scheduling", "fjssp", "flexible_job_shop"}:
            mode_l = "jssp"
        elif "binpack" in pid_l or pc_l in {"bin_packing", "binpack", "knapsack", "packing"}:
            mode_l = "bin_packing"
        elif "facility" in pid_l or pc_l in {"facility_location", "facility", "cflp", "location"}:
            mode_l = "facility_location"
        elif "portfolio" in pid_l or pc_l in {"portfolio_opt", "portfolio", "markowitz"}:
            mode_l = "portfolio_opt"
        elif "flow" in pid_l or pc_l in {"network_flow", "max_flow_matching", "bipartite_matching", "min_cost_flow"}:
            mode_l = "network_flow"
        elif "qubo" in pid_l or "ising" in pid_l or pc_l in {"qubo_ising", "qubo", "ising", "max_cut"}:
            mode_l = "qubo_ising"
        elif "rcpsp" in pid_l or pc_l in {"rcpsp", "project_scheduling", "psplib"}:
            mode_l = "rcpsp"
        elif "staff_rostering" in pid_l or pc_l in {"staff_rostering", "nurse_scheduling", "rostering", "shift_scheduling"}:
            mode_l = "staff_rostering"
        elif "pyvrp" in pid_l or "pdp" in pid_l or pc_l in {"pyvrp", "vrp_pdp", "pdp", "vrptw", "pickup_delivery"}:
            mode_l = "pyvrp"
        elif "lot_sizing" in pid_l or "wagner" in pid_l or "clsp" in pid_l or "ulsp" in pid_l or pc_l in {"lot_sizing", "inventory_planning", "wagner_whitin", "mrp", "clsp", "ulsp"}:
            mode_l = "lot_sizing"
        elif "qap" in pid_l or pc_l in {"qap", "quadratic_assignment", "facility_layout", "qaplib"}:
            mode_l = "qap"
        elif "coloring" in pid_l or pc_l in {"graph_coloring", "vertex_coloring", "vcp", "coloring", "dimacs_col"}:
            mode_l = "graph_coloring"
        elif "stochastic" in pid_l or "farmer" in pid_l or pc_l in {"stochastic_lp", "stochastic_programming", "stochastic", "two_stage_lp", "farmer", "farmer_problem"}:
            mode_l = "stochastic_lp"
        elif "clique" in pid_l or pc_l in {"max_clique", "clique", "maximum_clique", "max_independent_set", "mis", "independent_set"}:
            mode_l = "max_clique"
        elif "game" in pid_l or "nash" in pid_l or "bimatrix" in pid_l or pc_l in {"game_theory", "game", "nash", "nash_equilibrium", "bimatrix"}:
            mode_l = "game_theory"
        elif "hub" in pid_l or pc_l in {"hub_location", "hub", "hlp", "p_hub", "phub", "usahlp"}:
            mode_l = "hub_location"
        else:
            mode_l = "ortools"
    # class forces polyomino even if mode was ortools by default
    if mode_l == "ortools" and (
        pc_l in {"polyomino", "polyomino_cover", "poly"} or "polyomino" in pid_l
    ):
        mode_l = "polyomino"

    if mode_l not in ADAPTER_SCRIPTS:
        return False, {}, f"unknown solve mode: {mode}"

    script_name = ADAPTER_SCRIPTS[mode_l]
    # Adapters live next to this module (install tools/), not under case workdir.
    tools_dir = Path(__file__).resolve().parent
    script = tools_dir / script_name
    if not script.is_file():
        alt = root / "tools" / script_name
        if alt.is_file():
            script = alt
        else:
            return False, {}, f"adapter missing: {script}"

    args = _build_args(mode_l, problem_id, problem_class, extra_args, root=root)

    if mode_l in ("tube", "tube_cut", "tube_bfd"):
        # Public installs intentionally exclude the original contest attachments.
        # Preflight before running the solver or reading potentially stale outputs.
        from solve_tube_cut_b2026 import blocked_envelope, input_readiness

        ready = input_readiness()
        if not ready["ok"]:
            # Public installs ship the original contest attachments EXCLUDED,
            # so a real solve is impossible. When ORPATH_TUBE_REUSE=1 and a
            # shipped (public-verified) q*-envelope exists on disk, honor it;
            # otherwise fail safe with the honest BLOCKED envelope.
            reuse = str(os.environ.get("ORPATH_TUBE_REUSE") or "").strip() == "1"
            shipped = None
            if reuse:
                for cand in _tube_out_dirs(root):
                    if (cand / "q1-solution.json").is_file() or (cand / "summary.json").is_file():
                        shipped = cand
                        break
            if shipped is not None:
                try:
                    data = _tube_envelope_from_outputs(root, problem_id or "tube_cut_b2026")
                except Exception:  # noqa: BLE001
                    data = None
                if data is not None:
                    meta = data.get("meta")
                    if not isinstance(meta, dict):
                        meta = {}
                        data["meta"] = meta
                    meta["public_shipped_replay"] = True
                    data["model_snapshot"] = data.get("model_snapshot") or {}
            else:
                data = normalize_solution(
                    blocked_envelope(problem_id or "tube_cut_b2026"), mode=mode_l
                )
            if data is None:
                data = normalize_solution(
                    blocked_envelope(problem_id or "tube_cut_b2026"), mode=mode_l
                )
            ok_e, e_errs = validate_envelope(data)
            if not ok_e:
                return False, data, "envelope: " + "; ".join(e_errs)
            raw = json.dumps(data, ensure_ascii=False)
            return True, data, raw
        # Adapter uses install-root paths for CSV/OUT — run with install cwd.
        if os.environ.get("ORPATH_TUBE_REUSE") == "1":
            # Demo path: reuse the already-shipped b-tube-cut answers instead of
            # re-running the Q1–Q4 beam search (minutes). Env-gated, off by default.
            try:
                data = _tube_envelope_from_outputs(_ROOT, problem_id or "tube_cut_b2026")
            except Exception as exc:  # noqa: BLE001
                return False, {}, f"tube envelope reuse: {exc}"
            if normalize:
                data = normalize_solution(data, mode=mode_l)
            ok_e, e_errs = validate_envelope(data)
            if not ok_e:
                return False, data, "envelope: " + "; ".join(e_errs)
            raw = json.dumps(data, ensure_ascii=False)
            return True, data, raw
        code, out, err = _run_py(script, args, _ROOT)
        raw = (out + "\n" + err).strip()
        if code != 0:
            return False, {}, raw or f"tube solver exit {code}"
        try:
            # The adapter always writes to the install-root output directory.
            # Read that exact run, never a stale case-workdir copy.
            data = _tube_envelope_from_outputs(_ROOT, problem_id or "tube_cut_b2026")
        except Exception as exc:  # noqa: BLE001
            return False, {}, f"tube envelope: {exc}\n{raw[:500]}"
        if normalize:
            data = normalize_solution(data, mode=mode_l)
        ok_e, e_errs = validate_envelope(data)
        if not ok_e:
            return False, data, "envelope: " + "; ".join(e_errs)
        return True, data, raw
    prev_wd = os.environ.get("ORPATH_WORKDIR")
    os.environ["ORPATH_WORKDIR"] = str(root)
    try:
        handled, code, out, err = _try_in_proc(script_name, args)
        if not handled:
            code, out, err = _run_py(script, args, root)
    finally:
        if prev_wd is None:
            os.environ.pop("ORPATH_WORKDIR", None)
        else:
            os.environ["ORPATH_WORKDIR"] = prev_wd
    if code != 0:
        return False, {}, (err or out).strip()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return False, {}, (err or out).strip()
    if not isinstance(data, dict):
        return False, {}, "adapter returned non-object JSON"
    if normalize:
        data = normalize_solution(data, mode=mode_l)
        data.setdefault("source", f"tools/{script_name}")
        data.setdefault("problem_id", problem_id)
    ok_e, e_errs = validate_envelope(data)
    if not ok_e:
        return False, data, "envelope: " + "; ".join(e_errs)
    return True, data, out


def validate(
    root: Path,
    problem_id: str,
    solution: Path,
    out: Path,
) -> tuple[bool, dict[str, Any], str]:
    """Delegate to validate_solution.py (single validate seam, prefers in-proc import)."""
    root = Path(root)
    # 1. Try fast in-process validation first
    try:
        from tools import validate_solution as vs_mod
        sol_p = Path(solution)
        sol_dict = json.loads(sol_p.read_text(encoding="utf-8")) if sol_p.is_file() else {}
        v_res = vs_mod.validate(problem_id=problem_id, solution=sol_dict, solution_path=sol_p)
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(v_res, indent=2, ensure_ascii=False), encoding="utf-8")
        is_ok = bool(v_res.get("ok"))
        return is_ok, v_res, json.dumps(v_res, ensure_ascii=False)
    except Exception:
        pass

    # 2. Fallback to subprocess
    tools_dir = Path(__file__).resolve().parent
    script = tools_dir / "validate_solution.py"
    if not script.is_file():
        script = root / "tools" / "validate_solution.py"
    code, stdout, err = _run_py(
        script,
        [
            "--problem-id",
            problem_id,
            "--solution",
            str(solution),
            "--out",
            str(out),
        ],
        root,
    )

    try:
        data = (
            json.loads(stdout)
            if stdout.strip()
            else json.loads(Path(out).read_text(encoding="utf-8"))
        )
    except Exception:
        data = {"ok": False, "errors": [err or stdout]}
    return code == 0 and bool(data.get("ok")), data, (stdout + err).strip()


def list_adapters() -> dict[str, str]:
    return dict(ADAPTER_SCRIPTS)


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="OR-Path unified solve dispatch (ADR-0002)")
    p.add_argument("problem_id")
    p.add_argument(
        "--mode",
        default="mock",
        choices=sorted(ADAPTER_SCRIPTS.keys()),
    )
    p.add_argument("--class", dest="problem_class", default="")
    p.add_argument("--root", type=Path, default=_ROOT)
    args, rest = p.parse_known_args(argv)
    ok, data, raw = solve(
        args.root,
        args.problem_id,
        args.mode,
        problem_class=args.problem_class or None,
        extra_args=rest or None,
    )
    if not ok:
        print(raw or json.dumps(data), file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
