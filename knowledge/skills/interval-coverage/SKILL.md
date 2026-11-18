---
name: interval-coverage
description: Spatiotemporal interval-union coverage, line-of-sight occlusion, and multi-agent interval assignment kernel (`tools/or_kernels/interval_coverage.py`).
---
# Spatiotemporal Interval-Union Coverage Skill

1. **Exact Kernel Signatures (`tools.or_kernels.interval_coverage`)** *(NO optimizer imports — safe inside BOTH solver & validator)*:
   - `canonical_time_grid(t_max, dt=0.1) -> np.ndarray` (standardized uniform grid `[0, t_max]` step `dt` so solver and validator agree to `1e-6`)
   - `eval_projectile_detonation(origin_t0, speed, direction_xy, release_time, det_delay, *, g=9.8) -> dict` (`origin_t0` MUST be carrier position at `t=0`, NEVER `release_point`! Computes `release_point = origin_t0 + speed * release_time * u_xy` and `det_point`, **`det_time = release_time + det_delay`**)
   - `sample_cylinder_surface(center_base, radius, height, n_theta=16, n_z=5) -> np.ndarray` (shape `(N, 3)`)
   - `eval_smoke_masking_intervals(t_grid, missile_positions, smoke_centers, active_mask, target_points, *, cloud_radius=10.0) -> tuple[list[tuple[float, float]], float]` (`t_grid`: `(T,)`, `missile_positions`: `(T, 3)` e.g. `pos0 + v_vec * t_grid[:, None]`, `smoke_centers`: `(K, T, 3)` or `(T, 3)` e.g. `C0[None, :] + vel * dt[:, None]`, `active_mask`: bool `(K, T)` or `(T,)`, `target_points`: `(P, 3)`; NEVER `np.tile(vec, t_grid.shape)` which produces 1D!; returns `(merged_intervals, union_len)`)
   - `merge_intervals(intervals, *, tol=1e-9) -> list[tuple[float, float]]`
   - `union_length(intervals, *, tol=1e-9) -> float`
   - `point_to_segment_distance_3d(points, seg_a, seg_b, *, require_between=True) -> tuple[np.ndarray, np.ndarray]`
2. **Exact Interval Union Measure & Grid Consistency**:
   - Multiple agents covering overlapping time windows MUST merge intervals (`merge_intervals`) before summing length (`union_length`) — never sum raw durations without union deduplication.
   - **CRITICAL**: `validate_solution.py` checks `recompute_objective` with `atol=1e-6`! Your final reported `objective` inside `custom_solver.py` AND `*-custom-validate.py` MUST evaluate `eval_smoke_masking_intervals` using the **EXACT SAME `t_grid = canonical_time_grid(t_max, dt)` and target sampling density** (during coarse DE search you may use coarser steps, then re-score final winning candidates on the exact canonical grid before writing `solution.json`).
3. **LOS-Segment Corridor Seeding & Forward Kinematic Consistency (No Clamping Traps!)**:
   - Blind box sampling over `[0, 2π] × [v_min, v_max] × [0, T]` almost always hits `0.0` when masking small targets. Generate physics-informed candidates analytically along the line-of-sight segment `B(t, f, dz) = Target + f * (Observer(t) - Target) + (0, 0, dz)`, check `det_delay = sqrt(2*(z0 - B_z)/g)`, require `release_time = t_hit - det_delay >= 0.0` (**REJECT `release_time < 0`**, NEVER clamp `release_time = max(0, ...)` without updating `det_time`), and ALWAYS reconstruct final `det_point` and `det_time = release_time + det_delay` via forward `eval_projectile_detonation(...)` so `det_time == release_time + det_delay` holds identically!
   - For high-dimensional multi-agent/multi-target scenarios (>10 continuous vars), NEVER feed all 20–40 vars into a single low-budget `solve_box_nlp`: optimize in 4–8D corridors per `(agent, target)` first, then select/refine complementary windows.
4. **Multi-Agent Coverage & Coupled Heading Integrity**:
   - When a subproblem requires specific agents (`allowed_agents`), ALWAYS parameterize candidate search over **`for agent_id in allowed_agents:`** — NEVER hardcode a single `<agent_id>` inside `cand(...)`!
   - When the same carrier agent `i` drops/deploys multiple units across multiple targets simultaneously, ALL deployments from agent `i` share ONE constant `(speed_i, direction_xy_i)` vector, cumulative item cap `<= max_items_per_agent`, and pairwise inter-release spacing `|t_rel_a - t_rel_b| >= min_gap` jointly across ALL targets! Group outputs cleanly (`by_agent[agent_id]`), NEVER `zip(agent_list, flat_bombs_list)`.
   - Zero-required-arg CLI support in `*-custom-validate.py` (`python outputs/<slug>-custom-validate.py`).
