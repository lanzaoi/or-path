"""Explain, draft_paper, cite_pack, review_pack, revise_or_done, and provenance nodes."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orpath.annotations_lite import annotations_from_review, write_annotations
from orpath.artifact_versions import record_versions
from orpath.claim_ledger import (
    build_claim_ledger,
    select_final_candidate,
    write_claim_ledger,
    write_verification_md,
)
from orpath.gates import gate_claim_map, gate_r1, gate_r2
from orpath.lab_continuity import append_lab_changelog, write_solution_figure
from orpath.paper_workflow import (
    append_plan_log,
    apply_revise_fixes,
    build_review_markdown,
    draft_paper_with_writer,
    draft_paths,
    gate_research_text,
    load_retrieval,
    merge_review_if_child_wrote,
    render_or_paper,
    run_reviewer_agent,
    thick_provenance,
)
from orpath.research_run import build_research_run, write_research_run
from orpath.revise_proof import extract_bad_urls, write_revise_proof
from orpath.state import ORPathState
from orpath.pipeline.common import (
    _root,
    _rel_under,
    _ensure_dirs,
    _fixture_base,
    _infer_class,
    _paper_whitelist_path,
    _count_fatal,
    _solution_is_blocked,
    _intake_front_door_active,
)

def node_explain(state: ORPathState) -> dict:
    root = _root(state)
    sol_path = Path(state.get("solution_path") or "")
    if sol_path.is_file():
        sol = json.loads(sol_path.read_text(encoding="utf-8"))
    else:
        sol = {"status": "MISSING", "objective": None, "solver": "none"}
    path = root / "notes" / f"{state['slug']}-explain.md"
    shape = sol.get("path") or sol.get("tour") or sol.get("routes")
    meta = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
    blocked = str(sol.get("status") or "").upper() == "BLOCKED" or bool(meta.get("blocked"))
    reason = str(meta.get("reason") or "solver prerequisites are unavailable")
    note = f"**BLOCKED:** {reason}. Do not invent a result." if blocked else ""
    path.write_text(
        (
            f"# Explain: {state['slug']}\n\n"
            f"Solver `{sol.get('solver')}` status `{sol.get('status')}`.\n\n"
            f"- objective: {sol.get('objective')}\n"
            f"- shape: {shape}\n"
            f"- validate: {state.get('validate_path')}\n"
            f"- blocked: {blocked}\n"
            f"- last_error: {state.get('last_error')}\n\n"
            f"All numbers from `{state.get('solution_path')}` only.\n"
            f"{note}\n"
        ),
        encoding="utf-8",
    )
    return {"stage": "draft_paper", "explain_path": str(path)}


def node_draft_paper(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    sol_path = Path(state.get("solution_path") or "")
    if sol_path.is_file():
        sol = json.loads(sol_path.read_text(encoding="utf-8"))
    else:
        sol = {
            "status": "BLOCKED",
            "objective": None,
            "solver": "none",
            "source": "missing_solution",
            "meta": {"blocked": True, "exact": False, "proven_optimal": False},
        }
        sol_path = root / "outputs" / f"{slug}-solution.json"
        sol_path.write_text(json.dumps(sol, indent=2) + "\n", encoding="utf-8")
    paths = draft_paths(root, slug)
    paths["paper"].parent.mkdir(parents=True, exist_ok=True)
    pc = state.get("problem_class") or sol.get("problem_class")
    fb = _fixture_base(root, state["problem_id"])
    meta0 = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
    blocked0 = str(sol.get("status") or "").upper() == "BLOCKED" or bool(meta0.get("blocked"))
    intake_on = _intake_front_door_active(state)
    if blocked0 or intake_on:
        if fb is not None:
            try:
                rel = "shell_only:" + _rel_under(fb, root)
            except ValueError:
                rel = f"shell_only:adhoc:{state.get('problem_id')}"
        else:
            rel = f"shell_only:adhoc:{state.get('problem_id')}"
        wl_path = _paper_whitelist_path(root, state, fb)
        cites: list[str] = []
        try:
            wl = json.loads(wl_path.read_text(encoding="utf-8"))
            cites.extend(str(u) for u in (wl.get("urls") or []))
            cites.extend(str(n) for n in (wl.get("notes") or []))
        except (json.JSONDecodeError, OSError):
            cites = ["notes://intake-blocked-soak"]
        cites = [
            c
            for c in cites
            if "arxiv" not in c.lower() and "shortest-path" not in c.lower()
        ]
        if not cites:
            cites = ["notes://intake-blocked-soak"]
    else:
        if fb is None:
            rel = f"adhoc:{state.get('problem_id')}"
            cites = []
            wl_path = _paper_whitelist_path(root, state, None)
        else:
            try:
                rel = _rel_under(fb, root)
            except ValueError:
                rel = str(fb)
            cites = []
            wl_path = fb / "whitelist_refs.json"
        if wl_path.is_file():
            try:
                wl = json.loads(wl_path.read_text(encoding="utf-8"))
                cites.extend(str(u) for u in (wl.get("urls") or []))
                cites.extend(str(n) for n in (wl.get("notes") or []))
            except json.JSONDecodeError:
                cites = []
        if not cites:
            cites = [
                "notes://t2-tsp-ref"
                if pc == "tsp"
                else (
                    "notes://t2-vrp-ref"
                    if pc == "vrp"
                    else "notes://t1-shortest-path-ref"
                )
            ]
    source_lines = list(cites)
    source_lines.append(str(sol_path))
    if state.get("research_path"):
        source_lines.append(str(state.get("research_path")))
    if state.get("validate_path"):
        source_lines.append(str(state.get("validate_path")))
    if state.get("brief_path"):
        source_lines.append(str(state.get("brief_path")))
    if state.get("intake_path"):
        source_lines.append(str(state.get("intake_path")))

    revision_fb = state.get("last_error") if int(state.get("revise_count") or 0) > 0 else ""
    body = draft_paper_with_writer(
        root=root,
        slug=slug,
        problem_class=str(pc),
        problem_id=state["problem_id"],
        solution=sol,
        solution_path=str(sol_path),
        paper_path=paths["draft"],
        schema_path=str(state.get("schema_path") or ""),
        research_path=str(state.get("research_path") or ""),
        retrieval_path=str(state.get("retrieval_path") or ""),
        validate_path=str(state.get("validate_path") or ""),
        explain_path=str(state.get("explain_path") or ""),
        fixture_rel=rel,
        source_lines=source_lines,
        template="or",
        revision_feedback=revision_fb or "",
        state=dict(state),
    )
    meta = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
    if str(sol.get("status") or "").upper() == "BLOCKED" or meta.get("blocked"):
        blocked_code = str(meta.get("blocked_code") or "solution_blocked")
        blocked_reason = str(meta.get("reason") or "solver prerequisites are unavailable")
        body = (
            body
            + "\n\n## Provenance note (blocked solve)\n\n"
            + f"Solution status is **BLOCKED** (`{blocked_code}`): {blocked_reason}. "
            + "Do **not** invent result tables or forecasts. "
            + "Do **not** treat shell fixture gold objectives as contest answers. "
            + "Paper gates R2/claim should remain BLOCKED/fail-closed.\n"
        )
    # P1-5 layered drafts: draft only here; cite_pack builds cited
    paths["draft"].write_text(body, encoding="utf-8")
    paths["paper"].write_text(body, encoding="utf-8")
    append_plan_log(
        root,
        slug,
        stage="draft",
        status="done",
        detail=f"wrote {paths['draft'].name} (pending cite_pack)",
        plan_file=state.get("plan_path"),
    )
    return {
        "stage": "cite_pack",
        "paper_path": str(paths["paper"]),
        "solution_path": str(sol_path),
        "last_error": "",
    }


def node_cite_pack(state: ORPathState) -> dict:
    """P0-1/P0-2: cite layer — deterministic R1/claim → cited."""
    root = _root(state)
    slug = state["slug"]
    paths = draft_paths(root, slug)
    paper = Path(state["paper_path"])
    if not paper.is_file() and paths["draft"].is_file():
        paper = paths["draft"]
    fb = _fixture_base(root, state["problem_id"])
    wl = _paper_whitelist_path(root, state, fb)
    sol = Path(state["solution_path"])
    claim_out = root / "outputs" / ".drafts" / f"{slug}-claim-map.json"

    r1_ok, r1_msg = gate_r1(root, paper, wl)
    claim_ok, claim_msg = gate_claim_map(
        root,
        paper,
        sol,
        whitelist=wl if wl.is_file() else None,
        research=Path(state["research_path"]) if state.get("research_path") else None,
        retrieval=Path(state["retrieval_path"]) if state.get("retrieval_path") else None,
        out=claim_out,
    )

    body = paper.read_text(encoding="utf-8") if paper.is_file() else ""
    # append claim-map summary into cited artifact
    cmap = {}
    if claim_out.is_file():
        try:
            cmap = json.loads(claim_out.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cmap = {}
    footer = [
        "",
        "---",
        "## Claim map (P0 cite_pack)",
        f"- r1_ok: {r1_ok}",
        f"- claim_map_ok: {claim_ok}",
        f"- claim_map_path: `{claim_out}`",
        f"- claims_recorded: {len(cmap.get('claims') or [])}",
    ]
    if not claim_ok:
        footer.append(f"- claim_errors: {claim_msg[:500]}")
    cited_body = body.rstrip() + "\n" + "\n".join(footer) + "\n"
    paths["cited"].write_text(cited_body, encoding="utf-8")
    paper.write_text(body, encoding="utf-8")

    ok = r1_ok and claim_ok

    # Deep Feynman-style claim ledger + verification.md
    research_text = ""
    if state.get("research_path") and Path(state["research_path"]).is_file():
        research_text = Path(state["research_path"]).read_text(encoding="utf-8")
    texts = [(str(paper), body)]
    if research_text:
        texts.append((str(state["research_path"]), research_text))
    if paths["cited"].is_file():
        texts.append((str(paths["cited"]), paths["cited"].read_text(encoding="utf-8")))
    ledger = build_claim_ledger(
        slug=slug,
        texts=texts,
        r1_ok=r1_ok,
        r2_ok=None,
        claim_map_ok=claim_ok,
        research_ok=None,
        validate_ok=state.get("gate_validate_ok"),
    )
    write_claim_ledger(paths["claim_ledger"], ledger)
    write_verification_md(
        paths["verification"],
        ledger,
        extra=(
            f"cite_pack r1={r1_ok} claim_map={claim_ok}\n"
            f"{claim_msg[:400] if not claim_ok else ''}"
        ),
    )

    append_plan_log(
        root,
        slug,
        stage="cite",
        status="pass" if ok else "fail",
        detail=(
            f"r1={r1_ok} claim={claim_ok} "
            f"ledger_claims={ledger.get('claimCount')} vstate={ledger.get('verificationState')}"
        ),
        plan_file=state.get("plan_path"),
    )
    err_parts = []
    if not ok:
        if not r1_ok or not claim_ok:
            err_parts.append(f"cite: r1={r1_msg}; claim={claim_msg}")
    return {
        "stage": "review_pack",
        "paper_path": str(paper),
        "cited_path": str(paths["cited"]),
        "gate_r1_ok": r1_ok,
        "gate_claim_ok": claim_ok,
        "gate_subagent_ok": None,
        "verification_state": ledger.get("verificationState"),
        "last_error": "" if ok else "; ".join(err_parts),
    }


def node_review_pack(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    paper = Path(state["paper_path"])
    sol = Path(state["solution_path"])
    fb = _fixture_base(root, state["problem_id"])
    wl = _paper_whitelist_path(root, state, fb)
    paper_text = paper.read_text(encoding="utf-8") if paper.is_file() else ""
    review = root / "outputs" / f"{slug}-review.md"

    r2_ok, r2_msg = gate_r2(root, paper, sol)
    r1_ok, r1_msg = gate_r1(root, paper, wl)
    claim_out = root / "outputs" / ".drafts" / f"{slug}-claim-map.json"
    claim_ok, claim_msg = gate_claim_map(
        root,
        paper,
        sol,
        whitelist=wl if wl.is_file() else None,
        research=Path(state["research_path"]) if state.get("research_path") else None,
        retrieval=Path(state["retrieval_path"]) if state.get("retrieval_path") else None,
        out=claim_out,
    )

    research_ok = None
    research_msg = ""
    rp = state.get("research_path")
    if rp and Path(rp).is_file():
        rok, rerrs = gate_research_text(
            Path(rp).read_text(encoding="utf-8"),
            knowledge_mode=str(state.get("knowledge_mode") or "off"),
            retrieval=load_retrieval(state.get("retrieval_path")),
        )
        research_ok = rok
        research_msg = "; ".join(rerrs)

    body, fatal_n = build_review_markdown(
        slug=slug,
        paper_text=paper_text,
        r1_ok=r1_ok,
        r1_msg=r1_msg,
        r2_ok=r2_ok,
        r2_msg=r2_msg,
        validate_ok=state.get("gate_validate_ok"),
        research_ok=research_ok,
        research_msg=research_msg,
    )
    # inject claim map fatals
    if not claim_ok:
        body += f"\n### Claim map FATAL\n- **FATAL:** {claim_msg}\n"
        fatal_n = len(re.findall(r"\*\*FATAL:\*\*", body))

    # Run or_reviewer agent if live multiagent is active
    child_review = run_reviewer_agent(
        root=root,
        slug=slug,
        paper_path=paper,
        solution_path=sol,
        review_path=review,
        state=dict(state),
    )
    if child_review:
        body = merge_review_if_child_wrote(automated_body=body, child_review=review)
        fatal_n = len(re.findall(r"\*\*FATAL:\*\*", body))

    review.write_text(body, encoding="utf-8")
    # P2 annotations-lite from review
    ann_path = root / "outputs" / ".drafts" / f"{slug}-annotations.json"
    anns = annotations_from_review(body, artifact_path=str(paper), slug=slug)
    write_annotations(ann_path, slug=slug, annotations=anns)
    vn = root / "outputs" / f"{slug}-verify-notes.md"
    vn.write_text(
        f"# Verify notes {slug}\n\n- r1={r1_ok} ({r1_msg})\n- r2={r2_ok} ({r2_msg})\n"
        f"- claim_map={claim_ok} ({claim_msg[:300]})\n"
        f"- research_gate={research_ok} ({research_msg})\n- fatals={fatal_n}\n",
        encoding="utf-8",
    )
    fatals = []
    if not r2_ok:
        fatals.append(f"R2 failed: {r2_msg}")
    if not r1_ok:
        fatals.append(f"R1 failed: {r1_msg}")
    if not claim_ok:
        fatals.append(f"claim_map failed: {claim_msg}")
    append_plan_log(
        root,
        slug,
        stage="review",
        status="pass" if not fatals else "fail",
        detail="; ".join(fatals) if fatals else "r1/r2/claim green",
        plan_file=state.get("plan_path"),
    )
    return {
        "stage": "revise_or_done",
        "review_path": str(review),
        "gate_r1_ok": r1_ok,
        "gate_r2_ok": r2_ok,
        "gate_claim_ok": claim_ok,
        "gate_subagent_ok": state.get("gate_subagent_ok"),
        "review_fatal": fatal_n,
        "last_error": "; ".join(fatals),
    }


def node_revise_or_done(state: ORPathState) -> dict:
    ok = (
        state.get("gate_r1_ok")
        and state.get("gate_r2_ok")
        and state.get("gate_claim_ok", True)
        and state.get("review_fatal", 0) == 0
    )
    root = _root(state)
    slug = state["slug"]
    paths = draft_paths(root, slug)

    # 1.2 / intake soak: BLOCKED solution → paper shell is fail-closed by design.
    # Do NOT burn revise + live cite/review loops on fixture gold prose (42/32/…).
    if _solution_is_blocked(state):
        append_plan_log(
            root,
            slug,
            stage="revise",
            status="blocked",
            detail="solution BLOCKED — skip revise ladder; provenance fail-closed",
            plan_file=state.get("plan_path"),
        )
        return {
            "stage": "provenance",
            "human_required": True,
            "gate_r2_ok": False,
            "gate_claim_ok": False,
            "paper_blocked": True,
            "last_error": (
                "paper_blocked_solution: "
                + str(state.get("last_error") or "R2/claim not applicable")
            )[:500],
        }

    if ok:
        append_plan_log(
            root,
            slug,
            stage="revise",
            status="skip",
            detail="no FATAL; proceed provenance",
            plan_file=state.get("plan_path"),
        )
        return {"stage": "provenance", "last_error": ""}

    rev = int(state.get("revise_count") or 0)
    max_r = int(state.get("max_revise") or 2)
    if rev >= max_r:
        append_plan_log(
            root,
            slug,
            stage="revise",
            status="exhausted",
            detail=str(state.get("last_error") or ""),
            plan_file=state.get("plan_path"),
        )
        return {
            "stage": "human_stop",
            "human_required": True,
            "last_error": f"paper revise exhausted: {state.get('last_error')}",
        }

    paper = Path(state["paper_path"])
    sol = json.loads(Path(state["solution_path"]).read_text(encoding="utf-8"))
    fb = _fixture_base(root, state["problem_id"])
    wl_path = _paper_whitelist_path(root, state, fb)
    allowed: list[str] = []
    if wl_path.is_file():
        try:
            wl = json.loads(wl_path.read_text(encoding="utf-8"))
            allowed.extend(str(u) for u in (wl.get("urls") or []))
            allowed.extend(str(n) for n in (wl.get("notes") or []))
        except json.JSONDecodeError:
            pass
    old = paper.read_text(encoding="utf-8") if paper.is_file() else ""
    bad_urls = extract_bad_urls(old, set(allowed))
    fixed = apply_revise_fixes(
        old,
        solution=sol,
        allowed_urls=allowed,
        solution_path=state["solution_path"],
    )
    # strip affirmative global-opt marketing if not proven (keep honesty disclaimers)
    if not (sol.get("meta") or {}).get("proven_optimal"):
        try:
            from tools.r1_claim_map import GLOBAL_OPT_RE, _NEG_LEFT_RE
        except Exception:  # noqa: BLE001
            import sys
            from pathlib import Path as _P

            _td = _P(__file__).resolve().parents[1] / "tools"
            if str(_td) not in sys.path:
                sys.path.insert(0, str(_td))
            from r1_claim_map import GLOBAL_OPT_RE, _NEG_LEFT_RE  # type: ignore

        parts: list[str] = []
        last = 0
        for m in GLOBAL_OPT_RE.finditer(fixed):
            chunk_left = fixed[max(0, m.start() - 56) : m.start()]
            parts.append(fixed[last : m.start()])
            if _NEG_LEFT_RE.search(chunk_left) or re.search(
                r"is\s+not\s+true|proven_optimal[`\s:=]*false",
                chunk_left[-40:],
                re.I,
            ):
                parts.append(m.group(0))
            else:
                parts.append("best-found / validated feasible")
            last = m.end()
        parts.append(fixed[last:])
        fixed = "".join(parts)
    paths["revised"].write_text(fixed, encoding="utf-8")
    paper.write_text(fixed, encoding="utf-8")

    r2_ok, r2_msg = gate_r2(root, paper, Path(state["solution_path"]))
    r1_ok, r1_msg = gate_r1(root, paper, wl_path)
    claim_out = root / "outputs" / ".drafts" / f"{slug}-claim-map.json"
    claim_ok, claim_msg = gate_claim_map(
        root,
        paper,
        Path(state["solution_path"]),
        whitelist=wl_path if wl_path.is_file() else None,
        research=Path(state["research_path"]) if state.get("research_path") else None,
        retrieval=Path(state["retrieval_path"]) if state.get("retrieval_path") else None,
        out=claim_out,
    )

    proof_path = root / "outputs" / ".drafts" / f"{slug}-revise-proof.md"
    write_revise_proof(
        proof_path,
        slug=slug,
        before=old,
        after=fixed,
        removed_needles=bad_urls
        + (
            ["global optimal", "保证全局最优"]
            if not (sol.get("meta") or {}).get("proven_optimal")
            else []
        ),
        r1_ok=r1_ok,
        r2_ok=r2_ok,
        claim_ok=claim_ok,
        detail=f"rev={rev+1} r1={r1_msg[:80]} r2={r2_msg[:80]} claim={claim_msg[:80]}",
    )

    append_plan_log(
        root,
        slug,
        stage="revise",
        status="pass" if (r1_ok and r2_ok and claim_ok) else "retry",
        detail=f"rev={rev+1} proof={proof_path.name} r1={r1_ok} r2={r2_ok} claim={claim_ok}",
        plan_file=state.get("plan_path"),
    )

    # Conservative: a non-zero ``review_fatal`` from the prior review means the
    # writer must redraft even when the re-run gates pass (do not trust automated
    # fixes to have cleared fatal defects).
    if r1_ok and r2_ok and claim_ok and state.get("review_fatal", 0) == 0:
        body, fatal_n = build_review_markdown(
            slug=slug,
            paper_text=fixed,
            r1_ok=True,
            r1_msg="ok",
            r2_ok=True,
            r2_msg="ok",
            validate_ok=state.get("gate_validate_ok"),
            research_ok=True,
            research_msg="",
        )
        if state.get("review_path"):
            Path(state["review_path"]).write_text(body, encoding="utf-8")
        return {
            "stage": "provenance",
            "revise_count": rev + 1,
            "gate_r1_ok": True,
            "gate_r2_ok": True,
            "gate_claim_ok": True,
            "review_fatal": 0,
            "paper_path": str(paper),
            "last_error": "",
        }

    # If structural, claim, or optimality issues remain, route back to draft_paper for writer revision
    needs_redraft = not r2_ok or not claim_ok or bool(state.get("review_fatal", 0) > 0)
    next_stage = "draft_paper" if needs_redraft else "cite_pack"
    return {
        "stage": next_stage,
        "revise_count": rev + 1,
        "gate_r1_ok": r1_ok,
        "gate_r2_ok": r2_ok,
        "gate_claim_ok": claim_ok,
        "paper_path": str(paper),
        "last_error": f"after revise: r1={r1_msg}; r2={r2_msg}; claim={claim_msg}",
    }

def node_provenance(state: ORPathState) -> dict:
    root = _root(state)
    slug = state["slug"]
    dpaths = draft_paths(root, slug)
    # Promote final candidate (Feynman: revised > cited > draft)
    final = select_final_candidate(dpaths)
    if final and final.is_file():
        paper_out = dpaths["paper"]
        paper_out.parent.mkdir(parents=True, exist_ok=True)
        body = final.read_text(encoding="utf-8")
        # strip cite footer if present when promoting cited
        if "## Claim map (P0 cite_pack)" in body:
            body = body.split("## Claim map (P0 cite_pack)")[0].rstrip() + "\n"
        paper_out.write_text(body, encoding="utf-8")
        final_path = str(final)
    else:
        final_path = state.get("paper_path") or ""

    # rebuild ledger at end with all gates
    texts: list[tuple[str, str]] = []
    for key in ("draft", "cited", "revised", "paper", "verification"):
        p = dpaths.get(key)
        if p and Path(p).is_file():
            texts.append((str(p), Path(p).read_text(encoding="utf-8")))
    if state.get("research_path") and Path(state["research_path"]).is_file():
        texts.append(
            (str(state["research_path"]), Path(state["research_path"]).read_text(encoding="utf-8"))
        )
    research_ok = None
    if state.get("research_path") and Path(state["research_path"]).is_file():
        rok, _ = gate_research_text(
            Path(state["research_path"]).read_text(encoding="utf-8"),
            knowledge_mode=str(state.get("knowledge_mode") or "off"),
            retrieval=load_retrieval(state.get("retrieval_path")),
        )
        research_ok = rok
    ledger = build_claim_ledger(
        slug=slug,
        texts=texts,
        r1_ok=state.get("gate_r1_ok"),
        r2_ok=state.get("gate_r2_ok"),
        claim_map_ok=state.get("gate_claim_ok"),
        research_ok=research_ok,
        validate_ok=state.get("gate_validate_ok"),
    )
    write_claim_ledger(dpaths["claim_ledger"], ledger)
    write_verification_md(
        dpaths["verification"],
        ledger,
        extra=f"final_candidate={final_path}\nrevise_count={state.get('revise_count')}",
    )

    path_map = {
        "plan_path": state.get("plan_path") or str(dpaths["plan"]),
        "retrieval_path": state.get("retrieval_path"),
        "research_path": state.get("research_path"),
        "schema_path": state.get("schema_path"),
        "solution_path": state.get("solution_path"),
        "validate_path": state.get("validate_path"),
        "explain_path": state.get("explain_path"),
        "draft_path": str(dpaths["draft"]) if dpaths["draft"].is_file() else "",
        "cited_path": str(dpaths["cited"]) if dpaths["cited"].is_file() else "",
        "revised_path": str(dpaths["revised"]) if dpaths["revised"].is_file() else "",
        "verification_path": str(dpaths["verification"]) if dpaths["verification"].is_file() else "",
        "claim_ledger_path": str(dpaths["claim_ledger"]) if dpaths["claim_ledger"].is_file() else "",
        "claim_map_path": str(dpaths["claim_map"]) if dpaths["claim_map"].is_file() else "",
        "final_candidate_path": final_path,
        "paper_path": str(dpaths["paper"]) if dpaths["paper"].is_file() else state.get("paper_path"),
        "review_path": state.get("review_path"),
        "tune_log_path": state.get("tune_log_path"),
        "annotations_path": str(root / "outputs" / ".drafts" / f"{slug}-annotations.json")
        if (root / "outputs" / ".drafts" / f"{slug}-annotations.json").is_file()
        else "",
        "provenance_path": "",  # filled after write
    }

    # P2 figure from solution
    figure_path = ""
    if state.get("solution_path") and Path(state["solution_path"]).is_file():
        try:
            sol = json.loads(Path(state["solution_path"]).read_text(encoding="utf-8"))
            fig = root / "outputs" / ".drafts" / f"{slug}-figure.html"
            write_solution_figure(fig, sol, slug=slug)
            figure_path = str(fig)
            path_map["figure_path"] = figure_path
        except Exception:
            pass

    verif = "PASS"
    if state.get("human_required"):
        verif = "BLOCKED"
    elif ledger.get("verificationState") == "failed":
        verif = "BLOCKED"
    elif not (
        state.get("gate_r1_ok")
        and state.get("gate_r2_ok")
        and state.get("gate_validate_ok")
        and state.get("gate_claim_ok", True)
    ):
        verif = "PASS WITH NOTES"
    elif ledger.get("verificationState") == "partial":
        verif = "PASS WITH NOTES"

    # P2 artifact versions (before research_run so path can be included)
    version_paths = [v for k, v in path_map.items() if v and k.endswith("_path")]
    if final_path:
        version_paths.append(final_path)
    vers = record_versions(
        root,
        slug=slug,
        paths=version_paths,
        stage="provenance",
        input_paths=[
            path_map.get("solution_path") or "",
            path_map.get("research_path") or "",
            path_map.get("schema_path") or "",
        ],
        source="orpath",
    )
    versions_path = root / "outputs" / ".artifacts" / f"{slug}-versions.json"
    path_map["versions_path"] = str(versions_path) if versions_path.is_file() else ""

    prov = root / "outputs" / f"{slug}.provenance.md"
    path_map["provenance_path"] = str(prov)

    # P2 research run manifest
    run = build_research_run(
        slug=slug,
        state=dict(state),
        paths={k: str(v) for k, v in path_map.items() if v},
        verification_state=str(ledger.get("verificationState") or "partial"),
        verification_summary=verif,
        claim_count=int(ledger.get("claimCount") or 0),
    )
    run_path = root / "outputs" / ".drafts" / f"{slug}-research-run.json"
    _, run_ok, run_errs = write_research_run(run_path, run)
    path_map["research_run_path"] = str(run_path)

    # P2 lab changelog
    lab = append_lab_changelog(
        root,
        slug=slug,
        title="paper pipeline provenance",
        bullets=[
            f"verification={verif}",
            f"vstate={ledger.get('verificationState')}",
            f"claims={ledger.get('claimCount')}",
            f"versions={vers.get('versionCount')}",
            f"research_run_ok={run_ok}",
            f"final={Path(final_path).name if final_path else 'n/a'}",
        ],
    )
    path_map["lab_changelog_path"] = str(lab)

    st = dict(state)
    st["verification_state"] = ledger.get("verificationState")
    st["final_candidate_path"] = final_path
    text = thick_provenance(
        slug=slug,
        state=st,
        paths={k: str(v) for k, v in path_map.items() if v},
        verification=verif,
        extra_lines=[
            f"- claimCount: {ledger.get('claimCount')}",
            f"- claim_summary: {ledger.get('summary')}",
            f"- artifact_versions: {vers.get('versionCount')} deps={vers.get('dependencyCount')}",
            f"- research_run_valid: {run_ok}" + (f" errors={run_errs}" if not run_ok else ""),
            f"- paper_protocol: P0+P1+P2+P3",
        ],
    )
    paper_prov = root / "papers" / f"{slug}.provenance.md"
    prov.write_text(text, encoding="utf-8")
    try:
        paper_prov.write_text(text, encoding="utf-8")
    except OSError:
        pass
    # re-record provenance file version
    record_versions(
        root,
        slug=slug,
        paths=[prov, run_path, versions_path],
        stage="provenance_finalize",
        input_paths=[path_map.get("paper_path") or "", path_map.get("solution_path") or ""],
        source="orpath",
    )
    append_plan_log(
        root,
        slug,
        stage="provenance",
        status=verif,
        detail=(
            f"final={Path(final_path).name if final_path else 'n/a'} "
            f"vstate={ledger.get('verificationState')} "
            f"run_ok={run_ok} vers={vers.get('versionCount')}"
        ),
        plan_file=state.get("plan_path"),
    )
    return {
        "stage": "end",
        "provenance_path": str(prov),
        "paper_path": str(dpaths["paper"]) if dpaths["paper"].is_file() else state.get("paper_path"),
        "verification_state": ledger.get("verificationState"),
        "final_candidate_path": final_path,
        "research_run_path": str(run_path),
        "versions_path": str(versions_path) if versions_path.is_file() else "",
    }


# ---------------------------------------------------------------------------
# Product graph facade (merged from nodes_product — ADR-0001 closeout)
# Core bodies above stay callable as _core_*; public node_* are wrapped.
# ---------------------------------------------------------------------------
from typing import Any  # noqa: E402

def _provenance_thick(state: ORPathState) -> dict[str, Any]:
    out = node_provenance(state)
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

