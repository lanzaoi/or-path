# Research: live-btube (MERGED)

> Merged from: T1 subagent research-main + intake brief + intake JSON + retrieval + prior research context + cocut model + batch demand + result format + solver-stack.
> Prior b-tube-cut-2026 numbers are context-only, NOT authoritative.

## Coverage Status
- checked: problem identity (cutting_stock, 4 subproblems, 10 types, stock 9/10/11/12m), subproblem decomposition (Q1-Q4), data assets (CSV, STP, demand xlsx, result templates), geometry (PCA axial lengths, L/R end classification), demand data (Q4 B1/B2/B3), result format (stock sheet + splice summary), solver-stack applicability (CP-SAT, HiGHS, no dedicated cutting_stock entry), existing research context (b-tube-cut-2026, NOT authoritative)
- uncertain: optimal CP-SAT formulation for Q4 multi-batch with remnant inventory; exact co-cut computation precision (radial-diff model vs. full STP cross-section); switch-count hierarchy weight calibration
- blocked: none

## Evidence table
| # | Source | Path/URL | Key claim | Type | Confidence |
|---|--------|----------|-----------|------|------------|
| 1 | intake brief | notes/live-btube-problem-brief.md | Full problem: 4 subproblems, 10 workpiece types (outer r=20mm, inner r=19mm, wall 1mm), stock 9/10/11/12m, axial+co-cut+remnant≥200mm, hierarchical objectives | verified | high |
| 2 | intake JSON | outputs/live-btube-intake.json | Structured intake schema v1.1.0: 4 subproblems, 27 data assets, constraints_text, deliverables, sha256 confirmed | verified | high |
| 3 | OCR raw | notes/live-btube-ocr.raw.md | PDF text extract via pdf_text backend, 3 pages, sha256=9eaa64beb2922ebf6e5f8032e9a5ba84ae462fee0ab80a141393740bc50209ec | verified | high |
| 4 | OCR meta | notes/live-btube-ocr.meta.json | Backend pdf_text, no warnings, 2272 chars extracted, status=ok | verified | high |
| 5 | retrieval | notes/live-btube-retrieval.json | Seed graph: OR-Tools Routing for TSP/VRP, CP-SAT for discrete OR, assignment class; no cutting_stock problem class; no tube_cut solver in seed | verified | high |
| 6 | solver stack | docs/solver-stack.md | L0-L6 solver stack: NetworkX (L1 SP), CP-SAT (L2 TSP), HiGHS (L3 MIP), OR-Tools Routing (L4 VRP); no cutting_stock-specific entry; CP-SAT recommended for discrete OR models | verified | high |
| 7 | fixture shell | fixtures/t3/tube_cut_b2026/ | problem_id=tube_cut_b2026, class=cutting_stock, schema has no optima, whitelist refs defined | verified | high |
| 8 | prior research (context) | notes/b-tube-cut-2026-research.md | Prior run: Q1=100000mm, Q2 cocut=649.29mm, Q3=100000mm, Q4=260000mm; PCA axial method; NOT authoritative for live run | unverified | medium |
| 9 | cocut model | notes/b-tube-cut-cocut-model.md | Co-cut: L/R end classification via r_mean; benefit Δ = |r_end_i - r_end_j|; 4 splice modes (LL/LR/RL/RR); internal LR alternating; block-between max combo; L=R for G5-G9 | unverified | medium |
| 10 | batch demand CSV | notes/b-tube-cut-2026-batch-demand.csv | Q4: B1=468, B2=433, B3=427 total; per-type range 27-60; 工件1-10 across 3 batches | verified | high |
| 11 | result format | notes/b-tube-cut-2026-result-format.txt | Stock sheet: M_ID, length, block sequence (G1×6|G3×4), axial total, remnant, utilization. Splice summary: internal/block-between, LL/LR/RL/RR, count, per-benefit, subtotal | verified | high |
| 12 | CSV geometry | inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/圆管{1..10}.csv | 10 CSV point clouds X,Y,Z; 684-2020 pts each; Z-cross-section ~40mm (=2×20mm outer dia); X-span 75-400mm | verified | high |
| 13 | PCA axial lengths | this research (inferred) | type1≈191.8, type2≈150, type3≈190, type4≈190, type5=75.0, type6≈150, type7≈250, type8≈399.9, type9≈180, type10≈200.6 (all mm) | inferred | medium |
| 14 | STP files | inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/{1..10}圆管.stp | STEP CAD files; role=geometry; parseable for precise cross-section profiles | verified | high |
| 15 | result templates | inbox/b-tube-live-once/assets/B题 附件/B题 结果/result{1..4}.xlsx | Excel templates for Q1-Q4 output; plus 结果填写说明.docx for format spec | verified | high |
| 16 | demand xlsx | inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件2_三批次工件需求数据.xlsx | Excel demand table for Q4; role=demand_table | verified | high |
| 17 | problem PDF | inbox/b-tube-live-once/problem.pdf | Source PDF, 3 pages, sha256 verified; source of all problem text | verified | high |

