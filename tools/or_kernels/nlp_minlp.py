"""General Non-Convex Box/Constrained NLP & Decomposed MINLP solver kernel."""
from __future__ import annotations

import math
import time
from typing import Any, Callable, Sequence

import numpy as np
from scipy.optimize import differential_evolution, dual_annealing, minimize


def _lhs_samples(bounds: Sequence[tuple[float, float]], n_samples: int, seed: int) -> np.ndarray:
    """Generate stratified Latin Hypercube samples inside box ``bounds``."""
    rng = np.random.default_rng(int(seed))
    dim = len(bounds)
    if dim == 0 or n_samples <= 0:
        return np.empty((0, dim), dtype=np.float64)
    mat = np.empty((n_samples, dim), dtype=np.float64)
    lo = np.array([float(b[0]) for b in bounds], dtype=np.float64)
    hi = np.array([float(b[1]) for b in bounds], dtype=np.float64)
    for j in range(dim):
        perm = rng.permutation(n_samples)
        u = (perm + rng.uniform(0.0, 1.0, size=n_samples)) / float(n_samples)
        mat[:, j] = lo[j] + u * (hi[j] - lo[j])
    return mat


def _eval_penalized(
    objective_fn: Callable[[np.ndarray], float],
    x: np.ndarray,
    bounds: Sequence[tuple[float, float]],
    constraints: Sequence[Callable[[np.ndarray], float]],
    *,
    maximize: bool,
    penalty_weight: float,
) -> tuple[float, float, float]:
    """Return ``(penalized_min_val, raw_obj, max_violation)``; constraint c(x) >= 0 required."""
    arr = np.clip(
        np.asarray(x, dtype=np.float64),
        [float(b[0]) for b in bounds],
        [float(b[1]) for b in bounds],
    )
    raw = float(objective_fn(arr))
    if not math.isfinite(raw):
        return 1e18, raw, 1e9
    max_viol = 0.0
    pen = 0.0
    for cfn in constraints:
        val = float(cfn(arr))
        if not math.isfinite(val):
            max_viol = max(max_viol, 1e6)
            pen += 1e12
        elif val < 0.0:
            v = -val
            max_viol = max(max_viol, v)
            pen += penalty_weight * (v + v * v)
    base = -raw if maximize else raw
    return base + pen, raw, max_viol


