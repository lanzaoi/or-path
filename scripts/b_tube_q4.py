#!/usr/bin/env python3
"""LEGACY helper: superseded by solve_tube_cut_b2026 + tube_optimization beam search.

Kept only for historical reproducibility. Product commands must use solve_dispatch.
"""
import json
import os
from collections import Counter

OUT = "outputs/b-tube-cut"

with open(os.path.join(OUT, "axial_lengths.json"), encoding="utf-8") as f:
    axial_data = json.load(f)
with open(os.path.join(OUT, "cocut_savings.json"), encoding="utf-8") as f:
    savings_data = json.load(f)

L = {int(k[1:]): v for k, v in axial_data["axial_lengths_mm"].items()}
STOCKS = [9000, 10000, 11000, 12000]

BATCH_DEMAND = {
    1: {1: 52, 2: 31, 3: 43, 4: 39, 5: 58, 6: 55, 7: 57, 8: 41, 9: 45, 10: 47},
    2: {1: 46, 2: 28, 3: 40, 4: 35, 5: 57, 6: 50, 7: 51, 8: 37, 9: 44, 10: 45},
    3: {1: 44, 2: 27, 3: 36, 4: 34, 5: 60, 6: 56, 7: 49, 8: 39, 9: 42, 10: 40},
}


def get_savings(i, j, mode):
    return savings_data.get(f"G{i}-G{j}", {}).get(mode, 0.0)


def group_types(seq):
    c = Counter(seq)
    order = sorted(c.keys(), key=lambda g: (-c[g], g))
    out = []
    for g in order:
        out.extend([g] * c[g])
    return out


def pack_multi(pieces, stock_len):
    ordered = sorted(pieces, key=lambda x: -x[1])
    bins = []
    for gtype, piece_len in ordered:
        if piece_len > stock_len + 1e-9:
            return None
        best_i, best_rem = -1, 1e18
        for i, (rem, seq) in enumerate(bins):
            if rem + 1e-9 >= piece_len and rem - piece_len < best_rem:
                best_rem = rem - piece_len
                best_i = i
        if best_i < 0:
            bins.append([stock_len - piece_len, [gtype]])
        else:
            bins[best_i][0] -= piece_len
            bins[best_i][1].append(gtype)
    return [(seq, stock_len - rem) for rem, seq in bins]


def pack_into_one(pieces, stock_len):
    """Greedy fill one remnant (BFD into single bin)."""
    ordered = sorted(pieces, key=lambda x: -x[1])
    seq, used = [], 0.0
    left = []
    for g, ln in ordered:
        if used + ln <= stock_len + 1e-9:
            seq.append(g)
            used += ln
        else:
            left.append((g, ln))
    return seq, used, left


def optimize_ordering(seq):
    if len(seq) <= 1:
        return list(seq), [], 0.0
    ordered = group_types(seq)
    joints = []
    total_benefit = 0.0
    for k in range(len(ordered) - 1):
        i, j = ordered[k], ordered[k + 1]
        best_mode = max(["LL", "LR", "RL", "RR"], key=lambda m: get_savings(i, j, m))
        benefit = get_savings(i, j, best_mode)
        total_benefit += benefit
        joints.append(
            {
                "type": "internal" if i == j else "inter-block",
                "pair": f"G{i}-G{j}",
                "mode": best_mode,
                "benefit": benefit,
            }
        )
    return ordered, joints, total_benefit


def solve_single_batch(demand):
    pieces = []
    for g, cnt in demand.items():
        if cnt > 0:
            pieces.extend([(g, L[g])] * int(cnt))
    best = None
    best_key = None
    for slen in STOCKS:
        packed = pack_multi(pieces, slen)
        if packed is None:
            continue
        stocks = []
        for seq, used in packed:
            ordered, joints, benefit = optimize_ordering(seq)
            eff = used - benefit
            if eff > slen + 1e-6:
                benefit = max(0.0, used - slen)
                eff = used - benefit
            switches = sum(1 for k in range(1, len(ordered)) if ordered[k] != ordered[k - 1])
            stocks.append(
                {
                    "stock_len": slen,
                    "sequence": ordered,
                    "joints": joints,
                    "used_len": used,
                    "cocut_benefit": benefit,
                    "used_effective": eff,
                    "waste": slen - eff,
                    "utilization": eff / slen,
                    "switches": switches,
                }
            )
        total = slen * len(stocks)
        sw = sum(s["switches"] for s in stocks)
        key = (total, sw)
        if best is None or key < best_key:
            best = {
                "stocks": stocks,
                "total_stock_length": total,
                "total_cocut_benefit": sum(s["cocut_benefit"] for s in stocks),
                "total_switches": sw,
            }
            best_key = key
    return best


