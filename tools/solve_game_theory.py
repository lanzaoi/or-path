#!/usr/bin/env python3
"""Bimatrix Game / Nash Equilibrium Solver — nashpy engine.

Enumerates Nash equilibria of a two-player normal-form (bimatrix) game
using three independent algorithms:

* ``support_enumeration`` — nashpy ``support_enumeration`` (default; exact,
  finds every equilibrium via support enumeration).
* ``lemke_howson``        — nashpy ``lemke_howson`` (exact, one equilibrium
  per initial dropped label).
* ``vertex_enumeration``  — nashpy ``vertex_enumeration`` (exact, polytope
  vertex enumeration; finds every equilibrium).

Inputs
------
* ``fixture_path`` — JSON fixture under
  ``fixtures/benchmarks/game_theory/`` (default: ``prisoners_dilemma.json``).
* ``problem_dict`` — an in-memory problem with ``row_payoffs`` /
  ``col_payoffs`` (and optional ``row_actions``, ``col_actions``,
  ``game_type``).
* Direct ``row_payoffs`` / ``col_payoffs`` arrays.

Output follows the OR-Path "Numbers Truth" envelope (ADR-0002):
``problem_id, problem_class="game_theory", mode="game_theory", status,
objective=expected_payoffs[0], solver, source, game_type, row_actions,
col_actions, num_equilibria, equilibria[], primary_equilibrium{},
game_value, row_regret, col_regret, raw_problem, meta``.

The independent validator (``validators/extended_solvers.py``) re-derives
strategy distributions, dimensions, expected payoffs and best-response
regrets from ``raw_problem`` alone — no solver is re-run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

try:  # nashpy is the designated engine for this solver
    import nashpy as nash
except ImportError as exc:  # pragma: no cover - environment guard
    nash = None  # type: ignore[assignment]
    _NASH_IMPORT_ERROR = str(exc)
else:
    _NASH_IMPORT_ERROR = ""

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

DEFAULT_FIXTURE = (
    _ROOT / "fixtures" / "benchmarks" / "game_theory" / "prisoners_dilemma.json"
)
DEFAULT_METHOD = "support_enumeration"
METHODS = ("support_enumeration", "lemke_howson", "vertex_enumeration")


def _resolve_fixture_path(
    fixture_path: str | Path | None,
    problem_id: str | None,
) -> Path:
    """Resolve a game fixture JSON path (install-root first, then cwd)."""
    if fixture_path is not None:
        p = Path(fixture_path)
        if p.is_file():
            return p
        for base in (_ROOT, Path.cwd()):
            cand = base / fixture_path
            if cand.is_file():
                return cand
        raise FileNotFoundError(f"game fixture not found: {fixture_path}")

    # No explicit path: try <problem_id>.json under the canonical game dir.
    if problem_id:
        pid = str(problem_id).strip()
        for base in (_ROOT, Path.cwd()):
            cand = base / "fixtures" / "benchmarks" / "game_theory" / f"{pid}.json"
            if cand.is_file():
                return cand
        # Also accept a bare fixture stem that matches a shipped game.
        for base in (_ROOT, Path.cwd()):
            for cand in sorted((base / "fixtures" / "benchmarks" / "game_theory").glob("*.json")):
                if cand.stem.lower() == pid.lower():
                    return cand
    return DEFAULT_FIXTURE


def _load_fixture(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"game fixture not found: {p}")
    with p.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"game fixture root must be an object: {p}")
    return data


def _default_actions(prefix: str, n: int) -> list[str]:
    return [f"{prefix}_{i}" for i in range(n)]


def _coerce_payoffs(raw: Any, name: str) -> np.ndarray:
    arr = np.asarray(raw, dtype=float)
    if arr.ndim != 2 or arr.shape[0] < 1 or arr.shape[1] < 1:
        raise ValueError(f"{name} must be a non-empty 2D matrix")
    return arr


def _build_raw_problem(
    problem_dict: dict[str, Any] | None,
    row_payoffs: Any | None,
    col_payoffs: Any | None,
    row_actions: Any | None,
    col_actions: Any | None,
    game_type: str | None,
    fixture_name: str | None,
) -> dict[str, Any]:
    """Normalize every input surface into a single ``raw_problem`` dict."""
    if problem_dict is None:
        if row_payoffs is None and col_payoffs is None:
            # Fall back to the canonical default fixture.
            problem_dict = _load_fixture(DEFAULT_FIXTURE)
        else:
            problem_dict = {}

    A_raw = row_payoffs if row_payoffs is not None else problem_dict.get("row_payoffs")
    B_raw = col_payoffs if col_payoffs is not None else problem_dict.get("col_payoffs")
    if A_raw is None or B_raw is None:
        raise ValueError(
            "game requires row_payoffs and col_payoffs "
            "(via problem_dict, direct args, or a fixture)"
        )

    A = _coerce_payoffs(A_raw, "row_payoffs")
    B = _coerce_payoffs(B_raw, "col_payoffs")
    if A.shape != B.shape:
        raise ValueError(
            f"row_payoffs/col_payoffs shape mismatch: {A.shape} vs {B.shape}"
        )
    n_rows, n_cols = A.shape

    if row_actions is not None:
        row_acts = [str(x) for x in row_actions]
    elif problem_dict.get("row_actions"):
        row_acts = [str(x) for x in problem_dict["row_actions"]]
    else:
        row_acts = _default_actions("Row", n_rows)
    if len(row_acts) != n_rows:
        raise ValueError(f"row_actions length {len(row_acts)} != {n_rows}")

    if col_actions is not None:
        col_acts = [str(x) for x in col_actions]
    elif problem_dict.get("col_actions"):
        col_acts = [str(x) for x in problem_dict["col_actions"]]
    else:
        col_acts = _default_actions("Col", n_cols)
    if len(col_acts) != n_cols:
        raise ValueError(f"col_actions length {len(col_acts)} != {n_cols}")

    gtype = (
        game_type
        or problem_dict.get("game_type")
        or ("zero_sum" if np.allclose(A + B, 0.0, atol=1e-9) else "bimatrix")
    )
    gtype = str(gtype)

    return {
        "name": problem_dict.get("name") or fixture_name or "game_theory",
        "description": problem_dict.get("description", ""),
        "game_type": gtype,
        "row_actions": row_acts,
        "col_actions": col_acts,
        "row_payoffs": [[float(v) for v in row] for row in A],
        "col_payoffs": [[float(v) for v in row] for row in B],
    }


def _is_pure(strat: np.ndarray) -> bool:
    """A strategy is pure when at most one entry is non-zero."""
    return int(np.count_nonzero(strat)) <= 1


def _round_list(strat: np.ndarray) -> list[float]:
    return [float(v) for v in np.asarray(strat, dtype=float)]


def _dedupe_key(strat_pair: tuple[np.ndarray, np.ndarray]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    x, y = strat_pair
    return (tuple(round(float(v), 10) for v in x), tuple(round(float(v), 10) for v in y))


def _collect_equilibria(
    game: "nash.Game",
    method: str,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Run the requested algorithm and return a deduplicated equilibrium list."""
    if nash is None:  # pragma: no cover - guarded by environment
        raise RuntimeError(f"nashpy is required: {_NASH_IMPORT_ERROR}")

    out: list[tuple[np.ndarray, np.ndarray]] = []
    seen: set[Any] = set()

    if method == "support_enumeration":
        for eq in game.support_enumeration():
            x, y = np.asarray(eq[0], dtype=float), np.asarray(eq[1], dtype=float)
            key = _dedupe_key((x, y))
            if key not in seen:
                seen.add(key)
                out.append((x, y))
    elif method == "vertex_enumeration":
        for eq in game.vertex_enumeration():
            x, y = np.asarray(eq[0], dtype=float), np.asarray(eq[1], dtype=float)
            key = _dedupe_key((x, y))
            if key not in seen:
                seen.add(key)
                out.append((x, y))
    elif method == "lemke_howson":
        eq = game.lemke_howson(initial_dropped_label=0)
        x, y = np.asarray(eq[0], dtype=float), np.asarray(eq[1], dtype=float)
        key = _dedupe_key((x, y))
        seen.add(key)
        out.append((x, y))
    else:  # pragma: no cover - guarded by METHODS
        raise ValueError(f"unknown method {method!r}; expected one of {METHODS}")

    return out


