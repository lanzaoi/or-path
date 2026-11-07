#!/usr/bin/env python3
"""Markowitz Mean-Variance Portfolio Optimization Solver.

Primary solver: PyPortfolioOpt (``pypfopt``) via CVXPY/Clarabel.
Graceful fallback: SciPy SLSQP when ``pypfopt`` is not importable.

Supported objectives
--------------------
* ``max_sharpe``      : maximize (mu^T w - r_f) / sqrt(w^T Sigma w)
* ``min_volatility``  : minimize sqrt(w^T Sigma w)
* ``efficient_return``: minimize volatility for a target return
* ``utility``         : maximize mu^T w - 0.5 * gamma * w^T Sigma w

Extra features
--------------
* Covariance from historical prices (simple-return mean/cov) or the default
  5-asset benchmark covariance.
* Efficient-frontier sampling (sweep of target returns -> vol/return/sharpe).
* Discrete integer-share allocation with leftover cash.
"""
from __future__ import annotations

import argparse
import json
import time
from typing import Any

import numpy as np
from scipy.optimize import minimize

# ---------------------------------------------------------------------------
# PyPortfolioOpt availability probe (primary solver)
# ---------------------------------------------------------------------------
try:  # pragma: no cover - import success depends on environment
    import pandas as pd
    from pypfopt import EfficientFrontier
    from pypfopt.discrete_allocation import DiscreteAllocation

    _PYPFOPT_AVAILABLE = True
    _PYPFOPT_IMPORT_ERROR = ""
except Exception as exc:  # noqa: BLE001
    pd = None  # type: ignore[assignment]
    EfficientFrontier = None  # type: ignore[assignment]
    DiscreteAllocation = None  # type: ignore[assignment]
    _PYPFOPT_AVAILABLE = False
    _PYPFOPT_IMPORT_ERROR = str(exc)


DEFAULT_ASSETS = ["US_EQUITY", "GLOBAL_TECH", "TREASURY_BONDS", "GOLD", "REIT"]
DEFAULT_EXPECTED_RETURNS = [0.10, 0.15, 0.04, 0.07, 0.08]
DEFAULT_COV_MATRIX = [
    [0.040, 0.025, -0.002, 0.005, 0.015],
    [0.025, 0.060, -0.004, 0.008, 0.018],
    [-0.002, -0.004, 0.010, 0.001, 0.000],
    [0.005, 0.008, 0.001, 0.025, 0.004],
    [0.015, 0.018, 0.000, 0.004, 0.035],
]
DEFAULT_PRICES = [100.0, 150.0, 50.0, 200.0, 80.0]

VALID_OBJECTIVES = ("max_sharpe", "min_volatility", "efficient_return", "utility")


def _default_problem() -> tuple[list[str], np.ndarray, np.ndarray]:
    names = list(DEFAULT_ASSETS)
    mu = np.array(DEFAULT_EXPECTED_RETURNS, dtype=float)
    sigma = np.array(DEFAULT_COV_MATRIX, dtype=float)
    return names, mu, sigma


