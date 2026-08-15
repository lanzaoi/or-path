#!/usr/bin/env python3
"""Machine-check the Tube B collaboration protocol and role contracts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "contracts" / "tube_collaboration_v1.json"
CARD_SCHEMA_PATH = ROOT / "contracts" / "tube_experiment_card.schema.json"
CARD_TEMPLATE_PATH = ROOT / "templates" / "tube-experiment-card.json"
CARD_DIR = ROOT / "experiments" / "tube" / "cards"
BUDGET_LEDGER_PATH = ROOT / "experiments" / "tube" / "budget-ledger.json"


class GateFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateFailure(message)
    print(f"OK: {message}")


def load_json(path: Path) -> dict:
    require(path.is_file(), f"artifact exists: {path.relative_to(ROOT)}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateFailure(f"invalid JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON object: {path.relative_to(ROOT)}")
    return value


def validate_card(card: dict, schema: dict, protocol: dict) -> None:
    missing = [key for key in schema["required"] if key not in card]
    require(not missing, f"experiment card required fields (missing={missing})")
    require(card.get("schema") == schema["schema"], "experiment card schema version")
    require(card.get("domain") in schema["domains"], "experiment card domain")
    require(card.get("status") in schema["allowed_status"], "experiment card status")
    changed = card.get("changed_factor")
    require(isinstance(changed, dict), "changed_factor is one object")
    require(
        set(changed) == {"name", "baseline", "candidate"},
        "exactly one factor changes per experiment card",
    )
    require(changed["baseline"] != changed["candidate"], "changed factor actually changes")
    require(bool(card.get("baseline_artifact")), "baseline artifact declared")
    require(bool(card.get("frozen_factors")), "frozen factors declared")
    require(bool(card.get("acceptance")), "acceptance criteria fixed before run")
    require(bool(card.get("output_path")), "experiment output path declared")
    owner = str(card.get("owner_agent") or "")
    require(owner in protocol["roles"], "experiment owner is a protocol role")
    if card["domain"] in {"q1_q2", "q3", "q4"}:
        require(bool(card.get("seed_set")), "stochastic OR experiment has seed set")


def main() -> int:
    try:
        protocol = load_json(PROTOCOL_PATH)
        schema = load_json(CARD_SCHEMA_PATH)
        template = load_json(CARD_TEMPLATE_PATH)
        require(
            protocol.get("schema") == "orpath.tube_collaboration.v1",
            "Tube collaboration schema version",
        )
        require(
            protocol.get("numeric_authority")
            == "local_solver_and_independent_validator",
            "numeric authority is solve + independent validate",
        )
        require(
            protocol.get("selection_rule") == "lexicographic_not_agent_vote",
            "candidate selection forbids agent voting",
        )
        budget = protocol.get("budget_percent") or {}
        require(
            budget == {"geometry": 20, "q1_q2": 10, "q3": 25, "q4": 45},
            "discretionary effort allocation is 20/10/25/45",
        )
        require(sum(int(value) for value in budget.values()) == 100, "budget sums to 100%")
        q4_budget = protocol.get("q4_internal_budget_percent") or {}
        require(
            sum(int(value) for value in q4_budget.values()) == 100,
            "Q4 internal budget sums to 100%",
        )
        expected_roles = {
            "or-tube-lead",
            "or-tube-geometry",
            "or-tube-q1q2",
            "or-tube-q3",
            "or-tube-q4",
            "or-tube-redteam",
        }
        require(set(protocol.get("roles") or {}) == expected_roles, "six Tube roles declared")
        for role in sorted(expected_roles):
            path = ROOT / ".pi" / "agents" / f"{role}.md"
            require(path.is_file(), f"agent exists: {role}")
            text = path.read_text(encoding="utf-8")
            require(f"name: {role}" in text[:300], f"agent frontmatter name: {role}")
            require("Forbidden" in text, f"agent has forbidden boundary: {role}")
        rules = protocol.get("experiment_rules") or {}
        require(rules.get("changed_factors_per_card") == 1, "one-factor experiment rule")
        require(rules.get("failed_experiments_are_retained") is True, "failed experiments retained")
        require(
            rules.get("numbers_may_only_move_via_json_artifacts") is True,
            "numeric handoffs are JSON-only",
        )
        require(rules.get("hard_runtime_cap_required") is True, "hard runtime cap required")
        require(rules.get("timeout_is_not_no_solution") is True, "timeout is not infeasibility")
        require(
            rules.get("accepted_candidate_requires_independent_validation") is True,
            "accepted candidates require independent validation",
        )
        require(
            rules.get("official_candidate_must_be_lexicographically_nonworse") is True,
            "official candidate must be lexicographically nonworse",
        )
        require(
            protocol.get("candidate_lifecycle")
            == [
                "PROPOSED",
                "SOLVER_FEASIBLE",
                "INDEPENDENTLY_VALIDATED",
                "REDTEAM_PASSED",
                "ACCEPTED",
            ],
            "candidate lifecycle requires validate and red-team before acceptance",
        )
        for domain in budget:
            require(bool((protocol.get("stop_rules") or {}).get(domain)), f"stop rule: {domain}")
        validate_card(template, schema, protocol)
        cards = sorted(CARD_DIR.glob("*.json"))
        require(bool(cards), "actual Tube experiment cards exist")
        for path in cards:
            print(f"CARD: {path.relative_to(ROOT)}")
            validate_card(load_json(path), schema, protocol)
        ledger = load_json(BUDGET_LEDGER_PATH)
        require(ledger.get("schema") == "orpath.tube_budget_ledger.v1", "budget ledger schema")
        require(ledger.get("budget_percent") == budget, "budget ledger matches protocol")
        require(ledger.get("q4_internal_budget_percent") == q4_budget, "Q4 ledger matches protocol")
    except GateFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("PASS tube_collaboration_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
