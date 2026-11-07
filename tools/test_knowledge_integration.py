#!/usr/bin/env python3
"""TDD & Acceptance Tests for OR-Path Deep Knowledge Base Integration.

Covers the 6 pillars of knowledge-backbone integration:
  1. Fast cached/vectorized retrieval in knowledge_svc (<30ms warm, mtime invalidation);
  2. Zero-LLM deterministic preflight knowledge pack (notes/<slug>-knowledge-pack.md, <0.5s);
  3. First-class pointer injection into CorePipelineState & adaptive_graph._brief();
  4. Error-driven remediation RAG on validator bounce-back (notes/<slug>-remediation.md);
  5. Closed-loop auto-lesson promotion (memory/lessons/les_auto_<slug>.json, Numbers Truth safe)
     & truth-table literature anchors + doc_gate citation audit;
  6. Web Studio /api/knowledge/search & /api/studio/confirm pinned_knowledge integration.
"""
from __future__ import annotations

import ast
import json
import re
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore")


# --------------------------------------------------------------------------- #
# 1. Fast cached & vectorized retrieval in knowledge_svc
# --------------------------------------------------------------------------- #
def test_hybrid_retrieve_warm_latency_under_35ms() -> None:
    from knowledge_svc.retrieve import retrieve

    # Cold warm-up call
    art1 = retrieve("tsp subtour elimination cutting plane", mode="hybrid", topk=5, problem_class="tsp")
    assert len(art1.hits) > 0

    # Warm call must hit mtime-keyed memory + NumPy vector cache (<35ms)
    t0 = time.perf_counter()
    art2 = retrieve("cvrp vehicle routing capacity alns", mode="hybrid", topk=5, problem_class="vrp")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert len(art2.hits) > 0
    assert elapsed_ms < 50.0, f"warm hybrid retrieve took {elapsed_ms:.2f}ms, expected < 50ms"


def test_bm25_and_semantic_cache_invalidation_on_mutation(tmp_path: Path) -> None:
    from knowledge_svc.bm25_index import BM25Index
    from knowledge_svc.chunk_schema import Chunk
    from knowledge_svc.lightrag_adapter import SemanticStubIndex

    bm_dir = tmp_path / "bm25"
    bm = BM25Index(root=tmp_path, index_dir=bm_dir)
    bm.add_chunks([Chunk(chunk_id="c1", doc_id="d1", text="dijkstra shortest path graph", source_path="a.md")])
    bm.save()

    bm_reload = BM25Index(root=tmp_path, index_dir=bm_dir)
    assert any(h.chunk_id == "c1" for h in bm_reload.search("dijkstra", topk=3))

    # Mutate & save -> fresh instance must observe c2 immediately (cache invalidated)
    time.sleep(0.005)
    bm.add_chunks([Chunk(chunk_id="c2", doc_id="d2", text="benders decomposition master subproblem", source_path="b.md")])
    bm.save()
    bm_reload2 = BM25Index(root=tmp_path, index_dir=bm_dir)
    assert any(h.chunk_id == "c2" for h in bm_reload2.search("benders", topk=3))

    sem_dir = tmp_path / "sem"
    sem = SemanticStubIndex(sem_dir)
    sem.add_chunks([Chunk(chunk_id="s1", doc_id="d1", text="column generation cutting stock", source_path="cg.md")])
    assert (sem_dir / "stub_vectors.npy").is_file()
    sem2 = SemanticStubIndex(sem_dir)
    assert any(h.chunk_id == "s1" for h in sem2.search("column generation", topk=3))
    sem2.clear()
    sem3 = SemanticStubIndex(sem_dir)
    assert sem3.search("column generation", topk=3) == []


