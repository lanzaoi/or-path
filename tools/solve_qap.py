#!/usr/bin/env python3
"""Quadratic Assignment Problem (QAP) solver — SciPy FAQ + 2-opt hybrid.

The QAP assigns ``n`` facilities to ``n`` locations to minimise the total
flow-weighted travel cost::

    minimize  sum_i sum_j A[i, j] * B[perm[i], perm[j]]
    s.t.       perm is a permutation of 0..n-1

where ``A`` is the distance matrix and ``B`` the flow matrix.

Methods:
* ``faq``    — single SciPy Fast Approximate QAP run.
* ``2opt``   — multi-start greedy 2-opt from random permutations.
* ``hybrid`` — multi-start FAQ followed by 2-opt refinement, plus an
  iterated local-search (double-bridge perturbation + 2-opt) polish that
  escapes 2-opt local optima.

Inputs: ``distance_matrix`` + ``flow_matrix``, or a QAPLIB ``*.dat`` file via
``qaplib_path`` (e.g. ``fixtures/benchmarks/qaplib/nug12.dat``).

Output follows the OR-Path "Numbers Truth" envelope (ADR-0002):
``problem_id, problem_class="qap", mode="qap", status, objective, solver,
source, num_facilities, permutation, assignments, distance_matrix,
flow_matrix, meta``.  The reported objective is always recomputed from the
raw matrices with ``trace(A^T B[perm][:, perm])``; the independent validator
re-derives it from the envelope matrices.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import quadratic_assignment

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

DEFAULT_FIXTURE = _ROOT / "fixtures" / "benchmarks" / "qaplib" / "nug12.dat"
DEFAULT_SOLVER = "scipy-qap-faq-2opt"

# Known QAPLIB optima. Used ONLY to label ``status`` when the solver's
# recomputed objective matches; the objective itself never comes from this
# table (Numbers Truth).
KNOWN_OPTIMA: dict[str, int] = {
    "nug12": 578,
}


def _resolve_qaplib_path(path: str | Path | None) -> Path:
    """Resolve a QAPLIB path against cwd, then the install root."""
    raw = str(path or DEFAULT_FIXTURE)
    if raw in ("test_prob", "default") or not raw:
        return DEFAULT_FIXTURE
    p = Path(raw)
    if p.is_file():
        return p
    for base in (_ROOT, Path.cwd()):
        cand = base / raw
        if cand.is_file():
            return cand
        cand_qap = base / "fixtures" / "benchmarks" / "qaplib" / raw
        if cand_qap.is_file():
            return cand_qap
        if not raw.endswith(".dat"):
            cand_dat = base / "fixtures" / "benchmarks" / "qaplib" / f"{raw}.dat"
            if cand_dat.is_file():
                return cand_dat
    raise FileNotFoundError(f"QAPLIB instance not found: {raw}")


def load_qaplib(path: str | Path) -> tuple[np.ndarray, np.ndarray, str]:
    """Parse a QAPLIB ``*.dat`` file into (distance_matrix, flow_matrix, id).

    Format: first non-empty line is ``n``; the remaining numeric tokens are
    read row-major, the first ``n*n`` forming the distance matrix ``A`` and
    the next ``n*n`` the flow matrix ``B``. Non-numeric lines (e.g. an
    optional instance-name line) are skipped.
    """
    resolved = _resolve_qaplib_path(path)
    with resolved.open(encoding="utf-8") as fh:
        lines = [line.strip() for line in fh if line.strip()]
    if not lines:
        raise ValueError(f"empty QAPLIB file: {resolved}")
    n = int(lines[0].split()[0])
    tokens: list[float] = []
    for line in lines[1:]:
        parts = line.split()
        if not parts:
            continue
        try:
            tokens.extend(float(x) for x in parts)
        except ValueError:
            continue  # e.g. an instance-name line
    if len(tokens) < 2 * n * n:
        raise ValueError(
            f"QAPLIB file {resolved}: expected {2 * n * n} values, got {len(tokens)}"
        )
    A = np.array(tokens[: n * n], dtype=float).reshape((n, n))
    B = np.array(tokens[n * n : 2 * n * n], dtype=float).reshape((n, n))
    return A, B, resolved.stem


def _qap_objective(A: np.ndarray, B: np.ndarray, perm: np.ndarray) -> float:
    """Exact QAP objective for a permutation (Numbers Truth recomputation)."""
    return float(np.trace(A.T @ B[perm][:, perm]))


def _faq_run(A: np.ndarray, B: np.ndarray, seed: int) -> np.ndarray:
    """One SciPy FAQ run; returns the permutation found."""
    res = quadratic_assignment(
        A,
        B,
        method="faq",
        options={
            "rng": seed,
            "P0": "randomized",
            "maxiter": 500,
            "tol": 1e-6,
            "shuffle_input": True,
        },
    )
    return np.asarray(res.col_ind, dtype=int)


def _two_opt_refine(A: np.ndarray, B: np.ndarray, perm: np.ndarray, seed: int) -> np.ndarray:
    """SciPy greedy 2-opt refinement seeded from ``perm``."""
    guess = np.array([np.arange(A.shape[0]), perm]).T
    res = quadratic_assignment(
        A,
        B,
        method="2opt",
        options={"rng": seed, "partial_guess": guess},
    )
    return np.asarray(res.col_ind, dtype=int)


def _double_bridge(perm: np.ndarray, rng: np.random.Generator, n: int) -> np.ndarray:
    """Double-bridge (4-opt) perturbation; falls back to a random swap for n<4."""
    q = perm.copy()
    if n >= 4:
        a, b, c = sorted(rng.choice(np.arange(1, n), size=3, replace=False))
        return np.concatenate([q[:a], q[c:], q[a:b], q[b:c]])
    i, j = rng.choice(n, size=2, replace=False)
    q[i], q[j] = q[j], q[i]
    return q


def _known_best(stem: str, problem_id: str | None) -> int | None:
    return KNOWN_OPTIMA.get(stem) or (
        KNOWN_OPTIMA.get(str(problem_id).lower()) if problem_id else None
    )


def solve_qap(
    distance_matrix: Any = None,
    flow_matrix: Any = None,
    qaplib_path: str | Path | None = None,
    method: str = "hybrid",
    n_repeats: int = 10,
    seed: int = 42,
    problem_id: str | None = None,
) -> dict[str, Any]:
    """Solve a Quadratic Assignment Problem.

    Parameters
    ----------
    distance_matrix, flow_matrix : array-like, optional
        ``n x n`` distance and flow matrices.
    qaplib_path : str | Path, optional
        QAPLIB ``*.dat`` instance; mutually exclusive with the matrices.
    method : {"faq", "2opt", "hybrid"}
    n_repeats : int
        Number of multi-start repetitions (used by ``2opt``/``hybrid``).
    seed : int
    problem_id : str, optional
    """
    t0 = time.time()

    if qaplib_path is None and distance_matrix is None and flow_matrix is None:
        qaplib_path = DEFAULT_FIXTURE

    if qaplib_path is not None:
        A, B, stem_pid = load_qaplib(qaplib_path)
        pid = str(problem_id or stem_pid)
    else:
        if distance_matrix is None or flow_matrix is None:
            raise ValueError("provide distance_matrix+flow_matrix or qaplib_path")
        A = np.asarray(distance_matrix, dtype=float)
        B = np.asarray(flow_matrix, dtype=float)
        pid = str(problem_id or "qap_custom")

    if A.ndim != 2 or A.shape[0] != A.shape[1]:
        raise ValueError(f"distance_matrix must be square 2-D, got shape {A.shape}")
    if B.shape != A.shape:
        raise ValueError(f"flow_matrix shape {B.shape} != distance_matrix shape {A.shape}")

    n = int(A.shape[0])
    method = (method or "hybrid").lower()
    if method not in ("faq", "2opt", "hybrid"):
        raise ValueError(f"unknown QAP method: {method}")
    n_repeats = max(1, int(n_repeats))
    rng = np.random.default_rng(int(seed))

    known_best = _known_best(Path(qaplib_path).stem.lower() if qaplib_path else "", problem_id)

    if method == "faq":
        perm = _faq_run(A, B, int(seed))
        best_obj = _qap_objective(A, B, perm)
    elif method == "2opt":
        best_obj = float("inf")
        best_perm: np.ndarray | None = None
        for r in range(n_repeats):
            p = rng.permutation(n)
            p = _two_opt_refine(A, B, p, int(seed) + r)
            o = _qap_objective(A, B, p)
            if o < best_obj:
                best_obj, best_perm = o, p.copy()
        perm = best_perm
    else:  # hybrid: multi-start FAQ + 2-opt refinement + ILS polish
        best_obj = float("inf")
        best_perm = None
        for r in range(n_repeats):
            s = int(seed) + r
            p = _two_opt_refine(A, B, _faq_run(A, B, s), s)
            o = _qap_objective(A, B, p)
            if o < best_obj:
                best_obj, best_perm = o, p.copy()
        perm = best_perm
        # Iterated local search: double-bridge perturbation + 2-opt.
        if known_best is None or best_obj > known_best:
            for _ in range(max(0, n_repeats * 10)):
                q = _two_opt_refine(A, B, _double_bridge(perm, rng, n), int(rng.integers(0, 2**31 - 1)))
                o = _qap_objective(A, B, q)
                if o < best_obj:
                    best_obj, perm = o, q.copy()
                    if known_best is not None and best_obj <= known_best:
                        break
                elif o == best_obj:
                    perm = q.copy()

    objective = float(_qap_objective(A, B, perm))
    status = "OPTIMAL" if known_best is not None and abs(objective - known_best) < 1e-9 else "FEASIBLE"

    assignments = [
        {"facility_id": int(i), "location_id": int(perm[i])}
        for i in range(n)
    ]

    return {
        "problem_id": pid,
        "problem_class": "qap",
        "mode": "qap",
        "status": status,
        "objective": objective,
        "solver": DEFAULT_SOLVER,
        "source": "tools/solve_qap.py",
        "num_facilities": n,
        "permutation": [int(x) for x in perm],
        "assignments": assignments,
        "distance_matrix": A.tolist(),
        "flow_matrix": B.tolist(),
        "meta": {
            "exact": False,
            "proven_optimal": False,
            "method_class": "metaheuristic",
            "method": method,
            "num_repeats": n_repeats,
            "seed": int(seed),
            "num_facilities": n,
            "known_optimum": known_best,
            "optimality_gap": (objective - known_best) if known_best is not None else None,
            "status_reason": (
                "matches known QAPLIB optimum" if status == "OPTIMAL" else "heuristic solution"
            ),
            "solve_seconds": round(time.time() - t0, 5),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OR-Path QAP solver (SciPy FAQ + 2-opt hybrid)"
    )
    parser.add_argument(
        "--fixture",
        default=str(DEFAULT_FIXTURE),
        help=f"QAPLIB *.dat instance (default: {DEFAULT_FIXTURE.name})",
    )
    parser.add_argument(
        "--method",
        choices=["faq", "2opt", "hybrid"],
        default="hybrid",
        help="Solve method (default: hybrid)",
    )
    parser.add_argument("--repeats", type=int, default=10, help="Multi-start repeats")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    parser.add_argument("--output", default=None, help="Write result JSON to path")
    args = parser.parse_args(argv)

    sol = solve_qap(
        qaplib_path=args.fixture,
        method=args.method,
        n_repeats=args.repeats,
        seed=args.seed,
    )
    out = json.dumps(sol, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if sol.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
