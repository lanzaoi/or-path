# Knowledge corpus index (Pi RAG) — v3 Phase 2

**Consumer:** Pi research via hybrid retrieve — not a human website.  
**Rebuild:** `orpath.bat knowledge-sync`  
**Law:** numbers only from solve+validate; corpus never authoritative optima.

## Scale snapshot

| Metric | Target | Notes |
|--------|--------|-------|
| `papers/**/*.md` | ≥50 | includes lit/ + `_from_mineru/` |
| with `- title:` + `- source:` | ≥50 | metadata gate |
| `papers/lit/` | shortlist notes | from `or_papers_top*.json` |
| `_from_mineru/` | preprocess outputs | real PDF or fixture |
| chunks after ingest | ≥150 | |

Re-count after `knowledge-sync` / `phase2-real-corpus-gate`.

## Tables

### A. Literature shortlist (`papers/lit/`)

Materialized by:

```bat
.venv-314\Scripts\python.exe scripts\materialize_or_literature_corpus.py --top 45 --clear-lit --normalize-existing
```

Source: `knowledge/or_papers_top500.json` (Crossref/arXiv shortlist — **metadata notes, not full PDF text**).  
Each file has `kind/title/source/domain/doi`.

### B. Curated paper-notes (`papers/*.md`)

Teaching notes: SP/TSP/VRP/poly/HiGHS/CP-SAT/heuristics/…  
Normalized with `title` + `source: curated` when missing.

### C. MinerU path (`papers/_from_mineru/`)

| Kind | Meaning |
|------|---------|
| `or_sample_01.md` | Phase1 sample PDF preprocess |
| `fixture_*.md` | Offline fixture |
| `mineru_lecture_*.md` | Scale seeds (synthetic preprocess shape) |

### D. skills/ · lessons/

From `knowledge-export` / `knowledge-sync` (allowlist).

## Not in corpus

- Contest PDF binaries (use `inbox_pdf/` + preprocess)
- `*-solution.json` / validate optima dumps
- `README.md` (skipped by ingest)

## Commands

```bat
orpath.bat knowledge-lit-materialize
orpath.bat knowledge-sync
orpath.bat phase2-real-corpus-gate
```

## Fulltext OA batch (2026-08-04)

| Item | Path / count |
|------|----------------|
| OA PDF inbox | `knowledge/inbox_pdf/or_fulltext/` (~87 PDFs) |
| Extracted md | `knowledge/corpus/papers/_from_mineru/r*.md` |
| Download manifest | `knowledge/or_fulltext_download_manifest.json` |
| Script | `scripts/download_or_fulltexts.py` |

Attempted all Top500 via Unpaywall/OpenAlex/S2/arXiv. **Paywalled → not downloaded** (no piracy). Then `knowledge-preprocess --no-cloud` + `knowledge-sync`/ingest.

## lit_abs — abstract + modeling only (copyright-minimizing)

| Path | Role |
|------|------|
| `corpus/papers/lit_abs/*.md` | Top500 abstract + core modeling sketch |
| `archive/oa_fulltext_hold/` | Prior OA fulltext extracts held out of active corpus |

No paywalled body text. Numbers still only from solve+validate.

## lit_abs Top-200 (active)

Active set: **200** notes in `corpus/papers/lit_abs/` (~184 with public abstract; rest title+modeling pad).
Overflow: `archive/lit_abs_overflow/`.
Manifest: `knowledge/or_lit_abs_top200_manifest.json`.

