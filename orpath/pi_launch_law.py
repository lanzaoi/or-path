"""Pi launch hard law — bare `pi -p` must never claim multi-agent.

Two legal modes only:

1. SINGLE_LEAD — one Pi session may use write/bash; banner required.
   OK for: tube re-solve scripts, draft-only, Hermes-monitored script runs.
2. MULTI_AGENT_HARNESS — must go through orpath.subagent_harness /
   subagent_runtime.spawn_lead with LEAD_TOOLS_NO_WRITE + --mode json
   + subagent toolCall detection.

Illegal: env ORPATH_LIVE_SUBAGENT=1 + bare pi -p + prompt saying "orchestrator".
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Sequence

from orpath.subagent_harness import ANTI_COSPLAY_SYSTEM, LEAD_TOOLS_NO_WRITE
from orpath.subagent_runtime import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    build_pi_command,
)


class LaunchMode(str, Enum):
    SINGLE_LEAD = "SINGLE_LEAD"
    MULTI_AGENT_HARNESS = "MULTI_AGENT_HARNESS"


# Tools allowed on single-lead solve / draft (explicit, not "everything")
SINGLE_LEAD_TOOLS = "read,bash,edit,write,grep,find,ls"


@dataclass(frozen=True)
class LaunchVerdict:
    ok: bool
    mode: LaunchMode
    reason: str
    cmd: list[str] | None = None


def _cmd_has_flag(cmd: Sequence[str], flag: str) -> bool:
    return flag in cmd


def _tools_arg(cmd: Sequence[str]) -> str | None:
    for i, tok in enumerate(cmd):
        if tok in {"--tools", "-t"} and i + 1 < len(cmd):
            return cmd[i + 1]
        if tok.startswith("--tools="):
            return tok.split("=", 1)[1]
    return None


def is_harness_shaped_cmd(cmd: Sequence[str]) -> bool:
    """True iff command matches anti-cosplay harness shape."""
    tools = _tools_arg(cmd) or ""
    has_subagent = "subagent" in tools.split(",")
    no_write = "write" not in tools.split(",") and "edit" not in tools.split(",")
    json_mode = _cmd_has_flag(cmd, "--mode") and any(
        cmd[i + 1] == "json"
        for i, t in enumerate(cmd)
        if t == "--mode" and i + 1 < len(cmd)
    )
    # also accept --mode json as adjacent
    if not json_mode:
        joined = " ".join(cmd)
        json_mode = "--mode json" in joined or "--mode=json" in joined
    return bool(has_subagent and no_write and json_mode)


def classify_claimed_mode(
    *,
    claim_multi_agent: bool,
    cmd: Sequence[str] | None = None,
) -> LaunchMode:
    if claim_multi_agent:
        return LaunchMode.MULTI_AGENT_HARNESS
    if cmd is not None and is_harness_shaped_cmd(cmd):
        return LaunchMode.MULTI_AGENT_HARNESS
    return LaunchMode.SINGLE_LEAD


def validate_launch(
    cmd: Sequence[str],
    *,
    claim_multi_agent: bool,
    label: str = "pi-launch",
) -> LaunchVerdict:
    """Refuse fake multi-agent (LIVE env or claim without harness shape)."""
    live_env = (os.environ.get("ORPATH_LIVE_SUBAGENT") or "").strip().lower()
    live_on = live_env in {"1", "true", "yes", "on"} or live_env == ""
    # empty default is "on if check_env" in product — for launchers treat 1/true as on
    live_on = live_env in {"1", "true", "yes", "on"}

    mode = classify_claimed_mode(claim_multi_agent=claim_multi_agent, cmd=cmd)
    harness = is_harness_shaped_cmd(cmd)

    if claim_multi_agent and not harness:
        return LaunchVerdict(
            ok=False,
            mode=LaunchMode.MULTI_AGENT_HARNESS,
            reason=(
                f"[{label}] ILLEGAL: claim_multi_agent=True but cmd is not harness-shaped "
                f"(need --tools with subagent, NO write/edit, --mode json). "
                f"Use orpath.subagent_harness / spawn_lead — not bare pi -p."
            ),
            cmd=list(cmd),
        )

    # Soft-hard: LIVE=1 + bare cmd without explicit SINGLE_LEAD opt-out
    require_honest = (os.environ.get("ORPATH_PI_LAUNCH_HONEST") or "1").strip() not in {
        "0",
        "false",
        "off",
    }
    if require_honest and live_on and not harness and claim_multi_agent:
        return LaunchVerdict(
            ok=False,
            mode=LaunchMode.SINGLE_LEAD,
            reason=f"[{label}] LIVE_SUBAGENT=1 cannot pair with bare multi-agent claim",
            cmd=list(cmd),
        )

    if not claim_multi_agent:
        return LaunchVerdict(
            ok=True,
            mode=LaunchMode.SINGLE_LEAD,
            reason=f"[{label}] SINGLE_LEAD OK (not claiming multi-agent)",
            cmd=list(cmd),
        )

    return LaunchVerdict(
        ok=True,
        mode=LaunchMode.MULTI_AGENT_HARNESS,
        reason=f"[{label}] MULTI_AGENT harness-shaped OK",
        cmd=list(cmd),
    )


def banner(mode: LaunchMode, *, job: str, extra: str = "") -> str:
    if mode is LaunchMode.SINGLE_LEAD:
        lines = [
            "=" * 60,
            "OR-Path PI LAUNCH MODE: SINGLE_LEAD",
            f"job: {job}",
            "This is NOT multi-agent. No subagent toolCall is required.",
            "ORPATH_LIVE_SUBAGENT does not force spawn on bare pi -p.",
            "For real multi-agent use: orpath.bat run --live-subagent",
            "  or orpath.subagent_harness.run_forced_subagent_stage",
        ]
    else:
        lines = [
            "=" * 60,
            "OR-Path PI LAUNCH MODE: MULTI_AGENT_HARNESS",
            f"job: {job}",
            f"lead tools: {LEAD_TOOLS_NO_WRITE}",
            "Lead MUST toolCall name=subagent; write/edit stripped.",
        ]
    if extra:
        lines.append(extra)
    lines.append("=" * 60)
    return "\n".join(lines)


def build_single_lead_cmd(
    root: Path,
    *,
    prompt: str,
    provider: str = DEFAULT_PROVIDER,
    model: str = DEFAULT_MODEL,
    tools: str = SINGLE_LEAD_TOOLS,
    json_mode: bool = False,
    require_credentials: bool = True,
) -> list[str]:
    """Honest single-lead command (may include write)."""
    return build_pi_command(
        root,
        prompt=prompt,
        provider=provider,
        model=model,
        tools=tools,
        json_mode=json_mode,
        require_credentials=require_credentials,
        append_system_prompt=(
            "OR-Path SINGLE_LEAD mode: you are one agent. "
            "Do not claim multi-agent or subagent completion without calling tool `subagent`. "
            "Prefer existing project scripts for solve numbers."
        ),
    )


def build_multi_agent_lead_cmd(
    root: Path,
    *,
    prompt: str,
    provider: str = DEFAULT_PROVIDER,
    model: str = DEFAULT_MODEL,
    require_credentials: bool = True,
) -> list[str]:
    """Harness-shaped lead cmd (no write/edit)."""
    cmd = build_pi_command(
        root,
        prompt=prompt,
        provider=provider,
        model=model,
        tools=LEAD_TOOLS_NO_WRITE,
        json_mode=True,
        require_credentials=require_credentials,
        append_system_prompt=ANTI_COSPLAY_SYSTEM,
    )
    v = validate_launch(cmd, claim_multi_agent=True, label="build_multi_agent_lead_cmd")
    if not v.ok:
        raise RuntimeError(v.reason)
    return cmd


def refuse_if_fake_multi_agent_prompt(prompt: str) -> str | None:
    """Return error string if prompt claims multi-agent without harness intent."""
    low = prompt.lower()
    multi_words = (
        "multi-agent",
        "multi agent",
        "子智能体必须",
        "must call subagent",
        "or-researcher",
        "or-writer",
        "or-verifier",
        "or-reviewer",
    )
    # soft: only warn markers for launchers that claim multi
    hits = [w for w in multi_words if w in low]
    if hits and "single_lead" not in low and "single-lead" not in low:
        return (
            "prompt mentions multi-agent roles "
            f"({', '.join(hits[:4])}) — launcher must use MULTI_AGENT_HARNESS "
            "or rewrite prompt to SINGLE_LEAD"
        )
    return None
