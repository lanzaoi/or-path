# VRP with Time Windows — OR-Path T3 fixture

Capacitated VRP **with time windows**, 2 vehicles (capacities [10,10]), depot D, customers A B C E F.

Same spirit as fixtures/t2/vrp_multi but adds time windows and service times.

- vehicle_count=2; total demand=18 requires both vehicles (single vehicle capacity-infeasible).
- travel time = rounded Euclidean distance (unit speed, integer).
- time_windows: node_id -> [ready_time, due_time] (ints; depot [0,1000]).
- service_times: node_id -> int minutes (depot=0).
- Coordinates tweaked slightly from T2 base for TW feasibility while keeping spirit.
- Problem is TW-feasible with the 2-vehicle split (verified by manual route timing).

Numbers / objective / routes come **only** from solve tools + validate. No optima claimed in this fixture.

This is for testing CVRPTW support in the OR-Path pipeline.
