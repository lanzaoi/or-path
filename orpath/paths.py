"""Resolve OR-Path install home and optional workdir (relocatable installs)."""
from __future__ import annotations

import os
from pathlib import Path

# Package lives at <home>/orpath/paths.py → parents[1] == install root
_DEFAULT_HOME = Path(__file__).resolve().parents[1]


def orpath_home() -> Path:
    """Install root: env ORPATH_HOME, else directory containing this package."""
    raw = (os.environ.get("ORPATH_HOME") or "").strip().strip('"')
    if raw:
        return Path(raw).expanduser().resolve()
    return _DEFAULT_HOME


def orpath_workdir() -> Path:
    """User data / case directory (notes, outputs, papers). Defaults to home."""
    raw = (os.environ.get("ORPATH_WORKDIR") or "").strip().strip('"')
    if raw:
        return Path(raw).expanduser().resolve()
    return orpath_home()


def ensure_workdir_layout(workdir: Path | None = None) -> Path:
    wd = workdir or orpath_workdir()
    for rel in ("outputs", "notes", "papers", "runs", "outputs/.plans"):
        (wd / rel).mkdir(parents=True, exist_ok=True)
    return wd


def pi_settings_path(home: Path | None = None) -> Path:
    return (home or orpath_home()) / ".pi" / "settings.json"


def agents_dir(home: Path | None = None) -> Path:
    return (home or orpath_home()) / ".pi" / "agents"
