# T2 Evidence

**Date:** 2026-07-29  
**Gates:** `t2_gate` PASS · `t2_gate_cloud` PASS · `t1_gate` PASS  

## Live multi-agent isolation — HARD PASS

Machine gate: `scripts/t2_multiagent_isolation.py` (also inside `t2_gate`) → **PASS**  
Doc: `docs/t2-multiagent-isolation.md`  
JSON: `outputs/t2-multiagent-isolation-proof.json`

### Fresh t2-iso triad (2026-07-29)

| runId | agent |
|-------|-------|
| `0f28b9a7` | or-researcher |
| `f47ac4e0` | or-modeler |
| `a92616cb` | or-writer |

cwd = `C:\Users\Lanzao\Desktop\agent` (not OOP). Separate `*_transcript.jsonl` each.  
Solution objective **45**, validate ok, schema no optima, R2 on `papers/t2-iso-paper.md`.

### Prior t2-live triad (also valid)

`c8ef47e5` researcher · `76b842dd` modeler · `79afa49f` writer

## Engineering gates

```text
pytest tools knowledge_svc → 25 passed
scripts/t2_gate.py → PASS
scripts/t2_gate_cloud.py → PASS (embed live 1024; hybrid hits; R1 arxiv online; Cognee LOCAL_FALLBACK on 503)
scripts/t1_gate.py → PASS
```

## Fixtures

| id | objective | source |
|----|-----------|--------|
| tsp_n8 | 45 | ortools-routing freeze |
| vrp_multi | 58 | ortools-routing freeze |
| shortest_path | 42 | mock/networkx |

## Bridge + memory

- Bridge: `orpath/pi_bridge.py`, e.g. `outputs/t2-live-bridge-tsp-pi-bridge.json`
- pi-memory: installed project-local `npm:@samfp/pi-memory` in `.pi/settings.json`; localPath `.pi/memory`

## OpenPi GUI screenshot

- **File:** `docs/t2-openpi-screenshot.png` (captured 2026-07-29)
- **Shows:** OpenPi chrome + DeepSeek V4 Flash + T2 TSP summary (objective **45**, tour matches gold, paths under `Desktop\agent\...`)
- **Caveats (honest):**
  1. Session folder bar shows `C:\Users\Lanzao\Desktop\OOP` (wrong workspace root for OR-Path product; artifacts paths still correctly point at `Desktop\agent`).
  2. UI text admits **subagent tool unavailable** → roles ran **sequentially in one thread** (role-fidelity cosplay), **not** real pi-subagents isolation.
  3. Sidebar git error: OOP is not a git repo (noise for this session).
- **Real multi-agent isolation proof remains CLI:** `.pi-subagents/artifacts/c8ef47e5_*` / `76b842dd_*` / `79afa49f_*` + `docs/t2-live-evidence-board.png`.
- **GUI DoD:** screenshot **file present** (Q1 visual). Do **not** claim this frame alone proves live subagent isolation.

## Specs / plan

- `specs/` · `.hermes/plans/2026-07-29_105620-t2-thick-full-stack.md`
