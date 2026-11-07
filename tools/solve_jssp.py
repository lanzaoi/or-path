#!/usr/bin/env python3
"""Full-scale Job Shop Scheduling (JSSP / FJSSP) Solver using PyJobShop.

Industrial-grade adapter over PyJobShop (https://github.com/PyJobShop/PyJobShop)
with the CP-SAT solver backend.  Capabilities:

* **Taillard benchmark intake** — JSSP (ft/la/abz/orb/swv/yn/ta) and FJSSP
  (kacem/mk/abz-variants/dauzere-peres/chambers-barnes/...) instances live under
  ``fixtures/benchmarks/taillard/{jssp,fjssp}/<name>.json`` with known optima.
* **FJSSP** — each operation may list several (machine, duration) options.
* **Setup times (换模时延)** — sequence-dependent changeover delay between two
  operations on the same machine via ``model.add_setup_time``.  Accepts a uniform
  ``setup`` value or an explicit ``setup_matrix`` keyed by global operation pair.
* **Gantt chart generation** — ``plot_machine_gantt`` renders a per-machine
  Gantt chart to PNG.

Output follows the OR-Path "Numbers Truth" envelope: objective values and the
schedule are taken strictly from the solver; known optima are reported as
reference only (never used to fabricate a result).  ``lower_bound`` is the
published Taillard optimum when available, else the CP-SAT bound;
``optimality_gap`` = objective - lower_bound.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

from pyjobshop import Model, SolveStatus

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

FIXTURE_JSSP = _ROOT / "fixtures" / "benchmarks" / "taillard" / "jssp"
FIXTURE_FJSSP = _ROOT / "fixtures" / "benchmarks" / "taillard" / "fjssp"

# ---------------------------------------------------------------------------
# Legacy inline benchmark (kept for backward compatibility / zero-dep self-test)
# Fisher-Thompson FT06 (6 jobs, 6 machines, optimal makespan = 55)
# ---------------------------------------------------------------------------
FT06_DATA = [
    [(2, 1), (0, 3), (1, 6), (3, 7), (5, 3), (4, 6)],
    [(1, 8), (2, 5), (4, 10), (5, 10), (0, 10), (3, 4)],
    [(2, 5), (3, 4), (5, 8), (0, 9), (1, 1), (4, 7)],
    [(1, 5), (0, 5), (2, 5), (3, 3), (4, 8), (5, 9)],
    [(2, 9), (1, 3), (4, 5), (5, 4), (0, 3), (3, 1)],
    [(1, 3), (3, 3), (5, 9), (0, 10), (4, 4), (2, 1)],
]


# ---------------------------------------------------------------------------
# Instance loading
# ---------------------------------------------------------------------------
def list_taillard_instances(family: str | None = None) -> list[str]:
    """List available Taillard instance names.

    ``family`` in {"jssp", "fjssp"} filters by directory; ``None`` returns all.
    """
    dirs = {"jssp": FIXTURE_JSSP, "fjssp": FIXTURE_FJSSP}
    names: list[str] = []
    for key in ([family] if family else ["jssp", "fjssp"]):
        d = dirs.get(key)
        if d and d.is_dir():
            names.extend(sorted(p.stem for p in d.glob("*.json")))
    return names


def load_taillard_instance(name: str, family: str | None = None) -> dict[str, Any]:
    """Load a Taillard benchmark instance from fixtures."""
    clean_name = name or "ft06"
    if clean_name in ("test_prob", "default"):
        clean_name = "ft06"
    elif clean_name.startswith("jssp_"):
        clean_name = clean_name[5:]
    elif clean_name.startswith("fjssp_"):
        clean_name = clean_name[6:]
        family = family or "fjssp"

    # resolve directory: explicit family, else search both
    candidates: list[Path] = []
    if family:
        candidates.append(FIXTURE_FJSSP / f"{clean_name}.json" if family == "fjssp" else FIXTURE_JSSP / f"{clean_name}.json")
    else:
        candidates += [FIXTURE_JSSP / f"{clean_name}.json", FIXTURE_FJSSP / f"{clean_name}.json"]
    for p in candidates:
        if p.exists():
            d = json.loads(p.read_text())
            resolved_family = "fjssp" if p.parent == FIXTURE_FJSSP else "jssp"
            d["family"] = resolved_family
            d["instance"] = d.get("instance", name)
            return d
    raise FileNotFoundError(
        f"Taillard instance '{name}' not found in fixtures "
        f"(jssp={FIXTURE_JSSP}, fjssp={FIXTURE_FJSSP})"
    )


def _is_fjssp(jobs_data: Any) -> bool:
    """True if jobs_data is FJSSP (operations carry multiple options)."""
    if not jobs_data:
        return False
    first = jobs_data[0][0]
    return isinstance(first, list) and len(first) > 0 and isinstance(first[0], (list, tuple))


# ---------------------------------------------------------------------------
# Model construction
# ---------------------------------------------------------------------------
def _add_setup_times(
    model: Model,
    machines: list[Any],
    task_machine_pairs: list[tuple[int, int]],  # (task_idx, machine_idx)
    setup: int | dict | None,
) -> None:
    """Attach sequence-dependent setup times between tasks sharing a machine.

    ``setup`` may be:
      * ``None``            — no setup.
      * ``int``             — uniform changeover delay on every machine switch.
      * ``dict``            — ``{(op_a, op_b): duration}`` keyed by global
                              operation index pair (only those pairs get a setup).
    """
    if setup is None:
        return

    # group task indices by machine
    by_machine: dict[int, list[int]] = {}
    for task_idx, machine_idx in task_machine_pairs:
        by_machine.setdefault(machine_idx, []).append(task_idx)

    uniform = isinstance(setup, int)
    for machine_idx, task_ids in by_machine.items():
        machine = machines[machine_idx]
        # task objects are indexed in creation order; rebuild map
        for a in task_ids:
            for b in task_ids:
                if a == b:
                    continue
                if uniform:
                    dur = setup  # type: ignore[assignment]
                else:
                    dur = setup.get((a, b), 0)  # type: ignore[index]
                if dur:
                    ta = model.tasks[a]
                    tb = model.tasks[b]
                    model.add_setup_time(machine=machine, task1=ta, task2=tb, duration=dur)


def _build_model(
    jobs_data: list[Any],
    setup: int | dict | None = None,
) -> tuple[Model, list[tuple[int, int, int, int]], list[tuple[int, int]]]:
    """Build a PyJobShop model from jobs_data (JSSP or FJSSP).

    Returns ``(model, task_map, task_machine_pairs)`` where
    ``task_map[i] = (job_idx, op_idx, machine_idx, duration)`` for the default
    machine/duration of operation ``i`` (used for reporting), and
    ``task_machine_pairs`` lists every (task_idx, machine_idx) mode for setups.
    """
    is_fjssp = _is_fjssp(jobs_data)
    num_jobs = len(jobs_data)

    if is_fjssp:
        num_machines = 1 + max(
            m for job in jobs_data for options in job for (m, _) in options
        )
    else:
        num_machines = 1 + max(m for job in jobs_data for (m, _) in job)

    model = Model()
    jobs = [model.add_job() for _ in range(num_jobs)]
    machines = [model.add_machine() for _ in range(num_machines)]

    task_map: list[tuple[int, int, int, int]] = []
    task_machine_pairs: list[tuple[int, int]] = []
    global_op = 0

    for j_idx, job_ops in enumerate(jobs_data):
        prev_task = None
        for op_idx, ops in enumerate(job_ops):
            # ops is a list of (machine, duration) options (JSSP: single option)
            options = ops if is_fjssp else [ops]
            task = model.add_task(job=jobs[j_idx])
            default_m, default_d = options[0]
            for (m_idx, dur) in options:
                model.add_mode(task=task, resources=[machines[m_idx]], duration=dur)
                task_machine_pairs.append((global_op, m_idx))
            if prev_task is not None:
                model.add_end_before_start(prev_task, task)
            prev_task = task
            task_map.append((j_idx, op_idx, default_m, default_d))
            global_op += 1

    _add_setup_times(model, machines, task_machine_pairs, setup)
    return model, task_map, task_machine_pairs


def _total_setup_time(
    schedule: list[dict[str, Any]],
    setup: int | dict | None,
) -> int:
    """Recompute total setup time actually incurred on each machine."""
    if setup is None:
        return 0
    by_machine: dict[int, list[dict[str, Any]]] = {}
    for s in schedule:
        by_machine.setdefault(s["machine"], []).append(s)
    total = 0
    for m_tasks in by_machine.values():
        m_tasks.sort(key=lambda x: x["start"])
        for a, b in zip(m_tasks, m_tasks[1:]):
            if isinstance(setup, int):
                dur = setup
            else:
                dur = setup.get((a["op"], b["op"]), 0)
            if dur:
                total += dur
    return total


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def solve_jssp(
    instance_name: str = "ft06",
    custom_jobs: list[Any] | None = None,
    time_limit_s: float = 30.0,
    setup: int | dict | None = None,
    gantt_path: str | Path | None = None,
    family: str | None = None,
) -> dict[str, Any]:
    """Solve a JSSP/FJSSP instance with PyJobShop CP-SAT.

    Parameters
    ----------
    instance_name
         Taillard benchmark name (e.g. ``"ft06"``, ``"la01"``, ``"kacem1"``).
        Ignored when ``custom_jobs`` is provided.
    custom_jobs
         Optional inline instance; JSSP = ``[[(machine, duration), ...], ...]``,
         FJSSP = ``[[[(machine, duration), ...], ...], ...]``.
    time_limit_s
         CP-SAT wall-clock limit (seconds).
    setup
         换模时延: ``None`` (off), ``int`` (uniform), or ``dict``
         ``{(op_a, op_b): duration}``.
    gantt_path
         If given, render a per-machine Gantt chart PNG to this path.
    family
         ``"jssp"`` / ``"fjssp"`` to disambiguate instance lookup.
    """
    if custom_jobs is not None:
        jobs_data = custom_jobs
        source_name = instance_name
        known_optimum = None
        inst_family = "fjssp" if _is_fjssp(custom_jobs) else "jssp"
    else:
        inst = load_taillard_instance(instance_name, family=family)
        jobs_data = inst["jobs"]
        source_name = inst.get("instance", instance_name)
        known_optimum = inst.get("known_optimum")
        inst_family = inst.get("family", family or "jssp")

    num_jobs = len(jobs_data)
    model, task_map, _ = _build_model(jobs_data, setup=setup)

    # Number of machines from the compiled model data (authoritative for
    # FJSSP: an operation's default mode is not necessarily its used mode).
    num_machines = int(model.data().num_machines)

    t0 = time.perf_counter()
    res = model.solve(time_limit=time_limit_s, display=False)
    t1 = time.perf_counter()

    is_optimal = res.status == SolveStatus.OPTIMAL
    is_feasible = is_optimal or (res.status == SolveStatus.FEASIBLE)

    if not is_feasible or not res.best:
        return {
            "problem_id": f"jssp_{source_name}",
            "problem_class": inst_family,
            "status": "INFEASIBLE",
            "objective": -1,
            "lower_bound": None,
            "optimality_gap": None,
            "solver": "pyjobshop-cpsat",
            "source": "tools/solve_jssp.py",
            "schedule": [],
            "machine_schedules": {},
            "metrics": {},
        }

    sol = res.best
    makespan = int(sol.makespan)

    schedule: list[dict[str, Any]] = []
    for idx, st in enumerate(sol.tasks):
        if st.present:
            j_id, op_id, default_m, default_d = task_map[idx]
            schedule.append({
                "job": j_id,
                "task": op_id,
                "op": idx,  # global operation index (for setup validation)
                "machine": st.resources[0],
                "start": st.start,
                "end": st.end,
                "duration": st.duration if st.duration is not None else default_d,
                "idle": st.idle,
            })

    # Machine utilization (processing time / makespan)
    utilization: dict[int, float] = {}
    for m in range(num_machines):
        active = sum(s["duration"] for s in schedule if s["machine"] == m)
        utilization[m] = round(active / makespan, 4) if makespan > 0 else 0.0

    total_setup = _total_setup_time(schedule, setup)

    # Lower bound / optimality gap (Numbers Truth): prefer the published
    # Taillard optimum (a proven valid bound for the fixture instance);
    # otherwise the CP-SAT incumbent bound (BestObjectiveBound). Never invented.
    solver_lb = getattr(res, "lower_bound", None)
    solver_lower_bound: float | None = float(solver_lb) if solver_lb is not None else None
    if known_optimum is not None:
        lower_bound: int | None = int(known_optimum)
    elif solver_lb is not None:
        lower_bound = math.floor(float(solver_lb))
    else:
        lower_bound = None
    optimality_gap = (
        round(float(makespan - lower_bound), 4) if lower_bound is not None else None
    )

    # Machine timeline (Gantt standardization): per-machine schedule,
    # each machine's tasks sorted by start time, no overlaps (solver-enforced).
    machine_schedules: dict[int, list[dict[str, Any]]] = {}
    for s in sorted(schedule, key=lambda x: (x["machine"], x["start"], x["job"])):
        machine_schedules.setdefault(s["machine"], []).append(s)

    metrics: dict[str, Any] = {
        "makespan": makespan,
        "num_jobs": num_jobs,
        "num_machines": num_machines,
        "total_flow_time": int(sol.total_flow_time),
        "total_setup_time": total_setup,
        "machine_utilization": utilization,
        "solver_lower_bound": solver_lower_bound,
        "wall_time_s": round(t1 - t0, 4),
        "proven_optimal": is_optimal,
    }

    gantt_file = None
    if gantt_path:
        gantt_file = _render_gantt(model, res.best, Path(gantt_path))

    result: dict[str, Any] = {
        "problem_id": f"jssp_{source_name}",
        "problem_class": inst_family,
        "status": "OPTIMAL" if is_optimal else "FEASIBLE",
        "objective": makespan,
        "lower_bound": lower_bound,
        "optimality_gap": optimality_gap,
        "solver": "pyjobshop-cpsat",
        "source": "tools/solve_jssp.py",
        "instance": source_name,
        "instance_family": inst_family,
        "makespan": makespan,
        "num_jobs": num_jobs,
        "num_machines": num_machines,
        "total_flow_time": int(sol.total_flow_time),
        "total_setup_time": total_setup,
        "setup": setup if setup is not None else "none",
        "machine_utilization": utilization,
        "schedule": schedule,
        "machine_schedules": machine_schedules,
        "metrics": metrics,
        "meta": {
            "exact": True,
            "proven_optimal": is_optimal,
            "wall_time_s": round(t1 - t0, 4),
        },
    }
    if known_optimum is not None:
        result["known_optimum"] = known_optimum
    if gantt_file:
        result["gantt_path"] = gantt_file
    return result


def _render_gantt(model: Model, solution: Any, out_path: Path) -> str:
    """Render a per-machine Gantt chart PNG; return the written path."""
    import matplotlib

    matplotlib.use("Agg")
    from pyjobshop.plot import plot_machine_gantt

    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = model.data()
    import matplotlib.pyplot as plt

    _, ax = plt.subplots(1, 1, figsize=(12, 8))
    plot_machine_gantt(solution, data, plot_labels=True, ax=ax)
    fig = ax.get_figure()
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return str(out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PyJobShop Industrial JSSP/FJSSP Solver")
    parser.add_argument("--instance", default="ft06", help="Taillard instance name")
    parser.add_argument("--family", choices=["jssp", "fjssp"], default=None,
                        help="Instance family (auto-detected if omitted)")
    parser.add_argument("--time-limit-s", type=float, default=30.0)
    parser.add_argument("--setup", type=int, default=None,
                        help="Uniform changeover setup time (换模时延) per machine switch")
    parser.add_argument("--gantt", default=None, help="Output PNG path for Gantt chart")
    parser.add_argument("--list", action="store_true", help="List available Taillard instances")
    parser.add_argument("--json-out", default=None, help="Write result JSON to this path")
    args = parser.parse_args(argv)

    if args.list:
        fam = args.family
        print(json.dumps(list_taillard_instances(fam), ensure_ascii=False, indent=2))
        return 0

    result = solve_jssp(
        instance_name=args.instance,
        time_limit_s=args.time_limit_s,
        setup=args.setup,
        gantt_path=args.gantt,
        family=args.family,
    )
    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(out)
    print(out)
    return 0 if result.get("status") in ("OPTIMAL", "FEASIBLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
