"""P2: mini ResearchRun manifest (inspired by feynman.researchRun.v1, OR-native)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "orpath.researchRun.v1"
JOBS = (
    "retrieve_knowledge",
    "research_evidence",
    "model_schema",
    "solve",
    "validate",
    "draft_paper",
    "cite_pack",
    "review",
    "revise",
    "provenance",
)
VERIFICATION_STATES = (
    "not_checked",
    "inferred",
    "partial",
    "verified",
    "blocked",
    "failed",
)
RUN_STATUSES = ("planned", "running", "completed", "partial", "blocked", "failed")


def build_run_id(workflow: str, slug: str, generated_at: str) -> str:
    digest = hashlib.sha256(f"{workflow}\0{slug}\0{generated_at}".encode()).hexdigest()[:16]
    return f"{workflow}:{slug}:{digest}"


def validate_research_run(run: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if run.get("schemaVersion") != SCHEMA:
        errors.append(f"schemaVersion must be {SCHEMA}")
    for k in ("runId", "workflow", "slug", "topic", "generatedAt", "status"):
        if not str(run.get(k) or "").strip():
            errors.append(f"{k} is required")
    if run.get("status") not in RUN_STATUSES:
        errors.append(f"status unsupported: {run.get('status')}")
    jobs = run.get("researchJobs") or []
    if not jobs:
        errors.append("researchJobs must be non-empty")
    for j in jobs:
        if j not in JOBS:
            errors.append(f"unsupported job: {j}")
    arts = run.get("artifacts") or []
    if not arts:
        errors.append("artifacts must be non-empty")
    if not any(a.get("primary") for a in arts):
        errors.append("at least one artifact must be primary")
    for a in arts:
        if not a.get("path") or not a.get("role"):
            errors.append(f"artifact path/role required: {a}")
    v = (run.get("verification") or {}).get("state")
    if v not in VERIFICATION_STATES:
        errors.append(f"verification.state unsupported: {v}")
    # OR-Path: never claim raw fulltext blob stored in manifest
    constraints = run.get("constraints") or {}
    if constraints.get("rawFullTextStored"):
        errors.append("rawFullTextStored must be false")
    return len(errors) == 0, errors


def build_research_run(
    *,
    slug: str,
    state: dict[str, Any],
    paths: dict[str, str],
    verification_state: str,
    verification_summary: str,
    claim_count: int = 0,
) -> dict[str, Any]:
    generated = datetime.now(timezone.utc).isoformat()
    workflow = "orpath_product_paper"
    # jobs completed based on path presence / gates
    jobs: list[str] = []
    mapping = [
        ("retrieve_knowledge", "retrieval_path"),
        ("research_evidence", "research_path"),
        ("model_schema", "schema_path"),
        ("solve", "solution_path"),
        ("validate", "validate_path"),
        ("draft_paper", "draft_path"),
        ("cite_pack", "cited_path"),
        ("review", "review_path"),
        ("revise", "revised_path"),
        ("provenance", "provenance_path"),
    ]
    for job, key in mapping:
        p = paths.get(key) or ""
        if p and Path(p).is_file():
            jobs.append(job)
    if not jobs:
        jobs = ["provenance"]

    artifacts: list[dict[str, Any]] = []
    role_map = {
        "solution_path": ("json", "solution", "numbers_truth"),
        "paper_path": ("report", "paper", "final_narrative"),
        "cited_path": ("report", "cited_draft", "intermediate"),
        "draft_path": ("report", "draft", "intermediate"),
        "revised_path": ("report", "revised", "intermediate"),
        "review_path": ("audit", "review", "review"),
        "verification_path": ("audit", "verification", "verification"),
        "claim_ledger_path": ("ledger", "claim_ledger", "claims"),
        "provenance_path": ("provenance", "provenance", "source_accounting"),
        "research_path": ("report", "research", "evidence"),
        "plan_path": ("plan", "plan", "task_ledger"),
        "versions_path": ("ledger", "artifact_versions", "versioning"),
        "annotations_path": ("json", "annotations", "review_annotations"),
        "figure_path": ("html", "figure", "visual"),
    }
    primary_set = False
    for key, (kind, label, role) in role_map.items():
        p = paths.get(key) or ""
        if not p:
            continue
        primary = False
        if key == "paper_path" and not primary_set:
            primary = True
            primary_set = True
        elif key == "solution_path" and not primary_set:
            primary = True
            primary_set = True
        artifacts.append(
            {
                "kind": kind,
                "path": p.replace("\\", "/"),
                "label": label,
                "role": role,
                "primary": primary,
            }
        )
    if artifacts and not any(a.get("primary") for a in artifacts):
        artifacts[0]["primary"] = True

    vstate = verification_state if verification_state in VERIFICATION_STATES else "partial"
    status = "completed"
    if state.get("human_required") or vstate in {"blocked", "failed"}:
        status = "blocked" if vstate != "failed" else "failed"
    elif vstate == "partial":
        status = "partial"

    run = {
        "schemaVersion": SCHEMA,
        "runId": build_run_id(workflow, slug, generated),
        "workflow": workflow,
        "slug": slug,
        "topic": f"{state.get('problem_class')}:{state.get('problem_id')}",
        "generatedAt": generated,
        "status": status,
        "researchJobs": jobs,
        "sources": [
            {
                "id": "solution",
                "kind": "fixture",
                "path": paths.get("solution_path"),
                "fields": ["objective", "status", "meta"],
            },
            {
                "id": "retrieval",
                "kind": "other",
                "path": paths.get("retrieval_path"),
                "fields": ["hits", "seed_facts"],
            },
        ],
        "papers": [],
        "entities": [],
        "tools": [
            {"id": "solve", "kind": "experiment_runner", "label": "OR solve tools", "status": "completed"},
            {"id": "r1_claim_map", "kind": "rank_scorer", "label": "claim map gate", "status": "completed"},
            {"id": "claim_ledger", "kind": "artifact_exporter", "label": "claim ledger", "status": "completed"},
        ],
        "artifacts": artifacts,
        "nextActions": [],
        "verification": {
            "state": vstate,
            "summary": verification_summary,
            "caveats": [
                "claim_ledger is traceability, not full NLI",
                "solve numbers only from solution.json",
            ],
            "claimCount": claim_count,
        },
        "constraints": {
            "rawFullTextStored": False,
            "promptsStored": False,
            "modelOutputsStored": False,
        },
        "orpath": {
            "solve_mode": state.get("solve_mode"),
            "knowledge_mode": state.get("knowledge_mode"),
            "gate_r1_ok": state.get("gate_r1_ok"),
            "gate_r2_ok": state.get("gate_r2_ok"),
            "gate_claim_ok": state.get("gate_claim_ok"),
            "gate_validate_ok": state.get("gate_validate_ok"),
        },
    }
    return run


def write_research_run(path: Path, run: dict[str, Any]) -> tuple[Path, bool, list[str]]:
    ok, errors = validate_research_run(run)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path, ok, errors
