#!/usr/bin/env python3
"""B题异形圆管下料 — 全四问求解器 v2 (fixed stock selection)"""
import json, os, math
from collections import defaultdict, Counter

OUT = 'outputs/b-tube-cut'
os.makedirs(OUT, exist_ok=True)

# ── Load data ──
with open(os.path.join(OUT, 'axial_lengths.json')) as f:
    axial_data = json.load(f)
with open(os.path.join(OUT, 'cocut_savings.json')) as f:
    savings_data = json.load(f)

L = {int(k[1:]): v for k, v in axial_data['axial_lengths_mm'].items()}
STOCKS = [9000, 10000, 11000, 12000]

Q1_DEMAND = {i: 50 for i in range(1, 11)}
BATCH_DEMAND = {
    1: {1:52,2:31,3:43,4:39,5:58,6:55,7:57,8:41,9:45,10:47},
    2: {1:46,2:28,3:40,4:35,5:57,6:50,7:51,8:37,9:44,10:45},
    3: {1:44,2:27,3:36,4:34,5:60,6:56,7:49,8:39,9:42,10:40},
}

def get_savings(i, j, mode):
    key = f'G{i}-G{j}'
    return savings_data.get(key, {}).get(mode, 0.0)

# ── Bin packing: multi-bin BFD (Hermes fix: was 4^n stock enum — hangs with real axial lengths) ──
def best_fit_pack_multi(pieces, stock_len):
    """pieces: list[(type_id, length)]. Returns list of (seq, used) bins or None."""
    ordered = sorted(pieces, key=lambda x: -x[1])
    bins = []  # (remaining, seq)
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


def group_types(seq):
    """Contiguous same-type blocks; fewer switches."""
    from collections import Counter
    c = Counter(seq)
    order = sorted(c.keys(), key=lambda g: (-c[g], g))
    out = []
    for g in order:
        out.extend([g] * c[g])
    return out


def solve_min_stocks(demand, consider_cocut=False):
    """Min total stock length via uniform-stock BFD (each of 9/10/11/12m)."""
    pieces = []
    for g, cnt in demand.items():
        if cnt <= 0:
            continue
        pieces.extend([(g, L[g])] * int(cnt))
    total_needed = sum(L[g] * demand[g] for g in demand)

    best = None
    best_key = None
    for slen in STOCKS:
        packed = best_fit_pack_multi(pieces, slen)
        if packed is None:
            continue
        stocks = []
        for seq, used in packed:
            seq = group_types(seq)
            switches = sum(1 for k in range(1, len(seq)) if seq[k] != seq[k - 1])
            stock = {
                "stock_id": f"M{len(stocks)+1}",
                "stock_len": slen,
                "sequence": seq,
                "used_len": used,
                "waste_len": slen - used,
                "utilization": used / slen if slen else 0,
                "switches": switches,
            }
            if consider_cocut:
                ordered, joints, benefit = optimize_ordering(seq)
                # effective must still fit
                eff = used - benefit
                if eff > slen + 1e-6:
                    # scale down benefit to keep feasible
                    benefit = max(0.0, used - slen)
                    eff = used - benefit
                stock["sequence"] = ordered
                stock["joints"] = joints
                stock["cocut_benefit"] = benefit
                stock["used_len_effective"] = eff
                stock["utilization"] = eff / slen
                stock["waste_len"] = slen - eff
                stock["switches"] = sum(
                    1 for k in range(1, len(ordered)) if ordered[k] != ordered[k - 1]
                )
            stocks.append(stock)
        total = slen * len(stocks)
        sw = sum(s["switches"] for s in stocks)
        key = (total, sw, len(stocks))
        if best is None or key < best_key:
            best = {
                "stocks": stocks,
                "total_stock_length": total,
                "total_switches": sw,
            }
            best_key = key

    if best is None:
        return None
    # sanity: total capacity >= needed
    if best["total_stock_length"] + 1e-6 < total_needed and not consider_cocut:
        return None
    return best


