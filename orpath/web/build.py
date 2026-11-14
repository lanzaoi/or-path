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
STUDIO_OUT_FILE = WEB_DIR / "studio.html"

SHARED_CSS = [SRC_DIR / "css" / "base.css"]
SHARED_JS = [SRC_DIR / "js" / "common.js", SRC_DIR / "js" / "intake.js"]

PAGES = {
    "watch": {
        "out": OUT_FILE,
        "title": "OR-Path 实时过程台 · Live Watch",
        "body_class": "mode-inspector",
        "css": SHARED_CSS + [
            SRC_DIR / "css" / "watch" / "layout.css",
            SRC_DIR / "css" / "watch" / "panels.css",
            SRC_DIR / "css" / "watch" / "workbench.css",
        ],
        "html": [
            SRC_DIR / "html" / "header.html",
            SRC_DIR / "html" / "watch" / "shell.html",
            SRC_DIR / "html" / "watch" / "modals.html",
        ],
        "js": SHARED_JS + [
            SRC_DIR / "js" / "watch" / "state.js",
            SRC_DIR / "js" / "watch" / "timeline.js",
            SRC_DIR / "js" / "watch" / "dialogue.js",
            SRC_DIR / "js" / "watch" / "workbench.js",
            SRC_DIR / "js" / "watch" / "intake_modal.js",
            SRC_DIR / "js" / "watch" / "boot.js",
        ],
    },
    "studio": {
        "out": STUDIO_OUT_FILE,
        "title": "OR-Path 智能做题工作舱 · Studio",
        "body_class": "mode-studio",
        "css": SHARED_CSS + [
            SRC_DIR / "css" / "studio" / "layout.css",
            SRC_DIR / "css" / "studio" / "pipeline_intake.css",
            SRC_DIR / "css" / "studio" / "cards.css",
            SRC_DIR / "css" / "studio" / "viz.css",
        ],
        "html": [
            SRC_DIR / "html" / "header.html",
            SRC_DIR / "html" / "studio" / "shell.html",
            SRC_DIR / "html" / "studio" / "analysis.html",
            SRC_DIR / "html" / "studio" / "result.html",
        ],
        "js": SHARED_JS + [
            SRC_DIR / "js" / "studio" / "state.js",
            SRC_DIR / "js" / "studio" / "files.js",
            SRC_DIR / "js" / "studio" / "analyze.js",
            SRC_DIR / "js" / "studio" / "result.js",
            SRC_DIR / "js" / "studio" / "viz.js",
            SRC_DIR / "js" / "studio" / "boot.js",
        ],
    },
}


def _page_needs_rebuild(out_path: Path, sources: list[Path]) -> bool:
    if not out_path.is_file():
        return True
    out_mtime = out_path.stat().st_mtime
    for p in sources:
        if p.is_file() and p.stat().st_mtime >= out_mtime:
            return True
    return False


def needs_rebuild() -> bool:
    return any(
        _page_needs_rebuild(spec["out"], spec["css"] + spec["html"] + spec["js"])
        for spec in PAGES.values()
    )


def _assemble_page(spec: dict, force: bool = False) -> Path:
    out_path: Path = spec["out"]
    sources: list[Path] = spec["css"] + spec["html"] + spec["js"]
    if not force and not _page_needs_rebuild(out_path, sources):
        return out_path

    for p in sources:
        if not p.is_file():
            raise FileNotFoundError(f"Missing source file: {p}")

    css_blocks = [
        f"/* === {p.relative_to(WEB_DIR)} === */\n" + p.read_text(encoding="utf-8")
        for p in spec["css"]
    ]
    html_blocks = [
        f"<!-- === {p.relative_to(WEB_DIR)} === -->\n" + p.read_text(encoding="utf-8")
        for p in spec["html"]
    ]
    js_blocks = [
        f"// === {p.relative_to(WEB_DIR)} ===\n" + p.read_text(encoding="utf-8")
        for p in spec["js"]
    ]

    joined_css = "\n\n".join(css_blocks)
    joined_html = "\n\n".join(html_blocks)
    joined_js = "\n\n".join(js_blocks)

    output = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;" />
  <title>{spec["title"]}</title>
  <style>
{joined_css}
  </style>
</head>
<body class="{spec["body_class"]}">

{joined_html}

  <script>
{joined_js}

    boot();
  </script>
</body>
</html>
"""
    assert "boot();" in output, f"Build error: boot() call missing from {out_path.name}"
    out_path.write_text(output, encoding="utf-8")
    return out_path


def build(force: bool = False) -> Path:
    built = [
        _assemble_page(PAGES["watch"], force=force),
        _assemble_page(PAGES["studio"], force=force),
    ]
    return built[0]


if __name__ == "__main__":
    force_build = "--force" in sys.argv
    built_watch = build(force=force_build)
    print(f"watch.html assembled successfully: {built_watch} ({built_watch.stat().st_size} bytes)")
    print(f"studio.html assembled successfully: {STUDIO_OUT_FILE} ({STUDIO_OUT_FILE.stat().st_size} bytes)")
