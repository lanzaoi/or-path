# OR Reduction & Custom Modeling Playbook

> Do NOT let the 27 built-in canonical labels act as a cage. Use the 27 registered solvers **and** `tools.or_kernels` as **composable mathematical reductions**: separate domain physics from combinatorial optimization instead of dumping high-dimensional coupled problems into blind metaheuristics.

---

## Physics-to-OR Three-Stage Reduction (For Hybrid / Geometric / Non-Convex Problems)

Whenever a problem combines **continuous physics/kinematics/PDEs/economics** with **discrete selection, multi-entity coupling, regime exclusivity, capacity, or multi-target coverage**, NEVER conclude "no solver applies -> pure black-box DE over 30+ variables". Always decompose into 3 clean stages:

### Stage 1: Forward Physics / Candidate Column Generation (Pure NumPy)
- Discretize candidate operating regimes per entity (e.g., candidate headings/speeds, machine modes, facility configurations, commitment schedules) and candidate discrete actions/events within each regime.
- Evaluate the non-convex/nonlinear physics **once per candidate** in vectorized NumPy, producing clean coverage intervals, discrete element sets, costs, or transition matrices.

### Stage 2: Exact Discrete OR Backbone (`tools.or_kernels` / Registered Solvers)
Hand the combinatorial skeleton to an exact industrial solver (milliseconds to seconds, with bounds):
- **Multi-Target Continuous Interval Union + One-of-Regime + Cooldown**:
  ```python
  from tools.or_kernels.lns_hybrid import select_max_union_subset
  res = select_max_union_subset(
      target_intervals_by_item={item_id: {target_id: [(s, e), ...]}},
      target_weights={target_id: 1.0},          # optional per-target weights
      regime_groups={carrier_id: {reg_id: (member_items, per_regime_cap)}},
      item_times={item_id: (carrier_id, release_time)},
      min_separation=1.0,                       # cooldown / separation within carrier
      max_items=total_cap,
      time_limit_s=15.0,
  )
  ```
- **Discrete Weighted Max-Coverage / Min-Cost Set Cover / Budgeted Selection**:
  ```python
  from tools.or_kernels.milp_reduction import solve_budgeted_coverage_milp
  res = solve_budgeted_coverage_milp(
      item_coverages={item_id: [elem1, elem2, ...]},
      universe_weights={elem: w},
      item_costs={item_id: c},
      max_items=k, budget=B, cover_all=False,
      regime_groups=regime_groups, conflicts=(),
  )
  ```
- **Capacitated Assignment / Matching**: `solve_assignment_milp(cost_matrix, row_caps=..., col_demands=..., conflicts=...)`
- **General LP / MILP (HiGHS)**: `solve_general_milp(c, A_ub=..., b_ub=..., A_eq=..., b_eq=..., bounds=..., integrality=..., maximize=...)`
- **Registered Domain Solvers**: `solve_network_flow.py`, `solve_facility.py`, `solve_jssp.py`, `solve_rcpsp.py`, `solve_pyvrp.py`, `solve_lot_sizing.py`, `solve_highs.py`.

### Stage 3: Low-Dimensional Continuous Local Polish
Fix the discrete skeleton (`selected`, `selected_regimes`) returned by Stage 2, and polish **only the surviving active continuous parameters** (or per-carrier subproblems):
- Use `tools.or_kernels.nlp_minlp.solve_multistart_polish(obj_fn, bounds, initial_points=[x_stage2], maximize=..., constraints=..., time_limit_s=10.0)`
- Or `solve_box_nlp(...)` on low-dimensional (<12D) active continuous subproblems (**Note**: inequality constraints MUST satisfy **`c(x) >= 0`** for feasibility, SciPy SLSQP convention!).

---

## Decision Flow for Arbitrary OR Problems

1. **Inspect all problem & data files first**:
   Use `read_problem_file` / `read_file` on `inbox/<slug>/` and `outputs/<slug>-profile.json`. Never assume file structure without reading.
2. **Check if the problem reduces mathematically to a registered solver (`list_available_solvers`)**:
   - **Multi-depot / pickup-delivery / open VRP / prize-collecting routing** -> reduce via dummy depot, big-M arcs, or PyVRP variant (`solve_pyvrp.py` / `solve_ortools.py`).
   - **Sequence-dependent setup scheduling / parallel machines / flow shop** -> reduce to FJSSP/JSSP (`solve_jssp.py`) or cumulative CP-SAT (`solve_rcpsp.py`).
   - **Assignment / bipartite matching / max-flow / min-cost transport / transshipment** -> reduce to `network_flow` (`solve_network_flow.py`) or `solve_assignment_milp`.
   - **Budgeted selection / multi-dimensional knapsack / 1D cutting** -> reduce to `bin_packing` (`solve_binpack.py`), `lot_sizing` (`solve_lotsizing.py`), or `solve_budgeted_coverage_milp`.
   - **Multi-objective optimization (weighted-sum / ε-constraint)** -> sweep scalarized subproblems using exact LP/MILP (`solve_general_milp`).
   - **Spatiotemporal / multi-agent / multi-mode coverage** -> 3-stage reduction via `select_max_union_subset(..., regime_groups=..., target_intervals_by_item=...)` + `solve_multistart_polish`.
3. **If reduced to a built-in solver (`problem_class: "custom_reduced"`)**:
   Write a clean adapter script and include `reduction_manifest` in `outputs/<slug>-solution.json`:
   ```json
   {
     "reduction_manifest": {
       "target_solver": "network_flow",
       "mapping_notes": "Transformed piecewise penalty cost into parallel arcs.",
       "recomputed_original_objective": 1245.5,
       "original_constraints": [
         {"id": "C1_demand", "ok": true, "residual": 0.0}
       ]
     }
   }
   ```
4. **Otherwise: Custom Python Solver + Physically Isolated Validator (`problem_class: "custom_mip"`)**:
   - **Validator (`outputs/<slug>-custom-validate.py`) — Numbers Truth 2.0 Rules**:
     1. **Physically isolated**: NEVER import `*custom_solver*`, `ortools`, `highspy`, `pulp`, `gurobipy`, `pyvrp`, `alns`, `dimod`, `scipy.optimize`, `nlp_minlp`, `lns_hybrid`, or `milp_reduction`.
     2. Read raw problem data + `outputs/<slug>-solution.json` (`pl = env.get("solution") or {}`) directly from disk with zero required CLI arguments.
     3. Recompute the objective and every constraint residual from raw mathematical formulas using Python / `math` / `numpy` / `tools.or_kernels.interval_coverage` with the **exact same discretization grid (`canonical_time_grid`) and seed** as the solver.
     4. Persist `outputs/<slug>-custom-validate.json` containing `{"ok": bool, "objective": declared_obj, "recomputed_objective": recomputed_obj, "checks": [...]}`.
   - **Envelope & Optimality Honesty**:
     Use `tools.or_kernels.envelope_io.build_custom_envelope` + `write_solution_and_report`. Set `status="FEASIBLE"` and `proven_optimal=False` whenever any heuristic, discretization, or time-limited truncation is involved.
