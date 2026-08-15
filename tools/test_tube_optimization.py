from __future__ import annotations

import sys
from copy import deepcopy
from itertools import product
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from tube_optimization import (
    counts_from_bins,
    homogeneous_block_stock_patterns,
    joint_relaxation_stock_lower_bound,
    materialize_bins,
    minimize_type_splits_for_fixed_stock,
    mixed_stock_patterns,
    optimize_fixed_assignments,
    optimize_joint_bins,
    orientation_dp,
    solve_multibatch_beam,
    summarize_bins,
    solution_key,
)
from solve_tube_cut_b2026 import (
    cocut_saving,
    joint_summary,
    sequence_block_text,
    solve_q2,
    solve_q3,
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


def brute_orientation(sequence, savings):
    best = -1.0
    for orientation in product(("L", "R"), repeat=len(sequence)):
        value = 0.0
        for i, (a, b) in enumerate(zip(sequence, sequence[1:])):
            right_a = "R" if orientation[i] == "L" else "L"
            value += savings[f"{a}-{b}"][right_a + orientation[i + 1]]
        best = max(best, value)
    return best


def test_orientation_dp_matches_exhaustive_search():
    gids = ("A", "B", "C")
    savings = savings_for(gids)
    sequence = ["A", "B", "C", "A", "C", "B", "A", "A"]
    value, orientation, joints = orientation_dp(sequence, savings)
    assert value == brute_orientation(sequence, savings)
    assert len(orientation) == len(sequence)
    assert len(joints) == len(sequence) - 1


def test_orientation_dp_handles_long_sequences_without_greedy_fallback():
    gids = ("A", "B")
    sequence = [gids[i % 2] for i in range(80)]
    value, orientation, joints = orientation_dp(sequence, savings_for(gids))
    assert value >= 0
    assert len(orientation) == 80
    assert len(joints) == 79


def test_excel_block_and_joint_summary_match_contest_notation():
    stock = {
        "id": "M1",
        "sequence": ["G1", "G1", "G1", "G2", "G2"],
        "joints": [
            {"mode": "LL", "benefit": 2.0},
            {"mode": "LL", "benefit": 2.0},
            {"mode": "LR", "benefit": 3.0},
            {"mode": "RR", "benefit": 1.5},
        ],
    }
    assert sequence_block_text(stock["sequence"]) == "G1×3|G2×2"
    rows = joint_summary(stock)
    assert rows == [
        {
            "type": "内部拼接",
            "front": "G1×3",
            "rear": "G1×3",
            "mode": "LL",
            "count": 2,
            "unit_benefit_mm": 2.0,
            "subtotal_mm": 4.0,
        },
        {
            "type": "块间拼接",
            "front": "G1×3",
            "rear": "G2×2",
            "mode": "LR",
            "count": 1,
            "unit_benefit_mm": 3.0,
            "subtotal_mm": 3.0,
        },
        {
            "type": "内部拼接",
            "front": "G2×2",
            "rear": "G2×2",
            "mode": "RR",
            "count": 1,
            "unit_benefit_mm": 1.5,
            "subtotal_mm": 1.5,
        },
    ]


def test_profile_rotation_is_zero_for_flat_ends_and_pair_symmetric():
    flat = {
        "L_env": [0.0] * 360,
        "R_env": [0.0] * 360,
        "axial_length_mm": 100.0,
    }
    shaped_a = {
        "L_env": [float(i % 13) for i in range(360)],
        "R_env": [float((2 * i) % 17) for i in range(360)],
        "axial_length_mm": 100.0,
    }
    shaped_b = {
        "L_env": [float((5 * i) % 19) for i in range(360)],
        "R_env": [float((7 * i) % 23) for i in range(360)],
        "axial_length_mm": 120.0,
    }
    assert cocut_saving(flat, flat, "L", "R") == 0.0
    assert cocut_saving(shaped_a, shaped_b, "L", "R") == cocut_saving(
        shaped_b, shaped_a, "R", "L"
    )


def test_mixed_stock_master_really_mixes_lengths():
    # 11=(A+B), 10=(A): 21 is better than all-11 (22) or all-10 (30).
    bars = mixed_stock_patterns(
        {"A": 2, "B": 1},
        {"A": 6.0, "B": 5.0},
        stocks=(10.0, 11.0),
        seed=7,
        time_limit_s=2.0,
    )
    assert sum(b["stock_length_mm"] for b in bars) == 21.0
    assert {b["stock_length_mm"] for b in bars} == {10.0, 11.0}
    assert counts_from_bins(bars) == {"A": 2, "B": 1}


def test_compact_master_closes_real_scale_integer_pattern_gap():
    lengths = {
        "G1": 191.8068,
        "G2": 149.2395,
        "G3": 191.727,
        "G4": 191.6823,
        "G5": 75.0106,
        "G6": 150.0108,
        "G7": 250.0203,
        "G8": 399.9241,
        "G9": 181.0939,
        "G10": 200.5996,
    }
    demand = {gid: 50 for gid in lengths}
    bars = mixed_stock_patterns(
        demand,
        lengths,
        stocks=(9000.0, 10000.0, 11000.0, 12000.0),
        seed=20260813,
        time_limit_s=2.0,
    )
    # Total raw demand is 99,055.745 mm, so 100,000 mm is also a
    # straightforward lower bound with the available whole-metre stock sizes.
    assert sum(row["stock_length_mm"] for row in bars) == 100000.0
    assert counts_from_bins(bars) == demand


def test_secondary_master_preserves_stock_total_and_reduces_switches():
    demand = {"A": 2, "B": 2, "C": 2}
    lengths = {"A": 4.0, "B": 3.0, "C": 3.0}
    incumbent = [
        {
            "id": "M1",
            "stock_length_mm": 10.0,
            "purchase_cost_mm": 10.0,
            "sequence": ["A", "B", "C"],
            "from_remnant": False,
        },
        {
            "id": "M2",
            "stock_length_mm": 10.0,
            "purchase_cost_mm": 10.0,
            "sequence": ["A", "B", "C"],
            "from_remnant": False,
        },
    ]
    bars, evidence = minimize_type_splits_for_fixed_stock(
        demand,
        lengths,
        incumbent,
        stocks=(10.0,),
        seed=13,
        time_limit_s=2.0,
    )
    assert sum(row["stock_length_mm"] for row in bars) == 20.0
    assert counts_from_bins(bars) == demand
    assert sum(row["sequence"][i] != row["sequence"][i - 1] for row in bars for i in range(1, len(row["sequence"]))) <= 2
    assert evidence["switch_incumbent"] <= 2
    assert evidence["switch_lower_bound"] <= evidence["switch_incumbent"]


def test_joint_relaxation_is_a_valid_optimistic_stock_bound():
    demand = {"A": 2, "B": 1}
    lengths = {"A": 6.0, "B": 4.0}
    savings = {
        f"{a}-{b}": {mode: 1.0 for mode in ("LL", "LR", "RL", "RR")}
        for a in demand
        for b in demand
    }
    bound = joint_relaxation_stock_lower_bound(
        demand, lengths, savings, stocks=(10.0, 11.0)
    )
    bars = mixed_stock_patterns(
        demand, lengths, stocks=(10.0, 11.0), seed=17, time_limit_s=2.0
    )
    incumbent = sum(row["stock_length_mm"] for row in bars)
    assert 0 < bound["lower_bound_mm"] <= incumbent
    assert bound["effective_length_lower_bound_mm"] <= sum(
        lengths[gid] * count for gid, count in demand.items()
    )


def test_orientation_consistent_bound_limits_incompatible_high_saving_arcs():
    demand = {"A": 4}
    lengths = {"A": 10.0}
    # LL requires a source whose right end is L (orientation R) followed by a
    # target whose left end is L.  Four pieces cannot all receive that saving,
    # so an orientation-consistent cover caps it at two high-saving joints.
    savings = {"A-A": {"LL": 10.0, "LR": 0.0, "RL": 0.0, "RR": 0.0}}
    bound = joint_relaxation_stock_lower_bound(
        demand, lengths, savings, stocks=(10.0,)
    )
    proof = bound["orientation_consistent"]
    assert proof["status"] == "OPTIMAL"
    assert proof["co_cut_upper_bound_mm"] == 20.0
    assert proof["effective_length_lower_bound_mm"] == 20.0
    assert bound["lower_bound_mm"] == 20.0


def test_homogeneous_block_master_uses_internal_cocut_conservatively():
    demand = {"A": 3, "B": 2}
    lengths = {"A": 4.0, "B": 3.0}
    savings = {
        f"{a}-{b}": {mode: 1.0 for mode in ("LL", "LR", "RL", "RR")}
        for a in demand
        for b in demand
    }
    bars, evidence = homogeneous_block_stock_patterns(
        demand,
        lengths,
        savings,
        stocks=(10.0, 11.0),
        seed=19,
        time_limit_s=2.0,
    )
    assert counts_from_bins(bars) == demand
    assert all(row["effective_length_mm"] <= row["stock_length_mm"] for row in bars)
    assert evidence["conservative"] is True
    assert evidence["stock_lower_bound_mm"] <= evidence["stock_incumbent_mm"]


def test_materialize_rejects_infeasible_instead_of_scaling():
    bins = [{"id": "M1", "stock_length_mm": 10.0, "sequence": ["A", "A"]}]
    result = materialize_bins(
        bins,
        {"A": 6.0},
        {"A-A": {"LL": 0.0, "LR": 0.0, "RL": 0.0, "RR": 0.0}},
        resize_new=False,
    )
    assert result is None


def test_fixed_assignment_search_preserves_each_multiset_and_is_reproducible():
    gids = ("A", "B", "C")
    lengths = {g: 10.0 for g in gids}
    savings = savings_for(gids)
    bins = [
        {"id": "M1", "stock_length_mm": 100.0, "sequence": ["A", "A", "B", "C", "B"]},
        {"id": "M2", "stock_length_mm": 100.0, "sequence": ["C", "B", "C", "A"]},
    ]
    a = optimize_fixed_assignments(bins, lengths, savings, seed=19, iterations=300)
    b = optimize_fixed_assignments(bins, lengths, savings, seed=19, iterations=300)
    assert a == b
    for before, after in zip(bins, a):
        assert counts_from_bins([before]) == counts_from_bins([after])


def test_joint_search_preserves_global_demand_and_never_worsens_lexicographic_key():
    gids = ("A", "B", "C")
    lengths = {"A": 6.0, "B": 5.0, "C": 4.0}
    savings = savings_for(gids)
    raw = mixed_stock_patterns(
        {"A": 3, "B": 3, "C": 3}, lengths, stocks=(10.0, 11.0, 12.0), seed=3
    )
    initial = materialize_bins(raw, lengths, savings, resize_new=True, stocks=(10.0, 11.0, 12.0))
    assert initial is not None
    best = optimize_joint_bins(
        initial,
        lengths,
        savings,
        seed=3,
        iterations=800,
        resize_new=True,
        stocks=(10.0, 11.0, 12.0),
    )
    assert counts_from_bins(best) == {"A": 3, "B": 3, "C": 3}
    assert solution_key(best) <= solution_key(initial)


def test_q3_can_choose_an_alternative_primary_packing_base():
    lengths = {"A": 6.0, "B": 4.0}
    savings = zero_savings(("A", "B"))
    q1 = {
        "stocks": [
            {
                "id": "M1",
                "stock_length_mm": 10.0,
                "sequence": ["A", "B"],
            },
            {
                "id": "M2",
                "stock_length_mm": 10.0,
                "sequence": ["A", "B"],
            },
        ],
        "demand": {"A": 2, "B": 2},
    }
    q2 = solve_q2(
        q1, lengths, savings, seed=31, iterations=0, restarts=1
    )
    alternative = deepcopy(q1["stocks"])
    q3 = solve_q3(
        q2,
        lengths,
        savings,
        seed=37,
        iterations=0,
        restarts=2,
        alternative_bases=[alternative],
    )
    assert counts_from_bins(q3["stocks"]) == q1["demand"]
    assert {row["base"] for row in q3["search_evidence"]["restarts"]} == {
        "q2_low_switch",
        "primary_packing_1",
    }


def test_multibatch_beam_is_reproducible_and_balanced():
    gids = ("A", "B")
    lengths = {"A": 6.0, "B": 4.0}
    savings = savings_for(gids)
    demands = [
        {"A": 2, "B": 2},
        {"A": 1, "B": 3},
        {"A": 2, "B": 1},
    ]
    kwargs = dict(
        stocks=(10.0, 11.0),
        remnant_min_mm=1.0,
        seed=23,
        beam_width=5,
        variants_per_state=5,
        joint_iterations=80,
        master_time_limit_s=1.0,
    )
    first = solve_multibatch_beam(demands, lengths, savings, **kwargs)
    second = solve_multibatch_beam(demands, lengths, savings, **kwargs)
    assert first == second
    for expected, batch in zip(demands, first["batches"]):
        assert counts_from_bins(batch["result"]["stocks"]) == expected
    assert abs(batch["result"]["inventory_balance_error_mm"]) < 1e-7
    assert first["total_waste_mm"] >= 0
    assert first["final_inventory_mm"] >= 0
    assert first["direct_utilization"] <= first["nonwaste_utilization"] <= 1.0


def test_multibatch_beam_can_select_cocut_aware_initializer():
    lengths = {"A": 6.0}
    savings = {
        "A-A": {mode: 2.0 for mode in ("LL", "LR", "RL", "RR")}
    }
    demand = {"A": 2}
    # Raw occupancy is 12, requiring two 10-unit bars.  The validated co-cut
    # occupancy is 10, so this explicit initializer should win with one bar.
    cocut_initial = [
        [
            {
                "id": "B1-C1",
                "stock_length_mm": 10.0,
                "purchase_cost_mm": 10.0,
                "sequence": ["A", "A"],
                "from_remnant": False,
            }
        ]
    ]
    result = solve_multibatch_beam(
        [demand],
        lengths,
        savings,
        stocks=(10.0,),
        remnant_min_mm=1.0,
        seed=41,
        beam_width=3,
        variants_per_state=1,
        joint_iterations=0,
        master_time_limit_s=1.0,
        cocut_initial_bins=cocut_initial,
    )
    assert result["total_new_standard_stock_mm"] == 10.0
    assert (
        result["batches"][0]["result"]["new_stock_pattern_source"]
        == "homogeneous_cocut_block_master"
    )


def test_multibatch_beam_can_build_cocut_master_after_using_remnant():
    lengths = {"A": 6.0, "B": 2.0}
    savings = {
        f"{left}-{right}": {
            mode: (2.0 if left == right == "A" else 0.0)
            for mode in ("LL", "LR", "RL", "RR")
        }
        for left in lengths
        for right in lengths
    }
    first = {"A": 0, "B": 4}
    second = {"A": 2, "B": 1}
    result = solve_multibatch_beam(
        [first, second],
        lengths,
        savings,
        stocks=(10.0,),
        remnant_min_mm=1.0,
        seed=43,
        beam_width=8,
        variants_per_state=6,
        joint_iterations=0,
        master_time_limit_s=1.0,
        cocut_remaining_master_time_limit_s=1.0,
    )
    assert counts_from_bins(result["batches"][1]["result"]["stocks"]) == second
    assert any(
        row.get("available")
        for row in result["cocut_remaining_master_evidence"]
    )


def zero_savings(gids):
    return {
        f"{a}-{b}": {mode: 0.0 for mode in ("LL", "LR", "RL", "RR")}
        for a in gids
        for b in gids
    }


def strict_envelope():
    from validate_solution import validate

    gids = ("A", "B")
    lengths = {"A": 60.0, "B": 40.0}
    savings = zero_savings(gids)
    stocks = (100.0, 110.0)
    demand = {"A": 2, "B": 1}
    q1_bars = mixed_stock_patterns(demand, lengths, stocks=stocks, seed=11)
    for row in q1_bars:
        raw = sum(lengths[g] for g in row["sequence"])
        row.update(
            {
                "raw_length_mm": raw,
                "used_length_mm": raw,
                "co_cut_benefit_mm": 0.0,
                "effective_length_mm": raw,
                "leftover_mm": row["stock_length_mm"] - raw,
                "utilization": raw / row["stock_length_mm"],
                "switches": sum(a != b for a, b in zip(row["sequence"], row["sequence"][1:])),
            }
        )
    q1 = {
        "stocks": q1_bars,
        "total_stock_length_mm": sum(b["stock_length_mm"] for b in q1_bars),
        "total_axial_length_mm": sum(lengths[g] * n for g, n in demand.items()),
        "total_switch": sum(b["switches"] for b in q1_bars),
        "utilization": sum(lengths[g] * n for g, n in demand.items())
        / sum(b["stock_length_mm"] for b in q1_bars),
        "demand": demand,
        "status": "FEASIBLE",
    }
    q2_bars = materialize_bins(q1_bars, lengths, savings, resize_new=False)
    assert q2_bars is not None
    q2 = summarize_bins(q2_bars)
    q2["demand"] = demand
    q3 = deepcopy(q2)
    q4 = solve_multibatch_beam(
        [{"A": 1, "B": 1}, {"A": 1, "B": 1}, {"A": 1, "B": 1}],
        lengths,
        savings,
        stocks=stocks,
        remnant_min_mm=10.0,
        seed=29,
        beam_width=4,
        joint_iterations=40,
        master_time_limit_s=1.0,
    )
    envelope = {
        "problem_id": "synthetic_tube",
        "problem_class": "tube_cut",
        "status": "FEASIBLE",
        "objective": q3["total_stock_length_mm"],
        "source": "tools/solve_tube_cut_b2026.py",
        "solver": "tube-cg-cpsat-alns-beam",
        "questions": {"q1": q1, "q2": q2, "q3": q3, "q4": q4},
        "model_snapshot": {
            "schema": "orpath.tube_model.v2",
            "units": "mm",
            "lengths": lengths,
            "savings": savings,
            "stock_lengths_mm": list(stocks),
            "remnant_min_mm": 10.0,
            "profile_bins": 360,
            "seed": 29,
            "input_sha256": {"synthetic://tube-model": "0" * 64},
        },
        "meta": {"exact": False, "proven_optimal": False, "method_class": "heuristic"},
    }
    return envelope, validate


def test_strict_tube_validator_accepts_recomputed_solution():
    envelope, validate = strict_envelope()
    report = validate("synthetic_tube", envelope)
    assert report["ok"], report["errors"]


def test_synthetic_snapshot_cannot_masquerade_as_real_tube_input():
    envelope, validate = strict_envelope()
    envelope["problem_id"] = "tube_cut_b2026"
    report = validate("tube_cut_b2026", envelope)
    assert not report["ok"]
    assert any(c["name"] == "strict_problem_policy" and not c["ok"] for c in report["checks"])


def test_strict_tube_validator_rejects_numeric_and_assignment_tampering():
    envelope, validate = strict_envelope()

    inflated = deepcopy(envelope)
    inflated["questions"]["q2"]["stocks"][0]["co_cut_benefit_mm"] += 1.0
    assert not validate("synthetic_tube", inflated)["ok"]

    missing = deepcopy(envelope)
    missing["questions"]["q3"]["stocks"][0]["sequence"].pop()
    assert not validate("synthetic_tube", missing)["ok"]

    reassigned = deepcopy(envelope)
    q2_stocks = reassigned["questions"]["q2"]["stocks"]
    changed = False
    for left in range(len(q2_stocks)):
        for right in range(left + 1, len(q2_stocks)):
            for i, a in enumerate(q2_stocks[left]["sequence"]):
                for j, b in enumerate(q2_stocks[right]["sequence"]):
                    if a != b:
                        q2_stocks[left]["sequence"][i], q2_stocks[right]["sequence"][j] = b, a
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break
        if changed:
            break
    assert changed
    assert not validate("synthetic_tube", reassigned)["ok"]

    inventory = deepcopy(envelope)
    inventory["questions"]["q4"]["batches"][1]["result"]["inventory_before"].append(
        {"id": "FAKE", "length_mm": 999.0}
    )
    assert not validate("synthetic_tube", inventory)["ok"]
