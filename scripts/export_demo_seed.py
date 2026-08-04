#!/usr/bin/env python3
"""Export lean demo seeds from a workdir into demo/seed/<slug>/."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_ROOT = ROOT / "demo" / "seed"

# Never copy these names anywhere in the tree
BAN_NAMES = {".env", ".env.local", "backend.env"}
BAN_PARTS = {".agents", "node_modules", ".venv", ".venv-314", "__pycache__"}

OUTPUT_GLOBS = {
    "m0": [
        "outputs/m0-*",
        "outputs/m0.*",
        "notes/m0-*",
        "runs/m0/**/*",
    ],
    "live-btube": [
        "outputs/live-btube-*",
        "outputs/live-btube.*",
        "notes/live-btube-*",
        "papers/live-btube*",
        "runs/live-btube/**/*",
    ],
}


def _banned(path: Path) -> bool:
    if path.name in BAN_NAMES:
        return True
    parts = set(path.parts)
    if parts & BAN_PARTS:
        return True
    if path.suffix.lower() in {".pem", ".key"}:
        return True
    return False


def _expand_globs(workdir: Path, patterns: list[str]) -> list[Path]:
    found: list[Path] = []
    for pat in patterns:
        if "**" in pat:
            # pathlib rglob from parent
            head, _, tail = pat.partition("/**/")
            base = workdir / head
            if not base.exists():
                continue
            if tail == "*" or tail == "":
                for p in base.rglob("*"):
                    if p.is_file() and not _banned(p):
                        found.append(p)
            else:
                for p in base.rglob(tail):
                    if p.is_file() and not _banned(p):
                        found.append(p)
        else:
            for p in workdir.glob(pat):
                if p.is_file() and not _banned(p):
                    found.append(p)
                elif p.is_dir():
                    for f in p.rglob("*"):
                        if f.is_file() and not _banned(f):
                            found.append(f)
    # unique preserve order
    seen: set[Path] = set()
    out: list[Path] = []
    for p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def export_slug(workdir: Path, slug: str, out_root: Path) -> dict:
    patterns = OUTPUT_GLOBS.get(slug)
    if not patterns:
        raise SystemExit(f"unknown slug: {slug} (known: {sorted(OUTPUT_GLOBS)})")
    dest = out_root / slug
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    files = _expand_globs(workdir, patterns)
    copied = 0
    bytes_ = 0
    for src in files:
        rel = src.relative_to(workdir)
        # skip agents even if pattern slipped
        if ".agents" in rel.parts:
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied += 1
        bytes_ += target.stat().st_size
    meta = {
        "slug": slug,
        "source_workdir": str(workdir),
        "files": copied,
        "bytes": bytes_,
    }
    (dest / "SEED_META.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return meta


def check_seed(seed_root: Path) -> int:
    errors: list[str] = []
    for slug in ("m0", "live-btube"):
        d = seed_root / slug
        if not d.is_dir():
            errors.append(f"missing {d}")
            continue
        # must not contain banned
        for p in d.rglob("*"):
            if p.is_file() and _banned(p):
                errors.append(f"banned file in seed: {p}")
            if p.is_dir() and p.name == ".agents":
                errors.append(f"banned dir in seed: {p}")
        if slug == "m0":
            if not any(d.glob("outputs/m0-solution.json")) and not (
                d / "outputs" / "m0-solution.json"
            ).is_file():
                # path is dest/outputs/...
                sol = d / "outputs" / "m0-solution.json"
                if not sol.is_file():
                    errors.append("m0 missing outputs/m0-solution.json")
        if slug == "live-btube":
            sol = d / "outputs" / "live-btube-solution.json"
            runs = d / "runs" / "live-btube"
            if not sol.is_file():
                errors.append("live-btube missing outputs/live-btube-solution.json")
            if not runs.is_dir():
                errors.append("live-btube missing runs/live-btube/")
    if errors:
        print("FAIL export_demo_seed --check")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PASS export_demo_seed --check")
    for slug in ("m0", "live-btube"):
        d = seed_root / slug
        n = sum(1 for _ in d.rglob("*") if _.is_file())
        b = sum(_.stat().st_size for _ in d.rglob("*") if _.is_file())
        print(f"  {slug}: {n} files, {b} bytes")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Export OR-Path demo seeds")
    p.add_argument("--slug", choices=sorted(OUTPUT_GLOBS) + ["all"], default=None)
    p.add_argument("--from-workdir", type=Path, default=None, help="source workdir (default ORPATH_WORKDIR or repo root)")
    p.add_argument("--out", type=Path, default=SEED_ROOT)
    p.add_argument("--check", action="store_true", help="validate demo/seed only")
    args = p.parse_args(argv)

    if args.check:
        return check_seed(args.out)

    if not args.slug:
        p.error("--slug required unless --check")

    import os

    work = args.from_workdir
    if work is None:
        work = Path(os.environ.get("ORPATH_WORKDIR") or os.environ.get("ORPATH_HOME") or ROOT)
    work = work.resolve()

    slugs = list(OUTPUT_GLOBS) if args.slug == "all" else [args.slug]
    for s in slugs:
        meta = export_slug(work, s, args.out.resolve())
        print(f"OK {s}: {meta['files']} files, {meta['bytes']} bytes -> {args.out / s}")
    return check_seed(args.out.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
