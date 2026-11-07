#!/usr/bin/env python3
"""Reusable discretionary-budget ledger engine for OR-Path domain supervisors.

The Tube-B collaboration (``contracts/tube_collaboration_v1.json``) enforces a
hard budget discipline: the discretionary effort split across workstreams
(``budget_percent``) must sum to exactly 100 whole percent, every declared
sub-budget (``<name>_budget_percent``) must independently sum to 100, and a
risk override may temporarily swap in a different distribution that must revert
to the baseline once its release condition is satisfied.

This module generalises those rules into a domain-agnostic, offline-safe
``BudgetLedgerManager`` plus a LangChain ``StructuredTool`` factory so any
collaboration supervisor can audit its budget ledger without duplicating logic.

Core API
--------
* :func:`validate_ledger_structure` — structural validation of a ledger dict.
* :func:`check_compliance` — compare a ledger against expected distributions.
* :func:`evaluate_risk_override` — compute the currently effective budget.
* :func:`audit_file` — load a ledger file and produce a full audit report.
* :class:`BudgetLedgerManager` — stateful wrapper (load/validate/audit/track).
* :func:`create_budget_check_tool` — LangChain tool factory for supervisors.

Numbers Truth: every objective figure reported here is recomputed from the raw
ledger/contract data; nothing is invented.
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any

try:  # langchain_core is a hard runtime dependency; guard for offline imports.
    from langchain_core.tools import StructuredTool
except Exception:  # pragma: no cover - defensive, langchain_core always present
    StructuredTool = None  # type: ignore[assignment]

__all__ = [
    "BUDGET_KEY",
    "OVERRIDE_HISTORY_KEY",
    "BudgetLedgerManager",
    "audit_file",
    "check_compliance",
    "create_budget_check_tool",
    "discover_sub_budgets",
    "evaluate_risk_override",
    "validate_ledger_structure",
]

#: Key that holds the primary discretionary split (e.g. geometry/q1_q2/q3/q4).
BUDGET_KEY = "budget_percent"

#: Key that holds the ordered history of risk-override activations.
OVERRIDE_HISTORY_KEY = "risk_override_history"

#: A sub-budget is any top-level key ending in ``_budget_percent`` (excluding the
#: primary ``budget_percent`` key, which has no leading underscore segment).
_SUB_BUDGET_RE = re.compile(r"^.+_budget_percent$")

#: Accepted keys for the temporary distribution carried by an override entry.
_TEMPORARY_KEYS = ("temporary_percent", "temporary_budget_percent", "temporary_budget")


def _coerce_percent(value: Any) -> Any:
    """Coerce an exact whole number to ``int``; keep everything else untouched.

    Silent ``int()`` truncation (e.g. ``33.9 -> 33``) would corrupt reported
    budget figures, so non-integer floats, strings and ``None`` are passed
    through unchanged rather than truncated or crashed on.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return value
        return int(number) if number.is_integer() else value
    return value


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _is_int(value: Any) -> bool:
    """True for genuine integers only (``bool`` is excluded)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _sum_int_values(mapping: dict[str, Any]) -> int:
    return sum(v for v in mapping.values() if _is_int(v))


def _repo_root() -> Path:
    """Repository root derived from this file's location (orpath/agents/…)."""
    return Path(__file__).resolve().parents[2]


def _resolve_root(root: str | Path | None = None) -> Path:
    """Resolve a workspace root, honouring ``ORPATH_WORKDIR`` then repo root."""
    if root:
        return Path(root).expanduser().resolve()
    raw = (os.environ.get("ORPATH_WORKDIR") or "").strip().strip('"')
    if raw:
        candidate = Path(raw).expanduser().resolve()
        if candidate.is_dir():
            return candidate
    return _repo_root()


def discover_sub_budgets(ledger: Any) -> list[str]:
    """Return the names of every declared sub-budget in ``ledger``.

    Sub-budgets are identified by the ``_budget_percent`` suffix (e.g.
    ``q4_internal_budget_percent``). The primary ``budget_percent`` key does not
    match this pattern and is therefore excluded.
    """
    if not isinstance(ledger, dict):
        return []
    return [k for k in ledger if k != BUDGET_KEY and _SUB_BUDGET_RE.match(k)]


def _normalize_overrides(active_overrides: Any) -> list[dict[str, Any]]:
    """Coerce a variety of override inputs into a list of override dicts."""
    if active_overrides is None:
        return []
    if isinstance(active_overrides, dict):
        return [active_overrides]
    if isinstance(active_overrides, (list, tuple)):
        return [o for o in active_overrides if isinstance(o, dict)]
    return []


