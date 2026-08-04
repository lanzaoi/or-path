#!/usr/bin/env python3
"""P0-2: Claim map gate — every strong numeric/external claim must map to solution or research evidence.

Not full NLI; enforces traceability contracts used by OR-Path papers:
- objective-like and large numerics ⊆ solution tokens (aligns with R2) OR labeled non-result
- each HTTP(S) URL ⊆ whitelist
- research path / chunk_id / seed id mentioned when knowledge_mode != off and retrieval has ids
- optional structure: if paper states piece_count and board cells, piece_count * 4 >= cells (polyomino sanity)
- builds outputs/.drafts/<slug>-claim-map.json for provenance
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HTTP_URL_RE = re.compile(r"https?://[^\s)\]>\"']+", re.I)
OBJECTIVE_CLAIM_RE = re.compile(
    r"(?i)(?:objective|optimal(?:\s+cost)?|total\s+cost|最短路|目标值|最优(?:值|代价)?)"
    r"\s*[:=是为]?\s*"
    r"([+-]?(?:\d+\.\d+|\d+))"
)
BIG_NUM_RE = re.compile(r"(?<![A-Za-z0-9_/.])([+-]?(?:\d+\.\d+|\d{2,}))(?![A-Za-z0-9_])")
FAKE_CITE_RE = re.compile(
    r"(?<![/\w])([A-Z][\u4e00-\u9fffA-Za-z]{1,12})\s*[（(]?(20\d{2})[)）]?"
)
CHUNK_RE = re.compile(r"\bchunk[_-]?id\b|\b[a-f0-9]{8,}\b", re.I)
# Affirmative global-opt marketing only — honesty disclaimers must not trip the gate.
GLOBAL_OPT_RE = re.compile(
    r"global(?:ly)?\s+optim(?:al|um)\w*|保证全局最优|数学证明最优",
    re.I,
)
_NEG_LEFT_RE = re.compile(
    r"(?:"
    r"\bnot\b|\bnever\b|\bno\b|\bwithout\b|\bavoid\b|\bunless\b|"
    r"\bdo\s+not\b|\bdon'?t\b|\bnon-?|"
    r"禁止|不要|勿|未|非|并非|不|非证明|未证明|无法保证"
    r").{0,48}$",
    re.I | re.S,
)


def affirmative_global_opt_hits(text: str) -> list[str]:
    """Return matched phrases that claim global opt (not negated honesty wording)."""
    hits: list[str] = []
    for m in GLOBAL_OPT_RE.finditer(text or ""):
        left = (text or "")[max(0, m.start() - 56) : m.start()]
        # "not proven global optimum" / "do not claim global optimality" / "if proven_optimal is not true"
        if _NEG_LEFT_RE.search(left):
            continue
        if re.search(r"proven_optimal[`\s:=]*false|proven_optimal[`\s:=]*`?False", left[-40:], re.I):
            continue
        if re.search(r"is\s+not\s+true|is\s+false", left[-36:], re.I):
            continue
        hits.append(m.group(0))
    return hits


def _collect_solution_tokens(obj: Any, out: set[str]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _collect_solution_tokens(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_solution_tokens(v, out)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, int):
        out.add(str(obj))
    elif isinstance(obj, float):
        if obj.is_integer():
            out.add(str(int(obj)))
        out.add(str(obj))
    elif isinstance(obj, str):
        out.add(obj)
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", obj):
            out.add(obj.lstrip("+"))


def _allowed_float(allowed: set[str], f: float) -> bool:
    for a in allowed:
        if re.fullmatch(r"[+-]?(?:\d+\.\d+|\d+)", a):
            try:
                if abs(float(a) - f) < 1e-9:
                    return True
            except ValueError:
                continue
    return False


def _whitelist_urls(path: Path | None) -> set[str]:
    if not path or not path.is_file():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    urls: set[str] = set()

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if str(k).lower() in {"url", "href", "uri", "link"} and isinstance(v, str):
                    urls.add(v.rstrip(".,;"))
                walk(v)
        elif isinstance(o, list):
            for i in o:
                walk(i)
        elif isinstance(o, str) and o.startswith(("http://", "https://", "notes://")):
            urls.add(o.rstrip(".,;"))

    walk(data)
    return urls


def _research_anchors(research_text: str, retrieval: dict[str, Any]) -> set[str]:
    anchors: set[str] = set()
    for h in retrieval.get("hits") or []:
        if h.get("chunk_id"):
            anchors.add(str(h["chunk_id"]))
        if h.get("source_path"):
            anchors.add(str(h["source_path"]))
    for s in retrieval.get("seed_facts") or []:
        if s.get("id"):
            anchors.add(str(s["id"]))
    # paths mentioned in research evidence table
    for m in re.finditer(r"`([^`]+\.(?:md|json|py))`", research_text):
        anchors.add(m.group(1))
    for m in re.finditer(r"fixtures/[^\s|]+", research_text):
        anchors.add(m.group(0))
    return anchors


def build_claim_map(
    draft: str,
    solution: dict[str, Any],
    *,
    whitelist: Path | None = None,
    research_text: str = "",
    retrieval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    retrieval = retrieval or {}
    allowed: set[str] = set()
    _collect_solution_tokens(solution, allowed)
    for i in range(0, 21):
        allowed.add(str(i))

    wl = _whitelist_urls(whitelist)
    anchors = _research_anchors(research_text, retrieval)

    claims: list[dict[str, Any]] = []
    errors: list[str] = []

    # Mask process-meta counters (claims_recorded: N, duration_ms, …) before numeric scan.
    try:
        from r2_numeric_check import mask_non_result_numbers  # same tools/ dir
    except Exception:  # noqa: BLE001
        try:
            from tools.r2_numeric_check import mask_non_result_numbers  # type: ignore
        except Exception:  # noqa: BLE001
            def mask_non_result_numbers(text: str) -> str:  # type: ignore
                return text or ""

    draft_scan = mask_non_result_numbers(draft)

    # objective-like
    for m in OBJECTIVE_CLAIM_RE.finditer(draft_scan):
        num = m.group(1)
        ok = num in allowed or _allowed_float(allowed, float(num))
        claims.append(
            {
                "type": "objective_like",
                "text": m.group(0)[:120],
                "value": num,
                "mapped_to": "solution.json" if ok else None,
                "ok": ok,
            }
        )
        if not ok:
            errors.append(f"objective-like claim not in solution: {num}")

    # large nums (skip years handled loosely)
    for m in BIG_NUM_RE.finditer(draft_scan):
        raw = m.group(1)
        try:
            f = float(raw)
        except ValueError:
            continue
        if 1900 <= f <= 2100 and raw.isdigit() and len(raw) == 4:
            continue
        # skip if already in objective claims
        if any(c.get("value") == raw for c in claims):
            continue
        ok = raw in allowed or _allowed_float(allowed, f)
        # allow tiny counters already in 0-20
        if ok:
            claims.append(
                {
                    "type": "numeric",
                    "text": raw,
                    "value": raw,
                    "mapped_to": "solution_or_small_int",
                    "ok": True,
                }
            )
        else:
            # non-result context markers
            span = draft_scan[max(0, m.start() - 48) : m.end() + 40].lower()
            if any(
                k in span
                for k in (
                    "todo",
                    "placeholder",
                    "n/a",
                    "version",
                    "port",
                    "http",
                    "line",
                    "claims_recorded",
                    "claim_count",
                    "duration_ms",
                    "log_size",
                    "tool_count",
                    "event_count",
                    "meta_counter",
                )
            ):
                claims.append(
                    {
                        "type": "numeric_context",
                        "text": raw,
                        "value": raw,
                        "mapped_to": "context_exempt",
                        "ok": True,
                    }
                )
            else:
                claims.append(
                    {
                        "type": "numeric",
                        "text": raw,
                        "value": raw,
                        "mapped_to": None,
                        "ok": False,
                    }
                )
                errors.append(f"unmapped numeric claim: {raw}")

    # URLs
    for m in HTTP_URL_RE.finditer(draft):
        u = m.group(0).rstrip(".,;)]}>\"'")
        ok = u in wl or u.rstrip("/") in {x.rstrip("/") for x in wl}
        claims.append(
            {
                "type": "url",
                "text": u,
                "mapped_to": "whitelist" if ok else None,
                "ok": ok,
            }
        )
        if not ok:
            errors.append(f"url not in whitelist: {u}")

    # research / retrieval anchors when mode provided evidence
    need = []
    for h in retrieval.get("hits") or []:
        if h.get("chunk_id"):
            need.append(str(h["chunk_id"]))
    for s in retrieval.get("seed_facts") or []:
        if s.get("id"):
            need.append(str(s["id"]))
    if need:
        hit = any(n in draft or n in research_text for n in need)
        claims.append(
            {
                "type": "retrieval_consumption",
                "text": ",".join(need[:5]),
                "mapped_to": "research_or_draft" if hit else None,
                "ok": hit,
            }
        )
        if not hit:
            errors.append("retrieval ids not reflected in draft/research claim surface")

    # polyomino area sanity if both mentioned
    pc = re.search(r"piece(?:_count|s)?\s*[=:]\s*`?(\d+)", draft, re.I)
    cells = re.search(r"(?:n_cells|cells|格子|格数)\s*[=:]\s*`?(\d+)", draft, re.I)
    if pc and cells:
        pcn, cn = int(pc.group(1)), int(cells.group(1))
        ok = pcn * 4 >= cn  # max tetromino
        claims.append(
            {
                "type": "area_sanity",
                "text": f"pieces={pcn} cells={cn}",
                "mapped_to": "structure",
                "ok": ok,
            }
        )
        if not ok:
            errors.append(f"area impossible: pieces*{4} < cells ({pcn}*4 < {cn})")

    # honesty: affirmative global-opt marketing without proven flag
    opt_hits = affirmative_global_opt_hits(draft)
    if opt_hits:
        proven = bool((solution.get("meta") or {}).get("proven_optimal"))
        claims.append(
            {
                "type": "optimality_language",
                "text": "global optimal language: " + "; ".join(opt_hits[:5]),
                "mapped_to": "solution.meta.proven_optimal",
                "ok": proven,
            }
        )
        if not proven:
            errors.append("global-optimal language without solution.meta.proven_optimal")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "claims": claims,
        "anchors_available": sorted(anchors)[:50],
        "solution_objective": solution.get("objective"),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="OR-Path P0 claim map gate")
    p.add_argument("--draft", type=Path, required=True)
    p.add_argument("--solution", type=Path, required=True)
    p.add_argument("--whitelist", type=Path, default=None)
    p.add_argument("--research", type=Path, default=None)
    p.add_argument("--retrieval", type=Path, default=None)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)

    if not args.draft.is_file():
        print(f"FAIL: draft missing {args.draft}", file=sys.stderr)
        return 1
    if not args.solution.is_file():
        print(f"FAIL: solution missing {args.solution}", file=sys.stderr)
        return 1

    draft = args.draft.read_text(encoding="utf-8")
    solution = json.loads(args.solution.read_text(encoding="utf-8"))
    research = args.research.read_text(encoding="utf-8") if args.research and args.research.is_file() else ""
    retrieval = {}
    if args.retrieval and args.retrieval.is_file():
        retrieval = json.loads(args.retrieval.read_text(encoding="utf-8"))

    result = build_claim_map(
        draft,
        solution,
        whitelist=args.whitelist,
        research_text=research,
        retrieval=retrieval,
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not result["ok"]:
        for e in result["errors"]:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print("PASS: claim map")
    print(json.dumps({"claims": len(result["claims"]), "ok": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
