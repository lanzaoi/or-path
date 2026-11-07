#!/usr/bin/env python3
"""Task 4.1 — Meta-Router multi-probe domain classifier tests.

Covers:
1. 10/10 structured-payload schema sniff accuracy.
2. 10/10 bilingual (EN/CN) filename + text classification accuracy.
3. Composite problems (LRP / PRP / IRP / Microgrid-Facility) detection.
4. Edge cases: empty input, key-less data, unknown fallback, confidence bounds.
5. CLI (``python -m orpath.agents.meta_router``) and function-style interfaces.
6. ``orpath.agents`` package-level exports.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from orpath.agents.meta_router import (  # noqa: E402
    MATCHED_BY_COMPOSITE,
    MATCHED_BY_KEYWORD,
    MATCHED_BY_LLM,
    MATCHED_BY_SCHEMA,
    DomainRouteResult,
    get_supported_domains,
    route_problem,
)

# ---------------------------------------------------------------------------
# Fixtures — realistic payloads mirroring the domain solver input contracts
# ---------------------------------------------------------------------------
SCHEMA_PAYLOADS: dict[str, dict[str, Any]] = {
    "tube": {
        "tubes": [{"length": 3000.0, "diameter": 100.0}],
        "contours": [[[0.0, 0.0], [100.0, 0.0], [100.0, 50.0]]],
        "stock_lengths": [6000.0],
        "nesting": {"inset_mm": 4.0},
    },
    "routing": {
        "depot": 0,
        "customers": [{"id": 1, "demand": 5.0}],
        "demands": [0.0, 5.0, 3.0],
        "capacity": 10.0,
        "distance_matrix": [[0.0, 4.0, 6.0], [4.0, 0.0, 2.0], [6.0, 2.0, 0.0]],
        "time_windows": [[0.0, 999.0], [0.0, 999.0], [0.0, 999.0]],
    },
    "scheduling": {
        "jobs": [[(0, 4), (1, 3)], [(1, 2), (0, 5)]],
        "machines": [0, 1],
        "processing_times": [[4, 3], [2, 5]],
        "setup_times": {(0, 1): 2},
    },
    "project": {
        "activities": [{"duration": 4.0, "successors": [1]}, {"duration": 3.0, "successors": []}],
        "precedences": [[0, 1]],
        "resource_capacities": [10.0, 8.0],
        "renewable_resources": 2,
        "durations": [4.0, 3.0],
    },
    "inventory": {
        "demands": [20.0, 50.0, 10.0],
        "holding_cost": 1.0,
        "setup_cost": 85.0,
        "periods": 3,
        "production_cost": 5.0,
    },
    "facility": {
        "open_facilities": [0, 1],
        "fixed_costs": [100.0, 200.0],
        "capacities": [50.0, 60.0],
        "cost_matrix": [[0.0, 5.0], [5.0, 0.0]],
        "demands": [20.0, 30.0],
    },
    "rostering": {
        "roster": {"E1": ["D", "N"]},
        "shift_demands": [{"morning": 2, "night": 1}],
        "employees": ["E1", "E2"],
        "shifts": ["D", "N"],
        "assignments": {"E1": [0, 1]},
    },
    "microgrid": {
        "purchase_kwh": 10.0,
        "soc_kwh": 5.0,
        "loads_q1_kw": [[1.0, 2.0]],
        "prices_q1": [0.5],
        "pv_q1_kw": [[2.0, 1.5]],
        "battery_capacity_kwh": 20.0,
    },
    "pricing": {
        "first_stage_decision": {"capacity": 100.0},
        "second_stage_decision": {"production": 50.0},
        "scenarios": [{"probability": 0.5, "demand": 60.0}],
        "stochastic": True,
    },
    "finance": {
        "cov_matrix": [[0.04, 0.01], [0.01, 0.09]],
        "allocations": [0.6, 0.4],
        "expected_returns": [0.08, 0.12],
        "assets": ["A", "B"],
        "markowitz": True,
    },
}

TEXT_CASES: list[tuple[str, str, str]] = [
    # (expected_domain, filename, text)
    ("tube", "tube_cutting_nesting_problem.json", "激光套料与管材排样问题 cutting stock nesting"),
    ("routing", "vehicle_routing_vrp_instance.json", "车辆路径问题 VRP 配送路径优化"),
    ("scheduling", "jssp_job_shop_scheduling.json", "车间调度 JSSP 作业车间生产排程"),
    ("project", "rcpsp_project_scheduling.json", "工程项目调度 RCPSP 资源约束项目计划"),
    ("inventory", "wagner_whitin_lot_sizing.json", "动态批量 Wagner-Whitin 库存 lot sizing"),
    ("facility", "cflp_facility_location.json", "设施选址 CFLP 供应链网络仓库规划"),
    ("rostering", "staff_rostering_nurses.json", "护士排班 劳动力排班 班次安排"),
    ("microgrid", "microgrid_dispatch_pv_battery.json", "微电网光储充调度 分时电价优化"),
    ("pricing", "dynamic_pricing_yield_management.json", "收益管理 动态定价 两阶段随机规划"),
    ("finance", "markowitz_portfolio_optimization.json", "投资组合 资产配置 Markowitz 风险平价"),
]


# ---------------------------------------------------------------------------
# 1. Schema sniff — 10/10 structured payloads
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("domain", sorted(SCHEMA_PAYLOADS))
def test_schema_sniff_payloads(domain: str) -> None:
    result = route_problem(data=SCHEMA_PAYLOADS[domain])
    assert result.domain == domain, (
        f"payload for {domain} routed to {result.domain} "
        f"({result.matched_by}): {result.rationale}"
    )
    assert result.matched_by == MATCHED_BY_SCHEMA
    assert result.is_composite is False
    assert result.confidence >= 0.7
    assert 0.0 <= result.confidence <= 1.0


def test_schema_sniff_nested_and_json_string() -> None:
    # Nested payload + inline JSON string input should sniff identically.
    result_dict = route_problem(data=SCHEMA_PAYLOADS["microgrid"])
    result_json = route_problem(data=json.dumps(SCHEMA_PAYLOADS["microgrid"]))
    assert result_json.domain == result_dict.domain == "microgrid"


def test_schema_sniff_deeply_nested_does_not_recurse_crash() -> None:
    """A 2000-deep nested dict must not blow the recursion limit."""
    deep: dict[str, Any] = {}
    node = deep
    for _ in range(2000):
        node["child"] = {}
        node = node["child"]
    # Should complete (via budget cap) instead of raising RecursionError.
    result = route_problem(data=deep)
    assert result.domain in get_supported_domains()


def test_schema_sniff_cyclic_structure_terminates() -> None:
    """A self-referential dict must terminate via visited-id tracking."""
    cyc: dict[str, Any] = {"jobs": [1, 2], "machines": [1, 2]}
    cyc["self"] = cyc
    result = route_problem(data=cyc)
    assert result.domain == "scheduling"
    assert result.confidence > 0.5


# ---------------------------------------------------------------------------
# 2. Keyword tree — 10/10 bilingual filename + text
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("domain,filename,text", TEXT_CASES)
def test_keyword_tree_filename_and_text(domain: str, filename: str, text: str) -> None:
    result = route_problem(filename=filename, text=text)
    assert result.domain == domain, (
        f"{filename} routed to {result.domain}: {result.rationale}"
    )
    assert result.is_composite is False
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.parametrize("domain,filename,text", TEXT_CASES)
def test_keyword_tree_filename_only(domain: str, filename: str, text: str) -> None:
    result = route_problem(filename=filename)
    assert result.domain == domain


def test_keyword_tree_chinese_filename() -> None:
    result = route_problem(filename="微电网调度.json")
    assert result.domain == "microgrid"


def test_schema_probe_beats_conflicting_keyword() -> None:
    # Filename says routing, but the structured payload is clearly JSSP.
    result = route_problem(
        data=SCHEMA_PAYLOADS["scheduling"],
        filename="vehicle_routing_vrp.json",
        text="车辆路径问题",
    )
    assert result.domain == "scheduling"
    assert result.matched_by == MATCHED_BY_SCHEMA


# ---------------------------------------------------------------------------
# 3. Composite problems
# ---------------------------------------------------------------------------
LRP_PAYLOAD = {
    "open_facilities": [0, 1],
    "fixed_costs": [100.0, 200.0],
    "capacities": [50.0, 60.0],
    "cost_matrix": [[0.0, 5.0, 6.0], [5.0, 0.0, 2.0], [6.0, 2.0, 0.0]],
    "depot": 0,
    "customers": [{"id": 1, "demand": 5.0}, {"id": 2, "demand": 3.0}],
    "routes": [[0, 1, 0], [0, 2, 0]],
    "distance_matrix": [[0.0, 5.0, 6.0], [5.0, 0.0, 2.0], [6.0, 2.0, 0.0]],
}
IRP_PAYLOAD = {
    "demands": [20.0, 30.0],
    "holding_cost": 1.0,
    "setup_cost": 50.0,
    "periods": 2,
    "depot": 0,
    "customers": [{"id": 1, "demand": 5.0}],
    "routes": [[0, 1, 0]],
}
PRP_PAYLOAD = {
    "jobs": [[(0, 2)]],
    "machines": [0],
    "demands": [10.0],
    "holding_cost": 1.0,
    "depot": 0,
    "customers": [{"id": 1, "demand": 10.0}],
    "routes": [[0, 1, 0]],
}
MF_PAYLOAD = {
    "purchase_kwh": 10.0,
    "soc_kwh": 5.0,
    "battery_capacity_kwh": 20.0,
    "open_facilities": [0],
    "fixed_costs": [50.0],
}


def test_composite_lrp() -> None:
    result = route_problem(data=LRP_PAYLOAD)
    assert result.is_composite is True
    assert result.composite_domains == ["facility", "routing"]
    assert result.domain in result.composite_domains
    assert result.matched_by == MATCHED_BY_COMPOSITE
    assert result.confidence >= 0.8


def test_composite_lrp_text_marker() -> None:
    result = route_problem(filename="location_routing_problem.json")
    assert result.is_composite is True
    assert result.composite_domains == ["facility", "routing"]


def test_composite_irp() -> None:
    result = route_problem(data=IRP_PAYLOAD)
    assert result.is_composite is True
    assert result.composite_domains == ["inventory", "routing"]
    assert result.matched_by == MATCHED_BY_COMPOSITE


def test_composite_irp_text_marker() -> None:
    result = route_problem(text="inventory-routing problem IRP 库存路径问题")
    assert result.is_composite is True
    assert result.composite_domains == ["inventory", "routing"]


def test_composite_prp_ordered_domains() -> None:
    result = route_problem(data=PRP_PAYLOAD)
    assert result.is_composite is True
    assert result.composite_domains == ["scheduling", "inventory", "routing"]
    assert result.matched_by == MATCHED_BY_COMPOSITE


def test_composite_prp_text_marker() -> None:
    result = route_problem(text="production-inventory-routing PRP 生产-库存-路由")
    assert result.is_composite is True
    assert result.composite_domains == ["scheduling", "inventory", "routing"]


def test_composite_microgrid_facility() -> None:
    result = route_problem(data=MF_PAYLOAD)
    assert result.is_composite is True
    assert result.composite_domains == ["microgrid", "facility"]


# ---------------------------------------------------------------------------
# 4. Edge cases & fallback
# ---------------------------------------------------------------------------
def test_empty_input_falls_back() -> None:
    result = route_problem()
    assert result.domain in get_supported_domains()
    assert result.matched_by == MATCHED_BY_LLM
    assert result.confidence <= 0.5
    assert result.is_composite is False


def test_empty_string_inputs_fall_back() -> None:
    result = route_problem(data={}, text="", filename="")
    assert result.domain in get_supported_domains()
    assert result.confidence <= 0.5


def test_keyless_data_falls_back() -> None:
    result = route_problem(data={"foo": "bar", "values": [1, 2, 3]})
    assert result.domain in get_supported_domains()
    assert result.confidence <= 0.5


def test_plain_list_data_falls_back() -> None:
    result = route_problem(data=[1, 2, 3])
    assert result.domain in get_supported_domains()


def test_unknown_text_falls_back_without_model() -> None:
    result = route_problem(text="这里有一个问题需要解决", filename="mystery.json")
    assert result.domain in get_supported_domains()
    assert result.confidence <= 0.5


def test_confidence_always_bounded() -> None:
    for payload in SCHEMA_PAYLOADS.values():
        assert 0.0 <= route_problem(data=payload).confidence <= 1.0
    assert 0.0 <= route_problem().confidence <= 1.0


def test_invalid_domain_rejected() -> None:
    with pytest.raises(ValueError):
        DomainRouteResult(domain="not_a_domain", confidence=0.5)


def test_llm_fallback_with_model(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeResp:
        content = json.dumps(
            {"domain": "finance", "confidence": 0.8, "rationale": "covariance keys"}
        )

    class _FakeModel:
        def invoke(self, _messages: Any) -> _FakeResp:
            return _FakeResp()

    result = route_problem(data={"mystery": 1}, model=_FakeModel())
    assert result.domain == "finance"
    assert result.matched_by == MATCHED_BY_LLM
    assert 0.0 <= result.confidence <= 1.0


def test_llm_fallback_broken_model_does_not_crash() -> None:
    class _BrokenModel:
        def invoke(self, _messages: Any) -> Any:
            raise RuntimeError("model exploded")

    result = route_problem(data={"mystery": 1}, model=_BrokenModel())
    assert result.domain in get_supported_domains()


# ---------------------------------------------------------------------------
# 5. Function-style interface & convenience API
# ---------------------------------------------------------------------------
def test_get_supported_domains() -> None:
    domains = get_supported_domains()
    assert domains == [
        "tube", "routing", "scheduling", "project", "inventory",
        "facility", "rostering", "microgrid", "pricing", "finance",
    ]
    assert len(domains) == 10


def test_result_to_dict_shape() -> None:
    result = route_problem(data=SCHEMA_PAYLOADS["rostering"])
    payload = result.to_dict()
    assert set(payload) == {
        "domain", "confidence", "is_composite",
        "composite_domains", "matched_by", "rationale",
    }
    json.dumps(payload)  # must be JSON-serialisable


# ---------------------------------------------------------------------------
# 6. CLI interface
# ---------------------------------------------------------------------------
def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "orpath.agents.meta_router", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_cli_text_input() -> None:
    proc = _run_cli(["--text", "车间调度 JSSP 问题", "--filename", "jssp_case.json"])
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["domain"] == "scheduling"


def test_cli_data_file(tmp_path: Path) -> None:
    p = tmp_path / "vrp_case.json"
    p.write_text(json.dumps(SCHEMA_PAYLOADS["routing"]), encoding="utf-8")
    proc = _run_cli(["--data", str(p)])
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["domain"] == "routing"


def test_cli_empty_falls_back() -> None:
    proc = _run_cli([])
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["domain"] in get_supported_domains()


# ---------------------------------------------------------------------------
# 7. Package-level exports
# ---------------------------------------------------------------------------
def test_package_exports() -> None:
    from orpath.agents import (  # noqa: F401
        DomainRouteResult as ExportedResult,
        get_supported_domains as exported_domains,
        route_problem as exported_route,
    )

    assert ExportedResult is DomainRouteResult
    assert exported_domains() == get_supported_domains()
    assert exported_route(text="微电网调度").domain == "microgrid"
