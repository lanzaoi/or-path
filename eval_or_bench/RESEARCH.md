# OR-Path Benchmark Research & Selection Report (M1)

**Milestone:** M1 (R1: Deep Research & Benchmark Selection)  
**Author:** M1 Worker 1  
**Date:** 2026-08-10  
**Target Path:** `eval_or_bench/RESEARCH.md`  

---

## 1. Executive Summary & Objectives

This document establishes the official benchmark evaluation research, public suite analysis, instance selection strategy, schema mapping rules, distance metric formulations, risk mitigations, and out-of-scope boundaries for the OR-Path evaluation framework (`eval_or_bench/`).

OR-Path evaluates combinatorial optimization problems through a deterministic multi-stage pipeline:
$$\text{Problem Intake} \longrightarrow \text{ProblemSchema Validation} \longrightarrow \text{solve\_dispatch} \longrightarrow \text{solve\_envelope} \longrightarrow \text{validate\_solution}$$

To ensure absolute adherence to **"Numbers Truth"** (where reported objectives derive exclusively from independent deterministic recomputation rather than unverified prose claims), this report:
1. Conducts a comparative evaluation of five major public benchmark suites (TSPLIB, CVRPLIB, Solomon VRPTW, OR-Library, MIPLIB) against OR-Path repository capabilities.
2. Selects a canonical suite of 8 TSPLIB benchmark instances (`burma14`, `ulysses16`, `gr17`, `bayg29`, `swiss42`, `att48`, `eil51`, `kroA100`) covering dimensions $14 \le N \le 100$, multiple metric types (`EUC_2D`, `GEO`, `ATT`, `EXPLICIT`), and exact published mathematical optimal values backed by literature citations.
3. Formulates a strict 3-tier reference solution taxonomy (`optimal`, `bks`, `unknown`).
4. Specifies the lossless mapping protocol from standard `.tsp` formats to OR-Path `ProblemSchema` JSON specifications (`coords.json`, `distance_matrix.json`).
5. Details the exact mathematical distance metric rounding rules (`EUC_2D`, `GEO`, `ATT`, `EXPLICIT`) and establishes the mandatory architectural requirement that `distance_matrix.json` must be generated for all instances to prevent validation distance mismatch errors.
6. Analyzes key execution risks (indexing shifts, solver timeouts, metric rounding) and declares explicit out-of-scope boundaries.

---

## 2. Public Benchmark Suite Comparison Matrix

OR-Path natively registers five canonical problem classes in `orpath/domain_registry.py`: `shortest_path`, `tsp`, `vrp`, `tube_cut`, and `polyomino_cover`. The matrix below compares standard public benchmark libraries against these engine capabilities:

| Benchmark Suite | Primary Problem Domains | Fit with OR-Path Engine | Supported Solvers in OR-Path | Schema & Converter Compatibility | Recommendation & Rationale |
|---|---|---|---|---|---|
| **TSPLIB** | Symmetric TSP, Asymmetric TSP (ATSP), CVRP, Hamiltonian Cycle | **High / Full Alignment** (`tsp`, `vrp`) | `cpsat` (exact, small $N \le 20$), `highs` (MILP), `ortools` (routing/metaheuristics) | Direct mapping to `coords.json` and `distance_matrix.json` | **PRIMARY SELECTION (M1/M2).** Standardized `.tsp` format, mathematically proven optimal values, clean mapping into `tsp` domain schema. |
| **CVRPLIB** | Capacitated Vehicle Routing Problem (Augerat, Christofides, Golden) | **High Alignment** (`vrp`) | `ortools` (VRP routing engine with vehicle capacity checks) | Maps to `locations.json`, `demands`, `capacities`, `vehicle_count` | **SECONDARY CANDIDATE (M2 extension).** Ideal for testing multi-vehicle capacity constraints and fleet routing. |
| **Solomon VRPTW** | Vehicle Routing with Time Windows (56 instances: C1, C2, R1, R2, RC1, RC2) | **Partial Alignment** (`vrp` with time windows) | `validate_solution.py` has basic TW checks; `solve_ortools.py` requires TW adapter expansion | Maps to `locations.json` + `time_windows` / `service_times` | **FUTURE EXPANSION.** Requires extending solver builders in `solve_ortools.py` to handle window constraints natively. |
| **OR-Library (Beasley)** | Set Cover, Bin Packing, Job Shop, Knapsack, TSP | **Partial Alignment** (specific sub-domains) | `tube` (1D stock cut), `polyomino` (2D cover), `networkx`/`cpsat` (TSP) | Domain-specific schemas (`board.json` / stock item specs) | **SELECTIVE USE.** Supported sub-problems can be converted, but arbitrary OR-Lib LPs require dedicated domain schemas. |
| **MIPLIB (2017/2024)** | General Mixed Integer Linear Programming (`.mps` / `.lp`) | **Low / Out-of-Scope** (`status: "BLOCKED"`) | `highs` (generic LP/MILP solver) | Lacks domain `ProblemSchema`; violates structural domain invariants | **OUT OF SCOPE.** OR-Path requires domain-structured schema inputs rather than raw unstructured MILP constraint matrices. |

