"""P2: annotations-lite — structured review findings (Feynman annotations idea, file-native)."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "orpath.annotations.v1"
FATAL_RE = re.compile(r"\*\*FATAL:\*\*\s*(.+)")
MAJOR_RE = re.compile(r"\*\*MAJOR:\*\*\s*(.+)")
QUOTE_RE = re.compile(r"^>\s*(.+)$", re.M)


def annotations_from_review(
    review_text: str,
    *,
    artifact_path: str,
    slug: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # pair nearby quotes with following FATAL/MAJOR when possible
    lines = review_text.splitlines()
    last_quote = ""
    label = 0
    for i, line in enumerate(lines):
        qm = QUOTE_RE.match(line.strip())
        if qm:
            last_quote = qm.group(1).strip()
        for sev, rx in (("fatal", FATAL_RE), ("major", MAJOR_RE)):
            m = rx.search(line)
            if not m:
                continue
            label += 1
            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "artifactPath": artifact_path.replace("\\", "/"),
                    "kind": "revision" if sev == "fatal" else "note",
                    "severity": sev,
                    "labelIndex": label,
                    "body": m.group(1).strip()[:8000],
                    "anchorKind": "text_selection" if last_quote else "point",
                    "anchorText": last_quote[:1200] if last_quote else None,
                    "runSlug": slug,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                }
            )
            last_quote = ""
    return rows


def write_annotations(path: Path, *, slug: str, annotations: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "slug": slug,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(annotations),
        "artifactAnnotations": annotations,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
