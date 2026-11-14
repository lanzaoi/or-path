#!/usr/bin/env python3
"""Pure-Python workspace coding tools for OR-Path agents.

Provides controlled file inspection, editing, search, directory listing, and
shell execution grounded in the active case workdir (``ORPATH_WORKDIR``),
replicating coding-agent autonomy natively inside Python without subprocess
Node wrappers.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, tool

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "tools"
for _p in (str(REPO_ROOT), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ALLOWED_WRITE_SUBDIRS: frozenset[str] = frozenset(
    {"outputs", "notes", "papers", "custom_solvers", "inbox", "runs"}
)
FORBIDDEN_WRITE_DIRS: frozenset[str] = frozenset(
    {
        "orpath",
        "tools",
        "scripts",
        "knowledge",
        "knowledge_svc",
        "contracts",
        "fixtures",
        ".git",
        ".venv",
        "__pycache__",
    }
)

_SKIP_SCAN_DIRS: frozenset[str] = frozenset({".git", ".venv", "__pycache__", "node_modules"})
_BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".xlsx", ".xlsm", ".docx", ".sqlite", ".db", ".pyc", ".pyo", ".onnx"}
)
_DESTRUCTIVE_CMD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:^|[;&|\s])rm\s+-[^\s]*[rf][^\s]*\s+/(?:\s|$)", re.I),
    re.compile(r"\bgit\s+reset\s+--hard\b", re.I),
    re.compile(r"\bgit\s+checkout\s+--\b", re.I),
    re.compile(r"\bgit\s+clean\b", re.I),
    re.compile(r"\bmkfs(?:\.\w+)?\b", re.I),
    re.compile(r"\bdd\s+if=", re.I),
    re.compile(r"\b(?:shutdown|reboot|poweroff|halt)\b", re.I),
)


def _json(payload: dict[str, Any]) -> str:
    """Serialize tool output deterministically."""
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _resolve_root() -> Path:
    """Resolve active case workdir (honouring ORPATH_WORKDIR) or fall back to cwd."""
    raw = (os.environ.get("ORPATH_WORKDIR") or "").strip().strip('"')
    if raw:
        try:
            from orpath.paths import orpath_home

            raw_path = Path(raw).expanduser().resolve()
            home_path = orpath_home().resolve()
            cwd_path = Path.cwd().resolve()
            # If ORPATH_WORKDIR was polluted with home but cwd is an isolated test/case dir, prefer cwd.
            if raw_path == home_path and cwd_path != home_path:
                return cwd_path
            return raw_path
        except Exception:
            return Path(raw).expanduser().resolve()
    return Path.cwd().resolve()


def _resolve_safe_write_path(file_path: str) -> tuple[Path | None, str]:
    """Validate and resolve a writable target path strictly inside the case workdir."""
    raw = str(file_path or "").strip()
    if not raw:
        return None, "file_path must not be empty"

    norm_raw = raw.replace("\\", "/")
    if ".." in norm_raw.split("/") or ".." in Path(raw).parts:
        return None, f"path traversal ('..') is forbidden: {file_path!r}"

    root = _resolve_root().resolve()
    cand = Path(raw).expanduser()
    target = cand.resolve() if cand.is_absolute() else (root / raw).resolve()

    try:
        rel = target.relative_to(root)
    except ValueError:
        return None, f"path escapes workdir {root}: {file_path!r}"

    if not rel.parts:
        return None, "cannot overwrite the workdir root itself"

    top = rel.parts[0]
    if top in FORBIDDEN_WRITE_DIRS:
        return None, f"writing into protected directory {top!r} is forbidden"
    if len(rel.parts) >= 2 and top not in ALLOWED_WRITE_SUBDIRS:
        return None, (
            f"writing into subdirectory {top!r} is not in allowlist "
            f"{sorted(ALLOWED_WRITE_SUBDIRS)}"
        )
    if target.exists() and target.is_dir():
        return None, f"target path is an existing directory: {target}"
    return target, ""


def _resolve_read_file(file_path: str) -> Path | None:
    """Resolve an existing readable file against workdir and repo knowledge/skills."""
    raw = str(file_path or "").strip()
    if not raw:
        return None
    root = _resolve_root().resolve()
    cand = Path(raw).expanduser()
    if cand.is_absolute():
        return cand if cand.is_file() else None

    name = Path(raw).name
    candidates = [
        root / raw,
        root / "inbox" / name,
        root / "outputs" / name,
        root / "notes" / name,
        root / "papers" / name,
        root / "custom_solvers" / name,
        root / "fixtures" / raw,
        REPO_ROOT / "knowledge" / "skills" / raw,
    ]
    norm_raw = raw.replace("\\", "/").lstrip("./")
    if norm_raw.startswith(("knowledge/", "tools/", "contracts/", "docs/", "specs/")):
        candidates.append(REPO_ROOT / norm_raw)

    for c in candidates:
        if c.is_file():
            return c
    return None


def _resolve_search_base(path: str) -> tuple[Path | None, Path]:
    """Resolve directory or file base for grep_search / list_files."""
    root = _resolve_root().resolve()
    raw = str(path or ".").strip() or "."
    norm_raw = raw.replace("\\", "/")
    cand = Path(raw).expanduser()

    if cand.is_absolute():
        resolved = cand.resolve()
        try:
            resolved.relative_to(root)
            return resolved, root
        except ValueError:
            try:
                resolved.relative_to(REPO_ROOT.resolve())
                return resolved, REPO_ROOT.resolve()
            except ValueError:
                return None, root

    if ".." in norm_raw.split("/"):
        return None, root

    in_workdir = (root / raw).resolve()
    if in_workdir.exists():
        try:
            in_workdir.relative_to(root)
            return in_workdir, root
        except ValueError:
            return None, root

    stripped = norm_raw.lstrip("./")
    if stripped.startswith(("knowledge", "tools")):
        in_repo = (REPO_ROOT / stripped).resolve()
        try:
            in_repo.relative_to(REPO_ROOT.resolve())
            if in_repo.exists():
                return in_repo, REPO_ROOT.resolve()
        except ValueError:
            return None, root

    return None, root


@tool
def read_file(file_path: str, offset: int = 1, limit: int = 200) -> str:
    """Read a workspace or knowledge file with 1-based line pagination.

    Supports plain text / code / JSON / CSV / Markdown and structured office / PDF
    documents (``.docx``, ``.xlsx``, ``.xlsm``, ``.pdf`` via ``intake_assets``).

    Args:
        file_path: Workdir-relative or absolute path to read.
        offset: 1-based starting line number (default 1).
        limit: Maximum number of lines to return (1..2000, default 200).

    Returns:
        Formatted header (file_path, total_lines, showing_lines, has_more) plus
        numbered lines ``<line_no>: <content>``.
    """
    try:
        start = max(1, int(offset))
    except (TypeError, ValueError):
        start = 1
    try:
        count = max(1, min(int(limit), 2000))
    except (TypeError, ValueError):
        count = 200

    resolved = _resolve_read_file(file_path)
    if resolved is None:
        return f"file_path={file_path}\nerror=file_not_found"

    suf = resolved.suffix.lower()
    try:
        if suf in {".docx", ".xlsx", ".xlsm", ".pdf"}:
            from tools.intake_assets import extract_asset_text

            text, _pages, _warns = extract_asset_text(resolved, max_chars=200_000)
        else:
            text = resolved.read_bytes().decode("utf-8", errors="replace")
    except PermissionError:
        return f"file_path={resolved}\nerror=permission_denied"
    except IsADirectoryError:
        return f"file_path={resolved}\nerror=is_a_directory"
    except Exception as exc:  # noqa: BLE001
        return f"file_path={resolved}\nerror={type(exc).__name__}: {exc}"

    all_lines = text.splitlines()
    total = len(all_lines)
    if total == 0:
        return (
            f"file_path={resolved}\n"
            "total_lines=0 showing_lines=0-0 has_more=false\n"
            "---\n"
        )

    idx_start = start - 1
    if idx_start >= total:
        return (
            f"file_path={resolved}\n"
            f"total_lines={total} showing_lines={total + 1}-{total} has_more=false\n"
            "---\n"
        )

    slice_lines = all_lines[idx_start : idx_start + count]
    end = start + len(slice_lines) - 1
    has_more = (idx_start + len(slice_lines)) < total
    numbered = [f"{ln}: {txt}" for ln, txt in enumerate(slice_lines, start=start)]
    return "\n".join(
        [
            f"file_path={resolved}",
            f"total_lines={total} showing_lines={start}-{end} has_more={str(has_more).lower()}",
            "---",
            *numbered,
        ]
    )


@tool
def write_file(file_path: str, content: str) -> str:
    """Create or overwrite a text file inside allowlisted case workdir folders.

    Allowed subdirectories: ``outputs/``, ``notes/``, ``papers/``,
    ``custom_solvers/``, ``inbox/``, ``runs/``. Repository source folders
    (``orpath/``, ``tools/``, ``scripts/``, etc.) cannot be modified.

    Args:
        file_path: Relative or workdir-contained absolute target file path.
        content: Complete UTF-8 text content to write.

    Returns:
        JSON string with ``success``, ``path``, ``bytes``, ``lines`` (or ``detail``).
    """
    target, err = _resolve_safe_write_path(file_path)
    if target is None:
        return _json({"success": False, "detail": err})
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        data = str(content if content is not None else "")
        target.write_text(data, encoding="utf-8")
        return _json(
            {
                "success": True,
                "path": str(target),
                "bytes": target.stat().st_size,
                "lines": len(data.splitlines()),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _json({"success": False, "detail": f"{type(exc).__name__}: {exc}"})


@tool
def edit_file(file_path: str, old_text: str, new_text: str) -> str:
    """Replace one unique exact substring inside an allowlisted workdir file.

    Enforces unique match so partial edits never overwrite unexpected regions.
    Call ``read_file`` first if unsure of surrounding context.

    Args:
        file_path: Workdir-contained target file path.
        old_text: Non-empty exact substring occurring exactly once in the file.
        new_text: Replacement string.

    Returns:
        JSON string with ``success``, ``path``, ``bytes``, ``occurrences`` (or ``detail``).
    """
    target, err = _resolve_safe_write_path(file_path)
    if target is None:
        return _json({"success": False, "detail": err})
    if not target.is_file():
        return _json({"success": False, "detail": f"file not found: {target}"})
    if not old_text:
        return _json({"success": False, "detail": "old_text must not be empty"})

    try:
        existing = target.read_text(encoding="utf-8", errors="replace")
        occurrences = existing.count(old_text)
        if occurrences == 0:
            return _json(
                {
                    "success": False,
                    "detail": "old_text not found in file; call read_file first to check exact contents",
                }
            )
        if occurrences > 1:
            return _json(
                {
                    "success": False,
                    "occurrences": occurrences,
                    "detail": (
                        "old_text matched multiple locations; include more surrounding lines "
                        "for a unique match"
                    ),
                }
            )
        updated = existing.replace(old_text, str(new_text), 1)
        target.write_text(updated, encoding="utf-8")
        return _json(
            {
                "success": True,
                "path": str(target),
                "bytes": target.stat().st_size,
                "occurrences": 1,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _json({"success": False, "detail": f"{type(exc).__name__}: {exc}"})


@tool
def grep_search(pattern: str, path: str = ".", max_hits: int = 50) -> str:
    """Search text files under the case workdir (or repo knowledge/tools) by regex.

    Args:
        pattern: Case-insensitive Python regex pattern (falls back to literal on syntax error).
        path: Directory or file under workdir (or ``knowledge/...``, ``tools/...``).
        max_hits: Maximum matching lines returned (1..200, default 50).

    Returns:
        JSON string with ``success``, ``pattern``, ``count``, and ``hits``.
    """
    if not pattern:
        return _json({"success": False, "detail": "pattern must not be empty", "count": 0, "hits": []})

    target, base_root = _resolve_search_base(path)
    if target is None:
        return _json({"success": False, "detail": f"invalid or missing path: {path!r}", "count": 0, "hits": []})

    try:
        cap = max(1, min(int(max_hits), 200))
    except (TypeError, ValueError):
        cap = 50

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        regex = re.compile(re.escape(pattern), re.IGNORECASE)

    hits: list[dict[str, Any]] = []

    def _scan_file(fp: Path) -> None:
        if len(hits) >= cap or fp.suffix.lower() in _BINARY_EXTENSIONS:
            return
        try:
            rel = fp.resolve().relative_to(base_root).as_posix()
        except ValueError:
            rel = str(fp)
        try:
            text = fp.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            return
        for lineno, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                hits.append({"file": rel, "line": lineno, "text": line[:240]})
                if len(hits) >= cap:
                    return

    if target.is_file():
        _scan_file(target)
    else:
        for dirpath, dirnames, filenames in os.walk(target):
            dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_SCAN_DIRS)
            for fname in sorted(filenames):
                _scan_file(Path(dirpath) / fname)
                if len(hits) >= cap:
                    break
            if len(hits) >= cap:
                break

    return _json({"success": True, "pattern": pattern, "count": len(hits), "hits": hits})


@tool
def list_files(path: str = ".", pattern: str = "*", max_entries: int = 200) -> str:
    """List files and directories under the case workdir (or repo knowledge).

    Args:
        path: Directory under workdir (or ``knowledge/...`` / ``tools/...``). Defaults to ``"."``.
        pattern: Glob pattern applied to entry name or relative path (default ``"*"``).
        max_entries: Maximum entries to return (1..500, default 200).

    Returns:
        JSON string with ``success``, ``path``, ``count``, and ``entries``.
    """
    target, base_root = _resolve_search_base(path)
    if target is None:
        return _json({"success": False, "detail": f"invalid or missing path: {path!r}", "count": 0, "entries": []})

    try:
        cap = max(1, min(int(max_entries), 500))
    except (TypeError, ValueError):
        cap = 200

    glob_pat = str(pattern or "*").strip() or "*"
    entries: list[dict[str, Any]] = []

    if target.is_file():
        try:
            rel = target.resolve().relative_to(base_root).as_posix()
        except ValueError:
            rel = str(target)
        entries.append({"path": rel, "type": "file", "size": target.stat().st_size})
        return _json({"success": True, "path": str(target), "count": 1, "entries": entries})

    for dirpath, dirnames, filenames in os.walk(target):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_SCAN_DIRS)
        cur_dir = Path(dirpath)
        for dname in dirnames:
            if len(entries) >= cap:
                break
            dp = cur_dir / dname
            try:
                rel = dp.resolve().relative_to(base_root).as_posix()
            except ValueError:
                rel = str(dp)
            if fnmatch.fnmatch(dname, glob_pat) or fnmatch.fnmatch(rel, glob_pat):
                entries.append({"path": rel, "type": "dir", "size": 0})
        for fname in sorted(filenames):
            if len(entries) >= cap:
                break
            fp = cur_dir / fname
            try:
                rel = fp.resolve().relative_to(base_root).as_posix()
            except ValueError:
                rel = str(fp)
            if fnmatch.fnmatch(fname, glob_pat) or fnmatch.fnmatch(rel, glob_pat):
                try:
                    fsize = fp.stat().st_size
                except OSError:
                    fsize = 0
                entries.append({"path": rel, "type": "file", "size": fsize})
        if len(entries) >= cap:
            break

    return _json({"success": True, "path": str(target), "count": len(entries), "entries": entries})


@tool
def run_shell(command: str, timeout_sec: int = 180) -> str:
    """Execute a controlled shell command inside the active case workdir.

    Automatically injects ``ORPATH_WORKDIR`` and puts the active Python
    interpreter's ``bin/`` directory first on ``PATH``. Rejects destructive commands.

    Args:
        command: Shell command string to execute in ``root``.
        timeout_sec: Positive wall-clock timeout in seconds (default 180).

    Returns:
        JSON string with ``success``, ``returncode``, ``stdout``, ``stderr``,
        ``timed_out``, ``timeout_sec``.
    """
    cmd = str(command or "").strip()
    if not cmd:
        return _json(
            {
                "success": False,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "detail": "command must not be empty",
            }
        )
    for pat in _DESTRUCTIVE_CMD_PATTERNS:
        if pat.search(cmd):
            return _json(
                {
                    "success": False,
                    "returncode": None,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                    "detail": f"command blocked by safety guard ({pat.pattern})",
                }
            )

    try:
        timeout = int(timeout_sec)
    except (TypeError, ValueError):
        return _json(
            {
                "success": False,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "detail": f"timeout_sec must be an int, got {timeout_sec!r}",
            }
        )
    if timeout <= 0:
        return _json(
            {
                "success": False,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "detail": f"timeout_sec must be > 0, got {timeout}",
            }
        )

    root = _resolve_root().resolve()
    env = dict(os.environ)
    env["ORPATH_WORKDIR"] = str(root)
    py_bin = str(Path(sys.executable).resolve().parent)
    existing_path = env.get("PATH", "")
    env["PATH"] = f"{py_bin}{os.pathsep}{existing_path}" if existing_path else py_bin

    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return _json(
            {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "")[-16000:],
                "stderr": (proc.stderr or "")[-16000:],
                "timed_out": False,
                "timeout_sec": timeout,
            }
        )
    except subprocess.TimeoutExpired as exc:
        out_s = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", errors="replace")
        err_s = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="replace")
        return _json(
            {
                "success": False,
                "returncode": None,
                "stdout": out_s[-16000:],
                "stderr": err_s[-16000:],
                "timed_out": True,
                "timeout_sec": timeout,
                "detail": f"shell command timed out after {timeout}s",
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _json(
            {
                "success": False,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "timeout_sec": timeout,
                "detail": f"{type(exc).__name__}: {exc}",
            }
        )


CODING_TOOLS: tuple[BaseTool, ...] = (
    read_file,
    write_file,
    edit_file,
    grep_search,
    list_files,
    run_shell,
)

__all__ = [
    "ALLOWED_WRITE_SUBDIRS",
    "FORBIDDEN_WRITE_DIRS",
    "CODING_TOOLS",
    "read_file",
    "write_file",
    "edit_file",
    "grep_search",
    "list_files",
    "run_shell",
]