---

## 3. Selected TSPLIB Benchmark Suite

We select 8 canonical TSPLIB benchmark instances covering dimensions from $N = 14$ to $N = 100$, multiple distance metric formulations (`GEO`, `EXPLICIT`, `ATT`, `EUC_2D`), and varied coordinate/matrix representations. All 8 instances possess proven mathematical optimal values published in peer-reviewed literature:

| Instance Name | Dimension ($N$) | Metric Type | Published Optimal Value | Coordinate / Matrix Format | Literature Citation & Reference Source |
|---|---|---|---|---|---|
| **burma14** | 14 | `GEO` | **3323** | Geographical coordinates (Lat/Lon in Degrees.Minutes) | Reinelt, G. (1991). TSPLIB—A Traveling Salesman Problem Library. *ORSA Journal on Computing*, 3(4), 376-384. |
| **ulysses16** | 16 | `GEO` | **6859** | Geographical coordinates (Lat/Lon in Degrees.Minutes) | Grötschel, M., & Padberg, M. (1985). Polyhedral Theory. *The Traveling Salesman Problem*, 251-305; Reinelt (1991). |
| **gr17** | 17 | `EXPLICIT` | **2085** | Lower diagonal row matrix (`LOWER_DIAG_ROW`) | Grötschel, M. (1980). On the symmetric traveling salesman problem: Solution of a 120-city problem. *Mathematical Programming Study*, 12, 61-77. |
| **bayg29** | 29 | `EXPLICIT` | **1610** | Full distance matrix (`FULL_MATRIX`, Bavarian distances) | Reinelt, G. (1991). TSPLIB Repository, Heidelberg University. |
| **swiss42** | 42 | `EXPLICIT` | **1273** | Full distance matrix (`FULL_MATRIX`, Swiss city distances) | TSPLIB Benchmark Database, Heidelberg University (1991). |
| **att48** | 48 | `ATT` | **10628** | 2D coordinates (Pseudo-Euclidean metric) | Padberg, M., & Rinaldi, G. (1987). Optimization of a 532-city symmetric traveling salesman problem by branch-and-cut. *Operations Research Letters*, 6(1), 1-7. |
| **eil51** | 51 | `EUC_2D` | **426** | 2D Euclidean coordinates | Eilon, S., Watson-Gandy, C. D. T., & Christofides, N. (1971). *Distribution Management: Mathematical Modelling and Practical Analysis*. |
| **kroA100** | 100 | `EUC_2D` | **21282** | 2D Euclidean coordinates | Krolak, P., Felts, W., & Marble, G. (1971). A man-machine approach to the traveling salesman problem. *CACM*, 14(5), 327-334. |

---

## 4. Reference Solution Taxonomy

To prevent misrepresenting heuristic upper bounds as mathematical proofs, OR-Path strictly categorizes reference target values into three distinct taxonomy levels:

