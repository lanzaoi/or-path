---
name: lns-warmstart
description: Large Neighborhood Search (Destroy & Exact Repair) + CP-SAT/MIP hint warm-starting (`tools/or_kernels/lns_hybrid.py`) for closing optimality gaps.
---
# LNS + Warm-Start Exact Repair Skill

1. **Exact Kernel Signatures (`tools.or_kernels.lns_hybrid`)**:
   - `select_max_union_subset(intervals_by_item, *, max_items=None, group_caps=None, conflicts=(), scale=1000, time_limit_s=30.0) -> dict` — returns `{'ok', 'proven_optimal', 'selected', 'union_length', 'wall_time_s'}`. `intervals_by_item` is `{item_id: [(start, end), ...]}`.
   - `run_lns_loop(initial_state, evaluate_fn, repair_step_fn, *, maximize=False, n_iterations=10, time_limit_s=120.0) -> dict`
2. **Hint Injection / Warm-Start**: For continuous/hybrid solvers (`solve_box_nlp`), pass previous incumbent vectors into `initial_points=[best_x, ...]` in Round 2+ so searches never restart worse than incumbent.
3. **Structured Destroy Neighborhoods**: For grid/packing (`polyomino_cover`), scheduling (`jssp`), or multi-unit assignment problems, freeze 65%-85% of non-conflicting variables outside a spatial window / cluster / bottleneck unit, and optimize the free subset cleanly.
4. **Monotonic Ratchet**: Only accept candidate solutions when `validation_ok == True` AND objective strictly improves over incumbent; record `best_bound` vs `incumbent` gap honestly (`proven_optimal=False` if gap > 0).
