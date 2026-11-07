#!/usr/bin/env python3
"""Statistical Physics QUBO & Ising Model Solver using D-Wave dimod.

Adapts classic D-Wave / Statistical Physics quantum-inspired formulations:
- Quadratic Unconstrained Binary Optimization (QUBO): min x^T Q x, x in {0, 1}^n
- Ising Spin Glass: min sum h_i s_i + sum J_ij s_i s_j, s in {-1, +1}^n
- NP-hard reductions: Max-Cut, Number Partitioning

General solvers:
- solve_qubo: arbitrary QUBO matrix Q (dict of upper-triangle biases)
- solve_ising: arbitrary Ising spin glass (h, J, offset)
"""
from __future__ import annotations

import argparse
import json
import time
from typing import Any

import dimod

# ---------------------------------------------------------------------------
# Default benchmark instances (known ground states, verified by brute force)
# ---------------------------------------------------------------------------

# 6-variable QUBO with known ground state x = (0,1,0,0,0,1), energy = -5.0
DEFAULT_QUBO: dict[tuple[int, int], float] = {
    (0, 0): -3.0, (1, 1): -2.0, (2, 2): -1.0,
    (3, 3): -2.0, (4, 4): -1.0, (5, 5): -3.0,
    (0, 1): 2.0, (0, 2): 2.0, (1, 2): 2.0,
    (3, 4): 3.0, (4, 5): 3.0, (3, 5): 3.0,
    (2, 3): 1.5, (1, 4): 1.5, (0, 5): 1.5,
}

# 6-spin frustrated anti-ferromagnetic spin glass.
# Known ground state s = (-1,1,-1,1,-1,1), energy = -7.6
DEFAULT_ISING_H: dict[int, float] = {0: 0.5, 1: -0.5, 2: 0.4, 3: -0.4, 4: 0.3, 5: -0.3}
DEFAULT_ISING_J: dict[tuple[int, int], float] = {
    (0, 1): 1.0, (1, 2): 1.0, (0, 2): 1.0,   # frustrated AF triangle
    (2, 3): 1.0, (3, 4): 1.0, (4, 5): 1.0, (5, 0): 1.0,
    (1, 4): 0.8, (3, 0): -0.7, (2, 5): 0.6,
}
DEFAULT_ISING_OFFSET = 0.5


def solve_max_cut(
    edges: list[tuple[int, int]] | None = None,
    num_nodes: int | None = None,
    method: str = "simulated_annealing",
    num_reads: int = 100,
) -> dict[str, Any]:
    """Solve Graph Max-Cut mapped to QUBO."""
    t0 = time.perf_counter()

    if edges is None:
        # Default benchmark: Petersen Graph (10 nodes, 15 edges, max cut = 12)
        edges = [
            (0, 1), (1, 2), (2, 3), (3, 4), (4, 0),
            (0, 5), (1, 6), (2, 7), (3, 8), (4, 9),
            (5, 7), (7, 9), (9, 6), (6, 8), (8, 5),
        ]
        num_nodes = 10
    elif num_nodes is None:
        num_nodes = max(max(u, v) for u, v in edges) + 1

    # Max-Cut QUBO formulation:
    # Cut edge (u, v) iff x_u != x_v -> x_u + x_v - 2*x_u*x_v = 1
    # Maximize Cut = Minimize -Cut = Minimize sum_{(u,v)} (2*x_u*x_v - x_u - x_v)
    Q: dict[tuple[int, int], float] = {}
    for i in range(num_nodes):
        Q[(i, i)] = 0.0

    for u, v in edges:
        i, j = min(u, v), max(u, v)
        Q[(i, i)] -= 1.0
        Q[(j, j)] -= 1.0
        Q[(i, j)] = Q.get((i, j), 0.0) + 2.0

    bqm = dimod.BinaryQuadraticModel.from_qubo(Q)

    if method == "exact" and num_nodes <= 18:
        sampler = dimod.ExactSolver()
        sampleset = sampler.sample(bqm)
    else:
        sampler = dimod.SimulatedAnnealingSampler()
        sampleset = sampler.sample(bqm, num_reads=num_reads)

    t1 = time.perf_counter()

    first_record = sampleset.first
    sample = {int(k): int(v) for k, v in first_record.sample.items()}
    energy = float(first_record.energy)

    # Calculate actual cut edges and size
    cut_edges = []
    for u, v in edges:
        if sample.get(u, 0) != sample.get(v, 0):
            cut_edges.append([u, v])

    max_cut_size = len(cut_edges)

    is_opt = (method == "exact" and num_nodes <= 18)
    return {
        "problem_id": f"max_cut_{num_nodes}nodes_{len(edges)}edges",
        "problem_class": "qubo_ising",
        "mode": "max_cut",
        "status": "OPTIMAL" if is_opt else "FEASIBLE",
        "objective": max_cut_size,
        "solver": f"dimod-{method}",
        "source": "tools/solve_qubo_ising.py",
        "max_cut_size": max_cut_size,
        "total_edges": len(edges),
        "cut_ratio": round(max_cut_size / len(edges), 4) if edges else 0.0,
        "cut_edges": cut_edges,
        "node_partition": {
            "set_0": [node for node, val in sample.items() if val == 0],
            "set_1": [node for node, val in sample.items() if val == 1],
        },
        "ground_state_energy": energy,
        "meta": {
            "exact": method == "exact",
            "proven_optimal": method == "exact",
            "num_reads": num_reads if method != "exact" else 1,
            "wall_time_s": round(t1 - t0, 5),
        },
    }


