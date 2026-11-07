# OR-Path PDF Inbox (`knowledge/inbox_pdf/`)

Drop raw Operations Research PDFs here for MinerU / local PDF preprocessing into `knowledge/corpus/papers/_from_mineru/`.

## Commands

```bash
# Offline / local PDF text & fixture preprocessing
./orpath.sh knowledge-preprocess --offline-fixture --no-cloud

# Cloud MinerU batch preprocessing (requires MINERU_API_TOKEN in .env)
./orpath.sh knowledge-mineru --preprocess
```

## Pipeline

1. `knowledge/inbox_pdf/*.pdf`
2. `knowledge/mineru_out/<doc_id>/content.md`
3. `knowledge/corpus/papers/_from_mineru/<doc_id>.md`
4. `notes/mineru-last.json` (manifest)
5. `python -m knowledge_svc.ingest` (hybrid BM25 + BGE-M3 index)
