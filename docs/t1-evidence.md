# T1 Evidence

Date: 2026-07-29  
Operator: Hermes Agent (Q8=A)

## Day 1 — Core automated + live multi-agent

- [x] `scripts/t1_gate.py` → PASS  
- [x] pytest tools → 7 passed  
- [x] provenance: `outputs/t1-shortest-path.provenance.md`  
- [x] Live subagents **or-researcher** (`d31502fe`), **or-modeler** (`3611d41c`)  
- [x] Transcripts under `.pi-subagents/artifacts/*_transcript.jsonl` (local; gitignored — regenerate via Pi CLI)  
- [x] Schema gate + solve_mock objective **42**

## Day 2 — Writer + negatives

- [x] Live **or-writer** `e23acda5` → `papers/t1-live-paper.md`  
- [x] Live **or-verifier** `41742aef` → `outputs/t1-live-verify-notes.md`  
- [x] R1/R2 on live paper → PASS  
- [x] Summary: `outputs/t1-live-day2-summary.md`  
- [x] Negatives: `scripts/t1_negatives.py` → `outputs/t1-negatives-proof.md`  
- [x] HUMAN_REQUIRED ceiling simulated on persistent bad_draft (max_revise=2)

## Day 3 — Docs + git

- [x] `docs/t1-day2-day3.md`  
- [x] `docs/t1-portfolio-talk.md`  
- [x] `README.md` (PYTHONNOUSERSITE note)  
- [x] git init + baseline commit on `agent/`  

## OpenPi GUI (optional non-blocking)

- [ ] Screenshot subagent cards in OpenPi (CLI already proves multi-agent)  
  Steps: `docs/t1-day2-day3.md` § OpenPi handoff  

## Conclusion

**T1-core: PASS**  
**T1 three-day thicken (minus optional GUI shot): PASS**  
Next product work: T2 solver contracts / knowledge stack — not re-opening T1 DoD.
