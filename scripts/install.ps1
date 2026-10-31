#Requires -Version 5.1
<#
.SYNOPSIS
    Installs the RenderEyeMCP RenderDoc Extension.

.DESCRIPTION
    Copies the RenderDoc Extension from the extracted release archive to the
    per-user RenderDoc extension directory and prints coding-agent configuration
    instructions.

    Run from the extracted release archive directory (where rendereye-mcp.exe lives).
    The executable is NOT copied anywhere — configure your coding agent to point to it
    directly in its current location.

.PARAMETER RenderDocExtDir
    RenderDoc per-user extension directory.
    Default: %APPDATA%\qrenderdoc\extensions

.PARAMETER Force
    Overwrite an existing RenderDoc extension installation without prompting.
#>
param(
    [string]$RenderDocExtDir = "",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Helpers ──────────────────────────────────────────────────────────────────

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "    OK  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    WARN $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "    FAIL $msg" -ForegroundColor Red }

# ── Locate archive root ───────────────────────────────────────────────────────

$ScriptDir = $PSScriptRoot
$ExeSrc    = Join-Path $ScriptDir "rendereye-mcp.exe"
$ExtSrc    = Join-Path $ScriptDir "extensions"

if (-not (Test-Path $ExeSrc -PathType Leaf)) {
    Write-Fail "rendereye-mcp.exe not found in $ScriptDir"
    Write-Fail "Run install.ps1 from the extracted release archive directory."
    exit 1
}

$ExePath = (Resolve-Path $ExeSrc).Path

# ── Validate executable ───────────────────────────────────────────────────────

Write-Step "Verifying rendereye-mcp.exe"
try {
    $ver = & $ExePath version 2>&1 | Select-Object -First 1
    Write-OK "Executable: $ver"
} catch {
    Write-Warn "Could not run version check: $_"
    Write-Warn "Proceeding with extension installation."
}

# ── Resolve RenderDoc Extension directory ────────────────────────────────────

Write-Step "Locating RenderDoc Extension directory"

if ([string]::IsNullOrWhiteSpace($RenderDocExtDir)) {
    $RenderDocExtDir = Join-Path $env:APPDATA "qrenderdoc\extensions"
}

Write-OK "Extension directory: $RenderDocExtDir"

# ── Install Extension ─────────────────────────────────────────────────────────

if (-not (Test-Path $ExtSrc -PathType Container)) {
    Write-Fail "extension/ directory not found in $ScriptDir"
    Write-Fail "The release archive may be incomplete."
    exit 1
}

Write-Step "Installing RenderDoc Extension"

$ExtDst = Join-Path $RenderDocExtDir "rendereye"

if ((Test-Path $ExtDst) -and -not $Force) {
    Write-Warn "Existing extension found at $ExtDst"
    $confirm = Read-Host "    Overwrite? [y/N]"
    if ($confirm -notmatch '^[Yy]') {
        Write-Host "    Skipped extension installation."
    } else {
        Remove-Item -Recurse -Force $ExtDst
        $Force = $true
    }
}

if (-not (Test-Path $ExtDst) -or $Force) {
    if (-not (Test-Path $RenderDocExtDir)) {
        New-Item -ItemType Directory -Path $RenderDocExtDir -Force | Out-Null
    }
    if (-not (Test-Path $ExtDst)) {
        New-Item -ItemType Directory -Path $ExtDst -Force | Out-Null
    }

    Get-ChildItem -Path $ExtSrc -Recurse | Where-Object { $_.Name -ne "__pycache__" -and $_.FullName -notmatch "__pycache__" } | ForEach-Object {
        $rel = $_.FullName.Substring($ExtSrc.Length).TrimStart('\', '/')
        $dst = Join-Path $ExtDst $rel
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Path $dst -Force | Out-Null
        } else {
            $dstDir = Split-Path $dst -Parent
            if (-not (Test-Path $dstDir)) {
                New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
            }
            Copy-Item -Path $_.FullName -Destination $dst -Force
        }
    }
    Write-OK "Extension installed to $ExtDst"
    Write-Warn "Restart RenderDoc, then enable the extension:"
    Write-Warn "  Tools -> Manage Extensions -> RenderEyeMCP -> Always Load"
}

# ── Create default .env if not present ───────────────────────────────────────

$EnvDst = Join-Path $ScriptDir ".env"
if (-not (Test-Path $EnvDst)) {
    Set-Content -Path $EnvDst -Value @"
# RenderEyeMCP configuration
# Uncomment and edit as needed.
#RENDEREYE_IPC_HOST=127.0.0.1
#RENDEREYE_IPC_PORT=37020
#RENDEREYE_LOG_LEVEL=info
"@
    Write-OK "Created default .env in $ScriptDir"
}

# ── Summary ───────────────────────────────────────────────────────────────────

# Escape backslashes for JSON
$ExeJson = $ExePath -replace '\\', '\\'

Write-Host ""
Write-Host "Installation complete." -ForegroundColor Green
Write-Host ""
Write-Host "Executable : $ExePath"
Write-Host ""
Write-Host "Keep the extracted directory in place — your coding agent runs the"
Write-Host "executable directly from $ScriptDir"
Write-Host ""
Write-Host "Claude Code configuration (~/.claude.json or project .claude.json):"
Write-Host '  {' -ForegroundColor DarkGray
Write-Host '    "mcpServers": {' -ForegroundColor DarkGray
Write-Host '      "rendereye": {' -ForegroundColor DarkGray
Write-Host "        `"command`": `"$ExeJson`"" -ForegroundColor White
Write-Host '      }' -ForegroundColor DarkGray
Write-Host '    }' -ForegroundColor DarkGray
Write-Host '  }' -ForegroundColor DarkGray
Write-Host ""
Write-Host "Codex configuration (~/.codex/config.toml):"
Write-Host "  [mcp_servers.rendereye]" -ForegroundColor DarkGray
Write-Host "  command = `"$ExeJson`"" -ForegroundColor White
Write-Host ""
Write-Host "To start the IPC service manually:"
Write-Host "  $ExePath service" -ForegroundColor White
Write-Host ""
Write-Host "To check the version:"
Write-Host "  $ExePath version" -ForegroundColor White
