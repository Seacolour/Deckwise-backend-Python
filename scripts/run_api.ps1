$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & uv run uvicorn app.main:app --reload --no-access-log --log-config logging.json
    if ($LASTEXITCODE -ne 0) { throw 'FastAPI exited with an error.' }
} finally {
    Pop-Location
}
