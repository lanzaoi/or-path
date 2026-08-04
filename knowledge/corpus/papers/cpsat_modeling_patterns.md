# CP-SAT modeling patterns (OR-Tools)


- kind: paper-note
- title: CP-SAT modeling patterns (OR-Tools)
- source: curated

- kind: paper-note
- domain: general_or
- source: curated

## Common patterns

- Bool / Int vars
- Linear constraints, `AddCircuit`, `AddNoOverlap`, `AddElement`
- Objective: minimize sum of cost expressions
- `CpSolver` status: OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN

## OR-Path uses

- Polyomino cover placements
- Small TSP circuit (optional)
- Scheduling-like subproblems

## Discipline

Modeler writes schema only; CP-SAT runs in solve tools; status and objective stay in solution JSON.
