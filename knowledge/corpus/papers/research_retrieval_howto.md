# How research should use retrieval


- kind: paper-note
- title: How research should use retrieval
- source: curated

- kind: paper-note
- domain: general_or
- source: curated

## Artifact

`notes/<slug>-retrieval.json` from `node_retrieve` when `knowledge_mode` is seed/hybrid.

## Practice

1. Open retrieval path from brief
2. Prefer hits with `source_path`
3. Fill evidence table with chunk_ids
4. Never copy a number from a chunk as proven optimum

## Modes

- `off`: no retrieval required
- `seed`: domain seed graph facts
- `hybrid`: BM25/FTS + semantic RRF over corpus