def solve_q4_inventory():
    inventory = []  # (length_mm, source_batch)
    batch_results = {}
    all_stocks = []
    total_stock = 0
    total_cocut = 0
    total_switches = 0

    for bn in [1, 2, 3]:
        demand = dict(BATCH_DEMAND[bn])
        pieces = []
        for g, cnt in demand.items():
            pieces.extend([(g, L[g])] * int(cnt))

        # use remnants largest-first
        inv_sorted = sorted(enumerate(inventory), key=lambda x: -x[1][0])
        used_idx = set()
        for idx, (inv_len, src) in inv_sorted:
            if not pieces:
                break
            seq, used, left = pack_into_one(pieces, inv_len)
            if not seq:
                continue
            pieces = left
            ordered, joints, benefit = optimize_ordering(seq)
            eff = used - benefit
            if eff > inv_len + 1e-6:
                benefit = max(0.0, used - inv_len)
                eff = used - benefit
            switches = sum(1 for k in range(1, len(ordered)) if ordered[k] != ordered[k - 1])
            all_stocks.append(
                {
                    "stock_id": f"INV_{src}_{idx}",
                    "stock_len": inv_len,
                    "sequence": ordered,
                    "joints": joints,
                    "used_len": used,
                    "cocut_benefit": benefit,
                    "used_effective": eff,
                    "waste": inv_len - eff,
                    "utilization": eff / inv_len if inv_len > 0 else 0,
                    "switches": switches,
                    "is_inventory": True,
                    "source_batch": src,
                }
            )
            total_cocut += benefit
            total_switches += switches
            used_idx.add(idx)
            rem_left = inv_len - eff
            # leftover of remnant may return if still >=200
            if rem_left >= 200:
                inventory.append((rem_left, src))

        inventory = [inventory[i] for i in range(len(inventory)) if i not in used_idx]
        # rebuild demand from remaining pieces
        demand = {}
        for g, ln in pieces:
            demand[g] = demand.get(g, 0) + 1

        if any(demand.values()):
            br = solve_single_batch(demand)
            if br:
                for s in br["stocks"]:
                    s["is_inventory"] = False
                    s["stock_id"] = s.get("stock_id", f"B{bn}M")
                # renumber
                for i, s in enumerate(br["stocks"], 1):
                    s["stock_id"] = f"B{bn}-M{i}"
                all_stocks.extend(br["stocks"])
                total_stock += br["total_stock_length"]
                total_cocut += br["total_cocut_benefit"]
                total_switches += br["total_switches"]
                batch_results[bn] = br
                for s in br["stocks"]:
                    if s["waste"] >= 200:
                        inventory.append((s["waste"], bn))
            else:
                print(f"  ERROR: Batch {bn} unsolvable after inventory!")
                batch_results[bn] = None
        else:
            batch_results[bn] = {
                "stocks": [],
                "total_stock_length": 0,
                "total_cocut_benefit": 0,
                "total_switches": 0,
                "all_from_inventory": True,
            }
            print(f"  Batch {bn}: ALL from inventory!")

    return {
        "batch_results": batch_results,
        "all_stocks": all_stocks,
        "total_stock_length": total_stock,
        "total_cocut_benefit": total_cocut,
        "total_switches": total_switches,
        "final_inventory": [(l, s) for l, s in inventory],
        "bugfix": "packing uses multi-bin BFD; geometry from PCA axial",
    }


print("Q4: Three batches with cross-batch inventory (fixed packing)")
q4 = solve_q4_inventory()

for bn in [1, 2, 3]:
    br = q4["batch_results"][bn]
    if br:
        print(
            f"  Batch {bn}: {br['total_stock_length']}mm new stock, {len(br['stocks'])} stocks, "
            f"cocut={br['total_cocut_benefit']:.2f}mm, switches={br['total_switches']}"
        )

print(f"\n  Grand total new stock: {q4['total_stock_length']}mm = {q4['total_stock_length']/1000:.2f}m")
print(f"  Final inventory pieces: {len(q4['final_inventory'])}")

with open(os.path.join(OUT, "q4-solution.json"), "w", encoding="utf-8") as f:
    json.dump(q4, f, indent=2, ensure_ascii=False)
print("\nSaved: outputs/b-tube-cut/q4-solution.json")
