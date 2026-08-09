"""M3 research fan-out + modeler live subagent (implementation).

Product code should import from orpath.subagent_dispatch (ADR-0005).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from orpath.paper_live_subagent import live_subagent_enabled
from orpath.subagent_harness import ANTI_COSPLAY_SYSTEM, LEAD_TOOLS_NO_WRITE, run_forced_subagent_stage
from orpath.subagent_runtime import (
    build_lead_prompt,
    lead_result_to_json,
    require_env,
    spawn_lead,
    write_lead_manifest,
    write_task_brief,
)


def _retry_limit() -> int:
    try:
        return max(1, int(os.environ.get("ORPATH_SUBAGENT_RETRIES", "2")))
    except ValueError:
        return 2


def _research_steer_section(state: dict[str, Any]) -> str:
    """Optional human-steer block for researcher task briefs (D2)."""
    try:
        from orpath.human_steer import format_pi_steer_block

        block = format_pi_steer_block(state)
    except Exception:  # noqa: BLE001
        return ""
    if not block:
        return ""
    return f"## Human steer\n{block}\n"


def _timeout_s() -> int:
    try:
        return max(60, int(os.environ.get("ORPATH_SUBAGENT_TIMEOUT", "1200")))
    except ValueError:
        return 1200


def research_scale(state: dict[str, Any]) -> str:
    """Return 'off' | 'narrow' | 'wide'.

    off: knowledge_mode off → no researcher subagents
    narrow: seed single researcher
    wide: hybrid or explicit wide → 2 parallel researchers
    """
    mode = str(state.get("knowledge_mode") or "off")
    if mode == "off":
        return "off"
    if state.get("research_scale") in {"off", "narrow", "wide"}:
        return str(state["research_scale"])
    if mode == "hybrid":
        return "wide"
    # seed default narrow (1 researcher) unless problem class vrp/tsp complex
    pc = str(state.get("problem_class") or "")
    if pc in {"vrp", "cvrptw"}:
        return "wide"
    return "narrow"


def run_research_subagent_lead(
    root: Path,
    state: dict[str, Any],
    *,
    research_path: Path,
    retrieval_path: Path | None,
    fixture_dir: Path | None,
) -> dict[str, Any]:
    """Spawn research lead with 1–N or-researcher children; merge into research_path."""
    slug = str(state["slug"])
    if not live_subagent_enabled(state):
        return {"skipped": True, "gate_subagent_ok": None, "detail": "live off"}

    scale = research_scale(state)
    if scale == "off":
        return {"skipped": True, "gate_subagent_ok": None, "detail": "knowledge off / scale off"}

    require_env(root)
    pc = state.get("problem_class") or "unknown"
    pid = state.get("problem_id") or ""
    ret = str(retrieval_path or "n/a")
    brief_path = str(state.get("brief_path") or "")
    intake_path = str(state.get("intake_path") or "")
    intake_on = bool(
        (not state.get("skip_intake"))
        and (brief_path or intake_path or (state.get("intake_sources") or []))
    )

    # per-researcher briefs (Feynman: long text on disk)
    tasks_meta = []
    if intake_on:
        # 1.2 residual R2: true problem surface outranks borrowed SP/TSP shell fixture.
        specs = [
            (
                "T1",
                f"notes/{slug}-research-main.md",
                "PRIMARY sources are intake brief + intake.json (contest surface). "
                "Summarize ALL numbered subproblems, data assets, ambiguities. "
                f"problem_id=`{pid}` fixture is SHELL ONLY — do NOT treat fixture gold "
                "(e.g. objective 42/45/58, SP edges) as the contest answer. "
                "Evidence table required. No optima / no invented forecasts.",
            )
        ]
    elif scale == "narrow":
        specs = [
            (
                "T1",
                f"notes/{slug}-research-main.md",
                "Cover problem class, solver claim ladder, fixture constraints. "
                "Evidence table required. No optima.",
            )
        ]
    else:
        specs = [
            (
                "T1",
                f"notes/{slug}-research-fixture.md",
                "Focus on fixture problem.md + local specs/solvers-and-validate + domain constraints.",
            ),
            (
                "T2",
                f"notes/{slug}-research-solvers.md",
                "Focus on docs/solver-stack.md exact vs routing honesty, preferred_solve_mode.",
            ),
        ]

    plan_dir = root / "outputs" / ".plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    task_lines = []
    for tid, out_rel, focus in specs:
        tpath = plan_dir / f"{slug}-research-{tid}.md"
        intake_block = ""
        if intake_on:
            intake_block = (
                f"- intake_brief: `{brief_path or 'n/a'}`\n"
                f"- intake_json: `{intake_path or 'n/a'}`\n"
                f"- shell_fixture_only: `{fixture_dir}` (NOT the contest answer source)\n"
            )
        else:
            intake_block = f"- fixture: `{fixture_dir}`\n"
        tpath.write_text(
            f"# Researcher {tid} for `{slug}`\n\n"
            f"- problem_id: `{pid}`\n"
            f"- problem_class: `{pc}`\n"
            f"{intake_block}"
            f"- retrieval: `{ret}`\n"
            f"- output: `{out_rel}`\n\n"
            f"## Focus\n{focus}\n\n"
            f"{_research_steer_section(state)}"
            "## Integrity\n"
            "- No optimal objective/path/tour/routes.\n"
            "- Evidence table with paths.\n"
            "- Coverage Status section.\n"
            "- Return one line + path only.\n",
            encoding="utf-8",
        )
        tasks_meta.append({"id": tid, "brief": str(tpath), "output": str(root / out_rel)})
        task_lines.append(
            f'    {{ "agent": "or-researcher", "task": "Read {tpath.as_posix()} and write {out_rel}.", '
            f'"output": "{out_rel}" }}'
        )

    tasks_json = ",\n".join(task_lines)
    intake_inputs = (
        f"- intake_brief: `{brief_path or 'n/a'}`\n"
        f"- intake_json: `{intake_path or 'n/a'}`\n"
        f"- shell_fixture_only: `{fixture_dir}`\n"
        if intake_on
        else f"- fixture: `{fixture_dir}`\n"
    )
    lead_brief = f"""# Research lead `{slug}` scale={scale}

