#!/usr/bin/env python3
"""Guess problem domain from intake filename (Path-A helper)."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("")
        return 0
    s = sys.argv[1]
    n = Path(s).name.lower()
    poly_keys = ("polyomino", "tiling", "guapai", "骨牌", "多联", "覆盖")
    tube_keys = ("tube", "圆管", "bfd", "cutting")
    if any(k.lower() in n or k in s for k in poly_keys):
        print("poly")
        return 0
    if any(k.lower() in n or k in s for k in tube_keys):
        print("tube")
        return 0
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
