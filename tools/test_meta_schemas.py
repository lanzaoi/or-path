"""Meta-schema contract tests for OR-Path domain collaboration contracts and
experiment cards.

contracts/meta/domain_collaboration.schema.json formalizes the meta-schema that
any domain collaboration contract (e.g. contracts/tube_collaboration_v1.json)
must satisfy, while contracts/meta/experiment_card.schema.json generalizes the
single-factor experiment card shape to any OR-Path domain (e.g. the legacy
experiments/tube/cards/*.json and templates/meta-experiment-card.json).

These tests use plain JSON parsing and a focused draft-07 structural validator —
no external jsonschema dependency — so the schema and the tests stay
self-contained.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = ROOT / "contracts"
META_SCHEMA_PATH = CONTRACTS_DIR / "meta" / "domain_collaboration.schema.json"
TUBE_CONTRACT_PATH = CONTRACTS_DIR / "tube_collaboration_v1.json"

DRAFT07_URL = "http://json-schema.org/draft-07/schema#"
META_REQUIRED = [
    "schema",
    "problem_id",
    "numeric_authority",
    "roles",
    "budget_scope",
    "budget_percent",
    "objective_order",
    "candidate_lifecycle",
    "stop_rules",
]

EXPERIMENT_META_SCHEMA_PATH = CONTRACTS_DIR / "meta" / "experiment_card.schema.json"
META_TEMPLATE_PATH = ROOT / "templates" / "meta-experiment-card.json"
TUBE_CARD_TEMPLATE_PATH = ROOT / "templates" / "tube-experiment-card.json"
TUBE_CARD_DIR = ROOT / "experiments" / "tube" / "cards"
TUBE_CARD_SCHEMA_PATH = CONTRACTS_DIR / "tube_experiment_card.schema.json"

EXPERIMENT_META_REQUIRED = [
    "schema",
    "id",
    "domain",
    "status",
    "owner_agent",
    "changed_factor",
    "baseline_artifact",
    "frozen_factors",
    "acceptance",
    "output_path",
    "timeout_sec",
]
META_ALLOWED_STATUS = [
    "PROPOSED",
    "RUNNING",
    "PASSED",
    "FAILED",
    "BLOCKED",
    "SUPERSEDED",
]
META_SCHEMA_PATTERN = r"^orpath\..+_experiment_card\.v[0-9]+$"
TUBE_STATUS_TO_META = {
    "PLANNED": "PROPOSED",
    "RUNNING": "RUNNING",
    "ACCEPTED": "PASSED",
    "REJECTED": "FAILED",
    "ERROR": "FAILED",
    "BLOCKED": "BLOCKED",
    "SUPERSEDED": "SUPERSEDED",
}


def _load(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _type_ok(value, expected: str) -> bool:
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


def _resolve_ref(root, ref: str):
    assert ref.startswith("#/"), f"only local pointer refs supported, got {ref!r}"
    node = root
    for token in ref[2:].split("/"):
        node = node[token]
    return node


def _validate(doc, schema, root, path: str = "$") -> list[str]:
    """Focused draft-07 structural validation (subset used by the meta-schemas).

    Supports the keywords the OR-Path meta-schemas rely on: ``$ref``, ``type``,
    ``enum``, ``const``, ``pattern``, ``required``, ``properties``,
    ``additionalProperties`` (bool or schema), ``items``, ``minItems``,
    ``maxItems``, ``uniqueItems``, ``minimum``, ``maximum``, ``minLength``,
    ``maxLength``, ``not``, ``allOf``, ``anyOf``, ``oneOf``, ``if/then/else`` and
    the project-local ``baselineMustDiffer`` invariant. Unknown keywords are
    ignored, matching standard JSON Schema behaviour.
    """
    errors: list[str] = []
    if "$ref" in schema:
        schema = _resolve_ref(root, schema["$ref"])
    if "type" in schema and not _type_ok(doc, schema["type"]):
        errors.append(f"{path}: expected type {schema['type']!r}, got {type(doc).__name__}")
        return errors
    if "enum" in schema and doc not in schema["enum"]:
        errors.append(f"{path}: {doc!r} is not one of {schema['enum']!r}")
    if "const" in schema and doc != schema["const"]:
        errors.append(f"{path}: {doc!r} is not the const {schema['const']!r}")
    if isinstance(doc, str):
        if "pattern" in schema and not re.search(schema["pattern"], doc):
            errors.append(f"{path}: {doc!r} does not match pattern {schema['pattern']!r}")
        if "minLength" in schema and len(doc) < schema["minLength"]:
            errors.append(f"{path}: {doc!r} shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(doc) > schema["maxLength"]:
            errors.append(f"{path}: {doc!r} longer than maxLength {schema['maxLength']}")
    if isinstance(doc, (int, float)) and not isinstance(doc, bool):
        if "minimum" in schema and doc < schema["minimum"]:
            errors.append(f"{path}: {doc!r} < minimum {schema['minimum']}")
        if "maximum" in schema and doc > schema["maximum"]:
            errors.append(f"{path}: {doc!r} > maximum {schema['maximum']}")
    if isinstance(doc, list):
        if "minItems" in schema and len(doc) < schema["minItems"]:
            errors.append(f"{path}: {len(doc)} items < minItems {schema['minItems']}")
        if "maxItems" in schema and len(doc) > schema["maxItems"]:
            errors.append(f"{path}: {len(doc)} items > maxItems {schema['maxItems']}")
        if schema.get("uniqueItems") and len(doc) != len(
            {json.dumps(item, sort_keys=True, default=str) for item in doc}
        ):
            errors.append(f"{path}: items are not unique")
        if "items" in schema:
            for index, item in enumerate(doc):
                errors.extend(_validate(item, schema["items"], root, f"{path}[{index}]"))
    if isinstance(doc, dict):
        for key in schema.get("required", []):
            if key not in doc:
                errors.append(f"{path}: missing required key {key!r}")
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in doc:
                errors.extend(_validate(doc[key], subschema, root, f"{path}.{key}"))
        additional = schema.get("additionalProperties")
        if additional is False:
            for key in doc:
                if key not in properties:
                    errors.append(f"{path}: additional property {key!r} not allowed")
        elif isinstance(additional, dict):
            for key in doc:
                if key in properties:
                    continue
                errors.extend(_validate(doc[key], additional, root, f"{path}.{key}"))
    if "not" in schema and _validate(doc, schema["not"], root, path) == []:
        errors.append(f"{path}: value matches a forbidden subschema")
    for subschema in schema.get("allOf", []):
        errors.extend(_validate(doc, subschema, root, path))
    for combinator in ("anyOf", "oneOf"):
        subschemas = schema.get(combinator, [])
        if not subschemas:
            continue
        matches = [_validate(doc, sub, root, path) == [] for sub in subschemas]
        if combinator == "anyOf" and not any(matches):
            errors.append(f"{path}: does not match any allowed subschema")
        if combinator == "oneOf" and sum(matches) != 1:
            errors.append(f"{path}: matches {sum(matches)} subschemas, expected exactly one")
    if "if" in schema:
        if _validate(doc, schema["if"], root, path) == [] and "then" in schema:
            errors.extend(_validate(doc, schema["then"], root, path))
        elif "else" in schema:
            errors.extend(_validate(doc, schema["else"], root, path))
    if schema.get("baselineMustDiffer") and isinstance(doc, dict):
        if "baseline" in doc and "candidate" in doc and doc["baseline"] == doc["candidate"]:
            errors.append(f"{path}: baseline and candidate must differ")
    return errors


def _meta_schema() -> dict:
    return _load(META_SCHEMA_PATH)


def _tube_contract() -> dict:
    return _load(TUBE_CONTRACT_PATH)


def _tampered(mutate) -> dict:
    doc = _tube_contract()
    mutate(doc)
    return doc


# --- experiment card meta-schema helpers -----------------------------------


def _experiment_meta_schema() -> dict:
    return _load(EXPERIMENT_META_SCHEMA_PATH)


def _meta_template() -> dict:
    return _load(META_TEMPLATE_PATH)


def _tube_card_paths() -> list[Path]:
    return sorted(TUBE_CARD_DIR.glob("*.json")) + [TUBE_CARD_TEMPLATE_PATH]


def _canonicalize_legacy_tube_card(doc: dict) -> dict:
    """Map a legacy Tube card onto the canonical meta-experiment-card shape.

    Legacy Tube cards use ``experiment_id`` plus a ``budget`` object and a
    different status vocabulary. The meta schema is the forward-looking
    canonical contract, so the test adapter maps those legacy names onto the
    canonical ``id`` / ``timeout_sec`` fields before validation. Domain extras
    (hypothesis, seed_set, budget, experiment_id) remain allowed because the
    meta schema sets ``additionalProperties: true`` at the top level.
    """
    canonical = dict(doc)
    if "id" not in canonical and "experiment_id" in canonical:
        canonical["id"] = canonical["experiment_id"]
    if "timeout_sec" not in canonical:
        budget = canonical.get("budget")
        value = budget.get("value") if isinstance(budget, dict) else budget
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            canonical["timeout_sec"] = value
    status = canonical.get("status")
    if status in TUBE_STATUS_TO_META:
        canonical["status"] = TUBE_STATUS_TO_META[status]
    return canonical


def _validate_tube_card(doc: dict, schema: dict) -> list[str]:
    """Small structural check against the legacy Tube card schema."""
    errors: list[str] = []
    for key in schema.get("required", []):
        if key not in doc:
            errors.append(f"missing required key {key!r}")
    if doc.get("schema") != schema.get("schema"):
        errors.append(f"invalid schema id: {doc.get('schema')!r}")
    if doc.get("domain") not in schema.get("domains", []):
        errors.append(f"invalid domain: {doc.get('domain')!r}")
    if doc.get("status") not in schema.get("allowed_status", []):
        errors.append(f"invalid status: {doc.get('status')!r}")
    changed = doc.get("changed_factor")
    if not isinstance(changed, dict):
        errors.append("changed_factor must be an object")
    else:
        if set(changed) != {"name", "baseline", "candidate"}:
            errors.append(
                "changed_factor keys must be exactly name/baseline/candidate "
                f"(got {sorted(changed)})"
            )
        elif changed.get("baseline") == changed.get("candidate"):
            errors.append("changed_factor baseline and candidate must differ")
    for key in ("baseline_artifact", "frozen_factors", "acceptance", "output_path"):
        if not doc.get(key):
            errors.append(f"{key} must be non-empty")
    return errors


def _tampered_meta(mutate) -> dict:
    doc = _meta_template()
    mutate(doc)
    return doc


# --- meta-schema file itself ------------------------------------------------


def test_meta_schema_file_wellformed():
    schema = _meta_schema()
    assert schema["$schema"] == DRAFT07_URL
    assert schema["type"] == "object"
    assert schema["required"] == META_REQUIRED
    assert schema["properties"]["schema"]["pattern"] == "^orpath\\..+_collaboration\\.v[0-9]+$"
    assert schema["definitions"]["role"]["required"] == ["owns", "forbidden"]
    # selection_rule is a typed property but NOT a required key (per contract)
    assert schema["properties"]["selection_rule"]["type"] == "string"
    assert "selection_rule" not in schema["required"]


def test_meta_schema_pattern_matches_domain_contract_ids():
    pattern = _meta_schema()["properties"]["schema"]["pattern"]
    for good in (
        "orpath.tube_collaboration.v1",
        "orpath.microgrid_collaboration.v2",
        "orpath.polyomino_collaboration.v9",
    ):
        assert re.search(pattern, good), good
    for bad in (
        "tube_collaboration.v1",             # missing orpath. prefix
        "orpath.tube_collaboration.vX",      # non-numeric version
        "orpath.collaboration.v1",           # missing domain
        "orpath.tube_collaboration.v1.2",    # dotted version
        "orpath.tube_collaboration",         # missing .vN
    ):
        assert not re.search(pattern, bad), bad


# --- happy path -------------------------------------------------------------


def test_tube_contract_validates_against_meta_schema():
    schema = _meta_schema()
    doc = _tube_contract()
    errors = _validate(doc, schema, schema)
    assert errors == [], errors
    # the tube contract carries domain-specific extras; additionalProperties must allow them
    extras = set(doc) - set(schema["properties"])
    assert {"risk_override", "handoff_order", "experiment_rules", "registry"} <= extras


def test_minimal_valid_contract_with_extras_passes():
    schema = _meta_schema()
    doc = {
        "schema": "orpath.microgrid_collaboration.v2",
        "problem_id": "microgrid_dispatch",
        "numeric_authority": "local_solver_and_independent_validator",
        "objective_order": ["hard_constraints", "cost"],
        "budget_scope": "experiment_effort",
        "budget_percent": {"lp": 50, "mpc": 50},
        "roles": {
            "or-microgrid-lead": {"owns": ["ledger"], "forbidden": ["agent_vote"]}
        },
        "candidate_lifecycle": ["PROPOSED", "ACCEPTED"],
        "stop_rules": {"dispatch": ["stop_after_two_levels"]},
        "domain_specific_extra": {"any": [1, 2, 3]},
    }
    errors = _validate(doc, schema, schema)
    assert errors == [], errors


def test_selection_rule_optional_but_typed():
    schema = _meta_schema()
    doc = _tube_contract()
    doc.pop("selection_rule")
    assert _validate(doc, schema, schema) == []
    doc["selection_rule"] = 42
    assert _validate(doc, schema, schema) != []


# --- tampering -------------------------------------------------------------


def test_missing_required_field_rejected():
    schema = _meta_schema()
    for field in META_REQUIRED:
        doc = _tampered(lambda d, f=field: d.pop(f))
        errors = _validate(doc, schema, schema)
        assert errors, f"expected rejection when required field {field!r} removed"
        assert any(f"missing required key {field!r}" in e for e in errors)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema="tube_collaboration.v1"),
        lambda d: d.update(schema="orpath.tube_collaboration.vX"),
        lambda d: d.update(schema=123),
        lambda d: d.update(problem_id=None),
        lambda d: d.update(numeric_authority=7),
        lambda d: d.update(budget_scope=7),
        lambda d: d.update(objective_order="hard_constraints"),
        lambda d: d.update(objective_order=["hard_constraints", 7]),
        lambda d: d["budget_percent"].update(geometry="twenty"),
        lambda d: d["budget_percent"].update(geometry=20.5),
        lambda d: d["budget_percent"].update(geometry=True),
        lambda d: d.update(roles=[]),
        lambda d: d["roles"]["or-tube-lead"].pop("owns"),
        lambda d: d["roles"]["or-tube-q4"].pop("forbidden"),
        lambda d: d["roles"]["or-tube-redteam"].clear(),
        lambda d: d["roles"]["or-tube-q3"].update(owns="joint_packing_candidates"),
        lambda d: d["roles"]["or-tube-q1q2"].update(forbidden=[3]),
        lambda d: d.update(candidate_lifecycle="PROPOSED"),
        lambda d: d.update(candidate_lifecycle=[None]),
        lambda d: d["stop_rules"].update(geometry="compare_180_360_720_profiles_on_identical_input_hashes"),
        lambda d: d["stop_rules"].update(q3=["stop", 42]),
        lambda d: d["stop_rules"].update(q4={}),
    ],
    ids=[
        "schema-missing-prefix",
        "schema-bad-version",
        "schema-wrong-type",
        "problem-id-wrong-type",
        "numeric-authority-wrong-type",
        "budget-scope-wrong-type",
        "objective-order-not-array",
        "objective-order-non-string-item",
        "budget-percent-string-value",
        "budget-percent-float-value",
        "budget-percent-bool-value",
        "roles-not-object",
        "role-missing-owns",
        "role-missing-forbidden",
        "role-missing-both",
        "role-owns-not-array",
        "role-forbidden-non-string-item",
        "candidate-lifecycle-not-array",
        "candidate-lifecycle-non-string-item",
        "stop-rules-value-not-array",
        "stop-rules-non-string-item",
        "stop-rules-value-wrong-type",
    ],
)
def test_tampered_contract_rejected(mutate):
    schema = _meta_schema()
    doc = _tampered(mutate)
    errors = _validate(doc, schema, schema)
    assert errors, f"tampered contract unexpectedly validated: {mutate}"


# --- validator self-checks --------------------------------------------------


def test_validator_type_semantics():
    # bool must not pass as integer; int must pass as integer
    assert _type_ok(5, "integer") and not _type_ok(True, "integer")
    assert not _type_ok(20.5, "integer")
    assert _type_ok("x", "string") and not _type_ok(7, "string")
    assert _type_ok([], "array") and _type_ok({}, "object")


# --- experiment card meta-schema --------------------------------------------


def test_experiment_meta_schema_wellformed():
    schema = _experiment_meta_schema()
    assert schema["$schema"] == DRAFT07_URL
    assert schema["type"] == "object"
    assert schema["required"] == EXPERIMENT_META_REQUIRED
    assert schema["properties"]["schema"]["pattern"] == META_SCHEMA_PATTERN
    assert schema["properties"]["status"]["enum"] == META_ALLOWED_STATUS
    changed = schema["definitions"]["changed_factor"]
    assert changed["required"] == ["name", "baseline", "candidate"]
    assert changed["additionalProperties"] is False
    assert changed["baselineMustDiffer"] is True


def test_meta_schema_pattern_matches_domain_card_ids():
    pattern = _experiment_meta_schema()["properties"]["schema"]["pattern"]
    for good in (
        "orpath.tube_experiment_card.v1",
        "orpath.microgrid_experiment_card.v2",
        "orpath.polyomino_experiment_card.v9",
        "orpath.meta_experiment_card.v1",
    ):
        assert re.search(pattern, good), good
    for bad in (
        "tube_experiment_card.v1",          # missing orpath. prefix
        "orpath.tube_experiment_card.vX",   # non-numeric version
        "orpath.experiment_card.v1",        # missing domain segment
        "orpath.tube_experiment_card.v1.2", # dotted version
        "orpath.tube_experiment_card",      # missing .vN
    ):
        assert not re.search(pattern, bad), bad


def test_meta_template_validates_against_meta_schema():
    schema = _experiment_meta_schema()
    doc = _meta_template()
    errors = _validate(doc, schema, schema)
    assert errors == [], errors


def test_meta_template_has_clean_placeholders():
    doc = _meta_template()
    assert doc["schema"] == "orpath.meta_experiment_card.v1"
    assert doc["id"].startswith("meta-")
    assert doc["status"] in META_ALLOWED_STATUS
    assert doc["owner_agent"]
    assert doc["changed_factor"]["name"]
    assert doc["changed_factor"]["baseline"] != doc["changed_factor"]["candidate"]
    assert doc["frozen_factors"]
    assert doc["acceptance"]
    assert doc["timeout_sec"] > 0
    # every required key is present with a usable placeholder
    assert set(EXPERIMENT_META_REQUIRED) <= set(doc)


def test_meta_template_uses_canonical_field_names():
    doc = _meta_template()
    assert "id" in doc and "timeout_sec" in doc
    # the forward-looking canonical card does not lean on legacy names
    assert "experiment_id" not in doc


# --- existing Tube cards (regression) ---------------------------------------


@pytest.mark.parametrize("card_path", _tube_card_paths(), ids=lambda p: p.name)
def test_existing_tube_cards_validate_against_meta_schema(card_path):
    schema = _experiment_meta_schema()
    doc = _canonicalize_legacy_tube_card(_load(card_path))
    errors = _validate(doc, schema, schema)
    assert errors == [], errors


@pytest.mark.parametrize("card_path", _tube_card_paths(), ids=lambda p: p.name)
def test_existing_tube_cards_validate_against_tube_schema(card_path):
    schema = _load(TUBE_CARD_SCHEMA_PATH)
    errors = _validate_tube_card(_load(card_path), schema)
    assert errors == [], errors


# --- meta-template tampering ------------------------------------------------


def test_meta_template_missing_required_field_rejected():
    schema = _experiment_meta_schema()
    for field in EXPERIMENT_META_REQUIRED:
        doc = _tampered_meta(lambda d, f=field: d.pop(f))
        errors = _validate(doc, schema, schema)
        assert errors, f"expected rejection when required field {field!r} removed"
        assert any(f"missing required key {field!r}" in e for e in errors)


@pytest.mark.parametrize(
    "status",
    META_ALLOWED_STATUS,
    ids=["proposed", "running", "passed", "failed", "blocked", "superseded"],
)
def test_allowed_statuses_accepted(status):
    schema = _experiment_meta_schema()
    doc = _meta_template()
    doc["status"] = status
    assert _validate(doc, schema, schema) == []


@pytest.mark.parametrize(
    "status",
    ["PLANNED", "ACCEPTED", "REJECTED", "ERROR", "DONE", "", None, 7],
    ids=["legacy-planned", "legacy-accepted", "legacy-rejected", "legacy-error", "unknown", "empty", "null", "int"],
)
def test_invalid_status_rejected(status):
    schema = _experiment_meta_schema()
    doc = _meta_template()
    doc["status"] = status
    errors = _validate(doc, schema, schema)
    assert errors, f"expected rejection for invalid status {status!r}"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["changed_factor"].pop("name"),
        lambda d: d["changed_factor"].pop("baseline"),
        lambda d: d["changed_factor"].pop("candidate"),
        lambda d: d["changed_factor"].update(extra=1),
        lambda d: d["changed_factor"].update(note="nope"),
        lambda d: d["changed_factor"].update(name=""),
        lambda d: d["changed_factor"].update(name=7),
        lambda d: d.update(changed_factor=[]),
        lambda d: d.update(changed_factor="beam_width"),
        lambda d: d.update(changed_factor=None),
        lambda d: d["changed_factor"].update(baseline=d["changed_factor"]["candidate"]),
        lambda d: d["changed_factor"].update(candidate=d["changed_factor"]["baseline"]),
        lambda d: d.update(frozen_factors=[]),
        lambda d: d.update(frozen_factors="input_sha256"),
        lambda d: d.update(timeout_sec=0),
        lambda d: d.update(timeout_sec=-5),
        lambda d: d.update(timeout_sec=30.0),
        lambda d: d.update(timeout_sec="600"),
        lambda d: d.update(timeout_sec=True),
        lambda d: d.update(id=""),
        lambda d: d.update(owner_agent=""),
        lambda d: d.update(domain=""),
        lambda d: d.update(baseline_artifact=""),
        lambda d: d.update(output_path=""),
        lambda d: d.update(schema="experiment_card.v1"),
        lambda d: d.update(schema=123),
        lambda d: d.update(acceptance="none"),
        lambda d: d.update(acceptance=[]),
    ],
    ids=[
        "cf-missing-name",
        "cf-missing-baseline",
        "cf-missing-candidate",
        "cf-extra-key",
        "cf-extra-note",
        "cf-empty-name",
        "cf-name-not-string",
        "cf-not-object-list",
        "cf-not-object-string",
        "cf-not-object-null",
        "cf-baseline-equals-candidate",
        "cf-candidate-equals-baseline",
        "frozen-empty",
        "frozen-not-array",
        "timeout-zero",
        "timeout-negative",
        "timeout-float",
        "timeout-string",
        "timeout-bool",
        "id-empty",
        "owner-empty",
        "domain-empty",
        "baseline-artifact-empty",
        "output-path-empty",
        "schema-bad-pattern",
        "schema-wrong-type",
        "acceptance-not-object",
        "acceptance-not-object-list",
    ],
)
def test_tampered_meta_card_rejected(mutate):
    schema = _experiment_meta_schema()
    doc = _tampered_meta(mutate)
    errors = _validate(doc, schema, schema)
    assert errors, f"tampered card unexpectedly validated: {mutate}"


# --- validator extension self-checks ----------------------------------------


def test_experiment_validator_keyword_extensions():
    # enum / type
    enum_schema = {"type": "string", "enum": ["A", "B"]}
    assert _validate("A", enum_schema, enum_schema) == []
    assert _validate("C", enum_schema, enum_schema) != []
    assert _validate(7, enum_schema, enum_schema) != []

    # minimum / maximum
    num_schema = {"type": "integer", "minimum": 1, "maximum": 9}
    assert _validate(5, num_schema, num_schema) == []
    assert _validate(0, num_schema, num_schema) != []
    assert _validate(10, num_schema, num_schema) != []

    # additionalProperties: false
    strict = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"a": {"type": "string"}},
    }
    assert _validate({"a": "x"}, strict, strict) == []
    assert _validate({"a": "x", "b": "y"}, strict, strict) != []

    # baselineMustDiffer custom invariant
    differ = {
        "type": "object",
        "baselineMustDiffer": True,
        "properties": {"baseline": {}, "candidate": {}},
    }
    assert _validate({"baseline": 1, "candidate": 2}, differ, differ) == []
    assert _validate({"baseline": 1, "candidate": 1}, differ, differ) != []

    # minItems
    arr_schema = {"type": "array", "minItems": 1}
    assert _validate(["x"], arr_schema, arr_schema) == []
    assert _validate([], arr_schema, arr_schema) != []