## REQUIRED
Call the Pi tool **subagent** once with parallel tasks (failFast: false).

```json
{{
  "tasks": [
{tasks_json}
  ],
  "concurrency": 4,
  "failFast": false
}}
```

## After children return
1. Verify each output file exists.
2. Merge all researcher outputs into `{research_path.as_posix()}` with:
   - one Evidence table (renumber)
   - Coverage Status
   - Solver recommendation
   - no optima
3. Do not invent sources.
{"4. Prefer intake brief/json over shell fixture narrative." if intake_on else ""}

## Inputs
- retrieval: `{ret}`
{intake_inputs}"""
    brief = write_task_brief(
        root,
        slug,
        "research",
        body=lead_brief,
        outputs={"research": str(research_path), **{t["id"]: t["output"] for t in tasks_meta}},
    )
    extra = f"scale={scale}. Use PARALLEL tasks JSON as in the brief. Merge into final research path."
    if intake_on:
        extra += (
            " INTAKE PRIMARY: read brief_path/intake_path first; "
            "fixture is shell_only — forbid treating SP/TSP gold as contest solution."
        )
    prompt = build_lead_prompt(
        stage="research",
        slug=slug,
        brief_path=brief,
        required_agent="or-researcher",
        output_path=str(research_path),
        extra_rules=extra,
    )

    expected = [Path(t["output"]) for t in tasks_meta]
    # final research may be written by lead merge — expect research_path OR children
    results = []
    last = None
    for _ in range(_retry_limit()):
        last = spawn_lead(
            root,
            slug=slug,
            stage="research",
            prompt=prompt,
            timeout_s=_timeout_s(),
            require_subagent_call=True,
            expected_outputs=[],  # checked below more flexibly
            dry_run=False,
            tools=LEAD_TOOLS_NO_WRITE,
            append_system_prompt=ANTI_COSPLAY_SYSTEM + "\nResearch lead: spawn researchers only; Python merges outputs.",
            json_mode=True,
        )
        results.append(last)
        if last.subagent_calls_detected:
            break
    write_lead_manifest(root, slug, results)

    # merge children if final missing
    chunks = []
    for t in tasks_meta:
        p = Path(t["output"])
        if p.is_file() and p.stat().st_size > 20:
            chunks.append(f"<!-- from {t['id']} -->\n" + p.read_text(encoding="utf-8"))
    if chunks and (not research_path.is_file() or research_path.stat().st_size < 50):
        research_path.parent.mkdir(parents=True, exist_ok=True)
        research_path.write_text(
            f"# Research: {slug} (merged M3 fan-out)\n\n" + "\n\n---\n\n".join(chunks) + "\n",
            encoding="utf-8",
        )

    kids_ok = all(Path(t["output"]).is_file() and Path(t["output"]).stat().st_size > 20 for t in tasks_meta) or (
        research_path.is_file() and research_path.stat().st_size > 50
    )
    # Salvage: lead wall-clock timeout (-9) after real subagent work + usable research
    # is common on wide fan-out (4 researchers + merge). Prefer artifacts over exit code.
    research_ok_size = research_path.is_file() and research_path.stat().st_size > 200
    timeout_salvage = bool(
        last
        and int(last.exit_code or 0) == -9
        and last.subagent_calls_detected
        and kids_ok
        and research_ok_size
    )
    if timeout_salvage and chunks and research_path.is_file():
        # If lead timed out mid-merge, refresh from children when research looks thin
        # or lacks Evidence table (keep good lead merges).
        body = research_path.read_text(encoding="utf-8", errors="ignore")
        if "Evidence" not in body or len(body) < 400:
            research_path.write_text(
                f"# Research: {slug} (merged after lead timeout)\n\n"
                + "\n\n---\n\n".join(chunks)
                + "\n",
                encoding="utf-8",
            )
    ok = bool(
        last
        and last.subagent_calls_detected
        and kids_ok
        and (last.exit_code == 0 or timeout_salvage)
    )
    detail = {
        "skipped": False,
        "gate_subagent_ok": ok,
        "scale": scale,
        "tasks": tasks_meta,
        "log_path": last.log_path if last else "",
        "subagent_calls_detected": bool(last and last.subagent_calls_detected),
        "attempts": len(results),
        "timeout_salvage": timeout_salvage,
        "error": ""
        if ok
        else (last.error if last else "research subagent failed"),
        "lead": lead_result_to_json(last) if last else {},
    }
    rep = root / "outputs" / ".agents" / slug / "research-subagent.json"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(detail, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return detail


def run_model_subagent_lead(
    root: Path,
    state: dict[str, Any],
    *,
    schema_path: Path,
    research_path: Path | None,
    fixture_dir: Path | None,
) -> dict[str, Any]:
    """Harness: lead without write → subagent or-modeler → schema_path."""
    slug = str(state["slug"])
    if not live_subagent_enabled(state):
        return {"skipped": True, "gate_subagent_ok": None, "detail": "live off"}

    require_env(root)
    pc = state.get("problem_class") or "shortest_path"
    pid = state.get("problem_id") or ""
    brief_path = str(state.get("brief_path") or "")
    intake_path = str(state.get("intake_path") or "")
    intake_on = bool(
        (not state.get("skip_intake"))
        and (brief_path or intake_path or (state.get("intake_sources") or []))
    )
    if intake_on:
        surface = (
            f"- intake_brief: `{brief_path or 'n/a'}`\n"
            f"- intake_json: `{intake_path or 'n/a'}`\n"
            f"- shell_fixture_only: `{fixture_dir}` (topology shell; NOT contest gold)\n"
        )
        mode_note = (
            "Schema may note shell problem_id for pipeline binding, but describe "
            "TRUE contest subproblems from intake. Do not copy fixture optima shapes "
            "as if they solve the intake contest."
        )
    else:
        surface = f"- fixture: `{fixture_dir}`\n"
        mode_note = "Include preferred_solve_mode consistent with claim ladder."
    from orpath.human_steer import format_pi_steer_block

    steer_md = format_pi_steer_block(state)
    steer_section = f"\n## Human steer\n{steer_md}\n" if steer_md else ""
    sm = str(state.get("solve_mode") or "").strip()
    if sm:
        mode_note += f" preferred_solve_mode should align with human/control solve_mode=`{sm}` when set."
    brief_body = f"""# Model brief `{slug}`

