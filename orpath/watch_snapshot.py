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

_CANONICAL_DOMAINS: tuple[str, ...] = (
    "tube",
    "routing",
    "scheduling",
    "project",
    "inventory",
    "facility",
    "rostering",
    "microgrid",
    "pricing",
    "finance",
)

_SUBAGENT_DETECT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'"tool(?:_name|Name)?"\s*:\s*"subagent"', re.I),
    re.compile(r"\btool\s*(?:call|use|invocation)?\s*[:=]?\s*subagent\b", re.I),
    re.compile(r'"name"\s*:\s*"subagent"', re.I),
    re.compile(
        r"\bor[-_](?:analyst|verifier|reviewer|researcher|modeler|writer|verifier_writer|orchestrator|"
        r"(?:tube|routing|vrp|jssp|scheduling|project|inventory|facility|rostering|microgrid|pricing|finance)[-_a-z0-9]+|composite[-_]lead)\b",
        re.I,
    ),
    re.compile(r"\bsubagent\s*\(", re.I),
    re.compile(r'"agent"\s*:\s*"(?:or[-_][a-z0-9_-]+|supervisor)"', re.I),
    re.compile(r"transfer_to_or_", re.I),
    re.compile(r"\[subagent\]", re.I),
)


def detect_subagent_calls(log_text: str) -> tuple[bool, list[str]]:
    """Heuristic scan of log text for subagent tool / agent evidence."""
    if not log_text:
        return False, []
    evidence: list[str] = []
    for line in log_text.splitlines():
        s = line.strip()
        if not s:
            continue
        if "npm:pi-subagents" in s and "subagent" not in s.replace("pi-subagents", ""):
            continue
        for pat in _SUBAGENT_DETECT_PATTERNS:
            if pat.search(s):
                evidence.append(s[:240])
                break
        if len(evidence) >= 12:
            break
    strong = any(
        re.search(
            r'"tool(?:_name|Name)?"\s*:\s*"subagent"|\btool\s+call\s+subagent\b|"agent"\s*:\s*"(?:or[-_]|supervisor)|transfer_to_or_',
            e,
            re.I,
        )
        for e in evidence
    )
    has_or = any(
        re.search(
            r"\bor[-_](?:verifier|reviewer|researcher|modeler|writer|verifier_writer|orchestrator|"
            r"(?:tube|routing|vrp|jssp|scheduling|project|inventory|facility|rostering|microgrid|pricing|finance)[-_a-z0-9]+|composite[-_]lead)\b",
            e,
            re.I,
        )
        for e in evidence
    )
    has_sub_word = any(
        re.search(r"\bsubagent\b", e.replace("pi-subagents", ""), re.I) for e in evidence
    )
    detected = bool(strong or (has_or and has_sub_word) or len(evidence) >= 2)
    return detected, evidence


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

_STAGE_ROLE: dict[str, str] = {
    "supervisor": "or-supervisor",
    "analyst": "or-analyst",
    "or_analyst": "or-analyst",
    "research": "or-researcher",
    "or_researcher": "or-researcher",
    "model": "or-modeler",
    "or_modeler": "or-modeler",
    "modeler_track_a": "or-modeler",
    "modeler_track_b": "or-modeler",
    "tier_c_focus": "or-modeler",
    "cite": "or-verifier",
    "validator": "or-verifier",
    "table_render": "or-verifier",
    "doc_gate": "or-verifier",
    "or_verifier": "or-verifier",
    "or_writer": "or-writer",
    "or_reviewer": "or-reviewer",
    "or_verifier_writer": "or-verifier",
    "review": "or-reviewer",
    "draft": "or-writer",
    "explain": "or-writer",
    "orchestrate": "or-orchestrator",
}

