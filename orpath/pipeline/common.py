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


def _replay_authorized(state: ORPathState) -> bool:
    """True only when fixture replay is explicitly authorized or non-intake explicit fixture run."""
    if os.environ.get("ORPATH_FIXTURE_REPLAY") == "1":
        return True
    if state.get("is_replay"):
        return True
    if state.get("replay_authorized") is False:
        return False
    if str(state.get("fixture_ref") or "").strip():
        return True
    if _intake_front_door_active(state):
        return False
    return bool(state.get("replay_authorized"))


def _fixture_base(root: Path, problem_id: str, *, allow_fixture: bool = True) -> Path | None:
    """Locate inbox/<id> (case) or fixtures/t*/<id> (only if allow_fixture) under workdir/home."""
    pid = (problem_id or "").strip()
    if not pid:
        return None
    from orpath.paths import fixture_search_roots

    for base_root in fixture_search_roots(root):
        if (base_root / "inbox" / pid).is_dir():
            return base_root / "inbox" / pid
        if not allow_fixture:
            continue
        for base in (
            base_root / "fixtures" / "t3",
            base_root / "fixtures" / "t2",
            base_root / "fixtures" / "t1",
        ):
            if (base / pid).is_dir():
                return base / pid
    return None


def _infer_class(
    root: Path,
    problem_id: str,
    explicit: str | None,
    *,
    allow_fixture: bool = True,
) -> str:
    if explicit:
        return explicit
    pid = (problem_id or "").strip().lower()
    if not pid:
        return "unknown"
    # Ad-hoc / contest ids (no fixtures/t*/<id> dir)
    if "tube" in pid:
        return "tube_cut"
    if "polyomino" in pid or "poly" in pid:
        return "polyomino_cover"
    if "microgrid" in pid or "cumcm2026_c" in pid:
        return "microgrid_dispatch"
    d = _fixture_base(root, problem_id, allow_fixture=allow_fixture)
    if d is None:
        # Intake-driven run without fixture: do not fake shortest_path gold.
        return "unknown"
    if (d / "locations.json").is_file():
        return "vrp"
    if (d / "coords.json").is_file() or (d / "distance_matrix.json").is_file():
        return "tsp"
    if (d / "graph.json").is_file():
        return "shortest_path"
    return "unknown"



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
    pc = str(state.get("problem_class") or "").strip().lower()
    if not _solution_is_blocked(state) and pc:
        notes.append(f"notes://{pc}-ref")
        if pc == "tsp":
            notes.append("notes://t2-tsp-ref")
        elif pc == "vrp":
            notes.append("notes://t2-vrp-ref")
        elif pc == "shortest_path" and not _intake_front_door_active(state):
            notes.append("notes://t1-shortest-path-ref")
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
    if not wl.is_file():
        return _intake_whitelist_path(root, state)
    return wl




def _count_fatal(review_text: str) -> int:
    return len(re.findall(r"\*\*FATAL:\*\*", review_text))


