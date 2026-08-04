"""OR-Path product stage nodes (authoritative).

ADR-0001: single deep module for pipeline stages.
Core stage bodies + product facade (bridge_pi, NodeContext wrap).
Live vs deterministic selected inside bodies (ORPATH_LIVE_SUBAGENT).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from orpath.gates import gate_claim_map, gate_r1, gate_r2, gate_schema, gate_validate, solve
from orpath.annotations_lite import annotations_from_review, write_annotations
from orpath.artifact_versions import record_versions
from orpath.claim_ledger import (
    build_claim_ledger,
    select_final_candidate,
    write_claim_ledger,
    write_verification_md,
)
from orpath.lab_continuity import append_lab_changelog, write_solution_figure
from orpath.subagent_dispatch import (
    live_subagent_enabled,
    merge_review_if_child_wrote,
    run_cite_subagent_lead,
    run_model_subagent_lead,
    run_research_subagent_lead,
    run_review_subagent_lead,
)
from orpath.paper_workflow import (
    append_plan_log,
    apply_revise_fixes,
    build_review_markdown,
    draft_paths,
    ensure_research_coverage_section,
    gate_research_text,
    load_retrieval,
    render_or_paper,
    thick_provenance,
)
from orpath.research_run import build_research_run, write_research_run
from orpath.revise_proof import extract_bad_urls, write_revise_proof
from orpath.state import ORPathState

TUNE_STRATEGIES = [
    ("PATH_CHEAPEST_ARC", "GUIDED_LOCAL_SEARCH", 2000),
    ("PATH_CHEAPEST_ARC", "SIMULATED_ANNEALING", 4000),
    ("SAVINGS", "GUIDED_LOCAL_SEARCH", 5000),
]


def _root(state: ORPathState) -> Path:
    return Path(state["root"])


def _rel_under(path: Path, root: Path) -> str:
    """Path relative to root when possible; else absolute posix (fixture may live under install home)."""
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _ensure_dirs(root: Path) -> None:
    for rel in (
        "outputs/.plans",
        "outputs/.drafts",
        "notes",
        "papers",
        "runs",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)


def _fixture_base(root: Path, problem_id: str) -> Path | None:
    """Locate fixtures/t*/<id> under workdir root and/or install home."""
    from orpath.paths import fixture_search_roots

    for base_root in fixture_search_roots(root):
        for base in (
            base_root / "fixtures" / "t3",
            base_root / "fixtures" / "t2",
            base_root / "fixtures" / "t1",
        ):
            if (base / problem_id).is_dir():
                return base / problem_id
    return None


def _infer_class(root: Path, problem_id: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    pid = (problem_id or "").strip().lower()
    # Ad-hoc / contest ids (no fixtures/t*/<id> dir)
    if "tube" in pid:
        return "tube_cut"
    if "polyomino" in pid or "poly" in pid:
        return "polyomino_cover"
    d = _fixture_base(root, problem_id)
    if d is None:
        # Intake-driven run without fixture: do not fake shortest_path gold.
        return "unknown"
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
- paper_template: or (P1)

## Task ledger
- [ ] retrieve
- [ ] research
- [ ] model
- [ ] solve
- [ ] validate
- [ ] explain
- [ ] draft
- [ ] cite
- [ ] review
- [ ] provenance

## Decision log
- Numbers only from solve+validate; paper drafts layered under outputs/.drafts/

## Verification log
""",
        encoding="utf-8",
    )
    append_plan_log(root, slug, stage="orchestrate", status="done", detail="plan created", plan_file=plan)
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
    r = subprocess.run(cmd, cwd=root, text=True, encoding="utf-8", errors="replace", capture_output=True)
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
    mode = state.get("knowledge_mode") or "off"
    fb = _fixture_base(root, pid)
    path = root / "notes" / f"{slug}-research.md"
    rp = state.get("retrieval_path")
    retrieval = load_retrieval(rp)

    # M3: live research fan-out via or-researcher subagent(s)
    sub_meta: dict = {"skipped": True, "gate_subagent_ok": None}
    try:
        sub_meta = run_research_subagent_lead(
            root,
            dict(state),
            research_path=path,
            retrieval_path=Path(rp) if rp else None,
            fixture_dir=fb,
        )
    except Exception as exc:  # noqa: BLE001
        sub_meta = {
            "skipped": False,
            "gate_subagent_ok": False,
            "error": f"research subagent failed: {exc}",
        }
        if live_subagent_enabled(dict(state)) and mode in {"seed", "hybrid"}:
            append_plan_log(
                root,
                slug,
                stage="research",
                status="fail",
                detail=str(exc)[:300],
                plan_file=state.get("plan_path"),
            )
            return {
                "stage": "human_stop",
                "human_required": True,
                "research_path": str(path) if path.is_file() else "",
                "gate_subagent_ok": False,
                "last_error": str(exc),
            }

    # Deterministic scaffold if no live research file yet
    if not path.is_file() or path.stat().st_size < 40:
        problem = (fb / "problem.md").read_text(encoding="utf-8")
        hits = retrieval.get("hits") or []
        seed_facts = retrieval.get("seed_facts") or []
        cite_rows = []
        for i, h in enumerate(hits[:5], 1):
            cite_rows.append(
                f"| {i} | chunk | {h.get('chunk_id')} | {str(h.get('snippet', ''))[:80]} | retrieval | med |"
            )
        if not cite_rows:
            cite_rows.append(
                f"| 1 | Problem | {fb.as_posix()}/problem.md | fixture primary | primary | high |"
            )
        for j, s in enumerate(seed_facts[:3], len(cite_rows) + 1):
            cite_rows.append(
                f"| {j} | seed | {s.get('id')} | {s.get('label', s.get('name', ''))} | seed | high |"
            )
        body = f"""# Research: {slug}

## Summary
Research for `{pc}` / `{pid}`. Retrieval mode={retrieval.get('knowledge_mode', mode)}.

## Problem class
{pc}

## Evidence table
| # | Source | Path/URL | Key claim | Type | Confidence |
|---|--------|----------|-----------|------|------------|
{chr(10).join(cite_rows)}

## Findings
1. Use deterministic solvers (networkx/cpsat/highs/ortools); never LLM optima.
2. Validate must recompute objective.
3. Seed/retrieval chunk_ids when present must be cited in this table.

## Modeling recommendations
- problem_class: {pc}
- no objective/tour/routes/path answers in schema

## Retrieval artifact
`{rp}`

## Problem excerpt
{problem[:800]}
"""
        body = ensure_research_coverage_section(body, retrieval or {"knowledge_mode": mode})
        path.write_text(body, encoding="utf-8")

    body = path.read_text(encoding="utf-8")
    # ensure coverage section even for live merges
    body2 = ensure_research_coverage_section(body, retrieval or {"knowledge_mode": mode})
    if body2 != body:
        path.write_text(body2, encoding="utf-8")
        body = body2

    ok, errs = gate_research_text(body, knowledge_mode=mode, retrieval=retrieval)
    sub_ok = sub_meta.get("gate_subagent_ok")
    live_req = live_subagent_enabled(dict(state)) and mode in {"seed", "hybrid"}
    if live_req and sub_ok is False:
        ok = False
        errs = list(errs) + [f"subagent={sub_meta.get('error') or 'failed'}"]

    append_plan_log(
        root,
        slug,
        stage="research",
        status="pass" if ok else "fail",
        detail=(
            ("; ".join(errs) if errs else "evidence+coverage ok")
            + f" subagent={sub_ok} scale={sub_meta.get('scale')}"
        ),
        plan_file=state.get("plan_path"),
    )
    if not ok and mode in {"seed", "hybrid"}:
        return {
            "stage": "human_stop",
            "human_required": True,
            "research_path": str(path),
            "gate_subagent_ok": sub_ok,
            "last_error": "research_gate: " + "; ".join(errs),
        }
    return {
        "stage": "model",
        "research_path": str(path),
        "gate_subagent_ok": sub_ok,
        "last_error": "",
    }


