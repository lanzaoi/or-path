"""M1: Pi lead spawn + subagent-call detection (Feynman-aligned).

Control plane still LG; this module is the in-node runtime for short leads that
MUST call the Pi `subagent` tool (except draft lead, which may write directly).

Hard laws (grilled):
- Dispatch API = Pi tool name `subagent` only (not role cosplay).
- Forced stages: research (wide), cite→verifier, review→reviewer.
- Draft lead may write draft; lead must NOT write cited/review body alone.
- No Pi / no pi-subagents / no API key → fail (no silent mock green).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

# Tool name as registered by pi-subagents extension
SUBAGENT_TOOL_NAME = "subagent"

# Stages that require at least one real subagent tool call in the lead log
FORCED_SUBAGENT_STAGES = frozenset(
    {
        "research",
        "cite",
        "cite_pack",
        "review",
        "review_pack",
        "model",  # M3: or-modeler via subagent when live
    }
)

# Stages where lead is allowed to write the primary artifact without subagent
LEAD_OWNED_STAGES = frozenset(
    {
        "draft",
        "draft_paper",
        "provenance",
        "explain",
        "orchestrate",
    }
)

DEFAULT_PROVIDER = "deepseek"
DEFAULT_MODEL = "deepseek-v4-flash"


def _effective_defaults() -> tuple[str, str]:
    try:
        from orpath.pi_model_pref import resolve_launch_model

        return resolve_launch_model()
    except Exception:  # noqa: BLE001
        return (
            os.environ.get("ORPATH_PI_PROVIDER", DEFAULT_PROVIDER).strip() or DEFAULT_PROVIDER,
            os.environ.get("ORPATH_PI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        )

# Patterns that indicate a real subagent tool invocation in Pi logs / jsonl
_CALL_PATTERNS = [
    re.compile(r"\bsubagent\b", re.I),
    re.compile(r'"tool(?:Name)?"\s*:\s*"subagent"', re.I),
    re.compile(r'"name"\s*:\s*"subagent"', re.I),
    re.compile(r"toolName['\"]?\s*[:=]\s*['\"]subagent['\"]", re.I),
    # Pi --mode json tool events
    re.compile(r'"type"\s*:\s*"tool_call"[^\n]{0,200}"name"\s*:\s*"subagent"', re.I),
    re.compile(r'"name"\s*:\s*"subagent"[^\n]{0,80}"type"\s*:\s*"tool', re.I),
    re.compile(r'"toolName"\s*:\s*"subagent"', re.I),
    re.compile(r"tool_use[^\n]{0,80}subagent", re.I),
]



@dataclass
class EnvCheck:
    ok: bool
    pi_cli: str | None
    pi_subagents_ok: bool
    api_key_ok: bool
    agent_dir: str | None
    project_agents: list[str] = field(default_factory=list)
    detail: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class LeadResult:
    ok: bool
    stage: str
    slug: str
    log_path: str
    exit_code: int | None
    started_utc: str
    finished_utc: str
    duration_s: float
    subagent_calls_detected: bool
    call_evidence: list[str] = field(default_factory=list)
    cmd: list[str] = field(default_factory=list)
    error: str = ""
    stdout_tail: str = ""
    stderr_tail: str = ""


def project_root(start: Path | None = None) -> Path:
    """Install root for Pi defs / tools — never a bare case workdir.

    Prefer ``ORPATH_HOME`` / package home. Walking from a Path-A workdir
    (no orpath.bat) used to return the case folder and then fail with
    ``missing .pi/agents`` / ``missing .pi/settings.json``.
    """
    try:
        from orpath.paths import orpath_home

        home = orpath_home()
        if (home / "orpath").is_dir():
            return home.resolve()
    except Exception:  # noqa: BLE001
        pass
    if start is None:
        start = Path.cwd()
    p = start.resolve()
    for cand in [p, *p.parents]:
        if (cand / "orpath").is_dir() and (cand / "orpath.bat").is_file():
            return cand
    # last resort: package parent
    return Path(__file__).resolve().parents[1]


def agents_dir(root: Path | None = None) -> Path:
    try:
        from orpath.paths import agents_dir as _agents_home

        return _agents_home()
    except Exception:  # noqa: BLE001
        r = project_root(root)
        return r / ".pi" / "agents"


def agent_logs_dir(root: Path, slug: str) -> Path:
    """Per-case lead logs under workdir (Path A), not install home."""
    try:
        from orpath.paths import case_agents_dir, orpath_home, orpath_workdir

        home_p = orpath_home().resolve()
        root_p = Path(root).resolve()
        if root_p != home_p:
            d = root_p / "outputs" / ".agents" / slug
            d.mkdir(parents=True, exist_ok=True)
            return d
        d = case_agents_dir(orpath_workdir(), slug)
        d.mkdir(parents=True, exist_ok=True)
        return d
    except Exception:  # noqa: BLE001
        d = Path(root) / "outputs" / ".agents" / slug
        d.mkdir(parents=True, exist_ok=True)
        return d


def find_pi_cli(root: Path) -> str | None:
    candidates = [
        root / "runtime" / "node_modules" / "@earendil-works" / "pi-coding-agent" / "dist" / "cli.js",
        root / "runtime" / "node_modules" / ".bin" / "pi.cmd",
        root / "pi.bat",
    ]
    for c in candidates:
        if c.is_file():
            return str(c.resolve())
    which = shutil.which("pi")
    return which


def find_pi_subagents_pkg(root: Path) -> Path | None:
    cands = [
        root / "runtime" / "node_modules" / "pi-subagents",
        root / "runtime" / "node_modules" / "@earendil-works" / "pi-subagents",
        Path.home() / ".pi" / "agent" / "npm" / "node_modules" / "pi-subagents",
    ]
    for c in cands:
        if c.is_dir() and (c / "package.json").is_file():
            return c
    return None


def api_key_present() -> bool:
    for k in (
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "XAI_API_KEY",
    ):
        if os.environ.get(k, "").strip():
            return True
    # Pi auth.json may hold oauth tokens
    auth = Path.home() / ".pi" / "agent" / "auth.json"
    if auth.is_file() and auth.stat().st_size > 10:
        return True
    return False


def list_project_agents(root: Path) -> list[str]:
    d = agents_dir(root)
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("or-*.md"))


def check_env(root: Path | None = None) -> EnvCheck:
    # Pi agent defs + settings always on install home (Path A workdir has no .pi).
    home = project_root(root)
    errors: list[str] = []
    pi_cli = find_pi_cli(home)
    if not pi_cli:
        errors.append("pi CLI not found (runtime/.../cli.js or pi.bat)")
    pkg = find_pi_subagents_pkg(home)
    if not pkg:
        errors.append("pi-subagents package not installed under runtime or ~/.pi/agent/npm")
    key_ok = api_key_present()
    if not key_ok:
        errors.append("no API key / Pi auth.json (DEEPSEEK_API_KEY or ~/.pi/agent/auth.json)")
    agents = list_project_agents(home)
    required = {
        "or-orchestrator",
        "or-researcher",
        "or-modeler",
        "or-writer",
        "or-verifier",
        "or-reviewer",
    }
    missing = sorted(required - set(agents))
    if missing:
        errors.append(f"missing agent defs: {missing}")
    # settings packages
    settings = home / ".pi" / "settings.json"
    if settings.is_file():
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
            pkgs = " ".join(str(x) for x in (data.get("packages") or []))
            if "pi-subagents" not in pkgs:
                errors.append(".pi/settings.json packages missing npm:pi-subagents")
        except json.JSONDecodeError:
            errors.append(".pi/settings.json invalid JSON")
    else:
        errors.append("missing .pi/settings.json")

    ok = not errors
    return EnvCheck(
        ok=ok,
        pi_cli=pi_cli,
        pi_subagents_ok=pkg is not None,
        api_key_ok=key_ok,
        agent_dir=str(agents_dir(home)),
        project_agents=agents,
        detail="ok" if ok else "; ".join(errors),
        errors=errors,
    )


def require_env(root: Path | None = None) -> EnvCheck:
    """Q14: no silent mock — raise if environment incomplete."""
    chk = check_env(root)
    if not chk.ok:
        raise RuntimeError(f"OR-Path subagent env FAIL: {chk.detail}")
    return chk


def detect_subagent_calls(text: str) -> tuple[bool, list[str]]:
    """Return (hit, evidence lines). Prefer real Pi JSON tool events over prose."""
    if not text:
        return False, []
    evidence: list[str] = []

    # Strong signals: actual toolCall / tool_execution for subagent
    strong = [
        re.compile(r'"type"\s*:\s*"toolCall"[^\n]{0,300}"name"\s*:\s*"subagent"', re.I),
        re.compile(r'"name"\s*:\s*"subagent"[^\n]{0,200}"type"\s*:\s*"toolCall"', re.I),
        re.compile(r'"type"\s*:\s*"tool_execution_start"[^\n]{0,300}subagent', re.I),
        re.compile(r'"toolName"\s*:\s*"subagent"', re.I),
        re.compile(r'"name"\s*:\s*"subagent".{0,80}"arguments"', re.I | re.S),
    ]
    for i, line in enumerate(text.splitlines(), 1):
        for pat in strong:
            if pat.search(line):
                evidence.append(f"L{i}: {line.strip()[:220]}")
                break
        if len(evidence) >= 8:
            break

    if evidence:
        return True, evidence

    # Fallback weaker patterns (legacy text mode) — exclude prompt-only chatter
    for i, line in enumerate(text.splitlines(), 1):
        if re.search(r"pi-subagents|npm:pi-subagents|stage lead|REQUIRED: call", line, re.I):
            continue
        if re.search(r'"name"\s*:\s*"subagent"', line) or re.search(
            r"toolName['\"]?\s*[:=]\s*['\"]subagent['\"]", line
        ):
            evidence.append(f"L{i}: {line.strip()[:220]}")
        if len(evidence) >= 6:
            break
    return (len(evidence) > 0), evidence



def stage_requires_subagent(stage: str) -> bool:
    return stage.strip().lower() in FORCED_SUBAGENT_STAGES


def verify_outputs(
    paths: Sequence[Path],
    *,
    lead_start_ts: float | None = None,
    min_bytes: int = 1,
) -> list[str]:
    errs: list[str] = []
    for p in paths:
        path = Path(p)
        if not path.is_file():
            errs.append(f"missing output: {path}")
            continue
        if path.stat().st_size < min_bytes:
            errs.append(f"empty/too small: {path}")
        if lead_start_ts is not None and path.stat().st_mtime + 1 < lead_start_ts:
            errs.append(f"stale mtime (before lead start): {path}")
    return errs


def write_task_brief(
    root: Path,
    slug: str,
    stage: str,
    *,
    body: str,
    outputs: dict[str, str] | None = None,
) -> Path:
    """Feynman-style: long instructions on disk; subagent JSON stays short."""
    d = root / "outputs" / ".plans"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{slug}-{stage}-brief.md"
    outs = outputs or {}
    block = "\n".join(f"- `{k}`: `{v}`" for k, v in outs.items())
    text = (
        f"# Brief `{slug}` / stage `{stage}`\n\n"
        f"- utc: {datetime.now(timezone.utc).isoformat()}\n\n"
        f"## Required outputs\n{block or '- (see task)'}\n\n"
        f"## Instructions\n\n{body.rstrip()}\n"
    )
    path.write_text(text, encoding="utf-8")
    return path


def build_lead_prompt(
    *,
    stage: str,
    slug: str,
    brief_path: Path | str,
    required_agent: str | None,
    output_path: Path | str | None,
    extra_rules: str = "",
) -> str:
    """Short lead system+user hybrid prompt enforcing real subagent dispatch."""
    req = stage_requires_subagent(stage)
    lines = [
        f"You are the OR-Path **stage lead** for `{stage}` (slug=`{slug}`).",
        "You run inside Pi with the **subagent** tool from pi-subagents.",
        "",
        "## Hard laws",
        "1. Numbers truth only from solver JSON / validate — never invent optima.",
        "2. Prefer **file handoffs**; return short summaries + paths to parent.",
        "3. Do **not** cosplay child roles in prose without calling the tool.",
        "",
        f"Read the brief: `{brief_path}`",
        "",
    ]
    if req:
        agent = required_agent or {
            "research": "or-researcher",
            "cite": "or-verifier",
            "cite_pack": "or-verifier",
            "review": "or-reviewer",
            "review_pack": "or-reviewer",
            "model": "or-modeler",
        }.get(stage, "or-verifier")
        out = output_path or f"outputs/.drafts/{slug}-{stage}.md"
        lines += [
            f"## REQUIRED: call the `subagent` tool (not optional)",
            f"- You MUST invoke the tool named **subagent** (pi-subagents).",
            f"- agent: `{agent}`",
            f"- task: short pointer — Read `{brief_path}` and write the artifact.",
            f"- output: `{out}`",
            "- Set failFast false if using parallel tasks.",
            "- Keep subagent JSON small; do not paste multi-paragraph instructions in JSON.",
            f"- After the child returns, verify on disk that `{out}` exists.",
            "- **FORBIDDEN:** writing the full child artifact yourself without a real subagent tool call.",
            "- If you only write files with write/edit and never call `subagent`, you FAIL this stage.",
            "- If the subagent tool is missing, FAIL explicitly — say SUBAGENT_TOOL_MISSING.",
            "",
            "Example tool args shape:",
            "```",
            "{",
            f'  "agent": "{agent}",',
            f'  "task": "Read {brief_path} and complete the stage. Write output path.",',
            f'  "output": "{out}"',
            "}",
            "```",
        ]
    else:
        lines += [
            "## Lead-owned stage",
            "You may write the primary draft/provenance yourself when this is draft/provenance.",
            "Still use subagent for research/cite/review when those stages apply.",
        ]
    if extra_rules:
        lines += ["", "## Extra", extra_rules]
    lines += ["", "When done, print a one-line summary and absolute paths of artifacts."]
    return "\n".join(lines)


def pi_session_enabled() -> bool:
    """ORPATH_PI_SESSION=1 → write Pi sessions (Tier-2 kanban/Fleet).

    Default OFF so CI/gates keep --no-session (ephemeral).
    """
    raw = (os.environ.get("ORPATH_PI_SESSION") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def pi_sessions_root() -> Path:
    """Default Pi coding-agent sessions directory."""
    return Path.home() / ".pi" / "agent" / "sessions"


def resolve_no_session(no_session: bool | None = None) -> bool:
    """If no_session is None, derive from ORPATH_PI_SESSION (default: no_session=True)."""
    if no_session is not None:
        return bool(no_session)
    return not pi_session_enabled()


def build_pi_command(
    root: Path,
    *,
    prompt: str,
    provider: str | None = None,
    model: str | None = None,
    no_session: bool | None = None,
    json_mode: bool = True,
    tools: str | None = None,
    append_system_prompt: str | None = None,
) -> list[str]:
    chk = require_env(root)
    cli = chk.pi_cli
    assert cli
    ep, em = _effective_defaults()
    provider = (provider or ep).strip() or ep
    model = (model or em).strip() or em
    if cli.endswith(".js"):
        cmd = [
            "node",
            cli,
            "-p",
            "--provider",
            provider,
            "--model",
            model,
        ]
    elif cli.endswith((".bat", ".cmd")):
        cmd = [cli, "-p", "--provider", provider, "--model", model]
    else:
        cmd = [cli, "-p", "--provider", provider, "--model", model]
    if resolve_no_session(no_session):
        cmd.append("--no-session")
    # JSON event stream so tool_call / subagent names appear in logs (detection)
    if json_mode:
        cmd.extend(["--mode", "json"])
    # Ruthless harness: strip write/edit from lead so it cannot cosplay
    if tools:
        cmd.extend(["--tools", tools])
    if append_system_prompt:
        cmd.extend(["--append-system-prompt", append_system_prompt])
    cmd.append(prompt)
    return cmd


def spawn_lead(
    root: Path,
    *,
    slug: str,
    stage: str,
    prompt: str,
    provider: str | None = None,
    model: str | None = None,
    timeout_s: int = 1800,
    require_subagent_call: bool | None = None,
    expected_outputs: Sequence[Path] | None = None,
    dry_run: bool = False,
    tools: str | None = None,
    append_system_prompt: str | None = None,
    json_mode: bool = True,
    no_session: bool | None = None,
) -> LeadResult:
    """Run a short Pi lead; optionally enforce subagent call + output files."""
    root = project_root(root)
    started = time.time()
    started_utc = datetime.now(timezone.utc).isoformat()
    log_dir = agent_logs_dir(root, slug)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = log_dir / f"{stage}-lead-{ts}.log"

    if require_subagent_call is None:
        require_subagent_call = stage_requires_subagent(stage)

    ep, em = _effective_defaults()
    provider = (provider or ep).strip() or ep
    model = (model or em).strip() or em

    sess_off = resolve_no_session(no_session)
    try:
        cmd = build_pi_command(
            root,
            prompt=prompt,
            provider=provider,
            model=model,
            tools=tools,
            append_system_prompt=append_system_prompt,
            json_mode=json_mode,
            no_session=sess_off,
        )
    except RuntimeError as exc:
        return LeadResult(
            ok=False,
            stage=stage,
            slug=slug,
            log_path=str(log_path),
            exit_code=None,
            started_utc=started_utc,
            finished_utc=datetime.now(timezone.utc).isoformat(),
            duration_s=0.0,
            subagent_calls_detected=False,
            error=str(exc),
            cmd=[],
        )

    if dry_run:
        log_path.write_text(
            "DRY_RUN\n"
            + " ".join(cmd[:14])
            + " …\nprompt_len="
            + str(len(prompt))
            + f"\npi_session={'off' if sess_off else 'on'}\n"
            f"no_session_flag={sess_off}\n"
            f"sessions_root={pi_sessions_root()}\n",
            encoding="utf-8",
        )
        return LeadResult(
            ok=True,
            stage=stage,
            slug=slug,
            log_path=str(log_path),
            exit_code=0,
            started_utc=started_utc,
            finished_utc=datetime.now(timezone.utc).isoformat(),
            duration_s=0.0,
            subagent_calls_detected=False,
            cmd=cmd,
            error="dry_run",
        )

    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    # Prefer project agent dir for packages/settings
    env.setdefault("PI_CODING_AGENT_DIR", str(Path.home() / ".pi" / "agent"))
    # Windows: Pi/node may emit UTF-8; default text mode uses GBK and crashes reader threads.
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_s,
            shell=bool(cmd and str(cmd[0]).lower().endswith((".bat", ".cmd"))),
        )
        out = (proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or "")
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        # Timeout may still hold partial bytes; never assume GBK.
        partial_out = ""
        try:
            if exc.stdout:
                partial_out += exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode("utf-8", "replace")
            if exc.stderr:
                partial_out += "\n---STDERR---\n"
                partial_out += exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            partial_out = ""
        out = f"TIMEOUT after {timeout_s}s\n{exc}\n{partial_out}"
        exit_code = -9
    except Exception as exc:  # noqa: BLE001
        out = f"SPAWN_ERROR: {exc}"
        exit_code = -1

    header = (
        f"stage={stage}\nslug={slug}\nstarted={started_utc}\n"
        f"cmd={cmd[:12]!r}\nrequire_subagent_call={require_subagent_call}\n"
        f"tools={tools!r}\n"
        f"pi_session={'off' if sess_off else 'on'}\n"
        f"no_session_flag={sess_off}\n"
        f"sessions_root={pi_sessions_root()}\n"
        f"ORPATH_PI_SESSION={os.environ.get('ORPATH_PI_SESSION', '')!r}\n"
        f"---\n"
    )
    log_path.write_text(header + out, encoding="utf-8")
    hit, evidence = detect_subagent_calls(out)
    hit2, ev2 = detect_subagent_calls(log_path.read_text(encoding="utf-8", errors="ignore"))
    if hit2:
        hit = True
        evidence = list(dict.fromkeys(evidence + ev2))

    errs: list[str] = []
    if exit_code not in (0, None) and exit_code != 0:
        errs.append(f"lead exit_code={exit_code}")
    if require_subagent_call and not hit:
        errs.append("no subagent tool call detected in lead log")
    if expected_outputs:
        errs.extend(verify_outputs(expected_outputs, lead_start_ts=started - 5))

    finished = datetime.now(timezone.utc).isoformat()
    ok = not errs and (exit_code == 0)
    return LeadResult(
        ok=ok,
        stage=stage,
        slug=slug,
        log_path=str(log_path),
        exit_code=exit_code,
        started_utc=started_utc,
        finished_utc=finished,
        duration_s=round(time.time() - started, 3),
        subagent_calls_detected=hit,
        call_evidence=evidence[:12],
        cmd=cmd,
        error="; ".join(errs),
        stdout_tail=(out[-1500:] if out else ""),
        stderr_tail="",
    )


def lead_result_to_json(res: LeadResult) -> dict[str, Any]:
    d = asdict(res)
    # cmd may be huge with prompt — truncate last arg
    if d.get("cmd") and len(d["cmd"]) > 0:
        c = list(d["cmd"])
        if len(c[-1]) > 200:
            c[-1] = c[-1][:200] + "…"
        d["cmd"] = c
    return d


def write_lead_manifest(root: Path, slug: str, results: Iterable[LeadResult]) -> Path:
    path = root / "outputs" / ".agents" / slug / "lead-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "slug": slug,
        "utc": datetime.now(timezone.utc).isoformat(),
        "results": [lead_result_to_json(r) for r in results],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def sync_agents_to_user_dir(root: Path | None = None) -> list[str]:
    """Copy project .pi/agents/or-*.md into ~/.pi/agent/agents for global discovery."""
    root = project_root(root)
    src = agents_dir(root)
    dst = Path.home() / ".pi" / "agent" / "agents"
    dst.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for f in src.glob("or-*.md"):
        target = dst / f.name
        target.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
        copied.append(str(target))
    return copied
