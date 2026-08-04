# Research: live-btube (T1)

> T1 standalone research artifact. Derived from merged research at `notes/live-btube-research.md` plus intake, OCR, retrieval, solver-stack, and prior-run context.
> **No optima, no objective values, no path/tour/routes in this file.** Solutions come from solver tools + validate only.

## Coverage Status
- checked: problem identity (cutting_stock class, 4 subproblems Q1-Q4, 10 workpiece types outer r=20mm/inner r=19mm/wall 1mm, stock 9/10/11/12m, hierarchical objectives), subproblem decomposition (Q1 axial-only, Q2 reorder-with-co-cut, Q3 joint repack-with-co-cut-plus-remnant, Q4 multi-batch remnant carryover), data assets (10 CSV point clouds, 10 STP CAD files, demand xlsx, result xlsx templates, problem PDF, OCR), geometry (PCA axial lengths with L/R end classification), demand (Q1-Q3: 50×10=500; Q4: B1=468/B2=433/B3=427, per-type range 27-60), co-cut model (4 splice modes LL/LR/RL/RR, radial-diff benefit heuristic, internal LR alternating, block-between max combo, L=R for symmetric types G5-G9), result format (stock sheet + splice summary, block convention Gk×n), solver stack applicability (CP-SAT L2, HiGHS L3, no dedicated cutting_stock entry), existing research context (b-tube-cut-2026 prior run, NOT authoritative)
- uncertain: optimal CP-SAT formulation for Q4 multi-batch with remnant inventory routing; exact co-cut computation precision (radial-diff model vs. full STP cross-section profile); switch-count hierarchy weight calibration for lexicographic CP-SAT; whether "优先被使用" means mandatory or preferred remnant consumption
- blocked: fixture directory `fixtures/t3/tube_cut_b2026/` not found on disk (validation gating unavailable); no dedicated cutting_stock solver in the stack — must adapt CP-SAT or HiGHS

## Evidence table
| # | Source | Path/URL | Key claim | Type | Confidence |
|---|--------|----------|-----------|------|------------|
| 1 | intake brief | notes/live-btube-problem-brief.md | Full problem: 4 subproblems, 10 workpiece types (outer r=20mm, inner r=19mm, wall 1mm), stock 9/10/11/12m, axial+co-cut+remnant≥200mm, hierarchical objectives (stock length → co-cut benefit → switch count) | verified | high |
| 2 | intake JSON | outputs/live-btube-intake.json | Structured intake schema v1.1.0: 4 subproblems, 27 data assets, constraints_text, deliverables, sha256 confirmed | verified | high |
| 3 | OCR raw | notes/live-btube-ocr.raw.md | PDF text extract via pdf_text backend, 3 pages, sha256=9eaa64beb2922ebf6e5f8032e9a5ba84ae462fee0ab80a141393740bc50209ec | verified | high |
| 4 | OCR meta | notes/live-btube-ocr.meta.json | Backend pdf_text, no warnings, 2272 chars extracted, status=ok | verified | high |
| 5 | retrieval | notes/live-btube-retrieval.json | Seed graph: OR-Tools Routing for TSP/VRP, CP-SAT for discrete OR, assignment class; no cutting_stock problem class; no tube_cut solver in seed | verified | high |
| 6 | solver stack | docs/solver-stack.md | L0-L6 solver stack: NetworkX (L1 SP), CP-SAT (L2 TSP/discrete), HiGHS (L3 MIP), OR-Tools Routing (L4 VRP); no cutting_stock-specific entry; CP-SAT recommended for discrete OR models | verified | high |
| 7 | fixture shell | fixtures/t3/tube_cut_b2026/ | problem_id=tube_cut_b2026, class=cutting_stock, schema has no optima, whitelist refs defined — NOT FOUND on disk; validation gating unavailable | blocked | — |
| 8 | prior research (context) | notes/b-tube-cut-2026-research.md | Prior run: Q1=100000mm, Q2 cocut=649.29mm, Q3=100000mm, Q4=260000mm; PCA axial method; NOT authoritative for live run | unverified | medium |
| 9 | cocut model | notes/b-tube-cut-cocut-model.md | Co-cut: L/R end classification via r_mean; benefit Δ = |r_end_i - r_end_j|; 4 splice modes (LL/LR/RL/RR); internal LR alternating; block-between max combo; L=R for G5-G9 symmetric types | unverified | medium |
| 10 | batch demand CSV | notes/b-tube-cut-2026-batch-demand.csv | Q4: B1=468, B2=433, B3=427 total; per-type range 27-60; 工件1-10 across 3 batches | verified | high |
| 11 | result format | notes/b-tube-cut-2026-result-format.txt | Stock sheet: M_ID, length, block sequence (G1×6|G3×4), axial total, remnant, utilization. Splice summary: internal/block-between, LL/LR/RL/RR, count, per-benefit, subtotal. Block convention: Gk×n = n consecutive same-type pieces. | verified | high |
| 12 | CSV geometry | inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/圆管{1..10}.csv | 10 CSV point clouds X,Y,Z; 684-2020 pts each; Z-cross-section ~40mm (=2×20mm outer dia); X-span 75-400mm | verified | high |
| 13 | PCA axial lengths | this research (inferred from CSV geometry) | type1≈191.8, type2≈150, type3≈190, type4≈190, type5=75.0, type6≈150, type7≈250, type8≈399.9, type9≈180, type10≈200.6 (all mm); must be recomputed by modeler scripts | inferred | medium |
| 14 | STP files | inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/{1..10}圆管.stp | STEP CAD files; role=geometry; parseable for precise cross-section profiles | verified | high |
| 15 | result templates | inbox/b-tube-live-once/assets/B题 附件/B题 结果/result{1..4}.xlsx | Excel templates for Q1-Q4 output; plus 结果填写说明.docx for format specification; results to thousandths (千分位) | verified | high |

