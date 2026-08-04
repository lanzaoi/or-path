# MILP formulation tips for LLM modelers


- kind: paper-note
- title: MILP formulation tips for LLM modelers
- source: curated

- kind: paper-note
- domain: general_or
- source: curated

## Tips

- Define index sets first
- Separate data (params) from decisions (vars)
- Prefer linear over big nonlinear tricks when possible
- Document units

## OR-Path

Schema carries structure; numeric data may live in fixtures/JSON beside schema; solve tools own the MIP/CPSAT call.