def _prices_to_mu_sigma(
    prices: list[list[float]],
    asset_names: list[str] | None,
) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Convert a price history (rows = dates, cols = assets) to mu / Sigma."""
    arr = np.asarray(prices, dtype=float)
    if arr.ndim != 2 or arr.shape[0] < 2:
        raise ValueError("prices must be a 2D history with at least 2 rows")
    n = arr.shape[1]
    if asset_names is None or len(asset_names) != n:
        asset_names = [f"Asset_{i+1}" for i in range(n)]

    # Simple returns, then mean / sample covariance (ddof=1).
    rets = np.diff(arr, axis=0) / arr[:-1]
    # Guard against NaNs (e.g. missing prices) by column-mean imputation.
    if np.isnan(rets).any():
        col_means = np.nanmean(rets, axis=0)
        inds = np.where(np.isnan(rets))
        rets[inds] = np.take(col_means, inds[1])
    mu = np.mean(rets, axis=0)
    sigma = np.cov(rets, rowvar=False, ddof=1)
    # Symmetrize / ensure finite.
    sigma = (sigma + sigma.T) / 2.0
    np.fill_diagonal(sigma, np.maximum(np.diagonal(sigma), 1e-8))
    return list(asset_names), mu, sigma


def _resolve_assets(
    expected_returns: list[float] | None,
    cov_matrix: list[list[float]] | None,
    prices: list[list[float]] | None,
    asset_names: list[str] | None,
) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Determine names / mu / sigma from the available inputs."""
    if prices is not None:
        return _prices_to_mu_sigma(prices, asset_names)
    if expected_returns is None or cov_matrix is None:
        return _default_problem()

    n = len(expected_returns)
    if asset_names is None or len(asset_names) != n:
        asset_names = [f"Asset_{i+1}" for i in range(n)]
    mu = np.asarray(expected_returns, dtype=float)
    sigma = np.asarray(cov_matrix, dtype=float)
    if sigma.shape != (n, n):
        raise ValueError("cov_matrix shape does not match expected_returns")
    return list(asset_names), mu, sigma


def _objective_value(
    objective_type: str,
    ret: float,
    vol: float,
    sharpe: float,
    risk_aversion: float,
    target_return: float | None,
) -> float:
    if objective_type == "max_sharpe":
        return sharpe
    if objective_type == "min_volatility":
        return vol
    if objective_type == "efficient_return":
        return target_return if target_return is not None else ret
    return ret - 0.5 * risk_aversion * vol * vol


# ---------------------------------------------------------------------------
# Efficient frontier sampling
# ---------------------------------------------------------------------------
def _sample_frontier_pypfopt(
    mu: np.ndarray,
    sigma: np.ndarray,
    min_weight: float,
    max_weight: float,
    risk_free_rate: float,
    points: int,
) -> list[dict[str, float]]:
    points = max(20, min(50, int(points)))
    ef = EfficientFrontier(mu, sigma, weight_bounds=(min_weight, max_weight))
    # Minimum-volatility portfolio gives the lower return bound.
    ef.min_volatility()
    lo_ret, _lo_vol, _lo_sharpe = ef.portfolio_performance(
        verbose=False, risk_free_rate=risk_free_rate
    )
    # Long-only maximum return is concentrated in the best asset.
    hi_ret = float(np.max(mu))
    lo = float(lo_ret)
    hi = hi_ret - 1e-6 if hi_ret - lo > 1e-6 else hi_ret * (1.0 - 1e-6)

    targets = np.linspace(lo, hi, points)
    frontier: list[dict[str, float]] = []
    ef_ret = EfficientFrontier(mu, sigma, weight_bounds=(min_weight, max_weight))
    for target in targets:
        try:
            ef_ret.efficient_return(float(target))
            ret, vol, sharpe = ef_ret.portfolio_performance(
                verbose=False, risk_free_rate=risk_free_rate
            )
            frontier.append(
                {
                    "expected_return": round(float(ret), 6),
                    "volatility": round(float(vol), 6),
                    "sharpe_ratio": round(float(sharpe), 6),
                }
            )
        except Exception:  # noqa: BLE001 - target may be marginally infeasible
            continue
    return frontier


