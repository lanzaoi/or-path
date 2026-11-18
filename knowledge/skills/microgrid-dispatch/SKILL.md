---
name: microgrid-dispatch
description: Campus PV-BESS-EV microgrid multi-stage LP/MILP dispatch, SOC dynamics, TOU arbitrage, and rolling-horizon MPC.
---
# Microgrid Dispatch Modeling Skill

1. **Solver Mode**: `tools/solve_microgrid.py` (`highspy` / `pulp` multi-period LP/MILP across Q1–Q4).
2. **Physical Conservation**: Power balance `P_buy(t) + P_pv(t) + P_dis(t) >= P_load(t) + P_ch(t)` (plus EV load where applicable); SOC recursion `E(t) = E(t-1) + eta_c * P_ch(t)*dt - P_dis(t)*dt/eta_d` clamped to `[SOC_min, SOC_max]`, no simultaneous charge+discharge cheat.
3. **Deep Evolution Audit**: Vary rolling-horizon MPC window length, tariff forecast error sensitivity, and battery degradation penalty weights cleanly via CLI/parametric sweeps without inventing unverified numbers.
