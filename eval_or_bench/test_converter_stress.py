#!/usr/bin/env python3
"""Empirical Stress Test & Vulnerability Probe Suite for tsplib_converter.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from eval_or_bench.tsplib_converter import (
    parse_tsp_content,
    parse_tsp_file,
    convert_tsp_to_fixture,
    parse_geo_distance,
    parse_att_distance,
    parse_euc_2d_distance,
    main,
)
from tools.schema_models import ProblemSchema, walk_forbidden_keys


# =====================================================================
# 1. EXPLICIT Matrix Formats (Standard vs Edge Cases)
# =====================================================================

def test_explicit_lower_diag_row_standard():
    """Verify standard LOWER_DIAG_ROW conversion (4 nodes = 10 values)."""
    content = """
NAME: lower_diag_test
TYPE: TSP
DIMENSION: 4
EDGE_WEIGHT_TYPE: EXPLICIT
EDGE_WEIGHT_FORMAT: LOWER_DIAG_ROW
EDGE_WEIGHT_SECTION
0
10 0
20 25 0
30 35 40 0
EOF
"""
    parsed = parse_tsp_content(content)
    assert parsed["dimension"] == 4
    matrix = parsed["matrix"]
    assert len(matrix) == 4
    assert matrix[0][0] == 0.0
    assert matrix[1][0] == 10.0
    assert matrix[0][1] == 10.0
    assert matrix[3][2] == 40.0
    assert matrix[2][3] == 40.0


def test_explicit_upper_diag_row_standard():
    """Verify standard UPPER_DIAG_ROW conversion (4 nodes = 10 values)."""
    content = """
NAME: upper_diag_test
TYPE: TSP
DIMENSION: 4
EDGE_WEIGHT_TYPE: EXPLICIT
EDGE_WEIGHT_FORMAT: UPPER_DIAG_ROW
EDGE_WEIGHT_SECTION
0 12 23 34
0 45 56
0 67
0
EOF
"""
    parsed = parse_tsp_content(content)
    assert parsed["dimension"] == 4
    matrix = parsed["matrix"]
    assert matrix[0][1] == 12.0
    assert matrix[1][0] == 12.0
    assert matrix[0][3] == 34.0
    assert matrix[3][0] == 34.0
    assert matrix[1][2] == 45.0
    assert matrix[2][1] == 45.0


def test_explicit_full_matrix_standard():
    """Verify standard FULL_MATRIX conversion (3 nodes = 9 values)."""
    content = """
NAME: full_matrix_test
TYPE: TSP
DIMENSION: 3
EDGE_WEIGHT_TYPE: EXPLICIT
EDGE_WEIGHT_FORMAT: FULL_MATRIX
EDGE_WEIGHT_SECTION
0 10 15
10 0 20
15 20 0
EOF
"""
    parsed = parse_tsp_content(content)
    assert parsed["dimension"] == 3
    matrix = parsed["matrix"]
    assert matrix[0][1] == 10.0
    assert matrix[0][2] == 15.0
    assert matrix[1][2] == 20.0


def test_explicit_default_full_matrix():
    """Verify EDGE_WEIGHT_FORMAT defaulting to FULL_MATRIX when blank."""
    content = """
NAME: default_full_matrix
DIMENSION: 2
EDGE_WEIGHT_TYPE: EXPLICIT
EDGE_WEIGHT_SECTION
0 5
5 0
EOF
"""
    parsed = parse_tsp_content(content)
    assert parsed["matrix"] == [[0.0, 5.0], [5.0, 0.0]]


def test_explicit_unsupported_edge_format():
    """Verify unsupported EDGE_WEIGHT_FORMAT (e.g. INVALID_FORMAT) raises ValueError."""
    content = """
NAME: unsupported_format
DIMENSION: 3
EDGE_WEIGHT_TYPE: EXPLICIT
EDGE_WEIGHT_FORMAT: INVALID_FORMAT
EDGE_WEIGHT_SECTION
10 20 30
EOF
"""
    with pytest.raises(ValueError, match="Unsupported EDGE_WEIGHT_FORMAT"):
        parse_tsp_content(content)


def test_explicit_truncated_values():
    """Stress test: EDGE_WEIGHT_SECTION with missing values raises IndexError."""
    content = """
