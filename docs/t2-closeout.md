# T2 Closeout

**Date:** 2026-07-29  
**Status:** **CLOSED — PASS**  
Includes: engineering gates, **hard multi-agent isolation**, **relocatable install launcher** (`ORPATH_HOME`).

## What shipped

| Layer | Deliverable |
|-------|-------------|
| Specs SDD | `specs/**` |
| Contracts / solvers / validate | mock · networkx · ortools · validate · R1/R2 |
| Fixtures | SP 42 · TSP 45 · VRP multi 58 |
| LG T2 | `orpath/run_t2.py` |
| Knowledge vertical | `knowledge_svc/` + seed/corpus |
| Isolation | `scripts/t2_multiagent_isolation.py` (in `t2_gate`) |
| Relocatable | `orpath.bat` / `orpath.sh` · `scripts/orpath_doctor.py` · `orpath/paths.py` · `docs/t2-relocatable.md` |
| Live multi-agent | runIds `0f28b9a7` / `f47ac4e0` / `a92616cb` (+ earlier t2-live triad) |
| Gates | `t1_gate` · `t2_gate` · `t2_gate_cloud` |
| Docs | `docs/t2-*.md` |

## Verify

```bat
cd /d <any-copy-of-install>
set PYTHONNOUSERSITE=1
orpath.bat doctor
orpath.bat isolation
orpath.bat gate
```

Or without launcher:

```bat
set ORPATH_HOME=%CD%
.venv-314\Scripts\python.exe scripts\orpath_doctor.py
.venv-314\Scripts\python.exe scripts\t2_multiagent_isolation.py
.venv-314\Scripts\python.exe scripts\t2_gate.py
```

## Design note (folder ≠ product)

Multi-agent packages/agents live under **install home** (`ORPATH_HOME`), not
whatever random folder OpenPi last opened. OpenPi must still be pointed at the
install home for GUI demos; data may use `ORPATH_WORKDIR`.

## Next

T3+ when requested. Do not reopen T2 unless doctor/isolation/gates regress.
