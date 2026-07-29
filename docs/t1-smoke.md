# OR-Path T1 smoke

## Prerequisites

- Workspace: `C:\Users\Lanzao\Desktop\agent`
- DeepSeek configured in OpenPi / `~/.pi/agent`
- `pi-subagents@0.37.2` (see `.pi/settings.json` and user settings)

## Automated gate

```bat
.venv-314\Scripts\python.exe scripts\t1_gate.py
```

Expected: `PASS: t1_gate` and pytest green. This runs deterministic LG nodes + tools (CI path).

## OpenPi live multi-agent (required for full T1 DoD)

1. Start `openpi.bat`, open folder `Desktop\agent`
2. Select DeepSeek model
3. Paste:

```text
OR-Path T1 smoke.
Problem: fixtures/t1/shortest_path/problem.md
Rules:
- Use real subagents: or-orchestrator, or-researcher, or-modeler (pi-subagents).
- After schema, run: .venv-314\Scripts\python.exe tools\solve_mock.py shortest_path
- Never invent objective; only cite tool JSON.
- Then or-writer + or-verifier + or-reviewer; max 2 revises.
- Artifacts slug t1-shortest-path under outputs/ and papers/.
```

4. Fill `docs/t1-evidence.md` with paths + screenshots notes.

## Optional NetworkX solve

```bat
.venv-314\Scripts\python.exe tools\solve_ortools.py shortest_path
```

T1 default gate uses mock only.
