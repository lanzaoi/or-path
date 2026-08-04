#!/usr/bin/env python3
"""Pack L2 half-fat release zip: source + runtime/node_modules + demo/seed."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PI_CLI = ROOT / "runtime/node_modules/@earendil-works/pi-coding-agent/dist/cli.js"

INCLUDE_TOP = [
    "VERSION",
    "README.md",
    "ORPATH.md",
    "AGENTS.md",
    "IDEA.md",
    "requirements.txt",
    ".env.example",
    "orpath.env.example",
    "orpath.bat",
    "orpath.sh",
    "pi.bat",
    "pi.sh",
    "START-WATCH.bat",
    "START-CASE.bat",
    "START-ORPATH.bat",
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
    "docs",
    "demo",
    ".pi",
    "runtime",
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
    "node_modules",  # handled specially under runtime/
    "inbox",
    "dist",
    ".pi-subagents",
    "data",
    "models",
    "mineru_models",
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


def iter_files(root: Path, *, include_runtime_nm: bool) -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE_TOP:
        p = root / name
        if p.is_file():
            files.append(p)

    for dname in INCLUDE_DIRS:
        base = root / dname
        if not base.exists():
            continue
        if dname == "runtime":
            # package.json etc always; node_modules optional
            for p in base.rglob("*"):
                if not p.is_file():
                    continue
                rel_parts = p.relative_to(base).parts
                if rel_parts and rel_parts[0] == "node_modules":
                    if not include_runtime_nm:
                        continue
                if any(should_skip_dir(x) for x in p.relative_to(root).parts if x != "node_modules"):
                    # allow node_modules only under runtime
                    if "node_modules" not in p.parts:
                        continue
                if p.name in EXCLUDE_FILE_NAMES:
                    continue
                if p.suffix == ".pyc":
                    continue
                files.append(p)
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
            # never pack .pi/npm caches
            if ".pi" in parts and "npm" in parts:
                continue
            if ".pi" in parts and "memory" in parts:
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


def ensure_node_modules(root: Path, allow_npm: bool) -> bool:
    if PI_CLI.is_file():
        return True
    if not allow_npm:
        return False
    npm = shutil.which("npm")
    if not npm:
        return False
    print("==> npm ci in runtime/")
    r = subprocess.run([npm, "ci"], cwd=str(root / "runtime"))
    if r.returncode != 0:
        r = subprocess.run([npm, "install"], cwd=str(root / "runtime"))
    return PI_CLI.is_file()


def pack(root: Path, dist: Path, platform: str, allow_npm: bool) -> Path:
    ver = read_version(root)
    sha = git_sha(root)
    has_nm = ensure_node_modules(root, allow_npm=allow_npm)
    if not has_nm:
        raise SystemExit(
            "[ERROR] runtime Pi CLI missing. Run: cd runtime && npm ci\n"
            "Or pack on a machine that already has node_modules."
        )

    folder_name = f"orpath-{ver}-{platform}"
    files = iter_files(root, include_runtime_nm=True)

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
        "has_node_modules": True,
        "seed_slugs": ["m0", "live-btube"],
        "pi_cli": str(PI_CLI.relative_to(root)).replace("\\", "/"),
        "file_count": len(files) + len(extras) + 1,
    }

    zip_path = dist / f"{folder_name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    print(f"==> zipping {zip_path.name} ({len(files)} files + meta)…")
    # Stream into zip (avoid Windows MAX_PATH on staged node_modules tree)
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
    ap.add_argument("--no-npm", action="store_true", help="do not run npm if node_modules missing")
    args = ap.parse_args(argv)

    args.dist.mkdir(parents=True, exist_ok=True)
    pack(ROOT, args.dist.resolve(), args.platform, allow_npm=not args.no_npm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