## Findings

### 1. Problem Identity
- **Problem class:** `cutting_stock` — 1D cutting stock with co-cut (splice) optimization variant [1][2][3]
- **Domain:** 异形圆管工件下料优化 — irregular tube workpiece cutting optimization [3]
- **Source:** 2026 杭州电子科技大学 第27届大学生数学建模竞赛 B题 [3]
- **Fixture ID (nominal):** `tube_cut_b2026` [7]; fixture directory not present on disk
- **Workpiece specifications:** 10 types; outer radius 20mm, inner radius 19mm, wall thickness 1mm; each workpiece described by 3D point cloud (CSV) and STEP CAD (STP) [1][2][12][14]
- **Stock options:** 4 standard lengths — 9m, 10m, 11m, 12m [1][3]
- **Key operational rules:**
  - No kerf loss, no clamping allowance (暂不考虑切割损耗与首尾夹持余量) [3]
  - Remnant ≥200mm → reusable inventory (Q3-Q4); <200mm → scrap [3]
  - Same-type workpieces should be grouped consecutively to minimize switches [3]
- **Hierarchical objectives (lexicographic, per problem statement):**
  1. Primary: minimize total stock length (所选母材总长度尽可能小) [1][3]
  2. Secondary (Q2-Q4): maximize total co-cut benefit (总共切收益尽可能大) [3]
  3. Tertiary: minimize type-switch count (不同工件之间的切换次数尽可能少) [3]
- **Problem statement explicitly declares the hierarchy order** — this drives the solver's objective structure [3]

### 2. Subproblem Decomposition
Four sequential subproblems, each building on prior results [1][2][3]:

| Q | Description | Deliverable | Key features | Constraints |
|---|-------------|-------------|--------------|-------------|
| Q1 | Axial-only cutting stock: 50 each × 10 types = 500 items, any combo of 4 stock types, no co-cut | result1.xlsx | 1D bin packing, stock selection, workpiece ordering per stock | Min stock length, min switches |
| Q2 | Fixed Q1 bin assignment; reorder within each stock + co-cut splice | result2.xlsx | Co-cut benefit matrix pre-computed; internal splice (same-type) + block-between splice (different-type); 4 splice modes LL/LR/RL/RR | Stock length fixed from Q1; maximize co-cut benefit, min switches |
| Q3 | Full re-pack with co-cut optimization + remnant ≥200mm rule | result3.xlsx | Joint assignment + block formation + ordering + splice mode selection; remnant inventory introduced | Min stock length, max co-cut benefit, min switches; remnant ≥200mm reusable |
| Q4 | 3 consecutive batches B1(468) → B2(433) → B3(427); remnant carryover between batches; 1328 total items | result4.xlsx | Multi-period inventory; remnant priority use; batch-sequential optimization | Remnant from prior batch available as "free bins"; min new stock purchased across all 3 batches |

