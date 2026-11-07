# Task: Max Clique / Max Independent Set Solver (max_clique)

## Deliverables
- [x] 1. `tools/solve_max_clique.py` — solve_max_clique() + CLI (methods: networkx/cpsat/hybrid; modes: max_clique/max_independent_set)
- [x] 2. Register in `orpath/domain_registry.py` (CANONICAL_CLASSES + CLASS_ALIASES + REGISTERED_SOLVE_CLASSES)
- [x] 3. Register in `tools/solve_dispatch.py` (ADAPTER_SCRIPTS + _build_args + auto-route)
- [x] 4. Validators `validate_max_clique` + `validate_independent_set` in `tools/validators/extended_solvers.py`
- [x] 5. Wire into `tools/validate_solution.py` (shape check + class dispatch)
- [x] 6. Tests in `tools/test_extended_solvers.py` (myciel3, C5, cpsat, mis mode, dispatch)
- [x] 7. Verify: pytest -k clique, full suite, problem_workbench_gate, hygiene

## Mathematical Truth (myciel3.col)
- omega(G) = 2 (triangle-free), alpha(G) = 5
- Complement duality: omega(G) == alpha(G_comp) == 2; alpha(G) == omega(G_comp) == 5
- C5: omega = 2, alpha = 2
