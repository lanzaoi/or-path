# Fixed hybrid queries (Pi RAG smoke — v1/v2)

Run after `knowledge-sync` or `knowledge-rebuild`.

**Expect:** each query `hits >= 1` and at least one `source_path` under `knowledge/corpus`
(or seed path when intentionally seed-only — hybrid should prefer corpus).

| # | Query | Expect theme | Hint path fragment |
|---|-------|--------------|--------------------|
| 1 | shortest path Dijkstra networkx | SP | sp_networkx / dijkstra |
| 2 | TSP tour OR-Tools routing n=8 | TSP | tsp_ |
| 3 | CVRP capacity multi vehicle routing | VRP | cvrp / vrp |
| 4 | polyomino cover CP-SAT schema | poly | polyomino |
| 5 | objective only from solve validate | numbers-truth | numbers_truth / skill-or-numbers / validate_recompute |
| 6 | HiGHS LP MIP solver | HiGHS | highs |
| 7 | CP-SAT circuit modeling | CP-SAT | cpsat / circuit |
| 8 | time window VRPTW stub | TW stub | vrptw / time_window |
| 9 | schema forbid objective routes | modeling | modeling_checklist / schema |
| 10 | retrieval.json research hybrid | retrieval howto | research_retrieval |
| 11 | lesson polyomino process memory | lesson | lesson / polyomino |
| 12 | skill solver select problem class | skill | skill-or-solver / solver_select |
| 13 | MinerU lecture extract shortest path | mineru | _from_mineru / mineru_lecture |
| 14 | column generation VRP pricing | scale paper | column_generation / vrp |
| 15 | embed mode hybrid semantic stub or live | embed awareness | embed / hybrid / retrieval / semantic |
| 16 | polyomino connectivity CP-SAT placements | poly deep | polyomino_connectivity / polyomino |
| 17 | CasADi nonlinear optimization optimal control | lit shortlist | lit_ / casadi / nonlinear |
| 18 | vehicle routing column generation operations research DOI | lit routing | lit_ / routing / column |

## Runner

```bat
orpath.bat knowledge-eval
:: or: .venv-314\Scripts\python.exe scripts/knowledge_eval.py
```

Does **not** claim SOTA / MRR on public IR benchmarks — product smoke only.
