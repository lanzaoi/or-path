# OR Reduction & Custom Modeling Playbook

> Do NOT let the 22 built-in canonical labels act as a cage. Use the 27 registered solvers as **building blocks and mathematical reductions**, or synthesize a custom Python solver + physically isolated validator.

---

## Decision Flow for Arbitrary OR Problems

1. **Inspect all problem & data files first**:
   Use `list_files`, `read_file`, and `read_problem_file` on `inbox/<slug>/` and `outputs/<slug>-profile.json`. Never assume file structure without reading.
2. **Check if the problem reduces mathematically to a registered solver (`list_available_solvers`)**:
   - **Multi-depot / pickup-delivery / open VRP / prize-collecting routing** -> reduce via dummy depot, big-M arcs, or PyVRP variant (`solve_pyvrp.py` / `solve_ortools.py`).
   - **Sequence-dependent setup scheduling / parallel machines / flow shop** -> reduce to FJSSP/JSSP (`solve_jssp.py`) or cumulative CP-SAT (`solve_rcpsp.py`).
   - **Assignment / bipartite matching / max-flow / min-cost transport / transshipment** -> reduce to `network_flow` (`solve_network_flow.py`).
   - **Budgeted selection / multi-dimensional knapsack / 1D cutting** -> reduce to `bin_packing` (`solve_binpack.py`) or `lot_sizing` (`solve_lotsizing.py`).
   - **Multi-objective optimization (weighted-sum / ε-constraint)** -> sweep scalarized subproblems using exact LP/MILP (`highspy` / `scipy.optimize.milp`).
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
   - **Solver (`outputs/<slug>-custom_solver.py`)**:
     - Continuous LP / mixed-integer linear programs: `scipy.optimize.milp` or `highspy` (preserves floating-point precision).
     - Combinatorial / scheduling / logical constraints (`all_different`, cumulative, no-overlap): `ortools.sat.python.cp_model`.
     - Nonlinear / convex continuous optimization: `scipy.optimize.minimize` (SLSQP / trust-constr, report `proven_optimal=False` & `status="FEASIBLE"` if non-convex).
     - Network graphs: `networkx`.
   - **Validator (`outputs/<slug>-custom-validate.py`) — Numbers Truth 2.0 Rules**:
     1. **Physically isolated**: NEVER import `*custom_solver*`, `ortools`, `highspy`, `pulp`, `gurobipy`, `pyvrp`, `alns`, `dimod`, or `scipy.optimize.milp`.
     2. Read raw problem data (`inbox/<slug>/...` or `outputs/<slug>-instance.json`) + `outputs/<slug>-solution.json` directly from disk.
     3. Recompute the objective and every constraint residual from raw mathematical formulas using Python / `math` / `numpy`.
     4. Persist `outputs/<slug>-custom-validate.json` containing `{"ok": bool, "objective": declared_obj, "recomputed_objective": recomputed_obj, "checks": [...]}`.
   - **Envelope & Optimality Honesty**:
     In `outputs/<slug>-solution.json`, declare:
     - `"problem_id"`, `"slug"`, `"problem_class": "custom_mip"`, `"status": "OPTIMAL" | "FEASIBLE"`, `"objective"`, `"solver"`, `"source"`
     - `"values": { ... }`
     - `"validation_report": "outputs/<slug>-custom-validate.json"`
     - `"validator_script": "outputs/<slug>-custom-validate.py"`
     - `"meta": {"exact": bool, "proven_optimal": bool, "method_class": "exact" | "heuristic"}`
     Set `status="FEASIBLE"` whenever `proven_optimal=False`.
