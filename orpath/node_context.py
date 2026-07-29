"""NodeContext: snapshot, artifact manifest, owner asserts (T3 skeleton)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orpath.state import (
    FORBIDDEN_NUMERIC_KEYS,
    MANIFEST_PATH_KEYS,
    SOLVE_NODES,
    ORPathState,
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def thread_dir(state: ORPathState) -> Path:
    root = Path(state["root"])
    tid = state.get("thread_id") or state.get("slug") or "default"
    d = root / "runs" / str(tid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "stages").mkdir(parents=True, exist_ok=True)
    return d


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_manifest(state: ORPathState) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in MANIFEST_PATH_KEYS:
        raw = state.get(key)  # type: ignore[arg-type]
        if not raw:
            continue
        p = Path(str(raw))
        digest = file_sha256(p)
        if digest:
            out[str(p.resolve())] = digest
    return out


def write_manifest(state: ORPathState, extra: dict[str, str] | None = None) -> Path:
    td = thread_dir(state)
    path = td / "artifact_hashes.json"
    data = collect_manifest(state)
    if extra:
        data.update(extra)
    path.write_text(json.dumps({"utc": _utc(), "files": data}, indent=2) + "\n", encoding="utf-8")
    return path


def load_manifest(state: ORPathState) -> dict[str, str]:
    path = thread_dir(state) / "artifact_hashes.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return dict(raw.get("files") or {})


def dirty_artifacts(state: ORPathState) -> list[dict[str, str]]:
    """Return list of {path, expected, got} for changed tracked files."""
    expected = load_manifest(state)
    if not expected:
        return []
    dirty: list[dict[str, str]] = []
    for pth, exp in expected.items():
        p = Path(pth)
        got = file_sha256(p)
        if got is None:
            dirty.append({"path": pth, "expected": exp, "got": "MISSING"})
        elif got != exp:
            dirty.append({"path": pth, "expected": exp, "got": got})
    return dirty


def assert_owner(node_name: str, update: dict[str, Any]) -> None:
    if node_name in SOLVE_NODES:
        return
    bad = sorted(FORBIDDEN_NUMERIC_KEYS.intersection(update.keys()))
    if bad:
        raise RuntimeError(
            f"owner assert: node '{node_name}' must not write numeric keys {bad}"
        )


def write_snapshot(node_name: str, state: ORPathState, update: dict[str, Any]) -> Path:
    td = thread_dir(state)
    merged = {**dict(state), **update}
    # drop huge blobs if any
    snap = {
        "utc": _utc(),
        "node": node_name,
        "stage": merged.get("stage"),
        "thread_id": merged.get("thread_id"),
        "slug": merged.get("slug"),
        "human_required": merged.get("human_required"),
        "gate_schema_ok": merged.get("gate_schema_ok"),
        "gate_validate_ok": merged.get("gate_validate_ok"),
        "solver_tune": merged.get("solver_tune"),
        "schema_repair": merged.get("schema_repair"),
        "validate_repair": merged.get("validate_repair"),
        "revise_count": merged.get("revise_count"),
        "paths": {k: merged.get(k) for k in MANIFEST_PATH_KEYS if merged.get(k)},
        "last_error": merged.get("last_error"),
        "bridge_ok": merged.get("bridge_ok"),
        "bridge_skipped": merged.get("bridge_skipped"),
        "orpath_checkpoint_id": merged.get("orpath_checkpoint_id"),
    }
    # sequential filename
    stages = td / "stages"
    n = len(list(stages.glob("*.json"))) + 1
    path = stages / f"{n:04d}_{node_name}.json"
    path.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # also latest pointer
    (td / "latest_snapshot.json").write_text(
        json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


class NodeContext:
    def __init__(self, node_name: str, state: ORPathState):
        self.node_name = node_name
        self.state = state

    def wrap(self, update: dict[str, Any]) -> dict[str, Any]:
        assert_owner(self.node_name, update)
        # merge for snapshot/manifest
        merged_state: ORPathState = {**self.state, **update}  # type: ignore[misc]
        snap = write_snapshot(self.node_name, merged_state, update)
        man = write_manifest(merged_state)
        out = dict(update)
        out["last_snapshot_path"] = str(snap)
        out["artifact_manifest_path"] = str(man)
        out["runs_dir"] = str(thread_dir(merged_state))
        return out


def wrap_node(node_name: str, fn):
    """Decorator-style wrapper for LG node callables."""

    def _inner(state: ORPathState) -> dict[str, Any]:
        ctx = NodeContext(node_name, state)
        raw = fn(state) or {}
        return ctx.wrap(raw)

    _inner.__name__ = f"wrapped_{node_name}"
    return _inner
