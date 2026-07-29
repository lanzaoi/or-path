"""On-disk proof helpers for P0-3 revise loop."""
from __future__ import annotations

import re
from pathlib import Path


def write_revise_proof(
    path: Path,
    *,
    slug: str,
    before: str,
    after: str,
    removed_needles: list[str],
    r1_ok: bool,
    r2_ok: bool,
    claim_ok: bool,
    detail: str = "",
) -> Path:
    """Record that forbidden strings are gone and gates re-checked."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Revise proof: {slug}",
        "",
        f"- r1_ok: {r1_ok}",
        f"- r2_ok: {r2_ok}",
        f"- claim_map_ok: {claim_ok}",
        f"- detail: {detail}",
        "",
        "## Needle checks (must be ABSENT in after)",
    ]
    all_absent = True
    for n in removed_needles:
        if not n:
            continue
        present = n in after
        if present:
            all_absent = False
        lines.append(f"- `{n[:80]}`: {'STILL_PRESENT' if present else 'ABSENT_OK'}")
    lines.append("")
    lines.append("## Diff stats")
    lines.append(f"- before_chars: {len(before)}")
    lines.append(f"- after_chars: {len(after)}")
    lines.append(f"- changed: {before != after}")
    lines.append("")
    lines.append(f"## Proof status: {'PASS' if all_absent and r1_ok and r2_ok and claim_ok else 'FAIL'}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def extract_bad_urls(text: str, allowed: set[str]) -> list[str]:
    found = re.findall(r"https?://[^\s)\]>\"']+", text)
    bad = []
    allow_n = {a.rstrip("/") for a in allowed}
    for u in found:
        u2 = u.rstrip(".,;)]}>\"'")
        if u2 not in allowed and u2.rstrip("/") not in allow_n:
            bad.append(u2)
    return bad