_ALL_LEAD_STAGES = "|".join(re.escape(k) for k in _STAGE_ROLE.keys())
_LEAD_NAME_RE = re.compile(
    rf"^(?P<stage>{_ALL_LEAD_STAGES})(?:-lead)?(?:-(?P<ts>\d{{8}}T\d{{6}}Z))?\.log$",
    re.I,
)

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
    # Track key problem/solution artifacts so importing or solving triggers poll dirty
    for art_rel in (
        f"outputs/{slug}-intake.json",
        f"notes/{slug}-problem-brief.md",
        f"outputs/{slug}-schema.json",
        f"outputs/{slug}-solution.json",
        f"outputs/{slug}-validate.json",
        f"papers/{slug}.md",
    ):
        ap = wd / art_rel
        try:
            if ap.is_file():
                ast = ap.stat()
                h.update(f"a:{art_rel}:{int(ast.st_size)}:{float(ast.st_mtime):.3f}|".encode())
        except OSError:
            pass
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
            if p.stem == agents.name or p.stem in {"agent", "multiagent", "supervisor"}:
                stage = "supervisor"
            else:
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
        et = str(obj.get("type") or obj.get("event") or "")
        ts = str(obj.get("timestamp") or obj.get("utc") or "")

        # Multi-agent callback events
        if et in {"stage", "agent_start", "agent_end"}:
            ag = obj.get("agent") or "supervisor"
            step = obj.get("step")
            push(et, f"{et} step={step} agent={ag}", ts, agent=ag)
            continue

        if et == "tool_start":
            tool_name = str(obj.get("tool") or "")
            ag = obj.get("agent") or "agent"
            push("tool", f"{tool_name} agent={ag}", ts, tool=tool_name, agent=ag)
            continue

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

        children: list[dict[str, Any]] = []

        # event kind counts for UI
        kind_counts: dict[str, int] = {}
        for e in evs:
            k = str(e.get("kind") or "")
            kind_counts[k] = kind_counts.get(k, 0) + 1

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


_CLASS_TITLES_ZH: dict[str, str] = {
    "tube_cut": "异形圆管工件激光下料优化 (Tube Cutting)",
    "polyomino_cover": "异形多联骨牌覆盖与板材排样 (Polyomino Cover)",
    "shortest_path": "网络流最短路径规划 (Shortest Path)",
    "tsp": "多节点旅行商巡检规划 (TSP)",
    "vrp": "多车带容量路径调度 (VRP)",
}


def _find_fixture_problem_md(home: Path, workdir: Path, problem_id: str, problem_class: str, slug: str) -> Path | None:
    cands: list[Path] = []
    for base in (workdir, home):
        if problem_id:
            for tier in ("t3", "t2", "t1"):
                cands.append(base / "fixtures" / tier / problem_id / "problem.md")
        if problem_class == "tube_cut" or "tube" in slug.lower():
            cands.append(base / "fixtures" / "intake" / "tube_cut_b2026" / "problem-surface.md")
            cands.append(base / "fixtures" / "t3" / "tube_cut_b2026" / "problem.md")
        if problem_class == "polyomino_cover" or "poly" in slug.lower():
            cands.append(base / "fixtures" / "t3" / "polyomino_b_q1" / "problem.md")
        if problem_class == "shortest_path" or slug in {"m0", "test"}:
            cands.append(base / "fixtures" / "t1" / "shortest_path" / "problem.md")
    for p in cands:
        if p.is_file():
            return p
    return None


