# CVRP capacity modeling checklist


- kind: paper-note
- title: CVRP capacity modeling checklist
- source: curated

- kind: paper-note
- domain: vrp
- source: curated

## Essentials

- Depot + customers with **demands**
- Fleet with **capacities** and **vehicle_count ≥ 2** for T2-style multi-vehicle
- Single vehicle often **infeasible** under tight capacity — good test design

## Schema (model stage)

Include structural fields only. **Forbidden:** `routes`, `objective`, per-vehicle load solutions.

## Validate

- Every customer visited once
- Load never exceeds capacity on any vehicle
- Distance objective recomputed from routes geometry
