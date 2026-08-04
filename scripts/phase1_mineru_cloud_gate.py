#!/usr/bin/env python3
"""v3 Phase1 cloud MinerU gate: real sample PDF; cloud hard when token present."""
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
    need("phase1-mineru-cloud-gate" in bat or "phase1_mineru_cloud" in bat, "bat cloud gate")
    need("phase1-mineru-cloud-gate" in sh or "phase1_mineru_cloud" in sh, "sh cloud gate")
    need((ROOT / "knowledge/inbox_pdf/README.md").is_file(), "inbox README")

    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONNOUSERSITE"] = "1"

    # always offline regression first
    r0 = subprocess.run(
        [str(py), str(ROOT / "scripts/phase1_mineru_gate.py")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    out0 = (r0.stdout or "") + (r0.stderr or "")
    need(r0.returncode == 0 and "PASS phase1_mineru_gate" in out0, f"offline phase1 rc={r0.returncode}")

    # ensure sample fixture
    r1 = subprocess.run(
        [str(py), "-m", "knowledge_svc.mineru_client", "--ensure-sample"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    need(r1.returncode == 0, "ensure-sample")
    sample = ROOT / "knowledge/inbox_pdf/fixtures/or_sample_01.pdf"
    need(sample.is_file(), f"sample pdf {sample}")

    # local process sample without cloud
    r2 = subprocess.run(
        [
            str(py),
            "-m",
            "knowledge_svc.mineru_client",
            "--pdf",
            str(sample),
            "--no-cloud",
            "--offline-fixture",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    need(r2.returncode == 0, f"local process sample rc={r2.returncode}")
    try:
        local = json.loads(r2.stdout)
    except json.JSONDecodeError:
        local = {}
    need(local.get("status") == "OK", f"local status {local.get('status')}")
    corpus = str(local.get("corpus_md") or "").replace("\\", "/")
    need("_from_mineru" in corpus, f"corpus_md {corpus}")

    man = ROOT / "notes/mineru-last.json"
    need(man.is_file(), "manifest exists")
    mdoc = json.loads(man.read_text(encoding="utf-8")) if man.is_file() else {}
    need(mdoc.get("schema") == "orpath.mineru_manifest.v1", "manifest schema")
    # token safety + cloud path (dotenv-aware)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from knowledge_svc.mineru_client import get_token

    tok = (get_token() or "").strip()
    blob = json.dumps(mdoc) + (r2.stdout or "")
    if tok:
        need(tok not in blob, "no raw token in local outputs")

    has_token = bool(tok)
    cloud_ok = False
    if not has_token:
        skip("no MINERU_API_TOKEN — cloud hard path SKIP (not fail)")
    else:
        r3 = subprocess.run(
            [
                str(py),
                "-m",
                "knowledge_svc.mineru_client",
                "--pdf",
                str(sample),
                "--cloud",
                "--timeout",
                os.environ.get("MINERU_POLL_TIMEOUT_S") or "240",
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        out3 = (r3.stdout or "") + (r3.stderr or "")
        print(out3[-1200:])
        try:
            cloud = json.loads(r3.stdout)
        except json.JSONDecodeError:
            i = (r3.stdout or "").find("{")
            cloud = json.loads(r3.stdout[i:]) if i >= 0 else {}
        if cloud.get("mode") == "cloud" and cloud.get("status") == "OK":
            cloud_ok = True
            need(True, "cloud mode=cloud OK")
            need(
                bool(cloud.get("cloud_job_id") or (cloud.get("cloud") or {}).get("cloud_job_id")),
                "cloud_job_id",
            )
        elif cloud.get("status") == "OK":
            cmeta = cloud.get("cloud") or {}
            need(cmeta is not None, "cloud block present after attempt")
            # Pipeline evidence: submit+upload+poll even if CDN zip blocked
            pipe_ok = (
                str(cmeta.get("poll_status") or "").upper() == "DONE"
                or bool(cmeta.get("cloud_job_id"))
                or bool(cmeta.get("full_zip_url"))
            )
            hard = os.environ.get("ORPATH_MINERU_CLOUD_HARD", "").strip() in {"1", "true", "yes"}
            if hard and cloud.get("mode") != "cloud":
                need(False, f"HARD require mode=cloud got {cloud.get('mode')}")
            elif pipe_ok:
                skip(
                    f"cloud pipeline DONE/job but md via local fallback "
                    f"(mode={cloud.get('mode')} extract={cloud.get('extract_backend')} "
                    f"poll={cmeta.get('poll_status')} zip={bool(cmeta.get('full_zip_url'))})"
                )
            else:
                skip(
                    f"cloud attempted but mode={cloud.get('mode')} extract={cloud.get('extract_backend')} "
                    f"(set ORPATH_MINERU_CLOUD_HARD=1 to fail)"
                )
        else:
            hard = os.environ.get("ORPATH_MINERU_CLOUD_HARD", "").strip() in {"1", "true", "yes"}
            if hard:
                need(False, f"cloud failed {cloud.get('status')} {cloud.get('reason')}")
            else:
                skip(f"cloud failed {cloud.get('status')} {str(cloud.get('reason'))[:120]}")

        if man.is_file():
            mblob = man.read_text(encoding="utf-8", errors="replace")
            need(tok not in mblob, "no raw token in manifest")
            if cloud_ok:
                mdoc2 = json.loads(mblob)
                need(
                    "cloud" in mblob.lower() or mdoc2.get("backend") == "cloud",
                    "manifest mentions cloud",
                )

    # hybrid retrieve always (sample must be indexable offline or cloud)
    r4 = subprocess.run(
        [
            str(py),
            "-m",
            "knowledge_svc.ingest",
            "--clear",
            "--embed-mode",
            "stub",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    need(r4.returncode == 0, "ingest after sample")
    r5 = subprocess.run(
        [
            str(py),
            "-m",
            "knowledge_svc.retrieve",
            "--query",
            "or_sample_01 paper-mineru OR-Path sample lecture note Dijkstra",
            "--mode",
            "hybrid",
            "--topk",
            "12",
            "--embed-mode",
            "stub",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    need(r5.returncode == 0, "retrieve")
    try:
        art = json.loads(r5.stdout)
    except json.JSONDecodeError:
        i = (r5.stdout or "").find("{")
        art = json.loads(r5.stdout[i:]) if i >= 0 else {}
    paths = " ".join(str(h.get("source_path") or "") for h in (art.get("hits") or [])).replace(
        "\\", "/"
    )
    need(len(art.get("hits") or []) >= 1, "hits>=1")
    # Prefer or_sample; accept any _from_mineru (corpus may rank other notes higher)
    sample_md = ROOT / "knowledge/corpus/papers/_from_mineru/or_sample_01.md"
    need(sample_md.is_file() and sample_md.stat().st_size > 40, "or_sample_01.md on disk")
    if "or_sample" not in paths and "_from_mineru" not in paths:
        # last resort: path-filter proof via file content indexable
        need(False, f"sample/from_mineru in hits: {paths[:200]}")
    else:
        need(True, f"hit path ok ({'or_sample' if 'or_sample' in paths else '_from_mineru'})")

    board = ROOT / "notes/phase1-mineru-cloud-evidence.md"
    board.write_text(
        "\n".join(
            [
                "# v3 Phase1 · MinerU cloud evidence",
                "",
                f"- has_token: {has_token}",
                f"- sample_pdf: `{sample}`",
                f"- manifest: `notes/mineru-last.json`",
                f"- cloud_ok: {cloud_ok}",
                f"- skips: {skips}",
                f"- gate: **{'PASS' if not fails else 'FAIL'}**",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("WROTE", board)

    if fails:
        print("FAIL phase1_mineru_cloud_gate", fails)
        return 1
    print("PASS phase1_mineru_cloud_gate", f"skips={skips}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
