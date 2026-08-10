#!/usr/bin/env python3
"""Fast contract probe suite — fast pipeline check for small fixtures & TSPLIB burma14 (<1.5s total)."""
import sys
import time
from pathlib import Path

repo = Path(__file__).resolve().parent.parent
if str(repo) not in sys.path:
    sys.path.insert(0, str(repo))

from tools.solve_dispatch import solve
from tools.validate_solution import validate

PROBES = [
    {
        "id": "shortest_path",
        "mode": "networkx",
        "class": "shortest_path",
        "extra": None,
    },
    {
        "id": "tsp_n8",
        "mode": "cpsat",
        "class": "tsp",
        "extra": ["--time-limit-s", "1.0"],
    },
    {
        "id": "vrp_multi",
        "mode": "ortools",
        "class": "vrp",
        "extra": ["--time-limit-ms", "200"],
    },
    {
        "id": "polyomino_b_q1",
        "mode": "polyomino",
        "class": "polyomino_cover",
        "extra": ["--time-limit-s", "1.0"],
    },
    {
        "id": "burma14",
        "mode": "cpsat",
        "class": "tsp",
        "extra": ["--time-limit-s", "1.0"],
    },
]


def main() -> int:
    t0 = time.perf_counter()
    print("=" * 60)
    print("OR-Path Fast Contract Probe Suite")
    print("=" * 60)

    total_pass = 0
    for p in PROBES:
        pid = p["id"]
        mode = p["mode"]
        pclass = p["class"]
        extra = p["extra"]

        t_start = time.perf_counter()
        ok, sol, raw = solve(repo, pid, mode=mode, problem_class=pclass, extra_args=extra)
        assert ok, f"[{pid}] Solve failed: {raw}"

        val_report = validate(pid, sol)
        val_ok = bool(val_report.get("ok"))
        dt = time.perf_counter() - t_start
        assert val_ok, f"[{pid}] Validate failed: {val_report}"

        total_pass += 1
        print(f"  PROBE [{pid}]: solve_ok={ok} validate_ok={val_ok} obj={sol.get('objective')} ({dt:.3f}s)")

    total_time = time.perf_counter() - t0
    print("-" * 60)
    print(f"CONTRACT PROBE SUITE PASS: {total_pass}/{len(PROBES)} probes green in {total_time:.3f}s (<1.5s target)")
    print("=" * 60)

    assert total_time < 1.5, f"Contract probe suite exceeded 1.5s wall-clock time limit: {total_time:.3f}s"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