**Q2 dependency:** Q2 fixes the bin assignment from Q1 — it only reorders within each stock. This is a sub-problem of Q3 which jointly optimizes both assignment and ordering [3].

**Q3 → Q4 escalation:** Q3 introduces the remnant rule; Q4 extends it across multiple periods/batches with demand variation [3].

### 3. Data Assets
All assets in `inbox/b-tube-live-once/assets/` [2]:

| Asset class | Count | Path pattern | Role | Verification |
|-------------|-------|-------------|------|--------------|
| Problem PDF | 1 | inbox/b-tube-live-once/problem.pdf | Source document, 3 pages, sha256 confirmed | sha256=9eaa64beb2922ebf6e5f8032e9a5ba84ae462fee0ab80a141393740bc50209ec [3][4] |
| CSV point clouds | 10 | assets/B题 附件/B题 数据/附件1_10种工件/圆管{1..10}.csv | Geometry: X,Y,Z coordinates; 684-2020 points each [12] | On disk, readable |
| STP CAD files | 10 | assets/B题 附件/B题 数据/附件1_10种工件/{1..10}圆管.stp | Reference geometry: STEP format for precise cross-section [14] | On disk |
| Demand xlsx | 1 | assets/B题 附件/B题 数据/附件2_三批次工件需求数据.xlsx | Q4 batch demand table [16] | On disk |
| Result templates | 4 | assets/B题 附件/B题 结果/result{1..4}.xlsx | Excel output templates [15] | On disk |
| Format spec | 1 | assets/B题 附件/B题 结果/结果填写说明.docx | Result format documentation [15] | On disk |

**OCR artifacts:** `notes/live-btube-ocr.raw.md` (extracted text), `notes/live-btube-ocr.meta.json` (metadata) [3][4].

**Intake artifacts:** `outputs/live-btube-intake.json` (structured schema v1.1.0, sha256 gate passed) [2].

### 4. Geometry & Axial Lengths
**Method:** PCA on XYZ point cloud from CSV files [9][13]:
1. Center the point cloud (subtract mean)
2. Compute covariance matrix; eigenvalues/eigenvectors
3. First principal component = axial direction
4. Project all points onto PCA axis → min and max = axial bounds
5. Axial length = max − min (mm)

**L/R end classification** [9]:
- Extract points in end-zone neighborhoods (near axial min and max)
- Compute r_mean = average radial distance from PCA axis in each end zone
- L end: smaller r_mean (narrower end)
- R end: larger r_mean (wider end)
- Symmetric (L=R): when |r_mean_left − r_mean_right| < 0.01mm — applies to types G5, G6, G7, G8, G9 [9]

**Approximate PCA axial lengths (mm)** [13] — ALL values must be recomputed by modeler scripts:

| Type | Axial length (mm) | L/R classification | Notes |
|------|-------------------|--------------------|-------|
| 1 | ~191.8 | asymmetric (L≠R) | |
| 2 | ~150 (estimated) | asymmetric (L≠R) | |
| 3 | ~190 (estimated) | asymmetric (L≠R) | |
| 4 | ~190 (estimated) | asymmetric (L≠R) | |
| 5 | 75.0 | symmetric (L≈R) | |
| 6 | ~150 (estimated) | symmetric (L≈R) | |
| 7 | ~250 (estimated) | symmetric (L≈R) | |
| 8 | 399.9 | symmetric (L≈R) | longest workpiece |
| 9 | ~180 (estimated) | symmetric (L≈R) | |
| 10 | ~200.6 | asymmetric (L≠R) | |

**Critical caveats** [13]:
- Values marked "estimated" are approximate; exact PCA computation must run on the actual CSV data
- PCA axis sign may be flipped — the axial length (span) is invariant, but L/R classification depends on sign convention
- Consistency of L/R classification across all 10 types must be verified

### 5. Demand Analysis
**Q1-Q3:** 50 pieces each of all 10 types = 500 total pieces per question [1][3].

**Q4 batch demands (3 consecutive batches)** [10][16]:

