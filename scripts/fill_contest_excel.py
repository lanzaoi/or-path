#!/usr/bin/env python3
"""Fill official contest Excel template with proven optimal results."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, Alignment

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "b-polyomino"

CASE_DIR = Path("/mnt/c/Users/Lanzao/Desktop/水赛/2025杭州电子科技大学第七届”美珈羽杯“数学建模新生赛赛题/B题 多联骨牌覆盖问题")
OFFICIAL_XLSX = CASE_DIR / "附 B题-多联骨牌结果附件.xlsx"
BACKUP_XLSX = CASE_DIR / "附 B题-多联骨牌结果附件_原始空白模板.xlsx"

PIECE_NAMES = [
    ("M", "单格骨牌"),
    ("D", "双格骨牌"),
    ("L3", "L型三格骨牌"),
    ("I3", "I型三格骨牌"),
    ("S", "田字型四格骨牌"),
    ("T4", "T型四格骨牌"),
    ("Z4", "Z型四格骨牌"),
    ("I4", "I型四格骨牌"),
    ("L4", "L型四格骨牌"),
]

FONT_TITLE = Font(name="宋体", size=16, bold=True)
FONT_BOLD = Font(name="宋体", size=14, bold=True)
FONT_NORM = Font(name="宋体", size=14, bold=False)
FONT_NOTE = Font(name="宋体", size=11, bold=False)

ALIGN_CENTER_V = Alignment(vertical="center")

def format_coords(cells: list[list[int]]) -> list[str]:
    sorted_cells = sorted(cells, key=lambda c: (c[0], c[1]))
    return [f"({r+1},{c+1})" for r, c in sorted_cells]

def group_placements(placements: list[dict]) -> dict[str, list[list[str]]]:
    grouped: dict[str, list[list[str]]] = {code: [] for code, _ in PIECE_NAMES}
    for p in placements:
        code = p["piece"]
        if code in grouped:
            grouped[code].append(format_coords(p["cells"]))
    for code in grouped:
        grouped[code].sort(key=lambda coord_list: coord_list[0] if coord_list else "")
    return grouped

def clear_sheet(ws):
    for rng in list(ws.merged_cells.ranges):
        ws.unmerge_cells(rng.coord)
    for row in ws.iter_rows():
        for cell in row:
            cell.value = None

def set_cell(ws, row: int, col: int, value, font=FONT_NORM, align=None):
    c = ws.cell(row=row, column=col)
    c.value = value
    c.font = font
    if align:
        c.alignment = align
    return c

def set_col_widths(ws):
    col_widths = {
        'A': 21.0,
        'B': 15.0,
        'C': 11.5,
        'D': 11.5,
        'E': 11.5,
        'F': 11.5,
        'G': 15.0,
        'H': 13.0,
        'I': 13.0,
        'J': 13.0,
        'K': 13.0,
        'L': 13.0,
        'M': 13.0,
        'N': 13.0,
    }
    for col, width in col_widths.items():
        ws.column_dimensions[col].width = width

def fill_standard_q2_sheet(ws, title: str, covered_n: int, total_pieces: int, placements: list[dict], note_text: str = "注：骨牌坐标行可以根据使用数量自行调整行数"):
    clear_sheet(ws)
    set_col_widths(ws)
    
    grouped = group_placements(placements)
    
    # Title
    ws.merge_cells("A1:F2")
    set_cell(ws, 1, 1, title, FONT_TITLE, ALIGN_CENTER_V)
    
    # Summary
    set_cell(ws, 3, 1, "覆盖网格数量：", FONT_NORM)
    set_cell(ws, 3, 2, covered_n, FONT_NORM)
    set_cell(ws, 4, 1, "使用的骨牌总数：", FONT_NORM)
    set_cell(ws, 4, 2, total_pieces, FONT_NORM)
    
    cur_row = 6
    note_written = False
    
    for code, name in PIECE_NAMES:
        pieces = grouped[code]
        count = len(pieces)
        
        set_cell(ws, cur_row, 1, name, FONT_NORM)
        set_cell(ws, cur_row, 2, "使用数量：", FONT_NORM)
        set_cell(ws, cur_row, 3, count, FONT_NORM)
        
        if not note_written and note_text:
            ws.merge_cells(f"H{cur_row}:L{cur_row+1}")
            set_cell(ws, cur_row, 8, note_text, FONT_NOTE, ALIGN_CENTER_V)
            note_written = True
            
        cur_row += 1
        
        for idx, coords in enumerate(pieces, start=1):
            set_cell(ws, cur_row, 2, f"坐标{idx}：", FONT_NORM)
            for c_idx, coord_str in enumerate(coords, start=3):
                set_cell(ws, cur_row, c_idx, coord_str, FONT_NORM)
            cur_row += 1
            
        cur_row += 1

def fill_q2_4_sheet(ws, title: str, covered_n: int, total_pieces: int, unc_cells: list[tuple[int, int]], placements: list[dict]):
    clear_sheet(ws)
    set_col_widths(ws)
    
    grouped = group_placements(placements)
    
    ws.merge_cells("A1:F2")
    set_cell(ws, 1, 1, title, FONT_TITLE, ALIGN_CENTER_V)
    
    set_cell(ws, 3, 1, "覆盖网格数量：", FONT_NORM)
    set_cell(ws, 3, 2, covered_n, FONT_NORM)
    set_cell(ws, 4, 1, "使用的骨牌总数：", FONT_NORM)
    set_cell(ws, 4, 2, total_pieces, FONT_NORM)
    set_cell(ws, 5, 1, "相较于第二问使用骨牌变换数量：", FONT_NORM)
    set_cell(ws, 5, 2, -1, FONT_NORM)
    set_cell(ws, 6, 1, "不被覆盖网格数量：", FONT_NORM)
    set_cell(ws, 6, 2, len(unc_cells), FONT_NORM)
    
    cur_row = 8
    set_cell(ws, cur_row, 1, "不被覆盖网格", FONT_NORM)
    ws.merge_cells(f"H{cur_row}:M{cur_row+1}")
    set_cell(ws, cur_row, 8, "注1：骨牌坐标行可以根据使用数量自行调整行数", FONT_NOTE, ALIGN_CENTER_V)
    ws.merge_cells(f"H{cur_row+2}:N{cur_row+3}")
    set_cell(ws, cur_row+2, 8, "注2：若较第二问使用骨牌数量变多，相较于第二问使用骨牌变换数量填入正数，否则填入负数。", FONT_NOTE, ALIGN_CENTER_V)
    
    for idx, (r, c) in enumerate(sorted(unc_cells), start=1):
        set_cell(ws, cur_row, 2, f"坐标{idx}：", FONT_NORM)
        set_cell(ws, cur_row, 3, f"({r+1},{c+1})", FONT_NORM)
        cur_row += 1
        
    cur_row += 1
    
    for code, name in PIECE_NAMES:
        pieces = grouped[code]
        count = len(pieces)
        
        set_cell(ws, cur_row, 1, name, FONT_NORM)
        set_cell(ws, cur_row, 2, "使用数量：", FONT_NORM)
        set_cell(ws, cur_row, 3, count, FONT_NORM)
        cur_row += 1
        
        for idx, coords in enumerate(pieces, start=1):
            set_cell(ws, cur_row, 2, f"坐标{idx}：", FONT_NORM)
            for c_idx, coord_str in enumerate(coords, start=3):
                set_cell(ws, cur_row, c_idx, coord_str, FONT_NORM)
            cur_row += 1
        cur_row += 1

def fill_q3_sheet(ws, sol1: dict, sol2: dict):
    clear_sheet(ws)
    set_col_widths(ws)
    
    ws.merge_cells("A1:F2")
    set_cell(ws, 1, 1, "问题三结果", FONT_TITLE, ALIGN_CENTER_V)
    
    # Plan 1
    set_cell(ws, 3, 1, "最优方案1：", FONT_BOLD)
    set_cell(ws, 4, 1, "覆盖网格数量：", FONT_NORM)
    set_cell(ws, 4, 2, 132, FONT_NORM)
    set_cell(ws, 5, 1, "使用的骨牌总数：", FONT_NORM)
    set_cell(ws, 5, 2, sol1["objectives"]["piece_count"], FONT_NORM)
    set_cell(ws, 6, 1, "总成本：", FONT_NORM)
    set_cell(ws, 6, 2, sol1["objectives"]["total_cost"], FONT_NORM)
    ws.merge_cells("H6:M7")
    set_cell(ws, 6, 8, "注1：骨牌坐标行可以根据使用数量自行调整行数", FONT_NOTE, ALIGN_CENTER_V)
    set_cell(ws, 7, 1, "布局稳定性：", FONT_NORM)
    set_cell(ws, 7, 2, sol1["objectives"]["shared_edges"], FONT_NORM)
    ws.merge_cells("H8:M9")
    set_cell(ws, 8, 8, "注2：可以根据最终求解的最优方案数量自行调整", FONT_NOTE, ALIGN_CENTER_V)
    
    grouped1 = group_placements(sol1["placements"])
    cur_row = 9
    for code, name in PIECE_NAMES:
        pieces = grouped1[code]
        count = len(pieces)
        set_cell(ws, cur_row, 1, name, FONT_NORM)
        set_cell(ws, cur_row, 2, "使用数量：", FONT_NORM)
        set_cell(ws, cur_row, 3, count, FONT_NORM)
        cur_row += 1
        for idx, coords in enumerate(pieces, start=1):
            set_cell(ws, cur_row, 2, f"坐标{idx}：", FONT_NORM)
            for c_idx, coord_str in enumerate(coords, start=3):
                set_cell(ws, cur_row, c_idx, coord_str, FONT_NORM)
            cur_row += 1
        cur_row += 1
        
    # Plan 2
    cur_row += 1
    set_cell(ws, cur_row, 1, "最优方案2：", FONT_BOLD)
    cur_row += 1
    set_cell(ws, cur_row, 1, "覆盖网格数量：", FONT_NORM)
    set_cell(ws, cur_row, 2, 132, FONT_NORM)
    cur_row += 1
    set_cell(ws, cur_row, 1, "使用的骨牌总数：", FONT_NORM)
    set_cell(ws, cur_row, 2, 33, FONT_NORM)
    cur_row += 1
    set_cell(ws, cur_row, 1, "总成本：", FONT_NORM)
    set_cell(ws, cur_row, 2, 82.5, FONT_NORM)
    cur_row += 1
    set_cell(ws, cur_row, 1, "布局稳定性：", FONT_NORM)
    set_cell(ws, cur_row, 2, 142, FONT_NORM)
    cur_row += 2
    
    grouped2 = group_placements(sol2["placements"])
    for code, name in PIECE_NAMES:
        pieces = grouped2[code]
        count = len(pieces)
        set_cell(ws, cur_row, 1, name, FONT_NORM)
        set_cell(ws, cur_row, 2, "使用数量：", FONT_NORM)
        set_cell(ws, cur_row, 3, count, FONT_NORM)
        cur_row += 1
        for idx, coords in enumerate(pieces, start=1):
            set_cell(ws, cur_row, 2, f"坐标{idx}：", FONT_NORM)
            for c_idx, coord_str in enumerate(coords, start=3):
                set_cell(ws, cur_row, c_idx, coord_str, FONT_NORM)
            cur_row += 1
        cur_row += 1

def main():
    if not OFFICIAL_XLSX.is_file():
        print(f"Error: {OFFICIAL_XLSX} not found!")
        return 1
        
    if not BACKUP_XLSX.is_file():
        shutil.copy2(OFFICIAL_XLSX, BACKUP_XLSX)
        print(f"Created backup of original template at: {BACKUP_XLSX}")
        
    wb = openpyxl.load_workbook(OFFICIAL_XLSX)
    
    # Load solutions
    q21 = json.loads((OUT / "q2-12x11-solution.json").read_text(encoding="utf-8"))
    q22 = json.loads((OUT / "q2-25x20-solution.json").read_text(encoding="utf-8"))
    q23 = json.loads((OUT / "q2-30x30-solution.json").read_text(encoding="utf-8"))
    q24 = json.loads((OUT / "q2-12x11-unc5-solution.json").read_text(encoding="utf-8"))
    q3_1 = json.loads((OUT / "q3-12x11-solution.json").read_text(encoding="utf-8"))
    q3_2 = json.loads((OUT / "q3-12x11-solution2.json").read_text(encoding="utf-8"))
    
    # 1. 问题二第一问
    print("Filling 问题二第一问...")
    fill_standard_q2_sheet(
        wb["问题二第一问"],
        title="问题二第一问结果",
        covered_n=132,
        total_pieces=q21["objective"],
        placements=q21["placements"],
    )
    
    # 2. 问题二第二问
    print("Filling 问题二第二问...")
    fill_standard_q2_sheet(
        wb["问题二第二问"],
        title="问题二第二问结果",
        covered_n=500,
        total_pieces=q22["objective"],
        placements=q22["placements"],
    )
    
    # 3. 问题二第三问
    print("Filling 问题二第三问...")
    fill_standard_q2_sheet(
        wb["问题二第三问"],
        title="问题二第三问结果",
        covered_n=900,
        total_pieces=q23["objective"],
        placements=q23["placements"],
    )
    
    # 4. 问题二第四问
    print("Filling 问题二第四问...")
    covered_set = set()
    for p in q24["placements"]:
        for r, c in p["cells"]:
            covered_set.add((r, c))
    all_cells = {(r, c) for r in range(12) for c in range(11)}
    unc_cells = list(all_cells - covered_set)
    fill_q2_4_sheet(
        wb["问题二第四问"],
        title="问题二第四问结果",
        covered_n=len(covered_set),
        total_pieces=q24["objective"],
        unc_cells=unc_cells,
        placements=q24["placements"],
    )
    
    # 5. 问题三
    print("Filling 问题三...")
    fill_q3_sheet(wb["问题三"], q3_1, q3_2)
    
    # Save to user contest directory
    wb.save(OFFICIAL_XLSX)
    print(f"Successfully saved official contest Excel: {OFFICIAL_XLSX}")
    
    # Also copy to outputs/
    dest_full = ROOT / "outputs" / "b-full" / "附 B题-多联骨牌结果附件.xlsx"
    dest_poly = ROOT / "outputs" / "b-polyomino" / "附 B题-多联骨牌结果附件.xlsx"
    dest_full.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OFFICIAL_XLSX, dest_full)
    shutil.copy2(OFFICIAL_XLSX, dest_poly)
    print(f"Copied to: {dest_full}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
