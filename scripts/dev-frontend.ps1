Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot\common.ps1"
Import-SupoClipDotEnv
Set-SupoClipDefaultEnv

if (!(Get-Command pnpm.cmd -ErrorAction SilentlyContinue)) {
    throw "pnpm is required. Install it with corepack or npm install -g pnpm."
}

$env:DATABASE_URL = $env:FRONTEND_DATABASE_URL

Push-Location (Join-Path $Script:Root "frontend")
try {
    pnpm.cmd install
    pnpm.cmd dev
}
finally {
    Pop-Location
}
