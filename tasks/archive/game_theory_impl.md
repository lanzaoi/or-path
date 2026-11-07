# Game Theory Solver Implementation Plan

## Deliverables
1. `tools/solve_game_theory.py` — nashpy-based bimatrix Nash equilibrium solver + CLI.
2. `orpath/domain_registry.py` — register canonical class + aliases + solve class.
3. `tools/solve_dispatch.py` — adapter scripts + arg builder + auto-route.
4. `tools/validators/extended_solvers.py` — `validate_game_theory` (independent recompute).
5. `tools/validate_solution.py` — shape check + class dispatch.
6. `tools/test_extended_solvers.py` — 4 solver tests + dispatch parametrization.

## Envelope (ADR-0002 / Numbers Truth)
- problem_id, problem_class='game_theory', mode='game_theory', status='OPTIMAL'
- objective = primary expected_payoffs[0]
- solver='nashpy-engine', source='tools/solve_game_theory.py'
- game_type, row_actions, col_actions, num_equilibria
- equilibria[] (row_strategy, col_strategy, expected_payoffs, is_pure)
- primary_equilibrium{}, primary_row_strategy, primary_col_strategy, expected_payoffs
- game_value (zero-sum float, else None), row_regret, col_regret, raw_problem, meta

## Validator checks
- raw_problem_presence
- strategy_probability_distribution (>=0, sum≈1)
- strategy_dimension_match
- expected_payoffs_recompute (u_row=x^T A y, u_col=x^T B y)
- best_response_regret (row_regret<=1e-4, col_regret<=1e-4)
- objective_match
- all_equilibria_nash
