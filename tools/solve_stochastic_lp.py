#!/usr/bin/env python3
"""Two-Stage Stochastic Linear Programming with Recourse Solver (OR-Tools GLOP).

Solves two-stage stochastic programming problems with recourse in extensive form:
* First-stage decisions: made before uncertainty is realized (e.g., crop planting area).
* Second-stage recourse: decisions taken after uncertainty unfolds (e.g., sales, purchases).
* Key Stochastic Indicators computed:
  - RP (Recourse Problem Expected Value / Extensive Form Optimum)
  - WS (Wait-and-See / Perfect Information Expected Value)
  - EEV (Expected result of Expected Value mean problem)
  - EVPI (Expected Value of Perfect Information: WS - RP)
  - VSS (Value of Stochastic Solution: RP - EEV)

Default benchmark:
Birge & Louveaux (1997) classic Farmer Problem with 3 weather scenarios (good, average, bad).
Known optima:
  RP = 108390.0
  First stage: wheat=170.0, corn=80.0, sugar_beets=250.0
  WS = 115405.56
  EEV = 107240.0
  EVPI = 7015.56
  VSS = 1150.0

Output follows the OR-Path "Numbers Truth" envelope (ADR-0002).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from ortools.linear_solver import pywraplp

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

DEFAULT_FIXTURE = _ROOT / "fixtures" / "benchmarks" / "stochastic" / "farmer_problem.json"
DEFAULT_SOLVER = "ortools-glop-stochastic"


def load_problem_data(path_or_dict: str | Path | dict[str, Any] | None = None) -> dict[str, Any]:
    """Load problem data from JSON file or dictionary."""
    if isinstance(path_or_dict, dict):
        return path_or_dict

    raw_path = str(path_or_dict or DEFAULT_FIXTURE)
    p = Path(raw_path)
    if not p.is_file():
        for base in (_ROOT, Path.cwd()):
            cand = base / raw_path
            if cand.is_file():
                p = cand
                break
    if not p.is_file():
        raise FileNotFoundError(f"Stochastic LP fixture not found: {raw_path}")

    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def solve_recourse_problem(data: dict[str, Any]) -> tuple[float, dict[str, float], float, float, list[dict[str, Any]]]:
    """Solve the extensive form Recourse Problem (RP) via OR-Tools GLOP."""
    solver = pywraplp.Solver.CreateSolver("GLOP")
    if not solver:
        raise RuntimeError("OR-Tools GLOP solver unavailable")

    crops = data["crops"]
    total_land = float(data["total_land_acres"])
    planting_cost = {c: float(data["planting_cost_per_acre"][c]) for c in crops}
    quota = float(data["sugar_beet_quota"])

    # First stage variables: land allocation (acres)
    x = {c: solver.NumVar(0.0, total_land, f"x_{c}") for c in crops}
    solver.Add(sum(x.values()) <= total_land)

    first_stage_cost_expr = sum(planting_cost[c] * x[c] for c in crops)

    scenarios = data["scenarios"]
    scen_records = []
    scen_rev_terms = []

    for idx, s in enumerate(scenarios):
        prob = float(s["probability"])
        yields = {c: float(s["yield_per_acre"][c]) for c in crops}

        ww = solver.NumVar(0.0, solver.infinity(), f"ww_{idx}")
        yw = solver.NumVar(0.0, solver.infinity(), f"yw_{idx}")
        wc = solver.NumVar(0.0, solver.infinity(), f"wc_{idx}")
        yc = solver.NumVar(0.0, solver.infinity(), f"yc_{idx}")
        wb1 = solver.NumVar(0.0, quota, f"wb1_{idx}")
        wb2 = solver.NumVar(0.0, solver.infinity(), f"wb2_{idx}")

        # Recourse balance constraints
        solver.Add(yields["wheat"] * x["wheat"] + yw - ww >= float(data["internal_demand"]["wheat"]))
        solver.Add(yields["corn"] * x["corn"] + yc - wc >= float(data["internal_demand"]["corn"]))
        solver.Add(wb1 + wb2 <= yields["sugar_beets"] * x["sugar_beets"])

        rev_expr = (
            float(data["selling_price"]["wheat"]) * ww
            + float(data["selling_price"]["corn"]) * wc
            + float(data["selling_price"]["sugar_beets_quota"]) * wb1
            + float(data["selling_price"]["sugar_beets_excess"]) * wb2
            - float(data["purchase_price"]["wheat"]) * yw
            - float(data["purchase_price"]["corn"]) * yc
        )
        scen_rev_terms.append(prob * rev_expr)
        scen_records.append((s, ww, yw, wc, yc, wb1, wb2))

    solver.Maximize(sum(scen_rev_terms) - first_stage_cost_expr)
    status = solver.Solve()

    if status != pywraplp.Solver.OPTIMAL:
        raise RuntimeError(f"GLOP failed to solve RP: status code {status}")

    rp_obj = round(float(solver.Objective().Value()), 4)
    first_stage_dec = {c: round(float(x[c].solution_value()), 4) for c in crops}
    f_cost = sum(planting_cost[c] * first_stage_dec[c] for c in crops)
    expected_rev = rp_obj + f_cost

    scenario_outputs = []
    for s, ww, yw, wc, yc, wb1, wb2 in scen_records:
        recourse_dict = {
            "scenario": s.get("name", "unnamed"),
            "probability": float(s["probability"]),
            "wheat_sold": round(float(ww.solution_value()), 4),
            "wheat_purchased": round(float(yw.solution_value()), 4),
            "corn_sold": round(float(wc.solution_value()), 4),
            "corn_purchased": round(float(yc.solution_value()), 4),
            "sugar_beets_quota_sold": round(float(wb1.solution_value()), 4),
            "sugar_beets_excess_sold": round(float(wb2.solution_value()), 4),
        }
        net_rev = (
            float(data["selling_price"]["wheat"]) * recourse_dict["wheat_sold"]
            + float(data["selling_price"]["corn"]) * recourse_dict["corn_sold"]
            + float(data["selling_price"]["sugar_beets_quota"]) * recourse_dict["sugar_beets_quota_sold"]
            + float(data["selling_price"]["sugar_beets_excess"]) * recourse_dict["sugar_beets_excess_sold"]
            - float(data["purchase_price"]["wheat"]) * recourse_dict["wheat_purchased"]
            - float(data["purchase_price"]["corn"]) * recourse_dict["corn_purchased"]
        )
        recourse_dict["scenario_net_revenue"] = round(net_rev, 4)
        recourse_dict["scenario_net_profit"] = round(net_rev - f_cost, 4)
        scenario_outputs.append(recourse_dict)

    return rp_obj, first_stage_dec, round(f_cost, 4), round(expected_rev, 4), scenario_outputs


def solve_wait_and_see(data: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    """Solve the Wait-and-See (WS) deterministic problem for each scenario."""
    crops = data["crops"]
    total_land = float(data["total_land_acres"])
    planting_cost = {c: float(data["planting_cost_per_acre"][c]) for c in crops}
    quota = float(data["sugar_beet_quota"])

    ws_expected = 0.0
    ws_scenarios = []

    for s in data["scenarios"]:
        prob = float(s["probability"])
        yields = {c: float(s["yield_per_acre"][c]) for c in crops}

        solver = pywraplp.Solver.CreateSolver("GLOP")
        x = {c: solver.NumVar(0.0, total_land, f"x_{c}") for c in crops}
        solver.Add(sum(x.values()) <= total_land)
        f_cost = sum(planting_cost[c] * x[c] for c in crops)

        ww = solver.NumVar(0.0, solver.infinity(), "ww")
        yw = solver.NumVar(0.0, solver.infinity(), "yw")
        wc = solver.NumVar(0.0, solver.infinity(), "wc")
        yc = solver.NumVar(0.0, solver.infinity(), "yc")
        wb1 = solver.NumVar(0.0, quota, "wb1")
        wb2 = solver.NumVar(0.0, solver.infinity(), "wb2")

        solver.Add(yields["wheat"] * x["wheat"] + yw - ww >= float(data["internal_demand"]["wheat"]))
        solver.Add(yields["corn"] * x["corn"] + yc - wc >= float(data["internal_demand"]["corn"]))
        solver.Add(wb1 + wb2 <= yields["sugar_beets"] * x["sugar_beets"])

        rev = (
            float(data["selling_price"]["wheat"]) * ww
            + float(data["selling_price"]["corn"]) * wc
            + float(data["selling_price"]["sugar_beets_quota"]) * wb1
            + float(data["selling_price"]["sugar_beets_excess"]) * wb2
            - float(data["purchase_price"]["wheat"]) * yw
            - float(data["purchase_price"]["corn"]) * yc
        )
        solver.Maximize(rev - f_cost)
        st = solver.Solve()
        if st != pywraplp.Solver.OPTIMAL:
            raise RuntimeError(f"GLOP WS solve failed for scenario {s.get('name')}")

        scen_profit = float(solver.Objective().Value())
        ws_expected += prob * scen_profit
        ws_scenarios.append({
            "scenario": s.get("name"),
            "probability": prob,
            "optimal_profit": round(scen_profit, 4),
            "optimal_acres": {c: round(float(x[c].solution_value()), 4) for c in crops},
        })

    return round(ws_expected, 4), ws_scenarios


def solve_expected_value_and_eev(data: dict[str, Any]) -> tuple[dict[str, float], float]:
    """Solve the EV mean-scenario problem, then compute EEV."""
    crops = data["crops"]
    total_land = float(data["total_land_acres"])
    planting_cost = {c: float(data["planting_cost_per_acre"][c]) for c in crops}
    quota = float(data["sugar_beet_quota"])

    # 1. Compute mean yields
    mean_yields = {c: 0.0 for c in crops}
    for s in data["scenarios"]:
        prob = float(s["probability"])
        for c in crops:
            mean_yields[c] += prob * float(s["yield_per_acre"][c])

    # 2. Solve deterministic EV problem with mean yields
    ev_solver = pywraplp.Solver.CreateSolver("GLOP")
    x_ev = {c: ev_solver.NumVar(0.0, total_land, f"x_{c}") for c in crops}
    ev_solver.Add(sum(x_ev.values()) <= total_land)
    f_cost_ev = sum(planting_cost[c] * x_ev[c] for c in crops)

    ww = ev_solver.NumVar(0.0, ev_solver.infinity(), "ww")
    yw = ev_solver.NumVar(0.0, ev_solver.infinity(), "yw")
    wc = ev_solver.NumVar(0.0, ev_solver.infinity(), "wc")
    yc = ev_solver.NumVar(0.0, ev_solver.infinity(), "yc")
    wb1 = ev_solver.NumVar(0.0, quota, "wb1")
    wb2 = ev_solver.NumVar(0.0, ev_solver.infinity(), "wb2")

    ev_solver.Add(mean_yields["wheat"] * x_ev["wheat"] + yw - ww >= float(data["internal_demand"]["wheat"]))
    ev_solver.Add(mean_yields["corn"] * x_ev["corn"] + yc - wc >= float(data["internal_demand"]["corn"]))
    ev_solver.Add(wb1 + wb2 <= mean_yields["sugar_beets"] * x_ev["sugar_beets"])

    rev_ev = (
        float(data["selling_price"]["wheat"]) * ww
        + float(data["selling_price"]["corn"]) * wc
        + float(data["selling_price"]["sugar_beets_quota"]) * wb1
        + float(data["selling_price"]["sugar_beets_excess"]) * wb2
        - float(data["purchase_price"]["wheat"]) * yw
        - float(data["purchase_price"]["corn"]) * yc
    )
    ev_solver.Maximize(rev_ev - f_cost_ev)
    st = ev_solver.Solve()
    if st != pywraplp.Solver.OPTIMAL:
        raise RuntimeError("GLOP EV solve failed")

    x_mean = {c: round(float(x_ev[c].solution_value()), 4) for c in crops}

    # 3. Fix first-stage decisions to x_mean and evaluate expected recourse revenue (EEV)
    eev_solver = pywraplp.Solver.CreateSolver("GLOP")
    f_cost_fixed = sum(planting_cost[c] * x_mean[c] for c in crops)
    scen_eev_revs = []

    for idx, s in enumerate(data["scenarios"]):
        prob = float(s["probability"])
        yields = {c: float(s["yield_per_acre"][c]) for c in crops}

        ww_s = eev_solver.NumVar(0.0, eev_solver.infinity(), f"ww_{idx}")
        yw_s = eev_solver.NumVar(0.0, eev_solver.infinity(), f"yw_{idx}")
        wc_s = eev_solver.NumVar(0.0, eev_solver.infinity(), f"wc_{idx}")
        yc_s = eev_solver.NumVar(0.0, eev_solver.infinity(), f"yc_{idx}")
        wb1_s = eev_solver.NumVar(0.0, quota, f"wb1_{idx}")
        wb2_s = eev_solver.NumVar(0.0, eev_solver.infinity(), f"wb2_{idx}")

        eev_solver.Add(yields["wheat"] * x_mean["wheat"] + yw_s - ww_s >= float(data["internal_demand"]["wheat"]))
        eev_solver.Add(yields["corn"] * x_mean["corn"] + yc_s - wc_s >= float(data["internal_demand"]["corn"]))
        eev_solver.Add(wb1_s + wb2_s <= yields["sugar_beets"] * x_mean["sugar_beets"])

        rev_s = (
            float(data["selling_price"]["wheat"]) * ww_s
            + float(data["selling_price"]["corn"]) * wc_s
            + float(data["selling_price"]["sugar_beets_quota"]) * wb1_s
            + float(data["selling_price"]["sugar_beets_excess"]) * wb2_s
            - float(data["purchase_price"]["wheat"]) * yw_s
            - float(data["purchase_price"]["corn"]) * yc_s
        )
        scen_eev_revs.append(prob * rev_s)

    eev_solver.Maximize(sum(scen_eev_revs) - f_cost_fixed)
    st = eev_solver.Solve()
    if st != pywraplp.Solver.OPTIMAL:
        raise RuntimeError("GLOP EEV evaluation solve failed")

    eev_val = round(float(eev_solver.Objective().Value()), 4)
    return x_mean, eev_val


def solve_stochastic_lp(
    path_or_dict: str | Path | dict[str, Any] | None = None,
    solver_name: str = DEFAULT_SOLVER,
) -> dict[str, Any]:
    """Solve the Two-Stage Stochastic LP and compute complete stochastic indicators."""
    t0 = time.perf_counter()
    data = load_problem_data(path_or_dict)
    problem_id = data.get("name", "farmer_problem")

    # 1. Recourse Problem (Extensive Form)
    rp, first_stage_dec, first_stage_cost, exp_rev, scenarios = solve_recourse_problem(data)

    # 2. Wait-and-See (WS)
    ws, ws_scenarios = solve_wait_and_see(data)

    # 3. Expected Value (EV) & EEV
    x_mean, eev = solve_expected_value_and_eev(data)

    # 4. Stochastic indicators
    evpi = round(ws - rp, 4)
    vss = round(rp - eev, 4)

    dur = time.perf_counter() - t0

    envelope = {
        "problem_id": problem_id,
        "problem_class": "stochastic_lp",
        "mode": "stochastic_lp",
        "status": "OPTIMAL",
        "objective": rp,
        "solver": solver_name,
        "source": "tools/solve_stochastic_lp.py",
        "total_land_acres": float(data.get("total_land_acres", 500.0)),
        "first_stage_cost": first_stage_cost,
        "expected_second_stage_revenue": exp_rev,
        "first_stage_decision": first_stage_dec,
        "mean_scenario_decision": x_mean,
        "stochastic_indicators": {
            "RP": rp,
            "WS": ws,
            "EEV": eev,
            "EVPI": evpi,
            "VSS": vss,
        },
        "scenarios": scenarios,
        "wait_and_see_scenarios": ws_scenarios,
        "raw_problem": data,
        "meta": {
            "solve_time_sec": round(dur, 4),
            "method": "extensive_form_glop",
            "known_optimal": data.get("known_optimal", {}),
        },
    }
    return envelope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OR-Path Two-Stage Stochastic LP Solver")
    parser.add_argument("problem_id", nargs="?", default="farmer_problem", help="Problem id or fixture name")
    parser.add_argument("--fixture", type=Path, default=None, help="Path to custom stochastic problem JSON")
    parser.add_argument("--output", type=Path, default=None, help="Path to write solution envelope JSON")
    args = parser.parse_args(argv)

    if args.fixture:
        fixture_path = args.fixture
    elif args.problem_id in ("farmer_problem", "farmer", "default", None):
        fixture_path = DEFAULT_FIXTURE
    elif Path(args.problem_id).is_file():
        fixture_path = Path(args.problem_id)
    else:
        cand = Path(__file__).resolve().parent.parent / "fixtures" / "benchmarks" / "stochastic" / f"{args.problem_id}.json"
        fixture_path = cand if cand.is_file() else DEFAULT_FIXTURE
    res = solve_stochastic_lp(fixture_path)
    output_text = json.dumps(res, ensure_ascii=False, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_text + "\n", encoding="utf-8")

    print(output_text)
    return 0 if res.get("status") == "OPTIMAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
