"""PaperProtocol — single product interface for the paper loop (ADR-0004).

Interface (what callers learn):
  run_from_solution(...)  — post-solve full protocol (no re-solve)
  draft_paths / render helpers re-exported for thin CLIs
  IN_GRAPH_STAGES         — LG node names that implement the same loop

Implementation helpers stay in paper_workflow / claim_ledger / revise_proof.
Live cite/review adapters: orpath.subagent_dispatch (ADR-0005); impl paper_live_subagent.
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
from orpath.paper_workflow import (  # re-export seam for CLIs
    append_plan_log,
    build_review_markdown,
    draft_paths,
    gate_research_text,
    load_retrieval,
    render_or_paper,
)
from orpath.revise_proof import write_revise_proof

PIPELINE = "paper_protocol"
# Same stage names as product graph paper half
IN_GRAPH_STAGES = (
    "draft_paper",
    "cite_pack",
    "review_pack",
    "revise_or_done",
    "provenance",
)


def _live_subagent_flag() -> bool | None:
    raw = (os.environ.get("ORPATH_LIVE_SUBAGENT") or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return None


def base_state(
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
    """Canonical state seed for post-solve paper runs."""
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
        "live_subagent": _live_subagent_flag(),
        "gate_subagent_ok": None,
        "pipeline": PIPELINE,
    }


def _merge(state: dict[str, Any], upd: dict[str, Any]) -> dict[str, Any]:
    out = dict(state)
    out.update({k: v for k, v in upd.items() if v is not None})
    return out


def summarize_paper_result(result: dict[str, Any]) -> dict[str, Any]:
    """Compact view for CLIs / gates."""
    st = result.get("state") or {}
    man = result.get("manifest") or {}
    return {
        "pipeline": man.get("pipeline") or st.get("pipeline") or PIPELINE,
        "slug": man.get("slug") or st.get("slug"),
        "manifest_path": result.get("manifest_path"),
        "gates": man.get("gates")
        or {
            "r1": st.get("gate_r1_ok"),
            "r2": st.get("gate_r2_ok"),
            "claim": st.get("gate_claim_ok"),
            "subagent": st.get("gate_subagent_ok"),
            "review_fatal": st.get("review_fatal"),
            "human_required": st.get("human_required"),
        },
        "paper_path": st.get("paper_path"),
        "provenance_path": st.get("provenance_path"),
        "stage": st.get("stage"),
    }


def run_from_solution(
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
    """Execute draft→cite→review→revise*→provenance from an existing solution.json.

    Does **not** re-solve. Numbers must already be in solution_path (solve_dispatch).
    Returns {state, manifest, manifest_path}.
    """
    root = root.resolve()
    solution_path = solution_path.resolve()
    if not solution_path.is_file():
        raise FileNotFoundError(solution_path)

    state = base_state(
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
        stage="paper_protocol",
        status="start",
        detail=f"solution={solution_path.name}",
        plan_file=state["plan_path"],
    )

    state = _merge(state, node_draft_paper(state))  # type: ignore[arg-type]

    if inject_bad_claim:
        paper = Path(state["paper_path"])
        body = paper.read_text(encoding="utf-8")
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

    state = _merge(state, node_cite_pack(state))  # type: ignore[arg-type]
    state = _merge(state, node_review_pack(state))  # type: ignore[arg-type]

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
        if state.get("stage") in ("provenance", "human_stop"):
            break
        if state.get("stage") not in ("provenance", "human_stop"):
            state["stage"] = "cite_pack"
            state = _merge(state, node_cite_pack(state))  # type: ignore[arg-type]
            state = _merge(state, node_review_pack(state))  # type: ignore[arg-type]

    dpaths = draft_paths(root, slug)
    if not dpaths["revise_proof"].is_file():
        paper_txt = (
            Path(state["paper_path"]).read_text(encoding="utf-8")
            if Path(state["paper_path"]).is_file()
            else ""
        )
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
        "pipeline": PIPELINE,
        "in_graph_stages": list(IN_GRAPH_STAGES),
    }
    man_path = root / "outputs" / f"{slug}-paper-protocol.json"
    man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    append_plan_log(
        root,
        slug,
        stage="paper_protocol",
        status="done" if not state.get("human_required") else "human_required",
        detail=(
            f"r1={state.get('gate_r1_ok')} r2={state.get('gate_r2_ok')} "
            f"claim={state.get('gate_claim_ok')}"
        ),
        plan_file=state.get("plan_path"),
    )
    return {"state": state, "manifest": manifest, "manifest_path": str(man_path)}


# Back-compat alias used by older scripts/docs
run_post_solve_paper = run_from_solution

__all__ = [
    "IN_GRAPH_STAGES",
    "PIPELINE",
    "append_plan_log",
    "base_state",
    "build_review_markdown",
    "draft_paths",
    "gate_research_text",
    "load_retrieval",
    "render_or_paper",
    "run_from_solution",
    "run_post_solve_paper",
    "summarize_paper_result",
]
