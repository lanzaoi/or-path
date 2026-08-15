#!/usr/bin/env python3
"""Validate committed T2 closeout metadata without claiming a current LIVE run."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "archive" / "evidence" / "t2-live-meta"
REQUIRED_AGENTS = {"or-researcher", "or-modeler", "or-writer"}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    if not EVIDENCE.is_dir():
        fail(f"missing archived evidence: {EVIDENCE}")

    records: list[dict] = []
    for path in sorted(EVIDENCE.glob("*_meta.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"invalid {path.name}: {exc}")
        if not isinstance(record, dict):
            fail(f"non-object metadata: {path.name}")
        records.append(record)

    agents = {str(r.get("agent") or "") for r in records}
    run_ids = {str(r.get("runId") or "") for r in records if r.get("runId")}
    if not REQUIRED_AGENTS <= agents:
        fail(f"missing archived agents: {sorted(REQUIRED_AGENTS - agents)}")
    if len(run_ids) < len(REQUIRED_AGENTS):
        fail(f"runId isolation not evidenced: {sorted(run_ids)}")
    bad_exit = [r.get("agent") for r in records if r.get("exitCode") != 0]
    if bad_exit:
        fail(f"archived non-zero exits: {bad_exit}")
    missing_transcript_refs = [
        r.get("agent") for r in records if not str(r.get("transcriptPath") or "").strip()
    ]
    if missing_transcript_refs:
        fail(f"missing transcript references: {missing_transcript_refs}")

    print(
        json.dumps(
            {
                "ok": True,
                "evidence_kind": "archived_closeout_metadata",
                "current_live_run": False,
                "agents": sorted(agents),
                "runIds": sorted(run_ids),
                "strict_live_command": "orpath.bat isolation",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("PASS: archived T2 isolation evidence (not a current LIVE run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
