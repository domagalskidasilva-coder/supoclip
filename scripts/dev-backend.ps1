Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot\common.ps1"
Import-SupoClipDotEnv
Set-SupoClipDefaultEnv

if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/"
}

Push-Location (Join-Path $Script:Root "backend")
try {
    uv sync --all-groups
    uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
}
finally {
    Pop-Location
}
