# CORPUS layout (Pi RAG bookcase)

**Status:** living inventory · 2026-08-04 push

| Path | Role | Approx count |
|------|------|--------------|
| `knowledge/corpus/papers/**/*.md` | Main text for hybrid retrieve | **419** md |
| `.../papers/lit_abs/` | Literature abstracts + modeling notes (top list) | **201** |
| `.../papers/_from_mineru/` | PDF preprocess sidecars | **101** |
| `.../papers/*.md` (root notes) | Short OR method notes (CG, BFD, ALNS, …) | **117** |
| `knowledge/corpus/skills/` | Allowlisted skill **search copies** | export via allowlist |
| `knowledge/corpus/lessons/` | Lesson search copies | seeds + promote |
| `knowledge/lessons/*.json` | Canonical lessons (`orpath.lesson.v1`) | tracked seeds |
| `knowledge/or_papers_top500.json` | Bibliography checklist (not fulltext) | meta |
| `knowledge/export_allowlist.txt` | Which skills may enter RAG | — |

## Rules

1. RAG is for **Pi research method hints** — not authoritative optima.  
2. Do not put `solution.json` / objective tours into corpus.  
3. Product default retrieve mode = **hybrid** (see `ORPATH_KNOWLEDGE_MODE`).  
4. Indexes live under install home (`knowledge_svc`); cases only get `notes/*-retrieval.json`.

## Rebuild

```bat
set ORPATH_KNOWLEDGE_PROFILE=research
orpath.bat knowledge-sync
orpath.bat knowledge-retrieve --query "cutting stock column generation" --mode hybrid --topk 5
```

## Not in git (optional local)

- `knowledge/inbox_pdf/` large PDFs  
- `knowledge/chunks/*.jsonl` runtime index lines  
- build/ingest logs  
