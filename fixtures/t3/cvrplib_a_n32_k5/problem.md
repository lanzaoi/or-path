# CVRPLIB A-n32-k5 baseline

Capacitated vehicle routing problem (CVRP) with one depot, 31 customers, five vehicles, and capacity 100 per vehicle. Distance uses the instance's `EUC_2D` convention, rounded to the nearest integer by the OR-Path adapter.

- Public instance: https://galgos.inf.puc-rio.br/cvrplib/en/download/instance/4
- Public best-known solution: https://galgos.inf.puc-rio.br/cvrplib/en/download/bks/4
- CVRPLIB listing: https://galgos.inf.puc-rio.br/cvrplib/en/instances/1

The public reference objective is 784 and is marked optimal by CVRPLIB. OR-Path's default OR-Tools routing run remains `FEASIBLE` unless it independently proves optimality; the reference is used only to report a gap.
