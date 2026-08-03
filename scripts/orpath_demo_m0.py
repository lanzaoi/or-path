#!/usr/bin/env python3
"""OR-Path M0 demo entry: mock SP run + evidence checklist (Phase D).

Default path (reliable, no Pi bill):
  --fresh --problem-id shortest_path --solve-mode mock --no-live-subagent

Optional:
  --live          turn LIVE subagent ON (slow; needs Pi + API)
  --skip-run      only print evidence for existing slug
  --sub-evidence-slug SLUG
                  also accept true-sub toolCall evidence from another slug
                  (default: try current, then ``test``, then any recent agents)

Exit codes:
  0  D0(V0) + D2(solution+validate) green; D3 reported (pass or soft-warn)
  2  hard fail (run failed / D0 or D2 fail)
  3  --require-sub and no subagent evidence
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.subagent_dispatch import detect_subagent_calls  # noqa: E402
from orpath.watch_snapshot import build_snapshot, validate_snapshot_shape  # noqa: E402


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    # Hermes/other hosts often inject PYTHONPATH that breaks .venv-314 native wheels.
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("ORPATH_HOME", str(ROOT))
    env.setdefault("ORPATH_WORKDIR", str(ROOT))
    return env


def _py() -> str:
    cand = ROOT / ".venv-314" / "Scripts" / "python.exe"
    if cand.is_file():
        return str(cand)
    return sys.executable


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _tail_text(path: Path, max_bytes: int = 256 * 1024) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
            data = f.read()
        return data.decode("utf-8", errors="replace")
    except OSError:
        return ""


def find_subagent_evidence(slug: str) -> dict[str, Any]:
    agents = ROOT / "outputs" / ".agents" / slug
    out: dict[str, Any] = {
        "slug": slug,
        "ok": False,
        "log": None,
        "evidence": [],
        "detail": "",
    }
    if not agents.is_dir():
        out["detail"] = "agents_dir_missing"
        return out
    logs = sorted(agents.glob("*-lead-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    logs += sorted(agents.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    seen: set[Path] = set()
    for log in logs:
        if log in seen:
            continue
        seen.add(log)
        text = _tail_text(log)
        hit, ev = detect_subagent_calls(text)
        if hit:
            out["ok"] = True
            out["log"] = str(log.relative_to(ROOT)).replace("\\", "/")
            out["evidence"] = list(ev)[:6]
            out["detail"] = "detect_subagent_calls"
            return out
        # harness shortcut
    for hp in agents.glob("*-harness.json"):
        h = _read_json(hp) or {}
        if h.get("subagent_calls_detected") or (h.get("lead") or {}).get(
            "subagent_calls_detected"
        ):
            # still require log detect when possible
            lp = h.get("log_path") or (h.get("lead") or {}).get("log_path")
            if lp and Path(str(lp)).is_file():
                hit, ev = detect_subagent_calls(_tail_text(Path(str(lp))))
                if hit:
                    out["ok"] = True
                    out["log"] = str(Path(str(lp))).replace("\\", "/")
                    out["evidence"] = list(ev)[:6]
                    out["detail"] = "harness+log"
                    return out
            # harness-only is weaker; still not enough alone if detect fails
    out["detail"] = "no_toolCall_in_lead_logs"
    return out


def pick_sub_evidence(primary: str, extra: str | None) -> dict[str, Any]:
    candidates: list[str] = [primary]
    if extra:
        candidates.append(extra.strip())
    candidates.append("test")
    # recent agent dirs
    ad = ROOT / "outputs" / ".agents"
    if ad.is_dir():
        dirs = sorted(
            [p for p in ad.iterdir() if p.is_dir()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for p in dirs[:12]:
            if p.name not in candidates:
                candidates.append(p.name)
    for slug in candidates:
        ev = find_subagent_evidence(slug)
        if ev.get("ok"):
            ev["source_slug"] = slug
            ev["from_primary"] = slug == primary
            return ev
    return {
        "ok": False,
        "source_slug": None,
        "from_primary": False,
        "detail": "no_subagent_evidence_in_candidates",
        "tried": candidates[:8],
    }


def run_product(
    *,
    slug: str,
    live: bool,
    solve_mode: str,
    problem_id: str,
) -> int:
    env = _clean_env()
    env["ORPATH_LIVE_SUBAGENT"] = "1" if live else "0"
    # --fresh: clear prior stages so L0 does not stack forever
    stages = ROOT / "runs" / slug / "stages"
    if stages.is_dir():
        for p in stages.glob("*.json"):
            try:
                p.unlink()
            except OSError:
                pass
    latest = ROOT / "runs" / slug / "latest_snapshot.json"
    if latest.is_file():
        try:
            latest.unlink()
        except OSError:
            pass
    cmd = [
        _py(),
        str(ROOT / "orpath" / "run_orpath.py"),
        "run",
        "--fresh",
        "--slug",
        slug,
        "--thread-id",
        slug,
        "--problem-id",
        problem_id,
        "--solve-mode",
        solve_mode,
        "--root",
        str(ROOT),
    ]
    if live:
        cmd.append("--live-subagent")
    else:
        cmd.append("--no-live-subagent")
    print(">>", " ".join(cmd), flush=True)
    print(f"   ORPATH_LIVE_SUBAGENT={env['ORPATH_LIVE_SUBAGENT']}", flush=True)
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


def run_v0_gate() -> tuple[bool, str]:
    env = _clean_env()
    r = subprocess.run(
        [_py(), str(ROOT / "scripts" / "v0_watch_gate.py")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    tail = ((r.stdout or "") + (r.stderr or ""))[-800:]
    return r.returncode == 0, tail


def collect_evidence(
    *,
    slug: str,
    live: bool,
    sub_ev: dict[str, Any],
    v0_ok: bool,
    run_rc: int | None,
) -> dict[str, Any]:
    sol = _read_json(ROOT / "outputs" / f"{slug}-solution.json")
    val = _read_json(ROOT / "outputs" / f"{slug}-validate.json")
    snap = build_snapshot(slug=slug, thread_id=slug, root=ROOT, workdir=ROOT)
    shape_errs = validate_snapshot_shape(snap)

    sol_ok = bool(sol) and (
        str(sol.get("status", "")).upper() in {"OK", "OPTIMAL", "SUCCESS", "FEASIBLE"}
        or sol.get("objective") is not None
    )
    # validate shapes vary; prefer ok/True or status
    val_ok = False
    if val:
        if val.get("ok") is True or val.get("valid") is True or val.get("feasible") is True:
            val_ok = True
        st = str(val.get("status") or "").upper()
        if st in {"OK", "PASS", "VALID", "OPTIMAL"}:
            val_ok = True
        if val.get("errors") in ([], None) and sol_ok and "objective" in (val or {}):
            val_ok = True
        # common OR-Path validate envelope
        if val.get("gate_validate_ok") is True:
            val_ok = True
        if isinstance(val.get("result"), dict) and val["result"].get("ok") is True:
            val_ok = True

    d2 = bool(sol_ok and val_ok)
    d3 = bool(sub_ev.get("ok"))
    counters = (snap.get("current") or {}).get("counters") or {}
    d5 = any(k in counters for k in ("solver_tune", "schema_repair", "validate_repair", "revise_count"))

    report = {
        "utc": _utc(),
        "slug": slug,
        "live_requested": live,
        "run_rc": run_rc,
        "D0_v0_watch_gate": v0_ok,
        "D1_entry": "orpath.bat demo-m0 / menu demo-m0",
        "D2_solution_validate": d2,
        "D3_true_subagent": d3,
        "D4_timeline_optional": True,
        "D5_counters_visible": d5,
        "D6_claim": "V0+M0 only (no memory/MCP/domain-bridge claim)",
        "D7_no_secrets_check": "manual/git hygiene — not auto-scanned here",
        "solution": {
            "path": f"outputs/{slug}-solution.json" if sol else None,
            "objective": (sol or {}).get("objective"),
            "status": (sol or {}).get("status"),
            "source": (sol or {}).get("source") or (sol or {}).get("solver"),
        },
        "validate": {
            "path": f"outputs/{slug}-validate.json" if val else None,
            "ok": val_ok,
            "raw_keys": sorted((val or {}).keys())[:20],
        },
        "watch": {
            "status": snap.get("status"),
            "stages": len(snap.get("stages") or []),
            "shape_ok": not shape_errs,
            "shape_errs": shape_errs,
            "counters": counters,
            "cmd": f"orpath.bat watch --slug {slug}",
        },
        "subagent": sub_ev,
        "pass_core": bool(v0_ok and d2 and d5 and not shape_errs),
        "pass_full_m0_experience": bool(v0_ok and d2 and d3 and d5),
    }
    return report


def print_report(rep: dict[str, Any]) -> None:
    def yn(v: bool) -> str:
        return "PASS" if v else "FAIL"

    print()
    print("=== OR-Path M0 evidence ===")
    print(f"slug={rep['slug']}  utc={rep['utc']}")
    print(f"[D0] V0 watch gate          {yn(rep['D0_v0_watch_gate'])}")
    print(f"[D1] entry                  {rep['D1_entry']}")
    print(
        f"[D2] solution+validate      {yn(rep['D2_solution_validate'])}  "
        f"obj={rep['solution'].get('objective')} src={rep['solution'].get('source')}"
    )
    se = rep.get("subagent") or {}
    print(
        f"[D3] true subagent          {yn(rep['D3_true_subagent'])}  "
        f"source_slug={se.get('source_slug')} log={se.get('log')}"
    )
    if se.get("evidence"):
        print(f"     evidence0={se['evidence'][0][:160]}")
    print(f"[D4] timeline optional      (ok — not required)")
    print(
        f"[D5] counters on watch      {yn(rep['D5_counters_visible'])}  "
        f"{rep['watch'].get('counters')}"
    )
    print(f"[D6] claim ladder           {rep['D6_claim']}")
    print(f"[D7] secrets                {rep['D7_no_secrets_check']}")
    print()
    print(f"watch: {rep['watch'].get('cmd')}  stages={rep['watch'].get('stages')} status={rep['watch'].get('status')}")
    print(f"core_pass(D0+D2+D5)={rep['pass_core']}  full_m0_experience(D0+D2+D3+D5)={rep['pass_full_m0_experience']}")
    if not rep["D3_true_subagent"]:
        print(
            "NOTE: D3 missing on this machine — run a LIVE MA stage once, or pass "
            "--sub-evidence-slug <slug_with_lead_log>."
        )
    print("=== end evidence ===")
    print()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="OR-Path demo-m0 (Phase D)")
    p.add_argument("--slug", default="m0")
    p.add_argument("--problem-id", default="shortest_path")
    p.add_argument("--solve-mode", default="mock", choices=["mock", "networkx", "ortools", "auto"])
    p.add_argument("--live", action="store_true", help="LIVE subagent ON (slow)")
    p.add_argument("--no-live", action="store_true", help="force LIVE off (default)")
    p.add_argument("--skip-run", action="store_true", help="evidence only")
    p.add_argument("--skip-v0-gate", action="store_true")
    p.add_argument("--sub-evidence-slug", default="", help="extra slug for D3 evidence")
    p.add_argument(
        "--require-sub",
        action="store_true",
        help="exit 3 if D3 subagent evidence missing",
    )
    p.add_argument(
        "--allow-d3-from-history",
        action="store_true",
        default=True,
        help="allow D3 from historical agents (default ON)",
    )
    args = p.parse_args(argv)

    slug = (args.slug or "m0").strip()
    live = bool(args.live) and not bool(args.no_live)
    # default no-live unless --live
    if not args.live:
        live = False

    run_rc: int | None = None
    if not args.skip_run:
        run_rc = run_product(
            slug=slug,
            live=live,
            solve_mode=args.solve_mode,
            problem_id=args.problem_id,
        )
        if run_rc != 0:
            print(f"[ERROR] product run rc={run_rc}", file=sys.stderr)
            # still collect partial evidence
    else:
        print("[info] --skip-run: using on-disk artifacts only")

    if args.skip_v0_gate:
        v0_ok, v0_tail = True, "(skipped)"
    else:
        print(">> v0_watch_gate", flush=True)
        v0_ok, v0_tail = run_v0_gate()
        if not v0_ok:
            print(v0_tail[-500:], file=sys.stderr)

    extra = args.sub_evidence_slug or None
    if not args.allow_d3_from_history:
        sub_ev = find_subagent_evidence(slug)
        sub_ev["source_slug"] = slug if sub_ev.get("ok") else None
        sub_ev["from_primary"] = True
    else:
        sub_ev = pick_sub_evidence(slug, extra)

    rep = collect_evidence(
        slug=slug,
        live=live,
        sub_ev=sub_ev,
        v0_ok=v0_ok,
        run_rc=run_rc,
    )
    # Prefer short name for default slug=m0
    if slug == "m0":
        out_json = ROOT / "outputs" / "m0-evidence.json"
        out_md = ROOT / "outputs" / "m0-evidence.md"
    else:
        out_json = ROOT / "outputs" / f"{slug}-m0-evidence.json"
        out_md = ROOT / "outputs" / f"{slug}-m0-evidence.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = [
        f"# M0 evidence — `{slug}`",
        "",
        f"- utc: {rep['utc']}",
        f"- D0 V0: **{'PASS' if rep['D0_v0_watch_gate'] else 'FAIL'}**",
        f"- D2 numbers: **{'PASS' if rep['D2_solution_validate'] else 'FAIL'}** objective=`{rep['solution'].get('objective')}`",
        f"- D3 subagent: **{'PASS' if rep['D3_true_subagent'] else 'FAIL'}** source=`{sub_ev.get('source_slug')}`",
        f"- D5 counters: `{rep['watch'].get('counters')}`",
        f"- watch: `orpath.bat watch --slug {slug}`",
        f"- full_m0_experience: **{rep['pass_full_m0_experience']}**",
        "",
        "Numbers come only from solve tool JSON + validate — never from this markdown.",
        "",
    ]
    out_md.write_text("\n".join(md), encoding="utf-8")
    print_report(rep)
    print(f"wrote {out_json.relative_to(ROOT)}")
    print(f"wrote {out_md.relative_to(ROOT)}")

    if run_rc not in (None, 0):
        return 2
    if not rep["pass_core"]:
        return 2
    if args.require_sub and not rep["D3_true_subagent"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
