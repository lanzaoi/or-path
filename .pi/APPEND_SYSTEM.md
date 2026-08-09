# OR-Path project law (appended to Pi / any host session)

This workspace is **OR-Path Multi-Agent / Graph-OR Agent**. Hermes is not the product runtime.

## Hard laws

1. **Numbers truth:** `objective` / path / tour / routes come **only** from solve tools + validate. Never invent optima in prose or memory.
2. **Multi-agent:** When isolation is required, call the real **`subagent`** tool (`pi-subagents`). **Forbidden:** cosplay child roles in prose without a tool call.
3. **Control plane:** Product full chain is **LangGraph** via `orpath.bat run` / `run-full` / `menu`. Bare chat ≠ full pipeline.
4. **Intake / OCR:** Prefer `orpath.bat intake` / `menu` → intake. OCR backends: text PDF / **ppocr (paddle)** / rapidocr fallback — see `tools/intake_ocr.py`. No objectives in intake.
5. **Evidence:** After a real MA stage, check `outputs/.agents/<slug>/*-lead-*.log` for `"name":"subagent"`.

## Skills (project `.pi/skills/` — mostly **pulled**)

**Pulled (prefer these):**
- `or-modeling` — ClawHub 运筹建模全流程 + `scripts/paper_search.py`
- `operations-research-algorithm-developer` — skills.sh OR/LP/MIP/VRP/solver 集成
- `research-ops-skills` — research ops
- `agentmemory-architecture` — 记忆架构模式（≠ Cognee 主轴）
- `cuopt-routing-api-python` / `cuopt-numerical-optimization-*` / `cuopt-install` — **NVIDIA 官方** VRP/LP skills（GitHub NVIDIA/skills）

**Product glue (thin):**
- `or-numbers-truth` · `or-solver-select` · `or-process-memory`

Provenance: `third_party/PULLED.md`  
**Pulled skills count:** 19 under `.pi/skills/` (see directory listing).

## Process memory (≠ Skill)

- Auto on retrieve: `notes/<slug>-lessons.md`
- Search/record: `orpath.bat memory-search` / `memory-record`
- Never treat lessons as objective authority

## Tools / solvers / MCP

- Solvers (in-repo): NetworkX · CP-SAT · HiGHS · OR-Tools Routing · polyomino · tube · mock + validate
- Modeling API: **PuLP** (pip); optional **PyVRP** (SOTA VRP engine, not default claim)
- Catalog: `python -m orpath.tool_catalog`
- Product MCP: `orpath.bat mcp` → `python -m orpath.mcp_server`
- Pulled HiGHS MCP: `orpath.bat mcp-highs` → npm `highs-mcp@0.3.2`
- Pulled OR-Tools MCP: `orpath.bat mcp-ortools` → vendored `Jacck/mcp-ortools`

## Operator shortcuts (host-agnostic)

```bat
orpath.bat menu
orpath.bat run-full --slug X --thread-id X
orpath.bat intake --slug X --in path\to\file
orpath.bat memory-search --query "VRP" --class vrp
orpath.bat mcp
orpath.bat mcp-highs
orpath.bat mcp-ortools
```

Read `ORPATH.md` for GUI-primary workflow. Live multi-agent defaults ON (`ORPATH_LIVE_SUBAGENT=1`); set 0 for cheap runs.

## Pi guidance packages (project-local)

Installed under `.pi/settings.json` → `.pi/npm/` (optional Tier-2, not product face):
- `pi-kanban` — `/kanban start` (needs sessions; product LIVE: `ORPATH_PI_SESSION=1`)
- `pi-supervisor` — `/supervise <outcome>`; rules in `.pi/SUPERVISOR.md`
- `@juicesharp/rpiv-ask-user-question` — structured questions to the human
- Built-in: Enter=steer, Alt+Enter=follow-up while agent runs

Product face remains Watch. Control-plane routing stays LangGraph. Numbers only from solve+validate.
Law: `specs/human-steer-and-pi-guidance.md`.
