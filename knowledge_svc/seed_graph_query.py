"""L4 seed graph query CLI + library."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from knowledge_svc.chunk_schema import knowledge_dir, write_json


def seed_path(root: Path | None = None) -> Path:
    if root is None:
        return knowledge_dir() / "seed_graph" / "or_domain_seed.json"
    return Path(root) / "knowledge" / "seed_graph" / "or_domain_seed.json"


def load_seed(path: Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else seed_path()
    if not p.is_file():
        raise FileNotFoundError(f"seed graph not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _index(graph: dict[str, Any]) -> tuple[dict[str, dict], list[dict]]:
    nodes = {n["id"]: n for n in graph.get("nodes") or []}
    edges = list(graph.get("edges") or [])
    return nodes, edges


def query_by_class(problem_class: str, graph: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return structured seed facts for a problem class label (e.g. tsp, vrp)."""
    g = graph or load_seed()
    nodes, edges = _index(g)
    pc_label = problem_class.strip().lower()
    pc_nodes = [
        n
        for n in nodes.values()
        if n.get("type") == "ProblemClass"
        and (
            str(n.get("label", "")).lower() == pc_label
            or str(n.get("id", "")).lower() in {pc_label, f"pc_{pc_label}"}
            or pc_label in [a.lower() for a in (n.get("props") or {}).get("aliases") or []]
        )
    ]
    if not pc_nodes:
        pc_nodes = [
            n
            for n in nodes.values()
            if n.get("type") == "ProblemClass" and pc_label in str(n.get("label", "")).lower()
        ]
    facts: list[dict[str, Any]] = []

    def _src(e: dict) -> str:
        return str(e.get("source") or e.get("from") or "")

    def _tgt(e: dict) -> str:
        return str(e.get("target") or e.get("to") or "")

    for pc in pc_nodes:
        related_ids = {pc["id"]}
        for e in edges:
            if _src(e) == pc["id"]:
                related_ids.add(_tgt(e))
            if _tgt(e) == pc["id"]:
                related_ids.add(_src(e))
        for e in edges:
            if e.get("rel") == "instance_of" and _tgt(e) == pc["id"]:
                related_ids.add(_src(e))
                for e2 in edges:
                    if _src(e2) == _src(e):
                        related_ids.add(_tgt(e2))

        related_nodes = [nodes[i] for i in related_ids if i in nodes]
        related_edges = [
            e for e in edges if _src(e) in related_ids and _tgt(e) in related_ids
        ]
        facts.append(
            {
                "problem_class": pc.get("label"),
                "node_id": pc["id"],
                "summary": (pc.get("props") or {}).get("summary"),
                "nodes": related_nodes,
                "edges": related_edges,
                "solvers": [n for n in related_nodes if n.get("type") == "Solver"],
                "constraints": [n for n in related_nodes if n.get("type") == "Constraint"],
                "cases": [n for n in related_nodes if n.get("type") == "Case"],
            }
        )
    return facts


def query_all_classes(graph: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    g = graph or load_seed()
    labels = sorted(
        {
            str(n.get("label"))
            for n in g.get("nodes") or []
            if n.get("type") == "ProblemClass" and n.get("label")
        }
    )
    out: list[dict[str, Any]] = []
    for lab in labels:
        out.extend(query_by_class(lab, g))
    return out


def query_seed(problem_class: str | None = None, limit: int = 20) -> list[dict]:
    """Backward-compatible thin API used by some callers."""
    if problem_class:
        facts = query_by_class(problem_class)
        nodes: list[dict] = []
        for f in facts:
            nodes.extend(f.get("nodes") or [])
        # dedupe
        seen = set()
        out = []
        for n in nodes:
            i = n.get("id")
            if i in seen:
                continue
            seen.add(i)
            out.append(n)
        return out[:limit]
    g = load_seed()
    return list(g.get("nodes") or [])[:limit]


def stats(graph: dict[str, Any] | None = None) -> dict[str, Any]:
    g = graph or load_seed()
    nodes = g.get("nodes") or []
    edges = g.get("edges") or []
    by_type: dict[str, int] = {}
    for n in nodes:
        t = str(n.get("type") or "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    return {"node_count": len(nodes), "edge_count": len(edges), "by_type": by_type}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Query OR-Path L4 domain seed graph")
    p.add_argument("--class", dest="problem_class", default=None, help="Problem class label")
    p.add_argument("--all", action="store_true", help="Facts for all problem classes")
    p.add_argument("--stats", action="store_true", help="Print node/edge counts")
    p.add_argument("--seed", type=Path, default=None, help="Path to seed JSON")
    p.add_argument("--out", type=Path, default=None, help="Write JSON to path")
    p.add_argument("--limit", type=int, default=50)
    args = p.parse_args(argv)

    try:
        g = load_seed(args.seed) if args.seed else load_seed()
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2

    if args.stats:
        payload: Any = stats(g)
    elif args.problem_class and not args.all:
        payload = query_by_class(args.problem_class, g)
    elif args.all:
        payload = query_all_classes(g)
    else:
        payload = {"stats": stats(g), "facts": query_all_classes(g)}

    if args.out:
        write_json(args.out, payload)
        print(f"wrote {args.out}", file=sys.stderr)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
