# T1 Day 2–3 thickening plan (after core PASS)

Core T1 (Day 1) is green: multi-agent proof + LG + gates + evidence.  
This doc tracks **full 3-day thickness** without cutting stack locks.

## Status legend

- [x] done
- [ ] remaining
- [~] partial

## Day 2

| Item | Status | Evidence |
|------|--------|----------|
| Live `or-writer` (+ verifier) | [x] | `papers/t1-live-paper.md`, `outputs/t1-live-verify-notes.md`, `outputs/t1-live-day2-summary.md`, `.pi-subagents/artifacts/*or-writer*` / `*or-verifier*` if present |
| R1/R2 on live paper | [x] | day2 summary gate exits 0 |
| Negative schema/draft paths | [x] | `scripts/t1_negatives.py` → `outputs/t1-negatives-proof.md` |
| HUMAN_REQUIRED ceiling logic | [x] | proven via max_revise loop on persistent bad_draft |
| OpenPi GUI checklist | [x] | this file § OpenPi handoff (manual optional screenshot) |

## Day 3

| Item | Status | Evidence |
|------|--------|----------|
| Dev README (venv, PYTHONNOUSERSITE, gates) | [x] | `README.md` |
| git init + baseline commit | [x]/ | `agent/` root repo |
| Portfolio 30s script | [x] | `docs/t1-portfolio-talk.md` |
| Optional: LG node spawns real Pi | [ ] | deferred — dual-path documented (deterministic CI vs live Pi CLI) |
| Optional: pi-memory project-local | [ ] | deferred Task 10 |
| Optional: second problem class fixture | [ ] | deferred T1.1 |

## Dual-path (honest)

| Path | Purpose |
|------|---------|
| `orpath/run_t1.py` | Deterministic CI / `t1_gate` — LG owns stages; nodes write files |
| `pi.bat` / OpenPi + `.pi/agents/or-*` | Live multi-agent isolation proof |
| Both required for full story | CI alone ≠ multi-agent; multi-agent alone ≠ stage machine |

## OpenPi handoff (optional GUI)

1. `openpi.bat` → open folder `C:\Users\Lanzao\Desktop\agent`
2. Model: DeepSeek
3. Paste from `docs/t1-smoke.md` **or** Day2 live prompt in `outputs/t1-live-day2-summary.md`
4. Confirm subagent cards for `or-researcher` / `or-modeler` / `or-writer`
5. Optional screenshot → drop into `docs/t1-evidence.md` GUI section

CLI already satisfies multi-agent DoD; GUI is portfolio polish.

## Commands cheat sheet

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONNOUSERSITE=1
.venv-314\Scripts\python.exe scripts\t1_gate.py
.venv-314\Scripts\python.exe scripts\t1_negatives.py
.venv-314\Scripts\python.exe orpath\run_t1.py --solve-mode mock
```

Live multi-agent (non-interactive example):

```bat
pi.bat -p --provider deepseek --model deepseek-v4-flash --no-session "..."
```

## Exit criteria for “3-day T1 full”

- [x] Day1 core PASS (`docs/t1-evidence.md`)
- [x] Day2 live writer + negatives
- [x] Day3 docs + git baseline
- [ ] Human optional: OpenPi screenshot (not blocking)
