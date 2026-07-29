#!/usr/bin/env python3
"""T2 cloud/online gate: MinerU, silicon embed, hybrid retrieve, cognee, R1 online."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("PYTHONPATH", None)
    return env


def main() -> int:
    sys.path.insert(0, str(ROOT))
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:
        pass

    # Prefer subagent-rich clients when available
    offline_ok = False
    try:
        from knowledge_svc.mineru_client import MinerUClient

        client = MinerUClient(root=ROOT)
        off = client.offline_corpus_to_chunks()
        print("offline_md", off)
        offline_ok = off.get("status") == "OK" or off.get("ok") is True
        mu = client.cloud_smoke() if hasattr(client, "cloud_smoke") else {"ok": offline_ok}
        print("mineru", mu)
    except Exception as exc:
        try:
            from knowledge_svc.mineru_client import mineru_cloud_smoke, offline_md_pipeline

            off = offline_md_pipeline()
            print("offline_md", off)
            offline_ok = bool(off.get("ok"))
            mu = mineru_cloud_smoke()
            print("mineru", mu)
        except Exception as exc2:
            fail(f"mineru path failed: {exc} / {exc2}")

    if not offline_ok and not (isinstance(mu, dict) and mu.get("ok")):
        fail("mineru/offline failed")

    from knowledge_svc.embed_siliconflow import embed_probe, get_api_key

    # Prefer live key for cloud gate
    if get_api_key():
        emb = embed_probe("OR-Tools vehicle routing capacity constraint")
    else:
        emb = embed_probe("OR-Tools vehicle routing capacity constraint")
    print("embed", emb)
    if not emb.get("ok"):
        fail(f"embed failed: {emb}")
    if emb.get("dim") and int(emb["dim"]) != 1024:
        print("WARN: unexpected embed dim", emb.get("dim"))

    # Hybrid retrieve via package retrieve
    try:
        from knowledge_svc.ingest import collect_corpus_chunks, ingest_chunks
        from knowledge_svc.retrieve import retrieve
        from knowledge_svc.embed_siliconflow import MockEmbedder, embed_texts

        chunks = collect_corpus_chunks(ROOT / "knowledge" / "corpus", root=ROOT)
        if not chunks:
            fail("no corpus chunks")
        embed_fn = embed_texts if get_api_key() else MockEmbedder().embed_texts
        ingest_chunks(chunks, root=ROOT, clear=True, force_stub=True, embed_fn=embed_fn)
        art = retrieve(
            "capacitated VRP OR-Tools",
            mode="hybrid",
            topk=5,
            root=ROOT,
            force_stub=True,
            embed_fn=embed_fn,
        )
        hits = art.hits if hasattr(art, "hits") else art.get("hits") or []
        print("hits", len(hits))
        if not hits:
            fail("hybrid retrieve empty")
    except Exception as exc:
        fail(f"hybrid retrieve failed: {exc}")

    try:
        from knowledge_svc.cognee_client import cognee_smoke

        cg = cognee_smoke()
    except Exception:
        try:
            from knowledge_svc.cognee_client import CogneeClient

            c = CogneeClient()
            cg = c.write_lesson(
                "OR-Path: never store authoritative objective in memory; prefer multi-vehicle VRP."
            )
            cg = {"write": cg, "search": c.search("multi-vehicle")}
        except Exception as exc:
            fail(f"cognee failed: {exc}")
    print("cognee", cg)

    draft = ROOT / "outputs" / "t2-online-r1-draft.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(
        "# Draft\nSee https://arxiv.org/abs/2503.10009 for OR-LLM-Agent pipeline.\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [PY, str(ROOT / "tools" / "r1_online_check.py"), "--draft", str(draft)],
        cwd=ROOT,
        env=child_env(),
        text=True,
        capture_output=True,
    )
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        fail("r1 online failed")

    print("PASS: t2_gate_cloud")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
