"""Common helpers for OR-Path pipeline nodes."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from orpath.state import ORPathState

TUNE_STRATEGIES = [
    ("PATH_CHEAPEST_ARC", "GUIDED_LOCAL_SEARCH", 500),
    ("PATH_CHEAPEST_ARC", "SIMULATED_ANNEALING", 1500),
    ("SAVINGS", "GUIDED_LOCAL_SEARCH", 3000),
]

def _root(state: ORPathState) -> Path:
    r = state.get("root") or state.get("workdir")
    return Path(r) if r else Path.cwd()


def _rel_under(path: Path, root: Path) -> str:
    """Path relative to root when possible; else absolute posix (fixture may live under install home)."""
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _ensure_dirs(root: Path) -> None:
    for rel in (
        "outputs/.plans",
        "outputs/.drafts",
        "notes",
        "papers",
        "runs",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)


def _fixture_base(root: Path, problem_id: str) -> Path | None:
    """Locate fixtures/t*/<id> or inbox/<id> under workdir root and/or install home."""
    from orpath.paths import fixture_search_roots

    for base_root in fixture_search_roots(root):
        if (base_root / "inbox" / problem_id).is_dir():
            return base_root / "inbox" / problem_id
        for base in (
            base_root / "fixtures" / "t3",
            base_root / "fixtures" / "t2",
            base_root / "fixtures" / "t1",
        ):
            if (base / problem_id).is_dir():
                return base / problem_id
    return None


def _infer_class(root: Path, problem_id: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    pid = (problem_id or "").strip().lower()
    # Ad-hoc / contest ids (no fixtures/t*/<id> dir)
    if "tube" in pid:
        return "tube_cut"
    if "polyomino" in pid or "poly" in pid:
        return "polyomino_cover"
    if "microgrid" in pid or "cumcm2026_c" in pid:
        return "microgrid_dispatch"
    d = _fixture_base(root, problem_id)
    if d is None:
        # Intake-driven run without fixture: do not fake shortest_path gold.
        return "unknown"
    if (d / "locations.json").is_file():
        return "vrp"
    if (d / "coords.json").is_file() or (d / "distance_matrix.json").is_file():
        return "tsp"
    return "shortest_path"



def _intake_front_door_active(state: ORPathState) -> bool:
    """True when run used intake sources (not default skip_intake CI path)."""
    if state.get("skip_intake"):
        return False
    if state.get("intake_path"):
        return True
    srcs = state.get("intake_sources") or []
    return bool(srcs)



def _solution_is_blocked(state: ORPathState) -> bool:
    """True when solve refused or returned any honest BLOCKED envelope."""
    if state.get("solve_refused"):
        return True
    sp = state.get("solution_path") or ""
    p = Path(sp) if sp else None
    if not p or not p.is_file():
        return False
    try:
        sol = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(sol, dict):
        return False
    if str(sol.get("status") or "").upper() == "BLOCKED":
        return True
    meta = sol.get("meta")
    return bool(isinstance(meta, dict) and meta.get("blocked"))


def _intake_whitelist_path(root: Path, state: ORPathState) -> Path:
    """Write/return intake-scoped whitelist (no SP fixture arxiv) for blocked soak paper."""
    slug = str(state.get("slug") or "run")
    out = root / "outputs" / f"{slug}-intake-whitelist.json"
    notes: list[str] = ["notes://intake-blocked-soak"]
    bp = state.get("brief_path") or ""
    ip = state.get("intake_path") or ""
    rp = state.get("research_path") or ""
    if bp:
        notes.append(str(bp).replace("\\", "/"))
    if ip:
        notes.append(str(ip).replace("\\", "/"))
    if rp:
        notes.append(str(rp).replace("\\", "/"))
    notes.append(f"notes://{slug}-research")
    payload = {"urls": [], "notes": notes, "meta": {"kind": "intake_blocked_soak"}}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def _paper_whitelist_path(
    root: Path, state: ORPathState, fixture_dir: Path | None
) -> Path:
    """R4: when intake-on or BLOCKED, do not use shell fixture whitelist_refs.json."""
    blocked = _solution_is_blocked(state)
    intake_on = _intake_front_door_active(state)
    if blocked or intake_on or fixture_dir is None:
        return _intake_whitelist_path(root, state)
    wl = fixture_dir / "whitelist_refs.json"
    return wl




def _count_fatal(review_text: str) -> int:
    return len(re.findall(r"\*\*FATAL:\*\*", review_text))


