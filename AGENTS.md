# OR-Path Project Guide (`AGENTS.md`)

Durable project law for OR-Path sessions. Product runtime is **this repo** (`START.bat` / `START.sh` / `orpath.bat` / `./orpath.sh`). Legacy Node.js `pi` CLI wrapper (`@earendil-works/pi-coding-agent` & `pi-subagents`) has been permanently stripped and retired — never reintroduce `pi` subprocess calls.

> **v1.0.0 Stable Architecture**: Consolidated 60+ legacy cloned domain agents into **4 Core Specialist Agents + Deterministic Python Gates + 10 Pluggable `DomainCartridge` Packs**.

## Core Assets (5 Pillars)

1. **Unified Launcher & Web Studio (`START.bat`, `START.sh`, `orpath/web/`, `orpath/studio_analyzer.py`)**
   - Native Python connection to `.env` LLM APIs (iFlytek Spark `spark-x2.6` / DeepSeek `deepseek-reasoner` / `deepseek-chat`) + local ONNX `bge-m3` hybrid RAG (`knowledge_svc/`), zero external `pi` CLI dependency.
   - Supports folder drag-and-drop intake, structural data profiling, interactive confirmation, solver execution, and real-time `Live Watch` dashboard.
2. **Hardcore OR Solver Library (`tools/` & `scripts/` — 27 Industrial Solvers)**
   - **Graph, Routing & Facility**: `tools/solve_ortools.py`, `tools/solve_pyvrp.py`, `tools/solve_highs.py`, `tools/solve_networkx.py`, `tools/solve_facility.py`, `tools/solve_hub_location.py` (Shortest Path, TSP, CVRP, VRPTW, CFLP, Hub Location).
   - **Industrial & Project Scheduling**: `tools/solve_jssp.py` (PyJobShop CP-SAT; Taillard JSSP 67 + FJSSP 407 benchmarks, setup times / 换模时延, Gantt PNG export), `tools/solve_rcpsp.py` (PSPLib CPM + Cumulative CP-SAT), `tools/solve_staff_rostering.py`.
   - **3D Tube Cutting, Bin Packing & Polyomino**: `scripts/b_tube_solve.py`, `scripts/b_tube_geometry.py`, `tools/solve_tube_cut_b2026.py`, `tools/tube_optimization.py`, `tools/solve_polyomino.py`, `tools/solve_polyomino_q3.py`, `tools/solve_binpack.py`.
   - **Campus PV-BESS-EV Microgrid**: `tools/solve_microgrid.py`, `tools/microgrid_reporting.py` (TOU arbitrage, peak demand shaving, battery degradation, rolling-horizon MPC).
   - **Inventory, Portfolio & Stochastic Pricing**: `tools/solve_lotsizing.py` (Wagner-Whitin DP + CLSP), `tools/solve_portfolio.py` (Markowitz convex QP / Risk Parity), `tools/solve_stochastic_lp.py` (2-stage stochastic LP).
3. **Independent Physical & Mathematical Validator (`tools/validate_solution.py`, `tools/validators/`, `orpath/agents/dimo_mutator.py`)**
   - Enforces the **Numbers Truth** iron law: all objective values, schedules, routes, and cutting plans are independently recomputed and verified from raw problem data, backed by 5-class DIMO invariant mutation checks.
4. **Lean 4-Agent + Deterministic Gate + 10 `DomainCartridge` Architecture (`orpath/agents/`, `knowledge/skills/`)**
   - **4 Permanent LLM Specialists** (each running in an isolated fresh context with zero message truncation):
     1. `or_analyst` — Reads deterministic preflight data profile + RAG skills, identifies constraints & mathematical class, selects `DomainCartridge` and complexity tier (`A` / `B` / `C`).
     2. `or_modeler` — Formulates `schema.json`, invokes registered solvers or writes controlled Python MIP/CP-SAT sandbox scripts (`knowledge/skills/or-problems.md`), tracks lower bounds & optimality gaps. Dynamically splits per subproblem only on Tier-C multi-question contests.
     3. `or_writer` — Writes rigorous 6-chapter academic papers (`docs/or-paper-sop.md`) around Python-prerendered verified truth tables and figures.
     4. `or_reviewer` — Adversarial peer-review red team (`FATAL` / `MAJOR` / `MINOR` defect grading) paired with deterministic R1/R2/Optimality-Claim checks.
   - **0-Token Deterministic Python Gates**: Preflight file/schema probe, `validate_solution.py` hard gate, verified Markdown table/chart renderer, and `r1_cite_check` / `r2_numeric_check` / `optimality_claim_auditor` gates. Never use an LLM "Supervisor/Lead" to poll routing or an LLM "Verifier" to eyeball numbers.
   - **10 Pluggable `DomainCartridge` Packs (`orpath/agents/domain_analytics.py`)**: Domain expertise is injected by mounting genuine domain-specific tools (`profile_<domain>_data` & `inspect_<domain>_solution`), solver allowlists, and domain checklists onto `or_analyst` / `or_modeler` — **never** by copy-pasting 900-line 6-agent Python files per domain.
