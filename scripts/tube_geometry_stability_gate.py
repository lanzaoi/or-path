#!/usr/bin/env python3
"""Independent Tube geometry convergence gate.

This module intentionally does not import geometry functions from
``tools/solve_tube_cut_b2026.py``.  It is a second implementation that reads
the authorised CSVs, rebuilds PCA axes, conservative end profiles and the
10x10x4 co-cut matrix, then checks 180/360/720 convergence.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = (
    ROOT
    / "fixtures"
    / "t3"
    / "tube_cut_b2026"
    / "raw"
    / "B题 附件"
    / "B题 数据"
    / "附件1_10种工件"
)
GIDS = tuple(f"G{i}" for i in range(1, 11))
RADIUS_DEG = 6.25
MODES = ("LL", "LR", "RL", "RR")


def _points(index: int) -> np.ndarray:
    path = CSV_DIR / f"圆管{index}.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    return frame[["X", "Y", "Z"]].to_numpy(dtype=float)


def _geometry(index: int, bins: int) -> dict:
    points = _points(index)
    center = points.mean(axis=0)
    _u, singular, vt = np.linalg.svd(points - center, full_matrices=False)
    axis = vt[0].copy()
    pivot = int(np.argmax(np.abs(axis)))
    if axis[pivot] < 0:
        axis = -axis
    axial = (points - center) @ axis
    low, high = float(axial.min()), float(axial.max())
    reference = (
        np.array([0.0, 0.0, 1.0])
        if abs(axis[2]) < 0.9
        else np.array([0.0, 1.0, 0.0])
    )
    cross_1 = np.cross(axis, reference)
    cross_1 /= np.linalg.norm(cross_1) + 1e-15
    cross_2 = np.cross(axis, cross_1)
    cross_2 /= np.linalg.norm(cross_2) + 1e-15
    relative = points - center
    angles = np.arctan2(relative @ cross_2, relative @ cross_1)
    target_angles = -np.pi + (np.arange(bins, dtype=float) + 0.5) * 2 * np.pi / bins
    radius = np.deg2rad(RADIUS_DEG)

    def envelope(side: str) -> list[float]:
        values = []
        for target in target_angles:
            distance = np.abs(np.angle(np.exp(1j * (angles - target))))
            selected = distance <= radius + 1e-12
            if not selected.any():
                selected = distance <= float(distance.min()) + 1e-12
            edge = (
                float(axial[selected].min())
                if side == "L"
                else float(axial[selected].max())
            )
            inset = edge - low if side == "L" else high - edge
            values.append(max(0.0, inset))
        return values

    return {
        "length": round(high - low, 4),
        "L": envelope("L"),
        "R": envelope("R"),
        "pca_ratio_1_2": float(singular[0] / singular[1]),
    }


def _saving(left: dict, right: dict, mode: str) -> float:
    first = np.asarray(left[mode[0]], dtype=float)
    second = np.asarray(right[mode[1]], dtype=float)
    if mode[0] == mode[1]:
        second = second[::-1]
    best = max(
        float(np.min(first + np.roll(second, shift)))
        for shift in range(len(first))
    )
    best = min(best, left["length"] * 0.5, right["length"] * 0.5)
    return round(max(0.0, best), 4)


def _matrix(bins: int) -> tuple[dict, dict]:
    geometries = {f"G{i}": _geometry(i, bins) for i in range(1, 11)}
    savings = {
        f"{a}-{b}": {mode: _saving(geometries[a], geometries[b], mode) for mode in MODES}
        for a in GIDS
        for b in GIDS
    }
    return geometries, savings


def _comparison(left: dict, right: dict, left_bins: int, right_bins: int) -> dict:
    rows = [
        {
            "pair": pair,
            "mode": mode,
            "left_mm": left[pair][mode],
            "right_mm": right[pair][mode],
            "absolute_delta_mm": abs(left[pair][mode] - right[pair][mode]),
        }
        for pair in left
        for mode in MODES
    ]
    deltas = np.asarray([row["absolute_delta_mm"] for row in rows])
    worst = max(rows, key=lambda row: row["absolute_delta_mm"])
    return {
        "left_bins": left_bins,
        "right_bins": right_bins,
        "matrix_entries": len(rows),
        "max_absolute_delta_mm": round(float(deltas.max()), 6),
        "p95_absolute_delta_mm": round(float(np.quantile(deltas, 0.95)), 6),
        "entries_over_0_5_mm": int(np.count_nonzero(deltas > 0.5)),
        "entries_over_1_mm": int(np.count_nonzero(deltas > 1.0)),
        "worst": worst,
        "pass": float(deltas.max()) <= 0.5 and float(np.quantile(deltas, 0.95)) <= 0.2,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent Tube geometry stability gate")
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=ROOT / "outputs" / "b-tube-cut" / "model_snapshot.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "tube-geometry-stability.json",
    )
    args = parser.parse_args(argv)
    try:
        built = {bins: _matrix(bins) for bins in (180, 360, 720)}
        comparisons = [
            _comparison(built[180][1], built[360][1], 180, 360),
            _comparison(built[360][1], built[720][1], 360, 720),
        ]
        snapshot_match = None
        snapshot_detail = None
        if args.snapshot.is_file():
            snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
            bins = int(snapshot.get("profile_bins") or 0)
            if bins in built:
                independent_geos, independent_savings = built[bins]
            else:
                independent_geos, independent_savings = _matrix(bins)
            lengths_match = all(
                abs(float(snapshot["lengths"][gid]) - independent_geos[gid]["length"])
                <= 1e-6
                for gid in GIDS
            )
            savings_match = all(
                abs(float(snapshot["savings"][pair][mode]) - independent_savings[pair][mode])
                <= 1e-6
                for pair in independent_savings
                for mode in MODES
            )
            method_match = (
                snapshot.get("profile_method")
                == "fixed_angular_neighborhood_conservative_v1"
                and abs(
                    float(snapshot.get("angular_neighborhood_radius_deg") or 0.0)
                    - RADIUS_DEG
                )
                <= 1e-12
            )
            snapshot_match = lengths_match and savings_match and method_match
            snapshot_detail = {
                "bins": bins,
                "lengths_match": lengths_match,
                "savings_match": savings_match,
                "method_match": method_match,
            }
        symmetry_ok = all(
            abs(built[360][1][f"{a}-{b}"]["LL"] - built[360][1][f"{b}-{a}"]["LL"])
            <= 1e-6
            and abs(
                built[360][1][f"{a}-{b}"]["LR"]
                - built[360][1][f"{b}-{a}"]["RL"]
            )
            <= 1e-6
            for a in GIDS
            for b in GIDS
        )
        payload = {
            "schema": "orpath.tube_geometry_stability.v1",
            "implementation": "independent_no_solver_geometry_import",
            "profile_method": "fixed_angular_neighborhood_conservative_v1",
            "angular_neighborhood_radius_deg": RADIUS_DEG,
            "thresholds": {"p95_absolute_delta_mm": 0.2, "max_absolute_delta_mm": 0.5},
            "comparisons": comparisons,
            "symmetry_ok": symmetry_ok,
            "snapshot_match": snapshot_match,
            "snapshot_detail": snapshot_detail,
            "pca_ratio_1_2_min": round(
                min(geo["pca_ratio_1_2"] for geo in built[360][0].values()), 6
            ),
            "step_collision_proof": False,
            "ok": all(row["pass"] for row in comparisons)
            and symmetry_ok
            and snapshot_match is not False,
        }
    except Exception as exc:  # noqa: BLE001
        payload = {"schema": "orpath.tube_geometry_stability.v1", "ok": False, "error": str(exc)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("PASS tube_geometry_stability_gate" if payload["ok"] else "FAIL tube_geometry_stability_gate")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
