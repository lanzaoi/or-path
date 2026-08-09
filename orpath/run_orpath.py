#!/usr/bin/env python3
"""OR-Path product runner (T3): CLI over ControlPlane (ADR-0003).

checkpointer, resume, from-stage, status/list. State seed & graph build via
orpath.control_plane.
"""
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

from orpath.control_plane import (  # noqa: E402
    PREDECESSORS as _PREDECESSORS,
    PRODUCT_NODES,
    build_graph,
    db_path as _db_path,
    default_initial as _default_initial,
    open_sqlite_checkpointer,
    thread_config as _config,
    write_stage_map_files,
)
from orpath.node_context import dirty_artifacts, thread_dir  # noqa: E402
from orpath.paths import apply_workdir, orpath_home  # noqa: E402


def cmd_list(root: Path) -> int:
    runs = root / "runs"
    if not runs.is_dir():
        print(json.dumps({"threads": []}, indent=2))
        return 0
    threads = []
    for p in sorted(runs.iterdir()):
        if p.is_dir() and p.name != "__pycache__":
            latest = p / "latest_snapshot.json"
            meta: dict[str, Any] = {}
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
    """CLI > env. Product default ON when env unset.

    --no-live-subagent → False / env 0 (CI, gates).
    --live-subagent / --live-pi → True / env 1.
    Else honour env; if unset → default ON.
    """
    if getattr(args, "no_live_subagent", False):
        os.environ["ORPATH_LIVE_SUBAGENT"] = "0"
        return False
    if getattr(args, "live_subagent", False) or bool(getattr(args, "live_pi", False)):
        os.environ["ORPATH_LIVE_SUBAGENT"] = "1"
        return True
    raw = (os.environ.get("ORPATH_LIVE_SUBAGENT") or "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    os.environ["ORPATH_LIVE_SUBAGENT"] = "1"
    return True


def _resolve_intake_sources(root: Path, args: argparse.Namespace) -> tuple[list[str], bool]:
    """Return (sources, skip_intake). --auto-intake scans inbox/ when no --intake-in."""
    from orpath.intake_discover import merge_intake_sources

    auto = bool(getattr(args, "auto_intake", False))
    sources = merge_intake_sources(
        root,
        list(getattr(args, "intake_in", None) or []),
        auto_intake=auto,
    )
    skip = len(sources) == 0
    return sources, skip


def _resolve_data_root(args: argparse.Namespace) -> Path:
    """Case data root (runs/outputs/…). Prefer --workdir, else --root; sync ORPATH_WORKDIR."""
    wd = getattr(args, "workdir", None)
    if wd is not None and str(wd).strip():
        return apply_workdir(wd)
    # Historical --root is the data root; align env so Watch uses the same tree.
    root = getattr(args, "root", None) or ROOT
    return apply_workdir(root)


def cmd_run(args: argparse.Namespace) -> int:
    root = _resolve_data_root(args)
    # Install home stays on sys.path for package imports (ROOT already inserted).
    _ = orpath_home()
    write_stage_map_files(root)
    thread_id = args.thread_id or f"{args.slug or args.problem_id}-{uuid.uuid4().hex[:8]}"
    slug = args.slug or f"orpath-{args.problem_id}"

    # D2: human-steer resume_from when CLI --from-stage empty
    from orpath.human_steer import apply_steer_to_state, resume_from_steer

    if not getattr(args, "from_stage", None):
        rf = resume_from_steer(root, slug)
        if rf:
            args.from_stage = rf
            print(
                json.dumps(
                    {"info": "human_steer_resume_from", "from_stage": rf, "slug": slug},
                    ensure_ascii=False,
                ),
                flush=True,
            )

    saver, conn = open_sqlite_checkpointer(_db_path(root))
    app = build_graph(checkpointer=saver)
    cfg = _config(thread_id)

    if args.resume or args.from_stage:
        probe: dict[str, Any] = {
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

    # BUG-1 fix: block implicit reuse of an existing thread without --fresh
    if not args.fresh and not args.resume and not getattr(args, "force", False):
        stages_dir = root / "runs" / thread_id / "stages"
        if stages_dir.is_dir() and any(stages_dir.iterdir()):
            print(
                json.dumps(
                    {
                        "error": "dirty_artifacts",
                        "detail": f"thread {thread_id!r} already has stages under {stages_dir}",
                        "hint": "pass --fresh to start over, --resume to continue, or --force to overwrite",
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            conn.close()
            return 3

    if args.fresh or not args.resume:
        live_sa = _resolve_live_subagent(args)
        intake_sources, skip_intake = _resolve_intake_sources(root, args)
        if skip_intake and bool(getattr(args, "auto_intake", False)):
            print(
                json.dumps(
                    {
                        "info": "auto_intake_empty",
                        "detail": "no --intake-in and inbox/ empty — skip_intake=true",
                        "inbox": str(root / "inbox"),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        initial = _default_initial(
            root=root,
            slug=slug,
            problem_id=args.problem_id,
            problem_class=args.problem_class or "",
            solve_mode=args.solve_mode,
            knowledge_mode=(
                __import__("orpath.nodes", fromlist=["_resolve_knowledge_mode"])._resolve_knowledge_mode(
                    args.knowledge_mode
                )
            ),
            live_pi=bool(args.live_pi),
            live_subagent=live_sa,
            thread_id=thread_id,
            bridge_attachment=args.bridge_attachment,
            skip_intake=skip_intake,
            intake_sources=intake_sources,
            intake_assets_dir=str(getattr(args, "intake_assets", "") or ""),
            human_confirm_intake=bool(getattr(args, "human_confirm_intake", False)),
            intake_confirmed=bool(getattr(args, "intake_confirmed", False)),
        )
        # D2: merge human-steer into seed (solve_mode / pi fields)
        steer_seed = apply_steer_to_state(initial, workdir=root, boundary=None)
        if steer_seed:
            initial = {**initial, **{k: v for k, v in steer_seed.items() if k not in {"stage", "human_required", "steer_pause"}}}
            if steer_seed.get("solve_mode"):
                print(
                    json.dumps(
                        {
                            "info": "human_steer_solve_mode",
                            "solve_mode": steer_seed.get("solve_mode"),
                            "path": steer_seed.get("human_steer_path"),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
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
            cp_id = getattr(cp, "id", None) or (
                cp.get("id") if isinstance(cp, dict) else None
            )
        if cp_id:
            td = thread_dir(
                {"root": str(root), "thread_id": thread_id, "slug": slug}
            )  # type: ignore[arg-type]
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
        "solve_mode": final.get("solve_mode") or args.solve_mode,
        "human_steer_applied": final.get("human_steer_applied"),
        "human_steer_path": final.get("human_steer_path"),
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
        "pipeline": final.get("pipeline") or "product",
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


def cmd_intake(args: argparse.Namespace) -> int:
    """Standalone 1.1 OCR + parse (no solve)."""
    from orpath.intake_nodes import standalone_intake

    root = _resolve_data_root(args)
    sources = [Path(p) for p in (args.intake_in or [])]
    assets = Path(args.intake_assets) if getattr(args, "intake_assets", "") else None
    if assets and not assets.is_absolute():
        assets = root / assets
    result = standalone_intake(
        root=root,
        slug=args.slug,
        sources=sources,
        assets_dir=assets if assets and str(assets) else None,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if result.get("ok") else 1


def main() -> int:
    p = argparse.ArgumentParser(description="OR-Path product runner (T3 LG skeleton)")
    sub = p.add_subparsers(dest="cmd")

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--root",
            type=Path,
            default=ROOT,
            help="case data root (alias of workdir when --workdir unset)",
        )
        sp.add_argument(
            "--workdir",
            type=Path,
            default=None,
            help="case data root: outputs/notes/papers/runs (sets ORPATH_WORKDIR)",
        )
        sp.add_argument("--thread-id", default="")
        sp.add_argument("--problem-id", default="shortest_path")
        sp.add_argument("--problem-class", default="")
        sp.add_argument("--slug", default="")
        sp.add_argument(
            "--solve-mode",
            choices=(
                "mock",
                "networkx",
                "ortools",
                "cpsat",
                "highs",
                "polyomino",
                "polyomino_cover",
                "tube",
            ),
            default="mock",
        )
        sp.add_argument(
            "--knowledge-mode", choices=("off", "seed", "hybrid"), default="hybrid",
            help="default hybrid RAG (force retrieval); seed/off via flag or ORPATH_KNOWLEDGE_MODE",
        )
        sp.add_argument("--live-pi", action="store_true")
        sp.add_argument(
            "--live-subagent",
            action="store_true",
            help="force live MA ON (also product default when env unset)",
        )
        sp.add_argument(
            "--no-live-subagent",
            action="store_true",
            help="force no live MA (CI/gates); overrides product default ON",
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
        sp.add_argument(
            "--intake-in",
            action="append",
            default=[],
            dest="intake_in",
            help="problem surface file (repeatable); enables intake front-door",
        )
        sp.add_argument(
            "--auto-intake",
            action="store_true",
            help="if no --intake-in, scan inbox/ for md/txt/pdf/images and enable intake",
        )
        sp.add_argument(
            "--intake-assets",
            default="",
            help="optional unpacked assets directory for intake_parse",
        )
        sp.add_argument(
            "--human-confirm-intake",
            action="store_true",
            help="stop after intake until --intake-confirmed on a later resume",
        )
        sp.add_argument(
            "--intake-confirmed",
            action="store_true",
            help="mark intake brief accepted (with human_confirm_intake)",
        )

    run_p = sub.add_parser("run", help="run or resume product graph")
    add_common(run_p)

    st = sub.add_parser("status", help="show thread status")
    st.add_argument("--root", type=Path, default=ROOT)
    st.add_argument("--workdir", type=Path, default=None)
    st.add_argument("--thread-id", required=True)

    ls = sub.add_parser("list", help="list threads")
    ls.add_argument("--root", type=Path, default=ROOT)
    ls.add_argument("--workdir", type=Path, default=None)

    inp = sub.add_parser("intake", help="1.1 OCR+parse only (no full graph solve)")
    inp.add_argument("--root", type=Path, default=ROOT)
    inp.add_argument("--workdir", type=Path, default=None)
    inp.add_argument("--slug", required=True)
    inp.add_argument(
        "--in",
        dest="intake_in",
        action="append",
        required=True,
        help="problem surface file (repeatable)",
    )
    inp.add_argument("--assets", default="", dest="intake_assets")

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
    p.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="case data root (outputs/runs/…); sets ORPATH_WORKDIR",
    )
    p.add_argument("--thread-id", default="")
    p.add_argument("--bridge-attachment", default="before_research")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--fresh", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--from-stage", default="")
    p.add_argument("--intake-in", action="append", default=[], dest="intake_in")
    p.add_argument("--auto-intake", action="store_true")
    p.add_argument("--intake-assets", default="")
    p.add_argument("--human-confirm-intake", action="store_true")
    p.add_argument("--intake-confirmed", action="store_true")

    args = p.parse_args()

    if args.cmd == "list":
        return cmd_list(_resolve_data_root(args))
    if args.cmd == "status":
        return cmd_status(_resolve_data_root(args), args.thread_id)
    if args.cmd == "intake":
        return cmd_intake(args)
    if args.cmd == "run" or args.cmd is None:
        if args.cmd is None:
            if args.problem_id is None:
                args.problem_id = "shortest_path"
            if args.solve_mode is None:
                args.solve_mode = "mock"
            if args.knowledge_mode is None:
                args.knowledge_mode = "hybrid"
        else:
            if getattr(args, "problem_id", None) is None:
                args.problem_id = "shortest_path"
        return cmd_run(args)
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
