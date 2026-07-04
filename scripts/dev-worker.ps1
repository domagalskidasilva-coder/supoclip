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
    uv run arq src.workers.tasks.WorkerSettings
}
finally {
    Pop-Location
}
