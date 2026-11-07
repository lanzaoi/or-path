"""Phase 2 / Task 2.1 — JSSP Taillard Benchmark Gate (Numbers Truth).

Dedicated unit suite for tools/solve_jssp.py (PyJobShop CP-SAT) against the
published Taillard / Kacem known optima:

* FT06  (6 jobs x 6 machines, JSSP)  → makespan 55
* LA01  (10 jobs x 5 machines, JSSP) → makespan 666
* Kacem1 (4 jobs x 5 machines, FJSSP) → makespan 11

Every case asserts the standard solution envelope (objective / lower_bound /
optimality_gap == 0), independently recomputes the machine no-overlap and job
precedence constraints from raw schedule entries, and re-verifies the full
result through the independent validator
``tools/validators/extended_solvers.py::validate_jssp``.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from solve_jssp import solve_jssp
from validators.extended_solvers import validate_jssp

# (instance, family, gold makespan, num_jobs, num_machines)
BENCHMARKS = [
    ("ft06", None, 55, 6, 6),
    ("la01", None, 666, 10, 5),
    ("kacem1", "fjssp", 11, 4, 5),
]


@pytest.fixture(scope="module")
def solutions() -> dict[str, dict]:
    """Solve each benchmark once per module run (Numbers Truth: solver-only)."""
    out: dict[str, dict] = {}
    for name, family, _gold, _nj, _nm in BENCHMARKS:
        out[name] = solve_jssp(name, family=family, time_limit_s=30)
    return out


# ---------------------------------------------------------------------------
# 1. Published optima: objective, lower_bound, optimality_gap
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,family,gold,num_jobs,num_machines", BENCHMARKS)
def test_benchmark_matches_published_optimum(solutions, name, family, gold,
                                             num_jobs, num_machines):
    sol = solutions[name]
    assert sol["status"] == "OPTIMAL", f"{name}: status={sol['status']}"
    assert sol["objective"] == gold, f"{name}: makespan={sol['objective']} != {gold}"
    assert sol["lower_bound"] == gold, f"{name}: lower_bound={sol['lower_bound']} != {gold}"
    assert sol["optimality_gap"] == 0, f"{name}: gap={sol['optimality_gap']} != 0"
    assert sol["known_optimum"] == gold


@pytest.mark.parametrize("name,family,gold,num_jobs,num_machines", BENCHMARKS)
def test_envelope_contract(solutions, name, family, gold, num_jobs, num_machines):
    sol = solutions[name]
    # contract keys
    for key in ("status", "objective", "lower_bound", "optimality_gap",
                "problem_id", "problem_class", "schedule",
                "machine_schedules", "metrics"):
        assert key in sol, f"{name}: envelope missing key '{key}'"
    assert isinstance(sol["objective"], int)
    assert isinstance(sol["lower_bound"], int)
    assert isinstance(sol["optimality_gap"], float) or sol["optimality_gap"] == 0
    assert sol["problem_class"] == (family or "jssp")
    assert sol["metrics"]["makespan"] == gold
    assert sol["metrics"]["num_jobs"] == num_jobs
    assert sol["metrics"]["num_machines"] == num_machines
    # CP-SAT BestObjectiveBound captured (solver_lower_bound, Numbers Truth)
    assert sol["metrics"]["solver_lower_bound"] is not None
    assert sol["metrics"]["solver_lower_bound"] <= gold
    assert sol["metrics"]["proven_optimal"] is True


def test_ft06_schedule_size(solutions):
    assert len(solutions["ft06"]["schedule"]) == 36  # 6 jobs x 6 ops


# ---------------------------------------------------------------------------
# 2. Machine no-overlap: independently recomputed from raw schedule entries
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,family,gold,num_jobs,num_machines", BENCHMARKS)
def test_machine_no_overlap_independent(solutions, name, family, gold,
                                        num_jobs, num_machines):
    sol = solutions[name]
    by_machine: dict[int, list[dict]] = {}
    for t in sol["schedule"]:
        by_machine.setdefault(t["machine"], []).append(t)

    # every used machine must be a valid machine id; FJSSP may leave machines unused
    assert set(by_machine) <= set(range(num_machines))
    for m_id, tasks in by_machine.items():
        tasks.sort(key=lambda x: x["start"])
        for a, b in zip(tasks, tasks[1:]):
            assert b["start"] >= a["end"], (
                f"{name}: machine {m_id} overlap "
                f"[{a['start']},{a['end']}) vs [{b['start']},{b['end']})"
            )
    # machine_schedules mirror must agree with flat schedule
    mirror = sol["machine_schedules"]
    assert set(mirror) == set(by_machine)
    for m_id, tasks in by_machine.items():
        assert [s["op"] for s in mirror[m_id]] == [s["op"] for s in tasks]


# ---------------------------------------------------------------------------
# 3. Job precedence: op k must start at/after op k-1 ends
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,family,gold,num_jobs,num_machines", BENCHMARKS)
def test_job_precedence_independent(solutions, name, family, gold,
                                    num_jobs, num_machines):
    sol = solutions[name]
    by_job: dict[int, list[dict]] = {}
    for t in sol["schedule"]:
        by_job.setdefault(t["job"], []).append(t)

    assert len(by_job) == num_jobs
    for j_id, tasks in by_job.items():
        tasks.sort(key=lambda x: x["task"])
        assert [t["task"] for t in tasks] == list(range(len(tasks)))
        for a, b in zip(tasks, tasks[1:]):
            assert b["start"] >= a["end"], (
                f"{name}: job {j_id} precedence violated "
                f"op{a['task']} end={a['end']} > op{b['task']} start={b['start']}"
            )


# ---------------------------------------------------------------------------
# 4. Independent validation via tools.validators.extended_solvers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,family,gold,num_jobs,num_machines", BENCHMARKS)
def test_validate_jssp_ok(solutions, name, family, gold, num_jobs, num_machines):
    sol = solutions[name]
    checks = validate_jssp(f"jssp_{name}", sol)
    assert checks, "validate_jssp returned no checks"
    failed = [c for c in checks if not c.get("ok")]
    assert not failed, f"validate_jssp failed checks: {failed}"
    names = {c["name"] for c in checks}
    assert {"task_duration_consistency", "job_precedence",
            "machine_no_overlap", "makespan_objective_match"} <= names


def test_makespan_is_max_end_time(solutions):
    """Objective truth: makespan == max end over all operations."""
    for name, _f, gold, _nj, _nm in BENCHMARKS:
        sol = solutions[name]
        recomputed = max(t["end"] for t in sol["schedule"])
        assert recomputed == sol["objective"] == gold
        assert recomputed == max(
            max(s["end"] for s in tasks) if tasks else 0
            for tasks in sol["machine_schedules"].values()
        )
