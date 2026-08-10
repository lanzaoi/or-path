#!/usr/bin/env python3
"""Solver & Validator Integration Empirical Test for M1 Challenger 2.

Solves burma14, att48, gr17, eil51 using solve_dispatch.py and validates solutions with validate_solution.py.
Compares resulting objectives against published TSPLIB optimal reference values.
"""

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from eval_or_bench.tsplib_converter import KNOWN_OPTIMAL_REFS
from tools.solve_dispatch import solve
from tools.validate_solution import validate

def run_solver_tests():
    test_instances = ["burma14", "att48", "gr17", "eil51"]
    
    print("=== SOLVER DISPATCH & VALIDATOR INTEGRATION TESTS ===")
    
    for inst in test_instances:
        mode = "cpsat" if inst in ("burma14", "gr17") else "ortools"
        print(f"\nRunning solver for {inst} (mode={mode})...")
        
        ok, sol_data, raw_log = solve(_REPO_ROOT, inst, mode=mode)
        assert ok is True, f"Solver dispatch failed for {inst}:\n{raw_log}"
        
        print(f"Solver output for {inst}: status={sol_data.get('status')}, obj={sol_data.get('objective')}")
        
        # Validate solution via validate_solution.py
        val_report = validate(inst, sol_data)
        assert val_report["ok"] is True, f"Validation failed for {inst}: {val_report}"
        
        # Extract recomputation check
        recompute_check = [c for c in val_report["checks"] if c["name"] == "recompute_objective"][0]
        assert recompute_check["ok"] is True, f"Recomputation check failed for {inst}: {recompute_check}"
        
        recomputed_obj = recompute_check["expected"]
        sol_obj = float(sol_data["objective"])
        assert abs(recomputed_obj - sol_obj) < 1e-5, f"Objective mismatch: sol={sol_obj}, recomputed={recomputed_obj}"
        
        ref = KNOWN_OPTIMAL_REFS[inst]
        opt_val = ref["optimal_value"]
        gap_pct = (sol_obj - opt_val) / opt_val * 100.0
        
        print(f"  [VALIDATED OK] {inst}: sol_obj={sol_obj}, recomputed={recomputed_obj}, optimal={opt_val}, gap={gap_pct:.2f}%")
        
        if inst in ("burma14", "gr17"):
            assert abs(sol_obj - opt_val) < 1e-5, f"CP-SAT failed to achieve optimal for {inst}: got {sol_obj}, expected {opt_val}"
            print(f"  -> Exact match to literature optimal ({opt_val}) verified for {inst}!")

    print("\n=== SOLVER & VALIDATOR INTEGRATION TESTS PASSED ===")

if __name__ == "__main__":
    run_solver_tests()