def optimize_ordering(seq):
    """Optimize piece ordering within a stock for max co-cutting benefit."""
    if len(seq) <= 1:
        return list(seq), [], 0.0

    # Group same types to minimize switches (type blocks)
    ordered = group_types(seq)
    joints = []
    total_benefit = 0.0

    for k in range(len(ordered) - 1):
        i, j = ordered[k], ordered[k + 1]
        best_mode = max(["LL", "LR", "RL", "RR"], key=lambda m: get_savings(i, j, m))
        benefit = get_savings(i, j, best_mode)
        total_benefit += benefit
        jtype = "internal" if i == j else "inter-block"
        joints.append(
            {"type": jtype, "pair": f"G{i}-G{j}", "mode": best_mode, "benefit": benefit}
        )

    return ordered, joints, total_benefit

def compress_seq(seq):
    """Compress sequence like [1,1,1,2,2] -> 'G1×3|G2×2'"""
    if not seq:
        return '(empty)'
    parts = []
    i = 0
    while i < len(seq):
        g = seq[i]
        count = 1
        while i+count < len(seq) and seq[i+count] == g:
            count += 1
        parts.append(f'G{g}×{count}')
        i += count
    return '|'.join(parts)


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
print("=" * 80)
print("OR-Path B题异形圆管下料 — 全四问求解 v2")
print("=" * 80)

# ── Q1 ──
print("\n" + "─" * 40)
print("QUESTION 1: Each type × 50, no co-cutting")
print("─" * 40)
q1 = solve_min_stocks(Q1_DEMAND, consider_cocut=False)

if q1:
    print(f"\n  Total stock: {q1['total_stock_length']} mm = {q1['total_stock_length']/1000:.2f} m")
    print(f"  Total switches: {q1['total_switches']}")
    for s in q1['stocks']:
        print(f"  {s['stock_id']}({s['stock_len']}mm): {compress_seq(s['sequence'])}")
        print(f"    used={s['used_len']:.1f}mm  waste={s['waste_len']:.1f}mm  util={s['utilization']:.4f}  switches={s['switches']}")
    
    with open(os.path.join(OUT, 'q1-solution.json'), 'w') as f:
        json.dump(q1, f, indent=2, ensure_ascii=False)
    print("\n  Saved: outputs/b-tube-cut/q1-solution.json")
else:
    print("  FAILED!")

# ── Q2 ──
print("\n" + "─" * 40)
print("QUESTION 2: Same allocation, reorder + co-cutting")
print("─" * 40)
if q1:
    q2_stocks = []
    total_cocut = 0
    for stock in q1['stocks']:
        ordered, joints, benefit = optimize_ordering(stock['sequence'])
        total_cocut += benefit
        used = stock['used_len']
        q2_stocks.append({
            'stock_id': stock['stock_id'],
            'stock_len': stock['stock_len'],
            'sequence': ordered,
            'joints': joints,
            'cocut_benefit': benefit,
            'used_len_raw': used,
            'used_len_effective': used - benefit,
            'waste_len': stock['stock_len'] - (used - benefit),
            'utilization': (used - benefit) / stock['stock_len'],
            'switches': sum(1 for k in range(1, len(ordered)) if ordered[k] != ordered[k-1])
        })
    
    q2 = {
        'stocks': q2_stocks,
        'total_stock_length': q1['total_stock_length'],
        'total_cocut_benefit': total_cocut,
        'total_switches': sum(s['switches'] for s in q2_stocks)
    }
    
    print(f"\n  Total co-cutting benefit: {total_cocut:.2f} mm")
    print(f"  Total switches: {q2['total_switches']}")
    for s in q2['stocks']:
        print(f"  {s['stock_id']}: {compress_seq(s['sequence'])}")
        print(f"    cocut_ben={s['cocut_benefit']:.2f}mm  effective={s['used_len_effective']:.1f}mm  util={s['utilization']:.4f}")
    
    with open(os.path.join(OUT, 'q2-solution.json'), 'w') as f:
        json.dump(q2, f, indent=2, ensure_ascii=False)
    print("\n  Saved: outputs/b-tube-cut/q2-solution.json")

# ── Q3 ──
print("\n" + "─" * 40)
print("QUESTION 3: Re-plan with co-cutting")
print("─" * 40)
q3 = solve_min_stocks(Q1_DEMAND, consider_cocut=True)