def node_model(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    pid = state["problem_id"]
    pc = state.get("problem_class") or "shortest_path"
    fb = _fixture_base(root, pid)
    sp = root / "outputs" / f"{slug}-schema.json"

    # M3: live or-modeler subagent
    sub_meta: dict = {"skipped": True, "gate_subagent_ok": None}
    try:
        sub_meta = run_model_subagent_lead(
            root,
            dict(state),
            schema_path=sp,
            research_path=Path(state["research_path"]) if state.get("research_path") else None,
            fixture_dir=fb,
        )
    except Exception as exc:  # noqa: BLE001
        sub_meta = {
            "skipped": False,
            "gate_subagent_ok": False,
            "error": f"model subagent failed: {exc}",
        }

    live_req = live_subagent_enabled(dict(state))
    sub_ok = sub_meta.get("gate_subagent_ok")

    # Deterministic modeler if live skipped/off/failed (Path A: never leave empty schema).
    need_det = bool(sub_meta.get("skipped") or (not live_req) or (not sp.is_file()))
    if live_req and sub_ok is False:
        live_err = str(sub_meta.get("error") or "model subagent failed")
        append_plan_log(
            root,
            slug,
            stage="model",
            status="warn",
            detail=("live model failed → deterministic fallback: " + live_err)[:300],
            plan_file=state.get("plan_path"),
        )
        need_det = True

    if need_det or not sp.is_file():
        schema: dict
        try:
            from orpath.domain_registry import is_polyomino_class, normalize_problem_class

            pc_n = normalize_problem_class(pc) or str(pc or "")
            poly = is_polyomino_class(pc_n)
        except Exception:  # noqa: BLE001
            pc_n = str(pc or "")
            poly = "polyomino" in pc_n.lower()

        if pc_n == "shortest_path" or pc == "shortest_path":
            if fb is None:
                return {
                    "stage": "human_stop",
                    "human_required": True,
                    "last_error": "model: no fixture for shortest_path",
                }
            graph = json.loads((fb / "graph.json").read_text(encoding="utf-8"))
            schema = {
                "slug": slug,
                "problem_class": "shortest_path",
                "problem_id": pid,
                "nodes": graph.get("nodes", []),
                "edges_ref": _rel_under(fb / "graph.json", root),
                "source": graph["nodes"][0],
                "target": graph["nodes"][-1],
                "weight_key": "w",
                "preferred_solve_mode": "networkx",
                "constraints": [],
                "notes": "T2/T3 deterministic modeler",
            }
        elif pc_n == "tsp" or pc == "tsp":
            if fb is None:
                return {
                    "stage": "human_stop",
                    "human_required": True,
                    "last_error": "model: no fixture for tsp",
                }
            coords = json.loads((fb / "coords.json").read_text(encoding="utf-8"))
            schema = {
                "slug": slug,
                "problem_class": "tsp",
                "problem_id": pid,
                "coords": coords.get("coords", coords),
                "preferred_solve_mode": "cpsat",
                "constraints": [],
                "notes": "T2/T3 TSP modeler",
            }
        elif poly:
            board: dict = {}
            if fb is not None and (fb / "board.json").is_file():
                board = json.loads((fb / "board.json").read_text(encoding="utf-8"))
            schema = {
                "slug": slug,
                "problem_class": "polyomino_cover",
                "problem_id": pid,
                "preferred_solve_mode": "polyomino",
                "constraints": [],
                "notes": "M2 polyomino deterministic modeler (no placements/objective)",
            }
            if board:
                schema["board_ref"] = (
                    _rel_under(fb / "board.json", root) if fb else "board.json"
                )
                for k in ("rows", "cols", "pieces", "removed", "max_counts"):
                    if k in board and board[k] is not None:
                        schema[k] = board[k]
            else:
                schema["rows"] = 4
                schema["cols"] = 4
                schema["pieces"] = [{"id": "M"}, {"id": "D"}, {"id": "L3"}]
        else:
            if fb is None or not (fb / "locations.json").is_file():
                return {
                    "stage": "human_stop",
                    "human_required": True,
                    "last_error": f"model: unsupported class or missing fixture pc={pc}",
                }
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
                "preferred_solve_mode": "ortools",
                "constraints": ["capacity"],
                "notes": "T2 multi-vehicle VRP modeler (not proven global opt)",
            }
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")

    append_plan_log(
        root,
        slug,
        stage="model",
        status="pass",
        detail=f"schema={sp.name} subagent={sub_ok}",
        plan_file=state.get("plan_path"),
    )
    return {
        "stage": "gate_schema",
        "schema_path": str(sp),
        "gate_subagent_ok": sub_ok if sub_ok is not None else state.get("gate_subagent_ok"),
        "last_error": "",
    }


def node_gate_schema(state: ORPathState) -> dict:
    root = _root(state)
    raw_sp = state.get("schema_path") or ""
    sp = Path(str(raw_sp)) if str(raw_sp).strip() not in {"", "."} else Path()
    if not sp.is_file():
        msg = (
            "schema_path missing or not a file "
            f"(got {raw_sp!r}) — modeler did not write outputs/*-schema.json"
        )
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
            "human_required": True,
            "gate_schema_ok": False,
            "last_error": f"schema repair exhausted: {msg}",
        }
    ok, msg = gate_schema(root, sp)
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


def _intake_front_door_active(state: ORPathState) -> bool:
    """True when run used intake sources (not default skip_intake CI path)."""
    if state.get("skip_intake"):
        return False
    if state.get("intake_path"):
        return True
    srcs = state.get("intake_sources") or []
    return bool(srcs)



def _solution_is_blocked(state: ORPathState) -> bool:
    """True when solve refused / BLOCKED envelope (intake soak, no domain adapter)."""
    if state.get("solve_refused"):
        return True
    sp = state.get("solution_path") or ""
    p = Path(sp) if sp else None
    if not p or not p.is_file():
        return False
    try:
        sol = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(sol, dict):
        return False
    if str(sol.get("status") or "").upper() == "BLOCKED":
        return True
    meta = sol.get("meta")
    return bool(isinstance(meta, dict) and meta.get("blocked"))