NAME: truncated_explicit
DIMENSION: 4
EDGE_WEIGHT_TYPE: EXPLICIT
EDGE_WEIGHT_FORMAT: LOWER_DIAG_ROW
EDGE_WEIGHT_SECTION
0 10 0
EOF
"""
    with pytest.raises(IndexError):
        parse_tsp_content(content)


# =====================================================================
# 2. Distance Metric Types & Mathematical Edge Cases
# =====================================================================

def test_distance_metrics_negative_and_floats():
    """Test EUC_2D with float coordinates and negative values."""
    c1 = (-10.5, 20.0)
    c2 = (30.0, -10.0)
    d = parse_euc_2d_distance(c1, c2)
    assert isinstance(d, int)
    assert d == 50


def test_geo_distance_clamping_and_negatives():
    """Test GEO distance precision, negative lat/lon, and boundary clamping."""
    c1 = (16.47, 96.10)
    c2 = (16.47, 96.10)
    d0 = parse_geo_distance(c1, c2)
    assert d0 == 1  # TSPLIB GEO distance formula adds +1.0

    c3 = (-12.30, -45.15)
    c4 = (24.15, 55.45)
    d_neg = parse_geo_distance(c3, c4)
    assert isinstance(d_neg, int)
    assert d_neg > 0


def test_att_distance_precision():
    """Test ATT distance calculation logic."""
    c1 = (10.0, 20.0)
    c2 = (40.0, 60.0)
    d = parse_att_distance(c1, c2)
    assert isinstance(d, int)
    assert d == 16


def test_vulnerability_unsupported_edge_weight_type_silent_zeros():
    """Vulnerability probe: Unsupported EDGE_WEIGHT_TYPE (e.g. CEIL_2D) silently returns 0.0 matrix."""
    content = """
NAME: unsupported_type
DIMENSION: 2
EDGE_WEIGHT_TYPE: CEIL_2D
NODE_COORD_SECTION
1 0.0 0.0
2 3.0 4.0
EOF
"""
    parsed = parse_tsp_content(content)
    # Observe that matrix is silently all zeros!
    assert parsed["matrix"] == [[0.0, 0.0], [0.0, 0.0]]


# =====================================================================
# 3. Parser Vulnerability Probes (Colons, Case-Sensitivity, Missing Sections)
# =====================================================================

def test_vulnerability_section_header_with_colon():
    """Vulnerability probe: Section header ending with colon (e.g. NODE_COORD_SECTION:) is skipped."""
    content = """
NAME: section_colon_bug
DIMENSION: 2
EDGE_WEIGHT_TYPE: EUC_2D
NODE_COORD_SECTION:
1 0.0 0.0
2 3.0 4.0
EOF
"""
    parsed = parse_tsp_content(content)
    # The trailing colon causes NODE_COORD_SECTION: to be swallowed into meta, skipping section content
    assert parsed["matrix"] == [[0.0, 0.0], [0.0, 0.0]]


def test_vulnerability_section_header_lowercase():
    """Vulnerability probe: Lowercase section header (e.g. node_coord_section) is ignored."""
    content = """
NAME: lowercase_section_bug
DIMENSION: 2
EDGE_WEIGHT_TYPE: EUC_2D
node_coord_section
1 0.0 0.0
2 3.0 4.0
EOF
"""
    parsed = parse_tsp_content(content)
    # Lowercase section header is not matched, so matrix remains all zeros
    assert parsed["matrix"] == [[0.0, 0.0], [0.0, 0.0]]


def test_vulnerability_header_without_colon_no_coords():
    """Vulnerability probe: Space-separated header without colon for EXPLICIT matrix raises ValueError."""
    content = """
NAME no_colon_explicit
DIMENSION 3
EDGE_WEIGHT_TYPE EXPLICIT
EDGE_WEIGHT_FORMAT FULL_MATRIX
EDGE_WEIGHT_SECTION
0 1 2
1 0 3
2 3 0
EOF
"""
    with pytest.raises(ValueError, match="Could not determine DIMENSION"):
        parse_tsp_content(content)


def test_header_spaces_around_colon():
    """Verify headers with arbitrary whitespace around colons."""
    content = """
NAME   :   spaces_test
DIMENSION  :  3
EDGE_WEIGHT_TYPE :  EUC_2D
NODE_COORD_SECTION
1  0.0  0.0
2  3.0  0.0
3  3.0  4.0
EOF
"""
    parsed = parse_tsp_content(content)
    assert parsed["name"] == "spaces_test"
    assert parsed["dimension"] == 3
    assert parsed["matrix"][0][1] == 3.0
    assert parsed["matrix"][0][2] == 5.0


def test_missing_dimension_inferred_from_coords():
    """Verify missing DIMENSION header is inferred when NODE_COORD_SECTION exists."""
    content = """
NAME: missing_dim
EDGE_WEIGHT_TYPE: EUC_2D
NODE_COORD_SECTION
1 0 0
2 10 0
3 0 10
EOF
"""
    parsed = parse_tsp_content(content)
    assert parsed["dimension"] == 3


def test_invalid_dimension_non_integer():
    """Verify non-integer DIMENSION header raises ValueError."""
    content = """
