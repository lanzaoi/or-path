#!/usr/bin/env python3
"""Staff Rostering Solver using OR-Tools CP-SAT.

Shift rostering (nurse / workforce scheduling) over a planning horizon with:
* Four shift types: Morning, Afternoon, Night, Off
* Exactly one shift per employee per day
* Daily shift demand satisfaction
* Rest after Night shift (Night on day d → no Morning on day d+1)
* Max consecutive working days constraint
* Objective: minimise max_work − min_work (workload fairness)

Default benchmark: 8 nurses × 14 days, demand Morning=2 / Afternoon=2 / Night=1.

Output follows the OR-Path "Numbers Truth" envelope (ADR-0002):
  problem_id, problem_class="staff_rostering", mode="staff_rostering",
  status, objective, solver, source, num_employees, num_days, shifts,
  roster (dict[str, list[str]]), schedule_by_day (list[dict]),
  fairness_metrics (dict), shift_demands (list[dict]),
  max_consecutive_days (int), meta.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

from ortools.sat.python import cp_model

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

SHIFTS = ["Morning", "Afternoon", "Night", "Off"]
WORKING_SHIFTS = ["Morning", "Afternoon", "Night"]
DEFAULT_SOLVER = "ortools-cpsat-rostering"
DEFAULT_PROBLEM_ID = "staff_rostering"


def _normalise_demands(
    shift_demands: Any, num_days: int
) -> list[dict[str, int]]:
    """Normalise shift_demands into a per-day list of dicts.

    Accepts:
    * None → uniform default {Morning:2, Afternoon:2, Night:1}
    * dict  → same demand applied to every day
    * list  → per-day list of dicts
    """
    if shift_demands is None:
        uniform = {"Morning": 2, "Afternoon": 2, "Night": 1}
        return [dict(uniform) for _ in range(num_days)]
    if isinstance(shift_demands, dict):
        return [dict(shift_demands) for _ in range(num_days)]
    if isinstance(shift_demands, list):
        if len(shift_demands) != num_days:
            raise ValueError(
                f"shift_demands list length {len(shift_demands)} != num_days {num_days}"
            )
        return [dict(d) for d in shift_demands]
    raise TypeError(f"shift_demands must be None, dict, or list; got {type(shift_demands)}")


def solve_staff_rostering(
    num_employees: int = 8,
    num_days: int = 14,
    shift_demands: Any = None,
    max_consecutive_days: int = 5,
    time_limit_s: float = 30.0,
    problem_id: str | None = None,
) -> dict[str, Any]:
    """Solve a staff rostering problem via OR-Tools CP-SAT.

    Parameters
    ----------
    num_employees
        Number of staff to roster.
    num_days
        Planning horizon in days.
    shift_demands
        Daily demand per working shift.  ``None`` → uniform
        {Morning:2, Afternoon:2, Night:1}.  A dict applies uniformly;
        a list provides per-day overrides.
    max_consecutive_days
        Maximum consecutive working days before a mandatory off day.
    time_limit_s
        CP-SAT wall-clock limit.
    problem_id
        Envelope id; defaults to ``"staff_rostering"``.
    """
    t0 = time.time()
    employees = [f"Employee_{i}" for i in range(num_employees)]
    demands = _normalise_demands(shift_demands, num_days)

    model = cp_model.CpModel()
    x = {
        (e, d, s): model.NewBoolVar(f"x_{e}_{d}_{s}")
        for e in employees
        for d in range(num_days)
        for s in SHIFTS
    }

    # 1. Exactly one shift per employee per day.
    for e in employees:
        for d in range(num_days):
            model.Add(sum(x[e, d, s] for s in SHIFTS) == 1)

    # 2. Daily shift demand for working shifts.
    for d in range(num_days):
        for s in WORKING_SHIFTS:
            need = demands[d].get(s, 0)
            if need > 0:
                model.Add(sum(x[e, d, s] for e in employees) >= need)

    # 3. Rest after Night shift: no Night → Morning the next day.
    for e in employees:
        for d in range(num_days - 1):
            model.Add(x[e, d, "Night"] + x[e, d + 1, "Morning"] <= 1)

    # 4. Max consecutive working days.
    max_consec = int(max_consecutive_days)
    for e in employees:
        for d in range(num_days - max_consec):
            model.Add(
                sum(x[e, d + i, s] for i in range(max_consec + 1) for s in WORKING_SHIFTS)
                <= max_consec
            )

    # 5. Workload balance: minimise max_work − min_work.
    work_days = [model.NewIntVar(0, num_days, f"work_{e}") for e in employees]
    for idx, e in enumerate(employees):
        model.Add(
            work_days[idx]
            == sum(x[e, d, s] for d in range(num_days) for s in WORKING_SHIFTS)
        )

    max_work = model.NewIntVar(0, num_days, "max_work")
    min_work = model.NewIntVar(0, num_days, "min_work")
    model.AddMaxEquality(max_work, work_days)
    model.AddMinEquality(min_work, work_days)
    model.Minimize(max_work - min_work)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_s)
    status = solver.Solve(model)

    elapsed = time.time() - t0
    pid = str(problem_id or DEFAULT_PROBLEM_ID)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "problem_id": pid,
            "problem_class": "staff_rostering",
            "mode": "staff_rostering",
            "status": "INFEASIBLE",
            "objective": None,
            "solver": DEFAULT_SOLVER,
            "source": "tools/solve_staff_rostering.py",
            "num_employees": num_employees,
            "num_days": num_days,
            "shifts": SHIFTS,
            "roster": {},
            "schedule_by_day": [],
            "fairness_metrics": {},
            "shift_demands": demands,
            "max_consecutive_days": max_consec,
            "meta": {
                "exact": True,
                "proven_optimal": False,
                "method_class": "exact",
                "time_limit_s": float(time_limit_s),
                "solver_status": solver.StatusName(status),
                "solve_seconds": round(elapsed, 4),
            },
        }

    status_str = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
    objective = int(solver.ObjectiveValue())

    # Build roster: employee → list of shift names.
    roster: dict[str, list[str]] = {}
    for e in employees:
        roster[e] = []
        for d in range(num_days):
            for s in SHIFTS:
                if solver.Value(x[e, d, s]) == 1:
                    roster[e].append(s)
                    break

    # Build schedule_by_day: per-day shift assignments.
    schedule_by_day: list[dict[str, Any]] = []
    for d in range(num_days):
        assignments: dict[str, list[str]] = {s: [] for s in SHIFTS}
        for e in employees:
            for s in SHIFTS:
                if solver.Value(x[e, d, s]) == 1:
                    assignments[s].append(e)
                    break
        schedule_by_day.append({"day": d, "assignments": assignments})

    # Fairness metrics.
    work_counts = {e: sum(1 for s in roster[e] if s in WORKING_SHIFTS) for e in employees}
    vals = list(work_counts.values())
    min_shifts = min(vals)
    max_shifts = max(vals)
    mean = sum(vals) / len(vals)
    std_dev = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))

    elapsed = time.time() - t0
    pid = str(problem_id or DEFAULT_PROBLEM_ID)

    return {
        "problem_id": pid,
        "problem_class": "staff_rostering",
        "mode": "staff_rostering",
        "status": status_str,
        "objective": objective,
        "solver": DEFAULT_SOLVER,
        "source": "tools/solve_staff_rostering.py",
        "num_employees": num_employees,
        "num_days": num_days,
        "shifts": SHIFTS,
        "roster": roster,
        "schedule_by_day": schedule_by_day,
        "fairness_metrics": {
            "total_shifts_per_employee": work_counts,
            "min_shifts": min_shifts,
            "max_shifts": max_shifts,
            "std_dev": round(std_dev, 4),
        },
        "shift_demands": demands,
        "max_consecutive_days": max_consec,
        "meta": {
            "exact": True,
            "proven_optimal": status_str == "OPTIMAL",
            "method_class": "exact",
            "time_limit_s": float(time_limit_s),
            "solver_status": solver.StatusName(status),
            "solve_seconds": round(elapsed, 4),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OR-Path Staff Rostering solver (OR-Tools CP-SAT)"
    )
    parser.add_argument("--employees", type=int, default=8)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--max-consecutive", type=int, default=5)
    parser.add_argument("--time-limit-s", type=float, default=30.0)
    parser.add_argument("--json-out", default=None, help="Write result JSON to path")
    args = parser.parse_args(argv)

    sol = solve_staff_rostering(
        num_employees=args.employees,
        num_days=args.days,
        max_consecutive_days=args.max_consecutive,
        time_limit_s=args.time_limit_s,
    )
    out = json.dumps(sol, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if sol.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
