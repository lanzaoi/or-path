# HiGHS for LP/MIP


- kind: paper-note
- title: HiGHS for LP/MIP
- source: curated

- kind: paper-note
- domain: general_or
- source: curated

## Role

HiGHS is a high-performance open LP/MIP solver. In OR-Path it appears as:

- Optional dual track / MCP (`mcp-highs`) for generic LP/MIP JSON
- **Not** the default polyomino or TSP claim ladder

## Modeling

- Variables, constraints, sense (min/max)
- Prefer standard form; integer flags for MIP

## Numbers

Any objective from HiGHS must still pass product validate when wired; MCP demos are not contest submission authority by default.
