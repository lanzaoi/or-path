import sys
from pathlib import Path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
from tools.solve_dispatch import solve

INSTANCES = [
    "burma14",
    "ulysses16",
    "gr17",
    "bayg29",
    "swiss42",
    "att48",
    "eil51",
    "kroA100",
]

repo_root = Path(__file__).resolve().parent.parent

for inst in INSTANCES:
    # Try cpsat for small n, ortools for larger n
    mode = "cpsat" if inst in ("burma14", "ulysses16", "gr17") else "ortools"
    ok, sol, raw = solve(repo_root, inst, mode=mode, problem_class="tsp")
    if ok:
        obj = sol.get("objective")
        print(f"Instance: {inst:10s} Mode: {mode:7s} Status: {sol.get('status')} Objective: {obj}")
    else:
        print(f"Instance: {inst:10s} Mode: {mode:7s} FAILED: {raw}")
