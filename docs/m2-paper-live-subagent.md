# M2 — Paper-loop live subagent glue

**Status:** M2 implemented  
**Depends on:** M1 (`orpath/subagent_runtime.py`)

## What changed
| Piece | Role |
|-------|------|
| `orpath/paper_live_subagent.py` | cite/review short-lead spawn + merge helpers |
| `orpath/nodes.py` | stage nodes + product wrap + live leads |
| `orpath/state.py` | `gate_subagent_ok`, `live_subagent` |
| `scripts/paper_gate.py` / `paper_1_0_gate.py` | force `ORPATH_LIVE_SUBAGENT=0` (deterministic) |
| `scripts/subagent_gate.py` | `M2_PAPER_LIVE_GLUE_PASS` |

## Behavior
```
draft_paper  → lead-owned scripted render (unchanged)
cite_pack    → [live] short lead + subagent or-verifier → then R1/claim scripts
review_pack  → [live] short lead + subagent or-reviewer → then R2/R1/claim + merge review
revise / provenance → unchanged
```

- **Live on** when env complete and `ORPATH_LIVE_SUBAGENT` not `0` (default).
- **Live off** for paper gates via env `ORPATH_LIVE_SUBAGENT=0`.
- Live + failed subagent (no tool call / no output) → **hard fail** after 1 retry (M1 retry count).
- Lead must not silently author cited/review when live is on.

## Enable live paper subagents
```bat
set ORPATH_LIVE_SUBAGENT=1
orpath.bat run --problem-id shortest_path --solve-mode mock --knowledge-mode seed --slug demo-live
```

## Gates
```bat
orpath.bat subagent-gate
orpath.bat paper-gate
orpath.bat paper-1.0-gate
```

## Not M2
- research fan-out, modeler spawn, bridge default live → **M3**
