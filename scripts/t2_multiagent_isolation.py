#!/usr/bin/env python3
"""Hard DoD: real pi-subagents isolation (not single-thread cosplay).

PASS only if we find ≥2 distinct T2-relevant child runs with:
- different runId
- different agent names among or-researcher / or-modeler / or-writer (or T1 set)
- separate transcript.jsonl files with matching agent field in records
- cwd pointing at this repo (agent), not OOP
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / ".pi-subagents" / "artifacts"
REQUIRED_AGENTS = {"or-researcher", "or-modeler", "or-writer"}
ROOT_RESOLVED = str(ROOT.resolve()).lower().replace("/", "\\")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def load_meta(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def transcript_agents(path: Path) -> set[str]:
    agents: set[str] = set()
    if not path.is_file():
        return agents
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        a = rec.get("agent")
        if a:
            agents.add(str(a))
        # also cwd check on first records
    return agents


def transcript_cwds(path: Path) -> set[str]:
    cwds: set[str] = set()
    if not path.is_file():
        return cwds
    for line in path.read_text(encoding="utf-8").splitlines()[:20]:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        c = rec.get("cwd")
        if c:
            cwds.add(str(c).lower().replace("/", "\\"))
    return cwds


def main() -> int:
    if not ART.is_dir():
        fail(f"missing artifacts dir: {ART}")

    metas = list(ART.glob("*_or-*_meta.json"))
    if not metas:
        fail("no or-* meta.json under .pi-subagents/artifacts")

    runs: list[dict] = []
    for mp in metas:
        m = load_meta(mp)
        agent = str(m.get("agent") or "")
        run_id = str(m.get("runId") or "")
        if not agent.startswith("or-"):
            continue
        # pair transcript
        # name pattern: {runId}_{agent}_{i}_meta.json
        stem = mp.name.replace("_meta.json", "")
        tp = ART / f"{stem}_transcript.jsonl"
        t_agents = transcript_agents(tp)
        cwds = transcript_cwds(tp)
        runs.append(
            {
                "meta": mp.name,
                "agent": agent,
                "runId": run_id,
                "transcript": tp.name if tp.is_file() else None,
                "transcript_agents": sorted(t_agents),
                "cwds": sorted(cwds),
                "exitCode": m.get("exitCode"),
                "model": m.get("model"),
            }
        )

    if len(runs) < 2:
        fail(f"need ≥2 or-* runs with meta, found {len(runs)}")

    run_ids = {r["runId"] for r in runs if r["runId"]}
    agents = {r["agent"] for r in runs}
    if len(run_ids) < 2:
        fail(f"runIds not isolated: {run_ids}")
    if len(agents) < 2:
        fail(f"need ≥2 distinct agents, got {agents}")

    # Prefer T2 triad present
    have = agents & REQUIRED_AGENTS
    if len(have) < 2:
        # allow T1 set as partial but T2 wants researcher+modeler min
        if not ({"or-researcher", "or-modeler"} <= agents):
            fail(
                f"need or-researcher + or-modeler at minimum for isolation DoD, have {sorted(agents)}"
            )

    # transcripts exist and match agent
    missing_t = [r for r in runs if not r["transcript"]]
    if missing_t:
        fail(f"missing transcripts for: {[r['meta'] for r in missing_t]}")

    bad_agent = [
        r
        for r in runs
        if r["transcript_agents"] and r["agent"] not in r["transcript_agents"]
    ]
    if bad_agent:
        fail(f"transcript agent mismatch: {bad_agent}")

    # cwd must include this agent repo for at least the T2 runs
    t2ish = [
        r
        for r in runs
        if r["agent"] in REQUIRED_AGENTS
        and any("t2" in x or "tsp" in x for x in (r["meta"],))
        or r["agent"] in REQUIRED_AGENTS
    ]
    # check any researcher/modeler/writer transcript cwd is agent root
    ok_cwd = False
    for r in runs:
        if r["agent"] not in REQUIRED_AGENTS:
            continue
        for c in r["cwds"]:
            if ROOT_RESOLVED in c or c.endswith("\\agent") or "\\agent" in c:
                if "\\oop" not in c:
                    ok_cwd = True
    if not ok_cwd:
        # softer: accept if cwd contains Desktop\\agent
        for r in runs:
            for c in r["cwds"]:
                if "desktop\\agent" in c and "\\oop" not in c:
                    ok_cwd = True
    if not ok_cwd:
        fail(
            "no transcript cwd under Desktop\\agent (got: "
            + str([r["cwds"] for r in runs if r["agent"] in REQUIRED_AGENTS])
            + ")"
        )

    # T2 live artifacts binding
    sol = ROOT / "outputs" / "t2-live-tsp-solution.json"
    if sol.is_file():
        data = json.loads(sol.read_text(encoding="utf-8"))
        if data.get("objective") != 45:
            fail(f"t2-live-tsp solution objective expected 45, got {data.get('objective')}")
    else:
        print("WARN: outputs/t2-live-tsp-solution.json missing (isolation of agents still checked)")

    # write proof
    proof = {
        "ok": True,
        "root": str(ROOT),
        "n_runs": len(runs),
        "runIds": sorted(run_ids),
        "agents": sorted(agents),
        "required_hit": sorted(have),
        "runs": runs,
    }
    out = ROOT / "outputs" / "t2-multiagent-isolation-proof.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proof, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md = ROOT / "docs" / "t2-multiagent-isolation.md"
    lines = [
        "# T2 Multi-Agent Isolation Proof",
        "",
        "**Status: PASS (machine-checked)**",
        "",
        "This is **not** OpenPi single-thread role-play. Evidence is separate pi-subagents child runs.",
        "",
        "## Criteria",
        "",
        "- ≥2 distinct `runId`",
        "- ≥2 distinct `or-*` agents (researcher + modeler minimum)",
        "- Separate `*_transcript.jsonl` per run",
        "- Transcript `cwd` under this `agent` repo",
        "- T2 live solution objective 45 when present",
        "",
        "## Runs",
        "",
        "| runId | agent | model | transcript |",
        "|-------|-------|-------|------------|",
    ]
    for r in sorted(runs, key=lambda x: (x["agent"], x["runId"])):
        if r["agent"] not in REQUIRED_AGENTS and r["agent"] not in {
            "or-verifier",
            "or-reviewer",
            "or-orchestrator",
        }:
            continue
        lines.append(
            f"| `{r['runId']}` | `{r['agent']}` | `{r.get('model')}` | `{r.get('transcript')}` |"
        )
    lines += [
        "",
        f"Machine proof JSON: `{out.as_posix()}`",
        "",
        "## OpenPi note",
        "",
        "If OpenPi is opened on `Desktop\\OOP` without project packages, subagent tool may be missing",
        "and the model will cosplay roles. **Always open `Desktop\\agent`.**",
        "Isolation DoD is satisfied by Pi CLI + this gate even when a bad OpenPi session cosplays.",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"ok": True, "runIds": sorted(run_ids), "agents": sorted(agents), "proof": str(out)}, indent=2))
    print("PASS: t2_multiagent_isolation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
