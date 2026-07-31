# Anti-cosplay harness (ruthless)

**Status:** implemented  
**Modules:** `orpath/subagent_harness.py`, **`orpath/pi_launch_law.py`**

## Hard launch law (2026-07-30)

| Mode | When | Command shape |
|------|------|----------------|
| **SINGLE_LEAD** | 重解脚本、draft-only | `--tools` 可含 write；**禁止**宣称 multi-agent |
| **MULTI_AGENT_HARNESS** | cite/review/model/research live | `--tools read,bash,subagent,…` **无 write/edit** + `--mode json` |

**非法：** `ORPATH_LIVE_SUBAGENT=1` + 裸 `pi -p` + prompt 写 orchestrator/多角色。  
圆管 launcher：

- `outputs/b-tube-cut/logs/launch_pi_resolve.py` → **强制 SINGLE_LEAD**
- `outputs/b-tube-cut/logs/launch_pi_paper_loop.py` → draft SINGLE_LEAD；**cite/review 走 harness**

```bat
:: 真多 Agent 产品路径
orpath.bat run --live-subagent --slug ...
orpath.bat subagent-gate
```

## What harness changed
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
| tube paper loop | `launch_pi_paper_loop.py` → cite/review harness |
| tube resolve | SINGLE_LEAD only (scripts) |

## Smoke
```bat
set PYTHONNOUSERSITE=1
.venv-314\Scripts\python.exe -m pytest tools/test_pi_launch_law.py -q
orpath.bat subagent-gate
```

## Docs cross-ref
- M1 runtime, M2 paper live, M3 graph live
- `orpath/pi_launch_law.py`
