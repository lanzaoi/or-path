# OR Fixture Study (live-btube) — Cited

## Abstract
We study a `tube_cut` instance (`b-tube-cut`) with deterministic OR tools.
Solver honesty: **search/feasible track — not proven optimum** [S1].
All numerics bind to solver JSON [S1] + validate [V1].

## Problem statement
- problem_id: `b-tube-cut` [S1]
- problem_class: `tube_cut` [S1]
- fixture: `shell_only:adhoc:b-tube-cut`
- Source: 2026 杭州电子科技大学 第27届大学生数学建模竞赛 B题 [E1][E2][E17]
- 10 workpiece types, outer r=20mm, inner r=19mm, wall 1mm [E1][E2]
- Stock options: 9m, 10m, 11m, 12m standard lengths [E1]
- Hierarchical objectives: (1) minimize total stock length, (2) maximize co-cut benefit, (3) minimize type-switch count [E1][E2]

## Related modeling notes
- Research: `C:\Users\Lanzao\Desktop\agent\notes\live-btube-research.md` [R1]
- Retrieval: `C:\Users\Lanzao\Desktop\agent\notes\live-btube-retrieval.json` [R2]
- Explain: `C:\Users\Lanzao\Desktop\agent\notes\live-btube-explain.md`
- Solver-stack guidance: `docs/solver-stack.md` [E6]
- Co-cut model (context): `notes/b-tube-cut-cocut-model.md` [E9]

Evidence for modeling claims must appear in the research evidence table (paths/chunk_ids) [R1].

## Method / formulation
- Schema: `C:\Users\Lanzao\Desktop\agent\outputs\live-btube-schema.json`
- Solver: `tools/solve_tube_cut_b2026.py` → `tube-bfd` heuristic [S1]
- Solver owns optima; LLM must not invent objective/path/tour/routes [S1]
- Pre-processing: PCA on CSV point clouds → axial lengths + L/R end classification [E12][E13]
- Co-cut benefit matrix: 10×10×4, based on radial-difference model [E9]

## Results
From `C:\Users\Lanzao\Desktop\agent\outputs\live-btube-solution.json` [S1] only:
- status: `FEASIBLE`
- objective = `99000.0`
- solver: `tube-bfd`
- meta.exact: `False`
- meta.proven_optimal: `False`
- meta.method_class: `heuristic`
- meta.claim: `FEASIBLE BFD/heuristic; not proven OPTIMAL`

### Q1 — Axial-only cutting stock (no co-cut)
Method: BFD multi-stock + type-block grouping [S1:q1.method].
Status: `FEASIBLE`, heuristic track [S1:q1.exact=false].

| Metric | Value | Source |
|--------|-------|--------|
| Total stock length | 100000.0 mm | [S1:q1.total_stock_length_mm] |
| Total axial length consumed | 99055.745 mm | [S1:q1.total_axial_length_mm] |
| Utilization | 0.990557 | [S1:q1.utilization] |
| Total type switches | 12 | [S1:q1.total_switch] |
| Stock count | 10 stocks (M1–M10) | [S1:q1.stocks] |
| Demand | 50 per type (G1–G10) | [S1:q1.demand] |

### Q2 — Fixed Q1 assignment, reorder + co-cut
Method: Q1 assignment + type-block TSP-ish + end orientation DP [S1:q2.method].
Status: `FEASIBLE` [S1:q2.status].

| Metric | Value | Source |
|--------|-------|--------|
| Total raw axial length | 99055.745 mm | [S1:q2.total_raw_length_mm] |
| Total co-cut benefit | 464.2431 mm | [S1:q2.total_co_cut_benefit_mm] |
| Total effective length | 98591.5019 mm | [S1:q2.total_effective_length_mm] |
| Utilization (effective) | 0.985915 | [S1:q2.utilization] |
| Total type switches | 12 | [S1:q2.total_switch] |

### Q3 — Full re-pack with co-cut + remnant ≥200mm rule
Method: adjusted-length BFD + cocut refine [S1:q3.method].
Status: `FEASIBLE` [S1:q3.status].

| Metric | Value | Source |
|--------|-------|--------|
| Total stock length | 99000.0 mm | [S1:q3.total_stock_length_mm] |
| Total raw axial length | 99055.745 mm | [S1:q3.total_raw_length_mm] |
| Total co-cut benefit | 466.4661 mm | [S1:q3.total_co_cut_benefit_mm] |
| Total effective length | 98516.1333 mm | [S1:q3.total_effective_length_mm] |
| Utilization (effective) | 0.995851 | [S1:q3.utilization] |
| Total type switches | 12 | [S1:q3.total_switch] |
| Stock types | 11000 mm × 9 (M1–M9) | [S1:q3.stocks] |

**Note:** Q3 selects 11000 mm stock exclusively (9 stocks), achieving the top-level objective of 99000.0 mm [S1].

