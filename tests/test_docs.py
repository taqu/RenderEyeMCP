"""Documentation integrity: links, anchors and English/Japanese parity."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_docs", REPO_ROOT / "scripts" / "check_docs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_documentation_links_and_translations():
    checker = _load_checker()
    errors = checker.check_links(checker._markdown_files()) + checker.check_pairs()
    assert errors == []


def test_github_slug_handles_japanese_and_punctuation():
    slug = _load_checker().github_slug
    assert slug("Render Target、Texture、Pixel") == "render-targettexturepixel"
    assert slug("環境設定(.env)") == "環境設定env"
    assert slug("Connect `Claude Code`") == "connect-claude-code"


def test_tool_reference_lists_every_registered_tool():
    import asyncio

    from rendereye_mcp.config import Config
    from rendereye_mcp.server import create_server

    names = {t.name for t in asyncio.run(create_server(Config()).list_tools())}
    for lang in ("en", "ja"):
        text = (REPO_ROOT / "docs" / lang / "tools.md").read_text(encoding="utf-8")
        missing = sorted(n for n in names if f"`{n}`" not in text)
        assert missing == [], f"docs/{lang}/tools.md is missing {missing}"
        assert f"**{len(names)}" in text