1. **`optimal`**:
   - **Definition**: Mathematically proven global optimal objective value. The upper bound equals the lower bound ($\text{gap} = 0.0\%$).
   - **Verification**: Sourced from exact branch-and-cut proofs (e.g. Concorde, complete enumeration with zero remaining gap).
   - **Applicability**: Assigned to all 8 selected TSPLIB instances (`burma14` through `kroA100`).
2. **`bks` (Best Known Solution)**:
   - **Definition**: Best upper bound established in peer-reviewed literature for instances where global optimality remains unproven.
   - **Verification**: Sourced from vetted benchmark leaderboards (e.g. CVRPLIB BKS repository).
   - **Applicability**: Used for massive instances ($N > 1000$) or hard open VRP problems where exact lower bounds lag behind heuristic solutions.
3. **`unknown`**:
   - **Definition**: Problem instances lacking published optimal values or literature-vetted BKS targets.
   - **Verification**: Evaluated strictly for structural feasibility (`validate_ok=true`) and recomputed objective self-consistency without optimality gap calculation.

---

## 5. Mapping Strategy: `.tsp` Format to OR-Path `ProblemSchema`

### 5.1 Input File Specification (`.tsp` Format)
TSPLIB `.tsp` files comprise header key-value metadata followed by raw data sections:
```text
NAME: burma14
TYPE: TSP
COMMENT: 14-city problem (GEO)
DIMENSION: 14
EDGE_WEIGHT_TYPE: GEO
NODE_COORD_SECTION
1 16.47 96.10
2 16.47 94.44
...
EOF
```

### 5.2 Target Fixture Structure
For each instance, `eval_or_bench/tsplib_converter.py` emits a clean directory under `eval_or_bench/instances/<instance_name>/`:
- `distance_matrix.json`: $N \times N$ matrix of integer/float pairwise distances. **Always generated** to preserve exact metric semantics.
- `coords.json`: Node coordinate definitions (emitted when coordinates exist in source `.tsp`).
- `whitelist_refs.json` (optional metadata): Reference solution target (`optimal_value`, `reference_type`, citation).

### 5.3 Node Indexing Normalization
- TSPLIB nodes are 1-indexed (`1`, `2`, ..., `N`).
- OR-Path solvers (`cpsat`, `ortools`, `highs`) and `validate_solution.py` expect 0-indexed string labels (`"0"`, `"1"`, ..., `"n-1"`).
- **Mapping Rule**: TSPLIB node ID $k \in \{1 \dots N\}$ maps to label `"k-1"`.
- When reporting tours, solver tour `["0", "3", "1", "0"]` maps back to 1-indexed IDs `[1, 4, 2, 1]` for external literature comparison.

### 5.4 Forbidden Key Compliance (`FORBIDDEN_SCHEMA_KEYS`)
To enforce input integrity, input fixture files (`coords.json`, `distance_matrix.json`) **must never contain** answer keys or hints. Specifically, the converter verifies that files contain zero occurrences of:
$$\text{FORBIDDEN\_SCHEMA\_KEYS} = \{\text{"objective"}, \text{"optimal"}, \text{"objective\_value"}, \text{"optima"}, \text{"optimal\_value"}, \text{"optimal\_cost"}, \text{"tour"}, \text{"routes"}, \text{"path"}\}$$

---

## 6. Distance Metric Formulas, Risks & Out-of-Scope Boundaries

### 6.1 Distance Metric Mathematical Definitions

TSPLIB defines distance calculation rules strictly by `EDGE_WEIGHT_TYPE`:

1. **`EUC_2D` (2D Euclidean Distance)**:
   $$\Delta x = x_i - x_j, \quad \Delta y = y_i - y_j$$
   $$d(i, j) = \text{int}(\text{round}(\sqrt{\Delta x^2 + \Delta y^2}))$$

