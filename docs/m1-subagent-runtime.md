# M1 — Subagent runtime (Feynman-aligned)

**Status:** M1 implemented  
**Date:** 2026-07-29

## Goal
Replace multi-agent **cosplay** with verifiable Pi **`subagent` tool** infrastructure.

## Delivered
| Piece | Path |
|-------|------|
| Runtime | `orpath/subagent_runtime.py` |
| Gate | `scripts/subagent_gate.py` → `M1_SUBAGENT_GATE_PASS` |
| Agents | `.pi/agents/or-*.md` thickened (tools + output contract + subagent laws) |
| CLI | `orpath.bat subagent-gate` |

## Laws encoded
- Forced stages: `research`, `cite`/`cite_pack`, `review`/`review_pack`, `model`
- Lead-owned: `draft`/`draft_paper`, `provenance`, …
- Env incomplete (no Pi / no pi-subagents / no key) → **fail** (no mock green)
- Detector looks for tool name `subagent` + `or-*` agent assignments in lead logs
- Briefs on disk: `write_task_brief` → `outputs/.plans/<slug>-<stage>-brief.md`
- `spawn_lead(..., dry_run=True)` for CI command assembly without tokens

## Not in M1
- LG nodes calling spawn_lead → **M2/M3 done** (`docs/m2-paper-live-subagent.md`, `docs/m3-graph-live-subagent.md`)
- Live multi-subagent paper loop → **M2**
- Research fan-out + modeler → **M3**

## Commands
```bat
orpath.bat subagent-gate
python scripts/subagent_gate.py
```

## Next (M2)
Wire `cite_pack` / `review_pack` nodes to `spawn_lead` + require log evidence before gate pass.
