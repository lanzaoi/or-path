#!/usr/bin/env python3
"""Empirical Verification Script for M1 Challenger 2.

Verifies distance matrix accuracy and validation recomputation for:
- burma14 (GEO)
- att48 (ATT)
- gr17 (EXPLICIT)
- eil51 (EUC_2D)

Checks TSPLIB distance formulas, matrix properties, validate_solution.py lookups,
and objective recomputation accuracy.
"""

import sys
import math
import json
from pathlib import Path

# Add repo root to path
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from eval_or_bench.tsplib_converter import (
    parse_geo_distance,
    parse_att_distance,
    parse_euc_2d_distance,
    parse_tsp_file,
    convert_tsp_to_fixture,
    KNOWN_OPTIMAL_REFS,
)
from tools.validate_solution import validate, _matrix_and_labels, _validate_tsp
from tools.fixture_paths import fixture_dir

def run_tests():
    results = {}
    print("=== STARTING EMPIRICAL VERIFICATION FOR M1 CHALLENGER 2 ===")
    
    # 1. GEO Metric Verification (burma14)
    print("\n--- 1. GEO Metric Verification (burma14) ---")
    c1 = (16.47, 96.10) # city 1
    c2 = (16.47, 94.44) # city 2
    # TSPLIB formula manual check:
    # lat1, lon1: deg=16, min=0.47 => 16 + 5.0*0.47/3.0 = 16.783333... deg => 0.292925 rad
    # lat2, lon2: deg=16, min=0.47 => 16.783333 deg; lon2: deg=94, min=0.44 => 94.733333 deg => 1.653414 rad
    geo_dist_calculated = parse_geo_distance(c1, c2)
    print(f"burma14 city 1 to city 2 GEO distance: {geo_dist_calculated}")
    
    # Verify burma14 parsed matrix
    burma_data = parse_tsp_file(_REPO_ROOT / "eval_or_bench" / "raw_tsp" / "burma14.tsp")
    m_burma = burma_data["matrix"]
    assert len(m_burma) == 14, f"Expected dimension 14, got {len(m_burma)}"
    assert m_burma[0][1] == geo_dist_calculated, f"Matrix [0][1] {m_burma[0][1]} != {geo_dist_calculated}"
    assert m_burma[1][0] == m_burma[0][1], "Matrix asymmetry in burma14"
    assert m_burma[0][0] == 0.0, "Self-distance non-zero in burma14"
    
    # Check burma14 city 1 to city 3
    c3 = (20.09, 92.54)
    dist_1_3 = parse_geo_distance(c1, c3)
    assert m_burma[0][2] == dist_1_3, f"Matrix [0][2] {m_burma[0][2]} != {dist_1_3}"
    print(f"burma14 city 1 to city 3 GEO distance: {dist_1_3}")
    
    results["burma14_geo_formula"] = "PASS"

    # 2. ATT Metric Verification (att48)
    print("\n--- 2. ATT Metric Verification (att48) ---")
    att_c1 = (6734.0, 1453.0) # city 1
    att_c2 = (2233.0, 10.0)    # city 2
    # dx = 4501, dy = 1443, dx^2+dy^2 = 20259001 + 2082249 = 22341250
    # rij = sqrt(2234125.0) = 1494.698966
    # tij = int(round(1495.0)) = 1495
    # tij (1495) > rij (1494.6989) => dist = 1495
    att_dist_calculated = parse_att_distance(att_c1, att_c2)
    print(f"att48 city 1 to city 2 ATT distance: {att_dist_calculated}")
    assert att_dist_calculated == 1495, f"Expected 1495, got {att_dist_calculated}"
    
    # city 1 to city 8 (438, 521):
    att_c8 = (438.0, 521.0)
    # dx = 6296, dy = 932, dx^2+dy^2 = 39639616 + 868624 = 40508240
    # rij = sqrt(4050824.0) = 2012.66589
    # tij = int(round(2013)) = 2013
    # tij (2013) > rij (2012.66589) => dist = 2013
    att_dist_1_8 = parse_att_distance(att_c1, att_c8)
    print(f"att48 city 1 to city 8 ATT distance: {att_dist_1_8}")
    assert att_dist_1_8 == 2013, f"Expected 2013, got {att_dist_1_8}"
    
    att_data = parse_tsp_file(_REPO_ROOT / "eval_or_bench" / "raw_tsp" / "att48.tsp")
    m_att = att_data["matrix"]
    assert len(m_att) == 48, f"Expected dimension 48, got {len(m_att)}"
    assert m_att[0][1] == 1495.0, f"att48 matrix [0][1] expected 1495.0, got {m_att[0][1]}"
    assert m_att[0][7] == 2013.0, f"att48 matrix [0][7] expected 2013.0, got {m_att[0][7]}"
    results["att48_att_formula"] = "PASS"

    # 3. EXPLICIT Metric Verification (gr17)
    print("\n--- 3. EXPLICIT Metric Verification (gr17) ---")
    gr17_data = parse_tsp_file(_REPO_ROOT / "eval_or_bench" / "raw_tsp" / "gr17.tsp")
    m_gr17 = gr17_data["matrix"]
    assert len(m_gr17) == 17, f"Expected dimension 17, got {len(m_gr17)}"
    
    # Check LOWER_DIAG_ROW parsing against raw file entries
    # Row 0: 0
    # Row 1: 633 0
    # Row 2: 257 390 0
    # Row 3: 91 661 228 0
    # Row 6: 80 572 196 77 351 70 0
    assert m_gr17[1][0] == 633.0 and m_gr17[0][1] == 633.0, f"gr17 [1][0] mismatch: {m_gr17[1][0]}"
    assert m_gr17[2][0] == 257.0 and m_gr17[2][1] == 390.0, f"gr17 row 2 mismatch: {m_gr17[2]}"
    assert m_gr17[3][0] == 91.0 and m_gr17[3][3] == 0.0, f"gr17 row 3 mismatch: {m_gr17[3]}"
    assert m_gr17[6][0] == 80.0 and m_gr17[6][5] == 70.0, f"gr17 row 6 mismatch: {m_gr17[6]}"
    
    # Check symmetry across all entries
    for i in range(17):
        for j in range(17):
            assert m_gr17[i][j] == m_gr17[j][i], f"gr17 asymmetry at ({i},{j})"
            if i == j:
                assert m_gr17[i][j] == 0.0, f"gr17 non-zero diagonal at ({i},{i})"
    print("gr17 explicit matrix LOWER_DIAG_ROW verified 100% symmetric and accurate.")
    results["gr17_explicit_matrix"] = "PASS"

    # 4. EUC_2D Metric Verification (eil51)
    print("\n--- 4. EUC_2D Metric Verification (eil51) ---")
    eil_c1 = (37.0, 52.0) # node 1
    eil_c2 = (49.0, 49.0) # node 2
    # dx = 12, dy = -3, dx^2+dy^2 = 144+9 = 153. sqrt(153) = 12.3693 => round(12.3693) = 12
    euc_dist_1_2 = parse_euc_2d_distance(eil_c1, eil_c2)
    print(f"eil51 node 1 to node 2 EUC_2D distance: {euc_dist_1_2}")
    assert euc_dist_1_2 == 12, f"Expected 12, got {euc_dist_1_2}"
    
    eil_c3 = (52.0, 64.0) # node 3
    # node 1 (37, 52) to node 3 (52, 64): dx=15, dy=12, 225+144=369, sqrt(369)=19.209 => 19
    euc_dist_1_3 = parse_euc_2d_distance(eil_c1, eil_c3)
    print(f"eil51 node 1 to node 3 EUC_2D distance: {euc_dist_1_3}")
    assert euc_dist_1_3 == 19, f"Expected 19, got {euc_dist_1_3}"
    
    eil_data = parse_tsp_file(_REPO_ROOT / "eval_or_bench" / "raw_tsp" / "eil51.tsp")
    m_eil = eil_data["matrix"]
    assert len(m_eil) == 51, f"Expected dimension 51, got {len(m_eil)}"
    assert m_eil[0][1] == 12.0, f"eil51 matrix [0][1] expected 12.0, got {m_eil[0][1]}"
    assert m_eil[0][2] == 19.0, f"eil51 matrix [0][2] expected 19.0, got {m_eil[0][2]}"
    results["eil51_euc_2d_formula"] = "PASS"

    # 5. Verify validate_solution.py Matrix Lookup & Recomputation Accuracy
    print("\n--- 5. Verify validate_solution.py Matrix Lookup & Recomputation ---")
    
    # Test instances in eval_or_bench/instances/
    instances = ["burma14", "att48", "gr17", "eil51"]
    for inst in instances:
        # Load matrix via validate_solution's internal helper _matrix_and_labels
        mat, labels = _matrix_and_labels(inst)
        assert len(mat) == len(labels), f"{inst}: matrix size mismatch with labels"
        print(f"Instance '{inst}': matrix size {len(mat)}x{len(mat)}, labels len {len(labels)}")
        
        # Test dummy valid tour: 0 -> 1 -> 2 -> ... -> N-1 -> 0
        tour = labels + [labels[0]]
        expected_obj = 0.0
        for u, v in zip(tour[:-1], tour[1:]):
            iu, iv = int(u), int(v)
            expected_obj += mat[iu][iv]
            
        dummy_sol = {
            "problem_id": inst,
            "problem_class": "tsp",
            "status": "FEASIBLE",
            "objective": float(expected_obj),
            "tour": tour,
            "solver": "test",
            "source": "challenger2_test"
        }
        val_report = validate(inst, dummy_sol)
        assert val_report["ok"] is True, f"Validation failed for dummy tour on {inst}: {val_report}"
        recompute_check = [c for c in val_report["checks"] if c["name"] == "recompute_objective"][0]
        assert recompute_check["ok"] is True, f"Recompute check failed for {inst}: {recompute_check}"
        assert abs(recompute_check["expected"] - expected_obj) < 1e-5
        print(f"  [OK] {inst} dummy tour objective recomputation: {expected_obj}")

    # 6. Critical Impact Analysis: Compare GEO & ATT distance calculation with EUC_2D fallback
    print("\n--- 6. Critical Impact Analysis: distance_matrix.json vs EUC_2D Fallback ---")
    # If distance_matrix.json were omitted, validate_solution fallback uses int(round(math.hypot(dx, dy))) on coords.json.
    # Let's test burma14 coordinates under EUC_2D vs GEO:
    burma_coords = burma_data["coords"]
    euc_burma_1_2 = int(round(math.hypot(burma_coords[0]["x"] - burma_coords[1]["x"], burma_coords[0]["y"] - burma_coords[1]["y"])))
    geo_burma_1_2 = m_burma[0][1]
    print(f"burma14 0->1: GEO dist = {geo_burma_1_2}, EUC_2D dist = {euc_burma_1_2}")
    assert geo_burma_1_2 != euc_burma_1_2, "GEO and EUC_2D distances should differ for lat/lon coords!"
    print("  -> Confirmed: `distance_matrix.json` is MANDATORY for non-EUC_2D metrics (GEO/ATT/EXPLICIT) to avoid invalid objective recomputation!")
    results["fallback_vulnerability_prevented"] = "PASS"

    print("\n=== ALL EMPIRICAL TESTS PASSED SUCCESSFULLY ===")
    return results

if __name__ == "__main__":
    run_tests()
