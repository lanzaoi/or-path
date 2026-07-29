#!/usr/bin/env python3
"""orpath paper — thin CLI for P1 paper workflow helpers."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orpath.paper_workflow import (  # noqa: E402
    append_plan_log,
    build_review_markdown,
    draft_paths,
    gate_research_text,
    load_retrieval,
    render_or_paper,
)


def cmd_template(args: argparse.Namespace) -> int:
    root = Path(args.root)
    sol = json.loads(Path(args.solution).read_text(encoding="utf-8"))
    body = render_or_paper(
        slug=args.slug,
        problem_class=args.problem_class or sol.get("problem_class") or "unknown",
        problem_id=args.problem_id or sol.get("problem_id") or args.slug,
        solution=sol,
        solution_path=str(Path(args.solution).resolve()),
        schema_path=args.schema or "",
        research_path=args.research or "",
        template=args.skin,
        source_lines=[str(Path(args.solution).resolve())],
    )
    paths = draft_paths(root, args.slug)
    paths["draft"].write_text(body, encoding="utf-8")
    paths["cited"].write_text(body, encoding="utf-8")
    paths["paper"].write_text(body, encoding="utf-8")
    print(paths["paper"])
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    paper = Path(args.paper).read_text(encoding="utf-8")
    # gates optional if tools available
    r1_ok = r2_ok = True
    r1_msg = r2_msg = "skipped"
    root = Path(args.root)
    if args.solution and args.whitelist:
        from orpath.gates import gate_r1, gate_r2

        r2_ok, r2_msg = gate_r2(root, Path(args.paper), Path(args.solution))
        r1_ok, r1_msg = gate_r1(root, Path(args.paper), Path(args.whitelist))
    body, n = build_review_markdown(
        slug=args.slug,
        paper_text=paper,
        r1_ok=r1_ok,
        r1_msg=r1_msg,
        r2_ok=r2_ok,
        r2_msg=r2_msg,
        validate_ok=True,
    )
    out = Path(args.out) if args.out else root / "outputs" / f"{args.slug}-review.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    print(out, "fatals", n)
    return 0 if n == 0 else 1


def cmd_gate_research(args: argparse.Namespace) -> int:
    text = Path(args.research).read_text(encoding="utf-8")
    ret = load_retrieval(args.retrieval) if args.retrieval else {}
    ok, errs = gate_research_text(text, knowledge_mode=args.knowledge_mode, retrieval=ret)
    if not ok:
        for e in errs:
            print("FAIL", e)
        return 1
    print("PASS")
    return 0


def cmd_plan_log(args: argparse.Namespace) -> int:
    p = append_plan_log(
        Path(args.root),
        args.slug,
        stage=args.stage,
        status=args.status,
        detail=args.detail or "",
    )
    print(p)
    return 0


def cmd_protocol(args: argparse.Namespace) -> int:
    """Full draft→cite→review→revise→provenance from existing solution.json."""
    from orpath.post_solve_paper import run_post_solve_paper

    root = Path(args.root)
    result = run_post_solve_paper(
        root=root,
        slug=args.slug,
        problem_id=args.problem_id or args.slug,
        problem_class=args.problem_class or "unknown",
        solution_path=Path(args.solution),
        research_path=Path(args.research) if args.research else None,
        retrieval_path=Path(args.retrieval) if args.retrieval else None,
        validate_path=Path(args.validate) if args.validate else None,
        explain_path=Path(args.explain) if args.explain else None,
        schema_path=Path(args.schema) if args.schema else None,
        inject_bad_claim=bool(args.inject_bad_claim),
        max_revise=int(args.max_revise),
    )
    st = result["state"]
    print(result["manifest_path"])
    print(
        "r1",
        st.get("gate_r1_ok"),
        "r2",
        st.get("gate_r2_ok"),
        "claim",
        st.get("gate_claim_ok"),
        "fatal",
        st.get("review_fatal"),
    )
    if st.get("human_required"):
        return 2
    if not (st.get("gate_r1_ok") and st.get("gate_r2_ok") and st.get("gate_claim_ok", True)):
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="OR-Path P1 paper helpers")
    p.add_argument("--root", default=str(ROOT))
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("template", help="render paper template into drafts+papers")
    t.add_argument("--slug", required=True)
    t.add_argument("--solution", required=True)
    t.add_argument("--problem-class", default="")
    t.add_argument("--problem-id", default="")
    t.add_argument("--schema", default="")
    t.add_argument("--research", default="")
    t.add_argument("--skin", choices=["or", "mcm"], default="or")
    t.set_defaults(func=cmd_template)

    r = sub.add_parser("review", help="inline review pack")
    r.add_argument("--slug", required=True)
    r.add_argument("--paper", required=True)
    r.add_argument("--solution", default="")
    r.add_argument("--whitelist", default="")
    r.add_argument("--out", default="")
    r.set_defaults(func=cmd_review)

    g = sub.add_parser("gate-research", help="research evidence gate")
    g.add_argument("--research", required=True)
    g.add_argument("--retrieval", default="")
    g.add_argument("--knowledge-mode", default="seed")
    g.set_defaults(func=cmd_gate_research)

    pl = sub.add_parser("plan-log", help="append plan verification log")
    pl.add_argument("--slug", required=True)
    pl.add_argument("--stage", required=True)
    pl.add_argument("--status", required=True)
    pl.add_argument("--detail", default="")
    pl.set_defaults(func=cmd_plan_log)

    pr = sub.add_parser(
        "protocol",
        help="full paper protocol from existing solution (draft→cite→review→revise→provenance)",
    )
    pr.add_argument("--slug", required=True)
    pr.add_argument("--solution", required=True)
    pr.add_argument("--problem-id", default="")
    pr.add_argument("--problem-class", default="unknown")
    pr.add_argument("--research", default="")
    pr.add_argument("--retrieval", default="")
    pr.add_argument("--validate", default="")
    pr.add_argument("--explain", default="")
    pr.add_argument("--schema", default="")
    pr.add_argument("--inject-bad-claim", action="store_true", default=False)
    pr.add_argument("--max-revise", type=int, default=2)
    pr.set_defaults(func=cmd_protocol)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
