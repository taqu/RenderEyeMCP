"""
MkDocs hook: rewrite cross-language .md links to .html.

The source markdown files carry language-switcher links such as:
  [日本語](../ja/quickstart.md)
  [English](../../en/installation.md)

These point outside the docs_dir for each separate build, so MkDocs leaves
the .md extension in place.  Browsers cannot follow .md links from a local
file:// URL, so this hook rewrites them to .html after each page is rendered.
"""

import re


def on_page_content(html, page, config, files):
    # Match href="../ja/file.md" or href="../../en/file.md" (with optional #anchor).
    # Group 1: the relative path without extension.
    # Group 2: optional #anchor fragment.
    return re.sub(
        r'href="((?:\.\./)+(?:en|ja)/[^"#]+?)\.md((?:#[^"]*)?)"',
        r'href="\1.html\2"',
        html,
    )
