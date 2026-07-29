#!/usr/bin/env python3
"""Export B-题 all solutions to CSV/XLSX tables + master JSON."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "b-polyomino"


def load(name: str) -> dict:
    p = OUT / name
    return json.loads(p.read_text(encoding="utf-8"))


def write_placements_csv(path: Path, sol: dict) -> None:
    rows = []
    for i, p in enumerate(sol.get("placements") or []):
        cells = ";".join(f"({a},{b})" for a, b in p["cells"])
        rows.append(
            {
                "idx": i,
                "piece": p["piece"],
                "size": p.get("size", len(p["cells"])),
                "cost": p.get("cost", ""),
                "cells": cells,
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["idx", "piece", "size", "cost", "cells"])
        w.writeheader()
        w.writerows(rows)


def write_grid_csv(path: Path, grid: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        for row in grid or []:
            w.writerow(list(row))


def try_xlsx(master: dict) -> str | None:
    try:
        from openpyxl import Workbook
    except ImportError:
        return None
    wb = Workbook()
    # summary
    ws = wb.active
    ws.title = "summary"
    ws.append(["problem", "status", "objective", "proven", "extra"])
    for row in master["summary_rows"]:
        ws.append(row)
    # each problem sheet
    for block in master["blocks"]:
        name = block["sheet"][:31]
        w = wb.create_sheet(name)
        w.append(["key", "value"])
        for k, v in block["kv"]:
            w.append([k, v])
        w.append([])
        w.append(["piece_counts"])
        for k, v in (block.get("counts") or {}).items():
            w.append([k, v])
        w.append([])
        w.append(["grid"])
        for line in block.get("grid") or []:
            w.append(list(line))
        if block.get("placements"):
            w.append([])
            w.append(["idx", "piece", "size", "cost", "cells"])
            for i, p in enumerate(block["placements"][:5000]):
                cells = ";".join(f"({a},{b})" for a, b in p["cells"])
                w.append([i, p["piece"], p.get("size", ""), p.get("cost", ""), cells])
    path = OUT / "B-polyomino-all-results.xlsx"
    wb.save(path)
    return str(path)


def main() -> int:
    # promote best 30x30
    t4 = OUT / "q2-30x30-tetromino-only.json"
    if t4.is_file():
        d = json.loads(t4.read_text(encoding="utf-8"))
        d["problem_id"] = "polyomino_b_q2_30x30"
        d["meta"] = dict(d.get("meta") or {})
        d["meta"]["note"] = "Official Q2.3 result: pure tetromino OPTIMAL 225 (=ceil(900/4))"
        (OUT / "q2-30x30-solution.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    specs = [
        ("Q1.1 min cover", "q1-min-cover-solution.json"),
        ("Q1.2 L3 deficient", "q1-l3-deficient.json"),
        ("Q2.1 12x11", "q2-12x11-solution.json"),
        ("Q2.4 12x11 unc5", "q2-12x11-unc5-solution.json"),
        ("Q2.2 25x20", "q2-25x20-solution.json"),
        ("Q2.3 30x30", "q2-30x30-solution.json"),
        ("Q3 12x11 multiobj", "q3-12x11-solution.json"),
    ]

    summary_rows = []
    blocks = []
    master_solutions = {}

    for title, fname in specs:
        p = OUT / fname
        if not p.is_file():
            summary_rows.append([title, "MISSING", "", "", fname])
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        master_solutions[title] = {
            "file": fname,
            "status": d.get("status"),
            "objective": d.get("objective"),
            "objectives": d.get("objectives"),
            "piece_counts": d.get("piece_counts"),
            "proven_optimal": (d.get("meta") or {}).get("proven_optimal"),
        }
        extra = ""
        if d.get("objectives"):
            o = d["objectives"]
            extra = f"cost={o.get('total_cost')};shared={o.get('shared_edges')};pieces={o.get('piece_count')}"
        elif title.startswith("Q1.2"):
            extra = f"any_L3={d.get('any_removed_cell_L3_coverable')};n={d.get('feasible_positions')}"
        summary_rows.append(
            [
                title,
                d.get("status"),
                d.get("objective"),
                (d.get("meta") or {}).get("proven_optimal"),
                extra,
            ]
        )
        stem = fname.replace(".json", "")
        if d.get("placements"):
            write_placements_csv(OUT / "tables" / f"{stem}-placements.csv", d)
        grid = (d.get("meta") or {}).get("board_grid")
        if grid:
            write_grid_csv(OUT / "tables" / f"{stem}-grid.csv", grid)
        blocks.append(
            {
                "sheet": stem[:31],
                "kv": [
                    ("title", title),
                    ("status", d.get("status")),
                    ("objective", d.get("objective")),
                    ("proven_optimal", (d.get("meta") or {}).get("proven_optimal")),
                    ("solver", d.get("solver")),
                    ("objectives", json.dumps(d.get("objectives") or {}, ensure_ascii=False)),
                ],
                "counts": d.get("piece_counts") or {},
                "grid": grid or [],
                "placements": d.get("placements") or [],
            }
        )

    # summary csv
    OUT.joinpath("tables").mkdir(parents=True, exist_ok=True)
    with (OUT / "tables" / "summary.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["problem", "status", "objective", "proven", "extra"])
        w.writerows(summary_rows)

    master = {
        "contest": "HDU 2025 freshman MCM B polyomino",
        "summary_rows": summary_rows,
        "blocks": blocks,
        "solutions_index": master_solutions,
    }
    (OUT / "B-ALL-MASTER.json").write_text(
        json.dumps(
            {
                "contest": master["contest"],
                "summary_rows": summary_rows,
                "solutions_index": master_solutions,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    xlsx = try_xlsx(master)
    print("summary_csv", OUT / "tables" / "summary.csv")
    print("master_json", OUT / "B-ALL-MASTER.json")
    print("xlsx", xlsx or "openpyxl_missing_csv_only")
    for row in summary_rows:
        print("ROW", row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