NAME: invalid_dim
DIMENSION: abc
EOF
"""
    with pytest.raises(ValueError):
        parse_tsp_content(content)


def test_vulnerability_missing_edge_weight_section_explicit():
    """Vulnerability probe: EXPLICIT type with missing EDGE_WEIGHT_SECTION silently emits all zeros."""
    content = """
NAME: missing_explicit_section
DIMENSION: 3
EDGE_WEIGHT_TYPE: EXPLICIT
EDGE_WEIGHT_FORMAT: FULL_MATRIX
EOF
"""
    parsed = parse_tsp_content(content)
    assert parsed["matrix"] == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]


# =====================================================================
# 4. Coordinate Parsing & Index Out Of Bounds Crashes
# =====================================================================

def test_coordinates_scientific_notation_and_tabs():
    """Verify coordinates with scientific notation and tabs/mixed whitespace."""
    content = """
NAME: sci_notation_test
DIMENSION: 2
EDGE_WEIGHT_TYPE: EUC_2D
NODE_COORD_SECTION
1\t1.5e2\t0.0e0
2\t4.5e2\t4.0e2
EOF
"""
    parsed = parse_tsp_content(content)
    assert parsed["dimension"] == 2
    assert parsed["coords"][0]["x"] == 150.0
    assert parsed["coords"][1]["x"] == 450.0
    assert parsed["coords"][1]["y"] == 400.0
    assert parsed["matrix"][0][1] == 500.0


def test_vulnerability_coordinate_count_mismatch_crash():
    """Vulnerability probe: DIMENSION header exceeds coordinate count causes unhandled IndexError crash."""
    content = """
NAME: mismatch_crash_test
DIMENSION: 4
EDGE_WEIGHT_TYPE: EUC_2D
NODE_COORD_SECTION
1 0 0
2 3 4
EOF
"""
    with pytest.raises(IndexError):
        parse_tsp_content(content)


def test_coordinate_malformed_token():
    """Verify non-numeric value in coordinate section raises ValueError."""
    content = """
NAME: malformed_coord
DIMENSION: 2
EDGE_WEIGHT_TYPE: EUC_2D
NODE_COORD_SECTION
1 0.0 zero
2 3.0 4.0
EOF
"""
    with pytest.raises(ValueError):
        parse_tsp_content(content)


# =====================================================================
# 5. File I/O, Fixture Conversion, & CLI Stress Tests
# =====================================================================

def test_convert_tsp_to_fixture_end_to_end(tmp_path: Path):
    """End-to-end fixture conversion with schema and forbidden key validation."""
    tsp_content = """
NAME: fixture_test_inst
TYPE: TSP
DIMENSION: 3
EDGE_WEIGHT_TYPE: EUC_2D
NODE_COORD_SECTION
1 0 0
2 3 0
3 0 4
EOF
"""
    tsp_file = tmp_path / "fixture_test.tsp"
    tsp_file.write_text(tsp_content, encoding="utf-8")

    out_dir = tmp_path / "output_fixtures"
    converted_dir = convert_tsp_to_fixture(tsp_file, out_dir, validate_schema=True)

    assert converted_dir.is_dir()
    dist_file = converted_dir / "distance_matrix.json"
    coords_file = converted_dir / "coords.json"
    assert dist_file.is_file()
    assert coords_file.is_file()

    dist_data = json.loads(dist_file.read_text(encoding="utf-8"))
    coords_data = json.loads(coords_file.read_text(encoding="utf-8"))

    assert not walk_forbidden_keys(dist_data)
    assert not walk_forbidden_keys(coords_data)

    schema_obj = ProblemSchema(
        problem_id="fixture_test_inst",
        problem_class="tsp",
        distance_matrix=dist_data["matrix"],
        coords=coords_data["coords"],
    )
    assert schema_obj.problem_id == "fixture_test_inst"


def test_cli_non_existent_input():
    """Verify CLI main() returns exit code 1 on non-existent input path."""
    ret = main(["--input", "non_existent_file_path_xyz.tsp"])
    assert ret == 1


def test_cli_no_args():
    """Verify CLI main() returns exit code 1 when no arguments provided."""
    ret = main([])
    assert ret == 1


def test_cli_valid_file_conversion(tmp_path: Path):
    """Verify CLI main() converts a valid file successfully."""
    tsp_content = """
NAME: cli_test_inst
DIMENSION: 2
EDGE_WEIGHT_TYPE: EUC_2D
NODE_COORD_SECTION
1 0 0
2 1 1
EOF
"""
    tsp_file = tmp_path / "cli_test.tsp"
    tsp_file.write_text(tsp_content, encoding="utf-8")
    out_dir = tmp_path / "cli_out"

    ret = main(["--input", str(tsp_file), "--out-dir", str(out_dir)])
    assert ret == 0
    assert (out_dir / "cli_test_inst" / "distance_matrix.json").is_file()
