#!/usr/bin/env python3
"""LEGACY geometry script — prefer tools/solve_tube_cut_b2026.py (ADR-0002).

Kept for offline inspection only; product solve path is tools/solve_dispatch mode=tube.
"""
import csv
import json
import math
import os

import numpy as np

BASE = "fixtures/t3/tube_cut_b2026/raw/B题 附件/B题 数据/附件1_10种工件"
OUT = "outputs/b-tube-cut"


def load_tube(i):
    fn = os.path.join(BASE, f"圆管{i}.csv")
    with open(fn, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    pts = np.array([(float(r["X"]), float(r["Y"]), float(r["Z"])) for r in rows], dtype=float)
    return pts


def end_envelope(P, c, axis, e1, e2, t, t_end, side, n_bins=72, band=3.0):
    if side == "L":
        mask = t <= t_end + band
        inset = t[mask] - t_end
    else:
        mask = t >= t_end - band
        inset = t_end - t[mask]
    pts = P[mask]
    if len(pts) == 0:
        return np.zeros(n_bins)
    rel = pts - c
    ang = np.arctan2(rel @ e2, rel @ e1)
    bins = np.floor((ang + math.pi) / (2 * math.pi) * n_bins).astype(int)
    bins = np.clip(bins, 0, n_bins - 1)
    env = np.full(n_bins, np.nan)
    for b in range(n_bins):
        sel = inset[bins == b]
        if len(sel):
            env[b] = float(np.min(sel))
    idx = np.arange(n_bins)
    good = ~np.isnan(env)
    if not good.any():
        return np.zeros(n_bins)
    env[~good] = np.interp(idx[~good], idx[good], env[good], period=n_bins)
    return np.maximum(env, 0.0)


def analyze_tube(i, pts: np.ndarray):
    c = pts.mean(axis=0)
    _, _, Vt = np.linalg.svd(pts - c, full_matrices=False)
    axis = Vt[0].copy()
    if axis @ np.array([1.0, 0.0, 0.0]) < 0:
        axis = -axis
    t = (pts - c) @ axis
    t_min, t_max = float(t.min()), float(t.max())
    axial_len = t_max - t_min

    tmp = np.array([0.0, 0.0, 1.0]) if abs(axis[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(axis, tmp)
    e1 /= np.linalg.norm(e1) + 1e-15
    e2 = np.cross(axis, e1)
    e2 /= np.linalg.norm(e2) + 1e-15

    L_env = end_envelope(pts, c, axis, e1, e2, t, t_min, "L")
    R_env = end_envelope(pts, c, axis, e1, e2, t, t_max, "R")

    # L = smaller end "openness" proxy: mean envelope (more inset material → smaller end face)
    L_score = float(np.mean(L_env))
    R_score = float(np.mean(R_env))
    # Problem: L = smaller axial projection end. Use end radial mean as secondary.
    # Keep labels: left physical end vs right along +axis
    # Map L/R labels by score (smaller mean inset spread → L)
    if L_score <= R_score:
        L_end, R_end = "left", "right"
    else:
        L_end, R_end = "right", "left"

    return {
        "axial_len_mm": round(axial_len, 4),
        "axis": [round(float(x), 6) for x in axis],
        "t_min": t_min,
        "t_max": t_max,
        "left_env_mean": round(float(np.mean(L_env)), 4),
        "right_env_mean": round(float(np.mean(R_env)), 4),
        "L_end": L_end,
        "R_end": R_end,
        "L_env": L_env.tolist(),
        "R_env": R_env.tolist(),
        "n_points": int(len(pts)),
        # keep old keys so solve scripts don't break
        "z_min": t_min,
        "z_max": t_max,
        "left_z_spread": round(float(np.ptp(L_env)), 4),
        "right_z_spread": round(float(np.ptp(R_env)), 4),
        "left_min_radius": round(float(np.min(L_env)), 4),
        "right_min_radius": round(float(np.min(R_env)), 4),
    }


def env_for_label(tube, label: str):
    """label L/R → envelope array for that logical end."""
    phys = tube["L_end"] if label == "L" else tube["R_end"]
    return np.array(tube["L_env"] if phys == "left" else tube["R_env"], dtype=float)


def cocut_saving(ti, tj, mode: str) -> float:
    ei = env_for_label(ti, mode[0])
    ej = env_for_label(tj, mode[1])
    n = len(ei)
    best = 0.0
    for shift in range(n):
        nest = float(np.min(ei + np.roll(ej, shift)))
        if nest > best:
            best = nest
    li, lj = ti["axial_len_mm"], tj["axial_len_mm"]
    best = min(best, 0.5 * li, 0.5 * lj)
    return round(max(0.0, best), 4)


def compute_cocut_savings(tubes):
    savings = {}
    for i in range(1, 11):
        for j in range(1, 11):
            ti, tj = tubes[i], tubes[j]
            savings[f"G{i}-G{j}"] = {
                m: cocut_saving(ti, tj, m) for m in ("LL", "LR", "RL", "RR")
            }
    return savings


def main():
    os.makedirs(OUT, exist_ok=True)
    tubes = {}
    for i in range(1, 11):
        pts = load_tube(i)
        tubes[i] = analyze_tube(i, pts)

    print("=" * 80)
    print("TUBE GEOMETRY (PCA axis — bugfix)")
    print("=" * 80)
    print(f"{'Tube':>6} {'AxialLen':>10} {'L_end':>6} {'R_end':>6} {'n':>6}")
    for i in range(1, 11):
        t = tubes[i]
        print(f"  G{i:<2d}  {t['axial_len_mm']:10.3f} {t['L_end']:>6} {t['R_end']:>6} {t['n_points']:6d}")

    geo_out = {
        "description": "Tube geometry (PCA axial length; Hermes fix of Pi Z-bug)",
        "bugfix": "axial was Z_max-Z_min; now PCA first-axis span",
        "tubes": {f"G{i}": {k: v for k, v in tubes[i].items() if k not in ("L_env", "R_env")} for i in range(1, 11)},
    }
    # keep full envs in separate file for debug
    with open(os.path.join(OUT, "tube_geometry.json"), "w", encoding="utf-8") as f:
        json.dump(geo_out, f, indent=2, ensure_ascii=False)

    # store envs lightly for cocut recompute
    with open(os.path.join(OUT, "tube_end_envs.json"), "w", encoding="utf-8") as f:
        json.dump({f"G{i}": {"L_env": tubes[i]["L_env"], "R_env": tubes[i]["R_env"], "L_end": tubes[i]["L_end"], "R_end": tubes[i]["R_end"], "axial_len_mm": tubes[i]["axial_len_mm"]} for i in range(1, 11)}, f)

    savings = compute_cocut_savings(tubes)
    with open(os.path.join(OUT, "cocut_savings.json"), "w", encoding="utf-8") as f:
        json.dump(savings, f, indent=2, ensure_ascii=False)
    # Pi solve_all also reads cocut_benefits.json
    with open(os.path.join(OUT, "cocut_benefits.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "description": "Co-cutting benefit 10x10x4",
                "unit": "mm",
                "method": "end-envelope nest max_rot min_theta(env_i+env_j); Hermes fix",
                "matrix": savings,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    axial = {
        "source": "PCA first principal axis span of point cloud (tube axis)",
        "bugfix": "was Z_max-Z_min (~40mm cross-section diameter)",
        "pipe_outer_radius_mm": 20,
        "pipe_inner_radius_mm": 19,
        "axial_lengths_mm": {f"G{i}": tubes[i]["axial_len_mm"] for i in range(1, 11)},
        "total_one_each_mm": round(sum(tubes[i]["axial_len_mm"] for i in range(1, 11)), 4),
        "total_50_each_mm": round(50 * sum(tubes[i]["axial_len_mm"] for i in range(1, 11)), 4),
    }
    with open(os.path.join(OUT, "axial_lengths.json"), "w", encoding="utf-8") as f:
        json.dump(axial, f, indent=2, ensure_ascii=False)

    print("\nSaved axial_lengths.json / cocut_savings.json / cocut_benefits.json / tube_geometry.json")
    print("axial_lengths_mm:", axial["axial_lengths_mm"])
    print("sample cocut G1-G1", savings["G1-G1"])


if __name__ == "__main__":
    main()
