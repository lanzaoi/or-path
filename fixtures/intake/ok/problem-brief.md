# Problem brief — intake_ok_demo

## Sources
- `fixtures/intake/ok/source.txt` (manual_stub)

## Full problem statement (normalized)
A small demo OR homework with two questions. Units in meters.
Given a complete graph on 3 nodes with positive edge weights in an attached table.
Do not invent solver optima in this brief.

## Subproblems (Q1…Qn)
### Q1
Shortest path from S to T on the given graph. Deliver a model description and later a solver-backed path (solver stage only).

### Q2
TSP on the same 3 nodes (tour returning to start). Deliver tour definition only at solve time.

## Data assets
- `fixtures/intake/ok/source.txt` — problem statement text
- (optional) distance table referenced in statement

## Objectives (qualitative)
1. Primary: minimize total travel distance for each subproblem
2. Secondary: prefer simple explanations

## Constraints (qualitative)
- Non-negative edge weights
- Q2 tour must return to depot/start

## Deliverables
- notes and schema for modeling stage
- solution JSON only after solve tools run

## Ambiguities / OCR gaps
- None for this synthetic fixture.

## Non-goals for intake
- No objective values
- No calling solvers