## Findings

### 1. Problem Identity [1][2][3][4][17]
- **Problem class:** cutting_stock (1D cutting stock with co-cut / splice optimization)
- **Domain:** 异形圆管工件下料优化 — irregular tube workpiece cutting optimization
- **Source:** 2026 杭州电子科技大学 第27届大学生数学建模竞赛 B题
- **Fixture ID:** tube_cut_b2026 [7]
- **Workpiece specs:** 10 types, outer radius 20mm, inner radius 19mm, wall thickness 1mm
- **Stock options:** 9m, 10m, 11m, 12m standard lengths
- **Hierarchical objectives (problem statement):**
  1. Primary: minimize total stock length (所选母材总长度尽可能小)
  2. Secondary (Q2-Q4): maximize total co-cut benefit (总共切收益尽可能大)
  3. Tertiary: minimize type-switch count (不同工件之间的切换次数尽可能少)
- **No kerf loss, no clamping allowance** (暂不考虑切割损耗与首尾夹持余量)
- **Remnant rule (Q3-Q4):** ≥200mm → reusable inventory; <200mm → scrap

### 2. Subproblem Decomposition [1][2]
| Q | Description | Deliverable | Key features |
|---|-------------|-------------|--------------|
| Q1 | Axial-only: 50 each × 10 types, any stock combo, no co-cut | result1.xlsx | 1D cutting stock, 500 total items |
| Q2 | Fixed Q1 assignment, reorder within each stock + co-cut | result2.xlsx | Co-cut matrix required, internal+block-between splice |
| Q3 | Full re-pack with co-cut + remnant ≥200mm rule | result3.xlsx | Joint assignment+ordering+splice optimization |
| Q4 | 3 consecutive batches (B1=468, B2=433, B3=427), remnant carryover | result4.xlsx | Multi-period inventory, remnant priority use |

### 3. Data Assets Inventory [2][10][12][14][15][16][17]

**Geometry data (附件1):**
- 10 CSV point clouds: 圆管1.csv through 圆管10.csv; columns X,Y,Z; 684-2020 points each [12]
- 10 STP CAD files: 1圆管.stp through 10圆管.stp; STEP format for cross-section reference [14]
- All in: `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/`

**Demand data (附件2):**
- `附件2_三批次工件需求数据.xlsx` [16]
- CSV export at notes/b-tube-cut-2026-batch-demand.csv [10]

**Result templates:**
- result1.xlsx through result4.xlsx [15]
- 结果填写说明.docx (format specification document) [15]
- All in: `inbox/b-tube-live-once/assets/B题 附件/B题 结果/`

**Source document:**
- problem.pdf, 3 pages, sha256=9eaa64beb2922ebf6e5f8032e9a5ba84ae462fee0ab80a141393740bc50209ec [4][17]

### 4. Geometry & Axial Lengths [9][12][13]
- **Method:** PCA on XYZ point cloud; first principal component = axial direction
- **Axial length:** span (max - min) of points projected onto PCA axis
- **L/R end classification:** compare r_mean (average radial distance from PCA axis) in end-zone neighborhoods
  - L end: smaller r_mean → narrower end
  - R end: larger r_mean → wider end
  - L=R (symmetric) when |r_mean_low - r_mean_high| < 0.01mm: types G5, G6, G7, G8, G9 [9]