def _is_released(override: dict[str, Any]) -> bool:
    """An override is released once its ``released`` flag is explicitly True."""
    return override.get("released") is True


def _override_temporary(override: dict[str, Any]) -> dict[str, Any] | None:
    """Extract the temporary distribution carried by an override entry."""
    for key in _TEMPORARY_KEYS:
        value = override.get(key)
        if isinstance(value, dict):
            return value
    return None


# --------------------------------------------------------------------------- #
# Pure validation / compliance functions
# --------------------------------------------------------------------------- #

def validate_ledger_structure(ledger_dict: Any) -> tuple[bool, list[str]]:
    """Validate the structural integrity of a budget ledger.

    Enforces the budget ledger rules:
      * ``ledger_dict`` must be a JSON object.
      * ``budget_percent`` must be present and a non-empty mapping of
        workstream -> whole-percent integers.
      * Every value must be a genuine ``int`` (no floats, strings, bools, None).
      * Every value must be non-negative.
      * ``budget_percent`` must sum to exactly 100.
      * Every declared sub-budget (``<name>_budget_percent``) must independently
        be a non-empty mapping of int percents summing to exactly 100.

    Args:
        ledger_dict: The parsed ledger (typically from a JSON file).

    Returns:
        A ``(ok, errors)`` tuple where ``ok`` is True when no structural rule is
        violated and ``errors`` lists human-readable violations.
    """
    errors: list[str] = []
    if not isinstance(ledger_dict, dict):
        return False, ["ledger must be a JSON object"]

    if BUDGET_KEY not in ledger_dict:
        errors.append(f"missing required key '{BUDGET_KEY}'")
        return False, errors

    budget = ledger_dict.get(BUDGET_KEY)
    if not isinstance(budget, dict):
        errors.append(f"'{BUDGET_KEY}' must be an object mapping workstream -> percent")
    else:
        if not budget:
            errors.append(f"'{BUDGET_KEY}' must not be empty")
        for key, value in budget.items():
            if not _is_int(value):
                errors.append(
                    f"'{BUDGET_KEY}.{key}' must be an integer percent, got "
                    f"{type(value).__name__}: {value!r}"
                )
            elif value < 0:
                errors.append(f"'{BUDGET_KEY}.{key}' must be non-negative, got {value}")
        if not any(not _is_int(v) for v in budget.values()):
            total = _sum_int_values(budget)
            if total != 100:
                errors.append(f"'{BUDGET_KEY}' must sum to exactly 100, got {total}")

    for name in discover_sub_budgets(ledger_dict):
        sub = ledger_dict.get(name)
        if not isinstance(sub, dict):
            errors.append(f"sub-budget '{name}' must be an object")
            continue
        if not sub:
            errors.append(f"sub-budget '{name}' must not be empty")
        for key, value in sub.items():
            if not _is_int(value):
                errors.append(
                    f"'{name}.{key}' must be an integer percent, got "
                    f"{type(value).__name__}: {value!r}"
                )
            elif value < 0:
                errors.append(f"'{name}.{key}' must be non-negative, got {value}")
        if not any(not _is_int(v) for v in sub.values()):
            subtotal = _sum_int_values(sub)
            if subtotal != 100:
                errors.append(f"sub-budget '{name}' must sum to exactly 100, got {subtotal}")

    return (len(errors) == 0), errors


