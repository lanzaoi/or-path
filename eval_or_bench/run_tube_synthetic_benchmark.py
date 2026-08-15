#!/usr/bin/env python3
"""Public synthetic benchmark for Tube optimisation quality and runtime."""
from __future__ import annotations

import argparse
import json
import sys
import time
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from tube_optimization import (  # noqa: E402
    materialize_bins,
    mixed_stock_patterns,
    optimize_fixed_assignments,
    orientation_dp,
)


def savings_for(gids: tuple[str, ...]) -> dict[str, dict[str, float]]:
    result = {}
    for i, a in enumerate(gids):
        for j, b in enumerate(gids):
            result[f"{a}-{b}"] = {
                "LL": float((i + 2 * j + 1) % 7),
                "LR": float((3 * i + j + 2) % 9),
                "RL": float((i + 4 * j + 3) % 11),
                "RR": float((2 * i + 3 * j + 4) % 8),
            }
    return result


def brute_orientation(sequence, savings) -> float:
    best = -1.0
    for orientation in product(("L", "R"), repeat=len(sequence)):
        value = 0.0
        for i, (a, b) in enumerate(zip(sequence, sequence[1:])):
            right_a = "R" if orientation[i] == "L" else "L"
            value += savings[f"{a}-{b}"][right_a + orientation[i + 1]]
        best = max(best, value)
    return best


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run synthetic Tube performance checks")
    parser.add_argument("--seed", type=int, default=20260813)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "tube-synthetic-benchmark.json")
    args = parser.parse_args(argv)

    # Mixed-stock proof case: 11=(A+B), 10=(A), total 21 beats all-uniform.
    started = time.perf_counter()
    mixed = mixed_stock_patterns(
        {"A": 2, "B": 1},
        {"A": 6.0, "B": 5.0},
        stocks=(10.0, 11.0),
        seed=args.seed,
        time_limit_s=2.0,
    )
    mixed_ms = 1000.0 * (time.perf_counter() - started)
    mixed_total = sum(float(b["stock_length_mm"]) for b in mixed)

    gids = ("A", "B", "C")
    savings = savings_for(gids)
    short_seq = ["A", "B", "C", "A", "C", "B", "A", "A"]
    started = time.perf_counter()
    dp_value, _orientations, _joints = orientation_dp(short_seq, savings)
    dp_ms = 1000.0 * (time.perf_counter() - started)
    started = time.perf_counter()
    brute_value = brute_orientation(short_seq, savings)
    brute_ms = 1000.0 * (time.perf_counter() - started)

    lengths = {g: 10.0 for g in gids}
    initial_source = [
        {
            "id": "M1",
            "stock_length_mm": 200.0,
            "purchase_cost_mm": 200.0,
            "sequence": ["A", "A", "B", "C", "B", "A", "C", "B", "C", "A"],
            "from_remnant": False,
        }
    ]
    initial = materialize_bins(initial_source, lengths, savings, resize_new=False)
    assert initial is not None
    budgets = {}
    for iterations in (0, 100, 500, 2000):
        started = time.perf_counter()
        solution = optimize_fixed_assignments(
            initial_source,
            lengths,
            savings,
            seed=args.seed,
            iterations=iterations,
        )
        budgets[str(iterations)] = {
            "runtime_ms": round(1000.0 * (time.perf_counter() - started), 3),
            "co_cut_benefit_mm": solution[0]["co_cut_benefit_mm"],
            "switches": solution[0]["switches"],
        }

    report = {
        "ok": (
            mixed_total == 21.0
            and {b["stock_length_mm"] for b in mixed} == {10.0, 11.0}
            and dp_value == brute_value
            and budgets["2000"]["co_cut_benefit_mm"]
            >= budgets["0"]["co_cut_benefit_mm"]
        ),
        "seed": args.seed,
        "units": "synthetic length units; runtime ms",
        "mixed_stock": {
            "objective": mixed_total,
            "stock_lengths": [b["stock_length_mm"] for b in mixed],
            "runtime_ms": round(mixed_ms, 3),
        },
        "orientation": {
            "dp_value": dp_value,
            "brute_value": brute_value,
            "dp_runtime_ms": round(dp_ms, 6),
            "brute_runtime_ms": round(brute_ms, 6),
        },
        "alns_budgets": budgets,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
