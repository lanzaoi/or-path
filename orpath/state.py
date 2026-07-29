from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class ORPathState(TypedDict):
    slug: str
    problem_id: str
    solve_mode: Literal["mock", "ortools"]
    root: str
    stage: str
    revise_count: int
    max_revise: int
    human_required: bool
    schema_path: str
    solution_path: str
    research_path: str
    explain_path: str
    paper_path: str
    review_path: str
    provenance_path: str
    plan_path: str
    cited_path: str
    last_error: str
    gate_schema_ok: bool
    gate_r1_ok: bool
    gate_r2_ok: bool
    review_fatal: int
    artifacts: NotRequired[list[str]]
