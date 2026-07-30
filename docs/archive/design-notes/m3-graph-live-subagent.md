# M3 — Full-graph live subagent (research fan-out + modeler)

**Status:** M3 implemented  
**Depends on:** M1 runtime, M2 paper live

## Scope
| Stage | Live behavior |
|-------|----------------|
| research | scale off/narrow/wide → 0/1/2× `or-researcher` via lead `subagent` |
| model | short lead → `or-modeler` → schema.json (no optima keys) |
| cite/review | M2 (verifier / reviewer) |
| draft | lead-owned scripted paper |
| solve/validate | **never** LLM subagent |
| bridge_pi | unchanged; `--live-pi` also turns on live_subagent |

## Scale rules
- `knowledge_mode=off` → research scale **off** (no researcher spawn)
- `seed` + shortest_path → **narrow** (1 researcher)
- `hybrid` or VRP → **wide** (2 parallel researchers, `failFast: false`)
- override: state `research_scale` ∈ {off,narrow,wide}

## Enable / disable
```bat
REM product live (default when env ready and ORPATH_LIVE_SUBAGENT unset)
orpath.bat run --problem-id shortest_path --solve-mode mock --knowledge-mode seed --live-subagent --slug m3-live

REM force off (gates do this)
set ORPATH_LIVE_SUBAGENT=0
orpath.bat run ... --no-live-subagent
```

`--live-pi` implies live_subagent on.

## Artifacts
```
outputs/.agents/<slug>/research-subagent.json
outputs/.agents/<slug>/model-subagent.json
outputs/.agents/<slug>/cite-subagent.json
outputs/.agents/<slug>/review-subagent.json
outputs/.plans/<slug>-research-T*.md
notes/<slug>-research-*.md
```

## Gates
```bat
orpath.bat subagent-gate   REM M1+M2+M3_PASS
orpath.bat paper-gate      REM ORPATH_LIVE_SUBAGENT=0
```

## Hard fail (live on)
- research/model/cite/review: no `subagent` tool call or missing outputs after retry → stage fail
- model: schema with solution-shaped keys → fail
