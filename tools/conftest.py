"""Pytest configuration and environment initialization for OR-Path test suites."""
from __future__ import annotations

# Pre-import ortools shared libraries before any third-party solvers (e.g. CVXPY/highspy)
# to avoid Linux dynamic linker symbol collisions between bundled libortools and libhighs.
try:
    import ortools.linear_solver.pywraplp  # noqa: F401
    import ortools.sat.python.cp_model  # noqa: F401
except ImportError:
    pass