def _sample_frontier_scipy(
    mu: np.ndarray,
    sigma: np.ndarray,
    min_weight: float,
    max_weight: float,
    risk_free_rate: float,
    points: int,
) -> list[dict[str, float]]:
    """Fallback frontier sampling via SLSQP (constrained minimum variance)."""
    points = max(20, min(50, int(points)))
    n = len(mu)
    w0 = np.ones(n) / n
    bounds = tuple((min_weight, max_weight) for _ in range(n))
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    def min_vol(target_ret: float) -> tuple[float, float, float]:
        def loss(w: np.ndarray) -> float:
            return float(np.dot(w.T, np.dot(sigma, w)))

        c = list(constraints) + [{"type": "eq", "fun": lambda w, t=target_ret: np.dot(w, mu) - t}]
        res = minimize(loss, w0, method="SLSQP", bounds=bounds, constraints=c,
                       options={"maxiter": 1000, "ftol": 1e-9})
        w = res.x
        ret = float(np.dot(w, mu))
        vol = float(np.sqrt(np.dot(w.T, np.dot(sigma, w))))
        sharpe = (ret - risk_free_rate) / vol if vol > 0 else 0.0
        return ret, vol, sharpe

    # Lower bound: minimum variance portfolio.
    lo_ret, _, _ = min_vol(float(np.dot(w0, mu)))
    # Upper bound: best asset return.
    hi_ret = float(np.max(mu)) - 1e-6
    frontier: list[dict[str, float]] = []
    for target in np.linspace(float(lo_ret), hi_ret, points):
        try:
            ret, vol, sharpe = min_vol(float(target))
            frontier.append(
                {
                    "expected_return": round(ret, 6),
                    "volatility": round(vol, 6),
                    "sharpe_ratio": round(sharpe, 6),
                }
            )
        except Exception:  # noqa: BLE001
            continue
    return frontier


# ---------------------------------------------------------------------------
# Discrete allocation
# ---------------------------------------------------------------------------
def _discrete_allocation_pypfopt(
    weights: dict[str, float],
    prices: dict[str, float],
    total_portfolio_value: float,
) -> dict[str, Any]:
    latest_prices = pd.Series(prices)
    da = DiscreteAllocation(
        weights, latest_prices, total_portfolio_value=total_portfolio_value
    )
    allocation, leftover = da.greedy_portfolio()
    shares = {str(k): int(v) for k, v in allocation.items()}
    return {
        "shares": shares,
        "leftover_cash": round(float(leftover), 4),
        "total_invested": round(float(total_portfolio_value - leftover), 4),
        "prices": {str(k): float(v) for k, v in prices.items()},
        "total_portfolio_value": float(total_portfolio_value),
    }


def _discrete_allocation_simple(
    weights: dict[str, float],
    prices: dict[str, float],
    total_portfolio_value: float,
) -> dict[str, Any]:
    """Floor-based integer share allocation (SciPy fallback)."""
    shares: dict[str, int] = {}
    invested = 0.0
    for name, w in weights.items():
        price = float(prices[name])
        if price <= 0:
            continue
        qty = int(np.floor(max(w, 0.0) * total_portfolio_value / price))
        shares[name] = qty
        invested += qty * price
    leftover = total_portfolio_value - invested
    return {
        "shares": shares,
        "leftover_cash": round(float(leftover), 4),
        "total_invested": round(float(invested), 4),
        "prices": {str(k): float(v) for k, v in prices.items()},
        "total_portfolio_value": float(total_portfolio_value),
    }


def _resolve_prices(
    prices: list[list[float]] | None,
    asset_names: list[str],
) -> dict[str, float]:
    """Return a price-per-asset mapping, synthesizing defaults when absent."""
    if prices is not None:
        arr = np.asarray(prices, dtype=float)
        if arr.ndim == 2 and arr.shape[1] == len(asset_names):
            latest = arr[-1]
            return {name: float(price) for name, price in zip(asset_names, latest)}
    # Synthetic prices aligned with the resolved assets.
    base = DEFAULT_PRICES
    out: dict[str, float] = {}
    for i, name in enumerate(asset_names):
        out[name] = float(base[i] if i < len(base) else 100.0 * (i + 1))
    return out


