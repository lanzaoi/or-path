# OR-Path Benchmark & Evaluation Suite

This directory (`eval_or_bench/`) contains the official, deterministic benchmarking suite for the OR-Path project. It is designed to evaluate the physical `solve_dispatch` -> `validate_solution` pipeline against public operations research datasets, completely independent of LLM prose.

## Deliverables & Artifacts

- **[RESEARCH.md](./RESEARCH.md)**: Deep research into public datasets (TSPLIB, CVRPLIB, etc.), selection criteria, distance metrics, and risk mapping.
- **[summary.json](./results/summary.json)** & **[summary.md](./results/summary.md)**: The final numeric output of the benchmark runs.
- **`raw_tsp/` & `instances/`**: The authentic TSPLIB raw files and their OR-Path `ProblemSchema` converted equivalents.

## 1. Quick Start (一键入口)

We have integrated a `bench` command into the main OR-Path entrypoint. From the repository root, run:

```cmd
orpath.bat bench
```

This will automatically:
1. Run the fast contract probe (`contract_probe.py`) to ensure the pipeline is intact.
2. Run the full TSPLIB benchmark suite on all 8 instances.

## 2. Manual Reproduction (复现命令)

If you wish to run the individual scripts:

### Fast Contract Probe (秒级验证)
Tests the core pipeline on a single small instance (burma14) in under 2 seconds.
```cmd
python eval_or_bench/contract_probe.py
```

### Stress Test (转换器压力测试)
Validates the integrity of the TSPLIB converter and ensures NO forbidden schema keys are present.
```cmd
python eval_or_bench/test_converter_stress.py
```

### Full Benchmark Run (全量主评测)
Runs all 8 instances and regenerates the summary reports.
```cmd
python eval_or_bench/run_full_benchmark.py
```

## 3. Claim Boundaries (声明边界)

**What IS Tested (Trusted):**
- The deterministic `solve_dispatch.py` routing for `tsp` problem classes.
- The `solve_envelope.py` data normalization.
- The `validate_solution.py` mathematical recomputation of the objective.
- 8 classic TSPLIB instances (burma14 to kroA100).
- Geographic (GEO), Pseudo-Euclidean (ATT), and Explicit matrix (EXPLICIT) distance formulations.

**What is NOT Tested (Out of Scope):**
- `LIVE` Multi-Agent orchestration pipeline (`run_orpath.py --live-subagent`).
- Process visibility UI (`Watch`).
- Automated paper/latex generation.
- Problem classes other than `tsp` (e.g., `vrp`, `polyomino`, `tube_cut`).
- Scalability beyond N=100 (instances > 100 were explicitly excluded to ensure execution speed and exact optimality verification).

## 4. Gap Definition & Status

- **optimal**: Solver reported `OPTIMAL` and objective exactly matches the published TSPLIB optimal value.
- **feasible**: Solver reported `FEASIBLE` and passed independent validation.
- **Gap %**: `(solver_obj - published_optimal) / published_optimal * 100%`

*All numbers in this suite are derived strictly from validation recomputation. No numbers are LLM-generated.*
