"""Product pipeline node bodies (T3): orpath.nodes + bridge + NodeContext hooks."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orpath import nodes as n2
from orpath.node_context import wrap_node
from orpath.pi_bridge import bridge_smoke, maybe_annotate_live
from orpath.state import ORPathState


def node_bridge_pi(state: ORPathState) -> dict[str, Any]:
    """In-graph Pi bridge. Hard-fail when live_pi and bridge fails."""
    root = Path(state["root"])
    slug = state["slug"]
    live = bool(state.get("live_pi"))
    if not live:
        return {
            "stage": "research"
            if (state.get("bridge_attachment") or "before_research") == "before_research"
            else "retrieve",
            "bridge_skipped": True,
            "bridge_ok": True,
            "bridge_path": "",
            "last_error": "",
        }

    try:
        # Prefer smoke evidence; annotate when available
        info = bridge_smoke(root, slug)
        maybe_annotate_live(root, slug)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"bridge_pi hard fail: {exc}") from exc

    if not info.get("ok", True) and info.get("ok") is False:
        raise RuntimeError(f"bridge_pi hard fail: {info}")

    out_path = root / "outputs" / f"{slug}-bridge.json"
    out_path.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    att = state.get("bridge_attachment") or "before_research"
    next_stage = "research" if att == "before_research" else "retrieve"
    return {
        "stage": next_stage,
        "bridge_skipped": False,
        "bridge_ok": True,
        "bridge_path": str(out_path),
        "last_error": "",
    }


def _after_orchestrate_stage(state: ORPathState) -> dict[str, Any]:
    out = n2.node_orchestrate(state)
    att = state.get("bridge_attachment") or "before_research"
    # orchestrate sets stage=retrieve; if bridge before retrieve, mark pending bridge
    if att == "before_retrieve":
        out = {**out, "stage": "bridge_pi"}
    return out


def _after_retrieve_stage(state: ORPathState) -> dict[str, Any]:
    out = n2.node_retrieve(state)
    att = state.get("bridge_attachment") or "before_research"
    if att == "before_research":
        out = {**out, "stage": "bridge_pi"}
    else:
        out = {**out, "stage": "research"}
    return out


# Wrapped product nodes (snapshot + manifest + owner)
node_orchestrate = wrap_node("orchestrate", _after_orchestrate_stage)
node_retrieve = wrap_node("retrieve", _after_retrieve_stage)
node_bridge_pi_w = wrap_node("bridge_pi", node_bridge_pi)
node_research = wrap_node("research", n2.node_research)
node_model = wrap_node("model", n2.node_model)
node_gate_schema = wrap_node("gate_schema", n2.node_gate_schema)
node_solve = wrap_node("solve", n2.node_solve)
node_gate_validate = wrap_node("gate_validate", n2.node_gate_validate)
node_human_stop = wrap_node("human_stop", n2.node_human_stop)
node_explain = wrap_node("explain", n2.node_explain)
node_draft_paper = wrap_node("draft_paper", n2.node_draft_paper)
node_cite_pack = wrap_node("cite_pack", n2.node_cite_pack)
node_review_pack = wrap_node("review_pack", n2.node_review_pack)
node_revise_or_done = wrap_node("revise_or_done", n2.node_revise_or_done)


def _provenance_thick(state: ORPathState) -> dict[str, Any]:
    out = n2.node_provenance(state)
    # append T3 skeleton fields into provenance file
    prov = Path(out["provenance_path"])
    extra = [
        "",
        "## T3 skeleton",
        f"- thread_id: {state.get('thread_id')}",
        f"- bridge_attachment: {state.get('bridge_attachment')}",
        f"- bridge_path: {state.get('bridge_path')}",
        f"- bridge_ok: {state.get('bridge_ok')}",
        f"- bridge_skipped: {state.get('bridge_skipped')}",
        f"- runs_dir: {state.get('runs_dir')}",
        f"- artifact_manifest_path: {state.get('artifact_manifest_path')}",
        f"- last_snapshot_path: {state.get('last_snapshot_path')}",
        f"- orpath_checkpoint_id: {state.get('orpath_checkpoint_id')}",
        f"- pipeline: product",
    ]
    with prov.open("a", encoding="utf-8") as f:
        f.write("\n".join(extra) + "\n")
    return out


node_provenance = wrap_node("provenance", _provenance_thick)

# public alias used by graph
node_bridge = node_bridge_pi_w