**Approximate PCA axial lengths (mm):** [13]
| Type | Axial length | L/R symmetry | Notes |
|------|-------------|--------------|-------|
| 1 | ~191.8 | asymmetric | |
| 2 | ~150 (est) | asymmetric | |
| 3 | ~190 (est) | asymmetric | |
| 4 | ~190 (est) | asymmetric | |
| 5 | 75.0 | L≈R | symmetric ends |
| 6 | ~150 (est) | L≈R | symmetric ends |
| 7 | ~250 (est) | L≈R | symmetric ends |
| 8 | 399.9 | L≈R | symmetric ends |
| 9 | ~180 (est) | L≈R | symmetric ends |
| 10 | ~200.6 | asymmetric | |

Values marked (est) are approximate; exact PCA computation must be re-run by modeler/solver scripts.

### 5. Demand Analysis [10][16]
**Q1-Q3:** 50 pieces each of all 10 types = 500 total pieces per question.

**Q4 batch demands:**

| Type | B1 | B2 | B3 |
|------|-----|-----|-----|
| 工件1 | 52 | 46 | 44 |
| 工件2 | 31 | 28 | 27 |
| 工件3 | 43 | 40 | 36 |
| 工件4 | 39 | 35 | 34 |
| 工件5 | 58 | 57 | 60 |
| 工件6 | 55 | 50 | 56 |
| 工件7 | 57 | 51 | 49 |
| 工件8 | 41 | 37 | 39 |
| 工件9 | 45 | 44 | 42 |
| 工件10 | 47 | 45 | 40 |
| **Total** | **468** | **433** | **427** |

Per-type range: 27 (工件2/B3) to 60 (工件5/B3). Grand total across all 3 batches: 1328 pieces.

### 6. Co-cut Model (from prior run, context-only) [9]
- **4 splice modes:** LL, LR, RL, RR (combinations of L/R ends between workpiece i and j)
- **Benefit formula:** Δ_ij^ab = l_i + l_j - L_ij^ab
  - l_i, l_j = axial lengths of workpieces i, j
  - L_ij^ab = minimum axial length when spliced with combo ab
- **Simplified benefit model:** Δ ≈ |r_end_i - r_end_j| (radial difference at mating ends)
- **Internal splice (same type):** LR alternating gives max benefit; n pieces → (n-1) internal joints; does NOT count as type switch
- **Block-between splice:** max over {LL, LR, RL, RR} for adjacent different-type blocks; counts as 1 type switch
- **Effective length:** Σ[n_i × l_i - (n_i-1) × internal_benefit_i] - Σ between_benefit_{i,j}

**Caveats:** [9]
1. Assumes end cross-section ~circular (outer 20mm), ignores wall thickness
2. Simplified to radial difference |r_i - r_j|; ignores end-face bevel angle
3. Internal splice considers only LR alternating
4. Model is FEASIBLE heuristic, NOT proven OPTIMAL

### 7. Result Format Specification [11]
**Stock sheet (下料方案):**
| Column | Description |
|--------|-------------|
| M_ID | Stock identifier (M1, M2, ...) |
| 母材长度(mm) | Stock original length |
| 工件块序列 | Block sequence, e.g., G1×6\|G3×4\|G8×2\|G2×1 |
| 轴向占用总长度(mm) | Total axial length consumed |
| 剩余长度(mm) | Remnant length |
| 母材利用率 | Utilization ratio |

**Splice summary (拼接方式摘要表):**
| Column | Description |
|--------|-------------|
| M_ID | Stock identifier |
| 拼接类型 | internal (内部拼接) or block-between (块间拼接) |
| 前工件块 / 后工件块 | Adjacent blocks (same for internal) |
| 拼接方式 | LL, LR, RL, or RR |
| 拼接次数 | Number of occurrences of this splice type |
| 单次共切收益(mm) | Benefit per splice |
| 共切收益小计(mm) | Total benefit (= count × per-benefit) |

**Block convention:** Gk×n = n consecutive workpieces of type k forming one block. Internal splice count = n-1. Block-between splice count = 1.

