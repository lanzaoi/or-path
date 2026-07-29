# T2 Multi-Agent Isolation Proof

**Status: PASS (machine-checked)**

This is **not** OpenPi single-thread role-play. Evidence is separate pi-subagents child runs.

## Criteria

- ≥2 distinct `runId`
- ≥2 distinct `or-*` agents (researcher + modeler minimum)
- Separate `*_transcript.jsonl` per run
- Transcript `cwd` under this `agent` repo
- T2 live solution objective 45 when present

## Runs

| runId | agent | model | transcript |
|-------|-------|-------|------------|
| `3611d41c` | `or-modeler` | `deepseek/deepseek-v4-flash` | `3611d41c_or-modeler_0_transcript.jsonl` |
| `76b842dd` | `or-modeler` | `deepseek/deepseek-v4-flash` | `76b842dd_or-modeler_0_transcript.jsonl` |
| `f47ac4e0` | `or-modeler` | `deepseek/deepseek-v4-flash` | `f47ac4e0_or-modeler_0_transcript.jsonl` |
| `0f28b9a7` | `or-researcher` | `deepseek/deepseek-v4-flash` | `0f28b9a7_or-researcher_0_transcript.jsonl` |
| `c8ef47e5` | `or-researcher` | `deepseek/deepseek-v4-flash` | `c8ef47e5_or-researcher_0_transcript.jsonl` |
| `d31502fe` | `or-researcher` | `deepseek/deepseek-v4-flash` | `d31502fe_or-researcher_0_transcript.jsonl` |
| `41742aef` | `or-verifier` | `deepseek/deepseek-v4-flash` | `41742aef_or-verifier_0_transcript.jsonl` |
| `79afa49f` | `or-writer` | `deepseek/deepseek-v4-flash` | `79afa49f_or-writer_0_transcript.jsonl` |
| `a92616cb` | `or-writer` | `deepseek/deepseek-v4-flash` | `a92616cb_or-writer_0_transcript.jsonl` |
| `e23acda5` | `or-writer` | `deepseek/deepseek-v4-flash` | `e23acda5_or-writer_0_transcript.jsonl` |

Machine proof JSON: `C:/Users/Lanzao/Desktop/agent/outputs/t2-multiagent-isolation-proof.json`

## OpenPi note

If OpenPi is opened on `Desktop\OOP` without project packages, subagent tool may be missing
and the model will cosplay roles. **Always open `Desktop\agent`.**
Isolation DoD is satisfied by Pi CLI + this gate even when a bad OpenPi session cosplays.