def _intake_whitelist_path(root: Path, state: ORPathState) -> Path:
    """Write/return intake-scoped whitelist (no SP fixture arxiv) for blocked soak paper."""
    slug = str(state.get("slug") or "run")
    out = root / "outputs" / f"{slug}-intake-whitelist.json"
    notes: list[str] = ["notes://intake-blocked-soak"]
    bp = state.get("brief_path") or ""
    ip = state.get("intake_path") or ""
    rp = state.get("research_path") or ""
    if bp:
        notes.append(str(bp).replace("\\", "/"))
    if ip:
        notes.append(str(ip).replace("\\", "/"))
    if rp:
        notes.append(str(rp).replace("\\", "/"))
    notes.append(f"notes://{slug}-research")
    payload = {"urls": [], "notes": notes, "meta": {"kind": "intake_blocked_soak"}}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def _paper_whitelist_path(
    root: Path, state: ORPathState, fixture_dir: Path | None
) -> Path:
    """R4: when intake-on or BLOCKED, do not use shell fixture whitelist_refs.json."""
    blocked = _solution_is_blocked(state)
    intake_on = _intake_front_door_active(state)
    if blocked or intake_on or fixture_dir is None:
        return _intake_whitelist_path(root, state)
    wl = fixture_dir / "whitelist_refs.json"
    return wl



def node_solve(state: ORPathState) -> dict:
    root = _root(state)
    pc = state.get("problem_class") or "shortest_path"
    mode = state["solve_mode"]
    out = root / "outputs" / f"{state['slug']}-solution.json"

    # 1.2 soak law: intake-on must NOT bind fixture SP/TSP/VRP gold as the answer.
    # Domain adapters (tube_cut, polyomino_cover) may still run under intake.
    if _intake_front_door_active(state):
        pc_l = str(pc or "").lower()
        pid_l = str(state.get("problem_id") or "").lower()
        try:
            from orpath.domain_registry import is_polyomino_class, is_registered_solve_class

            poly_ad = is_polyomino_class(pc_l) or "polyomino" in pid_l
            tube_ad = pc_l in {"tube_cut", "tube", "tube_bfd"} or "tube" in pid_l
            has_domain_adapter = bool(poly_ad or tube_ad or is_registered_solve_class(pc_l))
        except Exception:  # noqa: BLE001
            poly_ad = "polyomino" in pc_l or "polyomino" in pid_l
            tube_ad = pc_l in {"tube_cut", "tube", "tube_bfd"} or "tube" in pid_l
            has_domain_adapter = poly_ad or tube_ad
        if not has_domain_adapter:
            blocked = {
                "status": "BLOCKED",
                "objective": None,
                "solver": "none",
                "source": "no_domain_adapter_for_intake",
                "problem_id": state.get("problem_id"),
                "problem_class": pc,
                "slug": state.get("slug"),
                "meta": {
                    "exact": False,
                    "proven_optimal": False,
                    "blocked": True,
                    "method_class": "fixture",
                    "reason": (
                        "intake front-door active: refusing fixture solve bind "
                        f"(problem_id={state.get('problem_id')!r}, mode={mode!r}); "
                        "no contest-domain adapter registered"
                    ),
                    "intake_path": state.get("intake_path") or "",
                    "brief_path": state.get("brief_path") or "",
                },
            }
            out.write_text(json.dumps(blocked, indent=2) + "\n", encoding="utf-8")
            return {
                "stage": "gate_validate",
                "solution_path": str(out),
                "gate_validate_ok": False,
                "last_error": "no_domain_adapter_for_intake",
                "solve_refused": True,
            }
        # Prefer domain solve mode when adapter applies
        if has_domain_adapter and str(mode).lower() in {"mock", "auto", ""}:
            mode = "polyomino" if poly_ad else "tube"

    # Non-intake: polyomino must not use SP mock bind
    try:
        from orpath.domain_registry import is_polyomino_class

        if is_polyomino_class(str(pc or "")) or "polyomino" in str(
            state.get("problem_id") or ""
        ).lower():
            if str(mode).lower() in {"mock", "auto", "ortools", ""}:
                mode = "polyomino"
    except Exception:  # noqa: BLE001
        if "polyomino" in str(pc or "").lower() or "polyomino" in str(
            state.get("problem_id") or ""
        ).lower():
            if str(mode).lower() in {"mock", "auto", "ortools", ""}:
                mode = "polyomino"

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
    if not ok and mode not in {
        "mock",
        "polyomino",
        "polyomino_cover",
        "poly",
        "tube",
        "tube_cut",
    }:
        ok, data, raw = solve(root, state["problem_id"], "mock", pc)
    if not ok:
        return {
            "stage": "human_stop",
            "human_required": True,
            "last_error": raw,
        }
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {
        "stage": "gate_validate",
        "solution_path": str(out),
        "last_error": "",
    }

