---
name: uncertainty-and-units
description: Dimensional consistency checking, physical unit conversion hygiene, CODATA constants, uncertainty propagation, curve-fit covariance, and order-of-magnitude sanity checks using `scipy.constants`, `scipy.optimize`, and `numpy`.
---
# Uncertainty Propagation & Physical Units Hygiene

Adapted to OR-Path (`scipy.constants`, `scipy.optimize`, `numpy`, `math` — **do NOT import uninstalled `pint` or `uncertainties`**).

1. **Single-Boundary SI Conversion Law**:
   - Normalize ALL raw inputs to coherent SI (e.g. `m`, `s`, `kg`, `rad`, `W`, `J`, `kWh`) at load time and document every conversion factor explicitly (`mm -> 1e-3 m`, `deg -> np.deg2rad`, `km/h -> / 3.6`, `RMB/kWh` consistency). Never mix units inside inner solver loops.
   - Use exact physical constants from `scipy.constants` (CODATA) or explicitly declared scenario parameters (e.g. `g = 9.8` vs `g = scipy.constants.g`).
2. **Uncertainty & Sensitivity Propagation**:
   - **Linear (GUM / Jacobian)**: Given parameter covariance `Sigma` (e.g., `pcov` from `scipy.optimize.curve_fit(..., absolute_sigma=True)`), propagate output variance `sigma_y^2 = grad_f^T Sigma grad_f` via central finite differences rather than discarding off-diagonal parameter correlations!
   - **Nonlinear / constrained models (Monte Carlo)**: Propagate uncertainty via deterministic fixed-seed sampling (`rng = np.random.default_rng(seed)`) and verify convergence across sample sizes (`N` vs `2N`), reporting mean/median, IQR, and 95% quantile intervals (`[2.5%, 97.5%]`).
3. **Order-of-Magnitude & Physical Sanity Gates**:
   - Before trusting any numerical output, verify dimensionless ratios and hard conservation bounds (energy/mass balance, speed/Mach/Reynolds feasibility, SOC in `[0, 1]`, non-negative lengths/durations, angles/directions unit-normalized).
   - Never pass unverified unit-scaled numbers as exact physical optima in papers or solution envelopes.
