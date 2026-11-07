#!/usr/bin/env python3
"""Shared deterministic domain-contract validator + spec-driven gates.

Phase 2.4 — the ~110-line ``_meta_type_ok`` / ``_meta_resolve_ref`` /
``_validate_against_meta_schema`` block and the ``validate_<x>_contract`` /
``check_<x>_budget_ledger`` / ``run_<x>_collaboration_gate`` /
``run_<x>_redteam_gate`` boilerplate were copy-pasted verbatim into all ten
``orpath/agents/domains/*.py`` clone modules.  This module concentrates the
exact same semantics into one place so each domain shim only declares its
protocol numbers (budget split, tamper tests, default paths).

Numbers Truth / deterministic law: this module never calls an LLM.  All JSON
verdicts are recomputed from raw contract / ledger / solution files, and tamper
equivalence checks are pure Python.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

__all__ = [
    "resolve_root",
    "to_json",
    "meta_type_ok",
    "meta_resolve_ref",
    "validate_against_meta_schema",
    "validate_contract_payload",
    "domain_invariant_errors",
    "DomainSpec",
    "audit_budget_ledger",
    "run_redteam_gate",
    "run_script_gate",
    "make_validate_contract_tool",
    "make_check_ledger_tool",
    "make_collaboration_gate_tool",
    "make_redteam_gate_tool",
    "make_experiment_card_tool",
    "make_script_gate_tool",
    "META_SCHEMA_RELPATH",
]

#: Canonical (workdir-relative) meta-schema location.
META_SCHEMA_RELPATH = ("contracts", "meta", "domain_collaboration.schema.json")


# --------------------------------------------------------------------------- #
# shared helpers (previously re-implemented in every clone module)
# --------------------------------------------------------------------------- #

def resolve_root() -> Path:
    """Resolve the OR-Path workdir root (``ORPATH_WORKDIR`` or cwd)."""
    raw = (os.environ.get("ORPATH_WORKDIR") or "").strip().strip('"')
    if raw:
        try:
            from orpath.paths import orpath_home

            raw_path = Path(raw).expanduser().resolve()
            home_path = orpath_home().resolve()
            cwd_path = Path.cwd().resolve()
            if raw_path == home_path and cwd_path != home_path:
                return cwd_path
            return raw_path
        except Exception:
            return Path(raw).expanduser().resolve()
    return Path.cwd()


def to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


#: backward-compatible alias (domain clone modules historically named it ``_json``).
_json = to_json


# --------------------------------------------------------------------------- #
# focused draft-07 meta-schema validator (self-contained, no deps)
# --------------------------------------------------------------------------- #

def meta_type_ok(value: Any, expected: str) -> bool:  # alias: _meta_type_ok
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def meta_resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    assert ref.startswith("#/"), f"only local pointer refs supported, got {ref!r}"
    node: Any = root
    for token in ref[2:].split("/"):
        node = node[token]
    return node


def validate_against_meta_schema(
    doc: Any,
    schema: dict[str, Any],
    root: dict[str, Any],
    path: str = "$",
) -> list[str]:
    """Validate ``doc`` against the draft-07 subset used by meta-schemas.

    Supports ``$ref``, ``type``, ``pattern``, ``required``, ``properties``,
    ``additionalProperties``, ``items`` and ``definitions`` — exactly the
    keywords ``contracts/meta/domain_collaboration.schema.json`` relies on.
    Unknown keywords are ignored, matching standard JSON Schema behaviour.
    """
    import re

    errors: list[str] = []
    if "$ref" in schema:
        schema = meta_resolve_ref(root, schema["$ref"])
    if "type" in schema and not meta_type_ok(doc, schema["type"]):
        errors.append(
            f"{path}: expected type {schema['type']!r}, got {type(doc).__name__}"
        )
        return errors
    if isinstance(doc, str) and "pattern" in schema:
        if not re.search(schema["pattern"], doc):
            errors.append(f"{path}: {doc!r} does not match pattern {schema['pattern']!r}")
    if isinstance(doc, list) and "items" in schema:
        for index, item in enumerate(doc):
            errors.extend(
                validate_against_meta_schema(item, schema["items"], root, f"{path}[{index}]")
            )
    if isinstance(doc, dict):
        for key in schema.get("required", []):
            if key not in doc:
                errors.append(f"{path}: missing required key {key!r}")
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in doc:
                errors.extend(
                    validate_against_meta_schema(doc[key], subschema, root, f"{path}.{key}")
                )
        additional = schema.get("additionalProperties")
        if additional is False:
            for key in doc:
                if key not in properties:
                    errors.append(f"{path}: additional property {key!r} not allowed")
        elif isinstance(additional, dict):
            for key in doc:
                if key in properties:
                    continue
                errors.extend(
                    validate_against_meta_schema(doc[key], additional, root, f"{path}.{key}")
                )
    return errors


# backward-compatible private aliases (domain shims historically exported them)
_meta_type_ok = meta_type_ok
_meta_resolve_ref = meta_resolve_ref
_validate_against_meta_schema = validate_against_meta_schema


# --------------------------------------------------------------------------- #
# contract validation
# --------------------------------------------------------------------------- #

def validate_contract_payload(
    root: Path,
    contract_path: str,
) -> dict[str, Any]:
    """Load + meta-schema validate one collaboration contract file.

    Returns a plain dict ``{ok, contract_path, schema, problem_id, ...,
    errors, contract}`` where ``contract`` is attached for downstream
    domain-invariant checks.
    """
    meta_path = root.joinpath(*META_SCHEMA_RELPATH)
    contract_file = Path(contract_path)
    if not contract_file.is_absolute():
        contract_file = root / contract_file
    if not contract_file.is_file() or not meta_path.is_file():
        return {
            "ok": False,
            "error": "Missing contract or meta-schema in contracts/",
            "contract_path": str(contract_file),
            "meta_schema_path": str(meta_path),
            "errors": [],
        }

    try:
        contract = json.loads(contract_file.read_text(encoding="utf-8"))
        meta_schema = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"Failed reading contract schemas: {exc}", "errors": []}

    errors = validate_against_meta_schema(contract, meta_schema, meta_schema)
    return {
        "ok": len(errors) == 0,
        "contract_path": str(contract_file.resolve()),
        "schema": contract.get("schema"),
        "problem_id": contract.get("problem_id"),
        "numeric_authority": contract.get("numeric_authority"),
        "budget_percent": contract.get("budget_percent") or {},
        "objective_order": contract.get("objective_order"),
        "roles": sorted((contract.get("roles") or {}).keys()),
        "errors": errors,
        "contract": contract,
    }


def domain_invariant_errors(contract: dict[str, Any], spec: "DomainSpec") -> list[str]:
    """Protocol invariants that every collaboration contract must satisfy."""
    errors: list[str] = []
    budget = contract.get("budget_percent") or {}
    if isinstance(budget, dict) and sum(
        int(v) for v in budget.values() if isinstance(v, int) and not isinstance(v, bool)
    ) != 100:
        errors.append("budget_percent must sum to exactly 100")

    lifecycle = contract.get("candidate_lifecycle")
    if isinstance(lifecycle, list):
        if lifecycle[0] != "PROPOSED" or lifecycle[-1] != "ACCEPTED":
            errors.append(
                "candidate_lifecycle must start at PROPOSED and end at ACCEPTED"
            )

    tamper = contract.get("tamper_tests")
    if isinstance(tamper, list):
        if sorted(tamper) != sorted(spec.tamper_tests):
            errors.append(f"tamper_tests must list exactly {sorted(spec.tamper_tests)}")

    return errors


# --------------------------------------------------------------------------- #
# DomainSpec — declarative protocol identity for one domain team
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class DomainSpec:
    """Declarative protocol identity consumed by every generic tool factory."""

    domain: str
    contract_path: str = ""
    ledger_path: str = ""
    solution_path: str = ""
    redteam_out_path: str = ""
    budget: dict[str, int] = field(default_factory=dict)
    risk_override_budget: dict[str, int] = field(default_factory=dict)
    objective_order: tuple[str, ...] = ()
    candidate_lifecycle: tuple[str, ...] = ()
    tamper_tests: tuple[str, ...] = ()
    # tube-style collaboration gate runs a script instead of contract+ledger
    collaboration_gate_script: str = ""
    # optional second ledger sub-budget (tube Q4 internal budget)
    sub_budget_key: str = ""
    sub_budget: dict[str, int] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# ledger audit (spec-driven; previously cloned ten times)
# --------------------------------------------------------------------------- #

def audit_budget_ledger(spec: DomainSpec, ledger_path: str) -> dict[str, Any]:
    """Audit a domain budget ledger through the shared engine."""
    from orpath.agents.budget_engine import BudgetLedgerManager

    root = resolve_root()
    path = Path(ledger_path)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return {"ok": False, "error": f"Budget ledger not found: {ledger_path}"}

    expected_budget = dict(spec.budget)
    expected_sub_budget: dict[str, int] = dict(spec.sub_budget)
    protocol_path = root / "contracts" / f"{spec.domain}_collaboration_v1.json"
    if protocol_path.is_file():
        try:
            protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"ok": False, "error": f"Failed reading protocol: {exc}"}
        if isinstance(protocol, dict):
            expected_budget = dict(protocol.get("budget_percent") or expected_budget)
            if spec.sub_budget_key and spec.sub_budget_key in protocol:
                expected_sub_budget = dict(protocol[spec.sub_budget_key])

    manager = BudgetLedgerManager(
        domain=spec.domain,
        root=root,
        baseline_budget=expected_budget,
        override_budget=spec.risk_override_budget,
    )
    manager.load(path)
    if manager.load_error:
        return {"ok": False, "error": manager.load_error, "ledger_path": str(path)}
    if not isinstance(manager.ledger, dict):
        return {
            "ok": False,
            "error": "budget ledger must be a JSON object",
            "ledger_path": str(path),
        }

    expected_sub_budgets: dict[str, dict[str, int]] = {}
    if spec.sub_budget_key and expected_sub_budget:
        expected_sub_budgets[spec.sub_budget_key] = expected_sub_budget

    report = manager.audit_file(
        expected_budget=expected_budget,
        expected_sub_budgets=expected_sub_budgets or None,
    )
    compliance = report.get("compliance") or {}
    budget = compliance.get("budget_percent") or {}
    sub_budgets = compliance.get("sub_budgets") or {}

    out: dict[str, Any] = {
        "ok": bool(report.get("ok")),
        "ledger_path": str(path.resolve()),
        "schema": report.get("schema"),
        "budget_percent": budget,
        "expected_budget_percent": expected_budget,
        "budget_matches_protocol": bool(compliance.get("budget_matches_expected")),
        "total_budget_sum": int(compliance.get("budget_sum") or 0),
        "risk_override": report.get("risk_override"),
        "validation": report.get("validation"),
        "audit": report,
    }
    if spec.sub_budget_key:
        block = sub_budgets.get(spec.sub_budget_key) or {}
        out["budget_percent_alt"] = block.get("actual") or {}
        out["expected_budget_percent_alt"] = expected_sub_budget
        out["budget_matches_protocol_alt"] = bool(block.get("matches_expected"))
        # Backward compatibility aliases for domain-specific sub-budget keys (e.g. Tube Q4)
        out[spec.sub_budget_key] = block.get("actual") or {}
        out[f"expected_{spec.sub_budget_key}"] = expected_sub_budget
        if spec.sub_budget_key == "q4_internal_budget_percent":
            out["q4_budget_matches_protocol"] = bool(block.get("matches_expected"))
    return out


# --------------------------------------------------------------------------- #
# redteam / script gates (subprocess runners, identical shape everywhere)
# --------------------------------------------------------------------------- #

def run_script_gate(
    root: Path,
    script: Path,
    args: list[str],
    timeout: int = 60,
) -> dict[str, Any]:
    """Execute a gate script and fold its optional JSON report into the verdict."""
    if not script.is_file():
        return {"ok": False, "error": f"Gate script not found: {script}"}
    try:
        proc = subprocess.run(
            [sys.executable, str(script), *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        report_data = None
        out_file = None
        if "--out" in args:
            idx = args.index("--out")
            if idx + 1 < len(args):
                out_file = Path(args[idx + 1])
        elif args and args[-1].startswith("--out"):
            # args like ["--solution", P, "--out", P]
            if len(args) >= 4:
                out_file = Path(args[-1])
        if out_file and out_file.is_file():
            try:
                report_data = json.loads(out_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip()[:1000],
            "stderr": proc.stderr.strip()[:1000],
            "report_path": str(out_file.resolve()) if out_file else "",
            "report": report_data,
        }
    except Exception as exc:
        return {"ok": False, "error": f"Failed running gate: {exc}"}


def run_redteam_gate(spec: DomainSpec, solution_path: str, out_path: str) -> dict[str, Any]:
    """Run the domain redteam gate script against a frozen solution file."""
    root = resolve_root()
    script = root / "scripts" / f"{spec.domain}_redteam_gate.py"
    if not script.is_file():
        return {"ok": False, "error": f"Redteam gate script not found: {script}"}
    sol = Path(solution_path)
    if not sol.is_absolute():
        sol = root / sol
    out = Path(out_path)
    if not out.is_absolute():
        out = root / out
    if not sol.is_file():
        return {"ok": False, "error": f"Solution file not found: {sol}"}
    return run_script_gate(root, script, ["--solution", str(sol), "--out", str(out)], timeout=60)


# --------------------------------------------------------------------------- #
# @tool factories — generate the historical ``validate_<x>_contract`` etc.
# --------------------------------------------------------------------------- #

def make_validate_contract_tool(spec: DomainSpec) -> Any:
    """Build ``validate_<domain>_contract(contract_path=...)`` tool."""

    @tool
    def validate_domain_contract(
        contract_path: str = spec.contract_path,
    ) -> str:
        """Validate the domain collaboration contract against the meta-schema.

        Enforces the Domain Collaboration Contract law from
        contracts/meta/domain_collaboration.schema.json: stable schema id,
        numeric authority, lexicographic objective order, role
        ownership/forbidden boundaries, budget split, candidate lifecycle
        and stop rules.
        """
        root = resolve_root()
        payload = validate_contract_payload(root, contract_path)
        if not payload.get("ok"):
            payload.pop("contract", None)
            return to_json({k: v for k, v in payload.items() if k != "contract"})

        contract = payload.pop("contract")
        payload["errors"] = payload["errors"] + domain_invariant_errors(contract, spec)
        payload["ok"] = not payload["errors"]
        payload.pop("contract", None)
        return to_json(payload)

    validate_domain_contract.name = f"validate_{spec.domain}_contract"
    return validate_domain_contract


def make_check_ledger_tool(spec: DomainSpec) -> Any:
    """Build ``check_<domain>_budget_ledger(ledger_path=...)`` tool."""

    @tool
    def check_budget_ledger(ledger_path: str = spec.ledger_path) -> str:
        """Audit the discretionary budget ledger against protocol requirements.

        Structural and sum-to-100 checks are delegated to the shared
        :class:`orpath.agents.budget_engine.BudgetLedgerManager`.
        """
        return to_json(audit_budget_ledger(spec, ledger_path))

    check_budget_ledger.name = f"check_{spec.domain}_budget_ledger"
    return check_budget_ledger


def make_collaboration_gate_tool(spec: DomainSpec) -> Any:
    """Build ``run_<domain>_collaboration_gate(...)`` tool.

    Standard domains: contract + ledger checks.  Script-gate domains (e.g.
    tube) run ``scripts/<domain>_collaboration_gate.py`` instead.
    """

    if spec.collaboration_gate_script:

        @tool
        def run_collaboration_gate() -> str:
            """Machine-check the collaboration protocol end to end (gate script).

            Verifies the entire contract: roles, experiment cards, budget
            ledger, candidate lifecycle, stop rules and lexicographic
            objective ordering.
            """
            root = resolve_root()
            result = run_script_gate(
                root,
                root / "scripts" / spec.collaboration_gate_script,
                [],
                timeout=30,
            )
            result["gate"] = f"{spec.domain}_collaboration_gate"
            return to_json(result)

        run_collaboration_gate.name = f"run_{spec.domain}_collaboration_gate"
        return run_collaboration_gate

    @tool
    def run_collaboration_gate(
        contract_path: str = spec.contract_path,
        ledger_path: str = spec.ledger_path,
    ) -> str:
        """Machine-check the collaboration protocol end to end.

        Runs the domain contract validator against the meta-schema and audits
        the golden budget ledger through :class:`BudgetLedgerManager`.
        """
        contract = json.loads(
            make_validate_contract_tool(spec).invoke({"contract_path": contract_path})
        )
        ledger = json.loads(
            make_check_ledger_tool(spec).invoke({"ledger_path": ledger_path})
        )
        ok = bool(contract.get("ok")) and bool(ledger.get("ok"))
        return to_json(
            {
                "ok": ok,
                "gate": f"{spec.domain}_collaboration_gate",
                "contract": {
                    "ok": contract.get("ok"),
                    "schema": contract.get("schema"),
                    "problem_id": contract.get("problem_id"),
                    "errors": contract.get("errors") or [],
                },
                "budget_ledger": {
                    "ok": ledger.get("ok"),
                    "budget_percent": ledger.get("budget_percent"),
                    "budget_matches_protocol": ledger.get("budget_matches_protocol"),
                    "error": ledger.get("error"),
                },
            }
        )

    run_collaboration_gate.name = f"run_{spec.domain}_collaboration_gate"
    return run_collaboration_gate


def make_redteam_gate_tool(spec: DomainSpec) -> Any:
    """Build ``run_<domain>_redteam_gate(solution_path=..., out_path=...)``."""

    @tool
    def run_redteam_gate_tool(
        solution_path: str = spec.solution_path,
        out_path: str = spec.redteam_out_path,
    ) -> str:
        """Execute the independent adversarial red-team audit + 5 DIMO attacks.

        Runs the domain red-team gate script: full independent recomputation
        of every constraint plus 5 deliberate tamper attack injections.
        Requires 100% interception of all attacks.
        """
        return to_json(run_redteam_gate(spec, solution_path, out_path))

    run_redteam_gate_tool.name = f"run_{spec.domain}_redteam_gate"
    return run_redteam_gate_tool


# --------------------------------------------------------------------------- #
# experiment-card validator (tube-style single-factor experiment cards)
# --------------------------------------------------------------------------- #

def make_experiment_card_tool(domain: str, schema_relpath: str, stochastic_domains: tuple[str, ...] = ("q1_q2", "q3", "q4")) -> Any:
    """Build ``validate_<domain>_experiment_card(card_path)`` tool.

    Enforces the One-Factor Experiment Card law: exactly 1 factor changes,
    baseline and frozen factors declared, acceptance criteria fixed before
    run, stochastic experiments require seed sets.
    """

    @tool
    def validate_experiment_card(card_path: str) -> str:
        """Validate a single-factor experiment card against the protocol schema."""
        root = resolve_root()
        path = Path(card_path)
        if not path.is_absolute():
            path = root / path
        if not path.is_file():
            return to_json({"ok": False, "error": f"Experiment card not found: {card_path}"})
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return to_json({"ok": False, "error": f"Invalid JSON in {card_path}: {exc}"})

        schema_path = root / schema_relpath
        protocol_path = root / "contracts" / f"{domain}_collaboration_v1.json"
        if not schema_path.is_file() or not protocol_path.is_file():
            return to_json({"ok": False, "error": "Missing contract schemas in contracts/"})
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return to_json({"ok": False, "error": f"Failed reading protocol schemas: {exc}"})

        errors: list[str] = []
        missing = [key for key in schema.get("required", []) if key not in card]
        if missing:
            errors.append(f"Missing required fields: {missing}")
        if card.get("schema") != schema.get("schema"):
            errors.append(f"Invalid schema: expected {schema.get('schema')}, got {card.get('schema')}")
        if card.get("domain") not in schema.get("domains", []):
            errors.append(f"Invalid domain: {card.get('domain')}")
        changed = card.get("changed_factor")
        if not isinstance(changed, dict):
            errors.append("changed_factor must be an object")
        else:
            if set(changed) != {"name", "baseline", "candidate"}:
                errors.append(
                    f"changed_factor must contain only name, baseline, candidate (got {list(changed)})"
                )
            elif changed.get("baseline") == changed.get("candidate"):
                errors.append("changed_factor baseline and candidate must differ")
        owner = str(card.get("owner_agent") or "")
        if owner not in protocol.get("roles", {}):
            errors.append(f"owner_agent '{owner}' is not an authorized protocol role")
        if card.get("domain") in set(stochastic_domains) and not card.get("seed_set"):
            errors.append(f"stochastic OR domains ({', '.join(stochastic_domains)}) require seed_set")

        return to_json({
            "ok": len(errors) == 0,
            "card_path": str(path.resolve()),
            "card_id": card.get("id"),
            "domain": card.get("domain"),
            "owner_agent": owner,
            "changed_factor": changed,
            "errors": errors,
        })

    validate_experiment_card.name = f"validate_{domain}_experiment_card"
    return validate_experiment_card


# --------------------------------------------------------------------------- #
# generic script gate tool (e.g. tube geometry stability gate)
# --------------------------------------------------------------------------- #

def make_script_gate_tool(
    domain: str,
    tool_name: str,
    script_relpath: str,
    docstring: str,
    param_specs: tuple[tuple[str, str, str], ...],
    timeout: int = 60,
) -> Any:
    """Build an ``@tool`` that executes a script with named CLI path params.

    ``param_specs`` is a sequence of ``(python_name, default_value, cli_flag)``.
    A dynamic signature is materialized so langchain derives the JSON schema
    exactly like the historical hand-written clone modules.
    """
    ns: dict[str, Any] = {
        "tool": tool,
        "resolve_root": resolve_root,
        "to_json": to_json,
        "run_script_gate": run_script_gate,
        "Path": Path,
        "timeout": timeout,
        "specs": list(param_specs),
    }
    signature = ", ".join(f"{p}: str = {d!r}" for p, d, _ in param_specs)
    defaults_src = "{" + ", ".join(
        f"{p!r}: {d!r}" for p, d, _ in param_specs
    ) + "}"
    flags_src = "{" + ", ".join(f"{p!r}: {f!r}" for p, _, f in param_specs) + "}"
    src = (
        f"""
@tool
def _generated_gate({signature}) -> str:
    '''Generated script-gate tool (see make_script_gate_tool docs).'''
    __flags = {flags_src}
    __defaults = {defaults_src}
    root = resolve_root()
    script = root / {script_relpath!r}
    if not script.is_file():
        return to_json({{"ok": False, "error": f"Gate script not found: {{script}}"}})
    args = []
    for name, flag in __flags.items():
        val = str(locals()[name] or __defaults[name])
        if not Path(val).is_absolute():
            val = str(root / val)
        args.extend([flag, val])
    return to_json(run_script_gate(root, script, args, timeout=timeout))
"""
    )
    exec(src, ns)  # noqa: S102 — intentional codegen for tool signature fidelity
    fn = ns["_generated_gate"]
    fn.__doc__ = docstring
    fn.name = tool_name
    return fn