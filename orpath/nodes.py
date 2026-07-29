from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from orpath.gates import gate_r1, gate_r2, gate_schema, solve
from orpath.state import ORPathState


def _root(state: ORPathState) -> Path:
    return Path(state["root"])


def _ensure_dirs(root: Path) -> None:
    for rel in (
        "outputs/.plans",
        "outputs/.drafts",
        "notes",
        "papers",
        "runs",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)


def node_orchestrate(state: ORPathState) -> dict:
    root = _root(state)
    _ensure_dirs(root)
    slug = state["slug"]
    plan = root / "outputs" / ".plans" / f"{slug}.md"
    plan.write_text(
        f"""# Plan {slug}

- problem_id: {state["problem_id"]}
- solve_mode: {state["solve_mode"]}
- started: {datetime.now(timezone.utc).isoformat()}

## Task ledger
- [ ] research
- [ ] model
- [ ] solve
- [ ] explain
- [ ] draft
- [ ] review
- [ ] provenance

## Verification log
(empty)
""",
        encoding="utf-8",
    )
    return {
        "stage": "research",
        "plan_path": str(plan),
        "last_error": "",
    }


def node_research(state: ORPathState) -> dict:
    """Deterministic research artifact (Pi or-researcher replaces in live OpenPi runs)."""
    root = _root(state)
    slug = state["slug"]
    pid = state["problem_id"]
    problem = (root / "fixtures" / "t1" / pid / "problem.md").read_text(encoding="utf-8")
    path = root / "notes" / f"{slug}-research.md"
    path.write_text(
        f"""# Research: {slug}

## Summary
Fixture shortest-path style OR problem. Modeling should expose graph endpoints; solving is delegated to tools.

## Problem class
shortest_path

## Evidence table
| # | Source | Path/URL | Key claim | Type | Confidence |
|---|--------|----------|-----------|------|------------|
| 1 | Problem statement | fixtures/t1/{pid}/problem.md | S to T weighted digraph | primary | high |
| 2 | Graph fixture | fixtures/t1/{pid}/graph.json | edges with weights | primary | high |
| 3 | Fixture note | notes://t1-shortest-path-ref | demo whitelist ref | secondary | medium |

## Findings
1. Use Dijkstra / shortest_path on directed weighted graph [1][2].
2. Do not treat LLM arithmetic as optima.

## Modeling recommendations
- problem_class: shortest_path
- source/target from problem
- edges_ref to graph.json

## Open questions
- None for fixture T1.

## Problem excerpt
{problem[:500]}
""",
        encoding="utf-8",
    )
    return {"stage": "model", "research_path": str(path), "last_error": ""}


