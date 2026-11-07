"""Phase 2 / Task 2.3 — RCPSP PSPLib Benchmark Gate (Numbers Truth).

Dedicated unit suite for tools/solve_rcpsp.py (OR-Tools CP-SAT, renewable
resources via ``AddCumulative``) against the published PSPLib known optimum:

* j301_1 (32 activities x 4 renewable resources) → makespan 43

Every case asserts the standard solution envelope (status / objective /
lower_bound / optimality_gap == 0.0), independently recomputes activity
precedence and renewable resource capacity from the raw schedule entries,
verifies the resource-usage timeline profile, and re-verifies the full result
through the independent validator
``tools/validators/extended_solvers.py::validate_rcpsp``.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from solve_rcpsp import solve_rcpsp
from validators.extended_solvers import validate_rcpsp

GOLD_MAKESPAN = 43
NUM_ACTIVITIES = 32
NUM_RESOURCES = 4


@pytest.fixture(scope="module")
def solution() -> dict:
    """Solve j301_1 once per module run (Numbers Truth: solver-only)."""
    return solve_rcpsp(time_limit_s=30)


# ---------------------------------------------------------------------------
# 1. Published optimum: objective, lower_bound, optimality_gap
# ---------------------------------------------------------------------------
def test_j301_1_matches_published_optimum(solution):
    sol = solution
    assert sol["status"] == "OPTIMAL", f"status={sol['status']}"
    assert sol["objective"] == GOLD_MAKESPAN, (
        f"makespan={sol['objective']} != {GOLD_MAKESPAN}"
    )
    assert sol["lower_bound"] == GOLD_MAKESPAN, (
        f"lower_bound={sol['lower_bound']} != {GOLD_MAKESPAN}"
    )
    assert isinstance(sol["lower_bound"], int)
    assert sol["optimality_gap"] == 0.0, f"gap={sol['optimality_gap']} != 0.0"
    assert sol["known_optimum"] == GOLD_MAKESPAN


def test_envelope_contract(solution):
    sol = solution
    # contract keys (ADR-0002 + Phase 2 bounds standardization)
    for key in ("status", "objective", "lower_bound", "optimality_gap",
                "problem_id", "problem_class", "schedule", "resource_usage",
                "critical_path", "metrics"):
        assert key in sol, f"envelope missing key '{key}'"
    assert isinstance(sol["objective"], int)
    assert isinstance(sol["lower_bound"], int)
    assert isinstance(sol["optimality_gap"], float)
    assert sol["problem_class"] == "rcpsp"
    assert sol["status"] in ("OPTIMAL", "FEASIBLE")
    assert sol["objective"] > 0

    # schedule entries: {"activity": int, "start": int, "end": int, "duration": int}
    assert len(sol["schedule"]) == NUM_ACTIVITIES
    for e in sol["schedule"]:
        assert set(e) >= {"activity", "start", "end", "duration"}
        assert isinstance(e["activity"], int)
        assert e["end"] - e["start"] == e["duration"]
    assert isinstance(sol["resource_usage"], dict) and sol["resource_usage"]
    assert isinstance(sol["critical_path"], list) and sol["critical_path"]
    assert isinstance(sol["metrics"], dict)


def test_metrics_contract(solution):
    sol = solution
    m = sol["metrics"]
    for key in ("makespan", "objective", "lower_bound", "optimality_gap",
                "num_activities", "num_resources", "proven_optimal",
                "solver_status", "solve_seconds"):
        assert key in m, f"metrics missing key '{key}'"
    assert m["makespan"] == sol["objective"] == GOLD_MAKESPAN
    assert m["lower_bound"] == sol["lower_bound"] == GOLD_MAKESPAN
    assert m["optimality_gap"] == sol["optimality_gap"] == 0.0
    assert m["num_activities"] == NUM_ACTIVITIES
    assert m["num_resources"] == NUM_RESOURCES
    assert m["proven_optimal"] is True
    assert m["solver_status"] == "OPTIMAL"


# ---------------------------------------------------------------------------
# 2. Precedence constraints: independently recomputed from raw schedule
# ---------------------------------------------------------------------------
def test_precedence_respected_independent(solution):
    sol = solution
    sched = {e["activity"]: e for e in sol["schedule"]}
    assert set(sched) == set(range(NUM_ACTIVITIES))
    for pair in sol["precedences"]:
        u, v = int(pair["u"]), int(pair["v"])
        assert sched[v]["start"] >= sched[u]["end"], (
            f"precedence {u}->{v} violated: "
            f"start[{v}]={sched[v]['start']} < end[{u}]={sched[u]['end']}"
        )
    # dummy source starts at 0, sink ends at the makespan
    assert sched[0]["start"] == 0 and sched[0]["end"] == 0
    assert sched[NUM_ACTIVITIES - 1]["end"] == sol["objective"]


# ---------------------------------------------------------------------------
# 3. Renewable resource capacity respected at every time period
# ---------------------------------------------------------------------------
def test_renewable_capacity_respected_independent(solution):
    sol = solution
    capacities = sol["resource_capacities"]
    horizon = max(e["end"] for e in sol["schedule"])
    for t in range(horizon):
        for r, cap in enumerate(capacities):
            used = sum(
                e["demands"][r]
                for e in sol["schedule"]
                if e["start"] <= t < e["end"] and r < len(e["demands"])
            )
            assert used <= cap, f"t={t} R{r}: used {used} > capacity {cap}"


def test_resource_usage_profile_recomputes(solution):
    """resource_usage timeline must match an independent recomputation."""
    sol = solution
    schedule = sol["schedule"]
    makespan = sol["objective"]
    recomputed: dict[str, list[int]] = {}
    for r in range(NUM_RESOURCES):
        loads = [0] * makespan
        for e in schedule:
            d = e["demands"][r] if r < len(e["demands"]) else 0
            if d > 0:
                for t in range(e["start"], e["end"]):
                    loads[t] += d
        recomputed[f"R{r}"] = loads
    assert sol["resource_usage"] == recomputed
    # every load never exceeds its capacity
    for r, cap in enumerate(sol["resource_capacities"]):
        assert max(sol["resource_usage"][f"R{r}"]) <= cap


# ---------------------------------------------------------------------------
# 4. Critical path: zero total slack, ordered by early start, ends at sink
# ---------------------------------------------------------------------------
def test_critical_path_zero_slack(solution):
    sol = solution
    sched = {e["activity"]: e for e in sol["schedule"]}
    starts = {a: e["start"] for a, e in sched.items()}
    # independent backward pass: LS[u] = min LS[v] - dur[u] (sink deadline =
    # makespan), via memoized DFS over the precedence DAG
    succ: dict[int, list[int]] = {a: [] for a in starts}
    for p in sol["precedences"]:
        succ[int(p["u"])].append(int(p["v"]))
    late_start: dict[int, int] = {}

    def late(u: int) -> int:
        if u not in late_start:
            lf = min((late(v) for v in succ[u]), default=sol["objective"])
            late_start[u] = lf - sched[u]["duration"]
        return late_start[u]

    for a in range(NUM_ACTIVITIES):
        late(a)
    cp = sol["critical_path"]
    assert cp[-1] == NUM_ACTIVITIES - 1, "critical path must end at sink dummy"
    assert [starts[a] for a in cp] == sorted(starts[a] for a in cp)
    for a in cp:
        assert starts[a] == late_start[a], (
            f"activity {a} on critical path has slack "
            f"{late_start[a] - starts[a]}"
        )


# ---------------------------------------------------------------------------
# 5. Independent validation via tools.validators.extended_solvers
# ---------------------------------------------------------------------------
def test_validate_rcpsp_all_checks_ok(solution):
    sol = solution
    checks = validate_rcpsp("rcpsp_j301_1", sol)
    assert checks, "validate_rcpsp returned no checks"
    failed = [c for c in checks if not c.get("ok")]
    assert not failed, f"validate_rcpsp failed checks: {failed}"
    names = {c["name"] for c in checks}
    assert {
        "rcpsp_duration_consistency",
        "rcpsp_schedule_completeness",
        "rcpsp_precedence_respected",
        "rcpsp_resource_capacities_respected",
        "rcpsp_makespan_matches_objective",
    } <= names


def test_makespan_is_max_end_time(solution):
    """Objective truth: makespan == max end over all activities."""
    sol = solution
    recomputed = max(e["end"] for e in sol["schedule"])
    assert recomputed == sol["objective"] == GOLD_MAKESPAN
