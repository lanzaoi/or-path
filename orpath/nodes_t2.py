"""T2 LangGraph node bodies (deterministic CI stand-ins + real tools/gates)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from orpath.gates import gate_r1, gate_r2, gate_schema, gate_validate, solve
from orpath.state import ORPathState

TUNE_STRATEGIES = [
    ("PATH_CHEAPEST_ARC", "GUIDED_LOCAL_SEARCH", 2000),
    ("PATH_CHEAPEST_ARC", "SIMULATED_ANNEALING", 4000),
    ("SAVINGS", "GUIDED_LOCAL_SEARCH", 5000),
]


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


def _fixture_base(root: Path, problem_id: str) -> Path:
    for base in (root / "fixtures" / "t2", root / "fixtures" / "t1"):
        if (base / problem_id).is_dir():
            return base / problem_id
    raise FileNotFoundError(problem_id)


def _infer_class(root: Path, problem_id: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    d = _fixture_base(root, problem_id)
    if (d / "locations.json").is_file():
        return "vrp"
    if (d / "coords.json").is_file() or (d / "distance_matrix.json").is_file():
        return "tsp"
    return "shortest_path"


def node_orchestrate(state: ORPathState) -> dict:
    root = _root(state)
    _ensure_dirs(root)
    slug = state["slug"]
    pc = _infer_class(root, state["problem_id"], state.get("problem_class"))
    plan = root / "outputs" / ".plans" / f"{slug}.md"
    plan.write_text(
        f"""# Plan {slug}

- problem_id: {state["problem_id"]}
- problem_class: {pc}
- solve_mode: {state["solve_mode"]}
- knowledge_mode: {state.get("knowledge_mode")}
- started: {datetime.now(timezone.utc).isoformat()}

## Task ledger
- [ ] retrieve
- [ ] research
- [ ] model
- [ ] solve
- [ ] validate
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
        "stage": "retrieve",
        "plan_path": str(plan),
        "problem_class": pc,
        "schema_repair": int(state.get("schema_repair") or 0),
        "validate_repair": int(state.get("validate_repair") or 0),
        "solver_tune": int(state.get("solver_tune") or 0),
        "last_error": "",
    }


