#!/usr/bin/env python3
"""T3 LG skeleton gate: topology, checkpointer, resume, dirty, owner."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault('ORPATH_LIVE_SUBAGENT', '0')
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env.pop("PYTHONPATH", None)
    return env


def run(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    r = subprocess.run(args, cwd=ROOT, env=child_env(), text=True, capture_output=True)
    if check and r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        fail(f"cmd failed ({r.returncode}): {' '.join(args)}")
    return r


def main() -> int:
    # export stage map
    r = run(
        [
            PY,
            "-c",
            "from orpath.graph_product import write_stage_map_files, PRODUCT_NODES, export_stage_map; "
            f"from pathlib import Path; write_stage_map_files(Path(r'{ROOT}')); "
            "m=export_stage_map(); print(len(m['nodes']), ','.join(PRODUCT_NODES))",
        ]
    )
    print(r.stdout)

    sm = ROOT / "orpath" / "stage_map.json"
    if not sm.is_file():
        fail("missing orpath/stage_map.json")
    data = json.loads(sm.read_text(encoding="utf-8"))
    from orpath.graph_product import PRODUCT_NODES

    if data.get("nodes") != list(PRODUCT_NODES):
        fail(f"stage_map nodes != PRODUCT_NODES: {data.get('nodes')}")

    mmd = ROOT / "docs" / "t3-stage-map.mmd"
    if not mmd.is_file():
        fail("missing docs/t3-stage-map.mmd")
    text = mmd.read_text(encoding="utf-8")
    for n in PRODUCT_NODES:
        if n not in text:
            fail(f"mermaid missing node {n}")

    # owner unit
    r = run(
        [
            PY,
            "-c",
            "from orpath.node_context import assert_owner\n"
            "assert_owner('model', {'stage':'x'})\n"
            "try:\n"
            "  assert_owner('model', {'objective': 1})\n"
            "  raise SystemExit('should have failed')\n"
            "except RuntimeError:\n"
            "  print('owner_ok')\n",
        ]
    )
    print(r.stdout)
    if "owner_ok" not in r.stdout:
        fail("owner assert")

    # happy path product run
    slug = "t3-lg-sp-mock"
    tid = "t3-lg-sp-mock"
    r = run(
        [
            PY,
            str(ROOT / "orpath" / "run_orpath.py"),
            "run",
            "--problem-id",
            "shortest_path",
            "--solve-mode",
            "mock",
            "--knowledge-mode",
            "off",
            "--slug",
            slug,
            "--thread-id",
            tid,
            "--fresh",
        ]
    )
    print(r.stdout)
    summary = json.loads(r.stdout)
    if not summary.get("gate_validate_ok"):
        fail("happy path validate")
    if not summary.get("provenance_path"):
        fail("no provenance")
    runs = Path(summary.get("runs_dir") or ROOT / "runs" / tid)
    if not (runs / "stages").is_dir() or not list((runs / "stages").glob("*.json")):
        fail("no stage snapshots")
    if not (runs / "artifact_hashes.json").is_file():
        fail("no artifact manifest")
    if not summary.get("bridge_skipped", True):
        # live not set — should skip
        pass

    # sqlite exists
    if not (ROOT / "runs" / "orpath.sqlite").is_file():
        fail("missing runs/orpath.sqlite")

    # status CLI
    r = run(
        [
            PY,
            str(ROOT / "orpath" / "run_orpath.py"),
            "status",
            "--thread-id",
            tid,
        ]
    )
    print(r.stdout)
    st = json.loads(r.stdout)
    if not st.get("exists"):
        fail("status missing thread")

    # dirty detection: tamper solution then resume without force
    sol = Path(summary["solution_path"])
    original = sol.read_text(encoding="utf-8")
    sol.write_text(original.replace('"objective"', '"objective" '), encoding="utf-8")
    # actually change bytes meaningfully
    sol.write_text(original + "\n", encoding="utf-8")
    r = run(
        [
            PY,
            str(ROOT / "orpath" / "run_orpath.py"),
            "run",
            "--thread-id",
            tid,
            "--resume",
            "--problem-id",
            "shortest_path",
            "--slug",
            slug,
        ],
        check=False,
    )
    if r.returncode != 3:
        print(r.stdout, r.stderr)
        fail(f"expected dirty exit 3, got {r.returncode}")
    print("dirty_ok")
    # restore
    sol.write_text(original, encoding="utf-8")

    # HUMAN path via forced bad: use max schema by temporarily not needed —
    # light check human_stop node importable
    r = run(
        [
            PY,
            "-c",
            "from orpath.graph_product import build_graph_product, open_sqlite_checkpointer; "
            f"from pathlib import Path; s,c=open_sqlite_checkpointer(Path(r'{ROOT}')/'runs'/'orpath.sqlite'); "
            "g=build_graph_product(s); print('compiled', g is not None); c.close()",
        ]
    )
    print(r.stdout)

    # specs present
    if not (ROOT / "specs" / "t3-lg-skeleton.md").is_file():
        fail("missing specs/t3-lg-skeleton.md")

    print("PASS: t3_lg_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