| Type | B1 | B2 | B3 | Per-type total |
|------|-----|-----|-----|----------------|
| 工件1 | 52 | 46 | 44 | 142 |
| 工件2 | 31 | 28 | 27 | 86 |
| 工件3 | 43 | 40 | 36 | 119 |
| 工件4 | 39 | 35 | 34 | 108 |
| 工件5 | 58 | 57 | 60 | 175 |
| 工件6 | 55 | 50 | 56 | 161 |
| 工件7 | 57 | 51 | 49 | 157 |
| 工件8 | 41 | 37 | 39 | 117 |
| 工件9 | 45 | 44 | 42 | 131 |
| 工件10 | 47 | 45 | 40 | 132 |
| **Batch total** | **468** | **433** | **427** | **1328** |

- Per-type per-batch range: 27 (工件2/B3) to 60 (工件5/B3)
- Grand total across all 3 batches: 1328 pieces
- Demand varies non-trivially across batches — affects remnant planning

### 6. Co-cut Model
From prior research model [9] — **NOT authoritative, context-only.** The live run must validate or replace this model.

**Core concept:** When two tube workpieces are placed end-to-end on the same stock, if their mating end cross-sections have similar radii, the combined axial length is less than the sum of individual lengths (the "overlap" or co-cut benefit).

**4 splice modes** [9]:
- **LL:** Left end of workpiece i mates with Left end of workpiece j
- **LR:** Left end of workpiece i mates with Right end of workpiece j
- **RL:** Right end of workpiece i mates with Left end of workpiece j
- **RR:** Right end of workpiece i mates with Right end of workpiece j

**Benefit formula (simplified)** [9]:
```
Δ_ij^ab = l_i + l_j − L_ij^ab
≈ |r_end_i^a − r_end_j^b|
```
Where `l_i` = axial length of workpiece i, `L_ij^ab` = minimum axial length when spliced in mode ab, `r_end_i^a` = r_mean at end a of workpiece i.

**Internal splice (same type within a block)** [9][11]:
- For block Gk×n: (n−1) internal joints
- LR alternating maximizes benefit (L→R→L→R→…)
- Internal splice benefit per joint = |r_L − r_R| of the same type
- Internal splice does NOT count as a type switch

**Block-between splice (different type blocks)** [9][11]:
- Between adjacent blocks G_i×n_i and G_j×n_j
- Try all 4 modes {LL, LR, RL, RR}; select max benefit
- Counts as 1 type switch

**Symmetric types (G5, G6, G7, G8, G9)** [9]:
- L≈R → r_mean_low ≈ r_mean_high → co-cut benefit ≈ 0 for ALL splice modes
- Internal splice LR alternating yields ~0 benefit
- Simplifies the optimization for these types

**Effective axial consumption** [9]:
```
Effective_length = Σ[n_i × l_i] − Σ[(n_i−1) × internal_benefit_i] − Σ[between_benefit_{i,j}]
```

**Caveats (from prior model)** [9]:
1. Assumes end cross-section ~circular (outer radius 20mm); ignores wall thickness (1mm)
2. Simplified to radial difference |r_i − r_j|; ignores end-face bevel angle and full cross-section profile
3. Internal splice only considers LR alternating — other patterns not explored
4. Model is a feasible heuristic, NOT proven optimal for co-cut benefit

### 7. Result Format
From result templates and format specification [11][15]:

**Stock sheet (下料方案)** — one row per stock:

| Column | Description |
|--------|-------------|
| M_ID | Stock identifier (M1, M2, M3, …) |
| 母材长度(mm) | Stock original length |
| 工件块序列 | Block sequence, e.g., G1×6\|G3×4\|G8×2\|G2×1 |
| 轴向占用总长度(mm) | Total axial length consumed (after co-cut deductions) |
| 剩余长度(mm) | Remnant length |
| 母材利用率 | Utilization ratio |

**Splice summary (拼接方式摘要表)** — per stock:

| Column | Description |
|--------|-------------|
| M_ID | Stock identifier |
| 拼接类型 | "internal" (内部拼接) or "block-between" (块间拼接) |
| 前工件块 / 后工件块 | Adjacent block IDs (same block ID for internal) |
| 拼接方式 | LL, LR, RL, or RR |
| 拼接次数 | Count of this splice type occurrence |
| 单次共切收益(mm) | Benefit per splice |
| 共切收益小计(mm) | Subtotal benefit (= count × per-benefit) |

