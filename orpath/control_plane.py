"""OR-Path ControlPlane — single entry for graph build + invoke (ADR-0003).

Interface (what callers learn):
  - build_graph(checkpointer=None)  → compiled product LangGraph
  - default_initial(...)            → ORPathState seed dict
  - invoke_once(...)                → one-shot run (no checkpointer; T1/CI)
  - PRODUCT_NODES / stage map helpers (re-export)

Topology lives in graph_product.py; checkpointed CLI stays run_orpath.py.
Legacy shims: graph.py, graph_t2.py, run_t1.py, run_t2.py.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from orpath.graph_product import (  # re-export seam
    PRODUCT_NODES,
    build_graph_product,
    export_stage_map,
    open_sqlite_checkpointer,
    write_stage_map_files,
)

# Canonical stage predecessors for --from-stage (product graph)
PREDECESSORS: dict[str, str] = {
    "retrieve": "orchestrate",
    "bridge_pi": "retrieve",
    "research": "bridge_pi",
    "model": "research",
    "gate_schema": "model",
    "solve": "gate_schema",
    "gate_validate": "solve",
    "explain": "gate_validate",
    "draft_paper": "explain",
    "cite_pack": "draft_paper",
    "review_pack": "cite_pack",
    "revise_or_done": "review_pack",
    "provenance": "revise_or_done",
}


def build_graph(checkpointer: Any | None = None) -> Any:
    """Build the **only** product pipeline graph."""
    return build_graph_product(checkpointer=checkpointer)


# Back-compat names used across gates/docs
build_graph_product_cp = build_graph  # alias


def db_path(root: Path) -> Path:
    return Path(root) / "runs" / "orpath.sqlite"


def thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def default_initial(
    *,
    root: Path,
    slug: str,
    problem_id: str,
    problem_class: str = "",
    solve_mode: str = "mock",
    knowledge_mode: str = "seed",
    live_pi: bool = False,
    live_subagent: bool | None = None,
    thread_id: str,
    bridge_attachment: str = "before_research",
) -> dict[str, Any]:
    """Canonical ORPathState seed for product runs."""
    root = Path(root)
    return {
        "slug": slug,
        "problem_id": problem_id,
        "problem_class": problem_class,
        "solve_mode": solve_mode,
        "knowledge_mode": knowledge_mode,
        "root": str(root),
        "stage": "start",
        "revise_count": 0,
        "max_revise": 2,
        "schema_repair": 0,
        "max_schema_repair": 2,
        "validate_repair": 0,
        "max_validate_repair": 2,
        "solver_tune": 0,
        "max_solver_tune": 3,
        "human_required": False,
        "schema_path": "",
        "solution_path": "",
        "validate_path": "",
        "research_path": "",
        "retrieval_path": "",
        "explain_path": "",
        "paper_path": "",
        "review_path": "",
        "provenance_path": "",
        "plan_path": "",
        "cited_path": "",
        "last_error": "",
        "gate_schema_ok": False,
        "gate_validate_ok": False,
        "gate_r1_ok": False,
        "gate_r2_ok": False,
        "gate_claim_ok": True,
        "gate_subagent_ok": None,
        "review_fatal": 0,
        "live_pi": bool(live_pi),
        "live_subagent": live_subagent,
        "thread_id": thread_id,
        "bridge_attachment": bridge_attachment,
        "bridge_path": "",
        "bridge_ok": False,
        "bridge_skipped": True,
        "orpath_checkpoint_id": "",
        "runs_dir": str(root / "runs" / thread_id),
        "artifact_manifest_path": "",
        "last_snapshot_path": "",
        "pipeline": "product",
    }


def summarize_run(final: dict[str, Any], *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compact JSON summary for CLIs / gates."""
    out = {
        "stage": final.get("stage"),
        "human_required": final.get("human_required"),
        "revise_count": final.get("revise_count"),
        "gate_r1_ok": final.get("gate_r1_ok"),
        "gate_r2_ok": final.get("gate_r2_ok"),
        "gate_validate_ok": final.get("gate_validate_ok"),
        "gate_subagent_ok": final.get("gate_subagent_ok"),
        "solution_path": final.get("solution_path"),
        "paper_path": final.get("paper_path"),
        "provenance_path": final.get("provenance_path"),
        "last_error": final.get("last_error"),
        "pipeline": final.get("pipeline") or "product",
        "thread_id": final.get("thread_id"),
    }
    if extra:
        out.update(extra)
    return out


def invoke_once(
    *,
    root: Path,
    slug: str,
    problem_id: str,
    problem_class: str = "",
    solve_mode: str = "mock",
    knowledge_mode: str = "off",
    live_pi: bool = False,
    live_subagent: bool | None = False,
    thread_id: str | None = None,
    bridge_attachment: str = "before_research",
) -> dict[str, Any]:
    """One-shot product run without Sqlite checkpointer (T1 / ad-hoc CI)."""
    root = Path(root).resolve()
    tid = thread_id or f"{slug}-{uuid.uuid4().hex[:8]}"
    initial = default_initial(
        root=root,
        slug=slug,
        problem_id=problem_id,
        problem_class=problem_class,
        solve_mode=solve_mode,
        knowledge_mode=knowledge_mode,
        live_pi=live_pi,
        live_subagent=live_subagent,
        thread_id=tid,
        bridge_attachment=bridge_attachment,
    )
    app = build_graph(checkpointer=None)
    return app.invoke(initial)


__all__ = [
    "PREDECESSORS",
    "PRODUCT_NODES",
    "build_graph",
    "build_graph_product",
    "db_path",
    "default_initial",
    "export_stage_map",
    "invoke_once",
    "open_sqlite_checkpointer",
    "summarize_run",
    "thread_config",
    "write_stage_map_files",
]