## Role
Lead has NO write/edit. Call `subagent` → `or-modeler`.

## Child must write
`{schema_path.as_posix()}`

## Inputs
- problem_id: `{pid}`
- problem_class: `{pc}`
{surface}- research: `{research_path or "n/a"}`
{steer_section}
## Hard forbid
No objective/path/tour/routes solved values in schema.
{mode_note}
"""
    extra = "Schema JSON only. No optima keys."
    if intake_on:
        extra += " Intake primary; shell fixture secondary."
    if steer_md:
        extra += " Honor human steer methods/notes; still no optima."
    detail = run_forced_subagent_stage(
        root,
        slug=slug,
        stage="model",
        required_agent="or-modeler",
        brief_body=brief_body,
        output_path=schema_path,
        extra_rules=extra,
    )
    # schema shape check
    ok = bool(detail.get("gate_subagent_ok"))
    err = detail.get("error") or ""
    if ok and schema_path.is_file():
        try:
            data = json.loads(schema_path.read_text(encoding="utf-8"))
            bad = {"objective", "tour", "routes", "path", "optimal"}
            if any(k in data and data[k] not in (None, "", [], {}) for k in bad):
                ok = False
                err = "schema contains solution-shaped keys"
                detail["gate_subagent_ok"] = False
                detail["error"] = err
        except json.JSONDecodeError as exc:
            ok = False
            err = f"invalid schema json: {exc}"
            detail["gate_subagent_ok"] = False
            detail["error"] = err

    rep = root / "outputs" / ".agents" / slug / "model-subagent.json"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(detail, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return detail
