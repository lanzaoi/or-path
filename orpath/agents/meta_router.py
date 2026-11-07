#!/usr/bin/env python3
"""Meta-Router — 10-domain OR problem triage (Task 4.1).

An industrial-grade multi-probe router that classifies any incoming operations
research problem (structured JSON / data dict, problem filename, or free text
description) into one of the 10 canonical OR domains, or into a well-known
composite problem class (LRP / PRP / IRP / Microgrid-Facility).

Probes
------
1. ``schema_sniff``  — recursive signature-key sniffing over structured data
                       (``roster`` + ``shift_demands`` → rostering,
                        ``precedences`` + ``resource_capacities`` → project, ...).
2. ``keyword_tree``  — bilingual (EN/CN) high-precision keyword/regex tree over
                       the filename + text description.
3. ``composite_rule``— recognises canonical composite OR problems:
                       Location-Routing (LRP), Production-Inventory-Routing
                       (PRP), Inventory-Routing (IRP), Microgrid-Facility.
4. ``llm_fallback``  — optional LLM classification when all deterministic
                       probes are inconclusive; falls back to a low-confidence
                       default when no model is configured or the call fails.

Numbers Truth: this module never invents objective values. It only routes
problems to domains; solver outputs remain the single source of truth.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Canonical domain registry
# ---------------------------------------------------------------------------
DOMAIN_TUBE = "tube"
DOMAIN_ROUTING = "routing"
DOMAIN_SCHEDULING = "scheduling"
DOMAIN_PROJECT = "project"
DOMAIN_INVENTORY = "inventory"
DOMAIN_FACILITY = "facility"
DOMAIN_ROSTERING = "rostering"
DOMAIN_MICROGRID = "microgrid"
DOMAIN_PRICING = "pricing"
DOMAIN_FINANCE = "finance"

SUPPORTED_DOMAINS: list[str] = [
    DOMAIN_TUBE,
    DOMAIN_ROUTING,
    DOMAIN_SCHEDULING,
    DOMAIN_PROJECT,
    DOMAIN_INVENTORY,
    DOMAIN_FACILITY,
    DOMAIN_ROSTERING,
    DOMAIN_MICROGRID,
    DOMAIN_PRICING,
    DOMAIN_FINANCE,
]

MATCHED_BY_SCHEMA = "schema_sniff"
MATCHED_BY_KEYWORD = "keyword_tree"
MATCHED_BY_COMPOSITE = "composite_rule"
MATCHED_BY_LLM = "llm_fallback"

# ---------------------------------------------------------------------------
# Probe 1 — schema signatures (exact, case-insensitive key match)
#   strong keys are distinctive (weight 3), weak keys are supportive (weight 1)
# ---------------------------------------------------------------------------
SCHEMA_SIGNATURES: dict[str, dict[str, set[str]]] = {
    DOMAIN_TUBE: {
        "strong": {
            "tubes", "contours", "co_cut", "nesting", "polyomino",
            "stock_lengths", "laser_cut", "chip_layout", "cutting_stock",
            "envelopes",
        },
        "weak": {"width", "perimeter", "cutting", "packing", "waste", "rotation"},
    },
    DOMAIN_ROUTING: {
        "strong": {
            "depot", "routes", "vehicles", "customers", "time_windows",
            "distance_matrix", "tsp", "vrp", "cvrp", "vrptw", "shortest_path",
        },
        "weak": {"demand", "demands", "capacity", "distance", "routing", "delivery"},
    },
    DOMAIN_SCHEDULING: {
        "strong": {
            "jobs", "machines", "processing_times", "operations",
            "setup_times", "jssp", "fjssp", "job_steps", "operators",
        },
        "weak": {"makespan", "duration", "setup", "sequence", "workshop", "gantt"},
    },
    DOMAIN_PROJECT: {
        "strong": {
            "precedences", "resource_capacities", "activities",
            "renewable_resources", "rcpsp", "psplib", "successors", "durations",
        },
        "weak": {"makespan", "resource", "project", "milestone", "gantt"},
    },
    DOMAIN_INVENTORY: {
        "strong": {
            "holding_cost", "setup_cost", "lot_sizing", "inventory",
            "wagner", "clsp", "backorder", "periods",
        },
        "weak": {"demands", "holding", "production", "stock", "eoq"},
    },
    DOMAIN_FACILITY: {
        "strong": {
            "open_facilities", "facility_costs", "fixed_costs", "cost_matrix",
            "cflp", "locations", "transportation_cost", "supply_chain",
        },
        "weak": {"capacities", "demands", "warehouse", "distribution", "site"},
    },
    DOMAIN_ROSTERING: {
        "strong": {
            "shift_demands", "roster", "employees", "shifts", "assignments",
            "staff_rostering", "contracts", "skills",
        },
        "weak": {"days", "workload", "shift", "nurse"},
    },
    DOMAIN_MICROGRID: {
        "strong": {
            "purchase_kwh", "soc_kwh", "prices_q1", "loads_q1_kw", "pv_q1_kw",
            "microgrid", "forecasts_365", "battery", "pv_generation",
        },
        "weak": {"prices", "loads", "kwh", "tou", "tariff", "photovoltaic"},
    },
    DOMAIN_PRICING: {
        "strong": {
            "first_stage_decision", "second_stage_decision", "scenarios",
            "stochastic", "price_elasticity", "demand_curve",
            "yield_management", "dynamic_pricing",
        },
        "weak": {"price", "revenue", "probability", "fare", "fares"},
    },
    DOMAIN_FINANCE: {
        "strong": {
            "cov_matrix", "allocations", "expected_returns", "markowitz",
            "portfolio", "risk_parity", "covariance", "assets",
        },
        "weak": {"returns", "variance", "risk", "investment", "budget"},
    },
}

SCHEMA_STRONG_WEIGHT = 3
SCHEMA_WEAK_WEIGHT = 1
SCHEMA_PRESENT_THRESHOLD = 3  # >= 1 strong key

# ---------------------------------------------------------------------------
# Probe 2 — bilingual keyword tree
#   (domain, pattern, weight); 3 = unique acronym / highly distinctive term
# ---------------------------------------------------------------------------
_KEYWORD_RULES: list[tuple[str, str, int]] = [
    # tube
    (DOMAIN_TUBE, r"\bcutting[-_ ]stock\b", 3),
    (DOMAIN_TUBE, r"\bpolyomino\b", 3),
    (DOMAIN_TUBE, r"\bnesting\b", 3),
    (DOMAIN_TUBE, r"\blaser[-_ ]cut(ting)?\b", 3),
    (DOMAIN_TUBE, r"\btubes?\b", 2),
    (DOMAIN_TUBE, r"套料", 3),
    (DOMAIN_TUBE, r"排样", 3),
    (DOMAIN_TUBE, r"激光切割", 3),
    (DOMAIN_TUBE, r"管材", 2),
    (DOMAIN_TUBE, r"装箱", 2),
    (DOMAIN_TUBE, r"拼板", 2),
    # routing
    (DOMAIN_ROUTING, r"\btsp\b", 3),
    (DOMAIN_ROUTING, r"\bvrp(tw|_tw)?\b", 3),
    (DOMAIN_ROUTING, r"\bcvrp\b", 3),
    (DOMAIN_ROUTING, r"vehicle[-_ ]routing", 3),
    (DOMAIN_ROUTING, r"traveling[-_ ]salesman|travelling[-_ ]salesman", 3),
    (DOMAIN_ROUTING, r"shortest[-_ ]path", 2),
    (DOMAIN_ROUTING, r"\bdepot\b", 2),
    (DOMAIN_ROUTING, r"车辆路径", 3),
    (DOMAIN_ROUTING, r"旅行商", 3),
    (DOMAIN_ROUTING, r"配送路径", 2),
    (DOMAIN_ROUTING, r"最短路径", 2),
    # scheduling
    (DOMAIN_SCHEDULING, r"\bjssp\b", 3),
    (DOMAIN_SCHEDULING, r"\bfjssp\b", 3),
    (DOMAIN_SCHEDULING, r"job[-_ ]shop", 3),
    (DOMAIN_SCHEDULING, r"shop[-_ ]floor", 2),
    (DOMAIN_SCHEDULING, r"车间调度", 3),
    (DOMAIN_SCHEDULING, r"作业车间", 3),
    (DOMAIN_SCHEDULING, r"柔性作业", 3),
    (DOMAIN_SCHEDULING, r"生产排程", 2),
    # project
    (DOMAIN_PROJECT, r"rcpsp", 3),
    (DOMAIN_PROJECT, r"psplib", 3),
    (DOMAIN_PROJECT, r"resource[-_ ]constrained", 3),
    (DOMAIN_PROJECT, r"project[-_ ]scheduling", 3),
    (DOMAIN_PROJECT, r"工程项目调度", 3),
    (DOMAIN_PROJECT, r"项目调度", 3),
    (DOMAIN_PROJECT, r"关键路径", 3),
    (DOMAIN_PROJECT, r"\bmilestone", 1),
    # inventory
    (DOMAIN_INVENTORY, r"wagner[-_ ]whitin", 3),
    (DOMAIN_INVENTORY, r"lot[-_ ]sizing", 3),
    (DOMAIN_INVENTORY, r"dynamic[-_ ]lot", 3),
    (DOMAIN_INVENTORY, r"\bclsp\b", 3),
    (DOMAIN_INVENTORY, r"动态批量", 3),
    (DOMAIN_INVENTORY, r"库存", 2),
    (DOMAIN_INVENTORY, r"批量", 2),
    (DOMAIN_INVENTORY, r"\bbackorder", 2),
    # facility
    (DOMAIN_FACILITY, r"\bcflp\b", 3),
    (DOMAIN_FACILITY, r"facility[-_ ]location", 3),
    (DOMAIN_FACILITY, r"supply[-_ ]chain[-_ ]network", 3),
    (DOMAIN_FACILITY, r"选址", 3),
    (DOMAIN_FACILITY, r"供应链网络", 3),
    (DOMAIN_FACILITY, r"仓库", 2),
    (DOMAIN_FACILITY, r"分销网络", 2),
    (DOMAIN_FACILITY, r"\bwarehouse\b", 1),
    # rostering
    (DOMAIN_ROSTERING, r"staff[-_ ]rostering", 3),
    (DOMAIN_ROSTERING, r"workforce[-_ ]scheduling", 3),
    (DOMAIN_ROSTERING, r"nurse[-_ ]scheduling", 3),
    (DOMAIN_ROSTERING, r"employee[-_ ]scheduling", 3),
    (DOMAIN_ROSTERING, r"排班", 3),
    (DOMAIN_ROSTERING, r"排课", 3),
    (DOMAIN_ROSTERING, r"班次", 2),
    # microgrid
    (DOMAIN_MICROGRID, r"\bmicro[-_ ]?grid\b", 3),
    (DOMAIN_MICROGRID, r"光储充", 3),
    (DOMAIN_MICROGRID, r"微电网", 3),
    (DOMAIN_MICROGRID, r"分时电价", 3),
    (DOMAIN_MICROGRID, r"光储", 3),
    (DOMAIN_MICROGRID, r"光伏发电", 2),
    (DOMAIN_MICROGRID, r"储能", 2),
    # pricing
    (DOMAIN_PRICING, r"yield[-_ ]management", 3),
    (DOMAIN_PRICING, r"dynamic[-_ ]pricing", 3),
    (DOMAIN_PRICING, r"revenue[-_ ]management", 3),
    (DOMAIN_PRICING, r"stochastic[-_ ]programming", 3),
    (DOMAIN_PRICING, r"两阶段随机", 3),
    (DOMAIN_PRICING, r"收益管理", 3),
    (DOMAIN_PRICING, r"动态定价", 3),
    (DOMAIN_PRICING, r"定价", 2),
    # finance
    (DOMAIN_FINANCE, r"markowitz", 3),
    (DOMAIN_FINANCE, r"portfolio[-_ ]optimization", 3),
    (DOMAIN_FINANCE, r"risk[-_ ]parity", 3),
    (DOMAIN_FINANCE, r"asset[-_ ]allocation", 3),
    (DOMAIN_FINANCE, r"投资组合", 3),
    (DOMAIN_FINANCE, r"资产配置", 3),
    (DOMAIN_FINANCE, r"风险平价", 3),
    (DOMAIN_FINANCE, r"\bcovariance\b", 2),
]

KEYWORD_STRONG_WEIGHT = 3
KEYWORD_PRESENT_THRESHOLD = 3


def _compile_keyword(pattern: str) -> re.Pattern[str]:
    """Compile a keyword regex with boundaries that treat ``_`` as a separator.

    Standard ``\b`` treats underscore as a word character, which would break
    filename matching (``nesting_problem`` would not match ``\bnesting\b``).
    """
    p = pattern
    if p.startswith(r"\b"):
        p = r"(?<![A-Za-z0-9])" + p[2:]
    if p.endswith(r"\b"):
        p = p[:-2] + r"(?![A-Za-z0-9])"
    return re.compile(p, re.IGNORECASE)


_KEYWORD_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    (domain, _compile_keyword(pattern), weight)
    for domain, pattern, weight in _KEYWORD_RULES
]

# ---------------------------------------------------------------------------
# Probe 3 — composite problem rules
# ---------------------------------------------------------------------------
COMPOSITE_TEXT_RULES: list[tuple[str, list[str], re.Pattern[str]]] = [
    ("production-inventory-routing", ["scheduling", "inventory", "routing"],
     _compile_keyword(r"production[-_ ]inventory[-_ ]routing|\bprp\b")),
    ("location-routing", ["facility", "routing"],
     _compile_keyword(r"location[-_ ]routing|\blrp\b")),
    ("inventory-routing", ["inventory", "routing"],
     _compile_keyword(r"inventory[-_ ]routing|\birp\b")),
    ("microgrid-facility", ["microgrid", "facility"],
     re.compile(r"microgrid[-_ ]facility|facility[-_ ]microgrid", re.IGNORECASE)),
]

COMPOSITE_SCHEMA_RULES: list[tuple[str, list[str]]] = [
    ("production-inventory-routing", ["scheduling", "inventory", "routing"]),
    ("location-routing", ["facility", "routing"]),
    ("inventory-routing", ["inventory", "routing"]),
    ("microgrid-facility", ["microgrid", "facility"]),
]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class DomainRouteResult:
    """Triage result of the Meta-Router."""

    domain: str
    confidence: float
    is_composite: bool = False
    composite_domains: list[str] = field(default_factory=list)
    matched_by: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        if self.domain not in SUPPORTED_DOMAINS:
            raise ValueError(
                f"domain must be one of {SUPPORTED_DOMAINS}, got {self.domain!r}"
            )
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        if self.is_composite and not self.composite_domains:
            self.composite_domains = [self.domain]
        if not self.is_composite:
            self.composite_domains = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "confidence": round(self.confidence, 4),
            "is_composite": self.is_composite,
            "composite_domains": list(self.composite_domains),
            "matched_by": self.matched_by,
            "rationale": self.rationale,
        }


def get_supported_domains() -> list[str]:
    """Return the 10 canonical OR domains in canonical order."""
    return list(SUPPORTED_DOMAINS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _collect_schema_keys(obj: Any, _limit: int = 4000) -> set[str]:
    """Recursively collect all dict key names (lower-cased) from *obj*.

    Iterative walk (explicit stack) so deeply nested or even cyclic object
    graphs cannot blow the interpreter recursion limit; a ``visited`` set of
    ``id()`` values guarantees termination on reference cycles. Re-visiting the
    same object at multiple tree locations is skipped, which is harmless here
    because keys accumulate into a set.
    """
    keys: set[str] = set()
    visited: set[int] = set()
    budget = [_limit]
    stack: list[Any] = [obj]

    while stack:
        if budget[0] <= 0:
            break
        o = stack.pop()
        budget[0] -= 1
        if id(o) in visited:
            continue
        visited.add(id(o))
        if isinstance(o, Mapping):
            for k, v in o.items():
                if isinstance(k, str):
                    keys.add(k.lower())
                stack.append(v)
        elif isinstance(o, (list, tuple, set, frozenset)):
            stack.extend(o)
        elif isinstance(o, (str, bytes, int, float, bool)) or o is None:
            continue
        elif hasattr(o, "__dict__"):
            try:
                stack.append(vars(o))
            except TypeError:
                continue

    return keys


def _schema_scores(keys: set[str]) -> dict[str, dict[str, Any]]:
    """Score every domain against the collected schema keys."""
    scores: dict[str, dict[str, Any]] = {}
    for domain, sig in SCHEMA_SIGNATURES.items():
        strong = sorted(k for k in sig["strong"] if k in keys)
        weak = sorted(k for k in sig["weak"] if k in keys)
        total = SCHEMA_STRONG_WEIGHT * len(strong) + SCHEMA_WEAK_WEIGHT * len(weak)
        scores[domain] = {
            "strong": strong,
            "weak": weak,
            "score": total,
        }
    return scores


def _keyword_scores(haystack: str) -> dict[str, dict[str, Any]]:
    """Score every domain against filename + text via the keyword tree."""
    scores: dict[str, dict[str, Any]] = {
        d: {"strong": [], "medium": [], "weak": [], "score": 0}
        for d in SUPPORTED_DOMAINS
    }
    if not haystack:
        return scores
    for domain, pattern, weight in _KEYWORD_PATTERNS:
        if pattern.search(haystack):
            bucket = (
                "strong" if weight == KEYWORD_STRONG_WEIGHT
                else "weak" if weight == 1
                else "medium"
            )
            entry = scores[domain][bucket]
            if pattern.pattern not in entry:
                entry.append(pattern.pattern)
                scores[domain]["score"] += weight
    return scores


def _detect_composite(
    present: set[str],
) -> tuple[str, list[str]] | None:
    """Match a composite pattern against the set of strongly present domains."""
    for label, members in COMPOSITE_SCHEMA_RULES:
        if set(members) <= present:
            return label, members
    return None


def _find_text_composite(haystack: str) -> tuple[str, list[str]] | None:
    if not haystack:
        return None
    for label, members, pattern in COMPOSITE_TEXT_RULES:
        if pattern.search(haystack):
            return label, members
    return None


def _schema_confidence(matched: dict[str, Any]) -> float:
    n_strong = len(matched["strong"])
    n_weak = len(matched["weak"])
    return max(0.0, min(0.99, 0.70 + 0.09 * n_strong + 0.05 * n_weak))


def _keyword_confidence(matched: dict[str, Any]) -> float:
    n_strong = len(matched["strong"])
    n_medium = len(matched["medium"])
    n_weak = len(matched["weak"])
    return max(
        0.0,
        min(0.98, 0.55 + 0.13 * n_strong + 0.06 * n_medium + 0.03 * n_weak),
    )


def _parse_json_loose(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object embedded in arbitrary LLM output."""
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
            if isinstance(obj, dict):
                return obj
        except ValueError:
            continue
    return None


