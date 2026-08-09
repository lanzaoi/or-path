"""Human steer + Watch dialogue digests (no LLM).

Law: specs/human-steer-and-pi-guidance.md
- Control fields → LG/runner (apply_steer_to_state)
- Cognitive fields → next Pi spawn (format_pi_steer_block)
- Never accept objective/tour/routes as steer input
- Dialogue bubbles are pure transforms of disk snapshot parts
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STEER_SCHEMA_VERSION = 1
STEER_FILENAME = "human-steer.json"  # under notes/ as notes/<slug>-human-steer.json

ALLOWED_SOLVE_MODES = frozenset(
    {
        "mock",
        "networkx",
        "ortools",
        "cpsat",
        "highs",
        "polyomino",
        "polyomino_cover",
        "poly",
        "tube",
        "tube_cut",
        "tube_bfd",
    }
)

# at_stage / resume_from → pause BEFORE this product node
_PAUSE_BEFORE: dict[str, str] = {
    "research": "research",
    "after_research": "model",
    "model": "model",
    "solve": "solve",
    "gate_validate": "gate_validate",
    "after_validate": "explain",
    "explain": "explain",
    "retrieve": "retrieve",
    "bridge_pi": "bridge_pi",
}

# Keys that must never appear as editable number authority via steer
_FORBIDDEN_NUMBER_KEYS = frozenset(
    {
        "objective",
        "tour",
        "routes",
        "path",
        "proven_optimal",
        "global_optimal",
        "optima",
        "best_cost",
    }
)

_NODE_ZH = {
    "intake_ocr": "题面识别",
    "intake_parse": "题面解析",
    "orchestrate": "编排",
    "retrieve": "检索",
    "bridge_pi": "桥接",
    "research": "调研",
    "model": "建模",
    "gate_schema": "结构门禁",
    "solve": "求解",
    "gate_validate": "校验",
    "human_stop": "人工确认",
    "explain": "解释",
    "draft_paper": "写稿",
    "cite_pack": "引用打包",
    "review_pack": "审稿",
    "revise_or_done": "修订/完成",
    "provenance": "溯源",
    "end": "结束",
}

_ROLE_SYSTEM = "system"
_ROLE_RESEARCH = "research"
_ROLE_MODEL = "model"
_ROLE_SOLVE = "solve"
_ROLE_VALIDATE = "validate"
_ROLE_HUMAN = "human"
_ROLE_PI = "pi"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def steer_path(workdir: Path, slug: str) -> Path:
    safe = re.sub(r"[^\w.\-]+", "_", (slug or "run").strip()) or "run"
    return Path(workdir) / "notes" / f"{safe}-human-steer.json"


def _clip(text: str, n: int = 280) -> str:
    t = (text or "").replace("\r\n", "\n").strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _node_label(node: str) -> str:
    k = str(node or "").strip()
    zh = _NODE_ZH.get(k)
    return f"{zh} · {k}" if zh else (k or "—")


def find_forbidden_keys(obj: Any, path: str = "") -> list[str]:
    """Return dotted paths of forbidden number-authority keys."""
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kk = str(k)
            low = kk.lower()
            here = f"{path}.{kk}" if path else kk
            if low in _FORBIDDEN_NUMBER_KEYS or low.replace("-", "_") in _FORBIDDEN_NUMBER_KEYS:
                hits.append(here)
            hits.extend(find_forbidden_keys(v, here))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(find_forbidden_keys(v, f"{path}[{i}]"))
    return hits


def normalize_steer_payload(
    body: dict[str, Any],
    *,
    slug: str,
    source: str = "watch_form",
) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate + normalize POST body → steer document.

    Returns (doc, errors). doc is None if errors non-empty.
    """
    errs: list[str] = []
    if not isinstance(body, dict):
        return None, ["body must be object"]

    forbid = find_forbidden_keys(body)
    if forbid:
        return None, [f"forbidden number key: {p}" for p in forbid]

    lg_in = body.get("lg") if isinstance(body.get("lg"), dict) else {}
    pi_in = body.get("pi") if isinstance(body.get("pi"), dict) else {}
    # Also accept flat form fields
    if body.get("solve_mode") and not lg_in.get("solve_mode"):
        lg_in = {**lg_in, "solve_mode": body.get("solve_mode")}
    if body.get("resume_from") and not lg_in.get("resume_from"):
        lg_in = {**lg_in, "resume_from": body.get("resume_from")}
    if "pause_next" in body and "pause_next" not in lg_in:
        lg_in = {**lg_in, "pause_next": body.get("pause_next")}
    if "fresh" in body and "fresh" not in lg_in:
        lg_in = {**lg_in, "fresh": body.get("fresh")}
    if body.get("notes") and not pi_in.get("notes"):
        pi_in = {**pi_in, "notes": body.get("notes")}
    if body.get("prefer_methods") and not pi_in.get("prefer_methods"):
        pm = body.get("prefer_methods")
        if isinstance(pm, str):
            pm = [x.strip() for x in pm.split(",") if x.strip()]
        pi_in = {**pi_in, "prefer_methods": pm}
    if body.get("at_stage"):
        at_stage = str(body.get("at_stage") or "").strip()
    else:
        at_stage = str(lg_in.get("at_stage") or body.get("stage") or "manual").strip()

    lg: dict[str, Any] = {}
    sm = str(lg_in.get("solve_mode") or "").strip()
    if sm:
        lg["solve_mode"] = sm
    rf = str(lg_in.get("resume_from") or "").strip()
    if rf:
        lg["resume_from"] = rf
    if "fresh" in lg_in:
        lg["fresh"] = bool(lg_in.get("fresh"))
    if "pause_next" in lg_in:
        lg["pause_next"] = bool(lg_in.get("pause_next"))

    pi: dict[str, Any] = {}
    notes = str(pi_in.get("notes") or "").strip()
    if notes:
        pi["notes"] = _clip(notes, 2000)
    pm2 = pi_in.get("prefer_methods")
    if isinstance(pm2, list):
        pi["prefer_methods"] = [str(x).strip() for x in pm2 if str(x).strip()][:12]
    elif isinstance(pm2, str) and pm2.strip():
        pi["prefer_methods"] = [x.strip() for x in pm2.split(",") if x.strip()][:12]
    mh = str(pi_in.get("modeling_hints") or "").strip()
    if mh:
        pi["modeling_hints"] = _clip(mh, 800)
    fids = pi_in.get("focus_chunk_ids")
    if isinstance(fids, list):
        pi["focus_chunk_ids"] = [str(x) for x in fids if str(x).strip()][:20]

    if not lg and not pi and not notes:
        # allow empty notes-only rejection
        if not str(body.get("notes") or "").strip():
            errs.append("empty steer: provide lg.solve_mode / resume_from and/or pi.notes")

    if errs:
        return None, errs

    doc = {
        "schema_version": STEER_SCHEMA_VERSION,
        "slug": str(slug or "").strip() or "run",
        "utc": _utc(),
        "at_stage": at_stage or "manual",
        "lg": lg,
        "pi": pi,
        "source": str(source or "watch_form"),
        "forbid_numbers_edit": True,
    }
    return doc, []


