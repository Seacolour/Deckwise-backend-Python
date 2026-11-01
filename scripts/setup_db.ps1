$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & uv run python scripts/setup_db.py
    if ($LASTEXITCODE -ne 0) { throw 'Database setup failed.' }
} finally {
    Pop-Location
}
