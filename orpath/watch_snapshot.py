"""Watch snapshot aggregator (V0 data plane) — pure disk/event read, no LLM.

Contract (schema_version=1) — fields for GET /api/snapshot consumers:

{
  "schema_version": 1,
  "generated_utc": ISO-8601,
  "slug": str,
  "thread_id": str,
  "live_subagent": bool,
  "status": "idle|running|ok|fail|blocked|no_product_run",
  "current": { node, stage, human_required, last_error, counters{...} },
  "stages": [ { seq, file, node, stage, utc, state, human_required, last_error, gates, paths } ],
  "dispatches": [ { stage, role, log_path, harness_path, subagent_detected, evidence, cosplay, ... } ],
  "events": [ { t, source, kind, text, dispatch_id } ],
  "thinking": { status: "available|thinking_unavailable", note },
  "artifacts": { solution, validate, schema, plan, intake, runs_dir, agents_dir, ... },
  "honesty": { bare_pi, live_off, transcript_missing, messages[] }
}

Law: specs/process-visibility.md — never invent collaboration stories.
Dialogue: specs/human-steer-and-pi-guidance.md — rule digests only (no LLM).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orpath.human_steer import build_dialogue
from orpath.paths import orpath_home, orpath_workdir
from orpath.subagent_dispatch import detect_subagent_calls

SCHEMA_VERSION = 1
# P1: bump poll contract; snapshot shape stays backward-compatible (+ optional poll).
POLL_SCHEMA = 1
MAX_EVENTS = 400
MAX_EVIDENCE = 8
# Prefer full file up to this size; else tail (P1: larger than old 256KiB).
LOG_FULL_MAX_BYTES = 1_500_000
LOG_TAIL_BYTES = 768 * 1024
# Stage/log mtime within this window → overall status may be "running".
LIVE_MTIME_S = 25.0
TEXT_CLIP = 400

# lead log filename → (stage_key, default_role)
_LEAD_NAME_RE = re.compile(
    r"^(?P<stage>research|model|cite|review|draft|explain|orchestrate)"
    r"(?:-lead)?(?:-(?P<ts>\d{8}T\d{6}Z))?\.log$",
    re.I,
)

_STAGE_ROLE = {
    "research": "or-researcher",
    "model": "or-modeler",
    "cite": "or-verifier",
    "review": "or-reviewer",
    "draft": "or-writer",
    "explain": "or-writer",
    "orchestrate": "or-orchestrator",
}

_REQUIRED_TOP = (
    "schema_version",
    "generated_utc",
    "slug",
    "thread_id",
    "live_subagent",
    "status",
    "current",
    "stages",
    "dispatches",
    "events",
    "thinking",
    "artifacts",
    "honesty",
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel_or_str(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _clip(text: str, n: int = TEXT_CLIP) -> str:
    t = (text or "").replace("\r\n", "\n").strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _read_text_tail(path: Path, max_bytes: int = LOG_TAIL_BYTES) -> str:
    text, _, _ = read_log_text(path, max_full=max_bytes, max_tail=max_bytes)
    return text


def read_log_text(
    path: Path,
    *,
    max_full: int = LOG_FULL_MAX_BYTES,
    max_tail: int = LOG_TAIL_BYTES,
    from_offset: int | None = None,
) -> tuple[str, int, bool]:
    """Read lead log bytes.

    Returns (text, file_size, truncated).
    - If from_offset is set, read from that byte offset to EOF (incremental).
    - Else if size <= max_full, read whole file.
    - Else read last max_tail bytes (truncated=True).
    """
    try:
        size = path.stat().st_size
    except OSError:
        return "", 0, False
    if size <= 0:
        return "", 0, False
    try:
        with path.open("rb") as f:
            if from_offset is not None:
                off = max(0, min(int(from_offset), size))
                # re-sync to line start if mid-file
                if off > 0:
                    f.seek(off - 1)
                    prev = f.read(1)
                    if prev != b"\n":
                        # skip partial line
                        f.readline()
                        off = f.tell()
                    else:
                        f.seek(off)
                else:
                    f.seek(0)
                    off = 0
                data = f.read()
                return data.decode("utf-8", errors="replace"), size, False
            if size <= max_full:
                data = f.read()
                return data.decode("utf-8", errors="replace"), size, False
            f.seek(max(0, size - max_tail))
            data = f.read()
            # drop partial first line after seek
            if size > max_tail and b"\n" in data:
                data = data.split(b"\n", 1)[1]
            return data.decode("utf-8", errors="replace"), size, True
    except OSError:
        return "", 0, False


def compute_source_fingerprint(
    *,
    slug: str,
    thread_id: str | None = None,
    workdir: Path | None = None,
) -> dict[str, Any]:
    """Cheap dirty detector — no lead parse. P1 poll plane."""
    wd = (workdir or orpath_workdir()).resolve()
    slug = (slug or "").strip() or "default"
    tid = (thread_id or slug).strip() or slug
    runs_thread = wd / "runs" / tid
    stages_dir = runs_thread / "stages"
    agents = wd / "outputs" / ".agents" / slug

    stage_files: list[tuple[str, int, float]] = []
    stages_mtime_max = 0.0
    if stages_dir.is_dir():
        for p in sorted(stages_dir.glob("*.json")):
            try:
                st = p.stat()
            except OSError:
                continue
            stage_files.append((p.name, int(st.st_size), float(st.st_mtime)))
            stages_mtime_max = max(stages_mtime_max, float(st.st_mtime))

    log_cursors: dict[str, dict[str, float | int | str]] = {}
    agents_mtime_max = 0.0
    if agents.is_dir():
        for p in sorted(agents.glob("*.log")):
            try:
                st = p.stat()
            except OSError:
                continue
            rel = _rel_or_str(p, wd) or p.name
            log_cursors[rel] = {
                "size": int(st.st_size),
                "mtime": float(st.st_mtime),
                "name": p.name,
            }
            agents_mtime_max = max(agents_mtime_max, float(st.st_mtime))
        for p in sorted(agents.glob("*.json")):
            try:
                st = p.stat()
            except OSError:
                continue
            agents_mtime_max = max(agents_mtime_max, float(st.st_mtime))

    h = hashlib.sha1()
    h.update(f"{slug}|{tid}|".encode())
    for name, sz, mt in stage_files:
        h.update(f"s:{name}:{sz}:{mt:.3f}|".encode())
    for rel in sorted(log_cursors):
        c = log_cursors[rel]
        h.update(f"l:{rel}:{c['size']}:{float(c['mtime']):.3f}|".encode())
    fingerprint = h.hexdigest()[:16]

    now = time.time()
    fresh = False
    if stages_mtime_max and (now - stages_mtime_max) <= LIVE_MTIME_S:
        fresh = True
    if agents_mtime_max and (now - agents_mtime_max) <= LIVE_MTIME_S:
        fresh = True

    return {
        "schema_poll": POLL_SCHEMA,
        "slug": slug,
        "thread_id": tid,
        "fingerprint": fingerprint,
        "stages_count": len(stage_files),
        "stages_mtime_max": stages_mtime_max or None,
        "agents_mtime_max": agents_mtime_max or None,
        "log_cursors": log_cursors,
        "sources_fresh": fresh,
        "generated_utc": _utc(),
    }


def _env_live_subagent() -> bool:
    raw = (os.environ.get("ORPATH_LIVE_SUBAGENT") or "1").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def _stage_state(snap: dict[str, Any], *, is_last: bool, sources_fresh: bool = False) -> str:
    if snap.get("human_required"):
        return "blocked"
    err = (snap.get("last_error") or "").strip()
    if err:
        return "fail"
    node = str(snap.get("node") or "")
    stage = str(snap.get("stage") or "")
    if is_last and node in {"human_stop", "provenance"} and stage in {"end", "human", "provenance"}:
        return "blocked" if snap.get("human_required") else "ok"
    if is_last and stage in {"end"}:
        return "ok"
    # P1: last stage with fresh mtime → running (live spine)
    if is_last and sources_fresh and stage not in {"end"}:
        return "running"
    return "ok"


def _parse_stage_file(
    path: Path, seq: int, *, is_last: bool, sources_fresh: bool = False
) -> dict[str, Any]:
    data = _read_json(path) or {}
    gates = {
        "schema": data.get("gate_schema_ok"),
        "validate": data.get("gate_validate_ok"),
    }
    return {
        "seq": seq,
        "file": path.name,
        "node": data.get("node") or path.stem.split("_", 1)[-1],
        "stage": data.get("stage"),
        "utc": data.get("utc") or "",
        "state": _stage_state(data, is_last=is_last, sources_fresh=sources_fresh),
        "human_required": bool(data.get("human_required")),
        "last_error": data.get("last_error") or "",
        "gates": gates,
        "paths": dict(data.get("paths") or {}),
        "counters": {
            "solver_tune": int(data.get("solver_tune") or 0),
            "schema_repair": int(data.get("schema_repair") or 0),
            "validate_repair": int(data.get("validate_repair") or 0),
            "revise_count": int(data.get("revise_count") or 0),
        },
    }


def load_stages(
    runs_thread: Path, *, sources_fresh: bool = False
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    stages_dir = runs_thread / "stages"
    if not stages_dir.is_dir():
        return [], None
    files = sorted(stages_dir.glob("*.json"), key=lambda p: p.name)
    if not files:
        return [], None
    out: list[dict[str, Any]] = []
    for i, fp in enumerate(files, 1):
        out.append(
            _parse_stage_file(
                fp, i, is_last=(i == len(files)), sources_fresh=sources_fresh
            )
        )
    latest = _read_json(runs_thread / "latest_snapshot.json")
    return out, latest


def _infer_stage_role_from_name(name: str) -> tuple[str, str]:
    m = _LEAD_NAME_RE.match(name)
    if m:
        st = m.group("stage").lower()
        return st, _STAGE_ROLE.get(st, f"or-{st}")
    lower = name.lower()
    for key, role in _STAGE_ROLE.items():
        if lower.startswith(key):
            return key, role
    return "unknown", "unknown"


def _latest_lead_logs(agents: Path) -> dict[str, Path]:
    """stage -> newest *-lead-*.log (or stage-lead.log)."""
    best: dict[str, Path] = {}
    if not agents.is_dir():
        return best
    for p in agents.glob("*.log"):
        stage, _ = _infer_stage_role_from_name(p.name)
        if stage == "unknown" and "-lead" not in p.name.lower():
            continue
        if stage == "unknown":
            # e.g. foo-lead-....log
            parts = p.name.split("-lead", 1)
            stage = parts[0].lower() if parts else "unknown"
        prev = best.get(stage)
        if prev is None or p.stat().st_mtime >= prev.stat().st_mtime:
            best[stage] = p
    return best


def _load_harness(agents: Path, stage: str) -> tuple[Path | None, dict[str, Any] | None]:
    candidates = [
        agents / f"{stage}-harness.json",
        agents / f"{stage}-subagent.json",
    ]
    for c in candidates:
        if c.is_file():
            return c, _read_json(c)
    # any *stage*harness*
    for p in sorted(agents.glob(f"{stage}*harness*.json")):
        return p, _read_json(p)
    for p in sorted(agents.glob(f"{stage}*subagent*.json")):
        return p, _read_json(p)
    return None, None


def _extract_text_blocks(obj: Any, out: list[str], *, keys: tuple[str, ...] = ("text", "thinking", "reasoning")) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and isinstance(v, str) and v.strip():
                out.append(v)
            else:
                _extract_text_blocks(v, out, keys=keys)
    elif isinstance(obj, list):
        for it in obj:
            _extract_text_blocks(it, out, keys=keys)


def _tool_name_from_obj(obj: dict[str, Any]) -> str:
    for k in ("toolName", "name", "tool_name"):
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "?"


def _extract_subagent_role(args: Any) -> str | None:
    if not isinstance(args, dict):
        return None
    for k in ("agent", "agentName", "name", "role"):
        v = args.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    # nested
    for v in args.values():
        if isinstance(v, dict):
            r = _extract_subagent_role(v)
            if r:
                return r
    return None


def load_subagent_artifact_index(
    bases: list[Path],
    *,
    root: Path,
) -> list[dict[str, Any]]:
    """Index .pi-subagents/artifacts/*_meta.json for P2 transcript attach."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for base in bases:
        arts = base / ".pi-subagents" / "artifacts"
        if not arts.is_dir():
            continue
        for meta_p in arts.glob("*_meta.json"):
            key = str(meta_p.resolve())
            if key in seen:
                continue
            seen.add(key)
            meta = _read_json(meta_p) or {}
            agent = str(meta.get("agent") or "")
            run_id = str(meta.get("runId") or meta.get("run_id") or "")
            tp = meta.get("transcriptPath") or meta.get("transcript_path")
            tpath: Path | None = None
            if isinstance(tp, str) and tp.strip():
                cand = Path(tp)
                if cand.is_file():
                    tpath = cand
            if tpath is None and run_id and agent:
                guess = arts / f"{run_id}_{agent}_0_transcript.jsonl"
                if guess.is_file():
                    tpath = guess
                else:
                    # any matching runId prefix
                    for g in arts.glob(f"{run_id}_*_transcript.jsonl"):
                        tpath = g
                        break
            out_md = None
            if run_id and agent:
                om = arts / f"{run_id}_{agent}_0_output.md"
                if om.is_file():
                    out_md = om
            try:
                mtime = float(meta_p.stat().st_mtime)
            except OSError:
                mtime = 0.0
            # meta timestamp is often ms
            ts_raw = meta.get("timestamp")
            if isinstance(ts_raw, (int, float)) and ts_raw > 1e12:
                mtime = max(mtime, float(ts_raw) / 1000.0)
            items.append(
                {
                    "agent": agent,
                    "run_id": run_id,
                    "task": _clip(str(meta.get("task") or ""), 200),
                    "exit_code": meta.get("exitCode"),
                    "meta_path": _rel_or_str(meta_p, root),
                    "transcript_path": _rel_or_str(tpath, root) if tpath else None,
                    "transcript_abs": str(tpath) if tpath else None,
                    "output_path": _rel_or_str(out_md, root) if out_md else None,
                    "mtime": mtime,
                    "tool_count": meta.get("toolCount"),
                    "duration_ms": meta.get("durationMs"),
                    "model": meta.get("model"),
                }
            )
    items.sort(key=lambda x: float(x.get("mtime") or 0), reverse=True)
    return items


def parse_transcript_events(
    path: Path,
    *,
    dispatch_id: str,
    agent: str,
    max_events: int = 120,
) -> tuple[list[dict[str, Any]], bool]:
    """Parse .pi-subagents transcript.jsonl into L2/L3 events (source=sub)."""
    events: list[dict[str, Any]] = []
    thinking_found = False
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], False

    def push(kind: str, body: str, t: str = "", **extra: Any) -> None:
        nonlocal thinking_found
        if kind == "thinking" and body.strip():
            thinking_found = True
        ev = {
            "t": str(t or ""),
            "source": "sub",
            "kind": kind,
            "text": _clip(body),
            "dispatch_id": dispatch_id,
            "agent": agent,
        }
        ev.update(extra)
        events.append(ev)
        if len(events) > max_events * 2:
            del events[: len(events) - max_events]

    for line in raw.splitlines():
        s = line.strip()
        if not s.startswith("{"):
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        et = str(obj.get("sourceEventType") or obj.get("recordType") or obj.get("type") or "")
        ts = str(obj.get("timestamp") or obj.get("ts") or "")
        role = str(obj.get("role") or "")

        if et in {"tool_execution_start", "tool_start"} or (
            obj.get("toolName") and obj.get("argsPreview") is not None and "end" not in et
        ):
            name = _tool_name_from_obj(obj)
            prev = obj.get("argsPreview") or obj.get("args") or ""
            push("tool", f"{name} {_clip(str(prev), 200)}", ts, tool=name)
            continue
        if et in {"tool_execution_end", "tool_end"} or (
            obj.get("toolName") and obj.get("isError") is not None and obj.get("argsPreview") is None
        ):
            name = _tool_name_from_obj(obj)
            err = obj.get("isError")
            push(
                "tool_result",
                f"{name}: {'ERROR' if err else 'ok'}",
                ts,
                tool=name,
            )
            continue
        if et in {"message_end", "message_start", "initial_prompt"} or role:
            # skip pure user dumps unless short assistant
            if role == "user" and et != "initial_prompt":
                # keep short task lines only
                text = obj.get("text") or ""
                if isinstance(text, str) and 0 < len(text) < 180 and et == "initial_prompt":
                    push("meta", f"task: {_clip(text, 160)}", ts)
                continue
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
            content = msg.get("content") if msg else None
            thinks: list[str] = []
            texts: list[str] = []
            if content is not None:
                _extract_text_blocks(content, thinks, keys=("thinking", "reasoning"))
                _extract_text_blocks(content, texts, keys=("text",))
            plain = obj.get("text")
            if isinstance(plain, str) and plain.strip() and not texts:
                texts.append(plain)
            for th in thinks:
                if th.strip():
                    push("thinking", th, ts)
            if role == "assistant" and texts:
                # skip huge acceptance-report dumps in preview
                body = texts[-1]
                if "acceptance-report" in body and len(body) > 400:
                    body = body[:200] + "…[acceptance-report truncated]"
                push("assistant", body, ts)
            continue

    if len(events) > max_events:
        events = events[-max_events:]
    return events, thinking_found


def parse_lead_events(
    text: str,
    *,
    dispatch_id: str,
    max_events: int = MAX_EVENTS,
) -> tuple[list[dict[str, Any]], bool, list[str]]:
    """Parse Pi --mode json lead stream into compact events.

    Returns (events, thinking_found, subagent_roles_seen).
    """
    events: list[dict[str, Any]] = []
    thinking_found = False
    roles_seen: list[str] = []
    if not text:
        return events, thinking_found, roles_seen

    def push(kind: str, body: str, t: str = "", **extra: Any) -> None:
        nonlocal thinking_found
        if kind == "thinking" and body.strip():
            thinking_found = True
        ev: dict[str, Any] = {
            "t": t or "",
            "source": "lead",
            "kind": kind,
            "text": _clip(body),
            "dispatch_id": dispatch_id,
        }
        ev.update(extra)
        events.append(ev)
        if len(events) > max_events * 2:
            del events[: len(events) - max_events]

    def note_role(args: Any) -> None:
        r = _extract_subagent_role(args)
        if r and r not in roles_seen:
            roles_seen.append(r)

    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("stage=") or s.startswith("slug=") or s.startswith("cmd="):
            if not s.startswith("cmd="):
                push("meta", s)
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            if len(s) < 300:
                push("meta", s)
            continue
        if not isinstance(obj, dict):
            continue
        et = str(obj.get("type") or "")
        ts = str(obj.get("timestamp") or obj.get("utc") or "")

        # P2: native toolCall shape
        if et in {"toolCall", "tool_call"}:
            name = _tool_name_from_obj(obj)
            args = obj.get("arguments") or obj.get("args") or {}
            if name == "subagent":
                note_role(args)
                role = _extract_subagent_role(args) or "?"
                push("tool", f"subagent agent={role}", ts, tool="subagent", agent=role)
            else:
                push(
                    "tool",
                    f"{name} {_clip(json.dumps(args, ensure_ascii=False), 240)}",
                    ts,
                    tool=name,
                )
            continue

        if et == "tool_execution_start":
            name = _tool_name_from_obj(obj)
            args = obj.get("args") or obj.get("arguments") or {}
            if name == "subagent":
                note_role(args)
                role = _extract_subagent_role(args) or "?"
                push("tool", f"subagent start agent={role}", ts, tool="subagent", agent=role)
            else:
                push(
                    "tool",
                    f"{name} {_clip(json.dumps(args, ensure_ascii=False), 240)}",
                    ts,
                    tool=name,
                )
            continue
        if et == "tool_execution_end":
            name = _tool_name_from_obj(obj)
            res = obj.get("result")
            bits: list[str] = []
            _extract_text_blocks(res, bits, keys=("text",))
            body = bits[0] if bits else json.dumps(res, ensure_ascii=False)[:200]
            if name == "subagent":
                # try agent in result
                note_role(res if isinstance(res, dict) else {})
            push("tool_result", f"{name}: {_clip(str(body), 280)}", ts, tool=name)
            continue
        if et == "tool_execution_update":
            name = str(obj.get("toolName") or "")
            if name == "subagent":
                args = obj.get("args") or {}
                note_role(args)
                agent = _extract_subagent_role(args) or "?"
                # high-signal status lines only
                status = ""
                if isinstance(args, dict):
                    status = str(args.get("status") or args.get("action") or "")
                push(
                    "tool",
                    f"subagent update agent={agent} {status}".strip(),
                    ts,
                    tool="subagent",
                    agent=agent,
                )
            continue
        if et in {"turn_end", "message_end"}:
            msg = obj.get("message") or {}
            if not isinstance(msg, dict):
                continue
            role = msg.get("role") or ""
            content = msg.get("content")
            thinks: list[str] = []
            texts: list[str] = []
            _extract_text_blocks(content, thinks, keys=("thinking", "reasoning"))
            _extract_text_blocks(content, texts, keys=("text",))
            # also toolCall blocks inside content
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    bt = str(block.get("type") or "")
                    if bt in {"toolCall", "tool_use", "toolcall"}:
                        tn = block.get("name") or block.get("toolName") or "?"
                        args = block.get("arguments") or block.get("input") or {}
                        if tn == "subagent":
                            note_role(args)
                            ar = _extract_subagent_role(args) or "?"
                            push("tool", f"subagent agent={ar}", ts, tool="subagent", agent=ar)
                        else:
                            push(
                                "tool",
                                f"{tn} {_clip(json.dumps(args, ensure_ascii=False), 200)}",
                                ts,
                                tool=str(tn),
                            )
            for th in thinks:
                if th.strip():
                    push("thinking", th, ts)
            if role == "assistant" and texts:
                push("assistant", texts[-1], ts)
            continue
        if et == "message_update":
            ame = obj.get("assistantMessageEvent") or {}
            if not isinstance(ame, dict):
                continue
            at = str(ame.get("type") or "")
            if at in {"thinking_start", "thinking_delta"}:
                partial = ame.get("partial") or ame.get("delta") or {}
                thinks = []
                _extract_text_blocks(partial, thinks, keys=("thinking", "reasoning"))
                # also direct fields
                for k in ("thinking", "text", "content"):
                    v = ame.get(k)
                    if isinstance(v, str) and v.strip():
                        thinks.append(v)
                if thinks and thinks[0].strip():
                    if at == "thinking_delta":
                        # collapse spam: only if last wasn't thinking
                        if not events or events[-1].get("kind") != "thinking":
                            push("thinking", thinks[0], ts)
                    else:
                        if not any(e.get("kind") == "thinking" for e in events[-5:]):
                            push("thinking", thinks[0], ts)
            elif at in {"toolcall_start", "tool_call_start"}:
                partial = ame.get("partial") or {}
                blob = json.dumps(partial, ensure_ascii=False)
                # extract name if present
                name = "?"
                if isinstance(partial, dict):
                    content = partial.get("content")
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") in {
                                "toolCall",
                                "tool_use",
                                "toolcall",
                            }:
                                name = str(block.get("name") or block.get("toolName") or name)
                                args = block.get("arguments") or block.get("input") or {}
                                if name == "subagent":
                                    note_role(args)
                if "subagent" in blob or name == "subagent":
                    role = roles_seen[-1] if roles_seen else "?"
                    push(
                        "tool",
                        f"toolcall_start subagent agent={role}",
                        ts,
                        tool="subagent",
                        agent=role if role != "?" else None,
                    )
                elif name != "?":
                    push("tool", f"toolcall_start {name}", ts, tool=name)
            elif at in {"text_start", "text_delta"}:
                # skip streaming text spam; final on turn_end
                pass
            continue
        if et in {"agent_start", "agent_end", "turn_start", "session", "agent_settled"}:
            push("meta", et, ts)
            continue

    if len(events) > max_events:
        events = events[-max_events:]
    return events, thinking_found, roles_seen


def _match_children_for_dispatch(
    *,
    role: str,
    stage: str,
    log_mtime: float,
    roles_from_log: list[str],
    index: list[dict[str, Any]],
    slug: str,
) -> list[dict[str, Any]]:
    """Pick subagent artifact rows for this stage lead."""
    want_roles = list(roles_from_log) if roles_from_log else []
    if role and role not in want_roles:
        want_roles.append(role)
    # stage name heuristic: research → or-researcher
    if stage and f"or-{stage}" not in want_roles and stage in _STAGE_ROLE:
        want_roles.append(_STAGE_ROLE[stage])

    candidates = [
        it
        for it in index
        if (not want_roles) or (it.get("agent") in want_roles)
    ]
    # prefer mtime near lead log (±2h) or task mentions slug
    scored: list[tuple[float, dict[str, Any]]] = []
    for it in candidates:
        score = 0.0
        mt = float(it.get("mtime") or 0)
        if log_mtime and mt:
            dt = abs(mt - log_mtime)
            if dt < 7200:
                score += max(0.0, 100.0 - dt / 72.0)
        task = str(it.get("task") or "")
        if slug and slug in task:
            score += 50
        if it.get("transcript_path"):
            score += 5
        if it.get("agent") == role:
            score += 10
        scored.append((score, it))
    scored.sort(key=lambda x: (-x[0], -float(x[1].get("mtime") or 0)))
    # top few per dispatch
    out: list[dict[str, Any]] = []
    seen_run: set[str] = set()
    for score, it in scored:
        if score < 5 and out:
            # weak matches only if nothing better
            if len(out) >= 1:
                break
        rid = str(it.get("run_id") or it.get("meta_path") or "")
        if rid in seen_run:
            continue
        seen_run.add(rid)
        out.append(it)
        if len(out) >= 5:
            break
    return out


def discover_pi_sessions(
    *,
    workdir: Path,
    limit: int = 12,
    home: Path | None = None,
) -> dict[str, Any]:
    """List recent Pi session JSONL under ~/.pi/agent/sessions (Tier-2).

    Read-only. Does not require ORPATH_PI_SESSION=1 (may show sessions from
    interactive `orpath.bat pi` even when product leads use --no-session).

    D3: also reports project package install status + copyable deep-link commands.
    """
    from orpath.subagent_runtime import pi_session_enabled, pi_sessions_root

    root = pi_sessions_root()
    enabled = pi_session_enabled()
    home_p = Path(home) if home else orpath_home()
    packages = _read_pi_packages(home_p)
    pkg_names = " ".join(packages).lower()
    has_kanban = "pi-kanban" in pkg_names
    has_supervisor = "pi-supervisor" in pkg_names
    has_ask = "rpiv-ask-user-question" in pkg_names or "ask-user-question" in pkg_names

    deep_links = [
        {
            "id": "session_on",
            "title": "产品 LIVE 写 session（供 kanban）",
            "command": (
                "set ORPATH_PI_SESSION=1\n"
                "set ORPATH_LIVE_SUBAGENT=1\n"
                "orpath.bat watch-run --live --keep-watch --slug tier2-demo"
            ),
            "reason": "默认 SESSION=0 时 lead 带 --no-session，kanban 看不到产品 lead",
        },
        {
            "id": "pi_interactive",
            "title": "打开交互 Pi（Tier-2 主场）",
            "command": "pi.bat",
            "reason": "Enter=steer · Alt+Enter=follow-up",
        },
        {
            "id": "kanban",
            "title": "启动 pi-kanban",
            "command": (
                "pi.bat\n"
                ":: then inside Pi:\n"
                "/kanban start\n"
                "/kanban open web"
            ),
            "reason": "需 npm:pi-kanban；读 ~/.pi/agent/sessions",
            "ready": has_kanban,
        },
        {
            "id": "supervise",
            "title": "启动 pi-supervisor 目标监督",
            "command": (
                "pi.bat\n"
                ":: then inside Pi:\n"
                "/supervise Prefer exact solve tracks; never invent objective; "
                "use tools/solve_dispatch + validate\n"
                "/supervise sensitivity medium\n"
                "/supervise status"
            ),
            "reason": "需 npm:pi-supervisor + .pi/SUPERVISOR.md；交互会话用",
            "ready": has_supervisor,
        },
        {
            "id": "install_pkgs",
            "title": "项目本地安装引导插件（若 list 缺包）",
            "command": (
                "pi.bat install npm:pi-kanban -l --approve\n"
                "pi.bat install npm:pi-supervisor -l --approve\n"
                "pi.bat install npm:@juicesharp/rpiv-ask-user-question -l --approve\n"
                "pi.bat list"
            ),
            "reason": "写入 .pi/settings.json + .pi/npm/",
        },
    ]

    out: dict[str, Any] = {
        "pi_session_env": enabled,
        "sessions_root": str(root),
        "sessions_root_exists": root.is_dir(),
        "recent": [],
        "kanban_hint": "pi install npm:pi-kanban  then  /kanban start",
        "supervise_hint": "pi.bat → /supervise <outcome>  (npm:pi-supervisor)",
        "fleet_hint": "inside Pi TUI: /subagents-fleet (package-dependent)",
        "docs": "docs/d3-tier2-deep-link.md",
        "docs_p4": "docs/p4-tier2-deep-look.md",
        "packages": packages,
        "package_status": {
            "pi-kanban": has_kanban,
            "pi-supervisor": has_supervisor,
            "rpiv-ask-user-question": has_ask,
            "pi-subagents": "pi-subagents" in pkg_names,
        },
        "deep_links": deep_links,
        "honesty": (
            []
            if enabled
            else [
                "tier2_session_off: set ORPATH_PI_SESSION=1 before LIVE product lead "
                "if kanban must see product sessions"
            ]
        ),
    }
    if not root.is_dir():
        out["workdir_hint"] = str(workdir.resolve())
        return out

    # Prefer dirs that look like this workdir (Pi encodes cwd in folder name)
    wd_key = str(workdir.resolve()).replace(":", "").replace("\\", "-").replace("/", "-")
    candidates: list[tuple[float, Path]] = []
    try:
        for p in root.rglob("*.jsonl"):
            try:
                st = p.stat()
            except OSError:
                continue
            candidates.append((st.st_mtime, p))
    except OSError:
        out["workdir_hint"] = str(workdir.resolve())
        return out
    candidates.sort(key=lambda x: -x[0])
    recent = []
    for mt, p in candidates[: max(limit * 3, limit)]:
        rel_parent = ""
        try:
            rel_parent = str(p.parent.relative_to(root))
        except ValueError:
            rel_parent = str(p.parent)
        score = 1.0
        if wd_key and any(
            part and part in rel_parent for part in wd_key.split("-") if len(part) > 4
        ):
            score += 5.0
        # path tokens like Users-Lanzao-Desktop-agent
        if "agent" in rel_parent.lower() and "desktop" in rel_parent.lower():
            score += 2.0
        recent.append(
            {
                "path": str(p),
                "name": p.name,
                "parent": rel_parent,
                "mtime": mt,
                "size": int(p.stat().st_size) if p.is_file() else 0,
                "score": score,
            }
        )
    recent.sort(key=lambda x: (-float(x.get("score") or 0), -float(x.get("mtime") or 0)))
    out["recent"] = recent[:limit]
    out["workdir_hint"] = str(workdir.resolve())
    return out


def _read_pi_packages(home: Path) -> list[str]:
    """Project .pi/settings.json packages (best-effort)."""
    settings = Path(home) / ".pi" / "settings.json"
    if not settings.is_file():
        return []
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    pkgs = data.get("packages") if isinstance(data, dict) else None
    if not isinstance(pkgs, list):
        return []
    return [str(x) for x in pkgs]


def build_dispatches(
    agents_dir: Path,
    *,
    root: Path,
    home: Path | None = None,
    slug: str = "",
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    bool,
    list[str],
    bool,
    dict[str, dict[str, Any]],
    bool,
    bool,
]:
    """Returns dispatches, events, thinking_found, honesty_msgs, events_truncated,
    log_cursors, events_cap_hit, transcript_missing_any.
    """
    dispatches: list[dict[str, Any]] = []
    all_events: list[dict[str, Any]] = []
    thinking_any = False
    messages: list[str] = []
    events_truncated = False
    log_cursors: dict[str, dict[str, Any]] = {}
    transcript_missing_any = False
    leads = _latest_lead_logs(agents_dir)

    bases = [root]
    if home is not None and home.resolve() != root.resolve():
        bases.append(home)
    sub_index = load_subagent_artifact_index(bases, root=root)

    for stage, log_path in sorted(leads.items(), key=lambda kv: kv[0]):
        role = _STAGE_ROLE.get(stage, f"or-{stage}")
        harness_path, harness = _load_harness(agents_dir, stage)
        text, fsize, trunc = read_log_text(log_path)
        if trunc:
            events_truncated = True
        rel = _rel_or_str(log_path, root) or log_path.name
        try:
            mtime = float(log_path.stat().st_mtime)
        except OSError:
            mtime = 0.0
        log_cursors[rel] = {
            "size": int(fsize),
            "mtime": mtime,
            "truncated_read": trunc,
            "stage": stage,
        }
        hit, evidence = detect_subagent_calls(text)
        if harness and harness.get("subagent_calls_detected") is True:
            hit = True
            hev = harness.get("call_evidence") or []
            if isinstance(hev, list) and hev and not evidence:
                evidence = [str(x)[:220] for x in hev[:MAX_EVIDENCE]]
        if harness and harness.get("lead", {}).get("subagent_calls_detected") is True:
            hit = True

        claimed_ma = False
        if harness:
            if harness.get("gate_subagent_ok") is True:
                claimed_ma = True
            tools = str(harness.get("tools") or "")
            if "subagent" in tools:
                claimed_ma = True
            if stage in {"research", "model", "cite", "review"}:
                claimed_ma = True

        cosplay = bool(claimed_ma and not hit and harness and not harness.get("skipped"))
        if harness and (harness.get("skipped") or (harness.get("error") or "") == "dry_run"):
            cosplay = False

        if cosplay:
            messages.append(f"cosplay_or_no_toolcall: stage={stage} log={log_path.name}")

        evs, th, roles_seen = parse_lead_events(text, dispatch_id=stage)
        if th:
            thinking_any = True

        children_raw = _match_children_for_dispatch(
            role=role,
            stage=stage,
            log_mtime=mtime,
            roles_from_log=roles_seen,
            index=sub_index,
            slug=slug,
        )
        children: list[dict[str, Any]] = []
        for ch in children_raw:
            child = {
                "agent": ch.get("agent"),
                "run_id": ch.get("run_id"),
                "task": ch.get("task"),
                "exit_code": ch.get("exit_code"),
                "meta_path": ch.get("meta_path"),
                "transcript_path": ch.get("transcript_path"),
                "output_path": ch.get("output_path"),
                "tool_count": ch.get("tool_count"),
                "duration_ms": ch.get("duration_ms"),
                "model": ch.get("model"),
                "event_count": 0,
            }
            tabs = ch.get("transcript_abs")
            if tabs:
                tp = Path(str(tabs))
                if tp.is_file():
                    tevs, tth = parse_transcript_events(
                        tp, dispatch_id=stage, agent=str(ch.get("agent") or "sub")
                    )
                    child["event_count"] = len(tevs)
                    if tth:
                        thinking_any = True
                    all_events.extend(tevs)
                else:
                    child["transcript_path"] = None
            children.append(child)

        if hit and not any(c.get("transcript_path") for c in children):
            transcript_missing_any = True
            messages.append(
                f"transcript_missing: stage={stage} subagent_detected but no .pi-subagents transcript matched"
            )

        # event kind counts for UI
        kind_counts: dict[str, int] = {}
        for e in evs:
            k = str(e.get("kind") or "")
            kind_counts[k] = kind_counts.get(k, 0) + 1
        for c in children:
            # counts already in child events merged to all_events
            pass

        disp = {
            "id": stage,
            "stage": stage,
            "role": role,
            "log_path": rel,
            "harness_path": _rel_or_str(harness_path, root) if harness_path else None,
            "subagent_detected": bool(hit),
            "evidence": list(evidence)[:MAX_EVIDENCE],
            "cosplay": cosplay,
            "skipped": bool(harness.get("skipped")) if harness else False,
            "gate_subagent_ok": harness.get("gate_subagent_ok") if harness else None,
            "log_size": int(fsize),
            "log_truncated_read": trunc,
            "roles_seen": roles_seen,
            "children": children,
            "event_kinds": kind_counts,
            "lead_event_count": len(evs),
        }
        dispatches.append(disp)
        all_events.extend(evs)

    events_cap_hit = False
    if len(all_events) > MAX_EVENTS:
        all_events = all_events[-MAX_EVENTS:]
        events_cap_hit = True
        events_truncated = True
    return (
        dispatches,
        all_events,
        thinking_any,
        messages,
        events_truncated,
        log_cursors,
        events_cap_hit,
        transcript_missing_any,
    )


def _resolve_artifact(workdir: Path, slug: str, suffixes: tuple[str, ...]) -> str | None:
    for suf in suffixes:
        p = workdir / "outputs" / f"{slug}{suf}"
        if p.is_file():
            return _rel_or_str(p, workdir)
    return None


def collect_artifacts(
    workdir: Path,
    slug: str,
    thread_id: str,
    stage_paths: dict[str, Any] | None,
) -> dict[str, Any]:
    art: dict[str, Any] = {
        "solution": _resolve_artifact(workdir, slug, ("-solution.json",)),
        "validate": _resolve_artifact(workdir, slug, ("-validate.json",)),
        "schema": _resolve_artifact(workdir, slug, ("-schema.json",)),
        "intake": _resolve_artifact(workdir, slug, ("-intake.json",)),
        "paper": None,
        "provenance": None,
        "plan": None,
        "runs_dir": _rel_or_str(workdir / "runs" / thread_id, workdir),
        "agents_dir": _rel_or_str(workdir / "outputs" / ".agents" / slug, workdir),
    }
    prov = workdir / "outputs" / f"{slug}.provenance.md"
    if prov.is_file():
        art["provenance"] = _rel_or_str(prov, workdir)
    plan = workdir / "outputs" / ".plans" / f"{slug}.md"
    if plan.is_file():
        art["plan"] = _rel_or_str(plan, workdir)
    paper = workdir / "papers" / f"{slug}.md"
    if paper.is_file():
        art["paper"] = _rel_or_str(paper, workdir)

    # merge stage path pointers (prefer existing files)
    if stage_paths:
        mapping = {
            "solution_path": "solution",
            "validate_path": "validate",
            "schema_path": "schema",
            "plan_path": "plan",
            "intake_path": "intake",
            "provenance_path": "provenance",
        }
        for src, dst in mapping.items():
            raw = stage_paths.get(src)
            if not raw or art.get(dst):
                continue
            p = Path(str(raw))
            if p.is_file():
                art[dst] = _rel_or_str(p, workdir)
    return art


def _overall_status(
    *,
    has_stages: bool,
    latest: dict[str, Any] | None,
    stages: list[dict[str, Any]],
    sources_fresh: bool = False,
) -> str:
    if not has_stages:
        return "no_product_run"
    cur = latest or {}
    if cur.get("human_required") or (stages and stages[-1].get("human_required")):
        return "blocked"
    err = (cur.get("last_error") or "").strip()
    if err:
        return "fail"
    if stages and stages[-1].get("state") == "fail":
        return "fail"
    node = str(cur.get("node") or (stages[-1].get("node") if stages else ""))
    stage = str(cur.get("stage") or (stages[-1].get("stage") if stages else ""))
    if stage in {"end"} or node in {"provenance", "human_stop"}:
        return "blocked" if cur.get("human_required") else "ok"
    if sources_fresh and stage not in {"end"}:
        return "running"
    # historical complete dumps without end still "ok" if no error
    return "ok"


def _explain_error(
    *,
    last_err: str,
    node: str | None,
    stage: str | None,
    status: str,
    human: bool,
) -> dict[str, str]:
    """Human-facing Chinese explanation of machine last_error (no LLM)."""
    raw = (last_err or "").strip()
    low = raw.lower()
    node_s = str(node or "").strip()
    stage_s = str(stage or "").strip()

    node_zh = {
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
    where = node_zh.get(node_s) or node_zh.get(stage_s) or (node_s or stage_s or "未知阶段")

    headline = "需要你看一下" if human else "运行出错"
    what = f"卡在「{where}」这一步。"
    why = "系统记录了一条技术错误（下面有原文）。"
    do = "把下方「建议操作」里的命令复制到终端执行。本页面不会自动继续跑。"
    icon = "hand" if human else "warn"

    if "exit_code=-9" in low or "exit_code = -9" in low or "timeout after" in low:
        headline = "调研超时被打断（不是算错）"
        what = (
            f"停在「{where}」。多路子智能体往往已经写完笔记，"
            "但负责汇总的主会话超过时限被强制结束。"
        )
        why = (
            "技术码 exit_code=-9 在本产品里表示「超时」（Timeout），"
            "不是乱码。常见于 LIVE 时限过短，或宽调研（多子任务）合并太慢。"
        )
        do = (
            "若 notes 里已有调研文稿：优先从「建模」续跑；"
            "并设 ORPATH_SUBAGENT_TIMEOUT=1800。"
            "按下面中文操作卡片复制命令即可。"
        )
        icon = "clock"
    elif "research_gate" in low or (node_s == "research" and "subagent" in low):
        headline = "调研门禁没过"
        what = f"「{where}」要求：调研文稿合格 +（LIVE 时）子智能体链路成功。"
        why = raw or "research_gate 失败"
        do = "先打开 notes/*-research.md 看是否已有内容；有则从建模续，没有则加长超时后重跑调研。"
        icon = "gate"
    elif "schema" in low or "forbidden key" in low or node_s in {"gate_schema", "model"}:
        headline = "建模/结构门禁失败"
        what = f"问题结构（schema）不合格，卡在「{where}」。"
        why = raw or "schema gate"
        do = "从建模或结构门禁续跑；不要手填 objective。"
        icon = "schema"
    elif "validate" in low or node_s in {"gate_validate", "solve"}:
        headline = "求解或校验失败"
        what = f"卡在「{where}」。数字必须以求解器 JSON + 校验为准。"
        why = raw or "validate/solve"
        do = "从求解或校验续跑；禁止改 objective 散文蒙混。"
        icon = "solve"
    elif any(k in low for k in ("cite", "claim", "r1", "r2", "whitelist", "unmapped")):
        headline = "论文引用/数字主张检查失败"
        what = f"卡在「{where}」（引用或 claim 门禁）。"
        why = raw
        do = "从引用打包或写稿续跑；数字只能来自 solution。"
        icon = "paper"
    elif "intake" in low or node_s in {"intake_ocr", "intake_parse"}:
        headline = "题面入口失败"
        what = "OCR/解析题面没过。"
        why = raw
        do = "检查 PDF/图片路径后从题面解析或编排续跑。"
        icon = "intake"
    elif raw == "human_required":
        headline = "流程要求人工确认"
        what = f"停在「{where}」，等待你决定下一步。"
        why = "控制面设置了需要人工确认（例如暂停边界或门禁）。"
        do = "看建议操作；复制命令到终端。页面不会自动续跑。"
        icon = "hand"

    status_zh = {
        "ok": "正常",
        "fail": "失败",
        "blocked": "受阻",
        "running": "运行中",
        "idle": "空闲",
        "no_product_run": "尚无产品跑次",
    }.get(status, status)

    return {
        "headline": headline,
        "what": what,
        "why": why,
        "do": do,
        "where": where,
        "status_zh": status_zh,
        "icon": icon,
        "raw": raw,
    }


def _build_error_block(
    *,
    current: dict[str, Any],
    stages: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    """Pure-data error panel payload for Watch (no LLM)."""
    last_err = str(current.get("last_error") or "").strip()
    human = bool(current.get("human_required"))
    fail_stage: dict[str, Any] | None = None
    # Prefer last stage that carries error / fail / human
    for st in reversed(stages or []):
        st_err = str(st.get("last_error") or "").strip()
        if st_err or st.get("state") in {"fail", "blocked"} or st.get("human_required"):
            fail_stage = st
            if not last_err and st_err:
                last_err = st_err
            break
    empty_explain = {
        "headline": "",
        "what": "",
        "why": "",
        "do": "",
        "where": "",
        "status_zh": "",
        "icon": "",
        "raw": "",
    }
    if not last_err and fail_stage is None and status not in {"fail", "blocked"}:
        return {
            "has_error": False,
            "last_error": "",
            "stage_seq": None,
            "node": current.get("node"),
            "stage": current.get("stage"),
            "human_required": human,
            "status": status,
            "copy_text": "",
            "explain": empty_explain,
        }
    if not last_err and human:
        last_err = "human_required"
    if not last_err and status in {"fail", "blocked"}:
        last_err = f"status={status}"
    seq = fail_stage.get("seq") if fail_stage else current.get("error_stage_seq")
    node = (fail_stage or {}).get("node") or current.get("node")
    stage_name = (fail_stage or {}).get("stage") or current.get("stage")
    explain = _explain_error(
        last_err=last_err,
        node=str(node) if node else None,
        stage=str(stage_name) if stage_name else None,
        status=status,
        human=human,
    )
    copy_lines = [
        f"【{explain.get('headline') or '错误'}】",
        f"状态: {explain.get('status_zh') or status}",
        f"位置: {explain.get('where') or node or stage_name}",
        f"怎么了: {explain.get('what')}",
        f"为什么: {explain.get('why')}",
        f"怎么做: {explain.get('do')}",
        "",
        "—— 技术原文（排障用）——",
        f"status={status}",
        f"node={node or ''}",
        f"stage={stage_name or ''}",
        f"stage_seq={seq if seq is not None else ''}",
        f"human_required={human}",
        f"last_error={last_err}",
    ]
    return {
        "has_error": bool(last_err) or human or status in {"fail", "blocked"},
        "last_error": last_err,
        "stage_seq": seq,
        "node": node,
        "stage": stage_name,
        "human_required": human,
        "status": status,
        "copy_text": "\n".join(copy_lines),
        "explain": explain,
    }


# Product graph stages safe for --from-stage (control_plane.PREDECESSORS keys + common)
_FROM_STAGE_WHITELIST = frozenset(
    {
        "intake_ocr",
        "intake_parse",
        "orchestrate",
        "retrieve",
        "bridge_pi",
        "research",
        "model",
        "gate_schema",
        "solve",
        "gate_validate",
        "explain",
        "draft_paper",
        "cite_pack",
        "review_pack",
        "revise_or_done",
        "provenance",
        "human_stop",
    }
)


def _detect_run_flags(workdir: Path, slug: str) -> str:
    """Optional --problem-id/--class/--solve-mode for resume CTAs (disk-only)."""
    flags = ""
    for name in (f"{slug}-schema.json", f"{slug}-solution.json"):
        p = Path(workdir) / "outputs" / name
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        pid = str(data.get("problem_id") or "").strip()
        pc = str(data.get("problem_class") or "").strip()
        if pid:
            flags += f" --problem-id {pid}"
        if pc:
            flags += f" --problem-class {pc}"
        pc_l = pc.lower()
        pid_l = pid.lower()
        if "polyomino" in pc_l or "polyomino" in pid_l or "poly" == pc_l:
            flags += " --solve-mode polyomino"
        elif "tube" in pc_l or "tube" in pid_l:
            flags += " --solve-mode tube"
        break
    return flags


def _build_next_actions(
    *,
    slug: str,
    thread_id: str,
    workdir: Path,
    home: Path,
    current: dict[str, Any],
    stages: list[dict[str, Any]],
    status: str,
    error: dict[str, Any],
) -> list[dict[str, str]]:
    """Pure rules → actionable CLI CTAs for HUMAN/fail (no LLM, no auto-run)."""
    if not (
        error.get("has_error")
        or current.get("human_required")
        or status in {"fail", "blocked"}
    ):
        return []

    last_err = str(error.get("last_error") or current.get("last_error") or "").lower()
    node = str(error.get("node") or current.get("node") or "").lower()
    counters = current.get("counters") if isinstance(current.get("counters"), dict) else {}
    schema_repair = int(counters.get("schema_repair") or 0)
    validate_repair = int(counters.get("validate_repair") or 0)

    wd = Path(workdir).resolve()
    hm = Path(home).resolve()
    wd_flag = ""
    if wd != hm:
        wd_s = str(wd)
        if " " in wd_s:
            wd_flag = f' --workdir "{wd_s}"'
        else:
            wd_flag = f" --workdir {wd_s}"

    slug_s = slug or "run"
    tid_s = thread_id or slug_s
    run_flags = _detect_run_flags(wd, slug_s)
    # polyomino hint from slug/error even if artifacts missing
    if "polyomino" in slug_s.lower() and "--solve-mode" not in run_flags:
        run_flags += (
            " --problem-id polyomino_b_q1 --problem-class polyomino_cover"
            " --solve-mode polyomino"
        )

    def act(title: str, command: str, reason: str) -> dict[str, str]:
        return {"title": title, "command": command, "reason": reason}

    def from_stage(stage: str) -> str | None:
        st = (stage or "").strip()
        if st not in _FROM_STAGE_WHITELIST:
            return None
        return (
            f"orpath.bat run --resume --force --slug {slug_s} --thread-id {tid_s}"
            f"{wd_flag}{run_flags} --from-stage {st}"
        )

    actions: list[dict[str, str]] = []
    seen_cmd: set[str] = set()

    def add(title: str, command: str | None, reason: str) -> None:
        if not command or command in seen_cmd:
            return
        seen_cmd.add(command)
        actions.append(act(title, command, reason))

    # 1) schema / modeler failures
    if (
        "schema" in last_err
        or "forbidden key" in last_err
        or "problem_class" in last_err
        or node in {"gate_schema", "model"}
        or schema_repair > 0
    ):
        cmd_g = from_stage("gate_schema")
        cmd_m = from_stage("model")
        if schema_repair >= 2:
            add(
                "重新建模（结构修复次数已用尽）",
                cmd_m,
                "结构字段多次不过 → 让建模节点重写 schema，再过门禁",
            )
            add("只重跑结构门禁", cmd_g, "若你已在磁盘上修好 schema.json")
        else:
            add("从结构门禁继续", cmd_g, "schema 不合格 / 还可自动修一次")
            add("从建模继续", cmd_m, "重新生成问题结构（schema）")

    # 2) validate / solve
    if (
        "validate" in last_err
        or "unknown class" in last_err
        or node in {"gate_validate", "solve"}
        or validate_repair > 0
        or "polyomino" in last_err
    ):
        add(
            "从校验继续",
            from_stage("gate_validate"),
            "重新检查求解结果是否自洽",
        )
        add(
            "从求解继续",
            from_stage("solve"),
            "重跑求解器，再用校验重算",
        )

    # 2b) research timeout / research gate — prefer model if research text likely exists
    if (
        "exit_code=-9" in last_err
        or "research_gate" in last_err
        or node == "research"
        or "timeout" in last_err
    ):
        research_p = wd / "notes" / f"{slug_s}-research.md"
        has_research = research_p.is_file() and research_p.stat().st_size > 200
        if has_research:
            add(
                "调研稿已在 → 从建模继续（推荐）",
                from_stage("model"),
                "notes 里已有调研文稿；超时多半是汇总超时，不必整段重做调研",
            )
        add(
            "加长超时后重跑调研",
            (
                f"set ORPATH_SUBAGENT_TIMEOUT=1800&& orpath.bat run --live --resume --force "
                f"--slug {slug_s} --thread-id {tid_s}{wd_flag}{run_flags} --from-stage research"
            ),
            "子任务多/合并慢时把 lead 时限调到 1800 秒再跑调研",
        )

    # 3) paper / cite / claim
    if any(
        k in last_err
        for k in ("cite", "claim", "r1", "r2", "paper", "numeric claim", "unmapped", "whitelist")
    ) or node in {"cite_pack", "review_pack", "draft_paper", "revise_or_done"}:
        add(
            "从引用打包继续",
            from_stage("cite_pack"),
            "引用白名单或数字主张对不上",
        )
        add(
            "从写稿继续",
            from_stage("draft_paper"),
            "只用 solution 里的数字重写草稿",
        )

    # 4) intake
    if "intake" in last_err or node in {"intake_ocr", "intake_parse"}:
        add(
            "从题面解析继续",
            from_stage("intake_parse"),
            "题面入口被挡住",
        )
        add(
            "从编排继续",
            from_stage("orchestrate"),
            "若 brief 已 OK，可跳过重新 OCR",
        )

    # 5) generic resume + always watch face
    add(
        "从断点继续整条产品链",
        f"orpath.bat run --resume --force --slug {slug_s} --thread-id {tid_s}{wd_flag}{run_flags}",
        "接着上次检查点往下走（不会在网页里自动点）",
    )
    add(
        "只打开过程台（看脸）",
        f"orpath.bat watch --slug {slug_s} --thread-id {tid_s}{wd_flag}",
        "只看进度，不自动开跑",
    )

    return actions[:8]


def build_snapshot(
    *,
    slug: str,
    thread_id: str | None = None,
    root: Path | None = None,
    workdir: Path | None = None,
    prev_fingerprint: str | None = None,
    prev_events_count: int | None = None,
) -> dict[str, Any]:
    """Aggregate L0–L4 watch snapshot for one slug/thread. Never calls an LLM."""
    home = (root or orpath_home()).resolve()
    wd = (workdir or orpath_workdir()).resolve()
    slug = (slug or "").strip() or "default"
    tid = (thread_id or slug).strip() or slug

    fp_info = compute_source_fingerprint(slug=slug, thread_id=tid, workdir=wd)
    sources_fresh = bool(fp_info.get("sources_fresh"))

    runs_thread = wd / "runs" / tid
    agents = wd / "outputs" / ".agents" / slug
    live = _env_live_subagent()

    stages, latest = load_stages(runs_thread, sources_fresh=sources_fresh)
    has_stages = bool(stages)
    honesty_msgs: list[str] = []

    if not has_stages:
        honesty_msgs.append("no_product_run: missing runs/<thread>/stages (bare pi ≠ product chain)")

    status = _overall_status(
        has_stages=has_stages,
        latest=latest,
        stages=stages,
        sources_fresh=sources_fresh,
    )

    # current from latest_snapshot or last stage
    if latest:
        cur_src = latest
    elif stages:
        last = stages[-1]
        cur_src = {
            "node": last.get("node"),
            "stage": last.get("stage"),
            "human_required": last.get("human_required"),
            "last_error": last.get("last_error"),
            **(last.get("counters") or {}),
        }
    else:
        cur_src = {}

    current = {
        "node": cur_src.get("node"),
        "stage": cur_src.get("stage"),
        "human_required": bool(cur_src.get("human_required")),
        "last_error": cur_src.get("last_error") or "",
        "counters": {
            "solver_tune": int(cur_src.get("solver_tune") or 0),
            "schema_repair": int(cur_src.get("schema_repair") or 0),
            "validate_repair": int(cur_src.get("validate_repair") or 0),
            "revise_count": int(cur_src.get("revise_count") or 0),
        },
    }
    if stages and stages[-1].get("counters") and not latest:
        current["counters"] = dict(stages[-1]["counters"])

    # M1 Part3: stable error surface for UI (banner / copy / stage jump)
    err_block = _build_error_block(current=current, stages=stages, status=status)
    if err_block.get("stage_seq") is not None:
        current["error_stage_seq"] = err_block["stage_seq"]
    current["has_error"] = bool(err_block.get("has_error"))

    next_actions = _build_next_actions(
        slug=slug,
        thread_id=tid,
        workdir=wd,
        home=home,
        current=current,
        stages=stages,
        status=status,
        error=err_block,
    )
    err_block = dict(err_block)
    err_block["next_actions"] = next_actions

    dispatches: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    thinking_any = False
    events_truncated = False
    events_cap_hit = False
    log_cursors: dict[str, dict[str, Any]] = {}
    transcript_missing = False
    if agents.is_dir():
        (
            dispatches,
            events,
            thinking_any,
            dmsgs,
            events_truncated,
            log_cursors,
            events_cap_hit,
            transcript_missing,
        ) = build_dispatches(agents, root=wd, home=home, slug=slug)
        honesty_msgs.extend(dmsgs)
    elif has_stages:
        honesty_msgs.append("agents_dir_missing: no outputs/.agents/<slug>")

    # summary stats for P2 UI / gates
    event_kind_totals: dict[str, int] = {}
    for e in events:
        k = str(e.get("kind") or "")
        event_kind_totals[k] = event_kind_totals.get(k, 0) + 1
    sub_event_count = sum(1 for e in events if e.get("source") == "sub")
    lead_event_count = sum(1 for e in events if e.get("source") == "lead")
    children_n = sum(len(d.get("children") or []) for d in dispatches)

    thinking = (
        {
            "status": "available",
            "note": "thinking/reasoning present in lead stream",
        }
        if thinking_any
        else {
            "status": "thinking_unavailable",
            "note": (
                "thinking_unavailable — 模型/Pi 未返回思维链；以下为工具与回复轨迹（L2）"
            ),
        }
    )

    stage_paths = None
    if latest:
        stage_paths = dict(latest.get("paths") or {})
    elif stages:
        stage_paths = dict(stages[-1].get("paths") or {})

    artifacts = collect_artifacts(wd, slug, tid, stage_paths)

    honesty = {
        "bare_pi": not has_stages,
        "live_off": not live,
        "transcript_missing": transcript_missing,
        "messages": honesty_msgs,
        "events_truncated": events_truncated,
        "events_cap_hit": events_cap_hit,
    }

    if not live:
        honesty["messages"] = list(honesty["messages"]) + ["LIVE=0: no live subagent expected"]
    if events_truncated:
        honesty["messages"] = list(honesty["messages"]) + [
            "events_truncated: large lead log tailed and/or events capped"
        ]

    ev_count = len(events)
    prev_ev = prev_events_count if prev_events_count is not None else None
    events_added = (ev_count - prev_ev) if prev_ev is not None else None
    dirty = True
    if prev_fingerprint is not None:
        dirty = prev_fingerprint != fp_info["fingerprint"]

    poll = {
        "schema_poll": POLL_SCHEMA,
        "fingerprint": fp_info["fingerprint"],
        "dirty": dirty,
        "stages_count": len(stages),
        "stages_mtime_max": fp_info.get("stages_mtime_max"),
        "agents_mtime_max": fp_info.get("agents_mtime_max"),
        "sources_fresh": sources_fresh,
        "log_cursors": log_cursors or fp_info.get("log_cursors") or {},
        "events_count": ev_count,
        "events_added": events_added,
        "events_truncated": events_truncated,
        "events_cap_hit": events_cap_hit,
        "max_events": MAX_EVENTS,
        "event_kinds": event_kind_totals,
        "lead_events": lead_event_count,
        "sub_events": sub_event_count,
        "children_count": children_n,
    }

    process = {
        "subagent_dispatches": sum(1 for d in dispatches if d.get("subagent_detected")),
        "cosplay_dispatches": sum(1 for d in dispatches if d.get("cosplay")),
        "children_count": children_n,
        "transcript_missing": transcript_missing,
        "event_kinds": event_kind_totals,
        "lead_events": lead_event_count,
        "sub_events": sub_event_count,
    }

    tier2 = discover_pi_sessions(workdir=wd, limit=10, home=home)
    if not tier2.get("pi_session_env"):
        msgs = list(honesty.get("messages") or [])
        if not any("tier2_session_off" in str(m) for m in msgs):
            msgs.append(
                "tier2_session_off: ORPATH_PI_SESSION not set — product leads use --no-session; "
                "kanban may only see interactive pi sessions"
            )
        honesty["messages"] = msgs
        # also fold tier2.honesty
        for m in tier2.get("honesty") or []:
            if m not in honesty["messages"]:
                honesty["messages"].append(m)

    # P5 Tier-3 optional Langfuse — surface only; does not replace Watch
    lf_raw = (os.environ.get("ORPATH_LANGFUSE") or os.environ.get("LANGFUSE_ENABLED") or "0").strip().lower()
    lf_on = lf_raw in {"1", "true", "yes", "on"}
    tier3 = {
        "enabled": lf_on,
        "hint": "docs/p5-tier3-langfuse.md",
        "note": (
            "Langfuse wired (env on) — still secondary to Watch"
            if lf_on
            else "optional portfolio/debug graph; set ORPATH_LANGFUSE=1 + keys to enable spans (see docs)"
        ),
        "host": (os.environ.get("LANGFUSE_HOST") or os.environ.get("LANGFUSE_BASE_URL") or ""),
        "replaces_watch": False,
    }

    dialogue = build_dialogue(
        workdir=wd,
        slug=slug,
        stages=stages if isinstance(stages, list) else [],
        current=current if isinstance(current, dict) else {},
        status=str(status or ""),
        artifacts=artifacts if isinstance(artifacts, dict) else {},
        honesty_messages=list(honesty.get("messages") or [])
        if isinstance(honesty, dict)
        else [],
    )

    snap: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": _utc(),
        "slug": slug,
        "thread_id": tid,
        "live_subagent": live,
        "status": status,
        "current": current,
        "stages": stages,
        "dispatches": dispatches,
        "events": events,
        "thinking": thinking,
        "artifacts": artifacts,
        "honesty": honesty,
        "poll": poll,
        "process": process,
        "tier2": tier2,
        "tier3": tier3,
        "dialogue": dialogue,
        "ui": {"phase": "P5", "event_cap_server": MAX_EVENTS, "dialogue": True},
        # M1 path contract: root alias = workdir (case data); home = install
        "root": str(wd),
        "workdir": str(wd),
        "home": str(home),
        "error": err_block,
        "next_actions": next_actions,
    }
    return snap


def validate_snapshot_shape(snap: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    for k in _REQUIRED_TOP:
        if k not in snap:
            errs.append(f"missing top key: {k}")
    if snap.get("schema_version") != SCHEMA_VERSION:
        errs.append(f"schema_version != {SCHEMA_VERSION}")
    if not isinstance(snap.get("stages"), list):
        errs.append("stages must be list")
    if not isinstance(snap.get("dispatches"), list):
        errs.append("dispatches must be list")
    if not isinstance(snap.get("events"), list):
        errs.append("events must be list")
    th = snap.get("thinking") or {}
    if th.get("status") not in {"available", "thinking_unavailable"}:
        errs.append("thinking.status invalid")
    poll = snap.get("poll")
    if poll is not None:
        if not isinstance(poll, dict):
            errs.append("poll must be dict")
        else:
            for pk in ("fingerprint", "stages_count", "events_count"):
                if pk not in poll:
                    errs.append(f"poll missing {pk}")
    return errs


def assert_no_llm_imports(source_path: Path | None = None) -> None:
    """Gate helper: this module must not pull LLM SDKs."""
    path = source_path or Path(__file__)
    text = path.read_text(encoding="utf-8")
    # Only real import lines (not strings inside this checker).
    patterns = (
        re.compile(r"(?m)^\s*import\s+openai\b"),
        re.compile(r"(?m)^\s*from\s+openai\b"),
        re.compile(r"(?m)^\s*import\s+anthropic\b"),
        re.compile(r"(?m)^\s*from\s+anthropic\b"),
        re.compile(r"(?m)^\s*import\s+litellm\b"),
        re.compile(r"(?m)^\s*from\s+litellm\b"),
        re.compile(r"(?m)^\s*import\s+google\.generativeai\b"),
        re.compile(r"(?m)^\s*from\s+google\.generativeai\b"),
    )
    for pat in patterns:
        if pat.search(text):
            raise AssertionError(f"LLM import banned in watch_snapshot: {pat.pattern}")


__all__ = [
    "SCHEMA_VERSION",
    "POLL_SCHEMA",
    "build_snapshot",
    "compute_source_fingerprint",
    "validate_snapshot_shape",
    "parse_lead_events",
    "parse_transcript_events",
    "load_subagent_artifact_index",
    "discover_pi_sessions",
    "read_log_text",
    "detect_subagent_calls",
    "assert_no_llm_imports",
]
