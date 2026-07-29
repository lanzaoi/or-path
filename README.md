# OR-Path Multi-Agent / Graph-OR Agent

Local-first workbench: **Pi + pi-subagents + LangGraph + solver tools + knowledge vertical**.

Primary UI: **OpenPi** (`openpi.bat`). Secondary: Pi TUI (`pi.bat`).  
Law: **`specs/`** (SDD). Plans: `.hermes/plans/`. Not Feynman-primary. Not Hermes runtime.

## Quick start (Windows)

```bat
cd /d C:\Users\Lanzao\Desktop\agent
:: or any install copy — set ORPATH_HOME if needed
orpath.bat doctor
orpath.bat isolation
set PYTHONNOUSERSITE=1
.venv-314\Scripts\python.exe -m pip install -r requirements.txt
orpath.bat gate
```

Relocatable install: `docs/t2-relocatable.md` (`ORPATH_HOME` / `ORPATH_WORKDIR`).

## Status

| Milestone | Doc |
|-----------|------|
| **T1 CLOSED/PASS** | `docs/t1-closeout.md` |
| **T2 gates PASS** (screenshot pending human) | `docs/t2-closeout.md` |
| Specs | `specs/README.md` |
| T2 smoke | `docs/t2-smoke.md` |

## Layout

```text
specs/               SDD living law
fixtures/t1|t2/      Gold cases (SP, TSP n=8, multi-vehicle VRP)
tools/               solve_* validate R1/R2 schema
orpath/              LG T1 + T2 runners, pi_bridge
knowledge_svc/       MinerU, hybrid retrieve, Cognee, seed graph
knowledge/           corpus, seed_graph, indexes (caches gitignored)
scripts/t*_gate.py   Semi-auto DoD
.pi/agents/or-*.md   Pi subagents
```

## Dual path

- **CI / gate:** deterministic LG nodes + tools  
- **Live multi-agent:** Pi/OpenPi + pi-subagents  
- **Bridge:** `ORPATH_LIVE_PI=1` evidence via `orpath/pi_bridge.py`

## Stack locks

Pi harness · pi-subagents · LangGraph · OR-Tools/NetworkX numbers + validate · DeepSeek · OpenPi ·  
MinerU/LightRAG+BM25/FTS/RRF/Cognee · Agent Teams/bus out · specs-first SDD
