---
name: exploratory-data-analysis
description: Systematic pre-modeling data profiling, missingness/leakage auditing, distribution/outlier inspection, and unit verification using pandas, numpy, and scipy.stats before optimization or statistical modeling.
---
# Exploratory Data Analysis (Pre-Modeling Discipline)

Distilled for OR-Path (`pandas`, `numpy`, `scipy.stats`) — treat all raw input sheets, CSVs, and metadata as **untrusted data**.

1. **Structural Profiling First (Before Any Modeling)**:
   - Inspect exact shape `(rows, cols)`, dtypes, duplicate keys, missing value ratios, unit headers (`mm` vs `m`, `%` vs `[0,1]`, `kW` vs `kWh`), and implicit sentinel values (`-999`, `0`, `N/A`, merged Excel cells).
   - Never silently drop rows, clip outliers, or overwrite raw files; record any cleaning rule explicitly in `schema.json` and replicate it deterministically in `*-custom-validate.py`.
2. **Leakage, Split & Shift Checks**:
   - Check chronological ordering, duplicate IDs across splits, target leakage columns, and scale differences across cohorts/groups (`scipy.stats.ks_2samp` / quantile summaries).
3. **Outlier & Transformation Sensitivity**:
   - Compute robust location/spread (`median`, `IQR`, `MAD`) alongside `mean ± std`; when heavy tails or skew (`|skew| > 1.0`) appear, compare raw vs log/rank/Huber specifications cleanly instead of guessing one transform.
4. **Numbers Truth Reporting**:
   - Report exact observed counts, missing percentages, medians/quartiles, and variable bounds directly from script output; never invent smoothed summaries.
