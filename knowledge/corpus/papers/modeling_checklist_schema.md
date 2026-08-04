# OR modeler schema checklist


- kind: paper-note
- title: OR modeler schema checklist
- source: curated

- kind: paper-note
- domain: general_or
- source: curated product law

## Must

- `problem_id` + `problem_class` (or registered alias)
- Structural keys for the class (graph / board / demands / …)

## Forbidden in schema

- `objective`, `path`, `tour`, `routes`, `placements` (solution shapes)
- Free-prose “optimal is X”

## Repair

gate_schema red → model repair bounded; then solve; validate red → solver tune bounded → else HUMAN_REQUIRED.