def solve_box_nlp(
    objective_fn: Callable[[np.ndarray], float],
    bounds: Sequence[tuple[float, float]],
    *,
    maximize: bool = False,
    constraints: Sequence[Callable[[np.ndarray], float]] = (),
    n_lhs: int = 96,
    global_method: str = "de",
    popsize: int = 12,
    maxiter: int = 120,
    n_local_starts: int = 5,
    time_limit_s: float = 60.0,
    seed: int = 42,
    initial_points: Sequence[Sequence[float]] = (),
    penalty_weight: float = 1e4,
) -> dict[str, Any]:
    """Solve a non-convex box/inequality constrained NLP via LHS + Global Search + Local Polish.

    Constraints follow ``scipy.optimize`` SLSQP inequality convention: ``c(x) >= 0`` is feasible.
    Never claims proven global optimality (``proven_optimal=False``).
    """
    t0 = time.monotonic()
    deadline = t0 + max(1.0, float(time_limit_s))
    bnds = [(float(a), float(b)) for a, b in bounds]
    dim = len(bnds)
    eval_counter = 0

    best_feas_x: np.ndarray | None = None
    best_feas_obj: float | None = None
    best_any_x: np.ndarray | None = None
    best_any_pen = float("inf")

    def _record(cand_x: np.ndarray) -> float:
        nonlocal eval_counter, best_feas_x, best_feas_obj, best_any_x, best_any_pen
        eval_counter += 1
        pen_v, raw_v, viol = _eval_penalized(
            objective_fn, cand_x, bnds, constraints, maximize=maximize, penalty_weight=penalty_weight
        )
        arr = np.clip(np.asarray(cand_x, dtype=np.float64), [b[0] for b in bnds], [b[1] for b in bnds])
        if pen_v < best_any_pen:
            best_any_pen = pen_v
            best_any_x = arr.copy()
        if viol <= 1e-6 and math.isfinite(raw_v):
            better = (
                best_feas_obj is None
                or (raw_v > best_feas_obj if maximize else raw_v < best_feas_obj)
            )
            if better:
                best_feas_obj = raw_v
                best_feas_x = arr.copy()
        return pen_v

    # Phase 1: Warm starts + LHS sweep
    seed_pool: list[tuple[float, np.ndarray]] = []
    for pt in initial_points:
        arr = np.asarray(pt, dtype=np.float64)
        if arr.shape == (dim,):
            seed_pool.append((_record(arr), arr))
    lhs = _lhs_samples(bnds, max(0, int(n_lhs)), seed=seed)
    for row in lhs:
        if time.monotonic() >= deadline * 0.9999 and best_any_x is not None:
            break
        seed_pool.append((_record(row), row))

    # Phase 2: Global search (reserve ~35% of remaining time for local polishing)
    rem_now = max(0.0, deadline - time.monotonic())
    global_deadline = time.monotonic() + rem_now * 0.65
    gm = (global_method or "de").strip().lower()

    if dim > 0 and rem_now > 0.5 and gm in {"de", "hybrid"}:
        try:
            init_arg: Any = "latinhypercube"
            if len(seed_pool) >= max(8, dim * 2):
                seed_pool.sort(key=lambda item: item[0])
                top_n = min(len(seed_pool), max(10, popsize * dim))
                init_arg = np.vstack([p for _, p in seed_pool[:top_n]])
            res_de = differential_evolution(
                lambda x: _record(x),
                bounds=bnds,
                maxiter=max(5, int(maxiter)),
                popsize=max(5, int(popsize)),
                seed=int(seed),
                init=init_arg,
                polish=False,
                callback=lambda _xk, convergence=0.0: time.monotonic() >= global_deadline,
            )
            if res_de.x is not None:
                _record(res_de.x)
        except Exception:
            pass

    if dim > 0 and (gm in {"da", "dual_annealing", "hybrid"}) and time.monotonic() < global_deadline:
        try:
            res_da = dual_annealing(
                lambda x: _record(x),
                bounds=bnds,
                maxiter=max(10, int(maxiter)),
                seed=int(seed) + 1,
                x0=best_any_x,
                callback=lambda _x, _f, _ctx: time.monotonic() >= global_deadline,
            )
            if res_da.x is not None:
                _record(res_da.x)
        except Exception:
            pass

    # Phase 3: Multi-start local polish (SLSQP with explicit inequalities or L-BFGS-B)
    polish_starts: list[np.ndarray] = []
    if best_feas_x is not None:
        polish_starts.append(best_feas_x.copy())
    if best_any_x is not None:
        polish_starts.append(best_any_x.copy())
    seed_pool.sort(key=lambda item: item[0])
    for _, pt in seed_pool[: max(1, int(n_local_starts))]:
        polish_starts.append(pt)

    scipy_cons = [{"type": "ineq", "fun": cfn} for cfn in constraints]
    method = "SLSQP" if scipy_cons else "L-BFGS-B"
    for x0 in polish_starts[: max(1, int(n_local_starts) + 2)]:
        if time.monotonic() >= deadline:
            break
        try:
            res_loc = minimize(
                lambda x: (-float(objective_fn(x)) if maximize else float(objective_fn(x))),
                x0=np.clip(x0, [b[0] for b in bnds], [b[1] for b in bnds]),
                method=method,
                bounds=bnds,
                constraints=scipy_cons if scipy_cons else (),
                options={"maxiter": 80, "ftol": 1e-7},
            )
            if res_loc.x is not None:
                _record(res_loc.x)
        except Exception:
            pass

    wall = time.monotonic() - t0
    final_x = best_feas_x if best_feas_x is not None else best_any_x
    final_obj = best_feas_obj
    feas = best_feas_x is not None
    if final_obj is None and final_x is not None:
        _, raw_fallback, viol = _eval_penalized(
            objective_fn, final_x, bnds, constraints, maximize=maximize, penalty_weight=penalty_weight
        )
        final_obj = raw_fallback
        feas = viol <= 1e-6

    return {
        "ok": bool(feas and final_x is not None),
        "feasible": bool(feas),
        "x": [float(v) for v in final_x] if final_x is not None else [],
        "objective": float(final_obj) if final_obj is not None else None,
        "n_evals": int(eval_counter),
        "wall_time_s": round(wall, 4),
        "proven_optimal": False,
        "global_method": gm,
    }


