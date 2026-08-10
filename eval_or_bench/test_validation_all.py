import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from tools.solve_dispatch import solve
from tools.validate_solution import validate

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

all_passed = True
for inst in INSTANCES:
    mode = "cpsat" if inst in ("burma14", "ulysses16", "gr17") else "ortools"
    ok, sol, raw = solve(repo_root, inst, mode=mode, problem_class="tsp")
    if not ok:
        print(f"[{inst}] Solve failed: {raw}")
        all_passed = False
        continue

    report = validate(inst, sol)
    ok_val = report.get("ok", False)
    if ok_val:
        print(f"[{inst}] PASS - Mode: {mode:7s} Status: {sol.get('status')} Obj: {sol.get('objective')}")
    else:
        print(f"[{inst}] FAIL Validation - Report: {report}")
        all_passed = False

if all_passed:
    print("ALL 8 INSTANCES SOLVED AND VALIDATED SUCCESSFULLY!")
else:
    print("SOME INSTANCES FAILED VALIDATION!")
