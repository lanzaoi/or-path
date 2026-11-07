#!/usr/bin/env python3
"""Build script for watch.html.

Assembles modular source files from `orpath/web/src/` into the standalone
distribution file `orpath/web/watch.html`.
"""

import sys
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent
SRC_DIR = WEB_DIR / "src"
OUT_FILE = WEB_DIR / "watch.html"

CSS_FILES = [
    SRC_DIR / "css" / "base.css",
    SRC_DIR / "css" / "studio.css",
    SRC_DIR / "css" / "inspector.css",
]

HTML_FILES = [
    SRC_DIR / "html" / "header.html",
    SRC_DIR / "html" / "studio.html",
    SRC_DIR / "html" / "inspector.html",
    SRC_DIR / "html" / "modals.html",
]

JS_FILES = [
    SRC_DIR / "js" / "common.js",
    SRC_DIR / "js" / "inspector.js",
    SRC_DIR / "js" / "studio.js",
]


def needs_rebuild() -> bool:
    if not OUT_FILE.is_file():
        return True
    out_mtime = OUT_FILE.stat().st_mtime
    all_src = CSS_FILES + HTML_FILES + JS_FILES
    for p in all_src:
        if p.is_file() and p.stat().st_mtime >= out_mtime:
            return True
    return False


def build(force: bool = False) -> Path:
    if not force and not needs_rebuild():
        return OUT_FILE

    # Check all sources exist
    all_src = CSS_FILES + HTML_FILES + JS_FILES
    for p in all_src:
        if not p.is_file():
            raise FileNotFoundError(f"Missing source file: {p}")

    css_blocks = []
    for p in CSS_FILES:
        rel = p.relative_to(WEB_DIR)
        css_blocks.append(f"/* === {rel} === */\n" + p.read_text(encoding="utf-8"))

    html_blocks = []
    for p in HTML_FILES:
        rel = p.relative_to(WEB_DIR)
        html_blocks.append(f"<!-- === {rel} === -->\n" + p.read_text(encoding="utf-8"))

    js_blocks = []
    for p in JS_FILES:
        rel = p.relative_to(WEB_DIR)
        js_blocks.append(f"// === {rel} ===\n" + p.read_text(encoding="utf-8"))

    joined_css = "\n\n".join(css_blocks)
    joined_html = "\n\n".join(html_blocks)
    joined_js = "\n\n".join(js_blocks)

    output = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;" />
  <title>OR-Path 实时过程台</title>
  <style>
{joined_css}
  </style>
</head>
<body class="mode-studio">

{joined_html}

  <script>
{joined_js}

    boot();
  </script>
</body>
</html>
"""
    assert "boot();" in output, "Build error: boot() call missing from output"
    OUT_FILE.write_text(output, encoding="utf-8")
    return OUT_FILE


if __name__ == "__main__":
    force_build = "--force" in sys.argv
    built = build(force=force_build)
    print(f"watch.html assembled successfully: {built} ({built.stat().st_size} bytes)")
