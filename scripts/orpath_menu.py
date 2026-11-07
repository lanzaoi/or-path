#!/usr/bin/env python3
"""OR-Path Interactive Console Menu (Web Studio & 4 Core OR Solvers)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / "orpath.bat"
SH = ROOT / "orpath.sh"


def _run(args: list[str]) -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONNOUSERSITE", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")
    if os.name == "nt" and BAT.is_file():
        cmd = ["cmd", "/c", str(BAT), *args]
    elif SH.is_file():
        cmd = ["bash", str(SH), *args]
    else:
        cmd = [sys.executable, str(ROOT / "orpath" / "run_orpath.py"), *args]
    print(">>", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


def main() -> int:
    if os.name == "nt":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    print()
    print("======================================================================")
    print("  OR-Path 运筹优化与智能工作台 · 交互式主控菜单")
    print(f"  ROOT = {ROOT}")
    print("======================================================================")
    print("  1) Web Studio & Live Watch  - 启动智能做题工作舱与实时看板 (:8765)")
    print("  w) Watch-Run (边跑边看)     - 启动实时看板并同步执行端到端求解流水线")
    print("  2) Tube Solver              - 空间异形圆管 3D 展开与共切 DP 求解 (--fast)")
    print("  3) Polyomino Solver         - 多联骨牌 CP-SAT 精确覆盖求解 (polyomino_b_q1)")
    print("  4) Polyomino Q3 Layout      - 芯片多目标共边排样优化 (12x11)")
    print("  5) Microgrid Solver         - 园区光储充微电网多时段 LP 与滚动 MPC")
    print("  6) Routing Solver           - 最短路 / TSP / CVRP / VRPTW 路径规划")
    print("  7) Demo M0                  - 运行 M0 最短路基准演示与独立验证")
    print("  8) Workbench Gate           - 运行 Web Studio 智能做题工作舱门禁")
    print("  d) Doctor                   - 运行系统环境、求解器与验证器健康检查")
    print("  0) Quit                     - 退出")
    print("======================================================================")
    print()
    try:
        choice = input("Select [1]: ").strip() or "1"
    except (EOFError, KeyboardInterrupt):
        print()
        return 0

    if choice == "0":
        return 0
    if choice == "1":
        slug = input("Slug [live-btube]: ").strip() or "live-btube"
        thread = input(f"Thread-id [{slug}]: ").strip() or slug
        return _run(["watch", "--slug", slug, "--thread-id", thread])
    if choice.lower() in {"w", "watch-run"}:
        slug = input("Slug [p3-menu]: ").strip() or "p3-menu"
        return _run(["watch-run", "--slug", slug, "--thread-id", slug, "--keep-watch"])
    if choice == "2":
        return _run(["tube-solve", "--fast"])
    if choice == "3":
        return _run(["polyomino-solve", "polyomino_b_q1"])
    if choice == "4":
        return _run(["polyomino-q3", "--rows", "12", "--cols", "11", "--time-limit-s", "10"])
    if choice == "5":
        return _run(["microgrid-solve"])
    if choice == "6":
        pid = input("Problem ID [shortest_path]: ").strip() or "shortest_path"
        return _run(["routing-solve", pid])
    if choice == "7":
        slug = input("Slug [m0]: ").strip() or "m0"
        return _run(["demo-m0", "--slug", slug, "--no-live"])
    if choice == "8":
        return _run(["workbench-gate"])
    if choice.lower() in {"d", "doctor"}:
        return _run(["doctor"])
    print("unknown choice")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
