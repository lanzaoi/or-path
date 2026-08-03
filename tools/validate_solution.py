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


def _validate_tube(_problem_id: str, sol: dict) -> list[dict]:
    """Validate tube_cut / cutting_stock envelope from solve_tube_cut_b2026.

    Does not re-solve the cutting problem. Checks:
    - envelope already applied by caller
    - questions.q1.. present with stocks/batches
    - top objective matches primary question total (q3 preferred, else q1)
    - source/solver claim tube tool (not SP mock gold)
    """
    checks: list[dict] = []
    pc = str(sol.get("problem_class") or "").lower()
    checks.append(
        {
            "name": "problem_class",
            "ok": pc in {"tube_cut", "tube", "tube_bfd", "cutting_stock", "cut_stock"},
            "detail": None if pc else "missing problem_class",
        }
    )
    src = str(sol.get("source") or "")
    solver = str(sol.get("solver") or "")
    tube_src = "tube" in src.lower() or "tube" in solver.lower() or "solve_tube" in src
    checks.append(
        {
            "name": "tube_source",
            "ok": tube_src,
            "detail": None if tube_src else f"source/solver not tube: {src!r}/{solver!r}",
        }
    )
    qs = sol.get("questions")
    if not isinstance(qs, dict) or not qs:
        checks.append(
            {"name": "shape_questions", "ok": False, "detail": "questions object required"}
        )
        return checks
    checks.append({"name": "shape_questions", "ok": True})

    for name in ("q1", "q2", "q3"):
        q = qs.get(name)
        if not isinstance(q, dict):
            checks.append(
                {"name": f"shape_{name}", "ok": False, "detail": f"{name} missing"}
            )
            continue
        stocks = q.get("stocks")
        ok_stocks = isinstance(stocks, list) and len(stocks) >= 1
        checks.append(
            {
                "name": f"shape_{name}_stocks",
                "ok": ok_stocks,
                "detail": None if ok_stocks else f"{name}.stocks empty/missing",
            }
        )
        st = str(q.get("status") or "").upper()
        checks.append(
            {
                "name": f"status_{name}",
                "ok": st in {"FEASIBLE", "OPTIMAL", "OK", ""},
                "detail": None if st in {"FEASIBLE", "OPTIMAL", "OK", ""} else f"{name}.status={st}",
            }
        )
        # light recompute: sum stock_length ≈ total_stock_length_mm
        if ok_stocks and "total_stock_length_mm" in q:
            try:
                total = sum(float(s.get("stock_length_mm") or 0) for s in stocks if isinstance(s, dict))
                declared = float(q["total_stock_length_mm"])
                checks.append(
                    {
                        "name": f"recompute_{name}_stock_sum",
                        "ok": _num_eq(total, declared),
                        "expected": declared,
                        "got": total,
                    }
                )
            except (TypeError, ValueError) as exc:
                checks.append(
                    {
                        "name": f"recompute_{name}_stock_sum",
                        "ok": False,
                        "detail": str(exc),
                    }
                )

    q4 = qs.get("q4")
    if isinstance(q4, dict):
        batches = q4.get("batches")
        ok_b = isinstance(batches, list) and len(batches) >= 1
        checks.append(
            {
                "name": "shape_q4_batches",
                "ok": ok_b,
                "detail": None if ok_b else "q4.batches empty/missing",
            }
        )
    else:
        checks.append({"name": "shape_q4", "ok": False, "detail": "q4 missing"})

    # primary objective = q3 total if present else q1 (matches solve_dispatch envelope)
    primary = None
    if isinstance(qs.get("q3"), dict) and "total_stock_length_mm" in qs["q3"]:
        primary = float(qs["q3"]["total_stock_length_mm"])
        primary_name = "q3.total_stock_length_mm"
    elif isinstance(qs.get("q1"), dict) and "total_stock_length_mm" in qs["q1"]:
        primary = float(qs["q1"]["total_stock_length_mm"])
        primary_name = "q1.total_stock_length_mm"
    else:
        primary_name = "missing"
    if primary is None:
        checks.append(
            {
                "name": "recompute_objective",
                "ok": False,
                "detail": "no q1/q3 total_stock_length_mm",
            }
        )
    else:
        try:
            obj = float(sol["objective"])
            checks.append(
                {
                    "name": "recompute_objective",
                    "ok": _num_eq(obj, primary),
                    "expected": primary,
                    "got": sol.get("objective"),
                    "detail": f"primary={primary_name}",
                }
            )
        except (TypeError, ValueError, KeyError) as exc:
            checks.append(
                {"name": "recompute_objective", "ok": False, "detail": str(exc)}
            )

    # heuristic honesty: not proven optimal unless meta says so
    meta = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
    if meta.get("proven_optimal") is True and str(sol.get("status")).upper() == "OPTIMAL":
        checks.append(
            {
                "name": "optimality_claim",
                "ok": False,
                "detail": "tube BFD must not claim proven_optimal OPTIMAL",
            }
        )
    else:
        checks.append({"name": "optimality_claim", "ok": True})

    return checks


def validate(problem_id: str, solution: dict, gold: dict | None = None) -> dict:
    pc = str(
        solution.get("problem_class")
        or (gold or {}).get("problem_class")
        or "shortest_path"
    ).lower()
    # aliases
    if pc in {"tube", "tube_bfd", "cutting_stock", "cut_stock"}:
        pc_norm = "tube_cut"
    else:
        pc_norm = pc

    checks = _checks_envelope_tube(solution) if pc_norm == "tube_cut" else _checks_envelope(solution, pc_norm)

    if solution.get("status") in {"INFEASIBLE", "ERROR", "BLOCKED"}:
        report = {
            "ok": False,
            "problem_id": problem_id,
            "problem_class": pc_norm,
            "checks": checks,
            "errors": [f"status={solution.get('status')}"],
        }
        return report

    if pc_norm == "shortest_path":
        checks.extend(_validate_sp(problem_id, solution))
    elif pc_norm == "tsp":
        checks.extend(_validate_tsp(problem_id, solution))
    elif pc_norm == "vrp":
        checks.extend(_validate_vrp(problem_id, solution))
    elif pc_norm == "tube_cut":
        checks.extend(_validate_tube(problem_id, solution))
    else:
        checks.append(
            {"name": "problem_class", "ok": False, "detail": f"unknown class {pc}"}
        )

    if gold and "objective" in gold and solution.get("status") in {
        "OPTIMAL",
        "FEASIBLE",
    }:
        # only gold-gap for fixture classes, not tube contest heuristics unless gold provided intentionally
        if pc_norm != "tube_cut" or gold.get("problem_class"):
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
        "problem_class": pc_norm,
        "checks": checks,
        "errors": errors,
    }


def _checks_envelope_tube(sol: dict) -> list[dict]:
    required = ["problem_id", "status", "objective", "solver", "source"]
    missing = [k for k in required if k not in sol]
    return [
        {
            "name": "envelope",
            "ok": not missing
            and str(sol.get("status") or "").upper()
            in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "ERROR", "BLOCKED"},
            "detail": f"missing={missing}" if missing else None,
        }
    ]


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
