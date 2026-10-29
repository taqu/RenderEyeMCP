"""Targeted JSON/JSONC edits. Offsets refer to the original, unchanged text."""

from __future__ import annotations

import json
import re


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate configuration key: {key}")
        result[key] = value
    return result


def clean(text: str, jsonc: bool | str, *, trailing=True) -> str:
    # Match strings before comments so URLs and escaped quotes are untouched.
    token = re.compile(r'"(?:[^"\\]|\\.)*"|//[^\r\n]*|/\*[\s\S]*?\*/')
    if not jsonc:
        return text
    masked = token.sub(
        lambda m: m[0] if m[0].startswith('"') else re.sub(r"[^\r\n]", " ", m[0]), text
    )
    if not trailing or jsonc == "comments":
        return masked
    # Only punctuation outside strings can be a trailing comma.
    chars = list(masked)
    strings = {m.start(): m.end() for m in token.finditer(masked) if m[0].startswith('"')}
    pos = 0
    while pos < len(chars):
        if pos in strings:
            pos = strings[pos]
            continue
        if chars[pos] == "," and re.match(r"\s*[}\]]", masked[pos + 1 :]):
            chars[pos] = " "
        pos += 1
    return "".join(chars)


def parse(text: str, jsonc: bool | str = False) -> dict:
    value = json.loads(
        clean(text, jsonc),
        object_pairs_hook=_unique,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"Invalid JSON constant: {value}")
        ),
    )
    if not isinstance(value, dict):
        raise ValueError("Configuration must be an object")
    return value


def _members(text: str, start: int):
    """Locate members in a validated object using the standard JSON decoder."""
    decoder = json.JSONDecoder()
    pos = start + 1
    members = []
    while True:
        while text[pos].isspace():
            pos += 1
        if text[pos] == "}":
            return members, pos
        key_start = pos
        key, pos = decoder.raw_decode(text, pos)
        while text[pos].isspace() or text[pos] == ":":
            pos += 1
        value_start = pos
        _, end = decoder.raw_decode(text, pos)
        pos = end
        while text[pos].isspace():
            pos += 1
        comma = pos if text[pos] == "," else None
        members.append((key, key_start, value_start, end, comma))
        if comma is not None:
            pos += 1


def edit(text: str, key: str, servers: dict, jsonc: bool | str = False) -> str:
    """Replace, add or remove only the rendereye member; preserve other text."""
    source = clean(text, jsonc)
    root = source.index("{")
    members, _ = _members(source, root)
    container = next((m for m in members if m[0] == key), None)
    if container is None:
        return _insert(text, source, root, key, servers)
    start = container[2]
    members, _ = _members(source, start)
    owned = next((m for m in members if m[0] == "rendereye"), None)
    if owned is None:
        if "rendereye" not in servers:
            return text
        return _insert(text, source, start, "rendereye", servers["rendereye"])
    _, begin, value_start, end, comma = owned
    if "rendereye" in servers:
        value = json.dumps(servers["rendereye"], ensure_ascii=False, indent=2)
        return text[:value_start] + value + text[end:]
    # Remove just the member and its separating comma, leaving comments in place.
    if comma is None and jsonc:
        tail = clean(text, True, trailing=False)
        match = re.match(r"\s*,", tail[end:])
        if match:
            comma = end + match.end() - 1
    if comma is not None:
        return text[:begin] + text[end:comma] + text[comma + 1 :]
    index = members.index(owned)
    result = text[:begin] + text[end:]
    if index:
        comma = members[index - 1][4]
        result = result[:comma] + result[comma + 1 :]
    return result


def _insert(text, source, start, key, value):
    members, end = _members(source, start)
    # Insert before the first member to avoid disturbing trailing comments/commas.
    pos = members[0][1] if members else end
    value = json.dumps(value, ensure_ascii=False, indent=2)
    newline = "\r\n" if "\r\n" in text else "\n"
    line_start = text.rfind("\n", 0, pos) + 1
    indent = text[line_start:pos]
    if indent.strip():
        indent = ""
    value = value.replace("\n", newline + indent)
    addition = json.dumps(key) + ": " + value + ("," + newline + indent if members else newline)
    return text[:pos] + addition + text[pos:]
