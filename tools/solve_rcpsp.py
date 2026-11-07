#!/usr/bin/env python3
"""RCPSP (Resource-Constrained Project Scheduling) Solver using OR-Tools CP-SAT.

Industrial-grade adapter over PSPLib-format project instances (``*.sm``):

* **PSPLib intake** — ``psplib.parse(..., instance_format="psplib")``; activity
  0 is the source dummy and activity ``n-1`` is the sink dummy (both zero
  duration).  Known optima are reported as reference only (Numbers Truth: the
  objective strictly comes from the solver).
* **CP-SAT formulation** — precedences via ``starts[succ] >= ends[i]``,
  renewable resources via ``AddCumulative``, non-renewable resources via a
  global sum constraint, objective = makespan (end of sink dummy).
* **Critical path** — zero total slack: an activity is critical when its
  start in the delivered schedule equals its late start (backward pass from
  the makespan through precedences).  Ordered by early start.

Default benchmark: ``fixtures/benchmarks/psplib/j301_1.sm`` (known optimal
makespan = 43).

Output follows the OR-Path "Numbers Truth" envelope (ADR-0002):
  problem_id, problem_class="rcpsp", mode="rcpsp", status, objective, makespan,
  solver, source, num_activities, num_resources, schedule, critical_path,
  precedences, resource_capacities, meta.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Iterable

import psplib
from ortools.sat.python import cp_model

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

DEFAULT_INSTANCE = _ROOT / "fixtures" / "benchmarks" / "psplib" / "j301_1.sm"
DEFAULT_SOLVER = "ortools-cpsat-rcpsp"

# Published optimal makespans for the shipped PSPLib fixtures (reference
# only — Numbers Truth: the objective strictly comes from the solver).
KNOWN_OPTIMA: dict[str, int] = {"j301_1": 43}


def _resolve_instance_path(instance_path: str | Path | None) -> Path:
    """Resolve instance path against cwd, then install root (not CWD-fragile)."""
    raw = str(instance_path or DEFAULT_INSTANCE)
    if raw in ("test_prob", "default") or not raw:
        return DEFAULT_INSTANCE
    p = Path(raw)
    if p.is_file():
        return p
    for base in (_ROOT, Path.cwd()):
        cand = base / raw
        if cand.is_file():
            return cand
        cand_psplib = base / "fixtures" / "benchmarks" / "psplib" / raw
        if cand_psplib.is_file():
            return cand_psplib
        if not raw.endswith(".sm"):
            cand_sm = base / "fixtures" / "benchmarks" / "psplib" / f"{raw}.sm"
            if cand_sm.is_file():
                return cand_sm
    raise FileNotFoundError(f"RCPSP instance not found: {raw}")


def _extract(
    activities: Iterable[Any], resources: Iterable[Any]
) -> tuple[list[int], list[list[int]], list[list[int]], list[int], list[bool]]:
    """Flatten psplib (or duck-typed) activities/resources into plain ints."""
    durations: list[int] = []
    demands: list[list[int]] = []
    successors: list[list[int]] = []
    for act in activities:
        mode = act.modes[0]
        durations.append(int(mode.duration))
        demands.append([int(d) for d in mode.demands])
        successors.append([int(s) for s in act.successors])
    capacities: list[int] = []
    renewable: list[bool] = []
    for res in resources:
        capacities.append(int(res.capacity))
        renewable.append(bool(getattr(res, "is_renewable", True)))
    return durations, demands, successors, capacities, renewable


def _topo_order(n: int, successors: list[list[int]]) -> list[int]:
    """Kahn topological order over the precedence DAG."""
    indeg = [0] * n
    for u in range(n):
        for v in successors[u]:
            indeg[v] += 1
    queue = deque(u for u in range(n) if indeg[u] == 0)
    order: list[int] = []
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in successors[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    # DAG by construction; guard anyway against malformed instances.
    if len(order) != n:
        order = list(range(n))
    return order


def _critical_path(
    n: int,
    durations: list[int],
    successors: list[list[int]],
    makespan: int,
    starts: list[int],
) -> list[int]:
    """Critical path: zero total slack in the delivered schedule.

    Backward pass from the makespan through precedences gives the latest
    start ``LS[u]`` (``LF[u] = min LS[v]``, sink deadline = makespan).
    Total slack is ``LS[u] - start[u]`` in the solver's schedule; critical
    activities have ``early_start == late_start`` (slack == 0), i.e. any
    delay of their start extends the makespan along the successor chain.
    Ordered by early start for readability.
    """
    order = _topo_order(n, successors)
    ls = [0] * n
    for u in reversed(order):
        lf = min((ls[v] for v in successors[u]), default=makespan)
        ls[u] = lf - durations[u]

    critical = [u for u in range(n) if starts[u] == ls[u]]
    critical.sort(key=lambda u: (starts[u], u))
    return critical or [n - 1]


def solve_rcpsp(
    instance_path: str | Path | None = None,
    activities: Iterable[Any] | None = None,
    resources: Iterable[Any] | None = None,
    time_limit_s: float = 30.0,
    problem_id: str | None = None,
) -> dict[str, Any]:
    """Solve an RCPSP instance via OR-Tools CP-SAT (Numbers Truth envelope).

    Parameters
    ----------
    instance_path
        Path to a PSPLib ``*.sm`` instance.  Defaults to
        ``fixtures/benchmarks/psplib/j301_1.sm``.  Ignored when both
        ``activities`` and ``resources`` are provided.
    activities, resources
        Optional duck-typed overrides (psplib ``Activity``/``Resource``
        objects with ``modes[0].duration``, ``modes[0].demands``,
        ``successors`` / ``capacity``, ``is_renewable``).
    time_limit_s
        CP-SAT wall-clock limit.
    problem_id
        Envelope id; defaults to the instance file stem.
    """
    t0 = time.time()
    if activities is None or resources is None:
        resolved = _resolve_instance_path(instance_path)
        inst = psplib.parse(str(resolved), instance_format="psplib")
        activities = inst.activities if activities is None else activities
        resources = inst.resources if resources is None else resources
    else:
        resolved = Path(str(instance_path)) if instance_path else DEFAULT_INSTANCE

    durations, demands, successors, capacities, renewable = _extract(
        activities, resources
    )
    n = len(durations)
    n_res = len(capacities)
    horizon = sum(durations)

    model = cp_model.CpModel()
    starts = [model.NewIntVar(0, horizon, f"start_{i}") for i in range(n)]
    ends = [model.NewIntVar(0, horizon, f"end_{i}") for i in range(n)]
    intervals = [
        model.NewIntervalVar(starts[i], durations[i], ends[i], f"iv_{i}")
        for i in range(n)
    ]

    # Precedences: successor may not start before predecessor ends.
    for i in range(n):
        for s in successors[i]:
            model.Add(starts[s] >= ends[i])

    # Renewable resources: cumulative capacity at every time slot.
    for r in range(n_res):
        active = [i for i in range(n) if demands[i][r] > 0]
        if active:
            model.AddCumulative(
                [intervals[i] for i in active],
                [demands[i][r] for i in active],
                capacities[r],
            )
        if not renewable[r]:
            # Non-renewable: total consumption across the project <= capacity.
            model.Add(
                sum(demands[i][r] for i in range(n)) <= capacities[r]
            )

    # Sink dummy (index n-1) closes the project; makespan = its end.
    model.Minimize(ends[n - 1])

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_s)
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            f"CP-SAT failed on {resolved}: {solver.StatusName(status)}"
        )

    status_str = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
    makespan = int(solver.ObjectiveValue())

    # CP-SAT incumbent bound → lower_bound / optimality_gap (Numbers Truth).
    # int() truncates toward zero, which never exceeds the true bound.
    lower_bound = int(solver.BestObjectiveBound())
    if status_str == "OPTIMAL":
        optimality_gap = 0.0  # proven optimum: zero gap by definition
    else:
        optimality_gap = round(makespan - lower_bound, 4)
        if -1e-6 <= optimality_gap < 0.0:
            optimality_gap = 0.0
    starts_v = [int(solver.Value(starts[i])) for i in range(n)]
    ends_v = [int(solver.Value(ends[i])) for i in range(n)]
    critical = _critical_path(n, durations, successors, makespan, starts_v)

    # Resource usage profile: cumulative load per resource per time slot
    # [t, t+1), recomputed from the delivered schedule (Numbers Truth).
    resource_usage: dict[str, list[int]] = {}
    for r in range(n_res):
        loads = [0] * makespan
        for i in range(n):
            d = demands[i][r] if r < len(demands[i]) else 0
            if d > 0:
                for t in range(starts_v[i], ends_v[i]):
                    loads[t] += d
        resource_usage[f"R{r}"] = loads

    precedences = [
        {"u": i, "v": s}
        for i in range(n)
        for s in successors[i]
    ]
    schedule = [
        {
            "activity_id": i,
            "activity": i,
            "start": starts_v[i],
            "end": ends_v[i],
            "duration": durations[i],
            "demands": demands[i],
        }
        for i in range(n)
    ]

    pid = str(problem_id or Path(resolved).stem)
    known_optimum = KNOWN_OPTIMA.get(Path(resolved).stem)
    elapsed = time.time() - t0
    result: dict[str, Any] = {
        "problem_id": pid,
        "problem_class": "rcpsp",
        "mode": "rcpsp",
        "status": status_str,
        "objective": makespan,
        "lower_bound": lower_bound,
        "optimality_gap": optimality_gap,
        "solver": DEFAULT_SOLVER,
        "source": "tools/solve_rcpsp.py",
        "makespan": makespan,
        "num_activities": n,
        "num_resources": n_res,
        "schedule": schedule,
        "resource_usage": resource_usage,
        "critical_path": critical,
        "precedences": precedences,
        "resource_capacities": capacities,
        "metrics": {
            "makespan": makespan,
            "objective": makespan,
            "lower_bound": lower_bound,
            "optimality_gap": optimality_gap,
            "num_activities": n,
            "num_resources": n_res,
            "critical_path_length": len(critical),
            "proven_optimal": status_str == "OPTIMAL",
            "solver_status": solver.StatusName(status),
            "solve_seconds": round(elapsed, 4),
            "method_class": "exact",
            "instance": str(resolved),
        },
        "meta": {
            "exact": True,
            "proven_optimal": status_str == "OPTIMAL",
            "method_class": "exact",
            "instance": str(resolved),
            "time_limit_s": float(time_limit_s),
            "solver_status": solver.StatusName(status),
            "solve_seconds": round(elapsed, 4),
            "critical_path_activities": len(critical),
            "critical_path_method": "zero_total_slack_late_start_from_makespan",
            "source_dummy": 0,
            "sink_dummy": n - 1,
        },
    }
    if known_optimum is not None:
        result["known_optimum"] = known_optimum
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OR-Path RCPSP solver (PSPLib *.sm via OR-Tools CP-SAT)"
    )
    parser.add_argument(
        "--instance",
        default=str(DEFAULT_INSTANCE),
        help=f"PSPLib instance path (default: {DEFAULT_INSTANCE.name})",
    )
    parser.add_argument("--time-limit-s", type=float, default=30.0)
    parser.add_argument("--json-out", default=None, help="Write result JSON to path")
    args = parser.parse_args(argv)

    sol = solve_rcpsp(instance_path=args.instance, time_limit_s=args.time_limit_s)
    out = json.dumps(sol, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if sol.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