def _llm_classify(
    text: str, filename: str, data: Any, model: Any
) -> DomainRouteResult | None:
    """Probe 4 — ask the configured chat model for a domain verdict."""
    if model is None:
        return None
    problem_excerpt = ""
    try:
        if data is not None:
            problem_excerpt = json.dumps(data, ensure_ascii=False, default=str)[:2000]
    except (TypeError, ValueError):
        problem_excerpt = str(data)[:2000]
    prompt = (
        "You are an operations-research domain classifier. "
        "Classify the problem below into exactly ONE of these domains:\n"
        + ", ".join(SUPPORTED_DOMAINS)
        + "\n\n"
        f"filename: {filename or '(none)'}\n"
        f"text: {text[:2000] or '(none)'}\n"
        f"data: {problem_excerpt or '(none)'}\n\n"
        'Reply with a single JSON object: '
        '{"domain": "<one of the listed domains>", '
        '"confidence": <0.0-1.0>, "rationale": "<short reason>"}'
    )
    try:
        if hasattr(model, "invoke"):
            resp = model.invoke([{"role": "user", "content": prompt}])
        elif callable(model):
            resp = model(prompt)
        else:
            return None
        content = getattr(resp, "content", None)
        if content is None:
            content = str(resp)
        parsed = _parse_json_loose(content)
        if not parsed:
            return None
        domain = str(parsed.get("domain", "")).strip().lower()
        if domain not in SUPPORTED_DOMAINS:
            return None
        conf = float(parsed.get("confidence", 0.5))
        rationale = str(parsed.get("rationale", "llm classification"))
        return DomainRouteResult(
            domain=domain,
            confidence=conf,
            matched_by=MATCHED_BY_LLM,
            rationale=f"LLM verdict: {rationale}",
        )
    except Exception:  # noqa: BLE001 — fallback must never crash routing
        return None


