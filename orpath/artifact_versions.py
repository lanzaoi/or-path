"""P2: lightweight artifact version chain (Feynman-inspired, not a TS port).

Tracks sha256 + parentVersionId + inputPaths for paper-pipeline artifacts under
outputs/, papers/, notes/. Writes jsonl + consolidated json per slug.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

TRACKED_ROOTS = ("outputs", "papers", "notes")
SCHEMA = "orpath.artifactVersion.v1"


def _posix(p: Path | str) -> str:
    return str(p).replace("\\", "/")


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(65536)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def rel_under_root(root: Path, path: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    s = _posix(rel)
    if any(s == r or s.startswith(r + "/") for r in TRACKED_ROOTS):
        return s
    return None


def version_id(artifact_path: str, checksum: str | None, version_number: int) -> str:
    raw = f"{artifact_path}:{checksum or 'none'}:{version_number}".lower()
    safe = re.sub(r"[^a-z0-9._:-]+", "-", raw)[:180]
    return f"artifact-version:{safe}"


def record_versions(
    root: Path,
    *,
    slug: str,
    paths: Iterable[str | Path],
    stage: str,
    input_paths: list[str] | None = None,
    source: str = "orpath",
) -> dict[str, Any]:
    """Append versions for existing files; return consolidated ledger."""
    root = root.resolve()
    out_dir = root / "outputs" / ".artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = out_dir / f"{slug}-versions.jsonl"
    consolidated = out_dir / f"{slug}-versions.json"

    existing: list[dict[str, Any]] = []
    if consolidated.is_file():
        try:
            data = json.loads(consolidated.read_text(encoding="utf-8"))
            existing = list(data.get("versions") or [])
        except json.JSONDecodeError:
            existing = []

    by_art: dict[str, list[dict[str, Any]]] = {}
    for v in existing:
        by_art.setdefault(v.get("artifactPath") or "", []).append(v)

    now = datetime.now(timezone.utc)
    iso = now.isoformat()
    ms = int(now.timestamp() * 1000)
    inputs = [_posix(p) for p in (input_paths or [])]
    new_rows: list[dict[str, Any]] = []

    for p in paths:
        path = Path(p)
        if not path.is_file():
            continue
        rel = rel_under_root(root, path) or _posix(path)
        checksum = file_sha256(path)
        prev_list = by_art.get(rel) or []
        # skip if same checksum as latest
        if prev_list and prev_list[-1].get("checksum") == checksum and checksum:
            continue
        n = len(prev_list) + 1
        parent = prev_list[-1]["id"] if prev_list else None
        row = {
            "schema": SCHEMA,
            "id": version_id(rel, checksum, n),
            "artifactPath": rel,
            "versionNumber": n,
            "label": f"v{n}",
            "source": source,
            "stage": stage,
            "slug": slug,
            "checksum": checksum,
            "sizeBytes": path.stat().st_size,
            "createdAt": iso,
            "createdAtMs": ms,
            "parentVersionId": parent,
            "inputPaths": [i for i in inputs if i != rel],
            "outputPaths": [rel],
            "isCheckpoint": "verification" in rel or "claim" in rel or stage in {"cite", "review", "provenance"},
        }
        new_rows.append(row)
        prev_list.append(row)
        by_art[rel] = prev_list

    if new_rows:
        with jsonl.open("a", encoding="utf-8") as f:
            for row in new_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    all_versions: list[dict[str, Any]] = []
    for lst in by_art.values():
        all_versions.extend(lst)
    all_versions.sort(key=lambda r: (r.get("createdAtMs") or 0, r.get("artifactPath") or ""))

    # lightweight dependencies: version depends on latest version of each inputPath
    deps: list[dict[str, Any]] = []
    latest_by_path = {rel: lst[-1] for rel, lst in by_art.items() if lst}
    for v in all_versions:
        for ip in v.get("inputPaths") or []:
            # resolve ip to tracked rel if possible
            key = ip
            tgt = latest_by_path.get(key)
            if not tgt:
                continue
            deps.append(
                {
                    "id": f"dep:{v['id']}:{tgt['id']}",
                    "artifactVersionId": v["id"],
                    "dependsOnVersionId": tgt["id"],
                    "referenceName": key,
                }
            )

    payload = {
        "schemaVersion": "orpath.artifactVersions.v1",
        "slug": slug,
        "updatedAt": iso,
        "versionCount": len(all_versions),
        "dependencyCount": len(deps),
        "versions": all_versions,
        "dependencies": deps[:500],
    }
    consolidated.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload
