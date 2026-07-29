"""P1 paper/knowledge workflow helpers (Feynman-inspired, OR-Path native).

P1-1 paper templates · P1-2 inline review helpers · P1-3 plan ledger
P1-4 research consumption gate · P1-5 drafts layering
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# P1-3 plan ledger
# ---------------------------------------------------------------------------

def plan_path(root: Path, slug: str) -> Path:
    return root / "outputs" / ".plans" / f"{slug}.md"


def append_plan_log(
    root: Path,
    slug: str,
    *,
    stage: str,
    status: str,
    detail: str = "",
    plan_file: str | Path | None = None,
) -> Path:
    """Append a verification-log line; create plan skeleton if missing."""
    p = Path(plan_file) if plan_file else plan_path(root, slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"- [{ts}] stage=`{stage}` status=`{status}`"
    if detail:
        line += f" — {detail.replace(chr(10), ' ')[:300]}"
    if not p.is_file():
        p.write_text(
            f"# Plan {slug}\n\n## Task ledger\n(see stages)\n\n## Verification log\n",
            encoding="utf-8",
        )
    text = p.read_text(encoding="utf-8")
    if "## Verification log" not in text:
        text = text.rstrip() + "\n\n## Verification log\n"
    # mark task ledger checkbox if present
    text2 = re.sub(
        rf"- \[ \] {re.escape(stage)}\b",
        f"- [x] {stage}",
        text,
        count=1,
    )
    if not text2.endswith("\n"):
        text2 += "\n"
    text2 += line + "\n"
    p.write_text(text2, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# P1-5 drafts layering
# ---------------------------------------------------------------------------

def drafts_dir(root: Path) -> Path:
    d = root / "outputs" / ".drafts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def draft_paths(root: Path, slug: str) -> dict[str, Path]:
    d = drafts_dir(root)
    return {
        "draft": d / f"{slug}-draft.md",
        "cited": d / f"{slug}-cited.md",
        "revised": d / f"{slug}-revised.md",
        "verification": d / f"{slug}-verification.md",
        "claim_ledger": d / f"{slug}-claim-ledger.json",
        "claim_map": d / f"{slug}-claim-map.json",
        "revise_proof": d / f"{slug}-revise-proof.md",
        "paper": root / "papers" / f"{slug}.md",
        "review": root / "outputs" / f"{slug}-review.md",
        "verify_notes": root / "outputs" / f"{slug}-verify-notes.md",
        "provenance": root / "outputs" / f"{slug}.provenance.md",
        "plan": root / "outputs" / ".plans" / f"{slug}.md",
    }


# ---------------------------------------------------------------------------
# P1-1 paper templates
# ---------------------------------------------------------------------------

OR_PAPER_SECTIONS = [
    "Title",
    "Abstract",
    "Problem statement",
    "Related modeling notes",
    "Method / formulation",
    "Results",
    "Validation",
    "Limitations",
    "Sources",
]


def render_or_paper(
    *,
    slug: str,
    problem_class: str,
    problem_id: str,
    solution: dict[str, Any],
    solution_path: str,
    schema_path: str = "",
    research_path: str = "",
    retrieval_path: str = "",
    validate_path: str = "",
    explain_path: str = "",
    fixture_rel: str = "",
    source_lines: list[str] | None = None,
    template: str = "or",
) -> str:
    """Deterministic OR paper body (portfolio/contest skins share evidence rules)."""
    meta = solution.get("meta") or {}
    exact = meta.get("exact")
    proven = meta.get("proven_optimal")
    shape = solution.get("path") or solution.get("tour") or solution.get("routes")
    if shape is None and solution.get("placements") is not None:
        shape = f"placements×{len(solution.get('placements') or [])}"
    honesty = (
        "exact/proven optimal under solver model"
        if proven
        else (
            "search/feasible track — not proven global optimum"
            if exact is False
            else "see solution.meta"
        )
    )
    sources = source_lines or []
    src_block = "\n".join(f"- {s}" for s in sources) if sources else "- (none)"

    if template == "mcm":
        title = f"数模风写稿（OR 绑定）: {slug}"
        abstract_extra = "本稿数字仅绑定求解器 JSON，禁止启发式冒充全局最优。"
    else:
        title = f"OR Fixture Study ({slug})"
        abstract_extra = "All numerics bind to solver JSON + validate."

    return f"""# {title}

