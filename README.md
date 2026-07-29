# OR-Path Multi-Agent / Graph-OR Agent

Local-first workbench for operations-research agents: **Pi + pi-subagents + LangGraph + solver tools**.

Primary UI: **OpenPi** (`openpi.bat`). Secondary: Pi TUI (`pi.bat`).  
Not Feynman-primary. Not Hermes runtime (Hermes may only navigate/code).

## Quick start (Windows)

```bat
cd /d C:\Users\Lanzao\Desktop\agent
:: Python 3.14 venv already at .venv-314 — recreate if needed:
:: py -3.14 -m venv .venv-314
.venv-314\Scripts\python.exe -m pip install -r requirements.txt

set PYTHONNOUSERSITE=1
.venv-314\Scripts\python.exe scripts\t1_gate.py
.venv-314\Scripts\python.exe scripts\t1_negatives.py
```

**Important:** set `PYTHONNOUSERSITE=1` so a broken user-site `pydantic` does not shadow the venv (seen on this machine).

## T1 status

| Slice | Command / path |
|-------|----------------|
| Core evidence | `docs/t1-evidence.md` |
| Day 2–3 thicken | `docs/t1-day2-day3.md` |
| Smoke prompt | `docs/t1-smoke.md` |
| Portfolio talk | `docs/t1-portfolio-talk.md` |
| LG pipeline | `orpath/run_t1.py` |
| Pi agents | `.pi/agents/or-*.md` |
| Live subagent proof | `.pi-subagents/artifacts/*_transcript.jsonl` |

## Layout

```text
.pi/agents/          Pi subagent definitions (or-*)
fixtures/t1/         Smoke cases
tools/               solve_* + gates + pytest
orpath/              LangGraph stage machine
scripts/t1_gate.py   Semi-auto DoD
scripts/t1_negatives.py
docs/                Smoke, evidence, day2-3, talk track
openpi/              Electron UI (git submodule-like tree)
runtime/             npm Pi CLI
```

## Dual path

- **CI / gate:** deterministic LG nodes + tools  
- **Live multi-agent:** Pi/OpenPi + `pi-subagents`  

Both are intentional; see `docs/t1-day2-day3.md`.

## Stack locks (summary)

Pi harness · pi-subagents · LangGraph · OR-Tools/NetworkX numbers · DeepSeek · OpenPi UI ·  
LightRAG/MinerU/Cognee later · Agent Teams / message bus out of main path.

Details: `IDEA.md`, skill `or-path-multi-agent`.
