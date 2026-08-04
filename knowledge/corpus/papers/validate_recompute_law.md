# Validate recompute law


- kind: paper-note
- title: Validate recompute law
- source: curated

- kind: paper-note
- domain: general_or
- source: curated product law

## Principle

`gate_validate` / `validate_solution` **recomputes** objective and feasibility from solution geometry — does not trust prose.

## Per class (examples)

- SP: sum edge weights along path
- TSP: tour length
- VRP: sum route lengths + capacity checks
- Polyomino: coverage, non-overlap, connectivity + objective vs placement count when applicable

## Agent

After solve, always expect validate artifact; research must not pre-empt validate.
