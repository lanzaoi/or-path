"""LG intake stage helpers (1.1 S5) — thin wrappers over tools/intake_*."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from gate_intake import check_intake_files  # noqa: E402
from intake_ocr import run_ocr  # noqa: E402
from intake_parse import run_parse  # noqa: E402


def _root(state: dict[str, Any]) -> Path:
    return Path(state["root"]).resolve()


def _sources_from_state(state: dict[str, Any]) -> list[Path]:
    raw = state.get("intake_sources") or []
    if isinstance(raw, str):
        raw = [p.strip() for p in raw.split(";") if p.strip()]
    out: list[Path] = []
    for item in raw:
        p = Path(str(item))
        if not p.is_absolute():
            p = _root(state) / p
        out.append(p)
    return out


def should_run_intake(state: dict[str, Any]) -> bool:
    if state.get("skip_intake", True):
        return False
    return bool(_sources_from_state(state))


def run_intake_ocr_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Node body: skip → orchestrate; else OCR → intake_parse."""
    root = _root(state)
    slug = state["slug"]
    if not should_run_intake(state):
        return {
            "stage": "orchestrate",
            "intake_skipped": True,
            "skip_intake": True,
            "gate_intake_ok": True,
            "last_error": "",
        }

    sources = _sources_from_state(state)
    notes = root / "notes"
    try:
        res = run_ocr(
            slug=slug,
            inputs=sources,
            root=root,
            notes_dir=notes,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "stage": "human_stop",
            "intake_skipped": False,
            "human_required": True,
            "gate_intake_ok": False,
            "last_error": f"intake_ocr failed: {exc}",
        }

    if res.status != "ok":
        return {
            "stage": "human_stop",
            "intake_skipped": False,
            "human_required": True,
            "gate_intake_ok": False,
            "ocr_raw_path": res.raw_path,
            "ocr_meta_path": res.meta_path,
            "last_error": "; ".join(res.warnings) or "intake_ocr status=error",
        }

    return {
        "stage": "intake_parse",
        "intake_skipped": False,
        "skip_intake": False,
        "ocr_raw_path": str(notes / f"{slug}-ocr.raw.md"),
        "ocr_meta_path": str(notes / f"{slug}-ocr.meta.json"),
        "last_error": "",
    }


def run_intake_parse_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Node body: parse OCR → brief + intake.json; optional human stop."""
    root = _root(state)
    slug = state["slug"]
    if state.get("intake_skipped") or state.get("skip_intake", True):
        return {
            "stage": "orchestrate",
            "gate_intake_ok": True,
            "last_error": "",
        }

    raw = Path(state.get("ocr_raw_path") or (root / "notes" / f"{slug}-ocr.raw.md"))
    meta = Path(state.get("ocr_meta_path") or (root / "notes" / f"{slug}-ocr.meta.json"))
    assets = state.get("intake_assets_dir") or ""
    assets_dir = Path(assets) if assets else None
    if assets_dir and not assets_dir.is_absolute():
        assets_dir = root / assets_dir

    try:
        pr = run_parse(
            slug=slug,
            ocr_raw=raw,
            ocr_meta=meta if meta.is_file() else None,
            root=root,
            notes_dir=root / "notes",
            outputs_dir=root / "outputs",
            assets_dir=assets_dir,
            run_gate=True,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "stage": "human_stop",
            "human_required": True,
            "gate_intake_ok": False,
            "last_error": f"intake_parse failed: {exc}",
        }

    intake_path = root / "outputs" / f"{slug}-intake.json"
    brief_path = root / "notes" / f"{slug}-problem-brief.md"
    gate_errs = list(pr.gate_errors)
    if not gate_errs and intake_path.is_file():
        gate_errs = check_intake_files(intake_path, brief_path=brief_path)

    out: dict[str, Any] = {
        "intake_path": str(intake_path) if intake_path.is_file() else pr.intake_path,
        "brief_path": str(brief_path) if brief_path.is_file() else pr.brief_path,
        "ocr_raw_path": str(raw),
        "ocr_meta_path": str(meta) if meta.is_file() else state.get("ocr_meta_path", ""),
        "gate_intake_ok": not gate_errs,
        "last_error": "; ".join(gate_errs) if gate_errs else "",
    }

    if gate_errs:
        out["stage"] = "human_stop"
        out["human_required"] = True
        return out

    # Optional human confirm when parse says needs_human or flag set
    status = (pr.intake or {}).get("status") or "ok"
    need_confirm = bool(state.get("human_confirm_intake")) or status == "needs_human"
    if need_confirm and not state.get("intake_confirmed"):
        out["stage"] = "human_stop"
        out["human_required"] = True
        out["last_error"] = out.get("last_error") or "intake awaiting human_confirm_intake / intake_confirmed"
        return out

    out["stage"] = "orchestrate"
    return out


def standalone_intake(
    *,
    root: Path,
    slug: str,
    sources: list[Path],
    assets_dir: Path | None = None,
) -> dict[str, Any]:
    """CLI path: OCR + parse + gate without LG."""
    root = root.resolve()
    notes = root / "notes"
    outputs = root / "outputs"
    ocr = run_ocr(slug=slug, inputs=sources, root=root, notes_dir=notes)
    if ocr.status != "ok":
        return {
            "ok": False,
            "error": ocr.warnings or ["ocr failed"],
            "ocr_raw_path": ocr.raw_path,
            "ocr_meta_path": ocr.meta_path,
        }
    raw = notes / f"{slug}-ocr.raw.md"
    meta = notes / f"{slug}-ocr.meta.json"
    pr = run_parse(
        slug=slug,
        ocr_raw=raw,
        ocr_meta=meta,
        root=root,
        notes_dir=notes,
        outputs_dir=outputs,
        assets_dir=assets_dir,
        run_gate=True,
    )
    intake_path = outputs / f"{slug}-intake.json"
    brief_path = notes / f"{slug}-problem-brief.md"
    return {
        "ok": not pr.gate_errors,
        "status": pr.status,
        "gate_errors": pr.gate_errors,
        "intake_path": str(intake_path),
        "brief_path": str(brief_path),
        "ocr_raw_path": str(raw),
        "ocr_meta_path": str(meta),
        "subproblems": len((pr.intake or {}).get("subproblems") or []),
        "intake": pr.intake,
    }
