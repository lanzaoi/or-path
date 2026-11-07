#!/usr/bin/env python3
"""Pack L2 release zip: source + core solvers + validators + demo/seed."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INCLUDE_TOP = [
    "VERSION",
    "README.md",
    "ORPATH.md",
    "AGENTS.md",
    "requirements.txt",
    ".env.example",
    "orpath.env.example",
    "orpath.bat",
    "orpath.sh",
    "START.bat",
    "START.sh",
    ".gitignore",
]

INCLUDE_DIRS = [
    "orpath",
    "tools",
    "scripts",
    "specs",
    "fixtures",
    "contracts",
    "templates",
    "knowledge_svc",
    "knowledge",
    "docs",
    "demo",
    "experiments",
]

EXCLUDE_DIR_NAMES = {
    ".git",
    ".venv",
    ".venv-314",
    "__pycache__",
    ".pytest_cache",
    ".hermes",
    "vendor",
    "pi-main",
    "openpi",
    "node_modules",
    "inbox",
    "dist",
    ".pi",
    ".pi-subagents",
    "runtime",
    "data",
    "models",
    "mineru_models",
    "tasks",
    "archive",
}

# Only skip these when they are top-level workdir dirs (not demo/seed/**)
TOP_LEVEL_SKIP = {"outputs", "notes", "papers", "runs"}

EXCLUDE_FILE_NAMES = {
    ".env",
    ".env.local",
    "backend.env",
    "nul",
}


def read_version(root: Path) -> str:
    vf = root / "VERSION"
    if vf.is_file():
        return vf.read_text(encoding="utf-8").strip()
    return "0.0.0-dev"


def git_sha(root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except OSError:
        pass
    return "unknown"


def should_skip_dir(name: str) -> bool:
    return name in EXCLUDE_DIR_NAMES or name.endswith(".egg-info")


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE_TOP:
        p = root / name
        if p.is_file():
            files.append(p)

    for dname in INCLUDE_DIRS:
        base = root / dname
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(root)
            parts = rel.parts
            if parts and parts[0] in TOP_LEVEL_SKIP:
                continue
            if any(should_skip_dir(x) for x in parts):
                continue
            if p.name in EXCLUDE_FILE_NAMES:
                continue
            if p.suffix == ".pyc":
                continue
            files.append(p)

    # unique
    seen: set[Path] = set()
    out: list[Path] = []
    for f in files:
        rf = f.resolve()
        if rf not in seen:
            seen.add(rf)
            out.append(f)
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pack(root: Path, dist: Path, platform: str) -> Path:
    ver = read_version(root)
    sha = git_sha(root)

    folder_name = f"orpath-{ver}-{platform}"
    files = iter_files(root)

    # Extra top-level install scripts inside the archive root folder
    extras: list[tuple[Path, str]] = []
    for rel in ("scripts/install/install.ps1", "scripts/install/install.sh"):
        src = root / rel
        if src.is_file():
            extras.append((src, f"{folder_name}/{Path(rel).name}"))

    meta = {
        "name": "or-path",
        "version": ver,
        "git_sha": sha,
        "platform": platform,
        "packed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed_slugs": ["m0", "live-btube"],
        "file_count": len(files) + len(extras) + 1,
    }

    zip_path = dist / f"{folder_name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    print(f"==> zipping {zip_path.name} ({len(files)} files + meta)…")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(
            f"{folder_name}/package-meta.json",
            json.dumps(meta, indent=2) + "\n",
        )
        for src in files:
            rel = src.relative_to(root).as_posix()
            arc = f"{folder_name}/{rel}"
            try:
                zf.write(src, arcname=arc)
            except OSError as exc:
                print(f"[WARN] skip {rel}: {exc}")
        for src, arc in extras:
            zf.write(src, arcname=arc)

    digest = sha256_file(zip_path)
    sums = dist / "SHA256SUMS"
    line = f"{digest}  {zip_path.name}\n"
    prev = ""
    if sums.is_file():
        prev_lines = [
            ln
            for ln in sums.read_text(encoding="utf-8").splitlines()
            if not ln.strip().endswith(zip_path.name)
        ]
        prev = "\n".join(prev_lines) + ("\n" if prev_lines else "")
    sums.write_text(prev + line, encoding="utf-8")

    # also copy install.ps1 next to zip for Release upload convenience
    ps1 = root / "scripts" / "install" / "install.ps1"
    if ps1.is_file():
        shutil.copy2(ps1, dist / "install.ps1")

    mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"OK packed {zip_path} ({mb:.1f} MiB)")
    print(f"SHA256 {digest}")
    print(f"meta {meta}")
    return zip_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pack OR-Path L2 release zip")
    ap.add_argument("--platform", default="win-x64", choices=["win-x64", "linux-x64", "darwin-arm64"])
    ap.add_argument("--dist", type=Path, default=ROOT / "dist")
    ap.add_argument("--no-npm", action="store_true", help="legacy no-op flag kept for compatibility")
    args = ap.parse_args(argv)

    args.dist.mkdir(parents=True, exist_ok=True)
    pack(ROOT, args.dist.resolve(), args.platform)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