if q3:
    total_cocut_q3 = sum(s.get('cocut_benefit', 0) for s in q3['stocks'])
    q3['total_cocut_benefit'] = total_cocut_q3
    print(f"\n  Total stock: {q3['total_stock_length']} mm = {q3['total_stock_length']/1000:.2f} m")
    print(f"  Total co-cutting benefit: {total_cocut_q3:.2f} mm")
    print(f"  Total switches: {q3['total_switches']}")
    for s in q3['stocks']:
        print(f"  {s['stock_id']}({s['stock_len']}mm): {compress_seq(s['sequence'])}")
        ben = s.get('cocut_benefit', 0)
        eff = s['used_len'] - ben
        print(f"    raw={s['used_len']:.1f}mm  cocut_ben={ben:.2f}mm  effective={eff:.1f}mm  util={eff/s['stock_len']:.4f}  switches={s['switches']}")
    
    with open(os.path.join(OUT, 'q3-solution.json'), 'w') as f:
        json.dump(q3, f, indent=2, ensure_ascii=False)
    print("\n  Saved: outputs/b-tube-cut/q3-solution.json")
else:
    print("  FAILED!")

# ── Q4 ──
print("\n" + "─" * 40)
print("QUESTION 4: Three batches with inventory")
print("─" * 40)
inventory = []  # leftover pieces >= 200mm
batch_results = {}
all_stocks_list = []
total_stock = 0
total_cocut = 0
total_switches = 0

for bn in [1, 2, 3]:
    demand = dict(BATCH_DEMAND[bn])
    br = solve_min_stocks(demand, consider_cocut=True)
    if br:
        batch_cocut = sum(s.get('cocut_benefit', 0) for s in br['stocks'])
        br['total_cocut_benefit'] = batch_cocut
        batch_results[bn] = br
        all_stocks_list.extend(br['stocks'])
        total_stock += br['total_stock_length']
        total_cocut += batch_cocut
        total_switches += br['total_switches']
        
        # Collect leftovers ≥200mm
        for s in br['stocks']:
            leftover = s['stock_len'] - (s['used_len'] - s.get('cocut_benefit', 0))
            if leftover >= 200:
                inventory.append(leftover)
        
        print(f"  Batch {bn}: {br['total_stock_length']}mm ({br['total_stock_length']/1000:.2f}m), "
              f"{len(br['stocks'])} stocks, cocut={batch_cocut:.2f}mm, switches={br['total_switches']}")
        for s in br['stocks']:
            ben = s.get('cocut_benefit', 0)
            eff = s['used_len'] - ben
            print(f"    {s['stock_id']}({s['stock_len']}mm): {compress_seq(s['sequence'])}  util={eff/s['stock_len']:.4f}")
    else:
        print(f"  Batch {bn}: FAILED!")

q4 = {
    'batch_results': batch_results,
    'total_stock_length': total_stock,
    'total_cocut_benefit': total_cocut,
    'total_switches': total_switches,
    'inventory_ge_200mm': inventory,
    'inventory_total_mm': sum(inventory)
}

print(f"\n  Grand total stock: {total_stock} mm = {total_stock/1000:.2f} m")
print(f"  Inventory (≥200mm): {len(inventory)} pieces, total {sum(inventory):.1f} mm")
with open(os.path.join(OUT, 'q4-solution.json'), 'w') as f:
    json.dump(q4, f, indent=2, ensure_ascii=False)
print("  Saved: outputs/b-tube-cut/q4-solution.json")

# ── Summary ──
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
if q1:
    print(f"  Q1: stock={q1['total_stock_length']}mm, switches={q1['total_switches']}")
if 'q2' in dir():
    print(f"  Q2: stock={q2['total_stock_length']}mm, cocut={q2['total_cocut_benefit']:.2f}mm, switches={q2['total_switches']}")
if q3:
    print(f"  Q3: stock={q3['total_stock_length']}mm, cocut={q3['total_cocut_benefit']:.2f}mm, switches={q3['total_switches']}")
print(f"  Q4: stock={total_stock}mm, cocut={total_cocut:.2f}mm, switches={total_switches}")