def _default_fallback(haystack: str) -> DomainRouteResult:
    """Deterministic low-confidence default when no probe fired."""
    return DomainRouteResult(
        domain=DOMAIN_SCHEDULING,
        confidence=0.2,
        matched_by=MATCHED_BY_LLM,
        rationale=(
            "No deterministic domain signal detected "
            f"(input excerpt: {haystack[:80]!r}); defaulted to the generic "
            "scheduling domain at low confidence."
        ),
    )


# ---------------------------------------------------------------------------
# Probe 4 — main entry
# ---------------------------------------------------------------------------
def route_problem(
    data: Any = None,
    text: str = "",
    filename: str = "",
    model: Any = None,
) -> DomainRouteResult:
    """Classify an OR problem into one of the 10 canonical domains.

    Parameters
    ----------
    data
        Structured payload: dict / Mapping / list / JSON string / pydantic-like
        object. Probe 1 sniffs its key signature.
    text
        Free-text problem description (bilingual keyword probe).
    filename
        Problem file name (bilingual keyword probe + composite marker probe).
    model
        Optional chat model used only when all deterministic probes miss.

    Returns
    -------
    DomainRouteResult
    """
    # --- normalize structured input ---------------------------------------
    if isinstance(data, (str, bytes)):
        raw = data.decode("utf-8", "ignore") if isinstance(data, bytes) else data
        stripped = raw.strip()
        if stripped.startswith(("{", "[")):
            try:
                data = json.loads(stripped)
            except ValueError:
                data = None
        else:
            data = None

    # --- Probe 1: schema sniff --------------------------------------------
    keys = _collect_schema_keys(data) if data is not None else set()
    schema_scores = _schema_scores(keys)

    # --- Probe 2: keyword tree ---------------------------------------------
    haystack = " ".join(part for part in (filename or "", text or "") if part)
    keyword_scores = _keyword_scores(haystack)

    # --- Probe 3a: text composite markers (filename / description) ----------
    text_composite = _find_text_composite(haystack)
    if text_composite is not None:
        label, members = text_composite
        return DomainRouteResult(
            domain=members[0],
            confidence=0.88,
            is_composite=True,
            composite_domains=members,
            matched_by=MATCHED_BY_COMPOSITE,
            rationale=f"Composite problem marker '{label}' matched in input text.",
        )

    # --- Probe 3b: composite from strongly present domains ------------------
    present = {
        d
        for d in SUPPORTED_DOMAINS
        if schema_scores[d]["score"] >= SCHEMA_PRESENT_THRESHOLD
        or keyword_scores[d]["score"] >= KEYWORD_PRESENT_THRESHOLD
    }
    domain_composite = _detect_composite(present)
    if domain_composite is not None:
        label, members = domain_composite
        schema_hit = sum(1 for m in members if schema_scores[m]["score"] >= 3)
        conf = 0.92 if schema_hit == len(members) else 0.85
        return DomainRouteResult(
            domain=members[0],
            confidence=conf,
            is_composite=True,
            composite_domains=members,
            matched_by=MATCHED_BY_COMPOSITE,
            rationale=(
                f"Composite '{label}' detected: "
                + " + ".join(
                    f"{m}(score={schema_scores[m]['score']})" for m in members
                )
            ),
        )

    # --- single-domain decision --------------------------------------------
    schema_top = max(SUPPORTED_DOMAINS, key=lambda d: schema_scores[d]["score"])
    keyword_top = max(SUPPORTED_DOMAINS, key=lambda d: keyword_scores[d]["score"])
    schema_best = schema_scores[schema_top]["score"]
    keyword_best = keyword_scores[keyword_top]["score"]

    if schema_best >= SCHEMA_PRESENT_THRESHOLD:
        conf = _schema_confidence(schema_scores[schema_top])
        rationale = (
            f"Schema sniff matched strong keys "
            f"{schema_scores[schema_top]['strong']} "
            f"and weak keys {schema_scores[schema_top]['weak']}."
        )
        if keyword_top == schema_top and keyword_best >= KEYWORD_PRESENT_THRESHOLD:
            conf = min(0.99, conf + 0.02)
            rationale += " Keyword tree corroborates the same domain."
        return DomainRouteResult(
            domain=schema_top,
            confidence=conf,
            matched_by=MATCHED_BY_SCHEMA,
            rationale=rationale,
        )

    if keyword_best >= KEYWORD_PRESENT_THRESHOLD:
        conf = _keyword_confidence(keyword_scores[keyword_top])
        matched = keyword_scores[keyword_top]
        rationale = (
            f"Keyword tree matched terms from filename/description: "
            f"strong={matched['strong']}, medium={matched['medium']}, "
            f"weak={matched['weak']}."
        )
        return DomainRouteResult(
            domain=keyword_top,
            confidence=conf,
            matched_by=MATCHED_BY_KEYWORD,
            rationale=rationale,
        )

    # --- Probe 4: LLM fallback / default -----------------------------------
    llm_result = _llm_classify(text or "", filename or "", data, model)
    if llm_result is not None:
        return llm_result
    return _default_fallback(haystack)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="orpath.agents.meta_router",
        description="Meta-Router: classify an OR problem into one of 10 domains.",
    )
    parser.add_argument(
        "--data",
        default=None,
        help="JSON file path or inline JSON payload for schema sniffing.",
    )
    parser.add_argument("--text", default="", help="Free-text problem description.")
    parser.add_argument("--filename", default="", help="Problem file name.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    data: Any = None
    if args.data:
        if os.path.exists(args.data):
            with open(args.data, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        else:
            try:
                data = json.loads(args.data)
            except ValueError:
                data = None

    result = route_problem(data=data, text=args.text, filename=args.filename)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
