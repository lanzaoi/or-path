"""Unit tests for knowledge_svc (no network required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from knowledge_svc.bm25_index import BM25Index
from knowledge_svc.chunk_schema import (
    Chunk,
    RetrievalArtifact,
    RetrievalHit,
    chunk_markdown,
    stable_chunk_id,
)
from knowledge_svc.cognee_client import CogneeClient, assert_safe_memory_text
from knowledge_svc.embed_siliconflow import MockEmbedder, cosine_similarity
from knowledge_svc.fts_index import FTSIndex
from knowledge_svc.ingest import collect_corpus_chunks, ingest_chunks
from knowledge_svc.lightrag_adapter import LightRAGAdapter
from knowledge_svc.mineru_client import MinerUClient
from knowledge_svc.notes_helper import citation_ids, write_retrieval_note
from knowledge_svc.retrieve import retrieve
from knowledge_svc.rrf_fuse import fuse_semantic_lexical, rrf_fuse
from knowledge_svc.seed_graph_query import load_seed, query_by_class, stats


@pytest.fixture()
def tmp_knowledge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated knowledge/ tree under tmp_path."""
    (tmp_path / "knowledge" / "seed_graph").mkdir(parents=True)
    (tmp_path / "knowledge" / "corpus").mkdir(parents=True)
    (tmp_path / "knowledge" / "chunks").mkdir(parents=True)
    (tmp_path / "knowledge" / "bm25").mkdir(parents=True)
    (tmp_path / "knowledge" / "fts").mkdir(parents=True)
    (tmp_path / "knowledge" / "lightrag_ws").mkdir(parents=True)
    (tmp_path / "notes").mkdir(parents=True)
    # copy seed
    src = ROOT / "knowledge" / "seed_graph" / "or_domain_seed.json"
    (tmp_path / "knowledge" / "seed_graph" / "or_domain_seed.json").write_text(
        src.read_text(encoding="utf-8"), encoding="utf-8"
    )
    # sample md
    (tmp_path / "knowledge" / "corpus" / "sample.md").write_text(
        "# Dijkstra sample\n\n"
        "Shortest path with Dijkstra and NetworkX on non-negative weights.\n\n"
        "CVRP capacity OR-Tools multi vehicle routing.\n",
        encoding="utf-8",
    )
    return tmp_path


def test_seed_graph_stats_and_query():
    g = load_seed(ROOT / "knowledge" / "seed_graph" / "or_domain_seed.json")
    st = stats(g)
    assert st["node_count"] >= 10
    assert st["edge_count"] >= 10
    assert st["by_type"].get("ProblemClass", 0) >= 3
    assert st["by_type"].get("Solver", 0) >= 2
    tsp = query_by_class("tsp", g)
    assert tsp
    assert any(s.get("label") == "ortools_routing" for s in tsp[0]["solvers"])
    vrp = query_by_class("vrp", g)
    assert vrp
    assert any(c.get("label") == "capacity" for c in vrp[0]["constraints"])
    sp = query_by_class("shortest_path", g)
    assert sp
    assert any(s.get("label") == "networkx_dijkstra" for s in sp[0]["solvers"])


def test_chunk_markdown_stable_ids():
    chunks = chunk_markdown(
        "Hello world.\n\nSecond paragraph about TSP tour modeling.",
        doc_id="docA",
        source_path="knowledge/corpus/docA.md",
        title="Doc A",
    )
    assert chunks
    assert chunks[0].chunk_id == stable_chunk_id("docA", chunks[0].text, 0)
    d = chunks[0].to_dict()
    assert d["chunk_id"] and d["text"]


def test_bm25_roundtrip(tmp_knowledge: Path):
    idx = BM25Index(root=tmp_knowledge, index_dir=tmp_knowledge / "knowledge" / "bm25")
    chunks = [
        Chunk("c1", "d1", "Dijkstra shortest path networkx", "a.md"),
        Chunk("c2", "d1", "CVRP capacity constraint ortools routing", "b.md"),
    ]
    idx.add_chunks(chunks)
    idx.save()
    idx2 = BM25Index(root=tmp_knowledge, index_dir=tmp_knowledge / "knowledge" / "bm25")
    assert idx2.load()
    hits = idx2.search("Dijkstra networkx", topk=2)
    assert hits
    assert hits[0].chunk_id == "c1"
    assert hits[0].backend == "bm25"


def test_fts_search(tmp_knowledge: Path):
    fts = FTSIndex(root=tmp_knowledge, index_dir=tmp_knowledge / "knowledge" / "fts")
    fts.clear()
    fts.add_chunks(
        [
            Chunk("f1", "d", "vehicle routing capacity OR-Tools", "x.md"),
            Chunk("f2", "d", "assignment bipartite matching", "y.md"),
        ]
    )
    hits = fts.search("capacity routing", topk=5)
    assert hits
    assert any(h.chunk_id == "f1" for h in hits)


