"""Notes helper: write retrieval artifacts researchers can consume.

Produces notes/<slug>-retrieval.json matching RetrievalArtifact contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from knowledge_svc.chunk_schema import RetrievalArtifact, repo_root, write_json
from knowledge_svc.retrieve import retrieve


def notes_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "notes"


def retrieval_path(slug: str, root: Path | None = None) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug).strip("-") or "run"
    return notes_dir(root) / f"{safe}-retrieval.json"


def write_retrieval_note(
    slug: str,
    query: str,
    *,
    mode: str = "hybrid",
    topk: int = 5,
    problem_class: str | None = None,
    root: Path | None = None,
    artifact: RetrievalArtifact | None = None,
) -> Path:
    """Run retrieve (unless artifact given) and write notes/<slug>-retrieval.json."""
    root = root or repo_root()
    if artifact is None:
        artifact = retrieve(
            query,
            mode=mode,  # type: ignore[arg-type]
            topk=topk,
            problem_class=problem_class,
            root=root,
        )
    path = retrieval_path(slug, root)
    write_json(path, artifact.to_dict())
    return path


def load_retrieval_note(path: Path) -> RetrievalArtifact:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return RetrievalArtifact.from_dict(data)


def citation_ids(artifact: RetrievalArtifact) -> list[str]:
    """chunk_id / seed node ids researchers may cite."""
    ids = [h.chunk_id for h in artifact.hits]
    for fact in artifact.seed_facts:
        nid = fact.get("node_id")
        if nid:
            ids.append(str(nid))
        for n in fact.get("nodes") or []:
            if n.get("id"):
                ids.append(str(n["id"]))
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Write notes/<slug>-retrieval.json")
    p.add_argument("--slug", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--mode", choices=["off", "seed", "hybrid"], default="seed")
    p.add_argument("--topk", type=int, default=5)
    p.add_argument("--class", dest="problem_class", default=None)
    args = p.parse_args(argv)
    try:
        path = write_retrieval_note(
            args.slug,
            args.query,
            mode=args.mode,
            topk=args.topk,
            problem_class=args.problem_class,
        )
    except Exception as e:
        print(f"notes_helper failed: {e}", file=sys.stderr)
        return 2
    art = load_retrieval_note(path)
    print(
        json.dumps(
            {
                "path": str(path),
                "n_hits": len(art.hits),
                "citation_ids": citation_ids(art)[:20],
                "knowledge_mode": art.knowledge_mode,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
