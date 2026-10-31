#!/usr/bin/env bash
# install.sh — RenderEyeMCP installer for Linux and macOS
#
# Usage:
#   ./install.sh [--renderdoc-ext-dir DIR] [--force]
#
# Run from the extracted release archive directory (where rendereye-mcp lives).
# The executable is NOT copied anywhere — configure your coding agent to point to it
# directly in its current location.
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────

RENDERDOC_EXT_DIR=""
FORCE=0

# ── Argument parsing ──────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --renderdoc-ext-dir) RENDERDOC_EXT_DIR="$2"; shift 2 ;;
        --force)             FORCE=1; shift ;;
        -h|--help)
            echo "Usage: $0 [--renderdoc-ext-dir DIR] [--force]"
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

[[ -f "$EXE_SRC" ]] || fail "rendereye-mcp not found in $SCRIPT_DIR. Run install.sh from the extracted release archive directory."

EXE_PATH="$(cd "$(dirname "$EXE_SRC")" && pwd)/$(basename "$EXE_SRC")"

# ── Validate executable ───────────────────────────────────────────────────────

step "Verifying rendereye-mcp"
if VER=$("$EXE_PATH" version 2>/dev/null | head -1); then
    ok "Executable: $VER"
else
    warn "Could not run version check — proceeding with extension installation."
fi

# ── Locate RenderDoc Extension directory ─────────────────────────────────────

step "Locating RenderDoc Extension directory"

if [[ -z "$RENDERDOC_EXT_DIR" ]]; then
    RENDERDOC_EXT_DIR="${HOME}/.local/share/qrenderdoc/extensions"
fi

ok "Extension directory: $RENDERDOC_EXT_DIR"

# ── Install Extension ─────────────────────────────────────────────────────────

[[ -d "$EXT_SRC" ]] || fail "extension/ directory not found in $SCRIPT_DIR. The release archive may be incomplete."

step "Installing RenderDoc Extension"

EXT_DST="${RENDERDOC_EXT_DIR}/rendereye"

if [[ -d "$EXT_DST" && "$FORCE" -eq 0 ]]; then
    warn "Existing extension found at $EXT_DST"
    read -rp "    Overwrite? [y/N]: " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "    Skipped extension installation."
        EXT_SKIP=1
    fi
fi

if [[ "${EXT_SKIP:-0}" -eq 0 ]]; then
    mkdir -p "$EXT_DST"
    # Copy extension files, skipping __pycache__
    find "$EXT_SRC" -not -path "*/__pycache__/*" -not -name "__pycache__" | while read -r src; do
        rel="${src#$EXT_SRC/}"
        [[ "$rel" == "$EXT_SRC" ]] && continue
        dst="${EXT_DST}/${rel}"
        if [[ -d "$src" ]]; then
            mkdir -p "$dst"
        else
            dstdir="$(dirname "$dst")"
            mkdir -p "$dstdir"
            cp "$src" "$dst"
        fi
    done
    ok "Extension installed to $EXT_DST"
    warn "Restart RenderDoc, then enable the extension:"
    warn "  Tools -> Manage Extensions -> RenderEyeMCP -> Always Load"
fi

# ── Create default .env if not present ───────────────────────────────────────

ENV_DST="${SCRIPT_DIR}/.env"
if [[ ! -f "$ENV_DST" ]]; then
    cat > "$ENV_DST" <<'EOF'
# RenderEyeMCP configuration
# Uncomment and edit as needed.
#RENDEREYE_IPC_HOST=127.0.0.1
#RENDEREYE_IPC_PORT=37020
#RENDEREYE_LOG_LEVEL=info
EOF
    ok "Created default .env in $SCRIPT_DIR"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "Installation complete."
echo ""
echo "Executable : $EXE_PATH"
echo ""
echo "Keep the extracted directory in place — your coding agent runs the"
echo "executable directly from $SCRIPT_DIR"
echo ""
echo "Claude Code configuration (~/.claude.json or project .claude.json):"
echo "  {"
echo "    \"mcpServers\": {"
echo "      \"rendereye\": {"
echo "        \"command\": \"$EXE_PATH\""
echo "      }"
echo "    }"
echo "  }"
echo ""
echo "Codex configuration (~/.codex/config.toml):"
echo "  [mcp_servers.rendereye]"
echo "  command = \"$EXE_PATH\""
echo ""
echo "To start the IPC service manually:"
echo "  $EXE_PATH service"
echo ""
echo "To check the version:"
echo "  $EXE_PATH version"
