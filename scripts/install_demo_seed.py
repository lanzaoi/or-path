#!/usr/bin/env python3
"""Copy demo/seed/<slug>/ trees into ORPATH_WORKDIR (merge, no overwrite by default)."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_ROOT = ROOT / "demo" / "seed"
DEFAULT_SLUGS = ("m0", "live-btube")


def _home() -> Path:
    return Path(os.environ.get("ORPATH_HOME") or ROOT).resolve()


def _workdir() -> Path:
    return Path(os.environ.get("ORPATH_WORKDIR") or _home()).resolve()


def install_seeds(
    seed_root: Path,
    workdir: Path,
    slugs: tuple[str, ...] = DEFAULT_SLUGS,
    force: bool = False,
) -> dict[str, int]:
    stats = {"copied": 0, "skipped": 0, "slugs": 0}
    if not seed_root.is_dir():
        print(f"[WARN] no seed root: {seed_root}")
        return stats

    for slug in slugs:
        src_root = seed_root / slug
        if not src_root.is_dir():
            print(f"[WARN] seed missing: {src_root}")
            continue
        stats["slugs"] += 1
        for src in src_root.rglob("*"):
            if not src.is_file():
                continue
            if src.name == "SEED_META.json":
                continue
            rel = src.relative_to(src_root)
            dst = workdir / rel
            if dst.exists() and not force:
                stats["skipped"] += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            stats["copied"] += 1
    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Install OR-Path demo seeds into workdir")
    p.add_argument("--seed-root", type=Path, default=None)
    p.add_argument("--workdir", type=Path, default=None)
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    p.add_argument("--slug", action="append", dest="slugs", default=None)
    args = p.parse_args(argv)

    seed_root = (args.seed_root or (_home() / "demo" / "seed")).resolve()
    workdir = (args.workdir or _workdir()).resolve()
    slugs = tuple(args.slugs) if args.slugs else DEFAULT_SLUGS

    print(f"install_demo_seed")
    print(f"  seed_root = {seed_root}")
    print(f"  workdir   = {workdir}")
    print(f"  slugs     = {slugs}")
    print(f"  force     = {args.force}")

    workdir.mkdir(parents=True, exist_ok=True)
    st = install_seeds(seed_root, workdir, slugs=slugs, force=args.force)
    print(f"  copied={st['copied']} skipped={st['skipped']} slugs_ok={st['slugs']}")
    if st["slugs"] == 0:
        print("[WARN] no seeds installed")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
