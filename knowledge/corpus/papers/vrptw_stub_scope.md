# VRPTW time windows — scope stub


- kind: paper-note
- title: VRPTW time windows — scope stub
- source: curated

- kind: paper-note
- domain: vrp
- source: curated
- t2_status: stub_only

## Idea

Each customer has [ready, due] service window; waiting may be allowed; lateness often forbidden.

## OR-Path honesty

- T2 multi-vehicle CVRP is **without** time windows
- Seed graph may list `time_window` as optional stub constraint
- Do not claim TW optima unless a registered solve_mode + validate exists

## Research tip

Cite TW literature for modeling inspiration; keep schema free of fabricated time-feasible routes.
