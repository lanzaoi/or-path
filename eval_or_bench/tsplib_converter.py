#!/usr/bin/env python3
"""TSPLIB to OR-Path ProblemSchema Converter.

Parses TSPLIB format files (.tsp) supporting EUC_2D, GEO, ATT, and EXPLICIT distance
metrics (FULL_MATRIX, LOWER_DIAG_ROW, UPPER_DIAG_ROW) and converts them into OR-Path
compliant problem definitions: `coords.json` and `distance_matrix.json`.

Enforces strict compliance with `ProblemSchema` and guarantees zero forbidden answer keys
(`FORBIDDEN_SCHEMA_KEYS`).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is on sys.path for importing schema_models
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from tools.schema_models import ProblemSchema, walk_forbidden_keys
except ImportError:  # pragma: no cover
    ProblemSchema = None  # type: ignore
    walk_forbidden_keys = None  # type: ignore


# Known canonical optimal values and literature citations for selected suite
KNOWN_OPTIMAL_REFS: Dict[str, Dict[str, Any]] = {
    "burma14": {
        "dimension": 14,
        "edge_weight_type": "GEO",
        "reference_type": "optimal",
        "optimal_value": 3323,
        "citation": "Reinelt, G. (1991). TSPLIB—A Traveling Salesman Problem Library. ORSA Journal on Computing, 3(4), 376-384.",
    },
    "ulysses16": {
        "dimension": 16,
        "edge_weight_type": "GEO",
        "reference_type": "optimal",
        "optimal_value": 6859,
        "citation": "Grötschel, M., & Padberg, M. (1985). Polyhedral Theory. The Traveling Salesman Problem, 251-305.",
    },
    "gr17": {
        "dimension": 17,
        "edge_weight_type": "EXPLICIT",
        "reference_type": "optimal",
        "optimal_value": 2085,
        "citation": "Grötschel, M. (1980). On the symmetric traveling salesman problem: Solution of a 120-city problem. Mathematical Programming Study, 12, 61-77.",
    },
    "bayg29": {
        "dimension": 29,
        "edge_weight_type": "EXPLICIT",
        "reference_type": "optimal",
        "optimal_value": 1610,
        "citation": "Reinelt, G. (1991). TSPLIB Repository, Heidelberg University.",
    },
    "swiss42": {
        "dimension": 42,
        "edge_weight_type": "EXPLICIT",
        "reference_type": "optimal",
        "optimal_value": 1273,
        "citation": "TSPLIB Benchmark Database, Heidelberg University (1991).",
    },
    "att48": {
        "dimension": 48,
        "edge_weight_type": "ATT",
        "reference_type": "optimal",
        "optimal_value": 10628,
        "citation": "Padberg, M., & Rinaldi, G. (1987). Optimization of a 532-city symmetric traveling salesman problem by branch-and-cut. Operations Research Letters, 6(1), 1-7.",
    },
    "eil51": {
        "dimension": 51,
        "edge_weight_type": "EUC_2D",
        "reference_type": "optimal",
        "optimal_value": 426,
        "citation": "Eilon, S., Watson-Gandy, C. D. T., & Christofides, N. (1971). Distribution Management: Mathematical Modelling and Practical Analysis.",
    },
    "kroA100": {
        "dimension": 100,
        "edge_weight_type": "EUC_2D",
        "reference_type": "optimal",
        "optimal_value": 21282,
        "citation": "Krolak, P., Felts, W., & Marble, G. (1971). A man-machine approach to the traveling salesman problem. CACM, 14(5), 327-334.",
    },
}


def parse_geo_distance(c1: Tuple[float, float], c2: Tuple[float, float]) -> int:
    """Compute exact TSPLIB GEO distance between two (lat, lon) coordinates."""
    PI = 3.141592
    RRR = 6378.388

    def to_rad(deg_min: float) -> float:
        deg = int(deg_min)
        minutes = deg_min - float(deg)
        return PI * (float(deg) + 5.0 * minutes / 3.0) / 180.0

    lat1, lon1 = to_rad(c1[0]), to_rad(c1[1])
    lat2, lon2 = to_rad(c2[0]), to_rad(c2[1])

    q1 = math.cos(lon1 - lon2)
    q2 = math.cos(lat1 - lat2)
    q3 = math.cos(lat1 + lat2)
    arg = 0.5 * ((1.0 + q1) * q2 - (1.0 - q1) * q3)
    # Clamp arg to [-1.0, 1.0] for floating point safety
    arg = max(-1.0, min(1.0, arg))
    d = RRR * math.acos(arg) + 1.0
    return int(d)


def parse_att_distance(c1: Tuple[float, float], c2: Tuple[float, float]) -> int:
    """Compute exact TSPLIB ATT pseudo-Euclidean distance between 2D coordinates."""
    dx = c1[0] - c2[0]
    dy = c1[1] - c2[1]
    rij = math.sqrt((dx * dx + dy * dy) / 10.0)
    tij = int(math.floor(rij + 0.5))
    return tij + 1 if tij < rij else tij


def parse_euc_2d_distance(c1: Tuple[float, float], c2: Tuple[float, float]) -> int:
    """Compute exact TSPLIB EUC_2D Euclidean distance between 2D coordinates."""
    dx = c1[0] - c2[0]
    dy = c1[1] - c2[1]
    return int(math.floor(math.hypot(dx, dy) + 0.5))


def parse_tsp_content(content: str, fallback_name: str = "instance") -> Dict[str, Any]:
    """Parse raw TSPLIB file text into metadata, coordinates, and distance matrix."""
    lines = [line.strip() for line in content.splitlines() if line.strip()]

    meta: Dict[str, str] = {}
    sections: Dict[str, List[str]] = {}
    current_section: Optional[str] = None

    for line in lines:
        if line == "EOF":
            break
        if ":" in line and current_section is None:
            key, val = line.split(":", 1)
            meta[key.strip().upper()] = val.strip()
        elif line in (
            "NODE_COORD_SECTION",
            "EDGE_WEIGHT_SECTION",
            "DISPLAY_DATA_SECTION",
            "FIXED_EDGES_SECTION",
        ):
            current_section = line
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)

    name = meta.get("NAME", fallback_name)
    dimension = int(meta.get("DIMENSION", "0"))
    edge_type = meta.get("EDGE_WEIGHT_TYPE", "EUC_2D").upper()
    edge_format = meta.get("EDGE_WEIGHT_FORMAT", "").upper()

    # Parse node coordinates
    coords_raw: List[Dict[str, float]] = []
    if "NODE_COORD_SECTION" in sections:
        for line in sections["NODE_COORD_SECTION"]:
            parts = line.split()
            if len(parts) >= 3:
                node_id, x, y = parts[0], float(parts[1]), float(parts[2])
                coords_raw.append({"orig_id": node_id, "x": x, "y": y})

    if dimension == 0:
        dimension = len(coords_raw)

    if dimension == 0:
        raise ValueError(f"Could not determine DIMENSION for TSPLIB instance {name}")

    # Build matrix
    matrix: List[List[float]] = [[0.0] * dimension for _ in range(dimension)]

    if edge_type == "EUC_2D" and coords_raw:
        for i in range(dimension):
            for j in range(dimension):
                if i != j:
                    c1 = (coords_raw[i]["x"], coords_raw[i]["y"])
                    c2 = (coords_raw[j]["x"], coords_raw[j]["y"])
                    matrix[i][j] = float(parse_euc_2d_distance(c1, c2))
    elif edge_type == "GEO" and coords_raw:
        for i in range(dimension):
            for j in range(dimension):
                if i != j:
                    c1 = (coords_raw[i]["x"], coords_raw[i]["y"])
                    c2 = (coords_raw[j]["x"], coords_raw[j]["y"])
                    matrix[i][j] = float(parse_geo_distance(c1, c2))
    elif edge_type == "ATT" and coords_raw:
        for i in range(dimension):
            for j in range(dimension):
                if i != j:
                    c1 = (coords_raw[i]["x"], coords_raw[i]["y"])
                    c2 = (coords_raw[j]["x"], coords_raw[j]["y"])
                    matrix[i][j] = float(parse_att_distance(c1, c2))
    elif edge_type == "EXPLICIT" and "EDGE_WEIGHT_SECTION" in sections:
        raw_vals: List[float] = []
        for line in sections["EDGE_WEIGHT_SECTION"]:
            raw_vals.extend([float(x) for x in line.split()])

        if edge_format == "LOWER_DIAG_ROW":
            idx = 0
            for i in range(dimension):
                for j in range(i + 1):
                    val = float(raw_vals[idx])
                    matrix[i][j] = val
                    matrix[j][i] = val
                    idx += 1
        elif edge_format == "LOWER_ROW":
            idx = 0
            for i in range(dimension):
                matrix[i][i] = 0.0
                for j in range(i):
                    val = float(raw_vals[idx])
                    matrix[i][j] = val
                    matrix[j][i] = val
                    idx += 1
        elif edge_format == "UPPER_DIAG_ROW":
            idx = 0
            for i in range(dimension):
                for j in range(i, dimension):
                    val = float(raw_vals[idx])
                    matrix[i][j] = val
                    matrix[j][i] = val
                    idx += 1
        elif edge_format in ("UPPER_ROW", "UPPER_DIAG_COL"):
            idx = 0
            for i in range(dimension):
                matrix[i][i] = 0.0
                for j in range(i + 1, dimension):
                    val = float(raw_vals[idx])
                    matrix[i][j] = val
                    matrix[j][i] = val
                    idx += 1
        elif edge_format in ("FULL_MATRIX", ""):
            idx = 0
            for i in range(dimension):
                for j in range(dimension):
                    matrix[i][j] = float(raw_vals[idx])
                    idx += 1
        else:
            raise ValueError(f"Unsupported EDGE_WEIGHT_FORMAT: {edge_format}")

    # Map labels to 0-indexed strings ("0", "1", ..., "N-1")
    labels = [str(i) for i in range(dimension)]
    normalized_coords: Optional[List[Dict[str, Any]]] = None
    if coords_raw:
        normalized_coords = [
            {"id": str(i), "x": c["x"], "y": c["y"]} for i, c in enumerate(coords_raw)
        ]

    return {
        "name": name,
        "dimension": dimension,
        "edge_weight_type": edge_type,
        "edge_weight_format": edge_format,
        "labels": labels,
        "coords": normalized_coords,
        "matrix": matrix,
    }


def parse_tsp_file(filepath: Path) -> Dict[str, Any]:
    """Parse a .tsp file into structured data dictionary."""
    content = filepath.read_text(encoding="utf-8", errors="replace")
    return parse_tsp_content(content, fallback_name=filepath.stem)


def convert_tsp_to_fixture(
    tsp_path: Path,
    output_dir: Path,
    *,
    validate_schema: bool = True,
) -> Path:
    """Convert a TSPLIB .tsp file into an OR-Path fixture directory.

    Emits:
    - distance_matrix.json (always generated)
    - coords.json (if coordinates exist)
    - whitelist_refs.json (if optimal metadata is known)
    """
    data = parse_tsp_file(tsp_path)
    inst_name = data["name"]
    inst_dir = output_dir / inst_name
    inst_dir.mkdir(parents=True, exist_ok=True)

    # 1. Build distance_matrix.json payload
    dist_payload = {
        "labels": data["labels"],
        "matrix": data["matrix"],
    }

    # Verify forbidden keys in distance_matrix payload
    if walk_forbidden_keys is not None:
        forbidden = walk_forbidden_keys(dist_payload)
        if forbidden:
            raise ValueError(f"Forbidden keys found in distance_matrix payload: {forbidden}")

    dist_file = inst_dir / "distance_matrix.json"
    dist_file.write_text(json.dumps(dist_payload, indent=2), encoding="utf-8")

    # 2. Build coords.json payload if coordinates present
    coords_payload = None
    if data["coords"]:
        coords_payload = {
            "labels": data["labels"],
            "coords": data["coords"],
        }
        if walk_forbidden_keys is not None:
            forbidden = walk_forbidden_keys(coords_payload)
            if forbidden:
                raise ValueError(f"Forbidden keys found in coords payload: {forbidden}")

        coords_file = inst_dir / "coords.json"
        coords_file.write_text(json.dumps(coords_payload, indent=2), encoding="utf-8")

    # 3. Optional whitelist_refs.json for reference solution metadata
    if inst_name in KNOWN_OPTIMAL_REFS:
        ref_info = KNOWN_OPTIMAL_REFS[inst_name]
        ref_payload = {
            "problem_id": inst_name,
            "dimension": data["dimension"],
            "edge_weight_type": data["edge_weight_type"],
            "reference_type": ref_info["reference_type"],
            "optimal_value": ref_info["optimal_value"],
            "citation": ref_info["citation"],
        }
        ref_file = inst_dir / "whitelist_refs.json"
        ref_file.write_text(json.dumps(ref_payload, indent=2), encoding="utf-8")

    # 4. Validate output payload against ProblemSchema
    if validate_schema and ProblemSchema is not None:
        schema_obj = ProblemSchema(
            problem_id=inst_name,
            problem_class="tsp",
            distance_matrix=data["matrix"],
            coords=data["coords"],
        )
        assert schema_obj.problem_id == inst_name

    return inst_dir


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert TSPLIB .tsp files to OR-Path ProblemSchema JSON fixtures."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        help="Path to input .tsp file or directory containing .tsp files.",
    )
    parser.add_argument(
        "--out-dir",
        "-o",
        type=Path,
        default=_THIS_DIR / "instances",
        help="Target output directory for converted fixtures (default: eval_or_bench/instances).",
    )
    args = parser.parse_args(argv)

    if not args.input:
        parser.print_help()
        return 1

    input_path = Path(args.input)
    output_dir = Path(args.out_dir)

    if input_path.is_file():
        tsp_files = [input_path]
    elif input_path.is_dir():
        tsp_files = sorted(list(input_path.glob("*.tsp")))
    else:
        print(f"Error: Input path {input_path} does not exist.", file=sys.stderr)
        return 1

    if not tsp_files:
        print(f"No .tsp files found under {input_path}.", file=sys.stderr)
        return 1

    print(f"Converting {len(tsp_files)} TSPLIB files to {output_dir}...")
    for tsp_file in tsp_files:
        try:
            out_path = convert_tsp_to_fixture(tsp_file, output_dir)
            print(f"  [OK] {tsp_file.name} -> {out_path}")
        except Exception as exc:
            print(f"  [ERROR] {tsp_file.name}: {exc}", file=sys.stderr)
            return 1

    print("Conversion complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