**Conventions** [11]:
- **Block:** `Gk×n` = n consecutive same-type k workpieces forming one block
- **Internal splice count:** (n−1) per block
- **Block-between splice count:** 1 per adjacent block pair
- **Utilization (Q1, no co-cut):** Σ(axial_i × count_i) / Σ stock_lengths
- **Utilization (Q2-Q4, with co-cut):** [Σ(axial_i × count_i) − total_co_cut_benefit] / Σ stock_lengths
- **Units:** mm, results to thousandths (千分位)
- **IDs:** Batch B1/B2/B3; Stock M1/M2/…; Remnant R1/R2/…

### 8. Solver Stack
Current solver stack from `docs/solver-stack.md` [6]:

| Layer | Engine | Problem class | Exact? | Role for this problem |
|-------|--------|--------------|--------|----------------------|
| L0 | Fixture mock | All | — | CI/gate; fixture not available on disk |
| L1 | NetworkX Dijkstra | shortest_path | Yes (P) | Not applicable |
| L2 | CP-SAT | Discrete combinatorial (TSP ≤20) | Yes (proven) | **Recommended** — bin-packing + ordering formulation |
| L3 | HiGHS | MIP (TSP/small VRP) | Yes (exact MIP) | **Alternative** — column generation or compact MIP |
| L4 | OR-Tools Routing | TSP/CVRP | No (metaheuristic) | Not suitable for cutting stock |
| L5 | VROOM | Real-road VRP | No | Not applicable |
| L6 | Gurobi/Hexaly | Academic benchmark | Yes | License-gated; not default |

**Gap** [5][6]: No dedicated `cutting_stock` problem class or solver in the stack or seed graph. The cutting stock problem must be adapted to:
- **CP-SAT (L2, recommended):** Bin-packing formulation with item-to-bin assignment variables. Can prove optimality for discrete formulations. Scales to ~500 items with careful modeling. Multi-objective lexicographic optimization feasible via sequential solves or weighted objectives.
- **HiGHS (L3, alternative):** MIP with compact formulation or column generation. Open-source exact MIP. Potentially better for continuous stock lengths, but 4 discrete stock types make CP-SAT equally suitable.

**Co-cut pre-processing** is NOT a solver step — it is a geometry computation feeding the solver:
1. Read CSV point clouds → PCA → axial lengths + L/R classification
2. Compute 10×10×4 co-cut benefit matrix Δ_ij^ab
3. Feed matrix as parameters into CP-SAT/HiGHS model

### 9. Existing Research Context (NOT AUTHORITATIVE)
The prior run `b-tube-cut-2026` produced solver-owned headline numbers [8]. These are **context references only** — the live run must produce its own fresh solutions via solve tools + validation.

Prior run numbers (from `notes/b-tube-cut-2026-research.md`, DO NOT USE as targets): Q1 total stock ≈ 100000 mm, Q2 co-cut benefit ≈ 649.29 mm, Q3 total stock ≈ 100000 mm, Q4 new stock ≈ 260000 mm. These values are from `chunk_id: tube-cut-seed-axial` and are NOT verified against the current intake data. The live run must compute independent solutions.

The co-cut model [9], PCA axial lengths [13], and result format [11] from the prior run are informative but must be validated or recomputed against the actual CSV/STP data in the current inbox.

## Solver recommendation
- **default_mode:** `cpsat`
- **exact?:** yes — CP-SAT can prove optimality for discrete bin-packing formulations at this scale
- **rationale:**
  - **Q1:** Classic 1D cutting stock with 4 discrete bin capacities (9000/10000/11000/12000 mm) and ~500 items. CP-SAT bin-packing formulation: for each item i, assign to a bin b; constraint Σ l_i ≤ t_b per bin; objective minimize Σ t_b for used bins. Discrete capacities align with CP-SAT's integer variable strengths.
  - **Q2:** Fixed Q1 assignment → per-bin reorder. Small TSP-like ordering problem per bin. CP-SAT with circuit constraints or direct enumeration (few blocks per bin). Co-cut benefit matrix pre-computed.
  - **Q3:** Joint assignment + block formation + ordering + splice mode selection. Significantly larger CP-SAT model with both assignment and ordering variables. May require decomposition: iterative assignment → ordering, or column generation approach.
  - **Q4:** Multi-period extension with remnant inventory state variables. Remnant ≥200mm creates "free bins" in subsequent batches. Sequential batch processing with inventory carryover. CP-SAT iterated per batch with state transfer.
  - CP-SAT aligns with solver-stack L2 for discrete OR [6]. "Proven optimal" narrative works for cutting stock at this scale.
