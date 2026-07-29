#!/usr/bin/env python3
"""Improve B-Q2 30x30: try pure tetromino cover (lb=225) then general."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from solve_polyomino import Q2_CAPS_30x30, solve_cover  # noqa: E402


def main() -> int:
    out_dir = Path(__file__).resolve().parents[1] / "outputs" / "b-polyomino"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []

    # Attempt 1: only tetrominoes, min count (hope 225)
    print("30x30 attempt1: tetromino-only...", flush=True)
    caps_t4 = {k: Q2_CAPS_30x30[k] for k in ["S", "I4", "T4", "L4", "Z4"]}
    d1 = solve_cover(
        30,
        30,
        piece_ids=["S", "I4", "T4", "L4", "Z4"],
        max_counts=caps_t4,
        time_limit_s=300.0,
        reflect=True,
        num_workers=8,
    )
    d1["problem_id"] = "polyomino_b_q2_30x30_tetromino_only"
    results.append(d1)
    print(
        "att1",
        d1.get("status"),
        d1.get("objective"),
        d1.get("meta", {}).get("proven_optimal"),
        d1.get("meta", {}).get("wall_time_s"),
        flush=True,
    )
    (out_dir / "q2-30x30-tetromino-only.json").write_text(
        json.dumps(d1, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Attempt 2: full inventory longer
    print("30x30 attempt2: full caps 400s...", flush=True)
    d2 = solve_cover(
        30,
        30,
        piece_ids=["M", "D", "L3", "I3", "S", "I4", "T4", "L4", "Z4"],
        max_counts=Q2_CAPS_30x30,
        time_limit_s=400.0,
        reflect=True,
        num_workers=8,
    )
    d2["problem_id"] = "polyomino_b_q2_30x30"
    results.append(d2)
    print(
        "att2",
        d2.get("status"),
        d2.get("objective"),
        d2.get("meta", {}).get("proven_optimal"),
        d2.get("meta", {}).get("objective_bound"),
        d2.get("meta", {}).get("wall_time_s"),
        flush=True,
    )
    (out_dir / "q2-30x30-solution.json").write_text(
        json.dumps(d2, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # pick best
    def key(d):
        st = d.get("status")
        ok = st in {"OPTIMAL", "FEASIBLE"}
        obj = d.get("objective") if ok and d.get("objective", -1) >= 0 else 10**9
        proven = 0 if d.get("meta", {}).get("proven_optimal") else 1
        return (proven, obj)

    best = min(results, key=key)
    summary = {
        "best_problem_id": best.get("problem_id"),
        "status": best.get("status"),
        "objective": best.get("objective"),
        "proven_optimal": best.get("meta", {}).get("proven_optimal"),
        "objective_bound": best.get("meta", {}).get("objective_bound"),
        "piece_counts": best.get("piece_counts"),
        "attempts": [
            {
                "id": r.get("problem_id"),
                "status": r.get("status"),
                "objective": r.get("objective"),
                "proven": r.get("meta", {}).get("proven_optimal"),
                "bound": r.get("meta", {}).get("objective_bound"),
                "time": r.get("meta", {}).get("wall_time_s"),
            }
            for r in results
        ],
    }
    (out_dir / "q2-30x30-best-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("BEST", json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if best.get("status") in {"OPTIMAL", "FEASIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
