"""OR-Path shared run state (T1/T2/T3 product)."""
from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class ORPathState(TypedDict):
    slug: str  # NOTE: slug is NotRequired in practice; declared via default init
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
    profile_path: NotRequired[str]          # Phase 3.1 deterministic probe artifact
    domain_cartridge: NotRequired[str]      # Phase 3.1 selected cartridge key
    cartridge_domain: NotRequired[str]      # alias kept for downstream
    complexity_tier: NotRequired[Literal["A", "B", "C"]]
    gap_path: NotRequired[str]              # Phase 3.2 Tier-B lower-bound gap record
    lessons_path: NotRequired[str]
    lesson_draft_path: NotRequired[str]
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
    # P0 paper / T3 product / M2 subagent
    gate_claim_ok: NotRequired[bool]
    gate_subagent_ok: NotRequired[bool | None]
    live_subagent: NotRequired[bool]
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
    # 1.1 intake (optional front-door; default skip)
    skip_intake: NotRequired[bool]
    intake_skipped: NotRequired[bool]
    intake_sources: NotRequired[list[str]]
    intake_assets_dir: NotRequired[str]
    ocr_raw_path: NotRequired[str]
    ocr_meta_path: NotRequired[str]
    intake_path: NotRequired[str]
    brief_path: NotRequired[str]
    gate_intake_ok: NotRequired[bool]
    human_confirm_intake: NotRequired[bool]
    intake_confirmed: NotRequired[bool]
    workdir: NotRequired[str]
    # D2 human-steer (Watch dialogue → LG/Pi)
    human_steer_path: NotRequired[str]
    human_steer_applied: NotRequired[bool]
    human_steer_lg: NotRequired[dict[str, Any]]
    human_steer_pi: NotRequired[dict[str, Any]]
    human_steer_at_stage: NotRequired[str]
    human_steer_utc: NotRequired[str]
    human_steer_fresh: NotRequired[bool]
    steer_pause: NotRequired[bool]


# Nodes allowed to create/overwrite solution.json content (numbers truth).
SOLVE_NODES = frozenset({"solve"})

# Keys non-solve nodes must never put into state updates.
FORBIDDEN_NUMERIC_KEYS = frozenset(
    {"objective", "path", "tour", "routes", "optimal", "objective_value"}
)

# Path fields tracked in artifact manifest for dirty detection.
MANIFEST_PATH_KEYS = (
    "plan_path",
    "profile_path",
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
    "ocr_raw_path",
    "ocr_meta_path",
    "intake_path",
    "brief_path",
)


def make_initial_orpath_state() -> ORPathState:
    """Default checkpoint-safe initial state (SqliteSaver / MemorySaver JSON).

    Carries only scalar defaults + pointer fields; no raw problem text or
    solution payloads (Feynman file-handoff principle, Plan 1.2).
    """
    return ORPathState(
        slug="",
        problem_id="",
        problem_class="",
        solve_mode="mock",
        knowledge_mode="off",
        root="",
        stage="start",
        revise_count=0,
        max_revise=3,
        schema_repair=0,
        max_schema_repair=2,
        validate_repair=0,
        max_validate_repair=2,
        solver_tune=0,
        max_solver_tune=2,
        human_required=False,
        schema_path="",
        solution_path="",
        validate_path="",
        research_path="",
        retrieval_path="",
        explain_path="",
        paper_path="",
        review_path="",
        provenance_path="",
        plan_path="",
        last_error="",
        gate_schema_ok=False,
        gate_validate_ok=False,
        gate_r1_ok=False,
        gate_r2_ok=False,
        review_fatal=0,
        live_pi=False,
        live_subagent=False,
        domain_cartridge="",
        complexity_tier="",  # type: ignore[literal-required]
        profile_path="",
        workdir="",
    )


def orpath_state_to_core(state: dict[str, Any]) -> "CorePipelineState":
    """Project ``ORPathState`` onto the pointer-only ``CorePipelineState``.

    Large/foreign payload keys are dropped via ``sanitize_core_state`` so the
    result is always <= ``MAX_CORE_STATE_BYTES`` and JSON-safe.
    """
    from orpath.agents.core_state import sanitize_core_state  # lazy: no cycles

    mapping = {
        "slug": state.get("slug", ""),
        "workdir": state.get("workdir", state.get("root", "")),
        "problem_id": state.get("problem_id", ""),
        "problem_class": state.get("problem_class", ""),
        "domain_cartridge": state.get("domain_cartridge", ""),
        "complexity_tier": state.get("complexity_tier", ""),
        "problem_file": state.get("intake_path", "") or state.get("problem_file", ""),
        "data_files": [p for p in (state.get("intake_sources") or []) if isinstance(p, str)],
        "profile_path": state.get("profile_path", ""),
        "research_path": state.get("research_path", ""),
        "schema_path": state.get("schema_path", ""),
        "solution_path": state.get("solution_path", ""),
        "validate_path": state.get("validate_path", ""),
        "paper_path": state.get("paper_path", ""),
        "review_path": state.get("review_path", ""),
        "validation_ok": bool(state.get("gate_validate_ok", False)),
        "proven_optimal": bool(state.get("gate_claim_ok", False)),
        "max_retries": int(state.get("max_revise", 3)),
        "last_error": state.get("last_error", ""),
    }
    return sanitize_core_state(mapping)


def core_state_to_orpath(core: "CorePipelineState") -> dict[str, Any]:
    """Inject a ``CorePipelineState`` projection back into an ORPathState patch."""
    patch: dict[str, Any] = {
        "slug": core.get("slug", ""),
        "workdir": core.get("workdir", ""),
        "problem_id": core.get("problem_id", ""),
        "problem_class": core.get("problem_class", ""),
        "domain_cartridge": core.get("domain_cartridge", ""),
        "complexity_tier": core.get("complexity_tier", ""),
        "profile_path": core.get("profile_path", ""),
        "schema_path": core.get("schema_path", ""),
        "solution_path": core.get("solution_path", ""),
        "validate_path": core.get("validate_path", ""),
        "research_path": core.get("research_path", ""),
        "paper_path": core.get("paper_path", ""),
        "review_path": core.get("review_path", ""),
        "last_error": core.get("last_error", ""),
    }
    if core.get("validation_ok"):
        patch["gate_validate_ok"] = True
    if core.get("proven_optimal"):
        patch["gate_claim_ok"] = True
    return patch
