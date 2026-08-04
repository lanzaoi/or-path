#!/usr/bin/env python3
"""Extract zip with Windows long-path support (\\\\?\\ prefix)."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path


def win_long(path: Path) -> str:
    s = str(path)
    if os.name != "nt":
        return s
    s = os.path.abspath(s)
    if s.startswith("\\\\?\\"):
        return s
    if s.startswith("\\\\"):
        # UNC
        return "\\\\?\\UNC\\" + s[2:]
    return "\\\\?\\" + s


def extract_zip(zip_path: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            # normalize
            name = info.filename.replace("\\", "/")
            if name.endswith("/"):
                target = dest / name
                os.makedirs(win_long(target), exist_ok=True)
                continue
            target = dest / name
            parent = target.parent
            os.makedirs(win_long(parent), exist_ok=True)
            with zf.open(info, "r") as src, open(win_long(target), "wb") as out:
                shutil.copyfileobj(src, out, length=1024 * 1024)
    # find top bundle dir
    tops = [p for p in dest.iterdir() if p.is_dir()]
    if len(tops) == 1:
        return tops[0]
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip")
    ap.add_argument("dest")
    args = ap.parse_args(argv)
    root = extract_zip(Path(args.zip), Path(args.dest))
    print(str(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
