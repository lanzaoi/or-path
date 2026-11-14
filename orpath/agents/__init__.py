"""OR-Path agent-facing tool surface (LangChain ``@tool`` wrappers).

Re-exports the lean 4-agent + deterministic gate + DomainCartridge layers:

  * ``workers``    — the four permanent elite specialist factories (analyst /
    modeler / writer / reviewer) with ``create_*_agent`` factories accepting
    per-call ``cartridge_tools`` / ``domain_directive`` injections.
  * ``deterministic_nodes`` — LLM-free preflight probe and hard validation
    nodes.
  * ``adaptive_graph``     — Tier-A/B/C deterministic routing state machine
    over the four elite workers (dual-track horse-racing & anti-cosplay).
  * ``cartridges``         — 10 pluggable ``DomainCartridge`` packs + ``general_or``.
  * ``callbacks``          — Live Watch event snapshots & per-stage JSONL logs.
"""
from __future__ import annotations

from orpath.agents.core_state import (
    MAX_CORE_STATE_BYTES,
    CorePipelineState,
    make_initial_core_state,
    sanitize_core_state,
    serialized_state_size_bytes,
)
from orpath.agents.cartridges import (
    CARTRIDGES,
    CLASS_TO_DOMAIN,
    GENERAL_OR_DOMAIN,
    TIER_FORCE_BY_RAW,
    DomainCartridge,
    cartridge_skills,
    cartridge_tier,
    cartridge_tools,
    cartridges,
    resolve_cartridge,
)
from orpath.agents.dimo_mutator import (
    DIMOMutator,
    DOMAIN_ATTACK_MAPPINGS,
    MutationResult,
    MutationType,
    SUPPORTED_DOMAINS,
    apply_mutation,
    generate_attack_suite,
    stable_hash,
)
from orpath.agents.optimality_claim_auditor import (
    ClaimAuditResult,
    ClaimSeverity,
    OptimalityClaim,
    OptimalityClaimAuditor,
    UnprovenOptimalityClaimError,
    assert_no_unproven_claims,
    audit_report_text,
    audit_text,
)
from orpath.agents.callbacks import (
    get_default_supervisor_checkpointer,
    persist_agent_stage_log,
)
from orpath.agents.workers import (
    ACADEMIC_WORKER_NAMES,
    ANALYST_NAME,
    MODELER_NAME,
    READ_PROBLEM_FILE_MAX_CHARS,
    REVIEWER_NAME,
    VERIFIER_NAME,
    WORKER_AGENT_NAMES,
    WRITER_NAME,
    append_domain_directive,
    create_analyst_agent,
    create_modeler_agent,
    create_reviewer_agent,
    create_verifier_agent,
    create_writer_agent,
    export_paper_markdown,
    get_academic_workers,
    get_default_workers,
    read_problem_file,
    search_or_knowledge,
)
from orpath.agents.deterministic_nodes import (
    collect_input_files,
    domain_tool_registry,
    file_overview,
    file_sha256,
    guess_domain,
    guess_problem_class,
    run_deterministic_validator,
    run_preflight_probe,
    validate_artifact,
)
from orpath.agents.adaptive_graph import (
    ADAPTIVE_NODES,
    ISOLATED_PIPELINE_NODES,
    AdaptivePipelineState,
    AdaptiveORState,
    MultiAgentPipelineState,
    TIER_A_CLASSES,
    adaptive_stage_map,
    build_adaptive_graph,
    build_compiled_adaptive_graph,
    build_compiled_isolated_pipeline,
    build_isolated_pipeline_graph,
    decide_tier,
    parse_review_reply,
    render_truth_tables,
    run_deterministic_doc_gate,
)

__all__ = [
    # core pipeline state contract
    "CorePipelineState",
    "make_initial_core_state",
    "sanitize_core_state",
    "serialized_state_size_bytes",
    "MAX_CORE_STATE_BYTES",
    # cartridges
    "DomainCartridge",
    "CARTRIDGES",
    "CLASS_TO_DOMAIN",
    "TIER_FORCE_BY_RAW",
    "GENERAL_OR_DOMAIN",
    "resolve_cartridge",
    "cartridge_tools",
    "cartridge_tier",
    "cartridge_skills",
    "cartridges",
    # isolated multi-agent pipeline
    "ISOLATED_PIPELINE_NODES",
    "MultiAgentPipelineState",
    "build_compiled_isolated_pipeline",
    "build_isolated_pipeline_graph",
    "get_default_supervisor_checkpointer",
    "persist_agent_stage_log",
    # workers
    "MODELER_NAME",
    "READ_PROBLEM_FILE_MAX_CHARS",
    "ANALYST_NAME",
    "VERIFIER_NAME",
    "WRITER_NAME",
    "REVIEWER_NAME",
    "WORKER_AGENT_NAMES",
    "ACADEMIC_WORKER_NAMES",
    "create_analyst_agent",
    "create_modeler_agent",
    "create_verifier_agent",
    "create_writer_agent",
    "create_reviewer_agent",
    "append_domain_directive",
    "export_paper_markdown",
    "get_default_workers",
    "get_academic_workers",
    "read_problem_file",
    "search_or_knowledge",
    # deterministic gates + adaptive tier machine
    "run_preflight_probe",
    "run_deterministic_validator",
    "validate_artifact",
    "file_overview",
    "file_sha256",
    "collect_input_files",
    "guess_domain",
    "guess_problem_class",
    "domain_tool_registry",
    "ADAPTIVE_NODES",
    "AdaptivePipelineState",
    "AdaptiveORState",
    "TIER_A_CLASSES",
    "adaptive_stage_map",
    "build_adaptive_graph",
    "build_compiled_adaptive_graph",
    "decide_tier",
    "parse_review_reply",
    "render_truth_tables",
    "run_deterministic_doc_gate",
    # DIMO mutator
    "DIMOMutator",
    "MutationResult",
    "MutationType",
    "apply_mutation",
    "generate_attack_suite",
    "stable_hash",
    "DOMAIN_ATTACK_MAPPINGS",
    "SUPPORTED_DOMAINS",
    # Optimality Claim Auditor
    "ClaimAuditResult",
    "ClaimSeverity",
    "OptimalityClaim",
    "OptimalityClaimAuditor",
    "UnprovenOptimalityClaimError",
    "assert_no_unproven_claims",
    "audit_report_text",
    "audit_text",
]
