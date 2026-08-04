#!/usr/bin/env python3
"""Run fixed hybrid queries from knowledge/eval_queries.md (or built-in table).

Smoke only — not BEIR/MS MARCO. Prints hit summary JSON; exit 1 if any miss.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Fallback if markdown table parse fails
DEFAULT_QUERIES: list[tuple[str, str, str]] = [
    ("1", "shortest path Dijkstra networkx", "sp_networkx|dijkstra"),
    ("2", "TSP tour OR-Tools routing n=8", "tsp_"),
    ("3", "CVRP capacity multi vehicle routing", "cvrp|vrp"),
    ("4", "polyomino cover CP-SAT schema", "polyomino"),
    ("5", "objective only from solve validate", "numbers_truth|skill-or-numbers|validate_recompute"),
    ("6", "HiGHS LP MIP solver", "highs"),
    ("7", "CP-SAT circuit modeling", "cpsat|circuit"),
    ("8", "time window VRPTW stub", "vrptw|time_window|time window"),
    ("9", "schema forbid objective routes", "modeling_checklist|schema"),
    ("10", "retrieval.json research hybrid", "research_retrieval|retrieval"),
    ("11", "lesson polyomino process memory", "lesson|polyomino"),
    ("12", "skill solver select problem class", "skill-or-solver|solver_select"),
]


def parse_eval_md(path: Path) -> list[tuple[str, str, str]]:
    if not path.is_file():
        return list(DEFAULT_QUERIES)
    rows: list[tuple[str, str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 3:
            continue
        if parts[0] in {"#", "---"} or parts[0].startswith("-"):
            continue
        if not parts[0].isdigit():
            continue
        num, q = parts[0], parts[1]
        hint = parts[3] if len(parts) > 3 else ""
        # convert "a / b" style hints to regex
        hint_re = "|".join(
            re.escape(h.strip()).replace("\\ ", " ")
            for h in re.split(r"[|/]", hint)
            if h.strip() and h.strip() != "—"
        )
        if not hint_re:
            hint_re = "knowledge"
        rows.append((num, q, hint_re.replace("\\ ", " ")))
    return rows or list(DEFAULT_QUERIES)


def retrieve(py: Path, query: str, mode: str, topk: int) -> dict:
    r = subprocess.run(
        [
            str(py),
            "-m",
            "knowledge_svc.retrieve",
            "--query",
            query,
            "--mode",
            mode,
            "--topk",
            str(topk),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        return {"error": (r.stderr or r.stdout)[:400], "hits": []}
    out = r.stdout
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        i = out.find("{")
        if i >= 0:
            return json.loads(out[i:])
        return {"error": "bad_json", "hits": []}


def main(argv: list[str] | None = None) -> int:
    os.environ.setdefault("PYTHONNOUSERSITE", "1")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", default="hybrid", choices=("hybrid", "seed", "off"))
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument(
        "--eval-md",
        type=Path,
        default=ROOT / "knowledge" / "eval_queries.md",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "notes" / "knowledge-eval-last.json",
    )
    ap.add_argument(
        "--strict-theme",
        action="store_true",
        help="Require hint regex match (default: hits>=1 + corpus path only)",
    )
    args = ap.parse_args(argv)

    py = ROOT / ".venv-314" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    queries = parse_eval_md(args.eval_md)
    results = []
    fails: list[str] = []

    for num, q, hint_re in queries:
        art = retrieve(py, q, args.mode, args.topk)
        hits = art.get("hits") or []
        paths = [str(h.get("source_path") or "").replace("\\", "/") for h in hits]
        blob = " ".join(paths + [str(h.get("chunk_id") or "") for h in hits]).lower()
        ok_hits = len(hits) >= 1
        ok_hint = bool(re.search(hint_re, blob, re.I)) if hint_re else True
        ok_corpus = any("knowledge/corpus" in p for p in paths) or any(
            "seed_graph" in p for p in paths
        )
        # Default product smoke: retrieval works on corpus. Theme is soft unless --strict-theme.
        row_ok = ok_hits and ok_corpus and (ok_hint if args.strict_theme else True)
        soft_theme = ok_hint
        if not row_ok:
            fails.append(num)
        results.append(
            {
                "id": num,
                "query": q,
                "hint_re": hint_re,
                "n_hits": len(hits),
                "top_path": paths[0] if paths else "",
                "top_chunk": (hits[0].get("chunk_id") if hits else ""),
                "theme_ok": soft_theme,
                "ok": row_ok,
            }
        )
        status = "OK" if row_ok else "MISS"
        theme = "theme+" if soft_theme else "theme-"
        print(f"[{status}/{theme}] #{num} hits={len(hits)} top={paths[0] if paths else None}")

    summary = {
        "mode": args.mode,
        "n_queries": len(queries),
        "n_ok": sum(1 for r in results if r["ok"]),
        "n_fail": len(fails),
        "fail_ids": fails,
        "results": results,
        "note": "Product smoke only — not public IR benchmark SOTA",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n_queries", "n_ok", "n_fail", "fail_ids")}, indent=2))
    print("WROTE", args.out)
    if fails:
        print("FAIL knowledge_eval", fails)
        return 1
    print("PASS knowledge_eval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
