#!/usr/bin/env python3
"""Knowledge stack smoke: seed | ingest | retrieve | cognee | mineru | all."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Hygiene
os.environ.setdefault("PYTHONNOUSERSITE", "1")


def _print(step: str, payload) -> None:
    print(f"=== {step} ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def step_seed() -> dict:
    from knowledge_svc.seed_graph_query import load_seed, query_by_class, stats

    g = load_seed()
    st = stats(g)
    facts = {
        "shortest_path": query_by_class("shortest_path", g),
        "tsp": query_by_class("tsp", g),
        "vrp": query_by_class("vrp", g),
    }
    return {"ok": True, "stats": st, "n_tsp_solvers": len(facts["tsp"][0]["solvers"]) if facts["tsp"] else 0}


def step_ingest() -> dict:
    from knowledge_svc.embed_siliconflow import MockEmbedder
    from knowledge_svc.ingest import ingest_corpus

    # Prefer mock embeddings so smoke is green without cloud
    emb = MockEmbedder()
    return ingest_corpus(root=ROOT, clear=True, force_stub=True, embed_fn=emb.embed_texts)


def step_retrieve() -> dict:
    from knowledge_svc.embed_siliconflow import MockEmbedder
    from knowledge_svc.notes_helper import write_retrieval_note
    from knowledge_svc.retrieve import retrieve

    emb = MockEmbedder()
    seed_art = retrieve("tsp ortools", mode="seed", topk=5, problem_class="tsp", root=ROOT)
    hyb_art = retrieve(
        "CVRP capacity OR-Tools vehicle routing",
        mode="hybrid",
        topk=5,
        root=ROOT,
        force_stub=True,
        embed_fn=emb.embed_texts,
    )
    note_path = write_retrieval_note(
        "knowledge-smoke",
        "CVRP capacity OR-Tools",
        mode="hybrid",
        topk=5,
        root=ROOT,
        artifact=hyb_art,
    )
    return {
        "ok": True,
        "seed_hits": len(seed_art.hits),
        "hybrid_hits": len(hyb_art.hits),
        "note": str(note_path),
        "hybrid_chunk_ids": [h.chunk_id for h in hyb_art.hits],
    }


def step_cognee() -> dict:
    from knowledge_svc.cognee_client import CogneeClient

    return CogneeClient().smoke()


def step_mineru() -> dict:
    from knowledge_svc.mineru_client import MinerUClient

    return MinerUClient(root=ROOT).smoke()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="OR-Path knowledge smoke")
    p.add_argument(
        "--step",
        choices=["seed", "ingest", "retrieve", "cognee", "mineru", "all"],
        default="all",
    )
    args = p.parse_args(argv)

    steps = {
        "seed": step_seed,
        "ingest": step_ingest,
        "retrieve": step_retrieve,
        "cognee": step_cognee,
        "mineru": step_mineru,
    }
    order = list(steps) if args.step == "all" else [args.step]
    # retrieve needs ingest first when all
    if args.step == "all":
        order = ["seed", "ingest", "retrieve", "mineru", "cognee"]

    failed = []
    results = {}
    for name in order:
        try:
            results[name] = steps[name]()
            _print(name, results[name])
        except Exception as e:
            failed.append(name)
            results[name] = {"ok": False, "error": str(e)}
            _print(name, results[name])

    summary = {"failed": failed, "ok": not failed}
    _print("summary", summary)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
