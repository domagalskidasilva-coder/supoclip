Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot\common.ps1"
Import-SupoClipDotEnv
Set-SupoClipDefaultEnv

if (!(Get-Command psql -ErrorAction SilentlyContinue)) {
    throw "psql is required. Install PostgreSQL client tools and make sure psql is on PATH."
}

$databaseUrl = $env:FRONTEND_DATABASE_URL
if (!$databaseUrl -and $env:DATABASE_URL) {
    $databaseUrl = $env:DATABASE_URL -replace "^postgresql\+asyncpg:", "postgresql:"
}

if (!$databaseUrl) {
    $databaseUrl = "postgresql://supoclip:supoclip_password@127.0.0.1:5432/supoclip"
}

psql $databaseUrl -f (Join-Path $Script:Root "init.sql")
