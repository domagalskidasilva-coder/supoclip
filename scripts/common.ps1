Set-StrictMode -Version Latest

$Script:Root = Resolve-Path (Join-Path $PSScriptRoot "..")

function Import-SupoClipDotEnv {
    $envPath = Join-Path $Script:Root ".env"
    if (!(Test-Path $envPath)) {
        Write-Warning ".env not found. Copy .env.example to .env and fill provider keys."
        return
    }

    Get-Content $envPath | ForEach-Object {
        if ($_ -match "^\s*#" -or $_ -match "^\s*$") { return }
        if ($_ -match "^\s*([^=]+?)\s*=\s*(.*)\s*$") {
            $name = $Matches[1].Trim()
            $value = $Matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Set-SupoClipDefaultEnv {
    if (!$env:DATABASE_URL) {
        $env:DATABASE_URL = "postgresql+asyncpg://supoclip:supoclip_password@127.0.0.1:5432/supoclip"
    }
    if (!$env:FRONTEND_DATABASE_URL) {
        $env:FRONTEND_DATABASE_URL = "postgresql://supoclip:supoclip_password@127.0.0.1:5432/supoclip"
    }
    if (!$env:REDIS_HOST) { $env:REDIS_HOST = "127.0.0.1" }
    if (!$env:REDIS_PORT) { $env:REDIS_PORT = "6379" }
    if (!$env:TEMP_DIR) { $env:TEMP_DIR = (Join-Path $Script:Root "backend\.tmp") }
    if (!$env:NEXT_PUBLIC_APP_URL) { $env:NEXT_PUBLIC_APP_URL = "http://localhost:3107" }
    if (!$env:NEXT_PUBLIC_API_URL) { $env:NEXT_PUBLIC_API_URL = "http://localhost:8000" }
    if (!$env:BACKEND_INTERNAL_URL) { $env:BACKEND_INTERNAL_URL = "http://localhost:8000" }
    if (!$env:CORS_ORIGINS) {
        $env:CORS_ORIGINS = "http://localhost:3107,http://sp.localhost:3107,http://supoclip.localhost:3107"
    }
    if (!$env:APP_SETTINGS_ENCRYPTION_KEY) {
        $env:APP_SETTINGS_ENCRYPTION_KEY = "supoclip_local_settings_secret_change_me"
    }
}