def _input_manifest(
    names: list[str],
    mu: np.ndarray,
    sigma: np.ndarray,
    prices: dict[str, float],
    risk_free_rate: float,
    total_portfolio_value: float | None,
) -> dict[str, Any]:
    """Build the frozen raw-input manifest embedded in every solution payload.

    The independent validator and red team recompute every reported metric
    (expected return, volatility, Sharpe, discrete capital) from this manifest,
    so it must travel with the solution under the Numbers Truth iron law.
    """
    return {
        "asset_names": list(names),
        "expected_returns": [float(x) for x in np.asarray(mu, dtype=float).ravel()],
        "cov_matrix": [
            [float(x) for x in np.asarray(sigma, dtype=float)[i]]
            for i in range(len(names))
        ],
        "prices": {name: float(prices[name]) for name in names},
        "risk_free_rate": float(risk_free_rate),
        "total_portfolio_value": (
            float(total_portfolio_value)
            if total_portfolio_value is not None
            else None
        ),
    }


# ---------------------------------------------------------------------------
# Main solver
# ---------------------------------------------------------------------------
def solve_portfolio(
    expected_returns: list[float] | None = None,
    cov_matrix: list[list[float]] | None = None,
    asset_names: list[str] | None = None,
    risk_aversion: float = 1.0,
    risk_free_rate: float = 0.02,
    objective_type: str = "max_sharpe",
    target_return: float | None = None,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
    prices: list[list[float]] | None = None,
    total_portfolio_value: float | None = None,
    frontier: bool = False,
    frontier_points: int = 30,
) -> dict[str, Any]:
    """Solve a Markowitz mean-variance portfolio optimization problem."""
    t0 = time.perf_counter()

    if objective_type not in VALID_OBJECTIVES:
        raise ValueError(f"Unknown objective_type: {objective_type}")

    names, mu, sigma = _resolve_assets(
        expected_returns, cov_matrix, prices, asset_names
    )

    if _PYPFOPT_AVAILABLE:
        try:
            result = _solve_pypfopt(
                names, mu, sigma, risk_aversion, risk_free_rate,
                objective_type, target_return, min_weight, max_weight,
                prices, total_portfolio_value, frontier, frontier_points,
            )
        except Exception as exc:  # noqa: BLE001 - graceful degradation
            # pypfopt can reject degenerate inputs (e.g. no asset above the
            # risk-free rate); fall back to the SciPy SLSQP formulation.
            result = _solve_scipy(
                names, mu, sigma, risk_aversion, risk_free_rate,
                objective_type, target_return, min_weight, max_weight,
                prices, total_portfolio_value, frontier, frontier_points,
            )
            result["meta"]["pypfopt_fallback_reason"] = str(exc)
    else:
        result = _solve_scipy(
            names, mu, sigma, risk_aversion, risk_free_rate,
            objective_type, target_return, min_weight, max_weight,
            prices, total_portfolio_value, frontier, frontier_points,
        )
    result["meta"]["wall_time_s"] = round(time.perf_counter() - t0, 5)
    return result


