$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$securePassword = Read-Host 'Local PostgreSQL postgres password' -AsSecureString
$credential = [pscredential]::new('postgres', $securePassword)
$previousPassword = [Environment]::GetEnvironmentVariable('PGPASSWORD', 'Process')
$previousAppEnv = [Environment]::GetEnvironmentVariable('DECKWISE_ENV', 'Process')

try {
    [Environment]::SetEnvironmentVariable('PGPASSWORD', $credential.GetNetworkCredential().Password, 'Process')
    if (-not $previousAppEnv) {
        [Environment]::SetEnvironmentVariable('DECKWISE_ENV', 'dev', 'Process')
    }
    Push-Location $projectRoot
    try {
        & uv run uvicorn app.main:app --reload --no-access-log
        if ($LASTEXITCODE -ne 0) { throw 'FastAPI exited with an error.' }
    } finally {
        Pop-Location
    }
} finally {
    [Environment]::SetEnvironmentVariable('PGPASSWORD', $previousPassword, 'Process')
    [Environment]::SetEnvironmentVariable('DECKWISE_ENV', $previousAppEnv, 'Process')
}
