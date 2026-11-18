"""Pure NumPy/Math spatiotemporal geometry & interval-union coverage kernel.

IMPORTANT (Numbers Truth 2.0): This module deliberately contains **ZERO**
optimizer / solver imports (no ``scipy.optimize``, ``ortools``, ``highspy``,
``pulp``). Both sandbox solvers and independent physics validators may safely
import these vectorized geometric & interval-measure primitives.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

import numpy as np


def merge_intervals(
    intervals: Iterable[Sequence[float]],
    *,
    tol: float = 1e-9,
) -> list[tuple[float, float]]:
    """Coalesce overlapping or touching ``[start, end]`` intervals into sorted disjoint spans."""
    cleaned: list[tuple[float, float]] = []
    for item in intervals:
        if len(item) < 2:
            continue
        s = float(item[0])
        e = float(item[1])
        if math.isfinite(s) and math.isfinite(e) and e > s + tol:
            cleaned.append((s, e))
    if not cleaned:
        return []
    cleaned.sort(key=lambda pair: (pair[0], pair[1]))
    merged: list[tuple[float, float]] = [cleaned[0]]
    for s, e in cleaned[1:]:
        prev_s, prev_e = merged[-1]
        if s <= prev_e + tol:
            merged[-1] = (prev_s, max(prev_e, e))
        else:
            merged.append((s, e))
    return merged


def union_length(
    intervals: Iterable[Sequence[float]],
    *,
    tol: float = 1e-9,
) -> float:
    """Return total Lebesgue measure (sum of lengths) of merged intervals."""
    return float(sum(e - s for s, e in merge_intervals(intervals, tol=tol)))


def point_to_segment_distance_3d(
    points: np.ndarray,
    seg_a: np.ndarray,
    seg_b: np.ndarray,
    *,
    require_between: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized 3D shortest distance from point(s) ``points`` to segment(s) ``seg_a -> seg_b``.

    Supports broadcasting across ``(..., 3)`` arrays. Returns ``(distance, proj_s)``
    where ``proj_s`` is the normalized projection parameter along ``seg_a -> seg_b``
    before/after clamping (when ``require_between=True``, ``s`` is clamped to ``[0, 1]``).
    """
    p = np.asarray(points, dtype=np.float64)
    a = np.asarray(seg_a, dtype=np.float64)
    b = np.asarray(seg_b, dtype=np.float64)
    ab = b - a
    ap = p - a
    ab_len_sq = np.sum(ab * ab, axis=-1)
    safe_den = np.where(ab_len_sq > 1e-18, ab_len_sq, 1.0)
    raw_s = np.sum(ap * ab, axis=-1) / safe_den
    s = np.clip(raw_s, 0.0, 1.0) if require_between else raw_s
    closest = a + s[..., None] * ab
    dist = np.linalg.norm(p - closest, axis=-1)
    return dist, s


def sample_cylinder_surface(
    center_base: Sequence[float] = (0.0, 200.0, 0.0),
    radius: float = 7.0,
    height: float = 10.0,
    n_theta: int = 16,
    n_z: int = 5,
) -> np.ndarray:
    """Sample representative boundary + interior test points of a vertical cylinder target."""
    cx, cy, cz = float(center_base[0]), float(center_base[1]), float(center_base[2])
    thetas = np.linspace(0.0, 2.0 * math.pi, max(4, int(n_theta)), endpoint=False)
    zs = np.linspace(cz, cz + float(height), max(2, int(n_z)))
    pts: list[list[float]] = []
    for z in zs:
        for th in thetas:
            pts.append([cx + radius * math.cos(float(th)), cy + radius * math.sin(float(th)), float(z)])
    pts.append([cx, cy, cz])
    pts.append([cx, cy, cz + 0.5 * float(height)])
    pts.append([cx, cy, cz + float(height)])
    return np.asarray(pts, dtype=np.float64)


def contiguous_true_intervals(
    t_grid: np.ndarray,
    mask: np.ndarray,
    *,
    refine_half_step: bool = True,
) -> list[tuple[float, float]]:
    """Convert a boolean time-grid mask into continuous ``[start, end]`` intervals."""
    t = np.asarray(t_grid, dtype=np.float64)
    m = np.asarray(mask, dtype=bool)
    if t.size < 2 or not np.any(m):
        return []
    dt = float(t[1] - t[0]) if t.size > 1 else 0.0
    pad = 0.5 * dt if refine_half_step and dt > 0 else 0.0
    intervals: list[tuple[float, float]] = []
    in_seg = False
    start_t = 0.0
    for idx in range(t.size):
        flag = bool(m[idx])
        if flag and not in_seg:
            start_t = max(float(t[0]), float(t[idx]) - (pad if idx > 0 else 0.0))
            in_seg = True
        elif not flag and in_seg:
            end_t = min(float(t[-1]), float(t[idx - 1]) + pad)
            if end_t > start_t:
                intervals.append((start_t, end_t))
            in_seg = False
    if in_seg:
        end_t = float(t[-1])
        if end_t > start_t:
            intervals.append((start_t, end_t))
    return merge_intervals(intervals)


