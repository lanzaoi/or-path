"""Reusable Python OR mathematical-paradigm kernels (`tools/or_kernels/`).

Provides modular, solver-agnostic building blocks imported by custom sandbox
solvers (``outputs/<slug>-custom_solver.py``) and registered tools:

- ``milp_reduction``: Exact HiGHS LP/MILP wrapper, budgeted weighted set-cover /
  max-coverage with One-of-Regime exclusivity, and capacitated assignment.
- ``lns_hybrid``: Multi-axis weighted interval-union assignment with One-of-Regime
  & cooldown separation via CP-SAT, plus generic Large Neighborhood Search.
- ``nlp_minlp``: Box/constrained non-convex NLP (LHS + DE / Dual Annealing +
  SLSQP/L-BFGS-B), Stage-3 multi-start local polish, and decomposed MINLP.
- ``interval_coverage``: Pure NumPy/math interval union measure, vectorized 3D
  line-of-sight segment-to-sphere occlusion, and multi-agent coverage evaluator
  (zero optimizer imports — safe for independent validators).
- ``envelope_io``: Standard Numbers-Truth compliant envelope & report writers.
"""
from __future__ import annotations

from tools.or_kernels.envelope_io import (
    build_custom_envelope,
    write_solution_and_report,
)
from tools.or_kernels.interval_coverage import (
    contiguous_true_intervals,
    eval_smoke_masking_intervals,
    merge_intervals,
    point_to_segment_distance_3d,
    sample_cylinder_surface,
    union_length,
)
from tools.or_kernels.lns_hybrid import select_max_union_subset
from tools.or_kernels.milp_reduction import (
    solve_assignment_milp,
    solve_budgeted_coverage_milp,
    solve_general_milp,
)
from tools.or_kernels.nlp_minlp import solve_box_nlp, solve_multistart_polish

__all__ = [
    "build_custom_envelope",
    "contiguous_true_intervals",
    "eval_smoke_masking_intervals",
    "merge_intervals",
    "point_to_segment_distance_3d",
    "sample_cylinder_surface",
    "select_max_union_subset",
    "solve_assignment_milp",
    "solve_box_nlp",
    "solve_budgeted_coverage_milp",
    "solve_general_milp",
    "solve_multistart_polish",
    "union_length",
    "write_solution_and_report",
]