def solve_multistart_polish(
    objective_fn: Callable[[np.ndarray], float],
    bounds: Sequence[tuple[float, float]],
    initial_points: Sequence[Sequence[float]],
    *,
    maximize: bool = False,
    constraints: Sequence[Callable[[np.ndarray], float]] = (),
    method: str = "auto",
    maxiter: int = 100,
    time_limit_s: float = 15.0,
    penalty_weight: float = 1e4,
) -> dict[str, Any]:
    """Stage-3 local continuous polish from Stage-2 discrete/seed solutions.

    Skips global DE/LHS overhead and runs SciPy local optimization (``SLSQP``
    when constrained; ``Powell`` + ``L-BFGS-B`` when unconstrained) around
    supplied ``initial_points``. Constraints obey ``c(x) >= 0`` feasibility.
    """
    t0 = time.monotonic()
    deadline = t0 + max(0.5, float(time_limit_s))
    bnds = [(float(a), float(b)) for a, b in bounds]
    dim = len(bnds)
    eval_counter = 0
    best_feas_x: np.ndarray | None = None
    best_feas_obj: float | None = None
    best_any_x: np.ndarray | None = None
    best_any_pen = float("inf")

    def _rec(cand_x: np.ndarray) -> float:
        nonlocal eval_counter, best_feas_x, best_feas_obj, best_any_x, best_any_pen
        eval_counter += 1
        pen_v, raw_v, viol = _eval_penalized(
            objective_fn, cand_x, bnds, constraints, maximize=maximize, penalty_weight=penalty_weight
        )
        arr = np.clip(np.asarray(cand_x, dtype=np.float64), [b[0] for b in bnds], [b[1] for b in bnds])
        if pen_v < best_any_pen:
            best_any_pen = pen_v
            best_any_x = arr.copy()
        if viol <= 1e-6 and math.isfinite(raw_v):
            better = (
                best_feas_obj is None
                or (raw_v > best_feas_obj if maximize else raw_v < best_feas_obj)
            )
            if better:
                best_feas_obj = raw_v
                best_feas_x = arr.copy()
        return pen_v

    seeds = [np.asarray(pt, dtype=np.float64) for pt in initial_points if len(pt) == dim]
    for s in seeds:
        _rec(s)

    scipy_cons = [{"type": "ineq", "fun": cfn} for cfn in constraints]
    m_req = (method or "auto").strip()
    run_methods = (
        ["SLSQP"]
        if scipy_cons
        else (["Powell", "L-BFGS-B"] if m_req.lower() == "auto" else [m_req])
    )
    for x0 in seeds:
        if time.monotonic() >= deadline:
            break
        cur = np.clip(x0, [b[0] for b in bnds], [b[1] for b in bnds])
        for m_name in run_methods:
            if time.monotonic() >= deadline:
                break
            try:
                res = minimize(
                    lambda x: (-float(objective_fn(x)) if maximize else float(objective_fn(x))),
                    x0=cur,
                    method=m_name,
                    bounds=bnds,
                    constraints=scipy_cons if scipy_cons else (),
                    options={"maxiter": max(10, int(maxiter))},
                )
                if res.x is not None:
                    _rec(res.x)
                    cur = np.clip(res.x, [b[0] for b in bnds], [b[1] for b in bnds])
            except Exception:
                pass

    final_x = best_feas_x if best_feas_x is not None else best_any_x
    feas = best_feas_x is not None
    final_obj = best_feas_obj
    if final_obj is None and final_x is not None:
        _, raw_fb, viol = _eval_penalized(
            objective_fn, final_x, bnds, constraints, maximize=maximize, penalty_weight=penalty_weight
        )
        final_obj = raw_fb
        feas = viol <= 1e-6
    return {
        "ok": bool(feas and final_x is not None),
        "feasible": bool(feas),
        "x": [float(v) for v in final_x] if final_x is not None else [],
        "objective": float(final_obj) if final_obj is not None else None,
        "n_evals": int(eval_counter),
        "wall_time_s": round(time.monotonic() - t0, 4),
        "proven_optimal": False,
    }


def solve_minlp_decomposed(
    discrete_candidates: Sequence[Any],
    build_subproblem_fn: Callable[[Any], tuple[Callable[[np.ndarray], float], Sequence[tuple[float, float]], Sequence[Callable[[np.ndarray], float]]]],
    *,
    maximize: bool = False,
    time_limit_s: float = 120.0,
    seed: int = 42,
    n_lhs_per_candidate: int = 48,
    maxiter_per_candidate: int = 80,
) -> dict[str, Any]:
    """Decompose mixed-integer non-convex problem over discrete skeletons -> continuous NLP subproblems."""
    t0 = time.monotonic()
    deadline = t0 + max(2.0, float(time_limit_s))
    cands = list(discrete_candidates)
    best_res: dict[str, Any] | None = None
    best_cand: Any = None
    history: list[dict[str, Any]] = []

    for idx, cand in enumerate(cands):
        rem = deadline - time.monotonic()
        if rem <= 1.0:
            break
        per_budget = rem / max(1, len(cands) - idx)
        obj_fn, bnds, cons = build_subproblem_fn(cand)
        sub = solve_box_nlp(
            obj_fn,
            bnds,
            maximize=maximize,
            constraints=cons,
            n_lhs=n_lhs_per_candidate,
            maxiter=maxiter_per_candidate,
            time_limit_s=per_budget,
            seed=int(seed) + idx,
        )
        history.append({"candidate": cand, "ok": sub["ok"], "objective": sub["objective"], "wall_time_s": sub["wall_time_s"]})
        if sub["ok"] and sub["objective"] is not None:
            better = (
                best_res is None
                or (sub["objective"] > best_res["objective"] if maximize else sub["objective"] < best_res["objective"])
            )
            if better:
                best_res = sub
                best_cand = cand

    return {
        "ok": best_res is not None,
        "best_discrete": best_cand,
        "best_x": best_res["x"] if best_res else [],
        "objective": best_res["objective"] if best_res else None,
        "wall_time_s": round(time.monotonic() - t0, 4),
        "proven_optimal": False,
        "candidates_tried": len(history),
        "history": history,
    }
