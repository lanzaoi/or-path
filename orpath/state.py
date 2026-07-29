from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class ORPathState(TypedDict):
    slug: str
    problem_id: str
    problem_class: str
    solve_mode: Literal["mock", "networkx", "ortools"]
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
    cited_path: str
    last_error: str
    gate_schema_ok: bool
    gate_validate_ok: bool
    gate_r1_ok: bool
    gate_r2_ok: bool
    review_fatal: int
    live_pi: bool
    artifacts: NotRequired[list[str]]
    tune_log_path: NotRequired[str]