def check_compliance(
    ledger_dict: Any,
    expected_budget: dict[str, Any] | None = None,
    expected_sub_budgets: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Check a ledger against expected distributions.

    Args:
        ledger_dict: The parsed ledger.
        expected_budget: The expected ``budget_percent`` mapping. When omitted the
            match check is skipped (sum/structure rules still apply).
        expected_sub_budgets: Mapping of sub-budget name -> expected mapping. Any
            declared-but-unexpected sub-budget is still sum-checked; any
            expected-but-absent sub-budget is reported as missing.

    Returns:
        A report dict with ``ok``, the actual/expected splits, sum checks,
        per-sub-budget detail, and a combined ``errors`` list.
    """
    structure_ok, errors = validate_ledger_structure(ledger_dict)

    budget = ledger_dict.get(BUDGET_KEY) if isinstance(ledger_dict, dict) else None
    budget = budget if isinstance(budget, dict) else {}
    expected_budget = expected_budget if isinstance(expected_budget, dict) else {}

    budget_matches = (not expected_budget) or (budget == expected_budget)
    budget_sum = _sum_int_values(budget)
    budget_sum_ok = budget_sum == 100

    sub_names = discover_sub_budgets(ledger_dict)
    if expected_sub_budgets:
        for name in expected_sub_budgets:
            if name not in sub_names:
                sub_names.append(name)

    sub_budgets_report: dict[str, dict[str, Any]] = {}
    for name in sub_names:
        actual = ledger_dict.get(name) if isinstance(ledger_dict, dict) else None
        actual = actual if isinstance(actual, dict) else {}
        expected = {}
        if isinstance(expected_sub_budgets, dict):
            expected = expected_sub_budgets.get(name) or {}
        sub_sum = _sum_int_values(actual)
        matches = (not expected) or (actual == expected)
        sub_budgets_report[name] = {
            "actual": actual,
            "expected": expected or None,
            "matches_expected": matches,
            "sum": sub_sum,
            "sum_ok": sub_sum == 100,
        }
        if not matches:
            errors.append(f"sub-budget '{name}' does not match the expected distribution")
        if sub_sum != 100:
            errors.append(f"sub-budget '{name}' must sum to exactly 100, got {sub_sum}")

    ok = structure_ok
    ok = ok and budget_sum_ok
    ok = ok and budget_matches
    for report in sub_budgets_report.values():
        ok = ok and report["matches_expected"] and report["sum_ok"]

    return {
        "ok": ok,
        "budget_percent": budget,
        "expected_budget_percent": expected_budget or None,
        "budget_matches_expected": budget_matches,
        "budget_sum": budget_sum,
        "budget_sum_ok": budget_sum_ok,
        "sub_budgets": sub_budgets_report,
        "errors": errors,
    }


def evaluate_risk_override(
    active_overrides: Any,
    baseline_budget: dict[str, Any] | None = None,
    override_budget: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Compute the currently effective budget given active risk overrides.

    Rules:
      * If no override is active (all released, or none supplied), the baseline
        distribution is returned unchanged.
      * If at least one override is active, the most recent active override's
        temporary distribution is applied; when it carries none, the supplied
        ``override_budget`` is used.
      * The result is the baseline merged with the temporary distribution so that
        any workstreams not specified by the override retain their baseline share.

    Args:
        active_overrides: A single override dict, a list of them, or the ledger's
            ``risk_override_history``. Each entry may carry ``released`` and a
            temporary distribution.
        baseline_budget: The normal discretionary split.
        override_budget: The fallback temporary split when an active override does
            not carry its own.

    Returns:
        A ``dict[str, int]`` describing the effective budget distribution.
    """
    baseline = dict(baseline_budget or {})
    override = dict(override_budget or {})

    overrides = _normalize_overrides(active_overrides)
    active = [o for o in overrides if not _is_released(o)]
    if not active:
        return {str(k): _coerce_percent(v) for k, v in baseline.items()}

    temp = _override_temporary(active[-1]) or override
    effective = dict(baseline)
    effective.update(temp)
    return {str(k): _coerce_percent(v) for k, v in effective.items()}


def audit_file(
    path: str | Path,
    expected_budget: dict[str, Any] | None = None,
    expected_sub_budgets: dict[str, dict[str, Any]] | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Load a budget ledger file and produce a full audit report.

    Args:
        path: Path to the ledger JSON (relative paths resolve against ``root``).
        expected_budget: Expected ``budget_percent`` distribution.
        expected_sub_budgets: Expected sub-budget distributions.
        root: Workspace root used to resolve relative paths.

    Returns:
        A report dict. On success it includes ``ok``, ledger metadata, the
        structural ``validation`` result, the ``compliance`` report, and the
        effective ``risk_override`` state. On load failure it returns
        ``{"ok": False, "exists": False, "error": ...}``.
    """
    manager = BudgetLedgerManager(
        domain="generic",
        root=root,
        baseline_budget=expected_budget,
        override_budget=None,
    )
    return manager.audit_file(path, expected_budget, expected_sub_budgets)


# --------------------------------------------------------------------------- #
# Manager
# --------------------------------------------------------------------------- #

class BudgetLedgerManager:
    """Stateful loader/validator/auditor/tracker for discretionary budgets.

    The manager is domain-agnostic: it works for any ledger that follows the
    ``budget_percent`` / ``<name>_budget_percent`` convention. It can load a
    ledger from a dict or file, validate and audit it, and track risk-override
    activation/release state transitions.

    Example:
        >>> mgr = BudgetLedgerManager(baseline_budget={"a": 100})
        >>> mgr.load("experiments/tube/budget-ledger.json")
        >>> mgr.validate()[0]
        True
    """

    def __init__(
        self,
        ledger: dict[str, Any] | None = None,
        *,
        domain: str = "generic",
        root: str | Path | None = None,
        baseline_budget: dict[str, Any] | None = None,
        override_budget: dict[str, Any] | None = None,
    ) -> None:
        self.domain = domain
        self.root = _resolve_root(root)
        self.ledger: dict[str, Any] = {}
        self.baseline_budget: dict[str, Any] = dict(baseline_budget or {})
        self.override_budget: dict[str, Any] = dict(override_budget or {})
        self.load_error: str | None = None
        if ledger is not None:
            self.load_dict(ledger)

    # -- loading ----------------------------------------------------------- #

    def load_dict(self, ledger: dict[str, Any]) -> "BudgetLedgerManager":
        """Load a ledger from an in-memory dict (deep-copied)."""
        if not isinstance(ledger, dict):
            self.load_error = "ledger must be a JSON object"
            return self
        self.ledger = copy.deepcopy(ledger)
        self.load_error = None
        return self

    def load(self, path: str | Path) -> "BudgetLedgerManager":
        """Load a ledger from a JSON file (relative paths resolve against root)."""
        resolved = self.resolve_path(path)
        self.load_error = None
        if not resolved.is_file():
            self.load_error = f"budget ledger not found: {resolved}"
            return self
        try:
            self.ledger = json.loads(resolved.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - surface any JSON/IO error
            self.load_error = f"invalid JSON in {resolved}: {exc}"
            return self
        return self

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        domain: str = "generic",
        root: str | Path | None = None,
        baseline_budget: dict[str, Any] | None = None,
        override_budget: dict[str, Any] | None = None,
    ) -> "BudgetLedgerManager":
        """Construct a manager and load ``path`` in one step."""
        manager = cls(
            domain=domain,
            root=root,
            baseline_budget=baseline_budget,
            override_budget=override_budget,
        )
        manager.load(path)
        return manager

    def resolve_path(self, path: str | Path) -> Path:
        """Resolve a path against the workspace root when relative."""
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return (self.root / candidate).resolve()

    # -- validation & compliance ------------------------------------------- #

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the currently loaded ledger structure."""
        return validate_ledger_structure(self.ledger)

    def compliance(
        self,
        expected_budget: dict[str, Any] | None = None,
        expected_sub_budgets: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Check compliance, defaulting expected budgets to instance state."""
        return check_compliance(
            self.ledger,
            expected_budget if expected_budget is not None else self.baseline_budget,
            expected_sub_budgets,
        )

    def audit_file(
        self,
        path: str | Path | None = None,
        expected_budget: dict[str, Any] | None = None,
        expected_sub_budgets: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Audit a ledger file (or the currently loaded ledger when ``path`` is None)."""
        if path is not None:
            self.load(path)
        if self.load_error:
            return {
                "ok": False,
                "exists": False,
                "domain": self.domain,
                "error": self.load_error,
            }
        return self._build_report(
            self.ledger,
            expected_budget if expected_budget is not None else self.baseline_budget,
            expected_sub_budgets,
        )

    def _build_report(
        self,
        ledger: dict[str, Any],
        expected_budget: dict[str, Any],
        expected_sub_budgets: dict[str, dict[str, Any]] | None,
    ) -> dict[str, Any]:
        structure_ok, errors = validate_ledger_structure(ledger)
        comp = check_compliance(ledger, expected_budget, expected_sub_budgets)

        overrides = _normalize_overrides(ledger.get(OVERRIDE_HISTORY_KEY))
        risk_block = ledger.get("risk_override") if isinstance(ledger, dict) else None
        if not overrides and isinstance(risk_block, dict):
            overrides = [risk_block]

        active = [o for o in overrides if not _is_released(o)]
        override_budget = self.override_budget
        if not override_budget and isinstance(risk_block, dict):
            override_budget = risk_block.get("temporary_budget_percent") or {}
        baseline = expected_budget or ledger.get(BUDGET_KEY) or {}
        effective = evaluate_risk_override(active, baseline, override_budget)

        return {
            "ok": bool(comp["ok"] and structure_ok),
            "domain": self.domain,
            "schema": ledger.get("schema"),
            "date": ledger.get("date"),
            "scope": ledger.get("scope"),
            "current_phase": ledger.get("current_phase"),
            "validation": {"ok": structure_ok, "errors": errors},
            "compliance": comp,
            "risk_override": {
                "active": bool(active),
                "active_count": len(active),
                "effective_budget_percent": effective,
                "history": overrides,
            },
        }

    # -- risk-override tracking ------------------------------------------- #

    def active_overrides(self) -> list[dict[str, Any]]:
        """Return the override entries that are currently active (not released)."""
        history = _normalize_overrides(self.ledger.get(OVERRIDE_HISTORY_KEY))
        return [o for o in history if not _is_released(o)]

    def effective_budget(self) -> dict[str, int]:
        """Effective budget given the currently active overrides."""
        baseline = self.baseline_budget or self.ledger.get(BUDGET_KEY) or {}
        return evaluate_risk_override(
            self.active_overrides(), baseline, self.override_budget
        )

    def apply_override(
        self,
        trigger: str,
        temporary_percent: dict[str, Any],
        release_condition: str | None = None,
        evidence: str | None = None,
    ) -> dict[str, int]:
        """Activate a risk override and return the new effective budget."""
        history = _normalize_overrides(self.ledger.get(OVERRIDE_HISTORY_KEY))
        entry = {
            "trigger": trigger,
            "temporary_percent": dict(temporary_percent),
            "released": False,
        }
        if release_condition is not None:
            entry["release_condition"] = release_condition
        if evidence is not None:
            entry["evidence"] = evidence
        history.append(entry)
        self.ledger[OVERRIDE_HISTORY_KEY] = history
        return self.effective_budget()

    def release_override(
        self,
        trigger: str | None = None,
        evidence: str | None = None,
    ) -> dict[str, int]:
        """Release the most recent active override and return the restored budget.

        When ``trigger`` is given, the newest active override with that trigger is
        released; otherwise the newest active override is released.
        """
        history = _normalize_overrides(self.ledger.get(OVERRIDE_HISTORY_KEY))
        for index in range(len(history) - 1, -1, -1):
            entry = history[index]
            if _is_released(entry):
                continue
            if trigger is not None and entry.get("trigger") != trigger:
                continue
            entry["released"] = True
            if evidence is not None:
                entry["evidence"] = evidence
            self.ledger[OVERRIDE_HISTORY_KEY] = history
            return self.effective_budget()
        # Nothing to release — effective budget is already the baseline.
        return self.effective_budget()


# --------------------------------------------------------------------------- #
# LangChain tool factory
# --------------------------------------------------------------------------- #

def create_budget_check_tool(
    name: str = "check_budget_ledger",
    description: str | None = None,
    default_ledger_path: str = "experiments/tube/budget-ledger.json",
    expected_budget: dict[str, Any] | None = None,
    expected_sub_budgets: dict[str, dict[str, Any]] | None = None,
    domain: str = "generic",
) -> Any:
    """Build a LangChain ``StructuredTool`` that audits a budget ledger.

    The returned tool is compatible with domain supervisors (it can be passed to
    ``create_react_agent`` / ``create_supervisor`` tool lists). It accepts an
    optional ``ledger_path`` and returns a JSON audit report as a string.

    Args:
        name: Tool name exposed to the model.
        description: Tool description; auto-generated when omitted.
        default_ledger_path: Path used when the model omits ``ledger_path``.
        expected_budget: Expected ``budget_percent`` distribution to compare against.
        expected_sub_budgets: Expected sub-budget distributions.
        domain: Domain label included in the report.

    Returns:
        A ``StructuredTool`` instance.

    Raises:
        RuntimeError: If ``langchain_core`` is unavailable.
    """
    if StructuredTool is None:
        raise RuntimeError("langchain_core is required to build budget check tools")

    description = description or (
        f"Audit the {domain} discretionary budget ledger. Verifies the budget split "
        "sums to exactly 100 percent, checks every declared sub-budget sums to 100, "
        "and reports any active risk-override distribution. Returns a JSON report."
    )

    def _check_budget_ledger(ledger_path: str = default_ledger_path) -> str:
        manager = BudgetLedgerManager(
            domain=domain,
            baseline_budget=expected_budget,
        )
        report = manager.audit_file(ledger_path, expected_budget, expected_sub_budgets)
        return json.dumps(report, ensure_ascii=False, indent=2, default=str)

    return StructuredTool.from_function(
        func=_check_budget_ledger,
        name=name,
        description=description,
    )
