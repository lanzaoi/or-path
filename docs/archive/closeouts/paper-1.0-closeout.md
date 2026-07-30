# OR-Path Paper Protocol 1.0 — P2/P3 Closeout

**Date:** 2026-07-29  
**Method:** Same as P0/P1 — read Feynman `src/workbench/*` contracts, re-implement natively in Python/LG.  
**Not:** file-level copy of TS workbench / PaperRank / org DB.

---

## P2 (from Feynman deep source → OR native)

| ID | Feynman source idea | OR-Path implementation | Status |
|----|---------------------|------------------------|--------|
| **P2-A** | `artifact-versions.ts` + checksum parent chain | `orpath/artifact_versions.py` → `outputs/.artifacts/<slug>-versions.json` | DONE |
| **P2-B** | `artifact-snapshots` before/after (lite) | version chain skips unchanged sha256; no full blob store (size-conscious) | DONE (lite) |
| **P2-C** | `research/contracts.ts` ResearchRun v1 | `orpath/research_run.py` `orpath.researchRun.v1` + validate | DONE |
| **P2-D** | `annotations.ts` structured feedback | `orpath/annotations_lite.py` from review FATAL/MAJOR + quotes | DONE (file-native) |
| **P2-E** | lab CHANGELOG continuity | `orpath/lab_continuity.py` → `outputs/.lab/CHANGELOG.md` | DONE |
| **P2-F** | figure with data fidelity | mermaid HTML from `path`/`tour`/objective only | DONE (minimal) |

### Intentionally still out (not P2 1.0)

| Item | Why |
|------|-----|
| alphaXiv / PaperRank / OpenAlex full stack | Literature triage product; OR has retrieval+R1 |
| Workbench UI + SQLite org ledgers | Desktop product shell |
| Full content snapshot files (10MB blobs) | Version hash chain sufficient for 1.0 audit |
| HF datasets / figure-composer skill pack | Optional polish |

---

## P3 — residual synthesis → 1.0 closed

P3 is **not a new tech stack**. It is the **integration closeout**:

| P3 item | Deliverable |
|---------|-------------|
| **P3-1** Unified gate | `scripts/paper_1_0_gate.py` / `orpath.bat paper-1.0-gate` |
| **P3-2** Provenance declares stack | `paper_protocol: P0+P1+P2+P3` |
| **P3-3** ResearchRun primary artifact | paper or solution marked primary; validate fails otherwise |
| **P3-4** Doc closeout | this file + gap doc update |
| **P3-5** Topology still green | `t3_lg_gate` with cite_pack |

### 1.0 definition of done (paper knowledge loop)

```text
retrieve → research(evidence gate)
  → model → solve → validate
  → draft → cite(claim_map+ledger) → review(annotations)
  → revise(proof+re-cite)? → provenance
       + versions + research_run + lab changelog + figure
```

**Numbers truth** remains solve+validate+R2.  
**Claim truth** = claim_map + claim_ledger (not full NLI).  
**Process truth** = research_run + versions + provenance.

---

## Commands

```bat
orpath.bat paper-gate
orpath.bat paper-1.0-gate
orpath.bat gate-t3
```

Expect: `PAPER_1_0_PASS` / `P3_CLOSEOUT_PASS` / `PASS: t3_lg_gate`.

---

## Honesty

- 1.0 paper protocol is **complete for OR-Path portfolio narrative**.  
- It is **not** a clone of Feynman workbench.  
- Live dspro multi-agent prose quality remains orthogonal; gates keep numerics honest.
