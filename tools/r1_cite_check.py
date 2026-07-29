#!/usr/bin/env python3
"""R1: draft HTTP(S) URLs and notes:// ids must be in whitelist."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

HTTP_URL_RE = re.compile(r"https?://[^\s\)\]\>\"']+", re.IGNORECASE)
NOTES_URL_RE = re.compile(r"notes://[^\s\)\]\>\"']+", re.IGNORECASE)


def _collect_whitelist_urls(data: Any) -> set[str]:
    urls: set[str] = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if str(k).lower() in {"url", "href", "uri", "link"} and isinstance(v, str):
                    urls.add(v.rstrip(".,;"))
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, str):
            if obj.startswith(("http://", "https://", "notes://")):
                urls.add(obj.rstrip(".,;"))

    walk(data)
    return urls


def normalize_url(url: str) -> str:
    return url.rstrip(".,;)]}>\"'")


def check_draft(draft: str, allowed: set[str]) -> list[str]:
    errors: list[str] = []
    # HTTP(S) must be in whitelist
    for m in HTTP_URL_RE.finditer(draft):
        u = normalize_url(m.group(0))
        if u not in allowed:
            # also try without trailing slash mismatch
            alt = u.rstrip("/")
            allowed_norm = {a.rstrip("/") for a in allowed}
            if alt not in allowed_norm:
                errors.append(f"http URL not in whitelist: {u}")
    # notes:// ok if in whitelist
    for m in NOTES_URL_RE.finditer(draft):
        u = normalize_url(m.group(0))
        if u not in allowed:
            errors.append(f"notes:// id not in whitelist: {u}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OR-Path R1 citation whitelist check")
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--whitelist", type=Path, required=True)
    args = parser.parse_args(argv)

    if not args.draft.is_file():
        print(f"FAIL: draft not found: {args.draft}", file=sys.stderr)
        return 1
    if not args.whitelist.is_file():
        print(f"FAIL: whitelist not found: {args.whitelist}", file=sys.stderr)
        return 1

    draft = args.draft.read_text(encoding="utf-8")
    with args.whitelist.open(encoding="utf-8") as f:
        wl = json.load(f)
    allowed = _collect_whitelist_urls(wl)
    errors = check_draft(draft, allowed)
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print("PASS: R1 cite check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