- **fallback:** HiGHS MIP (L3) if CP-SAT doesn't scale or if a continuous formulation proves advantageous
- **NOT suitable:** OR-Tools Routing (L4) — routing solvers are designed for vehicle routing, not bin packing
- **pre-solve step (geometry):** Custom Python script to compute PCA axial lengths + L/R end classification + 10×10×4 co-cut benefit matrix from CSV point clouds. This is a pure geometry computation, not a solve step.

## Modeling recommendations
For modeler only — no solution values.

### Pre-processing: Geometry
1. For each of 10 CSV files (`圆管1.csv` … `圆管10.csv`):
   - Read X, Y, Z points (numpy)
   - Center the data; compute PCA via `numpy.linalg.eigh` on covariance matrix
   - Retain first principal component as axial direction
   - Project all points onto PCA axis → min/max = axial bounds
   - Axial length = max − min (mm, to at least 3 decimal places)
   - Extract points in end-zone neighborhoods (e.g., |z_proj − z_min| < ε, |z_proj − z_max| < ε where ε ≈ 2mm)
   - Compute r_mean = average distance from PCA axis in each end zone
   - Classify L/R: smaller r_mean → L end; larger r_mean → R end
   - If |r_mean_left − r_mean_right| < 0.01mm → mark as L=R (symmetric)
   - Verify sign consistency across all 10 types

### Pre-processing: Co-cut Benefit Matrix
2. For each ordered pair (i, j) in 1..10 and each splice mode m in {LL, LR, RL, RR}:
   - Determine end of i and end of j from mode: e.g., LR → L end of i, R end of j
   - Compute benefit Δ[i][j][m] = |r\_end\_i − r\_end\_j|
   - Store in 10×10×4 matrix (or flattened index)
   - For symmetric types (L=R, types 5-9): all Δ ≈ 0

### Q1 Model: 1D Cutting Stock (No Co-cut)
3. **Decision variables (CP-SAT):**
   - `x[i][b]` ∈ {0,1}: workpiece i (of type t_i) assigned to bin b
   - `y[b]` ∈ {0,1}: bin b is used
   - `stock_type[b]` ∈ {9000, 10000, 11000, 12000}: stock type of bin b (or model as integer variable constrained to these 4 values)
   - `switch[b][k]` ∈ ℤ₊: count of type-switches on bin b

4. **Constraints:**
   - `Σ_b x[i][b] = demand[t_i]` for each type → every item assigned exactly once
   - `Σ_i x[i][b] × l[t_i] ≤ stock_type[b]` for each bin b → capacity constraint
   - `x[i][b] ≤ y[b]` for each bin b → bin active if any item present
   - Switch counting: consecutive different types per bin (formulate with ordering variable or proxy)

5. **Objective (lexicographic):**
   - Primary (M1 >> M2): minimize `Σ_b y[b] × stock_type[b]`
   - Secondary: minimize `Σ_b switch[b]` (total type-switch count)

### Q2 Model: Fixed Assignment, Reorder + Co-cut
6. **Pre-compute per-bin blocks:**
   - Input: Q1 assignment → group items by type within each bin → blocks
   - Block `(k, n)`: type k, count n, internal benefit = (n−1) × |r_L_k − r_R_k|

7. **Per-bin ordering (small TSP):**
   - Blocks as nodes; between-splice benefit as edge weights
   - Objective: maximize total co-cut benefit = Σ internal + Σ between
   - Can enumerate all permutations if blocks ≤ 6-7; otherwise CP-SAT with circuit constraints

### Q3 Model: Joint Optimization
8. **Joint variables:**
   - Item-to-bin assignment + bin stock type (from Q1)
   - Block formation within each bin (group same-type items)
   - Block ordering + between-splice mode selection (from Q2)
   - Remnant computation: `remnant[b] = stock_type[b] − effective_length[b]`

