"""Lightweight documentation checks (no third-party dependencies).

Checks:
  1. Relative Markdown links and images resolve to existing files.
  2. ``#anchor`` fragments match a heading in the target page (GitHub slug rules).
  3. Every page under docs/en/ has a docs/ja/ counterpart and vice versa
     (README.md <-> README.ja.md as well).
  4. Every paired page starts with an English | 日本語 language switcher.

Usage:
    python scripts/check_docs.py          # exit code 1 on any problem
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Pages checked for links. docs/work/ holds historical phase specs and is excluded.
_EXCLUDED_DIRS = {REPO_ROOT / "docs" / "work"}

_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _markdown_files() -> list[Path]:
    files = [p for p in REPO_ROOT.glob("*.md")]
    for path in (REPO_ROOT / "docs").rglob("*.md"):
        if not any(parent in _EXCLUDED_DIRS for parent in path.parents):
            files.append(path)
    return sorted(files)


def _strip_code(lines: list[str]) -> list[str]:
    """Blank out fenced code blocks so their contents are not parsed as links."""
    out, in_fence = [], False
    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return out


def github_slug(text: str) -> str:
    """Approximate GitHub's heading anchor algorithm (Unicode-aware)."""
    text = re.sub(r"`([^`]*)`", r"\1", text)            # inline code -> text
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links -> text
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)                # drop punctuation (keeps CJK)
    return text.replace(" ", "-")


def anchors_of(path: Path) -> set[str]:
    seen: dict[str, int] = {}
    anchors = set()
    for line in _strip_code(path.read_text(encoding="utf-8").splitlines()):
        match = _HEADING_RE.match(line)
        if not match:
            continue
        slug = github_slug(match.group(2))
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def check_links(files: list[Path]) -> list[str]:
    errors = []
    anchor_cache: dict[Path, set[str]] = {}
    for path in files:
        lines = _strip_code(path.read_text(encoding="utf-8").splitlines())
        for lineno, line in enumerate(lines, 1):
            for target in _LINK_RE.findall(line):
                if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                    continue  # http:, https:, mailto: ...
                file_part, _, fragment = target.partition("#")
                dest = (path.parent / file_part).resolve() if file_part else path
                where = f"{path.relative_to(REPO_ROOT)}:{lineno}"
                if file_part.startswith("../../releases") or file_part.startswith("../../issues"):
                    continue  # GitHub web routes, not files
                if not dest.exists():
                    errors.append(f"{where}: broken link -> {target}")
                    continue
                if fragment and dest.suffix == ".md":
                    anchors = anchor_cache.setdefault(dest, anchors_of(dest))
                    if fragment not in anchors:
                        errors.append(f"{where}: missing anchor #{fragment} in {dest.relative_to(REPO_ROOT)}")
    return errors


def language_pairs() -> list[tuple[Path, Path]]:
    pairs = [(REPO_ROOT / "README.md", REPO_ROOT / "README.ja.md")]
    en_root, ja_root = REPO_ROOT / "docs" / "en", REPO_ROOT / "docs" / "ja"
    rels = {p.relative_to(en_root) for p in en_root.rglob("*.md")}
    rels |= {p.relative_to(ja_root) for p in ja_root.rglob("*.md")}
    pairs += [(en_root / rel, ja_root / rel) for rel in sorted(rels)]
    return pairs


def check_pairs() -> list[str]:
    errors = []
    for en, ja in language_pairs():
        for page, other in ((en, ja), (ja, en)):
            rel = page.relative_to(REPO_ROOT)
            if not page.exists():
                errors.append(f"missing translation: {rel} (counterpart of {other.relative_to(REPO_ROOT)})")
                continue
            first = next((ln for ln in page.read_text(encoding="utf-8").splitlines() if ln.strip()), "")
            if "[English](" not in first or "[日本語](" not in first:
                errors.append(f"{rel}: first line must be the English | 日本語 language switcher")
    return errors


def main() -> int:
    errors = check_links(_markdown_files()) + check_pairs()
    for error in errors:
        print(error)
    if errors:
        print(f"\n{len(errors)} documentation problem(s) found.")
        return 1
    print("Documentation checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
