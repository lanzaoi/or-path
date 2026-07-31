#!/usr/bin/env python3
"""Unit tests for inbox auto-intake discovery."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orpath.intake_discover import discover_inbox_sources, merge_intake_sources  # noqa: E402


class TestIntakeDiscover(unittest.TestCase):
    def test_empty_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "inbox").mkdir()
            self.assertEqual(discover_inbox_sources(root), [])

    def test_finds_md_skips_readme(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = root / "inbox"
            inbox.mkdir()
            (inbox / "README.md").write_text("x", encoding="utf-8")
            q = inbox / "q1.txt"
            q.write_text("problem", encoding="utf-8")
            found = discover_inbox_sources(root)
            self.assertEqual(len(found), 1)
            self.assertTrue(found[0].endswith("q1.txt"))

    def test_merge_explicit_wins(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = root / "inbox"
            inbox.mkdir()
            (inbox / "a.txt").write_text("a", encoding="utf-8")
            other = root / "other.md"
            other.write_text("o", encoding="utf-8")
            m = merge_intake_sources(root, [str(other)], auto_intake=True)
            self.assertEqual(len(m), 1)
            self.assertTrue(m[0].endswith("other.md"))

    def test_merge_auto_when_empty_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = root / "inbox"
            inbox.mkdir()
            (inbox / "b.pdf").write_bytes(b"%PDF")
            m = merge_intake_sources(root, [], auto_intake=True)
            self.assertEqual(len(m), 1)


if __name__ == "__main__":
    unittest.main()