## Abstract
We study a `{problem_class}` instance (`{problem_id}`) with deterministic OR tools.
Solver honesty: **{honesty}**. {abstract_extra}

## Problem statement
- problem_id: `{problem_id}`
- problem_class: `{problem_class}`
- fixture: `{fixture_rel or "n/a"}`

## Related modeling notes
- Research: `{research_path or "n/a"}`
- Retrieval: `{retrieval_path or "n/a"}`
- Explain: `{explain_path or "n/a"}`

Evidence for modeling claims must appear in the research evidence table (paths/chunk_ids).

## Method / formulation
- Schema: `{schema_path or "n/a"}`
- Solver owns optima; LLM must not invent objective/path/tour/routes.
- Preferred stack: exact tracks (NetworkX / CP-SAT / HiGHS) when applicable; OR-Tools Routing as scale extension only.

## Results
From `{solution_path}` only:
- status: `{solution.get("status")}`
- objective = `{solution.get("objective")}`
- solver: `{solution.get("solver")}`
- solution_shape: `{shape}`
- meta.exact: `{exact}`
- meta.proven_optimal: `{proven}`
- meta.method_class: `{meta.get("method_class")}`

Claim: objective equals `{solution.get("objective")}` from solution.json (solver-owned).
Claim: solution status is `{solution.get("status")}` under declared solve_mode.
Finding: exactness flags are exact=`{exact}` proven_optimal=`{proven}`.

## Validation
- validate report: `{validate_path or "n/a"}`
- Feasibility and objective recomputed by `validate_solution` when available.

## Limitations
- Fixture or declared scale only.
- If `proven_optimal` is not true, do not claim global optimality.
- Live multi-agent prose quality is separate from gate-green numerics.

## Sources
{src_block}
"""


# ---------------------------------------------------------------------------
# P1-4 research consumption
# ---------------------------------------------------------------------------

def load_retrieval(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def extract_retrieval_ids(retrieval: dict[str, Any]) -> dict[str, list[str]]:
    chunk_ids: list[str] = []
    seed_ids: list[str] = []
    for h in retrieval.get("hits") or []:
        cid = h.get("chunk_id") or h.get("id")
        if cid:
            chunk_ids.append(str(cid))
    for s in retrieval.get("seed_facts") or []:
        sid = s.get("id") or s.get("node_id")
        if sid:
            seed_ids.append(str(sid))
    return {"chunk_ids": chunk_ids, "seed_ids": seed_ids}


def gate_research_text(
    research_md: str,
    *,
    knowledge_mode: str,
    retrieval: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Return (ok, errors). hybrid/seed must cite retrieval ids when present."""
    errors: list[str] = []
    if "## Evidence table" not in research_md and "| # | Source |" not in research_md:
        errors.append("missing Evidence table section")
    if "## Coverage Status" not in research_md and "Coverage Status" not in research_md:
        errors.append("missing Coverage Status section")

    mode = (knowledge_mode or "off").lower()
    ids = extract_retrieval_ids(retrieval)
    if mode == "off":
        return (len(errors) == 0, errors)

    # seed or hybrid: if retrieval produced ids, research must mention at least one
    need = ids["chunk_ids"] + ids["seed_ids"]
    if mode == "hybrid" and (retrieval.get("hits") or retrieval.get("seed_facts")):
        if not need:
            # empty hits allowed but must say so in coverage
            if "hits: []" not in research_md and "no hits" not in research_md.lower() and "empty" not in research_md.lower():
                if not retrieval.get("hits") and not retrieval.get("seed_facts"):
                    errors.append("hybrid mode but retrieval empty and research does not declare empty hits")
        else:
            if not any(i in research_md for i in need):
                errors.append(
                    "hybrid/seed retrieval ids not cited in research (need chunk_id or seed id)"
                )
    elif mode == "seed":
        if ids["seed_ids"] and not any(i in research_md for i in ids["seed_ids"]):
            # also allow citing via seed table rows built from labels
            if "seed |" not in research_md and "seed_graph" not in research_md:
                errors.append("seed_facts present but research does not cite seed ids")

    return (len(errors) == 0, errors)


