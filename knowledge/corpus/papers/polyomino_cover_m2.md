# Polyomino cover — agent briefing (corpus for Pi RAG)


- kind: paper-note
- title: Polyomino cover — agent briefing (corpus for Pi RAG)
- source: curated

- kind: paper-note
- domain: polyomino_cover

## Modeling

- `problem_class`: `polyomino_cover` (aliases: polyomino, poly, tiling_cover).
- Schema: board / rows+cols / pieces — **no** objective, placements, or solution-shaped keys.
- Product solve: `solve_mode=polyomino` → `tools/solve_polyomino.py` (CP-SAT).

## Numbers

- Q1.1 min cover 4×4 golden **objective=6** only after solve+validate.
- Full contest multi-Q bank: `scripts/pack_b_polyomino_case.py` (not watch-run alone).

## Pitfalls

- Unknown class historically blocked at gate_schema — registry must list polyomino_cover.
- Do not treat heuristic or prose as proven optimal.
- Large boards (25×20, 30×30): prefer bank artifacts; do not default expensive re-solve.

## See also

- `docs/m2-polyomino.md`
- skills: `or-numbers-truth`, `or-solver-select`
