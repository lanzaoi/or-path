# Tube optimization v2

## Status

The complete optimisation and strict-validation path is implemented. The public repository still excludes the original contest attachments, but an authorised local copy can be placed under the path listed in `fixtures/t3/tube_cut_b2026/DATA_REQUIRED.md`. A local real-data run is available whenever that preflight passes; otherwise the solver honestly returns `BLOCKED`.

The current independently validated local result (seed `20260813`, 180-bin
reproducibility budget, Q4 beam 12) is:

| question | purchased stock (mm) | co-cut (mm) | switches | proof status |
|---|---:|---:|---:|---|
| Q1 | 100000 | 0 | 7 | primary stock objective proven; switch optimum open |
| Q2 | 100000 | 3359.9943 | 8 | assignment fixed from Q1 |
| Q3 | 96000 | 3306.7211 | 60 | primary stock objective proven, lower bound 96000 |
| Q4 | 251000 | 7522.9420 | 94 | feasible; lower bound 250000, gap 1000 (0.4%) |

These numbers are read from the solve JSON and independently recomputed by
the strict validator. Q4 is not described as globally optimal.

## Model and algorithm

All lengths use millimetres. Objectives are lexicographic, not a fragile weighted sum:

1. minimise newly purchased standard-stock length;
2. maximise recomputed co-cut benefit while preserving the first objective;
3. minimise type switches while preserving the first two objectives.

The implementation uses:

- deterministic PCA axial orientation and a fixed ±6.25-degree physical
  neighbourhood envelope at every sampled angle;
- exhaustive discrete end-profile rotation for LL/LR/RL/RR benefits;
- exact two-state dynamic programming for orientations on every fixed sequence;
- a compact CP-SAT master that directly assigns item counts to candidate bars, enforces exact demand, and can mix 9/10/11/12 m stock;
- a lexicographic Q1 second stage that fixes the optimal stock total and minimises type switches;
- a conservative homogeneous-block CP-SAT master for Q3, using exact internal co-cut DP lengths before joint ALNS;
- seeded fixed-assignment ALNS for Q2;
- multi-start seeded joint assignment/sequence ALNS for Q3;
- multi-state, future-aware remnant beam search for Q4;
- stratified beam elites that retain low-purchase and initializer-source lanes;
- a next-batch feasible remnant value heuristic instead of treating every
  inventory millimetre as automatically useful;
- a capped co-cut-aware master for demand remaining after remnant allocation.

No routine scales an infeasible occupancy to make it appear feasible. Every over-capacity candidate is rejected.

## Commands

After placing the authorised attachments listed in `fixtures/t3/tube_cut_b2026/DATA_REQUIRED.md`:

```bat
orpath.bat tube-solve --fast
orpath.bat tube-solve
orpath.bat tube-solve --quality
```

Direct equivalent:

```bat
.venv-314\Scripts\python.exe tools\solve_tube_cut_b2026.py --seed 20260813
```

`--fast` is the deterministic smoke budget. The default is the balanced experiment budget. `--quality` uses 720 profile bins and larger ALNS/beam budgets. All output records the seed and search settings.

Q4's objective is applied lexicographically as purchase, co-cut, then switches.
Waste is recorded as a diagnostic and material-balance check, not inserted
ahead of the stated objectives.

The real-data JSON also records optimisation evidence. Q1 contains a raw-length lower bound and a CP-SAT bound for the secondary switch objective. Q3/Q4 contain an optimistic joint-relaxation lower bound, the incumbent gap, every deterministic restart, and the selected seed. These bounds are evidence, not a claim that the heuristic full model is globally optimal.

The Q3/Q4 bound is orientation-consistent: aggregate left/right orientation
counts and incoming/outgoing joints must agree. It still relaxes path
connectivity, bar capacity and batch timing, so it remains optimistic and safe
as a lower bound.

`orpath.bat tube-solve` is the authoritative end-to-end command: after a real solve it writes `outputs/tube_cut_b2026-solution.json`, invokes the strict validator, and writes `outputs/tube_cut_b2026-validate.json`. If source attachments are absent, it returns only the structured `BLOCKED` response and does not validate stale outputs.

`orpath.bat tube-live-gate` performs a strict current `--fast` run and accepts only v2 solve/validate artifacts from that run. With missing attachments it prints `gate_result=BLOCKED`, `strict_current_run=false`, and exits 2. Historical 99,000 mm demo output is not accepted as current evidence.

Collaboration and adversarial gates:

```bat
orpath.bat tube-collab-gate
orpath.bat tube-geometry-gate
orpath.bat tube-redteam-gate
```

The collaboration contract and experiment rules are documented in
`docs/tube-collaboration.md`.

## Strict validation

`model_snapshot.json` is embedded in the product solution envelope. The validator recomputes:

- all Q1–Q4 item demands;
- each bar's raw length, co-cut benefit, effective occupancy, leftover, utilisation and switches;
- allowed standard-stock lengths and zero purchase cost for remnants;
- Q2's fixed Q1 assignment per stock;
- Q4 remnant identity, single use, threshold, inventory chain and material balance;
- Q3 objective binding and all question totals.
- SHA-256 hashes for all 15 authorised inputs;
- an independent orientation-consistent lower-bound rebuild;
- independent Q4 inventory identity, threshold and material-balance checks.

The separate geometry gate deliberately does not import the solver's geometry
implementation. It compares 180/360/720 resolutions, symmetry and the current
snapshot. Current 360-to-720 drift is at most 0.1013 mm (P95 0.056025 mm),
with no entry above 0.5 mm.

Old output without `orpath.tube_model.v2` is not accepted as a strict current result.

## Reproducible tests

```bat
.venv-314\Scripts\python.exe -m pytest -q tools\test_tube_optimization.py
```

Synthetic tests cover exact orientation DP versus exhaustive enumeration,
genuine mixed-stock selection, orientation-consistent bounds, co-cut-aware
initializers after remnant use, fixed-seed reproducibility, demand preservation,
multi-batch inventory balance, valid-envelope acceptance and tamper rejection.

The public runtime/quality benchmark needs no private attachment:

```bat
orpath.bat tube-benchmark
```

It records mixed-stock selection, orientation DP versus exhaustive enumeration, and seeded ALNS quality at several iteration budgets in `outputs/tube-synthetic-benchmark.json`.

## Known limitation

The co-cut calculation is a resolution-stable point-cloud profile model, not a
CAD solid Boolean/non-intersection proof. STEP files are present locally but are
not read or hashed by the authoritative numerical path. A final engineering
deployment must validate selected joints against the original STEP solids or a
trusted collision kernel.