def save_human_steer(workdir: Path, slug: str, doc: dict[str, Any]) -> Path:
    path = steer_path(workdir, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # append history
    hist = path.with_suffix(".jsonl")
    with hist.open("a", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    return path


def load_human_steer(workdir: Path, slug: str) -> dict[str, Any] | None:
    path = steer_path(workdir, slug)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def build_steer_cta(doc: dict[str, Any], *, workdir: Path | None = None) -> list[dict[str, str]]:
    """Copyable commands for human (no browser auto-resume)."""
    acts: list[dict[str, str]] = []
    lg = doc.get("lg") if isinstance(doc.get("lg"), dict) else {}
    slug = str(doc.get("slug") or "run")
    mode = str(lg.get("solve_mode") or "").strip()
    resume = str(lg.get("resume_from") or "").strip()
    fresh = bool(lg.get("fresh"))
    wd = f' --workdir "{workdir}"' if workdir else ""

    if mode:
        cmd = f"orpath.bat run{wd} --slug {slug} --thread-id {slug} --solve-mode {mode}"
        if fresh:
            cmd += " --fresh"
        acts.append(
            {
                "title": f"用 solve-mode={mode} 重跑",
                "command": cmd,
                "reason": "人导 lg.solve_mode → 控制面 runner（非 Pi 聊天改数）",
            }
        )
    if resume:
        acts.append(
            {
                "title": f"从阶段续跑提示 · {resume}",
                "command": (
                    f"orpath.bat run{wd} --slug {slug} --thread-id {slug}"
                    + (f" --solve-mode {mode}" if mode else "")
                    + "  :: resume_from="
                    + resume
                    + "（若 CLI 支持 from-stage 则替换；否则 --fresh 全链）"
                ),
                "reason": "人导 lg.resume_from；以本机 runner 实际 flag 为准",
            }
        )
    pi = doc.get("pi") if isinstance(doc.get("pi"), dict) else {}
    if pi.get("notes") or pi.get("prefer_methods"):
        acts.append(
            {
                "title": "查看已写入的人导单",
                "command": f'type notes\\{slug}-human-steer.json'
                if not workdir
                else f'type "{Path(workdir) / "notes" / (slug + "-human-steer.json")}"',
                "reason": "认知字段 pi.* 供下一站 Pi 任务书读取（D2 接线后自动）",
            }
        )
    if not acts:
        acts.append(
            {
                "title": "人导已落盘",
                "command": f"notes\\{slug}-human-steer.json",
                "reason": "无控制字段；仅记录偏好",
            }
        )
    return acts


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _resolve_art(workdir: Path, rel_or_abs: str | None) -> Path | None:
    if not rel_or_abs:
        return None
    p = Path(rel_or_abs)
    if p.is_file():
        return p
    cand = Path(workdir) / rel_or_abs
    return cand if cand.is_file() else None


def build_dialogue(
    *,
    workdir: Path,
    slug: str,
    stages: list[dict[str, Any]],
    current: dict[str, Any] | None,
    status: str,
    artifacts: dict[str, Any] | None,
    honesty_messages: list[str] | None = None,
    max_bubbles: int = 48,
) -> dict[str, Any]:
    """Rule-based dialogue digest for Watch (no LLM)."""
    bubbles: list[dict[str, Any]] = []
    wd = Path(workdir)
    arts = artifacts or {}

    bubbles.append(
        {
            "id": "sys-head",
            "role": _ROLE_SYSTEM,
            "title": "过程台",
            "text": f"任务 {slug} · 状态 {status} · 以下为磁盘阶段精要（非 LLM 编造）",
            "utc": _utc(),
            "source": "snapshot",
        }
    )

    # Collapse stages: keep last occurrence per node + all errors
    seen_nodes: dict[str, dict[str, Any]] = {}
    for st in stages or []:
        if not isinstance(st, dict):
            continue
        node = str(st.get("node") or st.get("stage") or "")
        seen_nodes[node or f"seq-{st.get('seq')}"] = st

    ordered = list(stages or [])
    # Prefer chronological list; cap
    for st in ordered[-40:]:
        if not isinstance(st, dict):
            continue
        node = str(st.get("node") or st.get("stage") or "stage")
        role = _ROLE_SYSTEM
        low = node.lower()
        if "research" in low or "retrieve" in low:
            role = _ROLE_RESEARCH
        elif "model" in low or "schema" in low:
            role = _ROLE_MODEL
        elif low == "solve":
            role = _ROLE_SOLVE
        elif "validate" in low:
            role = _ROLE_VALIDATE
        elif "human" in low:
            role = _ROLE_HUMAN
        elif any(x in low for x in ("bridge", "cite", "review", "explain", "draft")):
            role = _ROLE_PI

        err = str(st.get("last_error") or "").strip()
        hr = bool(st.get("human_required"))
        parts = [_node_label(node)]
        if st.get("seq") is not None:
            parts.insert(0, f"#{st.get('seq')}")
        state = st.get("state") or st.get("status") or ""
        if state:
            parts.append(str(state))
        text = " · ".join(str(p) for p in parts if p)
        if err:
            text += f"\n⚠ { _clip(err, 200) }"
        if hr:
            text += "\n需要人工确认"
        bubbles.append(
            {
                "id": f"stage-{st.get('seq')}-{node}",
                "role": role,
                "title": _node_label(node),
                "text": text,
                "utc": st.get("utc") or st.get("generated_utc") or "",
                "source": "stages",
                "seq": st.get("seq"),
                "node": node,
            }
        )

    # Solution / validate digests
    sol_p = _resolve_art(wd, arts.get("solution") if isinstance(arts.get("solution"), str) else None)
    sol = _read_json(sol_p)
    if sol:
        meta = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
        obj = sol.get("objective")
        st_s = sol.get("status")
        method = meta.get("method_class") or meta.get("solver") or sol.get("solver") or ""
        exact = meta.get("exact")
        proven = meta.get("proven_optimal")
        lines = [
            f"status={st_s}",
            f"objective={obj}" if obj is not None else "objective=—",
        ]
        if method:
            lines.append(f"method={method}")
        if exact is not None:
            lines.append(f"exact={exact}")
        if proven is not None:
            lines.append(f"proven_optimal={proven}")
        bubbles.append(
            {
                "id": "solve-art",
                "role": _ROLE_SOLVE,
                "title": "求解结果（磁盘）",
                "text": " · ".join(lines),
                "utc": "",
                "source": "solution.json",
            }
        )

    val_p = _resolve_art(wd, arts.get("validate") if isinstance(arts.get("validate"), str) else None)
    val = _read_json(val_p)
    if val:
        ok = val.get("ok")
        errs = val.get("errors") or val.get("checks") or []
        msg = f"validate ok={ok}"
        if isinstance(errs, list) and errs and not ok:
            msg += " · " + _clip(json.dumps(errs, ensure_ascii=False)[:200], 200)
        bubbles.append(
            {
                "id": "val-art",
                "role": _ROLE_VALIDATE,
                "title": "校验（磁盘）",
                "text": msg,
                "utc": "",
                "source": "validate.json",
            }
        )

    # Schema preferred mode
    sch_p = _resolve_art(wd, arts.get("schema") if isinstance(arts.get("schema"), str) else None)
    sch = _read_json(sch_p)
    if sch:
        psm = sch.get("preferred_solve_mode") or (sch.get("meta") or {}).get("preferred_solve_mode")
        pc = sch.get("problem_class") or sch.get("class")
        if psm or pc:
            bubbles.append(
                {
                    "id": "model-art",
                    "role": _ROLE_MODEL,
                    "title": "建模摘要",
                    "text": f"class={pc or '—'} · preferred_solve_mode={psm or '—'}",
                    "utc": "",
                    "source": "schema",
                }
            )

    steer = load_human_steer(wd, slug)
    if steer:
        lg = steer.get("lg") if isinstance(steer.get("lg"), dict) else {}
        pi = steer.get("pi") if isinstance(steer.get("pi"), dict) else {}
        bits = []
        if lg.get("solve_mode"):
            bits.append(f"mode={lg.get('solve_mode')}")
        if lg.get("resume_from"):
            bits.append(f"resume={lg.get('resume_from')}")
        if pi.get("prefer_methods"):
            bits.append("methods=" + ",".join(pi.get("prefer_methods") or []))
        if pi.get("notes"):
            bits.append(_clip(str(pi.get("notes")), 160))
        bubbles.append(
            {
                "id": "human-steer",
                "role": _ROLE_HUMAN,
                "title": "人导（已落盘）",
                "text": " · ".join(bits) if bits else "steer 文件存在",
                "utc": str(steer.get("utc") or ""),
                "source": "human-steer.json",
            }
        )

    if honesty_messages:
        for i, m in enumerate(honesty_messages[:4]):
            bubbles.append(
                {
                    "id": f"honest-{i}",
                    "role": _ROLE_SYSTEM,
                    "title": "说明",
                    "text": _clip(str(m), 220),
                    "utc": "",
                    "source": "honesty",
                }
            )

    cur = current or {}
    if cur.get("last_error") or cur.get("human_required"):
        bubbles.append(
            {
                "id": "current-flag",
                "role": _ROLE_HUMAN if cur.get("human_required") else _ROLE_SYSTEM,
                "title": "当前",
                "text": _clip(
                    f"node={cur.get('node') or cur.get('stage')} · "
                    f"{cur.get('last_error') or ('human_required' if cur.get('human_required') else '')}",
                    240,
                ),
                "utc": "",
                "source": "current",
            }
        )

    if len(bubbles) > max_bubbles:
        head = bubbles[:1]
        tail = bubbles[-(max_bubbles - 1) :]
        bubbles = head + tail

    return {
        "schema_version": 1,
        "source": "disk_rules",
        "llm": False,
        "bubbles": bubbles,
        "steer": steer,
        "steer_path": str(steer_path(wd, slug).as_posix()) if steer else str(steer_path(wd, slug).as_posix()),
        "steer_exists": steer is not None,
        "form_hints": {
            "solve_modes": [
                "networkx",
                "cpsat",
                "highs",
                "ortools",
                "polyomino",
                "tube",
                "mock",
            ],
            "resume_stages": [
                "research",
                "model",
                "solve",
                "gate_validate",
                "explain",
            ],
            "note": "控制字段→LG；认知 notes→Pi；禁止填写 objective",
        },
    }


def steer_apply_enabled() -> bool:
    """ORPATH_APPLY_STEER=0 disables D2 merge (gates/CI). Default on."""
    raw = (os.environ.get("ORPATH_APPLY_STEER") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def format_pi_steer_block(state: dict[str, Any] | None) -> str:
    """Markdown block injected into research/model Pi briefs (cognitive only)."""
    st = state or {}
    pi = st.get("human_steer_pi")
    if not isinstance(pi, dict) or not pi:
        slug = str(st.get("slug") or "").strip()
        root = str(st.get("root") or "").strip()
        if slug and root and steer_apply_enabled():
            doc = load_human_steer(Path(root), slug)
            if doc and isinstance(doc.get("pi"), dict):
                pi = doc["pi"]
            else:
                pi = {}
        else:
            pi = {}
    if not pi:
        return ""
    lines = [
        "### Human steer (cognitive — not number authority)",
        "- Obey method preferences and notes below.",
        "- **Never** invent objective/tour/routes/proven optimal.",
        "- Numbers only from solve tools + validate later.",
    ]
    methods = pi.get("prefer_methods") or []
    if isinstance(methods, list) and methods:
        lines.append("- prefer_methods: " + ", ".join(str(m) for m in methods))
    notes = str(pi.get("notes") or "").strip()
    if notes:
        lines.append("- notes: " + notes.replace("\n", " ").strip())
    hints = str(pi.get("modeling_hints") or "").strip()
    if hints:
        lines.append("- modeling_hints: " + hints.replace("\n", " ").strip())
    fids = pi.get("focus_chunk_ids") or []
    if isinstance(fids, list) and fids:
        lines.append("- focus_chunk_ids: " + ", ".join(str(x) for x in fids))
    if len(lines) <= 4:
        return ""
    return "\n".join(lines) + "\n"


def resume_from_steer(workdir: Path, slug: str) -> str | None:
    """lg.resume_from for runner when CLI --from-stage empty."""
    if not steer_apply_enabled():
        return None
    doc = load_human_steer(workdir, slug)
    if not doc:
        return None
    lg = doc.get("lg") if isinstance(doc.get("lg"), dict) else {}
    rf = str(lg.get("resume_from") or "").strip()
    return rf or None


def apply_steer_to_state(
    state: dict[str, Any],
    *,
    workdir: Path | None = None,
    boundary: str | None = None,
) -> dict[str, Any]:
    """Merge human-steer.json into a LangGraph state **update** dict.

    - lg.solve_mode → state.solve_mode (allowed modes only)
    - lg.fresh recorded (runner may honor)
    - pi.* → human_steer_pi for Pi injection
    - pause_next + at_stage → steer_pause when boundary matches

    Never writes objective/tour/routes. Returns {} if disabled/missing.
    """
    if not steer_apply_enabled():
        return {}
    st = dict(state or {})
    slug = str(st.get("slug") or "").strip()
    if not slug:
        return {}
    wd = Path(workdir) if workdir else Path(str(st.get("root") or "."))
    doc = load_human_steer(wd, slug)
    if not doc:
        return {
            "human_steer_path": str(steer_path(wd, slug)),
            "human_steer_applied": False,
        }

    # reject poisoned files with forbidden keys
    forbid = find_forbidden_keys(doc)
    if forbid:
        return {
            "human_steer_path": str(steer_path(wd, slug)),
            "human_steer_applied": False,
            "last_error": "human_steer_forbidden_keys: " + ",".join(forbid[:6]),
        }

    lg = doc.get("lg") if isinstance(doc.get("lg"), dict) else {}
    pi = doc.get("pi") if isinstance(doc.get("pi"), dict) else {}
    at_stage = str(doc.get("at_stage") or lg.get("at_stage") or "manual").strip()

    upd: dict[str, Any] = {
        "human_steer_path": str(steer_path(wd, slug)),
        "human_steer_applied": True,
        "human_steer_lg": dict(lg),
        "human_steer_pi": dict(pi),
        "human_steer_at_stage": at_stage,
        "human_steer_utc": str(doc.get("utc") or ""),
    }

    mode = str(lg.get("solve_mode") or "").strip().lower()
    if mode:
        if mode not in ALLOWED_SOLVE_MODES:
            upd["last_error"] = f"human_steer_unknown_solve_mode:{mode}"
        else:
            # normalize aliases
            if mode in {"poly", "polyomino_cover"}:
                mode = "polyomino"
            if mode in {"tube_cut", "tube_bfd"}:
                mode = "tube"
            upd["solve_mode"] = mode

    if "fresh" in lg:
        upd["human_steer_fresh"] = bool(lg.get("fresh"))

    # Pause: before executing `boundary` node
    pause_next = bool(lg.get("pause_next"))
    if pause_next and boundary:
        target = _PAUSE_BEFORE.get(at_stage.lower()) if at_stage else None
        # also allow at_stage == boundary name directly
        if target is None and at_stage.lower() == str(boundary).lower():
            target = str(boundary)
        if target and str(boundary).lower() == str(target).lower():
            upd["steer_pause"] = True
            upd["human_required"] = True
            upd["stage"] = "human_stop"
            upd["last_error"] = (
                f"steer_pause before {boundary} (at_stage={at_stage}); "
                "clear lg.pause_next in human-steer.json then resume"
            )

    return upd


def maybe_steer_pause(
    state: dict[str, Any],
    *,
    boundary: str,
    workdir: Path | None = None,
) -> dict[str, Any] | None:
    """If pause applies at this boundary, return human_stop update; else None.

    Always merges non-pause steer fields into the returned dict when pausing.
    Callers that only need mode merge should use apply_steer_to_state.
    """
    upd = apply_steer_to_state(state, workdir=workdir, boundary=boundary)
    if upd.get("steer_pause"):
        return upd
    return None


__all__ = [
    "ALLOWED_SOLVE_MODES",
    "STEER_SCHEMA_VERSION",
    "apply_steer_to_state",
    "build_dialogue",
    "build_steer_cta",
    "find_forbidden_keys",
    "format_pi_steer_block",
    "load_human_steer",
    "maybe_steer_pause",
    "normalize_steer_payload",
    "resume_from_steer",
    "save_human_steer",
    "steer_apply_enabled",
    "steer_path",
]
