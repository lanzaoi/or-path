"""P2: lab CHANGELOG continuity + simple solution figure (mermaid HTML)."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_lab_changelog(
    root: Path,
    *,
    slug: str,
    title: str,
    bullets: list[str],
) -> Path:
    lab = root / "outputs" / ".lab"
    lab.mkdir(parents=True, exist_ok=True)
    path = lab / "CHANGELOG.md"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = [f"### {ts} — {slug}: {title}", ""]
    for b in bullets:
        block.append(f"- {b}")
    block.append("")
    if not path.is_file():
        path.write_text("# OR-Path lab CHANGELOG\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(block) + "\n")
    return path


def write_solution_figure(path: Path, solution: dict[str, Any], *, slug: str) -> Path | None:
    """Minimal visual: mermaid for path/tour; skip if nothing drawable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if isinstance(solution.get("path"), list) and solution["path"]:
        nodes = [str(x) for x in solution["path"]]
        lines.append("flowchart LR")
        for a, b in zip(nodes, nodes[1:]):
            lines.append(f"  { _safe_id(a) }[{_label(a)}] --> { _safe_id(b) }[{_label(b)}]")
    elif isinstance(solution.get("tour"), list) and solution["tour"]:
        nodes = [str(x) for x in solution["tour"]]
        lines.append("flowchart LR")
        for a, b in zip(nodes, nodes[1:] + nodes[:1]):
            lines.append(f"  { _safe_id(a) }[{_label(a)}] --> { _safe_id(b) }[{_label(b)}]")
    else:
        # still write a small status card
        lines = [
            "flowchart TD",
            f"  O[objective={solution.get('objective')}] --> S[status={solution.get('status')}]",
        ]

    mermaid = "\n".join(lines)
    body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>{html.escape(slug)} figure</title>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({{ startOnLoad: true }});
</script>
</head><body>
<h1>{html.escape(slug)} — solution figure</h1>
<p>objective=<code>{html.escape(str(solution.get('objective')))}</code>
 status=<code>{html.escape(str(solution.get('status')))}</code>
 solver=<code>{html.escape(str(solution.get('solver')))}</code></p>
<pre class="mermaid">
{html.escape(mermaid)}
</pre>
<p>Source: solution.json only. Not decorative without numbers.</p>
</body></html>
"""
    path.write_text(body, encoding="utf-8")
    # also keep mermaid source
    path.with_suffix(".mmd").write_text(mermaid + "\n", encoding="utf-8")
    return path


def _safe_id(s: str) -> str:
    import re

    x = re.sub(r"[^A-Za-z0-9_]", "_", s)
    if not x or x[0].isdigit():
        x = "n_" + x
    return x


def _label(s: str) -> str:
    return s.replace('"', "'")[:40]