5. **Core Gates & High-Signal Verification (`tools/test_*.py` & `scripts/*_gate.py`)**
   - Solver/validator mathematical truth tests, DIMO 5-class tamper rejection (`scripts/universal_redteam_gate.py`), Web Studio & Watch gates, and live LLM flagship end-to-end runs.

## Ground Rules (Non-Negotiable)

1. **Numbers Truth:** Objective values and physical metrics come strictly from `tools/solve_*` + `tools/validate_solution.py`. Never invent or vote on optima in LLM prose; never claim "global optimal" when `proven_optimal == False`.
2. **No Reskinned Parrots & No 900-Line Domain Clones:** Domain capability comes from binding real `orpath/agents/domain_analytics.py` tools (`profile_<domain>_data`, `inspect_<domain>_solution`) and domain skills via `DomainCartridge` — never duplicate whole agent graphs per domain, and never assign fake heuristic search agents to exact LP / convex QP problems (Tier-A).
3. **Zero Truncation & Isolated File Handoffs (Feynman Discipline):** Never slice prompts or messages with 1600-char truncation hooks, and never share a growing `MessagesState` chat history across agents. Pass compact file pointers under `notes/`, `outputs/`, `papers/`, `runs/`.
4. **Single Control Plane & Offline Gate Safety:** Route both CLI and Web Studio through `orpath/graph_product.py`. Explicit `live_subagent=False` in state must always bypass external LLM calls so offline CI gates never hang; flagship live benchmarks must use real `.env` LLM APIs (never fake live delivery with `MockChatModel` call-count assertions).
5. **Environment & Git Hygiene:** Always invoke Python and Pytest via `.venv/bin/python` and `.venv/bin/pytest`. Do not run destructive git commands (`git reset --hard`, `git checkout -- .`, `git clean -fd`) on working tree changes. `HOME != WORKDIR`.

## Key Specs & Docs

1. **`docs/ARCHITECTURE.md`** — Current native Python system architecture & lean 4-agent specification
2. **`docs/or-paper-sop.md`** — Mandatory 6-chapter academic OR paper SOP
3. **`knowledge/skills/or-problems.md`** — Classic OR mathematical formulations & Python modeling reference
4. **`specs/product-flow-sdd.md` & `specs/process-visibility.md`** — End-to-end product flow & Live Watch contracts
5. **`docs/repo-surface.md`** — Repository public boundaries & clean release rules

## Artifact Layout

| Path | Use |
|------|-----|
| `START.bat` / `START.sh` | Unified Web Studio & Live Watch launcher |
| `orpath/` | LangGraph control plane (`graph_product.py`), lean agents & cartridges (`orpath/agents/`), Web Studio (`orpath/web/`) |
| `tools/` | 27 OR solvers (`solve_*.py`) + independent validators (`validate_solution.py`, `validators/`) + unit tests |
| `scripts/` | CLI entrypoints (`orpath_watch.py`, `b_tube_solve.py`, `orpath_doctor.py`), red-team gates & live flagship runners |
| `knowledge/` `knowledge_svc/` | 19 OR modeling skills (`knowledge/skills/`) + Hybrid BM25 / local ONNX `bge-m3` RAG |
| `contracts/` `fixtures/` `demo/seed/` | JSON contracts, golden benchmark datasets & Watch replay seeds |
| `outputs/` `runs/` `papers/` `notes/` | Workdir runtime artifacts (Feynman file handoffs) |

## Verification Commands

| Check | Command |
|------|---------|
| Unit Tests | `.venv/bin/pytest tools/ -q -p no:langsmith` |
| DIMO Red-Team Gate | `.venv/bin/python scripts/universal_redteam_gate.py` |
| Swarms / Cartridge Gate | `.venv/bin/python scripts/or_swarms_master_gate.py` |
| Workbench Gate | `.venv/bin/python scripts/problem_workbench_gate.py` |
| Watch Gate | `.venv/bin/python scripts/v0_watch_gate.py` |
| T1 / T2 / M1 / M2 | `.venv/bin/python scripts/t1_gate.py` · `t2_gate.py` · `m1_gate.py` · `m2_gate.py` |