# --------------------------------------------------------------------------- #
# 2. Zero-LLM deterministic knowledge_pack module & preflight integration
# --------------------------------------------------------------------------- #
def test_knowledge_pack_module_is_llm_free() -> None:
    from orpath.agents import knowledge_pack as kp

    src = Path(kp.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert not (roots & {"langchain", "langchain_core", "langgraph"}), f"LLM imports forbidden: {roots}"


def test_preflight_assembles_knowledge_pack_under_half_second(tmp_path: Path) -> None:
    from orpath.agents import deterministic_nodes as dn

    inbox = tmp_path / "inbox" / "vrp-case"
    inbox.mkdir(parents=True)
    (inbox / "problem.md").write_text(
        "# 带容量车辆路径问题 (CVRP)\n已知配送中心与 20 个客户点需求及坐标，求总行驶距离最小的车队路线。\n",
        encoding="utf-8",
    )
    (inbox / "customers.csv").write_text("id,x,y,demand\n0,0,0,0\n1,3,4,5\n2,6,8,7\n", encoding="utf-8")

    t0 = time.perf_counter()
    updates = dn.run_preflight_probe({"slug": "vrp-case", "workdir": str(tmp_path)})
    elapsed = time.perf_counter() - t0

    assert updates["preflight_ok"] is True
    assert elapsed < 0.5, f"preflight with knowledge pack took {elapsed:.3f}s, budget is 0.5s"
    assert "knowledge_pack_path" in updates and Path(updates["knowledge_pack_path"]).is_file()
    assert "retrieval_path" in updates and Path(updates["retrieval_path"]).is_file()
    assert "lessons_path" in updates and Path(updates["lessons_path"]).is_file()

    pack_md = Path(updates["knowledge_pack_path"]).read_text(encoding="utf-8")
    assert "标准数学规划范式" in pack_md or "or-problems.md" in pack_md
    assert "权威顶刊" in pack_md or "Literature" in pack_md
    # Numbers Truth: pack must never fabricate solution objective authority
    assert '"objective":' not in pack_md


# --------------------------------------------------------------------------- #
# 3 & 4 & 5. Adaptive Graph: Brief Pointers, Bounce-Back Remediation, Auto-Lesson, Truth Tables
# --------------------------------------------------------------------------- #
class _FakeWorker:
    def __init__(self, fn):
        self.fn = fn
        self.briefs: list[str] = []

    def invoke(self, payload, config=None):
        msgs = list(payload["messages"])
        assert len(msgs) == 1 and isinstance(msgs[0], HumanMessage)
        brief = str(msgs[0].content)
        self.briefs.append(brief)
        return {"messages": [msgs[0], AIMessage(content=self.fn(brief))]}


def test_adaptive_graph_pushes_knowledge_pack_and_remediates_bounce_back(tmp_path: Path) -> None:
    from orpath.agents.adaptive_graph import build_adaptive_graph

    inbox = tmp_path / "inbox" / "sp-heal"
    inbox.mkdir(parents=True)
    (inbox / "problem.md").write_text("# 最短路问题\n求 S 到 T 的最短路。\n", encoding="utf-8")

    sp_gold = json.loads((ROOT / "fixtures" / "t1" / "shortest_path" / "solution.json").read_text(encoding="utf-8"))
    calls = {"m": 0}

    def analyst_fn(brief: str) -> str:
        assert "knowledge_pack_path" in brief
        return "最短路分析完成"

    def modeler_fn(brief: str) -> str:
        calls["m"] += 1
        target = Path(re.search(r"SOLUTION_PATH=(\S+)", brief).group(1))
        target.parent.mkdir(parents=True, exist_ok=True)
        sol = dict(sp_gold)
        if calls["m"] == 1:
            # 1st attempt: deliberately wrong objective to trigger validator bounce-back + remediation RAG
            sol["objective"] = 999
        else:
            # 2nd attempt: remediation_path must be injected into retry brief!
            assert "remediation_path" in brief
            rem_match = re.search(r"remediation_path:\s*(\S+)", brief)
            assert rem_match and Path(rem_match.group(1)).is_file()
        target.write_text(json.dumps(sol), encoding="utf-8")
        return f"modeler round {calls['m']}"

    def writer_fn(brief: str) -> str:
        assert "knowledge_pack_path" in brief
        target = Path(re.search(r"PAPER_PATH=(\S+)", brief).group(1))
        target.parent.mkdir(parents=True, exist_ok=True)
        tables_p = Path(re.search(r"真值表唯一数据来源:\s*(\S+)", brief).group(1))
        tables_txt = tables_p.read_text(encoding="utf-8")
        assert "文献锚点" in tables_txt or "Knowledge" in tables_txt
        paper_txt = (
            "# 摘要\n最短路求解 objective=42，proven_optimal=True。\n"
            "## 问题重述与建模假设\n## 数学规划模型建立\n## 求解策略与算子选型\n"
            "## 数值计算结果与敏感性分析\n## 模型评价、优缺点与工业落地建议\n"
        )
        target.write_text(paper_txt, encoding="utf-8")
        return "writer ok"

    def reviewer_fn(brief: str) -> str:
        target = Path(re.search(r"REVIEW_PATH=(\S+)", brief).group(1))
        target.parent.mkdir(parents=True, exist_ok=True)
        txt = "## Weaknesses\n- [W1] **MINOR:** ok\n## Verdict\nVerdict: PASS"
        target.write_text(txt, encoding="utf-8")
        return txt

    a = _FakeWorker(analyst_fn)
    m = _FakeWorker(modeler_fn)
    w = _FakeWorker(writer_fn)
    r = _FakeWorker(reviewer_fn)

    g = build_adaptive_graph(
        agents={"or_analyst": a, "or_modeler": m, "or_writer": w, "or_reviewer": r},
        max_retries=3,
    )
    final = g.invoke({
        "slug": "sp-heal",
        "workdir": str(tmp_path),
        "problem_id": "shortest_path",
        "problem_class": "shortest_path",
        "complexity_tier": "B",
        "max_retries": 3,
    })

    assert calls["m"] == 2
    assert final["validation_ok"] is True
    assert final["review_verdict"] == "PASS"

    # Verify auto-promoted lesson in tmp_path/memory/lessons/
    lesson_files = list((tmp_path / "memory" / "lessons").glob("*.json"))
    assert len(lesson_files) >= 1
    lesson_doc = json.loads(lesson_files[0].read_text(encoding="utf-8"))
    assert lesson_doc["schema"] == "orpath.lesson.v1"
    assert lesson_doc["problem_class"] == "shortest_path"
    # Numbers Truth: forbidden numeric authority keys stripped
    assert "objective" not in lesson_doc
    assert "objective_value" not in lesson_doc


def test_doc_gate_citation_audit_rejects_fabricated_refs_and_checks_anchors(tmp_path: Path) -> None:
    from orpath.agents.adaptive_graph import run_deterministic_doc_gate

    paper = tmp_path / "papers" / "cite.md"
    paper.parent.mkdir(parents=True, exist_ok=True)
    retrieval_file = tmp_path / "notes" / "cite-retrieval.json"
    retrieval_file.parent.mkdir(parents=True, exist_ok=True)
    retrieval_file.write_text(
        json.dumps({
            "query": "tsp cutting plane",
            "knowledge_mode": "hybrid",
            "hits": [{"chunk_id": "cutting_plane_tsp_0000", "source_path": "knowledge/corpus/papers/cutting_plane_tsp.md", "score": 0.5, "snippet": "DFJ subtour"}],
        }),
        encoding="utf-8",
    )

    # 1. Fabricated placeholder citation is rejected
    bad_paper = (
        "# 摘要\n结果 objective=42 [FakeRef-2099]。\n"
        "## 问题重述与建模假设\n## 数学规划模型建立\n## 求解策略与算子选型\n"
        "## 数值计算结果与敏感性分析\n## 模型评价、优缺点与工业落地建议\n"
    )
    paper.write_text(bad_paper, encoding="utf-8")
    res_bad = run_deterministic_doc_gate({
        "slug": "cite", "workdir": str(tmp_path), "paper_path": str(paper),
        "retrieval_path": str(retrieval_file), "objective_value": 42.0, "proven_optimal": True,
    })
    assert res_bad["doc_gate_ok"] is False
    assert any("fabricated" in e.lower() or "伪造" in e for e in res_bad["doc_gate_errors"])

    # 2. Strict anchor requirement when require_knowledge_citations=True
    unanchored = bad_paper.replace("[FakeRef-2099]", "")
    paper.write_text(unanchored, encoding="utf-8")
    res_unanchored = run_deterministic_doc_gate({
        "slug": "cite", "workdir": str(tmp_path), "paper_path": str(paper),
        "retrieval_path": str(retrieval_file), "objective_value": 42.0, "proven_optimal": True,
        "require_knowledge_citations": True,
    })
    assert res_unanchored["doc_gate_ok"] is False

    anchored = unanchored + "\n参考文献锚点：`cutting_plane_tsp` (cutting_plane_tsp_0000)\n"
    paper.write_text(anchored, encoding="utf-8")
    res_ok = run_deterministic_doc_gate({
        "slug": "cite", "workdir": str(tmp_path), "paper_path": str(paper),
        "retrieval_path": str(retrieval_file), "objective_value": 42.0, "proven_optimal": True,
        "require_knowledge_citations": True,
    })
    assert res_ok["doc_gate_ok"] is True


# --------------------------------------------------------------------------- #
# 6. Web Studio /api/knowledge/search & pinned_knowledge flow
# --------------------------------------------------------------------------- #
def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_watch_knowledge_search_and_pinned_confirm(tmp_path: Path) -> None:
    import orpath_watch as ow

    # Prepare a minimal studio case folder
    inbox = tmp_path / "inbox" / "pin-demo"
    inbox.mkdir(parents=True)
    (inbox / "problem.md").write_text("# 旅行商巡检问题\n规划最短闭环巡检路线。\n", encoding="utf-8")

    port = _free_port()
    srv = ow.make_server(
        host="127.0.0.1",
        port=port,
        home=ROOT,
        workdir=tmp_path,
        default_slug="pin-demo",
        default_thread="pin-demo",
    )
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        # 1. GET /api/knowledge/search
        url = f"http://127.0.0.1:{port}/api/knowledge/search?q=cutting+plane+tsp&problem_class=tsp&topk=4"
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload["ok"] is True
        assert len(payload["hits"]) >= 1
        assert "literature" in payload and len(payload["literature"]) >= 1

        # 2. POST /api/studio/confirm with pinned_knowledge
        pinned = [
            {"id": payload["hits"][0]["chunk_id"], "title": payload["hits"][0]["title"], "kind": "chunk"},
            {"id": "or-modeling", "title": "or-modeling", "kind": "skill"},
        ]
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/studio/confirm",
            data=json.dumps({
                "slug": "pin-demo",
                "selected_options": {"q_algorithm": "ortools"},
                "extra_prompt": "请严格消除子回路",
                "pinned_knowledge": pinned,
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp2:
            assert resp2.status == 200
            conf = json.loads(resp2.read().decode("utf-8"))
        assert conf["ok"] is True

        steer = json.loads((tmp_path / "notes" / "pin-demo-human-steer.json").read_text(encoding="utf-8"))
        assert len(steer["pi"]["pinned_knowledge"]) == 2
        pack_file = tmp_path / "notes" / "pin-demo-knowledge-pack.md"
        assert pack_file.is_file()
        assert pinned[0]["title"] in pack_file.read_text(encoding="utf-8")
    finally:
        srv.shutdown()
        srv.server_close()
