#!/usr/bin/env python3
"""OR-Path product runner (T3): checkpointer, resume, from-stage, status/list."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.graph_product import (  # noqa: E402
    PRODUCT_NODES,
    build_graph_product,
    open_sqlite_checkpointer,
    write_stage_map_files,
)
from orpath.node_context import dirty_artifacts, thread_dir  # noqa: E402

_PREDECESSORS = {
    "retrieve": "orchestrate",
    "bridge_pi": "retrieve",
    "research": "bridge_pi",
    "model": "research",
    "gate_schema": "model",
    "solve": "gate_schema",
    "gate_validate": "solve",
    "explain": "gate_validate",
    "draft_paper": "explain",
    "cite_pack": "draft_paper",
    "review_pack": "cite_pack",
    "revise_or_done": "review_pack",
    "provenance": "revise_or_done",
}


def _default_initial(
    *,
    root: Path,
    slug: str,
    problem_id: str,
    problem_class: str,
    solve_mode: str,
    knowledge_mode: str,
    live_pi: bool,
    live_subagent: bool | None,
    thread_id: str,
    bridge_attachment: str,
) -> dict[str, Any]:
    return {
        "slug": slug,
        "problem_id": problem_id,
        "problem_class": problem_class,
        "solve_mode": solve_mode,
        "knowledge_mode": knowledge_mode,
        "root": str(root),
        "stage": "start",
        "revise_count": 0,
        "max_revise": 2,
        "schema_repair": 0,
        "max_schema_repair": 2,
        "validate_repair": 0,
        "max_validate_repair": 2,
        "solver_tune": 0,
        "max_solver_tune": 3,
        "human_required": False,
        "schema_path": "",
        "solution_path": "",
        "validate_path": "",
        "research_path": "",
        "retrieval_path": "",
        "explain_path": "",
        "paper_path": "",
        "review_path": "",
        "provenance_path": "",
        "plan_path": "",
        "cited_path": "",
        "last_error": "",
        "gate_schema_ok": False,
        "gate_validate_ok": False,
        "gate_r1_ok": False,
        "gate_r2_ok": False,
        "gate_subagent_ok": None,
        "review_fatal": 0,
        "live_pi": bool(live_pi),
        "live_subagent": live_subagent,
        "thread_id": thread_id,
        "bridge_attachment": bridge_attachment,
        "bridge_path": "",
        "bridge_ok": False,
        "bridge_skipped": True,
        "orpath_checkpoint_id": "",
        "runs_dir": str(root / "runs" / thread_id),
        "artifact_manifest_path": "",
        "last_snapshot_path": "",
        "pipeline": "product",
    }


def _db_path(root: Path) -> Path:
    return root / "runs" / "orpath.sqlite"


def _config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def cmd_list(root: Path) -> int:
    runs = root / "runs"
    if not runs.is_dir():
        print(json.dumps({"threads": []}, indent=2))
        return 0
    threads = []
    for p in sorted(runs.iterdir()):
        if p.is_dir() and p.name != "__pycache__":
            latest = p / "latest_snapshot.json"
            meta = {}
            if latest.is_file():
                try:
                    meta = json.loads(latest.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    meta = {}
            threads.append(
                {
                    "thread_id": p.name,
                    "stage": meta.get("stage"),
                    "slug": meta.get("slug"),
                    "human_required": meta.get("human_required"),
                }
            )
    print(json.dumps({"threads": threads}, indent=2, ensure_ascii=False))
    return 0


def cmd_status(root: Path, thread_id: str) -> int:
    td = root / "runs" / thread_id
    latest = td / "latest_snapshot.json"
    man = td / "artifact_hashes.json"
    out: dict[str, Any] = {
        "thread_id": thread_id,
        "runs_dir": str(td),
        "exists": td.is_dir(),
    }
    if latest.is_file():
        out["latest"] = json.loads(latest.read_text(encoding="utf-8"))
    if man.is_file():
        out["manifest"] = json.loads(man.read_text(encoding="utf-8"))
    try:
        saver, conn = open_sqlite_checkpointer(_db_path(root))
        cfg = _config(thread_id)
        tup = saver.get_tuple(cfg)
        if tup:
            out["orpath_checkpoint_id"] = getattr(tup.checkpoint, "id", None) or (
                tup.checkpoint.get("id") if isinstance(tup.checkpoint, dict) else None
            )
            out["checkpoint_ts"] = (
                tup.checkpoint.get("ts") if isinstance(tup.checkpoint, dict) else None
            )
        conn.close()
    except Exception as exc:  # noqa: BLE001
        out["checkpoint_error"] = str(exc)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("exists") else 1


def _load_state_from_checkpoint(app: Any, thread_id: str) -> dict[str, Any] | None:
    cfg = _config(thread_id)
    snap = app.get_state(cfg)
    if snap is None or snap.values is None:
        return None
    return dict(snap.values)


def _resolve_live_subagent(args: argparse.Namespace) -> bool | None:
    """CLI > env. None = defer to ORPATH_LIVE_SUBAGENT / check_env default."""
    if getattr(args, "no_live_subagent", False):
        os.environ["ORPATH_LIVE_SUBAGENT"] = "0"
        return False
    if getattr(args, "live_subagent", False) or bool(getattr(args, "live_pi", False)):
        os.environ.setdefault("ORPATH_LIVE_SUBAGENT", "1")
        return True
    return None


def cmd_run(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    write_stage_map_files(root)
    thread_id = args.thread_id or f"{args.slug or args.problem_id}-{uuid.uuid4().hex[:8]}"
    slug = args.slug or f"orpath-{args.problem_id}"

    saver, conn = open_sqlite_checkpointer(_db_path(root))
    app = build_graph_product(checkpointer=saver)
    cfg = _config(thread_id)

    if args.resume or args.from_stage:
        probe = {
            "root": str(root),
            "thread_id": thread_id,
            "slug": slug,
        }
        latest = root / "runs" / thread_id / "latest_snapshot.json"
        if latest.is_file():
            meta = json.loads(latest.read_text(encoding="utf-8"))
            for k, v in (meta.get("paths") or {}).items():
                probe[k] = v
        dirty = dirty_artifacts(probe)  # type: ignore[arg-type]
        if dirty and not args.fresh and not args.force:
            print(
                json.dumps(
                    {
                        "error": "dirty_artifacts",
                        "detail": dirty,
                        "hint": "pass --fresh or --force after reviewing hashes",
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            conn.close()
            return 3

    if args.fresh or not args.resume:
        live_sa = _resolve_live_subagent(args)
        initial = _default_initial(
            root=root,
            slug=slug,
            problem_id=args.problem_id,
            problem_class=args.problem_class or "",
            solve_mode=args.solve_mode,
            knowledge_mode=args.knowledge_mode,
            live_pi=bool(args.live_pi),
            live_subagent=live_sa,
            thread_id=thread_id,
            bridge_attachment=args.bridge_attachment,
        )
        if args.from_stage and not args.fresh:
            existing = _load_state_from_checkpoint(app, thread_id)
            if existing is None:
                print(
                    json.dumps(
                        {"error": "no_checkpoint_for_from_stage", "thread_id": thread_id}
                    ),
                    file=sys.stderr,
                )
                conn.close()
                return 1
            existing["stage"] = args.from_stage
            existing["thread_id"] = thread_id
            as_node = _PREDECESSORS.get(args.from_stage, "orchestrate")
            app.update_state(cfg, existing, as_node=as_node)
            final = app.invoke(None, cfg)
        else:
            final = app.invoke(initial, cfg)
    else:
        existing = _load_state_from_checkpoint(app, thread_id)
        if existing is None:
            print(
                json.dumps({"error": "nothing_to_resume", "thread_id": thread_id}),
                file=sys.stderr,
            )
            conn.close()
            return 1
        if args.from_stage:
            existing["stage"] = args.from_stage
            as_node = _PREDECESSORS.get(args.from_stage, "orchestrate")
            app.update_state(cfg, existing, as_node=as_node)
        final = app.invoke(None, cfg)

    try:
        tup = saver.get_tuple(cfg)
        cp_id = None
        if tup:
            cp = tup.checkpoint
            cp_id = getattr(cp, "id", None) or (cp.get("id") if isinstance(cp, dict) else None)
        if cp_id:
            td = thread_dir({"root": str(root), "thread_id": thread_id, "slug": slug})  # type: ignore[arg-type]
            (td / "checkpoint_id.txt").write_text(str(cp_id) + "\n", encoding="utf-8")
            prov = final.get("provenance_path")
            if prov and Path(prov).is_file():
                with Path(prov).open("a", encoding="utf-8") as f:
                    f.write(f"- orpath_checkpoint_id: {cp_id}\n")
            final = {**final, "orpath_checkpoint_id": str(cp_id)}
    except Exception:  # noqa: BLE001
        pass

    summary = {
        "thread_id": thread_id,
        "stage": final.get("stage"),
        "human_required": final.get("human_required"),
        "problem_class": final.get("problem_class"),
        "solve_mode": args.solve_mode,
        "gate_validate_ok": final.get("gate_validate_ok"),
        "gate_r1_ok": final.get("gate_r1_ok"),
        "gate_r2_ok": final.get("gate_r2_ok"),
        "gate_subagent_ok": final.get("gate_subagent_ok"),
        "live_subagent": final.get("live_subagent"),
        "solution_path": final.get("solution_path"),
        "validate_path": final.get("validate_path"),
        "paper_path": final.get("paper_path"),
        "provenance_path": final.get("provenance_path"),
        "bridge_path": final.get("bridge_path"),
        "bridge_skipped": final.get("bridge_skipped"),
        "runs_dir": final.get("runs_dir"),
        "artifact_manifest_path": final.get("artifact_manifest_path"),
        "last_snapshot_path": final.get("last_snapshot_path"),
        "orpath_checkpoint_id": final.get("orpath_checkpoint_id"),
        "last_error": final.get("last_error"),
        "solver_tune": final.get("solver_tune"),
        "product_nodes": PRODUCT_NODES,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    conn.close()
    if final.get("human_required"):
        return 2
    if not final.get("provenance_path"):
        return 1
    if not final.get("gate_validate_ok"):
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="OR-Path product runner (T3 LG skeleton)")
    sub = p.add_subparsers(dest="cmd")

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--root", type=Path, default=ROOT)
        sp.add_argument("--thread-id", default="")
        sp.add_argument("--problem-id", default="shortest_path")
        sp.add_argument("--problem-class", default="")
        sp.add_argument("--slug", default="")
        sp.add_argument(
            "--solve-mode",
            choices=("mock", "networkx", "ortools", "cpsat", "highs"),
            default="mock",
        )
        sp.add_argument(
            "--knowledge-mode", choices=("off", "seed", "hybrid"), default="seed"
        )
        sp.add_argument("--live-pi", action="store_true")
        sp.add_argument(
            "--live-subagent",
            action="store_true",
            help="force Pi subagent live for research/model/cite/review",
        )
        sp.add_argument(
            "--no-live-subagent",
            action="store_true",
            help="force deterministic path (no Pi subagent spawn)",
        )
        sp.add_argument(
            "--bridge-attachment",
            choices=("before_research", "before_retrieve"),
            default="before_research",
        )
        sp.add_argument("--resume", action="store_true")
        sp.add_argument("--fresh", action="store_true")
        sp.add_argument("--force", action="store_true", help="ignore dirty artifacts")
        sp.add_argument("--from-stage", default="", help="jump/replay from stage name")

    run_p = sub.add_parser("run", help="run or resume product graph")
    add_common(run_p)

    st = sub.add_parser("status", help="show thread status")
    st.add_argument("--root", type=Path, default=ROOT)
    st.add_argument("--thread-id", required=True)

    ls = sub.add_parser("list", help="list threads")
    ls.add_argument("--root", type=Path, default=ROOT)

    # bare args = run (compat with thin wrappers)
    p.add_argument("--problem-id", default=None)
    p.add_argument("--problem-class", default="")
    p.add_argument("--slug", default="")
    p.add_argument("--solve-mode", default=None)
    p.add_argument("--knowledge-mode", default=None)
    p.add_argument("--live-pi", action="store_true")
    p.add_argument("--live-subagent", action="store_true")
    p.add_argument("--no-live-subagent", action="store_true")
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--thread-id", default="")
    p.add_argument("--bridge-attachment", default="before_research")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--fresh", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--from-stage", default="")

    args = p.parse_args()

    if args.cmd == "list":
        return cmd_list(args.root.resolve())
    if args.cmd == "status":
        return cmd_status(args.root.resolve(), args.thread_id)
    if args.cmd == "run" or args.cmd is None:
        if args.cmd is None:
            if args.problem_id is None:
                args.problem_id = "shortest_path"
            if args.solve_mode is None:
                args.solve_mode = "mock"
            if args.knowledge_mode is None:
                args.knowledge_mode = "seed"
        else:
            if getattr(args, "problem_id", None) is None:
                args.problem_id = "shortest_path"
        return cmd_run(args)
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
