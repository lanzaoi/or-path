"""Ruthless anti-cosplay harness for Pi stage leads.

Hard law: forced stages MUST show a real `subagent` toolCall in JSON logs.
Leads are stripped of write/edit so they cannot silently author child artifacts.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any, Sequence

from orpath.subagent_runtime import (
    LeadResult,
    build_lead_prompt,
    lead_result_to_json,
    spawn_lead,
    write_lead_manifest,
    write_task_brief,
)

# Lead may read/inspect and ONLY spawn children — never write the stage artifact.
LEAD_TOOLS_NO_WRITE = (
    "read,bash,subagent,subagent_wait,subagent_supervisor,grep,find,ls"
)

ANTI_COSPLAY_SYSTEM = """ANTI-COSPLAY HARD LAW (OR-Path harness):
1. For forced stages you MUST call the tool named `subagent` before finishing.
2. You do NOT have write/edit tools. Do not invent completion without the child.
3. Cosplay (saying you are or-verifier/or-reviewer without toolCall) is FAILURE.
4. After subagent returns, verify the output path exists via bash/read only.
5. If subagent tool is missing, reply exactly: SUBAGENT_TOOL_MISSING
"""


def _retry_limit() -> int:
    try:
        return max(1, int(os.environ.get("ORPATH_SUBAGENT_RETRIES", "3")))
    except ValueError:
        return 3


def _timeout_s() -> int:
    try:
        return max(60, int(os.environ.get("ORPATH_SUBAGENT_TIMEOUT", "1200")))
    except ValueError:
        return 1200


def _backup_paths(paths: Sequence[Path], bak_dir: Path) -> dict[str, Path | None]:
    bak_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path | None] = {}
    for p in paths:
        key = str(p)
        if p.is_file():
            dest = bak_dir / (p.name + ".pre-harness.bak")
            shutil.copy2(p, dest)
            out[key] = dest
        else:
            out[key] = None
    return out


def _restore_or_purge(paths: Sequence[Path], backups: dict[str, Path | None]) -> None:
    """If cosplay wrote files without valid subagent, restore backup or delete."""
    for p in paths:
        bak = backups.get(str(p))
        if bak and bak.is_file():
            shutil.copy2(bak, p)
        elif p.is_file():
            # quarantine cosplay artifact
            q = p.parent / (p.name + ".cosplay-quarantine")
            try:
                if q.exists():
                    q.unlink()
                p.replace(q)
            except OSError:
                try:
                    p.unlink()
                except OSError:
                    pass


def _quarantine_dir(root: Path, slug: str) -> Path:
    d = root / "outputs" / ".agents" / slug / "quarantine"
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_forced_subagent_stage(
    root: Path,
    *,
    slug: str,
    stage: str,
    required_agent: str,
    brief_body: str,
    output_path: Path,
    extra_outputs: Sequence[Path] | None = None,
    extra_rules: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run lead with NO write tools until real subagent toolCall + outputs exist.

    On cosplay: purge lead-written outputs (restore backup), retry harder.
    """
    root = Path(root).resolve()
    outputs = [output_path, *list(extra_outputs or [])]
    qdir = _quarantine_dir(root, slug)
    backups = _backup_paths(outputs, qdir)

    brief = write_task_brief(
        root,
        slug,
        stage,
        body=brief_body
        + "\n\n## HARNESS\n"
        + "- Lead has **no write/edit**. Only the child may create the output file.\n"
        + f"- Required agent: `{required_agent}`\n"
        + f"- Required output: `{output_path}`\n"
        + "- First tool call MUST be `subagent`.\n",
        outputs={"primary": str(output_path)},
    )

    base_extra = (
        "HARNESS: You have NO write/edit tools. "
        "FIRST tool call MUST be subagent. "
        "Do not claim success without a real toolCall.\n"
        + extra_rules
    )

    results: list[LeadResult] = []
    last: LeadResult | None = None
    n = _retry_limit()

    for attempt in range(n):
        # wipe cosplay outputs from previous attempt before retry
        if attempt > 0:
            _restore_or_purge(outputs, backups)

        harsh = base_extra
        if attempt > 0:
            harsh += (
                f"\nRETRY {attempt + 1}/{n}: Previous attempt FAILED cosplay detection. "
                f"Call subagent NOW with agent={required_agent}. "
                "Empty prose without toolCall = FAIL."
            )

        prompt = build_lead_prompt(
            stage=stage,
            slug=slug,
            brief_path=brief,
            required_agent=required_agent,
            output_path=str(output_path),
            extra_rules=harsh,
        )

        last = spawn_lead(
            root,
            slug=slug,
            stage=stage,
            prompt=prompt,
            timeout_s=_timeout_s(),
            require_subagent_call=True,
            expected_outputs=outputs,
            dry_run=dry_run,
            tools=LEAD_TOOLS_NO_WRITE,
            append_system_prompt=ANTI_COSPLAY_SYSTEM,
            json_mode=True,
        )
        results.append(last)

        if dry_run:
            break

        if last.ok and last.subagent_calls_detected and output_path.is_file():
            break

        # brief pause between retries
        time.sleep(min(2 * (attempt + 1), 6))

    write_lead_manifest(root, slug, results)

    ok = bool(
        last
        and last.ok
        and last.subagent_calls_detected
        and output_path.is_file()
        and output_path.stat().st_size > 0
    )

    if not ok and last and not last.subagent_calls_detected:
        _restore_or_purge(outputs, backups)

    detail = {
        "skipped": False,
        "gate_subagent_ok": ok,
        "harness": "no_write_lead+json+anti_cosplay",
        "tools": LEAD_TOOLS_NO_WRITE,
        "log_path": last.log_path if last else "",
        "subagent_calls_detected": bool(last and last.subagent_calls_detected),
        "call_evidence": (last.call_evidence if last else [])[:6],
        "attempts": len(results),
        "error": "" if ok else (last.error if last else "no spawn"),
        "lead": lead_result_to_json(last) if last else {},
        "results": [lead_result_to_json(r) for r in results],
    }

    rep = root / "outputs" / ".agents" / slug / f"{stage}-harness.json"
    rep.parent.mkdir(parents=True, exist_ok=True)
    import json

    rep.write_text(json.dumps(detail, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return detail