def node_model(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    pid = state["problem_id"]
    gpath = root / "fixtures" / "t1" / pid / "graph.json"
    graph = json.loads(gpath.read_text(encoding="utf-8"))
    schema = {
        "slug": slug,
        "problem_class": "shortest_path",
        "problem_id": pid,
        "nodes": graph.get("nodes", []),
        "edges_ref": f"fixtures/t1/{pid}/graph.json",
        "source": graph["nodes"][0],
        "target": graph["nodes"][-1],
        "weight_key": "w",
        "constraints": [],
        "notes": "T1 deterministic modeler node (live: or-modeler subagent)",
    }
    sp = root / "outputs" / f"{slug}-schema.json"
    sp.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    return {"stage": "gate_schema", "schema_path": str(sp), "last_error": ""}


def node_gate_schema(state: ORPathState) -> dict:
    root = _root(state)
    ok, msg = gate_schema(root, Path(state["schema_path"]))
    if not ok:
        return {
            "stage": "model",
            "gate_schema_ok": False,
            "last_error": msg,
        }
    return {"stage": "solve", "gate_schema_ok": True, "last_error": ""}


def node_solve(state: ORPathState) -> dict:
    root = _root(state)
    ok, data, raw = solve(root, state["problem_id"], state["solve_mode"])
    if not ok:
        # fallback to mock if ortools path fails
        if state["solve_mode"] != "mock":
            ok, data, raw = solve(root, state["problem_id"], "mock")
        if not ok:
            return {"stage": "solve", "last_error": raw, "human_required": True}
    out = root / "outputs" / f"{state['slug']}-solution.json"
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {
        "stage": "explain",
        "solution_path": str(out),
        "last_error": "",
    }


def node_explain(state: ORPathState) -> dict:
    root = _root(state)
    sol = json.loads(Path(state["solution_path"]).read_text(encoding="utf-8"))
    path = root / "notes" / f"{state['slug']}-explain.md"
    path.write_text(
        f"""# Explain: {state['slug']}

Solver `{sol.get('solver')}` reports status `{sol.get('status')}`.

- objective: {sol.get('objective')}
- path: {' → '.join(sol.get('path') or [])}
- source artifact: {sol.get('source')}

All numbers copied from `{state['solution_path']}`.
""",
        encoding="utf-8",
    )
    return {"stage": "draft_paper", "explain_path": str(path)}


def node_draft_paper(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    sol = json.loads(Path(state["solution_path"]).read_text(encoding="utf-8"))
    paper = root / "papers" / f"{slug}.md"
    path_str = " -> ".join(sol.get("path") or [])
    paper.write_text(
        f"""# Shortest Path Fixture Study ({slug})

## Abstract
We formalize a tiny directed shortest-path instance and report the solver output without LLM arithmetic.

## Problem statement
See fixtures/t1/{state['problem_id']}/problem.md.

## Related modeling notes
Research brief: `{state['research_path']}`.
Problem class shortest_path; graph endpoints from fixture.

## Method / formulation
Schema file: `{state['schema_path']}`.
Weighted digraph shortest path; solver tool owns optima.

## Results
From solver artifact `{state['solution_path']}`:
- status: {sol.get('status')}
- objective = {sol.get('objective')}
- path: {path_str}
- solver: {sol.get('solver')}

## Limitations
Fixture-scale graph only. Live multi-agent trajectories are demonstrated separately in OpenPi.

## Sources
- notes://t1-shortest-path-ref
- fixtures/t1/{state['problem_id']}/graph.json
- {state['solution_path']}
- {state['research_path']}
""",
        encoding="utf-8",
    )
    return {"stage": "review_pack", "paper_path": str(paper), "last_error": ""}


def _count_fatal(review_text: str) -> int:
    return len(re.findall(r"\*\*FATAL:\*\*", review_text))


def node_review_pack(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    paper = Path(state["paper_path"])
    sol = Path(state["solution_path"])
    wl = root / "fixtures" / "t1" / state["problem_id"] / "whitelist_refs.json"

    r2_ok, r2_msg = gate_r2(root, paper, sol)
    r1_ok, r1_msg = gate_r1(root, paper, wl)

    # lightweight reviewer artifact
    fatals = []
    if not r2_ok:
        fatals.append(f"R2 numeric gate failed: {r2_msg}")
    if not r1_ok:
        fatals.append(f"R1 cite gate failed: {r1_msg}")
    review = root / "outputs" / f"{slug}-review.md"
    body = f"""## Summary
Automated T1 review pack for `{slug}`.

## Strengths
- [S1] Results section binds to solution artifact path.

## Weaknesses
"""
    if fatals:
        for i, f in enumerate(fatals, 1):
            body += f"- [W{i}] **FATAL:** {f}\n"
    else:
        body += "- None FATAL from gates.\n"
    body += f"""
## Verdict
gates r1={r1_ok} r2={r2_ok}

## Revision Plan
1. Align all numerics with solution.json
2. Use only whitelist citations
"""
    review.write_text(body, encoding="utf-8")
    fatal_n = _count_fatal(body)
    return {
        "stage": "revise_or_done",
        "review_path": str(review),
        "gate_r1_ok": r1_ok,
        "gate_r2_ok": r2_ok,
        "review_fatal": fatal_n,
        "last_error": "; ".join(fatals),
    }


def node_revise_or_done(state: ORPathState) -> dict:
    ok = state.get("gate_r1_ok") and state.get("gate_r2_ok") and state.get("review_fatal", 0) == 0
    if ok:
        return {"stage": "provenance", "last_error": ""}
    rev = int(state.get("revise_count") or 0)
    max_r = int(state.get("max_revise") or 2)
    if rev < max_r:
        return {
            "stage": "draft_paper",
            "revise_count": rev + 1,
            "last_error": state.get("last_error") or "revise",
        }
    root = _root(state)
    hr = root / "outputs" / f"{state['slug']}.HUMAN_REQUIRED.md"
    hr.write_text(
        f"HUMAN_REQUIRED after {max_r} revises.\nLast error: {state.get('last_error')}\n",
        encoding="utf-8",
    )
    return {
        "stage": "provenance",
        "human_required": True,
        "last_error": f"HUMAN_REQUIRED: {state.get('last_error')}",
    }


def node_provenance(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    prov = root / "outputs" / f"{slug}.provenance.md"
    lines = [
        f"# Provenance {slug}",
        f"- utc: {datetime.now(timezone.utc).isoformat()}",
        f"- solve_mode: {state['solve_mode']}",
        f"- revise_count: {state.get('revise_count')}",
        f"- human_required: {state.get('human_required')}",
        f"- gate_schema_ok: {state.get('gate_schema_ok')}",
        f"- gate_r1_ok: {state.get('gate_r1_ok')}",
        f"- gate_r2_ok: {state.get('gate_r2_ok')}",
        "",
        "## Artifacts",
    ]
    for k in (
        "plan_path",
        "research_path",
        "schema_path",
        "solution_path",
        "explain_path",
        "paper_path",
        "review_path",
    ):
        if state.get(k):
            lines.append(f"- {k}: `{state[k]}`")
    lines.append("")
    lines.append("## Notes")
    lines.append(
        "Deterministic LG nodes emulate agent file outputs for CI. "
        "OpenPi live runs should use `.pi/agents/or-*.md` subagents for research/model/write/review."
    )
    prov.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"stage": "end", "provenance_path": str(prov)}
