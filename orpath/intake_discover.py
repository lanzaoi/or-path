"""Discover problem-surface files for auto-intake (inbox/ + CLI)."""
from __future__ import annotations

from pathlib import Path

# White-list extensions for auto-intake (no bulk zip/xls by default)
_INBOX_EXTS = {".md", ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def discover_inbox_sources(root: Path, *, inbox_name: str = "inbox") -> list[str]:
    """Return sorted absolute paths under root/inbox with allowed extensions.

    Skips README*, .gitkeep, and directories. Does not recurse into nested bulk trees
    deeper than one level of files (files in inbox/ only; one level of subdirs OK).
    """
    root = Path(root)
    inbox = root / inbox_name
    if not inbox.is_dir():
        return []
    found: list[Path] = []
    for p in sorted(inbox.rglob("*")):
        if not p.is_file():
            continue
        name = p.name.lower()
        if name in {".gitkeep", "readme.md", "readme.txt"} or name.startswith("readme"):
            continue
        if p.suffix.lower() not in _INBOX_EXTS:
            continue
        # avoid deep attachment dumps: max depth inbox/a/file or inbox/file
        try:
            rel = p.relative_to(inbox)
        except ValueError:
            continue
        if len(rel.parts) > 2:
            continue
        found.append(p.resolve())
    # stable unique
    out: list[str] = []
    seen: set[str] = set()
    for p in found:
        s = str(p)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def merge_intake_sources(
    root: Path,
    explicit: list[str] | None,
    *,
    auto_intake: bool,
) -> list[str]:
    """CLI paths first, then inbox if auto_intake and no explicit (or always append?).

    Policy: explicit --intake-in wins as primary list; if auto_intake and explicit empty,
    use inbox. If auto_intake and explicit non-empty, keep explicit only (no surprise merge).
    """
    explicit = [str(Path(p).expanduser()) for p in (explicit or []) if str(p).strip()]
    resolved: list[str] = []
    for p in explicit:
        path = Path(p)
        if not path.is_absolute():
            path = (root / path).resolve()
        else:
            path = path.resolve()
        if path.is_file():
            resolved.append(str(path))
    if resolved:
        return resolved
    if auto_intake:
        return discover_inbox_sources(root)
    return []