2. **`GEO` (Geographical Distance)**:
   - Coordinates are given as `DDD.MM` (Degrees.Minutes).
   - Convert to radians:
     $$\text{deg} = \text{int}(x_i), \quad \text{min} = x_i - \text{deg}, \quad \text{rad}_i = \pi \cdot \frac{\text{deg} + \frac{5.0 \cdot \text{min}}{3.0}}{180.0}$$
   - Great-circle spherical distance ($R = 6378.388\text{ km}$):
     $$q_1 = \cos(\text{lon}_i - \text{lon}_j), \quad q_2 = \cos(\text{lat}_i - \text{lat}_j), \quad q_3 = \cos(\text{lat}_i + \text{lat}_j)$$
     $$d(i, j) = \text{int}\left(6378.388 \cdot \arccos\left(0.5 \cdot ((1.0 + q_1) \cdot q_2 - (1.0 - q_1) \cdot q_3)\right) + 1.0\right)$$

3. **`ATT` (Pseudo-Euclidean Distance)**:
   $$\Delta x = x_i - x_j, \quad \Delta y = y_i - y_j, \quad r_{ij} = \sqrt{\frac{\Delta x^2 + \Delta y^2}{10.0}}$$
   $$t_{ij} = \text{int}(\text{round}(r_{ij}))$$
   $$d(i, j) = \begin{cases} t_{ij} + 1 & \text{if } t_{ij} < r_{ij} \\ t_{ij} & \text{otherwise} \end{cases}$$

4. **`EXPLICIT` (Explicit Distance Matrix)**:
   Values read directly from `EDGE_WEIGHT_SECTION` per `EDGE_WEIGHT_FORMAT`:
   - `FULL_MATRIX`: $N \times N$ values.
   - `LOWER_DIAG_ROW`: Lower triangular row-by-row matrix including diagonal.
   - `UPPER_DIAG_ROW`: Upper triangular row-by-row matrix including diagonal.

### 6.2 Mandatory Architectural Safeguard
`tools/validate_solution.py` resolves problem distances by checking `distance_matrix.json` first before inspecting `coords.json`. If `distance_matrix.json` is missing, `validate_solution.py` falls back to standard Euclidean distance on coordinates, which produces invalid distances for `GEO` and `ATT` problems.
**Mandatory Rule**: `tsplib_converter.py` **must always generate `distance_matrix.json`** for every converted instance.

### 6.3 Risk Assessment & Mitigation Matrix

| Risk Factor | Root Cause | Impact | Mitigation Strategy |
|---|---|---|---|
| **Validation Mismatch on `GEO`/`ATT`** | Validator default fallback computes Euclidean distance on lat/lon coordinates | Validation failure (`recompute_objective` mismatch) | Always emit `distance_matrix.json` with exact TSPLIB pairwise distances |
| **Node Indexing Shift** | TSPLIB uses 1-indexed node numbers; Python solvers expect 0-indexed keys | Index errors or invalid tour sequence | Map node IDs to 0-indexed string labels `"0"`..`"n-1"` in output files |
| **Solver Timeout on Large $N$** | Exact CP-SAT scaling is exponential for $N > 25$ | Execution hangs or exceeds timeout limits | Dispatch instances with $N \ge 29$ (`att48`, `eil51`, `kroA100`) to `mode="ortools"` or apply strict time limits |
| **Floating Point Precision Inexactness** | Float accumulation differences across platforms | Objective differs by fractional amounts | Cast matrix entries to integer costs where TSPLIB specifies integer distances |

### 6.4 Out-of-Scope Boundaries
- **Unstructured MILPs**: General MIPLIB `.mps` files without domain-specific schema definitions are out-of-scope (`status: "BLOCKED"`).
- **Massive Scale Instances**: Benchmark instances with $N > 1000$ (e.g. `pla85900`) exceed standard gate execution budgets.
- **Stochastic / Dynamic Problems**: Real-time or uncertain demand VRP variants requiring dynamic online solvers.

---

## 7. Verification & Validation Contract

All converted instances under `eval_or_bench/instances/` must satisfy:
1. **Schema Integrity**: Validated against `ProblemSchema` in `tools/schema_models.py`.
2. **Forbidden Key Check**: Clean per `walk_forbidden_keys`.
3. **Validator Recomputation**: Solutions verified via `tools/validate_solution.py` returning `validate_ok=true`.