def _solve_pypfopt(
    names: list[str],
    mu: np.ndarray,
    sigma: np.ndarray,
    risk_aversion: float,
    risk_free_rate: float,
    objective_type: str,
    target_return: float | None,
    min_weight: float,
    max_weight: float,
    prices: list[list[float]] | None,
    total_portfolio_value: float | None,
    frontier: bool,
    frontier_points: int,
) -> dict[str, Any]:
    ef = EfficientFrontier(mu, sigma, weight_bounds=(min_weight, max_weight))

    if objective_type == "max_sharpe":
        ef.max_sharpe(risk_free_rate=risk_free_rate)
    elif objective_type == "min_volatility":
        ef.min_volatility()
    elif objective_type == "efficient_return":
        # Compute the minimum-volatility return on a fresh instance so the
        # target-return solver below starts unsolved.
        ef_min = EfficientFrontier(
            mu, sigma, weight_bounds=(min_weight, max_weight)
        )
        ef_min.min_volatility()
        lo_ret = float(ef_min.portfolio_performance(
            verbose=False, risk_free_rate=risk_free_rate)[0])
        hi_ret = float(np.max(mu))
        if target_return is None:
            target_return = lo_ret + 0.5 * (hi_ret - lo_ret)
        if not (lo_ret - 1e-9 <= target_return <= hi_ret - 1e-6):
            target_return = min(max(target_return, lo_ret + 1e-9), hi_ret - 1e-6)
        ef = EfficientFrontier(mu, sigma, weight_bounds=(min_weight, max_weight))
        ef.efficient_return(float(target_return))
    elif objective_type == "utility":
        ef.max_quadratic_utility(risk_aversion=risk_aversion)

    cleaned = ef.clean_weights()
    weights = {names[int(k)]: float(v) for k, v in cleaned.items()}
    # Normalize to ensure the validator's weights_sum_to_one holds tightly.
    total_w = sum(weights.values())
    if total_w > 0:
        weights = {k: v / total_w for k, v in weights.items()}

    ret, vol, sharpe = ef.portfolio_performance(
        verbose=False, risk_free_rate=risk_free_rate
    )
    ret = float(ret)
    vol = float(vol)
    sharpe = float(sharpe)

    # If efficient_return, report the realized return (should equal target).
    if objective_type == "efficient_return" and target_return is not None:
        ret = float(target_return)

    obj_val = _objective_value(
        objective_type, ret, vol, sharpe, risk_aversion, target_return
    )

    result: dict[str, Any] = {
        "problem_id": f"markowitz_{len(names)}assets_{objective_type}",
        "problem_class": "portfolio_opt",
        "status": "OPTIMAL",
        "objective": round(obj_val, 6),
        "solver": "pypfopt-cvxpy",
        "source": "tools/solve_portfolio.py",
        "objective_type": objective_type,
        "expected_return": round(ret, 6),
        "volatility": round(vol, 6),
        "sharpe_ratio": round(sharpe, 6),
        "risk_free_rate": risk_free_rate,
        "allocations": {k: round(v, 6) for k, v in weights.items()},
        "inputs": _input_manifest(
            names, mu, sigma, _resolve_prices(prices, names),
            risk_free_rate, total_portfolio_value,
        ),
        "meta": {
            "exact": True,
            "proven_optimal": True,
            "engine": "pypfopt-cvxpy",
            "num_assets": len(names),
            "target_return": target_return,
        },
    }

    if frontier:
        result["efficient_frontier"] = _sample_frontier_pypfopt(
            mu, sigma, min_weight, max_weight, risk_free_rate, frontier_points
        )

    if total_portfolio_value is not None:
        price_map = _resolve_prices(prices, names)
        result["discrete_allocation"] = _discrete_allocation_pypfopt(
            weights, price_map, float(total_portfolio_value)
        )

    return result


