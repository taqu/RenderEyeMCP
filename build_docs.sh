#!/usr/bin/env bash
# Build the RenderEyeMCP bilingual HTML manual.
#
# Prerequisites:
#   pip install -r requirements-docs.txt
#
# Output:
#   manual/index.html   language selector
#   manual/en/          English documentation
#   manual/ja/          Japanese documentation
#
# Usage:
#   ./build_docs.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${REPO_ROOT}"

echo "Building English documentation..."
mkdocs build --config-file mkdocs.en.yml --clean

echo "Building Japanese documentation..."
mkdocs build --config-file mkdocs.ja.yml --clean

echo "Creating language selector..."
cp docs/manual_index.html manual/index.html

echo ""
echo "Manual built successfully:"
echo "  manual/index.html"
echo "  manual/en/index.html"
echo "  manual/ja/index.html"
echo ""
echo "Open manual/index.html in a browser to view the documentation."
