"""Run P0–P3 paper protocol from an existing solution.json (no re-solve).

Used when solve already happened outside LG (e.g. contest scripts / Pi), so we
still get draft → cite → review → revise? → provenance + claim ledger.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from orpath.nodes import (
    node_cite_pack,
    node_draft_paper,
    node_provenance,
    node_review_pack,
    node_revise_or_done,
)
from orpath.paper_workflow import append_plan_log, draft_paths
from orpath.revise_proof import write_revise_proof
from orpath.state import ORPathState


def _base_state(
    *,
    root: Path,
    slug: str,
    problem_id: str,
    problem_class: str,
    solution_path: Path,
    research_path: Path | None = None,
    retrieval_path: Path | None = None,
    validate_path: Path | None = None,
    explain_path: Path | None = None,
    schema_path: Path | None = None,
    plan_path: Path | None = None,
    max_revise: int = 2,
) -> dict[str, Any]:
    paths = draft_paths(root, slug)
    return {
        "slug": slug,
        "problem_id": problem_id,
        "problem_class": problem_class,
        "solve_mode": "mock",
        "knowledge_mode": "seed" if research_path else "off",
        "root": str(root.resolve()),
        "stage": "draft_paper",
        "revise_count": 0,
        "max_revise": max_revise,
        "schema_repair": 0,
        "max_schema_repair": 2,
        "validate_repair": 0,
        "max_validate_repair": 3,
        "solver_tune": 0,
        "max_solver_tune": 3,
        "human_required": False,
        "schema_path": str(schema_path or ""),
        "solution_path": str(solution_path.resolve()),
        "validate_path": str(validate_path or ""),
        "research_path": str(research_path or ""),
        "retrieval_path": str(retrieval_path or ""),
        "explain_path": str(explain_path or ""),
        "paper_path": str(paths["paper"]),
        "review_path": str(paths["review"]),
        "provenance_path": str(paths["provenance"]),
        "plan_path": str(plan_path or paths["plan"]),
        "last_error": "",
        "gate_schema_ok": True,
        "gate_validate_ok": True,
        "gate_r1_ok": False,
        "gate_r2_ok": False,
        "gate_claim_ok": False,
        "review_fatal": 0,
        "live_pi": False,
        # None → defer to ORPATH_LIVE_SUBAGENT / check_env (M2/M3)
        "live_subagent": (
            True
            if (os.environ.get("ORPATH_LIVE_SUBAGENT") or "").strip().lower()
            in {"1", "true", "yes", "on"}
            else (
                False
                if (os.environ.get("ORPATH_LIVE_SUBAGENT") or "").strip().lower()
                in {"0", "false", "no", "off"}
                else None
            )
        ),
        "gate_subagent_ok": None,
        "pipeline": "post_solve_paper",
    }


def _merge(state: dict[str, Any], upd: dict[str, Any]) -> dict[str, Any]:
    out = dict(state)
    out.update({k: v for k, v in upd.items() if v is not None})
    return out


def run_post_solve_paper(
    *,
    root: Path,
    slug: str,
    problem_id: str,
    problem_class: str,
    solution_path: Path,
    research_path: Path | None = None,
    retrieval_path: Path | None = None,
    validate_path: Path | None = None,
    explain_path: Path | None = None,
    schema_path: Path | None = None,
    inject_bad_claim: bool = True,
    max_revise: int = 2,
) -> dict[str, Any]:
    """Execute draft→cite→review→revise*→provenance. Returns final state + paths."""
    root = root.resolve()
    solution_path = solution_path.resolve()
    if not solution_path.is_file():
        raise FileNotFoundError(solution_path)

    state = _base_state(
        root=root,
        slug=slug,
        problem_id=problem_id,
        problem_class=problem_class,
        solution_path=solution_path,
        research_path=research_path,
        retrieval_path=retrieval_path,
        validate_path=validate_path,
        explain_path=explain_path,
        schema_path=schema_path,
        max_revise=max_revise,
    )
    append_plan_log(
        root,
        slug,
        stage="post_solve_paper",
        status="start",
        detail=f"solution={solution_path.name}",
        plan_file=state["plan_path"],
    )

    # draft
    state = _merge(state, node_draft_paper(state))  # type: ignore[arg-type]

    # optional: inject a bad numeric claim so revise_proof has real disk evidence
    if inject_bad_claim:
        paper = Path(state["paper_path"])
        body = paper.read_text(encoding="utf-8")
        # stale Pi-era numbers that must not survive R2/claim
        poison = (
            "\n\n## Stale claim (must be revised away)\n"
            "objective = `20000` (wrong legacy number — inject for revise demo)\n"
        )
        paper.write_text(body + poison, encoding="utf-8")
        dpaths = draft_paths(root, slug)
        dpaths["draft"].write_text(paper.read_text(encoding="utf-8"), encoding="utf-8")
        append_plan_log(
            root,
            slug,
            stage="inject_bad_claim",
            status="done",
            detail="appended objective=20000 for revise loop demo",
            plan_file=state["plan_path"],
        )

    # cite
    state = _merge(state, node_cite_pack(state))  # type: ignore[arg-type]
    # review
    state = _merge(state, node_review_pack(state))  # type: ignore[arg-type]

    # revise loop until clean or exhausted
    for _ in range(max_revise + 1):
        if (
            state.get("gate_r1_ok")
            and state.get("gate_r2_ok")
            and state.get("gate_claim_ok", True)
            and int(state.get("review_fatal") or 0) == 0
        ):
            break
        if state.get("human_required"):
            break
        upd = node_revise_or_done(state)  # type: ignore[arg-type]
        state = _merge(state, upd)
        if state.get("stage") == "provenance":
            break
        if state.get("stage") == "human_stop":
            break
        # after revise, re-cite + re-review
        if state.get("stage") not in ("provenance", "human_stop"):
            # revise node may set stage to cite_pack or keep revise
            state["stage"] = "cite_pack"
            state = _merge(state, node_cite_pack(state))  # type: ignore[arg-type]
            state = _merge(state, node_review_pack(state))  # type: ignore[arg-type]

    # if still clean without revise file, write skip proof
    dpaths = draft_paths(root, slug)
    if not dpaths["revise_proof"].is_file():
        paper_txt = Path(state["paper_path"]).read_text(encoding="utf-8") if Path(state["paper_path"]).is_file() else ""
        write_revise_proof(
            dpaths["revise_proof"],
            slug=slug,
            before=paper_txt,
            after=paper_txt,
            removed_needles=[],
            r1_ok=bool(state.get("gate_r1_ok")),
            r2_ok=bool(state.get("gate_r2_ok")),
            claim_ok=bool(state.get("gate_claim_ok", True)),
            detail="no FATAL after cite/review; revise skipped",
        )

    # provenance
    state["stage"] = "provenance"
    state = _merge(state, node_provenance(state))  # type: ignore[arg-type]

    paths = draft_paths(root, slug)
    manifest = {
        "slug": slug,
        "problem_id": problem_id,
        "solution_path": str(solution_path),
        "gates": {
            "r1": state.get("gate_r1_ok"),
            "r2": state.get("gate_r2_ok"),
            "claim": state.get("gate_claim_ok"),
            "subagent": state.get("gate_subagent_ok"),
            "review_fatal": state.get("review_fatal"),
            "human_required": state.get("human_required"),
        },
        "artifacts": {k: str(v) for k, v in paths.items()},
        "stage": state.get("stage"),
        "pipeline": "post_solve_paper",
    }
    man_path = root / "outputs" / f"{slug}-paper-protocol.json"
    man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    append_plan_log(
        root,
        slug,
        stage="post_solve_paper",
        status="done" if not state.get("human_required") else "human_required",
        detail=f"r1={state.get('gate_r1_ok')} r2={state.get('gate_r2_ok')} claim={state.get('gate_claim_ok')}",
        plan_file=state.get("plan_path"),
    )
    return {"state": state, "manifest": manifest, "manifest_path": str(man_path)}
