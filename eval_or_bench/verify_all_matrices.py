#!/usr/bin/env python3
"""Verify exact optimal matrix tour costs for all 8 TSPLIB instances using Held-Karp DP / CP-SAT."""

import sys
import math
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from eval_or_bench.tsplib_converter import parse_tsp_file, KNOWN_OPTIMAL_REFS
from tools.solve_dispatch import solve

def held_karp(dists):
    n = len(dists)
    memo = {}
    
    def solve_dp(mask, u):
        if mask == (1 << n) - 1:
            return dists[u][0]
        state = (mask, u)
        if state in memo:
            return memo[state]
        
        min_cost = float('inf')
        for v in range(n):
            if not (mask & (1 << v)):
                cost = solve_dp(mask | (1 << v), v)
                total = dists[u][v] + cost
                if total < min_cost:
                    min_cost = total
        memo[state] = min_cost
        return min_cost

    return solve_dp(1, 0)

def main():
    test_instances = ["burma14", "ulysses16", "gr17", "bayg29", "swiss42", "att48", "eil51", "kroA100"]
    
    print("=== CHECKING EXACT MATRIX OPTIMAL VALUES FOR ALL 8 INSTANCES ===")
    
    for inst in test_instances:
        tsp_file = _REPO_ROOT / "eval_or_bench" / "raw_tsp" / f"{inst}.tsp"
        data = parse_tsp_file(tsp_file)
        mat = data["matrix"]
        n = data["dimension"]
        ref = KNOWN_OPTIMAL_REFS[inst]
        pub_opt = ref["optimal_value"]
        
        if n <= 17:
            matrix_opt = held_karp(mat)
            print(f"{inst} (N={n}, {data['edge_weight_type']}): Held-Karp exact = {matrix_opt}, Literature opt = {pub_opt}")
            assert matrix_opt == pub_opt, f"Mismatch on {inst}: got {matrix_opt}, expected {pub_opt}"
        else:
            # Solve with CP-SAT
            ok, sol, _ = solve(_REPO_ROOT, inst, mode="cpsat")
            matrix_opt = sol.get("objective")
            print(f"{inst} (N={n}, {data['edge_weight_type']}): Solver obj = {matrix_opt}, Literature opt = {pub_opt}")
            assert matrix_opt == pub_opt, f"Mismatch on {inst}: got {matrix_opt}, expected {pub_opt}"

    print("ALL 8 INSTANCES MATCH LITERATURE OPTIMA EXACTLY!")

if __name__ == "__main__":
    main()