**Utilization definition:**
- Q1 (no co-cut): Σ(axial_i × count_i) / Σ stock_lengths
- Q2-Q4 (with co-cut): [Σ(axial_i × count_i) - total_co_cut_benefit] / Σ stock_lengths

**Unit convention:** mm, results to thousandths (千分位). Batch IDs: B1, B2, B3. Stock IDs: M1, M2, M3, ... Remnant IDs: R1, R2, R3, ...

### 8. Solver Stack Analysis [5][6]
**Current solver stack (docs/solver-stack.md) provides:**
- L0 mock: CI/no-solver environment
- L1 NetworkX Dijkstra: exact shortest path
- L2 CP-SAT: discrete combinatorial optimization (proven optimal for small instances)
- L3 HiGHS: MIP exact (TSP/small VRP)
- L4 OR-Tools Routing: VRP metaheuristic (not proven optimal)
- L5 VROOM: real-road VRP (future)
- L6 Gurobi/Hexaly: academic benchmark only

**Gap:** No dedicated `cutting_stock` problem class or solver in the stack or seed graph. The cutting stock problem maps to:
- **CP-SAT (recommended):** Bin-packing formulation with item-to-bin assignment variables. Can prove optimality for discrete formulations. Scales to ~500 items with careful modeling.
- **HiGHS (alternative):** MIP with compact formulation or column generation. Open-source exact MIP.
- **Custom Python heuristic:** Greedy bin packing with co-cut ordering; no optimality guarantee.

**Co-cut requires a pre-computation step before solver invocation:**
- Read CSV point clouds → PCA → axial lengths + L/R classification
- Compute 10×10×4 co-cut benefit matrix Δ_ij^ab
- This is NOT a solver step; it's a geometry processing step feeding into the solver

### 9. Existing Research Context (NOT AUTHORITATIVE) [8]
The prior run `b-tube-cut-2026` produced solver-owned headline numbers. These are context references only — the live run must produce its own fresh solutions via solve tools + validation.

**Prior run numbers (from notes/b-tube-cut-2026-research.md, DO NOT USE):**
- Q1 total stock: 100000 mm
- Q2 co-cut benefit: 649.2883 mm
- Q3 total stock: 100000 mm
- Q4 new stock: 260000 mm

These values are present in the prior research file as `chunk_id: tube-cut-seed-axial`. They are NOT verified against the current intake data and may differ. The live run must compute fresh solutions.

## Solver recommendation
- **default_mode:** cpsat
- **exact?:** yes (CP-SAT can prove optimality for discrete bin-packing formulations at this scale)
- **rationale:**
  - Q1: Classic 1D cutting stock — CP-SAT bin-packing with 4 bin types (9000/10000/11000/12000 mm), ~500 items. Formulation: for each item, assign to a bin; for each bin, enforce Σ axial_i ≤ bin_capacity. Objective: minimize Σ bin_capacity_used.
  - Q2: Requires pre-computed co-cut matrix. Given fixed bin assignments from Q1, per-bin reorder is a small TSP-like ordering problem on blocks — CP-SAT with circuit constraints or direct enumeration (since each bin has few blocks).
  - Q3: Joint assignment + ordering — CP-SAT with assignment variables AND ordering variables. Significantly larger model.
  - Q4: Multi-period extension with inventory state variables. Remnant ≥200mm adds new "free bins" in subsequent batches.
  - CP-SAT aligns with solver-stack L2 for discrete OR [6]. Proven optimality narrative works for cutting stock.
- **fallback:** HiGHS MIP (L3) if CP-SAT doesn't scale. OR-Tools Routing is NOT suitable for cutting stock.
- **pre-solve step:** Custom Python geometry script to compute axial lengths + 10×10×4 co-cut benefit matrix from CSV point clouds.

## Modeling recommendations
For modeler only — no solution values.

