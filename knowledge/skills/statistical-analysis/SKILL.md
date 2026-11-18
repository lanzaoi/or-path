---
name: statistical-analysis
description: Rigorous hypothesis testing, assumption diagnostics, effect sizes, correlation, and regression validation built exclusively on OR-Path installed packages (`scipy.stats`, `scikit-learn`, `numpy`, `pandas`).
---
# Statistical Analysis & Regression Validation

Tailored to OR-Path's runtime (`scipy.stats`, `sklearn`, `numpy`, `pandas` — **do NOT import uninstalled `pingouin` or `statsmodels`**).

1. **Test Selection Matrix**:
   - **Two independent groups**: check normality (`scipy.stats.shapiro` for `n <= 5000`) & variance homogeneity (`scipy.stats.levene`); use Welch t-test (`ttest_ind(..., equal_var=False)`) by default for continuous means, or Mann-Whitney U (`mannwhitneyu`) for skewed/ordinal rank questions.
   - **Paired / repeated within-unit**: `ttest_rel` on aligned differences, or `wilcoxon` signed-rank when symmetric non-normal differences apply.
   - **k >= 3 independent groups**: `f_oneway` (or Welch/Alexander-Govern `alexandergovern`), non-parametric `kruskal`, plus post-hoc Holm-adjusted pairwise tests (`scipy.stats.false_discovery_control` / Holm-Bonferroni).
   - **Contingency / association**: `chi2_contingency` (check expected cell counts >= 5, else `fisher_exact` for 2x2), linear `pearsonr` vs monotone rank `spearmanr` / `kendalltau`.
2. **Effect Sizes & Uncertainty alongside p-values**:
   - Never report bare p-values alone: always emit sample sizes `n`, group summaries, signed difference / Hedges' `g` / Cohen's `d` / `R^2` / Spearman `rho`, and 95% confidence interval (`scipy.stats.bootstrap` with fixed `rng = np.random.default_rng(42)`).
3. **Deterministic Validation Alignment**:
   - In data-fitting / forecasting / statistical evaluation tasks, fix `random_state` / `rng` seed in both solver and `*-custom-validate.py` so `recompute_objective` (`R^2`, RMSE, MAE, log-loss, test-stat) matches to `1e-6`.
