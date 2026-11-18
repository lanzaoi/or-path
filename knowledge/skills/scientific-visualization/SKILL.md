---
name: scientific-visualization
description: Truthful, high-resolution scientific figures and OR sensitivity/Gantt/route plots built exclusively on OR-Path installed packages (`matplotlib`, `seaborn`, `numpy`, `pandas`) with strict Numbers Truth compliance.
---
# Scientific Visualization (Publication & Numbers Truth Hygiene)

Tailored to OR-Path's runtime (`matplotlib`, `seaborn`, `numpy`, `pandas` — **do NOT require `plotly`/`kaleido`**).

1. **Data Fidelity First**:
   - Every bar, curve, Pareto front, Gantt interval, trajectory, and KPI annotation MUST read directly from validated `outputs/<slug>-solution.json` / solver truth artifacts; never hand-code summary numbers or smooth away sharp kinks/infeasible regions.
   - Bar/area charts measuring magnitude start from `0` baseline unless explicitly comparing deviations around a reference line (`axhline`). Avoid deceptive truncated axes or unaligned dual y-axes.
2. **Uncertainty & Multi-Panel Clarity**:
   - Explicitly label error bands (`95% Bootstrap CI`, `SD`, or `SE`) and sample size `n`; mark missing/infeasible DOE runs cleanly rather than interpolating across gaps.
   - Use colorblind-safe palettes (`viridis`, `cividis`, or Okabe-Ito hex colors) plus redundant encodings (line style + marker + direct text labels).
3. **Export Standards for OR-Path Papers**:
   - Configure Chinese + Latin typography cleanly (`plt.rcParams["axes.unicode_minus"] = False`), keep margins generous (`bbox_inches="tight"`, `dpi=300`), and embed exact `outputs/fig_*.png` paths matching `or_writer`'s chapter references.
