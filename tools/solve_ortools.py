#!/usr/bin/env python3
"""Compute shortest path from graph.json via NetworkX Dijkstra; print solution JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _import_networkx():
    try:
        import networkx as nx  # type: ignore
    except ImportError:
        print("error: networkx import failed", file=sys.stderr)
        raise SystemExit(2)
    return nx


def load_graph(problem_id: str) -> dict:
    path = ROOT / "fixtures" / "t1" / problem_id / "graph.json"
    if not path.is_file():
        raise FileNotFoundError(f"graph not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("graph.json must be a JSON object")
    return data


def shortest_path_solution(problem_id: str, source: str = "S", target: str = "T") -> dict:
    nx = _import_networkx()
    graph = load_graph(problem_id)
    g = nx.DiGraph()
    for node in graph.get("nodes") or []:
        g.add_node(node)
    for edge in graph.get("edges") or []:
        g.add_edge(edge["u"], edge["v"], weight=float(edge["w"]))
    path = nx.shortest_path(g, source=source, target=target, weight="weight")
    cost = nx.shortest_path_length(g, source=source, target=target, weight="weight")
    # Prefer int when exact
    if isinstance(cost, float) and cost.is_integer():
        cost = int(cost)
    return {
        "problem_id": problem_id,
        "status": "OPTIMAL",
        "objective": cost,
        "path": list(path),
        "solver": "networkx-dijkstra",
        "source": f"fixtures/t1/{problem_id}/graph.json",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OR-Path NetworkX shortest-path solver")
    parser.add_argument("problem_id", help="Fixture id under fixtures/t1/<id>/")
    parser.add_argument("--source", default="S")
    parser.add_argument("--target", default="T")
    args = parser.parse_args(argv)
    try:
        data = shortest_path_solution(args.problem_id, args.source, args.target)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
