#!/usr/bin/env python3
"""v3 Phase3 gate: research profile live default + incremental ingest skip."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    os.environ.setdefault("PYTHONNOUSERSITE", "1")
    os.environ.pop("PYTHONPATH", None)
    os.environ.pop("PYTHONHOME", None)

    py = ROOT / ".venv-314" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    fails: list[str] = []
    skips: list[str] = []

    def need(c: bool, msg: str) -> None:
        print(("PASS " if c else "FAIL ") + msg)
        if not c:
            fails.append(msg)

    def skip(msg: str) -> None:
        print("SKIP " + msg)
        skips.append(msg)

    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    sh = (ROOT / "orpath.sh").read_text(encoding="utf-8", errors="replace")
    need("phase3-live-default-gate" in bat or "phase3_live_default" in bat, "bat phase3-live")
    need("phase3-live-default-gate" in sh or "phase3_live_default" in sh, "sh phase3-live")

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from knowledge_svc.embed_siliconflow import get_api_key, resolve_embed_mode, resolve_knowledge_profile

    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONNOUSERSITE"] = "1"

    # --- stub path always ---
    env_stub = dict(env)
    env_stub["ORPATH_KNOWLEDGE_EMBED"] = "stub"
    env_stub["ORPATH_KNOWLEDGE_PROFILE"] = "demo"

    r0 = subprocess.run(
        [str(py), "-m", "knowledge_svc.ingest", "--clear", "--embed-mode", "stub", "--profile", "demo"],
        cwd=str(ROOT),
        env=env_stub,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    need(r0.returncode == 0, f"stub ingest clear rc={r0.returncode}")
    try:
        ing0 = json.loads(r0.stdout)
    except json.JSONDecodeError:
        ing0 = {}
    need(int(ing0.get("n_chunks") or 0) >= 1, f"stub n_chunks {ing0.get('n_chunks')}")
    need(ing0.get("embed_mode") == "stub", f"stub embed_mode {ing0.get('embed_mode')}")
    need(bool(ing0.get("index_fingerprint")), "index_fingerprint after full ingest")
    fp1 = ing0.get("index_fingerprint")

    t1 = time.perf_counter()
    r1 = subprocess.run(
        [str(py), "-m", "knowledge_svc.ingest", "--embed-mode", "stub", "--profile", "demo"],
        cwd=str(ROOT),
        env=env_stub,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    elapsed_skip = time.perf_counter() - t1
    need(r1.returncode == 0, f"incremental ingest rc={r1.returncode}")
    try:
        ing1 = json.loads(r1.stdout)
    except json.JSONDecodeError:
        ing1 = {}
    need(bool(ing1.get("skipped")) or int(ing1.get("n_skipped_files") or 0) > 0, f"incremental skip {ing1}")
    need(ing1.get("index_fingerprint") == fp1, "fingerprint stable")
    need(elapsed_skip < 30.0, f"incremental fast-ish elapsed={elapsed_skip:.2f}s")
    print(f"INFO incremental elapsed={elapsed_skip:.3f}s skipped={ing1.get('skipped')} n_skipped={ing1.get('n_skipped_files')}")

    r2_out = ROOT / "notes" / "_phase3_stub_retrieve.json"
    r2 = subprocess.run(
        [
            str(py),
            "-m",
            "knowledge_svc.retrieve",
            "--query",
            "shortest path Dijkstra",
            "--mode",
            "hybrid",
            "--topk",
            "3",
            "--embed-mode",
            "stub",
            "--profile",
            "demo",
            "--out",
            str(r2_out),
        ],
        cwd=str(ROOT),
        env=env_stub,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    need(r2.returncode == 0, f"stub retrieve rc={r2.returncode} {(r2.stderr or '')[:200]}")
    art = {}
    if r2_out.is_file():
        art = json.loads(r2_out.read_text(encoding="utf-8"))
    else:
        try:
            art = json.loads(r2.stdout)
        except json.JSONDecodeError:
            art = {}
    need(art.get("embed_mode") == "stub", f"retrieve stub {art.get('embed_mode')}")
    need(len(art.get("hits") or []) >= 1, "stub hits")
    if art.get("index_fingerprint"):
        need(art.get("index_fingerprint") == fp1, "retrieve fingerprint")

    # unit resolve profile
    prof, _ = resolve_knowledge_profile("research")
    need(prof == "research", "resolve research profile")
    mode_r, meta_r = resolve_embed_mode(None, profile="research")
    need(mode_r in {"live", "stub"}, f"research resolve mode {mode_r}")

    # --- live / research (no full-corpus live re-embed: too slow for gate) ---
    has_key = bool(get_api_key())
    if not has_key:
        skip("no SILICONFLOW_API_KEY — live research path SKIP")
    else:
        env_live = dict(env)
        env_live["ORPATH_KNOWLEDGE_PROFILE"] = "research"
        env_live["ORPATH_KNOWLEDGE_EMBED"] = "auto"
        # Resolve path honesty
        mode_live, meta_live = resolve_embed_mode("auto", profile="research")
        need(mode_live == "live", f"research+auto resolves live got {mode_live} {meta_live}")

        r4_out = ROOT / "notes" / "_phase3_live_retrieve.json"
        r4 = subprocess.run(
            [
                str(py),
                "-m",
                "knowledge_svc.retrieve",
                "--query",
                "CVRP capacity routing",
                "--mode",
                "hybrid",
                "--topk",
                "3",
                "--profile",
                "research",
                "--embed-mode",
                "auto",
                "--out",
                str(r4_out),
            ],
            cwd=str(ROOT),
            env=env_live,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        need(r4.returncode == 0, f"live retrieve rc={r4.returncode} {(r4.stderr or '')[:200]}")
        art4 = {}
        if r4_out.is_file():
            art4 = json.loads(r4_out.read_text(encoding="utf-8"))
        else:
            try:
                art4 = json.loads(r4.stdout)
            except json.JSONDecodeError:
                art4 = {}
        need(art4.get("embed_mode") == "live", f"retrieve live {art4.get('embed_mode')}")
        need(len(art4.get("hits") or []) >= 1, "live hits")
        need(art4.get("profile") == "research" or (art4.get("embed_meta") or {}).get("profile") == "research", "retrieve profile research")

        # tiny live ingest smoke (single-file corpus dir) — proves live ingest path
        tiny = ROOT / "knowledge" / "_phase3_tiny_corpus"
        tiny.mkdir(parents=True, exist_ok=True)
        (tiny / "tiny_live_note.md").write_text(
            "# Tiny live embed note\n\n- kind: paper-note\n- title: Tiny live embed note\n- source: gate\n\nShortest path Dijkstra CVRP capacity for live ingest smoke.\n",
            encoding="utf-8",
        )
        r3 = subprocess.run(
            [
                str(py),
                "-m",
                "knowledge_svc.ingest",
                "--corpus",
                str(tiny),
                "--clear",
                "--profile",
                "research",
                "--embed-mode",
                "live",
                "--no-incremental",
            ],
            cwd=str(ROOT),
            env=env_live,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        need(r3.returncode == 0, f"tiny live ingest rc={r3.returncode} {(r3.stderr or '')[:200]}")
        try:
            ing3 = json.loads(r3.stdout)
        except json.JSONDecodeError:
            ing3 = {}
        need(ing3.get("embed_mode") == "live", f"tiny live embed_mode {ing3.get('embed_mode')}")
        need(int(ing3.get("n_chunks") or 0) >= 1, "tiny live chunks")

        # restore main stub index for other gates
        subprocess.run(
            [str(py), "-m", "knowledge_svc.ingest", "--clear", "--embed-mode", "stub", "--no-incremental"],
            cwd=str(ROOT),
            env=env_stub,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )

    board = ROOT / "notes/phase3-live-default-evidence.md"
    board.write_text(
        "\n".join(
            [
                "# v3 Phase3 · live default + incremental evidence",
                "",
                f"- has_siliconflow_key: {has_key}",
                f"- stub_fingerprint: `{fp1}`",
                f"- incremental_skipped: {ing1.get('skipped')}",
                f"- incremental_elapsed_s: {elapsed_skip:.3f}",
                f"- skips: {skips}",
                f"- gate: **{'PASS' if not fails else 'FAIL'}**",
                "",
                "## Env",
                "",
                "- `ORPATH_KNOWLEDGE_PROFILE=demo|research`",
                "- `ORPATH_KNOWLEDGE_EMBED=auto|live|stub`",
                "- research + auto → live when key present",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("WROTE", board)

    if fails:
        print("FAIL phase3_live_default_gate", fails)
        return 1
    print("PASS phase3_live_default_gate", f"skips={skips}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
