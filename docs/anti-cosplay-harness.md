# Anti-cosplay harness (ruthless)

**Status:** implemented  
**Module:** `orpath/subagent_harness.py`

## What changed
Lead agents for forced stages **no longer have `write`/`edit` tools**.

```
--tools read,bash,subagent,subagent_wait,subagent_supervisor,grep,find,ls
--mode json
--append-system-prompt ANTI-COSPLAY HARD LAW
```

So the lead **cannot** author `*-cited.md` / `*-review.md` / schema itself.
It **must** call `subagent` → child agent writes the file.

## On cosplay
1. Detect no real `toolCall`/`name=subagent` in JSON log  
2. **Restore/quarantine** lead-touched outputs  
3. Retry (default 3) with harsher prompt  
4. Still fail → `gate_subagent_ok=false` (hard fail when live on)

## Wired into
| Stage | Path |
|-------|------|
| cite | `paper_live_subagent` → harness |
| review | `paper_live_subagent` → harness |
| model | `graph_live_subagent` → harness |
| research | lead also `LEAD_TOOLS_NO_WRITE`; Python merges child notes |

## Smoke
```bat
set ORPATH_LIVE_SUBAGENT=1
python -c "from orpath.subagent_harness import run_forced_subagent_stage; ..."
```

## Docs cross-ref
- M1 runtime, M2 paper live, M3 graph live
