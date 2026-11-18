---
name: polyomino-cover
description: Polyomino exact/minimum cover, symmetry breaking, area lower bounds, and LNS spatial window repair for large grids (e.g. 30x30).
---
# Polyomino Cover & Grid Tiling Skill

1. **Solver Mode**: `solve_polyomino.py` (`ortools` CP-SAT) with `--hint-solution`, `--lns-window`, and `--symmetry-break`.
2. **Lower Bound Honesty**: Area bound `ceil(board_cells / max_piece_size)` is a valid relaxation; report `optimality_gap = objective - max(lp_bound, area_lb)` and only set `proven_optimal=True` when CP-SAT returns `OPTIMAL`.
3. **Deep Evolution Strategy (30x30+)**: Cold 60s CP-SAT stalls near feasible cover (`~229` vs `LB 225`); use Round 1 baseline -> `AddHint` warm-start -> sub-board LNS destroy-and-repair (`10x10` / `12x12` local patches where size-1..3 pieces cluster) to squeeze piece counts downward.