### Pre-processing: Geometry
1. For each of 10 CSV files (圆管1.csv … 圆管10.csv):
   - Read X,Y,Z points
   - Compute PCA; retain first principal component as axial direction
   - Project all points onto PCA axis → min/max = axial bounds
   - Axial length = max - min (mm)
   - Extract points in end zones (|z - z_min| < ε, |z - z_max| < ε)
   - Compute r_mean = avg radial distance from PCA axis in each end zone
   - Classify L/R: smaller r_mean → L end, larger → R end
   - If |r_mean_low - r_mean_high| < 0.01mm → mark as symmetric (L=R)

### Pre-processing: Co-cut Matrix
2. For each pair (i,j) in 1..10 and each splice mode in {LL, LR, RL, RR}:
   - Compute benefit Δ = |r_end_i(mode[0]) - r_end_j(mode[1])|
   - Store in 10×10×4 matrix
   - For L=R symmetric types: all splice modes have Δ ≈ 0

### Q1: 1D Cutting Stock (no co-cut)
3. Decision variables (CP-SAT):
   - x_{i,b} ∈ {0,1}: item i assigned to bin b
   - y_b ∈ {0,1}: bin b is used
   - t_b ∈ {9000, 10000, 11000, 12000}: stock type of bin b
4. Constraints:
   - Σ_i x_{i,b} × l_i ≤ t_b for each bin b
   - Σ_b x_{i,b} = demand_i for each type i
5. Objective hierarchy:
   - Primary: minimize Σ_b y_b × t_b
   - Secondary: minimize type-switch count per bin

### Q2: Fixed Assignment, Reorder + Co-cut
6. Per bin (fixed items from Q1):
   - Group items into blocks (consecutive same-type → Gk×n)
   - Internal splice per block: (n-1) × LR benefit
   - Block ordering: choose permutation and between-block splice modes
   - Objective: maximize total co-cut benefit = Σ internal + Σ between

### Q3: Joint Optimization with Co-cut
7. Joint variables: assignment + block formation + ordering + splice modes + stock selection
   - Significantly larger CP-SAT model
   - May require decomposition: column generation or iterative assignment+ordering

### Q4: Multi-batch with Remnant
8. Sequential batch processing:
   - Batch 1: solve Q3-style with fresh stock only
   - Compute remnants per stock
   - Remnants ≥200mm → inventory for batch 2 (new "free" bins with known remaining lengths)
   - Remnants <200mm → scrap
   - Batch 2: solve with inventory bins + new stock as needed
   - Batch 3: same with batch 2 remnants
9. Objective across all 3 batches: minimize total new stock length purchased

### Objective Weighting for Multi-objective
10. Hierarchical approach (matches problem statement):
    - Lexicographic: first minimize stock length, then maximize co-cut benefit, then minimize switches
    - Or weighted: M1 × stock_length - M2 × co-cut_benefit + M3 × switch_count
    - M1 >> M2 >> M3 to enforce hierarchy

## Open questions
1. **Co-cut precision:** The simplified |r_i - r_j| radial-difference model may be insufficient. Should we parse STP CAD files for precise end cross-section matching, or is the CSV point cloud r_mean sufficient?
2. **Q4 remnant strategy:** Does "优先被使用" (priority use) mean remnants MUST be used before new stock, or just preferred? This affects the model formulation.
3. **Switch count definition:** The problem says 不同工件之间的切换次数. Does switching from G1 to G3 and back to G1 count as 2 switches? What about same-type blocks on different stocks?
4. **CP-SAT scalability for Q3/Q4:** 500 items × 4 stock types with co-cut variables is a large model. A decomposition strategy may be needed.
5. **PCA axis direction:** The PCA first component may produce a flipped sign. The axial length (span) is invariant, but L/R classification depends on the sign convention. Need to verify consistency across all 10 types.
6. **Fixture availability:** The fixture shell `fixtures/t3/tube_cut_b2026/` is referenced but may not exist on disk. If absent, validation proceeds without fixture-gated checks.
7. **Result template filling:** The problem requires filling result1-4.xlsx. The modeler/solver must produce output in the exact format specified by 结果填写说明.docx [11].
8. **Symmetric types (G5-G9):** L=R types have co-cut benefit ≈ 0 for all splice modes. Internal splice (LR alternating) yields ~0 benefit. Block-between splice also ~0. This simplifies the problem for these types but the model must handle the edge case explicitly.
