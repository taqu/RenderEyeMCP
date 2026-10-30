#Requires -Version 5.1
<#
.SYNOPSIS
    Installs RenderEyeMCP on Windows.

.DESCRIPTION
    Copies rendereye-mcp.exe to a target directory, installs the RenderDoc
    Extension, and prints coding-agent configuration instructions.

    Run from the extracted release archive directory.

.PARAMETER InstallDir
    Directory where rendereye-mcp.exe is placed.
    Default: $env:LOCALAPPDATA\RenderEyeMCP

.PARAMETER RenderDocExtDir
    RenderDoc Extension directory.
    Default: auto-detected from common RenderDoc installation paths.

.PARAMETER Force
    Overwrite existing installation without prompting.
#>
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\RenderEyeMCP",
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

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExeSrc    = Join-Path $ScriptDir "rendereye-mcp.exe"
$ExtSrc    = Join-Path $ScriptDir "extension"

if (-not (Test-Path $ExeSrc)) {
    Write-Fail "rendereye-mcp.exe not found next to install.ps1 ($ScriptDir)"
    exit 1
}

# ── Install executable ────────────────────────────────────────────────────────

Write-Step "Installing rendereye-mcp.exe to $InstallDir"

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$ExeDst = Join-Path $InstallDir "rendereye-mcp.exe"

if ((Test-Path $ExeDst) -and -not $Force) {
    $existing = & $ExeDst version 2>&1 | Select-Object -First 1
    Write-Warn "Existing installation found: $existing"
    $confirm = Read-Host "    Overwrite? [y/N]"
    if ($confirm -notmatch '^[Yy]') {
        Write-Host "    Skipped executable installation."
    } else {
        Copy-Item -Path $ExeSrc -Destination $ExeDst -Force
        Write-OK "Copied rendereye-mcp.exe"
    }
} else {
    Copy-Item -Path $ExeSrc -Destination $ExeDst -Force
    Write-OK "Copied rendereye-mcp.exe"
}

# ── Locate RenderDoc Extension directory ─────────────────────────────────────

Write-Step "Locating RenderDoc Extension directory"

if ($RenderDocExtDir -eq "") {
    $candidates = @(
        "$env:ProgramFiles\RenderDoc\plugins\amd\renderdoc",
        "$env:ProgramFiles\RenderDoc\plugins",
        "$env:LOCALAPPDATA\RenderDoc\plugins"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $RenderDocExtDir = $c
            break
        }
    }
}

if ($RenderDocExtDir -eq "") {
    Write-Warn "Could not auto-detect RenderDoc Extension directory."
    Write-Warn "Please set -RenderDocExtDir to your RenderDoc plugins folder."
    Write-Warn "Extension files are in: $ExtSrc"
    Write-Warn "Copy them manually to your RenderDoc plugins directory."
} else {
    Write-OK "RenderDoc Extension directory: $RenderDocExtDir"
}

# ── Install Extension ─────────────────────────────────────────────────────────

if ($RenderDocExtDir -ne "" -and (Test-Path $ExtSrc)) {
    Write-Step "Installing RenderDoc Extension to $RenderDocExtDir"

    $ExtDst = Join-Path $RenderDocExtDir "rendereye"
    if (-not (Test-Path $ExtDst)) {
        New-Item -ItemType Directory -Path $ExtDst -Force | Out-Null
    }

    Get-ChildItem -Path $ExtSrc -Recurse | ForEach-Object {
        $rel = $_.FullName.Substring($ExtSrc.Length).TrimStart('\', '/')
        $dst = Join-Path $ExtDst $rel
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Path $dst -Force | Out-Null
        } else {
            Copy-Item -Path $_.FullName -Destination $dst -Force
        }
    }
    Write-OK "Extension installed to $ExtDst"
    Write-Warn "Restart RenderDoc for the extension to take effect."
}

# ── Copy .env template if not present ────────────────────────────────────────

$EnvDst = Join-Path $InstallDir ".env"
if (-not (Test-Path $EnvDst)) {
    Set-Content -Path $EnvDst -Value @"
# RenderEyeMCP configuration
# Uncomment and edit as needed.
#RENDEREYE_IPC_HOST=127.0.0.1
#RENDEREYE_IPC_PORT=37020
#RENDEREYE_LOG_LEVEL=info
"@
    Write-OK "Created default .env in $InstallDir"
}

# ── Summary ───────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "Installation complete." -ForegroundColor Green
Write-Host ""
Write-Host "Executable : $ExeDst"
Write-Host ""
Write-Host "Claude Code configuration (~/.claude.json or project .claude.json):"
Write-Host '  {' -ForegroundColor DarkGray
Write-Host '    "mcpServers": {' -ForegroundColor DarkGray
Write-Host '      "rendereye": {' -ForegroundColor DarkGray
Write-Host "        `"command`": `"$ExeDst`"" -ForegroundColor White
Write-Host '      }' -ForegroundColor DarkGray
Write-Host '    }' -ForegroundColor DarkGray
Write-Host '  }' -ForegroundColor DarkGray
Write-Host ""
Write-Host "To start the IPC service manually:"
Write-Host "  $ExeDst service" -ForegroundColor White
Write-Host ""
Write-Host "To check the version:"
Write-Host "  $ExeDst version" -ForegroundColor White