def _extract_heading_title(md_text: str) -> str:
    for line in (md_text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            t = s.lstrip("#").strip()
            if t and not t.lower().startswith("problem brief") and not t.lower().startswith("sources"):
                return t
        if "B 题" in s or "A 题" in s or "C 题" in s or "优化问题" in s:
            return s[:80]
    for line in (md_text or "").splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()[:80]
    return ""


def build_problem_view(
    *,
    workdir: Path,
    home: Path,
    slug: str,
    stage_paths: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic disk reader for Problem Intake & Solution Workbench (zero LLM)."""
    intake_file = workdir / "outputs" / f"{slug}-intake.json"
    brief_file = workdir / "notes" / f"{slug}-problem-brief.md"
    ocr_raw_file = workdir / "notes" / f"{slug}-ocr.raw.md"
    schema_file = workdir / "outputs" / f"{slug}-schema.json"
    solution_file = workdir / "outputs" / f"{slug}-solution.json"
    validate_file = workdir / "outputs" / f"{slug}-validate.json"
    paper_file = workdir / "papers" / f"{slug}.md"
    explain_file = workdir / "notes" / f"{slug}-explain.md"
    research_file = workdir / "notes" / f"{slug}-research.md"

    if stage_paths:
        if not intake_file.is_file() and stage_paths.get("intake_path"):
            p = Path(str(stage_paths["intake_path"]))
            if p.is_file():
                intake_file = p
        if not brief_file.is_file() and stage_paths.get("brief_path"):
            p = Path(str(stage_paths["brief_path"]))
            if p.is_file():
                brief_file = p
        if not schema_file.is_file() and stage_paths.get("schema_path"):
            p = Path(str(stage_paths["schema_path"]))
            if p.is_file():
                schema_file = p
        if not solution_file.is_file() and stage_paths.get("solution_path"):
            p = Path(str(stage_paths["solution_path"]))
            if p.is_file():
                solution_file = p
        if not validate_file.is_file() and stage_paths.get("validate_path"):
            p = Path(str(stage_paths["validate_path"]))
            if p.is_file():
                validate_file = p

    intake_doc = _read_json(intake_file) if intake_file.is_file() else None
    schema_doc = _read_json(schema_file) if schema_file.is_file() else None
    solution_doc = _read_json(solution_file) if solution_file.is_file() else None
    validate_doc = _read_json(validate_file) if validate_file.is_file() else None

    intake_pid_hint = str((intake_doc or {}).get("problem_id_hint") or "").strip()
    intake_pclass_hint = str((intake_doc or {}).get("problem_class_hint") or "").strip()

    problem_id = (
        (schema_doc or {}).get("problem_id")
        or (solution_doc or {}).get("problem_id")
        or (validate_doc or {}).get("problem_id")
        or intake_pid_hint
        or ""
    )
    # Per specs/problem-intake.md §6.4: problem_class_hint is a soft hint, NOT a validated schema class,
    # unless paired with an explicit solvable preset problem_id_hint.
    problem_class = (
        (schema_doc or {}).get("problem_class")
        or (solution_doc or {}).get("problem_class")
        or (validate_doc or {}).get("problem_class")
        or (intake_pclass_hint if intake_pid_hint else "")
        or ""
    )
    slug_l = slug.lower()
    if not problem_class and intake_doc is None:
        if "tube" in slug_l or "tube" in str(problem_id).lower():
            problem_class = "tube_cut"
        elif "poly" in slug_l or "poly" in str(problem_id).lower():
            problem_class = "polyomino_cover"
        elif "vrp" in slug_l or "cvrp" in slug_l:
            problem_class = "vrp"
        elif "tsp" in slug_l:
            problem_class = "tsp"
        elif slug_l in {"m0", "test", "sp", "shortest_path"} or "shortest" in str(problem_id).lower():
            problem_class = "shortest_path"

    brief_text = ""
    brief_source_rel = None
    if brief_file.is_file():
        try:
            brief_text = brief_file.read_text(encoding="utf-8", errors="replace")[:20000]
            brief_source_rel = _rel_or_str(brief_file, workdir)
        except OSError:
            brief_text = ""
    elif ocr_raw_file.is_file():
        try:
            brief_text = ocr_raw_file.read_text(encoding="utf-8", errors="replace")[:20000]
            brief_source_rel = _rel_or_str(ocr_raw_file, workdir)
        except OSError:
            brief_text = ""
    else:
        fx_md = _find_fixture_problem_md(home, workdir, str(problem_id), str(problem_class), slug)
        if fx_md is not None:
            try:
                brief_text = fx_md.read_text(encoding="utf-8", errors="replace")[:20000]
                brief_source_rel = _rel_or_str(fx_md, home)
            except OSError:
                brief_text = ""

    title = _extract_heading_title(brief_text)
    if not title:
        title = _CLASS_TITLES_ZH.get(str(problem_class), "") or str(problem_id or slug)

    subproblems: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    data_assets: list[dict[str, Any]] = []
    deliverables: list[str] = []
    objectives_text = ""
    constraints_text = ""
    ocr_backend = "none"
    intake_status = "none"

    if isinstance(intake_doc, dict):
        intake_status = str(intake_doc.get("status") or "ok")
        ocr_backend = str(intake_doc.get("ocr_backend") or "manual_stub")
        for sp in intake_doc.get("subproblems") or []:
            if isinstance(sp, dict):
                subproblems.append({
                    "id": str(sp.get("id") or ""),
                    "title": str(sp.get("title") or ""),
                    "notes": str(sp.get("notes") or ""),
                    "must_deliver": list(sp.get("must_deliver") or []),
                    "data_refs": list(sp.get("data_refs") or [])[:10],
                })
        for src in intake_doc.get("sources") or []:
            if isinstance(src, dict):
                sources.append({
                    "path": str(src.get("path") or ""),
                    "kind": str(src.get("kind") or ""),
                    "pages": src.get("pages"),
                })
        raw_assets = intake_doc.get("data_assets") or []
        for a in raw_assets[:40]:
            if isinstance(a, dict):
                data_assets.append({
                    "path": str(a.get("path") or ""),
                    "kind": str(a.get("kind") or ""),
                    "role": str(a.get("role") or ""),
                })
        deliverables = [str(x) for x in (intake_doc.get("deliverables") or [])]
        objectives_text = str(intake_doc.get("objectives_text") or "")
        constraints_text = str(intake_doc.get("constraints_text") or "")
    elif brief_text:
        intake_status = "fixture"
        ocr_backend = "fixture"

    if not objectives_text and isinstance(schema_doc, dict):
        objectives_text = str(schema_doc.get("objective") or "")
    if not constraints_text and isinstance(schema_doc, dict):
        c_list = schema_doc.get("constraints") or []
        if isinstance(c_list, list):
            constraints_text = "；".join(str(x) for x in c_list[:8])

    # Schema summary
    schema_summary: dict[str, Any] = {"exists": isinstance(schema_doc, dict)}
    if isinstance(schema_doc, dict):
        params = schema_doc.get("parameters") if isinstance(schema_doc.get("parameters"), dict) else {}
        schema_summary.update({
            "problem_id": schema_doc.get("problem_id"),
            "problem_class": schema_doc.get("problem_class"),
            "sense": schema_doc.get("sense") or "minimize",
            "objective": schema_doc.get("objective"),
            "variables": schema_doc.get("variables") or {},
            "constraints": list(schema_doc.get("constraints") or [])[:20],
            "param_keys": list(params.keys())[:20],
            "nodes_count": len(params.get("nodes") or []) if isinstance(params.get("nodes"), list) else None,
            "edges_count": len(params.get("edges") or []) if isinstance(params.get("edges"), list) else None,
        })

    # Solution summary
    solution_summary: dict[str, Any] = {"exists": isinstance(solution_doc, dict)}
    if isinstance(solution_doc, dict):
        sol_questions: list[dict[str, Any]] = []
        q_dict = solution_doc.get("questions")
        if isinstance(q_dict, dict):
            for qk in sorted(q_dict.keys()):
                qv = q_dict[qk]
                if not isinstance(qv, dict):
                    continue
                stocks = qv.get("stocks") if isinstance(qv.get("stocks"), list) else []
                batches = qv.get("batches") if isinstance(qv.get("batches"), list) else []
                sol_questions.append({
                    "id": qk.upper(),
                    "status": qv.get("status") or solution_doc.get("status"),
                    "total_stock_length_mm": qv.get("total_stock_length_mm") or qv.get("total_stock_length") or qv.get("total_new_standard_stock_mm"),
                    "total_cocut_gain_mm": qv.get("total_cocut_gain_mm") or qv.get("total_cocut_gain") or qv.get("cocut_gain_mm"),
                    "total_switches": qv.get("total_switches") or qv.get("switches"),
                    "overall_utilization": qv.get("overall_utilization") or qv.get("utilization"),
                    "stocks_count": len(stocks),
                    "batches_count": len(batches),
                    "stocks_preview": [
                        {
                            "id": st.get("id"),
                            "stock_length_mm": st.get("stock_length_mm"),
                            "used_length_mm": st.get("used_length_mm"),
                            "leftover_mm": st.get("leftover_mm"),
                            "utilization": st.get("utilization"),
                            "switches": st.get("switches"),
                            "parts_count": len(st.get("sequence") or []),
                            "sequence_head": (st.get("sequence") or [])[:12],
                        }
                        for st in stocks[:12]
                        if isinstance(st, dict)
                    ],
                })
        solution_summary.update({
            "status": solution_doc.get("status"),
            "objective": solution_doc.get("objective"),
            "solver": solution_doc.get("solver"),
            "source": solution_doc.get("source"),
            "path": solution_doc.get("path"),
            "tour": solution_doc.get("tour"),
            "routes": solution_doc.get("routes"),
            "placements": (solution_doc.get("placements") or [])[:30] if isinstance(solution_doc.get("placements"), list) else None,
            "questions": sol_questions,
            "metrics": solution_doc.get("metrics") if isinstance(solution_doc.get("metrics"), dict) else None,
        })

    # Validate summary
    validate_summary: dict[str, Any] = {"exists": isinstance(validate_doc, dict)}
    if isinstance(validate_doc, dict):
        checks = validate_doc.get("checks") if isinstance(validate_doc.get("checks"), list) else []
        passed = sum(1 for c in checks if isinstance(c, dict) and c.get("ok"))
        validate_summary.update({
            "ok": bool(validate_doc.get("ok")),
            "total_checks": len(checks),
            "passed_checks": passed,
            "failed_checks": len(checks) - passed,
            "checks": [
                {
                    "name": c.get("name"),
                    "ok": bool(c.get("ok")),
                    "expected": c.get("expected"),
                    "got": c.get("got"),
                    "detail": c.get("detail"),
                }
                for c in checks[:40]
                if isinstance(c, dict)
            ],
            "errors": list(validate_doc.get("errors") or []),
        })

    paper_preview = ""
    paper_rel = None
    if paper_file.is_file():
        try:
            paper_preview = paper_file.read_text(encoding="utf-8", errors="replace")[:12000]
            paper_rel = _rel_or_str(paper_file, workdir)
        except OSError:
            pass
    elif explain_file.is_file():
        try:
            paper_preview = explain_file.read_text(encoding="utf-8", errors="replace")[:12000]
            paper_rel = _rel_or_str(explain_file, workdir)
        except OSError:
            pass

    has_problem = bool(
        intake_doc is not None
        or brief_text
        or schema_doc is not None
        or solution_doc is not None
    )

    return {
        "has_problem": has_problem,
        "has_intake": intake_doc is not None,
        "title": title,
        "problem_id": str(problem_id or ""),
        "problem_class": str(problem_class or ""),
        "intake_status": intake_status,
        "ocr_backend": ocr_backend,
        "brief_path": brief_source_rel,
        "brief_text": brief_text,
        "subproblems": subproblems,
        "sources": sources,
        "data_assets": data_assets,
        "data_assets_total": len((intake_doc or {}).get("data_assets") or []) if isinstance(intake_doc, dict) else 0,
        "deliverables": deliverables,
        "objectives_text": objectives_text,
        "constraints_text": constraints_text,
        "schema_summary": schema_summary,
        "solution_summary": solution_summary,
        "validate_summary": validate_summary,
        "paper_path": paper_rel,
        "paper_preview": paper_preview,
        "research_exists": research_file.is_file(),
    }


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
        "supervisor": "中心主控",
        "or_researcher": "文献研判",
        "or_modeler": "数学建模",
        "or_verifier": "独立验算",
        "or_writer": "学术论文",
        "or_reviewer": "同行评审",
        "or_verifier_writer": "验算成文",
        "or_tube_lead": "管件主控",
        "or_tube_geometry": "几何审计",
        "or_tube_q1q2": "Q1/Q2求解",
        "or_tube_q3": "Q3联合堆叠",
        "or_tube_q4": "Q4多批余料",
        "or_tube_redteam": "红队对抗验算",
        "retrieve": "检索",
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
        "supervisor",
        "or_researcher",
        "or_modeler",
        "or_verifier",
        "or_writer",
        "or_reviewer",
        "or_verifier_writer",
        "or_tube_lead",
        "or_tube_geometry",
        "or_tube_q1q2",
        "or_tube_q3",
        "or_tube_q4",
        "or_tube_redteam",
        "retrieve",
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

    tier2 = {
        "pi_session_env": False,
        "sessions_root": "",
        "sessions_root_exists": False,
        "recent": [],
        "kanban_hint": "START.bat / START.sh 启动 Web Studio",
        "supervise_hint": "tools/validate_solution.py 独立数学与物理校验",
        "deep_links": [],
        "honesty": [],
    }

    # Optional Langfuse — surface only; does not replace Watch
    lf_raw = (os.environ.get("ORPATH_LANGFUSE") or os.environ.get("LANGFUSE_ENABLED") or "0").strip().lower()
    lf_on = lf_raw in {"1", "true", "yes", "on"}
    tier3 = {
        "enabled": lf_on,
        "note": (
            "Langfuse wired (env on) — still secondary to Watch"
            if lf_on
            else "optional portfolio/debug graph; set ORPATH_LANGFUSE=1 + keys to enable spans"
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

    problem_view = build_problem_view(
        workdir=wd,
        home=home,
        slug=slug,
        stage_paths=stage_paths,
    )

    # Infer active domain
    active_domain = "generic"
    for d_name in _CANONICAL_DOMAINS:
        if d_name in slug.lower() or (isinstance(problem_view, dict) and d_name in str(problem_view.get("problem_id", "")).lower()):
            active_domain = d_name
            break
    if active_domain == "generic" and isinstance(dispatches, list):
        for disp in dispatches:
            role_str = str(disp.get("role", "")).lower()
            for d_name in _CANONICAL_DOMAINS:
                if f"or-{d_name}" in role_str or f"or_{d_name}" in role_str:
                    active_domain = d_name
                    break
            if active_domain != "generic":
                break

    domain_roles: list[dict[str, Any]] = []

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
        "problem_view": problem_view,
        "domain": active_domain,
        "domain_roles": domain_roles,
        "ui": {"phase": "P5", "event_cap_server": MAX_EVENTS, "dialogue": True, "problem_workbench": True},
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
    "read_log_text",
    "detect_subagent_calls",
    "assert_no_llm_imports",
]
