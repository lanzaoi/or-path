#!/usr/bin/env python3
"""Online R1: verify arXiv / DOI identifiers mentioned in draft exist (HTTP)."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import httpx

ARXIV_RE = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:)(\d{4}\.\d{4,5})(v\d+)?", re.I
)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.I)


def check_arxiv(arxiv_id: str) -> tuple[bool, str]:
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        r = httpx.get(url, timeout=30.0)
        ok = r.status_code == 200 and arxiv_id in r.text and "<entry>" in r.text
        return ok, f"status={r.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def check_doi(doi: str) -> tuple[bool, str]:
    url = f"https://doi.org/{doi}"
    try:
        r = httpx.get(url, timeout=30.0, follow_redirects=True)
        ok = r.status_code < 400
        return ok, f"status={r.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--draft", type=Path, required=True)
    args = p.parse_args(argv)
    text = args.draft.read_text(encoding="utf-8")
    arx = sorted({m.group(1) for m in ARXIV_RE.finditer(text)})
    dois = sorted(set(DOI_RE.findall(text)))
    if not arx and not dois:
        print("FAIL: no arXiv/DOI found in draft for online R1", file=sys.stderr)
        return 1
    errors = []
    for a in arx:
        ok, msg = check_arxiv(a)
        print(f"arxiv:{a} -> {ok} {msg}")
        if not ok:
            errors.append(f"arxiv {a}: {msg}")
    for d in dois:
        ok, msg = check_doi(d)
        print(f"doi:{d} -> {ok} {msg}")
        if not ok:
            errors.append(f"doi {d}: {msg}")
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print("PASS: R1 online")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