def test_rrf_fuse_order():
    a = [
        RetrievalHit("x", 1.0, "lightrag", "sx"),
        RetrievalHit("y", 0.9, "lightrag", "sy"),
    ]
    b = [
        RetrievalHit("y", 5.0, "bm25", "sy"),
        RetrievalHit("z", 4.0, "bm25", "sz"),
    ]
    fused = fuse_semantic_lexical(a, b, w_semantic=1.0, w_lexical=0.4, topk=3)
    assert fused
    assert fused[0].backend == "rrf"
    ids = [h.chunk_id for h in fused]
    assert "y" in ids
    # y appears in both lists → should rank well
    assert ids.index("y") <= 1


def test_rrf_empty():
    assert rrf_fuse([]) == []
    assert fuse_semantic_lexical([], []) == []


def test_mock_embedder_cosine():
    m = MockEmbedder(dim=1024)
    v1 = m.embed_query("hello dijkstra")
    v2 = m.embed_query("hello dijkstra")
    v3 = m.embed_query("completely different tsp routing")
    assert len(v1) == 1024
    assert cosine_similarity(v1, v2) > 0.99
    assert cosine_similarity(v1, v3) < cosine_similarity(v1, v2)


def test_ingest_and_hybrid_retrieve(tmp_knowledge: Path):
    chunks = collect_corpus_chunks(
        tmp_knowledge / "knowledge" / "corpus", root=tmp_knowledge
    )
    assert chunks
    embedder = MockEmbedder()
    result = ingest_chunks(
        chunks,
        root=tmp_knowledge,
        clear=True,
        force_stub=True,
        embed_fn=embedder.embed_texts,
    )
    assert result["n_chunks"] >= 1
    # same chunk_ids dual-written
    assert result["bm25"] == result["fts"] == result["semantic"]

    art = retrieve(
        "Dijkstra NetworkX shortest path",
        mode="hybrid",
        topk=5,
        root=tmp_knowledge,
        force_stub=True,
        embed_fn=embedder.embed_texts,
    )
    assert art.knowledge_mode == "hybrid"
    assert isinstance(art.hits, list)
    # should find something from corpus
    assert len(art.hits) >= 1
    assert all(h.chunk_id for h in art.hits)


def test_seed_mode_retrieve(tmp_knowledge: Path):
    # patch seed path via root
    art = retrieve(
        "tsp ortools routing",
        mode="seed",
        topk=5,
        root=tmp_knowledge,
        problem_class="tsp",
    )
    assert art.knowledge_mode == "seed"
    assert art.seed_facts
    assert art.hits  # seed hits


def test_ingest_from_real_corpus_md():
    """Offline path: curated md under knowledge/corpus exists and chunks."""
    corpus = ROOT / "knowledge" / "corpus"
    files = list(corpus.glob("*.md"))
    assert len(files) >= 2
    texts = " ".join(f.read_text(encoding="utf-8") for f in files)
    assert "Dijkstra" in texts or "dijkstra" in texts.lower()
    assert "CVRP" in texts or "VRP" in texts or "vrp" in texts.lower()
    assert "2503.10009" in texts
    chunks = collect_corpus_chunks(corpus, root=ROOT)
    assert len(chunks) >= 2


def test_mineru_offline(tmp_knowledge: Path):
    client = MinerUClient(root=tmp_knowledge, token=None)
    out = client.offline_corpus_to_chunks()
    assert out["status"] == "OK"
    assert out["n_chunks"] >= 1
    assert Path(out["chunks_jsonl"]).is_file()


def test_cognee_rejects_objective():
    with pytest.raises(ValueError):
        assert_safe_memory_text('solution objective is 42 with "tour": ["0","1"]')
    c = CogneeClient(api_key=None, base_url=None, use_env=False)
    r = c.write_lesson("Prefer multi-vehicle VRP; never trust memory for optima.")
    assert r["status"] in {"LOCAL_OK", "LOCAL_FALLBACK", "OK"}
    s = c.search("multi-vehicle")
    assert s.get("hits") is not None or s.get("status") in {
        "OK",
        "LOCAL_OK",
        "LOCAL_FALLBACK",
    }
    assert s.get("hits")


def test_notes_helper(tmp_knowledge: Path):
    path = write_retrieval_note(
        "unit-test",
        "vrp capacity",
        mode="seed",
        topk=5,
        problem_class="vrp",
        root=tmp_knowledge,
    )
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    art = RetrievalArtifact.from_dict(data)
    assert art.knowledge_mode == "seed"
    ids = citation_ids(art)
    assert ids


def test_lightrag_stub(tmp_knowledge: Path):
    emb = MockEmbedder()
    rag = LightRAGAdapter(
        root=tmp_knowledge,
        work_dir=tmp_knowledge / "knowledge" / "lightrag_ws",
        force_stub=True,
        embed_fn=emb.embed_texts,
    )
    rag.add_chunks(
        [Chunk("s1", "d", "OR-Tools capacitated vehicle routing capacity", "z.md")]
    )
    hits = rag.search("OR-Tools capacity VRP", topk=3)
    assert hits
    assert hits[0].backend == "lightrag"
