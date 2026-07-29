# OR-Path paper template (portfolio / technical)

Use as narrative arc for `papers/<slug>.md` (P1-1).

1. **Title**
2. **Abstract** — problem class + solver honesty (exact vs search)
3. **Problem statement** — fixture / NL statement
4. **Related modeling notes** — research evidence table only
5. **Method / formulation** — schema, no optima
6. **Results** — solution.json only (objective, path|tour|routes)
7. **Validation** — validate report path
8. **Limitations** — scale, non-proven when applicable
9. **Sources** — whitelist ∪ research paths ∪ solution

Rules:
- Never invent objective/path/tour/routes.
- If `meta.proven_optimal` is not true, do not claim global optimum.
- Drafts live in `outputs/.drafts/<slug>-{draft,cited,revised}.md` before `papers/`.