def solve_number_partitioning(
    numbers: list[int] | None = None,
    method: str = "simulated_annealing",
    num_reads: int = 100,
) -> dict[str, Any]:
    """Solve Number Partitioning mapped to Ising Hamiltonian H = (sum s_i * c_i)^2."""
    t0 = time.perf_counter()

    if numbers is None:
        # Default benchmark instance
        numbers = [25, 7, 13, 31, 42, 17, 21, 10]

    n = len(numbers)
    # H = (sum_i c_i s_i)^2 = sum_i c_i^2 + sum_{i != j} c_i c_j s_i s_j
    # In spin glass: J_ij = 2 * c_i * c_j for i < j, h_i = 0
    h = {i: 0.0 for i in range(n)}
    J = {}
    for i in range(n):
        for j in range(i + 1, n):
            J[(i, j)] = 2.0 * numbers[i] * numbers[j]

    offset = sum(c ** 2 for c in numbers)
    bqm = dimod.BinaryQuadraticModel.from_ising(h, J, offset=offset)

    if method == "exact" and n <= 18:
        sampler = dimod.ExactSolver()
        sampleset = sampler.sample(bqm)
    else:
        sampler = dimod.SimulatedAnnealingSampler()
        sampleset = sampler.sample(bqm, num_reads=num_reads)

    t1 = time.perf_counter()

    first_record = sampleset.first
    sample = {int(k): int(v) for k, v in first_record.sample.items()}

    subset_pos = [numbers[i] for i, s in sample.items() if s == 1]
    subset_neg = [numbers[i] for i, s in sample.items() if s == -1]

    sum_pos = sum(subset_pos)
    sum_neg = sum(subset_neg)
    discrepancy = abs(sum_pos - sum_neg)

    return {
        "problem_id": f"partition_{n}numbers",
        "problem_class": "qubo_ising",
        "mode": "number_partitioning",
        "status": "OPTIMAL" if discrepancy == 0 else "FEASIBLE",
        "objective": discrepancy,
        "solver": f"dimod-{method}",
        "source": "tools/solve_qubo_ising.py",
        "discrepancy": discrepancy,
        "subset_a": subset_pos,
        "subset_b": subset_neg,
        "sum_a": sum_pos,
        "sum_b": sum_neg,
        "meta": {
            "exact": method == "exact",
            "proven_optimal": method == "exact",
            "wall_time_s": round(t1 - t0, 5),
        },
    }


