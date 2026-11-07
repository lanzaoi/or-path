"""Tests for Industrial Microgrid Dispatch & Rolling MPC Solver and Validator."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TOOLS))

from orpath.domain_registry import (
    CANONICAL_CLASSES,
    CLASS_ALIASES,
    REGISTERED_SOLVE_CLASSES,
    MICROGRID_SCHEMA_KEYS,
    is_known_class,
    is_registered_solve_class,
    normalize_problem_class,
)
from tools.gate_schema import check_schema
from tools.solve_microgrid import (
    DEFAULT_CASE_DIR,
    INITIAL_SOC_KWH,
    MAX_ENERGY_PER_STEP,
    SOC_MAX_KWH,
    SOC_MIN_KWH,
    interpolate_hourly_to_10min,
    simulate_realtime_day,
    solve_day_lp,
    solve_q1,
)
from tools.validators.microgrid_dispatch import validate_microgrid


def test_domain_registry_and_aliases():
    assert "microgrid_dispatch" in CANONICAL_CLASSES
    assert "microgrid_dispatch" in REGISTERED_SOLVE_CLASSES

    for alias in ("microgrid", "energy_storage", "smart_grid", "microgrid_mpc", "power_dispatch"):
        assert normalize_problem_class(alias) == "microgrid_dispatch"
        assert is_known_class(alias)
        assert is_registered_solve_class(alias)

    assert "battery" in MICROGRID_SCHEMA_KEYS
    assert "subproblems" in MICROGRID_SCHEMA_KEYS


def test_guess_intake_domain():
    from scripts.guess_intake_domain import main as guess_main

    test_cases = [
        ("微网与外部电网电力调控策略.pdf", "microgrid"),
        ("附件1_微电网负荷与储能调度.xlsx", "microgrid"),
        ("smart_grid_mpc_case.json", "microgrid"),
    ]
    for filename, expected in test_cases:
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "guess_intake_domain.py"), filename],
            capture_output=True,
            text=True,
        )
        assert r.stdout.strip() == expected


def test_schema_models_and_gate(tmp_path: Path):
    schema = {
        "problem_id": "microgrid_cumcm2026_c",
        "problem_class": "microgrid_dispatch",
        "battery": {
            "capacity_kwh": 12000.0,
            "max_power_kw": 5000.0,
            "soc_min_kwh": 1200.0,
            "soc_max_kwh": 10800.0,
            "efficiency": 0.90,
            "initial_soc_kwh": 6000.0,
        },
        "intervals_per_day": 144,
        "subproblems": ["q1", "q2", "q3", "q4_2", "q4_3"],
        "constraints": ["power_balance", "soc_limits", "charge_discharge_power_limits"],
        "preferred_solve_mode": "microgrid",
    }
    errors = check_schema(schema)
    assert not errors, f"Unexpected schema errors: {errors}"

    # Negative test: missing structural keys
    bad_schema = {"problem_id": "mg_bad", "problem_class": "microgrid_dispatch"}
    bad_errs = check_schema(bad_schema)
    assert any("requires structural keys" in e for e in bad_errs)


def test_interpolate_hourly_to_10min():
    hourly = [float(h) for h in range(1, 25)]
    interpolated = interpolate_hourly_to_10min(hourly, start_val=0.0)
    assert len(interpolated) == 144
    assert interpolated[0] == pytest.approx(1.0 / 6.0)
    assert interpolated[5] == pytest.approx(1.0)
    assert interpolated[-1] == pytest.approx(24.0)


def test_solve_day_lp_physics():
    # 144 intervals synthetic problem
    prices = [0.4 if (t < 36 or t > 120) else 1.2 for t in range(144)]
    loads = [600.0] * 144  # 600 kWh per 10min = 3600 kW
    pvs = [800.0 if 40 <= t <= 80 else 0.0 for t in range(144)]

    sol = solve_day_lp(
        prices=prices,
        loads_kwh=loads,
        pvs_kwh=pvs,
        soc_start=6000.0,
        target_soc_end=6000.0,
    )

    assert sol["status"] == "OPTIMAL"
    assert len(sol["purchase_kwh"]) == 144
    assert len(sol["soc_kwh"]) == 144
    assert sol["soc_kwh"][-1] == pytest.approx(6000.0, abs=1e-2)

    # Power balance & bounds
    for t in range(144):
        delivered = sol["purchase_kwh"][t] + pvs[t] + sol["discharge_kwh"][t] - sol["charge_kwh"][t]
        assert delivered >= loads[t] - 1e-4
        assert SOC_MIN_KWH - 1e-4 <= sol["soc_kwh"][t] <= SOC_MAX_KWH + 1e-4
        assert sol["charge_kwh"][t] <= MAX_ENERGY_PER_STEP + 1e-4
        assert sol["discharge_kwh"][t] <= MAX_ENERGY_PER_STEP + 1e-4


def test_realtime_emergency_simulation():
    # Scenario where planned purchase + PV falls short of load
    prices = [0.5] * 144
    plan_buy = [100.0] * 144
    actual_load = [1200.0] * 144  # High load
    actual_pv = [0.0] * 144

    rt = simulate_realtime_day(
        plan_purchase_kwh=plan_buy,
        actual_load_kwh=actual_load,
        actual_pv_kwh=actual_pv,
        prices=prices,
        soc_start=2000.0,
    )

    # Battery can only discharge down to 1200
    assert rt["emerg_cost"] > 0.0
    assert rt["total_emerg_kwh"] > 0.0
    assert rt["end_soc"] >= SOC_MIN_KWH - 1e-4


def test_validators_physics_and_economics():
    # Test valid Q1 solution
    prices = [0.4] * 144
    loads = [500.0] * 144
    pvs = [0.0] * 144

    q1_sol = solve_day_lp(
        prices=prices,
        loads_kwh=loads,
        pvs_kwh=pvs,
        soc_start=6000.0,
        target_soc_end=6000.0,
    )

    valid_sol = {
        "status": "OPTIMAL",
        "objective": q1_sol["total_cost"],
        "subproblems": {
            "q1": {
                **q1_sol,
                "total_cost": q1_sol["total_cost"],
            }
        },
    }

    checks = validate_microgrid("microgrid_cumcm2026_c", valid_sol)
    assert all(c["ok"] for c in checks if c["name"] in ("q1_power_balance", "q1_soc_bounds", "q1_daily_storage_balance"))

    # Negative test: violate energy balance
    bad_sol = json.loads(json.dumps(valid_sol))
    bad_sol["subproblems"]["q1"]["purchase_kwh"][10] = 0.0  # Deficit
    bad_checks = validate_microgrid("microgrid_cumcm2026_c", bad_sol)
    assert any(c["name"] == "q1_power_balance" and not c["ok"] for c in bad_checks)


def test_official_excel_files_intact():
    base = DEFAULT_CASE_DIR / "附件" / "附件5"
    required = ("result1.xlsx", "result2.xlsx", "result3.xlsx", "result4-2.xlsx", "result4-3.xlsx")
    if not base.is_dir() or not all((base / fn).is_file() for fn in required):
        pytest.skip("Full contest results not all present in contest directory")

    for fn in required:
        p = base / fn
        assert p.is_file(), f"missing {fn}"
        wb = openpyxl.load_workbook(p, data_only=True)
        assert len(wb.sheetnames) >= 2
        for sname in wb.sheetnames:
            ws = wb[sname]
            assert ws.max_row >= 2, f"{fn} sheet {sname} has no data rows"


def test_reporting_and_paper_generation():
    from tools.microgrid_reporting import generate_paper_markdown, generate_audit_markdown

    mock_sol = {
        "problem_id": "microgrid_cumcm2026_c",
        "objective": 35126.95,
        "total_purchase_cost": 35126.95,
        "subproblems": {
            "q1": {
                "total_cost": 35126.95,
                "total_purchase_kwh": 45000.0,
                "table1_samples": {"10:00-10:10": 100.0},
                "blocks_4h": [{"period": "0:00-4:00", "charge_kwh": 500.0, "discharge_kwh": 0.0}],
            },
            "q2": {
                "total_days": 334,
                "total_cost": 500000.0,
                "total_plan_cost": 450000.0,
                "total_emerg_cost": 50000.0,
                "key_dates_summary": {
                    "2025-03-20": {"plan_cost": 1000.0, "emerg_cost": 100.0, "total_cost": 1100.0, "emerg_periods": []},
                    "2025-06-21": {"plan_cost": 1000.0, "emerg_cost": 100.0, "total_cost": 1100.0, "emerg_periods": []},
                    "2025-09-23": {"plan_cost": 1000.0, "emerg_cost": 100.0, "total_cost": 1100.0, "emerg_periods": []},
                    "2025-12-21": {"plan_cost": 1000.0, "emerg_cost": 100.0, "total_cost": 1100.0, "emerg_periods": []},
                },
            },
            "q3": {
                "total_days": 334,
                "total_cost": 380000.0,
                "total_plan_cost": 300000.0,
                "total_adj_delta": 60000.0,
                "total_emerg_cost": 20000.0,
                "total_emergency_kwh": 5000.0,
                "cost_saving_vs_q2": 120000.0,
                "key_dates_summary": {
                    "2025-03-20": {"base_plan_cost": 900.0, "adj_cost_delta": 50.0, "emerg_cost": 50.0, "total_cost": 1000.0, "emerg_periods": []},
                    "2025-06-21": {"base_plan_cost": 900.0, "adj_cost_delta": 50.0, "emerg_cost": 50.0, "total_cost": 1000.0, "emerg_periods": []},
                    "2025-09-23": {"base_plan_cost": 900.0, "adj_cost_delta": 50.0, "emerg_cost": 50.0, "total_cost": 1000.0, "emerg_periods": []},
                    "2025-12-21": {"base_plan_cost": 900.0, "adj_cost_delta": 50.0, "emerg_cost": 50.0, "total_cost": 1000.0, "emerg_periods": []},
                },
            },
            "q4_2": {"total_days": 334, "total_cost": 600000.0, "total_emerg_cost": 60000.0},
            "q4_3": {"total_days": 334, "total_cost": 450000.0, "total_emerg_cost": 30000.0},
        },
    }

    paper = generate_paper_markdown(mock_sol)
    assert "微网与外部电网电力调控策略" in paper
    assert "2025.3.20" in paper
    assert "2025.6.21" in paper
    assert "2025.9.23" in paper
    assert "2025.12.21" in paper

    audit = generate_audit_markdown(mock_sol, [{"name": "test_chk", "ok": True, "detail": "All good"}])
    assert "全量复核" in audit
    assert "test_chk" in audit


def test_mpc_interpolation_start_val():
    hourly = [1000.0] * 24
    # When start_val is 1000.0, the first interval should be 1000.0, NOT falling to 166.7
    smooth = interpolate_hourly_to_10min(hourly, start_val=1000.0)
    assert smooth[0] == pytest.approx(1000.0)
    assert smooth[5] == pytest.approx(1000.0)
