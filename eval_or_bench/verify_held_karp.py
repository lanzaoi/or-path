#!/usr/bin/env python3
"""Held-Karp Exact TSP Solver for burma14 to verify true matrix optimal value."""

import sys
import math
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from eval_or_bench.tsplib_converter import parse_tsp_file

def held_karp(dists):
    n = len(dists)
    memo = {}
    
    def solve_dp(mask, u):
        if mask == (1 << n) - 1:
            return dists[u][0], [u, 0]
        state = (mask, u)
        if state in memo:
            return memo[state]
        
        min_cost = float('inf')
        best_path = []
        for v in range(n):
            if not (mask & (1 << v)):
                cost, path = solve_dp(mask | (1 << v), v)
                total = dists[u][v] + cost
                if total < min_cost:
                    min_cost = total
                    best_path = [u] + path
        memo[state] = (min_cost, best_path)
        return min_cost, best_path

    cost, path = solve_dp(1, 0)
    return cost, path

def main():
    burma_data = parse_tsp_file(_REPO_ROOT / "eval_or_bench" / "raw_tsp" / "burma14.tsp")
    mat = burma_data["matrix"]
    cost, path = held_karp(mat)
    print(f"Held-Karp Exact Minimum Cost for burma14 matrix: {cost}")
    print(f"Optimal Path: {path}")

if __name__ == "__main__":
    main()
