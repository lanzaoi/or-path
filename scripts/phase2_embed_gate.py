#!/usr/bin/env python3
"""Phase 2 gate: embed_mode live|stub dual-track for hybrid retrieve/ingest."""
from __future__ import annotations

import json
import os
import subprocess
import sys
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

    def need(c: bool, msg: str) -> None:
        print(("PASS " if c else "FAIL ") + msg)
        if not c:
            fails.append(msg)

    bat = (ROOT / "orpath.bat").read_text(encoding="utf-8", errors="replace")
    sh = (ROOT / "orpath.sh").read_text(encoding="utf-8", errors="replace")
    need("phase2-embed-gate" in bat or "phase2_embed_gate" in bat, "bat phase2")
    need("phase2-embed-gate" in sh or "phase2_embed" in sh, "sh phase2")

    sys.path.insert(0, str(ROOT))
    from knowledge_svc.embed_siliconflow import get_api_key, resolve_embed_mode

    # --- stub track (always hard) ---
    env_stub = {
        k: v
        for k, v in os.environ.items()
        if k not in ("PYTHONPATH", "PYTHONHOME", "ORPATH_KNOWLEDGE_EMBED")
    }
    env_stub["PYTHONNOUSERSITE"] = "1"
    env_stub["ORPATH_KNOWLEDGE_EMBED"] = "stub"

    r = subprocess.run(
        [str(py), "-m", "knowledge_svc.ingest", "--clear", "--embed-mode", "stub"],
        cwd=str(ROOT),
        env=env_stub,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    need(r.returncode == 0, f"ingest stub rc0 {r.returncode}")
    try:
        ing = json.loads(r.stdout)
    except json.JSONDecodeError:
        ing = {}
        need(False, "ingest stub json")
    need(ing.get("embed_mode") == "stub", f"ingest embed_mode stub got {ing.get('embed_mode')}")
    need(int(ing.get("n_chunks") or 0) >= 1, "ingest n_chunks")

    r2 = subprocess.run(
        [
            str(py),
            "-m",
            "knowledge_svc.retrieve",
            "--query",
            "shortest path Dijkstra networkx",
            "--mode",
            "hybrid",
            "--topk",
            "5",
            "--embed-mode",
            "stub",
        ],
        cwd=str(ROOT),
        env=env_stub,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    need(r2.returncode == 0, "retrieve stub rc0")
    try:
        art = json.loads(r2.stdout)
    except json.JSONDecodeError:
        i = (r2.stdout or "").find("{")
        art = json.loads(r2.stdout[i:]) if i >= 0 else {}
    need(art.get("embed_mode") == "stub", f"retrieve embed_mode stub got {art.get('embed_mode')}")
    need(isinstance(art.get("hits"), list) and len(art["hits"]) >= 1, "stub hits>=1")
    need(art.get("knowledge_mode") == "hybrid", "hybrid mode")

    # auto resolve
    mode_a, meta_a = resolve_embed_mode("auto")
    need(mode_a in ("live", "stub"), f"auto resolve {mode_a}")
    need("has_api_key" in meta_a, "auto meta")

    # --- live track ---
    key = get_api_key()
    if not key:
        print("SKIP live embed track: SILICONFLOW_API_KEY not set")
        need(True, "live track soft-skip without key")
    else:
        env_live = dict(env_stub)
        env_live["ORPATH_KNOWLEDGE_EMBED"] = "live"
        # keep API key from environ
        if "SILICONFLOW_API_KEY" in os.environ:
            env_live["SILICONFLOW_API_KEY"] = os.environ["SILICONFLOW_API_KEY"]
        if "SF_API_KEY" in os.environ:
            env_live["SF_API_KEY"] = os.environ["SF_API_KEY"]

        r3 = subprocess.run(
            [str(py), "-m", "knowledge_svc.ingest", "--clear", "--embed-mode", "live"],
            cwd=str(ROOT),
            env=env_live,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        print((r3.stdout or "")[-400:])
        if r3.returncode != 0:
            print((r3.stderr or "")[-400:])
            # soft: live API flaky → warn but do not fail whole gate if stub already green?
            # Plan: live with key must pass. Fail hard.
            need(False, f"ingest live rc0 {r3.returncode}")
        else:
            try:
                ing_l = json.loads(r3.stdout)
            except json.JSONDecodeError:
                ing_l = {}
            need(ing_l.get("embed_mode") == "live", f"ingest live mode {ing_l.get('embed_mode')}")
            r4 = subprocess.run(
                [
                    str(py),
                    "-m",
                    "knowledge_svc.retrieve",
                    "--query",
                    "CVRP capacity multi vehicle",
                    "--mode",
                    "hybrid",
                    "--topk",
                    "5",
                    "--embed-mode",
                    "live",
                ],
                cwd=str(ROOT),
                env=env_live,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            need(r4.returncode == 0, "retrieve live rc0")
            try:
                art_l = json.loads(r4.stdout)
            except json.JSONDecodeError:
                i = (r4.stdout or "").find("{")
                art_l = json.loads(r4.stdout[i:]) if i >= 0 else {}
            need(art_l.get("embed_mode") == "live", f"retrieve live mode {art_l.get('embed_mode')}")
            need(len(art_l.get("hits") or []) >= 1, "live hits>=1")
            # secret: full key not in stdout
            need(key not in (r3.stdout or "") + (r4.stdout or ""), "no full api key in output")

    # leave indexes in stub-friendly state for other gates
    subprocess.run(
        [str(py), "-m", "knowledge_svc.ingest", "--clear", "--embed-mode", "stub"],
        cwd=str(ROOT),
        env=env_stub,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )

    # docs pointer
    need(
        "ORPATH_KNOWLEDGE_EMBED" in (ROOT / "ORPATH.md").read_text(encoding="utf-8", errors="replace")
        or "embed_mode" in (ROOT / "ORPATH.md").read_text(encoding="utf-8", errors="replace"),
        "ORPATH mentions embed",
    )

    if fails:
        print("FAIL phase2_embed_gate", fails)
        return 1
    print("PASS phase2_embed_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
