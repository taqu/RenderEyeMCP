#!/usr/bin/env bash
# install.sh — RenderEyeMCP installer for Linux and macOS
#
# Usage:
#   ./install.sh [--install-dir DIR] [--renderdoc-ext-dir DIR] [--force]
#
# Run from the extracted release archive directory.
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────

INSTALL_DIR="${HOME}/.local/bin"
RENDERDOC_EXT_DIR=""
FORCE=0

# ── Argument parsing ──────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install-dir)       INSTALL_DIR="$2"; shift 2 ;;
        --renderdoc-ext-dir) RENDERDOC_EXT_DIR="$2"; shift 2 ;;
        --force)             FORCE=1; shift ;;
        -h|--help)
            echo "Usage: $0 [--install-dir DIR] [--renderdoc-ext-dir DIR] [--force]"
            exit 0
            ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────

step()  { echo "==> $*"; }
ok()    { echo "    OK  $*"; }
warn()  { echo "    WARN $*"; }
fail()  { echo "    FAIL $*" >&2; exit 1; }

# ── Locate archive root ───────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXE_SRC="${SCRIPT_DIR}/rendereye-mcp"
EXT_SRC="${SCRIPT_DIR}/extension"

[[ -f "$EXE_SRC" ]] || fail "rendereye-mcp not found next to install.sh ($SCRIPT_DIR)"

# ── Install executable ────────────────────────────────────────────────────────

step "Installing rendereye-mcp to $INSTALL_DIR"

mkdir -p "$INSTALL_DIR"
EXE_DST="${INSTALL_DIR}/rendereye-mcp"

if [[ -f "$EXE_DST" && "$FORCE" -eq 0 ]]; then
    existing=$("$EXE_DST" version 2>/dev/null | head -1 || echo "unknown version")
    warn "Existing installation found: $existing"
    read -rp "    Overwrite? [y/N]: " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "    Skipped executable installation."
        EXE_DST_SKIP=1
    fi
fi

if [[ "${EXE_DST_SKIP:-0}" -eq 0 ]]; then
    install -m 755 "$EXE_SRC" "$EXE_DST"
    ok "Installed rendereye-mcp to $EXE_DST"
fi

# ── Locate RenderDoc Extension directory ─────────────────────────────────────

step "Locating RenderDoc Extension directory"

if [[ -z "$RENDERDOC_EXT_DIR" ]]; then
    candidates=(
        "/opt/renderdoc/plugins"
        "/usr/share/renderdoc/plugins"
        "${HOME}/.local/share/renderdoc/plugins"
    )
    for c in "${candidates[@]}"; do
        if [[ -d "$c" ]]; then
            RENDERDOC_EXT_DIR="$c"
            break
        fi
    done
fi

if [[ -z "$RENDERDOC_EXT_DIR" ]]; then
    warn "Could not auto-detect RenderDoc Extension directory."
    warn "Pass --renderdoc-ext-dir to specify it, or copy extension/ manually."
else
    ok "RenderDoc Extension directory: $RENDERDOC_EXT_DIR"
fi

# ── Install Extension ─────────────────────────────────────────────────────────

if [[ -n "$RENDERDOC_EXT_DIR" && -d "$EXT_SRC" ]]; then
    step "Installing RenderDoc Extension to $RENDERDOC_EXT_DIR"
    EXT_DST="${RENDERDOC_EXT_DIR}/rendereye"
    mkdir -p "$EXT_DST"
    cp -r "${EXT_SRC}/." "$EXT_DST/"
    ok "Extension installed to $EXT_DST"
    warn "Restart RenderDoc for the extension to take effect."
fi

# ── PATH reminder ─────────────────────────────────────────────────────────────

if [[ ":$PATH:" != *":${INSTALL_DIR}:"* ]]; then
    warn "$INSTALL_DIR is not in your PATH."
    warn "Add this to your shell profile:"
    warn "  export PATH=\"\$PATH:${INSTALL_DIR}\""
fi

# ── .env template ─────────────────────────────────────────────────────────────

ENV_DST="${INSTALL_DIR}/.env"
if [[ ! -f "$ENV_DST" ]]; then
    cat > "$ENV_DST" <<'EOF'
# RenderEyeMCP configuration
# Uncomment and edit as needed.
#RENDEREYE_IPC_HOST=127.0.0.1
#RENDEREYE_IPC_PORT=37020
#RENDEREYE_LOG_LEVEL=info
EOF
    ok "Created default .env in $INSTALL_DIR"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "Installation complete."
echo ""
echo "Executable : $EXE_DST"
echo ""
echo "Claude Code configuration (~/.claude.json or project .claude.json):"
echo "  {"
echo "    \"mcpServers\": {"
echo "      \"rendereye\": {"
echo "        \"command\": \"$EXE_DST\""
echo "      }"
echo "    }"
echo "  }"
echo ""
echo "To start the IPC service manually:"
echo "  $EXE_DST service"
echo ""
echo "To check the version:"
echo "  $EXE_DST version"
