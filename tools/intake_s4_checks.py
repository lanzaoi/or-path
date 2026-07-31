"""S4 helpers: legacy skip_intake proof + multi-Q structure smoke (no solver numbers)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Headings we expect in product problem-brief (gate_intake semantics).
# Tube historical brief uses different titles; structure smoke maps Q1..Qn coverage.
_PRODUCT_BRIEF_HEADING_HINTS = (
    "Sources",
    "Full problem statement",
    "Subproblems",
    "Data assets",
    "Objectives",
    "Constraints",
    "Deliverables",
    "Ambiguities",
    "Non-goals",
)


def legacy_skip_intake_ok(root: Path) -> list[str]:
    """Legacy/CI path must not require intake artifacts to exist.

    Proof (static + fixture presence):
    - T1 fixture shortest_path exists and is the product smoke without intake files
    - No required outputs/*-intake.json for that fixture
    - tools/gate_intake is opt-in CLI (not imported by run_t1)
    """
    errors: list[str] = []
    t1 = root / "fixtures" / "t1" / "shortest_path"
    if not t1.is_dir():
        errors.append("missing fixtures/t1/shortest_path (legacy baseline)")
        return errors
    # must not require intake.json beside t1 fixture
    if (t1 / "intake.json").is_file():
        errors.append("t1 fixture unexpectedly has intake.json (legacy should not require it)")
    # run_t1 should not import gate_intake
    run_t1 = root / "orpath" / "run_t1.py"
    if run_t1.is_file():
        text = run_t1.read_text(encoding="utf-8", errors="replace")
        if "gate_intake" in text or "intake_parse" in text or "intake_ocr" in text:
            errors.append("run_t1.py imports intake tools — breaks skip_intake legacy")
    # control_plane seed path should not hard-require intake
    cp = root / "orpath" / "control_plane.py"
    if cp.is_file():
        text = cp.read_text(encoding="utf-8", errors="replace")
        # allow comments mentioning intake; forbid hard required file reads of intake.json
        if re.search(r"raise\s+\w*Error\([^)]*intake\.json", text):
            errors.append("control_plane hard-fails on missing intake.json")
    return errors


def structure_coverage_from_intake(data: dict[str, Any], *, min_subproblems: int) -> list[str]:
    """Assert intake.json has multi-subproblem coverage without solution keys."""
    errors: list[str] = []
    subs = data.get("subproblems") or []
    if not isinstance(subs, list) or len(subs) < min_subproblems:
        errors.append(
            f"structure: subproblems {len(subs) if isinstance(subs, list) else type(subs)} "
            f"< min {min_subproblems}"
        )
    # no solution-shaped top-level keys
    for k in ("objective", "tour", "routes", "path", "optimal"):
        if k in data:
            errors.append(f"structure: forbidden top-level key {k}")
    return errors


def brief_has_product_sections(text: str) -> list[str]:
    missing = []
    for h in _PRODUCT_BRIEF_HEADING_HINTS:
        if h.lower() not in text.lower():
            missing.append(f"brief missing heading hint: {h}")
    return missing


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
