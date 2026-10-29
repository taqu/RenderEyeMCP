"""Tag classification and version normalization for PyPI publishing.

Parses a Git tag and classifies it as:
  production  -- vMAJOR.MINOR.PATCH          -> PEP 440 version MAJOR.MINOR.PATCH
  test        -- vMAJOR.MINOR.PATCH-test.N   -> PEP 440 version MAJOR.MINOR.PATCH.devN
  invalid     -- anything else

Usage:
    python scripts/classify_tag.py v1.0.0
    python scripts/classify_tag.py v1.0.0-test.1
    python scripts/classify_tag.py --gha v1.0.0-test.1   # GitHub Actions output
"""

from __future__ import annotations

import argparse
import os
import re
import sys

# Anchored patterns — no partial matches allowed.
_PRODUCTION_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_TEST_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)-test\.([1-9]\d*)$")


class TagResult:
    def __init__(
        self,
        kind: str,
        version: str | None = None,
        error: str | None = None,
    ) -> None:
        self.kind = kind      # 'production' | 'test' | 'invalid'
        self.version = version
        self.error = error

    def __repr__(self) -> str:
        return f"TagResult(kind={self.kind!r}, version={self.version!r})"


def classify(tag: str) -> TagResult:
    """Classify a Git tag and return the normalized PEP 440 version.

    Accepts:
        v1.2.3           -> production, version=1.2.3
        v1.2.3-test.1    -> test,       version=1.2.3.dev1
        v1.2.3-test.2    -> test,       version=1.2.3.dev2

    Rejects (returns kind='invalid'):
        v1.2             missing patch segment
        v1.2.3-test      unnumbered test suffix
        v1.2.3-test.0    test iteration must be >= 1
        v1.2.3-test.foo  non-numeric iteration
        v1.2.3-debug     unknown suffix
        release-1.2.3    wrong prefix
    """
    m = _PRODUCTION_RE.match(tag)
    if m:
        version = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
        return TagResult("production", version)

    m = _TEST_RE.match(tag)
    if m:
        version = f"{m.group(1)}.{m.group(2)}.{m.group(3)}.dev{m.group(4)}"
        return TagResult("test", version)

    return TagResult(
        "invalid",
        error=(
            f"Tag {tag!r} does not match a recognized release pattern.\n"
            "  Production: vMAJOR.MINOR.PATCH        (e.g. v1.0.0)\n"
            "  Test:       vMAJOR.MINOR.PATCH-test.N (e.g. v1.0.0-test.1, N >= 1)"
        ),
    )


def _write_gha_output(pairs: dict[str, str]) -> None:
    """Write key=value pairs to $GITHUB_OUTPUT (or stdout in local runs)."""
    env_file = os.environ.get("GITHUB_OUTPUT", "")
    lines = [f"{k}={v}" for k, v in pairs.items()]
    if env_file:
        with open(env_file, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    else:
        for line in lines:
            print(line)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify a Git release tag and normalize it to a PEP 440 version."
    )
    parser.add_argument("tag", help="Git tag to classify (e.g. v1.0.0 or v1.0.0-test.1)")
    parser.add_argument(
        "--gha",
        action="store_true",
        help="Write outputs to $GITHUB_OUTPUT instead of stdout",
    )
    args = parser.parse_args()

    result = classify(args.tag)

    if args.gha:
        _write_gha_output({"kind": result.kind, "version": result.version or ""})
    else:
        print(f"kind:    {result.kind}")
        print(f"version: {result.version or 'N/A'}")

    if result.kind == "invalid":
        print(f"ERROR: {result.error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