### Q4 — Multi-batch with remnant carryover
Method: sequential batches + remnant ≥200mm reuse + BFD [S1:q4.method].
Status: `FEASIBLE` [S1:q4.status].

| Metric | Value | Source |
|--------|-------|--------|
| Total stock length (all batches) | 260000.0 mm | [S1:q4.total_stock_length_mm] |
| Total new standard stock | 260000.0 mm | [S1:q4.total_new_standard_stock_mm] |
| Total co-cut benefit | 1020.5559 mm | [S1:q4.total_co_cut_benefit_mm] |
| Total type switches | 40 | [S1:q4.total_switch] |
| Final inventory (remnants ≥200mm) | [208.7168, 2338.5013] mm | [S1:q4.final_inventory_mm] |

**Batch breakdown** [S1:q4.batches]:

| Batch | Stock length (mm) | Raw axial (mm) | Co-cut benefit (mm) | Effective length (mm) | Utilization | Switches |
|-------|-------------------|----------------|---------------------|----------------------|-------------|----------|
| B1 | 96000.0 | 91146.9095 | 366.0805 | 90780.829 | 0.945634 | 12 |
| B2 | 84646.629 | 83699.2641 | 337.479 | 83361.7851 | 0.984821 | 15 |
| B3 | 84791.88 | 82267.5391 | 316.9964 | 81950.5427 | 0.96649 | 13 |

B1 used 8 × 12000 mm stock [S1:q4.batches[0].result]. B2 and B3 used a mix of new standard stock and remnant inventory carried over from prior batches [S1:q4.batches[1].result][S1:q4.batches[2].result].

Remnant carryover: B1→B2 inventory = [4646.6286] mm; B2→B3 inventory = [791.8799] mm [S1:q4.batches].

## Top-level objective
- **objective = `99000.0`** — sourced from [S1:objective]; solver-owned, not LLM-invented.
- Decomposition: Q3 achieves 99000.0 mm stock; Q1 uses 100000.0 mm baseline; Q4 uses 260000.0 mm across 3 batches.
- The 99000.0 value reflects the Q3 optimized re-pack with co-cut benefit applied.

## Validation
- validate report: `C:\Users\Lanzao\Desktop\agent\outputs\live-btube-validate.json` [V1]
- Feasibility and objective recomputed by `validate_solution` when available.
- Validate gate exit code: see `outputs/live-btube-verify-notes.md` for full gate results.

## Limitations
- Fixture or declared scale only.
- `meta.proven_optimal` = `False` — **do not claim any optimality.** Results are heuristic-only. [S1]
- Results are FEASIBLE heuristic-track; no optimality proof exists.
- Co-cut benefit model uses simplified radial-difference approximation [E9].
- Live multi-agent prose quality is separate from gate-green numerics.

## Citation key

| Tag | Source | Path |
|-----|--------|------|
| [S1] | Solution JSON | `C:\Users\Lanzao\Desktop\agent\outputs\live-btube-solution.json` |
| [V1] | Validate JSON | `C:\Users\Lanzao\Desktop\agent\outputs\live-btube-validate.json` |
| [R1] | Research notes | `C:\Users\Lanzao\Desktop\agent\notes\live-btube-research.md` |
| [R2] | Retrieval JSON | `C:\Users\Lanzao\Desktop\agent\notes\live-btube-retrieval.json` |
| [E1] | Intake brief | `notes/live-btube-problem-brief.md` |
| [E2] | Intake JSON | `outputs/live-btube-intake.json` |
| [E3] | OCR raw | `notes/live-btube-ocr.raw.md` |
| [E6] | Solver stack | `docs/solver-stack.md` |
| [E9] | Co-cut model | `notes/b-tube-cut-cocut-model.md` |
| [E10] | Batch demand CSV | `notes/b-tube-cut-2026-batch-demand.csv` |
| [E12] | CSV geometry | `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/` |
| [E13] | PCA axial lengths | Research findings (inferred, medium confidence) |
| [E16] | Demand xlsx | `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件2_三批次工件需求数据.xlsx` |
| [E17] | Problem PDF | `inbox/b-tube-live-once/problem.pdf` |
| [W1] | Whitelist | `outputs/live-btube-intake-whitelist.json` |

## Sources (file references)
- `C:/Users/Lanzao/Desktop/agent/notes/live-btube-problem-brief.md` [E1]
- `C:/Users/Lanzao/Desktop/agent/outputs/live-btube-intake.json` [E2]
- `C:/Users/Lanzao/Desktop/agent/notes/live-btube-research.md` [R1]
- `C:/Users/Lanzao/Desktop/agent/outputs/live-btube-solution.json` [S1]
- `C:/Users/Lanzao/Desktop/agent/outputs/live-btube-validate.json` [V1]
- `C:/Users/Lanzao/Desktop/agent/outputs/live-btube-intake-whitelist.json` [W1]
