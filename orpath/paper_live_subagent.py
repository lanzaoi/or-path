"""M2: paper-loop live subagent glue for cite_pack / review_pack.

Lead draft remains lead-owned (scripted render_or_paper).
Cite → harness → subagent or-verifier (lead has NO write tools).
Review → harness → subagent or-reviewer (lead has NO write tools).

Deterministic gates set ORPATH_LIVE_SUBAGENT=0.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from orpath.subagent_harness import run_forced_subagent_stage
from orpath.subagent_runtime import check_env, detect_subagent_calls, require_env


def live_subagent_enabled(state: dict[str, Any] | None = None) -> bool:
    """Whether to spawn Pi leads for cite/review."""
    raw = (os.environ.get("ORPATH_LIVE_SUBAGENT") or "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    if state:
        if state.get("live_subagent") is True or state.get("live_pi") is True:
            return True
        if state.get("live_subagent") is False:
            return False
    return bool(check_env().ok)


def run_cite_subagent_lead(
    root: Path,
    state: dict[str, Any],
    *,
    paper: Path,
    cited: Path,
    solution: Path,
    whitelist: Path | None,
    research: Path | None,
    claim_map: Path,
) -> dict[str, Any]:
    """Forced harness: lead without write → must subagent or-verifier."""
    slug = str(state["slug"])
    if not live_subagent_enabled(state):
        return {
            "skipped": True,
            "gate_subagent_ok": None,
            "detail": "live_subagent disabled (deterministic path)",
        }

    require_env(root)
    brief_body = f"""# Cite brief for `{slug}`

## Role
Stage lead for cite_pack. You have **NO write/edit**. Call `subagent` → `or-verifier`.

## Inputs (child reads these)
- draft/paper: `{paper}`
- solution: `{solution}`
- whitelist: `{whitelist or "n/a"}`
- research: `{research or "n/a"}`

## Child (or-verifier) MUST
1. Read draft + solution.
2. Write cited draft to `{cited}` with Sources / claim anchors.
3. Prefer local gates via bash:
   - `python tools/r1_cite_check.py --draft ... --whitelist ...`
   - `python tools/r2_numeric_check.py --draft ... --solution ...`
   - `python tools/r1_claim_map.py --draft ... --solution ... --out {claim_map}`
4. No invented URLs. Numerics only from solution.json.
5. No dishonest global-opt unless meta.proven_optimal.

## Lead
- FIRST tool = subagent with agent or-verifier.
- Verify `{cited}` exists via bash/read only.
"""
    detail = run_forced_subagent_stage(
        root,
        slug=slug,
        stage="cite",
        required_agent="or-verifier",
        brief_body=brief_body,
        output_path=cited,
        extra_outputs=[claim_map] if False else None,  # claim_map optional from child
        extra_rules="Serial cite only. No review.",
    )
    # also write cite-subagent.json alias for older monitors
    rep = root / "outputs" / ".agents" / slug / "cite-subagent.json"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(detail, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return detail


def run_review_subagent_lead(
    root: Path,
    state: dict[str, Any],
    *,
    paper: Path,
    review: Path,
    solution: Path,
    whitelist: Path | None,
) -> dict[str, Any]:
    """Forced harness: lead without write → must subagent or-reviewer."""
    slug = str(state["slug"])
    if not live_subagent_enabled(state):
        return {
            "skipped": True,
            "gate_subagent_ok": None,
            "detail": "live_subagent disabled (deterministic path)",
        }

    require_env(root)
    brief_body = f"""# Review brief for `{slug}`

## Role
Stage lead for review_pack. You have **NO write/edit**. Call `subagent` → `or-reviewer`.

## Inputs
- paper: `{paper}`
- solution: `{solution}`
- whitelist: `{whitelist or "n/a"}`

## Child (or-reviewer) MUST
1. Read paper + solution.
2. Write adversarial review to `{review}` (FATAL/MAJOR/MINOR + inline quotes).
3. Flag fake optima, numerics not in solution, missing limitations.
4. Do not rewrite the full paper.

## Lead
- FIRST tool = subagent with agent or-reviewer.
- Verify `{review}` exists via bash/read only.
- After cite only; do not re-run verifier.
"""
    detail = run_forced_subagent_stage(
        root,
        slug=slug,
        stage="review",
        required_agent="or-reviewer",
        brief_body=brief_body,
        output_path=review,
        extra_rules="Do not parallelize with cite. Reviewer only.",
    )
    rep = root / "outputs" / ".agents" / slug / "review-subagent.json"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(detail, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return detail


def merge_review_if_child_wrote(
    *,
    automated_body: str,
    child_review: Path,
) -> str:
    """Prefer child review body when present; append automated gate summary."""
    if child_review.is_file() and child_review.stat().st_size > 80:
        child = child_review.read_text(encoding="utf-8")
        return (
            child.rstrip()
            + "\n\n---\n## Automated gate appendix (OR-Path scripts)\n\n"
            + automated_body
            + "\n"
        )
    return automated_body


def log_has_subagent(path: Path) -> bool:
    if not path.is_file():
        return False
    hit, _ = detect_subagent_calls(path.read_text(encoding="utf-8", errors="ignore"))
    return hit