def node_gate_validate(state: ORPathState) -> dict:
    root = _root(state)
    vpath = root / "outputs" / f"{state['slug']}-validate.json"
    sol_path = Path(state.get("solution_path") or "")
    # BLOCKED / intake refuse: no tune/model repair ladder — go explain→paper shell
    if sol_path.is_file():
        try:
            sol_obj = json.loads(sol_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            sol_obj = {}
        meta = sol_obj.get("meta") if isinstance(sol_obj, dict) else None
        blocked = bool(
            isinstance(sol_obj, dict)
            and (
                str(sol_obj.get("status") or "").upper() == "BLOCKED"
                or (isinstance(meta, dict) and meta.get("blocked"))
                or state.get("solve_refused")
            )
        )
        if blocked:
            report = {
                "ok": False,
                "blocked": True,
                "errors": [
                    sol_obj.get("meta", {}).get("reason")
                    if isinstance(sol_obj.get("meta"), dict)
                    else "solution BLOCKED"
                ],
                "solution_path": str(sol_path),
                "detail": "intake_or_domain_adapter_blocked",
            }
            vpath.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            return {
                "stage": "explain",
                "validate_path": str(vpath),
                "gate_validate_ok": False,
                "human_required": True,
                "last_error": state.get("last_error") or "no_domain_adapter_for_intake",
            }

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
    sol_path = Path(state.get("solution_path") or "")
    if sol_path.is_file():
        sol = json.loads(sol_path.read_text(encoding="utf-8"))
    else:
        sol = {"status": "MISSING", "objective": None, "solver": "none"}
    path = root / "notes" / f"{state['slug']}-explain.md"
    shape = sol.get("path") or sol.get("tour") or sol.get("routes")
    meta = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
    blocked = str(sol.get("status") or "").upper() == "BLOCKED" or bool(meta.get("blocked"))
    note = (
        "**BLOCKED:** no domain adapter for intake problem — do not treat fixture gold as answer."
        if blocked
        else ""
    )
    path.write_text(
        (
            f"# Explain: {state['slug']}\n\n"
            f"Solver `{sol.get('solver')}` status `{sol.get('status')}`.\n\n"
            f"- objective: {sol.get('objective')}\n"
            f"- shape: {shape}\n"
            f"- validate: {state.get('validate_path')}\n"
            f"- blocked: {blocked}\n"
            f"- last_error: {state.get('last_error')}\n\n"
            f"All numbers from `{state.get('solution_path')}` only.\n"
            f"{note}\n"
        ),
        encoding="utf-8",
    )
    return {"stage": "draft_paper", "explain_path": str(path)}


def node_draft_paper(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    sol_path = Path(state.get("solution_path") or "")
    if sol_path.is_file():
        sol = json.loads(sol_path.read_text(encoding="utf-8"))
    else:
        sol = {
            "status": "BLOCKED",
            "objective": None,
            "solver": "none",
            "source": "missing_solution",
            "meta": {"blocked": True, "exact": False, "proven_optimal": False},
        }
        sol_path = root / "outputs" / f"{slug}-solution.json"
        sol_path.write_text(json.dumps(sol, indent=2) + "\n", encoding="utf-8")
    paths = draft_paths(root, slug)
    paths["paper"].parent.mkdir(parents=True, exist_ok=True)
    pc = state.get("problem_class") or sol.get("problem_class")
    fb = _fixture_base(root, state["problem_id"])
    meta0 = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
    blocked0 = str(sol.get("status") or "").upper() == "BLOCKED" or bool(meta0.get("blocked"))
    intake_on = _intake_front_door_active(state)
    if blocked0 or intake_on:
        if fb is not None:
            try:
                rel = "shell_only:" + _rel_under(fb, root)
            except ValueError:
                rel = f"shell_only:adhoc:{state.get('problem_id')}"
        else:
            rel = f"shell_only:adhoc:{state.get('problem_id')}"
        wl_path = _paper_whitelist_path(root, state, fb)
        cites: list[str] = []
        try:
            wl = json.loads(wl_path.read_text(encoding="utf-8"))
            cites.extend(str(u) for u in (wl.get("urls") or []))
            cites.extend(str(n) for n in (wl.get("notes") or []))
        except (json.JSONDecodeError, OSError):
            cites = ["notes://intake-blocked-soak"]
        cites = [
            c
            for c in cites
            if "arxiv" not in c.lower() and "shortest-path" not in c.lower()
        ]
        if not cites:
            cites = ["notes://intake-blocked-soak"]
    else:
        if fb is None:
            rel = f"adhoc:{state.get('problem_id')}"
            cites = []
            wl_path = _paper_whitelist_path(root, state, None)
        else:
            try:
                rel = _rel_under(fb, root)
            except ValueError:
                rel = str(fb)
            cites = []
            wl_path = fb / "whitelist_refs.json"
        if wl_path.is_file():
            try:
                wl = json.loads(wl_path.read_text(encoding="utf-8"))
                cites.extend(str(u) for u in (wl.get("urls") or []))
            except json.JSONDecodeError:
                cites = []
        if not cites:
            cites = [
                "notes://t2-tsp-ref"
                if pc == "tsp"
                else (
                    "notes://t2-vrp-ref"
                    if pc == "vrp"
                    else "notes://t1-shortest-path-ref"
                )
            ]
    source_lines = list(cites)
    source_lines.append(str(sol_path))
    if state.get("research_path"):
        source_lines.append(str(state.get("research_path")))
    if state.get("validate_path"):
        source_lines.append(str(state.get("validate_path")))
    if state.get("brief_path"):
        source_lines.append(str(state.get("brief_path")))
    if state.get("intake_path"):
        source_lines.append(str(state.get("intake_path")))

    body = render_or_paper(
        slug=slug,
        problem_class=str(pc),
        problem_id=state["problem_id"],
        solution=sol,
        solution_path=str(sol_path),
        schema_path=str(state.get("schema_path") or ""),
        research_path=str(state.get("research_path") or ""),
        retrieval_path=str(state.get("retrieval_path") or ""),
        validate_path=str(state.get("validate_path") or ""),
        explain_path=str(state.get("explain_path") or ""),
        fixture_rel=rel,
        source_lines=source_lines,
        template="or",
    )
    meta = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
    if str(sol.get("status") or "").upper() == "BLOCKED" or meta.get("blocked"):
        body = (
            body
            + "\n\n## Provenance note (intake soak)\n\n"
            + "Solution status is **BLOCKED** (`no_domain_adapter_for_intake`). "
            + "Do **not** invent Q1–Q4 numeric tables or 2-week profit forecasts. "
                        + "Do **not** treat shell fixture gold objectives as contest answers. "
                        + "Paper gates R2/claim should remain BLOCKED/fail-closed.\n"
                    )
    # P1-5 layered drafts: draft only here; cite_pack builds cited
    paths["draft"].write_text(body, encoding="utf-8")
    paths["paper"].write_text(body, encoding="utf-8")
    append_plan_log(
        root,
        slug,
        stage="draft",
        status="done",
        detail=f"wrote {paths['draft'].name} (pending cite_pack)",
        plan_file=state.get("plan_path"),
    )
    return {
        "stage": "cite_pack",
        "paper_path": str(paths["paper"]),
        "solution_path": str(sol_path),
        "last_error": "",
    }


def node_cite_pack(state: ORPathState) -> dict:
    """P0-1/P0-2: cite layer — optional live or-verifier subagent + R1/claim → cited."""
    root = _root(state)
    slug = state["slug"]
    paths = draft_paths(root, slug)
    paper = Path(state["paper_path"])
    if not paper.is_file() and paths["draft"].is_file():
        paper = paths["draft"]
    fb = _fixture_base(root, state["problem_id"])
    wl = _paper_whitelist_path(root, state, fb)
    sol = Path(state["solution_path"])
    claim_out = root / "outputs" / ".drafts" / f"{slug}-claim-map.json"

    # M2: live short lead → subagent or-verifier (skipped when ORPATH_LIVE_SUBAGENT=0)
    sub_meta: dict = {"skipped": True, "gate_subagent_ok": None}
    try:
        sub_meta = run_cite_subagent_lead(
            root,
            dict(state),
            paper=paper,
            cited=paths["cited"],
            solution=sol,
            whitelist=wl if wl.is_file() else None,
            research=Path(state["research_path"]) if state.get("research_path") else None,
            claim_map=claim_out,
        )
    except Exception as exc:  # noqa: BLE001
        sub_meta = {
            "skipped": False,
            "gate_subagent_ok": False,
            "error": f"cite subagent spawn failed: {exc}",
        }
        if live_subagent_enabled(dict(state)):
            append_plan_log(
                root,
                slug,
                stage="cite",
                status="fail",
                detail=str(exc)[:300],
                plan_file=state.get("plan_path"),
            )
            return {
                "stage": "review_pack",
                "paper_path": str(paper),
                "cited_path": str(paths["cited"]) if paths["cited"].is_file() else "",
                "gate_r1_ok": False,
                "gate_claim_ok": False,
                "gate_subagent_ok": False,
                "last_error": str(exc),
            }

    # If child wrote cited, prefer it as working paper body for subsequent gates
    if paths["cited"].is_file() and paths["cited"].stat().st_size > 50 and not sub_meta.get("skipped"):
        try:
            child = paths["cited"].read_text(encoding="utf-8")
            # strip prior claim-map footers if re-run
            paper.write_text(child, encoding="utf-8")
        except OSError:
            pass

    r1_ok, r1_msg = gate_r1(root, paper, wl)
    claim_ok, claim_msg = gate_claim_map(
        root,
        paper,
        sol,
        whitelist=wl if wl.is_file() else None,
        research=Path(state["research_path"]) if state.get("research_path") else None,
        retrieval=Path(state["retrieval_path"]) if state.get("retrieval_path") else None,
        out=claim_out,
    )

    body = paper.read_text(encoding="utf-8") if paper.is_file() else ""
    # append claim-map summary into cited artifact
    cmap = {}
    if claim_out.is_file():
        try:
            cmap = json.loads(claim_out.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cmap = {}
    footer = [
        "",
        "---",
        "## Claim map (P0 cite_pack)",
        f"- r1_ok: {r1_ok}",
        f"- claim_map_ok: {claim_ok}",
        f"- claim_map_path: `{claim_out}`",
        f"- claims_recorded: {len(cmap.get('claims') or [])}",
        f"- subagent_live: {not sub_meta.get('skipped')}",
        f"- gate_subagent_ok: {sub_meta.get('gate_subagent_ok')}",
    ]
    if sub_meta.get("log_path"):
        footer.append(f"- subagent_lead_log: `{sub_meta.get('log_path')}`")
    if not claim_ok:
        footer.append(f"- claim_errors: {claim_msg[:500]}")
    cited_body = body.rstrip() + "\n" + "\n".join(footer) + "\n"
    paths["cited"].write_text(cited_body, encoding="utf-8")
    paper.write_text(body, encoding="utf-8")

    sub_ok = sub_meta.get("gate_subagent_ok")
    # Live cite fail: if solve+validate already green, keep deterministic R1/claim
    # so Path-A does not hang the whole face on paper prose alone (numbers truth first).
    live_req = live_subagent_enabled(dict(state))
    if live_req and sub_ok is False:
        if state.get("gate_validate_ok"):
            ok = bool(r1_ok and claim_ok)
            append_plan_log(
                root,
                slug,
                stage="cite",
                status="warn",
                detail=(
                    "live cite failed/timeout; kept deterministic gates because "
                    f"validate_ok=1 sub_err={(sub_meta.get('error') or '')[:180]}"
                ),
                plan_file=state.get("plan_path"),
            )
        else:
            ok = False
    else:
        ok = r1_ok and claim_ok

    # Deep Feynman-style claim ledger + verification.md
    research_text = ""
    if state.get("research_path") and Path(state["research_path"]).is_file():
        research_text = Path(state["research_path"]).read_text(encoding="utf-8")
    texts = [(str(paper), body)]
    if research_text:
        texts.append((str(state["research_path"]), research_text))
    if paths["cited"].is_file():
        texts.append((str(paths["cited"]), paths["cited"].read_text(encoding="utf-8")))
    ledger = build_claim_ledger(
        slug=slug,
        texts=texts,
        r1_ok=r1_ok,
        r2_ok=None,
        claim_map_ok=claim_ok,
        research_ok=None,
        validate_ok=state.get("gate_validate_ok"),
    )
    write_claim_ledger(paths["claim_ledger"], ledger)
    write_verification_md(
        paths["verification"],
        ledger,
        extra=(
            f"cite_pack r1={r1_ok} claim_map={claim_ok} subagent={sub_ok}\n"
            f"{claim_msg[:400] if not claim_ok else ''}\n"
            f"{sub_meta.get('error') or ''}"
        ),
    )

    append_plan_log(
        root,
        slug,
        stage="cite",
        status="pass" if ok else "fail",
        detail=(
            f"r1={r1_ok} claim={claim_ok} subagent={sub_ok} "
            f"ledger_claims={ledger.get('claimCount')} vstate={ledger.get('verificationState')}"
        ),
        plan_file=state.get("plan_path"),
    )
    err_parts = []
    if not ok:
        if live_req and sub_ok is False:
            err_parts.append(f"subagent={sub_meta.get('error') or 'failed'}")
        if not r1_ok or not claim_ok:
            err_parts.append(f"cite: r1={r1_msg}; claim={claim_msg}")
    return {
        "stage": "review_pack",
        "paper_path": str(paper),
        "cited_path": str(paths["cited"]),
        "gate_r1_ok": r1_ok,
        "gate_claim_ok": claim_ok,
        "gate_subagent_ok": sub_ok,
        "verification_state": ledger.get("verificationState"),
        "last_error": "" if ok else "; ".join(err_parts),
    }


def _count_fatal(review_text: str) -> int:
    return len(re.findall(r"\*\*FATAL:\*\*", review_text))


def node_review_pack(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    paper = Path(state["paper_path"])
    sol = Path(state["solution_path"])
    fb = _fixture_base(root, state["problem_id"])
    wl = _paper_whitelist_path(root, state, fb)
    paper_text = paper.read_text(encoding="utf-8") if paper.is_file() else ""
    review = root / "outputs" / f"{slug}-review.md"

    # M2: live short lead → subagent or-reviewer (serial after cite)
    sub_meta: dict = {"skipped": True, "gate_subagent_ok": None}
    try:
        sub_meta = run_review_subagent_lead(
            root,
            dict(state),
            paper=paper,
            review=review,
            solution=sol,
            whitelist=wl if wl.is_file() else None,
        )
    except Exception as exc:  # noqa: BLE001
        sub_meta = {
            "skipped": False,
            "gate_subagent_ok": False,
            "error": f"review subagent spawn failed: {exc}",
        }

    r2_ok, r2_msg = gate_r2(root, paper, sol)
    r1_ok, r1_msg = gate_r1(root, paper, wl)
    claim_out = root / "outputs" / ".drafts" / f"{slug}-claim-map.json"
    claim_ok, claim_msg = gate_claim_map(
        root,
        paper,
        sol,
        whitelist=wl if wl.is_file() else None,
        research=Path(state["research_path"]) if state.get("research_path") else None,
        retrieval=Path(state["retrieval_path"]) if state.get("retrieval_path") else None,
        out=claim_out,
    )
    # prefer prior cite_pack flag if present and claim still run
    if state.get("gate_claim_ok") is False and claim_ok:
        pass

    research_ok = None
    research_msg = ""
    rp = state.get("research_path")
    if rp and Path(rp).is_file():
        rok, rerrs = gate_research_text(
            Path(rp).read_text(encoding="utf-8"),
            knowledge_mode=str(state.get("knowledge_mode") or "off"),
            retrieval=load_retrieval(state.get("retrieval_path")),
        )
        research_ok = rok
        research_msg = "; ".join(rerrs)

    body, fatal_n = build_review_markdown(
        slug=slug,
        paper_text=paper_text,
        r1_ok=r1_ok,
        r1_msg=r1_msg,
        r2_ok=r2_ok,
        r2_msg=r2_msg,
        validate_ok=state.get("gate_validate_ok"),
        research_ok=research_ok,
        research_msg=research_msg,
    )
    # inject claim map fatals
    if not claim_ok:
        body += f"\n### Claim map FATAL\n- **FATAL:** {claim_msg}\n"
        fatal_n = len(re.findall(r"\*\*FATAL:\*\*", body))

    # Merge child reviewer prose when live subagent wrote a review
    body = merge_review_if_child_wrote(automated_body=body, child_review=review)
    fatal_n = len(re.findall(r"\*\*FATAL:\*\*", body))

    review.write_text(body, encoding="utf-8")
    # P2 annotations-lite from review
    ann_path = root / "outputs" / ".drafts" / f"{slug}-annotations.json"
    anns = annotations_from_review(body, artifact_path=str(paper), slug=slug)
    write_annotations(ann_path, slug=slug, annotations=anns)
    vn = root / "outputs" / f"{slug}-verify-notes.md"
    vn.write_text(
        f"# Verify notes {slug}\n\n- r1={r1_ok} ({r1_msg})\n- r2={r2_ok} ({r2_msg})\n"
        f"- claim_map={claim_ok} ({claim_msg[:300]})\n"
        f"- research_gate={research_ok} ({research_msg})\n- fatals={fatal_n}\n"
        f"- subagent_live={not sub_meta.get('skipped')} gate_subagent_ok={sub_meta.get('gate_subagent_ok')}\n"
        f"- subagent_log={sub_meta.get('log_path') or 'n/a'}\n",
        encoding="utf-8",
    )
    fatals = []
    live_req = live_subagent_enabled(dict(state))
    sub_ok = sub_meta.get("gate_subagent_ok")
    if live_req and sub_ok is False:
        fatals.append(f"subagent failed: {sub_meta.get('error') or 'no subagent call'}")
    if not r2_ok:
        fatals.append(f"R2 failed: {r2_msg}")
    if not r1_ok:
        fatals.append(f"R1 failed: {r1_msg}")
    if not claim_ok:
        fatals.append(f"claim_map failed: {claim_msg}")
    append_plan_log(
        root,
        slug,
        stage="review",
        status="pass" if not fatals else "fail",
        detail="; ".join(fatals) if fatals else f"r1/r2/claim green subagent={sub_ok}",
        plan_file=state.get("plan_path"),
    )
    # preserve cite subagent flag if review skipped
    gate_sub = sub_ok if sub_ok is not None else state.get("gate_subagent_ok")
    return {
        "stage": "revise_or_done",
        "review_path": str(review),
        "gate_r1_ok": r1_ok,
        "gate_r2_ok": r2_ok,
        "gate_claim_ok": claim_ok,
        "gate_subagent_ok": gate_sub,
        "review_fatal": fatal_n,
        "last_error": "; ".join(fatals),
    }


def node_revise_or_done(state: ORPathState) -> dict:
    ok = (
        state.get("gate_r1_ok")
        and state.get("gate_r2_ok")
        and state.get("gate_claim_ok", True)
        and state.get("review_fatal", 0) == 0
    )
    root = _root(state)
    slug = state["slug"]
    paths = draft_paths(root, slug)

    # 1.2 / intake soak: BLOCKED solution → paper shell is fail-closed by design.
    # Do NOT burn revise + live cite/review loops on fixture gold prose (42/32/…).
    if _solution_is_blocked(state):
        append_plan_log(
            root,
            slug,
            stage="revise",
            status="blocked",
            detail="solution BLOCKED — skip revise ladder; provenance fail-closed",
            plan_file=state.get("plan_path"),
        )
        return {
            "stage": "provenance",
            "human_required": True,
            "gate_r2_ok": False,
            "gate_claim_ok": False,
            "paper_blocked": True,
            "last_error": (
                "paper_blocked_no_domain_adapter: "
                + str(state.get("last_error") or "R2/claim not applicable")
            )[:500],
        }

    if ok:
        append_plan_log(
            root,
            slug,
            stage="revise",
            status="skip",
            detail="no FATAL; proceed provenance",
            plan_file=state.get("plan_path"),
        )
        return {"stage": "provenance", "last_error": ""}

    rev = int(state.get("revise_count") or 0)
    max_r = int(state.get("max_revise") or 2)
    if rev >= max_r:
        append_plan_log(
            root,
            slug,
            stage="revise",
            status="exhausted",
            detail=str(state.get("last_error") or ""),
            plan_file=state.get("plan_path"),
        )
        return {
            "stage": "human_stop",
            "human_required": True,
            "last_error": f"paper revise exhausted: {state.get('last_error')}",
        }

    paper = Path(state["paper_path"])
    sol = json.loads(Path(state["solution_path"]).read_text(encoding="utf-8"))
    fb = _fixture_base(root, state["problem_id"])
    wl_path = _paper_whitelist_path(root, state, fb)
    allowed: list[str] = []
    if wl_path.is_file():
        try:
            wl = json.loads(wl_path.read_text(encoding="utf-8"))
            allowed.extend(str(u) for u in (wl.get("urls") or []))
            allowed.extend(str(n) for n in (wl.get("notes") or []))
        except json.JSONDecodeError:
            pass
    old = paper.read_text(encoding="utf-8") if paper.is_file() else ""
    bad_urls = extract_bad_urls(old, set(allowed))
    fixed = apply_revise_fixes(
        old,
        solution=sol,
        allowed_urls=allowed,
        solution_path=state["solution_path"],
    )
    # strip global-opt marketing if not proven
    if not (sol.get("meta") or {}).get("proven_optimal"):
        fixed = re.sub(
            r"(?i)global(?:ly)?\s+optimal|保证全局最优|数学证明最优",
            "best-found / validated feasible",
            fixed,
        )
    paths["revised"].write_text(fixed, encoding="utf-8")
    paper.write_text(fixed, encoding="utf-8")

    r2_ok, r2_msg = gate_r2(root, paper, Path(state["solution_path"]))
    r1_ok, r1_msg = gate_r1(root, paper, wl_path)
    claim_out = root / "outputs" / ".drafts" / f"{slug}-claim-map.json"
    claim_ok, claim_msg = gate_claim_map(
        root,
        paper,
        Path(state["solution_path"]),
        whitelist=wl_path if wl_path.is_file() else None,
        research=Path(state["research_path"]) if state.get("research_path") else None,
        retrieval=Path(state["retrieval_path"]) if state.get("retrieval_path") else None,
        out=claim_out,
    )

    proof_path = root / "outputs" / ".drafts" / f"{slug}-revise-proof.md"
    write_revise_proof(
        proof_path,
        slug=slug,
        before=old,
        after=fixed,
        removed_needles=bad_urls
        + (
            ["global optimal", "保证全局最优"]
            if not (sol.get("meta") or {}).get("proven_optimal")
            else []
        ),
        r1_ok=r1_ok,
        r2_ok=r2_ok,
        claim_ok=claim_ok,
        detail=f"rev={rev+1} r1={r1_msg[:80]} r2={r2_msg[:80]} claim={claim_msg[:80]}",
    )

    append_plan_log(
        root,
        slug,
        stage="revise",
        status="pass" if (r1_ok and r2_ok and claim_ok) else "retry",
        detail=f"rev={rev+1} proof={proof_path.name} r1={r1_ok} r2={r2_ok} claim={claim_ok}",
        plan_file=state.get("plan_path"),
    )

    if r1_ok and r2_ok and claim_ok:
        body, fatal_n = build_review_markdown(
            slug=slug,
            paper_text=fixed,
            r1_ok=True,
            r1_msg="ok",
            r2_ok=True,
            r2_msg="ok",
            validate_ok=state.get("gate_validate_ok"),
            research_ok=True,
            research_msg="",
        )
        if state.get("review_path"):
            Path(state["review_path"]).write_text(body, encoding="utf-8")
        return {
            "stage": "provenance",
            "revise_count": rev + 1,
            "gate_r1_ok": True,
            "gate_r2_ok": True,
            "gate_claim_ok": True,
            "review_fatal": 0,
            "paper_path": str(paper),
            "last_error": "",
        }

    # re-enter cite→review after partial fix
    return {
        "stage": "cite_pack",
        "revise_count": rev + 1,
        "gate_r1_ok": r1_ok,
        "gate_r2_ok": r2_ok,
        "gate_claim_ok": claim_ok,
        "paper_path": str(paper),
        "last_error": f"after revise: r1={r1_msg}; r2={r2_msg}; claim={claim_msg}",
    }

def node_provenance(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    dpaths = draft_paths(root, slug)
    # Promote final candidate (Feynman: revised > cited > draft)
    final = select_final_candidate(dpaths)
    if final and final.is_file():
        paper_out = dpaths["paper"]
        paper_out.parent.mkdir(parents=True, exist_ok=True)
        body = final.read_text(encoding="utf-8")
        # strip cite footer if present when promoting cited
        if "## Claim map (P0 cite_pack)" in body:
            body = body.split("## Claim map (P0 cite_pack)")[0].rstrip() + "\n"
        paper_out.write_text(body, encoding="utf-8")
        final_path = str(final)
    else:
        final_path = state.get("paper_path") or ""

    # rebuild ledger at end with all gates
    texts: list[tuple[str, str]] = []
    for key in ("draft", "cited", "revised", "paper", "verification"):
        p = dpaths.get(key)
        if p and Path(p).is_file():
            texts.append((str(p), Path(p).read_text(encoding="utf-8")))
    if state.get("research_path") and Path(state["research_path"]).is_file():
        texts.append(
            (str(state["research_path"]), Path(state["research_path"]).read_text(encoding="utf-8"))
        )
    research_ok = None
    if state.get("research_path") and Path(state["research_path"]).is_file():
        rok, _ = gate_research_text(
            Path(state["research_path"]).read_text(encoding="utf-8"),
            knowledge_mode=str(state.get("knowledge_mode") or "off"),
            retrieval=load_retrieval(state.get("retrieval_path")),
        )
        research_ok = rok
    ledger = build_claim_ledger(
        slug=slug,
        texts=texts,
        r1_ok=state.get("gate_r1_ok"),
        r2_ok=state.get("gate_r2_ok"),
        claim_map_ok=state.get("gate_claim_ok"),
        research_ok=research_ok,
        validate_ok=state.get("gate_validate_ok"),
    )
    write_claim_ledger(dpaths["claim_ledger"], ledger)
    write_verification_md(
        dpaths["verification"],
        ledger,
        extra=f"final_candidate={final_path}\nrevise_count={state.get('revise_count')}",
    )

    path_map = {
        "plan_path": state.get("plan_path") or str(dpaths["plan"]),
        "retrieval_path": state.get("retrieval_path"),
        "research_path": state.get("research_path"),
        "schema_path": state.get("schema_path"),
        "solution_path": state.get("solution_path"),
        "validate_path": state.get("validate_path"),
        "explain_path": state.get("explain_path"),
        "draft_path": str(dpaths["draft"]) if dpaths["draft"].is_file() else "",
        "cited_path": str(dpaths["cited"]) if dpaths["cited"].is_file() else "",
        "revised_path": str(dpaths["revised"]) if dpaths["revised"].is_file() else "",
        "verification_path": str(dpaths["verification"]) if dpaths["verification"].is_file() else "",
        "claim_ledger_path": str(dpaths["claim_ledger"]) if dpaths["claim_ledger"].is_file() else "",
        "claim_map_path": str(dpaths["claim_map"]) if dpaths["claim_map"].is_file() else "",
        "final_candidate_path": final_path,
        "paper_path": str(dpaths["paper"]) if dpaths["paper"].is_file() else state.get("paper_path"),
        "review_path": state.get("review_path"),
        "tune_log_path": state.get("tune_log_path"),
        "annotations_path": str(root / "outputs" / ".drafts" / f"{slug}-annotations.json")
        if (root / "outputs" / ".drafts" / f"{slug}-annotations.json").is_file()
        else "",
        "provenance_path": "",  # filled after write
    }

    # P2 figure from solution
    figure_path = ""
    if state.get("solution_path") and Path(state["solution_path"]).is_file():
        try:
            sol = json.loads(Path(state["solution_path"]).read_text(encoding="utf-8"))
            fig = root / "outputs" / ".drafts" / f"{slug}-figure.html"
            write_solution_figure(fig, sol, slug=slug)
            figure_path = str(fig)
            path_map["figure_path"] = figure_path
        except Exception:
            pass

    verif = "PASS"
    if state.get("human_required"):
        verif = "BLOCKED"
    elif ledger.get("verificationState") == "failed":
        verif = "BLOCKED"
    elif not (
        state.get("gate_r1_ok")
        and state.get("gate_r2_ok")
        and state.get("gate_validate_ok")
        and state.get("gate_claim_ok", True)
    ):
        verif = "PASS WITH NOTES"
    elif ledger.get("verificationState") == "partial":
        verif = "PASS WITH NOTES"

    # P2 artifact versions (before research_run so path can be included)
    version_paths = [v for k, v in path_map.items() if v and k.endswith("_path")]
    if final_path:
        version_paths.append(final_path)
    vers = record_versions(
        root,
        slug=slug,
        paths=version_paths,
        stage="provenance",
        input_paths=[
            path_map.get("solution_path") or "",
            path_map.get("research_path") or "",
            path_map.get("schema_path") or "",
        ],
        source="orpath",
    )
    versions_path = root / "outputs" / ".artifacts" / f"{slug}-versions.json"
    path_map["versions_path"] = str(versions_path) if versions_path.is_file() else ""

    prov = root / "outputs" / f"{slug}.provenance.md"
    path_map["provenance_path"] = str(prov)

    # P2 research run manifest
    run = build_research_run(
        slug=slug,
        state=dict(state),
        paths={k: str(v) for k, v in path_map.items() if v},
        verification_state=str(ledger.get("verificationState") or "partial"),
        verification_summary=verif,
        claim_count=int(ledger.get("claimCount") or 0),
    )
    run_path = root / "outputs" / ".drafts" / f"{slug}-research-run.json"
    _, run_ok, run_errs = write_research_run(run_path, run)
    path_map["research_run_path"] = str(run_path)

    # P2 lab changelog
    lab = append_lab_changelog(
        root,
        slug=slug,
        title="paper pipeline provenance",
        bullets=[
            f"verification={verif}",
            f"vstate={ledger.get('verificationState')}",
            f"claims={ledger.get('claimCount')}",
            f"versions={vers.get('versionCount')}",
            f"research_run_ok={run_ok}",
            f"final={Path(final_path).name if final_path else 'n/a'}",
        ],
    )
    path_map["lab_changelog_path"] = str(lab)

    st = dict(state)
    st["verification_state"] = ledger.get("verificationState")
    st["final_candidate_path"] = final_path
    text = thick_provenance(
        slug=slug,
        state=st,
        paths={k: str(v) for k, v in path_map.items() if v},
        verification=verif,
        extra_lines=[
            f"- claimCount: {ledger.get('claimCount')}",
            f"- claim_summary: {ledger.get('summary')}",
            f"- artifact_versions: {vers.get('versionCount')} deps={vers.get('dependencyCount')}",
            f"- research_run_valid: {run_ok}" + (f" errors={run_errs}" if not run_ok else ""),
            f"- paper_protocol: P0+P1+P2+P3",
        ],
    )
    paper_prov = root / "papers" / f"{slug}.provenance.md"
    prov.write_text(text, encoding="utf-8")
    try:
        paper_prov.write_text(text, encoding="utf-8")
    except OSError:
        pass
    # re-record provenance file version
    record_versions(
        root,
        slug=slug,
        paths=[prov, run_path, versions_path],
        stage="provenance_finalize",
        input_paths=[path_map.get("paper_path") or "", path_map.get("solution_path") or ""],
        source="orpath",
    )
    append_plan_log(
        root,
        slug,
        stage="provenance",
        status=verif,
        detail=(
            f"final={Path(final_path).name if final_path else 'n/a'} "
            f"vstate={ledger.get('verificationState')} "
            f"run_ok={run_ok} vers={vers.get('versionCount')}"
        ),
        plan_file=state.get("plan_path"),
    )
    return {
        "stage": "end",
        "provenance_path": str(prov),
        "paper_path": str(dpaths["paper"]) if dpaths["paper"].is_file() else state.get("paper_path"),
        "verification_state": ledger.get("verificationState"),
        "final_candidate_path": final_path,
        "research_run_path": str(run_path),
        "versions_path": str(versions_path) if versions_path.is_file() else "",
    }


# ---------------------------------------------------------------------------
# Product graph facade (merged from nodes_product — ADR-0001 closeout)
# Core bodies above stay callable as _core_*; public node_* are wrapped.
# ---------------------------------------------------------------------------
from typing import Any  # noqa: E402

from orpath.node_context import wrap_node  # noqa: E402
from orpath.pi_bridge import bridge_smoke, maybe_annotate_live  # noqa: E402
from orpath.intake_nodes import (  # noqa: E402
    run_intake_ocr_stage,
    run_intake_parse_stage,
)

_core_orchestrate = node_orchestrate
_core_retrieve = node_retrieve
_core_research = node_research
_core_model = node_model
_core_gate_schema = node_gate_schema
_core_solve = node_solve
_core_gate_validate = node_gate_validate
_core_human_stop = node_human_stop
_core_explain = node_explain
_core_draft_paper = node_draft_paper
_core_cite_pack = node_cite_pack
_core_review_pack = node_review_pack
_core_revise_or_done = node_revise_or_done
_core_provenance = node_provenance


def node_bridge_pi(state: ORPathState) -> dict[str, Any]:
    """In-graph Pi bridge. Hard-fail when live_pi and bridge fails."""
    root = Path(state["root"])
    slug = state["slug"]
    live = bool(state.get("live_pi"))
    if not live:
        return {
            "stage": "research"
            if (state.get("bridge_attachment") or "before_research") == "before_research"
            else "retrieve",
            "bridge_skipped": True,
            "bridge_ok": True,
            "bridge_path": "",
            "last_error": "",
        }

    try:
        info = bridge_smoke(root, slug)
        maybe_annotate_live(root, slug)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"bridge_pi hard fail: {exc}") from exc

    if not info.get("ok", True) and info.get("ok") is False:
        raise RuntimeError(f"bridge_pi hard fail: {info}")

    out_path = root / "outputs" / f"{slug}-bridge.json"
    out_path.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    att = state.get("bridge_attachment") or "before_research"
    next_stage = "research" if att == "before_research" else "retrieve"
    return {
        "stage": next_stage,
        "bridge_skipped": False,
        "bridge_ok": True,
        "bridge_path": str(out_path),
        "last_error": "",
    }


def _after_orchestrate_stage(state: ORPathState) -> dict[str, Any]:
    out = _core_orchestrate(state)
    att = state.get("bridge_attachment") or "before_research"
    if att == "before_retrieve":
        out = {**out, "stage": "bridge_pi"}
    return out


def _after_retrieve_stage(state: ORPathState) -> dict[str, Any]:
    out = _core_retrieve(state)
    att = state.get("bridge_attachment") or "before_research"
    if att == "before_research":
        out = {**out, "stage": "bridge_pi"}
    else:
        out = {**out, "stage": "research"}
    return out


def _provenance_thick(state: ORPathState) -> dict[str, Any]:
    out = _core_provenance(state)
    prov = Path(out["provenance_path"])
    extra = [
        "",
        "## T3 skeleton",
        f"- thread_id: {state.get('thread_id')}",
        f"- bridge_attachment: {state.get('bridge_attachment')}",
        f"- bridge_path: {state.get('bridge_path')}",
        f"- bridge_ok: {state.get('bridge_ok')}",
        f"- bridge_skipped: {state.get('bridge_skipped')}",
        f"- runs_dir: {state.get('runs_dir')}",
        f"- artifact_manifest_path: {state.get('artifact_manifest_path')}",
        f"- last_snapshot_path: {state.get('last_snapshot_path')}",
        f"- orpath_checkpoint_id: {state.get('orpath_checkpoint_id')}",
        f"- pipeline: product",
    ]
    with prov.open("a", encoding="utf-8") as f:
        f.write("\n".join(extra) + "\n")
    return out


# Public names for product graph (NodeContext snapshot + owner)
node_intake_ocr = wrap_node("intake_ocr", run_intake_ocr_stage)
node_intake_parse = wrap_node("intake_parse", run_intake_parse_stage)
node_orchestrate = wrap_node("orchestrate", _after_orchestrate_stage)
node_retrieve = wrap_node("retrieve", _after_retrieve_stage)
node_bridge = wrap_node("bridge_pi", node_bridge_pi)
node_research = wrap_node("research", _core_research)
node_model = wrap_node("model", _core_model)
node_gate_schema = wrap_node("gate_schema", _core_gate_schema)
node_solve = wrap_node("solve", _core_solve)
node_gate_validate = wrap_node("gate_validate", _core_gate_validate)
node_human_stop = wrap_node("human_stop", _core_human_stop)
node_explain = wrap_node("explain", _core_explain)
node_draft_paper = wrap_node("draft_paper", _core_draft_paper)
node_cite_pack = wrap_node("cite_pack", _core_cite_pack)
node_review_pack = wrap_node("review_pack", _core_review_pack)
node_revise_or_done = wrap_node("revise_or_done", _core_revise_or_done)
node_provenance = wrap_node("provenance", _provenance_thick)
