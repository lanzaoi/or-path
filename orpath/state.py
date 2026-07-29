"""OR-Path shared run state (T1/T2/T3 product)."""
from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class ORPathState(TypedDict):
    slug: str
    problem_id: str
    problem_class: str
    solve_mode: Literal["mock", "networkx", "ortools", "cpsat", "highs"]
    knowledge_mode: Literal["off", "seed", "hybrid"]
    root: str
    stage: str
    revise_count: int
    max_revise: int
    schema_repair: int
    max_schema_repair: int
    validate_repair: int
    max_validate_repair: int
    solver_tune: int
    max_solver_tune: int
    human_required: bool
    schema_path: str
    solution_path: str
    validate_path: str
    research_path: str
    retrieval_path: str
    explain_path: str
    paper_path: str
    review_path: str
    provenance_path: str
    plan_path: str
    last_error: str
    gate_schema_ok: bool
    gate_validate_ok: bool
    gate_r1_ok: bool
    gate_r2_ok: bool
    review_fatal: int
    live_pi: bool
    # P0 paper / T3 product
    gate_claim_ok: NotRequired[bool]
    cited_path: NotRequired[str]
    thread_id: NotRequired[str]
    bridge_attachment: NotRequired[Literal["before_research", "before_retrieve"]]
    bridge_path: NotRequired[str]
    bridge_ok: NotRequired[bool]
    bridge_skipped: NotRequired[bool]
    orpath_checkpoint_id: NotRequired[str]
    runs_dir: NotRequired[str]
    artifact_manifest_path: NotRequired[str]
    last_snapshot_path: NotRequired[str]
    pipeline: NotRequired[str]
    artifacts: NotRequired[list[str]]
    tune_log_path: NotRequired[str]


# Nodes allowed to create/overwrite solution.json content (numbers truth).
SOLVE_NODES = frozenset({"solve"})

# Keys non-solve nodes must never put into state updates.
FORBIDDEN_NUMERIC_KEYS = frozenset(
    {"objective", "path", "tour", "routes", "optimal", "objective_value"}
)

# Path fields tracked in artifact manifest for dirty detection.
MANIFEST_PATH_KEYS = (
    "plan_path",
    "retrieval_path",
    "research_path",
    "schema_path",
    "solution_path",
    "validate_path",
    "explain_path",
    "paper_path",
    "review_path",
    "provenance_path",
    "bridge_path",
    "tune_log_path",
    "cited_path",
)
