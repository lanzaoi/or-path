# OR modeling discipline for Pi (corpus)


- kind: paper-note
- title: OR modeling discipline for Pi (corpus)
- source: curated

- kind: paper-note

## Pipeline roles

1. **Research** — literature + retrieval paths; no numeric optima claims without solution files.
2. **Model** — JSON schema only; forbidden: objective, path, tour, routes, placements.
3. **Solve** — tools only write objective / geometry of solution.
4. **Validate** — recompute; gate_validate is authority for feasibility consistency.

## Knowledge mode

- `seed` — domain seed graph (light).
- `hybrid` — BM25/FTS + semantic + RRF over `knowledge/corpus` (for **Pi**, not a human website).
- Retrieval artifact: `notes/<slug>-retrieval.json` — research must be able to read it.

## Memory vs skill vs RAG

- **Skill** — executable procedure (load on demand).
- **Lesson / process memory** — how a run went; never authoritative numbers.
- **RAG** — runtime reference book for Pi; optional copies of skills/lessons after export.

## Forbidden

- Inventing optima in prose.
- Dumping solution JSON into knowledge corpus as “training data”.
- Claiming RAG fine-tunes the model weights.
