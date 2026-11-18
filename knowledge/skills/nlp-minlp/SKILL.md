---
name: nlp-minlp
description: Non-convex continuous NLP and mixed-integer MINLP paradigm using tools/or_kernels/nlp_minlp.py (LHS global sweep + Differential Evolution / Dual Annealing + SLSQP/L-BFGS-B local polish + discrete decomposition).
---
# Non-Convex NLP & MINLP Modeling Skill

1. **Exact Kernel Signatures (`tools.or_kernels.nlp_minlp` & `tools.or_kernels.envelope_io`)**:
   - `solve_box_nlp(objective_fn, bounds, *, maximize=False, constraints=(), n_lhs=96, global_method='de', popsize=12, maxiter=120, n_local_starts=5, time_limit_s=60.0, seed=42, initial_points=(), penalty_weight=10000.0) -> dict` — returns keys `{'x', 'objective', 'feasible', 'ok', 'proven_optimal', 'wall_time_s', 'n_evals'}` (`constraints` follow `g(x) <= 0` convention!). Note: key is `'objective'`, NOT `'fun'`.
   - `solve_minlp_decomposed(discrete_candidates, build_subproblem_fn, *, maximize=False, time_limit_s=120.0, seed=42, n_lhs_per_candidate=48, maxiter_per_candidate=80) -> dict`
   - `from tools.or_kernels.envelope_io import build_custom_envelope, write_solution_and_report`:
     `env = build_custom_envelope(problem_id=..., slug=..., problem_class=..., objective=..., solver_name=..., source_script=..., validator_script=..., validation_report=f"outputs/{slug}-custom-validate.json", decision_payload=..., proven_optimal=False, wall_time_s=0.0)`
     `write_solution_and_report(f"outputs/{slug}-solution.json", env)`
     CRITICAL: `build_custom_envelope` ONLY returns a `dict` (it does NOT write to disk!); you MUST call `write_solution_and_report(...)` to save `solution.json`, MUST pass non-empty `validation_report` (NEVER `""`), and note the saved JSON puts `decision_payload` under top-level key **`"solution"`** (NOT `"decision_payload"`!).
2. **Global + Local Hybrid & Time Guard**: Always pass explicit `time_limit_s` per subproblem (summing safely below the round script timeout) so scripts finish fast cleanly instead of hanging.
3. **Continuous/Discrete Decoupling (Round 3+ Playbook)**: Separate discrete assignment / timing-order / active-unit binaries from continuous kinematic/trajectory parameters (`[theta, v, t_drop, tau]`), or optimize per-unit parameters first before joint refinement.
4. **Independent Verification (Numbers Truth)**: `outputs/<slug>-custom-validate.py` must NEVER import `scipy.optimize`, `ortools`, `nlp_minlp`, or `custom_solver` (pure `numpy` / `math` / `tools.or_kernels.interval_coverage` are AST-whitelisted). It must run with ZERO CLI arguments (reading `outputs/<slug>-solution.json`, extracting `pl = env.get("solution") or {}`) and write `outputs/<slug>-custom-validate.json` (`{"ok": bool, "objective": float, "checks": [...]}`).
