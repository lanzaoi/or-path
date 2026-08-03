"""SubagentDispatch — single product interface for Pi subagent policy (ADR-0005).

What callers should import from **this module only**:

  live_subagent_enabled
  run_cite_subagent_lead / run_review_subagent_lead
  run_research_subagent_lead / run_model_subagent_lead
  run_forced_subagent_stage / LEAD_TOOLS_NO_WRITE / ANTI_COSPLAY_SYSTEM
  detect_subagent_calls / spawn_lead / check_env / FORCED_SUBAGENT_STAGES
  STAGE_AGENTS / stage_agent

Layered implementation (do not import these from product nodes unless debugging):
  subagent_runtime   — env, spawn, detect, briefs
  subagent_harness   — no-write lead + anti-cosplay retries
  paper_live_subagent — cite/review stage leads
  graph_live_subagent — research/model stage leads
"""
from __future__ import annotations

from typing import Any

# --- runtime (spawn / detect / env) ---
from orpath.subagent_runtime import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    FORCED_SUBAGENT_STAGES,
    LEAD_OWNED_STAGES,
    SUBAGENT_TOOL_NAME,
    EnvCheck,
    LeadResult,
    agents_dir,
    agent_logs_dir,
    api_key_present,
    build_lead_prompt,
    build_pi_command,
    check_env,
    detect_subagent_calls,
    find_pi_cli,
    find_pi_subagents_pkg,
    lead_result_to_json,
    list_project_agents,
    pi_session_enabled,
    pi_sessions_root,
    project_root,
    require_env,
    resolve_no_session,
    spawn_lead,
    stage_requires_subagent,
    sync_agents_to_user_dir,
    verify_outputs,
    write_lead_manifest,
    write_task_brief,
)

# --- harness (anti-cosplay) ---
from orpath.subagent_harness import (
    ANTI_COSPLAY_SYSTEM,
    LEAD_TOOLS_NO_WRITE,
    run_forced_subagent_stage,
)

# --- paper stages ---
from orpath.paper_live_subagent import (
    live_subagent_enabled,
    log_has_subagent,
    merge_review_if_child_wrote,
    run_cite_subagent_lead,
    run_review_subagent_lead,
)

# --- graph stages ---
from orpath.graph_live_subagent import (
    research_scale,
    run_model_subagent_lead,
    run_research_subagent_lead,
)

# Stage → required child agent (product policy table)
STAGE_AGENTS: dict[str, str] = {
    "research": "or-researcher",
    "model": "or-modeler",
    "cite": "or-verifier",
    "cite_pack": "or-verifier",
    "review": "or-reviewer",
    "review_pack": "or-reviewer",
}


def stage_agent(stage: str) -> str | None:
    """Return required or-* agent for a forced stage, if any."""
    return STAGE_AGENTS.get(stage) or STAGE_AGENTS.get(stage.replace("_pack", ""))


def policy_snapshot() -> dict[str, Any]:
    """Compact policy for docs/gates — one place to read harness law."""
    return {
        "forced_stages": sorted(FORCED_SUBAGENT_STAGES),
        "lead_owned_stages": sorted(LEAD_OWNED_STAGES),
        "stage_agents": dict(STAGE_AGENTS),
        "lead_tools": LEAD_TOOLS_NO_WRITE,
        "subagent_tool": SUBAGENT_TOOL_NAME,
        "default_model": DEFAULT_MODEL,
        "default_provider": DEFAULT_PROVIDER,
        "anti_cosplay": True,
        "pi_session_enabled": pi_session_enabled(),
        "pi_sessions_root": str(pi_sessions_root()),
        "default_no_session": resolve_no_session(None),
    }


__all__ = [
    "ANTI_COSPLAY_SYSTEM",
    "DEFAULT_MODEL",
    "DEFAULT_PROVIDER",
    "FORCED_SUBAGENT_STAGES",
    "LEAD_OWNED_STAGES",
    "LEAD_TOOLS_NO_WRITE",
    "STAGE_AGENTS",
    "SUBAGENT_TOOL_NAME",
    "EnvCheck",
    "LeadResult",
    "agent_logs_dir",
    "agents_dir",
    "api_key_present",
    "build_lead_prompt",
    "build_pi_command",
    "check_env",
    "detect_subagent_calls",
    "find_pi_cli",
    "find_pi_subagents_pkg",
    "lead_result_to_json",
    "list_project_agents",
    "live_subagent_enabled",
    "log_has_subagent",
    "merge_review_if_child_wrote",
    "pi_session_enabled",
    "pi_sessions_root",
    "policy_snapshot",
    "project_root",
    "require_env",
    "research_scale",
    "resolve_no_session",
    "run_cite_subagent_lead",
    "run_forced_subagent_stage",
    "run_model_subagent_lead",
    "run_research_subagent_lead",
    "run_review_subagent_lead",
    "spawn_lead",
    "stage_agent",
    "stage_requires_subagent",
    "sync_agents_to_user_dir",
    "verify_outputs",
    "write_lead_manifest",
    "write_task_brief",
]
