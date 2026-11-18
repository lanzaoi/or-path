---
name: experimental-design
description: Design of experiments (DOE), Latin Hypercube / Sobol / Halton space-filling sampling, multi-factor sensitivity sweeps, and blocking matrices using OR-Path installed packages (`scipy.stats.qmc`, `itertools`, `numpy`, `pandas`).
---
# Experimental Design & Sensitivity Sweeps

Tailored to OR-Path's installed stack (`scipy.stats.qmc`, `scipy.stats`, `numpy`, `pandas` — **do NOT import uninstalled `pydoe` / `pyDOE3`**).

1. **Continuous Parameter & Simulation Space Filling (QMC)**:
   - Use `scipy.stats.qmc.LatinHypercube(d=..., seed=42)` or `Sobol(d=..., scramble=True, seed=42)` with `.random(n)` and `qmc.scale(samples, l_bounds, u_bounds)` for multi-start global optimization seeds, black-box surrogate sweeps, and multi-parameter sensitivity grids.
   - Prefer QMC space-filling over naive uniform i.i.d. sampling when evaluating expensive simulation/ODE/MILP objectives across `[l_bounds, u_bounds]`.
2. **Factorial & Sensitivity Analysis Design**:
   - **Full / fractional factorials**: construct coded `{-1, +1}` or `{low, mid, high}` matrices via `itertools.product` or `np.meshgrid` so main effects and pairwise interactions are orthogonal and identifiable.
   - **Blocking & replication**: vary one nuisance block/seed factor systematically alongside core policy parameters; never confound solver hyperparameter changes with instance changes across comparison runs.
3. **Numbers Truth Alignment**:
   - Every sensitivity point `(param_vector -> objective, feasible)` reported in `outputs/` and Paper Ch. 5 must come directly from solving + independently validating each DOE point with identical discretization (`dt`) and fixed `seed`.
