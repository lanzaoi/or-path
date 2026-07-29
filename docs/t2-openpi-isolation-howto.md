# OpenPi — real multi-agent isolation (mandatory path)

## Why your last screenshot failed isolation

OpenPi was on `Desktop\OOP` and reported **subagent tool unavailable** → one-thread role-play.

## Do this

1. **Close** the OOP session.
2. Double-click **`openpi-orpath.bat`** in `Desktop\agent`  
   (or OpenPi → Open folder → `C:\Users\Lanzao\Desktop\agent` only).
3. Confirm title bar / folder chip shows **`...\Desktop\agent`**, not OOP.
4. Model: **DeepSeek**.
5. Paste entire contents of `docs/t2-live-prompt.txt`.
6. You must see **separate subagent runs** (cards / fleet / distinct child sessions).  
   If the model says “subagent not available”, **stop** — fix packages, do not accept cosplay.
7. Screenshot → overwrite `docs/t2-openpi-screenshot.png`.

## Machine check (no GUI needed)

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONNOUSERSITE=1
.venv-314\Scripts\python.exe scripts\t2_multiagent_isolation.py
```

Expected: `PASS: t2_multiagent_isolation`  
Proof: `outputs/t2-multiagent-isolation-proof.json` + `docs/t2-multiagent-isolation.md`

This gate is now part of `scripts/t2_gate.py`.
