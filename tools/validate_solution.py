#!/usr/bin/env python3
"""Validate solution.json against fixture problem data via recompute."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_paths import fixture_dir, fixture_file  # noqa: E402

EPS = 1e-6


def _num_eq(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= EPS or (
        abs(float(a) - float(b)) / max(1.0, abs(float(b))) <= 1e-9
    )


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be object")
    return data


def _checks_envelope(sol: dict, pc: str) -> list[dict]:
    checks = []
    required = ["problem_id", "status", "objective", "solver", "source"]
    missing = [k for k in required if k not in sol]
    checks.append(
        {
            "name": "envelope",
            "ok": not missing and sol.get("status")
            in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "ERROR"},
            "detail": f"missing={missing}" if missing else None,
        }
    )
    if pc == "shortest_path":
        checks.append(
            {
                "name": "shape_path",
                "ok": bool(sol.get("path")),
                "detail": None if sol.get("path") else "path required",
            }
        )
    elif pc == "tsp":
        checks.append(
            {
                "name": "shape_tour",
                "ok": bool(sol.get("tour")),
                "detail": None if sol.get("tour") else "tour required",
            }
        )
    elif pc == "vrp":
        checks.append(
            {
                "name": "shape_routes",
                "ok": bool(sol.get("routes")),
                "detail": None if sol.get("routes") else "routes required",
            }
        )
    return checks


def _validate_sp(problem_id: str, sol: dict) -> list[dict]:
    checks: list[dict] = []
    g = _load(fixture_file(problem_id, "graph.json"))
    edges = {(e["u"], e["v"]): float(e["w"]) for e in g.get("edges") or []}
    path = list(sol.get("path") or [])
    if len(path) < 2:
        checks.append({"name": "feasibility", "ok": False, "detail": "path too short"})
        return checks
    total = 0.0
    ok = True
    for a, b in zip(path, path[1:]):
        if (a, b) not in edges:
            ok = False
            checks.append(
                {
                    "name": "feasibility",
                    "ok": False,
                    "detail": f"missing edge {a}->{b}",
                }
            )
            break
        total += edges[(a, b)]
    if ok:
        checks.append({"name": "feasibility", "ok": True})
        obj = float(sol["objective"])
        checks.append(
            {
                "name": "recompute_objective",
                "ok": _num_eq(total, obj),
                "expected": total if float(total).is_integer() else total,
                "got": sol["objective"],
            }
        )
    return checks


def _matrix_and_labels(problem_id: str) -> tuple[list[list[float]], list[str]]:
    d = fixture_dir(problem_id)
    if (d / "distance_matrix.json").is_file():
        raw = _load(d / "distance_matrix.json")
        matrix = raw["matrix"] if "matrix" in raw else raw
        labels = raw.get("labels") or [str(i) for i in range(len(matrix))]
        return matrix, [str(x) for x in labels]
    coords = _load(d / "coords.json")
    if isinstance(coords, dict):
        coords = coords["coords"]
    labels = [str(c.get("id", i)) for i, c in enumerate(coords)]
    n = len(coords)
    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dx = float(coords[i]["x"]) - float(coords[j]["x"])
            dy = float(coords[i]["y"]) - float(coords[j]["y"])
            mat[i][j] = float(int(round(math.hypot(dx, dy))))
    return mat, labels


def _validate_tsp(problem_id: str, sol: dict) -> list[dict]:
    checks: list[dict] = []
    matrix, labels = _matrix_and_labels(problem_id)
    idx = {lab: i for i, lab in enumerate(labels)}
    tour = [str(x) for x in (sol.get("tour") or [])]
    if len(tour) < 2 or tour[0] != tour[-1]:
        checks.append(
            {
                "name": "feasibility",
                "ok": False,
                "detail": "tour must start and end at same node",
            }
        )
        return checks
    core = tour[:-1]
    if sorted(core) != sorted(labels):
        checks.append(
            {
                "name": "feasibility",
                "ok": False,
                "detail": f"tour must visit each city once; got {core}",
            }
        )
        return checks
    total = 0.0
    for a, b in zip(tour, tour[1:]):
        total += float(matrix[idx[a]][idx[b]])
    checks.append({"name": "feasibility", "ok": True})
    checks.append(
        {
            "name": "recompute_objective",
            "ok": _num_eq(total, float(sol["objective"])),
            "expected": int(total) if float(total).is_integer() else total,
            "got": sol["objective"],
        }
    )
    return checks


def _validate_vrp(problem_id: str, sol: dict) -> list[dict]:
    checks: list[dict] = []
    data = _load(fixture_file(problem_id, "locations.json"))
    locations = data["locations"]
    labels = [str(loc["id"]) for loc in locations]
    depot = str(data.get("depot", labels[0]))
    capacities = [int(c) for c in data["capacities"]]
    vehicle_count = int(data["vehicle_count"])
    demands_raw = data["demands"]
    if isinstance(demands_raw, dict):
        demands = {str(k): int(v) for k, v in demands_raw.items()}
    else:
        demands = {labels[i]: int(demands_raw[i]) for i in range(len(labels))}

    if "distance_matrix" in data:
        matrix = data["distance_matrix"]
    else:
        coords = [{"x": loc["x"], "y": loc["y"]} for loc in locations]
        n = len(coords)
        matrix = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                dx = float(coords[i]["x"]) - float(coords[j]["x"])
                dy = float(coords[i]["y"]) - float(coords[j]["y"])
                matrix[i][j] = int(round(math.hypot(dx, dy)))
    idx = {lab: i for i, lab in enumerate(labels)}

    tw_raw = data.get("time_windows") or {}
    st_raw = data.get("service_times") or {}
    has_tw = bool(tw_raw)
    tw: dict[str, tuple[int, int]] = {}
    st: dict[str, int] = {}
    if has_tw:
        for lab in labels:
            if isinstance(tw_raw, dict) and lab in tw_raw:
                lo, hi = tw_raw[lab]
                tw[lab] = (int(lo), int(hi))
            else:
                tw[lab] = (0, 10**9)
            st[lab] = int(st_raw.get(lab, 0)) if isinstance(st_raw, dict) else 0

    routes = sol.get("routes") or []
    checks.append(
        {
            "name": "vehicle_count_meta",
            "ok": vehicle_count >= 2,
            "detail": f"fixture vehicle_count={vehicle_count}",
        }
    )

    customers = [lab for lab in labels if lab != depot]
    seen: list[str] = []
    total = 0.0
    cap_ok = True
    tw_ok = True
    for ri, route in enumerate(routes):
        r = [str(x) for x in route]
        load = 0
        for node in r:
            if node == depot:
                continue
            load += demands.get(node, 0)
            seen.append(node)
        cap = capacities[min(ri, len(capacities) - 1)]
        if load > cap:
            cap_ok = False
            checks.append(
                {
                    "name": "capacity",
                    "ok": False,
                    "detail": f"route {ri} load {load} > cap {cap}",
                }
            )
        for a, b in zip(r, r[1:]):
            total += float(matrix[idx[a]][idx[b]])

        if has_tw and len(r) >= 2:
            # Simulate: start at depot at time max(0, ready_depot); wait allowed.
            t = float(tw[depot][0])
            for a, b in zip(r, r[1:]):
                travel = float(matrix[idx[a]][idx[b]])
                # leave a after service (depot service 0)
                # time at arrival to b
                arrive = t + travel
                ready, due = tw[b]
                start_service = max(arrive, float(ready))
                if b != depot and start_service > float(due) + 1e-9:
                    tw_ok = False
                    checks.append(
                        {
                            "name": "time_windows",
                            "ok": False,
                            "detail": (
                                f"route {ri} node {b}: start_service={start_service} "
                                f"> due={due} (arrive={arrive})"
                            ),
                        }
                    )
                # after service at b
                t = start_service + float(st.get(b, 0))
                # also ensure a started within window when leaving (except pure start)
                if a != depot or r.index(a) != 0:
                    pass

    if cap_ok:
        checks.append({"name": "capacity", "ok": True})

    if has_tw and tw_ok:
        checks.append({"name": "time_windows", "ok": True})
    elif not has_tw:
        checks.append(
            {
                "name": "time_windows",
                "ok": True,
                "detail": "no time_windows in fixture (T2-style CVRP)",
            }
        )

    if sorted(seen) != sorted(customers) or len(seen) != len(customers):
        checks.append(
            {
                "name": "feasibility",
                "ok": False,
                "detail": f"customers coverage bad seen={seen} need={customers}",
            }
        )
    else:
        checks.append({"name": "feasibility", "ok": True})

    checks.append(
        {
            "name": "recompute_objective",
            "ok": _num_eq(total, float(sol["objective"])),
            "expected": int(total) if float(total).is_integer() else total,
            "got": sol["objective"],
        }
    )
    return checks


def validate(problem_id: str, solution: dict, gold: dict | None = None) -> dict:
    pc = str(
        solution.get("problem_class")
        or (gold or {}).get("problem_class")
        or "shortest_path"
    )
    checks = _checks_envelope(solution, pc)
    if solution.get("status") in {"INFEASIBLE", "ERROR"}:
        report = {
            "ok": False,
            "problem_id": problem_id,
            "problem_class": pc,
            "checks": checks,
            "errors": [f"status={solution.get('status')}"],
        }
        return report

    if pc == "shortest_path":
        checks.extend(_validate_sp(problem_id, solution))
    elif pc == "tsp":
        checks.extend(_validate_tsp(problem_id, solution))
    elif pc == "vrp":
        checks.extend(_validate_vrp(problem_id, solution))
    else:
        checks.append(
            {"name": "problem_class", "ok": False, "detail": f"unknown class {pc}"}
        )

    if gold and "objective" in gold and solution.get("status") in {
        "OPTIMAL",
        "FEASIBLE",
    }:
        gap = abs(float(solution["objective"]) - float(gold["objective"]))
        checks.append(
            {
                "name": "gold_gap",
                "ok": _num_eq(solution["objective"], gold["objective"]),
                "expected": gold["objective"],
                "got": solution["objective"],
                "detail": f"gap={gap}",
            }
        )

    errors = [
        c.get("detail") or c["name"]
        for c in checks
        if not c.get("ok")
    ]
    ok = all(c.get("ok") for c in checks)
    return {
        "ok": ok,
        "problem_id": problem_id,
        "problem_class": pc,
        "checks": checks,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate OR-Path solution JSON")
    parser.add_argument("--problem-id", required=True)
    parser.add_argument("--solution", type=Path, required=True)
    parser.add_argument("--gold", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    sol = _load(args.solution)
    gold = None
    if args.gold and args.gold.is_file():
        gold = _load(args.gold)
    else:
        try:
            gold = _load(fixture_file(args.problem_id, "solution.json"))
        except FileNotFoundError:
            gold = None
    report = validate(args.problem_id, sol, gold)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