def ensure_research_coverage_section(body: str, retrieval: dict[str, Any]) -> str:
    if "Coverage Status" in body:
        return body
    ids = extract_retrieval_ids(retrieval)
    extra = f"""

## Coverage Status
- knowledge_mode: {retrieval.get("knowledge_mode")}
- hits: {len(retrieval.get("hits") or [])}
- seed_facts: {len(retrieval.get("seed_facts") or [])}
- chunk_ids_seen: {", ".join(ids["chunk_ids"][:12]) or "(none)"}
- seed_ids_seen: {", ".join(ids["seed_ids"][:12]) or "(none)"}
- checked_directly: retrieval artifact + fixture problem.md
- uncertain: full-text of non-local URLs not fetched in CI stand-in
"""
    return body.rstrip() + extra + "\n"


# ---------------------------------------------------------------------------
# P1-2 inline review annotations
# ---------------------------------------------------------------------------

def build_review_markdown(
    *,
    slug: str,
    paper_text: str,
    r1_ok: bool,
    r1_msg: str,
    r2_ok: bool,
    r2_msg: str,
    validate_ok: bool | None,
    research_ok: bool | None = None,
    research_msg: str = "",
) -> tuple[str, int]:
    """Feynman-style structured review + inline annotations. Returns (md, fatal_count)."""
    fatals: list[str] = []
    majors: list[str] = []
    inlines: list[str] = []

    if not r2_ok:
        fatals.append(f"R2 failed: {r2_msg}")
        # try quote objective line
        m = re.search(r"^.*objective.*$", paper_text, re.I | re.M)
        if m:
            inlines.append(
                f"> {m.group(0).strip()}\n"
                f"**[W-R2] FATAL:** Numeric claim fails R2 against solution.json — {r2_msg}"
            )
    if not r1_ok:
        fatals.append(f"R1 failed: {r1_msg}")
        m = re.search(r"https?://\S+", paper_text)
        if m:
            inlines.append(
                f"> ... {m.group(0)} ...\n"
                f"**[W-R1] FATAL:** Citation/URL not on whitelist — {r1_msg}"
            )
        else:
            inlines.append(
                f"> (Sources section)\n**[W-R1] FATAL:** {r1_msg}"
            )
    if research_ok is False:
        majors.append(f"Research gate: {research_msg}")
        inlines.append(
            f"> Related modeling notes\n**[W-K] MAJOR:** Research evidence consumption failed — {research_msg}"
        )
    if validate_ok is False:
        majors.append("Validate gate was not green earlier in pipeline")

    # honesty: claim global opt without proven
    if re.search(r"global(?:ly)?\s+optimal|保证全局最优|数学证明最优", paper_text, re.I):
        if not re.search(r"proven_optimal[`\s:=]+true|proven_optimal\s*=\s*true", paper_text, re.I):
            majors.append("Uses global-opt language without proven_optimal=true in prose")
            inlines.append(
                "> (optimality wording)\n"
                "**[W-H] MAJOR:** Avoid marketing global optimality unless solution.meta.proven_optimal is true."
            )

    body = [f"## Summary\nP1 review pack `{slug}` (gates + inline annotations).\n"]
    body.append("## Strengths")
    if r1_ok and r2_ok:
        body.append("- [S1] R1 and R2 scripts green on current draft.")
    else:
        body.append("- [S1] (blocked by FATAL gates)")
    body.append("\n## Weaknesses")
    wi = 1
    for f in fatals:
        body.append(f"- [W{wi}] **FATAL:** {f}")
        wi += 1
    for mmsg in majors:
        body.append(f"- [W{wi}] **MAJOR:** {mmsg}")
        wi += 1
    if not fatals and not majors:
        body.append("- None FATAL/MAJOR from automated pack.")
    body.append("\n## Questions for Authors")
    body.append("- [Q1] Confirm every numeric maps to solution.json and validate report.")
    body.append("\n## Verdict")
    body.append(
        f"r1={r1_ok} r2={r2_ok} validate={validate_ok} research_gate={research_ok}"
    )
    body.append("\n## Revision Plan")
    if fatals:
        body.append("1. Fix FATAL gate failures (R1 whitelist / R2 numerics).")
        body.append("2. Rewrite affected Results/Sources spans.")
        body.append("3. Re-run R1+R2 before delivery.")
    else:
        body.append("1. No FATAL — optional polish only.")
    body.append("\n## Inline Annotations")
    if inlines:
        body.extend(["", *inlines])
    else:
        body.append("\n_(no span-level FATAL quotes; gates clean)_")
    text = "\n".join(body) + "\n"
    fatal_count = len(re.findall(r"\*\*FATAL:\*\*", text))
    return text, fatal_count