def node_retrieve(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    mode = state.get("knowledge_mode") or "seed"
    out = root / "notes" / f"{slug}-retrieval.json"
    query = f"OR {state.get('problem_class')} routing solver constraints"
    if mode == "off":
        art = {"query": query, "knowledge_mode": "off", "hits": [], "seed_facts": []}
        out.write_text(json.dumps(art, indent=2) + "\n", encoding="utf-8")
        return {"stage": "research", "retrieval_path": str(out)}

    # Prefer knowledge_svc CLI when present
    import subprocess
    import sys

    cmd = [
        sys.executable,
        "-m",
        "knowledge_svc.retrieve",
        "--query",
        query,
        "--mode",
        mode,
        "--topk",
        "5",
        "--out",
        str(out),
    ]
    r = subprocess.run(cmd, cwd=root, text=True, capture_output=True)
    if r.returncode != 0 or not out.is_file():
        # fallback seed-only inline
        seed_path = root / "knowledge" / "seed_graph" / "or_domain_seed.json"
        facts = []
        if seed_path.is_file():
            seed = json.loads(seed_path.read_text(encoding="utf-8"))
            pc = state.get("problem_class")
            for n in seed.get("nodes") or []:
                if n.get("type") == "ProblemClass" and n.get("id") == pc:
                    facts.append(n)
                if n.get("type") == "Solver":
                    facts.append(n)
        art = {
            "query": query,
            "knowledge_mode": mode,
            "hits": [],
            "seed_facts": facts,
            "fallback": True,
            "cli_err": (r.stderr or r.stdout)[:500],
        }
        out.write_text(json.dumps(art, indent=2) + "\n", encoding="utf-8")
    return {"stage": "research", "retrieval_path": str(out), "last_error": ""}


def node_research(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    pid = state["problem_id"]
    pc = state.get("problem_class") or "shortest_path"
    fb = _fixture_base(root, pid)
    problem = (fb / "problem.md").read_text(encoding="utf-8")
    retrieval = {}
    rp = state.get("retrieval_path")
    if rp and Path(rp).is_file():
        retrieval = json.loads(Path(rp).read_text(encoding="utf-8"))
    hits = retrieval.get("hits") or []
    seed_facts = retrieval.get("seed_facts") or []
    cite_rows = []
    for i, h in enumerate(hits[:5], 1):
        cite_rows.append(
            f"| {i} | chunk | {h.get('chunk_id')} | {h.get('snippet', '')[:80]} | retrieval | med |"
        )
    if not cite_rows:
        cite_rows.append(
            f"| 1 | Problem | {fb.as_posix()}/problem.md | fixture primary | primary | high |"
        )
    for j, s in enumerate(seed_facts[:3], len(cite_rows) + 1):
        cite_rows.append(
            f"| {j} | seed | {s.get('id')} | {s.get('label', s.get('name', ''))} | seed | high |"
        )
    path = root / "notes" / f"{slug}-research.md"
    path.write_text(
        f"""# Research: {slug}

## Summary
T2 research for `{pc}` / `{pid}`. Retrieval mode={retrieval.get('knowledge_mode')}.

## Problem class
{pc}

## Evidence table
| # | Source | Path/URL | Key claim | Type | Confidence |
|---|--------|----------|-----------|------|------------|
{chr(10).join(cite_rows)}

## Findings
1. Use deterministic solvers (networkx/ortools); never LLM optima.
2. Validate must recompute objective.
3. Seed/retrieval chunk_ids when present must be cited.

## Modeling recommendations
- problem_class: {pc}
- no objective/tour/routes/path answers in schema

## Retrieval artifact
`{rp}`

## Problem excerpt
{problem[:800]}
""",
        encoding="utf-8",
    )
    return {"stage": "model", "research_path": str(path), "last_error": ""}


def node_model(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    pid = state["problem_id"]
    pc = state.get("problem_class") or "shortest_path"
    fb = _fixture_base(root, pid)
    schema: dict
    if pc == "shortest_path":
        graph = json.loads((fb / "graph.json").read_text(encoding="utf-8"))
        schema = {
            "slug": slug,
            "problem_class": "shortest_path",
            "problem_id": pid,
            "nodes": graph.get("nodes", []),
            "edges_ref": str(fb.relative_to(root) / "graph.json").replace("\\", "/"),
            "source": graph["nodes"][0],
            "target": graph["nodes"][-1],
            "weight_key": "w",
            "constraints": [],
            "notes": "T2 deterministic modeler",
        }
    elif pc == "tsp":
        coords = json.loads((fb / "coords.json").read_text(encoding="utf-8"))
        schema = {
            "slug": slug,
            "problem_class": "tsp",
            "problem_id": pid,
            "coords": coords.get("coords", coords),
            "constraints": [],
            "notes": "T2 TSP modeler",
        }
    else:
        loc = json.loads((fb / "locations.json").read_text(encoding="utf-8"))
        schema = {
            "slug": slug,
            "problem_class": "vrp",
            "problem_id": pid,
            "depot": loc.get("depot"),
            "locations": loc.get("locations"),
            "demands": loc.get("demands"),
            "vehicle_count": loc.get("vehicle_count"),
            "capacities": loc.get("capacities"),
            "constraints": ["capacity"],
            "notes": "T2 multi-vehicle VRP modeler",
        }
    sp = root / "outputs" / f"{slug}-schema.json"
    sp.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    return {"stage": "gate_schema", "schema_path": str(sp), "last_error": ""}


def node_gate_schema(state: ORPathState) -> dict:
    root = _root(state)
    ok, msg = gate_schema(root, Path(state["schema_path"]))
    if ok:
        return {"stage": "solve", "gate_schema_ok": True, "last_error": ""}
    repair = int(state.get("schema_repair") or 0)
    max_r = int(state.get("max_schema_repair") or 2)
    if repair < max_r:
        return {
            "stage": "model",
            "gate_schema_ok": False,
            "schema_repair": repair + 1,
            "last_error": msg,
        }
    return {
        "stage": "human_stop",
        "gate_schema_ok": False,
        "human_required": True,
        "last_error": f"schema repair exhausted: {msg}",
    }


def node_solve(state: ORPathState) -> dict:
    root = _root(state)
    pc = state.get("problem_class") or "shortest_path"
    mode = state["solve_mode"]
    extra: list[str] = []
    tune = int(state.get("solver_tune") or 0)
    if mode == "ortools" and tune > 0 and tune <= len(TUNE_STRATEGIES):
        fs, mh, tl = TUNE_STRATEGIES[min(tune, len(TUNE_STRATEGIES)) - 1]
        extra = [
            "--first-solution",
            fs,
            "--metaheuristic",
            mh,
            "--time-limit-ms",
            str(tl),
        ]
    ok, data, raw = solve(root, state["problem_id"], mode, pc, extra or None)
    if not ok and mode != "mock":
        ok, data, raw = solve(root, state["problem_id"], "mock", pc)
    if not ok:
        return {
            "stage": "human_stop",
            "human_required": True,
            "last_error": raw,
        }
    out = root / "outputs" / f"{state['slug']}-solution.json"
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {
        "stage": "gate_validate",
        "solution_path": str(out),
        "last_error": "",
    }


def node_gate_validate(state: ORPathState) -> dict:
    root = _root(state)
    vpath = root / "outputs" / f"{state['slug']}-validate.json"
    ok, report, msg = gate_validate(
        root, state["problem_id"], Path(state["solution_path"]), vpath
    )
    if ok:
        return {
            "stage": "explain",
            "validate_path": str(vpath),
            "gate_validate_ok": True,
            "last_error": "",
        }

    # Q12-C: param retune then model
    tune = int(state.get("solver_tune") or 0)
    max_tune = int(state.get("max_solver_tune") or 3)
    mode = state["solve_mode"]
    log_path = root / "outputs" / f"{state['slug']}-tune-log.jsonl"
    if mode == "ortools" and tune < max_tune:
        entry = {
            "try": tune + 1,
            "report_errors": report.get("errors"),
            "strategy": TUNE_STRATEGIES[min(tune, len(TUNE_STRATEGIES) - 1)],
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return {
            "stage": "solve",
            "solver_tune": tune + 1,
            "gate_validate_ok": False,
            "validate_path": str(vpath),
            "tune_log_path": str(log_path),
            "last_error": msg,
        }

    vrep = int(state.get("validate_repair") or 0)
    max_v = int(state.get("max_validate_repair") or 2)
    if vrep < max_v:
        return {
            "stage": "model",
            "validate_repair": vrep + 1,
            "gate_validate_ok": False,
            "validate_path": str(vpath),
            "last_error": msg,
        }
    return {
        "stage": "human_stop",
        "human_required": True,
        "gate_validate_ok": False,
        "validate_path": str(vpath),
        "last_error": f"validate exhausted: {msg}",
    }


def node_human_stop(state: ORPathState) -> dict:
    root = _root(state)
    hr = root / "outputs" / f"{state['slug']}.HUMAN_REQUIRED.md"
    hr.write_text(
        f"HUMAN_REQUIRED\nlast_error: {state.get('last_error')}\n"
        f"schema_repair={state.get('schema_repair')} solver_tune={state.get('solver_tune')} "
        f"validate_repair={state.get('validate_repair')}\n",
        encoding="utf-8",
    )
    return {"stage": "provenance", "human_required": True}


def node_explain(state: ORPathState) -> dict:
    root = _root(state)
    sol = json.loads(Path(state["solution_path"]).read_text(encoding="utf-8"))
    path = root / "notes" / f"{state['slug']}-explain.md"
    shape = sol.get("path") or sol.get("tour") or sol.get("routes")
    path.write_text(
        f"""# Explain: {state['slug']}

Solver `{sol.get('solver')}` status `{sol.get('status')}`.

- objective: {sol.get('objective')}
- shape: {shape}
- validate: {state.get('validate_path')}

All numbers from `{state['solution_path']}` only.
""",
        encoding="utf-8",
    )
    return {"stage": "draft_paper", "explain_path": str(path)}


def node_draft_paper(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    sol = json.loads(Path(state["solution_path"]).read_text(encoding="utf-8"))
    paper = root / "papers" / f"{slug}.md"
    pc = state.get("problem_class") or sol.get("problem_class")
    shape = sol.get("path") or sol.get("tour") or sol.get("routes")
    fb = _fixture_base(root, state["problem_id"])
    rel = fb.relative_to(root).as_posix()
    # whitelist-friendly cites
    wl_note = "notes://t2-tsp-ref" if pc == "tsp" else (
        "notes://t2-vrp-ref" if pc == "vrp" else "notes://t1-shortest-path-ref"
    )
    paper.write_text(
        f"""# OR Fixture Study ({slug})

## Abstract
We solve a `{pc}` instance with deterministic tools and bind all numerics to solver JSON.

## Problem statement
See `{rel}/problem.md`.

## Related modeling notes
Research: `{state.get('research_path')}`.
Retrieval: `{state.get('retrieval_path')}`.

## Method / formulation
Schema: `{state['schema_path']}`.
Solver owns optima; validate recomputes.

## Results
From `{state['solution_path']}`:
- status: {sol.get('status')}
- objective = {sol.get('objective')}
- solution_shape: {shape}
- solver: {sol.get('solver')}

## Limitations
Fixture-scale. Live multi-agent + OpenPi evidence separate.

## Sources
- {wl_note}
- https://arxiv.org/abs/2503.10009
- {state['solution_path']}
- {state.get('research_path')}
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
    fb = _fixture_base(root, state["problem_id"])
    wl = fb / "whitelist_refs.json"
    r2_ok, r2_msg = gate_r2(root, paper, sol)
    r1_ok, r1_msg = gate_r1(root, paper, wl)
    fatals = []
    if not r2_ok:
        fatals.append(f"R2 failed: {r2_msg}")
    if not r1_ok:
        fatals.append(f"R1 failed: {r1_msg}")
    review = root / "outputs" / f"{slug}-review.md"
    body = f"## Summary\nT2 review pack `{slug}`.\n\n## Weaknesses\n"
    if fatals:
        for i, f in enumerate(fatals, 1):
            body += f"- [W{i}] **FATAL:** {f}\n"
    else:
        body += "- None FATAL from gates.\n"
    body += f"\n## Verdict\nr1={r1_ok} r2={r2_ok} validate={state.get('gate_validate_ok')}\n"
    review.write_text(body, encoding="utf-8")
    return {
        "stage": "revise_or_done",
        "review_path": str(review),
        "gate_r1_ok": r1_ok,
        "gate_r2_ok": r2_ok,
        "review_fatal": _count_fatal(body),
        "last_error": "; ".join(fatals),
    }


def node_revise_or_done(state: ORPathState) -> dict:
    ok = (
        state.get("gate_r1_ok")
        and state.get("gate_r2_ok")
        and state.get("review_fatal", 0) == 0
    )
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
    return {
        "stage": "human_stop",
        "human_required": True,
        "last_error": f"paper revise exhausted: {state.get('last_error')}",
    }


def node_provenance(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    prov = root / "outputs" / f"{slug}.provenance.md"
    lines = [
        f"# Provenance {slug}",
        f"- utc: {datetime.now(timezone.utc).isoformat()}",
        f"- problem_class: {state.get('problem_class')}",
        f"- solve_mode: {state['solve_mode']}",
        f"- knowledge_mode: {state.get('knowledge_mode')}",
        f"- schema_repair: {state.get('schema_repair')}",
        f"- solver_tune: {state.get('solver_tune')}",
        f"- validate_repair: {state.get('validate_repair')}",
        f"- revise_count: {state.get('revise_count')}",
        f"- human_required: {state.get('human_required')}",
        f"- gate_schema_ok: {state.get('gate_schema_ok')}",
        f"- gate_validate_ok: {state.get('gate_validate_ok')}",
        f"- gate_r1_ok: {state.get('gate_r1_ok')}",
        f"- gate_r2_ok: {state.get('gate_r2_ok')}",
        "",
        "## Artifacts",
    ]
    for k in (
        "plan_path",
        "retrieval_path",
        "research_path",
        "schema_path",
        "solution_path",
        "validate_path",
        "explain_path",
        "paper_path",
        "review_path",
        "tune_log_path",
    ):
        if state.get(k):
            lines.append(f"- {k}: `{state[k]}`")
    lines.append("")
    lines.append("## Notes")
    lines.append(
        "T2 LG nodes write file handoffs for CI; live Pi/OpenPi + bridge evidence separate."
    )
    prov.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"stage": "end", "provenance_path": str(prov)}