def _expected_payoffs(
    A: np.ndarray,
    B: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
) -> tuple[float, float]:
    u_row = float(np.dot(x, np.dot(A, y)))
    u_col = float(np.dot(x, np.dot(B, y)))
    return u_row, u_col


def _best_response_regret(
    A: np.ndarray,
    B: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
) -> tuple[float, float]:
    u_row, u_col = _expected_payoffs(A, B, x, y)
    row_regret = float(np.max(np.dot(A, y)) - u_row)
    col_regret = float(np.max(np.dot(x, B)) - u_col)
    return row_regret, col_regret


def solve_game_theory(
    problem_id: str | None = None,
    fixture_path: str | Path | None = None,
    problem_dict: dict[str, Any] | None = None,
    method: str = DEFAULT_METHOD,
    row_payoffs: Any | None = None,
    col_payoffs: Any | None = None,
    row_actions: Any | None = None,
    col_actions: Any | None = None,
    game_type: str | None = None,
) -> dict[str, Any]:
    """Solve a bimatrix game and emit the OR-Path envelope (ADR-0002).

    ``method`` ∈ {'support_enumeration', 'lemke_howson', 'vertex_enumeration'}.
    The default ``support_enumeration`` finds every Nash equilibrium.
    """
    method_l = (method or DEFAULT_METHOD).lower().strip()
    if method_l not in METHODS:
        raise ValueError(f"unknown method {method!r}; expected one of {METHODS}")

    if nash is None:  # pragma: no cover - environment guard
        raise RuntimeError(f"nashpy is required: {_NASH_IMPORT_ERROR}")

    # Resolve the fixture path first so the fixture name can feed raw_problem.
    resolved_fixture: Path | None = None
    if problem_dict is None and row_payoffs is None and col_payoffs is None:
        resolved_fixture = _resolve_fixture_path(fixture_path, problem_id)
        problem_dict = _load_fixture(resolved_fixture)
        fixture_name = resolved_fixture.stem
    else:
        fixture_name = None

    raw = _build_raw_problem(
        problem_dict=problem_dict,
        row_payoffs=row_payoffs,
        col_payoffs=col_payoffs,
        row_actions=row_actions,
        col_actions=col_actions,
        game_type=game_type,
        fixture_name=fixture_name,
    )
    A = np.asarray(raw["row_payoffs"], dtype=float)
    B = np.asarray(raw["col_payoffs"], dtype=float)

    game = nash.Game(A, B)
    eqs = _collect_equilibria(game, method_l)
    if not eqs:
        raise RuntimeError(
            f"{method_l} found no equilibrium for game "
            f"'{raw.get('name')}' (this is unexpected for finite games)"
        )

    # Primary = first discovered equilibrium (Numbers Truth: no invented choice).
    primary_x, primary_y = eqs[0]
    u_row, u_col = _expected_payoffs(A, B, primary_x, primary_y)
    row_regret, col_regret = _best_response_regret(A, B, primary_x, primary_y)
    is_zero_sum = bool(np.allclose(A + B, 0.0, atol=1e-9))
    game_value = float(u_row) if is_zero_sum else None

    equilibria: list[dict[str, Any]] = []
    for x, y in eqs:
        ur, uc = _expected_payoffs(A, B, x, y)
        equilibria.append(
            {
                "row_strategy": _round_list(x),
                "col_strategy": _round_list(y),
                "expected_payoffs": [ur, uc],
                "is_pure": bool(_is_pure(x) and _is_pure(y)),
            }
        )

    primary_equilibrium = equilibria[0]

    envelope: dict[str, Any] = {
        "problem_id": problem_id or raw.get("name") or "game_theory",
        "problem_class": "game_theory",
        "mode": "game_theory",
        "status": "OPTIMAL",
        "objective": round(u_row, 6),
        "solver": "nashpy-engine",
        "source": "tools/solve_game_theory.py",
        "game_type": raw.get("game_type", "bimatrix"),
        "row_actions": list(raw["row_actions"]),
        "col_actions": list(raw["col_actions"]),
        "num_equilibria": len(equilibria),
        "equilibria": equilibria,
        "primary_equilibrium": primary_equilibrium,
        "primary_row_strategy": primary_equilibrium["row_strategy"],
        "primary_col_strategy": primary_equilibrium["col_strategy"],
        "expected_payoffs": primary_equilibrium["expected_payoffs"],
        "game_value": game_value,
        "row_regret": row_regret,
        "col_regret": col_regret,
        "raw_problem": raw,
        "meta": {
            "exact": True,
            "proven_optimal": True,
            "method_class": "exact",
            "method": method_l,
            "engine": "nashpy",
            "is_zero_sum": is_zero_sum,
            "num_row_actions": int(A.shape[0]),
            "num_col_actions": int(A.shape[1]),
        },
    }
    return envelope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OR-Path Bimatrix Game / Nash Equilibrium solver (nashpy)"
    )
    parser.add_argument(
        "problem_id",
        nargs="?",
        default="prisoners_dilemma",
        help="Game fixture stem (e.g. prisoners_dilemma, matching_pennies)",
    )
    parser.add_argument(
        "--fixture",
        default=None,
        help="Game fixture JSON path (default: fixtures/benchmarks/game_theory/"
        "prisoners_dilemma.json)",
    )
    parser.add_argument(
        "--method",
        choices=list(METHODS),
        default=DEFAULT_METHOD,
        help="Equilibrium enumeration algorithm (default: support_enumeration)",
    )
    parser.add_argument("--output", default=None, help="Write result JSON to path")
    args = parser.parse_args(argv)

    sol = solve_game_theory(
        problem_id=args.problem_id,
        fixture_path=args.fixture,
        method=args.method,
    )
    out = json.dumps(sol, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if sol.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
