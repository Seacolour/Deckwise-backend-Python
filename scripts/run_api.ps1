$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & uv run uvicorn app.main:app --reload --no-access-log --log-config logging.json --loop app.db.checkpoint:selector_loop_factory
    if ($LASTEXITCODE -ne 0) { throw 'FastAPI exited with an error.' }
} finally {
    Pop-Location
}