9. **Constraints:**
   - Q1 constraints plus Q2 ordering variables
   - `remnant[b] ≥ 200` OR `remnant[b] < 200` → bifurcation

10. **Decomposition strategy (if full joint model too large):**
    - Iterative: assign items → form blocks → order blocks → adjust assignment → repeat
    - Or: column generation with pricing problem for co-cut-aware patterns

### Q4 Model: Multi-batch with Remnant
11. **Sequential batch processing:**
    - Batch 1: Solve Q3-style with fresh stock only
    - Compute remnants per stock; remnants ≥200mm → inventory
    - Batch 2: Add inventory bins (fixed remaining lengths, cost = 0) to bin pool; solve Q3-style
    - Batch 3: Same with batch 2 remnants

12. **Remnant priority rule:**
    - "优先被使用" → inventory bins enter the model with zero cost (cost_weight = 0)
    - New stock bins carry positive cost
    - Objective: minimize Σ new_stock_length → naturally uses remnants first

13. **Global objective:** Σ new stock purchased across all 3 batches

### Objective Weighting
14. **Lexicographic approach (matches problem statement):**
    - Stage 1: minimize stock length
    - Stage 2: with stock length fixed, maximize co-cut benefit
    - Stage 3: with stock length and co-cut fixed, minimize switch count
    - Implement via sequential CP-SAT solves with constraints from prior stages
15. **Weighted alternative (if single solve needed):**
    - `M1 × Σ stock_lengths − M2 × total_co_cut_benefit + M3 × switch_count`
    - `M1 >> M2 >> M3`; e.g., M1=10^6, M2=10^3, M3=1
    - Lexicographic is preferred for correctness; weighted is a practical fallback

## Open questions
1. **Co-cut precision:** The simplified `|r_i − r_j|` radial-difference model assumes end cross-sections are approximately circular (outer radius 20mm). Should the modeler parse STP CAD files for precise end cross-section profile matching, or is the CSV point cloud r_mean sufficient? The answer affects pre-processing complexity.

2. **Q4 remnant strategy semantics:** "优先被使用" — does this mean remnants MUST be consumed before purchasing new stock (hard constraint), or are they PREFERRED (soft objective)? A hard constraint could force suboptimal solutions if remnants have awkward lengths.

3. **Switch count definition:** Does switching from G1→G3→G1 within one stock count as 2 switches? Are switches counted per stock or globally? Do same-type blocks on different stocks count as switches when comparing across stocks? The problem says 不同工件之间的切换次数 — implies per-stock count within a bin's sequence.

4. **CP-SAT scalability for Q3/Q4:** 500 items × 4 stock types with co-cut matrix and ordering variables could produce a model with O(10^5) variables. A decomposition strategy (assignment → ordering) may be necessary. The modeler must assess CP-SAT performance boundaries.

5. **PCA axis direction and L/R consistency:** The PCA first component sign can flip arbitrarily. While axial length (span) is invariant, L/R classification depends on sign convention. The geometric pre-processing script must enforce a consistent sign convention (e.g., "L = narrower end") across all 10 types.

6. **Fixture directory:** `fixtures/t3/tube_cut_b2026/` is referenced but not present on disk. Validation gating against fixture data is unavailable.

7. **Result template fidelity:** The modeler/solver must produce output matching the exact format in `结果填写说明.docx` [15]. The result format specification in evidence [11] is informative but the `.docx` document is the authoritative format source.

8. **Co-cut model validation:** The prior co-cut model [9] is a heuristic. The live run should either validate it against STP cross-section geometry or adopt a more rigorous model if the simplified radial-difference approach introduces significant error.

9. **Symmetric type handling (G5-G9):** Types 5-9 have L≈R → co-cut benefit ≈ 0 for all splice modes. Internal splice (LR) yields ~0 benefit; block-between splice also ~0. This simplifies the optimization for these types but the model must explicitly handle the edge case to avoid solver errors.

10. **Q2 independence:** Q2 fixes Q1's bin assignment. If Q1's solution is suboptimal, Q2 inherits that suboptimality. The modeler should document this dependency and note that only Q3 can recover globally.

