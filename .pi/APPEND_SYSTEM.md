# OR-Path project law (appended to Pi / any host session)

This workspace is **OR-Path Multi-Agent / Graph-OR Agent**. Hermes is not the product runtime.

## Hard laws

1. **Numbers truth:** `objective` / path / tour / routes come **only** from solve tools + validate. Never invent optima in prose or memory.
2. **Multi-agent:** When isolation is required, call the real **`subagent`** tool (`pi-subagents`). **Forbidden:** cosplay child roles in prose without a tool call.
3. **Control plane:** Product full chain is **LangGraph** via `orpath.bat run` / `run-full` / `menu`. Bare chat ≠ full pipeline.
4. **Intake / OCR:** Prefer `orpath.bat intake` / `menu` → intake. OCR backends: text PDF / **ppocr (paddle)** / rapidocr fallback — see `tools/intake_ocr.py`. No objectives in intake.
5. **Evidence:** After a real MA stage, check `outputs/.agents/<slug>/*-lead-*.log` for `"name":"subagent"`.

## Operator shortcuts (host-agnostic)

```bat
orpath.bat menu
orpath.bat run-full --slug X --thread-id X
orpath.bat intake --slug X --in path\to\file
```

Read `ORPATH.md` for GUI-primary workflow. Live multi-agent defaults ON (`ORPATH_LIVE_SUBAGENT=1`); set 0 for cheap runs.