def eval_smoke_masking_intervals(
    t_grid: np.ndarray,
    missile_positions: np.ndarray,
    smoke_centers: np.ndarray,
    active_mask: np.ndarray,
    target_points: np.ndarray,
    *,
    cloud_radius: float = 10.0,
) -> tuple[list[tuple[float, float]], float]:
    """Evaluate when moving spherical smoke clouds completely occlude a target from a missile.

    Args:
        t_grid: Shape ``(T,)`` monotonically increasing time vector.
        missile_positions: Shape ``(T, 3)`` missile coordinates over ``t_grid``.
        smoke_centers: Shape ``(K, T, 3)`` (or ``(T, 3)`` for single cloud) cloud centers.
        active_mask: Shape ``(K, T)`` (or ``(T,)``) boolean active window (``z >= 0`` and ``t in [t_det, t_det+20]``).
        target_points: Shape ``(M, 3)`` sampled points on protected target.
        cloud_radius: Effective spherical occlusion radius (default 10.0 m).

    Returns:
        ``(merged_intervals, total_union_duration)`` where at time ``t``, the target is
        occluded iff for EVERY sampled target point ``j``, at least one active cloud ``k``
        has shortest distance ``<= cloud_radius`` to sight segment ``M(t) -> P_j``.
    """
    t = np.asarray(t_grid, dtype=np.float64)
    m_pos = np.asarray(missile_positions, dtype=np.float64)
    c_pos = np.asarray(smoke_centers, dtype=np.float64)
    act = np.asarray(active_mask, dtype=bool)
    tgt = np.asarray(target_points, dtype=np.float64)

    if c_pos.ndim == 2:
        c_pos = c_pos[None, :, :]
        act = act[None, :]
    if t.size < 2 or not np.any(act):
        return [], 0.0

    k_cnt, t_cnt, _ = c_pos.shape
    m_cnt = tgt.shape[0]
    # Broadcast shapes -> (K, T, M, 3)
    p = c_pos[:, :, None, :]
    a = m_pos[None, :, None, :]
    b = tgt[None, None, :, :]
    dist, _ = point_to_segment_distance_3d(p, a, b, require_between=True)  # (K, T, M)
    covered_by_k = (dist <= float(cloud_radius)) & act[:, :, None]
    # Sightline (t, j) covered if ANY cloud k covers it; target occluded at t if ALL M sightlines covered
    sight_covered = np.any(covered_by_k, axis=0)  # (T, M)
    target_occluded = np.all(sight_covered, axis=-1) if m_cnt > 1 else sight_covered[:, 0]  # (T,)
    intervals = contiguous_true_intervals(t, target_occluded)
    return intervals, union_length(intervals)


def canonical_time_grid(t_max: float = 70.0, dt: float = 0.1) -> np.ndarray:
    """Return deterministic uniform time grid ``[0, t_max]`` with step ``dt``.

    Using identical grids in solver final scoring and independent validators
    eliminates discretization quantization drift in ``recompute_objective``.
    """
    step = float(dt)
    if step <= 0.0:
        raise ValueError(f"dt must be > 0, got {dt!r}")
    return np.arange(0.0, float(t_max) + 1e-9, step, dtype=np.float64)


def eval_projectile_detonation(
    origin: Sequence[float],
    speed: float,
    direction_xy: Sequence[float],
    release_time: float,
    det_delay: float,
    *,
    g: float = 9.8,
) -> dict[str, Any]:
    """Forward kinematics for level-flight carrier release + free-fall detonation.

    Guarantees ``det_time == float(release_time) + float(det_delay)`` and
    normalizes horizontal direction ``(dx, dy, 0)``.
    """
    p0 = np.asarray(origin, dtype=np.float64).reshape(3)
    dxy = np.asarray(direction_xy[:2], dtype=np.float64)
    norm = float(np.hypot(dxy[0], dxy[1]))
    if norm <= 1e-12:
        raise ValueError(f"degenerate horizontal direction: {direction_xy!r}")
    ux = float(dxy[0] / norm)
    uy = float(dxy[1] / norm)
    u = np.array([ux, uy, 0.0], dtype=np.float64)
    v = float(speed)
    tr = max(0.0, float(release_time))
    td = max(0.0, float(det_delay))
    rel_pt = p0 + v * tr * u
    det_time = tr + td
    det_pt = np.array(
        [
            rel_pt[0] + v * ux * td,
            rel_pt[1] + v * uy * td,
            rel_pt[2] - 0.5 * float(g) * (td**2),
        ],
        dtype=np.float64,
    )
    return {
        "speed": v,
        "direction": [ux, uy, 0.0],
        "release_time": tr,
        "det_delay": td,
        "det_time": float(det_time),
        "release_point": [float(rel_pt[0]), float(rel_pt[1]), float(rel_pt[2])],
        "det_point": [float(det_pt[0]), float(det_pt[1]), float(det_pt[2])],
    }