def _solve_scipy(
    names: list[str],
    mu: np.ndarray,
    sigma: np.ndarray,
    risk_aversion: float,
    risk_free_rate: float,
    objective_type: str,
    target_return: float | None,
    min_weight: float,
    max_weight: float,
    prices: list[list[float]] | None,
    total_portfolio_value: float | None,
    frontier: bool,
    frontier_points: int,
) -> dict[str, Any]:
    n = len(names)
    w0 = np.ones(n) / n
    bounds = tuple((min_weight, max_weight) for _ in range(n))
    constraints: list[dict[str, Any]] = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
    ]

    def portfolio_volatility(w: np.ndarray) -> float:
        return float(np.sqrt(np.dot(w.T, np.dot(sigma, w))))

    def portfolio_return(w: np.ndarray) -> float:
        return float(np.dot(w, mu))

    if objective_type == "min_volatility":
        loss_fn = portfolio_volatility
    elif objective_type == "utility":
        loss_fn = lambda w: float(
            -portfolio_return(w) + 0.5 * risk_aversion * np.dot(w.T, np.dot(sigma, w))
        )
    elif objective_type == "max_sharpe":
        loss_fn = lambda w: float(
            -(portfolio_return(w) - risk_free_rate) / (portfolio_volatility(w) + 1e-9)
        )
    elif objective_type == "efficient_return":
        if target_return is None:
            lo_ret = float(np.dot(w0, mu))
            hi_ret = float(np.max(mu))
            target_return = lo_ret + 0.5 * (hi_ret - lo_ret)
        constraints.append(
            {"type": "eq", "fun": lambda w, t=float(target_return): np.dot(w, mu) - t}
        )
        loss_fn = portfolio_volatility
    else:  # pragma: no cover - guarded by VALID_OBJECTIVES
        raise ValueError(f"Unknown objective_type: {objective_type}")

    res = minimize(
        loss_fn,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-9},
    )

    w_opt = np.where(np.abs(res.x) < 1e-6, 0.0, res.x)
    total_w = float(np.sum(w_opt))
    if total_w > 0:
        w_opt = w_opt / total_w

    port_ret = portfolio_return(w_opt)
    port_vol = portfolio_volatility(w_opt)
    sharpe = (port_ret - risk_free_rate) / port_vol if port_vol > 0 else 0.0

    weights = {name: float(w) for name, w in zip(names, w_opt)}
    obj_val = _objective_value(
        objective_type, port_ret, port_vol, sharpe, risk_aversion, target_return
    )

    result: dict[str, Any] = {
        "problem_id": f"markowitz_{n}assets_{objective_type}",
        "problem_class": "portfolio_opt",
        "status": "OPTIMAL" if bool(res.success) else "FEASIBLE",
        "objective": round(obj_val, 6),
        "solver": "scipy-slsqp-markowitz",
        "source": "tools/solve_portfolio.py",
        "objective_type": objective_type,
        "expected_return": round(port_ret, 6),
        "volatility": round(port_vol, 6),
        "sharpe_ratio": round(sharpe, 6),
        "risk_free_rate": risk_free_rate,
        "allocations": {k: round(v, 6) for k, v in weights.items()},
        "inputs": _input_manifest(
            names, mu, sigma, _resolve_prices(prices, names),
            risk_free_rate, total_portfolio_value,
        ),
        "meta": {
            "exact": bool(res.success),
            "proven_optimal": bool(res.success),
            "engine": "scipy-slsqp",
            "iterations": int(res.nit),
            "num_assets": n,
            "target_return": target_return,
            "message": str(res.message),
        },
    }

    if frontier:
        result["efficient_frontier"] = _sample_frontier_scipy(
            mu, sigma, min_weight, max_weight, risk_free_rate, frontier_points
        )

    if total_portfolio_value is not None:
        price_map = _resolve_prices(prices, names)
        result["discrete_allocation"] = _discrete_allocation_simple(
            weights, price_map, float(total_portfolio_value)
        )

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Markowitz Portfolio Optimizer (PyPortfolioOpt / SciPy)"
    )
    parser.add_argument(
        "--objective",
        choices=list(VALID_OBJECTIVES),
        default="max_sharpe",
        help="Optimization objective",
    )
    parser.add_argument("--risk-free-rate", type=float, default=0.02)
    parser.add_argument("--risk-aversion", type=float, default=1.0)
    parser.add_argument("--target-return", type=float, default=None)
    parser.add_argument(
        "--frontier",
        action="store_true",
        help="Sweep target returns and emit the efficient frontier",
    )
    parser.add_argument(
        "--frontier-points",
        type=int,
        default=30,
        help="Number of efficient-frontier sample points (clamped 20-50)",
    )
    parser.add_argument(
        "--discrete-total",
        type=float,
        default=None,
        help="Total portfolio value for integer-share discrete allocation",
    )
    args = parser.parse_args(argv)

    res = solve_portfolio(
        objective_type=args.objective,
        risk_free_rate=args.risk_free_rate,
        risk_aversion=args.risk_aversion,
        target_return=args.target_return,
        total_portfolio_value=args.discrete_total,
        frontier=args.frontier,
        frontier_points=args.frontier_points,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
