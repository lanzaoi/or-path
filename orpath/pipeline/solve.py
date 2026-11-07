"""Model, gate_schema, solve, gate_validate, and human_stop nodes.

Phase 3.2 — the :func:`node_model` static five-branch tree
(``shortest_path / tsp / polyomino / tube_cut / microgrid_dispatch``) is gone.
Modeling is dispatched through the unified ``DomainCartridge`` registry for all
22 registered OR classes; unknown open questions fall back to the isolated
multi-agent pipeline. Tier-B solves additionally record a lower-bound /
incumbent gap record (``outputs/<slug>-gap.json``) straight from the solver
envelope — numbers truth, no LLM voting.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orpath.gates import gate_schema, gate_validate, solve
from orpath.human_steer import apply_steer_to_state
from orpath.paper_workflow import append_plan_log
from orpath.state import ORPathState
from orpath.pipeline.common import (
    _root,
    _rel_under,
    _ensure_dirs,
    _fixture_base,
    _infer_class,
    _intake_front_door_active,
    _solution_is_blocked,
    _intake_whitelist_path,
    _paper_whitelist_path,
    TUNE_STRATEGIES,
)

# Class-specific solver-mode preference for the registry modeler.
_SOLVE_MODE_BY_CLASS: dict[str, str] = {
    "shortest_path": "networkx",
    "tsp": "cpsat",
    "vrp": "ortools",
    "pyvrp": "pyvrp",
    "jssp": "jssp",
    "rcpsp": "rcpsp",
    "staff_rostering": "staff_rostering",
    "facility_location": "facility_location",
    "hub_location": "hub_location",
    "qap": "qap",
    "portfolio_opt": "portfolio_opt",
    "stochastic_lp": "stochastic_lp",
    "lot_sizing": "lot_sizing",
    "tube_cut": "tube",
    "polyomino_cover": "polyomino",
    "bin_packing": "bin_packing",
    "microgrid_dispatch": "microgrid",
    "network_flow": "network_flow",
    "qubo_ising": "qubo_ising",
    "graph_coloring": "graph_coloring",
    "max_clique": "max_clique",
    "game_theory": "game_theory",
}

_FORBIDDEN_SCHEMA_KEYS = frozenset(
    {
        "objective",
        "path",
        "tour",
        "routes",
        "optimal",
        "optimal_value",
        "placements",
        "answers",
    }
)


def _merge_fixture_base(schema: dict, base: dict) -> None:
    """Merge a fixture-provided base model into schema; forbidden keys never leak."""
    for k, v in base.items():
        kl = str(k).lower()
        if kl in _FORBIDDEN_SCHEMA_KEYS:
            continue
        if k not in schema or k in {"decision_vars", "notes"}:
            schema.setdefault(k, v)


def _adapter_modes() -> dict[str, str]:
    """Lazily load ADAPTER_SCRIPTS from tools/solve_dispatch (install tools)."""
    try:
        from solve_dispatch import ADAPTER_SCRIPTS  # type: ignore[import-not-found]

        return dict(ADAPTER_SCRIPTS)
    except Exception:
        try:
            from orpath.gates import tools_dir

            tools = tools_dir(Path(os.environ.get("ORPATH_ROOT", ".")))
            if str(tools) not in sys.path:
                sys.path.insert(0, str(tools))
            from solve_dispatch import ADAPTER_SCRIPTS  # type: ignore[import-not-found]

            return dict(ADAPTER_SCRIPTS)
        except Exception:
            return {}


def _resolve_cartridge_and_tier(pc: str) -> tuple[str, str, tuple[str, ...]]:
    """Return (domain_key, tier, solver_modes) for any problem class (Phase 3.1/3.2)."""
    try:
        from orpath.agents.cartridges import cartridge_tier, resolve_cartridge

        cartridge = resolve_cartridge(pc)
        return cartridge.domain, str(cartridge_tier(pc)), tuple(cartridge.solver_modes)
    except Exception:
        try:
            from orpath.domain_registry import is_known_class, normalize_problem_class

            pc_n = normalize_problem_class(pc)
            known = is_known_class(pc)
        except Exception:
            pc_n, known = str(pc or ""), False
        modes = (str(pc_n),) if known else ("ortools", "mock")
        tier = "A" if known else "B"
        return ("general_or" if not known else "general_or"), tier, modes


def _registry_model_schema(
    root: Path, slug: str, pid: str, pc_raw: str, sm: str
) -> dict | None:
    """Unified registry modeler: build ``<slug>-schema.json`` for any registered class.

    Returns None when the class is not registered (caller falls back to the
    isolated multi-agent pipeline / human_stop).
    """
    from orpath.domain_registry import (
        is_polyomino_class,
        is_registered_solve_class,
        normalize_problem_class,
    )

    pc_n = normalize_problem_class(pc_raw) or str(pc_raw or "")
    if not is_registered_solve_class(pc_n):
        return None

    cartridge_domain, tier, cartridge_modes = _resolve_cartridge_and_tier(pc_n)
    adapters = _adapter_modes()
    # solve-mode: explicit preferred (registered for this class) -> cartridge first mode -> class name
    mode = ""
    for candidate in (sm, _SOLVE_MODE_BY_CLASS.get(pc_n, ""), *cartridge_modes, pc_n):
        if candidate and candidate in adapters:
            mode = candidate
            break

    fb = _fixture_base(root, pid)
    schema = {
        "slug": slug,
        "problem_class": pc_n,
        "problem_id": pid,
        "preferred_solve_mode": mode or "auto",
        "constraints": [],
        "notes": (
            f"Phase 3.2 unified modeler — DomainCartridge={cartridge_domain} "
            f"tier={tier}; structural model only (no optima)"
        ),
        "domain_cartridge": cartridge_domain,
        "complexity_tier": tier,
    }
    if fb is not None:
        schema["fixture_ref"] = _rel_under(fb, root)
        for base_name in ("schema.json", "instance.json", "problem.json"):
            if (fb / base_name).is_file():
                try:
                    base = json.loads((fb / base_name).read_text(encoding="utf-8"))
                    if isinstance(base, dict):
                        _merge_fixture_base(schema, base)
                except (OSError, json.JSONDecodeError):
                    pass
        # class-specific structural keys inferred from fixture data files
        if pc_n == "shortest_path" and (fb / "graph.json").is_file():
            graph = json.loads((fb / "graph.json").read_text(encoding="utf-8"))
            schema["nodes"] = graph.get("nodes", [])
            schema["edges_ref"] = _rel_under(fb / "graph.json", root)
            schema.setdefault("source", graph["nodes"][0])
            schema.setdefault("target", graph["nodes"][-1])
            schema.setdefault("weight_key", "w")
        if pc_n == "tsp":
            coords_file = fb / "coords.json"
            if not coords_file.is_file() and (fb / "data" / "coords.json").is_file():
                coords_file = fb / "data" / "coords.json"
            if not coords_file.is_file() and (fb / "distance_matrix.json").is_file():
                try:
                    schema["distance_matrix"] = json.loads(
                        (fb / "distance_matrix.json").read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError):
                    pass
            if "distance_matrix" not in schema and coords_file.is_file():
                try:
                    coords = json.loads(coords_file.read_text(encoding="utf-8"))
                    schema["coords"] = coords.get("coords", coords)
                except (OSError, json.JSONDecodeError):
                    pass
        if pc_n == "vrp" and (fb / "locations.json").is_file():
            try:
                loc = json.loads((fb / "locations.json").read_text(encoding="utf-8"))
                for k in ("depot", "locations", "demands", "vehicle_count", "capacities"):
                    if loc.get(k) is not None:
                        schema.setdefault(k, loc[k])
                schema.setdefault("constraints", []).append("capacity")
                schema["notes"] += " Registry VRP modeler"
            except (OSError, json.JSONDecodeError):
                pass
        if is_polyomino_class(pc_n):
            board: dict = {}
            if fb is not None and (fb / "board.json").is_file():
                try:
                    board = json.loads((fb / "board.json").read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    board = {}
            schema.setdefault("rows", 4)
            schema.setdefault("cols", 4)
            pieces = board.get("pieces") or board.get("piece_types")
            schema["pieces"] = pieces if pieces else [{"id": "M"}, {"id": "D"}, {"id": "L3"}]
            for k in ("removed", "max_counts", "allow_reflect", "max_uncovered"):
                if board.get(k) is not None:
                    schema.setdefault(k, board[k])
            if fb is not None and (fb / "board.json").is_file():
                schema.setdefault("board_ref", _rel_under(fb / "board.json", root))
            else:
                schema["task"] = "polyomino_cover"
        if pc_n == "microgrid_dispatch":
            schema.setdefault("intervals_per_day", 144)
            schema.setdefault("subproblems", ["q1", "q2", "q3", "q4_2", "q4_3"])
    return schema


def _default_tube_schema(slug: str, pid: str) -> dict:
    pid_t = str(pid or "tube_cut_b2026").strip() or "tube_cut_b2026"
    return {
        "slug": slug,
        "problem_class": "tube_cut",
        "problem_id": pid_t,
        "preferred_solve_mode": "tube",
        "constraints": [],
        "notes": (
            "tube_cut deterministic modeler — structural only; "
            "no optima; solve via tools/solve_tube_cut_b2026.py"
        ),
        "stock_lengths": [9000, 10000, 11000, 12000],
        "workpiece_specs": [{"id": f"G{i}"} for i in range(1, 11)],
        "geometry_preprocessing": {
            "method": "pca_axial_length",
            "cocut": "end_envelope_rotation_search",
        },
        "questions": ["q1", "q2", "q3", "q4"],
        "subproblems": [
            "single_batch",
            "cocut",
            "optimized_layout",
            "multi_batch",
        ],
    }


def _run_isolated_pipeline(root: Path, state: dict, sp: Path, sm: str) -> dict | None:
    """Legacy multi-agent isolated pipeline (researcher→modeler→verifier→writer→reviewer)."""
    try:
        from orpath.agents.supervisor import build_compiled_isolated_pipeline

        pipeline_app = build_compiled_isolated_pipeline()
        pipe_state = {
            "workdir": str(root),
            "slug": state["slug"],
            "problem_id": state["problem_id"],
            "problem_class": state.get("problem_class") or "general_optimization",
            "solve_mode": sm or state.get("solve_mode") or "auto",
            "problem_file": str(state.get("problem_file") or ""),
            "research_path": str(state.get("research_path") or ""),
            "schema_path": str(sp),
            "solution_path": str(root / "outputs" / f"{state['slug']}-solution.json"),
            "validate_path": str(root / "outputs" / f"{state['slug']}-validate.json"),
            "paper_path": str(root / "papers" / f"{state['slug']}.md"),
            "review_path": str(root / "outputs" / f"{state['slug']}-review.md"),
            "lifecycle_status": "PROPOSED",
            "max_model_repairs": 2,
            "max_revisions": 2,
        }
        res = pipeline_app.invoke(pipe_state)
        if sp.is_file():
            return res
    except Exception:
        return None
    return None


def _record_tier_b_gap(root: Path, slug: str, sol_path: Path, tier: str) -> str | None:
    """Record real lower-bound / incumbent / gap from the solver envelope (Tier-B)."""
    if str(tier).strip().upper() != "B":
        return None
    try:
        sol = json.loads(sol_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(sol, dict):
        return None
    obj = sol.get("objective")
    lb = sol.get("lower_bound")
    meta = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
    if lb is None:
        lb = meta.get("lower_bound")
    og = sol.get("optimality_gap")
    if og is None and isinstance(obj, (int, float)) and isinstance(lb, (int, float)):
        og = round(float(obj) - float(lb), 6)
    record = {
        "slug": slug,
        "problem_id": sol.get("problem_id"),
        "problem_class": sol.get("problem_class"),
        "complexity_tier": "B",
        "incumbent": obj,
        "lower_bound": lb,
        "optimality_gap": og,
        "proven_optimal": bool(meta.get("proven_optimal")),
        "status": sol.get("status"),
        "source": "solver envelope (Numbers Truth)",
        "recorded_by": "orpath.pipeline.solve._record_tier_b_gap",
    }
    out = root / "outputs" / f"{slug}-gap.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(out)


def node_model(state: ORPathState) -> dict:
    root = _root(state)
    from orpath.human_steer import apply_steer_to_state

    steer_upd = apply_steer_to_state(dict(state), workdir=root, boundary="model")
    if steer_upd.get("steer_pause"):
        return steer_upd
    state = {**dict(state), **steer_upd}  # type: ignore[assignment]
    slug = state["slug"]
    pid = state["problem_id"]
    pc = state.get("problem_class") or "shortest_path"
    sm = str(state.get("solve_mode") or "").strip()
    fb = _fixture_base(root, pid)
    sp = root / "outputs" / f"{slug}-schema.json"

    sub_ok = None
    res: dict | None = None
    if not sp.is_file():
        schema: dict | None = None
        multiagent_ran = False
        if state.get("multiagent") or state.get("use_multiagent"):
            res = _run_isolated_pipeline(root, dict(state), sp, sm)
            if res is not None:
                sub_ok = bool(
                    res.get("validation_ok")
                    or res.get("lifecycle_status") in {
                        "SOLVER_FEASIBLE",
                        "INDEPENDENTLY_VALIDATED",
                        "ACCEPTED",
                        "REDTEAM_PASSED",
                    }
                )
                multiagent_ran = True
            if sp.is_file():
                schema = json.loads(sp.read_text(encoding="utf-8"))
            elif res is not None:
                schema = {
                    "slug": slug,
                    "problem_class": pc or "general_optimization",
                    "problem_id": pid,
                    "preferred_solve_mode": sm or state.get("solve_mode") or "auto",
                    "constraints": [],
                    "notes": f"Multi-agent modeled instance status={res.get('lifecycle_status')}",
                }

        # Phase 3.2: unified registry modeler — DomainCartridge for all 22 classes.
        if schema is None:
            schema = _resolve_registry_schema(root, slug, pid, pc or "", sm, sp)
        if schema is None:
            state_try = dict(state)
            state_try["multiagent"] = True
            res = _run_isolated_pipeline(root, state_try, sp, sm)
            sub_ok = bool(res) if res else None
            if sp.is_file():
                schema = json.loads(sp.read_text(encoding="utf-8"))
            else:
                return {
                    "stage": "human_stop",
                    "human_required": True,
                    "last_error": (
                        "model: unsupported class "
                        f"(problem_class={pc!r}, problem_id={pid!r}); isolated pipeline unavailable"
                    ),
                }

        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")

    # D2: if human steer set solve_mode, align preferred_solve_mode on disk schema
    sm = str(state.get("solve_mode") or "").strip()
    if sm and sp.is_file() and state.get("human_steer_applied"):
        try:
            data = json.loads(sp.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data["preferred_solve_mode"] = sm
                notes = str(data.get("notes") or "")
                if "human_steer" not in notes:
                    data["notes"] = (notes + " human_steer_mode=" + sm).strip()
                sp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass

    append_plan_log(
        root,
        slug,
        stage="model",
        status="pass",
        detail=f"schema={sp.name} subagent={sub_ok} class={state.get('problem_class')}",
        plan_file=state.get("plan_path"),
    )
    out_m: dict = {
        "stage": "gate_schema",
        "schema_path": str(sp),
        "gate_subagent_ok": sub_ok if sub_ok is not None else state.get("gate_subagent_ok"),
        "last_error": "",
    }
    # carry Phase 3.1 pointers downstream
    for k in ("domain_cartridge", "complexity_tier", "cartridge_domain", "profile_path", "data_files"):
        if state.get(k) is not None:
            out_m[k] = state.get(k)
    try:
        from orpath.agents.cartridges import cartridge_tier

        out_m.setdefault("complexity_tier", str(cartridge_tier(str(state.get("problem_class") or ""))))
    except Exception:
        pass
    if res and isinstance(res, dict):
        for k in ("solution_path", "validate_path", "paper_path", "review_path", "research_path"):
            if res.get(k):
                out_m[k] = res[k]
        if res.get("lifecycle_status"):
            out_m["lifecycle_status"] = res["lifecycle_status"]
    if sm:
        out_m["solve_mode"] = sm
    for k in (
        "human_steer_path",
        "human_steer_applied",
        "human_steer_lg",
        "human_steer_pi",
        "human_steer_at_stage",
        "human_steer_utc",
        "human_steer_fresh",
    ):
        if state.get(k) is not None:
            out_m[k] = state.get(k)
    return out_m


def _resolve_registry_schema(
    root: Path, slug: str, pid: str, pc_raw: str, sm: str, sp: Path
) -> dict | None:
    """Registry-driven schema for a registered class; tube_cut / polyomino defaults kept."""
    from orpath.domain_registry import (
        is_polyomino_class,
        normalize_problem_class,
    )

    pc_n = normalize_problem_class(pc_raw) or str(pc_raw or "")
    try:
        # container / cutting-stock family: explicit fixture schema merge + structural default
        if pc_n in {"tube_cut", "tube", "cutting_stock", "cut_stock"} or "tube" in str(pc_raw or "").lower() or "tube" in str(pid or "").lower():
            schema = _default_tube_schema(slug, pid)
            if fb := _fixture_base(root, pid):
                schema["fixture_ref"] = _rel_under(fb, root)
                if (fb / "schema.json").is_file():
                    try:
                        base = json.loads((fb / "schema.json").read_text(encoding="utf-8"))
                        if isinstance(base, dict):
                            _merge_fixture_base(schema, base)
                    except (OSError, json.JSONDecodeError):
                        pass
            return schema
        schema = _registry_model_schema(root, slug, pid, pc_raw, sm)
        return schema
    except Exception:
        return None


def node_gate_schema(state: ORPathState) -> dict:
    root = _root(state)
    if state.get("stage") == "human_stop":
        return {
            "stage": "human_stop",
            "human_required": True,
            "gate_schema_ok": False,
            "last_error": str(state.get("last_error") or "steer_pause before model"),
        }
    raw_sp = state.get("schema_path") or ""
    sp = Path(str(raw_sp)) if str(raw_sp).strip() not in {"", "."} else Path()
    if not sp.is_file():
        msg = (
            "schema_path missing or not a file "
            f"(got {raw_sp!r}) — modeler did not write outputs/*-schema.json"
        )
        repair = int(state.get("schema_repair") or 0)
        max_r = int(state.get("max_schema_repair") or 2)
        if repair < max_r:
            return {
                "stage": "model",
                "gate_schema_ok": False,
                "schema_repair": repair + 1,
                "last_error": msg,
            }
        return {
            "stage": "human_stop",
            "human_required": True,
            "gate_schema_ok": False,
            "last_error": f"schema repair exhausted: {msg}",
        }
    ok, msg = gate_schema(root, sp)
    if ok:
        return {"stage": "solve", "gate_schema_ok": True, "last_error": ""}
    repair = int(state.get("schema_repair") or 0)
    max_r = int(state.get("max_schema_repair") or 2)
    if repair < max_r:
        return {
            "stage": "model",
            "gate_schema_ok": False,
            "schema_repair": repair + 1,
            "last_error": msg,
        }
    return {
        "stage": "human_stop",
        "gate_schema_ok": False,
        "human_required": True,
        "last_error": f"schema repair exhausted: {msg}",
    }


def node_solve(state: ORPathState) -> dict:
    root = _root(state)
    from orpath.human_steer import apply_steer_to_state

    steer_upd = apply_steer_to_state(dict(state), workdir=root, boundary="solve")
    if steer_upd.get("steer_pause"):
        return steer_upd
    if steer_upd.get("solve_mode"):
        state = {**dict(state), **steer_upd}  # type: ignore[assignment]
    elif steer_upd:
        state = {**dict(state), **{k: v for k, v in steer_upd.items() if k != "stage"}}  # type: ignore[assignment]
    pc = state.get("problem_class") or "shortest_path"
    mode = state["solve_mode"]
    out = root / "outputs" / f"{state['slug']}-solution.json"

    # If multi-agent already generated and verified the solution:
    if (state.get("gate_subagent_ok") or state.get("solution_path")) and out.is_file():
        try:
            sol_data = json.loads(out.read_text(encoding="utf-8"))
            if isinstance(sol_data, dict) and sol_data.get("status") in {
                "FEASIBLE",
                "OPTIMAL",
                "SOLVER_FEASIBLE",
            }:
                tier = str(state.get("complexity_tier") or "B")
                gap_path = _record_tier_b_gap(root, state["slug"], out, tier)
                return {
                    "stage": "gate_validate",
                    "solution_path": str(out),
                    "gap_path": gap_path,
                    "last_error": "",
                }
        except Exception:
            pass

    # 1.2 soak law: intake-on must NOT bind fixture SP/TSP/VRP gold as the answer.
    # Domain adapters (tube_cut, polyomino_cover) may still run under intake.
    if _intake_front_door_active(state):
        pc_l = str(pc or "").lower()
        pid_l = str(state.get("problem_id") or "").lower()
        try:
            from orpath.domain_registry import is_polyomino_class, is_registered_solve_class

            poly_ad = is_polyomino_class(pc_l) or "polyomino" in pid_l
            tube_ad = pc_l in {"tube_cut", "tube", "tube_bfd"} or "tube" in pid_l
            has_domain_adapter = bool(poly_ad or tube_ad or is_registered_solve_class(pc_l))
        except Exception:  # noqa: BLE001
            poly_ad = "polyomino" in pc_l or "polyomino" in pid_l
            tube_ad = pc_l in {"tube_cut", "tube", "tube_bfd"} or "tube" in pid_l
            has_domain_adapter = poly_ad or tube_ad
        if not has_domain_adapter:
            blocked = {
                "status": "BLOCKED",
                "objective": None,
                "solver": "none",
                "source": "no_domain_adapter_for_intake",
                "problem_id": state.get("problem_id"),
                "problem_class": pc,
                "slug": state.get("slug"),
                "meta": {
                    "exact": False,
                    "proven_optimal": False,
                    "blocked": True,
                    "method_class": "fixture",
                    "reason": (
                        "intake front-door active: refusing fixture solve bind "
                        f"(problem_id={state.get('problem_id')!r}, mode={mode!r}); "
                        "no contest-domain adapter registered"
                    ),
                    "intake_path": state.get("intake_path") or "",
                    "brief_path": state.get("brief_path") or "",
                },
            }
            out.write_text(json.dumps(blocked, indent=2) + "\n", encoding="utf-8")
            return {
                "stage": "gate_validate",
                "solution_path": str(out),
                "gate_validate_ok": False,
                "last_error": "no_domain_adapter_for_intake",
                "solve_refused": True,
            }
        # Prefer domain solve mode when adapter applies
        if str(mode).lower() in {"mock", "auto", ""}:
            if poly_ad:
                mode = "polyomino"
            elif tube_ad:
                mode = "tube"
            elif "microgrid" in pc_l or "microgrid" in pid_l:
                mode = "microgrid"

    # Non-intake: polyomino / microgrid must not use SP mock bind
    if "microgrid" in str(pc or "").lower() or "microgrid" in str(state.get("problem_id") or "").lower():
        if str(mode).lower() in {"mock", "auto", "ortools", ""}:
            mode = "microgrid"
    try:
        from orpath.domain_registry import is_polyomino_class

        if is_polyomino_class(str(pc or "")) or "polyomino" in str(
            state.get("problem_id") or ""
        ).lower():
            if str(mode).lower() in {"mock", "auto", "ortools", ""}:
                mode = "polyomino"
    except Exception:  # noqa: BLE001
        if "polyomino" in str(pc or "").lower() or "polyomino" in str(
            state.get("problem_id") or ""
        ).lower():
            if str(mode).lower() in {"mock", "auto", "ortools", ""}:
                mode = "polyomino"

    extra: list[str] = []
    tune = int(state.get("solver_tune") or 0)
    if mode == "ortools" and tune > 0 and tune <= len(TUNE_STRATEGIES):
        fs, mh, tl = TUNE_STRATEGIES[min(tune, len(TUNE_STRATEGIES)) - 1]
        extra = [
            "--first-solution",
            fs,
            "--metaheuristic",
            mh,
            "--time-limit-ms",
            str(tl),
        ]
    ok, data, raw = solve(root, state["problem_id"], mode, pc, extra or None)
    if not ok and mode not in {
        "mock",
        "polyomino",
        "polyomino_cover",
        "poly",
        "tube",
        "tube_cut",
    }:
        ok, data, raw = solve(root, state["problem_id"], "mock", pc)
    if not ok:
        return {
            "stage": "human_stop",
            "human_required": True,
            "last_error": raw,
        }
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tier = str(state.get("complexity_tier") or "B")
    gap_path = _record_tier_b_gap(root, state["slug"], out, tier)
    return {
        "stage": "gate_validate",
        "solution_path": str(out),
        "gap_path": gap_path,
        "last_error": "",
    }


def node_gate_validate(state: ORPathState) -> dict:
    root = _root(state)
    vpath = root / "outputs" / f"{state['slug']}-validate.json"
    sol_path = Path(state.get("solution_path") or "")
    # BLOCKED: no tune/model repair ladder — go explain → paper shell.
    if sol_path.is_file():
        try:
            sol_obj = json.loads(sol_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            sol_obj = {}
        meta = sol_obj.get("meta") if isinstance(sol_obj, dict) else None
        blocked = bool(
            isinstance(sol_obj, dict)
            and (
                str(sol_obj.get("status") or "").upper() == "BLOCKED"
                or (isinstance(meta, dict) and meta.get("blocked"))
                or state.get("solve_refused")
            )
        )
        if blocked:
            report = {
                "ok": False,
                "blocked": True,
                "errors": [
                    sol_obj.get("meta", {}).get("reason")
                    if isinstance(sol_obj.get("meta"), dict)
                    else "solution BLOCKED"
                ],
                "solution_path": str(sol_path),
                "detail": "solution_blocked",
            }
            vpath.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            return {
                "stage": "explain",
                "validate_path": str(vpath),
                "gate_validate_ok": False,
                "human_required": True,
                "last_error": (
                    sol_obj.get("meta", {}).get("blocked_code")
                    if isinstance(sol_obj.get("meta"), dict)
                    else None
                )
                or state.get("last_error")
                or "solution_blocked",
            }

    def _record_validation_pass() -> dict:
        lesson_path = ""
        try:
            from orpath.process_memory import auto_draft_after_validate

            p = auto_draft_after_validate(root, dict(state), gate_ok=True)
            if p is not None:
                lesson_path = str(p)
        except Exception:
            lesson_path = ""
        out_ok: dict = {
            "stage": "explain",
            "validate_path": str(vpath),
            "gate_validate_ok": True,
            "last_error": "",
        }
        if lesson_path:
            out_ok["lesson_draft_path"] = lesson_path
        return out_ok

    # If already validated by multi-agent pipeline:
    if state.get("gate_subagent_ok") and vpath.is_file():
        try:
            val_data = json.loads(vpath.read_text(encoding="utf-8"))
            if isinstance(val_data, dict) and val_data.get("ok"):
                return _record_validation_pass()
        except Exception:
            pass

    ok, report, msg = gate_validate(
        root, state["problem_id"], Path(state["solution_path"]), vpath
    )
    if ok:
        return _record_validation_pass()

    # Q12-C: param retune then model
    tune = int(state.get("solver_tune") or 0)
    max_tune = int(state.get("max_solver_tune") or 3)
    mode = state["solve_mode"]
    log_path = root / "outputs" / f"{state['slug']}-tune-log.jsonl"
    if mode == "ortools" and tune < max_tune:
        entry = {
            "try": tune + 1,
            "report_errors": report.get("errors"),
            "strategy": TUNE_STRATEGIES[min(tune, len(TUNE_STRATEGIES) - 1)],
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return {
            "stage": "solve",
            "solver_tune": tune + 1,
            "gate_validate_ok": False,
            "validate_path": str(vpath),
            "tune_log_path": str(log_path),
            "last_error": msg,
        }

    vrep = int(state.get("validate_repair") or 0)
    max_v = int(state.get("max_validate_repair") or 2)
    if vrep < max_v:
        return {
            "stage": "model",
            "validate_repair": vrep + 1,
            "gate_validate_ok": False,
            "validate_path": str(vpath),
            "last_error": msg,
        }
    return {
        "stage": "human_stop",
        "human_required": True,
        "gate_validate_ok": False,
        "validate_path": str(vpath),
        "last_error": f"validate exhausted: {msg}",
    }


def node_human_stop(state: ORPathState) -> dict:
    root = _root(state)
    hr = root / "outputs" / f"{state['slug']}.HUMAN_REQUIRED.md"
    hr.write_text(
        f"HUMAN_REQUIRED\nlast_error: {state.get('last_error')}\n"
        f"schema_repair={state.get('schema_repair')} solver_tune={state.get('solver_tune')} "
        f"validate_repair={state.get('validate_repair')}\n",
        encoding="utf-8",
    )
    return {"stage": "provenance", "human_required": True}