def apply_revise_fixes(
    paper_text: str,
    *,
    solution: dict[str, Any],
    allowed_urls: list[str],
    solution_path: str,
) -> str:
    """Best-effort deterministic revise for CI: strip bad URLs, force objective from solution."""
    text = paper_text
    # remove http URLs not in allow list
    allow = set(allowed_urls)

    def _url_ok(u: str) -> bool:
        u2 = u.rstrip(".,;)]}>\"'")
        if u2 in allow:
            return True
        an = {a.rstrip("/") for a in allow}
        return u2.rstrip("/") in an

    def repl_url(m: re.Match[str]) -> str:
        u = m.group(0)
        return u if _url_ok(u) else "[removed-non-whitelist-url]"

    text = re.sub(r"https?://[^\s)\]>\"']+", repl_url, text)
    obj = solution.get("objective")
    if obj is not None:
        # normalize objective lines
        text = re.sub(
            r"(objective\s*[=:]\s*)(`?)([^`\n]+)(`?)",
            rf"\1`{obj}`",
            text,
            flags=re.I,
        )
    if f"`{solution_path}`" not in text and solution_path not in text:
        text = text.rstrip() + f"\n\n## Revise note\n- rebound to `{solution_path}` objective=`{obj}`\n"
    return text


def thick_provenance(
    *,
    slug: str,
    state: dict[str, Any],
    paths: dict[str, str],
    verification: str,
    extra_lines: list[str] | None = None,
) -> str:
    lines = [
        f"# Provenance {slug}",
        f"- utc: {datetime.now(timezone.utc).isoformat()}",
        f"- problem_class: {state.get('problem_class')}",
        f"- solve_mode: {state.get('solve_mode')}",
        f"- knowledge_mode: {state.get('knowledge_mode')}",
        f"- revise_count: {state.get('revise_count')}",
        f"- human_required: {state.get('human_required')}",
        f"- gate_schema_ok: {state.get('gate_schema_ok')}",
        f"- gate_validate_ok: {state.get('gate_validate_ok')}",
        f"- gate_r1_ok: {state.get('gate_r1_ok')}",
        f"- gate_r2_ok: {state.get('gate_r2_ok')}",
        f"- gate_claim_ok: {state.get('gate_claim_ok')}",
        f"- Verification: {verification}",
        f"- verificationState: {state.get('verification_state') or 'n/a'}",
        f"- final_candidate: {state.get('final_candidate_path') or 'n/a'}",
        "",
        "## Artifacts",
    ]
    for k, v in paths.items():
        if v:
            lines.append(f"- {k}: `{v}`")
    lines += [
        "",
        "## Notes",
        "P0/P1 paper workflow: drafts layered + cite/claim-map + claim ledger + plan ledger + research gate.",
        "Final candidate rule (Feynman): revised > cited > draft > paper.",
    ]
    if extra_lines:
        lines.extend(["", *extra_lines])
    return "\n".join(lines) + "\n"