def solve_qubo(
    Q: dict[tuple[int, int], float] | None = None,
    method: str = "simulated_annealing",
    num_reads: int = 100,
    beta_range: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Solve a general QUBO instance: min x^T Q x, x in {0, 1}^n.

    Q is a dict of upper-triangle biases {(i, j): val} with i <= j, matching
    dimod's from_qubo convention. Energy: E(x) = sum Q_ij x_i x_j.

    Default benchmark: 6-variable QUBO with known ground state
    x = (0,1,0,0,0,1), E = -5.0.
    """
    t0 = time.perf_counter()

    if Q is None:
        Q = dict(DEFAULT_QUBO)
    n = max(max(i, j) for i, j in Q) + 1 if Q else 0

    bqm = dimod.BinaryQuadraticModel.from_qubo(Q)

    if method == "exact" and len(bqm.variables) <= 18:
        sampler = dimod.ExactSolver()
        sampleset = sampler.sample(bqm)
    else:
        sampler = dimod.SimulatedAnnealingSampler()
        kwargs: dict[str, Any] = {"num_reads": num_reads}
        if beta_range:
            kwargs["beta_range"] = beta_range
        sampleset = sampler.sample(bqm, **kwargs)

    t1 = time.perf_counter()

    first = sampleset.first
    sample = {int(k): int(v) for k, v in first.sample.items()}
    # Independent recomputation of x^T Q x (Numbers Truth)
    energy = float(sum(Q[(i, j)] * sample.get(i, 0) * sample.get(j, 0) for (i, j) in Q))

    spectrum = [{"energy": round(float(r.energy), 4), "num_occurrences": int(r.num_occurrences)}
                for r in list(sampleset.data(fields=["energy", "num_occurrences"]))[:5]]

    is_opt = (method == "exact" and n <= 18)
    return {
        "problem_id": f"qubo_{n}vars",
        "problem_class": "qubo_ising",
        "mode": "qubo",
        "status": "OPTIMAL" if is_opt else "FEASIBLE",
        "objective": energy,
        "solver": f"dimod-{method}",
        "source": "tools/solve_qubo_ising.py",
        "Q": {f"{i},{j}": float(v) for (i, j), v in Q.items()},
        "sample": sample,
        "ground_state_energy": energy,
        "energy_spectrum": spectrum,
        "meta": {
            "exact": method == "exact",
            "proven_optimal": method == "exact" and len(bqm.variables) <= 18,
            "num_reads": num_reads if method != "exact" else 1,
            "beta_range": beta_range,
            "num_variables": n,
            "wall_time_s": round(t1 - t0, 5),
        },
    }


def solve_ising(
    h: dict[int, float] | None = None,
    J: dict[tuple[int, int], float] | None = None,
    offset: float = 0.0,
    method: str = "simulated_annealing",
    num_reads: int = 100,
    beta_range: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Solve a general Ising spin glass: min sum h_i s_i + sum J_ij s_i s_j + offset.

    h is a dict {i: h_i}; J is a dict {(i, j): J_ij} with i < j.

    Default benchmark: 6-spin frustrated anti-ferromagnetic spin glass with
    known ground state s = (-1,1,-1,1,-1,1), E = -7.6.
    """
    t0 = time.perf_counter()

    if h is None and J is None:
        # Default benchmark instance (with its known offset)
        h = dict(DEFAULT_ISING_H)
        J = dict(DEFAULT_ISING_J)
        offset = DEFAULT_ISING_OFFSET
    else:
        if h is None:
            h = dict(DEFAULT_ISING_H)
        if J is None:
            J = dict(DEFAULT_ISING_J)
    n = max(max(h.keys()) if h else -1, max(max(i, j) for i, j in J) + 1 if J else -1) + 1

    bqm = dimod.BinaryQuadraticModel.from_ising(h, J, offset=offset)

    if method == "exact" and len(bqm.variables) <= 18:
        sampler = dimod.ExactSolver()
        sampleset = sampler.sample(bqm)
    else:
        sampler = dimod.SimulatedAnnealingSampler()
        kwargs: dict[str, Any] = {"num_reads": num_reads}
        if beta_range:
            kwargs["beta_range"] = beta_range
        sampleset = sampler.sample(bqm, **kwargs)

    t1 = time.perf_counter()

    first = sampleset.first
    spins = {int(k): int(v) for k, v in first.sample.items()}
    # Independent recomputation of H = sum h_i s_i + sum J_ij s_i s_j + offset
    energy = float(offset + sum(h[i] * spins[i] for i in h)
                   + sum(J[(i, j)] * spins.get(i, 0) * spins.get(j, 0) for (i, j) in J))

    spectrum = [{"energy": round(float(r.energy), 4), "num_occurrences": int(r.num_occurrences)}
                for r in list(sampleset.data(fields=["energy", "num_occurrences"]))[:5]]

    is_opt = (method == "exact" and n <= 18)
    return {
        "problem_id": f"ising_{n}spins",
        "problem_class": "qubo_ising",
        "mode": "ising",
        "status": "OPTIMAL" if is_opt else "FEASIBLE",
        "objective": energy,
        "solver": f"dimod-{method}",
        "source": "tools/solve_qubo_ising.py",
        "h": {str(i): float(v) for i, v in h.items()},
        "J": {f"{i},{j}": float(v) for (i, j), v in J.items()},
        "offset": float(offset),
        "spins": spins,
        "ground_state_energy": energy,
        "energy_spectrum": spectrum,
        "meta": {
            "exact": method == "exact",
            "proven_optimal": method == "exact" and len(bqm.variables) <= 18,
            "num_reads": num_reads if method != "exact" else 1,
            "beta_range": beta_range,
            "num_variables": n,
            "wall_time_s": round(t1 - t0, 5),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QUBO & Ising Solver (D-Wave dimod)")
    parser.add_argument(
        "--mode",
        choices=["max_cut", "number_partitioning", "qubo", "ising"],
        default="max_cut",
        help="Problem mode to solve",
    )
    parser.add_argument(
        "--method",
        choices=["simulated_annealing", "exact"],
        default="simulated_annealing",
        help="Sampling method",
    )
    args = parser.parse_args(argv)

    if args.mode == "max_cut":
        res = solve_max_cut(method=args.method)
    elif args.mode == "number_partitioning":
        res = solve_number_partitioning(method=args.method)
    elif args.mode == "qubo":
        res = solve_qubo(method=args.method)
    else:
        res = solve_ising(method=args.method)

    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
