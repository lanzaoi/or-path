"""Resolve OR-Path install home vs case workdir (relocatable installs).

## Path contract (M1 Part 1)

| Symbol | Env | Meaning |
|--------|-----|---------|
| **home** (`orpath_home`) | `ORPATH_HOME` | Install root: package, `tools/`, `fixtures/`, `.pi/` |
| **workdir** (`orpath_workdir`) | `ORPATH_WORKDIR` | Case data root: `outputs/`, `notes/`, `papers/`, `runs/` |

Defaults: both resolve to the directory that contains the `orpath` package
when env is unset (single-tree developer layout).

**Rules:**

1. Artifact writers and Watch L0 must use **workdir**, never assume cwd.
2. Fixture packs and `tools/*.py` adapters resolve from **home** (and may
   fall back to workdir only if a copy exists there).
3. Call `apply_workdir(...)` at process entry so `ORPATH_WORKDIR` and
   layout dirs stay aligned with CLI `--workdir` / `--root`.
4. Pi agent *definitions* stay under home `.pi/agents`; lead logs for a
   case live under `workdir/outputs/.agents/<slug>/`.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# Package lives at <home>/orpath/paths.py → parents[1] == install root
_DEFAULT_HOME = Path(__file__).resolve().parents[1]

# Git-bash / MSYS often mangles Windows paths into:
#   /c/Users/...  or  C:\c\Users\...  (double drive)
_MSYS_POSIX = re.compile(r"^[/\\]([A-Za-z])[/\\](.*)$")
_DOUBLE_DRIVE = re.compile(
    r"^([A-Za-z]:)[/\\]+[A-Za-z][/\\]+((?:Users|users|home)[/\\].+)$"
)


def normalize_fs_path(path: Path | str) -> Path:
    """Normalize user/CLI paths from cmd, PowerShell, or git-bash/MSYS.

    Fixes the common agent footgun where bash passes ``/c/Users/...`` and the
    Windows process ends up writing under ``C:\\c\\Users\\...``.
    """
    s = str(path).strip().strip('"').strip("'")
    if not s:
        return Path(s)
    s = s.replace("/", "\\") if "\\" in s or re.match(r"^[A-Za-z]:", s) else s
    # Prefer explicit POSIX-MSYS form first: /c/Users/foo or \c\Users\foo
    m = _MSYS_POSIX.match(s.replace("\\", "/"))
    if m and not re.match(r"^[A-Za-z]:", s):
        drive, rest = m.group(1).upper(), m.group(2).replace("/", "\\")
        s = f"{drive}:\\{rest}"
    else:
        # C:\c\Users\... → C:\Users\...
        m2 = _DOUBLE_DRIVE.match(s.replace("/", "\\"))
        if m2:
            s = f"{m2.group(1)}\\{m2.group(2).replace('/', chr(92))}"
    return Path(s)


def _resolve_user_path(raw: str | Path) -> Path:
    return normalize_fs_path(raw).expanduser().resolve()

# Relative dirs that must exist under a case workdir
ARTIFACT_DIR_RELS: tuple[str, ...] = (
    "outputs",
    "notes",
    "papers",
    "runs",
    "outputs/.plans",
    "outputs/.drafts",
    "outputs/.agents",
)


def orpath_home() -> Path:
    """Install root: env ORPATH_HOME, else directory containing this package."""
    raw = (os.environ.get("ORPATH_HOME") or "").strip().strip('"')
    if raw:
        return _resolve_user_path(raw)
    return _DEFAULT_HOME


def orpath_workdir() -> Path:
    """Case data directory (notes, outputs, papers, runs). Defaults to home."""
    raw = (os.environ.get("ORPATH_WORKDIR") or "").strip().strip('"')
    if raw:
        return _resolve_user_path(raw)
    return orpath_home()


def resolve_workdir(path: Path | str | None = None) -> Path:
    """Resolve an explicit path or fall back to ``orpath_workdir()``."""
    if path is None:
        return orpath_workdir()
    s = str(path).strip().strip('"').strip("'")
    if not s:
        return orpath_workdir()
    return _resolve_user_path(s)


def ensure_workdir_layout(workdir: Path | None = None) -> Path:
    """Create standard artifact subdirs under workdir; return resolved workdir."""
    wd = resolve_workdir(workdir)
    for rel in ARTIFACT_DIR_RELS:
        (wd / rel).mkdir(parents=True, exist_ok=True)
    return wd


def apply_workdir(path: Path | str | None = None) -> Path:
    """Set ``ORPATH_WORKDIR`` env, ensure layout, return resolved workdir.

    Call once at CLI entry (run / watch / watch-run) so child code and
    ``build_snapshot`` see the same case directory.
    """
    wd = resolve_workdir(path)
    os.environ["ORPATH_WORKDIR"] = str(wd)
    return ensure_workdir_layout(wd)


def install_tools_dir(home: Path | None = None) -> Path:
    """``<home>/tools`` — adapter scripts and gates."""
    return (home or orpath_home()) / "tools"


def resolve_tools_dir(root: Path | None = None, home: Path | None = None) -> Path:
    """Prefer ``root/tools`` if present, else install home tools."""
    home_p = home or orpath_home()
    if root is not None:
        cand = Path(root) / "tools"
        if cand.is_dir():
            return cand
    return install_tools_dir(home_p)


def fixture_search_roots(
    root: Path | None = None, home: Path | None = None
) -> list[Path]:
    """Ordered unique roots to search for ``fixtures/t*/<problem_id>``."""
    home_p = (home or orpath_home()).resolve()
    out: list[Path] = []
    for p in (root, home_p):
        if p is None:
            continue
        rp = Path(p).resolve()
        if rp not in out:
            out.append(rp)
    return out


def pi_settings_path(home: Path | None = None) -> Path:
    return (home or orpath_home()) / ".pi" / "settings.json"


def agents_dir(home: Path | None = None) -> Path:
    """Pi agent *definitions* (install), not per-case lead logs."""
    return (home or orpath_home()) / ".pi" / "agents"


def case_agents_dir(workdir: Path | None = None, slug: str = "") -> Path:
    """Per-case subagent lead logs: ``workdir/outputs/.agents/<slug>``."""
    wd = resolve_workdir(workdir)
    base = wd / "outputs" / ".agents"
    return base / slug if slug else base
